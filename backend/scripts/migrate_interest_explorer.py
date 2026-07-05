"""
InterestExplorer 模块数据迁移脚本（ADR 0007）

执行:
    python -m backend.scripts.migrate_interest_explorer

效果:
    1. 新增 interest_tags          (3 层独立标签，主/次权重)
    2. 新增 interest_push_prefs    (推送偏好，可配置频率/时间/比例)
    3. 新增 interest_sources       (信息源，4 种类型 arxiv/biorxiv/rss/atom/opml)
    4. 新增 interest_push_records  (推送历史，链接级别去重)
    5. 新增 interest_feedback      (用户反馈 read/later/dislike/imported)
    6. 新增 interest_weight_adjustments (本地权重调整，不发送到服务端)

关键设计:
    - 不调用 LLM：内容搬运而非生成
    - 链接级别去重（不是 title）
    - 3 层标签 (level 0/1/2)
    - 本地权重：调整表用于本地采样概率调整
    - 严格遵循 data-model.md §1-6

注意:
    - 全部使用 IF NOT EXISTS / CREATE OR REPLACE，可重复执行
    - 唯一约束避免重复 (user_id, name, parent) / (user_id, url) / (user_id, tag_id)
    - CHECK 约束确保字段值在合法范围内
"""

import os
import sys
from pathlib import Path


