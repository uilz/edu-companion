# Task 0013: 信息增益 UI 反馈与事件流设计文档

> 任务：将 ADR 0013 中"信息增益核心反馈机制"从文档落地为代码。
> 状态：**已被 Task 0015 吸收，本方案仅供参考，不再独立执行。**
> 说明：AP008 已关闭，其读取侧代码（FeedbackService / FeedbackBuilder / GET /feedback）由 AP007 废弃重写。本设计文档中的目标与关键阈值已合并至 `docs/temp/task0015-target-architecture-vision.md` 的 5.2 练习壳与 Phase 2-6，具体实现以 Task 0015 为准。
>
> 关键决策（2026-07-11）：
> 1. 采用**拉取模型**：`POST /submit` 只返回基础反馈 + `attempt_id`，前端通过 `GET /feedback/{attempt_id}` 拉取完整反馈（含信息增益）。保持命令处理器精简，认知更新完全事件驱动。
> 2. 保留 **`cognitive_reward` 只读事件**，写入事件流供审计/跨模块消费。
> 3. 信息增益“高/低”阈值：`uncertainty_reduction_percent >= 15%` 为高，否则为低。

---

## 1. 问题定义与背景

### 1.1 当前现状

练习答题后，系统当前返回的反馈是：
- 正确/错误标识
- 正确答案
- 解析
- 元认知反馈（基于 `confidence_before` 与正确性）

认知中心已升级为 Beta(α, β) 概率动态系统（ADR 0015）。每次练习都会触发 `belief_update`，并计算 `information_gain = H(Beta_before) - H(Beta_after)`。该值已写入 `cognitive_node_projections.last_information_gain` / `total_information_gain`，但：
- **前端未展示**信息增益；
- **未作为独立事件写入事件流**，无法被秘书系统、调度系统或审计流消费；
- 现有 `information_gain_event` 事件类型仅用于秘书系统评估的弱信号（`estimated_ig` + `confidence`），与练习硬观测信号语义不同。

### 1.2 目标

1. 用户在答题后能看到基于信息增益的自然语言反馈，替代或补充简单的"正确/错误"。
2. 练习产生的信息增益作为 `cognitive_reward` 事件写入事件流，供秘书系统、调度、审计、回放使用。
3. 保持事件溯源原则：`practice_response` 只记录不可变事实，派生值（信息增益）通过独立事件记录。

---

## 2. 方案对比

| 维度 | 方案 A：同步返回 + `cognitive_reward` 事件（推荐） | 方案 B：同步返回 + 复用 `information_gain_event` | 方案 C：纯异步推送 |
|---|---|---|---|
| **前端体验** | 优秀，提交后立即在反馈面板展示 | 优秀，同 A | 较差，用户提交后无法立即看到反馈 |
| **事件流语义** | 清晰：`practice_response` 记录事实，`cognitive_reward` 记录派生 reward | 混乱：`information_gain_event` 同时承载秘书弱信号和练习硬信号，处理逻辑需按 source 分支 | 清晰，但无法解决即时反馈 |
| **投影更新单一性** | 强。练习的投影更新只在 `handle_practice_response` 中发生一次 | 弱。若 `information_gain_event` 也被触发，可能重复更新投影；需加 source 分支判断 | 强，但前端体验不足 |
| **秘书系统消费** | 可直接订阅 `cognitive_reward` | 需先区分 source | 可直接订阅 |
| **实现复杂度** | 中：新增事件类型 + handler + 前后端字段 | 中：改造现有 `information_gain_event` handler | 低：但产品体验不可接受 |
| **可扩展性** | 高：未来对话、创造、浏览等来源均可产生 `cognitive_reward` | 中：需持续维护 source 分支 | 高 |
| **风险** | 新增事件类型需保证幂等和幂等键 | 改造现有事件类型可能引入回归 | 不符合产品需求 |

### 2.1 确认方案

**方案 A 调整版（拉取模型 + `cognitive_reward` 事件）**：
- 后端 `POST /submit` 返回基础反馈 + `attempt_id`；前端通过 `GET /feedback/{attempt_id}` 拉取完整反馈（含 `information_gain` 和 `uncertainty_reduction_percent`）。
- 新增 `FeedbackService` / `FeedbackBuilder`，从 `practice_attempts` 和 `cognitive_node_projections` 构建反馈投影。
- 新增 `cognitive_reward` 事件类型，由 `CognitiveEventHandler.handle_practice_response()` 在处理完成后发布，payload 包含 `node_id`、`source_type="practice_response"`、`reward_value`（信息增益，单位 nats）、`belief_before`、`belief_after`。
- `cognitive_reward` 事件为只读事件：不直接修改投影，只供订阅者消费。

---

## 3. 关键设计

### 3.1 后端反馈拉取模型

`POST /submit` 只负责写入事实并发布 `AnswerSubmitted`：

```
SubmitAnswerCommandHandler.handle()
  ├─ insert_attempt()
  ├─ aggregate.submit_answer()
  ├─ save aggregate / command record
  └─ await bus.publish(AnswerSubmitted(...))
       ├─ CognitiveEventHandler → update projection + publish cognitive_reward
       └─ SecretaryEventHandler → proposals
```

