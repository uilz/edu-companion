# Task 0016: 认知 OS 内核深度设计

> 版本：v1.0
> 起草 Agent：AP007
> 起草时间：2026-07-11
> 状态：设计稿，待用户确认
> 依赖：Task 0015（目标架构愿景）、ADR 0015（认知概率图）

---

## 1. 定位与边界

### 1.1 一句话定位

认知 OS 内核是苹果果的「学习事实记录 + 认知状态派生 + 跨模块编排」基础设施。它向上层场景壳提供统一的读写契约，但**不生成用户文案、不决定 UI、不维护任何场景壳的业务状态**。

### 1.2 内核三大职责

| 职责 | 说明 | 对应子系统 |
|------|------|-----------|
| **记录学习事实** | 所有用户/系统的学习行为只产生一次不可变事件 | 事件总线 + 统一事件存储 |
| **派生认知状态** | 从事件流增量更新认知节点投影，供只读查询 | 认知状态中心 + 投影构建器 |
| **编排跨模块行动** | 读事件流与投影，生成提案/计划请求/对话上下文 | 秘书编排器（单独成篇，见 Task 0018） |

### 1.3 内核 vs 场景壳的边界

| 边界 | 内核 | 场景壳 |
|------|------|--------|
| 写 | 只接收事件；不直接调用壳 API | 只发布事件；不直接写内核投影 |
| 读 | 维护投影与事件存储 | 只读内核暴露的投影视图 |
| 用户文案 | 不生成 | 负责展示与交互 |
| 业务规则 | 认知数学、调度、去重、因果链 | 壳内局部流程（如出题、卡片复习） |

### 1.4 设计原则

1. **单一事实源（SSOT）**：任何学习行为只产生一个领域事件。
2. **事件不可变**：事件一旦写入不可修改，错误通过补偿事件修正。
3. **投影完全可重建**：所有 `cognitive_node_projections` 字段都能从事件流重新计算。
4. **幂等性**：同一事件重复处理不会导致重复副作用。
5. **因果链完整**：每个派生事件必须携带 `caused_by_event_id`。
6. **同步更新用户-facing 投影，异步处理图传播与秘书洞察**：保证核心路径低延迟。

---

## 2. 总体架构

