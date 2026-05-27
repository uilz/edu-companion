# 智能伴学系统架构文档 v4.0

> 版本: v4.0
> 最后更新: 2026-05-27
> 状态: ✅ 全部 16 个 Phase 已交付

---

## 一、项目概述

智能伴学系统（edu-companion）是一个基于 AI 的全栈学习伴侣平台，提供自适应学习规划、精准答疑、多模态交互、学情追踪、心理陪伴等功能。

### 技术栈

| 层级 | 技术 | 说明 |
|------|------|------|
| 前端 | Next.js 14 + shadcn/ui + Tailwind CSS | SSR/CSR 混合，CSS Variables 主题切换 |
| 后端 | Python FastAPI | 异步高性能，OpenAPI 自动文档 |
| 数据库 | PostgreSQL 14+ + pgvector | JSONB 灵活存储 + 向量检索 |
| LLM | OpenAI 兼容 API | 通过 .env 配置模型名，禁止硬编码 |
| 存储 | PG 主存 + JSON 备降 | `USE_PG_STORAGE=true` 默认开启 |
| 部署 | Docker + Nginx | 双容器部署，前端 standalone 模式 |

---

## 二、系统架构

```
┌─────────────────────────────────────────────────────────────────┐
│                        前端 (Next.js 14)                        │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐          │
│  │ 对话页   │ │ 练习页   │ │ 仪表盘   │ │ 秘书页   │          │
│  └────┬─────┘ └────┬─────┘ └────┬─────┘ └────┬─────┘          │
│       │            │            │            │                  │
│  ┌────┴────────────┴────────────┴────────────┴────┐            │
│  │              API Layer (lib/api.ts)             │            │
│  └────────────────────────┬───────────────────────┘            │
└───────────────────────────┼────────────────────────────────────┘
                            │ HTTP/WebSocket
┌───────────────────────────┼────────────────────────────────────┐
│                        后端 (FastAPI)                           │
│  ┌────────────────────────┴───────────────────────┐            │
│  │              API Router (17 模块)               │            │
│  └────┬────────────┬────────────┬────────────┬────┘            │
│       │            │            │            │                  │
│  ┌────┴────┐ ┌─────┴────┐ ┌────┴────┐ ┌────┴────┐            │
│  │ 对话层  │ │ 练习层   │ │ 秘书层  │ │ 图谱层  │            │
│  └────┬────┘ └─────┬────┘ └────┬────┘ └────┬────┘            │
│       │            │            │            │                  │
│  ┌────┴────────────┴────────────┴────────────┴────┐            │
│  │           Service Layer (35+ 服务)              │            │
│  └────┬────────────┬────────────┬────────────┬────┘            │
│       │            │            │            │                  │
│  ┌────┴────┐ ┌─────┴────┐ ┌────┴────┐ ┌────┴────┐            │
│  │ LLM    │ │ 认知引擎 │ │ 事件总线│ │ 存储层  │            │
│  └────────┘ └──────────┘ └─────────┘ └────┬────┘            │
└────────────────────────────────────────────┼──────────────────┘
                                             │
┌────────────────────────────────────────────┼──────────────────┐
│                    数据层 (PostgreSQL)       │                  │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌─┴────────┐        │
│  │cognitive │ │conversation│ │practice │ │ secretary│        │
│  │_nodes    │ │_*         │ │_*        │ │ _*       │        │
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘        │
└──────────────────────────────────────────────────────────────┘
```

---

## 三、核心实体：CognitiveNode

系统中所有知识点的统一表征。图谱是它的投影，练习是它的更新事件，对话是它的上下文引用。

