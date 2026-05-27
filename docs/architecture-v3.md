# 智能伴学系统架构设计 v3.0

> 版本: v3.0
> 最后更新: 2026-05-26 (Phase 15 完成)
> 状态: **✅ 全部 16 个 Phase 已交付**

> ⚠️ 注意：本架构文档主要覆盖 Phase 1-6 核心设计。Phase 7（秘书系统）和 Phase 8（知识图谱树+分类器）的详细设计见 `docs/phase7/` 和 `docs/phase8/`。

---

## 交付现状

|Phase|模块|状态|时间|
|:-----|------|:----:|:----:|
|①|MVP 练习系统 + 对话基础|✅|v0.1|
|②|学习画像（雷达图/日历/遗忘曲线）|✅|v0.2|
|③|智能路由（图谱/边栏/搜索/首页）|✅|v0.2|
|④|对话系统重构（分层路由/多模态）|✅|v0.3|
|⑤|认知事件（事件层+画像层）|✅|v0.3|
|⑥|CognitiveNode 全联动（15 子系统）|✅|v0.3|
|⑦|秘书系统（诊断/提案/策略/7模块）|✅|v0.4|
|⑧|知识图谱树 + 向量分类器 + 融合会话|✅|v0.5|
|⑨|认知追踪同步 + 分类器降级|✅|v0.5|
|⑩|间隔重复 (SM-2) + 自适应选题|✅|v0.5|
|⑪|事件驱动填充 + 认知字段增强|✅|v0.5|
|⑫|仪表盘 API + 前端展示|✅|v0.5|
|⑬|多模态讲解助手 (B站+TTS+卡片)|✅|v0.5|
|⑭|伴学心智 (行为+情绪+习惯+创造)|✅|v0.6|
|⑮|多模态输入 + 图谱可视化|✅|v0.6|

### 当前核心功能矩阵

| 层级 | 模块 | 状态 |
|------|------|:--:|
| ① 事件层 | 对话消息 / 练习提交 / 情绪标记 / 学习时长 / 错题 | ✅ 13 种事件类型 |
| ② 画像层 | CognitiveNode 统一认知模型 (Phase 6) | ✅ 15 子系统 + 22 方程 + 31 列 JSONB |
| ② 画像层 | PartitionProgress 分区进度画像 API | ✅ CognitiveNode 主源 → 旧 JSON 备降 |
| ③ 决策层 | CognitiveNode 18 步事件驱动 Pipeline | ✅ 信念/激活/趋势/疲劳/遗忘/激励/自评/目标/组合/深度/对话/异常 |
| ③ 决策层 | 秘书系统 Secretary (Phase 7) | ✅ 诊断/提案/策略/7 内置模块 |
| ③ 决策层 | 知识图谱分类器 (Phase 8) | ✅ 分层向量检索 + 3 模式决策 |
| ③ 决策层 | 智能创造扩展 (Phase 14) | ✅ 知识拓展 / 变式题 / 关联发现 |
| ③ 决策层 | 心理陪伴 (Phase 14) | ✅ 情绪检测 + 趋势分析 + 对话注入 |
| 多媒体 | 视觉理解 (Phase 15) | ✅ OCR / 拍题理解 / 通用图片分析 |
| 多媒体 | 语音输入 (Phase 4) | ✅ 语音录制 + Whisper 转文字 |
| 多媒体 | 语音合成 (Phase 13) | ✅ Edge-TTS 知识点讲解 |
| 多媒体 | 视频检索 (Phase 13) | ✅ B站/知乎/Youtube 多平台搜索 |
| 治理 | 48h 临时对话清理 (Phase 15) | ✅ 每日 cron 自动归档 |
| 治理 | Classify 确认 UI (Phase 15) | ✅ 浮窗确认 + 搜索选择 |
| 数据层 | PG `cognitive_nodes` 表 | ✅ 默认存储开启 |
| 数据层 | PG `knowledge_states` 旧表 | ✅ (备降源, 不删) |
| 数据层 | JSON 存储 | ✅ (`USE_JSON_STORAGE=true` 回滚) |
| 联动 | 练习→CognitiveNode 双写 | ✅ `submit_practice()` |
| 联动 | 图谱→CognitiveNode 同步 | ✅ `_sync_graph_to_cognitive()` |
| 联动 | ZPD 调度→CognitiveNode | ✅ 优先读 CognitiveNode |
| 联动 | 对话→CognitiveNode | ✅ 非流式 + 流式双路径 |
| 联动 | 知识 API→CognitiveNode | ✅ `_BKTKnowledgeAdapter` 主源 |
| 联动 | 学习计划→CognitiveNode | ✅ 优先读 CognitiveNode |
| 联动 | Phase 8 分类→KG 树 | ✅ `POST /api/v2/classify` 自动归类 |

