# Task 0022: 闪卡壳（Flashcard Shell）深度设计 v1.0

> 版本：v1.0
> 起草 Agent：AP007
> 起草时间：2026-07-11
> 状态：设计稿，待用户确认
> 依赖：Task 0015（目标架构愿景）、Task 0016（认知 OS 内核深度设计）、Task 0014（事件协议设计）、Task 0018（练习壳深度设计）、Task 0019（秘书编排器深度设计）、Task 0020（规划壳深度设计）、Task 0021（对话壳深度设计）

---

## 1. 定位与边界

### 1.1 一句话定位

闪卡壳是认知节点的「学习材料视图」和「间隔重复复习引擎」：它把来自对话、阅读、练习、项目等场景的碎片化知识封装成可复习的卡片，通过 FSRS 算法调度复习节奏，并把复习自评转化为学习事实事件，回写到认知节点的信念状态。

### 1.2 闪卡壳的职责（必须做）

| 职责 | 说明 |
|------|------|
| **卡片 CRUD** | 创建、读取、更新、删除、归档闪卡 |
| **多来源制卡** | 支持手动、对话笔记、阅读笔记、练习错题、项目、语言房间、兴趣探索 7 种来源 |
| **节点关联** | 每张卡片必须关联至少一个认知节点，区分 primary / secondary 角色 |
| **FSRS 调度** | 根据 stability / difficulty / forgetting_rate 计算下次复习时间 |
| **复习会话** | 支持开始复习会话、逐张复习、结束会话 |
| **自评回写** |  difficult / good / easy 自评转化为信念更新事件 |
| **错题联动** | 错题卡复习 easy 后自动标记错题本条目为已解决 |
| **笔记同步** | 与对话壳、阅读壳共享同一份节点材料，修改双向同步 |
| **统计面板** | 展示掌握度、到期量、来源分布、稳定性分布 |

### 1.3 闪卡壳的禁止（不由它做）

| 禁止项 | 原因 | 应该由谁做 |
|--------|------|-----------|
| 直接更新认知投影 belief | 破坏 SSOT | 认知状态中心订阅 `FlashCardReviewed` 后更新 |
| 维护掌握度/紧迫度 | 属于认知投影 | 认知 OS 内核 |
| 决定用户何时复习 | 属于秘书编排器策略 | 秘书编排器生成提案 |
| 直接生成题目 | 属于练习壳 | 练习壳 |
| 直接维护阅读笔记元数据 | 属于阅读壳 | 阅读壳 |
| 替用户归档/删除对话 | 属于对话壳 | 对话壳 |

### 1.4 闪卡壳在架构中的位置

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

**闪卡壳的特殊地位**：它是「认知原子模型」落地的关键视图层。练习产生错题 → 转为闪卡；对话产生笔记 → 转为闪卡；阅读产生标注 → 转为闪卡。闪卡把这些碎片统一为节点的学习材料，并通过复习让认知状态持续更新。

---

## 2. 领域模型

### 2.1 聚合根：FlashCard

```python
@dataclass
class FlashCard:
    """闪卡聚合根 — 认知节点的学习材料视图。"""

    card_id: str
    user_id: str

    # 卡片内容
    type: Literal[1, 2, 3, 4, 5, 6, 7] = 1
    source: Literal[
        "manual", "practice_error", "reading_note", "conversation",
        "project", "language_room", "interest_explorer"
    ] = "manual"
    front_text: str = ""
    back_text: str = ""
    back_context: str = ""  # 背面补充上下文/例子
    language: str = ""

    # 来源追溯
    source_ref: SourceRef = field(default_factory=SourceRef)

    # 状态
    status: Literal[
        "pending", "later", "processing", "completed", "suspended", "archived"
    ] = "pending"
    suspended_at: datetime | None = None
    is_resolved: bool = False

    # FSRS 调度参数
    stability: float = 2.5
    difficulty: float = 5.0
    forgetting_rate: float = 0.0
    last_review_at: datetime | None = None
    next_review_at: datetime | None = None
    review_count: int = 0
    lapse_count: int = 0
    target_retention: float = 0.85

    # 节点关联
    linked_node_ids: list[str] = field(default_factory=list)
    node_link_roles: dict[str, Literal["primary", "secondary"]] = field(default_factory=dict)

    # 标签与反思
    tags: list[str] = field(default_factory=list)
    error_book_entry_id: str = ""
    response_history: list[ReviewRecord] = field(default_factory=list)

    # 版本控制
    field_versions: dict[str, int] = field(default_factory=dict)

    created_at: datetime = field(default_factory=_now)
    updated_at: datetime = field(default_factory=_now)
```