```python
class CognitiveNode(BaseModel):
    # ── 身份 ──
    id: str                    # "calc-derivatives"
    label: str                 # "导数"
    level: str                 # "partition" | "domain" | "topic" | "concept" | "atom"
    parent: str | None         # 父节点 ID
    is_core: bool = False      # 核心知识点

    # ── 15 个认知子系统 ──
    activation: Activation              # ACT-R 激活 + 扩散
    belief: Belief                      # Beta(α,β) 掌握度信念
    prediction: Prediction | None       # 作答预测
    cognitive_load: CognitiveLoad       # 认知负荷
    scheduling: Scheduling              # 复习调度
    dialogue_contexts: list[DialogueContext]  # 对话上下文
    metacognition: Metacognition | None # 自评校准
    engagement: Engagement | None       # 投入度
    composition: Composition | None     # 组合结构
    deep_processing: DeepProcessing | None  # 深度处理
    deep_links: list[DeepLink]          # 深层链接
    goal_alignment: GoalAlignment | None    # 目标对齐
    diagnostic: Diagnostic | None       # 诊断结果
    practice_summary: PracticeSummary   # 练习统计
    learning_trend: Trend               # 趋势
    error_clusters: list[ErrorCluster]  # 错误簇

    # ── 图谱关系 ──
    prerequisites: list[Prerequisite]   # 前置依赖
    unlocks: list[Unlock]               # 解锁知识
    associates: list[Associate]         # 关联知识

    # ── Phase 8 扩展 ──
    path_id: str | None                 # 层级路径
    node_type: str = "explicit"         # 节点类型
    is_visible: bool = False            # 前端展示
    embedding: list[float] | None       # 语义向量
```

---

## 四、三层架构

```
┌──────────────────────────────────────────────────────────────┐
│ ③ 决策层：秘书系统 + 分类器 + 创造扩展                       │
│   "现在推什么？归到哪里？怎么拓展？"                           │
│                                                              │
│   ├─ 诊断引擎 DiagnosisEngine           (Phase 7)           │
│   ├─ 提案生成器 ProposalGenerator        (Phase 7)           │
│   ├─ 策略引擎 PolicyEngine              (Phase 7)           │
│   ├─ 7 内置模块                         (Phase 7)           │
│   ├─ Phase8 向量分类器 (3 模式决策)      (Phase 8)           │
│   ├─ 知识拓展 KnowledgeExpander         (Phase 14)          │
│   └─ 情绪分析 EmotionAnalyzer           (Phase 14)          │
└───────────────────────────┬──────────────────────────────────┘
                            │
┌───────────────────────────┴──────────────────────────────────┐
│ ② 画像层：CognitiveNode + PartitionProgress                  │
│   "学得到底怎么样了？" — 多维学习画像                         │
│                                                              │
│   ├─ CognitiveNode 统一实体 (30 模型, 15 子系统)             │
│   ├─ PartitionProgress API (画像计算 + 缓存)                 │
│   ├─ 间隔重复 SpacedRepetition (SM-2)       (Phase 10)      │
│   ├─ 自适应选题 AdaptiveSelector            (Phase 10)      │
│   ├─ 行为分析 BehaviorAnalyzer              (Phase 14)      │
│   └─ 习惯养成 HabitFormation                (Phase 14)      │
└───────────────────────────┬──────────────────────────────────┘
                            │
┌───────────────────────────┴──────────────────────────────────┐
│ ① 事件层：LearningEvents + CognitiveEvents                   │
│   对话消息 / 练习提交 / 心情标记 / 学习时长 / 错题           │
│                                                              │
│   ├─ record_event() → UserData.event_log                     │
│   ├─ practice_submit → submit_practice() → CognitiveNode     │
│   └─ 13 种学习事件类型                                       │
└──────────────────────────────────────────────────────────────┘
```

---

## 五、API 端点清单

### 对话系统

| 方法 | 路径 | 功能 |
|------|------|------|
| WS | `/api/chat/ws` | WebSocket 实时聊天 |
| POST | `/api/chat/api/chat` | HTTP 聊天 |
| GET | `/api/conversations/tree/{level}` | 获取树节点 |
| POST | `/api/conversations/tree/{level}` | 创建树节点 |
| PATCH | `/api/conversations/tree/{level}/{node_id}` | 更新节点 |
| DELETE | `/api/conversations/tree/{level}/{node_id}` | 删除节点 |
| GET | `/api/conversations/tree/conversation/{conv_id}/messages` | 获取消息 |
| POST | `/api/conversations/tree/conversation/{conv_id}/message` | 发送消息 |
| POST | `/api/conversations/tree/conversation/{conv_id}/switch` | 切换分支 |

### 练习系统

| 方法 | 路径 | 功能 |
|------|------|------|
| POST | `/api/practice/questions/generate` | 生成题目 |
| GET | `/api/practice/questions` | 获取题目列表 |
| POST | `/api/practice/sessions` | 创建练习会话 |
| POST | `/api/practice/sessions/{id}/complete` | 完成会话 |
| POST | `/api/practice/submit` | 提交答案 |
| POST | `/api/practice/hint` | 获取提示 |
| POST | `/api/practice/inline/answer` | 内联答题 |

