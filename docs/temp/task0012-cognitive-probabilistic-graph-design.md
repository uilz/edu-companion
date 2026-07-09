# Task #12 设计文档：图上的概率动态系统

> 任务：将认知数据系统从 BKT-lite 升级为图上的概率动态系统  
> 日期：2026-07-09  
> 状态：已完成，已归档至 `docs/adr/0015-cognitive-probabilistic-graph.md`

---

## 1. 问题定义与背景

当前认知数据系统（Task #5）已实现事件溯源 + 物化投影五层架构，但核心信念模型仍使用 BKT-lite（隐马尔可夫二元掌握状态）。BKT-lite 的问题是：

1. **无法直接表达不确定性**：BKT 输出的是点估计 p(known)，没有显式分布，难以计算信息增益所需的前/后验熵变。
2. **不适合单用户稀疏数据**：BKT 参数（学习概率、遗忘概率、猜测概率、 slip 概率）需要足够数据才能稳定估计。
3. **题目由 AI 动态生成**：每道题可能只被单个用户练习，无法通过群体数据校准题目参数。
4. **缺乏结构传播**：节点之间独立更新，无法表达"掌握 A 会提升 B 的估计"这种结构关系。

因此需要将核心认知模型升级为：**图上的概率动态系统**——每个节点维护一个概率分布，信号在节点之间按认知边有界传播，时间衰减遗忘，统一表达掌握度、不确定性和复习需求。

---

## 2. 方案对比

### 方案 A：层次 Beta-二项 + 时间衰减 + 图传播（推荐）

每个节点维护 Beta(α, β) 后验。响应时按题目参数调制似然做贝叶斯更新；子节点向父节点收缩；信号沿认知边传播 1-2 跳；时间衰减让 α+β 逐渐减少。

- **优点**：可解释、适合单用户、能算信息增益、能表达结构关系、实现可控。
- **缺点**：图传播需要仔细设计权重，避免过度平滑；多步传播计算量增加。

### 方案 B：深度知识追踪（DKT/DKT+）

用 RNN/Transformer 建模用户整个响应序列，输出每个节点的掌握概率。

- **优点**：预测能力强，能捕捉复杂时序模式。
- **缺点**：需要大量数据；单用户数据稀疏时效果差；黑盒，难以解释；与苹果果"可解释认知镜像"定位冲突。

### 方案 C：高斯过程状态空间模型

把每个节点的掌握度看作随时间演化的潜在函数，用高斯过程建模。

- **优点**：能自然表达不确定性和遗忘曲线；连续时间建模优雅。
- **缺点**：计算复杂度高（O(n³)）；大规模节点不可行；需要近似推断。

### 方案 D：继续优化 BKT-lite

保留 BKT，增加跨节点参数共享和时间衰减。

- **优点**：改动最小，已有代码可用。
- **缺点**：仍然无法表达显式概率分布和信息增益；结构传播弱。

**推荐方案 A**。它在可解释性、单用户适应性、信息增益计算、结构表达能力之间最平衡，且与苹果果"个人认知镜像"定位一致。

---

## 3. 核心算法

### 3.1 Beta-二项信念更新

节点 n 维护 Beta(αₙ, βₙ)。

**先验掌握度**：

```
p_n = α_n / (α_n + β_n)
```

对于一次练习响应：

- `success=True`：`α_n ← α_n + w · Δα`，`β_n ← β_n + w · Δβ_adjust`
- `success=False`：`α_n ← α_n + w · Δα_adjust`，`β_n ← β_n + w · Δβ`

其中 `w` 是由题目参数和响应质量决定的权重。

更精确的贝叶斯更新：给定题目参数 (a, b, c)，响应 y ∈ {0, 1}：

```
P(y=1 | θ) = c + (1 - c) · σ(a(θ - b))
```

其中 θ 是掌握度（latent），σ 是 sigmoid。

由于 θ 有 Beta 先验，后验没有解析解。实用近似：