**设计要点：**
- `type` 支持 7 种卡片类型：基础问答、填空、对比、流程、应用场景、错题溯源、反思。
- `source` 表达卡片来源，用于统计和策略决策。
- `source_ref` 精确追溯来源（如对话消息 ID、阅读段落偏移、错题条目 ID）。
- `node_link_roles` 区分 primary（核心知识点）和 secondary（相关知识点），影响 belief 回写权重。
- `field_versions` 实现字段级版本控制，便于冲突检测与同步。

### 2.2 值对象：SourceRef

```python
@dataclass(frozen=True)
class SourceRef:
    """卡片来源追溯 — 让闪卡可回到原始上下文。"""

    module: str = ""           # conversation / reading / practice / project / ...
    id: str = ""               # 原始对象 ID（如对话 ID、错题 ID）
    sub_id: str = ""           # 子对象 ID（如消息 ID、段落 ID）
    offset: int = 0            # 文本偏移（阅读场景）
    length: int = 0            # 文本长度
    url: str = ""              # 外部锚点
    title: str = ""            # 来源标题
```

### 2.3 值对象：ReviewRecord

```python
@dataclass(frozen=True)
class ReviewRecord:
    """一次复习记录。"""

    record_id: str
    card_id: str
    user_id: str
    session_id: str = ""

    self_assessment: Literal["difficult", "good", "easy"]

    stability_before: float
    stability_after: float
    difficulty_before: float
    difficulty_after: float
    interval_before: int
    interval_after: int
    elapsed_days: int
    retrievability_before: float

    reviewed_at: datetime = field(default_factory=_now)
```

### 2.4 实体：ReviewSession

```python
@dataclass
class ReviewSession:
    """一次复习会话。"""

    session_id: str
    user_id: str
    started_at: datetime
    ended_at: datetime | None = None

    card_count: int = 0
    difficult_count: int = 0
    good_count: int = 0
    easy_count: int = 0
    duration_seconds: int = 0

    source_module: str = "manual"  # manual / plan_item / secretary
    plan_item_id: str = ""
```

### 2.5 值对象：FSRSState

```python
@dataclass
class FSRSState:
    """FSRS 调度状态。"""

    stability: float           # 稳定性（天）
    difficulty: float          # 难度 [1, 10]
    forgetting_rate: float     # 遗忘速率 [0, 1]
    last_review_at: datetime | None
    next_review_at: datetime | None
    review_count: int
    lapse_count: int
    target_retention: float    # 目标保留率
```

---

## 3. 状态机

### 3.1 闪卡状态机

```
                    ┌─────────────┐
                    │   pending   │  （待复习）
                    └──────┬──────┘
                           │ start review / schedule
                           ▼
                    ┌─────────────┐
                    │ processing  │  （正在复习）
                    └──────┬──────┘
                           │
              ┌────────────┼────────────┐
              │            │            │
    difficult ▼   good     ▼   easy     ▼
        ┌─────────┐  ┌─────────┐  ┌─────────┐
        │ 仍是    │  │ 保持    │  │ 标记    │
        │ pending │  │ pending │  │completed│
        │(lapse++)│  │         │  │/resolved│
        └────┬────┘  └────┬────┘  └────┬────┘
             │            │            │
             ▼            ▼            ▼
    publish(FlashCardReviewed)  publish(FlashCardReviewed)

                    ┌─────────────┐
         suspend ──▶│  suspended  │
                    └──────┬──────┘
                           │ resume
                           ▼
                        pending

                    ┌─────────────┐
         archive ──▶│  archived   │
                    └─────────────┘
```

**关键规则：**
1. `pending` → `processing`：用户开始复习某张卡。
2. `processing` → `pending`：复习完成，根据自评计算新的 `next_review_at`。
3. 自评 `difficult` 增加 `lapse_count`，卡片仍回到 `pending`。
4. 自评 `easy` 可标记卡片为 `completed`（可配置）或 `is_resolved=true`。
5. `suspended` 是临时暂停，不影响 FSRS 计算。
6. `archived` 是长期归档，不再参与调度。

### 3.2 复习会话状态机

