-- 秘书系统数据表
-- 存储提案、用户偏好、决策日志

BEGIN;

-- 提案表
CREATE TABLE IF NOT EXISTS secretary_proposals (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id TEXT NOT NULL,
    proposal JSONB NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'pending',  -- pending | accepted | dismissed | snoozed | expired
    decision_log JSONB,                              -- 完整决策链日志
    session_id TEXT,                                  -- 关联会话ID
    created_at TIMESTAMPTZ DEFAULT NOW(),
    accepted_at TIMESTAMPTZ,
    dismissed_at TIMESTAMPTZ,
    snoozed_until TIMESTAMPTZ,
    expires_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_sp_user_status ON secretary_proposals(user_id, status);
CREATE INDEX IF NOT EXISTS idx_sp_created ON secretary_proposals(created_at DESC);

-- 用户偏好扩展
-- 在 user_data.metadata JSONB 中增加 secretary_prefs 字段

COMMIT;
