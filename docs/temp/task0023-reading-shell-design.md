# Task 0023: 阅读壳（Reading Shell）深度设计 v1.0

> 版本：v1.0
> 起草 Agent：AP007
> 起草时间：2026-07-11
> 状态：设计稿，待用户确认
> 依赖：Task 0015（目标架构愿景）、Task 0016（认知 OS 内核深度设计）、Task 0014（事件协议设计）、Task 0018（练习壳深度设计）、Task 0019（秘书编排器深度设计）、Task 0020（规划壳深度设计）、Task 0021（对话壳深度设计）、Task 0022（闪卡壳深度设计）

---

## 1. 定位与边界

### 1.1 一句话定位

阅读壳是用户与「学习材料」之间的交互界面：它负责把 PDF、文章、视频等原始材料组织成可阅读、可标注、可笔记、可复习的认知加工入口，并通过标注、笔记、阅读进度等事件把用户的阅读行为转化为学习事实。

### 1.2 阅读壳的职责（必须做）

| 职责 | 说明 |
|------|------|
| **材料管理** | 导入、组织、归档、删除阅读材料（PDF/文章/视频/网页） |
| **阅读会话** | 开始、继续、结束阅读会话，支持中断恢复 |
| **高亮标注** | 5 色多意图标注（重要概念/数据事实/可引用/疑问/冲突） |
| **阅读笔记** | 把阅读中的问题/回应/关键论述转为闪卡反思型 |
| **节点关联** | 标注和笔记关联到认知节点，成为节点材料池的一部分 |
| **进度追踪** | 记录阅读位置、完成百分比、访问章节 |
| **对比阅读** | 支持两篇材料并排对比、同步滚动 |
| **回顾提醒** | 基于材料创建复习计划项（复用规划壳） |
| **阅读偏好** | 默认模式、高亮设置、复习间隔等 |

### 1.3 阅读壳的禁止（不由它做）

| 禁止项 | 原因 | 应该由谁做 |
|--------|------|-----------|
| 直接更新认知投影 | 破坏 SSOT | 认知状态中心 |
| 维护闪卡复习调度 | 属于闪卡壳 | 闪卡壳 |
| 维护计划项生命周期 | 属于规划壳 | 规划壳 |
| 生成跨模块计划 | 属于秘书编排器 | 秘书编排器 |
| 直接维护错题本 | 属于练习壳 | 练习壳 |
| 替用户做最终学习决策 | 用户拥有最终控制权 | 用户 |

### 1.4 阅读壳在架构中的位置

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

**阅读壳的特殊地位**：它是「原始学习材料」进入认知系统的第一站。标注、笔记、阅读时长等行为是低摩擦但高价值的学习事实。阅读壳的核心任务是把这些事实沉淀为事件，让后续的认知诊断、秘书提案、规划安排都能利用上。

---

## 2. 领域模型

### 2.1 聚合根：ReadingMaterial

```python
@dataclass
class ReadingMaterial:
    """阅读材料聚合根 — 原始学习材料的容器。"""

    material_id: str
    user_id: str

    title: str = ""
    author: str = ""
    source_url: str = ""
    material_type: Literal["pdf", "article", "video", "webpage", "epub"] = "article"

    # 内容组织
    chunks: list[MaterialChunk] = field(default_factory=list)  # 段落/章节列表
    total_length: int = 0  # 总字数/秒数

    # 元数据
    language: str = ""
    tags: list[str] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)

    # 状态
    status: Literal["uploading", "processing", "ready", "failed", "archived"] = "uploading"
    progress_pct: float = 0.0

    created_at: datetime = field(default_factory=_now)
    updated_at: datetime = field(default_factory=_now)
```

**设计要点：**
- `ReadingMaterial` 只负责材料的组织与元数据，不保存用户的标注/笔记（这些属于阅读壳的行为产物）。
- 材料被切分为 `MaterialChunk`，便于标注定位、RAG 检索、语义关联认知节点。
- `progress_pct` 是阅读进度的投影，可从 `ReadingSession` 事件重建。

### 2.2 实体：MaterialChunk

```python
@dataclass
class MaterialChunk:
    """材料的一个片段（章节/段落/视频片段）。"""

    chunk_id: str
    material_id: str
    user_id: str

    index: int = 0
    title: str = ""
    content: str = ""           # 文本内容或转录文本
    start_offset: int = 0       # 在材料中的起始位置
    end_offset: int = 0         # 在材料中的结束位置
    chunk_type: Literal["text", "heading", "image", "video_segment"] = "text"

    # 语义
    embedding: list[float] | None = None
    linked_node_ids: list[str] = field(default_factory=list)
```

