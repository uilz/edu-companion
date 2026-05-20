# 智能伴学系统架构设计 v3.0

> 版本: v3.0  
> 最后更新: 2026-05-19  
> 状态: **✅ 核心已交付 — 画像层 + 事件层 + 前端图谱已完成**

---

## 交付现状

| 层级 | 模块 | 状态 |
|------|------|:--:|
| ① 事件层 | LearningEvent 记录 + 会话标注 + 练习挂钩 | ✅ |
| ② 画像层 | PartitionProgress API（覆盖率/技能/异常/时序） | ✅ |
| ② 画像层 | SkillAtom / StudentProfile schema | ✅ |
| ③ 决策层 | LearningTutor（情境感知决策） | 🔴 待实现 |
| 数据层 | PG `skill_atoms` 独立表 | 🔴 待实现 |
| 前端 | GraphTab 切换到 PartitionProgress | ✅ |

---

## 一、问题诊断（v2.0 架构缺陷）

v2.0 的核心问题是**三个模块各自维护一份「同一个知识点」的表示，靠约定 ID 一致来连接**，没有任何强制外键或类型安全：

```
图谱 KGNode(id="calculus")  ─┐
BKT state("calculus")       ─┼─ 三个独立对象，约定同名
练习题 skill_id="calculus"  ─┘
```

导致 12 个具体缺陷：

| # | 缺陷 | 后果 |
|---|------|------|
| 1 | 图谱节点 ID 与 BKT 技能 ID 靠约定对齐，不强制 | 掌握度可能完全错误 |
| 2 | 三个「学习状态」源（BKT / SharedState / GraphNode）| 同一个问题三个答案 |
| 3 | 图谱节点无练习历史 | 查练习数据需跨表联查，无外键 |
| 4 | 会话消息不引用图谱节点 | 无法回答「我们聊过什么关于 X」 |
| 5 | 分支练习总结是自由文本字符串 | 无法结构化查询 |
| 6 | BKT 全局平面，图谱按分区隔离 | 同技能跨分区共享 BKT，不准确 |
| 7 | SharedKnowledgeState 在内存中，重启丢失 | 融合掌握度不可靠 |
| 8 | AI 上下文是文本拼接，不是结构化视图 | 10 个源各自独立拼 |
| 9 | 无学习全景 API | 前端需调 5+ 端点拼画像 |
| 10 | AI 生成图谱时不知道 BKT 数据 | 重复生成已掌握节点 |
| 11 | 练习结果不反馈图谱 | 无 priority 调整、无依赖关系验证 |
| 12 | 分区/分支承载太多语义 | 垃圾桶字段集合 |

---

## 二、v3.0 架构：三层 + SkillAtom 统一实体

```
┌──────────────────────────────────────────────────────┐
│ ③ 决策层：LearningTutor                              │
│   "现在推什么？" — 情境感知决策                       │
│   输入: StudentProfile + LearningContext              │
│   输出: Action (推题/复习/换学科/鼓励/讲解)            │
└───────────────────────┬──────────────────────────────┘
                        │
┌───────────────────────┴──────────────────────────────┐
│ ② 画像层：StudentProfile                             │
│   "学得到底怎么样了？" — 多维学习画像                  │
│   ├─ partition_progresses[pid] → PartitionProgress    │
│   ├─ cognitive_state（精力/情绪/节奏）                │
│   ├─ forgetting_curves（遗忘状态）                    │
│   └─ temporal_metrics（时间维度）                     │
└───────────────────────┬──────────────────────────────┘
                        │
┌───────────────────────┴──────────────────────────────┐
│ ① 事件层：LearningEvents (原始行为记录)               │
│   对话消息 / 练习提交 / 心情标记 / 学习时长 /         │
│   页面停留 / 错题重做间隔 / 考试日程                   │
└──────────────────────────────────────────────────────┘
```

### 核心实体：SkillAtom

**所有表示「同一个知识点」的模块只读/写这一个实体**。图谱是它的投影，BKT 是它的字段，练习是它的更新事件，会话是它的引用。

