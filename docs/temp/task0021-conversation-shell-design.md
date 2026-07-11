# Task 0021: 对话壳（Conversation Shell）深度设计 v1.0

> 版本：v1.0
> 起草 Agent：AP007
> 起草时间：2026-07-11
> 状态：设计稿，待用户确认
> 依赖：Task 0015（目标架构愿景）、Task 0016（认知 OS 内核深度设计）、Task 0014（事件协议设计）、Task 0018（练习壳深度设计）、Task 0019（秘书编排器深度设计）、Task 0020（规划壳深度设计）

---

## 1. 定位与边界

### 1.1 一句话定位

对话壳是用户与认知 OS 之间的「主交互界面」和「意图入口」：它负责理解用户当前想做什么、调用正确的能力（教学、练习、闪卡、规划、秘书）完成任务，并把对话过程中产生的学习事实（笔记、题目、闪卡、目标）沉淀为事件，让内核持续学习用户的认知状态。

### 1.2 对话壳的职责（必须做）

| 职责 | 说明 |
|------|------|
| **自然语言意图理解** | 解析用户输入，识别教学、练习、闪卡、规划、秘书、知识树等意图 |
| **多 Agent 会话编排** | 通过 Orchestrator 调度 Tutor / Coach / Secretary / 其他壳层能力 |
| **上下文构建** | 通过 ContextPipeline 组装认知、情绪、活动、能力、位置等上下文 |
| **流式回复生成** | 支持 token/reasoning/tool_block/agent_message 等事件流 |
| **对话内出题** | 在对话流中直接创建练习会话，保留完整上下文，不让练习壳"盲出" |
| **对话内制卡** | 把对话中的笔记、解释、例子一键转为闪卡，关联到认知节点 |
| **学习事实发布** | 用户确认后发布 `MessageClassified` / `AssistantReplied` / `NoteCreatedAsFlashcard` 等事件 |
| **会话生命周期** | 创建、继续、分支、归档、删除对话 |
| **消息与引用** | 支持文本、引用、图片、文件、工具块、代理消息等多种内容块 |

### 1.3 对话壳的禁止（不由它做）

| 禁止项 | 原因 | 应该由谁做 |
|--------|------|-----------|
| 直接更新认知投影 | 破坏 SSOT | 认知状态中心 |
| 直接判定答题对错 | 属于练习壳 | 练习壳 |
| 直接维护闪卡复习调度 | 属于闪卡壳 | 闪卡壳 |
| 直接创建/修改计划项 | 属于规划壳 | 规划壳（通过事件请求） |
| 替用户做最终学习决策 | 用户拥有最终控制权 | 用户 |
| 长期策略学习与编排 | 属于秘书编排器 | 秘书编排器 |

### 1.4 对话壳在架构中的位置

```
┌─────────────────────────────────────────────────────────────────┐
│                         场景壳层                                  │
│  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌───────────┐ │
│  │  对话壳  │ │  练习壳  │ │  闪卡壳  │ │  阅读壳  │ │  规划壳    │ │
│  │    │    │ │    │    │ │    │    │ │    │    │ │    │      │ │
│  └────┼────┘ └────┼────┘ └────┼────┘ └────┼────┘ └─────┼─────┘ │
│       │           │           │           │             │       │
│       └───────────┴───────────┴───────────┴─────────────┘       │
│                           │                                      │
│                    统一事件协议（shared/events.py）                │
└───────────────────────────┬──────────────────────────────────────┘
                            │
┌───────────────────────────▼──────────────────────────────────────┐
│                      认知 OS 内核                                  │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐      │
│  │  事件总线    │  │ 认知状态中心 │  │   秘书编排器         │      │
│  └─────────────┘  └─────────────┘  └─────────────────────┘      │
└─────────────────────────────────────────────────────────────────┘
```

**对话壳的特殊地位**：它是大多数用户意图的第一落点。很多"练习"、"规划"、"闪卡"请求其实先从对话壳进入，再由对话壳通过事件或工具调用委托给其他壳层。因此对话壳必须做好"意图分发"和"上下文不丢失"两件事。

---

