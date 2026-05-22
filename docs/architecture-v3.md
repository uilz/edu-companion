# 智能伴学系统架构设计 v3.0

> 版本: v3.0
> 最后更新: 2026-05-22
> 状态: **✅ 全部 6 个 Phase 已交付 — 全模块 CognitiveNode 联动已修复**

---

## 交付现状

| 层级 | 模块 | 状态 |
|------|------|:--:|
| ① 事件层 | 对话消息 / 练习提交 / 情绪标记 / 学习时长 / 错题 | ✅ 13 种事件类型 |
| ② 画像层 | CognitiveNode 统一认知模型 (Phase 6) | ✅ 15 子系统 + 22 方程 + 31 列 JSONB |
| ② 画像层 | PartitionProgress 分区进度画像 API | ✅ CognitiveNode 主源 → 旧 JSON 备降 |
| ③ 决策层 | CognitiveNode 18 步事件驱动 Pipeline | ✅ 信念/激活/趋势/疲劳/遗忘/激励/自评/目标/组合/深度/对话/异常 |
| ③ 决策层 | LearningTutor 情境感知决策 | 🔴 待实现 (Phase 7) |
| 数据层 | PG `cognitive_nodes` 表 | ✅ 默认存储开启 |
| 数据层 | PG `knowledge_states` 旧表 | ✅ (备降源, 不删) |
| 数据层 | JSON 存储 | ✅ (`USE_JSON_STORAGE=true` 回滚) |
| 联动 | 练习→CognitiveNode 双写 | ✅ `submit_practice()` |
| 联动 | 图谱→CognitiveNode 同步 | ✅ `_sync_graph_to_cognitive()` |
| 联动 | ZPD 调度→CognitiveNode | ✅ 优先读 CognitiveNode |
| 联动 | 对话→CognitiveNode | ✅ 非流式 + 流式双路径 |
| 联动 | 知识 API→CognitiveNode | ✅ `_BKTKnowledgeAdapter` 主源 |
| 联动 | 学习计划→CognitiveNode | ✅ 优先读 CognitiveNode |

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

图谱生成/编辑 (knowledge_graph.py)
  └─ _sync_graph_to_cognitive() ──→ CognitiveNode (partition/topic/concept/atom)
       └─ 图谱生成 + 节点CRUD + 边CRUD 三入口 ✅
```

---

## 二、三层架构

```
┌──────────────────────────────────────────────────────┐
│ ③ 决策层：LearningTutor                              │
│   "现在推什么？" — 情境感知决策                       │
│   输入: CognitiveNode + StudentProfile + Context     │
│   输出: Action (推题/复习/换学科/鼓励/讲解)            │
│                                                     │
│   已就绪: CognitiveNode 18 步 Pipeline               │
│   待实现: LearningTutor 规则引擎 + ZPD 调度增强       │
└───────────────────────┬──────────────────────────────┘
                        │
┌───────────────────────┴──────────────────────────────┐
│ ② 画像层：CognitiveNode + PartitionProgress          │
│   "学得到底怎么样了？" — 多维学习画像                  │
│                                                     │
│   ├─ CognitiveNode 统一实体 (PG 主存)                │
│   ├─ PartitionProgress API (画像计算 + 缓存)          │
│   ├─ 旧 BKT/knowledge_graphs (备降源)                │
│   └─ 13 种学习事件统计                                │
└───────────────────────┬──────────────────────────────┘
                        │
┌───────────────────────┴──────────────────────────────┐
│ ① 事件层：LearningEvents                              │
│   对话消息 / 练习提交 / 心情标记 / 学习时长 /          │
│   页面停留 / 错题重做间隔 / 考试日程                   │
│                                                     │
│   record_event() → UserData.event_log               │
│   practice_submit → submit_practice() → CognitiveNode│
└──────────────────────────────────────────────────────┘
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

                  ┌─────────────────────────┐
                  │  对话系统 conversati    │
                  │  非流式 + 流式 双路径    │
                  └──────────┬──────────────┘
                             │
                   submit_dialogue_context()
                             │
                             ▼
              CognitiveNode.dialogue_contexts[]

                  ┌─────────────────────────┐
                  │  图谱生成/编辑/删除      │
                  │  knowledge_graph.py     │
                  └──────────┬──────────────┘
                             │
                   _sync_graph_to_cognitive()
                             │
                             ▼
              CognitiveNode (partition→topic→...→atom)

                  ┌─────────────────────────┐
                  │  ZPD 调度器            │
                  │  zpd_scheduler.py      │
                  └──────────┬──────────────┘
                             │
                    estimate_student_ability()
                             │
                    CognitiveNode.belief 优先
                        BKT 备降

                  ┌─────────────────────────┐
                  │  知识 API + 学习计划     │
                  │  knowledge.py / study.py│
                  └──────────┬──────────────┘
                             │
                     get_knowledge_state()
                             │
                    CognitiveNode 优先 → BKT 备降

                  ┌─────────────────────────┐
                  │  AI 上下文 (orchestrator)│
                  └──────────┬──────────────┘
                             │
                     _build_cognitive_context()
                             │
                    CognitiveNode 优先 → old profile
