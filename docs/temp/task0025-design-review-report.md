# Task 0025: 全模块设计统一评审报告 v1.1

> 版本：v1.1
> 评审 Agent：AP007
> 评审时间：2026-07-11
> 更新时间：2026-07-11
> 评审范围：Task 0015（目标架构愿景）、Task 0016（认知 OS 内核）、Task 0014（事件协议）、Task 0018-0024（六大场景壳深度设计）
> 状态：Phase 1.1 事件协议收口已完成

---

## 1. 评审结论（摘要）

各场景壳设计的**深度、边界清晰度、与目标架构愿景的一致性**整体良好，核心决策（用户结构 vs 认知数据分离、事件驱动、SSOT、CQRS）在各文档中基本统一。

**Phase 1.1 事件协议收口已完成**：

1. ✅ 补充了知识树、对话、规划、阅读、认知奖励等 20+ 缺失事件到 `shared/events.py`。
2. ✅ 对齐了 `AnswerSubmitted` 字段：`answer` / `correct_answer` 改为 `list[str]`，统一耗时字段为 `response_time_seconds: float`，新增 `attempt_id`。
3. ✅ 规划壳与秘书系统协作新增 `PlanItemRequested` / `PlanGoalRequested`（支持「提案 + 直接请求并存」）。
4. ✅ `CognitiveStateChanged` 已增加 `information_gain` / `uncertainty_reduction_percent`。
5. ✅ 所有事件已注册到 `EVENT_TYPES`（共 118 个），契约测试 36 项全部通过。

**仍遗留、需在后续阶段处理的问题**：

1. **SourceRef / source_ref 结构统一**（值对象层，不阻塞事件协议）。
2. **考试完成事件**：用户决策复用 `SessionCompleted(session_type="exam")`，无需独立 `ExamSubmitted`。
3. **SourceRef 值对象未在 `shared/events.py` 中定义**：需要单独 ADR / schema 文档。

**总体判断**：事件协议层已收口，可以进入 Phase 2 编码（练习模块单事件源改造）。

---

## 2. 事件协议一致性审查

### 2.1 已注册但设计稿中语义不一致的事件

| 事件 | 注册表语义 | 设计稿语义 | 冲突说明 | 建议 |
|------|-----------|-----------|----------|------|
| `CognitiveNodeLinked` | 节点与其他实体链接变化（创建/删除/更新），通用元事件 | 闪卡壳：Belief 回写触发事件，带 `belief_delta` | 同一个名字承载了两个不同层级的语义：通用元数据链接 vs 信念更新信号 | **拆分**：保留 `CognitiveNodeLinked` 为通用链接事件；新增 `CognitiveBeliefUpdated` 或让 `CognitiveStateChanged` 承担 belief 变化通知 |
| `FlashCardImportedToModule` | 闪卡导入到其他模块 | 未在各设计稿中明确使用 | 可能为旧事件，需确认是否仍需要 | 若知识树壳的 `TreeImportedContent` 可替代，则废弃；否则明确使用场景 |

### 2.2 设计稿中定义但未注册的事件（已补充）

