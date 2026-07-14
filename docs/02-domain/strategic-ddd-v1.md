# AppleGo Strategic DDD Document v1

> 版本: v1.0.0 | 创建于: 2026-07-13
>
> **定位**: 苹果果 V1 战略领域驱动设计文档。本文件是 V1 所有 Domain Model、Bounded Context、Event Storming 的冻结版本。
>
> **冻结声明**: 本文档定义的所有 Aggregate、BC 边界、Invariants 在 V1 开发周期内（PR-004 ~ PR-005）不再变更。新增领域对象必须在 V2 ADR 中提案。

---

## 一、Bounded Context Map（上下文映射总图）

```
┌──────────────────────────────────────────────────────────────────────┐
│                                                                        │
│  ┌──────────────────┐                                                 │
│  │   Auth BC        │──── 通用域，独立进程（18001）                     │
│  │   AR: User       │                                                 │
│  │   - login/jwt    │                                                 │
│  │   - register     │                                                 │
│  └────────┬─────────┘                                                 │
│           │ user_id === learner_id                                     │
│           │ Conformist（Auth 不消费 Learner 事件）                     │
│           ▼                                                           │
│  ┌──────────────────────────────────────────────────────────────┐     │
│  │                   Learner BC (Core)                           │     │
│  │                                                               │     │
│  │  聚合根 (AR):                                                  │     │
│  │  ┌─ Learner ───────────────────────────────────────────┐     │     │
│  │  │  ├─ Persona (Entity)        半年改一次                   │     │
│  │  │  ├─ Preferences (Value)     一月改一次                   │     │
│  │  │  └─ MemoryEntry[] (Value)   每次 Session 完成后追加      │     │
│  │  └────────────────────────────────────────────────────┘     │     │
│  │                                                               │     │
│  │  领域服务:                                                     │     │
│  │    ├─ PersonaAnalyzer（基于 Memory 定期重算画像）               │     │
│  │    └─ MemoryEngine（监听 SessionCompleted → 写入 MemoryEntry） │     │
│  │                                                               │
│  │  发布事件: LearnerModelUpdated                                 │     │
│  │  订阅事件: SessionCompleted（→ MemoryEngine）                  │     │
│  └──────────────────────────────────────────────────────────┘     │     │
│           │                                                        │     │
│           │ Customer/Supplier                                       │     │
│           │ (Learning BC 通过 learner_id 引用 Learner)              │     │
│           ▼                                                        │     │
│  ┌──────────────────────────────────────────────────────────────┐     │
│  │                   Learning BC (Core)                          │     │
│  │                                                               │     │
│  │  聚合根 (AR):                                                  │     │
│  │  ┌─ Goal ──────────────────────────────────────────────┐     │     │
│  │  │  ├─ title / description (Value)                          │     │
│  │  │  ├─ status: active|completed|abandoned (Value)           │     │
│  │  │  ├─ target_module / target_metric (Value)                │     │
│  │  │  ├─ progress_pct (computed, 不可直接设置)                  │     │
│  │  │  └─ learner_id (Reference)                               │     │
│  │  │     一月改一次                                               │     │
│  │  └────────────────────────────────────────────────────────┘     │     │
│  │                                                               │     │
│  │  ┌─ Session ────────────────────────────────────────────┐     │     │
│  │  │  ├─ stage: intro→learn→practice→reflect (Value)          │     │
│  │  │  ├─ status: active|completed|cancelled (Value)            │     │
│  │  │  ├─ mission (SessionMission, Value)                       │     │
│  │  │  ├─ reflection (Reflection, Value)                        │     │
│  │  │  ├─ conversation_id (Reference, 内部交互组件)               │     │
│  │  │  ├─ goal_id / recommendation_id (Reference)               │     │
│  │  │  └─ learner_id (Reference)                                │     │
│  │  │     一分钟改一次                                               │     │
│  │  └────────────────────────────────────────────────────────┘     │     │
│  │                                                               │     │
│  │  Projection (Read Model):                                      │     │
│  │  └─ GrowthTimeline（GrowthProjector 监听 SessionCompleted）    │     │
│  │                                                               │     │
│  │  领域服务:                                                     │     │
│  │  └─ GrowthProjector（SessionCompleted → GrowthRecord）         │     │
│  │                                                               │     │
│  │  发布事件: SessionCreated, SessionStageChanged,                 │     │
│  │            ReflectionGenerated, SessionCompleted,               │     │
│  │            GrowthRecordCreated                                  │     │
│  └──────────────────────────────────────────────────────────┘     │     │
│           │                                                        │     │
│           │ Customer/Supplier                                       │     │
│           │ (Rec 为 Session 提供创建参数)                           │     │
│           ▼                                                        │     │
│  ┌──────────────────────────────────────────────────────────────┐     │
│  │              Recommendation BC (Supporting)                   │     │
│  │                                                               │     │
│  │  聚合根 (AR):                                                  │     │
│  │  ┌─ Recommendation ─────────────────────────────────────┐     │     │
│  │  │  ├─ focus / reason (Value)                               │     │
│  │  │  ├─ predicted_growth (Value)                             │     │
│  │  │  ├─ priority: high|medium|low (Value)                    │     │
│  │  │  ├─ status: generated→accepted→expired (Value)           │     │
│  │  │  ├─ accepted 一旦写入不可变 (Invariant)                     │     │
│  │  │  ├─ consumed_by: session_id|null (Reference)             │     │
│  │  │  └─ learner_id (Reference)                               │     │
│  │  │     一天生成一次                                             │     │
│  │  └────────────────────────────────────────────────────────┘     │     │
│  │                                                               │     │
│  │  领域服务:                                                     │     │
│  │  └─ RecommendationEngine（输入: Learner + Memory + Goals）    │     │
│  │                                                               │     │
│  │  发布事件: RecommendationGenerated, RecommendationAccepted     │     │
│  │  订阅事件: LearnerModelUpdated（→ 触发重算推荐）                │     │
│  └──────────────────────────────────────────────────────────────┘     │
│                                                                        │
└──────────────────────────────────────────────────────────────────────┘
```