```

---

## 四、数据表设计 (PostgreSQL)

**cognitive_nodes** 表 (31 列, Phase 6 核心)：

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
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (id, user_id)
);

-- 索引
CREATE INDEX idx_cognitive_nodes_user ON cognitive_nodes(user_id);
CREATE INDEX idx_cognitive_nodes_parent ON cognitive_nodes(parent);
CREATE INDEX idx_cognitive_nodes_level ON cognitive_nodes(level);
CREATE INDEX idx_cognitive_nodes_next_review 
    ON cognitive_nodes(((scheduling->>'next_review')::double precision));
```

**其他 PG 表** (存储层):

| 表名 | 用途 | 状态 |
|------|------|:--:|
| `conversation_user_meta` | 用户元数据（全字段持久化） | ✅ |
| `conversation_partitions` | 分区 | ✅ |
| `conversation_branches` | 对话 | ✅ |
| `conversation_nodes` | 消息节点 | ✅ |
| `conversation_response_blocks` | 响应块 | ✅ |
| `conversation_link_nodes` | 链接节点 | ✅ |
| `cognitive_events` | CognitiveNode 事件日志 | ✅ |

---

## 五、API 端点

| 方法 | 路径 | 功能 | 状态 |
|------|------|------|:--:|
| GET | `/api/partition-progress/{pid}` | 分区进度画像 (CognitiveNode 主源) | ✅ |
| POST | `/api/practice/submit` | 练习提交 (双写 CognitiveNode) | ✅ |
| POST | `/api/practice/generate` | 练习生成 | ✅ |
| GET/POST/PUT | `/api/knowledge/*` | 知识图谱/前置检查 (CognitiveNode 主源) | ✅ |
| GET | `/api/learning-events/stats/{pid}` | 学习事件统计 | ✅ |
| GET | `/api/learning-events/daily/{pid}` | 按天指标 | ✅ |
| POST | `/api/knowledge-graph/{pid}/generate` | AI 生成图谱 (联动 CognitiveNode) | ✅ |
| PUT | `/api/knowledge-graph/{pid}/nodes` | 节点 CRUD (联动 CognitiveNode) | ✅ |
| PUT | `/api/knowledge-graph/{pid}/edges` | 边 CRUD (联动 CognitiveNode) | ✅ |
| POST | `/api/conversation/send` | 对话发送 (联动 CognitiveNode) | ✅ |
| GET | `/api/study/plan` | 学习计划 (CognitiveNode 主源) | ✅ |
| GET | `/api/search` | 全局搜索 (CognitiveNode + PG) | ✅ |
| GET | `/api/progress/{uid}` | 进度总览 | ✅ |

---

## 六、前端变化

| 页面 | 数据源 | 状态 |
|------|--------|:--:|
| 图谱页 (🧠) | `PartitionProgress` + CognitiveNode 掌握度 | ✅ |
| 学情驾驶舱 | `cognitive_nodes` → 覆盖率/趋势/异常 | ✅ |
| 错题本 | `CognitiveNode.error_clusters` | ✅ |
| 学习计划 | `CognitiveNode.scheduling` | ✅ |
| 对话 | cognitive contexts 标注 | ✅ |

---

## 七、Phase 完成状态

```
Phase 1 MVP  ─── 工作空间/练习/对话基础   ✅
Phase 2 学习画像 ─── 雷达图/日历/遗忘曲线  ✅
Phase 3 智能路由 ─── 图谱/边栏/搜索/首页  ✅
Phase 4 对话系统 ─── 对话系统重构          ✅
Phase 5 认知事件 ─── 事件层/画像层         ✅
Phase 6 认知模型 ─── CognitiveNode 全联动  ✅
  ├─ 6.1 模型+方程+常量                   ✅
  ├─ 6.2 PG 存储+CRUD                     ✅
  ├─ 6.3 事件处理器+对话联动              ✅
  ├─ 6.4 迁移+清理（双源备降架构）         ✅
  ├─ 6.5 PG 默认存储                      ✅
  └─ 全模块联动修复（7个断裂点）           ✅
Phase 7 LearningTutor 决策层              🔴 待开始
```

---

## 八、旧文档归档

过时设计文档已按 Phase 归档到对应目录：

```
docs/
├── architecture-v3.md          ← 本文件（唯一最新设计）
├── PROGRESS.md                  ← 进度跟踪
├── phase1/                     ← MVP 设计
├── phase2/                     ← 学习画像设计
├── phase3/                     ← 智能路由设计
├── phase4/                     ← 对话系统设计
├── phase5/                     ← 认知事件设计
├── phase6/                     ← CognitiveNode 设计
└── phase7/ (待建)              ← LearningTutor 设计
```