| 事件 | 来源设计稿 | 当前注册状态 | 优先级 | 备注 |
|------|-----------|-------------|--------|------|
| `TreeNodeCreated` | 知识树壳 | ✅ 已注册 | P0 | 核心用户结构事件 |
| `TreeNodeUpdated` | 知识树壳 | ✅ 已注册 | P0 | |
| `TreeNodeDeleted` | 知识树壳 | ✅ 已注册 | P0 | |
| `TreeNodeMoved` | 知识树壳 | ✅ 已注册 | P0 | |
| `TreeEdgeCreated` | 知识树壳 | ✅ 已注册 | P0 | |
| `TreeEdgeDeleted` | 知识树壳 | ✅ 已注册 | P0 | |
| `TreeNodeLinkedToCognitiveNode` | 知识树壳 | ✅ 已注册 | P0 | 采用双向事件：树壳发本事件，认知中心再发 `CognitiveNodeLinked` |
| `TreeNodeUnlinkedFromCognitiveNode` | 知识树壳 | ✅ 已注册 | P1 | |
| `TreeImportedContent` | 知识树壳 | ✅ 已注册 | P0 | 跨壳导入关键事件 |
| `TreeViewChanged` | 知识树壳 | ✅ 已注册 | P2 | 纯前端/分析事件 |
| `NoteCreatedAsFlashcard` | 对话壳 | ✅ 已注册 | P0 | 对话 → 闪卡关键事件 |
| `InConversationTaskCreated` | 对话壳 | ✅ 已注册 | P0 | 对话内子任务关键事件 |
| `ConversationBranchCreated` | 对话壳 | ✅ 已注册 | P1 | |
| `ConversationArchived` | 对话壳 | ✅ 已注册 | P1 | |
| `UserMessageSent` | 目标架构愿景 | ✅ 已注册 | P1 | 对话壳用户消息事件 |
| `AnswerBehaviorRecorded` | 练习壳 | ✅ 已注册 | P0 | 行为遥测事件，仅携带 telemetry_id + 派生指标 |
| `ExamSubmitted` | 练习壳 / 规划壳 | ⏭️ 已决策不独立注册 | P1 | 用户决策：复用 `SessionCompleted(session_type="exam")` |
| `PlanItemRequested` | 规划壳 | ✅ 已注册 | P0 | 秘书 → 规划创建请求，支持 `requires_user_confirmation` |
| `PlanGoalRequested` | 规划壳 | ✅ 已注册 | P1 | |
| `CognitiveReward` | 目标架构愿景 / 认知内核 | ✅ 已注册 | P0 | 只读审计事件 |
| `ReadingMaterialCompleted` | 规划壳订阅 | ✅ 已注册 | P1 | 阅读完成事件 |
| `MaterialProgressUpdated` | 阅读壳 | ✅ 已注册 | P1 | 阅读进度更新，与 `ReadingReviewReminderScheduled` 不重叠 |

### 2.3 已注册但设计稿未使用/未说明的事件

| 事件 | 注册状态 | 问题 | 建议 |
|------|---------|------|------|
| `ReadingReviewReminderScheduled` | ✅ 已注册 | 阅读壳设计稿中未提及，但阅读壳 routes.py 已使用 | 确认是否保留；若保留应在阅读壳设计稿 §4 中补充 |
| `FlashCardImportedToModule` | ✅ 已注册 | 闪卡壳设计稿未说明使用场景 | 补充或废弃 |
| `FlashCardStatusChanged` | ✅ 已注册 | 设计稿 §4 提到发布，但未在关键事件定义中给出 schema | 补充 schema |
| `PendingCrossTopic` | ✅ 已注册 | 对话壳设计稿未使用 | 是旧事件，需确认是否继续保留在对话流程中 |

### 2.4 命名规范问题

1. **动词时态不一致**：
   - `AnswerSubmitted`（过去分词） vs `TreeNodeCreated`（过去分词） ✅ 一致
   - 但 `ReadingAnnotationProcessed` 与 `TreeImportedContent` 一个是被动，一个是主动，建议统一为过去分词：`TreeContentImported`。

2. **模块前缀缺失**：
   - `AnswerBehaviorRecorded` 建议改为 `PracticeAnswerBehaviorRecorded`，避免与将来其他行为遥测混淆。
   - `NoteCreatedAsFlashcard` 建议改为 `ConversationNoteCreatedAsFlashcard`，明确来源。

3. **复数形式不一致**：
   - `cognitive_node_ids` 在多个事件中使用复数，但 `CognitiveStateChanged` 中只处理单个 `node_id`。是否一个事件只通知一个节点变化？需在认知中心实现中明确。

---

## 3. 领域模型与 Schema 审查

### 3.1 CognitiveStateChanged 字段偏差 ✅ 已对齐