```
E[P(y=1)] = c + (1 - c) · E[σ(a(θ - b))]
```

用 E[p_n] 近似 E[θ]，计算预测正确率：

```
predicted = c + (1 - c) · σ(a(p_n - b))
```

然后按预测误差调整 α/β：

```
error = y - predicted
if error > 0:  # 实际比预测好
    α_n += η · error · (1 - predicted) · evidence_strength
else:
    β_n += η · (-error) · predicted · evidence_strength
```

其中 η 是学习率，evidence_strength 由题目区分度 a 和响应时间/置信度决定。

**简化版（生产首选）**：

```
if success:
    α += w
    β += w · (1 - p_n) · difficulty_factor
else:
    α += w · p_n · (1 - difficulty_factor)
    β += w
```

`difficulty_factor` 由题目 difficulty 映射到 [0, 1]，难题使更新更谨慎。

### 3.2 信息增益

响应前后 Beta 分布熵变：

```
H(Beta(α, β)) = ln(B(α, β)) - (α-1)ψ(α) - (β-1)ψ(β) + (α+β-2)ψ(α+β)
```

其中 B 是 Beta 函数，ψ 是 digamma 函数。

信息增益：

```
IG = H_before - H_after
```

对于非练习交互，由秘书系统评估 `estimated_ig`，直接调整 α/β 使熵减少对应量（需设置最大调整上限，避免弱信号过度影响）。

### 3.3 收缩先验（Shrinkage Prior）

子节点初始参数来自父节点：

```
α_child_0 = α_parent
β_child_0 = β_parent
```

运行时，子节点后验向父节点收缩：

```
λ = shrinkage_strength / (shrinkage_strength + evidence_count)
α_child_effective = λ · α_parent + (1 - λ) · α_child_observed
β_child_effective = λ · β_parent + (1 - λ) · β_child_observed
```

`evidence_count` 是子节点自己的练习/交互次数。`shrinkage_strength` 是超参数（如 5）。

展示给用户的掌握度使用 effective 参数计算：

```
p_display = α_child_effective / (α_child_effective + β_child_effective)
```

### 3.4 图上有界传播

认知数据系统内部存在以下边类型：

| 边类型 | 示例 | 传播权重范围 |
|---|---|---|
| `hierarchy` | topic → atom | 0.3 ~ 0.5 |
| `prerequisite` | atom_a → atom_b | 0.4 ~ 0.7 |
| `co_occurrence` | 同 session 练习 | 0.1 ~ 0.3 |
| `chunk` | 组块成员之间 | 0.3 ~ 0.5 |
| `user_related` | 用户确认相关 | 0.2 ~ 0.6 |
| `cross_domain` | 跨域连接 | 0.1 ~ 0.2 |

当节点 n 收到信号 Δ（α, β 更新量）时，向邻居 m 传播：

```
Δ_m = Δ · w_edge(n, m) · decay(distance)
decay(d) = γ^d,  γ ∈ [0.3, 0.7]
```

`distance` 从目标节点算起：直接邻居 d=1，邻居的邻居 d=2。

**传播顺序**：

1. 处理事件，更新目标节点 n。
2. 向 n 的直接邻居传播弱更新（d=1）。
3. 向邻居的邻居传播更弱更新（d=2）。
4. 不继续传播到 d=3 及以上。

**方向性**：

- hierarchy：双向，但 parent→child 更强。
- prerequisite：单向 forward（前置掌握提升后继估计）。
- co_occurrence / chunk：双向对称。
- cross_domain：双向，但权重低。

### 3.5 时间衰减

每个节点记录 `last_updated` 时间戳。每次读取或事件处理时计算经过时间 Δt（天）。

```
forgetting_rate = base_rate · (1 - stability_factor)
α_total = α + β
α_total_decayed = α_total · exp(-forgetting_rate · Δt)
```

保持均值不变，调整精度：

```
p = α / (α + β)
α_new = max(α_min, α_total_decayed · p)
β_new = max(β_min, α_total_decayed · (1 - p))
```