## 2. 领域模型

### 2.1 聚合根：ConversationSession

```python
@dataclass
class ConversationSession:
    """对话会话聚合根 — 用户与系统一次连续对话的容器。"""

    conv_id: str
    user_id: str
    dir_id: str  # 所属分区/知识域

    title: str = "新对话"
    mode: Literal["tutor", "feynman", "peer", "review", "planning"] = "tutor"
    status: Literal["active", "archived", "deleted"] = "active"

    # 消息树（支持分支）
    root_message_id: str = ""
    current_leaf_id: str = ""  # 当前焦点消息，支持分支切换

    # 学习意图快照
    intents: list[DetectedIntent] = field(default_factory=list)
    active_agent_label: str = "tutor"

    # 关联的认知节点（本次对话涉及的知识点）
    linked_node_ids: list[str] = field(default_factory=list)

    # 会话元数据
    metadata: dict = field(default_factory=dict)
    created_at: datetime = field(default_factory=_now)
    last_active_at: datetime = field(default_factory=_now)
    version: int = 0
```

**设计要点：**
- `dir_id` 是分区（partition）或知识域（domain）的锚点，决定默认认知上下文。
- `mode` 支持 tutor（教学）、feynman（费曼）、peer（同伴）、review（复习）、planning（规划）五种对话模式。
- 消息树支持分支，用户可以随时回到历史消息继续另一条对话路径。
- `linked_node_ids` 是会话与认知节点的动态关联，由 Orchestrator 在运行中维护。

### 2.2 实体：ConversationMessage

```python
@dataclass
class ConversationMessage:
    """对话消息实体 — 消息树上的一个节点。"""

    msg_id: str
    conv_id: str
    user_id: str

    role: Literal["user", "assistant", "system", "tool", "agent"]
    agent_label: str = ""  # tutor / coach / secretary / orchestrator

    # 内容块（支持多模态）
    content_blocks: list[ContentBlock] = field(default_factory=list)

    # 树结构
    parent_id: str | None = None
    children_ids: list[str] = field(default_factory=list)

    # 工具/来源
    tool_calls: list[dict] = field(default_factory=list)
    response_blocks: list[ResponseBlock] = field(default_factory=list)

    # 元数据
    intent: DetectedIntent | None = None
    source_event_id: str | None = None  # 若由事件触发（如 ProposalAccepted 后自动开启）
    metadata: dict = field(default_factory=dict)

    created_at: datetime = field(default_factory=_now)
```

**设计要点：**
- 所有消息都是树上的节点，支持分支与回溯。
- `agent_label` 让前端能渲染不同头像、颜色、标签。
- `content_blocks` 支持 text / reasoning / quote / image / file / tool_block / agent_delegate 等类型。
- `source_event_id` 用于追踪"由秘书提案自动开启的对话"等自动化场景。

### 2.3 值对象：DetectedIntent

```python
@dataclass(frozen=True)
class DetectedIntent:
    """对话意图识别结果。"""

    intent_id: str
    primary: Literal[
        "explain",           # 讲解/答疑
        "practice",          # 想做题
        "create_flashcard",  # 想做闪卡
        "plan",              # 想规划
        "review",            # 想复习
        "explore",           # 想探索/发散
        "emotion_support",   # 情绪支持
        "chitchat",          # 闲聊
        "tool_use",          # 明确调用某个工具
        "ambiguous",         # 意图不明
    ]

    confidence: float = 0.0  # 0-1
    target_node_ids: list[str] = field(default_factory=list)
    extracted_entities: dict = field(default_factory=dict)

    # 多 Agent 协作时，决定路由到哪些 agent
    suggested_agents: list[str] = field(default_factory=list)
    agent_instructions: dict = field(default_factory=dict)
```

**设计要点：**
- 意图识别使用**规则 + LLM fallback** 双轨制，短消息沿用上一轮意图。
- `suggested_agents` 可能包含多个 agent，触发 Orchestrator 多 Agent 协作流。
- `target_node_ids` 让用户口中的"导数"、"链式法则"等自然语言映射到认知节点。

### 2.4 值对象：ContentBlock 联合类型

