# ADR 0003: Reading（知识加工车间）

## Status

Accepted

## 实现状态（截至 2026-07-02）

### 已实现

- **决策 1 核心定位**：阅读模块 = `file-management` 之上的"阅读体验 + 加工工具"增强层
- **决策 2 阅读材料预处理**：复用 `Material` / `MaterialChunk` + `embedding` + TOC（章节锚点 = `chunk_id`）
- **决策 3 阅读中的知识互动**：
  - 3.1 已有知识点高亮（混合匹配 = 标签 + embedding，阈值可配置默认 0.85）
  - 3.2 划线与标注（5 颜色多意图，存 `reading_annotations` 表）
  - 3.3 上下文提问（复用 `ExplainCard`）
  - 3.4 跨材料参照提示（基于 `MaterialChunk.embedding` + 知识图谱相似度）
- **决策 4 阅读笔记复用 FlashCard 反思型**：**不新建 `reading_notes` 表**（设计保持）
- **决策 5 阅读后的综合处理**：阅读收获面板 + 回顾提醒（复用 0006 Planning）+ 阅读事件
- **决策 6 阅读策略支持**：精读/略读/回顾 3 模式 + 阅读速度统计
- **决策 7 多材料对比阅读**：分屏 + 同步滚动 + 跨材料标注
- **决策 8 阅读材料版本管理**：`material.versions[]` 关联

### 与原设计差异

- **关键差异 1（source 字段拆分 — 决策 4 实际状态）**：`ReadingNoteCreated` 实际使用**两个互斥字段**（`shared/events.py:1152-1163`）：
  - `source: Literal["reading_note"]` = 阅读笔记的内部归类
  - `cross_module_source: Literal["reading"] | None` = 跨模块引用来源
  - 与 `FlashCardCreated` 的 `source` / `cross_module_source` 拆分保持一致
- **关键差异 2（事件 schema 实际名称）**：
  - 原设计稿 4 个事件，实际为 10 个：`ReadingSessionStarted` / `ReadingSessionEnded` / `ReadingSessionResumed` / `ReadingAnnotationCreated` / `ReadingAnnotationUpdated` / `ReadingAnnotationDeleted` / `ReadingAnnotationProcessed` / `ReadingModeChanged` / `ReadingNoteCreated` / `ReadingReviewReminderScheduled`（`docs/modules/reading/events.md`）
- **关键差异 3（命名统一 — `nodes_linked` → `linked_node_ids`）**：`ReadingSessionEnded.nodes_linked` 旧命名已统一为 `linked_node_ids`（`shared/events.py:1055`），与 LanguageRoom/Project 命名一致
- **关键差异 4（标注 intent 枚举值显式化）**：原设计中文 `important/data/quote/question/conflict`，实际为 `important_concept` / `data_fact` / `quotable` / `doubt` / `conflict`（`shared/events.py:1083-1086`），与 color 字段语义对应
- **关键差异 5（target_module 统一）**：`ReadingAnnotationProcessed.target_module` 实际为 `CrossModuleTarget` 枚举（`flashcard` / `conversation` / `cognitive_node`，`shared/events.py:1128`），强类型校验
- **关键差异 6（ReadingReviewReminderScheduled）**：原设计说"复用 0006 PlanItemScheduled"，实际**新建**了 `ReadingReviewReminderScheduled` 事件作为提醒意图的事件，由 0006 消费后**内部**创建 `PlanItem`（`source_module='reading'`），而非直接发 `PlanItemScheduled`（`docs/modules/reading/events.md §2.3` + `events.md §5`）
- **关键差异 7（Belief 拆分事件）**：阅读事件**不**触发 `CognitiveNodeUpdated`（已废弃），Belief 更新严格由练习/FlashCard/对话主动行为产生
- **关键差异 8（图表索引归属）**：原设计"图表索引 = 阅读模块独立实现"，实际未单独建表，图表标注通过 `reading_annotations` + 关联 `linked_node_id` 实现

### 待修复

