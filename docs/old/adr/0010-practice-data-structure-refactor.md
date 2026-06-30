# ADR 0010: 练习系统底层数据结构重构

> 日期: 2026-06-15 | 状态: Proposed
> Round 2 第一步 — 与开发者 grill-me 7 轮决策产出

---

## 决策清单

### D1. 统一建表管理

砍掉散落在 `database.py` / `question_bank.sql` / 各文件内联 `_ensure_tables()` 的建表逻辑。
**决定**: `practice_schema.sql` 为唯一建表文件, 删除所有内联 `_ensure_tables()`.

### D2. 统一 Pydantic 列名映射

当前 Pydantic (`schemas/practice.py`) 与 DB 列名不一致, 通过 `_row_to_question()` 做转换。
**决定**: Pydantic 直接映射 DB 列名, 删除转换层.

| Pydantic 当前 | DB 当前 | 统一后 |
|---------------|---------|--------|
| `question_id` | `id` | `id` |
| `options` (list[QuestionOption]) | `options_json` (JSONB) | `options` (JSONB, Pydantic 序列化) |
| `correct_answer` | `answer` (JSONB) | `answer` (JSONB) |
| `hints` (list[str]) | `hints_json` (JSONB) | `hints` (JSONB) |
| `explanation` | `analysis` | `explanation` |
| `source` | `source` | 不变 |

### D3. 统一业务查询模型

当前 `practice_session.py` 直接用 DB dict 操作, 不经过 `PracticeSession` Pydantic。
**决定**: 业务层统一用 `PracticeSession` 对象, `session_repository.py` 从 DB 读取后组装, `session_engine.py` 纯函数操作对象属性, `PracticeServiceImpl` 返回 Pydantic 对象.

### D4. 砍 `attempts` 表, 留 `practice_attempts`

双表双写同一笔答题记录。`practice_attempts` 含完整字段 (is_wrong / consecutive_correct / cognitive_node_ids)。
**决定**: 砍 `attempts` 表, 全走 `practice_attempts`. 旧数据直接丢弃(开发阶段).

### D5. 答案统一从 `options[].is_correct` 推导

选择题的 `correct_answer` 和 `options[].is_correct` 语义冗余。
**决定**: 砍 `correct_answer` 字段。选择题答案由 `options` 数组中 `is_correct=True` 的 `letter` 推导。`is_correct` 同时保留错因类型标记。

### D6. 统一 `cognitive_links` 关联表

当前关联 CognitiveNode 的方式碎片化:

| 来源 | 当前方式 | 废弃 |
|------|----------|------|
| questions | `cognitive_node_ids TEXT[]` | ✅ |
| conversation | `conversation_node_links` 表 | ✅ |
| cognitive | `knowledge_edges` 表 (prerequisite/associate) | ✅ |
| cognitive | `cognitive_nodes.prerequisites/unlocks/associates JSONB` | ✅ |
| materials | `material_chunks.skill_ids_json JSONB` | ✅ |

**决定**: 统一为 `cognitive_links` 表:

```sql
CREATE TABLE cognitive_links (
    id          TEXT PRIMARY KEY,
    user_id     TEXT NOT NULL,
    source_type TEXT NOT NULL,  -- 'question' | 'conversation' | 'material_chunk' | 'cognitive_edge'
    source_id   TEXT NOT NULL,
    node_id     TEXT NOT NULL,  -- CognitiveNode.id
    link_type   TEXT NOT NULL,  -- 'belongs_to' | 'prerequisite' | 'associate' | 'unlocks'
    weight      FLOAT DEFAULT 1.0,
    metadata    JSONB DEFAULT '{}',
    created_at  TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX idx_cl_source ON cognitive_links(source_type, source_id);
CREATE INDEX idx_cl_node ON cognitive_links(node_id);
CREATE INDEX idx_cl_type ON cognitive_links(link_type);
```

### D7. 统一知识源为 CognitiveNode.Belief

当前 `KnowledgeState` (BKT 四参数 p_known/p_learned/p_guess/p_slip) 与 `CognitiveNode.Belief` (Beta 分布 α/β) 共存。
**决定**: 砍 `KnowledgeState` (Pydantic 模型保留为 DTO, BKT 参数全部删除). 练习系统从 `CognitiveNode.Belief.proficiency_mean` 读取掌握度.

### D8. `error_book` 改为聚合缓存

当前 `error_book` 独立接收 submit_answer 写入, 与 `practice_attempts` 双写。
**决定**: `error_book` 保留作为缓存表, 但数据来源改为从 `practice_attempts` 聚合后异步写入. `submit_answer` 不再直接写 `error_book`.

### D9. `session_questions` 无状态化

`session_questions.user_answer / is_correct / time_spent` 与 `practice_attempts` 重复。
**决定**: 删除 `session_questions` 的答题状态字段, 仅保留 `session_id / question_id / sort_order / question_type / bloom_level / difficulty`. 答题状态从 `practice_attempts` 聚合.