```
┌─────────┐   start   ┌─────────┐   first card   ┌─────────┐   next card   ┌─────────┐
│ pending │ ────────▶ │ active  │ ─────────────▶│reviewing│ ────────────▶│reviewing│
└─────────┘           └────┬────┘               └─────────┘              └────┬────┘
                           │                                                    │
                           │ end                                                │ end
                           ▼                                                    ▼
                    ┌─────────────┐                                       ┌─────────────┐
                    │   ended     │                                       │   ended     │
                    └─────────────┘                                       └─────────────┘
```

---

## 4. 事件协议

### 4.1 闪卡壳发布的事件

| 事件 | 消费者 | 说明 |
|------|--------|------|
| `FlashCardCreated` | 认知中心、秘书、分析 | 新卡片创建 |
| `FlashCardUpdated` | 认知中心、对话壳、阅读壳 | 卡片内容/节点关联修改 |
| `FlashCardReviewed` | 认知中心、错题本、秘书 | 完成一次复习自评 |
| `FlashCardStatusChanged` | 秘书、分析 | 卡片状态变化 |
| `FlashCardSuspended` | 秘书、分析 | 卡片暂停 |
| `FlashCardResumed` | 秘书、分析 | 卡片恢复 |
| `FlashCardReset` | 认知中心、分析 | 重置 FSRS 状态 |
| `FlashCardArchived` | 分析 | 卡片归档 |
| `FlashCardDeleted` | 分析 | 卡片删除 |
| `FlashCardSessionStarted` | 秘书、分析 | 复习会话开始 |
| `FlashCardSessionEnded` | 秘书、分析、奖励 | 复习会话结束 |
| `CognitiveNodeLinked` | 认知中心 | 通知节点 belief 更新（通过 BeliefWriter） |

### 4.2 闪卡壳订阅的事件

| 事件 | 来源 | 用途 |
|------|------|------|
| `NoteCreatedAsFlashcard` | 对话壳 | 从对话笔记创建闪卡 |
| `ReadingNoteCreated` | 阅读壳 | 从阅读笔记创建闪卡 |
| `ErrorRecorded` | 练习壳 | 从错题创建闪卡 |
| `ProposalAccepted` | 前端/秘书 | 用户接受复习提案后创建复习计划 |
| `PlanItemStarted` | 规划壳 | 开始计划中的复习项 |

### 4.3 关键事件定义

```python
@dataclass(frozen=True)
class FlashCardCreated(DomainEvent):
    """闪卡创建。"""

    user_id: str
    card_id: str
    type: int
    source: str
    cross_module_source: str | None = None
    linked_node_ids: list[str] = field(default_factory=list)
    source_ref: dict = field(default_factory=dict)


@dataclass(frozen=True)
class FlashCardUpdated(DomainEvent):
    """闪卡更新（内容或节点关联）。"""

    user_id: str
    card_id: str
    changed_fields: list[str] = field(default_factory=list)
    old_linked_node_ids: list[str] = field(default_factory=list)
    new_linked_node_ids: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class FlashCardReviewed(DomainEvent):
    """闪卡复习自评。"""

    user_id: str
    card_id: str
    session_id: str = ""

    self_assessment: Literal["difficult", "good", "easy"] = "good"

    stability_before: float = 0.0
    stability_after: float = 0.0
    difficulty_before: float = 0.0
    difficulty_after: float = 0.0
    interval_before: int = 0
    interval_after: int = 0
    elapsed_days: int = 0
    retrievability_before: float = 0.0

    linked_node_ids: list[str] = field(default_factory=list)
    node_link_roles: dict = field(default_factory=dict)


@dataclass(frozen=True)
class CognitiveNodeLinked(DomainEvent):
    """闪卡与认知节点关联变化，触发 belief 更新。"""

    user_id: str
    node_id: str
    link_type: str  # flashcard_review / flashcard_created / flashcard_updated
    target_ref_type: str = "flashcard"
    target_ref_id: str = ""
    action: str = "updated"  # created / updated / deleted
    belief_delta: dict = field(default_factory=dict)
```

---

## 5. 核心流程

### 5.1 手动创建闪卡

```
用户填写 front_text / back_text
  │
  ▼
选择/系统自动推荐 linked_node_ids
  │
  ▼
FlashCardService.create_card()
  │
  ▼
写入 flashcards 表
  │
  ▼
publish(FlashCardCreated)
  │
  ▼
认知中心订阅 → 更新节点材料池
秘书编排器订阅 → 纳入复习策略
```

### 5.2 从对话笔记创建闪卡

