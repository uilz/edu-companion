# 事件层次聚合系统 — 设计文档

> 版本: 1.0 (最终) | 日期: 2026-06-22 | 状态: 待实现

## 一、解决的问题

当前 EventStore v2 将所有事件平铺存储，EventAggregator 做了一级聚合,但存在：

1. **聚合后原始事件仍独立** — 没有"折叠"关系，视图上两者同级
2. **聚合维度单一** — 只按 event_type，无法跨类型/跨主题
3. **无层级** — 聚合结果不能再被聚合
4. **AI 无法区分"原始"和"聚合"** — 查询时混在一起

## 二、核心概念

### 2.1 三个分离的概念

```
事件类型(event_type)  ≠  聚合维度(dimension)  ≠  时间窗口(window_minutes)

event_type  =  EpisodeDigest | TopicDigest | TypeDigest    (粒度:3种)
dimension   =  mixed | topic | type                         (粒度:3种)
window_minutes = 5 | 30 | 60 | 1440 | 10080 | 43200        (粒度:6种)
```

| 概念 | 存放位置 | 可选值 |
|------|---------|--------|
| **事件类型** | `event_type` | `EpisodeDigest` / `TopicDigest` / `TypeDigest` |
| **聚合维度** | `payload.dimension` | `mixed` / `topic` / `type` |
| **时间窗口** | `payload.window_minutes` | 5 / 30 / 60 / 1440(日) / 10080(周) / 43200(月) |
| **来源** | `source_type` | `aggregator` |
| **主题标签** | `payload.topic_label` | 仅 topic 维度，如 `"三角函数"` |

### 2.2 三个聚合维度

| 维度 | 分组依据 | 产出 event_type | 说明 |
|------|---------|----------------|------|
| `mixed` | 时间窗口内所有事件 | `EpisodeDigest` | 混合类型，形成"学习片段" |
| `topic` | 事件涉及的知识主题 | `TopicDigest` | 按知识点主题聚类 |
| `type` | 事件的 event_type | `TypeDigest` | 按事件类型分组 |

### 2.3 时间窗口体系

| 窗口 | 名称 | window_minutes |
|------|------|----------------|
| 5 min | 微片段 | 5 |
| 30 min | 短片段 | 30 |
| 1 h | 中片段 | 60 |
| 1 day | 日总结 | 1440 |
| 7 day | 周总结 | 10080 |
| 30 day | 月总结 | 43200 |

### 2.4 聚合矩阵

每个 (dimension × window_minutes) 是一个潜在聚合节点。
条件：该窗口+维度内有 ≥ 1 个无父事件。

```
dimension →  mixed        topic:三角函数  topic:函数图像  type:AnswerSubmitted
window    ────────────────────────────────────────────────────────────────────
5m         EpisodeDigest   TopicDigest     TopicDigest     TypeDigest
30m        EpisodeDigest   TopicDigest     TopicDigest     TypeDigest
1h         EpisodeDigest   TopicDigest     TopicDigest     TypeDigest
day        EpisodeDigest   TopicDigest     TopicDigest     TypeDigest
week       EpisodeDigest   TopicDigest     TopicDigest     TypeDigest
month      EpisodeDigest   TopicDigest     TopicDigest     TypeDigest
```

同一列内维度一致，事件类型一致，窗口递增 → 层层聚合。

### 2.5 事件关系 DAG

```
                        DailyDigest
                      ↗     ↑        ↖
            EpisodeDigest  TopicDigest  TypeDigest
            (1h,mixed)   (topic:三角函数) (type:AnswerSubmitted)
              ↗              ↑               ↑
          EpisodeDigest   TopicDigest     TypeDigest
          (30m,mixed)    (topic:三角函数)  (type:AnswerSubmitted)
            ↗                ↑               ↑
        EpisodeDigest   TopicDigest     TypeDigest
        (5m,mixed)     (topic:三角函数)  (type:AnswerSubmitted)
            ↑                ↑               ↑
      [AnswerSubmitted(三角函数)]  ← 原始事件，3 条聚合路径
```

### 2.6 多父多子含义

一条 `AnswerSubmitted(三角函数, 9:02)` 同时参与 3 条聚合链：

- **mixed 链**: `EpisodeDigest(5m)` → `EpisodeDigest(30m)` → `EpisodeDigest(1h)` → `EpisodeDigest(day)`
- **topic 链**: `TopicDigest(5m,三角函数)` → `TopicDigest(30m,三角函数)` → `TopicDigest(1h,三角函数)` → `TopicDigest(day,三角函数)`
- **type 链**: `TypeDigest(5m,AnswerSubmitted)` → `TypeDigest(30m,AnswerSubmitted)` → `TypeDigest(1h,AnswerSubmitted)` → `TypeDigest(day,AnswerSubmitted)`

每个维度的聚合在同一时间窗口层汇聚到同一个更高层父节点（如 DailyDigest）。

## 三、数据模型

### 3.1 event_relations 表

