# 智能伴学系统架构文档 v4.3

> 版本: v4.4
> 最后更新: 2026-06-04
> 当前版本号: v7.0.14 (Phase 14.1)
> Phase 状态: 1-10 ✅ 已交付 / 11-13 ❌ 未开始 / 14.1 ✅ 情绪分析与心理陪伴 / 14.2+ ❌ 未开始

---

## 一、项目概述

智能伴学系统（edu-companion）是一个基于 AI 的全栈学习助手工具平台，提供自适应学习规划、精准答疑、多模态交互、学情追踪、心理陪伴等功能。

### 技术栈

| 层级 | 技术 | 说明 |
|------|------|------|
| 前端 | Next.js 14 + Tailwind CSS | SSR/CSR 混合，CSS Variables 主题切换 |
| 设计系统 | 纸墨质感 + 亮暗双主题 | 40+ CSS token，design.md 规范驱动 |
| 状态管理 | Zustand | 替代 monolithic useConversation hook，分模块 store |
| 后端 | Python FastAPI | 异步高性能，OpenAPI 自动文档 |
| 数据库 | PostgreSQL 14+ + pgvector | JSONB 灵活存储 + 向量检索 |
| LLM | OpenAI 兼容 API | 通过 .env 配置模型名，禁止硬编码 |
| 存储 | PG 主存 + JSON 备降 | `USE_PG_STORAGE=true` 默认开启 |
| 部署 | Docker + Nginx | 双容器部署，前端 standalone 模式 |

### 设计系统 (v5.0)

> 核心理念："让思考成为焦点，让界面成为陪伴"
> 详细规范：`design.md`

| 维度 | 规范 |
|------|------|
| 色彩 | 暖白书页 `#fbfaf7` / 暖黑 `#1a1816`，40+ CSS token 亮暗双主题 |
| 排版 | Inter 正文 16px / 行高 1.65 / 字重 400/600（非 700）/ JetBrains Mono 代码 |
| 气泡 | 用户白底+边框 / AI微暖底无边框 / 14px圆角 / 入场动画150ms |
| 卡片 | 10px 圆角 / 无阴影（用边框+色差分层） |
| 按钮 | 10px 圆角 / active:scale-[0.97] / 药丸输入框 |
| 浮层 | 仅 modal/dropdown/tooltip 保留 shadow |
| 响应式 | 768px→1024px 断点 / 侧边栏 280px 可折叠 |

### 代码规模

| 模块 | 行数 | 文件数 |
|------|------|--------|
| 后端 (Python) | ~28,000 | ~120 (含 64 服务, 22 路由) |
| 前端 (TS/TSX) | ~15,500 | ~83 (25 页面路由) |
| 合计 | ~43,500 | ~203 |

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
│  │         Zustand Store (状态管理层)               │            │
│  │         conversation-store.ts                   │            │
│  │         + streaming.ts / tree-helpers.ts        │            │
│  └────────────────────┬───────────────────────────┘            │
│       │               │                                        │
│  ┌────┴───────────────┴───────────────────────┐                │
│  │           API Layer (lib/api.ts)            │                │
│  └────────────────────┬───────────────────────┘                │
└───────────────────────┼────────────────────────────────────────┘
                        │ HTTP/WebSocket
┌───────────────────────┼────────────────────────────────────────┐
│                        后端 (FastAPI)                           │
│  ┌────────────────────┴───────────────────────┐                │
│  │     API Router (~22 模块, ~151 端点)       │                │
│  │  对话/练习/v7题库/秘书/图谱/情绪           │                │
│  └────┬────────────┬────────────┬────────────┬┘                │
│       │            │            │            │                  │
│  ┌────┴────┐ ┌─────┴────┐ ┌────┴────┐ ┌────┴────┐            │
│  │ 对话层  │ │ 练习层   │ │ 秘书层  │ │ 图谱层  │            │
│  └────┬────┘ └─────┬────┘ └────┬────┘ └────┬────┘            │
│       │            │            │            │                  │
│  ┌────┴────────────┴────────────┴────────────┴────┐            │
│  │          Service Layer (40+ 服务, 模块化拆分)  │            │
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

> 共 ~22 个路由模块，~151 个端点

### 对话系统 (conversation.py)

