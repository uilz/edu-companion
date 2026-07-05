"""
InterestExplorer 表初始化（供 main.py lifespan 调用）

提供 ensure_interest_tables() — 与 migrate_interest_explorer.py 共享 DDL。
保证:
- 幂等可重复执行
- 不依赖 sys.path 操作
- 启动时自动建表
"""

from __future__ import annotations

import logging

from app.infrastructure.db.database import get_db

logger = logging.getLogger(__name__)


def _get_ddl_statements() -> list[str]:
    return [
        # ── 1. interest_tags ──
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
        """
        CREATE UNIQUE INDEX IF NOT EXISTS uq_tags_user_name_parent
        ON interest_tags(user_id, name, COALESCE(parent_id::text, ''))
        """,

        # ── 2. interest_push_prefs ──
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

        # ── 3. interest_sources ──
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
        """
        CREATE UNIQUE INDEX IF NOT EXISTS uq_sources_system_name
        ON interest_sources(COALESCE(user_id, ''), type, name)
        """,

        # ── 4. interest_push_records ──
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
        """
        CREATE UNIQUE INDEX IF NOT EXISTS uq_push_records_user_url
        ON interest_push_records(user_id, url)
        WHERE url IS NOT NULL
        """,

        # ── 5. interest_feedback ──
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

        # ── 6. interest_weight_adjustments ──
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
        """
        CREATE UNIQUE INDEX IF NOT EXISTS uq_weight_adj_user_tag
        ON interest_weight_adjustments(user_id, tag_id)
        """,

        # ── 6.5 interest_source_subscriptions (用户订阅系统源/自定义源的映射) ──
        # 系统源 (user_id IS NULL) 需要通过订阅表实现 per-user 启用控制
        # 用户私有源 (user_id=xxx) 自动隐式订阅
        """
        CREATE TABLE IF NOT EXISTS interest_source_subscriptions (
            id UUID PRIMARY KEY,
            user_id VARCHAR(64) NOT NULL,
            source_id UUID NOT NULL REFERENCES interest_sources(id) ON DELETE CASCADE,
            enabled BOOLEAN NOT NULL DEFAULT TRUE,
            created_at TIMESTAMP NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMP NOT NULL DEFAULT NOW(),

            CONSTRAINT interest_subs_unique UNIQUE (user_id, source_id)
        )
        """,
        "CREATE INDEX IF NOT EXISTS idx_subs_user_enabled "
        "ON interest_source_subscriptions(user_id, enabled)",
        "CREATE INDEX IF NOT EXISTS idx_subs_source "
        "ON interest_source_subscriptions(source_id)",

        # ── 6.6 interest_fetched_items (抓取缓存：按 source_id 缓存最近条目) ──
        # 用于 trigger_push 时按用户启用的 source 找到候选条目
        # 配合 source_subscriptions 支持系统源 + 用户源统一调度
        """
        CREATE TABLE IF NOT EXISTS interest_fetched_items (
            id UUID PRIMARY KEY,
            source_id UUID NOT NULL REFERENCES interest_sources(id) ON DELETE CASCADE,
            title TEXT NOT NULL,
            url TEXT,
            summary TEXT,
            author TEXT,
            published_at TIMESTAMP,
            fetched_at TIMESTAMP NOT NULL DEFAULT NOW()
        )
        """,
        "CREATE INDEX IF NOT EXISTS idx_fetched_source_time "
        "ON interest_fetched_items(source_id, fetched_at DESC)",
        "CREATE INDEX IF NOT EXISTS idx_fetched_url "
        "ON interest_fetched_items(url) WHERE url IS NOT NULL",

        # ── 7. 触发器 ──
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


def ensure_interest_tables() -> None:
    """幂等建表（在 lifespan 中调用）"""
    db = get_db()
    success = 0
    failed = 0
    for sql in _get_ddl_statements():
        try:
            db.execute(sql)
            success += 1
        except Exception as e:
            failed += 1
            logger.warning("DDL 失败: %s — %s", sql.splitlines()[0][:80], e)
    logger.info(
        "🔍 InterestExplorer 表初始化: %d 成功, %d 失败",
        success, failed,
    )
