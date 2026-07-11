# Conversation（对话壳）

> 用户与系统协作的核心交互界面：以多轮对话为载体，承载答疑、出题、笔记提取、任务创建等学习行为。

---

## 1. 模块定位

Conversation 是**对话壳（Conversation Shell）**，职责是：

- 提供自然语言交互入口，降低学习行为的启动成本
- 在对话过程中捕获有价值的学习材料（笔记、任务、错题线索）
- 通过事件协议将学习行为发布给认知 OS 内核、闪卡壳、规划壳、秘书等下游模块
- **不维护**知识状态、**不直接**调度复习、**不替代**各子领域的专业判断

**解决**：用户在学习的任意时刻都能以对话方式获得帮助，并把对话成果沉淀为结构化学习数据。

**不解决**：知识点状态管理（认知节点数据系统）；复习调度（闪卡壳 / 规划壳）；错题统计（练习系统）；阅读材料处理（阅读壳）。

---

## 2. 核心概念

| 概念 | 说明 |
|------|------|
| `Conversation` | 一次连续对话会话，属于知识树中的一个节点 |
| `Message` | 对话中的单条消息，支持文本、引用、内容块 |
| `ConversationNote` | 对话中的学习笔记，可一键转为闪卡 |
| `ConversationTask` | 在对话中创建的待办任务，推送到规划壳 |
| `SourceRef` | 跨模块来源引用值对象，描述「内容来自哪里」 |

---

## 3. 核心能力

### 3.1 多轮对话

- 支持分支、重放、引用、上下文压缩
- 支持在对话中绑定知识树节点（`knowledge_node_id`）
- 支持多种模式：tutor / feynman / peer

### 3.2 对话笔记（Phase 3）

- 用户可在任意 assistant 消息上创建笔记
- 笔记包含 `front_text` / `back_text` / `back_context` / `tags` / `linked_node_ids`
- 创建笔记时可选自动创建闪卡（默认开启）
- 笔记与闪卡保持**内容字段双向同步**：
  - 笔记 → 闪卡：`ConversationNoteCreatedAsFlashcard`
  - 闪卡 → 笔记：`FlashCardUpdated` 反向同步内容字段
- 源优先策略：笔记侧更新时间 >= 闪卡事件时间时跳过反向同步

### 3.3 对话内任务

- 在对话中识别或手动创建学习任务
- 发布 `InConversationTaskCreated` 事件，由规划壳消费

### 3.4 答题微行为遥测（Phase 3）

- 练习过程中前端采集 hover、选项切换、输入停顿等行为
- 前端聚合为派生指标后提交到 `/api/practice/telemetry`
- 后端保存原始事件并发布 `PracticeAnswerBehaviorRecorded` 事件
- 认知中心订阅后生成 `DiagnosticSignal`，秘书订阅后生成复习/讲解提案

---

## 4. 事件协议

对话壳发布的事件：

| 事件 | 消费方 | 说明 |
|------|--------|------|
| `UserMessageSent` | 秘书、分析模块 | 用户发送消息 |
| `ConversationNoteCreatedAsFlashcard` | 闪卡壳 | 笔记转闪卡 |
| `InConversationTaskCreated` | 规划壳 | 对话中创建任务 |
| `ConversationBranchCreated` | 对话系统 | 分支创建 |
| `ConversationArchived` | 对话系统 | 会话归档 |

对话壳消费的事件：

| 事件 | 发布方 | 说明 |
|------|--------|------|
| `FlashCardUpdated` | 闪卡壳 | 反向同步内容到对话笔记 |

---

## 5. API 入口

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/knowledge-tree/conversations` | 创建会话 |
| GET | `/api/conversations/tree/conversation/{conv_id}` | 获取会话 |
| POST | `/api/conversations/tree/conversation/{conv_id}/notes` | 创建笔记 |
| GET | `/api/conversations/tree/conversation/{conv_id}/notes` | 列出笔记 |
| PATCH | `/api/conversations/tree/conversation/{conv_id}/notes/{note_id}` | 更新笔记 |
| DELETE | `/api/conversations/tree/conversation/{conv_id}/notes/{note_id}` | 删除笔记 |
| POST | `/api/conversations/tree/conversation/{conv_id}/tasks` | 创建任务 |

---

## 6. 数据表

| 表名 | 说明 |
|------|------|
| `conversation_notes` | 对话笔记，与闪卡通过 `flashcard_id` 1:1 关联 |

完整 schema 见 Alembic 迁移 `3228233e13ee_add_conversation_notes_and_answer_.py`。

---

## 7. 模块联动

| 方向 | 内容 |
|------|------|
| 对话 → 闪卡 | 笔记转闪卡，双向同步内容字段 |
| 对话 → 规划 | 创建任务，推送到计划项 |
| 对话 → 秘书 | 用户消息、笔记创建、任务创建进入事件流 |
| 练习 → 对话 | 答题微行为遥测经认知中心分析后，秘书生成讲解/复习提案 |

---

## 8. 系统边界

**系统可做**：

- 自然语言交互与上下文管理
- 笔记创建与闪卡双向同步
- 任务创建与事件发布
- 接收练习遥测并转发事件

**系统不做**：

- 不维护认知节点状态
- 不直接调度复习
- 不自动生成卡片内容（仅沉淀用户确认的笔记）
- 不替代练习系统的判题逻辑
