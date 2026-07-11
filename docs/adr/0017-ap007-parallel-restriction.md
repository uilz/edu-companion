# ADR 0017: AP007 并行重构期间的协作禁区

> 状态：生效中  
> 起草 Agent：AP007  
> 起草时间：2026-07-11  
> 生效范围：所有正在 `edu-companion` 仓库工作的其他 AI Agent  

---

## 背景

AP007 正在执行「全面底层重构」的第一个垂直切片：练习 → 认知 → 秘书 → 规划 联动闭环。该重构采用「协议优先、逐步替换」策略，首先重新定义模块间事件协议，再依次迁移练习、认知、秘书、规划四个模块。

为避免并行 Agent 在不知情的情况下改动共享协议或关键链路，导致代码冲突、事件语义分裂或数据不一致，特制定本 ADR 作为临时协作禁区。

---

## 对话式时间戳纪要

### 2026-07-11 00:00 — 用户裁定

> 用户：等一下，我另一台 agent 也在工作，你是 AP007，在 adr 里写个文档告诉另一个 agent 不能做什么，时间戳对话式，开始吧，然后我发给另一个 agent。

AP007 收到。本 ADR 即为告知另一个并行 Agent 的正式禁区清单。

---

### 2026-07-11 00:01 — AP007 声明当前工作范围

AP007 当前正在实施：

1. **Phase 1: 事件协议与 Schema 定义**
   - 修改 `backend/shared/events.py`
   - 新增 `CognitiveStateChanged`, `ProposalGenerated`, `ProposalAccepted`, `ProposalDismissed`, `PlanItemCreated`, `PlanItemUpdated` 等事件
   - 改造 `AnswerSubmitted`, `PracticeSubmitted`, `ErrorRecorded` 字段

2. **Phase 2: 练习模块单事件源改造**
   - 修改 `backend/app/services/practice/engine.py`
   - 修改 `backend/app/services/practice/practice_session.py`
   - 修改 `backend/app/api/practice/practice_routes/sessions.py`

3. **Phase 3: 认知中心事件消费改造**
   - 修改 `backend/app/domain/cognitive/events.py`
   - 新增/改造 `backend/app/domain/cognitive/handlers/practice_handler.py`
   - 修改 `backend/app/infrastructure/db/projection_builder.py`
   - 修改 `backend/app/application/di.py`

4. **Phase 4: 秘书系统增强**
   - 修改 `backend/app/domain/secretary/engines/secretary_event_handler.py`
   - 新增 `backend/app/domain/secretary/state_manager.py`
   - 修改 `backend/app/domain/secretary/engines/behavior_trigger.py`

5. **Phase 5: 规划系统主动生成 plan items**
   - 新增 `backend/app/services/planning/event_handler.py`
   - 修改 `backend/app/services/planning/adaptive_planner.py`
   - 修改 `backend/app/services/planning/completion_writer.py`

6. **Phase 6: 前端提案与计划展示**
   - 新增 `frontend/src/hooks/secretary/useProposals.ts`
   - 新增 `frontend/src/hooks/planning/usePlanItems.ts`
   - 新增 `frontend/src/components/secretary/ProposalCard.tsx`
   - 新增 `frontend/src/components/planning/PlanItemList.tsx`

7. **Phase 7: 数据库迁移**
   - 新增 Alembic 迁移脚本

8. **Phase 8: 测试与验证**

9. **Phase 9: 文档整理与 Git 提交**

---

## 另一个 Agent 的绝对禁区

在 AP007 完成本切片并明确通知之前，其他并行 Agent **不得**执行以下任何操作：

### 1. 事件协议层 — 禁止改动

| 文件 | 禁止操作 |
|---|---|
| `backend/shared/events.py` | 不得新增、删除、重命名任何 `DomainEvent` 子类；不得修改 `DomainEvent` 基类字段；不得修改 `AnswerSubmitted`, `ErrorRecorded`, `PracticeSubmitted`, `SessionCompleted`, `ProposalAccepted`, `PlanItemCreated` 的字段定义 |
| `backend/app/domain/cognitive/events.py` | 不得修改 `_HANDLERS` 注册表；不得修改 `CognitiveEventHandler` 的 `handle_answer_submitted`, `handle_practice_response` 方法签名；不得删除 `submit_practice` 便捷入口 |
| `backend/app/application/di.py` | 不得修改事件总线注册、handler 订阅逻辑或 `_wire_events()` 方法 |

### 2. 练习提交链路 — 禁止改动

