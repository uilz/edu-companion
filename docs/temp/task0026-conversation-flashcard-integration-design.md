# Task 0026: Phase 3 — 对话壳与闪卡整合深度设计 v1.0

> 版本：v1.0
> 起草 Agent：AP007
> 起草时间：2026-07-11
> 状态：设计稿，待用户确认
> 依赖：Task 0025（设计评审报告 / 事件协议收口）、Task 0021（对话壳深度设计）、Task 0022（闪卡壳深度设计）、Task 0016（认知 OS 内核深度设计）

---

## 1. 目标与范围

### 1.1 一句话目标

把「对话中沉淀笔记」和「闪卡复习」打通为**同一认知材料的两种视图**：对话壳负责捕获意图与上下文，闪卡壳负责间隔重复与记忆参数，二者通过事件协议双向同步，用户在任何一侧修改内容都能实时反映到另一侧。

### 1.2 解决的核心痛点

| 痛点 | 当前表现 | 本方案解决方式 |
|------|---------|--------------|
| 笔记与闪卡割裂 | 对话里记的笔记无法直接变成闪卡 | `ConversationNoteCreatedAsFlashcard` 事件 + 闪卡壳自动建卡 |
| 修改不同步 | 闪卡改了内容，对话笔记还是旧的 | 分字段所有权：内容字段归笔记侧，FSRS 参数归闪卡侧 |
| 对话内出题信息丢失 | 练习壳"盲出"题目，脱离对话上下文 | `InConversationTaskCreated(generate_practice)` + 练习壳读取完整上下文 |
| 答题过程不可见 | 系统不知道用户选选项停了多久 | `PracticeAnswerBehaviorRecorded` 遥测事件 + `DiagnosticSignal` 分析 |
| 秘书无法感知对话行动 | 对话里生成的闪卡/计划无法触发后续编排 | 事件总线自动通知秘书编排器 |

### 1.3 明确不做（边界）

- **不**把对话壳变成闪卡壳的 CRUD 入口：闪卡壳仍独立提供 `/api/flashcards/*`。
- **不**让对话壳直接更新 FSRS 参数：复习自评、调度仍由闪卡壳负责。
- **不**在本次 Phase 重构整个对话 LLM 推理链：只新增「意图识别 → 子任务 → 事件」的分支，原有 ReplyPipeline 保持兼容。
- **不**做实时协同编辑：笔记↔闪卡同步是**最终一致性**（事件驱动），延迟目标 < 1s。

---

## 2. 关键决策

### 2.1 分字段所有权（冲突解决）

| 字段组 | 所有权 | 修改入口 | 同步方向 |
|--------|--------|---------|---------|
| 内容字段（front_text / back_text / back_context / language / tags / linked_node_ids）| 对话笔记侧（源） | 对话笔记编辑器、闪卡编辑器均可改 | 源 → 闪卡；闪卡改内容时反向写回源笔记 |
| 记忆/调度字段（stability / difficulty / forgetting_rate / next_review_at / review_count / lapse_count / status / is_resolved）| 闪卡侧 | 仅闪卡复习流程 | 单向：闪卡 → 投影，不覆盖笔记 |
| 来源追溯（source_ref）| 共同只读 | 创建时写入，之后不可改 | 不变 |
| 版本控制（field_versions）| 闪卡侧维护 | 内容字段变化时闪卡侧 bump | 用于冲突检测，不覆盖用户数据 |

**冲突检测规则**：
- 当闪卡侧内容字段变化时，发布 `FlashCardUpdated(changed_fields=["front_text", ...])`。
- 对话壳订阅后，若发现源笔记的 `note_updated_at >= card_updated_at`，则放弃反向同步（源更新优先）。
- 若对话壳检测到笔记与闪卡内容字段不一致且时间戳接近（< 5s），标记为 `sync_conflict`，在前端提示用户选择。

### 2.2 事件协议最终收口

已在 Task 0025 / Task 0039 中完成：

