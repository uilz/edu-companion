"""
MoodStress 模块数据迁移脚本（ADR 0005）

执行:
    python -m backend.scripts.migrate_mood_stress

效果:
    1. 扩展 emotion_records 表 (添加 source / pressure_score / energy_score / text_note / related_event_ids)
    2. 新增 mood_stress_prefs (用户偏好)
    3. 新增 mood_stress_intervention_logs (干预日志)
    4. 新增 mood_stress_rules (用户规则)
    5. 新增 behavior_signals (行为信号缓存)

注意:
    - 全部使用 IF NOT EXISTS / ADD COLUMN IF NOT EXISTS, 可重复执行
    - 写入 scripts/schema_ddl.sql 后即可在 ensure_all_tables 体系中管理
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
        # ── 1. 扩展 emotion_records ──
        """
        CREATE TABLE IF NOT EXISTS emotion_records (
            id UUID PRIMARY KEY,
            user_id VARCHAR(64) NOT NULL,
            source VARCHAR(10) NOT NULL DEFAULT 'auto',
            emotion_tags JSONB DEFAULT '[]',
            pressure_score SMALLINT,
            energy_score SMALLINT,
            text_note TEXT,
            related_event_ids JSONB DEFAULT '[]',
            created_at TIMESTAMP NOT NULL DEFAULT NOW(),
            CONSTRAINT emotion_records_source_check
                CHECK (source IN ('manual', 'auto'))
        )
        """,
        "CREATE INDEX IF NOT EXISTS idx_emotion_user_time ON emotion_records(user_id, created_at DESC)",
        "CREATE INDEX IF NOT EXISTS idx_emotion_source ON emotion_records(user_id, source)",

        # 兼容已存在的 emotion_records（只缺列时补全）
        "ALTER TABLE emotion_records ADD COLUMN IF NOT EXISTS source VARCHAR(10) DEFAULT 'auto'",
        "ALTER TABLE emotion_records ADD COLUMN IF NOT EXISTS emotion_tags JSONB DEFAULT '[]'",
        "ALTER TABLE emotion_records ADD COLUMN IF NOT EXISTS pressure_score SMALLINT",
        "ALTER TABLE emotion_records ADD COLUMN IF NOT EXISTS energy_score SMALLINT",
        "ALTER TABLE emotion_records ADD COLUMN IF NOT EXISTS text_note TEXT",
        "ALTER TABLE emotion_records ADD COLUMN IF NOT EXISTS related_event_ids JSONB DEFAULT '[]'",
        "ALTER TABLE emotion_records DROP CONSTRAINT IF EXISTS emotion_records_source_check",
        """
        ALTER TABLE emotion_records
        ADD CONSTRAINT emotion_records_source_check
        CHECK (source IN ('manual', 'auto'))
        """,
        """
        ALTER TABLE emotion_records
        DROP CONSTRAINT IF EXISTS emotion_records_pressure_check
        """,
        """
        ALTER TABLE emotion_records
        ADD CONSTRAINT emotion_records_pressure_check
        CHECK (pressure_score IS NULL OR pressure_score BETWEEN 1 AND 10)
        """,
        """
        ALTER TABLE emotion_records
        DROP CONSTRAINT IF EXISTS emotion_records_energy_check
        """,
        """
        ALTER TABLE emotion_records
        ADD CONSTRAINT emotion_records_energy_check
        CHECK (energy_score IS NULL OR energy_score BETWEEN 1 AND 10)
        """,

        # ── 2. mood_stress_prefs ──
        """
        CREATE TABLE IF NOT EXISTS mood_stress_prefs (
            user_id VARCHAR(64) PRIMARY KEY,
            reminder_enabled BOOLEAN DEFAULT FALSE,
            reminder_frequency VARCHAR(20),
            reminder_time TIME,
            data_retention_days INT DEFAULT 90,
            auto_collect_task_switch BOOLEAN DEFAULT TRUE,
            auto_collect_stay_duration BOOLEAN DEFAULT TRUE,
            auto_collect_error_rate BOOLEAN DEFAULT TRUE,
            auto_collect_undo BOOLEAN DEFAULT TRUE,
            auto_collect_session_anomaly BOOLEAN DEFAULT TRUE,
            auto_collect_flashcard_failure BOOLEAN DEFAULT TRUE,
            auto_collect_voice_features BOOLEAN DEFAULT FALSE,
            output_to_planning BOOLEAN DEFAULT TRUE,
            output_to_conversation BOOLEAN DEFAULT TRUE,
            output_to_language_room BOOLEAN DEFAULT TRUE,
            knowledge_breathing_excluded_node_ids JSONB DEFAULT '[]',
            environment_theme VARCHAR(20) DEFAULT 'default',
            environment_sound VARCHAR(20) DEFAULT 'none',
            planning_rules JSONB DEFAULT '{}',
            created_at TIMESTAMP NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMP NOT NULL DEFAULT NOW()
        )
        """,

        # ── 3. intervention_logs ──
        """
        CREATE TABLE IF NOT EXISTS mood_stress_intervention_logs (
            id UUID PRIMARY KEY,
            user_id VARCHAR(64) NOT NULL,
            intervention_type VARCHAR(30) NOT NULL,
            duration_seconds INT,
            trigger_event VARCHAR(50),
            notes TEXT,
            created_at TIMESTAMP NOT NULL DEFAULT NOW(),
            CONSTRAINT mood_stress_intervention_type_check
                CHECK (intervention_type IN (
                    'breathing', 'knowledge_breathing',
                    'cognitive_reappraisal', 'environment'
                ))
        )
        """,
        "CREATE INDEX IF NOT EXISTS idx_intervention_user_time "
        "ON mood_stress_intervention_logs(user_id, created_at DESC)",

        # ── 4. mood_stress_rules ──
        """
        CREATE TABLE IF NOT EXISTS mood_stress_rules (
            id UUID PRIMARY KEY,
            user_id VARCHAR(64) NOT NULL,
            rule_name TEXT NOT NULL,
            trigger_metric VARCHAR(30) NOT NULL,
            trigger_operator VARCHAR(10) NOT NULL,
            trigger_value JSONB NOT NULL,
            action VARCHAR(30) NOT NULL,
            is_enabled BOOLEAN DEFAULT TRUE,
            created_at TIMESTAMP NOT NULL DEFAULT NOW()
        )
        """,
        "CREATE INDEX IF NOT EXISTS idx_rules_user "
        "ON mood_stress_rules(user_id, is_enabled)",

        # ── 5. behavior_signals ──
        """
        CREATE TABLE IF NOT EXISTS behavior_signals (
            id UUID PRIMARY KEY,
            user_id VARCHAR(64) NOT NULL,
            signal_type VARCHAR(50) NOT NULL,
            signal_data JSONB NOT NULL,
            severity SMALLINT DEFAULT 1,
            is_read BOOLEAN DEFAULT FALSE,
            created_at TIMESTAMP NOT NULL DEFAULT NOW(),
            CONSTRAINT behavior_signals_severity_check
                CHECK (severity BETWEEN 1 AND 3)
        )
        """,
        "CREATE INDEX IF NOT EXISTS idx_signals_user_time "
        "ON behavior_signals(user_id, created_at DESC)",
        "CREATE INDEX IF NOT EXISTS idx_signals_unread "
        "ON behavior_signals(user_id, is_read) WHERE is_read = FALSE",
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

    print(f"✅ MoodStress 迁移完成: {success} 成功, {failed} 失败")


if __name__ == "__main__":
    main()
