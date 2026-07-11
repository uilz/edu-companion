# Task 0028: Phase 6 — 前端提案、计划与反馈展示

## 1. 目标

将 Phase 4-5 后端产生的「秘书提案」与「待确认计划项」以及 Phase 3 认知中心产生的「信息增益」以可交互方式呈现给用户：

- 用户在秘书页可接受/忽略/完成秘书提案，并看到提案触发的计划项/导航结果。
- 用户在规划页可查看并处理 Phase 5 生成的待确认计划项。
- 用户在练习提交答案后，可在反馈面板看到信息增益、掌握度变化与元认知建议。

## 2. 范围

### 2.1 后端

- 新增 `GET /api/practice/feedback/{attempt_id}`：返回答题后的信息增益、掌握度变化、元认知建议。
- 修正 `PracticeEngine.submit_answer`：返回 `attempt_id` 且与 `AnswerSubmitted.attempt_id` / `practice_attempts.id` 一致。
- （可选）新增 `GET /api/planning/confirmations/pending-count` 小红点计数。

### 2.2 前端

- `ProposalCard` 升级：区分「秘书提案」与「计划项确认请求」，展示来源、原因、预期时长，操作后触发对应 API。
- `PlanItemList` 新增：在 `/planning/daily` 页面顶部增加「待确认」池，支持一键接受/忽略。
- `FeedbackPanel` 升级：在现有正确/错误/解析/元认知反馈基础上，新增信息增益与掌握度变化展示。
- `usePlanning` Hook 扩展：增加 confirmations CRUD 方法。
- `usePracticeSession` Hook 扩展：提交后读取 `attempt_id` 并拉取反馈。

## 3. 现状分析

### 3.1 后端现状

| 能力 | 现状 | 缺口 |
|------|------|------|
| 答题提交 | `POST /api/practice/sessions/{id}/submit` 返回 `submitted_event_id`、`is_correct`、`analysis`、`metacognition_feedback` | 无 `attempt_id` 返回；事件中的 `attempt_id` 与 `practice_attempts.id` 不一致 |
| 信息增益 | `CognitiveEventHandler` 将 `cognitive_reward` 写入 `cognitive_events` 表；`CognitiveStateChanged` 携带 `information_gain` | 无 API 供前端按 attempt 查询 |
| 待确认计划项 | Phase 5 已实现 `/api/planning/confirmations`、`/accept`、`/dismiss` | 前端未对接 |
| 秘书提案 | `/api/secretary/proposals/pending`、`/accept` 已存在 | 未与 planning confirmations 联动展示 |

### 3.2 前端现状

- `ProposalCard`：仅展示 `SecretaryNotification`，来源标签写死，未对接 planning confirmations。
- `FeedbackPanel`：展示正确性、解析、元认知反馈，缺少信息增益。
- `usePlanning`：缺少 confirmations 相关 API 封装。
- `/planning/daily`：仅有时间轴与待安排池，无待确认区域。

## 4. 关键决策

### 4.1 attempt_id 一致性（必须先解决）

**方案 A：修改 submit_answer 返回统一 attempt_id**
- `PracticeEngine.submit_answer` 在写入 `practice_attempts` 前生成 `attempt_id = f"att_{session_id}_{question_id}_{timestamp}"`。
- 将同一 `attempt_id` 用于 `AnswerSubmitted.attempt_id`。
- `submit_answer` 返回 `{ ..., attempt_id }`。
- `GET /api/practice/feedback/{attempt_id}` 通过 `practice_attempts.id` 定位记录。

**方案 B：feedback API 用 event_id 查询**
- 前端使用 `submitted_event_id` 调用 `GET /api/practice/feedback/{event_id}`。
- 后端通过 `cognitive_events` 表按 `source_event_id` 或事件 ID 查找。

**推荐：方案 A**。理由：
- `task0015` 明确要求 `GET /feedback/{attempt_id}`。
- `attempt_id` 是用户可理解的答题尝试标识，`event_id` 是内部事件标识。
- 统一 `attempt_id` 后，遥测、错题本、反馈链路都能对齐。

### 4.2 信息增益反馈数据来源