```python
class TextBlock(TypedDict):
    type: Literal["text"]
    text: str

class ReasoningBlock(TypedDict):
    type: Literal["reasoning"]
    text: str

class QuoteBlock(TypedDict):
    type: Literal["quote"]
    quoted_text: str
    source_message_id: str
    source_conv_id: str
    char_start: int
    char_end: int

class ToolBlock(TypedDict):
    type: Literal["tool_block"]
    block_type: str  # practice / flashcard / plan / mindmap / agent_delegate / ...
    block_id: str
    content: dict
    status: Literal["pending", "ready", "failed"]

class AgentDelegateBlock(TypedDict):
    type: Literal["agent_delegate"]
    source_agent: str
    target_agent: str
    instruction: str

ContentBlock = TextBlock | ReasoningBlock | QuoteBlock | ToolBlock | AgentDelegateBlock
```

### 2.5 值对象：InConversationTask

```python
@dataclass(frozen=True)
class InConversationTask:
    """对话过程中发起的子任务，例如"出 5 道题"、"做一张闪卡"。"""

    task_id: str
    conv_id: str
    user_id: str

    task_type: Literal[
        "generate_practice",
        "generate_flashcard",
        "generate_plan",
        "generate_note",
        "search_media",
        "generate_mindmap",
    ]

    # 原始请求上下文（关键！避免信息丢失）
    user_request_text: str = ""
    linked_node_ids: list[str] = field(default_factory=list)
    context_summary: str = ""  # 对话上下文的摘要
    constraints: list[str] = field(default_factory=list)

    # 生成的结果引用
    result_ref_id: str = ""  # session_id / flashcard_id / plan_item_id / note_id
    result_status: Literal["pending", "ready", "failed"] = "pending"

    created_at: datetime = field(default_factory=_now)
```

**设计要点：**
- `InConversationTask` 是解决"对话系统内出题交给练习系统会丢失信息"的关键结构。
- 它把用户的完整请求上下文（包括对话摘要、约束、关联节点）一起打包，交给目标壳层。
- 练习壳收到 `generate_practice` 任务后，使用 `QuestionGenerationSpec` 组卷，其中 `conv_context` 字段直接携带对话上下文。

---

## 3. 状态机

### 3.1 对话会话状态机

```
                    ┌─────────────┐
                    │   active    │
                    │  （进行中）  │
                    └──────┬──────┘
                           │
              ┌────────────┼────────────┐
              │            │            │
    archive   ▼   delete   ▼   branch   ▼
        ┌──────────┐  ┌────────┐  ┌──────────┐
        │ archived │  │ deleted│  │ branched │
        └──────────┘  └────────┘  └────┬─────┘
                                       │
                                       ▼
                              创建新的 active 会话
```

**关键规则：**
1. 一个用户在同一个 `dir_id` 下可以有多个 `active` 会话（多线程）。
2. `archived` 会话只读，可重新激活。
3. `deleted` 为软删除，保留事件可重建。
4. `branch` 操作从某条历史消息分叉，产生新的会话或新的消息分支。

### 3.2 消息节点状态机

```
┌─────────────┐   streaming   ┌─────────────┐   completed   ┌─────────────┐
│   pending   │ ─────────────▶│  streaming  │ ─────────────▶│   final     │
└─────────────┘               └─────────────┘               └─────────────┘
                                     │
                                     │ error / cancelled
                                     ▼
                               ┌─────────────┐
                               │  failed     │
                               └─────────────┘
```

**关键规则：**
1. `pending`：已预分配 msg_id，等待 LLM 开始输出。
2. `streaming`：正在流式输出 token/tool_block。
3. `final`：流结束，内容块已落库。
4. `failed`：发生错误或用户取消。

### 3.3 子任务状态机

```
┌─────────┐   accepted   ┌─────────┐   delegated   ┌─────────┐   result   ┌─────────┐
│ pending │ ───────────▶ │accepted │ ────────────▶ │running  │ ─────────▶│ ready   │
└─────────┘              └────┬────┘               └─────────┘           └────┬────┘
                              │                                                │
                              │ reject                                         │ fail
                              ▼                                                ▼
                         ┌─────────┐                                      ┌─────────┐
                         │ rejected│                                      │ failed  │
                         └─────────┘                                      └─────────┘
```