### 2.3 实体：ReadingSession

```python
@dataclass
class ReadingSession:
    """一次阅读会话。"""

    session_id: str
    user_id: str
    material_id: str

    mode: Literal["intensive", "skim", "review"] = "intensive"
    started_at: datetime = field(default_factory=_now)
    ended_at: datetime | None = None
    duration_seconds: int = 0

    # 活动追踪
    chapters_visited: list[str] = field(default_factory=list)
    annotations_created: int = 0
    notes_created: int = 0
    cards_generated: int = 0
    linked_node_ids: list[str] = field(default_factory=list)

    # 中断恢复
    state_snapshot: dict = field(default_factory=dict)  # 最后浏览位置
    last_active_at: datetime = field(default_factory=_now)
```

### 2.4 实体：ReadingAnnotation

```python
@dataclass
class ReadingAnnotation:
    """阅读高亮标注。"""

    annotation_id: str
    user_id: str
    material_id: str

    chunk_id: str = ""
    start_offset: int = 0
    end_offset: int = 0

    color: Literal["yellow", "blue", "green", "purple", "orange"] = "yellow"
    intent: Literal[
        "important_concept", "data_fact", "quotable", "doubt", "conflict"
    ] = "important_concept"

    text: str = ""          # 标注原文
    note: str = ""          # 用户附加备注
    linked_node_id: str = ""  # 关联认知节点

    is_processed: bool = False  # 是否已被提取/转卡片/转对话
    followup: dict = field(default_factory=dict)  # 颜色对应的后续动作提示

    created_at: datetime = field(default_factory=_now)
    updated_at: datetime = field(default_factory=_now)
```

**设计要点：**
- 5 色 5 意图是固定的语义约定，前端和后端共享同一映射：
  - yellow → important_concept → 建议关联知识点或创建 FlashCard
  - blue → data_fact → 建议提取为数据卡片
  - green → quotable → 保留为原文引用
  - purple → doubt → 建议发起对话讨论
  - orange → conflict → 建议对比分析
- `is_processed` 防止同一段高亮被重复处理。

### 2.5 值对象：ReadingNote

```python
@dataclass(frozen=True)
class ReadingNote:
    """阅读笔记 — 实际存储为 FlashCard 反思型 (card_type=7)。"""

    note_id: str          # = flashcard_id
    user_id: str
    material_id: str

    front_text: str       # 我的问题
    back_text: str        # 我的回应
    back_context: str     # 关键论述

    linked_node_ids: list[str] = field(default_factory=list)
    chunk_id: str = ""
    chunk_id_range: list[str] = field(default_factory=list)

    source_ref: dict = field(default_factory=dict)
```

**设计要点：**
- 阅读笔记不单独建表，直接复用闪卡壳的 FlashCard（card_type=7，source='reading_note'）。
- 这样既获得了 FSRS 调度能力，又能与闪卡壳、对话壳共享节点材料池。
- `source_ref` 精确记录材料 ID、段落 ID、偏移量，支持一键回到原文。

### 2.6 值对象：ReadingComparison

```python
@dataclass(frozen=True)
class ReadingComparison:
    """对比阅读分组。"""

    comparison_id: str
    user_id: str
    material_id_left: str
    material_id_right: str
    sync_scroll: bool = False
    created_at: datetime = field(default_factory=_now)
```

### 2.7 值对象：ReadingPrefs

```python
@dataclass
class ReadingPrefs:
    """用户阅读偏好。"""

    user_id: str
    default_mode: Literal["intensive", "skim", "review"] = "intensive"
    highlight_mastered: bool = True    # 是否高亮已掌握知识点
    highlight_weak: bool = True        # 是否高亮薄弱知识点
    auto_open_sidebar: bool = True
    sync_scroll_default: bool = False
    review_reminder_days: list[int] = field(default_factory=lambda: [7, 30, 90])
```

---

## 3. 状态机

### 3.1 材料状态机

```
                    ┌─────────────┐
                    │  uploading  │
                    │  （上传中）  │
                    └──────┬──────┘
                           │ upload complete
                           ▼
                    ┌─────────────┐
                    │  processing │
                    │  （解析中）  │
                    └──────┬──────┘
                           │ parse success
                           ▼
                    ┌─────────────┐     archive      ┌───────────┐
                    │    ready    │◀────────────────▶│  archived │
                    │  （可阅读）  │                  │           │
                    └──────┬──────┘                  └───────────┘
                           │ parse fail
                           ▼
                    ┌─────────────┐
                    │   failed    │
                    └─────────────┘
```