def main() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    sys.path.insert(0, str(repo_root / "backend"))

    from app.infrastructure.db.database import get_db

    db = get_db()
    cur = db.get_conn().cursor()

    ddl_statements: list[str] = [
        # ── 1. interest_tags (3 层独立标签) ──
        """
        CREATE TABLE IF NOT EXISTS interest_tags (
            id UUID PRIMARY KEY,
            user_id VARCHAR(64) NOT NULL,
            name VARCHAR(128) NOT NULL,
            level SMALLINT NOT NULL DEFAULT 0,
            parent_id UUID REFERENCES interest_tags(id) ON DELETE CASCADE,
            weight SMALLINT NOT NULL DEFAULT 1,
            source VARCHAR(20) NOT NULL,
            source_ref_id VARCHAR(64),
            color VARCHAR(7),
            created_at TIMESTAMP NOT NULL DEFAULT NOW(),

            CONSTRAINT interest_tags_level_check
                CHECK (level BETWEEN 0 AND 2),
            CONSTRAINT interest_tags_weight_check
                CHECK (weight IN (1, 2)),
            CONSTRAINT interest_tags_source_check
                CHECK (source IN ('manual', 'from_knowledge', 'from_reading'))
        )
        """,
        "CREATE INDEX IF NOT EXISTS idx_tags_user_parent ON interest_tags(user_id, parent_id)",
        "CREATE INDEX IF NOT EXISTS idx_tags_user_level ON interest_tags(user_id, level)",
        # 同一用户同一父标签下不允许重名（顶级标签 parent_id IS NULL 通过部分唯一索引处理）
        """
        CREATE UNIQUE INDEX IF NOT EXISTS uq_tags_user_name_parent
        ON interest_tags(user_id, name, COALESCE(parent_id::text, ''))
        """,

        # ── 2. interest_push_prefs (推送偏好) ──
        """
        CREATE TABLE IF NOT EXISTS interest_push_prefs (
            user_id VARCHAR(64) PRIMARY KEY,
            frequency VARCHAR(20) NOT NULL DEFAULT 'daily',
            push_time TIME DEFAULT '08:00:00',
            timezone VARCHAR(64) DEFAULT 'Asia/Shanghai',
            daily_limit INT DEFAULT 6,
            research_object_pct SMALLINT DEFAULT 50,
            research_method_pct SMALLINT DEFAULT 30,
            hot_news_pct SMALLINT DEFAULT 20,
            cross_disciplinary BOOLEAN DEFAULT FALSE,
            retention_days INT DEFAULT 90,
            is_enabled BOOLEAN DEFAULT TRUE,
            created_at TIMESTAMP NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMP NOT NULL DEFAULT NOW(),

            CONSTRAINT interest_push_prefs_freq_check
                CHECK (frequency IN ('daily', 'weekly', 'manual')),
            CONSTRAINT interest_push_prefs_pct_sum_check
                CHECK (research_object_pct + research_method_pct + hot_news_pct = 100),
            CONSTRAINT interest_push_prefs_pct_range_check
                CHECK (
                    research_object_pct BETWEEN 0 AND 100
                    AND research_method_pct BETWEEN 0 AND 100
                    AND hot_news_pct BETWEEN 0 AND 100
                ),
            CONSTRAINT interest_push_prefs_retention_check
                CHECK (retention_days > 0)
        )
        """,

        # ── 3. interest_sources (信息源) ──
        """
        CREATE TABLE IF NOT EXISTS interest_sources (
            id UUID PRIMARY KEY,
            user_id VARCHAR(64),
            name VARCHAR(128) NOT NULL,
            type VARCHAR(20) NOT NULL,
            category VARCHAR(50),
            config JSONB NOT NULL,
            enabled BOOLEAN DEFAULT TRUE,
            is_system BOOLEAN DEFAULT FALSE,
            last_fetched_at TIMESTAMP,
            last_fetch_status VARCHAR(20),
            last_fetch_error TEXT,
            created_at TIMESTAMP NOT NULL DEFAULT NOW(),

            CONSTRAINT interest_sources_type_check
                CHECK (type IN ('arxiv', 'biorxiv', 'rss', 'atom', 'opml', 'internal')),
            CONSTRAINT interest_sources_status_check
                CHECK (last_fetch_status IS NULL OR last_fetch_status IN
                       ('success', 'error', 'rate_limited'))
        )
        """,
        "CREATE INDEX IF NOT EXISTS idx_sources_user ON interest_sources(user_id)",
        "CREATE INDEX IF NOT EXISTS idx_sources_type_enabled ON interest_sources(type, enabled)",
        # 系统内置源 (user_id IS NULL + type + name) 不重复
        """
        CREATE UNIQUE INDEX IF NOT EXISTS uq_sources_system_name
        ON interest_sources(COALESCE(user_id, ''), type, name)
        """,

        # ── 4. interest_push_records (推送历史，链接级别去重) ──
        """
        CREATE TABLE IF NOT EXISTS interest_push_records (
            id UUID PRIMARY KEY,
            user_id VARCHAR(64) NOT NULL,
            source_id UUID REFERENCES interest_sources(id) ON DELETE SET NULL,
            push_type VARCHAR(20) NOT NULL,
            title TEXT NOT NULL,
            summary TEXT,
            url TEXT,
            author TEXT,
            published_at TIMESTAMP,
            matched_tags JSONB DEFAULT '[]',
            generated_at TIMESTAMP NOT NULL DEFAULT NOW(),

            CONSTRAINT interest_push_records_type_check
                CHECK (push_type IN ('research_object', 'research_method', 'hot_news'))
        )
        """,
        "CREATE INDEX IF NOT EXISTS idx_push_records_user_time "
        "ON interest_push_records(user_id, generated_at DESC)",
        "CREATE INDEX IF NOT EXISTS idx_push_records_type "
        "ON interest_push_records(user_id, push_type)",
        "CREATE INDEX IF NOT EXISTS idx_push_records_source "
        "ON interest_push_records(source_id)",
        # 链接级别去重（不是 title 级别）
        """
        CREATE UNIQUE INDEX IF NOT EXISTS uq_push_records_user_url
        ON interest_push_records(user_id, url)
        WHERE url IS NOT NULL
        """,

        # ── 5. interest_feedback (用户反馈) ──
        """
        CREATE TABLE IF NOT EXISTS interest_feedback (
            push_id UUID PRIMARY KEY REFERENCES interest_push_records(id) ON DELETE CASCADE,
            user_id VARCHAR(64) NOT NULL,
            feedback VARCHAR(20) NOT NULL,
            target_module VARCHAR(30),
            target_ref_id VARCHAR(64),
            feedback_at TIMESTAMP NOT NULL DEFAULT NOW(),

            CONSTRAINT interest_feedback_type_check
                CHECK (feedback IN ('read', 'later', 'dislike', 'imported')),
            CONSTRAINT interest_feedback_target_check
                CHECK (
                    target_module IS NULL
                    OR target_module IN (
                        'reading', 'project', 'flashcard',
                        'cognitive_node', 'language_room'
                    )
                )
        )
        """,
        "CREATE INDEX IF NOT EXISTS idx_feedback_user_time "
        "ON interest_feedback(user_id, feedback_at DESC)",
        "CREATE INDEX IF NOT EXISTS idx_feedback_user_type "
        "ON interest_feedback(user_id, feedback)",

        # ── 6. interest_weight_adjustments (本地权重调整) ──
        """
        CREATE TABLE IF NOT EXISTS interest_weight_adjustments (
            id UUID PRIMARY KEY,
            user_id VARCHAR(64) NOT NULL,
            tag_id UUID REFERENCES interest_tags(id) ON DELETE CASCADE,
            dislike_score FLOAT NOT NULL DEFAULT 0,
            adjustment_count INT NOT NULL DEFAULT 0,
            updated_at TIMESTAMP NOT NULL DEFAULT NOW(),

            CONSTRAINT interest_weight_score_check
                CHECK (dislike_score BETWEEN 0 AND 1),
            CONSTRAINT interest_weight_count_check
                CHECK (adjustment_count >= 0)
        )
        """,
        "CREATE INDEX IF NOT EXISTS idx_weight_adj_user "
        "ON interest_weight_adjustments(user_id)",
        "CREATE INDEX IF NOT EXISTS idx_weight_adj_user_tag "
        "ON interest_weight_adjustments(user_id, tag_id)",
        # 同一用户对同一标签只有一条权重调整记录
        """
        CREATE UNIQUE INDEX IF NOT EXISTS uq_weight_adj_user_tag
        ON interest_weight_adjustments(user_id, tag_id)
        """,

        # ── 7. 触发器：自动更新 updated_at ──
        """
        CREATE OR REPLACE FUNCTION interest_updated_at_trigger()
        RETURNS TRIGGER AS $$
        BEGIN
            NEW.updated_at = NOW();
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql
        """,
        """
        DROP TRIGGER IF EXISTS trg_interest_push_prefs_updated ON interest_push_prefs
        """,
        """
        CREATE TRIGGER trg_interest_push_prefs_updated
        BEFORE UPDATE ON interest_push_prefs
        FOR EACH ROW
        EXECUTE FUNCTION interest_updated_at_trigger()
        """,
        """
        DROP TRIGGER IF EXISTS trg_interest_weight_adj_updated ON interest_weight_adjustments
        """,
        """
        CREATE TRIGGER trg_interest_weight_adj_updated
        BEFORE UPDATE ON interest_weight_adjustments
        FOR EACH ROW
        EXECUTE FUNCTION interest_updated_at_trigger()
        """,

        # ── 8. 清理过期推送的存储过程 ──
        """
        CREATE OR REPLACE FUNCTION interest_cleanup_expired(retention_days INT)
        RETURNS INT AS $$
        DECLARE
            deleted_count INT;
        BEGIN
            DELETE FROM interest_push_records
            WHERE generated_at < NOW() - (retention_days || ' days')::INTERVAL;
            GET DIAGNOSTICS deleted_count = ROW_COUNT;
            RETURN deleted_count;
        END;
        $$ LANGUAGE plpgsql
        """,
    ]

    success = 0
    failed = 0
    for sql in ddl_statements:
        try:
            cur.execute(sql)
            success += 1
        except Exception as e:
            failed += 1
            print(f"  ! FAIL: {sql.splitlines()[0][:80]}: {e}")
    cur.connection.commit()
    cur.close()
    db.put_conn(cur.connection)

    print(f"✅ InterestExplorer 迁移完成: {success} 成功, {failed} 失败")
    print(f"   - interest_tags: 3 层独立标签 (主/次权重)")
    print(f"   - interest_push_prefs: 推送偏好 (frequency/time/比例)")
    print(f"   - interest_sources: 信息源 (arxiv/biorxiv/rss/atom/opml/internal)")
    print(f"   - interest_push_records: 推送历史 (链接级别去重)")
    print(f"   - interest_feedback: 用户反馈 (read/later/dislike/imported)")
    print(f"   - interest_weight_adjustments: 本地权重调整")


if __name__ == "__main__":
    main()