---

## 一、核心实体：CognitiveNode

**系统中所有「同一个知识点」的表征统一到一个实体**。图谱是它的投影，旧的 BKT 是它的备降，练习是它的更新事件，对话是它的上下文引用。

```python
class CognitiveNode(BaseModel):
    """统一认知数据模型 — 一个知识点在学生身上的完整状态"""

    # ── 身份 ──
    id: str                    # "calc-derivatives"
    label: str                 # "导数"
    level: str                 # "partition" | "domain" | "topic" | "concept" | "atom"
    parent: str | None         # 父节点 ID
    is_core: bool = False      # 核心知识点
    
    # ── 15 个子系统 ──
    activation: Activation              # ACT-R 激活 + 扩散
    belief: Belief                      # Beta(α,β) 掌握度信念
    prediction: Prediction | None       # 作答预测 (正确概率)
    cognitive_load: CognitiveLoad       # 认知负荷
    scheduling: Scheduling              # 复习调度
    dialogue_contexts: list[DialogueContext]  # 对话上下文 (上限 5 条)
    metacognition: Metacognition | None # 自评校准
    engagement: Engagement | None       # 投入度
    composition: Composition | None     # 组合结构
    deep_processing: DeepProcessing | None  # 深度处理
    deep_links: list[DeepLink]          # 深层链接
    goal_alignment: GoalAlignment | None    # 目标对齐
    diagnostic: Diagnostic | None       # 诊断结果
    practice_summary: PracticeSummary   # 练习统计汇总
    learning_trend: LearningTrend       # 趋势 (velocity/plateau/decline)
    error_clusters: list[ErrorCluster]  # 错误簇

    # ── 图谱关系 ──
    prerequisites: list[Prerequisite]   # 前置依赖
    unlocks: list[Unlock]               # 解锁知识
    associates: list[Associate]         # 关联知识

    # ── 元信息 ──
    meta: MetaInfo
```

### 数据流：事件 → CognitiveNode

```
练习提交 (practice.py)
  └─ submit_practice() ──→ CognitiveNode
       ├─ belief: Beta(α,β) 更新
       ├─ activation: base_level + recency 更新
       ├─ cognitive_load: 疲劳/负荷 更新
       ├─ scheduling: review_urgency 重新计算
       ├─ practice_summary: attempts + correct
       ├─ learning_trend: velocity + plateau 检测
       ├─ error_clusters: 错误模式聚类
       ├─ diagnostic: 知识漏洞标记
       ├─ goal_alignment: 目标进度偏差
       ├─ composition: 组合掌握度传播
       ├─ deep_processing: 深度处理触发
       └─ metacognition: 自评偏差校准

对话回复 (conversation_llm.py)
  └─ submit_dialogue_context() ──→ CognitiveNode.dialogue_contexts[]
       └─ 非流式 + 流式 双路径 ✅
        └─ Phase 8 classify (发消息时自动归属)

图谱生成/编辑 (knowledge_graph.py → Phase8Sidebar)
  └─ _sync_graph_to_cognitive() ──→ CognitiveNode (partition/topic/concept/atom)
       └─ 图谱生成 + 节点CRUD + 边CRUD 三入口 ✅
```

---

## 二、三层架构