---

## 4. 事件协议

### 4.1 对话壳发布的事件

| 事件 | 消费者 | 说明 |
|------|--------|------|
| `MessageClassified` | 秘书、分析 | 用户消息已完成意图分类，附带检测到的意图 |
| `AssistantReplied` | 秘书、分析 | 助手已回复，附带内容块和 agent_label |
| `NoteCreatedAsFlashcard` | 闪卡壳、认知中心 | 对话中的笔记被转为闪卡 |
| `InConversationTaskCreated` | 练习壳、闪卡壳、规划壳 | 对话内发起的子任务 |
| `ConversationBranchCreated` | 分析、前端 | 对话发生分支 |
| `ConversationArchived` | 分析 | 对话归档 |

### 4.2 对话壳订阅的事件

| 事件 | 来源 | 用途 |
|------|------|------|
| `ProposalAccepted` | 秘书/前端 | 用户接受提案后，可能自动开启对应对话 |
| `CognitiveStateChanged` | 认知中心 | 实时更新对话上下文中的认知画像 |
| `PlanItemStarted` | 规划壳 | 用户在规划中开始练习，对话壳可展示提醒 |
| `SessionCompleted` | 练习壳 | 练习完成后回到对话壳展示总结 |

### 4.3 关键事件定义

```python
@dataclass(frozen=True)
class MessageClassified(DomainEvent):
    """用户消息已完成意图分类。"""

    conv_id: str
    user_id: str
    msg_id: str

    detected_intent: DetectedIntent
    raw_user_text: str = ""
    linked_node_ids: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class AssistantReplied(DomainEvent):
    """助手完成一次回复。"""

    conv_id: str
    user_id: str
    msg_id: str
    parent_msg_id: str = ""

    agent_label: str = "tutor"
    content_blocks: list[dict] = field(default_factory=list)
    response_blocks: list[dict] = field(default_factory=list)

    # 元认知追踪
    used_tool_names: list[str] = field(default_factory=list)
    referenced_node_ids: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class InConversationTaskCreated(DomainEvent):
    """对话内发起子任务，保留完整上下文。"""

    task_id: str
    conv_id: str
    user_id: str

    task_type: str
    user_request_text: str = ""
    linked_node_ids: list[str] = field(default_factory=list)
    context_summary: str = ""
    constraints: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class NoteCreatedAsFlashcard(DomainEvent):
    """对话中的笔记被保存为闪卡，关联到认知节点。"""

    note_id: str
    flashcard_id: str
    conv_id: str
    user_id: str

    front_text: str = ""
    back_text: str = ""
    linked_node_ids: list[str] = field(default_factory=list)
    source_message_id: str = ""
```

---

## 5. 核心流程

### 5.1 用户发送消息 → 流式回复（单 Agent）

```
用户输入
  │
  ▼
[SaveMessageStage] 保存用户消息
  │ publish(MessageClassified)
  ▼
[ClassifyStage] 意图分类
  │
  ▼
[Orchestrator] 决定 routing_plan = [tutor]
  │
  ▼
[ContextPipeline] 组装上下文
  ├─ ConversationModeProvider
  ├─ ConversationLocationProvider
  ├─ LearnerEmotionProvider
  ├─ LearnerCognitionProvider
  ├─ LearningActivityProvider
  └─ TutorCapabilityProvider
  │
  ▼
[ToolLoopStage] LLM 流式生成 / 工具调用
  │ token / reasoning / tool_block
  ▼
[PostProcessStage] 追问解析 + 来源解析 + 保存助手消息
  │ publish(AssistantReplied)
  ▼
[DoneStage]
```

### 5.2 用户说"给我出 5 道链式法则的题"（对话内出题）

