# Task 0015: 苹果果全系统目标架构愿景 v1.0

> 起草 Agent：AP007
> 起草时间：2026-07-11
> 依赖：ADR 0013（战略共识与蓝图 v3.1）、ADR 0014（完美执行协议）、ADR 0015（认知概率图）、Task 0014（事件协议设计）
> 状态：已确认（含 AP008 反馈目标吸收）
> 确认时间：2026-07-11
> 用户决策：
>   1. 本文档作为后续实现的唯一北极星。
>   2. 接受 Phase 1-10 顺序。
>   3. **完全舍弃旧 API**，不保留兼容层。
>   4. **AP008 已改动的读取侧代码废弃重写**，由 AP007 统一负责。
>   5. **AP008 的设计目标已吸收**：答题后信息增益反馈、`GET /feedback/{attempt_id}`、考试模式差异反馈由 AP007 在 Phase 2-6 统一实现。

---

## 一、目标系统总览

苹果果重构后的最终形态是：**个人认知操作系统（Cognitive OS）+ 场景壳（Scene Shells）**。

- **内核** 只负责三件事：记录学习事实事件、维护认知状态投影、编排跨模块提案与计划。
- **场景壳** 是用户能直接感知的模块：对话、练习、闪卡、阅读、规划、知识树。它们不维护独立的「业务状态」，只通过事件与内核交互，并从投影读取只读视图。
- **秘书系统** 不是聊天机器人，而是内核中的「学习编排器」：读事件流、评估状态、生成提案、推动计划、为对话注入上下文。

一句话：**所有学习行为只产生事件；所有业务状态都从事件派生；所有模块通过统一协议联动。**

---

## 二、核心架构：认知 OS 内核 + 场景壳

```
┌─────────────────────────────────────────────────────────────────┐
│                        场景壳（Scene Shells）                    │
│  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌───────────┐ │
│  │  对话壳  │ │  练习壳  │ │  闪卡壳  │ │  阅读壳  │ │  规划壳    │ │
│  │Conversation│ │Practice │ │Flashcard│ │Reading  │ │Planning   │ │
│  └────┬────┘ └────┬────┘ └────┬────┘ └────┬────┘ └─────┬─────┘ │
│       │           │           │           │             │       │
│       └───────────┴───────────┴───────────┴─────────────┘       │
│                           │                                      │
│                    统一事件协议（shared/events.py）                │
└───────────────────────────┬──────────────────────────────────────┘
                            │
┌───────────────────────────▼──────────────────────────────────────┐
│                      认知 OS 内核（Cognitive OS Kernel）          │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐  │
│  │   事件总线       │  │   认知状态中心   │  │   秘书编排器     │  │
│  │ PersistentEvent │  │ Cognitive Center│  │  Secretary      │  │
│  │    Bus          │  │                 │  │  Orchestrator   │  │
│  └────────┬────────┘  └────────┬────────┘  └────────┬────────┘  │
│           │                    │                    │           │
│           │           ┌────────▼────────┐           │           │
│           │           │  投影构建器      │           │           │
│           │           │ProjectionBuilder│           │           │
│           │           └────────┬────────┘           │           │
│           │                    │                    │           │
│           └────────────────────┼────────────────────┘           │
│                                │                                 │
│                    ┌───────────▼────────────┐                   │
│                    │   认知节点数据系统      │                   │
│                    │  knowledge_nodes /     │                   │
│                    │  knowledge_edges /     │                   │
│                    │  cognitive_node_       │                   │
│                    │  projections           │                   │
│                    └────────────────────────┘                   │
└─────────────────────────────────────────────────────────────────┘
```

### 2.1 内核三大子系统

| 子系统 | 职责 | 禁止做的事 |
|--------|------|-----------|
| **事件总线** | 接收、持久化、分发领域事件；保证事件不丢失；支持事件回放 | 不解释事件语义，不执行业务逻辑 |
| **认知状态中心** | 订阅学习事实事件，更新 `knowledge_nodes` 与 `cognitive_node_projections`；发布 `CognitiveStateChanged` | 不直接调用场景壳 API，不生成用户文案 |
| **秘书编排器** | 订阅 `CognitiveStateChanged` 与其他行为事件；维护信任积分、情绪状态、策略画像；生成 `ProposalGenerated` 与计划请求 | 不直接修改认知投影，只通过事件建议 |