- **待修复 1**：图表索引（独立列表 + 点击跳转）尚未独立实现，目前通过标注 + 关联节点间接支持
- **待修复 2**：对比阅读的"标注导出为对比表，存入项目模块"链路未端到端打通（标注可导出，但未自动转对比 FlashCard）
- **待修复 3**：5 颜色标注的"后续动作提示"（软引导）UI 弱化，目前以手动操作为主
- **待修复 4**：阅读收获面板的"标注/笔记拖入生成卡片"批量操作 UI 需补强
- **待修复 5**：术语嗅探 API（知识图谱模块提供）尚未独立端点，目前走 `embedding` 相似度匹配

## Context

### 要解决的问题

学习者的核心知识输入通道是**阅读**（论文、教材、参考书、文档）。当前痛点：

- 阅读时标注、笔记、心得散落在多处，无法进入知识体系
- 读到已学过的概念时，缺乏即时反馈（掌握度、关联卡片）
- 跨材料对比、跨版本对照缺乏工具
- 阅读完没有闭环：标注、笔记、提问、心得难以转化为可复习的资产

现有系统的状态：

- `file-management` 模块已实现：文件上传、PDF/文档解析、TOC 索引、RAG 检索、MaterialChunk 分块、练习生成
- `Material` / `MaterialChunk` 数据模型已存在（含 `embedding` / `skill_ids` / `chunk_type`）
- 知识图谱已有 `CognitiveNode.mastery`、BFS 扩展
- 解释卡片（`ExplainCard`）是绑定 `message_id` 的对话标注
- FlashCard 模块（ADR 0002）有"多源提取"接口，含阅读笔记来源

**关键洞察**：阅读模块**不是**文档查看器，也**不是**文件存储层。它是**在 file-management 之上的"阅读体验 + 加工工具"增强层**。

### 关键定位：与 file-management 的关系

| 层级 | 职责 | 现有归属 |
|------|------|---------|
| **存储/解析层** | 文件上传、格式解析、分块、向量化、TOC、RAG 索引 | `file-management`（已有） |
| **阅读体验层** | 章节展示、阅读模式、标注、笔记、对比、回顾 | **阅读模块（本 ADR）** |
| **知识层** | 知识点状态、掌握度、关联 | `CognitiveNode` |
| **材料层** | FlashCard / Question / ErrorBookEntry / ExplainCard | 已有 + ADR 0002 |

**复用原则**：

- 章节结构 = 复用 `file-management` 的 TOC
- 段落锚点 = 复用 `MaterialChunk.chunk_id`
- 知识图谱匹配 = 复用 `MaterialChunk.embedding` + `CognitiveNode.embedding`
- 上下文对话 = 复用 `ExplainCard` 机制
- 提取为卡片 = 复用 `FlashCard` 多源提取接口

**新建原则**：

- 标注系统（新表 `reading_annotations`）
- 笔记 = **复用 FlashCard 反思型**（`source='reading_note'`）— **不新建 reading_notes 表**
- 阅读会话状态（新表 `reading_sessions`）
- 阅读模式 / 对比阅读 / 版本管理
- 回顾提醒 = **复用 0006 Planning 提醒机制**（触发 `PlanItemScheduled` 事件，source_module='reading'）

### 模块定位

一个**用户主导的知识加工车间**：

- 帮助用户在阅读中完成**信息拆解、关联、转化**
- 让阅读的每一处标注都能进入卡片、知识图谱、练习
- 构建"阅读→加工→复习→应用"完整闭环
- **不做**：自动摘要、自动评估重要性、自动调整知识掌握度

### 与现有系统的关系

| 对方 | 阅读模块提供 | 阅读模块使用 |
|------|------------|------------|
| `file-management` | 阅读会话、标注、笔记、模式 | TOC、MaterialChunk、RAG 检索 |
| `CognitiveNode` | 知识图谱匹配、阅读事件 | 知识点 mastery 显示、关联 |
| `FlashCard` | 多源提取（笔记/划线→卡片） | FlashCard 创建接口、复习回链 |
| `ExplainCard` | 基于选中文本发起对话 | 上下文对话机制 |
| 对话模块 | 阅读中上下文提问 | 对话接口、消息流 |
| 项目模块 | 阅读材料作为项目节点关联；对比输出到项目 | 项目节点引用、成果板导入 |
| 规划模块 | 阅读回顾提醒排入日程 | 调度接口 |
| 全局事件流 | `ReadingSessionEnded` 事件 | 消费知识点更新事件 |
| 练习模块 | 笔记/标注生成自测题 | 题目生成 API |