**方案 A：查询 cognitive_events（cognitive_reward）**
- 通过 `practice_attempts.id` → `practice_events(session_id, question_id)` → `cognitive_events(event_type='cognitive_reward', source_id=practice_event.id)`。
- 优点：数据权威，包含 belief_before/after。
- 缺点：需要多表 join，依赖认知事件 handler 已执行。

**方案 B：查询 cognitive_node_projections（最新投影）**
- 直接读取节点当前 `proficiency`、`uncertainty`、`total_information_gain`。
- 优点：查询简单。
- 缺点：无法精确反映「本次答题」带来的增量，只能展示当前状态。

**推荐：方案 A 为主，方案 B 兜底**。理由：
- 反馈面板要展示的是「这次答题带来的学习价值」，需要本次增量。
- 若 cognitive_reward 尚未生成（异步延迟），则回退到当前投影。

### 4.3 秘书提案与计划项确认的关系

**方案 A：秘书页统一展示 proposals + confirmations**
- `/secretary` 页面同时拉取 `/api/secretary/proposals/pending` 和 `/api/planning/confirmations?status=pending`。
- 计划项确认请求以特殊 `actionType='plan_item_confirmation'` 的提案形式混入通知列表。

**方案 B：分离展示**
- 秘书页只展示秘书提案。
- 规划页 `/planning/daily` 顶部单独展示待确认计划项。

**推荐：方案 A + B 结合**。理由：
- 用户痛点是「不知道要处理什么」，统一入口能降低认知负担。
- 但规划页也要有专门区域，因为确认后直接进入计划项，与规划场景强相关。

### 4.4 FeedbackPanel 信息增益展示时机

**方案 A：提交后立即拉取**
- `submit_answer` 返回 `attempt_id` 后，前端立即调用 `GET /api/practice/feedback/{attempt_id}`。
- 若 cognitive_reward 尚未生成，显示加载状态并轮询。

**方案 B：提交返回即包含反馈**
- 在 `submit_answer` 中同步等待认知事件处理完成后再返回。
- 优点：一次请求拿到全部数据。
- 缺点：阻塞用户交互，破坏事件驱动异步边界。

**推荐：方案 A**。理由：
- 保持答题提交快速响应。
- 认知处理可异步完成，前端通过轮询或 SSE 获取反馈。
- Phase 6 v1 采用轮询（简单），后续可升级为 SSE。

## 5. API 契约

### 5.1 提交答题返回扩展

```json
POST /api/practice/sessions/{session_id}/submit
{
  "question_id": "q_xxx",
  "answer": ["A"],
  "time_spent": 12,
  "confidence_before": 4
}

Response 200:
{
  "is_correct": true,
  "correct_answer": ["A"],
  "analysis": "...",
  "metacognition_feedback": "...",
  "attempt_id": "att_session_q_1721234567",
  "submitted_event_id": "evt_xxx"
}
```

### 5.2 答题反馈查询

```json
GET /api/practice/feedback/{attempt_id}

Response 200:
{
  "attempt_id": "att_session_q_1721234567",
  "session_id": "session_xxx",
  "question_id": "q_xxx",
  "is_correct": true,
  "submitted_at": "2026-07-11T15:23:00Z",
  "feedback": {
    "information_gain": 0.42,
    "uncertainty_reduction_percent": 18.5,
    "proficiency_before": 0.55,
    "proficiency_after": 0.68,
    "uncertainty_before": 0.30,
    "uncertainty_after": 0.24,
    "nodes": [
      {
        "node_id": "kn_xxx",
        "label": "导数定义",
        "information_gain": 0.42,
        "proficiency_before": 0.55,
        "proficiency_after": 0.68
      }
    ]
  },
  "metacognition": {
    "advice": "你确实掌握了，自信是对的",
    "confidence_before": 4,
    "bias": "accurate"
  },
  "suggestions": [
    {
      "type": "review",
      "title": "复习相关知识",
      "node_id": "kn_xxx",
      "reason": "掌握度仍有提升空间"
    }
  ]
}
```

### 5.3 待确认计划项 API（已存在，前端对接）

```json
GET /api/planning/confirmations?status=pending
POST /api/planning/confirmations/{id}/accept
POST /api/planning/confirmations/{id}/dismiss
```

### 5.4 待确认数量小红点

