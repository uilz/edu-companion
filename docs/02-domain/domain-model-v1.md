# AppleGo Domain Model v1

> 版本: v1.3.0 | 创建于: 2026-07-13 | 最后更新: 2026-07-13
>
> **定位**: 苹果果 V1 产品领域模型。解决未来 6~12 个月的产品演进问题。
>
> **原则**: 领域模型决定产品形态。Conversation 不是领域对象，Session 才是。
>
> **冻结**: 本文档已在 Strategic DDD Document v1 冻结。V1 开发周期内不再变更。
>
> **变更 v1.2→v1.3**:
> - Mission 保持为 Session 内部值对象（非独立 AR），V2 升级为 AR
> - Goal 升级为 Aggregate Root（有独立 API + 不变量）
> - Vision 推迟到 V2
> - MemoryEntry 为 Learner 下的值对象集合（非独立 AR）
> - Recommendation 升级为 AR（Supporting BC）
> - GrowthRecord 确认 Projection（非 Domain）
> - 与 Strategic DDD v1 对齐

---

## 一、对象分类

| 类型 | 对象 | 所属 BC | 定义 |
|------|------|--------|------|
| **聚合根** (AR) | Learner | Learner BC | 学习者数字孪生，全局唯一，永不删除 |
| **聚合根** (AR) | Session | Learning BC | 一次学习会话（2~90min），所有学习行为在此发生 |
| **聚合根** (AR) | Goal | Learning BC | 中期学习目标（月级），有独立 CRUD API |
| **聚合根** (AR) | Recommendation | Recommendation BC | AI 推荐记录，可追踪接受率 |
| **实体** (Entity) | Persona | Learner BC | AI 长期总结的学习者画像标签 |
| **值对象** (Value) | SessionMission | Learning BC | Session 内的任务分解 |
| **值对象** (Value) | Reflection | Learning BC | Session 结束后的 AI 反思 |
| **值对象** (Value) | MemoryEntry | Learner BC | 四级多维记忆条目，append-only |
| **读模型** (ReadModel) | GrowthRecord | Learning BC | Session 完成后的成长快照，append-only |
| **领域服务** | GrowthProjector | Learning BC | 监听 SessionCompleted → 追加 GrowthRecord |
| **领域服务** | RecommendationEngine | Recommendation BC | 基于 Learner + Memory + Goals → 生成 Recommendation |
| **领域服务** | MemoryEngine | Learner BC | 消费事件 → 写入 MemoryEntry |

---

## 二、聚合根详细定义

### 2.1 Learner（Learner BC）

```
聚合根: Learner
──────────────────────────────────
生命周期: 注册创建 → 持续成长 → 永不删除

实体:
  ├── Persona
  │     type: "explorer"|"practitioner"|"exam_driven"|"researcher"|"social"|"systematic"
  │     confidence: 0~1
  │     evidence: str[]
  │     lastUpdated: timestamp

值对象:
  ├── Preferences
  │     preferred_format, daily_minutes, ...
  └── MemoryEntry[]
        level: "short"|"working"|"long"|"episodic"
        category: "knowledge"|"behavior"|"preference"|"reflection"
        content, embedding, importance, source

修改入口:
  ├── PersonaAnalyzer.recalculate()      ← 定时 / 事件触发
  └── MemoryEngine.append(entry)         ← SessionCompleted 事件

不变量:
  ├── Learner 永不删除
  └── MemoryEntry 只追加不修改不删除
```

### 2.2 Goal（Learning BC）

```
聚合根: Goal
──────────────────────────────────
生命周期: 用户创建 → active → completed/abandoned

属性:
  ├── title, description
  ├── target_module, target_metric, target_value
  ├── status: active|completed|abandoned
  ├── progress_pct: computed（不可直接设置）
  └── learner_id: Reference

修改入口:
  ├── POST /api/planning/goals          ← 用户创建
  ├── PATCH /api/planning/goals/{id}    ← 用户修改
  └── goal.complete()                   ← 内部方法

不变量:
  ├── 必须属于一个 Learner
  ├── status 只能 active → completed，不可逆
  └── progress_pct 不可直接设置，由关联 Session 的事件计算
```

### 2.3 Session（Learning BC）

```
聚合根: Session
──────────────────────────────────
生命周期: 创建 → intro → learn → practice → reflect → completed

值对象:
  ├── SessionMission
  │     title, estimated_minutes, steps[]
  └── Reflection
        content, key_takeaways, next_steps

状态机:
  stage: intro → learn → practice → reflect (单调不可逆)
  status: active → completed | cancelled

引用:
  ├── learner_id
  ├── goal_id
  ├── recommendation_id
  └── conversation_id (内部交互组件)

修改入口:
  ├── POST /api/session                     ← 创建
  ├── PATCH /api/session/{id}/stage         ← 阶段切换
  └── POST /api/session/{id}/complete       ← 完成

不变量:
  ├── 必须属于且只属于一个 Learner
  ├── stage 单调不可逆
  ├── status completed 后不可修改
  ├── conversation_id 不暴露为独立 API
  └── Reflection 只能在 reflect 阶段写入
```