```
用户输入
  │
  ▼
ClassifyStage → intent=practice, target_node_ids=["chain_rule"]
  │
  ▼
Orchestrator → routing_plan = [tutor]
  │
  ▼
Tutor Agent 调用工具 generate_practice
  │ 参数携带：
  │   - target_node_ids=["chain_rule"]
  │   - count=5
  │   - difficulty_mode="auto"
  │   - question_types=["single", "multiple"]
  │   - conv_context="用户在对话中刚问完链式法则，希望巩固..."
  │   - constraints=["不要考三角函数链式法则", "用中文题干"]
  │
  ▼
练习壳接收 InConversationTaskCreated
  │
  ▼
练习壳生成 PracticeSession
  │ publish(AnswerSubmitted) → 认知中心
  ▼
返回 session_id 给对话壳
  │
  ▼
对话壳在回复中嵌入 PracticeToolBlock
  │
  ▼
用户点击 PracticeToolBlock → 进入练习壳
```

**关键设计：为什么不在对话壳直接调用练习壳 API？**

因为我们希望练习壳拥有自己的事务边界和事件发布语义。对话壳通过 `InConversationTaskCreated` 事件把"带有完整上下文的请求"交给练习壳，练习壳独立创建会话、组卷、发布事件。这样既保留了上下文，又遵守了"写操作只产生事件"的契约。

### 5.3 用户说"把刚才的解释做成闪卡"（笔记 → 闪卡）

```
用户输入
  │
  ▼
ClassifyStage → intent=create_flashcard
  │
  ▼
Tutor Agent 调用工具 create_flashcard
  │ 参数：
  │   - front_text="链式法则的核心思想是什么？"
  │   - back_text="复合函数求导 = 外层导数 × 内层导数"
  │   - linked_node_ids=["chain_rule"]
  │   - source_message_id="msg_xxx"
  │
  ▼
闪卡壳接收 NoteCreatedAsFlashcard 事件
  │
  ▼
闪卡壳创建 Flashcard，关联 cognitive node
  │ publish(CognitiveNodeMetadataChanged)
  ▼
返回 flashcard_id 给对话壳
  │
  ▼
对话壳展示 FlashcardToolBlock（可预览、可跳转编辑）
```

**关键设计：为什么对话中的笔记用闪卡实现？**

因为闪卡是"认知节点的学习材料视图"（见 Task 0015 认知原子模型）。对话中产生的笔记本质上是对某个知识点的理解，把它做成闪卡就自然关联到了认知节点。之后在闪卡壳修改，也会通过事件同步到认知节点；在知识树壳查看节点时，也能看到这张闪卡。

### 5.4 多 Agent 协作场景

```
User: "最近导数学得怎么样？感觉不太扎实，能不能讲讲链式法则"
  │
  ▼
Orchestrator → routing_plan = [
  {agent: "secretary", instruction: "诊断用户最近导数学习情况，输出掌握度、薄弱点"},
  {agent: "tutor", instruction: "根据 secretary 的诊断，针对性讲解链式法则"}
]
  │
  ▼
Orchestrator 出声："让我先看看你的学习数据，再让 Tutor 针对性讲解。"
  │
  ▼
Secretary Agent 流：
  token("根据最近3次练习，导数掌握度62%，链式法则准确率55%...")
  │
  ▼
Tutor Agent 流：
  token("看到了，链式法则是你的薄弱项。先从基本概念来...")
  │
  ▼
Orchestrator done
```

**消息树结构：**

```
[user_msg]
  └── [orchestrator_msg]  "让我先看看..."
        ├── [secretary_msg]  "根据最近3次..."
        └── [tutor_msg]      "看到了，链式..."
```

---

## 6. 关键设计决策与多方案对比

### 6.1 决策 1：Orchestrator 应该放在对话壳还是内核？

| 方案 | 位置 | 优点 | 缺点 | 结论 |
|------|------|------|------|------|
| A | 对话壳内 | 贴近消息流，延迟低，易于调试 | 其他壳层无法复用调度能力 | ❌ 不满足跨壳联动 |
| B | 内核中独立 | 所有壳层共享，统一调度策略 | 与对话细节耦合时沟通成本高 | 部分正确 |
| **C** | **对话壳内，但能力通过事件暴露** | 既贴近对话，又能被秘书/规划壳通过事件触发 | 需要清晰的事件边界 | ✅ **推荐** |