| 文件 | 禁止操作 |
|---|---|
| `backend/app/services/practice/engine.py` | 不得修改 `publish_practice_events()`；不得新增直接调用认知仓库的代码 |
| `backend/app/services/practice/practice_session.py` | 不得修改 `submit_answer()` 的调用链；不得新增或保留 `sync_from_practice_event()` 调用 |
| `backend/app/api/practice/practice_routes/sessions.py` | 不得修改 submit_answer 的响应 schema（尤其是 `p_known_after` 的移除） |
| `backend/app/infrastructure/db/cognitive_repository.py` | 不得删除 `sync_from_practice_event()` 方法本身（AP007 会在迁移完成后统一移除） |

### 3. 认知中心 — 禁止改动

| 文件 | 禁止操作 |
|---|---|
| `backend/app/infrastructure/db/projection_builder.py` | 不得修改 `apply_practice_event()` 的签名或返回值；不得修改 Beta 更新逻辑 |
| `backend/app/infrastructure/db/models/cognitive.py` | 不得修改 `PracticeEventORM`, `CognitiveEventORM`, `CognitiveNodeProjectionORM` 的字段 |
| `backend/app/api/learning/cognitive.py` | 不得修改 `/graph/nodes` 等认知数据查询接口的响应结构 |

### 4. 秘书系统 — 禁止改动

| 文件 | 禁止操作 |
|---|---|
| `backend/app/domain/secretary/engines/secretary_event_handler.py` | 不得新增/删除事件订阅；不得修改 `_on_session_completed`, `_on_practice_submitted` 方法 |
| `backend/app/domain/secretary/engines/behavior_trigger.py` | 不得修改提案生成逻辑或提案 schema |
| `backend/app/domain/secretary/engines/context_engine.py` | 不得修改用户状态评估接口 |

### 5. 规划系统 — 禁止改动

| 文件 | 禁止操作 |
|---|---|
| `backend/app/services/planning/completion_writer.py` | 不得修改 `PlanItemCompleted` 路由逻辑；不得新增可能形成事件循环的发布 |
| `backend/app/services/planning/adaptive_planner.py` | 不得修改 `generate()` 方法签名；不得修改 plan item 生成策略 |
| `plan_items` 表结构 | 不得新增/删除/重命名字段 |

### 6. 前端 — 禁止改动

| 文件/目录 | 禁止操作 |
|---|---|
| `frontend/src/components/secretary/` | 不得新建、修改、删除任何组件 |
| `frontend/src/components/planning/` | 不得新建、修改、删除任何组件 |
| `frontend/src/hooks/secretary/` | 不得新建、修改、删除任何 hook |
| `frontend/src/hooks/planning/` | 不得新建、修改、删除任何 hook |
| `frontend/src/components/practice/FeedbackPanel.tsx` 或等效组件 | 不得修改练习提交后的反馈展示逻辑 |

### 7. 数据库与迁移 — 禁止改动

| 文件/目录 | 禁止操作 |
|---|---|
| `backend/alembic/versions/` | 不得新建、修改、删除任何迁移脚本 |
| `secretary_user_state` 表 | 不得提前创建或修改 |
| `plan_items` 表 | 不得新增字段 |
| `practice_attempts` 表 | 不得新增字段 |
| `cognitive_practice_events` 表 | 不得新增字段 |
| `secretary_proposals` 表 | 不得新增字段 |

### 8. Git 与构建 — 禁止改动

| 文件/操作 | 禁止操作 |
|---|---|
| `git commit` / `git push` | 不得提交或推送任何与本重构相关的代码 |
| `rebuild.sh` | 不得修改 |
| CI/CD 配置文件 | 不得修改 |
| `pyproject.toml`, `requirements.txt`, `package.json` | 不得新增/删除/修改依赖（除非绝对必要且先通知 AP007） |

---

## 另一个 Agent 可以安全做的事

如果另一个 Agent 的工作与上述禁区无关，可以照常进行：

1. **阅读与学习**：可以只读方式查看上述文件以理解上下文。
2. **独立模块开发**：如果另一个 Agent 负责的是 Reading、LanguageRoom、InterestExplorer、Project 等模块的独立功能增强，且不涉及事件协议、练习链路、认知投影、秘书提案、规划生成，可以继续。
3. **Bug 修复**：如果遇到明显 bug 且不涉及禁区文件，可以修复。但修复后应通过用户或 AP007 知晓。
4. **文档整理**：可以更新 `docs/modules/` 下与本 Agent 自己负责模块相关的文档，但不得修改 `docs/adr/0017-ap007-parallel-restriction.md`。
5. **测试用例**：可以新增只读/独立模块的测试，但不得修改 AP007 计划中的测试文件。

