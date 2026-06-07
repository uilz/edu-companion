-- 迁移：移除 v7_ 表名前缀
-- 配合 Python 代码中 SQL 引用的同步更新

ALTER TABLE IF EXISTS v7_question_banks     RENAME TO question_banks;
ALTER TABLE IF EXISTS v7_questions          RENAME TO questions;
ALTER TABLE IF EXISTS v7_practice_sessions  RENAME TO practice_sessions;
ALTER TABLE IF EXISTS v7_session_questions  RENAME TO session_questions;
ALTER TABLE IF EXISTS v7_practice_attempts  RENAME TO practice_attempts;
ALTER TABLE IF EXISTS v7_achievements       RENAME TO achievements;

-- 收藏 & 斩题 表
ALTER TABLE IF EXISTS v7_question_favorites RENAME TO question_favorites;
ALTER TABLE IF EXISTS v7_slashed_questions  RENAME TO slashed_questions;

-- 重命名相关索引
ALTER INDEX IF EXISTS idx_v7ach_user  RENAME TO idx_ach_user;
ALTER INDEX IF EXISTS idx_v7qf_user_q RENAME TO idx_qf_user_q;
ALTER INDEX IF EXISTS idx_v7sq_user_q RENAME TO idx_sq_user_q;
ALTER INDEX IF EXISTS idx_v7pa_user_q RENAME TO idx_pa_user_q;
ALTER INDEX IF EXISTS idx_v7pa_wrong  RENAME TO idx_pa_wrong;