### 3.2 阅读会话状态机

```
┌─────────┐   start   ┌─────────┐   pause/leave   ┌─────────┐   resume   ┌─────────┐
│ pending │ ────────▶ │ active  │ ───────────────▶│ paused  │ ─────────▶│ active  │
└─────────┘           └────┬────┘                 └─────────┘            └────┬────┘
                           │                                                   │
                           │ end                                               │ end
                           ▼                                                   ▼
                    ┌─────────────┐                                       ┌─────────────┐
                    │   ended     │                                       │   ended     │
                    └─────────────┘                                       └─────────────┘
```

### 3.3 标注处理状态机

```
                    ┌─────────────┐
                    │  unprocessed │
                    │  （未处理）  │
                    └──────┬──────┘
                           │ process → flashcard / conversation / node
                           ▼
                    ┌─────────────┐
                    │  processed  │
                    │  （已提取）  │
                    └─────────────┘
```

---

## 4. 事件协议

### 4.1 阅读壳发布的事件

| 事件 | 消费者 | 说明 |
|------|--------|------|
| `ReadingSessionStarted` | 秘书、分析 | 阅读会话开始 |
| `ReadingSessionEnded` | 秘书、分析、认知中心 | 阅读会话结束 |
| `ReadingModeChanged` | 秘书、分析 | 阅读模式切换 |
| `ReadingAnnotationCreated` | 秘书、分析 | 创建标注 |
| `ReadingAnnotationUpdated` | 秘书、分析 | 更新标注 |
| `ReadingAnnotationDeleted` | 秘书、分析 | 删除标注 |
| `ReadingAnnotationProcessed` | 闪卡壳、对话壳、认知中心 | 标注被处理为卡片/对话/节点 |
| `ReadingNoteCreated` | 闪卡壳、认知中心 | 创建阅读笔记（实际为 FlashCard） |
| `MaterialProgressUpdated` | 认知中心、秘书 | 材料阅读进度更新 |
| `ReadingComparisonCreated` | 分析 | 创建对比阅读 |

### 4.2 阅读壳订阅的事件

| 事件 | 来源 | 用途 |
|------|------|------|
| `ProposalAccepted` | 秘书/前端 | 接受"把这段高亮做成闪卡"等提案 |
| `CognitiveStateChanged` | 认知中心 | 在材料中高亮已掌握/薄弱知识点 |
| `FlashCardUpdated` | 闪卡壳 | 阅读笔记内容同步 |
| `PlanItemStarted` | 规划壳 | 开始计划中的阅读项 |

### 4.3 关键事件定义

```python
@dataclass(frozen=True)
class ReadingSessionStarted(DomainEvent):
    """阅读会话开始。"""

    user_id: str
    session_id: str
    material_id: str
    mode: str = "intensive"


@dataclass(frozen=True)
class ReadingSessionEnded(DomainEvent):
    """阅读会话结束。"""

    user_id: str
    session_id: str
    material_id: str

    duration_seconds: int = 0
    progress_pct: float = 0.0
    annotations_created: int = 0
    notes_created: int = 0
    cards_generated: int = 0
    linked_node_ids: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class ReadingAnnotationCreated(DomainEvent):
    """阅读标注创建。"""

    user_id: str
    annotation_id: str
    material_id: str
    chunk_id: str = ""
    color: str = "yellow"
    intent: str = "important_concept"
    linked_node_id: str = ""


@dataclass(frozen=True)
class ReadingAnnotationProcessed(DomainEvent):
    """阅读标注被处理为其他模块产物。"""

    user_id: str
    annotation_id: str
    material_id: str
    target_module: str  # flashcard / conversation / cognitive_node / project
    target_ref_id: str = ""


@dataclass(frozen=True)
class ReadingNoteCreated(DomainEvent):
    """阅读笔记创建（实际为 FlashCard 反思型）。"""

    user_id: str
    material_id: str
    card_id: str = ""
    source: str = "reading_note"
    cross_module_source: str = "reading"
    linked_node_ids: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class MaterialProgressUpdated(DomainEvent):
    """材料阅读进度更新。"""

    user_id: str
    material_id: str
    progress_pct: float = 0.0
    last_position: dict = field(default_factory=dict)
```

