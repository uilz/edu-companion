# Phase 6 实施计划

## 总体结构

```
backend/app/
├── cognitive/                    ← 新增
│   ├── models.py                 CognitiveNode Pydantic 模型
│   ├── events.py                 事件处理器 (practice/diagnostic/dialogue)
│   ├── equations.py              数学方程 (激活/信念/遗忘/趋势/疲劳/调度)
│   └── constants.py              全局参数默认值
│
├── api/
│   └── cognitive.py              新增 API 端点
│
├── db/
│   └── schema_cognitive.sql      PG 建表 DDL
│
└── services/
    ├── pg_storage.py             扩展：读写 cognitive_nodes
    └── ...                       现有文件不变
```

## 6.1 PG 表

```sql
-- 节点表：每行一个 CognitiveNode，JSONB 存储全部子系统
CREATE TABLE cognitive_nodes (
  id           TEXT PRIMARY KEY,      -- "math.analysis.derivative.chain_rule"
  user_id      TEXT NOT NULL,         -- 多用户支持
  level        TEXT NOT NULL,         -- partition|domain|topic|concept|atom
  parent_id    TEXT,                  -- 父节点 ID
  children     TEXT[] DEFAULT '{}',
  is_core      BOOLEAN DEFAULT false,

  -- 认知状态全部在 JSONB 中
  activation   JSONB,
  belief       JSONB,
  trend        JSONB,
  scheduling   JSONB,
  dialogue_contexts JSONB DEFAULT '[]',
  practice_summary  JSONB,
  error_clusters    JSONB DEFAULT '[]',
  cognitive_load    JSONB,
  metacognition     JSONB,
  engagement        JSONB,
  composition       JSONB,
  deep_links        JSONB DEFAULT '[]',
  goal_alignment    JSONB,
  diagnostic        JSONB,
  param_refs        JSONB,

  -- 事件: 最多50条练习事件
  practice_events   JSONB DEFAULT '[]',

  -- 图谱
  prerequisites     JSONB DEFAULT '[]',
  unlocks           JSONB DEFAULT '[]',
  associates        JSONB DEFAULT '[]',

  meta JSONB DEFAULT '{}',

  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- 事件表
CREATE TABLE cognitive_events (
  event_id    TEXT PRIMARY KEY,
  event_type  TEXT NOT NULL,          -- practice_response|diagnostic_result|...
  user_id     TEXT NOT NULL,
  node_id     TEXT,
  timestamp   TIMESTAMPTZ NOT NULL,
  payload     JSONB NOT NULL,
  processed   BOOLEAN DEFAULT false,
  created_at  TIMESTAMPTZ DEFAULT NOW()
);
```

## 6.2 CognitiveNode 模型

按 v2.10 文档创建，用 Python Pydantic 嵌套结构：

```python
# 核心
class CognitiveNode(BaseModel):
    id: str
    label: str
    level: str  # partition|domain|topic|concept|atom
    parent: str | None
    children: list[str] = []
    is_core: bool = False

    # 15 个子系统（见文档）
    activation: Activation | None = None
    belief: Belief | None = None
    trend: Trend | None = None
    scheduling: Scheduling | None = None
    dialogue_contexts: list[DialogueContext] = []
    practice_summary: PracticeSummary | None = None
    error_clusters: list[ErrorCluster] = []
    cognitive_load: CognitiveLoad | None = None
    metacognition: Metacognition | None = None
    engagement: Engagement | None = None
    composition: Composition | None = None
    deep_links: list[DeepLink] = []
    goal_alignment: GoalAlignment | None = None
    diagnostic: Diagnostic | None = None
    prediction: Prediction | None = None
    deep_processing: DeepProcessing | None = None

    # 图谱
    prerequisites: list[Prerequisite] = []
    unlocks: list[Unlock] = []
    associates: list[Associate] = []

    # 练习事件（最多50条）
    practice_events: list[PracticeEvent] = []

    # 参数引用
    param_refs: dict[str, str] = {}

    meta: MetaInfo = MetaInfo()
```

## 6.3 数学方程

按文档 4.1~4.6 节实现为纯函数：