| 方法 | 路径 | 功能 |
|------|------|------|
| WS | `/api/conversations/ws` | WebSocket 实时聊天 |
| GET | `/api/conversations/tree/{level}` | 获取树节点 |
| POST | `/api/conversations/tree/{level}` | 创建树节点 |
| PATCH | `/api/conversations/tree/{level}/{node_id}` | 更新节点 |
| DELETE | `/api/conversations/tree/{level}/{node_id}` | 删除节点 |
| GET | `/api/conversations/tree/conversation/{conv_id}/messages` | 获取消息 |
| GET | `/api/conversations/tree/conversation/{conv_id}/blocks` | 获取响应块 |
| POST | `/api/conversations/tree/conversation/{conv_id}/message` | 发送消息 |
| POST | `/api/conversations/tree/conversation/{conv_id}/switch` | 切换分支 |
| GET | `/api/conversations/tree/message/{message_id}` | 获取消息详情 |
| PUT | `/api/conversations/tree/message/{message_id}` | 更新消息 |
| GET | `/api/conversations/tree/message/{message_id}/blocks` | 消息关联块 |
| GET | `/api/conversations/tree/response-block/{block_id}` | 响应块详情 |
| GET | `/api/conversations/tree/stream/active/{conversation_id}` | 活跃流 |
| POST | `/api/conversations/tree/conversation/{conv_id}/message/persist` | 持久化消息 |
| GET | `/api/conversations/tree/conversations/{conv_id}/materials` | 关联资料 |
| GET | `/api/conversations/tree/conversations/{conv_id}/practice-suggestions` | 练习建议 |
| POST | `/api/conversations/workspace/upload` | 工作区上传 |
| GET | `/api/conversations/workspace/files` | 工作区文件列表 |
| DELETE | `/api/conversations/workspace/files/{file_id}` | 删除工作区文件 |
| GET | `/api/conversations/workspace/download/{file_id}` | 下载工作区文件 |
| GET | `/api/conversations/emotion/trend` | 情绪趋势 |
| GET | `/api/conversations/jobs/{job_id}` | 异步任务状态 |
| POST | `/api/conversations/jobs/{job_id}/cancel` | 取消异步任务 |
| GET | `/api/conversations/jobs/{job_id}/block` | 任务响应块 |

### 聊天 (chat.py)

| 方法 | 路径 | 功能 |
|------|------|------|
| WS | `/api/chat/ws` | WebSocket 聊天 |
| POST | `/api/chat/api/chat` | HTTP 聊天 |

### 练习系统 (practice.py)

| 方法 | 路径 | 功能 |
|------|------|------|
| POST | `/api/practice/questions/generate` | 生成题目 |
| GET | `/api/practice/questions` | 获取题目列表 |
| GET | `/api/practice/sessions` | 会话列表 |
| GET | `/api/practice/sessions/{session_id}` | 会话详情 |
| POST | `/api/practice/sessions/{session_id}/complete` | 完成会话 |
| POST | `/api/practice/hint` | 获取提示 |
| POST | `/api/practice/inline/answer` | 内联答题 |
| POST | `/api/practice/inline/hint` | 内联提示 |
| GET | `/api/practice/errors` | 错题列表 |
| POST | `/api/practice/errors/{entry_id}/review` | 复习错题 |
| GET | `/api/practice/errors/due` | 待复习错题 |
| POST | `/api/practice/errors/{entry_id}/analyze` | 错题分析 |
| GET | `/api/practice/errors/stats` | 错题统计 |
| GET | `/api/practice/stats` | 练习统计 |
| GET | `/api/practice/behavior` | 练习行为分析 |
| GET | `/api/practice/quality` | 质量分析 |
| GET | `/api/practice/quality/worst` | 最差题目 |
| POST | `/api/practice/quality/apply` | 应用质量优化 |
| GET | `/api/practice/quality/detail/{question_id}` | 题目详情 |
| GET | `/api/practice/quality/{question_id}/distractors` | 干扰项分析 |
| GET | `/api/practice/knowledge/state` | 知识状态 |
| GET | `/api/practice/knowledge/skill/{skill_id}` | 技能详情 |
| GET | `/api/practice/knowledge/weak` | 薄弱知识点 |
| POST | `/api/practice/knowledge/evidence` | 知识证据 |

### 知识图谱 (knowledge.py)

| 方法 | 路径 | 功能 |
|------|------|------|
| GET | `/api/knowledge/graph` | 知识图谱 |
| GET | `/api/knowledge/prerequisites` | 前置检查 |
| POST | `/api/knowledge/check` | 前置校验 |
| GET | `/api/knowledge/blocked` | 被卡控节点 |
| GET | `/api/knowledge/ready` | 可学习节点 |
| GET | `/api/knowledge/path` | 学习路径 |
| GET | `/api/knowledge/retention` | 遗忘曲线 |