### 错题与质量

| 方法 | 路径 | 功能 |
|------|------|------|
| GET | `/api/practice/errors` | 错题列表 |
| POST | `/api/practice/errors/{id}/review` | 复习错题 |
| GET | `/api/practice/errors/due` | 待复习错题 |
| GET | `/api/practice/quality` | 质量分析 |
| GET | `/api/practice/quality/worst` | 最差题目 |
| GET | `/api/practice/quality/detail/{id}` | 题目详情 |

### 知识图谱

| 方法 | 路径 | 功能 |
|------|------|------|
| GET | `/api/knowledge/graph` | 知识图谱 |
| GET | `/api/knowledge/prerequisites` | 前置检查 |
| GET | `/api/knowledge/ready` | 可学习节点 |
| GET | `/api/knowledge/retention` | 遗忘曲线 |
| GET | `/api/v2/graph/nodes` | Phase8 图节点 |
| GET | `/api/v2/graph/search` | 图谱搜索 |
| POST | `/api/v2/classify` | 消息分类 |

### 学习计划与进度

| 方法 | 路径 | 功能 |
|------|------|------|
| POST | `/api/study/plan/generate` | 生成计划 |
| GET | `/api/study/plan/{user_id}` | 获取计划 |
| PUT | `/api/study/plan/{user_id}/{task_id}/complete` | 完成任务 |
| GET | `/api/progress/{user_id}` | 学习进度 |
| GET | `/api/progress/{user_id}/stats` | 统计数据 |
| GET | `/api/progress/{user_id}/calendar` | 学习日历 |

### 秘书系统

| 方法 | 路径 | 功能 |
|------|------|------|
| GET | `/api/secretary/snapshot` | 实时快照 |
| GET | `/api/secretary/daily-brief` | 每日简报 |
| POST | `/api/secretary/diagnose` | 诊断 |
| POST | `/api/secretary/suggest` | 生成提案 |
| GET | `/api/secretary/proposals/pending` | 待处理提案 |
| POST | `/api/secretary/proposals/{id}/accept` | 采纳提案 |
| GET | `/api/secretary/preferences` | 偏好设置 |

### 多模态

| 方法 | 路径 | 功能 |
|------|------|------|
| POST | `/api/multimodal/transcribe` | 语音转文字 |
| GET | `/api/multimodal/audio/{filename}` | 音频文件 |
| POST | `/api/v2/vision/ocr` | OCR 识别 |
| POST | `/api/v2/vision/understand-problem` | 拍题理解 |
| POST | `/api/v2/vision/analyze` | 图片分析 |
| POST | `/api/v2/media/search` | 媒体搜索 |

### 其他

| 方法 | 路径 | 功能 |
|------|------|------|
| GET | `/api/search` | 全站搜索 |
| GET | `/api/achievements/{user_id}` | 成就系统 |
| GET | `/api/content/search` | 内容搜索 |
| POST | `/api/material/upload` | 资料上传 |
| POST | `/api/material/search` | 资料搜索 |
| GET | `/api/partition-progress/{pid}` | 分区进度 |
| GET | `/api/learning-events/stats/{pid}` | 事件统计 |

---

## 六、数据库表设计

### 核心表

| 表名 | 用途 | 记录数 |
|------|------|--------|
| `cognitive_nodes` | 认知节点（核心，31+ JSONB 字段） | ~100+ |
| `cognitive_events` | 认知事件日志 | ~500+ |
| `knowledge_edges` | 知识边表（图谱关系） | ~200+ |
| `conversation_node_links` | 会话-知识点关联 | ~100+ |

### 对话表

| 表名 | 用途 |
|------|------|
| `conversation_partitions` | 对话分区 |
| `conversation_branches` | 对话分支 |
| `conversation_nodes` | 消息节点 |
| `conversation_response_blocks` | 响应块 |
| `conversation_link_nodes` | 链接节点 |

### 练习表

| 表名 | 用途 |
|------|------|
| `questions` | 题库 |
| `practice_sessions` | 练习会话 |
| `attempts` | 答题记录 |
| `error_book` | 错题本 |
| `knowledge_states` | 知识状态（BKT 备降） |