```
对话中用户说"把刚才的解释做成闪卡"
  │
  ▼
对话壳调用 create_flashcard 工具
  │ 参数：front_text, back_text, linked_node_ids, source_ref
  │
  ▼
publish(NoteCreatedAsFlashcard)
  │
  ▼
闪卡壳订阅并创建 FlashCard
  │ source="conversation"
  │ source_ref.module="conversation"
  │ source_ref.id="conv_xxx"
  │ source_ref.sub_id="msg_xxx"
  │
  ▼
publish(FlashCardCreated)
  │
  ▼
对话壳展示 FlashcardToolBlock
```

**关键设计：如何实现"对话中修改闪卡，对话历史同步"？**

- 闪卡内容不是孤立存储在闪卡壳，而是作为「认知节点材料池」的一部分。
- 当闪卡内容更新时，发布 `FlashCardUpdated` 事件，认知中心同步更新节点材料。
- 对话壳在展示历史消息时，对于嵌入的 `FlashcardToolBlock`，实时从节点材料池读取最新内容，而不是读取对话时快照。
- 这样用户在闪卡壳修改卡片后，回到对话历史看到的就是最新版本。

### 5.3 从错题本创建闪卡

```
练习壳 publish(ErrorRecorded)
  │
  ▼
错题本模块存储错题条目
  │
  ▼
用户/秘书发起"把错题转为闪卡"
  │
  ▼
闪卡壳调用 import_from_errorbook(error_id)
  │ 生成 suggested_front / suggested_back / suggested_linked_node_ids
  │
  ▼
用户确认后创建 FlashCard
  │ source="practice_error"
  │ error_book_entry_id="err_xxx"
  │
  ▼
publish(FlashCardCreated)
```

### 5.4 复习流程

```
用户开始复习会话
  │
  ▼
FlashCardService.start_session()
  │ publish(FlashCardSessionStarted)
  │
  ▼
查询 due cards（next_review_at <= now）
  │
  ▼
逐张展示卡片 front_text
  │
  ▼
用户查看背面并自评 difficult / good / easy
  │
  ▼
FSRScheduler.review() 计算新状态
  │
  ▼
写入 review_history + 更新 flashcards
  │
  ▼
publish(FlashCardReviewed)
  │
  ▼
BeliefWriter 计算 node weights → publish(CognitiveNodeLinked)
  │
  ▼
认知中心更新 belief projection
  │
  ▼
如果是错题卡且自评 easy → publish(ErrorBookEntryResolved)
  │
  ▼
会话结束 → publish(FlashCardSessionEnded)
```

---

## 6. 关键设计决策与多方案对比

### 6.1 决策 1：闪卡是否必须关联认知节点？

| 方案 | 说明 | 优点 | 缺点 | 结论 |
|------|------|------|------|------|
| A | 可选关联 | 灵活，用户可建任意卡片 | 形成数据孤岛，无法参与认知建模 | ❌ |
| **B** | **必须关联至少一个节点** | 统一认知原子，支持 belief 回写、知识树查看、秘书策略 | 创建时需要选择/推荐节点 | ✅ **推荐** |
| C | 默认关联一个"未分类"节点 | 折中 | 长期积累未分类垃圾 | 备选 |

**选择 B 的理由：**
- 认知原子模型要求所有学习内容最终落在认知节点上。
- 必须关联节点后，闪卡才能成为知识树壳的可视化材料、秘书编排器的策略输入、规划壳的行动目标。
- 创建时的节点选择可以通过 embedding 搜索 + 对话上下文自动推荐，降低用户负担。

### 6.2 决策 2：Belief 回写采用直接 UPDATE 还是事件通知？

| 方案 | 说明 | 优点 | 缺点 | 结论 |
|------|------|------|------|------|
| A | 闪卡壳直接 UPDATE knowledge_nodes.belief | 简单直接 | 破坏 SSOT，与认知中心双路径更新 | ❌ |
| **B** | **通过 CognitiveNodeLinked 事件通知认知中心更新** | 事件驱动，认知中心拥有唯一更新权 | 多一次事件分发 | ✅ **推荐** |

**选择 B 的理由：**
- 现有 `belief_writer.py` 已经采用事件通知模式，应继续强化而非回退。
- 认知中心可以聚合来自练习、闪卡、阅读、规划的多源证据，做更合理的 belief 更新。

### 6.3 决策 3：错题卡 resolved 状态由谁维护？