---

## 5. 核心流程

### 5.1 导入材料 → 可阅读

```
用户上传 PDF/文章/视频
  │
  ▼
ReadingMaterialService.create_material()
  │
  ▼
异步解析：OCR / 分 chunk / 生成 embedding
  │
  ▼
状态变为 ready
  │
  ▼
publish(MaterialProgressUpdated)
  │
  ▼
用户开始阅读
```

### 5.2 阅读会话中断恢复

```
用户打开材料
  │
  ▼
查询 active session（ended_at IS NULL）
  │
  ▼
如有 active session → 恢复 state_snapshot 中的位置
  │
  ▼
如无 active session → 创建新 session
  │
  ▼
publish(ReadingSessionStarted)
```

### 5.3 创建标注 → 处理为闪卡

```
用户选中段落并选择 yellow（重要概念）
  │
  ▼
ReadingAnnotationService.create_annotation()
  │
  ▼
写入 reading_annotations 表
  │
  ▼
publish(ReadingAnnotationCreated)
  │
  ▼
前端显示 followup："建议关联知识点或创建 FlashCard"
  │
  ▼
用户点击"创建闪卡"
  │
  ▼
调用闪卡壳 create_card()
  │ source="reading_note" / cross_module_source="reading"
  │ source_ref 记录 material_id / chunk_id / offsets
  │
  ▼
闪卡壳 publish(FlashCardCreated)
  │
  ▼
阅读壳标记标注 is_processed=True
  │
  ▼
publish(ReadingAnnotationProcessed)
```

### 5.4 创建阅读笔记

```
用户在阅读中写笔记
  │ 三段式：我的问题 / 关键论述 / 我的回应
  ▼
notes_svc.create_reading_note()
  │
  ▼
调用 FlashCardService.create_card(type=7, source='reading_note')
  │
  ▼
publish(ReadingNoteCreated)
  │
  ▼
认知中心订阅 → 更新节点材料池
闪卡壳订阅 → 纳入 FSRS 调度
```

### 5.5 阅读进度更新

```
用户滚动/翻页
  │
  ▼
前端定时上报 position
  │
  ▼
ReadingSessionService.update_activity()
  │
  ▼
更新 state_snapshot + progress_pct
  │
  ▼
publish(MaterialProgressUpdated)
  │
  ▼
秘书编排器订阅 → 评估是否该生成复习提醒
```

---

## 6. 关键设计决策与多方案对比

### 6.1 决策 1：阅读笔记是否独立建表？

| 方案 | 说明 | 优点 | 缺点 | 结论 |
|------|------|------|------|------|
| A | 独立 reading_notes 表 | 字段完全贴合阅读场景 | 与闪卡、对话笔记割裂，无法共享 FSRS 和节点材料池 | ❌ |
| **B** | **复用 FlashCard 反思型** | 自动获得复习调度、节点关联、跨壳同步 | 字段命名需要映射 | ✅ **推荐** |
| C | 独立表但同步到 FlashCard | 保留阅读语义 | 双写复杂，易不一致 | 备选 |

**选择 B 的理由：**
- 阅读笔记本质上是"对某个知识点的反思"，与闪卡反思型语义一致。
- 复用 FlashCard 后，阅读笔记自动进入 FSRS 调度，用户不需要额外操作。
- 与对话笔记、手动创建的反思型闪卡共享同一套节点材料池。

### 6.2 决策 2：标注是否合并到 FlashCard？

| 方案 | 说明 | 优点 | 缺点 | 结论 |
|------|------|------|------|------|
| A | 标注也存为 FlashCard | 统一存储 | 标注是高亮行为，不是复习卡片；强行卡片化会污染闪卡队列 | ❌ |
| **B** | **标注独立表，处理后才转为 FlashCard** | 区分"高亮"和"卡片"两个行为阶段 | 需要额外一张表 | ✅ **推荐** |

**选择 B 的理由：**
- 标注是轻量级行为（用户可能只是高亮），不一定想复习。
- 只有当用户明确把标注"处理"为闪卡/对话/节点时，才进入闪卡队列。
- `is_processed` 字段可以追踪标注的转化率，供秘书分析。

### 6.3 决策 3：阅读进度实时上报还是批量上报？

| 方案 | 说明 | 优点 | 缺点 | 结论 |
|------|------|------|------|------|
| A | 每次滚动都上报 | 进度精确 | 事件风暴，后端压力大 | ❌ |
| **B** | **节流批量上报（如每 10 秒或每翻一章）** | 平衡精度与性能 | 中断恢复时可能丢少量进度 | ✅ **推荐** |
| C | 只在 session end 上报 | 最简单 | 无法做实时干预 | 备选 |

