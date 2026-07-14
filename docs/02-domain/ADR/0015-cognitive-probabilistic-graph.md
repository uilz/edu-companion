# ADR 0015: 认知模型升级为图上的概率动态系统

> 状态：已生效  
> 日期：2026-07-09  
> 范围：认知数据系统（cognitive）、核心信念模型、复习调度、认知边传播

## 背景

Task #5 已完成认知数据系统的事件溯源 + 物化投影五层架构，但核心信念模型仍使用 BKT-lite（隐马尔可夫二元掌握状态）。随着 Task #7 视图层迁移和秘书系统接入，BKT-lite 暴露出以下问题：

1. **无法显式表达不确定性**：BKT 输出点估计 `p(known)`，缺少可用于信息增益的显式概率分布。
2. **单用户稀疏数据下不稳定**：BKT 参数（学习、遗忘、猜测、slip）需要大量数据才能估计。
3. **题目由 AI 动态生成**：每道题可能只被单个用户练习，无法通过群体数据校准。
4. **节点之间缺乏结构传播**：无法表达"掌握 A 会提升 B 的估计"这类关系。

因此决定将核心认知模型升级为**图上的概率动态系统**：每个节点维护一个概率分布，信号沿认知边有界传播，时间衰减模拟遗忘，统一表达掌握度、不确定性和复习需求。

## 决策

采用**方案 A：层次 Beta-二项 + 时间衰减 + 图传播**，作为认知数据系统的新核心信念模型。

- 每个节点维护 `Beta(α, β)` 后验。
- 练习/评估信号按难度调制后更新 α/β。
- 子节点数据稀疏时向父节点收缩（shrinkage prior）。
- 更新量沿认知边有界传播（最多 2 跳），支持方向性与距离衰减。
- 复习间隔由 Beta 方差（不确定性）决定，秘书系统可通过事件注入修正。
- BKT-lite 字段从投影表中移除，由新字段替代。

## 方案对比

| 方案 | 优点 | 缺点 | 结论 |
|---|---|---|---|
| A：层次 Beta-二项 + 时间衰减 + 图传播 | 可解释、适合单用户、能算信息增益、能表达结构关系、实现可控 | 图传播需仔细设计权重避免过度平滑 | **采用** |
| B：深度知识追踪（DKT） | 预测能力强，捕捉复杂时序 | 需要大量数据；黑盒，难以解释；与"可解释认知镜像"定位冲突 | 否 |
| C：高斯过程状态空间 | 自然表达不确定性与遗忘曲线 | 计算复杂度高 O(n³)，大规模不可行 | 否 |
| D：继续优化 BKT-lite | 改动最小 | 仍无法显式表达分布与信息增益；结构传播弱 | 否 |

## 核心算法

### 1. Beta-二项信念更新（简化生产版）

```
p = α / (α + β)
difficulty_factor = clamp(difficulty, -1, 1) -> [0, 1]
if success:
    α += w
    β += w * (1 - p) * difficulty_factor
else:
    α += w * p * (1 - difficulty_factor)
    β += w
```

难题使 `success` 分支的 β 增量更大，更新更谨慎。

### 2. 信息增益

使用 Beta 分布微分熵：

```
H(Beta(α, β)) = ln(B(α, β)) - (α-1)ψ(α) - (β-1)ψ(β) + (α+β-2)ψ(α+β)
IG = H_before - H_after
```

### 3. 收缩先验

```
λ = shrinkage_strength / (shrinkage_strength + evidence_count)
α_effective = λ * α_parent + (1 - λ) * α_child
β_effective = λ * β_parent + (1 - λ) * β_child
```

### 4. 图上有界传播

- 构建带方向性的邻接表。
- BFS 最多 `max_hops` 跳（默认 2）。
- 传播因子 = 累积因子 × 边权重 × 距离衰减^d × 方向因子 × 目标独立证据权重。
- 不同边类型方向性：prerequisite 仅 forward；hierarchy 双向但 parent→child 更强；co_occurrence/chunk 双向对称。

### 5. 时间衰减

```
effective_rate = forgetting_rate * (1 - stability_factor)
total_decayed = (α + β) * exp(-effective_rate * Δt_days)
p = α / (α + β)
α_new = max(α_min, total_decayed * p)
β_new = max(β_min, total_decayed * (1 - p))
```

保持均值不变，降低精度以模拟遗忘。

### 6. 统一调度