| 方案 | 说明 | 优点 | 缺点 | 结论 |
|------|------|------|------|------|
| A | 闪卡壳直接更新 error_book 表 | 快 | 破坏模块边界 | ❌ |
| **B** | **闪卡壳发布 ErrorBookEntryResolved 事件，错题本模块自己更新** | 模块自治，事件可追踪 | 需要错题本模块订阅事件 | ✅ **推荐** |

**选择 B 的理由：**
- 错题本属于练习壳的子域，闪卡壳不应直接写其表。
- 通过事件可以保留"错题因复习 easy 而被解决"的完整审计链。

### 6.4 决策 4：FSRS 计算放在应用层还是数据库层？

| 方案 | 说明 | 优点 | 缺点 | 结论 |
|------|------|------|------|------|
| A | 数据库层存储过程 | 批量复习时性能高 | 算法迭代需要改存储过程，难以测试 | 备选 |
| **B** | **应用层 Python 实现** | 易于单元测试、调参、扩展 | 批量时需要逐条计算 | ✅ **推荐** |
| C | 混合：核心公式在应用层，调度查询在数据库层 | 平衡 | 复杂度略高 | 长期优化 |

**选择 B 的理由：**
- 现有 `fsrs_scheduler.py` 已在应用层实现，算法透明、可观测。
- FSRS 参数调优是常见需求，应用层更灵活。
- 查询 due cards 时只需比较 `next_review_at`，不需要在数据库层计算。

### 6.5 决策 5：闪卡与对话/阅读笔记的内容同步策略

| 方案 | 说明 | 优点 | 缺点 | 结论 |
|------|------|------|------|------|
| A | 各自独立存储，互不影响 | 简单 | 用户修改一处，另一处不同步 | ❌ |
| **B** | **闪卡作为节点材料视图，共享同一份内容** | 修改双向同步 | 需要节点材料池抽象 | ✅ **推荐** |
| C | 闪卡保存副本，但记录指向源笔记的链接 | 保留原始上下文 | 修改不同步，只提供跳转 | 备选 |

**选择 B 的理由：**
- 用户明确要求"在对话系统或者闪卡系统修改了要能支持"同步。
- 认知原子模型下，笔记/闪卡都是节点的学习材料，共享一份内容最自然。
- 如果需要保留历史版本，可以通过 `field_versions` 实现，不影响当前视图同步。

---

## 7. API 契约

### 7.1 闪卡壳 Command API

```python
class FlashCardShell:
    async def create_card(
        self,
        user_id: str,
        front_text: str,
        back_text: str,
        linked_node_ids: list[str],
        type: int = 1,
        source: str = "manual",
        source_ref: dict | None = None,
        tags: list[str] | None = None,
    ) -> FlashCard: ...

    async def update_card(
        self,
        user_id: str,
        card_id: str,
        updates: dict,
        reset_scheduling: bool = False,
    ) -> FlashCard: ...

    async def review_card(
        self,
        user_id: str,
        card_id: str,
        self_assessment: Literal["difficult", "good", "easy"],
        session_id: str = "",
    ) -> ReviewResult: ...

    async def start_review_session(
        self,
        user_id: str,
        source_module: str = "manual",
        limit: int = 20,
        plan_item_id: str = "",
    ) -> ReviewSession: ...

    async def end_review_session(
        self,
        user_id: str,
        session_id: str,
        duration_seconds: int,
    ) -> ReviewSession: ...

    async def import_from_errorbook(
        self,
        user_id: str,
        error_entry_id: str,
    ) -> ImportPreview: ...

    async def import_from_text(
        self,
        user_id: str,
        text: str,
        default_linked_node_ids: list[str] | None = None,
    ) -> list[ImportPreviewItem]: ...
```

### 7.2 闪卡壳 Query API

```python
class FlashCardQueryService:
    async def get_card(self, user_id: str, card_id: str) -> FlashCard: ...

    async def list_cards(
        self,
        user_id: str,
        status: str | None = None,
        type: int | None = None,
        source: str | None = None,
        tag: str | None = None,
        node_id: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[FlashCard]: ...

    async def get_due_cards(
        self,
        user_id: str,
        limit: int = 20,
        node_id: str | None = None,
    ) -> list[FlashCard]: ...

    async def get_stats(self, user_id: str) -> FlashCardStats: ...
```

---

## 8. 集成点

### 8.1 与对话壳的集成