| 方程 | Python 函数 | 用途 |
|------|------------|------|
| 4.1 激活 | `calc_activation(node, now)` | ACT-R base_level + spread |
| 4.2 遗忘 | `decay_belief(belief, dt, d)` | α/β 同比例衰减 |
| 4.3 聚合 | `aggregate_children(children_nodes)` | parent 掌握度 |
| 4.4 压缩 | `update_decayed_count(old, dt, d)` | 递推 |
| 4.5 趋势 | `update_trend(trend, new_mu, dt)` | 速度/停滞/波动 |
| 4.6 疲劳 | `calc_fatigue(fatigue, dt, count)` | 会话疲劳 |

## 6.4 事件处理

### `handle_practice_response` (18步)

```python
async def handle_practice_response(event):
    1. load_node + user_state
    2. 会话管理（1h超时→新session）
    3. 趋势预处理（速度衰减+时间累积）
    4. 遗忘衰减
    5. 快速重学检查（条件+冷却）
    6. 信念更新（Beta融合）
    7. 更新趋势（速度/停滞/波动）
    8. 更新练习历史（追加+裁剪+summary）
    9. 重新计算激活（base_level + spread）
    10. 更新认知负荷（前置掌握→dynamic）
    11. 预测误差检测
    12. 异步通知父节点（dirty标记）
    13. 更新激励（XP + streak）
    14. 更新错误簇（embedding匹配）
    15. 更新Chunk形成
    16. 检查解锁（gate缓存）
    17. 调度决策（urgency评分）
    18. 保存节点（乐观锁）
```

### `handle_diagnostic_result` (7步)

```python
async def handle_diagnostic_result(event):
    1. 清空练习历史+重置decayed_count
    2. 重置趋势+Chunk
    3. 计算 α/β from diagnostic_precision
    4. 设置 peak_proficiency
    5. base_level 缓存
    6. 标记 diagnostic 字段
    7. 保存节点
```

### `handle_dialogue_context_update` (4步)

```python
async def handle_dialogue_context_update(event):
    1. load_node
    2. 匹配/追加 dialogue_contexts 条目
    3. 裁剪≤5条
    4. 保存节点
```

## 6.5 对话联动

```python
# conversation_llm.py — AI回复完成后
async def _annotate_dialogue_context(node, reply_text):
    """识别回复涉及的知识点 → dialogue_context_update"""
    skill_ids = extract_skill_ids(reply_text)  # 现有 discussed_skill_ids 逻辑
    for sid in skill_ids:
        await handle_dialogue_context_update(Event(
            type="dialogue_context_update",
            node_id=sid,
            payload={
                "session_id": node.conversation_id,
                "branch_id": node.branch_id,
                "version": current_version,
                "context_type": "upper",  # 用户消息=upper, AI回复=lower
                "relevance_score": calc_relevance(sid, node),
                "summary_text": summarize_context(node, sid),
            }
        ))
```

## 6.6 迁移

```sql
-- knowledge_states → cognitive_nodes (旧BKT转Beta分布)
INSERT INTO cognitive_nodes (id, user_id, level, belief, practice_summary)
SELECT
  skill_id,
  user_id,
  'atom',
  jsonb_build_object(
    'alpha', GREATEST(p_known * 10, 2.0),
    'beta', GREATEST((1-p_known) * 10, 2.0),
    'proficiency_mean', p_known,
    'proficiency_precision', p_known * (1-p_known) * 40 + 4,
    'peak_proficiency', p_known,
    'last_updated', extract(epoch from COALESCE(last_updated, now()))
  ),
  jsonb_build_object(
    'total_attempts', attempt_count,
    'recent_success_rate_7d', CASE WHEN attempt_count > 0
      THEN correct_count::float / attempt_count ELSE 0 END,
    'decayed_event_count', attempt_count
  )
FROM knowledge_states;
```

## 6.7 实施顺序

```
Week 1:  6.1 Pydantic 模型 + 常量 + 方程纯函数
Week 2:  6.2 PG 表 + pg_storage 读写扩展
Week 3:  6.3 事件处理器 (practice/diagnostic/dialogue)
Week 4:  6.4 对话联动 + 迁移脚本 + 清理
```

## 6.8 风险

| 风险 | 缓解 |
|------|------|
| CognitiveNode 数据量大（15子系统×500节点=~5KB/节点）| JSONB 压缩，索引仅 id/parent/scheduling.next_review |
| 对话联动实时性 | dialogue_context_update 异步，非阻塞 |
| 旧数据迁移精度 | Beta 参数从 BKT 近似映射（文档 6.6 公式），可接受 |
| 乐观锁冲突 | meta.version + 重试策略 |