### 知识图谱 CRUD (knowledge_graph.py)

| 方法 | 路径 | 功能 |
|------|------|------|
| GET | `/api/knowledge/graph/{pid}` | 获取分区图谱（节点+边） |
| POST | `/api/knowledge/graph/{pid}/generate` | AI 生成图谱 |
| POST | `/api/knowledge/graph/{pid}/node` | 添加知识节点 |
| PATCH | `/api/knowledge/graph/{pid}/node/{nid}` | 编辑节点（标签/描述/优先级） |
| DELETE | `/api/knowledge/graph/{pid}/node/{nid}` | 删除节点 + 关联边 |
| POST | `/api/knowledge/graph/{pid}/edge` | 添加依赖边 |
| DELETE | `/api/knowledge/graph/{pid}/edge/{eid}` | 删除依赖边 |

### Phase8 图谱 (phase8.py)

| 方法 | 路径 | 功能 |
|------|------|------|
| POST | `/api/v2/classify` | 消息分类 |
| POST | `/api/v2/classify/select` | 分类选择 |
| POST | `/api/v2/classify/custom` | 自定义分类 |
| PUT | `/api/v2/conversations/{conv_id}/save` | 保存对话分类 |
| GET | `/api/v2/conversations/{conv_id}/links` | 获取链接 |
| POST | `/api/v2/conversations/{conv_id}/links` | 创建链接 |
| PATCH | `/api/v2/conversations/{conv_id}/links/{link_id}` | 更新链接 |
| DELETE | `/api/v2/conversations/{conv_id}/links/{link_id}` | 删除链接 |
| GET | `/api/v2/graph/nodes` | 图节点 |
| GET | `/api/v2/graph/search` | 图谱搜索 |
| POST | `/api/v2/graph/nodes/{node_id}/expand` | 展开节点 |
| POST | `/api/v2/graph/nodes` | 创建图节点 |
| PATCH | `/api/v2/graph/nodes/{node_id}` | 更新图节点 |
| DELETE | `/api/v2/graph/nodes/{node_id}` | 删除图节点 |
| GET | `/api/v2/graph/edges` | 图边列表 |
| POST | `/api/v2/graph/edges/{edge_id}/accept` | 接受边 |
| POST | `/api/v2/graph/edges/{edge_id}/reject` | 拒绝边 |
| DELETE | `/api/v2/graph/edges/{edge_id}` | 删除边 |
| GET | `/api/v2/graph/export` | 导出图谱 |
| POST | `/api/v2/practice/queue` | 练习队列 |

### 学习计划与进度

| 方法 | 路径 | 功能 |
|------|------|------|
| POST | `/api/study/plan/generate` | 生成计划 |
| GET | `/api/study/plan/{user_id}` | 获取计划 |
| PUT | `/api/study/plan/{user_id}/{task_id}/complete` | 完成任务 |
| GET | `/api/study/plan/{user_id}/progress` | 计划进度 |
| GET | `/api/study/plan/{user_id}/history` | 历史计划 |
| POST | `/api/study/plan/refresh` | 刷新计划 |
| GET | `/api/study/suggestions` | 学习建议 |
| GET | `/api/progress/{user_id}` | 学习进度 |
| GET | `/api/progress/{user_id}/stats` | 统计数据 |
| POST | `/api/progress/{user_id}/session/start` | 开始学习会话 |
| POST | `/api/progress/{user_id}/profile/update` | 更新画像 |
| GET | `/api/progress/{user_id}/profile` | 获取画像 |
| GET | `/api/progress/{user_id}/calendar` | 学习日历 |
| GET | `/api/progress/{user_id}/summary` | 进度摘要 |

### 秘书系统 (secretary.py)

| 方法 | 路径 | 功能 |
|------|------|------|
| GET | `/api/secretary/snapshot` | 实时快照 |
| GET | `/api/secretary/daily-brief` | 每日简报 |
| POST | `/api/secretary/diagnose` | 诊断 |
| POST | `/api/secretary/suggest` | 生成提案 |
| GET | `/api/secretary/proposals/pending` | 待处理提案 |
| GET | `/api/secretary/proposals/history` | 历史提案 |
| POST | `/api/secretary/proposals/{proposal_id}/accept` | 采纳提案 |
| POST | `/api/secretary/proposals/{proposal_id}/dismiss` | 拒绝提案 |
| POST | `/api/secretary/proposals/{proposal_id}/snooze` | 推迟提案 |
| POST | `/api/secretary/generate-llm-proposals` | LLM 生成提案 |
| POST | `/api/secretary/push-to-blackboard` | 推送到黑板 |
| GET | `/api/secretary/modules` | 模块列表 |
| POST | `/api/secretary/modules/toggle` | 切换模块 |
| GET | `/api/secretary/preferences` | 偏好设置 |
| PATCH | `/api/secretary/preferences` | 更新偏好 |
| GET | `/api/secretary/onboarding` | 引导流程 |
| POST | `/api/secretary/onboarding/dialogue` | 引导对话 |
| GET | `/api/secretary/data/export` | 数据导出 |
| DELETE | `/api/secretary/data/delete` | 数据删除 |