```
┌─────────────────────────────────────────────────────────────────────┐
│                          场景壳（Scene Shells）                       │
│  对话 / 练习 / 闪卡 / 阅读 / 规划 / 知识树                            │
│   │ 写：发布 DomainEvent          读：查 Projection View            │
└───┬─────────────────────────────────────────────────────────────┬───┘
    │                                                             │
    ▼                                                             ▼
┌─────────────────────────────────────────────────────────────────────┐
│                        认知 OS 内核（Cognitive OS Kernel）           │
│  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐  │
│  │  事件总线         │  │  认知状态中心     │  │  秘书编排器       │  │
│  │  PersistentEvent │  │  CognitiveEvent  │  │  Secretary       │  │
│  │  Bus             │  │  Handler         │  │  Orchestrator    │  │
│  │                  │  │                  │  │  （Task 0018）   │  │
│  │  · 接收/持久化    │  │  · 订阅学习事实   │  │  · 订阅派生事件   │  │
│  │  · 分发           │  │  · 更新 projection│  │  · 生成提案       │  │
│  │  · 幂等/重放      │  │  · 发布          │  │  · 注入对话上下文 │  │
│  │                  │  │    CognitiveState│  │                  │  │
│  │                  │  │    Changed       │  │                  │  │
│  └────────┬─────────┘  └────────┬─────────┘  └────────┬─────────┘  │
│           │                     │                     │            │
│  ┌────────▼─────────────────────▼─────────────────────▼────────┐   │
│  │                  统一事件存储（EventStore）                   │   │
│  │   events 表：所有 DomainEvent 的持久化真相源                   │   │
│  │   practice_events / cognitive_events：认知专用事件表          │   │
│  └──────────────────────────┬───────────────────────────────────┘   │
│                             │                                       │
│  ┌──────────────────────────▼───────────────────────────────────┐   │
│  │                  认知节点数据系统                              │   │
│  │  knowledge_nodes / knowledge_edges / cognitive_node_projections │   │
│  └───────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 3. 子系统详细设计

### 3.1 事件总线（PersistentEventBus）

#### 3.1.1 职责

- 接收场景壳发布的 `DomainEvent`。
- 将事件持久化到 `events` 表（统一事件存储）。
- 并行分发事件给所有订阅 handler。
- 保证事件不丢失、单个 handler 失败不影响其他 handler。
- 提供递归深度保护，防止 handler 内嵌套 publish 导致栈溢出。

#### 3.1.2 当前实现与待加固点

当前实现位于：
- [backend/app/infrastructure/event_bus.py](file:///home/deploy/edu-companion/backend/app/infrastructure/event_bus.py)
- [backend/app/infrastructure/persistent_event_bus.py](file:///home/deploy/edu-companion/backend/app/infrastructure/persistent_event_bus.py)

| 能力 | 当前状态 | 需加固 |
|------|---------|--------|
| 内存 EventBus | 已实现 | 保留，用于测试与无 DB 场景 |
| 持久化 EventBus | 已实现 | 统一为生产环境唯一总线 |
| 事件写入 | 走 EventStore.append | OK |
| 后台轮询 | 已实现 poll_once | 需接入中央调度器 |
| handler 超时 | 5s 默认 | 按事件类型可配置 |
| 幂等分发 | 无 | 需基于 event_id + handler 名去重 |
| 死信队列 | 无 | 失败事件进入 dead_letter_events |
| 因果链透传 | 基类支持 | handler 内 publish 事件必须设置 caused_by_event_id |

#### 3.1.3 事件分发语义

```python
async def publish(event: DomainEvent) -> str:
    """
    1. 递归深度检查（max_depth=8）
    2. EventStore.append(event) → 返回 event_id
    3. EventMemory.remember(event) 写入短期记忆
    4. 并行 dispatch 给所有已订阅 handler（asyncio.gather）
    5. handler 超时/异常不影响其他 handler
    6. 返回 event_id
    """