`stability_factor` 由历史练习表现决定：掌握越稳定、练习越规律的节点衰减越慢。

### 3.6 统一调度

复习间隔由后验不确定性决定：

```
uncertainty = Var(Beta) = αβ / ((α+β)²(α+β+1))
interval_days = base_interval · uncertainty / target_uncertainty
```

`target_uncertainty` 是目标不确定性阈值。

秘书系统可以通过事件流注入 `scheduling_adjustment`：

```
interval_days_adjusted = interval_days · adjustment_factor
```

`adjustment_factor` 由秘书根据情绪、负荷、信任积分等决定。

---

## 4. Schema 变更

### 4.1 KnowledgeNodeORM

无需大改，维持层级树结构。

### 4.2 CognitiveNodeProjectionORM

**移除**：
- `bkt_*` 相关字段
- 独立的 `sched_*` FSRS 字段

**新增/修改**：

```python
belief_alpha: float = 1.0
belief_beta: float = 1.0
belief_evidence_count: int = 0
belief_last_updated: float  # 时间戳

# 时间衰减参数
stability_factor: float = 0.5
forgetting_rate: float = 0.1

# 调度
next_review_at: float | None = None
review_interval_days: float = 1.0

# 信息增益累计（可选，用于展示）
total_information_gain: float = 0.0
last_information_gain: float = 0.0

# 图传播相关
independent_evidence_weight: float = 1.0  # 独立证据权重，防止过度平滑
```

### 4.3 KnowledgeEdgeORM

新增字段：

```python
edge_weight: float = 0.5  # 传播权重
edge_distance_decay: float = 0.5  # 距离衰减系数
max_propagation_hops: int = 2  # 最大传播跳数
```

### 4.4 PracticeEventORM / CognitiveEventRecord

新增字段：

```python
actor_type: str  # 'user' | 'system' | 'external_agent'
# source_type / source_id 已存在
```

### 4.5 Question 表（或 questions.metadata）

新增独立字段（推荐）或 metadata 字段：

```python
irt_difficulty: float = 0.0      # b
irt_discrimination: float = 1.0  # a
irt_guess: float = 0.25          # c
irt_confidence: float = 0.5      # 参数置信度
```

---

## 5. 接口变更

### 5.1 CognitiveOperationRegistry

新增/替换操作：

- `belief_update`：Beta 更新
- `belief_decay`：时间衰减
- `belief_information_gain`：信息增益计算
- `graph_propagate`：图传播
- `scheduling_update`：统一调度更新
- `shrinkage_prior_apply`：收缩先验

移除：
- `bkt_update`
- `bkt_decay`
- 独立的 FSRS scheduling 操作（如果存在）

### 5.2 ProjectionBuilder

- `_update_belief`：改为调用 `belief_update` + `shrinkage_prior_apply` + `graph_propagate`
- `_update_scheduling`：改为基于 Beta 不确定性 + 秘书修正
- `_decay_node`：改为 `belief_decay`

### 5.3 CognitiveEventHandler

- `handle_practice_response`：写入事件后触发新的 belief/scheduling 更新流程
- 新增 `handle_information_gain_event`：处理秘书系统评估的非练习信息增益
- 新增 `handle_scheduling_adjustment`：处理秘书修正

---

## 6. 测试策略

### 6.1 单元测试

1. **Beta 更新**：
   - 成功响应 α 增加，β 少量增加；
   - 失败响应 β 增加，α 少量增加；
   - 难题更新幅度小于简单题；
   - 掌握度趋近于真实水平。

2. **信息增益**：
   - 成功后的熵减少；
   - 失败后的熵变化方向正确；
   - 非练习信号产生弱增益。

3. **收缩先验**：
   - 新节点初始掌握度接近父节点；
   - 练习次数增加后逐渐独立；
   - 数据稀疏时向父节点收缩。