```sql
CREATE TABLE IF NOT EXISTS event_relations (
    id              TEXT PRIMARY KEY,
    parent_id       TEXT NOT NULL,        -- 聚合事件ID (event_type ∈ {EpisodeDigest,TopicDigest,TypeDigest})
    child_id        TEXT NOT NULL,        -- 子事件ID (原始或下层聚合)
    created_at      TIMESTAMPTZ DEFAULT NOW(),

    UNIQUE(parent_id, child_id),
    FOREIGN KEY (parent_id) REFERENCES events(id) ON DELETE CASCADE,
    FOREIGN KEY (child_id) REFERENCES events(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_er_parent ON event_relations(parent_id);
CREATE INDEX IF NOT EXISTS idx_er_child ON event_relations(child_id);
```

**简化说明**：parent_id / child_id 连回 events 表后，dimension / window_minutes / topic_label 都可以通过 JOIN parent 的 payload 获取，不在 event_relations 中冗余。

### 3.2 聚合事件的 payload 结构

```json5
// EpisodeDigest (mixed 维度)
{
    "event_type": "EpisodeDigest",
    "source_type": "aggregator",
    "stream_type": "aggregate",
    "stream_id": "episode:{time_bucket}",
    // 示例: stream_id = "episode:2026-06-22T09:00"
    "payload": {
        "dimension": "mixed",
        "window_minutes": 5,
        "window_start": 1719028800.0,     // epoch
        "window_end": 1719029100.0,
        "child_count": 5,
        "child_type_counts": {"AssistantReplied": 3, "AnswerSubmitted": 2},
        "summary": "你在这5分钟内与AI讨论了函数图像的平移变换，并完成了2道练习题（正确率50%）。"
    }
}

// TopicDigest (topic 维度)
{
    "event_type": "TopicDigest",
    "source_type": "aggregator",
    "stream_type": "aggregate",
    "stream_id": "topic:三角函数:{time_bucket}",
    // 示例: stream_id = "topic:三角函数:2026-06-22"
    "payload": {
        "dimension": "topic",
        "topic_label": "三角函数",
        "window_minutes": 1440,           // 日窗口
        "window_start": 1718956800.0,
        "window_end": 1719043199.0,
        "child_count": 18,
        "child_type_counts": {"AnswerSubmitted": 10, "AssistantReplied": 6, "CognitiveNodeUpdated": 2},
        "accuracy": 0.7,                   // 仅答题事件有
        "summary": "今天你在三角函数主题上完成了10道题（正确率70%），与AI讨论了6次，知识掌握度从0.45提升到0.62。"
    }
}

// TypeDigest (type 维度)
{
    "event_type": "TypeDigest",
    "source_type": "aggregator",
    "stream_type": "aggregate",
    "stream_id": "type:AnswerSubmitted:{time_bucket}",
    // 示例: stream_id = "type:AnswerSubmitted:2026-06-22T09:00"
    "payload": {
        "dimension": "type",
        "type_label": "AnswerSubmitted",
        "window_minutes": 30,
        "window_start": 1719028800.0,
        "window_end": 1719030600.0,
        "child_count": 7,
        "accuracy": 0.71,
        "summary": "30分钟内完成7道题，正确率71%。错题集中在三角函数图像变换上。"
    }
}
```

## 四、聚合引擎

### 4.1 触发机制

**定时扫描 + 滑动窗口**。

```
每 60s 扫描一次:
  for 每个有新增事件的 user_id:
    for window in [5, 30, 60, 1440, 10080, 43200]:
      for dimension in [mixed, topic, type]:
        find_ungrouped(user_id, window, dimension) → 分组
        for 每组事件 (≥ threshold 条):
          create_aggregate_event()
          create_event_relations(child→parent)
```

### 4.2 未聚合判断

一个事件在某个 (dimension × window) 上没有父节点 → 需要聚合。

```sql
-- 查找 5min mixed 维度未聚合的事件
SELECT e.* FROM events e
WHERE e.user_id = %s
  AND e.created_at >= NOW() - INTERVAL '5 minutes'
  AND e.id NOT IN (
    SELECT child_id FROM event_relations er
    JOIN events p ON er.parent_id = p.id
    WHERE p.payload->>'dimension' = 'mixed'
      AND (p.payload->>'window_minutes')::int = 5
  )
```

### 4.3 分组逻辑

- **mixed**: 窗口内所有事件 → 1 个 `EpisodeDigest`
- **type**: 按 event_type 分组 → N 个 `TypeDigest`
- **topic**: 提取 topic 后按 topic_label 分组 → M 个 `TopicDigest`

### 4.4 Topic 提取策略 (分类器 + LLM fallback)

```
输入: 事件 payload (含 content / skill_id / label)
     │
     ├── 字段映射 (优先): skill_id / label / domain → 直接匹配已有 topic
     │       匹配成功 → 使用该 topic_label
     │       匹配度 < 阈值 → 标记为 "ambiguous"
     │
     └── LLM fallback (仅当 ambiguous 或无字段):
             输入: 事件摘要 / content 前 200 字
             输出: topic_label (单选, 取自已有 topics 或 "new:xxx")
```