| 事件 | 角色 | 发布者 | 消费者 |
|------|------|--------|--------|
| `ConversationNoteCreatedAsFlashcard` | 笔记→闪卡 | 对话壳 | 闪卡壳、秘书编排器、认知中心 |
| `FlashCardUpdated` | 闪卡内容反向同步 | 闪卡壳 | 对话壳（仅同步内容字段） |
| `FlashCardReviewed` | 复习自评 | 闪卡壳 | 认知中心、错题本、秘书编排器 |
| `PracticeAnswerBehaviorRecorded` | 答题微行为 | 练习前端/练习壳 | 认知中心（DiagnosticSignal）、秘书编排器 |
| `InConversationTaskCreated` | 对话内子任务 | 对话壳 | 练习壳 / 闪卡壳 / 规划壳 |
| `ProposalGenerated` / `ProposalAccepted` | 秘书提案 | 秘书编排器 / 前端 | 目标壳执行 |

### 2.3 对话内子任务模型

对话壳不直接生成题目/闪卡/计划，而是发布 `InConversationTaskCreated`，由目标壳消费并保留完整上下文：

```python
InConversationTaskCreated(
    user_id="u1",
    conv_id="c1",
    task_id="task_xxx",
    task_type="generate_practice",  # 或 generate_flashcard / generate_plan / generate_note
    user_request_text="用我刚才问的贝叶斯问题给我出 3 道不同难度的题",
    linked_node_ids=["bayes"],
    context_summary="用户正在学习贝叶斯定理，已讨论先验/似然/后验...",
    constraints=["难度覆盖 easy/medium/hard", "保留对话上下文"],
)
```

目标壳消费后：
- 练习壳：创建练习会话，题目 stem 中可引用 `context_summary` 与 `user_request_text`。
- 闪卡壳：创建闪卡，自动填充 `source_ref` 指向对话。
- 规划壳：创建计划项（或提案）。

---

## 3. 领域模型补充

### 3.1 对话笔记实体：ConversationNote

```python
@dataclass
class ConversationNote:
    """对话中的笔记 — 作为闪卡的源内容视图。"""

    note_id: str
    user_id: str
    conv_id: str
    source_message_id: str          # 从哪条 assistant 消息创建

    front_text: str = ""            # 问题/正面
    back_text: str = ""             # 回答/背面
    back_context: str = ""          # 补充上下文
    language: str = ""
    tags: list[str] = field(default_factory=list)
    linked_node_ids: list[str] = field(default_factory=list)

    source_ref: dict = field(default_factory=dict)  # SourceRef schema
    flashcard_id: str = ""          # 关联的闪卡 ID

    status: Literal["draft", "synced", "conflict"] = "draft"
    field_versions: dict[str, int] = field(default_factory=dict)
    created_at: datetime = field(default_factory=_now)
    updated_at: datetime = field(default_factory=_now)
```

**设计要点**：
- `flashcard_id` 建立 1:1 或 1:N 映射。默认一个笔记对应一张闪卡；未来可扩展为一张笔记对应多张闪卡（如正反面分离）。
- `status=conflict` 用于提示用户内容不一致。
- `field_versions` 与闪卡侧 `field_versions` 共同用于冲突检测。

### 3.2 答题遥测聚合：DiagnosticSignal

```python
@dataclass
class DiagnosticSignal:
    """由 PracticeAnswerBehaviorRecorded 派生的诊断信号。

    不直接修改 belief，只作为反馈和秘书编排的输入。
    """

    signal_id: str
    user_id: str
    attempt_id: str
    question_id: str

    signals: dict[str, float] = field(default_factory=dict)
    # 示例键：
    #   hesitation_ratio: 犹豫时间 / 总耗时
    #   answer_change_rate: 改选次数 / 选项数
    #   hover_focus: 鼠标在正确项上停留时间 / 总 hover 时间
    #   pause_burstiness: 输入停顿的突发度
    #   time_deviation: 实际耗时 / 预期耗时

    interpretation: str = ""        # 给前端的自然语言解释
    suggested_action: str = ""      # review / practice / hint / explain
    confidence: float = 0.0
    generated_at: datetime = field(default_factory=_now)
```

### 3.3 前端遥测采集模型

