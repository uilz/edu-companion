-- 秘书系统数据表 — DEPRECATED
-- 存储提案、用户偏好、决策日志
--
-- ⚠️ secretary_proposals 表定义已统一至 app/api/secretary.py (_ensure_db_schema)。
-- 本文件中的表定义已注释掉，不再由应用直接执行。
-- 如需修改表结构，请修改 secretary.py 中的 inline CREATE TABLE。

BEGIN;

-- [DEPRECATED] secretary_proposals 表定义已移至 app/api/secretary.py (_ensure_db_schema)
-- 此处保留注释以作历史参考。canonical 版本: secretary.py inline CREATE TABLE。
-- 如需修改表结构，请仅修改 secretary.py 中的定义。
--
-- CREATE TABLE IF NOT EXISTS secretary_proposals (
--     id              TEXT PRIMARY KEY,
--     user_id         TEXT NOT NULL,
--     session_id      TEXT,
--     emoji           TEXT DEFAULT '💡',
--     title           TEXT NOT NULL,
--     description     TEXT DEFAULT '',
--     action_type     TEXT NOT NULL,
--     payload         JSONB DEFAULT '{}',
--     priority        INTEGER DEFAULT 3,
--     generated_by    TEXT DEFAULT '',
--     overrideable    BOOLEAN DEFAULT TRUE,
--     status          TEXT DEFAULT 'pending',
--     metadata        JSONB DEFAULT '{}',
--     snoozed_until   TIMESTAMP,
--     created_at      TIMESTAMP DEFAULT NOW(),
--     expires_at      TIMESTAMP,
--     updated_at      TIMESTAMP DEFAULT NOW()
-- );
--
-- CREATE INDEX IF NOT EXISTS idx_sp_user_status ON secretary_proposals(user_id, status);
-- CREATE INDEX IF NOT EXISTS idx_sp_created ON secretary_proposals(created_at DESC);
-- CREATE INDEX IF NOT EXISTS idx_sp_user_priority ON secretary_proposals(user_id, priority DESC);

-- 用户偏好扩展
-- 在 user_data.metadata JSONB 中增加 secretary_prefs 字段

COMMIT;