```python
class SkillAtom(BaseModel):
    """原子学习单元 — 唯一的「知识点」实体"""
    
    # ── 身份 ──
    id: str                              # "calc-derivatives"
    label: str                           # "导数"
    description: str                     # 一句话定义
    partition_id: str                    # 所属分区
    created_by: str                      # "ai" | "user"
    
    # ── 图谱属性 ──
    priority: int = 5                    # 学习优先级 1-10
    depth: int = 0                       # 拓扑层级（自动计算）
    prerequisites: list[str]             # 前置 SkillAtom ID
    unlocks: list[str]                   # 解锁的后继
    
    # ── BKT 掌握度（直接嵌入，不另存）──
    bkt_p_know: float = 0.1
    bkt_p_learn: float = 0.3
    bkt_p_guess: float = 0.25
    bkt_p_slip: float = 0.1
    mastery: float = 0.0
    mastery_level: str = "未接触"
    confidence: float = 0.0              # BKT 观测信度（样本少 → 低）
    
    # ── 练习历史（汇总在实体上）──
    attempt_count: int = 0
    correct_count: int = 0
    last_practiced: datetime | None = None
    time_spent_minutes: float = 0.0
    error_clusters: list[str] = []       # 高频错误模式
    
    # ── 趋势 ──
    trend: str = "stable"                # improving | stable | declining | plateau
    stagnation_days: int = 0
    velocity: float = 0.0                # 掌握度变化/周
    
    # ── 遗忘 ──
    forgetting_curve: float = 1.0        # 艾宾浩斯遗忘因子（1=刚学）
    review_urgency: float = 0.0          # 复习紧迫度 0-1
    
    # ── 时间戳 ──
    created_at: datetime
    updated_at: datetime
```

---

## 三、分区进度画像 (PartitionProgress)

对每个分区构建完整学习地图。**这是前端图谱页和驾驶舱的单一数据源。**

```python
class PartitionProgress(BaseModel):
    """一个分区的完整学习进度画像"""
    partition_id: str
    generated_at: datetime
    
    # ── 覆盖率 ──
    coverage: Coverage
    
    # ── 技能节点（带着学生真实数据）──
    skills: dict[str, SkillNodeState]
    
    # ── 依赖关系 ──
    dependencies: list[Dependency]
    
    # ── 学习路径 ──
    learning_path: LearningPath
    
    # ── 技能聚类 ──
    clusters: list[SkillCluster]
    
    # ── 异常 ──
    anomalies: list[Anomaly]
    
    # ── 时间维度 ──
    temporal: TemporalMetrics


class Coverage:
    total: int = 0
    touched: int = 0       # 接触过（有练习或对话）
    assessed: int = 0      # 有足够 BKT 数据
    mastered: int = 0
    learning: int = 0
    weak: int = 0
    untouched: int = 0


class SkillNodeState(BaseModel):
    """知识点在该学生身上的完整状态"""
    skill_id: str
    label: str
    description: str
    
    # 掌握度
    mastery: float = 0.0
    mastery_level: str = "未接触"
    confidence: float = 0.0
    trend: str = "stable"
    
    # DAG 位置
    depth: int = 0
    prerequisites: list[str] = []
    prerequisites_met: bool = False
    blocked: bool = True
    
    # 练习
    attempt_count: int = 0
    correct_count: int = 0
    last_practiced: datetime | None = None
    error_clusters: list[str] = []
    
    # 遗忘
    forgetting_curve: float = 1.0
    review_urgency: float = 0.0


class Dependency:
    from_skill: str
    to_skill: str
    relation: str        # prerequisite | builds_on | analogy | confusion_risk
    satisfied: bool      # from_skill 是否已满足
    student_deviation: str | None


class LearningPath:
    ideal_order: list[str]
    actual_order: list[str]
    deviations: list[PathDeviation]
    frontier: list[str]         # 下一步该学
    review_queue: list[str]     # 该复习


class SkillCluster:
    skills: list[str]
    correlation: float
    type: str                   # co-mastered | co-weak | co-confused
    interpretation: str


class Anomaly:
    type: str     # mastered_without_prereq | long_stagnation | rapid_forgetting
    skills: list[str]
    detail: str
    severity: str  # warning | info


class TemporalMetrics:
    learning_velocity: float           # 每周掌握技能数
    estimated_completion_days: int
    review_backlog: int
    daily_practice_minutes: float
```

---

---

## 三-B、事件层 Schema（实现中）