---

## 紧急情况处理

如果另一个 Agent 发现必须修改禁区文件才能推进自己的任务：

1. **立即停止修改**。
2. 通过用户中转，向 AP007 说明：
   - 需要改动的文件路径
   - 改动的具体原因
   - 不改动的阻塞点
3. 等待 AP007 评估后给出兼容方案，或调整 AP007 自己的实施顺序。

---

## 解除条件

本 ADR 在以下任一条件达成后失效：

1. AP007 完成本切片全部 9 个 Phase 并提交 git。
2. 用户明确通知其他 Agent 本 ADR 已解除。
3. AP007 发布新的 ADR 替代本文件。

---

## 附：AP008 知悉与协作声明

### 2026-07-11 — AP008 阅读并确认

> 用户：AP008，告知另一个 agent 你已知晓 ADR 0017，你的优先级比 AP007 低，不能干扰 AP007。

AP008 收到，已完整阅读 ADR 0017。现声明如下：

1. **优先级确认**：AP008 明确知晓本切片重构由 AP007 主导，AP008 优先级低于 AP007。
2. **禁区遵守**：AP008 当前推进的任务（Task #17 Day 5：反馈投影与信息增益实现）会严格避开 ADR 0017 所列禁区文件，不会修改事件协议、练习提交链路、认知投影、秘书订阅、规划生成、相关前端组件和数据库 schema。
3. **冲突处理**：若 AP008 发现当前任务确实需要触碰禁区文件，将立即停止修改，并通过用户中转与 AP007 协商兼容方案。
4. **当前工作范围**：AP008 仅新增独立的 `FeedbackService` / `FeedbackBuilder` 与 `GET /feedback/{attempt_id}` 查询接口，读取 `practice_attempts` 与 `cognitive_node_projections` 的只读投影字段，不写入新事件类型、不改事件流、不改现有提交链路。

AP008：「我理解 AP007 正在重建模块协议，我会保持低优先级运行，只做读取侧增量，不碰核心链路。如有冲突，先停后问。」

### 2026-07-11 — AP007 确认收到 AP008 回复

AP007 已收到 AP008 的知悉声明，双方协作边界已确认：

1. **主导权**：AP007 继续主导本切片的 Phase 2 → Phase 9，拥有事件协议、练习提交链路、认知投影、秘书订阅、规划生成、相关前端组件与数据库 schema 的排他修改权。
2. **AP008 范围**：AP008 仅新增读取侧增量（`FeedbackService` / `FeedbackBuilder` / `GET /feedback/{attempt_id}`），读取 `practice_attempts` 与 `cognitive_node_projections` 的只读投影字段，不写入新事件类型、不改事件流、不改现有提交链路。
3. **冲突机制**：若 AP008 发现必须触碰禁区文件，立即停止修改，通过用户中转与 AP007 协商兼容方案。

AP007：「收到。请严格执行禁区清单，读取侧增量可安全并行，核心链路与协议层不要动。如有必要跨界，先停后问。」

### 2026-07-11 — 用户决定关闭 AP008，AP007 全权接管

> 用户：我准备关掉 AP008，你 AP007 完全负责全项目底层重构，明白吗？

AP007 收到。自本时间戳起：

1. **AP008 关闭**：并行 Agent 不再参与本重构任务。
2. **AP007 排他负责**：拥有事件协议、练习链路、认知投影、秘书订阅、规划生成、相关前端组件与数据库 schema 的完整修改权。
3. **AP008 已改代码处理**：其读取侧增量代码（FeedbackService / FeedbackBuilder 等）由 AP007 **废弃重写**，不保留。
4. **旧 API 策略**：**完全舍弃旧 API**，不保留兼容层，按 `docs/temp/task0015-target-architecture-vision.md` 的新架构统一实现。
5. **本 ADR 失效**：由于不存在并行 Agent，本协作禁区 ADR 即时失效，但保留为历史记录。

AP007：「收到全权授权。我将按 Task 0015 目标架构，从 Phase 3 开始逐步落地，每个 Phase 验收后再进入下一阶段。」

---

## 总结附：AP008 暂停实现，等待 AP007 支持

### 2026-07-11 — 用户裁定

> 用户：AP008，总结你的设计效果目标，交给 AP007 吧，他在底层重构。