```typescript
interface AnswerTelemetry {
  telemetry_id: string;
  session_id: string;
  question_id: string;
  attempt_id: string;

  events: TelemetryEvent[];
  // events 类型：
  //   { type: "option_hover", option: "A", start_ms: 0, end_ms: 1200 }
  //   { type: "option_select", option: "A", at_ms: 1500 }
  //   { type: "option_deselect", option: "A", at_ms: 2300 }
  //   { type: "text_input_pause", duration_ms: 800, at_ms: 4200 }
  //   { type: "hint_open", at_ms: 3000 }
  //   { type: "submit", at_ms: 8000 }

  derived: {
    time_on_question_ms: number;
    hesitation_ms: number;
    answer_change_count: number;
    total_hover_ms: number;
    avg_text_pause_ms: number;
    hint_count: number;
  };
}
```

**设计要点**：
- 前端采集原始 events，本地计算 derived 指标后立即上报 `PracticeAnswerBehaviorRecorded`。
- 完整原始 events 存储在独立遥测表/对象存储，用于后续模型训练；事件总线只传轻量派生指标。
- 隐私与性能：events 批量上报，单题结束后一次性发送。

---

## 4. 核心流程

### 4.1 对话笔记 → 闪卡

```
用户选中 assistant 消息 → 点击"记为闪卡"
  │
  ▼
对话壳创建 ConversationNote (status=draft)
  │
  ▼
用户编辑正面/反面/关联节点 → 点击"保存"
  │
  ▼
发布 ConversationNoteCreatedAsFlashcard
  │
  ├───────────────┬────────────────┐
  ▼               ▼                ▼
闪卡壳订阅       秘书编排器订阅    持久化到 cognitive_events
  │
  ▼
闪卡壳创建 FlashCard (type=7 反思型, source="conversation")
  │
  ▼
闪卡壳发布 FlashCardCreated
  │
  ▼
对话壳订阅 FlashCardCreated，回填 ConversationNote.flashcard_id，status=synced
```

**SourceRef 构造**：
```python
source_ref = {
    "module": "conversation",
    "id": conv_id,
    "sub_id": source_message_id,
    "title": note_title,
    "metadata": {
        "note_id": note_id,
        "message_role": "assistant",
        "message_index": message_index,
    }
}
```

### 4.2 闪卡内容 → 笔记反向同步

```
用户在闪卡编辑器修改 front_text / back_text
  │
  ▼
闪卡壳更新 FlashCard，bump field_versions
  │
  ▼
发布 FlashCardUpdated(changed_fields=["front_text", "back_text"])
  │
  ▼
对话壳订阅 → 读取 source_ref.metadata.note_id
  │
  ▼
对比 ConversationNote.updated_at 与 FlashCard.updated_at
  │
  ├── 笔记更新 ▼ 跳过（源优先）
  │
  └── 闪卡更新 ▼ 反向写回 ConversationNote
              │
              ▼
        发布 NoteContentSyncedFromFlashcard（可选，用于审计）
```

### 4.3 答题微行为 → 诊断信号

```
用户开始答题
  │
  ▼
前端 TelemetryCollector 启动
  │
  ▼
用户 hover / select / input / submit
  │
  ▼
前端本地聚合 derived 指标
  │
  ▼
随 submit 一起上报 PracticeAnswerBehaviorRecorded
  │
  ▼
认知中心 DiagnosticSignalBuilder 消费
  │
  ▼
生成 DiagnosticSignal → 写入反馈视图
  │
  ▼
秘书编排器订阅 → 若检测到高犹豫/多次改选，生成"建议复习"提案
```

### 4.4 对话内出题（保留上下文）

```
用户说："给我出几道刚才讲的贝叶斯题"
  │
  ▼
对话壳意图识别 → task_type=generate_practice
  │
  ▼
构建 InConversationTaskCreated(
        user_request_text=...,
        linked_node_ids=["bayes"],
        context_summary=...,
        constraints=["基于当前对话上下文"]
    )
  │
  ▼
练习壳订阅 → 创建 SessionWithContext
  │
  ▼
练习壳返回 session_id 给对话壳
  │
  ▼
对话壳在消息流中插入 ToolBlock(type="practice", block_id=session_id)
```

