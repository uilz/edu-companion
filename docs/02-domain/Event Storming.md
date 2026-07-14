# AppleGo Event Storming v1

> 版本: v1.1.0 | 创建于: 2026-07-13 | 最后更新: 2026-07-13
>
> **冻结**: 与 [Strategic DDD Document v1](strategic-ddd-v1.md) 同步冻结。

---

## 一、全链路事件流图

```
Today 入口
────────────────────────────────────────────────────────────
  [User] 打开首页
    │
    ▼
  RecommendationEngine.generate()
    │  输入: Learner.persona + MemoryEntry[] + Goal[]
    │  输出: Recommendation (status=generated)
    ▼
  RecommendationGenerated ──────────────────────────────────
    │  payload: { recommendation_id, learner_id, goal_id,
    │             focus, reason, predicted_growth,
    │             estimated_minutes, priority }
    ▼
  [User] 点击 "开始今天"
    │
    ▼
  recommendation.accept(session_id)  ← 一次性写入, immutable
    ▼
  RecommendationAccepted
    │  payload: { recommendation_id, session_id }

Session 生命周期
────────────────────────────────────────────────────────────
  SessionService.create_session({recommendation_id, goal_id, learner_id})
    ▼
  SessionCreated
    │  payload: { session_id, learner_id, goal_id, recommendation_id }
    ▼
  stage: intro
    │  [AI] 展示 SessionMission，用户确认
    ▼
  SessionStageChanged(intro→learn)
    │  payload: { session_id, old_stage, new_stage }
    ▼
  stage: learn
    │  [AI] 讲解 + 用户交互
    │  ├── AnswerSubmitted (复用)
    │  └── CognitiveStateChanged (复用)
    ▼
  SessionStageChanged(learn→practice)
    ▼
  stage: practice
    │  [User] 做练习
    │  └── AnswerSubmitted (复用)
    ▼
  SessionStageChanged(practice→reflect)
    ▼
  stage: reflect
    │  [AI] "今天完成了。一起总结？"
    │  [User] "好的"
    ▼
  ReflectionGenerated
    │  payload: { session_id, content, key_takeaways, next_steps }
    ▼
  SessionCompleted
    │  payload: { session_id, learner_id, started_at,
    │             finished_at, total_duration, stage_history,
    │             recommendation_id }

异步处理链
────────────────────────────────────────────────────────────
  [Learning BC] GrowthProjector.on(SessionCompleted)
    → 追加 GrowthRecord (Projection, append-only)
    → 发布 GrowthRecordCreated

  [Learner BC] MemoryEngine.on(SessionCompleted)
    → 追加 MemoryEntry (Value, append-only)
    → 发布 LearnerModelUpdated

  [Recommendation BC] RecommendationEngine.on(LearnerModelUpdated)
    → 重算推荐（下次 Today 打开时使用）
```

---

## 二、事件清单（冻结版）

### 新增事件

| 事件名 | 发布方 BC | 消费方 | 优先级 |
|--------|----------|--------|--------|
| `RecommendationGenerated` | Recommendation BC | Today 页面 | P1 |
| `RecommendationAccepted` | Recommendation BC | Learning BC | P1 |
| `SessionCreated` | Learning BC | GrowthProjector | P1 |
| `SessionStageChanged` | Learning BC | GrowthProjector | P1 |
| `ReflectionGenerated` | Learning BC | GrowthProjector | P1 |
| `SessionCompleted` | Learning BC | GrowthProjector, MemoryEngine | P0 |
| `GrowthRecordCreated` | Learning BC | Growth 页面 | P2 |
| `LearnerModelUpdated` | Learner BC | RecommendationEngine | P2 |

### 复用现有事件

| 事件名 | 现有定义 |
|--------|---------|
| `AnswerSubmitted` | 已有 |
| `CognitiveStateChanged` | 已有 |
| `ErrorRecorded` | 已有 |

---

## 三、V1 实现状态

| 事件 | 状态 |
|------|------|
| `SessionCreated` | PR-002b 已实现 |
| `SessionStageChanged` | PR-002b 已实现 |
| `SessionCompleted` | PR-002b 已实现 |
| `ReflectionGenerated` | PR-002b 已实现 |
| `GrowthRecordCreated` | Sprint C 已实现 |
| `RecommendationGenerated` | PR-004 (新建 Recommendation 实体) |
| `RecommendationAccepted` | PR-004 |
| `LearnerModelUpdated` | PR-004 (MemoryEngine 写 MemoryEntry 后触发) |

---

> **冻结**: 与 [Strategic DDD Document v1](strategic-ddd-v1.md) 同步冻结。