完整反馈通过 `GET /feedback/{attempt_id}` 按需生成：

```
FeedbackService.generate(attempt_id)
  ├─ practice_attempts row
  ├─ cognitive_node_projections for each cognitive_node_id
  └─ FeedbackProjection / response DTO
```

信息增益来源：
- `ProjectionBuilder.apply_practice_event()` 返回 `{"information_gain": float, "alpha_before", "beta_before", "alpha_after", "beta_after", ...}`。
- `CognitiveEventHandler.handle_practice_response()` 在处理完成后返回 `information_gain`。
- `FeedbackService` 读取关联节点的 `last_information_gain`，取 **max** 作为单题信息增益。
- `uncertainty_reduction_percent = ig / H_before * 100`（上限 99.9%）。

聚合策略：
- 单题反馈：取关联 nodes 的**最大信息增益**（避免稀释）。
- 节点级统计（如 total_information_gain）：对同一节点历次信息增益 **sum**。

### 3.2 前端信息增益文案

在 `FeedbackPanel` 中新增 `informationGain?: number` 和 `uncertaintyReductionPercent?: number` prop。

高/低判定阈值：
- `uncertainty_reduction_percent >= 15%` → **高**
- 否则 → **低**

文案策略：

| 正确性 | 信息增益 | 文案示例 |
|---|---|---|
| 正确 | 高 | "✅ 洞察确认！你对此的认知不确定性降低了 {X}%" |
| 正确 | 低 | "✅ 回答正确。这个知识点对你来说已经比较稳定了。" |
| 错误 | 高 | "🔍 意外信号！这次挫败带来了 {Y} nats 的信息量，边界正在外推。" |
| 错误 | 低 | "🔍 回答错误。这里有一个小盲区，值得回头再看一眼。" |

> 文案需支持考试模式切换：考试模式下仍显示"正确/错误 + 分数"，不展示信息增益。

### 3.3 `cognitive_reward` 事件

事件类型：`cognitive_reward`

Payload 结构：

```json
{
  "node_id": "kn_xxx",
  "source_type": "practice_response",
  "source_event_id": "pe_xxx",
  "reward_value": 0.42,
  "reward_unit": "nats",
  "belief_before": {"alpha": 2.0, "beta": 3.0},
  "belief_after": {"alpha": 3.0, "beta": 3.0},
  "confidence": 1.0,
  "context": {
    "is_correct": true,
    "question_id": "q_xxx",
    "difficulty": 0.3
  }
}
```

处理规则：
- `CognitiveEventHandler` 在处理 `practice_response` 后，计算并发布 `cognitive_reward`。
- `cognitive_reward` 的 handler 只做持久化，不修改投影。
- 秘书系统可订阅该事件调整推荐策略、信任积分、节奏等。

幂等键：基于 `source_event_id` + `node_id` + `source_type` 生成，避免重复写入。

---

## 4. Schema / 接口变更

### 4.1 后端 API

`POST /api/practice/v7/sessions/{session_id}/submit` 返回基础反馈：

```json
{
  "attempt_id": "att_xxx",
  "is_correct": true,
  "correct_answer": ["A"],
  "analysis": "...",
  "metacognition_feedback": "..."
}
```

新增 `GET /api/practice/v7/feedback/{attempt_id}` 返回完整反馈：

```json
{
  "attempt_id": "att_xxx",
  "session_id": "sess_xxx",
  "question_id": "q_xxx",
  "is_correct": true,
  "correct_answer": ["A"],
  "analysis": "...",
  "metacognition_feedback": "...",
  "information_gain": 0.42,
  "uncertainty_reduction_percent": 18.5,
  "next_action_type": "review_weak_node",
  "next_action_text": "建议回顾相关概念"
}
```

### 4.2 事件类型

`cognitive_events` 表新增 `event_type = 'cognitive_reward'`，无需改表结构（`event_type` 是字符串）。

### 4.3 前端类型

`frontend/src/lib/api/practice-api.ts`：

```ts
export interface V7SubmitResult {
  attempt_id: string;
  is_correct: boolean;
  correct_answer: string[];
  analysis: string;
  consecutive_correct: number;
  mastered: boolean;
  wrong_count_increased: boolean;
  metacognition_feedback?: string;
}

export interface V7FeedbackResult {
  attempt_id: string;
  session_id: string;
  question_id: string;
  is_correct: boolean;
  correct_answer: string[];
  analysis: string;
  metacognition_feedback?: string;
  information_gain?: number;
  uncertainty_reduction_percent?: number;
  next_action_type?: string;
  next_action_text?: string;
}
```

### 4.4 前端组件

- `FeedbackPanel`：增加 `attemptId` prop，挂载后调用 `getFeedback(attemptId)`；展示 `information_gain` 和 `uncertainty_reduction_percent` 文案。
- `QuestionCard`：透传 `attemptId` 到 `FeedbackPanel`。
- `PracticePanel`：提交成功后保存 `attemptId` 并触发反馈拉取。

---

## 5. 关键算法与伪代码

### 5.1 信息增益计算

已在 `belief_operations.py` 中实现：