```

#### 3.1.4 订阅契约

```python
# 订阅示例
bus.subscribe("AnswerSubmitted", analytics_service.on_answer_submitted)
bus.subscribe("AnswerSubmitted", cognitive_event_handler.on_answer_submitted)
bus.subscribe("CognitiveStateChanged", secretary_event_handler.on_cognitive_state_changed)
```

订阅规则：
- handler 必须是 `Callable[[DomainEvent], Awaitable[None]]`。
- handler 内部可以再次 `publish` 派生事件，但递归深度受限。
- handler 失败只记录日志，不阻塞其他 handler。

#### 3.1.5 幂等与去重

生产环境必须保证：
- 同一 `event_id` 对同一 handler 只执行一次。
- 实现：在 `events` 表或 `event_handler_logs` 表中记录 `(event_id, handler_name, status)`。
- 重放场景（rebuild）通过 `event_handler_logs` 跳过已处理记录。

---

### 3.2 统一事件存储（EventStore）

#### 3.2.1 职责

- 所有用户可感知操作的唯一写入入口。
- 提供事件查询、流回放、因果链追踪、语义搜索。
- 为 PersistentEventBus 提供持久化 backend。

#### 3.2.2 当前实现

当前实现位于 [backend/app/infrastructure/event_store.py](file:///home/deploy/edu-companion/backend/app/infrastructure/event_store.py)。

核心方法：
- `append(event, stream_type, stream_id, ...)`：写入事件。
- `query(...)`：条件查询。
- `stream(stream_type, stream_id)`：获取指定流的事件。
- `replay(user_id, since, until, event_types)`：时间范围回放。
- `get_parent_chain(event_id)` / `get_correlated(correlation_id)`：因果链与关联追踪。
- `search_similar(query, user_id)`：基于 pgvector 的语义搜索。

#### 3.2.3 events 表结构

| 字段 | 类型 | 说明 |
|------|------|------|
| id | UUID / string | 事件唯一 ID |
| user_id | string | 用户 ID |
| event_type | string | 事件类型名（如 AnswerSubmitted） |
| stream_type | string | 流类型（conversation / practice / cognitive / secretary） |
| stream_id | string | 流内实体 ID |
| source_type | string | 业务来源类型 |
| source_id | string | 业务来源 ID |
| parent_event_id | string | 因果链上一事件 ID |
| correlation_id | string | 跨域关联 ID |
| status | string | done / pending / failed |
| payload | JSONB | 事件完整 payload |
| summary | text | AI 生成摘要 |
| importance | float | 重要性评分 |
| embedding | vector | 语义向量 |
| created_at | timestamptz | 写入时间 |

#### 3.2.4 专用事件表

除统一 `events` 表外，认知域使用专用表：

- `practice_events`：练习事实事件，供 ProjectionBuilder 回放。
- `cognitive_events`：认知领域事件（node_created / cognitive_reward / cognitive_update 等）。

专用表与 `events` 表的关系：
- `events` 表是**统一真相源**，包含所有 DomainEvent。
- `practice_events` / `cognitive_events` 是认知域的**物化视图/查询优化表**，数据从 `events` 同步写入，允许从统一事件重建。

---

### 3.3 认知状态中心（CognitiveEventHandler）

#### 3.3.1 职责

- 订阅学习事实事件（`AnswerSubmitted`, `FlashCardReviewed`, `PlanItemCompleted`, `MessageClassified` 等）。
- 将事实事件转换为认知域事件（`practice_response`, `conversation_assessment` 等）。
- 调用 `ProjectionBuilder` 增量更新 `cognitive_node_projections`。
- 发布派生事件 `CognitiveStateChanged`。
- 写入只读审计事件 `CognitiveReward`。

#### 3.3.2 当前实现

当前实现位于 [backend/app/domain/cognitive/events.py](file:///home/deploy/edu-companion/backend/app/domain/cognitive/events.py)。

核心入口：
- `handle_answer_submitted(event: AnswerSubmitted) -> list[dict]`
- `handle_practice_response(event: CognitiveEventRecord) -> dict`
- `handle_conversation_assessment(event: CognitiveEventRecord) -> dict`
- `handle_node_created(event: CognitiveEventRecord) -> dict`

#### 3.3.3 处理流程

```
AnswerSubmitted (practice)
  │
  ▼
CognitiveEventHandler.handle_answer_submitted()
  │
  ├── 对每个 cognitive_node_ids 中的 node_id：
  │     ├── 创建 CognitiveEventRecord(practice_response)
  │     ├── handle_practice_response(record)
  │     │     ├── 自动创建原子节点（如不存在）
  │     │     ├── 幂等写入 practice_events
  │     │     ├── ProjectionBuilder.apply_practice_event()
  │     │     │     ├── belief_update (Beta 更新 + 信息增益)
  │     │     │     ├── shrinkage_prior_apply (父节点收缩)
  │     │     │     ├── graph_propagate (图传播)
  │     │     │     ├── activation_update
  │     │     │     ├── update_trend
  │     │     │     ├── update_metacognition
  │     │     │     ├── update_engagement
  │     │     │     ├── update_prediction
  │     │     │     ├── error_cluster (答错时)
  │     │     │     ├── update_scheduling
  │     │     │     ├── check_deep_processing_trigger
  │     │     │     └── update_composition
  │     │     ├── 写入 cognitive_reward 审计事件
  │     │     ├── 写入 cognitive_update 审计事件
  │     │     └── 返回认知状态变化视图
  │     └── 收集结果
  │
  └── 返回所有 node_results