### 2.2 场景壳通用契约

每个场景壳必须遵守：

1. **写操作只产生事件**：练习壳产生 `AnswerSubmitted`，闪卡壳产生 `FlashCardReviewed`，对话壳产生 `MessageClassified`/`AssistantReplied` 等。
2. **读操作只查投影**：不直接读其他壳的私有表，只读内核暴露的投影视图。
3. **不维护跨模块状态**：例如练习壳不能自己维护「掌握度」，必须从认知投影读取。
4. **响应秘书提案**：通过 `ProposalAccepted`/`ProposalDismissed` 事件与秘书系统协作。

---

## 三、认知原子模型（Cognitive Atom）

苹果果里所有学习内容最终都落在 **认知节点（Cognitive Node / Knowledge Node）** 上。它是系统的最小不可分认知单位。

### 3.1 节点本体

| 字段 | 说明 |
|------|------|
| `id` | 节点唯一 ID |
| `label` | 节点名称（如「贝叶斯定理」） |
| `level` | 层级：domain / topic / atom（原子） |
| `parent_id` | 父节点，构成层级树 |
| `node_type` | explicit（用户创建）/ inferred（系统推断）/ imported（外部导入） |
| `brief` / `emoji` / `color` / `tags` | 展示与组织元数据 |
| `embedding` | 语义向量，用于相似度、扭曲度计算 |
| `metadata.anchors` | 外部锚点（Notion Page ID、B站 BV 号等） |

### 3.2 节点投影（只读，从事件重建）

`cognitive_node_projections` 是节点的「实时状态仪表板」：

| 字段 | 语义 |
|------|------|
| `proficiency` | 掌握度 `α / (α + β)`，[0, 1] |
| `uncertainty` | Beta 分布熵，表达不确定性 |
| `belief_alpha` / `belief_beta` | 后验分布参数 |
| `urgency` | 复习紧迫度 |
| `stagnation_days` | 停滞天数 |
| `next_review_at` | 下次复习时间 |
| `next_action_type` | 推荐下一步：review / practice / explore / deep_processing / idle |
| `last_event_id` | 最后更新本投影的事件 ID |

### 3.3 节点关联边

`knowledge_edges` 表达节点间关系：

| 边类型 | 含义 |
|--------|------|
| `prerequisite` | 前置依赖 |
| `related` | 相关 |
| `chunk` | 组块关系 |
| `cooccurrence` | 练习共现 |
| `imported_from` | 外部导入来源 |

边的 `strength` 与 `max_propagation_hops` 控制信念传播范围（ADR 0015）。

### 3.4 统一认知原子的落地规则

1. **闪卡 = 节点的学习材料视图**：一张闪卡必须关联至少一个节点，修改闪卡内容同步到节点材料池。
2. **错题 = 节点上的失败证据**：错题本记录来自 `ErrorRecorded` 事件，归属到对应节点。
3. **对话笔记 = 节点材料**：对话中产生的笔记可一键转为闪卡或节点 brief，修改时同步。
4. **题目 = 节点的探测工具**：每道题关联 `cognitive_node_ids`，答题结果用于更新节点信念。
5. **计划项 = 节点的行动建议**：plan item 通过 `linked_node_ids` 关联节点，完成后产生 `PlanItemCompleted` 事件回写认知状态。

---

## 四、事件协议全景

### 4.1 事件分层

```
事实事件（Fact Events）        → 用户/系统行为，不可变
  ├── AnswerSubmitted
  ├── FlashCardReviewed
  ├── MessageClassified
  ├── AssistantReplied
  ├── PlanItemCompleted
  ├── ReadingNoteCreated
  └── ...

派生事件（Derived Events）      → 内核消费事实事件后产生
  ├── CognitiveStateChanged
  ├── CognitiveNodeMetadataChanged
  ├── CognitiveNodeLinked
  └── CognitiveReward            # 练习事件处理完成后写入的只读审计事件，幂等键 cr_{practice_event_id}_{node_id}

提案事件（Proposal Events）     → 秘书系统产生
  ├── ProposalGenerated
  ├── ProposalAccepted
  └── ProposalDismissed

计划事件（Plan Events）         → 规划系统产生
  ├── PlanItemCreated
  ├── PlanItemUpdated
  ├── PlanItemScheduled
  └── PlanGoalProgressUpdated
```