```python
from enum import StrEnum

class EventType(StrEnum):
    PRACTICE_SUBMIT = "practice_submit"
    PRACTICE_SESSION_START = "practice_session_start"
    PRACTICE_SESSION_COMPLETE = "practice_session_complete"
    CONVERSATION_MESSAGE = "conversation_message"
    SKILL_DISCUSSED = "skill_discussed"
    SKILL_MASTERY_CHANGED = "skill_mastery_changed"
    BRANCH_CREATED = "branch_created"
    PARTITION_SWITCHED = "partition_switched"
    EMOTION_DETECTED = "emotion_detected"
    FRUSTRATION_PEAK = "frustration_peak"
    GRAPH_GENERATED = "graph_generated"
    REVIEW_RECOMMENDED = "review_recommended"

class LearningEvent(BaseModel):
    id: str
    user_id: str
    type: EventType
    timestamp: datetime
    partition_id: Optional[str] = None
    skill_ids: list[str] = []
    data: dict = {}       # 载荷（{correct, time_spent, before, after, ...}）
    event_date: str        # "2026-05-19" 方便按天聚合
    event_hour: int        # 0-23 方便统计高峰时段

class DailyMetrics(BaseModel):
    date: str
    practice_minutes: float
    practice_count: int
    correct_count: int
    conversations: int
    skills_covered: list[str]
```

## 四、数据流

### 4.0 事件采集（新）

```
所有学习行为 → record_event() → UserData.event_log

对话完成 → send_and_reply
  └─ [来源: xxx] → _resolve_skill_ids() → TreeNode.discussed_skill_ids
     └─ record_event(SKILL_DISCUSSED, skill_ids=[...])

练习提交 → submit_answer
  ├─ record_event(PRACTICE_SUBMIT, {correct, time_spent})
  └─ 掌握度变化 >5% → record_event(SKILL_MASTERY_CHANGED, {before, after})

事件存储：
  - 位置: UserData.event_log（JSON 数组，最多 500 条自动裁剪）
  - 查询: GET /api/learning-events/stats/{pid}?days=7
  - 按天: GET /api/learning-events/daily/{pid}?days=7
  - 13 种事件类型: practice_submit/session_start/complete | conversation_message
    | skill_discussed | skill_mastery_changed | branch_created | partition_switched
    | emotion_detected | frustration_peak | graph_generated | review_recommended
```

### 4.1 练习 → 反馈图谱

```
POST /api/practice/submit {skill_id, answer}
  │
  ├─ SkillAtom[skill_id].attempt_count += 1
  ├─ BKT.update() → SkillAtom[skill_id].mastery 更新
  ├─ 检查趋势：连续N次 → velocity 更新
  ├─ 检查遗忘：last_practiced → forgetting_curve 更新
  ├─ 异常检测：
  │   ├─ 5次连续错但前置mastery>80% → "依赖关系可能错误"
  │   ├─ 7天stagnation → "学习平台期"
  │   └─ 已掌握(>85%)但priority仍高 → "priority建议降低"
  └─ 触发异步 → 生成建议列表（不自动改，需确认）
```

### 4.2 图谱 → 会话注入

```
AI 对话时注入（不再拼10个源）:
  GET /api/partition-progress/{pid}
  → PartitionProgress
  → 格式化为结构化上下文:
  
  📊 [分区: 高等数学] 覆盖率: 7/12 已接触, 3 已掌握
  ✅ 已掌握: limits(92%) · continuity(88%) · basic_functions(85%)
  🔶 发展中: derivatives(54%, 趋势↑) · chain_rule(48%, 停滞4天⚠️)
  ⬜ 未接触: integrals(前置未满足🔒) · series · multivariable
  🎯 建议: 巩固 chain_rule → 解锁 integrals
  ⏰ 复习压力: limits 遗忘因子0.7（建议3天内复习）
```

### 4.3 会话标注知识点

```python
class TreeNode:
    # 新增字段
    discussed_skill_ids: list[str] = []  # AI 回复自动标注
```

> System prompt 要求 AI 每次回答后标注涉及的知识点。这是自动行为，用户无感。

结果：
- 「关于导数我们聊过什么？」→ 查 `discussed_skill_ids` 含 `derivatives` 的消息
- 「哪些聊得多但练得少？」→ 讨论频次 vs attempt_count
- 学习热力图：partition 下每个 SkillAtom 被讨论次数

---

## 五、API 端点