| 字段 | 目标架构愿景 | 实际代码 `shared/events.py` | 知识树壳设计 CognitiveNodeView | 偏差 |
|------|-------------|---------------------------|------------------------------|------|
| `stagnation_days` | int | float | int | ✅ 统一为 float（允许部分天数） |
| `uncertainty` | 有 | 有 | 有 | ✅ 一致 |
| `next_review_at` | datetime | datetime | datetime | ✅ 一致 |
| `next_action_type` | enum string | str | str | ✅ 一致 |
| `information_gain` | 目标架构 §5.2 提及 | ✅ 已增加 | - | ✅ 已对齐 |
| `uncertainty_reduction_percent` | - | ✅ 已增加 | - | ✅ 已对齐 |
| `proficiency_before/after` | 有 | 有 | - | ✅ 一致 |

**结论**：
- `stagnation_days` 保持 `float`。
- `CognitiveStateChanged` 已增加 `information_gain: float` 和 `uncertainty_reduction_percent: float`。
- 一个 `CognitiveStateChanged` 事件对应**一个 node_id**；一次答题更新多个节点时发布多个事件。

### 3.2 AnswerSubmitted 字段偏差 ✅ 已对齐

| 字段 | 修改后代码 | 练习壳设计 AttemptRecord | 状态 |
|------|-----------|------------------------|------|
| 用户答案 | `answer: list[str]` | `user_answer: list[str]` | ✅ 已对齐 |
| 正确答案 | `correct_answer: list[str]` | - | ✅ 新增对齐 |
| 耗时 | `response_time_seconds: float` | `response_time_ms: int` | ✅ 已统一为秒（用户决策） |
| 尝试 ID | `attempt_id: str` | `attempt_id: str` | ✅ 新增 |
| 关联节点 | `cognitive_node_ids: list[str]` | - | ✅ 一致 |
| 行为遥测 | `AnswerBehaviorRecorded` 单独事件 | `AnswerBehaviorTelemetry` 单独事件 | ✅ 遥测只传 telemetry_id + 派生指标 |

**结论**：
- `answer` / `correct_answer` 已改为 `list[str]`，单选统一用单元素列表。
- 删除 `time_spent` 和 `response_time_ms`，统一为 `response_time_seconds: float`。
- 新增 `attempt_id`，`source_id` 指向 `attempt_id`。
- `AnswerSubmitted` 不内嵌完整遥测；遥测通过 `AnswerBehaviorRecorded` 事件单独上报，携带 `telemetry_id` 和派生指标。

### 3.3 SourceRef / source_ref 结构不统一

| 来源 | 字段 | 问题 |
|------|------|------|
| 闪卡壳设计 | `module`, `id`, `sub_id`, `offset`, `length`, `url`, `title` | 标准定义 |
| 阅读壳 notes.py 现有代码 | `module`, `id`, `sub_id`, `chunk_id_range`, `title` | 多了 `chunk_id_range`，少了 `offset`/`length` |
| 对话壳设计 | 通过 `source_message_id` 直接放在 `NoteCreatedAsFlashcard` 事件中 | 未使用 SourceRef 值对象 |

**建议**：
- 统一 `SourceRef` schema，所有跨壳引用必须使用同一结构。
- 允许 `metadata: dict` 扩展字段（如 `chunk_id_range`、`message_id`），但核心字段统一。

### 3.4 计划项与秘书提案的协作 ✅ 已补齐

用户决策：**两种模式并存**。

已在 `shared/events.py` 中新增：
- `PlanItemRequested`：秘书请求规划壳创建计划项，带 `requires_user_confirmation` 标志。
- `PlanGoalRequested`：秘书请求规划壳创建目标。

| 模式 | 流程 | 用户决策 |
|------|------|---------|
| A | 秘书发布 `ProposalGenerated` → 前端接受 → `ProposalAccepted` → 规划壳创建 plan item | 保留 |
| B | 秘书直接发布 `PlanItemRequested` → 规划壳创建 plan item（可配置是否需用户确认） | 新增支持 |