```

#### 3.3.4 幂等保证

- `practice_events.idempotency_key` 唯一。
- `cognitive_reward` 事件幂等键：`cr_{practice_event_id}_{node_id}`。
- 同一 `AnswerSubmitted` 重复处理不会新增多条 `practice_events`。

#### 3.3.5 发布 CognitiveStateChanged

`CognitiveEventHandler` 处理完成后，由 DI 容器中的事件处理器统一发布 `CognitiveStateChanged`：

```python
# backend/app/application/di.py
async def _on_answer_submitted_to_cognitive(event: DomainEvent):
    ...
    results = handler.handle_answer_submitted(event)
    for result in results:
        if result.get("status") == "ok":
            publish_event_safe(CognitiveStateChanged(
                user_id=result["user_id"],
                source_module="cognitive",
                source_id=result["node_id"],
                correlation_id=event.correlation_id,
                caused_by_event_id=event.event_id,
                node_id=result["node_id"],
                proficiency_before=result["proficiency_before"],
                proficiency_after=result["proficiency_after"],
                uncertainty_before=result["uncertainty_before"],
                uncertainty_after=result["uncertainty_after"],
                belief_alpha=result["belief_alpha"],
                belief_beta=result["belief_beta"],
                urgency=result["urgency"],
                stagnation_days=result["stagnation_days"],
                next_review_at=result["next_review_at"],
                next_action_type=result["next_action_type"],
            ))
```

---

### 3.4 投影构建器（ProjectionBuilder）

#### 3.4.1 职责

- 从 `practice_events` / `cognitive_events` 增量更新 `cognitive_node_projections`。
- 提供 `rebuild(user_id)` / `rebuild_node(user_id, node_id)` 用于修复与测试。
- 每个 practice 事件触发 12 步认知子系统更新。

#### 3.4.2 当前实现

当前实现位于 [backend/app/infrastructure/db/projection_builder.py](file:///home/deploy/edu-companion/backend/app/infrastructure/db/projection_builder.py)。

#### 3.4.3 12 步更新流程

| 步骤 | 操作名 | 职责 | 关键输出字段 |
|------|--------|------|-------------|
| 1 | `belief_update` | Beta(α, β) 后验更新 + 信息增益 | `belief_alpha`, `belief_beta`, `last_information_gain`, `total_information_gain` |
| 2 | `shrinkage_prior_apply` | 子节点向父节点收缩先验 | effective belief（用于下游） |
| 3 | `graph_propagate` | 信念变化沿边传播给邻居 | 邻居节点的 `belief_alpha`, `belief_beta` |
| 4 | `activation_update` | 更新节点激活水平 | `act_base_level`, `act_retrieval_prob` |
| 5 | `update_trend` | 更新趋势与停滞检测 | `trend_velocity`, `trend_stagnation_days`, `trend_direction` |
| 6 | `update_metacognition` | 校准自信度偏差 | `meta_calibration_error`, `meta_direction` |
| 7 | `update_engagement` | 更新经验值与连击 | `eng_xp`, `eng_streak_current`, `eng_flow_score` |
| 8 | `update_prediction` | 基于前序节点预测掌握度 | `pred_top_down_mean`, `pred_error_flag` |
| 9 | `error_cluster` | 答错时聚类错误类型 | `cognitive_node_error_clusters` 子表 |
| 10 | `update_scheduling` | 计算复习紧迫度与下次行动 | `sched_urgency`, `sched_next_review`, `sched_next_action_type` |
| 11 | `check_deep_processing_trigger` | 触发深加工任务 | `cognitive_node_deep_processing` 子表 |
| 12 | `update_composition` | 检测同 session 共现组块 | `comp_chunk_id`, `comp_chunking_status` |

#### 3.4.4 信息增益计算

```python
entropy_before = _beta_entropy(alpha_before, beta_before)
entropy_after = _beta_entropy(alpha_after, beta_after)
information_gain = max(0.0, entropy_before - entropy_after)

if entropy_before > 0:
    uncertainty_reduction_percent = min(99.9, information_gain / entropy_before * 100)