```
variance = αβ / ((α+β)^2 * (α+β+1))
uncertainty = sqrt(variance)
interval_days = base_interval * (target_uncertainty / uncertainty) * adjustment_factor
urgency = w_retention*(1-retention) + w_mastery*(target-proficiency) + w_core*is_core - w_stagnation*stagnation + w_goal*goal_push
```

## Schema 变更

### cognitive_node_projections

移除：
- `bkt_proficiency`, `bkt_peak`, `bkt_last_updated`, `bkt_slip`
- `bkt_known`, `bkt_guess`, `bkt_learn`, `bkt_forget`

新增：
- `belief_alpha`, `belief_beta`, `belief_evidence_count`, `belief_last_updated`
- `stability_factor`, `forgetting_rate`
- `total_information_gain`, `last_information_gain`
- `independent_evidence_weight`

### knowledge_edges

新增：
- `edge_weight`
- `edge_distance_decay`
- `max_propagation_hops`

### practice_events / cognitive_events

新增：
- `actor_type`（'user' | 'system' | 'external_agent'）

## 关键文件

- `backend/alembic/versions/45cad95ec888_migrate_cognitive_projections_to_beta_.py`
- `backend/app/domain/cognitive/operations/belief_operations.py`
- `backend/app/domain/cognitive/operations/graph_propagation_operations.py`
- `backend/app/domain/cognitive/operations/scheduling_operations.py`
- `backend/app/domain/cognitive/operations/__init__.py`
- `backend/app/domain/cognitive/events.py`
- `backend/app/infrastructure/db/projection_builder.py`
- `backend/app/infrastructure/db/cognitive_view_mapper.py`
- `backend/app/infrastructure/db/cognitive_event_repository.py`
- `backend/app/infrastructure/db/models/cognitive.py`
- `backend/tests/test_cognitive_operation_registry.py`

## 测试与验证

- 单元测试：`backend/tests/test_cognitive_operation_registry.py` 新增 `TestBeliefOperations`、`TestGraphPropagationOperations`、`TestSchedulingOperations`，共 19 项全部通过。
- 相关集成测试：认知存储、writer、repo、phase9/phase10 等 119 项全部通过。
- Alembic 迁移：`alembic upgrade head` 成功，当前版本 `45cad95ec888`。
- 端到端：通过 `rebuild.sh` 拉起前后端后，运行 `scripts/test/task0169/verify_adr0015_cognitive_beta_model.py`，验证从答题提交到信念更新、图传播、认知视图的完整链路；节点 A 与 B 的掌握度均 > 0.5。

## 风险与回滚

| 风险 | 缓解 | 回滚 |
|---|---|---|
| 图传播导致错误传播 | 最多 2 跳、低权重、独立证据权重 | 调低 `independent_evidence_weight` 或关闭传播 |
| Beta 更新对弱信号过敏感 | 非练习信息增益设置上限与置信度 | 降低非练习信号权重 |
| 调度间隔不合理 | 保留秘书修正入口、大量测试 | 回退到固定间隔启发式 |
| Schema 迁移失败 | 开发环境先跑通、仅修改 cognitive 相关表 | `alembic downgrade` |
| 旧代码依赖 BKT 字段 | Task #7 处理 service/API 迁移；视图层已适配 | 临时恢复 BKT 字段只读（不推荐长期） |

## 后续工作

- 秘书系统通过 `information_gain_event` 和 `scheduling_adjustment` 事件与认知模型交互。
- 监控生产数据，校准 `shrinkage_strength`、边权重范围、目标不确定性阈值。
- 如需更高精度，可在简化版基础上引入 IRT 似然近似版 Beta 更新。

---

**修订记录**

- v1.0（2026-07-09）：Task #12 完成后归档。
- v1.1（2026-07-13）：Task #169 端到端验证修复：
  - `projection_builder.py`：无父节点时补充 `proficiency` 字段，避免 KeyError。
  - `belief_operations.py`：信息增益显式转 `float`，避免 `np.float64` 序列化失败。
  - `cognitive_event_repository.py`：幂等键改为 SHA-256 短哈希，避免中文字段超长。
  - `trees.py`：认知视图不确定性计算改用 `scipy.special.digamma`，兼容 Python 3.11。
  - `di.py`：增强认知事件 handler 的调用与异常日志。
  - 新增 `scripts/test/task0169/verify_adr0015_cognitive_beta_model.py` 端到端验证脚本。
