# 认知引擎 · ACT-R 激活与信念模型

> CognitiveNode 的激活水平和掌握信念计算模型。
>
> 源码：[backend/app/cognitive/models.py](../../../backend/app/cognitive/models.py)

---

## Activation 模型

```python
class Activation(BaseModel):
    base_level: float = 0.0           # 基线激活 Bi
    retrieval_prob: float = 0.5       # 提取概率
    latency_ms: float = 5000.0        # 提取延迟（毫秒）
    noise_sigma: dict[str, Any]       # 噪声参数（引用 student.retrieval_sigma）
    spread_from_network: float = 0.0  # 网络扩散激活 Σ Wj * Sji
```

### ACT-R 激活公式

```
Ai = Bi + Σ Wj * Sji
```

| 符号 | 对应字段 | 说明 |
|------|----------|------|
| `Ai` | retrieval_prob | 节点 i 的激活水平 |
| `Bi` | base_level | 基线激活，基于使用频率和间隔 |
| `Wj` | — | 上下文权重，当前上下文的注意力分配 |
| `Sji` | spread_from_network | 关联强度，节点 j 到 i 的边权重 |

### 激活衰减

长时间未访问的节点激活水平逐渐降低：

```
B_new = B_old * exp(-λ * Δt)
```

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `λ` | param_refs.decay_factor → student.decay_factor | 遗忘速率 |

## Belief 模型（Beta 分布）

```python
class Belief(BaseModel):
    alpha: float = 2.0                   # Beta 分布 α 参数
    beta: float = 2.0                    # Beta 分布 β 参数
    proficiency_mean: float = 0.5        # α/(α+β) 掌握期望
    proficiency_precision: float = 4.0   # α+β 精度（越小越不确定）
    peak_proficiency: float = 0.5        # 历史最高掌握度
    last_updated: float                  # 最后更新时间戳
```

### 关键指标

| 指标 | 公式/字段 | 说明 |
|------|-----------|------|
| 掌握期望 | `proficiency_mean = α / (α + β)` | 期望掌握概率 |
| 精度 | `proficiency_precision = α + β` | 越大越确定 |
| 历史最高 | `peak_proficiency` | 历史峰值掌握度 |

### 便捷属性

```python
class CognitiveNode:
    @property
    def proficiency(self) -> float:
        return self.belief.proficiency_mean

    @property
    def precision(self) -> float:
        return self.belief.proficiency_precision
```

### 更新规则

| 事件 | α 变化 | β 变化 |
|------|--------|--------|
| 练习正确 | +1 | 不变 |
| 练习错误 | 不变 | +1 |
| AI 确认掌握 | +0.5 | 不变 |
| 长期未复习 | 不变 | +0.1（衰减）|

## Prediction 模型（预测编码）

```python
class Prediction(BaseModel):
    top_down_mean: float = 0.5       # 自上而下预测
    prediction_error: float = 0.0    # 预测误差
    error_flag: bool = False         # 误差标志
```

## PracticeSummary 模型

```python
class PracticeSummary(BaseModel):
    total_attempts: int = 0
    correct_attempts: int = 0
    total_time_spent: float = 0.0
    recent_success_rate_7d: float = 0.0   # 近 7 天正确率
    mean_latency_7d: float = 0.0          # 近 7 天平均延迟
    decayed_event_count: float = 0.0      # 衰减后事件计数
    rapid_relearn_cooldown_until: float = 0.0  # 快速重学冷却
    last_practiced: float | None = None
```

## Trend 模型（学习趋势）

```python
class Trend(BaseModel):
    recent_proficiencies: list[float] = []  # 近期掌握度序列
    velocity_ewma: float = 0.0             # 速度指数加权移动平均
    stagnation_days: float = 0.0           # 停滞天数
    volatility_std: float = 0.0            # 波动率
    direction: str = "stable"              # ascending / descending / plateau / volatile
```

## 遗忘方程

```
Recall(t) = exp(-t / S)
S = S0 * 2^(n / h)
```

| 符号 | 含义 | 说明 |
|------|------|------|
| `t` | 时间间隔 | 距离上次复习 |
| `S` | 记忆强度 | 初始 S0，每次复习翻倍 |
| `n` | 复习次数 | 成功复习计数 |
| `h` | 半衰期因子 | 默认 2.0 |

## Scheduling 模型（统一调度）

```python
class Scheduling(BaseModel):
    urgency: float = 0.0              # 紧急度
    next_review: float = 0.0          # 下次复习时间
    interleaving_group: str = "default"  # 交叉练习组
    last_interleaved_with: list[str] = []  # 上次交叉的节点
    next_action_type: str = "none"    # review / deep_processing / none
```

调度权重通过 `param_refs` 引用全局参数：

- `sched_retention_weight` → 保持度权重
- `sched_mastery_push_weight` → 掌握推进权重
- `sched_interleaving_weight` → 交叉练习权重
- `sched_core_boost` → 核心节点加成
- `sched_stagnation_penalty` → 停滞惩罚
