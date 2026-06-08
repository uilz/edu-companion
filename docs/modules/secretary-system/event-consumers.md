# 秘书系统 · 事件消费逻辑

> 各事件消费者如何监听事件总线并触发分析。
>
> 源码：[backend/app/domain/secretary/engines/secretary_event_handler.py](../../../backend/app/domain/secretary/engines/secretary_event_handler.py)

---

## 事件消费者：SecretaryEventHandler

秘书系统通过 `SecretaryEventHandler` 统一消费事件总线上的领域事件，然后分发到对应的处理逻辑。

## 事件消费列表

### 1. AnswerSubmitted

```python
async def on_answer_submitted(event: AnswerSubmitted):
    # 更新薄弱点分析
    if not event.is_correct:
        weak_analysis.add(event.skill_id, event.error_type)

    # 触发疲劳管理检查
    fatigue_manager.run_check(event.user_id)
```

### 2. SessionCompleted

```python
async def on_session_completed(event: SessionCompleted):
    # 触发复习计划检查
    review_reminder.run_check(event.user_id)

    # 更新疲劳状态
    fatigue_manager.run_check(event.user_id)
```

### 3. CognitiveNodeUpdated

```python
async def on_node_updated(event: CognitiveNodeUpdated):
    # 检查掌握度变化
    if event.proficiency_after >= 0.85:
        # 掌握后推荐下一步
        planning_engine.suggest_next(event.user_id, event.node_id)
```

### 4. NodeCreated

```python
async def on_node_created(event: NodeCreated):
    # 触发波纹扩展
    knowledge_service.ripple_expand(event.node_id)
```

### 5. ProposalAccepted

```python
async def on_proposal_accepted(event: ProposalAccepted):
    # 执行提案操作
    proposal_action_handler.execute(event.proposal_id, event.action_type, event.target_node_id)
```

## 消费者注册

```python
# 在秘书系统初始化时注册
event_bus.subscribe("AnswerSubmitted", secretary_handler)
event_bus.subscribe("SessionCompleted", secretary_handler)
event_bus.subscribe("CognitiveNodeUpdated", secretary_handler)
event_bus.subscribe("NodeCreated", secretary_handler)
event_bus.subscribe("ProposalAccepted", secretary_handler)
```

## 分析周期

| 分析 | 触发方式 | 频率 |
|------|----------|------|
| 薄弱点发现 | 事件驱动 | 每次答题完成 |
| 复习提醒 | 定时 + 事件 | 每 600 秒 / 会话完成 |
| 疲劳管理 | 事件驱动 | 每次答题 / 会话完成 |
| 学习规划 | 事件驱动 | 每次节点更新 |
| 波纹扩展 | 事件驱动 | 每次节点创建 |
