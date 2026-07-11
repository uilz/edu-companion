# Task 0013: 练习模块架构重构设计文档

> 目标：将练习模块从"同步大函数 + 事件补丁"模式，重构为事件驱动、职责分离、与认知中心深度协同的现代架构。
> 状态：方案对比阶段，待用户选定方向。

---

## 1. 现状诊断

### 1.1 文件地图

```
backend/app/api/practice/practice_routes/
├── sessions.py          # API 路由：创建/提交/完成会话
├── misc.py              # 独立练习提交、题库查询等
├── errors.py            # 错题本 API
└── ...

backend/app/services/practice/
├── practice_session.py  # 会话门面：create/submit/complete/get
├── engine.py            # 事件发布 + 模块聚合入口
├── session_repository.py# 会话/答题记录持久化
├── session_engine.py    # 判题、统计、状态转换
├── practice_adaptive.py # 自适应选题
├── practice_service.py  # 认知更新、提示、错题本等业务函数
├── practice_question_bank.py / practice_question_crud.py / practice_question_gen.py
└── ...

backend/app/domain/cognitive/
├── events.py            # CognitiveEventHandler：处理 practice_response / information_gain_event 等
├── operations/          # belief_update / graph_propagate / scheduling 等
└── ...

backend/app/infrastructure/
├── event_bus.py         # 内存事件总线
├── persistent_event_bus.py # 持久化事件总线
└── db/cognitive_repository.py # 认知仓库 + 视图映射

frontend/src/components/practice/
├── panels/PracticePanel.tsx
├── components/QuestionCard.tsx
├── components/FeedbackPanel.tsx
└── ...

frontend/src/lib/api/practice-api.ts
```

### 1.2 当前调用链（简化）

```
用户提交答案
  ↓
api_submit_answer (sessions.py)
  ↓
submit_answer (practice_session.py)
  ├── 验证 session & 题目归属
  ├── check_answer 判对错
  ├── repo.insert_attempt 写 practice_attempts
  ├── repo.update_session_stats 更新统计
  ├── get_repo().sync_from_practice_event 直接更新认知投影
  └── asyncio.ensure_future(publish_practice_events) 异步发布事件
  ↓
返回 {is_correct, correct_answer, analysis, metacognition_feedback}
  ↓
前端 FeedbackPanel 展示
```

### 1.3 核心问题

| # | 问题 | 说明 |
|---|---|---|
| 1 | **submit_answer 职责过重** | 一个 150+ 行函数处理验证、判题、持久化、统计、认知更新、事件发布、反馈组装，违反单一职责 |
| 2 | **认知状态双路径更新** | `sync_from_practice_event()` 直接更新 + `PracticeSubmitted` 事件异步发布，语义重复，易不一致 |
| 3 | **反馈生成与认知投影割裂** | `metacognition_feedback` 只基于 `confidence_before` 和 `is_correct`，未利用 Beta 信念变化 |
| 4 | **同步/异步混杂** | `submit_answer` 是 sync 函数，却用 asyncio fire-and-forget 发布事件，错误难追踪 |
| 5 | **事件语义重复** | `AnswerSubmitted`（analytics）和 `PracticeSubmitted`（cognitive）都描述一次答题，增加维护成本 |
| 6 | **没有反馈投影** | 反馈临时计算，无法支持：异步复杂反馈、历史反馈审计、秘书系统基于反馈调整策略 |
| 7 | **前端只依赖同步返回** | 无法接收练习完成后异步生成的元认知建议、复习推荐、信息增益深度分析 |

---

## 2. 重构目标

1. **单一职责**：`submit_answer` 只负责接收命令、写入事实、发布事件；反馈由独立 builder 生成。
2. **唯一事实源**：一次答题只产生一个核心领域事件 `AnswerSubmitted`，认知中心通过订阅该事件更新投影。
3. **反馈投影化**：建立 `FeedbackProjection`，从认知投影和事件流构建完整反馈视图。
4. **同步基础 + 异步增强**：基础反馈（正确/错误/答案）同步返回；信息增益、元认知建议、复习推荐可异步生成。
5. **事件驱动**：练习模块不再直接调用认知仓库，而是通过事件总线与认知中心、秘书系统解耦。
6. **可测试性**：每个组件可独立单元测试，链路可通过事件回放验证。

---

## 3. 方案对比