### 多模态

| 方法 | 路径 | 功能 |
|------|------|------|
| POST | `/api/multimodal/transcribe` | 语音转文字 |
| GET | `/api/multimodal/audio/{filename}` | 音频文件 |
| GET | `/api/multimodal/images/{filename}` | 图片文件 |

### 资料管理 (material.py)

| 方法 | 路径 | 功能 |
|------|------|------|
| POST | `/api/materials/upload` | 资料上传 |
| GET | `/api/materials` | 资料列表 |
| PATCH | `/api/materials/{material_id}` | 更新资料 |
| POST | `/api/materials/{material_id}/promote` | 提升资料 |
| GET | `/api/materials/promote-suggestions` | 提升建议 |
| POST | `/api/materials/search` | 资料搜索 |
| GET | `/api/materials/{material_id}/chunks` | 资料分块 |
| POST | `/api/materials/generate-questions` | 生成题目 |
| DELETE | `/api/materials/{material_id}` | 删除资料 |
| POST | `/api/materials/cleanup-sessions` | 清理会话 |

### 其他

| 方法 | 路径 | 功能 |
|------|------|------|
| GET | `/api/search` | 全站搜索 |
| GET | `/api/achievements/{user_id}` | 成就系统 |
| POST | `/api/achievements/{user_id}/check` | 检查成就 |
| GET | `/api/partition-progress/{pid}` | 分区进度 |

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
| `conversation_user_meta` | 用户元信息 |

### 练习表