### 其他表

| 表名 | 用途 |
|------|------|
| `materials` | 资料表 |
| `material_chunks` | 资料分块 |
| `secretary_proposals` | 秘书提案 |

### cognitive_nodes 表结构

```sql
CREATE TABLE cognitive_nodes (
    id              TEXT NOT NULL,
    user_id         TEXT NOT NULL,
    label           TEXT NOT NULL DEFAULT '',
    level           TEXT NOT NULL DEFAULT 'atom',
    parent          TEXT,
    children        JSONB DEFAULT '[]',
    is_core         BOOLEAN DEFAULT FALSE,

    -- 认知状态（15 个 JSONB 子系统）
    activation      JSONB DEFAULT '{}',
    belief          JSONB DEFAULT '{}',
    prediction      JSONB DEFAULT '{}',
    cognitive_load  JSONB DEFAULT '{}',
    trend           JSONB DEFAULT '{}',
    scheduling      JSONB DEFAULT '{}',
    dialogue_contexts JSONB DEFAULT '[]',
    practice_events JSONB DEFAULT '[]',
    practice_summary JSONB DEFAULT '{}',
    error_clusters  JSONB DEFAULT '[]',
    metacognition   JSONB DEFAULT '{}',
    engagement      JSONB DEFAULT '{}',
    composition     JSONB DEFAULT '{}',
    deep_links      JSONB DEFAULT '[]',
    deep_processing JSONB DEFAULT '{}',
    goal_alignment  JSONB DEFAULT '{}',
    diagnostic      JSONB DEFAULT '{}',

    -- 图谱结构
    prerequisites   JSONB DEFAULT '[]',
    unlocks         JSONB DEFAULT '[]',
    associates      JSONB DEFAULT '[]',

    -- Phase 8 扩展
    path_id         VARCHAR(500),
    node_type       VARCHAR(50) DEFAULT 'explicit',
    is_visible      BOOLEAN DEFAULT false,
    subsystems      JSONB DEFAULT '{}',
    embedding       JSONB,
    is_active       BOOLEAN DEFAULT true,
    deleted_at      TIMESTAMPTZ,

    -- 元信息
    meta            JSONB DEFAULT '{}',
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW(),

    PRIMARY KEY (id, user_id)
);
```

---

## 七、前端页面结构

### 页面路由

| 路径 | 页面 | 功能 |
|------|------|------|
| `/` | 首页 | 学习概览 |
| `/dashboard` | 仪表盘 | 多 Tab 展示（概览/分析/日历/进度/错题/质量/统计/学习/计划/成就/图谱） |
| `/learn` | 学习页 | 知识图谱 + 学习面板 |
| `/practice` | 练习页 | 答题交互 |
| `/progress` | 进度页 | 学习进度追踪 |
| `/analytics` | 分析页 | 行为分析 + 情绪看板 |
| `/calendar` | 日历页 | 学习日历 |
| `/errors` | 错题本 | 错题复习 |
| `/quality` | 质量页 | 题目质量分析 |
| `/stats` | 统计页 | 学习统计 |
| `/study` | 计划页 | 学习计划 |
| `/achievements` | 成就页 | 成就系统 |
| `/graph` | 图谱页 | 全屏力导向图谱 |
| `/materials` | 资料页 | 资料管理 |
| `/secretary` | 秘书页 | 秘书系统主页 |
| `/secretary/settings` | 秘书设置 | 秘书偏好配置 |
| `/settings` | 设置页 | 系统设置 |

### 核心组件