4. **图传播**：
   - 练习 A 后，相关邻居 B 的后验轻微变化；
   - d=2 邻居变化小于 d=1；
   - 不相关节点不受影响。

5. **时间衰减**：
   - 长期未练习方差增大；
   - 均值变化合理；
   - 稳定节点衰减慢于不稳定节点。

6. **统一调度**：
   - 不确定性高时间隔短；
   - 秘书修正事件有效调整间隔。

### 6.2 集成测试

1. 写入 practice_response 事件 → ProjectionBuilder 更新 → 读取 projection 验证掌握度、调度、信息增益。
2. 创建父子节点 → 子节点初始状态受父节点影响 → 多次练习后独立。
3. 创建边 → 练习一个节点 → 验证邻居节点传播更新。
4. 秘书 scheduling_adjustment 事件 → 验证 next_review_at 变化。
5. 事件回放：删除投影后重放事件，验证重建结果一致。

### 6.3 端到端验证

1. `rebuild.sh` 拉起前后端。
2. 登录后完成练习。
3. 验证前端掌握度展示变化。
4. 验证复习队列/引力种子更新。

---

## 7. 风险点与回滚方案

### 风险 1：图传播导致错误传播

- **缓解**：有界传播（最多 2 跳）、低权重、保留独立证据权重。
- **回滚**：通过 `independent_evidence_weight` 快速关闭传播影响。

### 风险 2：Beta 更新对弱信号过敏感

- **缓解**：非练习信息增益设置上限；秘书系统输出置信度；evidence_strength 上限控制。
- **回滚**：降低非练习信号权重或关闭该路径。

### 风险 3：调度间隔不合理

- **缓解**：统一调度公式需大量测试；保留手动调整入口；秘书修正作为安全边界。
- **回滚**：回退到固定间隔或简单启发式调度。

### 风险 4：Schema 迁移失败

- **缓解**：Alembic 迁移脚本先在开发环境跑通；保留旧字段的默认值；迁移前备份。
- **回滚**：执行 Alembic downgrade。

### 风险 5：旧代码依赖 BKT 字段

- **缓解**：Task #7 已交给其他 agent 处理 service/API 迁移；本任务只改核心模型和 projection。
- **回滚**：保留 BKT 字段只读，新字段并行运行（但协议禁止长期两套并存，过渡时间不超过一个任务周期）。

---

## 8. 实现顺序

1. **Schema 调整**：新增 Beta/调度/边参数字段，移除/废弃 BKT 字段。
2. **算法实现**：belief_update、shrinkage_prior、graph_propagate、belief_decay、scheduling_update。
3. **ProjectionBuilder 集成**：替换现有 BKT 更新路径。
4. **事件处理增强**：actor_type、秘书修正事件、信息增益事件。
5. **测试**：单元、集成、端到端。
6. **文档归档**：更新 docs/modules/cognitive-engine/overview.md 和相关 ADR。
7. **提交**：按规范 commit。

---

## 9. 实现结果

- 已按本设计文档完成全部实现，关键文件见 `docs/adr/0015-cognitive-probabilistic-graph.md`。
- Alembic 迁移 `45cad95ec888` 已升级到 head，仅修改 cognitive 相关表，未删除任何其他表。
- BKT-lite 字段已从 `cognitive_node_projections` 移除，由 Beta 信念字段替代。
- 新增操作：`belief_update`、`belief_decay`、`belief_information_gain`、`shrinkage_prior_apply`、`graph_propagate`、`update_scheduling`。
- `ProjectionBuilder` 与 `CognitiveEventHandler` 已切换至 Beta 模型 + 图传播 + 统一调度。
- 单元测试新增 19 项全部通过；相关集成测试 119 项全部通过。
- 已通过 `rebuild.sh` 拉起前后端并验证 LLM 无关功能。

## 10. 待确认事项

- 是否需要根据生产数据进一步校准 `shrinkage_strength`、边权重范围、目标不确定性阈值？
- 是否需要引入完整 IRT 似然近似版 Beta 更新替代当前简化版？