**选择 C 的理由：**
- Orchestrator 的核心输入是"用户自然语言消息"，天然属于对话壳。
- 但秘书编排器可以通过 `ProposalAccepted` 等事件触发 Orchestrator 启动一个"由事件驱动的对话"。
- Orchestrator 的"路由决策"结果（DetectedIntent + routing_plan）通过 `MessageClassified` 事件发布，供内核分析。

### 6.2 决策 2：上下文构建采用集中式预加载还是 Provider 按需访问？

| 方案 | 说明 | 优点 | 缺点 | 结论 |
|------|------|------|------|------|
| A | 集中式预加载 bag | 一次查完所有数据，Provider 只读 bag | 预加载逻辑成为瓶颈，新增 Provider 需要改预加载 | ❌ 不满足扩展性 |
| **B** | **Provider 独立按需访问** | 每个 Provider 自己决定查什么，互不阻塞 | 可能重复查询 | ✅ **推荐** |
| C | 混合：核心 bag + Provider 扩展 | 平衡性能与扩展 | 复杂度高，边界易模糊 | 备选 |

**选择 B 的理由：**
- 对话上下文涉及的数据源差异很大（情绪、认知、练习、知识树、工具能力），很难用一个统一的 bag 表达。
- Provider 独立访问让新增上下文维度变得容易，例如未来加入"阅读进度"只需新增一个 Provider。
- 重复查询问题可以通过在每个 Provider 内部加本地缓存或请求级缓存解决。

### 6.3 决策 3：对话内出题采用同步生成还是异步生成？

| 方案 | 说明 | 优点 | 缺点 | 结论 |
|------|------|------|------|------|
| A | 同步生成，等题目返回再回复 | 用户立即可见，流程简单 | AI 出题慢时用户体验差，阻塞回复流 | ❌ |
| **B** | **异步生成，先返回确认卡片，完成后推送** | 不阻塞对话流，可展示进度 | 需要任务状态追踪 | ✅ **推荐** |
| C | 预生成题目池，对话时直接取 | 响应最快 | 需要额外存储和命中率管理 | 长期优化 |

**选择 B 的理由：**
- AI 出题可能涉及 LLM 调用、知识点匹配、难度校准，耗时几秒到几十秒。
- 异步生成时，Tutor 可以先回复"好的，我正在为你准备 5 道链式法则练习题..."，然后展示 pending 的 PracticeToolBlock。
- 题目生成完成后，通过 WebSocket 推送 block 更新事件。

### 6.4 决策 4：多 Agent 消息是独立节点还是合并节点？

| 方案 | 说明 | 优点 | 缺点 | 结论 |
|------|------|------|------|------|
| A | 合并为一条 assistant 消息 | 简单，前端改动小 | 无法区分 agent，失去多 Agent 协作的可解释性 | ❌ |
| **B** | **每条 agent 回复独立成节点** | 清晰展示谁说了什么，支持单独引用/分支 | 消息树变深 | ✅ **推荐** |
| C | 合并 but 内容块带 agent_label | 折中 | 历史消息结构复杂 | 备选 |

**选择 B 的理由：**
- 用户需要知道"这是秘书的诊断"、"这是 Tutor 的讲解"，才能建立信任。
- 独立节点支持对某条 agent 消息单独引用、分支、评价。
- 前端渲染时可以通过缩进/颜色区分协作组。

### 6.5 决策 5：工具调用权限按 Agent 过滤还是全开放？

| 方案 | 说明 | 优点 | 缺点 | 结论 |
|------|------|------|------|------|
| A | 按 Agent 白名单过滤 | 安全，避免 Agent 越权 | 限制灵活性，Orchestrator 需要维护映射 | 备选 |
| **B** | **全开放，通过 system prompt 约束行为** | 简单，Agent 可以灵活组合 | 需要 LLM 足够听话 | ✅ **推荐** |

**选择 B 的理由：**
- 苹果果的 Agent 边界是"职责建议"而非"权限隔离"。
- 通过 system prompt 和工具描述足够让 LLM 理解每个 Agent 该做什么。
- 全开放避免了 Orchestrator 维护复杂白名单，也支持 Agent 调用 `tool_delegate` 自由协作。

