# ADR 0018: 对话笔记与闪卡双向同步及答题微行为遥测

## 状态

- 状态：已接受
- 日期：2026-07-11
- 作者：AP007

## 背景

在重构后的「认知操作系统内核 + 场景壳」架构下，对话壳（Conversation Shell）与闪卡壳（Flashcard Shell）需要打通：

1. 用户在对话中记录的笔记应当能进入闪卡复习流程，而不是两套独立内容。
2. 用户在对话侧或闪卡侧修改内容时，另一側应保持同步。
3. 练习系统需要采集答题过程中的微行为（hover、选项切换、输入停顿等），用于智能诊断和秘书提案。

## 决策

### 决策 1：分字段所有权

- **内容字段**（`front_text` / `back_text` / `back_context` / `language` / `tags` / `linked_node_ids`）由 `conversation_notes` 所有。
- **记忆参数字段**（FSRS 参数：stability / difficulty / forgetting_rate 等）由 `flashcards` 所有。
- 反向同步只更新内容字段，不触碰闪卡记忆参数。

### 决策 2：事件驱动双向同步

- 笔记 → 闪卡：`ConversationNoteCreatedAsFlashcard` 事件由对话壳发布，闪卡壳消费后创建反思型卡片（`type=7`），并回填 `conversation_notes.flashcard_id`。
- 闪卡 → 笔记：`FlashCardUpdated` 事件由闪卡壳发布，对话壳消费后反向同步内容字段。
- 冲突解决采用**源优先**：笔记更新时间 >= 闪卡事件时间时，跳过反向同步。

### 决策 3：答题遥测只携带派生指标

- 前端采集原始行为事件（hover/select/input）并本地聚合为派生指标。
- 提交到后端的只有 `telemetry_id` + 派生指标，原始事件序列落库但不在事件总线上传播。
- 后端发布轻量 `PracticeAnswerBehaviorRecorded` 事件，供认知中心和秘书消费。

### 决策 4：DiagnosticSignal 作为只读诊断信号

- `DiagnosticSignalBuilder` 订阅 `PracticeAnswerBehaviorRecorded`，生成诊断信号并存入 `diagnostic_signals` 表。
- 诊断信号不直接修改 `Belief`，只作为秘书编排和反馈的输入。

## 后果

### 正面

- 对话笔记与闪卡内容保持一致，避免用户维护两套数据。
- 答题微行为进入事件流，支持更精细的认知诊断和主动服务。
- 事件驱动架构保证模块解耦，新增消费方无需修改发布方。

### 负面

- 引入双向同步后需要处理时间戳冲突和字段级版本追踪。
- 答题遥测需要前端 SDK 支持聚合逻辑。

## 相关实现

- `backend/app/services/conversation/conversation_note_service.py`
- `backend/app/services/flashcard/conversation_note_handler.py`
- `backend/app/services/practice/telemetry_service.py`
- `backend/app/domain/cognitive/diagnostic_signal_builder.py`
- `backend/app/domain/secretary/engines/secretary_event_handler.py`
- `backend/alembic/versions/3228233e13ee_add_conversation_notes_and_answer_.py`
- `backend/tests/test_phase3_conversation_flashcard_integration.py`
