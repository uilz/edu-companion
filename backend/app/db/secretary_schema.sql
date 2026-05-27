-- 秘书系统数据表
-- 存储提案、用户偏好、决策日志
--
-- 注意: canonical 表定义在 app/api/secretary.py (inline CREATE) 中，
-- 此文件为参考副本，保持与 secretary.py 一致。

BEGIN;

-- 提案表 (inline schema from secretary.py)
CREATE TABLE IF NOT EXISTS secretary_proposals (
    id              TEXT PRIMARY KEY,
    user_id         TEXT NOT NULL,
    session_id      TEXT,
    emoji           TEXT DEFAULT '💡',
    title           TEXT NOT NULL,
    description     TEXT DEFAULT '',
    action_type     TEXT NOT NULL,
    payload         JSONB DEFAULT '{}',
    priority        INTEGER DEFAULT 3,
    generated_by    TEXT DEFAULT '',
    overrideable    BOOLEAN DEFAULT TRUE,
    status          TEXT DEFAULT 'pending',
    metadata        JSONB DEFAULT '{}',
    snoozed_until   TIMESTAMP,
    created_at      TIMESTAMP DEFAULT NOW(),
    expires_at      TIMESTAMP,
    updated_at      TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_sp_user_status ON secretary_proposals(user_id, status);
CREATE INDEX IF NOT EXISTS idx_sp_created ON secretary_proposals(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_sp_user_priority ON secretary_proposals(user_id, priority DESC);

-- 用户偏好扩展
-- 在 user_data.metadata JSONB 中增加 secretary_prefs 字段

COMMIT;
