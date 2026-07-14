# Architecture 层：领域驱动设计

> 苹果果 V1 的领域模型定义与架构决策。

## 文档索引

| 文档 | 内容 | 状态 |
|------|------|------|
| **[Strategic DDD v1](strategic-ddd-v1.md)** | **主入口**：BC Map、Aggregate Map、聚合交互、事件、命令、读模型、事务边界、不变量 | v1.0 |
| [Domain Model v1](domain-model-v1.md) | 领域对象、聚合根、实体、值对象、领域服务详细定义 | v1.3 |
| [Event Storming v1](event-storming-v1.md) | 全链路事件流、事件清单 | v1.1 |
| [Bounded Contexts v1](bounded-contexts-v1.md) | Context 边界、Context Map、实现策略 | v1.1 |

## V1 核心架构（4 BC，4 AR）

| BC | Aggregate Root | 职责 |
|----|---------------|------|
| **Learner BC** (Core) | Learner | 学习者画像、偏好、记忆 |
| **Learning BC** (Core) | Goal, Session | 学习目标 + 学习会话完整闭环 |
| **Recommendation BC** (Supporting) | Recommendation | AI 推荐生成 + 接受追踪 |
| **Auth BC** (Generic) | User | 认证/授权（独立进程） |

## 全链路事件流

```
RecommendationGenerated → RecommendationAccepted
  → SessionCreated → SessionStageChanged(...)
  → ReflectionGenerated → SessionCompleted
  → GrowthRecordCreated + LearnerModelUpdated
```

## 开发铁律

> **新增 Domain 前必须通过三问：没有它业务能运行吗？它有独立不变量吗？业务决策依赖它吗？**
> **三问中任何一问为"否"，则为 Projection 而非 Domain，归属到最近的 Aggregate Root 下。**