### 3.5 知识树节点与认知节点关联关系 ✅ 已决策

**决策**：采用**双向事件**。

- 知识树壳发布 `TreeNodeLinkedToCognitiveNode` 作为域事件。
- 认知中心订阅后，更新 `cognitive_node.metadata.anchors`，并再发布 `CognitiveNodeLinked(target_ref_type="tree_node", target_ref_id=tree_node_id)` 供秘书、分析、前端订阅。

---

## 4. 模块边界与职责审查

### 4.1 边界清晰的点 ✅

| 模块 | 清晰边界 |
|------|---------|
| 练习壳 | 只负责出题、收答案、发布 `AnswerSubmitted`，不直接更新认知投影 |
| 闪卡壳 | 复习自评后发布 `FlashCardReviewed`，不直接写 belief |
| 阅读壳 | 笔记复用 FlashCard，标注独立表，不建独立 reminder 表 |
| 知识树壳 | 用户结构与认知数据分离，只读投影 |
| 秘书编排器 | 只读事件流，生成提案/计划请求/对话上下文 |

### 4.2 边界模糊的点 ⚠️

1. **对话壳 vs 秘书编排器**：
   - 对话壳设计中的「多 Agent 协作」让 Orchestrator 同时承担了秘书编排器的一部分职责（调度 secretary/tutor）。
   - 秘书编排器设计中也提到「为对话壳提供当前学习状态、推荐话题」。
   - **风险**：两个 Orchestrator 概念（对话壳内 vs 秘书编排器）可能冲突。

   **建议**：明确对话壳内的 Orchestrator 是**会话级消息路由**，只决定「这条消息由哪个 agent 回复」；秘书编排器是**跨模块学习编排**，决定「现在该做什么学习行动」。前者属于对话壳，后者属于内核。

2. **规划壳完成计划与自动完成**：
   - 规划壳订阅 `SessionCompleted` / `FlashCardReviewed` / `ReadingMaterialCompleted` 自动完成 plan item。
   - 但这意味着规划壳需要理解其他壳的事件语义，可能跨界。
   - **建议**：自动完成逻辑由规划壳的「事件匹配器」处理，规则是「plan item 的 target_ref_id 与事件 source_id 匹配」，不解释业务语义。

3. **知识树壳的材料聚合**：
   - 知识树壳需要从各壳查询材料聚合到节点详情面板。
   - 如果直接调用各壳服务，会引入依赖；如果通过投影查询，需要内核提供统一材料视图。
   - **建议**：短期由知识树壳调用各壳只读查询接口；中期由内核提供 `node_material_bundle` 投影。

---

## 5. API 与接口审查

### 5.1 路由前缀不一致

| 模块 | 设计稿前缀 | 现有实现前缀 | 状态 |
|------|-----------|-------------|------|
| 阅读壳 | `/api/reading` | `/api/reading` | ✅ 一致 |
| 练习壳 | 未明确 | 旧实现可能是 `/api/practice` | 需确认 |
| 闪卡壳 | 未明确 | 旧实现可能是 `/api/flashcards` | 需确认 |
| 知识树壳 | 未明确 | 新模块 | 需定义 |

**建议**：统一路由规范：`/api/{shell-name}/{resource}`。

### 5.2 反馈接口

目标架构愿景要求 `GET /feedback/{attempt_id}`，练习壳设计也提到「完整反馈异步拉取」。

**问题**：
- 该接口放在练习壳还是认知中心？
- 反馈内容包括信息增益、元认知建议、相关节点状态，这些数据来自认知投影。

**建议**：
- `GET /feedback/{attempt_id}` 由练习壳路由暴露，但数据组装来自认知中心/投影服务。
- 反馈是**只读投影**，不是练习壳私有状态。

### 5.3 认知节点查询接口

知识树壳设计需要 `/cognitive-nodes` 和 `/cognitive-nodes/{node_id}/projection`。