| 表名 | 用途 |
|------|------|
| `questions` | 题库 |
| `practice_sessions` | 练习会话 |
| `attempts` | 答题记录 |
| `error_book` | 错题本 |

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

    -- 参数引用
    param_refs      JSONB DEFAULT '{}',

    -- 元信息
    meta            JSONB DEFAULT '{}',
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW(),

    PRIMARY KEY (id)
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
frontend/src/
├── store/                          # Zustand 状态管理
│   ├── conversation-store.ts       # 对话系统 store (替代 useConversation hook)
│   ├── streaming.ts                # 流式输出、WS 连接管理
│   └── tree-helpers.ts             # 树操作、API fetch 封装
├── components/
│   ├── conversation/               # 对话系统
│   │   ├── Phase8Sidebar.tsx       # 知识图谱树 + 会话混合展示
│   │   ├── SidebarTreeNode.tsx     # 侧边栏树节点
│   │   ├── ChatInput.tsx           # 聊天输入（支持图片/语音）
│   │   ├── MessageList.tsx         # 消息列表
│   │   ├── ConversationPanel.tsx   # 对话面板
│   │   ├── ResponseBlockRenderer.tsx # 响应块渲染器
│   │   ├── InlinePracticeBlock.tsx # 内联练习块
│   │   ├── MediaSearchBlock.tsx    # 媒体搜索块
│   │   ├── SecretarySuggestionsBlock.tsx # 秘书提案卡片
│   │   ├── SpeakButton.tsx         # 语音播放按钮
│   │   ├── VideoEmbed.tsx          # 视频嵌入
│   │   └── VoiceRecorder.tsx       # 语音录制
│   ├── dashboard/                  # 仪表盘
│   │   ├── DashboardShell.tsx      # 仪表盘外壳
│   │   ├── OverviewTab.tsx         # 概览 Tab
│   │   ├── AnalyticsTab.tsx        # 分析 Tab
│   │   ├── CalendarTab.tsx         # 日历 Tab
│   │   ├── ProgressTab.tsx         # 进度 Tab
│   │   ├── ErrorsTab.tsx           # 错题 Tab
│   │   ├── QualityTab.tsx          # 质量 Tab
│   │   ├── StatsTab.tsx            # 统计 Tab
│   │   ├── StudyTab.tsx            # 学习 Tab
│   │   ├── PlanTab.tsx             # 计划 Tab
│   │   ├── AchievementsTab.tsx     # 成就 Tab
│   │   ├── GraphTab.tsx            # 图谱 Tab（双数据源合并 + 编辑模式）
│   │   └── analytics/              # 分析子组件
│   │       ├── OverviewCards.tsx    # 概览卡片
│   │       ├── MasteryErrorsCard.tsx # 掌握度+错题卡片
│   │       ├── SuggestionsCard.tsx  # 建议卡片
│   │       ├── RetentionPanel.tsx   # 遗忘曲线
│   │       ├── DailySummaryCard.tsx # 每日摘要
│   │       ├── HabitTab.tsx         # 习惯 Tab
│   │       ├── HeatmapGrid.tsx      # 热力图
│   │       └── TrendChart.tsx       # 趋势图
│   ├── analytics/                  # 分析组件
│   │   ├── RadarChart.tsx          # 雷达图
│   │   └── EmotionCard.tsx         # 情绪卡片
│   ├── layout/                     # 布局
│   │   ├── AppShell.tsx            # 应用外壳
│   │   ├── Sidebar.tsx             # 侧边栏
│   │   ├── BottomNav.tsx           # 底部导航
│   │   └── ClientProviders.tsx     # 客户端 Provider
│   ├── search/                     # 搜索
│   │   └── UnifiedSearch.tsx       # 统一搜索
│   ├── secretary/                  # 秘书
│   │   └── SecretaryBellBadge.tsx  # 秘书铃铛
│   └── ui/                         # 通用 UI
│       ├── Card.tsx
│       ├── ConfirmDialog.tsx       # 确认对话框
│       ├── EmptyState.tsx
│       ├── ErrorBoundary.tsx
│       ├── InlineEdit.tsx          # 内联编辑
│       ├── MathContent.tsx         # 数学公式渲染
│       └── Skeleton.tsx
```

---

## 八、Phase 完成状态

### 功能开发阶段 (v0.1 — v0.6)

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

### v4.0 重构阶段 (v4.0)

| Phase | 模块 | 状态 | 说明 |
|-------|------|:----:|------|
| ⑰ | 前端状态管理重构 | ✅ | monolithic hook → Zustand 分模块 store |
| ⑱ | 组件树精简 | ✅ | 删除 7 个废弃组件，新增 6 个功能组件 |
| ⑲ | API 端点清理 | ✅ | 移除 practice/sessions、practice/submit 等废弃端点 |
| ⑳ | 数据库表精简 | ✅ | 移除 knowledge_states 表，纯 CognitiveNode 模型 |
| ㉑ | BKT 全量清除 | ✅ | 移除所有 BKT 引用，统一为 CognitiveNode.belief |
| ㉒ | 架构文档 v4.0 | ✅ | 更新架构文档，反映全部重构变更 |

---

## 九、模块联动全景

```
                  ┌─────────────────────────┐
                  │  练习提交 practice.py   │
                  │  inline/answer()        │
                  └──────────┬──────────────┘
                             │
                        CognitiveNode
                  ┌─────────┴─────────┐
                  │                   │
                  ▼                   ▼
    CognitiveNode.belief      CognitiveNode.practice_summary
                  │                   │
                  └─────────┬─────────┘
                            │
                   submit_practice_event()

                  ┌─────────────────────────────┐
                  │  对话系统                     │
                  │  conversation_llm.py (facade) │
                  │  → llm_core.py                │
                  │  → tool_dispatch.py           │
                  │  → cognitive_sync.py          │
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
                  │  phase8.py / knowledge.py   │
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
                         CognitiveNode.belief

                  ┌─────────────────────────────┐
                  │  知识 API + 学习计划          │
                  │  knowledge.py / study.py     │
                  │  → knowledge_state.py (共享)  │
                  └──────────────┬────────────────┘
                         get_knowledge_state()
                         CognitiveNode.belief
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
DB_PASSWORD=        # 从环境变量读取，禁止硬编码

# LLM
TEXT_MODEL=gpt-4o
TEXT_REASONING_MODEL=gpt-4o
TEXT_FAST_MODEL=gpt-4o-mini

# 存储
USE_PG_STORAGE=true
COMPANION_HOME=~/.companion  # 数据目录（集中化配置）
# USE_JSON_STORAGE=true  # 回滚到 JSON 存储

# 调试
DEBUG=false
```

---

## 十一、文档索引

```
docs/
├── architecture.md              ← 本文件（唯一最新架构设计 v4.0）
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