### 方案 A：领域事件驱动 + FeedbackProjection（推荐）

**核心思想**：
- `submit_answer` 只写 `practice_attempts` 并发布 `AnswerSubmitted` 事件。
- 认知中心订阅 `AnswerSubmitted`，生成/更新 `cognitive_node_projections`。
- 新增 `FeedbackBuilder`，从 `cognitive_node_projections` 和 `practice_attempts` 生成 `FeedbackProjection`。
- 前端 `submit_answer` 同步返回基础反馈；通过 `/feedback/{attempt_id}` 拉取完整反馈（含信息增益、元认知建议）。

**架构图**：

```
用户提交答案
  ↓
submit_answer
  ├── insert_attempt
  └── publish(AnswerSubmitted)
       ├── CognitiveEventHandler → update projection
       ├── SecretaryEventHandler → generate proposals
       └── FeedbackBuilder → upsert FeedbackProjection
  ↓
返回 {attempt_id, is_correct, correct_answer, basic_feedback}
  ↓
前端拉取 /feedback/{attempt_id} → FeedbackProjection
  ↓
FeedbackPanel 展示
```

**优点**：
- 职责最清晰，练习模块与认知中心完全解耦。
- 反馈可扩展：未来可加入 LLM 生成的深度解析、复习推荐、情绪适配等。
- 支持审计和回放：`FeedbackProjection` 可从事件重建。
- 认知状态更新单一路径，避免双写。

**缺点**：
- 改造成本中上：需要新增 FeedbackBuilder、FeedbackProjection、拉取 API。
- 前端需要改为"提交后拉取完整反馈"，交互有小变化。

**适用性**：**最符合 ADR 0013/0015 的长线架构**。

---

### 方案 B：CQRS + 保留同步反馈

**核心思想**：
- 保留 `submit_answer` 同步返回完整反馈（与现状一致）。
- 但把反馈生成逻辑抽到 `FeedbackService`，`submit_answer` 同步调用它。
- `FeedbackService` 从认知投影读取 Beta 状态，生成信息增益、元认知建议。
- 同时发布 `AnswerSubmitted` 事件，供秘书系统和 analytics 异步消费。

**架构图**：

```
用户提交答案
  ↓
submit_answer
  ├── insert_attempt
  ├── sync update projection (直接调用 cognitive repo)
  ├── feedback = FeedbackService.generate(...)
  ├── publish(AnswerSubmitted) // 异步
  └── return feedback
```

**优点**：
- 前端交互不变，改造成本较低。
- 反馈生成集中，避免散落在 practice_session 中。

**缺点**：
- 认知状态更新仍在 `submit_answer` 主路径中，未完全解耦。
- `AnswerSubmitted` 事件发布后，认知中心可能再次处理同一事件，需做幂等。
- 反馈仍是临时计算，未投影化，无法支撑异步增强反馈。

**适用性**：**中等改造，适合快速看到信息增益 UI，但架构债未根本解决**。

---

### 方案 C：全面重写 Practice Engine

**核心思想**：
- 引入 `PracticeAggregateRoot` 作为练习领域的聚合根。
- 所有操作变为命令：`CreateSessionCommand`、`SubmitAnswerCommand`、`CompleteSessionCommand`。
- 命令产生事件：`SessionCreated`、`AnswerSubmitted`、`SessionCompleted`。
- 建立独立的 `PracticeProjection`（会话视图）、`FeedbackProjection`、`CognitiveProjection`。
- 前端通过 SSE 或 WebSocket 订阅反馈事件。

**优点**：
- 最符合 DDD + 事件溯源的纯模型。
- 可扩展性最强。

**缺点**：
- 改造成本最高，涉及 10+ 文件重写。
- 需要引入命令总线、聚合根、投影重建等基础设施。
- 当前项目阶段可能过度设计。

**适用性**：**长期理想形态，但当前不建议一次性落地**。

---

### 方案 D：渐进式重构

**核心思想**：
- 第一阶段：拆分 `submit_answer` 为验证、判题、持久化、认知联动、事件发布、反馈组装 6 个独立函数。
- 第二阶段：把认知联动改为事件订阅，移除 `sync_from_practice_event()` 直接调用。
- 第三阶段：引入 `FeedbackProjection` 和拉取 API。
- 第四阶段：统一事件语义，合并 `PracticeSubmitted` 到 `AnswerSubmitted`。

