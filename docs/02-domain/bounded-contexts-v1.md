# AppleGo Bounded Contexts v1

> 版本: v1.1.0 | 创建于: 2026-07-13 | 最后更新: 2026-07-13
>
> **冻结**: 与 [Strategic DDD Document v1](strategic-ddd-v1.md) 同步冻结。

---

## 一、Bounded Context 清单

| Context | 类型 | 聚合根 | 核心职责 |
|---------|------|--------|---------|
| **Auth BC** | 通用域 | User | 认证/授权（独立进程 18001） |
| **Learner BC** | 核心域 | Learner | 学习者画像、偏好、记忆 |
| **Learning BC** | 核心域 | Goal, Session | 学习目标 + 学习会话完整闭环 |
| **Recommendation BC** | 支撑域 | Recommendation | AI 推荐生成 + 接受追踪 |

---

## 二、Context 详细定义

### 2.1 Learner BC

```
┌─────────────────────────────────────────┐
│            Learner BC (Core)            │
│                                         │
│  AR: Learner                           │
│    ├── Persona (Entity)                │
│    ├── Preferences (Value)             │
│    └── MemoryEntry[] (Value, append)   │
│                                         │
│  Domain Services:                       │
│    ├── PersonaAnalyzer                 │
│    └── MemoryEngine                    │
│                                         │
│  Events Out: LearnerModelUpdated       │
│  Events In: SessionCompleted           │
└─────────────────────────────────────────┘
```

### 2.2 Learning BC

```
┌─────────────────────────────────────────┐
│           Learning BC (Core)           │
│                                         │
│  AR: Goal                              │
│    ├── title / description (Value)     │
│    ├── status: active→completed        │
│    └── progress_pct (computed)         │
│                                         │
│  AR: Session                           │
│    ├── SessionMission (Value)          │
│    ├── Reflection (Value)             │
│    ├── stage: intro→learn→practice→     │
│    │          reflect (state machine)   │
│    ├── conversation_id (internal)       │
│    ├── goal_id / recommendation_id     │
│    └── learner_id (Reference)          │
│                                         │
│  Projection:                            │
│  └── GrowthTimeline                    │
│                                         │
│  Domain Services:                       │
│  └── GrowthProjector                   │
│                                         │
│  Events Out:                            │
│    SessionCreated, SessionStageChanged, │
│    ReflectionGenerated, SessionCompleted│
│    GrowthRecordCreated                  │
│                                         │
│  Events In:                             │
│    RecommendationAccepted (from Rec BC) │
└─────────────────────────────────────────┘
```

### 2.3 Recommendation BC

```
┌─────────────────────────────────────────┐
│      Recommendation BC (Supporting)     │
│                                         │
│  AR: Recommendation                    │
│    ├── focus / reason (Value)          │
│    ├── predicted_growth (Value)        │
│    ├── status: generated→accepted→     │
│    │          expired (lifecycle)       │
│    ├── accepted (immutable once set)   │
│    └── consumed_by (Reference)         │
│                                         │
│  Domain Services:                       │
│  └── RecommendationEngine              │
│                                         │
│  Events Out:                            │
│    RecommendationGenerated,             │
│    RecommendationAccepted               │
│                                         │
│  Events In:                             │
│    LearnerModelUpdated (from Learner BC)│
└─────────────────────────────────────────┘
```

---

## 三、Context Map（上下文映射关系）

```
┌──────────────────┐
│   Auth BC        │──── 独立进程（18001）
│   AR: User       │
└────────┬─────────┘
         │ user_id === learner_id
         │ Conformist
         ▼
┌──────────────────────────────────────────┐
│           Learner BC (Core)              │
│           AR: Learner                    │
└──────────────┬───────────────────────────┘
               │
     ┌─────────┼─────────┐
     │         │         │
     │ Cust/   │ Event   │ Event
     │ Supplier│ Listener│ Listener
     │         │         │
     ▼         ▼         ▼
┌─────────┐ ┌──────────────┐ ┌───────────────────┐
│Learning │ │ Learning BC  │ │ Recommendation BC │
│   BC    │ │ (via Event)  │ │ (Supporting)      │
│ (Core)  │ │ MemoryEngine │ │ AR: Recommendation│
│ AR: Goal│ │ writes to    │ └───────────────────┘
│ AR:Sess │ │ Learner BC   │
└─────────┘ └──────────────┘
```

### 上下文关系说明

| 上游 (U) → 下游 (D) | 关系类型 | 规则 |
|---------------------|---------|------|
| Auth BC → Learner BC | **Conformist** | Learner 通过 user_id 引用 User，不消费 Auth 事件 |
| Learner BC → Learning BC | **Customer/Supplier** | Learning BC 通过 learner_id 引用 Learner |
| Learning BC → Learner BC | **Event Listener** | SessionCompleted → MemoryEngine 写入 MemoryEntry |
| Learner BC → Recommendation BC | **Event Listener** | LearnerModelUpdated → RecommendationEngine 重算 |
| Recommendation BC → Learning BC | **Customer/Supplier** | Session 消费 Recommendation.accepted 状态 |

**无 ACL**。四个 BC 共享统一的 Ubiquitous Language。

---

## 四、V1 实现边界

| Context | V1 实现策略 | 状态 |
|---------|-----------|------|
| **Auth BC** | `auth-gateway/` 独立进程 | 已稳定 |
| **Learner BC** | `shared/learner_model.py` → 新增 Persona + MemoryEntry API | PR-004 |
| **Learning BC** | PR-002b (Session) + `services/planning/goals.py` (Goal) | PR-002b 完成 |
| **Recommendation BC** | 复用 `api/system/secretary.py` Dashboard → 新建持久化实体 | PR-004 或 PR-005 |

---

> **冻结**: 与 [Strategic DDD Document v1](strategic-ddd-v1.md) 同步冻结。V1 中 BC 边界不再变更。