---

## 7. API 契约

### 7.1 对话壳 Command API

```python
class ConversationShell:
    async def create_conversation(
        self,
        user_id: str,
        dir_id: str,
        title: str = "",
        mode: str = "tutor",
        linked_node_ids: list[str] | None = None,
    ) -> ConversationSession: ...

    async def send_message(
        self,
        user_id: str,
        conv_id: str,
        text: str,
        parent_id: str | None = None,
        pending_quote: dict | None = None,
        content_blocks: list[dict] | None = None,
    ) -> AsyncGenerator[ConversationEvent, None]: ...

    async def resume_suspended_pipeline(
        self,
        user_id: str,
        conv_id: str,
        tool_call_id: str,
        answer: str,
    ) -> AsyncGenerator[ConversationEvent, None]: ...

    async def create_branch(
        self,
        user_id: str,
        conv_id: str,
        from_msg_id: str,
        new_user_text: str = "",
    ) -> ConversationSession: ...

    async def archive_conversation(
        self,
        user_id: str,
        conv_id: str,
    ) -> ConversationSession: ...
```

### 7.2 对话壳 Query API

```python
class ConversationQueryService:
    async def get_conversation(
        self,
        user_id: str,
        conv_id: str,
    ) -> ConversationDetail: ...

    async def list_conversations(
        self,
        user_id: str,
        dir_id: str | None = None,
        status: str = "active",
        limit: int = 20,
        offset: int = 0,
    ) -> list[ConversationSummary]: ...

    async def get_message_tree(
        self,
        user_id: str,
        conv_id: str,
    ) -> MessageTree: ...
```

### 7.3 WebSocket 事件协议

```typescript
type ConversationEvent =
  | { type: "user_message"; message: Message }
  | { type: "pending_msg"; msg_id: string; agent_label: string }
  | { type: "token"; msg_id: string; content: string; agent_label: string }
  | { type: "reasoning"; msg_id: string; content: string; agent_label: string }
  | { type: "tool_block"; msg_id: string; block: ToolBlock; agent_label: string }
  | { type: "agent_message"; msg_id: string; content: string; agent_label: "orchestrator" }
  | { type: "context_switch"; switch_detail: ContextSwitchDetail }
  | { type: "pipeline_suspended"; tool_call_id: string }
  | { type: "done"; msg_id: string; response_blocks: ResponseBlock[] }
  | { type: "error"; msg_id: string; error: string };
```

---

## 8. 集成点

### 8.1 与练习壳的集成

```
对话壳 ──InConversationTaskCreated(task_type=generate_practice)──▶ 练习壳
练习壳 ──PracticeSessionCreated(session_id)──────────────────────▶ 对话壳（通过事件 / WS 推送）
练习壳 ──AnswerSubmitted────────────────────────────────────────▶ 认知中心
认知中心 ──CognitiveStateChanged────────────────────────────────▶ 对话壳 ContextPipeline
```

**关键点：**
- 对话壳只负责"触发"和"展示"，不维护练习状态。
- `QuestionGenerationSpec.conv_context` 必须携带对话摘要，避免出题丢失信息。

### 8.2 与闪卡壳的集成

```
对话壳 ──NoteCreatedAsFlashcard──────────────────────────────────▶ 闪卡壳
闪卡壳 ──FlashcardCreated(flashcard_id)──────────────────────────▶ 对话壳（展示卡片）
闪卡壳 ──FlashCardReviewed───────────────────────────────────────▶ 认知中心
```

**关键点：**
- 对话中的笔记默认先作为"节点学习材料"，用户可一键"转为闪卡"。
- 闪卡修改时通过 `CognitiveNodeMetadataChanged` 事件同步到认知节点，知识树壳也能看到。

### 8.3 与规划壳的集成

```
对话壳 ──InConversationTaskCreated(task_type=generate_plan)──────▶ 规划壳
规划壳 ──PlanItemCreated────────────────────────────────────────▶ 对话壳（展示计划卡片）
用户点击"接受计划" ──ProposalAccepted───────────────────────────▶ 规划壳
```