```
┌──────────────────────────────────────────────────────────────────┐
│ ③ 决策层：秘书系统 + 分类器                                     │
│   "现在推什么？归到哪里？"                                         │
│   输入: CognitiveNode + StudentProfile + Context                 │
│   输出: 提案 / 分类结果 / Action                                  │
│                                                                  │
│   ├─ 诊断引擎 DiagnosisEngine           (Phase 7) ✅            │
│   ├─ 提案生成器 ProposalGenerator        (Phase 7) ✅            │
│   ├─ 策略引擎 PolicyEngine              (Phase 7) ✅            │
│   ├─ 7 内置模块                         (Phase 7) ✅            │
│   └─ Phase8 向量分类器 (3 模式决策)      (Phase 8) ✅            │
└───────────────────────────┬──────────────────────────────────────┘
                            │
┌───────────────────────────┴──────────────────────────────────────┐
│ ② 画像层：CognitiveNode + PartitionProgress                      │
│   "学得到底怎么样了？" — 多维学习画像                              │
│                                                                  │
│   ├─ CognitiveNode 统一实体 (PG 主存)                            │
│   ├─ PartitionProgress API (画像计算 + 缓存)                      │
│   ├─ 旧 BKT/knowledge_graphs (备降源)                            │
│   └─ 13 种学习事件统计                                            │
└───────────────────────────┬──────────────────────────────────────┘
                            │
┌───────────────────────────┴──────────────────────────────────────┐
│ ① 事件层：LearningEvents                                          │
│   对话消息 / 练习提交 / 心情标记 / 学习时长 /                       │
│   页面停留 / 错题重做间隔 / 考试日程                               │
│                                                                  │
│   record_event() → UserData.event_log                             │
│   practice_submit → submit_practice() → CognitiveNode             │
└──────────────────────────────────────────────────────────────────┘
```

---

## 三、模块联动全景

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
                  │   Phase 8 classify 自动归类   │
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
                   提案 → 前端 SecretrayBellBadge

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

                  ┌─────────────────────────────┐
                  │  AI 上下文 (orchestrator)    │
                  └──────────────┬────────────────┘
                     _build_cognitive_context()
                         CognitiveNode 优先 → old profile
```

---

## 四、数据表设计 (PostgreSQL)

**cognitive_nodes** 表 (Phase 6 核心 + Phase 8 扩展)：

```sql
CREATE TABLE cognitive_nodes (
    id              TEXT NOT NULL,
    user_id         TEXT NOT NULL,
    label           TEXT,
    level           TEXT DEFAULT 'atom',
    parent          TEXT,
    is_core         BOOLEAN DEFAULT FALSE,
    prerequisites   JSONB DEFAULT '[]',
    unlocks         JSONB DEFAULT '[]',
    associates      JSONB DEFAULT '[]',
    activation      JSONB,        -- {base_level, recency, spread_targets}
    belief          JSONB,        -- {alpha, beta, proficiency_mean, ...}
    prediction      JSONB,
    cognitive_load  JSONB,        -- {fatigue, session_count, capacity_remaining}
    scheduling      JSONB,        -- {next_review, review_urgency, ...}
    dialogue_contexts JSONB DEFAULT '[]',
    metacognition   JSONB,
    engagement      JSONB,
    composition     JSONB,
    deep_processing JSONB,
    deep_links      JSONB DEFAULT '[]',
    goal_alignment  JSONB,
    diagnostic      JSONB,
    practice_summary JSONB,       -- {total_attempts, correct_attempts, ...}
    learning_trend  JSONB,        -- {velocity, direction, plateau_days, ...}
    error_clusters  JSONB DEFAULT '[]',
    meta            JSONB,
    -- Phase 8 新增列
    path_id         VARCHAR(500),                    -- 层级路径标识
    node_type       VARCHAR(50) DEFAULT 'explicit',  -- explicit | auto_generated | ...
    is_visible      BOOLEAN DEFAULT false,           -- 前端展示控制
    subsystems      JSONB DEFAULT '{}',              -- Phase 8 专属元数据
    embedding       VECTOR(1536),                    -- 语义向量
    is_active       BOOLEAN DEFAULT true,            -- 热冷分层标记
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW(),
    deleted_at      TIMESTAMPTZ,
    PRIMARY KEY (id, user_id)
);

-- 索引
CREATE INDEX idx_cognitive_nodes_user ON cognitive_nodes(user_id);
CREATE INDEX idx_cognitive_nodes_parent ON cognitive_nodes(parent);
CREATE INDEX idx_cognitive_nodes_level ON cognitive_nodes(level);
CREATE INDEX idx_cognitive_nodes_next_review 
    ON cognitive_nodes(((scheduling->>'next_review')::double precision));
CREATE INDEX IF NOT EXISTS idx_cn_path_id ON cognitive_nodes(user_id, path_id)
    WHERE path_id IS NOT NULL AND deleted_at IS NULL;
CREATE INDEX IF NOT EXISTS idx_cn_embedding ON cognitive_nodes
    USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100)
    WHERE embedding IS NOT NULL;