```python
entropy_before = _beta_entropy(alpha_before, beta_before)
entropy_after = _beta_entropy(alpha_after, beta_after)
information_gain = max(0.0, entropy_before - entropy_after)
```

不确定性降低百分比：

```python
if entropy_before > 0:
    reduction_pct = min(99.9, information_gain / entropy_before * 100)
else:
    reduction_pct = 0.0
```

### 5.2 发布 cognitive_reward 事件

```python
def handle_practice_response(self, event):
    # ... 写入 practice_events, 更新投影 ...
    ig_result = self._builder.apply_practice_event(...)
    information_gain = ig_result.get("information_gain", 0.0)

    # 发布 cognitive_reward
    reward_event = CognitiveEventORM(
        user_id=user_id,
        event_type="cognitive_reward",
        actor_type="system",
        source_type="practice_response",
        source_id=practice_event.id,
        node_id=node_id,
        payload={
            "node_id": node_id,
            "source_type": "practice_response",
            "source_event_id": practice_event.id,
            "reward_value": information_gain,
            "reward_unit": "nats",
            "belief_before": {"alpha": alpha_before, "beta": beta_before},
            "belief_after": {"alpha": alpha_after, "beta": beta_after},
            "confidence": 1.0,
            "context": {
                "is_correct": is_correct,
                "question_id": question_id,
                "difficulty": difficulty,
            },
        },
        idempotency_key=f"cr_{practice_event.id}_{node_id}",
    )
    self._session.add(reward_event)
    self._session.commit()

    return {"status": "ok", "information_gain": information_gain, ...}
```

---

## 6. 测试策略

### 6.1 单元测试

- `test_belief_operations.py`：验证 `belief_update` 返回的 `information_gain` 非负，且 `entropy_after <= entropy_before`。
- `test_cognitive_event_handler.py`：验证 `handle_practice_response()` 返回 `information_gain`，并写入 `cognitive_reward` 事件。
- `test_cognitive_reward_handler.py`：验证 `cognitive_reward` handler 只持久化、不修改投影。

### 6.2 集成测试

- `test_practice_submit.py`：验证 `POST /sessions/{id}/submit` 返回 `attempt_id`。
- `test_feedback_api.py`：验证 `GET /feedback/{attempt_id}` 返回包含 `information_gain` 和 `uncertainty_reduction_percent`。
- 验证多次提交同一题（幂等）不会产生重复 `cognitive_reward` 事件。

### 6.3 端到端测试

- 通过浏览器/MCP 完成一次练习提交，确认 FeedbackPanel 展示信息增益文案。
- 验证考试模式切换后文案隐藏。

### 6.4 边界与异常

- 首次答题（α=1, β=1）的信息增益展示。
- 已掌握节点（α 很大，β 很小）的信息增益可能接近 0，文案降级。
- 多 node 关联一题时，取最大信息增益。
- `belief_update` 异常时，仍返回基础反馈，信息增益字段为 null。

---

## 7. 风险点与回滚方案

| 风险 | 影响 | 缓解 | 回滚 |
|---|---|---|---|
| 信息增益计算依赖 scipy，新环境缺失 | 后端报错 | 已在 `requirements.txt` 声明 scipy | 临时 fallback 为 0 |
| 前端文案让用户困惑 | 体验下降 | A/B 文案 + 可关闭开关 | 隐藏信息增益文案，恢复传统反馈 |
| `cognitive_reward` 事件重复写入 | 数据膨胀 | 幂等键 | 清理重复事件 |
| 多 node 聚合策略不当 | 反馈失真 | 先取 max，后续可配置 | 改为 sum 或平均 |
| 考试模式信息增益仍展示 | 与 ADR 冲突 | 前端按 mode 控制 | 加 feature flag |

---

## 8. 任务拆分

| # | 子任务 | 验收条件 | 依赖 |
|---|---|---|---|
| 1 | `ProjectionBuilder` 返回信息增益 | `apply_practice_event()` 返回 `information_gain` 及 belief before/after | - |
| 2 | `CognitiveEventHandler` 发布 `cognitive_reward` | 处理 `practice_response` 后写入 `cognitive_events`（event_type='cognitive_reward'），幂等 | 1 |
| 3 | 新增 `FeedbackService` / `FeedbackBuilder` | 能根据 `attempt_id` 生成完整反馈（含 info gain） | 1 |
| 4 | 新增 `GET /feedback/{attempt_id}` API | 返回完整反馈 DTO | 3 |
| 5 | 前端 `FeedbackPanel` 拉取并展示 | 提交后拉取反馈，按 15% 阈值渲染文案 | 4 |
| 6 | 单元/集成测试 | 相关测试通过 | 1-5 |
| 7 | 端到端验证 | 浏览器验证反馈面板 | 6 |

---

## 9. 后续可扩展

- 对话评估信息增益：对话系统评估用户理解后，发布 `cognitive_reward`，`source_type="conversation_assessment"`。
- 秘书系统订阅 `cognitive_reward` 调整信任积分和推荐策略。
- 首页"引力种子"可基于 `total_information_gain` 和 `last_information_gain` 计算节点活跃度。