## Decision

### 1. 核心定位：阅读体验增强层

- 阅读模块 = 消费 `file-management` 数据 + 提供标注/笔记/模式/对比/回顾能力
- 不再独立实现文件存储、解析、分块、向量化
- 所有材料数据通过 `Material` / `MaterialChunk` API 访问

### 2. 阅读材料的预处理（依赖 file-management）

- **章节识别**：完全复用 `file-management` 的 TOC 数据；用户可手动调整
- **段落锚点**：完全复用 `MaterialChunk.chunk_id`，不造平行 ID
- **图表索引**：阅读模块独立实现（file-management 暂无）—— 识别材料中的图表及其标题，生成图表索引列表，点击跳转；图表可单独标注和关联知识点
- **术语嗅探**：调用**知识图谱模块**的"候选知识点识别 API"（理由：术语识别需要知识图谱的标签/embedding 库，是知识图谱的能力）

### 3. 阅读中的知识互动

#### 3.1 已有知识点高亮（混合匹配策略）

- **第一步**：标签精确匹配——将用户知识图谱节点的 `label` 与正文文本匹配
- **第二步**：对未匹配的段落用 `MaterialChunk.embedding` 与 `CognitiveNode.embedding` 做相似度检索
- **阈值可配置**（默认 0.85）
- **分层显示**：核心知识点（掌握度高且关联密集的）用淡标记，薄弱知识点用醒目标记
- 悬停弹出：概念定义摘要、当前掌握度、关联卡片数、上次复习时间
- 点击跳转：进入该知识点的完整页面

#### 3.2 划线与标注（多意图分类）

存储在新表 `reading_annotations`：

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | UUID | 主键 |
| `user_id` | str | 用户 ID |
| `material_id` | str | 所属材料 |
| `chunk_id` | str | 所属段落（复用 MaterialChunk） |
| `start_offset` | int | 段落内起始偏移 |
| `end_offset` | int | 段落内结束偏移 |
| `color` | enum | yellow / blue / green / purple / orange |
| `intent` | enum | important / data / quote / question / conflict |
| `note` | str\|null | 用户批注 |
| `linked_node_ids` | list[str] | 关联知识点 |
| `created_at` | datetime | 创建时间 |

**颜色与意图映射**：

| 颜色 | 意图 | 后续动作提示 |
|------|------|-------------|
| 黄色 | 重要概念 | 建议关联知识点或创建卡片 |
| 蓝色 | 数据/事实 | 建议提取为数据卡片 |
| 绿色 | 可引用段落 | 保留为原文引用 |
| 紫色 | 疑问/反驳 | 建议发起对话讨论 |
| 橙色 | 与其他内容冲突 | 建议对比分析 |

标注在侧栏形成结构化列表，按颜色分类、按章节分组。

#### 3.3 上下文提问（复用 ExplainCard）

- 选中文本唤起对话时，**复用 ExplainCard 机制**（绑定 message_id）
- 对话自动携带：
  - 当前选中文本
  - 所在 chunk 的上下文（前后段落）
  - 用户已关联的知识点列表
- 对话结果可保存为笔记（写入 `reading_notes`）或转为 FlashCard

#### 3.4 跨材料参照提示

- 用户选中一段文本关联到知识点 X 时，系统检索该知识点的已有引用列表
- 检索复用 `MaterialChunk.embedding` 与知识点的相似度
- 若发现其他阅读材料中有对同一知识点的论述，在侧栏显示"其他材料引用"
- 点击跳转到对应材料的对应段落

### 4. 阅读笔记：复用 FlashCard 反思型