### 4.2 核心事件链路示例

**链路 1：练习 → 认知 → 秘书 → 规划**

```
用户提交答案
  ↓
AnswerSubmitted (practice)
  ↓
CognitiveEventHandler → 更新 projection
  ↓
CognitiveStateChanged (cognitive)
  ↓
SecretaryEventHandler → 评估状态 → 生成 ProposalGenerated
  ↓
用户接受提案
  ↓
ProposalAccepted (frontend/secretary)
  ↓
PlanningEventHandler → PlanItemCreated (planning)
  ↓
用户完成 plan item
  ↓
PlanItemCompleted (planning)
  ↓
CognitiveEventHandler → 再次更新 projection
```

**链路 2：对话 → 出题 → 认知 → 闪卡**

```
对话中用户表达困惑
  ↓
AssistantReplied + MessageClassified
  ↓
秘书识别薄弱节点 → ProposalGenerated(practice)
  ↓
对话壳在会话内直接出题（调用练习壳组题接口）
  ↓
用户答题 → AnswerSubmitted
  ↓
CognitiveStateChanged
  ↓
秘书判断应制卡 → ProposalGenerated(flashcard)
  ↓
用户接受 → FlashCardCreated（关联同一节点）
```

### 4.3 事件基类约定

所有事件必须携带（已实现于 `DomainEvent`）：

- `event_id`：唯一 ID
- `occurred_at`：业务发生时间
- `source_id`：业务来源 ID
- `correlation_id`：请求/会话追踪 ID
- `caused_by_event_id`：因果链上一事件 ID（防循环）

跨模块字段使用统一枚举：
- `CrossModuleTarget`：target_module 合法值
- `PlanningSourceModule`：plan item source_module 合法值

---

## 五、各场景壳的目标形态

### 5.1 对话壳（Conversation Shell）

**核心定位**：用户与认知系统的自然语言入口，也是秘书系统最重要的上下文来源。

**目标能力**：
- **认知感知**：回复时能看到用户当前薄弱节点、最近错题、进行中的计划。
- **内联练习**：在对话流中直接出题，题目保留对话上下文（不再丢失信息）。
- **笔记即闪卡**：对话中的笔记可一键生成闪卡，后续在闪卡壳修改会同步回对话历史中的同一则材料。
- **主动追问**：基于苏格拉底追问策略，在合适时机提出反问题。
- **提案接入**：在对话界面展示秘书提案，接受后可在对话内直接执行。

**关键事件**：
- 产生：`AssistantReplied`, `MessageClassified`, `UserMessageSent`
- 消费：`CognitiveStateChanged`, `ProposalGenerated`

### 5.2 练习壳（Practice Shell）

**核心定位**：探测认知状态的「探针」，只负责出题、收答案、记录事实。

**目标能力**：
- **单事件源**：一次答题只发布 `AnswerSubmitted` 事件。
- **组题接口**：支持按节点、按薄弱点、按对话上下文组题。
- **基础反馈同步返回**：is_correct / correct_answer / explanation / attempt_id。
- **完整反馈异步拉取**：`GET /feedback/{attempt_id}` 返回信息增益、元认知建议、相关节点状态。
- **信息增益可视化**：当 `uncertainty_reduction_percent ≥ 15%` 时，反馈面板展示自然语言文案（如「这次答题大幅降低了你对 XX 的不确定性」）；低于阈值则展示常规鼓励文案。
- **模式差异反馈**：普通练习模式展示完整信息增益与元认知建议；考试/测评模式仅展示「正确/错误 + 分数」，不展示信息增益文案，避免干扰。
- **错题归属**：错题自动关联到 `cognitive_node_ids`。

**关键事件**：
- 产生：`AnswerSubmitted`, `ErrorRecorded`, `SessionCompleted`
- 消费：`CognitiveStateChanged`（用于组题时的难度自适应）