```
frontend/src/components/
├── conversation/           # 对话系统
│   ├── Phase8Sidebar.tsx   # 知识图谱树 + 会话混合展示
│   ├── ChatInput.tsx       # 聊天输入（支持图片/语音）
│   ├── MessageList.tsx     # 消息列表
│   ├── ConversationPanel.tsx # 对话面板
│   ├── ClassifyConfirmPopover.tsx # 分类确认浮窗
│   ├── InlinePracticeBlock.tsx    # 内联练习块
│   ├── MediaSearchBlock.tsx       # 媒体搜索块
│   ├── SecretarySuggestionsBlock.tsx # 秘书提案卡片
│   ├── SpeakButton.tsx     # 语音播放按钮
│   ├── VideoEmbed.tsx      # 视频嵌入
│   └── VoiceRecorder.tsx   # 语音录制
├── dashboard/              # 仪表盘
│   ├── DashboardShell.tsx  # 仪表盘外壳
│   ├── OverviewTab.tsx     # 概览 Tab
│   ├── AnalyticsTab.tsx    # 分析 Tab
│   ├── CalendarTab.tsx     # 日历 Tab
│   ├── ProgressTab.tsx     # 进度 Tab
│   ├── ErrorsTab.tsx       # 错题 Tab
│   ├── QualityTab.tsx      # 质量 Tab
│   ├── StatsTab.tsx        # 统计 Tab
│   ├── StudyTab.tsx        # 学习 Tab
│   ├── PlanTab.tsx         # 计划 Tab
│   ├── AchievementsTab.tsx # 成就 Tab
│   └── GraphTab.tsx        # 图谱 Tab
├── analytics/              # 分析组件
│   ├── RadarChart.tsx      # 雷达图
│   ├── EmotionCard.tsx     # 情绪卡片
│   ├── TrendChart.tsx      # 趋势图
│   ├── HeatmapGrid.tsx     # 热力图
│   ├── HabitTab.tsx        # 习惯 Tab
│   ├── RetentionPanel.tsx  # 遗忘曲线
│   └── DailySummaryCard.tsx # 每日摘要
├── layout/                 # 布局
│   ├── AppShell.tsx        # 应用外壳
│   ├── Sidebar.tsx         # 侧边栏
│   ├── BottomNav.tsx       # 底部导航
│   └── ClientProviders.tsx # 客户端 Provider
├── materials/              # 资料
│   ├── MaterialPanel.tsx   # 资料面板
│   └── MaterialPicker.tsx  # 资料选择器
├── search/                 # 搜索
│   └── UnifiedSearch.tsx   # 统一搜索
├── secretary/              # 秘书
│   └── SecretaryBellBadge.tsx # 秘书铃铛
├── explain/                # 讲解
│   ├── ExplainPanel.tsx    # 讲解面板
│   └── ExpandPanel.tsx     # 拓展面板
├── graph/                  # 图谱
│   └── GraphSidePanel.tsx  # 图谱侧边面板
└── ui/                     # 通用 UI
    ├── Card.tsx
    ├── EmptyState.tsx
    ├── ErrorBoundary.tsx
    ├── MathContent.tsx     # 数学公式渲染
    └── Skeleton.tsx
```

---

## 八、Phase 完成状态

| Phase | 模块 | 状态 | 版本 |
|-------|------|:----:|:----:|
| ① | MVP 练习系统 + 对话基础 | ✅ | v0.1 |
| ② | 学习画像（雷达图/日历/遗忘曲线） | ✅ | v0.2 |
| ③ | 智能路由（图谱/边栏/搜索/首页） | ✅ | v0.2 |
| ④ | 对话系统重构（分层路由/多模态） | ✅ | v0.3 |
| ⑤ | 认知事件（事件层+画像层） | ✅ | v0.3 |
| ⑥ | CognitiveNode 全联动（15 子系统） | ✅ | v0.3 |
| ⑦ | 秘书系统（诊断/提案/策略/7模块） | ✅ | v0.4 |
| ⑧ | 知识图谱树 + 向量分类器 + 融合会话 | ✅ | v0.5 |
| ⑨ | 认知追踪同步 + 分类器降级 | ✅ | v0.5 |
| ⑩ | 间隔重复 (SM-2) + 自适应选题 | ✅ | v0.5 |
| ⑪ | 事件驱动填充 + 认知字段增强 | ✅ | v0.5 |
| ⑫ | 仪表盘 API + 前端展示 | ✅ | v0.5 |
| ⑬ | 多模态讲解助手 (B站+TTS+卡片) | ✅ | v0.5 |
| ⑭ | 伴学心智 (行为+情绪+习惯+创造) | ✅ | v0.6 |
| ⑮ | 多模态输入 + 图谱可视化 | ✅ | v0.6 |
| ⑯ | 系统整合与质量提升 | ✅ | v0.6 |

---

## 九、模块联动全景