**优点**：
- 风险可控，每阶段可独立验证和回滚。
- 符合"一次只做一件事"的完美执行协议。

**缺点**：
- 总周期较长。
- 中间状态可能存在临时兼容层。

**适用性**：**最稳健，推荐作为实施方案**。

---

## 4. 推荐方案

**采用方案 D（渐进式重构），但第一阶段一次性做到方案 A 的骨架**：

具体落地方案：

### 4.1 事件语义统一

- 保留 `AnswerSubmitted` 作为练习域唯一核心事件。
- **废弃 `PracticeSubmitted`**：认知中心改为订阅 `AnswerSubmitted`，而不是接收 `PracticeSubmitted`。
- `AnswerSubmitted` 增加字段：`cognitive_node_ids`、`difficulty`、`response_time_ms`、`confidence_before`。

### 4.2 练习模块职责拆分

```python
# submit_answer 只负责：
def submit_answer(...) -> SubmitAnswerResult:
    attempt = record_attempt(...)
    publish(AnswerSubmitted(...))
    return SubmitAnswerResult(
        attempt_id=attempt.id,
        is_correct=attempt.is_correct,
        correct_answer=attempt.correct_answer,
    )

# 反馈生成：
class FeedbackService:
    def generate(self, attempt_id: str) -> FeedbackProjection:
        attempt = get_attempt(attempt_id)
        projection = get_projection(attempt.node_id, attempt.user_id)
        return FeedbackProjection(
            is_correct=attempt.is_correct,
            correct_answer=attempt.correct_answer,
            analysis=attempt.analysis,
            information_gain=projection.last_information_gain,
            uncertainty_reduction=...,
            metacognition_feedback=...,
            next_action_recommendation=...,
        )
```

### 4.3 认知中心订阅 `AnswerSubmitted`

```python
class CognitiveEventHandler:
    def handle_answer_submitted(self, event: AnswerSubmitted):
        for node_id in event.cognitive_node_ids:
            self.handle_practice_response(
                user_id=event.user_id,
                node_id=node_id,
                success=event.is_correct,
                latency_ms=event.response_time_ms,
                question_id=event.question_id,
                difficulty=event.difficulty,
                confidence_before=event.confidence_before,
            )
```

### 4.4 FeedbackProjection

新表/ORM：`practice_feedback_projections`

字段：
- `attempt_id` (PK)
- `user_id`
- `session_id`
- `question_id`
- `node_id`
- `is_correct`
- `information_gain`
- `uncertainty_reduction_percent`
- `metacognition_feedback`
- `analysis`
- `next_action_type`
- `created_at`

由 `FeedbackBuilder` 在 `AnswerSubmitted` 事件处理后生成，或按需生成。

### 4.5 前端适配

- `submitAnswer` 返回增加 `attempt_id`。
- `FeedbackPanel` 增加 `attemptId`，组件挂载后拉取 `/api/practice/v7/feedback/{attempt_id}`。
- 展示信息增益文案和元认知反馈。

---

## 5. 关键设计决策

| 决策 | 选择 | 理由 |
|---|---|---|
| 核心事件 | `AnswerSubmitted` | 统一事实源，替代 `PracticeSubmitted` |
| 认知更新方式 | 事件订阅 | 解耦练习模块与认知中心 |
| 反馈生成 | `FeedbackService` + `FeedbackProjection` | 可扩展、可审计、可回放 |
| 前后端交互 | 同步基础返回 + 拉取完整反馈 | 平衡体验和架构 |
| 多 node 聚合 | 取最大信息增益 | 单题反馈不过度稀释 |
| 考试模式 | 保留传统正确/错误 + 分数 | 满足备考场景需求 |

---

## 6. Schema / 接口变更

### 6.1 后端 API

`POST /api/practice/v7/sessions/{session_id}/submit` 返回：

```json
{
  "attempt_id": "att_xxx",
  "is_correct": true,
  "correct_answer": ["A"],
  "already_answered": false
}
```

新增：

`GET /api/practice/v7/feedback/{attempt_id}` 返回：

```json
{
  "attempt_id": "att_xxx",
  "is_correct": true,
  "correct_answer": ["A"],
  "analysis": "...",
  "information_gain": 0.42,
  "uncertainty_reduction_percent": 18.5,
  "metacognition_feedback": "...",
  "next_action_type": "review_weak_node",
  "next_action_text": "建议回顾相关概念"
}
```