**关键决策**：**不**新建 `reading_notes` 表，笔记直接用 **FlashCard 反思型**实现。

#### 4.1 笔记到 FlashCard 的映射

| 笔记三段式 | 对应 FlashCard 字段 | 说明 |
|----------|------------------|------|
| 我的问题 | `front_text`（正面）| 开放式元认知问题 |
| 关键论述 | `back_context`（反面附加）| 关联的标注 / 原文引用 |
| 我的回应 | `back_text`（反面）| 用户的回答记录 |
| 关联材料 | `source_ref.material_id` | 来源材料 |
| 关联段落 | `source_ref.chunk_id_range` | 来源段落 |
| 关联知识点 | `linked_node_ids` | 与 FlashCard 一致 |

**`source` 字段**：`source='reading_note'`，区分于其他来源的 FlashCard。

#### 4.2 三段式笔记模板（可选）

| 区域 | 用途 |
|------|------|
| 我的问题 | 读前或读中产生的疑问 |
| 关键论述 | 作者的核心观点和论据，从标注中汇入 |
| 我的回应 | 同意/反对/补充/关联自己的经验 |

用户可用模板或纯自由笔记。模板只提供结构框架，不填充内容，**最终都生成一张 FlashCard**。

#### 4.3 双向绑定

- 笔记（即 FlashCard）的 `linked_node_ids` 关联到 `CognitiveNode`
- 知识点页面的"关联笔记"列表**复用 FlashCard 列表**，按 `source='reading_note'` 筛选
- 不需要单独的"笔记列表"UI

#### 4.4 笔记可提取为新 FlashCard

- 一张笔记（即 FlashCard）中的"我的回应"段落可选中，**再生成一张新 FlashCard**（如应用场景型）
- 调用 FlashCard 多源提取接口
- 自动携带：来源材料、来源 FlashCard（笔记本身）、关联知识点

#### 4.5 复用优势

- **纵向对比**：反思卡片的特殊功能"定期回顾对比回答变化"自动实现
- **统一复习入口**：笔记与其他 FlashCard 一起进入 FSRS 调度
- **避免双数据结构**：不新建 `reading_notes`，所有复习材料都在 `flashcards` 表
- **Belief 更新一致**：用户复习笔记时触发 `FlashCardReviewed` 事件，与 0002 设计一致

### 5. 阅读后的综合处理

#### 5.1 阅读收获面板

完成阅读后，系统汇总本次阅读会话的所有标注、笔记、提问、关联知识点，集中展示。用户可：

- 复查所有标注，删改无用的
- 将标注/笔记拖入"生成卡片"区域（批量调用 FlashCard 创建）
- 将标注/笔记拖入"更新知识点参考材料"区域
- 将笔记拖入"生成练习"区域（基于笔记内容生成自测题）

所有操作由用户手动执行，系统只汇总展示。

#### 5.2 阅读回顾提醒（复用 0006 Planning）

- 用户可设置"阅读后 N 天回顾"（默认 7 / 30 / 90 天）
- 到时**触发 0006 Planning 提醒**——在用户打开应用时显示
- 0006 触发 `PlanItemScheduled` 事件（`source_module='reading'`）
- 与 FSRS 无关：这是"重新打开材料"层面的回顾，FSRS 调度的是 FlashCard（包括阅读笔记）
- 用户可一键从提醒跳转到原材料的回顾面板
- **不**新建独立的提醒机制，复用 0006 调度

#### 5.3 阅读事件

触发 `ReadingSessionEnded` 事件，schema：

```python
class ReadingSessionEnded(DomainEvent):
    user_id: str
    material_id: str
    session_id: str
    duration_seconds: float
    annotations_count: int
    notes_count: int  # 创建的 FlashCard 反思型数量（source='reading_note'）
    cards_generated: int
    linked_node_ids: list[str]  # 关联/创建的 CognitiveNode (Task #58 后 DB/事件/Schema 命名统一)
    ended_at: datetime
```

**重要**：阅读事件**不**直接更新 `CognitiveNode.Belief`（避免阅读影响认知状态过强）。Belief 的更新只通过：
- 练习答题
- FlashCard 复习
- 诊断测试
- 对话深度参与