```json
GET /api/planning/confirmations/pending-count
Response 200:
{
  "count": 3
}
```

## 6. 数据查询策略

### 6.1 GET /api/practice/feedback/{attempt_id}

```python
def get_feedback(user_id: str, attempt_id: str) -> dict:
    # 1. 验证 practice_attempts 归属
    attempt = db.fetchone(
        "SELECT * FROM practice_attempts WHERE id=%s AND user_id=%s",
        (attempt_id, user_id)
    )
    if not attempt:
        raise HTTPException(404)

    # 2. 找 practice_event
    pe = db.fetchone(
        "SELECT * FROM practice_events WHERE session_id=%s AND question_id=%s AND user_id=%s ORDER BY timestamp DESC LIMIT 1",
        (attempt["session_id"], attempt["question_id"], user_id)
    )

    # 3. 找 cognitive_reward
    reward = None
    if pe:
        reward = db.fetchone(
            "SELECT payload FROM cognitive_events WHERE event_type='cognitive_reward' AND source_id=%s AND user_id=%s",
            (pe["id"], user_id)
        )

    # 4. 组装反馈
    if reward:
        payload = reward["payload"]
        return _build_feedback_from_reward(attempt, payload)

    # 5. 兜底：当前投影
    return _build_feedback_from_projections(attempt)
```

## 7. 前端组件设计

### 7.1 ProposalCard 扩展

增加对 `type === 'plan_item_confirmation'` 的渲染分支：

- 标题前显示 ⏳ 图标。
- 展示 `estimated_minutes`、`priority`、生成原因（如「掌握度低于 50%」）。
- 操作按钮：接受（创建 plan item）、忽略。
- 普通秘书提案保持现有接受/忽略/延后/隐藏逻辑。

### 7.2 PlanItemConfirmationPool（新增组件）

在 `/planning/daily` 页面顶部渲染：

```tsx
<PlanItemConfirmationPool
  confirmations={data.confirmations}
  onAccept={handleAccept}
  onDismiss={handleDismiss}
/>
```

- 仅在有 pending confirmations 时显示。
- 每个确认项以紧凑卡片展示，支持展开详情。

### 7.3 FeedbackPanel 扩展

在现有 Props 基础上新增：

```tsx
interface Props {
  // 已有
  isCorrect: boolean;
  correctAnswer: string[];
  analysis?: string;
  skipped?: boolean;
  score?: number;
  metacognitionFeedback?: string;
  confidenceBefore?: number | null;
  // 新增
  attemptId?: string;
}
```

内部通过 `useAttemptFeedback(attemptId)` 拉取信息增益：

```tsx
const { feedback, loading } = useAttemptFeedback(attemptId);
```

展示：
- 信息增益数值（如 +0.42 nats）
- 掌握度变化条（before → after）
- 涉及知识点标签
- 若 feedback 未就绪，显示「认知分析中…」

### 7.4 Hooks 扩展

`usePlanning.ts` 新增：

```tsx
export function usePlanItemConfirmations(status?: string) { ... }
export function useAcceptConfirmation() { ... }
export function useDismissConfirmation() { ... }
export function usePendingConfirmationCount() { ... }
```

`usePracticeSession.ts` 提交后：

```tsx
const result = await submitAnswer(...);
setLastAttemptId(result.attempt_id);
```

新增 `useAttemptFeedback(attemptId?: string)` Hook。

## 8. 核心流程

### 8.1 练习反馈展示

```
用户提交答案
  │
  ▼
POST /api/practice/sessions/{id}/submit
  │ 返回 attempt_id + 基本反馈
  ▼
FeedbackPanel 渲染基本反馈（正确/错误/解析/元认知）
  │
  ▼
useAttemptFeedback(attempt_id) 轮询 GET /api/practice/feedback/{attempt_id}
  │
  ▼
信息增益、掌握度变化展示
```

### 8.2 待确认计划项处理

```
PlanningProactiveGenerator 发布 PlanItemSuggested
  │
  ▼
SecretaryEventHandler 中转 → PlanItemRequested(requires_user_confirmation=True)
  │
  ▼
PlanningEventHandler 写入 plan_item_confirmations
  │
  ▼
前端拉取 /planning/confirmations?status=pending
  │
  ├─ 用户接受 → POST /accept → 创建 plan item → 进入日视图时间轴
  │
  └─ 用户忽略 → POST /dismiss → 状态更新
```