### BC 与现有实现映射

| BC | 当前实现 | 差距 |
|----|---------|------|
| **Auth BC** | `auth-gateway/` 独立进程 | 稳定，无需修改 |
| **Learner BC** | `shared/learner_model.py` | 需暴露 Persona API + MemoryEntry 写入 |
| **Learning BC** | PR-002b (Session) + `services/planning/goals.py` (Goal) | Session AR 已完成；Goal AR API 已存在；GrowthProjector 已实现 |
| **Recommendation BC** | `api/system/secretary.py` Dashboard 动态生成 | ⚠️ **Tentative（待验证）**：当前仅为 Dashboard 动态计算，无 Repository/独立生命周期。PR-004/PR-005 期间观察后决定是否升级为独立 BC 或降级为 Application Service |

---

## 二、Aggregate Map（聚合图）

### 2.1 聚合清单

| BC | Aggregate Root | 实体/值对象 | 谁创建它 | 谁可以修改它 |
|----|---------------|-----------|---------|------------|
| Learner BC | **Learner** | Persona, Preferences, MemoryEntry[] | 用户注册时 | PersonaAnalyzer（重算）、MemoryEngine（追加） |
| Learning BC | **Goal** | — | 用户通过 API | 用户通过 API（PATCH） |
| Learning BC | **Session** | SessionMission, Reflection | RecommendationAccepted → SessionService | SessionService.transition_stage() |
| Recommendation BC | **Recommendation** | — | RecommendationEngine | 仅 accepted（用户点"开始今天"一次性写入） |

### 2.2 每个 AR 的修改入口证明