这样保持"状态变更来自主动行为"的设计原则。

### 6. 阅读策略支持

#### 6.1 可选阅读模式

- **精读模式**：边栏全展开，显示标注工具、知识点提示、笔记区
- **略读模式**：边栏最小化，只保留目录和简单划线
- **回顾模式**：只显示已有标注和笔记，隐藏正文其他内容

#### 6.2 阅读速度与进度统计

- 记录每章节的阅读用时，展示阅读速度趋势
- 统计全书预计完成时间（基于当前速度）
- 纯客观统计，不催促、不评价

### 7. 多材料对比阅读

- 用户可同时打开 2 篇独立材料，进入分屏对比模式
- 左右分屏，各自独立滚动但有联动选项（同步滚动开关）
- 标注自动带上材料来源标记（来自 `reading_annotations` 的 `material_id`）
- 对比标注可导出为对比表，存入项目模块或转为对比 FlashCard
- 适用：同主题不同作者观点对比、原始文献与译文对照

### 8. 阅读材料版本管理

- **同一材料的多个版本**（PDF 扫描+文字版、原文+译文）通过 `material.versions[]` 字段关联
- 标注和笔记按版本分组但可跨版本查看
- 适用：书籍多个译本、更新版本教材、整理前后笔记
- **与"对比阅读"的区别**：
  - 版本管理 = **同一材料**的多个副本（`material_id` 相同，`version_id` 不同）
  - 对比阅读 = **多个独立材料**的临时组合（`material_id` 不同）

### 9. 关键接口决策（10 个）

| 决策点 | 选择 | 理由 |
|--------|------|------|
| 1. 阅读模块与 file-management 的关系 | **A: 增强层** | 避免重复造轮子，专注于体验+加工 |
| 2. 章节模型 | 复用 TOC | file-management 已有完整实现 |
| 3. 段落锚点 ID | 复用 chunk_id | 不造平行 ID，保持单一数据源 |
| 4. 术语嗅探归属 | 知识图谱模块 | 术语识别依赖知识图谱标签/embedding 库 |
| 5. 知识点高亮匹配 | 混合（标签 + embedding）| 兼顾精度与召回 |
| 6. 标注数据存储 | 新表 reading_annotations | 查询性能 + 模块边界清晰 |
| 7. 笔记数据存储 | 新表 reading_notes | 结构化字段 + JSONB 富文本 |
| 8. 上下文提问 | 复用 ExplainCard | 已有完整机制 |
| 9. 回顾提醒与 FSRS 关系 | **独立**（不耦合）| 不同维度：重开材料 vs 卡片复习 |
| 10. 对比 vs 版本管理 | **清晰区分** | 同一材料多版本 vs 多独立材料组合 |

### 10. 系统边界

**阅读模块可做**：

- 章节展示、阅读模式切换
- 标注（5 颜色多意图）、笔记、图表索引
- 已有知识点高亮匹配
- 上下文对话（复用 ExplainCard）
- 对比阅读、版本管理
- 阅读收获面板、回顾提醒
- 复用 file-management 的存储/解析/索引能力
- 调用知识图谱的候选识别 API

**阅读模块不做**：

- 文件上传、格式解析、分块、向量化（file-management 负责）
- 自动摘要、自动提炼中心思想
- 自动推荐"应该重点读哪些部分"
- 自动创建知识点或卡片
- 自动判断内容"重要性"
- 根据阅读内容直接更新知识点 Belief（避免阅读影响认知状态过强）
- 自动评估或调整任何知识状态

## Consequences

### 正面

- 与 file-management 边界清晰：底层存储/解析/索引复用，上层专注体验和加工
- 通过混合匹配策略（标签 + embedding）实现高质量的已有知识点高亮
- 标注、笔记数据结构化（独立表 + JSONB），支持复杂查询和聚合
- 复用 ExplainCard 减少对话机制的重复实现
- 阅读事件不直接更新 Belief，保持"状态变更来自主动行为"原则
- 与 FlashCard、项目模块、规划模块形成完整加工闭环