### 5.3 闪卡壳（Flashcard Shell）

**核心定位**：节点的复习材料视图，与对话笔记、错题本共享同一认知原子。

**目标能力**：
- **一卡一节点或多节点**：`linked_node_ids` + `node_link_roles`（primary/secondary）。
- **来源透明**：可来自手动创建、错题、阅读笔记、对话笔记、项目节点。
- **复习驱动信念**：`FlashCardReviewed` 事件对关联节点做贝叶斯小贡献。
- **FSRS 自研调度**：开源 `py-fsrs` 计算稳定性，苹果果自研参数注入（认知负荷、情绪）。

**关键事件**：
- 产生：`FlashCardCreated`, `FlashCardReviewed`, `FlashCardUpdated`, `FlashCardSuspended`
- 消费：`CognitiveStateChanged`（用于推荐复习队列）

### 5.4 阅读壳（Reading Shell）

**核心定位**：文件管理与阅读体验层，产出高亮、笔记、批注等材料。

**目标能力**：
- **文件是材料容器**：PDF/文章/视频导入后，高亮和笔记关联到认知节点。
- **笔记即节点材料**：阅读笔记可一键创建/关联节点，与闪卡、对话笔记打通。
- **阅读事件入流**：`ReadingNoteCreated`, `MaterialProgressUpdated` 进入事件总线。

**关键事件**：
- 产生：`ReadingNoteCreated`, `MaterialProgressUpdated`
- 消费：`ProposalGenerated`（如「把这段高亮做成闪卡」）

### 5.5 规划壳（Planning Shell）

**核心定位**：把秘书的提案和认知状态转化为可执行的计划项。

**目标能力**：
- **主动生成 plan items**：秘书基于 `CognitiveStateChanged` 请求规划系统生成计划。
- **去重与合并**：同一节点的多个提案合并为一个 plan item，避免重复。
- **完成回写认知**：`PlanItemCompleted` 触发认知中心更新节点信念。
- **今日引力种子**：首页展示由认知紧迫度、目标关键路径、情绪状态综合计算的 Top-K 起点。

**关键事件**：
- 产生：`PlanItemCreated`, `PlanItemUpdated`, `PlanItemScheduled`, `PlanItemCompleted`
- 消费：`ProposalAccepted`, `CognitiveStateChanged`

### 5.6 知识树壳（Knowledge Tree Shell）

**核心定位**：用户创作的知识组织 + 认知数据的一体化视图。

**目标能力**：
- **双重视角**：树的一边是用户手动组织的项目/内容结构，另一边是认知节点数据（掌握度、不确定性、行动建议）。
- **美观现代的前端**：告别旧版力导向图的粗糙交互，支持缩放、筛选、拖拽、聚焦。
- **节点状态可视化**：颜色/大小反映掌握度和紧迫度。
- **直接操作**：在树上创建节点、关联材料、发起练习、生成计划。

**关键约束**：
- 知识图谱的边（用户创作）与认知数据系统的边（推断/确认的认知关系）**独立维护**。
- 认知数据系统的图结构来自节点层级、练习共现、AI 依赖分析、组块形成和用户确认的认知关系。

---

## 六、秘书系统定位：学习编排器

### 6.1 秘书不是聊天机器人

| 旧认知 | 新定位 |
|--------|--------|
| 回答用户问题 | 读事件流，评估状态，主动生成提案 |
| 独立维护一套推荐规则 | 通过事件与认知中心、规划系统协作 |
| 直接调用认知仓库 | 只发布事件，不直接写认知状态 |

### 6.2 秘书维护的状态变量

| 状态 | 来源 | 用途 |
|------|------|------|
| 信任积分（Trust Score） | 用户接受/忽略/反馈提案 | 控制推送胆量 |
| 情绪状态 | 情绪记录事件 | 调整推荐难度与频率 |
| 用户策略画像 | 事件流特征提取 | 元学习周报、个性化推荐 |
| 干预历史 | 已发送提案与结果 | 避免重复打扰 |

### 6.3 秘书输出