```

#### 3.4.5 返回值

`apply_practice_event` 返回字典，供 `cognitive_reward` 与反馈服务使用：

```python
{
    "information_gain": float,
    "uncertainty_reduction_percent": float,
    "entropy_before": float,
    "entropy_after": float,
    "uncertainty_before": float,
    "uncertainty_after": float,
    "proficiency_before": float,
    "proficiency_after": float,
    "belief_alpha_before": float,
    "belief_beta_before": float,
    "belief_alpha_after": float,
    "belief_beta_after": float,
}
```

#### 3.4.6 重建语义

```python
def rebuild_node(self, user_id: str, node_id: str):
    projection = self._projection_repo.reset_projection(user_id, node_id)
    events = self._event_repo.list_practice_events_for_node(user_id, node_id)
    events.sort(key=lambda e: e.timestamp)
    for event in events:
        self.apply_practice_event(event, projection)
    self._decay_to_now(projection)
    self._projection_repo.upsert(projection)
```

重建保证：任何投影状态都可以从事件流完全恢复。

---

### 3.5 认知操作注册中心（CognitiveOperationRegistry）

#### 3.5.1 职责

- 统一管理所有认知子系统操作（belief、scheduling、activation 等）。
- 支持装饰器注册与自动发现。
- 使 ProjectionBuilder 与具体算法解耦。

#### 3.5.2 当前实现

当前实现位于 [backend/app/domain/cognitive/operation_registry.py](file:///home/deploy/edu-companion/backend/app/domain/cognitive/operation_registry.py)。

注册方式：

```python
@_registry.register(
    "belief_update",
    "基于观测信号更新 Beta(α, β) 后验，并计算信息增益",
    params_schema={...},
)
def belief_update(belief_state, success, difficulty=None, weight=1.0, now=None):
    ...