### 8.4 与秘书编排器的集成

```
对话壳 ──MessageClassified──────────────────────────────────────▶ 秘书编排器
秘书编排器 ──ProposalGenerated──────────────────────────────────▶ 对话壳（展示提案卡片）
用户点击"接受" ──ProposalAccepted───────────────────────────────▶ 秘书编排器 / 对应壳层
秘书编排器 ──OrchestrationContextUpdate─────────────────────────▶ 对话壳 ContextPipeline
```

---

## 9. 核心算法与策略

### 9.1 意图分类双轨算法

```python
async def classify_intent(
    user_text: str,
    conv_context: ConversationContext,
    previous_intent: DetectedIntent | None,
) -> DetectedIntent:
    # 规则层
    rule_result = _rule_based_classify(user_text, conv_context)
    if rule_result.confidence >= 0.85:
        return rule_result

    # 短消息沿用上一轮意图
    if len(user_text.strip()) <= 3 and previous_intent:
        return previous_intent

    # LLM fallback
    llm_result = await _llm_classify(user_text, conv_context)
    return _merge_intents(rule_result, llm_result)
```

### 9.2 上下文压缩策略

当对话历史过长时，ContextPipeline 需要压缩历史消息：

```python
def compress_history(messages: list[Message], max_tokens: int) -> list[Message]:
    # 1. 保留最近 N 轮完整消息
    recent = messages[-6:]

    # 2. 对更早消息进行摘要
    older = messages[:-6]
    summary = _summarize_messages(older, focus_nodes=linked_node_ids)

    return [summary_message] + recent
```

### 9.3 对话 → 认知节点映射

```python
async def resolve_nodes_from_text(
    user_text: str,
    dir_id: str,
    user_id: str,
) -> list[str]:
    # 1. 用 embedding 搜索语义最近节点
    semantic_hits = await cognitive_repo.semantic_search(user_text, dir_id, user_id, top_k=5)

    # 2. 用 KG 关系扩展（前置/相关节点）
    expanded = await kg_repo.expand_by_relationship(semantic_hits, hops=1)

    # 3. 用 LLM 做消歧
    return await _llm_disambiguate(user_text, candidates=expanded)
```

---

## 10. 风险点与缓解

| 风险 | 影响 | 缓解措施 |
|------|------|----------|
| Orchestrator 路由错误 | 用户看到不相关的 Agent 回复 | 双轨分类 + 允许用户点击"换 Agent"重新路由 |
| 对话上下文过长 | 延迟高、token 贵 | 上下文压缩 + 摘要 + 关键节点快照 |
| 工具调用失败 | 回复中断 | 工具执行异常捕获，fallback 到文本回复 |
| 多 Agent 协作消息树过深 | 前端展示混乱 | 协作组折叠 + 颜色/头像区分 |
| 对话内出题上下文丢失 | 题目不符合用户期望 | `InConversationTaskCreated` 强制携带 `context_summary` + `constraints` |
| 笔记 → 闪卡同步冲突 | 数据不一致 | 闪卡作为节点材料视图，修改通过事件同步 |
| LLM 不遵守 Agent 角色 | 越权调用工具 | 强 system prompt + 后处理校验 tool_block 类型 |

---

## 11. 验收条件

1. 用户发送消息后，能在 500ms 内看到 `pending_msg`。
2. 单 Agent 场景下，流式回复 token 延迟 < 1s（首 token）。
3. 对话内出题请求能正确携带 `conv_context`，生成的题目与对话主题一致。
4. 对话中创建的闪卡能在闪卡壳和知识树壳中双向同步。
5. 多 Agent 协作场景下，消息树能正确展示 orchestrator/secretary/tutor 三条消息。
6. `MessageClassified` 和 `AssistantReplied` 事件能正常发布并被秘书编排器消费。
7. 上下文构建支持至少 6 个 Provider，新增 Provider 不需要修改 Pipeline 核心代码。

---

## 12. 下一步

Task #22：闪卡壳（Flashcard Shell）深度设计。