---

## 5. API 契约

### 5.1 对话壳新增/修改接口

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/conversations/{conv_id}/notes` | 创建对话笔记 |
| PATCH | `/api/conversations/{conv_id}/notes/{note_id}` | 更新笔记内容 |
| DELETE | `/api/conversations/{conv_id}/notes/{note_id}` | 删除笔记 |
| POST | `/api/conversations/{conv_id}/tasks` | 创建对话内子任务 |
| GET | `/api/conversations/{conv_id}/notes` | 列出对话笔记 |
| GET | `/api/conversations/{conv_id}/notes/{note_id}` | 获取笔记（含关联闪卡状态） |

### 5.2 创建对话笔记请求/响应

```json
// POST /api/conversations/{conv_id}/notes
{
  "source_message_id": "msg_xxx",
  "front_text": "什么是贝叶斯定理？",
  "back_text": "P(A|B) = P(B|A) * P(A) / P(B)",
  "back_context": "先验、似然、后验的关系...",
  "linked_node_ids": ["bayes"],
  "tags": ["概率论"]
}

// Response 201
{
  "note_id": "note_xxx",
  "flashcard_id": "fc_yyy",          // 若 auto_create_flashcard=true
  "status": "synced",
  "source_ref": {
    "module": "conversation",
    "id": "conv_id",
    "sub_id": "msg_xxx",
    "metadata": {"note_id": "note_xxx"}
  }
}
```

### 5.3 创建对话内子任务请求/响应

```json
// POST /api/conversations/{conv_id}/tasks
{
  "task_type": "generate_practice",
  "user_request_text": "出 3 道贝叶斯题",
  "linked_node_ids": ["bayes"],
  "constraints": ["难度覆盖 easy/medium/hard"]
}

// Response 202 Accepted
{
  "task_id": "task_xxx",
  "status": "pending",
  "result_ref_id": null
}
```

### 5.4 闪卡壳新增/修改接口

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/flashcards/from-conversation-note` | 由对话笔记创建闪卡（内部/事件触发） |
| PATCH | `/api/flashcards/{card_id}` | 更新闪卡（内容变更时发布反向同步事件） |

### 5.5 练习壳新增/修改接口

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/practice/sessions/from-conversation-task` | 由对话内任务创建练习会话 |
| POST | `/api/practice/telemetry` | 接收前端遥测数据 |

---

## 6. 数据库变更

### 6.1 新增表：conversation_notes

```sql
CREATE TABLE conversation_notes (
    id VARCHAR(32) PRIMARY KEY,
    user_id VARCHAR(32) NOT NULL,
    conv_id VARCHAR(32) NOT NULL,
    source_message_id VARCHAR(32) NOT NULL,

    front_text TEXT NOT NULL,
    back_text TEXT,
    back_context TEXT,
    language VARCHAR(10),
    tags JSONB DEFAULT '[]',
    linked_node_ids JSONB DEFAULT '[]',

    source_ref JSONB DEFAULT '{}',
    flashcard_id VARCHAR(32),

    status VARCHAR(16) DEFAULT 'draft',  -- draft / synced / conflict
    field_versions JSONB DEFAULT '{}',

    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),

    FOREIGN KEY (conv_id) REFERENCES conversations(id) ON DELETE CASCADE,
    FOREIGN KEY (flashcard_id) REFERENCES flashcards(id) ON DELETE SET NULL
);