**选择 B 的理由：**
- 阅读进度不需要毫秒级精确，秒级/章节级足够。
- 节流上报既支持中断恢复，又不会压垮事件总线。

### 6.4 决策 4：材料解析是同步还是异步？

| 方案 | 说明 | 优点 | 缺点 | 结论 |
|------|------|------|------|------|
| A | 同步解析，等完成再返回 | 用户立即可读 | 大文件上传慢，接口超时 | ❌ |
| **B** | **异步解析，上传后返回 processing 状态** | 接口稳定，支持大文件 | 需要轮询或 WebSocket 通知 | ✅ **推荐** |
| C | 后台预解析常见格式 | 最快 | 需要维护解析集群 | 长期优化 |

**选择 B 的理由：**
- PDF/OCR/视频转录都是耗时操作，不适合放在 HTTP 同步路径。
- 异步后可以逐步更新 `status: uploading → processing → ready`，前端展示进度。

### 6.5 决策 5：回顾提醒是否独立建表？

| 方案 | 说明 | 优点 | 缺点 | 结论 |
|------|------|------|------|------|
| A | 独立 reading_reminders 表 | 字段贴合阅读场景 | 与规划壳割裂 | ❌ |
| **B** | **复用 PlanItem（source_module='reading'）** | 统一计划视图，秘书/规划壳可见 | 需要规划壳支持 source_module 筛选 | ✅ **推荐** |

**选择 B 的理由：**
- 阅读回顾提醒本质上是"未来要做的事"，与规划壳的 PlanItem 语义一致。
- 复用后可以在今日计划、周视图中统一展示。
- 现有实现已经采用此方案，应继续强化。

---

## 7. API 契约

### 7.1 阅读壳 Command API

```python
class ReadingShell:
    async def create_material(
        self,
        user_id: str,
        title: str,
        material_type: str,
        file_url: str = "",
        source_url: str = "",
    ) -> ReadingMaterial: ...

    async def start_session(
        self,
        user_id: str,
        material_id: str,
        mode: str = "intensive",
    ) -> ReadingSession: ...

    async def end_session(
        self,
        user_id: str,
        session_id: str,
        duration_seconds: int | None = None,
    ) -> ReadingSession: ...

    async def update_session_activity(
        self,
        user_id: str,
        session_id: str,
        position: dict,
        progress_pct: float,
    ) -> ReadingSession: ...

    async def create_annotation(
        self,
        user_id: str,
        material_id: str,
        color: str,
        start_offset: int,
        end_offset: int,
        text: str = "",
        note: str = "",
        linked_node_id: str = "",
    ) -> ReadingAnnotation: ...

    async def process_annotation(
        self,
        user_id: str,
        annotation_id: str,
        target_module: str,
        target_ref_id: str = "",
    ) -> ReadingAnnotation: ...

    async def create_note(
        self,
        user_id: str,
        material_id: str,
        front_text: str,
        back_text: str = "",
        back_context: str = "",
        linked_node_ids: list[str] | None = None,
        chunk_id: str = "",
    ) -> dict: ...  # 返回 FlashCard

    async def create_review_reminder(
        self,
        user_id: str,
        material_id: str,
        review_after_days: int = 7,
        estimated_minutes: int = 30,
    ) -> PlanItem: ...
```

### 7.2 阅读壳 Query API

```python
class ReadingQueryService:
    async def get_material(self, user_id: str, material_id: str) -> ReadingMaterial: ...

    async def list_materials(
        self,
        user_id: str,
        status: str | None = None,
        material_type: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[ReadingMaterial]: ...

    async def get_active_session(
        self,
        user_id: str,
        material_id: str,
    ) -> ReadingSession | None: ...

    async def list_annotations(
        self,
        user_id: str,
        material_id: str,
        color: str | None = None,
        grouped: bool = False,
    ) -> list[ReadingAnnotation] | dict[str, list[ReadingAnnotation]]: ...

    async def list_notes(
        self,
        user_id: str,
        material_id: str | None = None,
    ) -> list[dict]: ...  # FlashCard list

    async def get_prefs(self, user_id: str) -> ReadingPrefs: ...
```

---

## 8. 集成点

### 8.1 与闪卡壳的集成