### 2.4 Recommendation（Recommendation BC）

```
聚合根: Recommendation
──────────────────────────────────
生命周期: generated → accepted → expired

属性:
  ├── goal_id (来自哪个 Goal)
  ├── focus / reason
  ├── predicted_growth: {skill, before, after}
  ├── estimated_minutes
  ├── priority: high|medium|low
  ├── status: generated → accepted → expired
  └── consumed_by: session_id|null

修改入口:
  ├── RecommendationEngine.generate()        ← 生成
  └── recommendation.accept(session_id)      ← 用户点"开始今天"一次性写入

不变量:
  ├── accepted 一旦写入不可改
  └── 过期 Recommendation 不可被接受
```

---

## 三、对象关系图

```
Learner BC                         Learning BC
┌──────────────┐                  ┌───────────────────────┐
│ Learner (AR) │                  │ Goal (AR)             │
│              │                  │  ├─ status            │
│ ├─ Persona   │←── learner_id ──│  └─ progress_pct       │
│ ├─ Preferences│                 │                       │
│ └─ MemoryEntry│                 │ Session (AR)          │
│    []         │                  │  ├─ SessionMission    │
└──────────────┘                  │  ├─ Reflection       │
                                  │  ├─ conversation_id   │
Recommendation BC                 │  ├─ goal_id ──────────┤
┌──────────────────────┐          │  ├─ recommendation_id─┤
│ Recommendation (AR)  │──────────│  └─ learner_id ───────┤
│  ├─ status           │          │                       │
│  ├─ focus / reason   │          │ GrowthRecord          │
│  └─ predicted_growth │          │  (Projection)         │
└──────────────────────┘          │  append-only          │
                                  └───────────────────────┘
```

---

## 四、与现有代码的映射

| Domain Object | 现有实现 | 差距 |
|--------------|---------|------|
| **Learner** | `shared/learner_model.py` | 需暴露 Persona API |
| **Persona** | 不存在 | 需新建 PersonaAnalyzer |
| **MemoryEntry** | `infrastructure/event_memory.py`（四级已存在） | 需添加 category 字段 |
| **Goal** | `services/planning/goals.py` + `plan_goals` 表 | 已存在，需对齐不变量 |
| **Session** | `domain/session/` + API | PR-002b 已完成 |
| **SessionMission** | `domain/session/models.py::SessionMission` | 已存在 |
| **Reflection** | Session.reflection 字段 | 已存在 |
| **Recommendation** | `api/system/secretary.py` Dashboard 动态生成 | 需创建独立实体 + 持久化 |
| **GrowthRecord** | `domain/growth/models.py` | Sprint C 已完成 |
| **Conversation** | `domain/conversation/` + API | 已降级为 Session 内部组件 |
| **Vision** | 不存在 | V2 |
| **Mission (独立AR)** | 不存在 | V2 |

---

## 五、V1 范围内的约束

| 不做的事 | 理由 |
|---------|------|
| Vision 层 | V2。V1 中 Goal 直接归属 Learner |
| Mission 独立 AR | V2。V1 中 Mission 是 Session 内部值对象 |
| Persona 实时更新 | 每周/每月批量更新 |
| Recommendation A/B 测试 | V1 不追踪推荐策略版本 |
| Memory 跨 Learner 共享 | 单用户系统 |
| Growth 趋势预测 | 只计算当前 Session 的成长 |
| Event 分布式 | 保持内存 + DB |

---

## 六、Domain Evolution（领域演进路线）

```
V1 — 当前（冻结）
  Learner (AR): Persona + MemoryEntry[]
  Goal (AR)
  Session (AR): SessionMission (Value) + Reflection (Value)
  Recommendation (AR)
  GrowthRecord (Projection)

V2 — 扩展
  Mission (AR)                           ← SessionMission → 独立 AR
  Vision (Entity)                        ← Goal 之上增加层
  Habit / Review / Project               ← 新能力

V3 — 社会化 + 智能化
  Community / Knowledge Graph (可视化) / Multi-Agent
```

---

## 七、Domain Invariants（领域不变量）

> **每次有人违反下面任何一条，就是 Bug。**

| # | 不变量 | 所属 AR |
|---|--------|--------|
| 1 | 一个 Session 必须属于且只属于一个 Learner | Session |
| 2 | Session.stage 单调不可逆 | Session |
| 3 | Session.status completed 后不可修改 | Session |
| 4 | Conversation 永远不能脱离 Session 存在 | Session |
| 5 | GrowthRecord 永远不能直接修改 Session | Session (Projection) |
| 6 | MemoryEntry 永远属于 Learner，只追加不修改 | Learner |
| 7 | Recommendation.accepted 一旦写入不可改 | Recommendation |
| 8 | Goal.status 只能 active → completed，不可逆 | Goal |
| 9 | Goal.progress_pct 不可直接设置 | Goal |
| 10 | Domain 层不依赖 UI 层 | 全部 |

---

> **版本**: v1.3.0 | 创建于: 2026-07-13 | 最后更新: 2026-07-13
>
> **冻结**: 与 [Strategic DDD Document v1](strategic-ddd-v1.md) 同步冻结。