**问题**：这些接口属于哪个模块？

**建议**：
- 由认知 OS 内核暴露 `/api/cognitive/nodes` 和 `/api/cognitive/nodes/{node_id}/projection`。
- 各场景壳只读该接口，不直接查 `cognitive_node_projections` 表。

---

## 6. 实现依赖与风险

### 6.1 高风险

| 风险 | 说明 | 缓解 |
|------|------|------|
| 事件协议未收口即编码 | 各模块按不同事件名实现，后期无法连通 | Phase 1 必须先补全 `shared/events.py` 和 `EVENT_TYPES` |
| `CognitiveNodeLinked` 语义冲突 | 通用元事件与 belief 触发事件混用 | 立即拆分或重命名 |
| SourceRef 不统一 | 阅读/闪卡/对话各写各的，导致来源追溯不一致 | 统一 schema 并写 ADR |
| 对话壳 Orchestrator 与秘书编排器职责重叠 | 可能两个编排器互相覆盖 | 明确分层：会话路由 vs 学习编排 |

### 6.2 中风险

| 风险 | 说明 | 缓解 |
|------|------|------|
| 考试模式事件缺失 | `ExamSubmitted` 未定义 | 决定与 `SessionCompleted` 合并还是独立事件 |
| 行为遥测事件未定义 | `AnswerBehaviorRecorded` 未注册 | 补充事件并明确与 `AnswerSubmitted` 的关联 |
| 知识树事件大量缺失 | 10+ 事件未注册 | 在 Phase 1 中批量补充 |
| 规划壳直接订阅多壳事件自动完成 | 可能过度耦合 | 用 target_ref_id 匹配，不解释语义 |

### 6.3 低风险

| 风险 | 说明 | 缓解 |
|------|------|------|
| `stagnation_days` 类型 int/float | 数据库 schema 需兼容 | 统一为 float |
| 前端图引擎选型 | G6 vs react-flow | 技术选型可在实现前最终确定 |

---

## 7. 修改清单执行状态

### 7.1 事件协议层（shared/events.py）✅ 已完成

1. ✅ 新增以下事件类并注册到 `EVENT_TYPES`（注册表共 118 个事件）：
   - 知识树：`TreeNodeCreated`, `TreeNodeUpdated`, `TreeNodeDeleted`, `TreeNodeMoved`, `TreeEdgeCreated`, `TreeEdgeDeleted`, `TreeNodeLinkedToCognitiveNode`, `TreeNodeUnlinkedFromCognitiveNode`, `TreeImportedContent`, `TreeViewChanged`
   - 对话：`NoteCreatedAsFlashcard`, `InConversationTaskCreated`, `ConversationBranchCreated`, `ConversationArchived`, `UserMessageSent`
   - 练习：`AnswerBehaviorRecorded`
   - 规划：`PlanItemRequested`, `PlanGoalRequested`
   - 认知：`CognitiveReward`
   - 阅读：`MaterialProgressUpdated`, `ReadingMaterialCompleted`
   - `ExamSubmitted` 经用户决策不独立注册，复用 `SessionCompleted(session_type="exam")`。

2. ✅ 清理语义冲突：
   - 保留 `CognitiveNodeLinked` 为通用节点链接元事件。
   - Belief 更新由 `CognitiveStateChanged` 承担。

3. ✅ 统一 `CognitiveStateChanged` 字段：
   - `stagnation_days: float`
   - 增加 `information_gain: float` 和 `uncertainty_reduction_percent: float`
   - 明确单 node_id，多节点变化发布多个事件

4. ⏭️ 统一 `SourceRef` schema：
   - 遗留到 Phase 1.2 或后续单独 ADR 处理，不阻塞事件协议收口。

### 7.2 设计文档更新 ⏭️ 部分完成