### 负面

- 跨表（reading_annotations / reading_notes / reading_sessions）+ 跨模块（file-management / CognitiveNode / FlashCard / ExplainCard）查询复杂度高
- 混合匹配策略需要同时维护标签索引和 embedding 索引
- 5 种标注意图的"后续动作提示"是软引导，可能被用户忽略
- 阅读事件不更新 Belief 是设计选择，但也意味着用户读完书后看不到"进度变化"，可能需要补充心理反馈
- 对比阅读和版本管理是相对独立的功能，开发工作量不小

### 风险

- 跨模块 API（file-management / 知识图谱 / FlashCard）变更可能影响阅读模块
- 混合匹配的阈值需要用户配置，调参不当会高亮过多/过少
- 标注和笔记数据增长快，需要定期归档/清理策略
- 阅读会话状态在断网/刷新后的恢复机制需设计

## 附录：3 个压力测试场景

### 场景 A：纯阅读体验——精读一本专业教材

**用户行为**：用 2 周时间精读 500 页机器学习教材，过程中标注、记笔记、查询概念。

**流程**：

- 打开材料 → 精读模式 → 看到核心概念已自动高亮（混合匹配）
- 悬停"梯度下降"看到掌握度 0.6、关联卡片 3 张
- 标注一段复杂推导为紫色（疑问）→ 侧栏自动建议"发起对话讨论"
- 选中一段应用案例标为黄色（重要概念）→ 关联到"反向传播"知识点
- 暂停阅读 → 重新打开 → 自动恢复到上次位置和精读模式

**关键能力覆盖**：

- 章节展示与导航（复用 TOC）
- 混合匹配高亮（标签 + embedding）
- 5 颜色标注 + 侧栏结构化列表
- 复习会话状态恢复
- ExplainCard 上下文对话

### 场景 B：跨模块联动——精读中创建 FlashCard 和项目

**用户行为**：读《算法导论》某章节，对比阅读另一本教材的相关章节，把心得汇总到项目模块。

**流程**：

- 标注 3 个核心算法为黄色 → 批量生成 FlashCard（调用 FlashCard 多源提取）
- 对比模式：同时打开《算法导论》和另一本教材 → 同步滚动查看同一概念的不同讲法
- 标注对比差异为橙色（冲突）→ 跨材料参照提示列出所有相关材料
- 创建项目"算法学习" → 把对比表导出到项目聚合节点
- 阅读完成 → 触发 `ReadingSessionEnded` 事件
- 7 天后 → 回顾提醒排入规划模块日程
- 复习 FlashCard 自评"简单" → 事件回写 CognitiveNode.Belief

**关键能力覆盖**：

- 标注 → FlashCard 批量创建
- 对比阅读（双材料分屏 + 同步滚动）
- 跨材料参照提示
- 项目模块成果板导入
- 阅读事件 + 回顾提醒 + 规划模块日程
- FlashCard 复习事件回写 Belief（与阅读事件不更新 Belief 的对比）

### 场景 C：加工闭环——从阅读到长期记忆

**用户行为**：用户读一篇论文，目标是彻底掌握论文中提出的新算法。

**流程**：

1. **阅读阶段**：精读论文，标注关键公式为蓝色（数据），标注方法论为黄色（重要）
2. **加工阶段**：在笔记的"我的问题"区写下疑问，选中"我的回应"段落生成 FlashCard
3. **理解阶段**：用 ExplainCard 发起对话，询问公式推导细节
4. **应用阶段**：对话结果保存为笔记，笔记再次生成 FlashCard（应用场景型）
5. **复习阶段**：3 天后复习生成的 FlashCard（FSRS 调度）
6. **巩固阶段**：7 天后阅读回顾提醒触发，重新打开论文复习区
7. **更新阶段**：用户对算法有了新理解，标注新笔记"修正"已有知识点

**关键能力覆盖**：