### D10. 砍 `questions.skill_id`

Q8 的 `cognitive_links` 表统一后, `skill_id` 完全冗余 (link_type='belongs_to' 表达主知识点).
**决定**: 砍 `questions.skill_id`. 主知识点由 `cognitive_links WHERE source_type='question' AND link_type='belongs_to'` 推导.

### D11. 砍 `questions.cognitive_node_ids TEXT[]`

同上, Q6 已覆盖。
**决定**: 删除该列, 全走 `cognitive_links`.

### D12. `practice_sessions` 保留统计缓存

`question_ids_json` 完全冗余 (session_questions 可推导), 但 `correct_count/wrong_count/score` 避免每次查会话都要聚合 practice_attempts。
**决定**: 砍 `question_ids_json`. 保留 `correct_count/wrong_count/score` 为缓存字段, 由 session 完成时从 practice_attempts 聚合写入.

---

## 废弃与保留总结

| 废弃 | 替换方案 |
|------|----------|
| `attempts` 表 | `practice_attempts` (唯一) |
| `error_book` 独立写入 | `error_book` 聚合缓存 (只读) |
| `questions.cognitive_node_ids` | `cognitive_links(source_type='question')` |
| `questions.correct_answer` | `options[].is_correct` 推导 |
| `questions.skill_id` | `cognitive_links(link_type='belongs_to')` |
| `conversation_node_links` 表 | `cognitive_links(source_type='conversation')` |
| `knowledge_edges` 表 | `cognitive_links(link_type='prerequisite'/'associate')` |
| `session_questions.user_answer/is_correct/time_spent` | `practice_attempts` 聚合 |
| `KnowledgeState` BKT 参数 | `CognitiveNode.Belief` (唯一权威源) |
| `practice_sessions.question_ids_json` | `session_questions` 排序蓝图 |
| 内联 `_ensure_tables()` | `practice_schema.sql` |
| Pydantic→DB 转换层 (`_row_to_question`) | 直接列名映射 |

| 保留 | 理由 |
|------|------|
| `practice_attempts` | 答题记录主表 (含错因分析) |
| `session_questions` | 会话题目排序蓝图 (无状态) |
| `error_book` | 看板缓存 (只读聚合) |
| `practice_sessions.correct_count/wrong_count/score` | 统计缓存 |

---

### D13. 统一 `question_user_flags` 表

`question_favorites` 和 `slashed_questions` 两张表结构完全相同 (user_id + question_id 映射).
**决定**: 合并为 `question_user_flags(question_id, user_id, flag_type)` 表, 其中 `flag_type` = `'favorite'` | `'slashed'`.

### D14. `explain_cards` 归入对话系统, 嵌入消息元数据

当前 `explain_cards` 独立表 (响应对话中选中文本生成解释卡片), 属于对话系统的标注能力.
**决定**: 砍 `explain_cards` 独立表。卡片数据嵌入 `messages` 表的 `content_blocks` 或 `metadata` JSONB 中, 与消息同生命周期.

### D15. 全拆 `conversation_user_meta` 巨型 JSONB

当前 `conversation_user_meta` 单行 JSONB 存放目录树/消息/文件/秘书偏好/策略记忆/后台任务等多个领域的数据.
**决定**: 全部拆为独立关系表:

| 当前 JSONB 字段 | 目标 |
|-----------------|------|
| `directory_nodes` | 已有 `directory_schema.sql` (目录节点表) |
| `nodes` / `messages` | **新建** `messages` 表 |
| `response_blocks` | 嵌入 `messages.content_blocks` JSONB |
| `link_nodes` | 统一 `cognitive_links` 表 (D6) |
| `files` | 已有 `materials` 表 |
| `secretary_prefs` | 统一 `user_settings` 表 (D16) |
| `policy_memory` | 统一 `user_settings` 表 (D16) |
| `background_jobs` | 纯内存 (D17) |
| `partitions/domains/topics/conversations/event_log` | 废弃删除 |

### D16. 统一 `user_settings` 表

用户配置散落三处: `conversation_user_meta.secretary_prefs` JSONB / `conversation_user_meta.policy_memory` JSONB / `user_llm_configs` 表 / UI 偏好 localStorage.
**决定**: 统一 `user_settings(user_id, settings_jsonb)` 表, 所有用户级配置 (LLM 配置/秘书偏好/策略记忆/UI 偏好) 集中到此表.

### D17. `background_jobs` 纯内存 + 审计兜底

`BackgroundJob` 是临时运行时状态 (跟踪 LLM 工具异步执行进度), 持久化到 PG 不合理.
**决定**: 砍 PG 存储, `BackgroundJobManager._jobs` 纯内存 dict. Job 完成后写 `events` 表做审计 (event_type='background_job_done'). 服务重启丢失的 job 由前端 SSE 重连重试.