```
                  ┌─────────────────────────┐
                  │  练习提交 practice.py   │
                  │  submit_answer()       │
                  └──────┬──────────┬──────┘
                         │          │
                    CognitiveNode   BKT (备降)
                  ┌─────┴─────┐
                  │           │
                  ▼           ▼
    CognitiveNode.belief   old knowledge_states

                  ┌─────────────────────────────┐
                  │  对话系统 conversation_llm.py │
                  │  非流式 + 流式 双路径          │
                  │  Phase 8 classify 自动归类    │
                  └──────────────┬────────────────┘
                                 │
                   submit_dialogue_context()
                                 │
                                 ▼
              CognitiveNode.dialogue_contexts[]

                  ┌─────────────────────────────┐
                  │  图谱生成/编辑/删除           │
                  │  knowledge_graph.py          │
                  │  Phase8Sidebar (前端)        │
                  └──────────────┬────────────────┘
                                 │
                   _sync_graph_to_cognitive()
                                 │
                                 ▼
              CognitiveNode (partition→topic→...→atom)

                  ┌─────────────────────────────┐
                  │  秘书系统 Secretary          │
                  │  diagnosis_engine.py         │
                  │  proposal_generator.py       │
                  │  policy_engine.py            │
                  │  7 内置模块                   │
                  └──────────────┬────────────────┘
                                 │
                   事件总线订阅 CognitiveNode 变化
                                 │
                                 ▼
                   提案 → 前端 SecretaryBellBadge

                  ┌─────────────────────────────┐
                  │  ZPD 调度器                  │
                  │  zpd_scheduler.py           │
                  └──────────────┬────────────────┘
                         estimate_student_ability()
                         CognitiveNode.belief 优先
                            BKT 备降

                  ┌─────────────────────────────┐
                  │  知识 API + 学习计划          │
                  │  knowledge.py / study.py     │
                  └──────────────┬────────────────┘
                         get_knowledge_state()
                         CognitiveNode 优先 → BKT 备降
```

---

## 十、部署架构

```
┌─────────────────────────────────────────────────────┐
│                    Docker Compose                    │
│  ┌──────────────────┐  ┌──────────────────┐        │
│  │  frontend         │  │  backend          │        │
│  │  Next.js 14       │  │  FastAPI          │        │
│  │  :3000            │  │  :8000            │        │
│  └────────┬─────────┘  └────────┬─────────┘        │
│           │                      │                   │
│  ┌────────┴──────────────────────┴─────────┐        │
│  │              Nginx (反向代理)             │        │
│  │              :80 / :443                  │        │
│  └────────────────────┬────────────────────┘        │
└───────────────────────┼─────────────────────────────┘
                        │
┌───────────────────────┼─────────────────────────────┐
│                    数据层                            │
│  ┌──────────────────┐  ┌──────────────────┐        │
│  │  PostgreSQL 14+   │  │  文件存储          │        │
│  │  :5432            │  │  /uploads         │        │
│  │  + pgvector       │  │                   │        │
│  └──────────────────┘  └──────────────────┘        │
└─────────────────────────────────────────────────────┘
```

### 环境变量

```bash
# 数据库
DB_HOST=localhost
DB_PORT=5432
DB_NAME=edu_companion
DB_USER=companion
DB_PASSWORD=companion123

# LLM
TEXT_MODEL=gpt-4o
TEXT_REASONING_MODEL=gpt-4o
TEXT_FAST_MODEL=gpt-4o-mini

# 存储
USE_PG_STORAGE=true
# USE_JSON_STORAGE=true  # 回滚到 JSON 存储

# 调试
DEBUG=false
```

---

## 十一、文档索引

```
docs/
├── architecture.md              ← 本文件（唯一最新架构设计）
├── architecture-v3.md           ← 旧版架构（Phase 1-8）
├── PROGRESS.md                  ← 进度跟踪
├── README.md                    ← 文档总入口
├── phase1/                      ← MVP 设计 (已归档)
├── phase2/                      ← 学习画像设计 (已归档)
├── phase3/                      ← 智能路由设计 (已归档)
├── phase4/                      ← 对话系统设计 (已归档)
├── phase5/                      ← 认知事件设计 (已归档)
├── phase6/                      ← CognitiveNode 设计 (已归档)
├── phase7/                      ← 秘书系统设计 (已归档)
└── phase8/                      ← 知识图谱树+分类器设计 (已归档)
```