```

已注册操作列表：
- `belief_update`, `belief_information_gain`, `shrinkage_prior_apply`, `belief_decay`
- `update_scheduling`
- `graph_propagate`
- `update_prediction`
- `update_goal_alignment`
- `check_chunk_formation`
- `check_deep_processing_trigger`, `generate_deep_processing_task`
- `bump_error_cluster`
- `update_engagement`
- `update_metacognition`
- `update_trend`
- `activation_update`, `activation_decay`

---

## 4. 数据模型与 Schema

### 4.1 实体层：knowledge_nodes

| 字段 | 类型 | 说明 |
|------|------|------|
| id | string PK | 节点唯一 ID，前缀 `kn_` |
| user_id | string | 用户 ID |
| label | text | 节点名称 |
| level | string | domain / topic / atom |
| parent_id | FK | 父节点，构成层级树 |
| path_id | text | 层级路径快照 |
| node_type | string | explicit / inferred / imported |
| is_visible / is_active / is_core | bool | 可见、活跃、核心标记 |
| brief / emoji / color / tags | - | 展示元数据 |
| embedding | JSONB | 语义向量 |

### 4.2 边关系层：knowledge_edges

| 字段 | 类型 | 说明 |
|------|------|------|
| id | string PK | 边唯一 ID，前缀 `ke_` |
| user_id | string | 用户 ID |
| source_id / target_id | FK | 源/目标节点 |
| edge_type | string | prerequisite / related / chunk / cooccurrence / imported_from |
| strength | float | 边强度 |
| edge_weight / edge_distance_decay | float | 传播权重与衰减 |
| max_propagation_hops | int | 最大传播跳数 |
| edge_metadata | JSONB | 附加元数据 |

### 4.3 事件层

#### practice_events

| 字段 | 类型 | 说明 |
|------|------|------|
| id | string PK | 前缀 `pe_` |
| user_id / node_id | string | 用户/节点 |
| session_id / question_id | string | 会话/题目 |
| timestamp | float | 业务时间戳 |
| success | bool | 是否正确 |
| latency_ms / weight / difficulty | float | 时延/权重/难度 |
| confidence_before / confidence_after | float | 自信度 |
| hints_used / time_spent | int/float | 提示数/耗时 |
| error_embedding | JSONB | 错误语义向量 |
| idempotency_key | string UNIQUE | 幂等键 |

#### cognitive_events

| 字段 | 类型 | 说明 |
|------|------|------|
| id | string PK | 前缀 `ce_` |
| user_id | string | 用户 |
| event_type | string | node_created / cognitive_reward / cognitive_update / edge_created |
| actor_type | string | user / system |
| source_type / source_id | string | 来源 |
| node_id | FK nullable | 关联节点 |
| payload | JSONB | 事件负载 |
| status | string | pending / done |

### 4.4 派生状态层：cognitive_node_projections

| 字段组 | 字段 | 说明 |
|--------|------|------|
| 主键 | node_id / user_id | 节点级投影 |
| Belief | belief_alpha / belief_beta | Beta 后验参数 |
| | belief_evidence_count | 证据数 |
| | belief_last_updated | 最后更新时间戳 |
| 信息增益 | total_information_gain / last_information_gain | 累计/上次信息增益 |
| 调度 | sched_urgency | 复习紧迫度 |
| | sched_next_review | 下次复习时间戳 |
| | sched_interval_days | 建议间隔天数 |
| | sched_next_action_type | review / practice / explore / deep_processing / idle |
| 激活 | act_base_level / act_retrieval_prob / act_latency_ms | ACT-R 风格激活 |
| 趋势 | trend_velocity / trend_stability / trend_volatility / trend_direction / trend_stagnation_days | 趋势分析 |
| 元认知 | meta_self_assessment / meta_calibration_error / meta_direction | 自信度校准 |
| 参与 | eng_xp / eng_streak_current / eng_streak_longest / eng_flow_score | 经验与心流 |
| 目标 | goal_toward / goal_distance / goal_on_critical_path | 目标对齐 |
| 组块 | comp_chunk_id / comp_chunking_status | 组块归属 |
| 预测 | pred_top_down_mean / pred_prediction_error / pred_error_flag | 前序节点预测 |
| 负荷 | load_intrinsic / load_dynamic | 认知负荷 |

### 4.5 子表

- `cognitive_node_error_clusters`：错误聚类。
- `cognitive_node_deep_processing`：深加工任务。
- `cognitive_node_composition_members`：组块成员。

---

## 5. 关键算法

### 5.1 Beta-二项信念更新

```python
def belief_update(alpha, beta, success, difficulty=None, weight=1.0):
    p = alpha / (alpha + beta)
    difficulty_factor = map_difficulty(difficulty)  # [0, 1]

    if success:
        alpha += weight
        beta += weight * (1.0 - p) * difficulty_factor
    else:
        alpha += weight * p * (1.0 - difficulty_factor)
        beta += weight

    return alpha, beta
```

### 5.2 信息增益

```python
entropy_before = beta_entropy(alpha_before, beta_before)
entropy_after = beta_entropy(alpha_after, beta_after)
information_gain = max(0.0, entropy_before - entropy_after)
```

### 5.3 Shrinkage 先验

```python
def shrinkage_prior(child_alpha, child_beta, child_evidence,
                    parent_alpha, parent_beta, shrinkage_strength=5.0):
    lam = shrinkage_strength / (shrinkage_strength + child_evidence)
    effective_alpha = lam * parent_alpha + (1.0 - lam) * child_alpha
    effective_beta = lam * parent_beta + (1.0 - lam) * child_beta
    return effective_alpha, effective_beta
```

### 5.4 信念衰减

```python
def belief_decay(alpha, beta, last_updated, forgetting_rate, stability_factor, now):
    delta_days = (now - last_updated) / 86400.0
    total = alpha + beta
    p = alpha / total
    effective_rate = forgetting_rate * (1.0 - stability_factor)
    total_decayed = total * math.exp(-effective_rate * delta_days)
    return max(0.1, total_decayed * p), max(0.1, total_decayed * (1.0 - p))