CREATE INDEX idx_conversation_notes_conv ON conversation_notes(conv_id);
CREATE INDEX idx_conversation_notes_flashcard ON conversation_notes(flashcard_id);
CREATE INDEX idx_conversation_notes_user ON conversation_notes(user_id);
```

### 6.2 新增表：answer_telemetry

```sql
CREATE TABLE answer_telemetry (
    id VARCHAR(32) PRIMARY KEY,
    user_id VARCHAR(32) NOT NULL,
    telemetry_id VARCHAR(64) NOT NULL UNIQUE,
    session_id VARCHAR(32),
    question_id VARCHAR(32) NOT NULL,
    attempt_id VARCHAR(32) NOT NULL,

    raw_events JSONB DEFAULT '[]',       -- 原始事件序列
    derived JSONB DEFAULT '{}',          -- 派生指标

    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_answer_telemetry_attempt ON answer_telemetry(attempt_id);
CREATE INDEX idx_answer_telemetry_user ON answer_telemetry(user_id);
```

### 6.3 新增表：diagnostic_signals

```sql
CREATE TABLE diagnostic_signals (
    id VARCHAR(32) PRIMARY KEY,
    user_id VARCHAR(32) NOT NULL,
    attempt_id VARCHAR(32) NOT NULL,
    question_id VARCHAR(32) NOT NULL,

    signals JSONB DEFAULT '{}',
    interpretation TEXT,
    suggested_action VARCHAR(32),
    confidence FLOAT DEFAULT 0.0,

    generated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_diagnostic_signals_attempt ON diagnostic_signals(attempt_id);
```

### 6.4 修改 flashcards 表

- 已存在 `source_ref` JSONB 字段，无需新增。
- 确保 `field_versions` 字段存在（已在 flashcard_schema.sql 中）。
- 建议增加 `conversation_note_id` 索引列或复用 `source_ref.metadata.note_id`。

---

## 7. 与现有模块的集成

### 7.1 与认知 OS 内核

| 集成点 | 说明 |
|--------|------|
| `FlashCardReviewed` → CognitiveStateChanged | 认知中心订阅复习自评，更新 belief |
| `PracticeAnswerBehaviorRecorded` → DiagnosticSignal | 认知中心分析微行为，不直接更新 belief |
| `ConversationNoteCreatedAsFlashcard` → CognitiveNodeLinked | 若笔记关联新节点，认知中心建立链接 |

### 7.2 与秘书编排器

| 集成点 | 说明 |
|--------|------|
| `ConversationNoteCreatedAsFlashcard` | 秘书可生成"基于新闪卡的复习计划"提案 |
| `DiagnosticSignal` | 秘书可生成"检测到犹豫，建议重新讲解"提案 |
| `InConversationTaskCreated` | 秘书可追踪用户意图，避免重复推荐 |

### 7.3 与规划壳

- `InConversationTaskCreated(task_type="generate_plan")` 由规划壳消费，生成 `PlanItemRequested` 或直接创建 plan item。
- 用户可在对话中直接说"帮我规划一下本周复习"，对话壳发布任务事件。

### 7.4 与阅读壳

- 阅读壳已使用 `ReadingNoteCreated` + 闪卡反思型。
- 本方案中的 `ConversationNoteCreatedAsFlashcard` 与 `ReadingNoteCreated` 是**并列来源**，闪卡壳统一消费并标记 `source` / `cross_module_source`。

---

## 8. 前端变更

### 8.1 对话消息操作栏

每条 assistant 消息增加：
- 「记为闪卡」按钮 → 打开侧边制卡面板
- 「出几道相关题」按钮 → 创建 `InConversationTaskCreated(generate_practice)`
- 「加入规划」按钮 → 创建 `InConversationTaskCreated(generate_plan)`

### 8.2 制卡侧边面板

```
┌─────────────────────────────┐
│  保存为闪卡                    │
├─────────────────────────────┤
│  正面（问题）                  │
│  [什么是贝叶斯定理？]          │
├─────────────────────────────┤
│  背面（答案）                  │
│  [P(A|B) = ...]              │
├─────────────────────────────┤
│  补充上下文                    │
│  [先验/似然/后验...]          │
├─────────────────────────────┤
│  关联知识点：[贝叶斯定理 ▼]    │
│  标签：[概率论]                │
├─────────────────────────────┤
│  [取消]        [保存并创建闪卡] │
└─────────────────────────────┘
```

### 8.3 遥测采集 SDK

新增 `AnswerTelemetryCollector`：
- 挂载在练习组件 lifecycle 上。
- 收集 hover、select、input、hint 事件。
- 在 `submit_answer` 时通过 `PracticeAnswerBehaviorRecorded` 上报派生指标。
- 原始 events 通过 `/api/practice/telemetry` 批量存储。

---

## 9. 实施顺序

### Phase 3.1：基础设施（1-2 天）

1. 创建 `conversation_notes` / `answer_telemetry` / `diagnostic_signals` 表。
2. 在 `shared/events.py` 中确认事件已收口（Task 0039 已完成）。
3. 对话壳新增笔记 CRUD API。
4. 前端新增消息操作栏与制卡面板。

### Phase 3.2：笔记→闪卡单向流（1-2 天）

1. 对话壳发布 `ConversationNoteCreatedAsFlashcard`。
2. 闪卡壳订阅并创建反思型卡片（type=7）。
3. 回填 `flashcard_id`，对话壳展示"已创建闪卡"状态。

### Phase 3.3：闪卡→笔记反向同步（1 天）

1. 闪卡壳更新时发布 `FlashCardUpdated`。
2. 对话壳订阅并反向写回 `conversation_notes`（分字段所有权）。
3. 冲突检测与前端提示。

### Phase 3.4：对话内子任务（1-2 天）

1. 对话壳发布 `InConversationTaskCreated`。
2. 练习壳消费 `generate_practice` 创建带上下文的会话。
3. 闪卡壳消费 `generate_flashcard`。
4. 规划壳消费 `generate_plan`。

### Phase 3.5：答题微行为（2 天）

1. 前端 `AnswerTelemetryCollector`。
2. `/api/practice/telemetry` 接收与存储。
3. 发布 `PracticeAnswerBehaviorRecorded`。
4. 认知中心 `DiagnosticSignalBuilder`。
5. 秘书编排器订阅生成提案。

### Phase 3.6：测试与收尾（1-2 天）

1. 单元测试、集成测试。
2. 端到端浏览器测试。
3. `rebuild.sh` 全链路验证。
4. 提交 git，更新 `docs/modules/conversation/overview.md` 与 `docs/modules/flashcard/overview.md`。

---

## 10. 验收条件

- [ ] 用户能在对话中选中 assistant 消息并一键创建闪卡，创建后可在闪卡列表中看到。
- [ ] 修改闪卡内容后，对话笔记中的内容同步更新（5s 内）。
- [ ] 修改对话笔记内容后，闪卡内容同步更新，且不会与闪卡复习参数冲突。
- [ ] 用户能在对话中说"给我出几道题"，系统创建带对话上下文的练习会话。
- [ ] 答题时前端能采集 hover/select/input 事件，后端能生成 DiagnosticSignal。
- [ ] `ConversationNoteCreatedAsFlashcard` / `FlashCardUpdated` / `PracticeAnswerBehaviorRecorded` 均能在事件流中追踪。
- [ ] 所有新增代码通过单元测试，`rebuild.sh` 启动成功，核心流程端到端通过。

---

## 11. 风险与缓解

| 风险 | 影响 | 缓解 |
|------|------|------|
| 双向同步冲突 | 用户同时改笔记和闪卡，内容覆盖 | 分字段所有权 + 时间戳优先 + 冲突提示 |
| 遥测数据量过大 | 每题产生大量 events | 前端聚合派生指标，原始 events 异步批量存储 |
| 对话内子任务失败 | 用户请求无响应 | 异步任务 + 轮询/websocket 状态更新 |
| 旧对话数据迁移 | 旧笔记无法转为闪卡 | 提供一次性迁移脚本，未迁移的保持只读 |

---

## 12. 待与用户确认的问题

1. **笔记→闪卡默认自动创建还是手动确认？** 当前设计为手动编辑后保存；是否需要"一键自动"模式？
2. **一张对话笔记是否允许对应多张闪卡？** 当前设计为 1:1，是否支持拆分正反面为两张卡片？
3. **遥测原始数据保留多久？** 建议 90 天，用于模型迭代；超出后归档或删除。
4. **DiagnosticSignal 是否立即展示给用户？** 建议作为反馈面板的高级信息，不在答题后立即弹窗打扰。