### D18. `messages` 独立表

`conversation_user_meta.nodes/messages` JSONB dict → `messages` 关系表:

```sql
CREATE TABLE messages (
    id              TEXT PRIMARY KEY,
    user_id         TEXT NOT NULL,
    directory_id    TEXT NOT NULL,       -- 所属目录节点 (conv)
    role            TEXT NOT NULL,       -- user | assistant | system
    content         TEXT DEFAULT '',
    content_blocks  JSONB DEFAULT '[]',  -- [TextBlock, ImageBlock, PracticeBlock, ...]
    text_summary    TEXT DEFAULT '',
    parent_id       TEXT,
    children_ids    TEXT[] DEFAULT '{}',
    timestamp       DOUBLE PRECISION DEFAULT 0,
    token_count     INTEGER DEFAULT 0,
    version         INTEGER DEFAULT 1,
    is_deleted      BOOLEAN DEFAULT FALSE,
    agent_label     TEXT DEFAULT '',
    metadata        JSONB DEFAULT '{}',
    created_at      TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX idx_messages_dir ON messages(directory_id);
CREATE INDEX idx_messages_user ON messages(user_id);
CREATE INDEX idx_messages_parent ON messages(parent_id);
```

注意: `content_blocks` 统一存储用户消息 (TextBlock/ImageBlock 等) 和 AI 回复块 (PracticeBlock/MindMapBlock/VideoBlock 等), 按数组顺序渲染, 不再有独立的 `response_blocks`.

---

## 废弃与保留总结 (完整版)

### 废弃

| 数据源 | 替换方案 |
|--------|----------|
| `attempts` 表 | `practice_attempts` (唯一) |
| `error_book` 独立写入 | `error_book` 聚合缓存 (只读) |
| `questions.cognitive_node_ids` | `cognitive_links(source_type='question')` |
| `questions.correct_answer` | `options[].is_correct` 推导 |
| `questions.skill_id` | `cognitive_links(link_type='belongs_to')` |
| `conversation_node_links` 表 | `cognitive_links(source_type='conversation')` |
| `knowledge_edges` 表 | `cognitive_links(link_type='prerequisite'/'associate')` |
| `cognitive_nodes.prerequisites/unlocks/associates JSONB` | `cognitive_links(link_type='...')` |
| `session_questions.user_answer/is_correct/time_spent` | `practice_attempts` 聚合 |
| `KnowledgeState` BKT 参数 | `CognitiveNode.Belief` (唯一权威源) |
| `practice_sessions.question_ids_json` | `session_questions` 排序蓝图 |
| `question_favorites` 表 | `question_user_flags(flag_type='favorite')` |
| `slashed_questions` 表 | `question_user_flags(flag_type='slashed')` |
| `explain_cards` 表 | 嵌入 `messages.content_blocks` |
| `conversation_user_meta` JSONB | 拆为 5+ 张表和废弃 |
| `material_chunks.skill_ids_json` | `cognitive_links(source_type='material_chunk')` |
| `conversation_user_meta.background_jobs` | 纯内存 + events 审计 |
| 内联 `_ensure_tables()` | 统一 `practice_schema.sql` |
| Pydantic→DB 转换层 (`_row_to_question`) | 直接列名映射 |

### 保留

| 数据源 | 理由 |
|--------|------|
| `practice_attempts` | 答题记录主表 (含错因分析) |
| `session_questions` | 会题目排序蓝图 (无状态) |
| `error_book` | 看板缓存 (只读聚合) |
| `practice_sessions.correct_count/wrong_count/score` | 统计缓存 |
| `messages` 表 | 消息持久化 (新建) |
| `user_settings` 表 | 用户配置统一存储 (新建) |
| `question_user_flags` 表 | 题目用户标记 (新建) |
| `cognitive_links` 表 | 统一关联 (新建) |
| `events` 表 | 审计日志 (已有) |

### 影响范围

| 领域 | 文件数 | 说明 |
|------|--------|------|
| 练习建表 | ~8 文件 | 删除 `_ensure_tables()`, 合并 `practice_schema.sql` |
| Pydantic 重构 | 1 文件 | `schemas/practice.py` |
| 练习业务层 | ~15 文件 | 统一 Pydantic 对象, 去 dict |
| 关联查询 | ~10 文件 | cognitive_node_ids → JOIN cognitive_links |
| 知识状态查询 | ~5 文件 | shared/knowledge_trace.py 简化为直读 |
| error_book | ~3 文件 | 改为聚合写入 |
| 删除旧表 | ~5 文件 | attempts/conversation_node_links/knowledge_edges/... 清理 |
| 对话存储重构 | ~10 文件 | conversation_user_meta 拆表, messages 独立 |
| 用户配置重构 | ~5 文件 | user_settings 统一 |
| background_jobs | ~3 文件 | 去持久化, 纯内存 |
| 标记合并 | ~4 文件 | 合为 question_user_flags |