```

### 5.5 图传播

```python
# 对每条边，按 edge_weight / distance_decay / max_hops 计算 delta
delta_alpha_to_neighbor = delta_alpha * edge_weight * decay ** hops
delta_beta_to_neighbor = delta_beta * edge_weight * decay ** hops
```

### 5.6 调度

调度由 `update_scheduling` 操作根据 effective belief、趋势、目标距离、是否核心节点综合计算：

```python
next_review = last_practiced + interval_days * 86400
urgency = f(proficiency, uncertainty, stagnation_days, goal_distance)
next_action_type = choose_action(proficiency, pred_error_flag, stagnation_days)
```

---

## 6. 事件流与序列图

### 6.1 练习 → 认知状态变化

```
用户提交答案
  │
  ▼
PracticeShell.submit_answer()
  │
  ▼
EventBus.publish(AnswerSubmitted(
    user_id=u1,
    session_id=s1,
    question_id=q1,
    cognitive_node_ids=["kn_a", "kn_b"],
    is_correct=True,
    ...
))
  │
  ├──► CognitiveEventHandler.handle_answer_submitted()
  │      │
  │      ├──► 对 kn_a: handle_practice_response()
  │      │      ├── 写入 practice_events (idempotency_key)
  │      │      ├── ProjectionBuilder.apply_practice_event()
  │      │      ├── 写入 cognitive_reward (cr_pe001_kn_a)
  │      │      └── 返回 kn_a 状态变化
  │      │
  │      └──► 对 kn_b: handle_practice_response()
  │             └── 同上
  │
  ├──► EventBus.publish(CognitiveStateChanged(kn_a))
  ├──► EventBus.publish(CognitiveStateChanged(kn_b))
  │
  └──► SecretaryEventHandler.on_cognitive_state_changed()
         └── 评估后生成 ProposalGenerated
```

### 6.2 闪卡复习 → 认知状态变化

```
用户复习闪卡
  │
  ▼
FlashCardShell.review_card(card_id, self_assessment="good")
  │
  ▼
EventBus.publish(FlashCardReviewed(
    user_id=u1,
    card_id=c1,
    linked_node_ids=["kn_a"],
    node_link_roles={"kn_a": "primary"},
    ...
))
  │
  ├──► CognitiveEventHandler.handle_flashcard_reviewed()
  │      └── 将 FlashCardReviewed 转为低权重 practice_response
  │          └── ProjectionBuilder.apply_practice_event(weight=0.1 * role_weight)
  │
  └──► EventBus.publish(CognitiveStateChanged(kn_a))
```

### 6.3 计划完成 → 认知状态变化

```
用户完成 plan item
  │
  ▼
PlanningShell.complete_plan_item(plan_item_id)
  │
  ▼
EventBus.publish(PlanItemCompleted(
    user_id=u1,
    plan_item_id=p1,
    source_module="practice",
    linked_node_ids=["kn_a"],
    ...
))
  │
  ├──► CognitiveEventHandler.handle_plan_item_completed()
  │      └── 将完成视为一次成功观测，更新 kn_a 信念
  │
  └──► EventBus.publish(CognitiveStateChanged(kn_a))
```

---

## 7. 读写边界与依赖规则

### 7.1 写方向：单向上游

```
场景壳 → 事件总线 → 事件存储
              ↓
        认知状态中心 → 投影构建器 → 认知节点数据系统
              ↓
        发布 CognitiveStateChanged → 秘书/规划订阅