复用事件的 `summary` 字段（如果已有）来节省 token：
- 有 `summary` → 直接用 summary 做 topic 匹配
- 无 `summary` → 用 `payload.content` / `payload.question` 等字段

### 4.5 层层聚合

聚合事件也参与更高层聚合——一个 `EpisodeDigest(5m)` 在 30m 扫描时被父化为 `EpisodeDigest(30m)` 的子节点：

```
EpisodeDigest(5m)   → 30m 扫描 → EpisodeDigest(30m) 的子节点
EpisodeDigest(30m)  → 1h 扫描  → EpisodeDigest(1h)  的子节点
EpisodeDigest(1h)   → 日定时   → EpisodeDigest(day)  的子节点
```

聚合事件参与聚合时维度不变、窗口递增。

### 4.6 AI 摘要生成时机

**聚合时同步生成**。聚合事件生成后立即调用 LLM 生成 summary。

- 复用子事件的已有 summary（避免重复计算）
- 聚合 summary = 子事件 summary 的组合 + 统计
- 示例：5 条 `AssistantReplied` 各有自己的 summary，`EpisodeDigest(5m)` 的 summary = LLM 将其压缩为一句

## 五、查询模式

### 5.1 AI 上下文：只看顶层

```sql
SELECT * FROM events e
WHERE e.user_id = %s
  AND e.id NOT IN (SELECT child_id FROM event_relations)
ORDER BY e.created_at DESC
LIMIT 50;
```

### 5.2 下钻：获取子节点

```sql
SELECT e.* FROM events e
JOIN event_relations er ON e.id = er.child_id
WHERE er.parent_id = %s
ORDER BY e.created_at ASC;
```

### 5.3 按维度过滤顶层

```sql
SELECT * FROM events e
WHERE e.user_id = %s
  AND e.id NOT IN (SELECT child_id FROM event_relations)
  AND e.payload->>'dimension' = 'topic'    -- 只显示 topic 维度
ORDER BY e.created_at DESC;
```

### 5.4 获取事件的所有祖先 (CTE)

```sql
WITH RECURSIVE ancestors AS (
    SELECT parent_id, child_id, 1 AS depth
    FROM event_relations WHERE child_id = %s
    UNION ALL
    SELECT er.parent_id, er.child_id, a.depth + 1
    FROM event_relations er
    JOIN ancestors a ON er.child_id = a.parent_id
)
SELECT e.*, a.depth FROM ancestors a
JOIN events e ON e.id = a.parent_id
ORDER BY a.depth DESC;
```

## 六、前端视图

### 6.1 两个视图模式

| 模式 | 说明 |
|------|------|
| **原始流** | events 表所有事件（与当前一致），时间倒序 |
| **聚合流** | 仅显示没有父节点的顶层聚合事件 |

用户通过 Toggle 切换，偏好记忆在 localStorage。

### 6.2 聚合流视图

默认展示顶层聚合，按时间倒序：

```
DailyDigest (day, mixed) 2026-06-22  (12子节点)  [+]
DailyDigest (day, mixed) 2026-06-21  (8子节点)   [+]
```

展开后：

```
DailyDigest (day, mixed) 2026-06-22  (12子节点)  [-]
  ├── EpisodeDigest (1h, mixed) 09:00  (5子节点)  [+]
  ├── EpisodeDigest (1h, mixed) 10:00  (3子节点)  [+]
  ├── TopicDigest (day, topic, 三角函数)         [+]
  └── TypeDigest (day, type, AnswerSubmitted)    [+]
```

### 6.3 维度切换

用户可在聚合流中选择维度：
- **全部** — 混合展示（默认）
- **时间线** — `payload.dimension = 'mixed'`
- **按主题** — `payload.dimension = 'topic'`
- **按类型** — `payload.dimension = 'type'`

偏好存储在 localStorage。

### 6.4 显示规则

- 有父节点 → 默认隐藏（折叠在父节点内）
- 有子节点 → 显示 `[+]` 可展开
- 原始事件且无子节点 → 仅原始流可见

## 七、已确定的决策

| 问题 | 决策 |
|------|------|
| 阈值 | mixed ≥ 2, type ≥ 2, topic ≥ 1 |
| `source_id` | 废弃，聚合事件不留此字段 |
| 外键约束 | `ON DELETE CASCADE`（仅用户清空全量数据时触发） |
| 旧 ConversationDigest | 开发阶段淘汰，统一为新体系 |

## 八、实现阶段

### Phase A: 基础设施
- event_relations 表迁移 SQL
- 查询 CTE + 索引
- 聚合引擎框架（定时扫描 + 滑动窗口 + 维度循环）

### Phase B: 核心聚合逻辑
- mixed 维度聚合 (5m/30m/1h/day/week/month)
- type 维度聚合
- topic 维度聚合 + 分类器集成
- AI 摘要生成

### Phase C: 前端 + AI 接口
- 事件树视图（有父折叠/有子展开）
- 原始流/聚合流切换
- 维度切换
- AI 上下文查询改用顶层事件