1. **提案（Proposal）**：跨模块行动建议，如「复习节点 A」「把对话笔记做成闪卡」「开始一次薄弱点练习」。
2. **计划请求**：请求规划系统生成/更新 plan items。
3. **对话上下文注入**：为对话壳提供「用户当前最需要的回应策略」。
4. **元学习周报**：每周基于事件流生成自然语言复盘。

---

## 七、数据流原则

### 7.1 写方向：单向上游

```
场景壳 → 事件总线 → 认知中心/秘书 → 投影/提案/计划
```

- 任何学习行为只产生事件。
- 认知中心订阅事件并更新投影。
- 秘书订阅事件并生成提案。
- 规划系统订阅提案接受事件并生成计划。

### 7.2 读方向：只读投影

```
场景壳 ← 投影视图 ← 认知中心
```

- 练习壳组题时读 `cognitive_node_projections`。
- 规划壳生成今日种子时读投影。
- 知识树壳展示节点状态时读投影。
- 对话壳回复前读投影和秘书上下文。

### 7.3 禁止的双向数据流

- 场景壳直接调用认知仓库更新状态。
- 秘书直接修改 `cognitive_node_projections`。
- 规划系统直接修改节点信念。
- 一个模块直接读另一个模块的私有表。

---

## 八、重构路线（调整后）

基于用户决定「AP007 单独负责全项目底层重构」，将原计划扩展为覆盖全系统的 10 个 Phase。每个 Phase 为 2-4 小时的垂直切片，含明确输入、输出、验收条件。

| Phase | 主题 | 输入 | 输出 | 验收条件 |
|-------|------|------|------|----------|
| 1 | 事件协议与 Schema | ADR 0013/0014/0015 | `shared/events.py` 新协议 | 事件可序列化/重建；contract tests 通过 |
| 2 | 练习模块单事件源 | Phase 1 协议 | `PracticeEngine` + 路由委托 | 答题只发 `AnswerSubmitted`；`POST /submit` 返回 `attempt_id`；无双路径更新 |
| 3 | 认知中心事件消费 | Phase 2 事件 | `CognitiveEventHandler` 订阅 `AnswerSubmitted` | 投影正确更新；发布 `CognitiveStateChanged`；写入 `CognitiveReward` 审计事件 |
| 4 | 秘书系统增强 | Phase 3 派生事件 | 秘书订阅 `CognitiveStateChanged`；生成提案 | 答题后秘书产生合理提案 |
| 5 | 规划系统主动生成 | Phase 4 提案 | `PlanItemCreated` 由提案触发 | 接受提案后生成 plan item |
| 6 | 前端提案、计划与反馈展示 | Phase 5 后端 | ProposalCard / PlanItemList / FeedbackPanel | 用户可接受/忽略/完成提案；`GET /feedback/{attempt_id}` 返回信息增益与元认知建议 |
| 7 | 闪卡与错题联动 | Phase 3 投影 | 错题可一键制卡；复习事件回写节点 | 闪卡复习影响节点信念 |
| 8 | 对话壳认知感知 | Phase 3-7 完成 | 对话可见节点状态；内联出题保留上下文 | 对话出题携带上下文 |
| 9 | 知识树壳升级 | Phase 3-8 完成 | 合并认知数据与知识树的前端 | 节点状态可视化；操作流畅 |
| 10 | 数据库迁移、集成测试、文档归档 | 前述所有 | Alembic 迁移；`rebuild.sh` 通过；ADR 更新 | 端到端验证通过；git 提交 |

---

## 九、验收标准

### 9.1 每个 Phase 的通用验收

1. **单元测试**：新增/修改的函数有对应测试。
2. **集成测试**：模块间事件链路可通过测试验证。
3. **端到端测试**：`rebuild.sh` 启动前后端，走通用户路径。
4. **回归测试**：不破坏现有独立功能（如闪卡 FSRS、阅读批注）。

### 9.2 全系统最终验收（用户可感知）