**Goal AR 的独立修改入口**：`PATCH /api/planning/goals/{goal_id}`
- 代码证据：[goals.py](file:///home/deploy/edu-companion/backend/app/services/planning/goals.py)
- Goal 可以被独立更新（title/description/status），不需要通过任何上层对象。

**Session AR 的独立修改入口**：`POST /api/session` → `PATCH /api/session/{id}/stage`
- 代码证据：[session.py](file:///home/deploy/edu-companion/backend/app/api/session/session.py)
- Session 有独立生命周期管理，不通过 Learner 或 Goal 间接修改。

**Mission 为什么不是 AR（V1）**：
- 当前代码中 Mission 仅作为 Session 内部值对象存在：`SessionMission` 是一个 `@dataclass`
- 没有独立的 Mission 数据库表、API 端点或服务
- Mission 的 progress/steps 通过 Session 的 `set_mission()` 方法操作，不是独立入口
- V1 中 Mission 作为 Session 值对象足以支持产品需求（跨 Session 连续性通过 Goal 的 Session 列表追踪）

### 2.3 Memory 为什么不是 AR

- KnowledgeMemory、BehaviorMemory、PreferenceMemory、ReflectionMemory 全是追加型写入
- 四种 Memory 之间不存在跨类型的事务一致性约束
- 没有 "修改 Memory" 的场景（append-only）
- 因此 MemoryEntry 是 Learner 聚合根下的值对象集合，不是独立 AR

---

## 三、Aggregate Interaction（聚合交互）

```
用户打开 Today
  │
  ▼
RecommendationEngine.generate()
  │  输入: Learner.persona + Learner.memories + Goal[]
  │  创建 Recommendation (status=generated)
  │  发布 RecommendationGenerated
  │
  ▼
用户点击 "开始今天"
  │  Recommendation.accept(session_id)
  │  发布 RecommendationAccepted
  │
  ▼
SessionService.create_session({recommendation_id, goal_id, learner_id})
  │  创建 Session AR (status=active, stage=intro)
  │  发布 SessionCreated
  │
  ▼
SessionService.transition_stage(learn → practice → reflect)
  │  发布 SessionStageChanged
  │
  ▼
SessionService.complete_session()
  │  Session.status = "completed"
  │  发布 SessionCompleted  ─────────────┐
  │                                      │
  ▼                                      ▼
Learn BC 内部:                    Learner BC:
  GrowthProjector.on(SessionCompleted)   MemoryEngine.on(SessionCompleted)
    → 追加 GrowthRecord                    → 追加 MemoryEntry
    → 发布 GrowthRecordCreated
```

**原则**：AR 之间通过事件异步通信，不在同一事务中修改对方的聚合。

---

## 四、Domain Events

### 4.1 事件清单

| # | 事件名 | 发布方 | 消费方 | 优先级 |
|---|--------|--------|--------|--------|
| 1 | `RecommendationGenerated` | Recommendation BC | Today 页面 | P1 |
| 2 | `RecommendationAccepted` | Recommendation BC | Learning BC (Session 创建) | P1 |
| 3 | `SessionCreated` | Learning BC | GrowthProjector | P1 |
| 4 | `SessionStageChanged` | Learning BC | GrowthProjector | P1 |
| 5 | `ReflectionGenerated` | Learning BC | GrowthProjector | P1 |
| 6 | `SessionCompleted` | Learning BC | GrowthProjector, MemoryEngine | P0 |
| 7 | `GrowthRecordCreated` | Learning BC | Growth 页面 | P2 |
| 8 | `LearnerModelUpdated` | Learner BC | RecommendationEngine | P2 |
| 9 | `AnswerSubmitted` | Learning BC (通过 Cognitive) | BKT, GrowthProjector | 复用现有 |
| 10 | `CognitiveStateChanged` | Learning BC (通过 Cognitive) | BKT | 复用现有 |

### 4.2 事件 Schema

```python
# shared/events.py — 新增事件

@dataclass(frozen=True)
class RecommendationGenerated(DomainEvent):
    recommendation_id: str    # rec_xxx
    learner_id: str
    goal_id: str              # 来自哪个 Goal
    focus: str                # "Iterator"
    reason: str               # AI 推荐理由
    predicted_growth: dict    # {skill, before, after}
    estimated_minutes: int
    priority: str             # high|medium|low

@dataclass(frozen=True)
class RecommendationAccepted(DomainEvent):
    recommendation_id: str
    session_id: str

@dataclass(frozen=True)
class SessionCreated(DomainEvent):
    session_id: str
    learner_id: str
    goal_id: str | None
    recommendation_id: str | None

@dataclass(frozen=True)
class SessionStageChanged(DomainEvent):
    session_id: str
    old_stage: str | None
    new_stage: str            # intro|learn|practice|reflect

@dataclass(frozen=True)
class ReflectionGenerated(DomainEvent):
    session_id: str
    content: str
    key_takeaways: list[str]
    next_steps: list[str]

@dataclass(frozen=True)
class GrowthRecordCreated(DomainEvent):
    session_id: str
    record_id: str
    growth_items: list[dict]  # [{skill, before, after, evidence}]
    summary: str

@dataclass(frozen=True)
class LearnerModelUpdated(DomainEvent):
    learner_id: str
    updated_fields: list[str]
```

---

## 五、Command Model（命令模型）

| 命令 | 发起方 | 目标 AR | 操作 |
|------|--------|---------|------|
| `CreateRecommendation` | Today 页面 | Recommendation | 生成新的推荐 |
| `AcceptRecommendation` | 用户点"开始今天" | Recommendation | recommendation.accepted = true |
| `CreateSession` | RecommendationAccepted 后 | Session | 创建 Session AR |
| `TransitionStage` | AI / 用户触发 | Session | session.stage 前移 |
| `CompleteSession` | reflect 阶段结束 | Session | session.status = "completed" |
| `AppendMemory` | SessionCompleted 事件 | Learner | 追加 MemoryEntry |
| `RecalculatePersona` | 定时 / LearnerModelUpdated | Learner | 重算 persona.type |

---

## 六、Read Model（读模型）

### 6.1 GrowthTimeline

```
来源: SessionCompleted → GrowthProjector → GrowthRecord
消费方: Growth 页面 (GET /api/growth/records)
        Today 页面 (GET /api/growth/latest, 显示上次学习后的成长)
        Profile 页面 (GET /api/growth/summary, 累计统计)

特性: append-only, immutable, 永远不 UPDATE
```

### 6.2 Today View

```
来源: GET /api/recommendations/latest (最新 Recommendation)
      + GET /api/growth/latest (最近成长快照)
      + GET /api/goals?status=active (当前目标)
消费方: Today 页面 (/)

非持久化, 组合查询, 无独立 Read Model 表
```

### 6.3 Profile View

```
来源: GET /api/learner/profile (Persona + Preferences)
      + GET /api/growth/summary (累计成长统计 + streak)
      + GET /api/goals (Goal 列表)
消费方: Profile 页面 (/profile)

非持久化, 组合查询
```

### 6.4 GrowthRecord (内部)

```python
# backend/app/domain/growth/models.py — 冻结不变

@dataclass(frozen=True)
class GrowthRecord:
    id: str
    session_id: str
    learner_id: str
    items: tuple[SkillGain, ...]    # tuple, immutable
    summary: str
    next_steps: list[str]
    created_at: float

    # NOT Aggregate. Projection (Read Model).
    # Only created by GrowthProjector.
    # Never updated. Never deleted.
```

---

## 七、Context Relationships（上下文关系）

| 上游 (U) → 下游 (D) | 关系类型 | 规则 |
|---------------------|---------|------|
| Auth BC → Learner BC | **Conformist** | Learner BC 通过 user_id 引用 User，不消费 Auth 事件 |
| Learner BC → Learning BC | **Customer/Supplier** | Learning BC 通过 learner_id 引用 Learner，不等待 Learner 变更 |
| Learning BC → Learner BC | **Event Listener** | SessionCompleted 事件 → MemoryEngine 写入 MemoryEntry |
| Recommendation BC → Learning BC | **Customer/Supplier** | Session 消费 Recommendation 的 accepted 状态 |
| Learner BC → Recommendation BC | **Event Listener** | LearnerModelUpdated 事件 → RecommendationEngine 重新计算推荐 |

**没有 ACL（防腐层）需求**。四个 BC 共享统一的 Ubiquitous Language（统一语言附录 A），不需要翻译。

---

## 八、Transaction Boundaries（事务边界）

| 事务 | 涉及对象 | 是否跨 AR | 一致性策略 |
|------|---------|----------|-----------|
| 创建 Session | Session AR | 否 (单 AR) | 同步事务 |
| 切换 Stage | Session AR | 否 (单 AR) | 同步事务 |
| 完成 Session | Session AR | 否 (单 AR) | 同步事务 |
| Session → GrowthRecord | Session AR → GrowthRecord (Projection) | 异步 | Event：SessionCompleted → GrowthProjector |
| Session → MemoryEntry | Session AR → Learner AR | 异步 | Event：SessionCompleted → MemoryEngine |
| 接受 Recommendation | Recommendation AR | 否 (单 AR) | 同步事务 |
| Recommendation → 创建 Session | Rec AR → Session AR | 异步 | Event：RecommendationAccepted → CreateSession |

**V1 不使用分布式事务**。跨聚合的一致性通过 Eventual Consistency（最终一致性）保证。

---

## 九、Invariants（领域不变量）

> **每次有人违反下面任何一条，就是 Bug。**

### 9.1 Session 不变量

| # | 不变量 | 实施位置 |
|---|--------|---------|
| S1 | Session 必须属于且只属于一个 Learner | Session.learner_id NOT NULL |
| S2 | Session.stage 单调不可逆：intro → learn → practice → reflect | Session.transition_stage() 拒绝回退 |
| S3 | Session.status 只能 active → completed，completed 后不可修改 | Session.complete_session() 检查 |
| S4 | Session.conversation_id 是内部实现细节，不暴露为独立 API | Session API 不暴露 conversation CRUD |
| S5 | Reflection 只能在 reflect 阶段写入 | SessionService.reflect() 检查 stage |

### 9.2 Goal 不变量

| # | 不变量 | 实施位置 |
|---|--------|---------|
| G1 | Goal 必须属于一个 Learner | Goal.learner_id NOT NULL |
| G2 | Goal.status 只能 active → completed，不可逆 | GoalService.complete_goal() 检查 |
| G3 | Goal.progress_pct 不可直接设置，由关联 Sessions 的事件汇总计算 | Goal API 不暴露 progress_pct 写操作 |

### 9.3 Recommendation 不变量

| # | 不变量 | 实施位置 |
|---|--------|---------|
| R1 | Recommendation.accepted 一旦写入不可改 | Recommendation.accept() 幂等检查 |
| R2 | 过期 Recommendation 不可被接受 | Recommendation.accept() 检查 expires_at |

### 9.4 Learner 不变量

| # | 不变量 | 实施位置 |
|---|--------|---------|
| L1 | Learner 永不删除（软删除或归档） | 无 DELETE /api/learner 端点 |
| L2 | MemoryEntry 只追加，不修改不删除 | MemoryEngine 只写不删 |

---

## 十、Domain Evolution（领域演进路线）

```
V1 — 当前（稳定）
  Learner (AR)
    ├─ Persona (Entity)
    ├─ MemoryEntry[] (Value)
  Goal (AR)    ← 现有 plan_goals 表
  Session (AR) ← PR-002b 已完成
    └─ SessionMission (Value) ← Mission 作为 Session 内部值对象
  Recommendation (AR)
  GrowthTimeline (Projection)

V2 — 扩展
  Mission (AR)          ← Mission 从 Session 值对象升级为独立聚合根
  Habit (Entity)         ← 习惯养成
  Vision (Entity)        ← Goal 之上增加 Vision 层（V1 中 Goal 直接归属 Learner）
  Review (Entity)        ← 周期性回顾
  Project (AR)           ← 从 V1 删除的 project 模块回归（重构后）

V3 — 社会化 + 智能化
  Community              ← 学习社群
  Knowledge Graph (可视化) ← 从后台能力升级为前台
  Multi-Agent            ← 多 Agent 协作教学
```

---

## 附录 A：Ubiquitous Language（统一语言）

| 正确术语 | 禁止术语 | 所属 BC | 定义 |
|---------|---------|--------|------|
| **Learner** | User（领域层） | Learner BC | 学习者，苹果果的核心服务对象 |
| **Session** | Chat, Conversation | Learning BC | 一次学习会话（2~90分钟） |
| **Goal** | Target, Objective | Learning BC | 中期学习目标（月级） |
| **Mission** | Task, Assignment | Learning BC | V1 中为 Session 内部值对象（V2 升级为 AR） |
| **Recommendation** | Suggestion, Tip | Recommendation BC | AI 生成的学习建议，可追踪 |
| **Reflection** | Summary | Learning BC | Session 结束时的 AI 反思 |
| **GrowthRecord** | Report, Analysis | Learning BC (Projection) | Session 完成后的成长快照 |
| **MemoryEntry** | Memory Record, Log | Learner BC | 追加型记忆条目 |
| **Persona** | Profile Tag, Type | Learner BC | AI 长期总结的学习者画像 |
| **Conversation** | Chat History, Dialog | — | Session 的内部交互组件，不暴露 |

---

> **冻结**: 本文档定义的所有 Aggregate、BC 边界、Invariants 在 V1 开发周期内不再变更。
>
> **文件结构**: 本文档是 DDD 系列的主入口。配套文档：
> - [Domain Model v1](domain-model-v1.md) — 领域对象详细定义（对齐后更新）
> - [Event Storming v1](event-storming-v1.md) — 事件流图
> - [Bounded Contexts v1](bounded-contexts-v1.md) — Context Map 详细说明
> - [DDD.md](DDD.md) — DDD 概要索引