### 6.2 事件变更

`AnswerSubmitted` 增加字段：

```python
@dataclass(frozen=True)
class AnswerSubmitted(DomainEvent):
    ...
    cognitive_node_ids: list[str] = field(default_factory=list)
    difficulty: float = 0.0
    response_time_ms: int = 0
    confidence_before: int | None = None
```

### 6.3 新增表

```sql
CREATE TABLE practice_feedback_projections (
    attempt_id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    session_id TEXT NOT NULL,
    question_id TEXT NOT NULL,
    node_id TEXT,
    is_correct BOOLEAN NOT NULL,
    information_gain FLOAT DEFAULT 0,
    uncertainty_reduction_percent FLOAT DEFAULT 0,
    metacognition_feedback TEXT DEFAULT '',
    analysis TEXT DEFAULT '',
    next_action_type TEXT DEFAULT '',
    next_action_text TEXT DEFAULT '',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
```

### 6.4 废弃

- `PracticeSubmitted` 事件类型（或标记为 deprecated，保留一段时间供旧 handler 兼容）。
- `publish_practice_events()` 中的 `PracticeSubmitted` 发布逻辑。
- `submit_answer` 中的 `sync_from_practice_event()` 直接调用。

---

## 7. 任务拆分

| # | 子任务 | 验收条件 | 依赖 |
|---|---|---|---|
| 1 | 扩展 `AnswerSubmitted` 事件字段 | `shared/events.py` 增加字段，不破坏旧订阅者 | - |
| 2 | 认知中心订阅 `AnswerSubmitted` | `CognitiveEventHandler` 新增 handler，移除对 `PracticeSubmitted` 的依赖 | 1 |
| 3 | 拆分 `submit_answer` | 抽出 `record_attempt`、`publish_answer_submitted` 等函数；移除直接认知联动 | 1 |
| 4 | 新增 `FeedbackService` + `FeedbackProjection` | 能根据 attempt_id 生成完整反馈 | 2 |
| 5 | 新增反馈拉取 API | `GET /feedback/{attempt_id}` 返回完整反馈 | 4 |
| 6 | 前端适配 | `FeedbackPanel` 拉取并展示信息增益文案 | 5 |
| 7 | 清理 `PracticeSubmitted` | 移除事件定义和发布逻辑 | 2-6 |
| 8 | 单元/集成/端到端测试 | 相关测试通过 | 1-7 |
| 9 | 文档归档 | 更新 ADR / 模块文档 | 8 |

---

## 8. 风险与回滚

| 风险 | 缓解 | 回滚 |
|---|---|---|
| 事件订阅延迟导致反馈生成慢 | FeedbackBuilder 可同步兜底生成 | 前端直接展示基础反馈 |
| `AnswerSubmitted` 字段扩展破坏旧订阅者 | 新字段均有默认值 | 修复具体订阅者 |
| 认知状态更新从双路径变单路径后数据不一致 | 灰度验证 + 事件回放重建 | 恢复 `sync_from_practice_event` 直接调用 |
| 前端拉取反馈增加延迟 | 支持同步生成 + 缓存 | 改为同步返回完整反馈 |
| `PracticeSubmitted` 仍有秘书系统订阅 | 先让秘书系统同时订阅 `AnswerSubmitted`，再移除 `PracticeSubmitted` | 恢复订阅 |

---

## 9. 与 ADR 0013/0015 的对应关系

| ADR 要求 | 本方案落地 |
|---|---|
| 信息增益核心反馈算法 | `FeedbackService` 从 `cognitive_node_projections` 读取 `last_information_gain` |
| 信息增益 UI 文案 | `FeedbackPanel` 按正确性/增益渲染文案 |
| 信息增益作为 Reward 写入事件流 | `AnswerSubmitted` → 认知中心 → `cognitive_reward` 事件（后续 Task） |
| 全量事件流覆盖练习 | `AnswerSubmitted` 字段扩展，承载完整练习事实 |
| 秘书系统处理脏数据 | 秘书系统订阅 `AnswerSubmitted` 生成提案，不直接读写认知状态 |
| 认知中心只处理干净数据 | 认知中心通过订阅 `AnswerSubmitted` 更新投影 |
| 考试模式保留传统反馈 | `FeedbackService` 支持 `mode="exam"` 返回传统反馈 |