| 用户痛点 | 验收标准 |
|----------|----------|
| 对话体验割裂、不智能 | 对话能基于认知状态主动追问、内联出题、推荐复习 |
| 出题不方便且丢失信息 | 对话内出题保留上下文；组题可按节点/薄弱点/对话主题 |
| 练习反馈无价值感 | 答题后反馈面板展示信息增益文案；考试模式不展示冗余信息 |
| 闪卡制作不便 | 错题、对话笔记、阅读笔记可一键制卡；双端修改同步 |
| 规划系统不好用 | 秘书主动生成 plan items；完成计划回写认知状态 |
| 无法查看认知节点数据 | 知识树壳展示掌握度、不确定性、下次行动 |
| 知识图谱前端落后 | 新前端支持缩放/筛选/拖拽/聚焦，美观现代 |
| 秘书不够智能 | 秘书基于事件流生成个性化提案，而非固定规则 |
| 模块联动不足 | 一个模块的行为能在其他模块实时反映 |

---

## 十、风险与成功条件

### 10.1 主要风险

| 风险 | 影响 | 缓解措施 |
|------|------|----------|
| 一次改太多模块 | 回归不可控 | 严格按 Phase 推进，每 Phase 验收后再进入下一 Phase |
| 事件协议不稳定 | 各模块语义分裂 | Phase 1 先固化协议；后续只追加不破坏 |
| 旧代码残留双路径更新 | 状态不一致 | 每改一个模块，彻底移除旧直接调用 |
| 前端改动过大 | 体验断层 | 按壳逐步替换，先保证旧功能可用 |
| 性能问题 | 事件流处理延迟 | 同步更新用户-facing 投影；异步处理图传播与秘书洞察 |

### 10.2 成功条件

1. 任何学习行为都能追溯到唯一事件。
2. 任何业务状态都能从事件流重建。
3. 模块间不直接读写对方私有状态。
4. 秘书系统能基于真实认知状态生成提案。
5. 用户能在知识树中看到自己的认知数据。
6. 对话、练习、闪卡、阅读、规划之间的数据是连贯的。

---

## 十一、与现有文档的关系

| 文档 | 关系 |
|------|------|
| `docs/adr/0013-redirect.md` | 战略蓝图，本文档在此基础上细化架构与实施路线 |
| `docs/adr/0014-perfect-execution-protocol.md` | 执行纪律，每个 Phase 必须遵守 |
| `docs/adr/0015-cognitive-probabilistic-graph.md` | 认知模型数学基础，投影构建器实现依据 |
| `docs/temp/task0014-event-protocol-design.md` | Phase 1 详细设计，已部分完成 |
| `docs/temp/task0013-practice-module-refactor-design.md` | 练习模块重构方案，Phase 2 参考 |
| `docs/temp/task0013-info-gain-feedback-design.md` | AP008 原设计的信息增益反馈方案；其目标已吸收进本文档 5.2 / Phase 2-6，具体实现由 AP007 按新架构统一重写，原读取侧服务/接口代码废弃 |
| 本文档 | 全系统目标架构与实施路线图，经用户确认后作为后续所有实现的北极星 |

---

## 十二、关键决策记录

| # | 决策项 | 决策结果 | 影响 |
|---|--------|----------|------|
| 1 | 本架构是否作为后续实现的唯一北极星？ | **是** | 所有后续实现以本文档为准，旧设计文档仅作参考。 |
| 2 | Phase 顺序是否接受？ | **接受 1-10 顺序** | 按表格顺序推进，每 Phase 验收后再进入下一阶段。 |
| 3 | 旧 API 处理策略？ | **完全舍弃旧 API** | 不保留兼容层，新前端与后端按新协议实现。 |
| 4 | AP008 已改代码处理？ | **废弃重写** | AP008 的 FeedbackService / FeedbackBuilder 等读取侧增量由 AP007 统一重写，其设计目标（信息增益反馈、GET /feedback/{attempt_id}）已吸收进本文档 5.2 与 Phase 6。 |
| 5 | 知识树壳的新前端是否有明确视觉参考？ | **待定** | AP007 将在 Phase 9 前提供 UI 方案供确认。 |

---

> AP007：「这是苹果果全系统重构后的目标图景，已吸收 AP008 的反馈设计目标。确认后，我将从 Phase 3（认知中心事件消费）开始，按此架构逐步落地。」