- 标注、笔记、对话、卡片的全流程串联
- 同一知识点的多源数据（标注+笔记+对话+卡片）协同
- 阅读模块不更新 Belief，但通过 FlashCard 复习更新
- 回顾提醒与 FSRS 调度的协同（不同维度）
- 知识点的多源数据汇聚（按节点查看所有相关标注/笔记/卡片/对话）

---

## 层级概念图

```mermaid
graph TD
    Reading[Reading 阅读体验增强层] --> Session[ReadingSession 阅读会话]
    Reading --> Annot[ReadingAnnotation 标注]
    Reading --> NoteCard[FlashCard 反思型 笔记]
    Reading --> ExpCard[ExplainCard 上下文对话]
    Reading --> Mode[ReadingMode 3种模式]
    Reading --> Review[ReviewReminder 回顾提醒]
    Reading --> Harvest[HarvestPanel 收获面板]
    Reading --> Compare[CompareMode 对比阅读]
    Reading --> VerMgmt[VersionMgmt 版本管理]

    Session --> Status[started/paused/ended]
    Session --> Stat[阅读速度/进度统计]

    Annot --> Color[5 种颜色 yellow/blue/green/purple/orange]
    Annot --> Intent[5 种意图 important_concept/data_fact/quotable/doubt/conflict]
    Annot --> LinkedNode[linked_node_ids 关联知识点]
    Annot --> Offset[start_offset/end_offset 段落内偏移]

    NoteCard --> Front[front_text 我的问题]
    NoteCard --> Back[back_text 我的回应]
    NoteCard --> BackCtx[back_context 关键论述]
    NoteCard --> Src[source=reading_note cross_module_source=reading]

    ExpCard --> Mid[message_id 绑定]
    ExpCard --> Ctx[chunk 上下文]

    Mode --> Care[精读 边栏全展开]
    Mode --> Skip[略读 边栏最小化]
    Mode --> Recall[回顾 只看标注笔记]

    Review --> After[7/30/90 天 复用 0006 Planning]
    Review --> Event[ReadingReviewReminderScheduled 事件]

    Compare --> Split[分屏 + 同步滚动]
    Compare --> CrossAnnot[跨材料标注]

    VerMgmt --> MaterialVer[material.versions[] 同一材料多版本]
    VerMgmt --> VerGroup[标注/笔记按版本分组 可跨版本]
```

---

## 数据归属表

| 表/实体 | 主要字段 | 写入方 | 读取方 | 触发场景 |
|--------|---------|--------|--------|----------|
| `reading_sessions` | id, user_id, material_id, status, started_at, ended_at, mode | api/reading/routes.py | api/reading/session + reading/dashboard | 用户开始/恢复/结束阅读 |
| `reading_annotations` | id, user_id, material_id, chunk_id, start_offset, end_offset, color, intent, note, linked_node_ids | api/reading/annotations.py | api/reading/sidebar + 跨材料参照 + 收获面板 | 用户划线/批注 |
| `reading_notes` (复用 flashcards) | flashcard 反思型, source=reading_note, cross_module_source=reading | api/reading/notes.py → api/flashcard | api/reading + api/flashcard 复习入口 + KG 关联 | 用户写笔记（三段式）|
| `reading_explain_cards` (复用 explain_cards) | message_id, chunk_id, selected_text | api/reading/ask.py → conversation-system | api/conversation 上下文 | 选中提问 |
| `reading_events` | 10 个 Reading* 事件 (SessionStarted/SessionEnded/AnnotationCreated/AnnotationUpdated/AnnotationDeleted/AnnotationProcessed/ModeChanged/NoteCreated/ReviewReminderScheduled/...) | services/reading/event_emitter.py | 全局事件流 + 0002 FlashCard + 0006 Planning + 0001 Project 消费者 | 阅读会话/标注/笔记/回顾 |
| `reading_compare_sessions` | id, user_id, material_id_a, material_id_b, sync_scroll | api/reading/compare.py | api/reading/compare + 导出对比表 | 用户开启对比阅读 |
| `reading_version_annotations` | annotation_id, material_id, version_id | api/reading/versions.py | api/reading/version_view | 用户在多版本材料上标注 |