```

**其他 PG 表** (存储层):

| 表名 | 用途 | 状态 |
|------|------|:--:|
| `conversation_user_meta` | 用户元数据（全字段持久化） | ✅ |
| `conversation_partitions` | 分区（旧） | ✅ (备降) |
| `conversation_branches` | 对话 | ✅ |
| `conversation_nodes` | 消息节点 | ✅ |
| `conversation_response_blocks` | 响应块 | ✅ |
| `conversation_link_nodes` | 链接节点 | ✅ |
| `cognitive_events` | CognitiveNode 事件日志 | ✅ |
| `knowledge_edges` | Phase 8 知识边表 | ✅ 新表 |
| `conversation_node_links` | 会话↔知识点关联 | ✅ 新表 |

---

## 五、API 端点

| 方法 | 路径 | 功能 | 状态 |
|------|------|------|:--:|
| POST | `/api/v2/classify` | Phase 8 消息分类 | ✅ |
| GET | `/api/v2/graph/nodes` | Phase 8 图节点 | ✅ |
| GET | `/api/v2/graph/search` | Phase 8 图谱搜索 | ✅ |
| GET | `/api/partition-progress/{pid}` | 分区进度画像 | ✅ |
| POST | `/api/practice/submit` | 练习提交 (双写 CognitiveNode) | ✅ |
| GET/POST/PUT | `/api/knowledge/*` | 知识图谱/前置检查 | ✅ |
| POST | `/api/conversation/send` | 对话发送 | ✅ |
| POST | `/api/conversation/v2/secretary/*` | 秘书系统 API | ✅ |
| GET | `/api/data/export` | 数据导出 (隐私合规) | ✅ |
| DELETE | `/api/data/delete` | 遗忘权删除 (隐私合规) | ✅ |
| GET | `/api/study/plan` | 学习计划 | ✅ |
| GET | `/api/search` | 全局搜索 | ✅ |

---

## 六、前端变化 (截至 Phase 8)

| 页面 | 数据源 | 状态 |
|------|--------|:--:|
| 对话页 (侧栏) | Phase 8 知识图谱树 (`/api/v2/graph/nodes`) | ✅ Phase8Sidebar 替代 PartitionSidebar |
| 对话页 (分类卡片) | Phase 8 classify 结果 | ✅ 模式1/2/3 |
| 秘书铃铛 | 秘书 API 提案数 | ✅ SecretaryBellBadge |
| 秘书卡片 | 对话内嵌提案 | ✅ SecretarySuggestionsBlock |
| 秘书设置页 | 模块配置 | ✅ |
| 图谱页 (🧠) | CognitiveNode 掌握度 | ✅ |
| 学情驾驶舱 | cognitive_nodes 覆盖率/趋势/异常 | ✅ |
| 错题本 | CognitiveNode.error_clusters | ✅ |
| 学习计划 | CognitiveNode.scheduling | ✅ |

---

## 七、Phase 完成状态

```
Phase 1 MVP  ─── 工作空间/练习/对话基础   ✅ v0.1
Phase 2 学习画像 ─── 雷达图/日历/遗忘曲线  ✅ v0.2
Phase 3 智能路由 ─── 图谱/边栏/搜索/首页  ✅ v0.2
Phase 4 对话系统 ─── 对话系统重构         ✅ v0.3
Phase 5 认知事件 ─── 事件层/画像层        ✅ v0.3
Phase 6 认知模型 ─── CognitiveNode 全联动 ✅ v0.3
  ├─ 6.1 模型+方程+常量               ✅
  ├─ 6.2 PG 存储+CRUD                 ✅
  ├─ 6.3 事件处理器+对话联动           ✅
  ├─ 6.4 迁移+清理（双源备降架构）      ✅
  ├─ 6.5 PG 默认存储                  ✅
  └─ 全模块联动修复（7个断裂点）        ✅
Phase 7 秘书系统 ─── 诊断/提案/策略/7模块 ✅ v0.4
Phase 8 图谱树 ─── 知识图谱树+分类器+融合 ✅ v0.5
```

---

## 八、旧文档归档

过时设计文档已按 Phase 归档到对应目录：

```
docs/
├── architecture-v3.md          ← 本文件（唯一最新架构设计）
├── PROGRESS.md                  ← 进度跟踪
├── README.md                    ← 文档总入口
├── phase1/                     ← MVP 设计
├── phase2/                     ← 学习画像设计
├── phase3/                     ← 智能路由设计
├── phase4/                     ← 对话系统设计
├── phase5/                     ← 认知事件设计
├── phase6/                     ← CognitiveNode 设计
├── phase7/                     ← 秘书系统 (Secretary) 设计
└── phase8/                     ← 知识图谱树+分类器设计
```