| 方法 | 路径 | 功能 | 状态 |
|------|------|------|:--:|
| GET | `/api/partition-progress/{partition_id}` | **分区完整进度画像** | ✅ |
| GET | `/api/learning-events/stats/{pid}?days=7` | 分区事件统计 | ✅ |
| GET | `/api/learning-events/daily/{pid}?days=7` | 按天指标 | ✅ |
| GET | `/api/student-profile` | 全科学习画像 | 🔴 |
| GET | `/api/skill-atoms?partition_id=xxx` | 旧图谱兼容 | 🔴 |
| POST | `/api/skill-atoms/{pid}/generate` | AI 生成知识点 | 🔴 |
| PUT | `/api/skill-atoms/{pid}/nodes` | 节点 CRUD | 🔴 |
| PUT | `/api/skill-atoms/{pid}/edges` | 依赖边 CRUD | 🔴 |

---

## 六、前端变化

### 图谱页（Dashboard 🧠Tab）

**数据源**：`GET /api/partition-progress/{pid}` → `PartitionProgress`

```typescript
// 从 SkillNodeState[] 计算图谱渲染数据
const nodes = pp.skills.map(s => ({
  id: s.skill_id,
  label: s.label,
  mastery: s.mastery,
  masteryLevel: s.mastery_level,
  blocked: s.blocked,
  anomaly: pp.anomalies.find(a => a.skills.includes(s.skill_id)),
}));
const edges = pp.dependencies.map(d => ({
  from: d.from_skill,
  to: d.to_skill,
  satisfied: d.satisfied,
}));
```

其他 tab 的变化：
- **概览** → 各分区 coverage 卡片
- **学情** → PartitionProgress 的趋势图表
- **错题** → SkillAtom.error_clusters 汇总

---

## 七、数据表设计（PostgreSQL）

```
skill_atoms (
  id            TEXT PRIMARY KEY,
  partition_id  TEXT NOT NULL,
  label         TEXT NOT NULL,
  description   TEXT,
  priority      INT DEFAULT 5,
  depth         INT DEFAULT 0,
  bkt_p_know    FLOAT DEFAULT 0.1,
  bkt_p_learn   FLOAT DEFAULT 0.3,
  bkt_p_guess   FLOAT DEFAULT 0.25,
  bkt_p_slip    FLOAT DEFAULT 0.1,
  mastery       FLOAT DEFAULT 0,
  mastery_level TEXT DEFAULT '未接触',
  confidence    FLOAT DEFAULT 0,
  attempt_count INT DEFAULT 0,
  correct_count INT DEFAULT 0,
  last_practiced TIMESTAMPTZ,
  error_clusters JSONB DEFAULT '[]',
  trend         TEXT DEFAULT 'stable',
  forgetting_curve FLOAT DEFAULT 1.0,
  review_urgency FLOAT DEFAULT 0,
  created_by    TEXT DEFAULT 'ai',
  created_at    TIMESTAMPTZ DEFAULT NOW(),
  updated_at    TIMESTAMPTZ DEFAULT NOW()
);

skill_dependencies (
  from_skill  TEXT REFERENCES skill_atoms(id),
  to_skill    TEXT REFERENCES skill_atoms(id),
  relation    TEXT DEFAULT 'prerequisite',
  PRIMARY KEY (from_skill, to_skill)
);

-- TreeNode 加列
ALTER TABLE conversation_nodes ADD COLUMN discussed_skill_ids JSONB DEFAULT '[]';
```

---

## 八、迁移路径

| 步骤 | 内容 | 风险 | 状态 |
|------|------|------|:--:|
| 1 | 创建 `SkillAtom` / `PartitionProgress` Schema | 低 | ✅ |
| 2 | 创建 PG 表 `skill_atoms` + `skill_dependencies` | 低 | 🔴 |
| 3 | 迁移脚本：旧 `knowledge_graphs` + `knowledge_states` → `skill_atoms` | 中 | 🔴 |
| 4 | 实现 `GET /api/partition-progress/{pid}`（兼容旧数据） | 低 | ✅ |
| 5 | 旧图谱 API 保留兼容层 | 低 | ✅（内部转发） |
| 6 | 前端 GraphTab 切换到新数据源 | 中 | ✅ |
| 7 | `TreeNode.discussed_skill_ids` + 事件记录 + AI prompt | 低 | ✅ |
| 8 | 删旧存储：`knowledge_graphs` / `knowledge_states` / `SharedKnowledgeState` | 低 | 🔴 |

已完成 5/8。API 接口保持向后兼容。剩余 3 项（PG 表 / 正式迁移 / 清理旧存储）可在数据积累后执行。