1. ⏭️ 各设计稿补充「事件注册状态」小节（可在 Phase 2 推进时同步更新）。
2. ⏭️ 阅读壳设计稿补充 `ReadingReviewReminderScheduled` 事件说明。
3. ⏭️ 闪卡壳设计稿补充 `FlashCardStatusChanged` 和 `FlashCardImportedToModule` 的 schema 或使用说明。
4. ⏭️ 对话壳设计稿明确「对话壳内 Orchestrator」与「秘书编排器」的职责边界。
5. ✅ 练习壳 `AnswerSubmitted` 与 `AnswerBehaviorRecorded` 的关系已在事件定义和本报告中明确。

### 7.3 实现顺序状态

1. ✅ **Phase 1.1**：事件协议收口（`shared/events.py` + `EVENT_TYPES` + 测试）已完成。
2. ⏭️ **Phase 1.2**：统一 `SourceRef` 和投影 schema（可在 Phase 2 初期并行）。
3. ✅ **Phase 1.3**：事件序列化/反序列化 contract test 已通过（36 项）。
4. 下一步：进入 Phase 2 练习模块单事件源改造。

---

## 8. 评审未发现重大问题但值得优化的点

1. ✅ **事件体积**：已按用户决策实现——`AnswerBehaviorRecorded` 只携带 `telemetry_id` + 派生指标，完整遥测数据单独存储。
2. **知识树壳性能**：`NodeMaterialBundle` 跨 7 类材料聚合，查询复杂度高。建议由内核逐步提供 `node_material_bundle` 物化视图。
3. **秘书编排器策略学习**：设计稿提到根据用户接受/忽略历史调整策略，但具体算法（bandit / 简单计数 / LLM 反思）未细化。可在 Phase 4 实现时再深入。
4. ✅ **考试模式**：已决策复用 `SessionCompleted(session_type="exam")`，不独立注册 `ExamSubmitted`。

---

## 9. 与用户确认的问题 ✅ 已确认

| # | 问题 | 用户决策 |
|---|------|---------|
| 1 | `CognitiveNodeLinked` 语义拆分 | `CognitiveStateChanged` 完全承担 belief 变化通知，`CognitiveNodeLinked` 仅作为通用链接元事件 |
| 2 | 秘书生成计划方式 | **两种模式并存**：`ProposalGenerated` 提案 + `PlanItemRequested` 直接请求（可配置是否需用户确认） |
| 3 | 考试完成事件 | 复用 `SessionCompleted(session_type="exam")`，不独立 `ExamSubmitted` |
| 4 | `CognitiveStateChanged` 单节点 vs 多节点 | **单节点**，多节点变化发布多个事件 |
| 5 | `AnswerSubmitted` 耗时字段 | 统一为 `response_time_seconds: float` |
| 6 | `AnswerSubmitted` 用户答案字段 | `answer: list[str]`，单选也用单元素列表 |
| 7 | `AnswerBehaviorRecorded` 遥测负载 | 只传 `telemetry_id` + 派生指标，完整遥测单独存储 |
| 8 | 知识树节点关联认知节点 | **双向事件**：树壳发 `TreeNodeLinkedToCognitiveNode`，认知中心再发 `CognitiveNodeLinked` |
| 9 | 知识树前端图引擎 | 待后续技术选型阶段确定（`@antv/g6` 或 `react-flow`） |

---

## 10. 结论与下一步

**结论**：Phase 1.1 事件协议收口已完成。`shared/events.py` 已补充全部缺失的跨模块事件，`AnswerSubmitted` 字段已对齐用户决策，`EVENT_TYPES` 注册表完整（118 个事件），契约测试 36 项全部通过。

**下一步建议**：
1. 进入 **Phase 2：练习模块单事件源改造**（以 `AnswerSubmitted` 为唯一事实源，取消 practice 模块直接调用 cognitive repository）。
2. 在 Phase 2 推进过程中并行处理 SourceRef schema 统一（Phase 1.2）。
3. 更新各设计稿中的事件注册状态与 schema 说明（可在对应模块编码前完成）。