```
对话壳 ──NoteCreatedAsFlashcard────▶ 闪卡壳
闪卡壳 ──FlashCardCreated──────────▶ 认知中心（更新节点材料池）
闪卡壳 ──FlashCardUpdated──────────▶ 认知中心（同步节点材料）
认知中心 ──CognitiveNodeMetadataChanged──▶ 对话壳（刷新历史消息中的卡片视图）
```

### 8.2 与阅读壳的集成

```
阅读壳 ──ReadingNoteCreated─────────▶ 闪卡壳（或直接创建）
闪卡壳 ──FlashCardCreated──────────▶ 认知中心
source_ref: {module: "reading", id: "material_xxx", sub_id: "annotation_xxx", offset, length}
```

### 8.3 与练习壳的集成

```
练习壳 ──ErrorRecorded──────────────▶ 错题本
错题本 ──import_from_errorbook─────▶ 闪卡壳
闪卡壳 ──FlashCardCreated──────────▶ 认知中心
闪卡壳 ──FlashCardReviewed(easy)───▶ 错题本（ErrorBookEntryResolved）
```

### 8.4 与秘书编排器的集成

```
秘书编排器 ──ProposalGenerated(flashcard review)──▶ 前端
用户接受 ──ProposalAccepted──────────────────────▶ 规划壳（创建 PlanItem）
规划壳 ──PlanItemStarted─────────────────────────▶ 闪卡壳（启动复习会话）
闪卡壳 ──FlashCardSessionEnded───────────────────▶ 秘书编排器（更新信任/疲劳）
```

---

## 9. 核心算法

### 9.1 FSRS 核心公式

```python
# 保留率
R(t, S) = (1 + t / (9 * S)) ^ (-1)

# 由目标保留率反解间隔
I = 9 * S * (1/R_target - 1)

# 稳定性更新
def update_stability(S, D, R, rating):
    if rating == "difficult":
        return S * w11 * exp(-w12 * (D - 1))
    elif rating == "good":
        factor = 1 + exp(w8) * (11 - D) * S^(-w9) * (exp((1-R)*w10) - 1)
        return S * max(1.0, factor)
    elif rating == "easy":
        return S * (1 + w13)
```

### 9.2 Belief 回写权重

```python
def compute_belief_delta(assessment, node_roles):
    deltas = []
    for node_id, role in node_roles.items():
        weight = 1.0 if role == "primary" else 0.3
        contribution = 0.1 * weight
        if assessment == "easy":
            deltas.append({"node_id": node_id, "alpha_delta": contribution, "beta_delta": 0})
        elif assessment == "difficult":
            deltas.append({"node_id": node_id, "alpha_delta": 0, "beta_delta": contribution})
    return deltas
```

---

## 10. 风险点与缓解

| 风险 | 影响 | 缓解措施 |
|------|------|----------|
| 卡片必须关联节点导致创建门槛高 | 用户不愿用 | 自动推荐 linked_node_ids，支持模糊搜索 |
| FSRS 参数不适合所有用户 | 复习节奏不准 | 支持用户手动覆盖 stability/difficulty/target_retention |
| 错题卡 easy 后用户其实没真会 | 过早标记 resolved | 增加"连续两次 easy 才 resolved"策略 |
| 闪卡与笔记双向同步冲突 | 数据不一致 | 以节点材料池为 SSOT，field_versions 检测冲突 |
| 大量卡片导致 due 列表过长 | 用户压力 | 支持按节点/标签筛选，秘书编排器动态调节每日复习量 |
| 复习自评数据稀疏 | belief 更新慢 | 结合练习、阅读等多源证据，不要只依赖闪卡 |

---

## 11. 验收条件

1. 创建闪卡时必须关联至少一个认知节点，系统自动推荐前 3 个候选节点。
2. 从对话笔记、阅读笔记、错题本创建闪卡时，`source_ref` 能正确追溯原始上下文。
3. 复习自评后，`FlashCardReviewed` 事件正常发布，认知中心能正确更新 belief。
4. 错题卡自评 `easy` 后，自动发布 `ErrorBookEntryResolved` 事件。
5. 闪卡内容修改后，对话历史中的嵌入卡片视图能展示最新内容。
6. 支持按 status / type / source / tag / node_id 筛选卡片。
7. FSRS 调度计算可观测：返回 stability/difficulty/forgetting_rate/interval 的变化。
8. 秘书编排器能根据到期卡片生成复习提案。

---

## 12. 下一步

Task #23：阅读壳（Reading Shell）深度设计。
