# ADR 0021: Phase 6 — 前端提案、计划与反馈展示

## 状态

已接受 / 已实现

## 背景

Phase 3-5 分别完成了认知中心事件消费、秘书编排器增强、规划系统主动生成计划项。这些后端能力产生了三类用户可见的数据：

1. **答题后的信息增益**：`cognitive_events.event_type='cognitive_reward'` 记录了每次答题对知识点信念状态的更新。
2. **待确认计划项**：`plan_item_confirmations` 表存储了需要用户确认的 Planning 建议。
3. **秘书提案**：`secretary_proposals` 表存储了秘书系统生成的学习建议。

Phase 6 需要把这三类数据以可交互方式展示给用户，让用户在练习后看到学习价值、在规划页处理待确认项、在秘书页统一处理所有需要用户决策的事项。

## 决策

### 1. 统一 `attempt_id`

- `PracticeEngine.submit_answer` 在写入 `practice_attempts` 前生成统一 `attempt_id`。
- 同一 `attempt_id` 用于 `AnswerSubmitted.attempt_id` 和返回给前端的结果。
- `GET /api/practice/feedback/{attempt_id}` 通过 `practice_attempts.id` 定位记录。

理由：`attempt_id` 是用户可理解的答题尝试标识，统一后遥测、错题本、反馈链路都能对齐。

### 2. 反馈数据双源策略

- 主数据源：`cognitive_events.event_type='cognitive_reward'`，通过 `practice_events.id` 关联。
- 兜底数据源：`cognitive_node_projections` 当前投影。
- API 返回 `is_final` 字段标识是否已拿到权威认知奖励数据。

理由：反馈面板要展示「这次答题带来的学习价值」，需要本次增量；若 cognitive_reward 异步延迟，则回退到当前投影。

### 3. 前端轮询获取反馈

- `submit_answer` 保持快速响应，仅返回基础反馈 + `attempt_id`。
- 前端通过 `useAttemptFeedback(attempt_id)` 轮询 `GET /api/practice/feedback/{attempt_id}`，最多轮询 10 次。

理由：保持答题提交快速响应，认知处理可异步完成。

### 4. 秘书页与规划页都展示待确认计划项

- `/planning/daily` 页面顶部增加「待确认计划项池」，与规划场景强相关。
- `/secretary` 页面同时拉取 proposals 和 confirmations，统一渲染为 `SecretaryNotification`。
- 通过 `actionType='plan_item_confirmation'` 区分 confirmation 与普通提案。

理由：降低用户认知负担，同时保留规划场景的专门入口。

## 影响

- 练习反馈从「对错 + 解析」升级为「对错 + 解析 + 信息增益 + 掌握度变化 + 学习建议」。
- 规划系统生成的建议需要用户确认后才能进入日程，符合主动式规划的闭环。
- 秘书系统成为跨模块待办事项的统一入口。

## 实现要点

### 后端

- `backend/app/services/practice/engine.py`：生成统一 `attempt_id`。
- `backend/app/api/practice/feedback_service.py`：组装 feedback，优先 cognitive_reward，兜底 projections。
- `backend/app/api/practice/practice_routes/sessions.py`：新增 `GET /api/practice/feedback/{attempt_id}`。
- `backend/tests/test_phase6_feedback_api.py`：覆盖 attempt_id 一致性、404、数据隔离、基本结构、cognitive_reward。

### 前端

- `frontend/src/lib/api/practice-api.ts`：`AttemptFeedback` 类型 + `getAttemptFeedback`。
- `frontend/src/hooks/practice/useAttemptFeedback.ts`：轮询 hook。
- `frontend/src/components/practice/components/FeedbackPanel.tsx`：信息增益展示。
- `frontend/src/hooks/planning/usePlanning.ts`：confirmation 类型与 mutations。
- `frontend/src/components/planning/PlanItemConfirmationPool.tsx`：待确认计划项池。
- `frontend/src/app/planning/daily/page.tsx`：渲染 confirmation pool。
- `frontend/src/app/secretary/page.tsx` + `ProposalCard.tsx` + `shared.ts` + `types.ts`：统一展示与操作。

## 验证

- `test_phase6_feedback_api.py`：5 passed。
- `test_phase5_planning_proactive_generation.py` + `test_planning_e2e_full.py` + `test_phase4_secretary_context_plan.py`：117 passed, 3 skipped。
- `rebuild.sh --skip-build --skip-admin`：全部服务正常启动。

## 相关文档

- `docs/temp/task0028-frontend-proposal-feedback-design.md`
- `docs/adr/0020-planning-proactive-generation.md`
- `docs/adr/0019-secretary-orchestrator-phase4.md`
