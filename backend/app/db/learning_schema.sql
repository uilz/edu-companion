-- ════════════════════════════════════════════
-- Phase 10 学习增强表
-- user_notes, learning_goals, exploration_projects
-- ════════════════════════════════════════════

-- 1. 用户笔记表
-- 存储高亮、自我解释、反思、标注等所有学生主动加工行为
CREATE TABLE IF NOT EXISTS user_notes (
    id              TEXT PRIMARY KEY,
    user_id         TEXT NOT NULL,
    content         TEXT NOT NULL,               -- 笔记内容
    type            TEXT NOT NULL DEFAULT 'note', -- highlight | explain | reflect | note
    source_text     TEXT DEFAULT '',             -- 原文（高亮/引用时）
    node_ids        JSONB DEFAULT '[]',         -- 关联的知识节点 ID 列表
    message_id      TEXT,                        -- 来源消息 ID
    conversation_id TEXT,                        -- 来源对话 ID
    metadata        JSONB DEFAULT '{}',         -- 额外信息（情绪倾向等）
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_notes_user ON user_notes(user_id);
CREATE INDEX IF NOT EXISTS idx_notes_type ON user_notes(type);
CREATE INDEX IF NOT EXISTS idx_notes_node ON user_notes USING gin(node_ids);
CREATE INDEX IF NOT EXISTS idx_notes_created ON user_notes(created_at DESC);

-- 2. 学习目标表
-- 对关键知识节点手动设定掌握度目标和预计达成时间
CREATE TABLE IF NOT EXISTS learning_goals (
    id              TEXT PRIMARY KEY,
    user_id         TEXT NOT NULL,
    node_id         TEXT NOT NULL,               -- 关联的认知节点
    node_label      TEXT DEFAULT '',             -- 节点名称快照
    target_mastery  DOUBLE PRECISION DEFAULT 0.8, -- 目标掌握度 0-1
    target_date     DATE,                        -- 预计达成日期
    current_mastery DOUBLE PRECISION DEFAULT 0.0, -- 当前掌握度（快照）
    priority        INTEGER DEFAULT 2,           -- 1-5，数字小优先级高
    status          TEXT DEFAULT 'active',        -- active | achieved | paused | abandoned
    notes           TEXT DEFAULT '',
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_goals_user ON learning_goals(user_id);
CREATE INDEX IF NOT EXISTS idx_goals_node ON learning_goals(node_id);
CREATE INDEX IF NOT EXISTS idx_goals_status ON learning_goals(status);

-- 3. 探索项目表
-- 项目式学习入口，链接多个知识点形成跨节点学习任务
CREATE TABLE IF NOT EXISTS exploration_projects (
    id              TEXT PRIMARY KEY,
    user_id         TEXT NOT NULL,
    title           TEXT NOT NULL,
    description     TEXT DEFAULT '',
    goal            TEXT DEFAULT '',              -- 项目目标
    node_ids        JSONB DEFAULT '[]',          -- 关联的知识节点
    prerequisites   JSONB DEFAULT '[]',          -- 前置知识点
    deliverables    JSONB DEFAULT '[]',           -- 交付物/里程碑
    status          TEXT DEFAULT 'suggested',     -- suggested | active | in_progress | completed | archived
    difficulty      DOUBLE PRECISION DEFAULT 0.5,
    estimated_hours DOUBLE PRECISION DEFAULT 2.0,
    source          TEXT DEFAULT 'system',        -- system | user_created
    metadata        JSONB DEFAULT '{}',
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_projects_user ON exploration_projects(user_id);
CREATE INDEX IF NOT EXISTS idx_projects_status ON exploration_projects(status);
CREATE INDEX IF NOT EXISTS idx_projects_node ON exploration_projects USING gin(node_ids);