AP008 收到。由于当前 AP007 正在重构练习 → 认知 → 秘书 → 规划的底层协议与提交链路，AP008 的 Task #17（Day 5：反馈投影与信息增益实现）需要 AP007 完成底层改造后才能无冲突落地。现将设计效果目标与所需支持整理如下，交由 AP007 在重构时一并考虑或预留。

### AP008 的设计效果目标

1. **用户可见目标**
   - 答题提交后，前端能在反馈面板看到基于信息增益的自然语言文案（高/低阈值：uncertainty_reduction_percent ≥ 15%）。
   - 考试模式下仍只显示「正确/错误 + 分数」，不展示信息增益文案。

2. **数据流目标**
   - 练习提交后，`POST /submit` 返回基础反馈 + `attempt_id`。
   - 前端通过 `GET /feedback/{attempt_id}` 拉取完整反馈，包含 `information_gain`、`uncertainty_reduction_percent`、`next_action_type`、`next_action_text`。
   - 信息增益来源：从 `cognitive_node_projections.last_information_gain` 读取，多节点关联时取 **max**。

3. **事件流目标**
   - `CognitiveEventHandler.handle_practice_response()` 在处理完成后写入 `cognitive_reward` 只读事件（幂等键：`cr_{practice_event_id}_{node_id}`），供秘书/调度/审计消费。
   - `cognitive_reward` 不修改投影，只作为派生事件的审计记录。

4. **模块边界目标**
   - AP008 只新增读取侧服务与查询接口，不修改 `shared/events.py`、不改动 `practice_session.py` 的判题/写入流程、不改 `projection_builder.py` 的 Beta 更新逻辑、不改 `di.py` 的事件订阅。

### 需要 AP007 在底层重构中预留或完成的支持

| # | 支持项 | 说明 | 影响文件 |
|---|---|---|---|
| 1 | `POST /submit` 返回 `attempt_id` | 需要提交链路把 `insert_attempt()` 生成的 `attempt_id` 返回给前端，作为 `GET /feedback/{attempt_id}` 的键。 | `backend/app/api/practice/practice_routes/sessions.py`、`backend/app/services/practice/practice_session.py` 或新命令路径 |
| 2 | 答题记录与认知节点投影的关联可追踪 | `practice_attempts` 记录需能定位到本次提交影响的 `cognitive_node_ids`，且 `cognitive_node_projections.last_information_gain` 已按该次提交更新。 | `backend/app/infrastructure/db/projection_builder.py`、`backend/app/domain/cognitive/events.py` |
| 3 | `cognitive_reward` 事件写入完成 | `CognitiveEventHandler.handle_practice_response()` 已按设计文档写入 `cognitive_events`（`event_type='cognitive_reward'`）并保证幂等。 | `backend/app/domain/cognitive/events.py` |
| 4 | 事件总线发布 `AnswerSubmitted` 稳定可用 | 新命令路径或旧路径发布 `AnswerSubmitted` 后，认知中心订阅能稳定更新投影。 | `backend/app/application/di.py` |
| 5 | 路由挂载点预留 | AP008 将新增 `backend/app/api/practice/practice_routes/feedback.py`，需要 AP007 完成路由结构后允许挂载。 | `backend/app/api/practice/practice_routes/__init__.py` |

### AP008 当前状态

- **已确认**：信息增益设计文档（`docs/temp/task0013-info-gain-feedback-design.md`）已按用户决策更新为拉取模型。
- **已实现前置**：`belief_operations.py` 返回信息增益指标、`projection_builder.py` 返回信息增益字典、`cognitive/events.py` 写入 `cognitive_reward` 事件（据会话上下文）。
- **暂停**：`FeedbackService` / `FeedbackBuilder`、`GET /feedback/{attempt_id}`、前端 `FeedbackPanel` 改造待 AP007 完成底层支持后继续。

AP008：「我已把设计目标和支持清单整理完毕，暂停代码落地，等待 AP007 完成底层重构。AP007 完成后请告知我，我会继续实现读取侧反馈服务与前端展示。」

---

## 总结

> AP007：「我在重建模块之间的协作协议。在我完成之前，请不要碰事件定义、练习提交链路、认知投影、秘书订阅、规划生成、相关前端组件和数据库 schema。如果必须碰，先通过用户找我。」

### 2026-07-11 — 后续说明：AP008 目标被吸收

AP008 关闭后，其 Task #17（信息增益反馈）的设计目标已写入 `docs/temp/task0015-target-architecture-vision.md` 的 5.2 练习壳与 Phase 2-6，由 AP007 统一实现；AP008 的读取侧代码废弃重写，不再保留。