### 8.3 秘书提案与计划项确认统一入口

```
/secretary 页面加载
  │
  ├─ GET /api/secretary/proposals/pending
  ├─ GET /api/planning/confirmations?status=pending
  │
  ▼
合并为 SecretaryNotification[] 列表
  │
  ▼
ProposalCard 根据 type 渲染不同操作
```

## 9. 实现文件

### 后端
- `backend/app/services/practice/engine.py` — 生成统一 `attempt_id` 并返回。
- `backend/app/services/practice/session_repository.py` — `insert_attempt` 支持传入 `attempt_id`。
- `backend/app/api/practice/feedback_service.py` — 组装 feedback 数据（cognitive_reward 优先，投影兜底）。
- `backend/app/api/practice/practice_routes/sessions.py` — 新增 `GET /api/practice/feedback/{attempt_id}`。
- `backend/app/services/common/analytics_stub.py` — 修复 `AnswerSubmitted` 字段访问。
- `backend/tests/test_phase6_feedback_api.py` — feedback API 集成测试。

### 前端
- `frontend/src/lib/api/practice-api.ts` — `AttemptFeedback` 类型与 `getAttemptFeedback`。
- `frontend/src/hooks/practice/useAttemptFeedback.ts` — 轮询拉取反馈 hook。
- `frontend/src/components/practice/components/FeedbackPanel.tsx` — 信息增益与掌握度变化展示。
- `frontend/src/components/practice/components/QuestionCard.tsx` — 传递 `attempt_id`。
- `frontend/src/hooks/planning/usePlanning.ts` — `PlanItemConfirmation` 类型、`usePlanItemConfirmations`、accept/dismiss mutations。
- `frontend/src/components/planning/PlanItemConfirmationPool.tsx` — 待确认计划项池组件。
- `frontend/src/app/planning/daily/page.tsx` — 渲染待确认计划项池。
- `frontend/src/components/secretary/shared.ts` — `confirmationToNotification`、扩展 `ActionType`。
- `frontend/src/components/secretary/ProposalCard.tsx` — 计划项确认专用操作。
- `frontend/src/store/notification/types.ts` — 扩展 `ActionType`。
- `frontend/src/app/secretary/page.tsx` — 合并展示 proposals 与 confirmations。

## 10. 验收条件

- [x] `submit_answer` 返回 `attempt_id`，且与 `AnswerSubmitted.attempt_id`、`practice_attempts.id` 一致。
- [x] 新增 `GET /api/practice/feedback/{attempt_id}`，返回信息增益、掌握度变化、元认知建议。
- [x] 后端有单元/集成测试覆盖 feedback API（`test_phase6_feedback_api.py` 5 项全部通过）。
- [x] `FeedbackPanel` 展示信息增益与掌握度变化（加载态 + 错误态）。
- [x] `/planning/daily` 页面展示待确认计划项池，支持接受/忽略。
- [x] `/secretary` 页面能展示待确认计划项，操作后同步更新 planning confirmations。
- [x] 新增或更新前端 Hooks/API 封装。
- [x] `rebuild.sh --skip-build --skip-admin` 端到端验证通过。
- [x] 更新 ADR 或设计文档。

## 11. 风险与缓解

| 风险 | 影响 | 缓解 |
|------|------|------|
| 修改 submit_answer 的 attempt_id 影响现有事件/测试 | 回归 | 同步更新事件契约测试与 E2E 测试 |
| cognitive_reward 异步生成导致 feedback API 返回兜底数据 | 用户体验 | API 明确标识 `is_final`，前端轮询 |
| 秘书提案与 confirmations 合并展示导致类型复杂 | 维护性 | 引入统一的 `SecretaryNotification` 转换层 |
| 前端状态更新后不同步 | 数据不一致 | 操作成功后统一 invalidate 相关 query |

## 12. 相关文档

- `docs/temp/task0015-target-architecture-vision.md`
- `docs/temp/task0027-planning-proactive-generation-design.md`
- `docs/adr/0020-planning-proactive-generation.md`
- `docs/adr/0019-secretary-orchestrator-phase4.md`