```
阅读壳 ──ReadingNoteCreated────────▶ 闪卡壳
阅读壳 ──ReadingAnnotationProcessed(target_module=flashcard)──▶ 闪卡壳
闪卡壳 ──FlashCardCreated──────────▶ 认知中心
闪卡壳 ──FlashCardUpdated──────────▶ 认知中心
认知中心 ──CognitiveNodeMetadataChanged──▶ 阅读壳（更新材料中的节点高亮）
```

### 8.2 与对话壳的集成

```
阅读壳 ──ReadingAnnotationProcessed(target_module=conversation)──▶ 对话壳
对话壳 ──NoteCreatedAsFlashcard────▶ 闪卡壳（来源可标记为 reading）
```

### 8.3 与规划壳的集成

```
阅读壳 ──create_review_reminder────▶ 规划壳（PlanItem source_module='reading'）
规划壳 ──PlanItemStarted───────────▶ 阅读壳（打开对应材料）
阅读壳 ──ReadingSessionEnded───────▶ 规划壳（自动完成关联 PlanItem）
```

### 8.4 与秘书编排器的集成

```
阅读壳 ──ReadingAnnotationCreated──▶ 秘书编排器
阅读壳 ──MaterialProgressUpdated──▶ 秘书编排器
秘书编排器 ──ProposalGenerated────▶ 阅读壳（"把这段高亮做成闪卡"）
```

---

## 9. 核心算法

### 9.1 材料分块与节点关联

```python
async def chunk_material_and_link_nodes(
    material: ReadingMaterial,
    user_id: str,
) -> list[MaterialChunk]:
    # 1. 按语义/章节分块
    chunks = semantic_chunk(material.content, chunk_size=500, overlap=50)

    # 2. 为每个 chunk 生成 embedding
    for chunk in chunks:
        chunk.embedding = await embed(chunk.content)

    # 3. 用 embedding 搜索最相关的认知节点
    for chunk in chunks:
        chunk.linked_node_ids = await cognitive_repo.semantic_search(
            chunk.content, user_id=user_id, top_k=3
        )

    return chunks
```

### 9.2 阅读进度计算

```python
def compute_progress(material: ReadingMaterial, state_snapshot: dict) -> float:
    if not material.chunks:
        return 0.0
    last_chunk_index = state_snapshot.get("last_chunk_index", 0)
    return min(1.0, (last_chunk_index + 1) / len(material.chunks))
```

### 9.3 标注后续动作推荐

```python
def suggest_followup(annotation: ReadingAnnotation) -> dict:
    return COLOR_FOLLOWUP.get(annotation.color, {
        "label": "通用",
        "suggestion": "可记录为笔记",
        "next_action": "create_note",
    })
```

---

## 10. 风险点与缓解

| 风险 | 影响 | 缓解措施 |
|------|------|----------|
| 大文件解析慢/失败 | 用户体验差 | 异步解析 + 进度通知 + 失败重试 |
| 阅读笔记与闪卡混淆 | 用户不理解 | 前端明确标注"这是阅读笔记，已加入复习队列" |
| 标注过多导致侧边栏混乱 | 可读性差 | 按颜色/意图分组，支持折叠 |
| 自动关联节点不准确 | 用户需要手动修正 | 推荐 top-3，用户可修改 |
| 阅读进度上报丢失 | 中断恢复不准 | 本地缓存 + 批量上报 + session end 最终上报 |
| 跨壳同步延迟 | 笔记修改后阅读壳显示旧版 | 以节点材料池为 SSOT，读取时实时拉取 |

---

## 11. 验收条件

1. 支持导入至少 3 种材料类型（PDF/文章/视频）。
2. 阅读会话支持中断恢复：关闭页面后重新打开能回到上次位置。
3. 5 色标注创建后，`ReadingAnnotationCreated` 事件正常发布。
4. 阅读笔记创建后，`ReadingNoteCreated` 事件正常发布，并能在闪卡壳中作为 FlashCard 反思型查看。
5. 标注处理为闪卡后，`ReadingAnnotationProcessed` 事件正常发布，标注 `is_processed` 标记为 true。
6. 阅读进度更新时，`MaterialProgressUpdated` 事件正常发布。
7. 回顾提醒创建后，能在规划壳中作为 `source_module='reading'` 的 PlanItem 查看。
8. 认知状态变化时，阅读材料中的对应知识点能高亮显示（已掌握/薄弱）。

---

## 12. 下一步

Task #24：知识树壳（Knowledge Tree Shell）深度设计。