```

### 7.2 读方向：只读投影

```
场景壳 ← 投影视图 ← 认知节点数据系统
```

### 7.3 禁止行为

- 场景壳直接调用认知仓库更新状态。
- 秘书直接修改 `cognitive_node_projections`。
- 规划系统直接修改节点信念。
- 一个模块直接读另一个模块的私有表。
- handler 内不设置 `caused_by_event_id` 就发布派生事件。

---

## 8. 与场景壳的接口

### 8.1 内核暴露的查询接口（供场景壳只读）

| 接口 | 输入 | 输出 | 使用方 |
|------|------|------|--------|
| `get_node_projection(user_id, node_id)` | 用户/节点 ID | 投影完整字段 | 练习、闪卡、知识树 |
| `list_weak_nodes(user_id, limit)` | 用户 ID | 薄弱节点列表 | 练习组题、秘书 |
| `list_review_queue(user_id, limit)` | 用户 ID | 按 urgency 排序的节点 | 闪卡、规划 |
| `get_node_graph(user_id, node_ids, depth)` | 节点集合 | 子图（节点+边+投影） | 知识树 |
| `get_feedback_projection(attempt_id)` | attempt ID | 反馈视图 | 练习壳 |

### 8.2 内核接收的事件（场景壳写入）

| 事件 | 来源壳 | 说明 |
|------|--------|------|
| AnswerSubmitted | 练习壳 | 答题事实 |
| FlashCardReviewed | 闪卡壳 | 复习自评 |
| PlanItemCompleted | 规划壳 | 计划完成 |
| MessageClassified | 对话壳 | 消息认知归属 |
| AssistantReplied | 对话壳 | AI 回复 |
| ReadingSessionEnded | 阅读壳 | 阅读会话结束 |
| ErrorRecorded | 练习壳 | 错题记录 |

---

## 9. 前端与内核的关系

前端不直接访问内核数据库，通过以下方式间接使用：

1. **通过场景壳 API**：练习壳 API 内部读取投影后组装响应。
2. **通过场景壳事件流**：SSE / WebSocket 推送 `CognitiveStateChanged` 等事件到前端。
3. **通过秘书提案**：前端展示 `ProposalGenerated`，用户接受后触发后续流程。

---

## 10. 风险与缓解

| 风险 | 影响 | 缓解措施 |
|------|------|----------|
| 事件流处理延迟 | 反馈/提案不及时 | 核心投影同步更新；图传播与秘书洞察异步 |
| 递归 publish 过深 | 栈溢出/事件风暴 | PersistentEventBus 递归深度保护 |
| handler 失败丢失 | 状态不一致 | 持久化事件 + 死信队列 + 可重放 |
| 图传播过度平滑 | 邻居节点信念失真 | `independent_evidence_weight` 与 `max_propagation_hops` 限制 |
| 首次答题信息增益异常 | 前端文案奇怪 | 阈值逻辑 + 边界测试 |
| 数据量大时 rebuild 慢 | 恢复困难 | 按用户/节点分区重建；快照加速 |

---

## 11. 验收条件

### 11.1 单元测试

- [ ] `belief_update` 返回正确的 α/β 与信息增益。
- [ ] `shrinkage_prior_apply` 在证据稀疏时接近父节点，证据充足时接近子节点。
- [ ] `belief_decay` 保持均值不变，精度随时间下降。
- [ ] `ProjectionBuilder.apply_practice_event` 幂等：同一事件执行两次结果不变。
- [ ] `CognitiveEventHandler.handle_answer_submitted` 对多节点分别产生状态变化。

### 11.2 集成测试

- [ ] 发布 `AnswerSubmitted` 后，`cognitive_node_projections` 正确更新。
- [ ] 发布 `AnswerSubmitted` 后，`CognitiveStateChanged` 事件被发布。
- [ ] `cognitive_reward` 事件按幂等键唯一写入。
- [ ] `rebuild_node` 结果与增量更新结果一致。

### 11.3 端到端测试

- [ ] `rebuild.sh` 启动前后端。
- [ ] 完成一次答题，查询投影字段与反馈接口返回一致。
- [ ] 完成一次闪卡复习，节点信念发生小幅度更新。

---

## 12. 后续依赖

本设计为以下模块提供基础：
- Task 0017：练习壳（依赖内核事件与投影）
- Task 0018：秘书系统（依赖 `CognitiveStateChanged`）
- Task 0019：规划系统（依赖秘书提案与认知投影）
- Task 0020：闪卡壳（依赖 `FlashCardReviewed` → 认知更新）
- Task 0021：对话壳（依赖 `MessageClassified` / `AssistantReplied` → 认知同步）
- Task 0022：知识树壳（依赖 `get_node_graph` 与投影可视化）

---

> AP007：「这是认知 OS 内核的深度设计。确认后，练习壳、秘书系统、规划系统等上层模块的设计将在此内核契约之上展开。」
