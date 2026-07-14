# ADR 0019: 秘书编排器 Phase 4 增强架构

## 状态

已接受 (Accepted)

## 背景

在底层重构中，秘书系统被定位为认知 OS 的"学习编排大脑"，负责在正确时机向正确壳层推送学习建议、计划与上下文。Phase 4 聚焦完成以下缺口：

1. **对话上下文注入**：秘书需要把学习状态、待办计划、pending proposals 注入对话壳，影响 AI 回复。
2. **计划项主动请求**：秘书在感知到学习机会时，可直接向规划壳请求创建 plan item。
3. **后台预计算**：通过 SilentTask 子系统异步执行复习列表生成、诊断计算、测验预生成等任务。
4. **用户编排画像**：持久化用户信任度、疲劳度、关系记忆等，用于提案优先级与响应风格。
5. **提案状态机**：补充 `presented` 状态，追踪提案是否已被展示给用户。

## 决策

### 1. 对话上下文注入采用"事件 + 内存缓存"模式

- 秘书服务 `get_conversation_context()` 组装上下文包并发布 `ConversationContextInjected` 事件。
- 对话壳通过 `ConversationContextHook` 订阅该事件，将 payload 缓存到进程内存（TTL 5 分钟）。
- `ContextPipeline` 新增 `SecretaryContext` Provider，在 LLM system prompt 中渲染缓存的上下文。
- 对话路由在启动 pipeline 前显式调用秘书服务触发注入。

**理由**：
- 避免对话壳直接依赖秘书服务的同步调用，保持事件驱动边界。
- 内存缓存足够满足单请求内的多次读取，且重启后自动失效，不引入额外持久化复杂度。

### 2. 计划项请求采用"幂等事件 + 元数据去重"

- 秘书通过 `PlanItemRequested` 事件请求规划壳创建计划项，字段包含 `request_id`（幂等键）、`requires_user_confirmation`、`estimated_minutes` 等。
- 规划壳 `PlanningEventHandler` 消费事件：
  - `requires_user_confirmation=False` → 直接创建 plan item。
  - `requires_user_confirmation=True` → 当前阶段不自动创建（可后续扩展为 pending confirmation 表）。
- `plan_items` 表新增 `metadata JSONB` 字段保存 `request_id`，并通过索引实现幂等去重。

**理由**：
- 事件契约清晰区分"自动执行"与"需用户确认"两种模式。
- `request_id` 元数据去重避免秘书重试或事件重放导致重复计划项。

### 3. SilentTask 后台任务子系统

- 定义 `SilentTask` 模型与状态机：`pending → running → ready | failed → consumed`。
- `SilentTaskManager` 负责任务调度、执行与状态流转，事件包括 `SilentTaskCreated`、`SilentTaskCompleted`、`SilentTaskFailed`。
- 任务类型包括 `prepare_review_list`、`pre_generate_quiz`、`compute_diagnosis`、`generate_daily_brief`、`expand_knowledge_graph`。

**理由**：
- 将耗时预计算从请求路径剥离，避免阻塞用户交互。
- 状态机支持幂等消费与失败追踪，便于监控与重试。

### 4. UserOrchestrationProfile 持久化

- 新建 `secretary_user_profiles` 表持久化 `trust_score`、`fatigue_score`、`proactive_quota_today`、`enabled_modules`、`quiet_hours`、`relation_memory` 等。
- 提供 `/secretary/profile` API 读写画像，并在提案交互（accept/dismiss）中更新关系记忆。

**理由**：
- 秘书需要长期记忆用户偏好与交互历史，避免每次重启后策略冷启动。
- 关系记忆支持策略引擎基于用户反馈调整提案排序与频率。

## 影响

- **新增模块/文件**：
  - `backend/app/domain/conversation/context_hooks.py`
  - `backend/app/api/planning/event_handler.py`
  - `backend/app/domain/secretary/engines/silent_task_manager.py`
  - `backend/app/infrastructure/db/silent_task_store.py`
  - `backend/app/infrastructure/db/user_profile_store.py`
  - `backend/tests/test_phase4_secretary_context_plan.py`

- **修改模块/文件**：
  - `backend/app/domain/secretary/secretary_service.py`
  - `backend/app/domain/secretary/engines/secretary_event_handler.py`
  - `backend/app/domain/conversation/context_pipeline.py`
  - `backend/app/api/conversation/conversation_routes.py`
  - `backend/app/api/planning/service.py`
  - `backend/app/infrastructure/db/planning_schema.sql`
  - `backend/app/infrastructure/db/proposal_store.py`
  - `backend/app/infrastructure/db/secretary_schema.sql`
  - `backend/app/api/system/secretary.py`
  - `backend/app/main.py`
  - `backend/shared/events.py`

- **事件协议更新**：
  - `PlanItemRequested` 新增 `estimated_minutes` 字段。
  - `ConversationContextInjected` 用于对话壳上下文注入。
  - `SilentTaskCreated` / `SilentTaskCompleted` / `SilentTaskFailed` 用于后台任务。

## 替代方案

- **方案 A（直接服务调用）**：对话壳直接调用秘书服务获取上下文。 rejected，因为会引入循环依赖并破坏事件驱动边界。
- **方案 B（持久化上下文）**：将注入上下文写入 Redis/DB 供对话壳读取。 rejected，因为当前阶段不需要跨请求持久化，内存缓存更简单。

## 相关文档

- `docs/temp/task0019-secretary-orchestrator-design.md`
- `docs/adr/0009-secretary-module.md`
- `docs/adr/0018-conversation-flashcard-integration.md`
