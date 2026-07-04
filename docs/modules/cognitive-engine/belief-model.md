# Belief Beta 分布与状态机

## 1. 信念数据结构

```python
class Belief(BaseModel):
    alpha: float = 2.0                  # Beta 分布 α 参数
    beta: float = 2.0                   # Beta 分布 β 参数
    proficiency_mean: float = 0.5       # α/(α+β) — 掌握度均值
    proficiency_precision: float = 4.0  # α+β — 精度
    peak_proficiency: float = 0.5       # 历史峰值 (单调不降)
    last_updated: float = 0.0           # 用于遗忘衰减
```

**默认先验**：α=β=2，等价于"看了 2 次答对 + 2 次答错"的均匀先验。

## 2. 贝叶斯更新公式

### 2.1 证据融合 (update_belief_from_evidence)

```
if success:
    α ← α + weight
else:
    β ← β + weight
mean ← α / (α + β)
precision ← α + β
peak ← max(peak, mean)
```

| weight | 典型来源 |
|--------|----------|
| 1.0 | 答题（practice_response） |
| 0.3 | 对话评估（conversation_assessment） |
| 0.5 | 弱证据（hint, multiple_choice 等） |

### 2.2 遗忘衰减 (decay_belief)

```
elapsed_hours = (now - last_updated) / 3600
decay_rate = 0.05 ^ (elapsed_hours / 24)    # 每 24h precision 减 5%
total = (α + β - 4) * decay_rate + 4         # 保底 4 (先验强度)
mean_drift = mean * (1 - drift_strength) + 0.5 * drift_strength
                                             # 7 天内 drift → 0.5
```

参数来源：`docs/old/archive/2026-phases/phases/05-cognitive/` 设计文档。

## 3. 状态机 (Mastery Level)

### 3.1 阈值 (修复 B3 后统一)

定义在 `app.domain.cognitive.constants`：

| 范围 | 标签 |
|------|------|
| `mean < 0.3` | 未接触 |
| `0.3 ≤ mean < 0.6` | 初学 |
| `0.6 ≤ mean < 0.8` | 发展中 |
| `0.8 ≤ mean < 0.9` | 接近掌握 |
| `mean ≥ 0.9` | 已掌握 |

**历史分歧**：
- `profiles.py` 用 0.9 作为"已掌握"分界
- `adaptive_planner.py` 用 0.8 与 BKT 对齐
- 修复 (2026-07-04)：统一为 0.8，与 BKT 一致

### 3.2 节点生命周期

```
created (is_active=true, is_visible=false)
  └→ in_progress (practice_events 累积, trend 更新)
       ├→ mastered (mean ≥ 0.9)
       │    └→ archived (subsystems.growth.state = "expanded")
       └→ stagnated (stagnation_days ≥ 7)
            └→ recommended_for_review (scheduling.urgency ↑)
```

实际状态机通过 `subsystems` 字段 (free-form dict) 软实现，无强约束。

## 4. Profile 提取

按场景加载最小化字段集：

| Profile | 字段 | 用途 |
|---------|------|------|
| `MasteryAtom` | id, label, level, proficiency_mean/precision, mastery_level | 对话上下文注入 |
| `PracticeProfile` | + practice_summary, trend_direction, error_clusters | 练习反馈 |
| `PlanningProfile` | + scheduling.urgency, cognitive_load | 学习计划 |
| `DiagnosisProfile` | + metacognition_score, goal_alignment | 秘书诊断 |

## 5. 元认知校准

```python
correctness_score = 4 if success else 0
gap = confidence_before - correctness_score   # 1-4 标度
if |gap| ≤ 1:   direction = "accurate"
elif gap > 0:   direction = "overconfident"
else:           direction = "underconfident"
calibration_error = mean(|history|)  # 20 条滚动窗口
```

**修复 (B12)**：同时接受 `int 1-4` 和 `float 0-1` 两种 confidence_before 格式。

## 6. 测试覆盖

- `tests/test_cognitive_operation_registry.py` — 13 个测试
- `tests/test_phase9_cognitive_sync.py` — 12 个测试
- `tests/test_cognitive_e2e_full.py::TestBeliefBetaDistribution` — 8 个测试
- `tests/test_cognitive_e2e_full.py::TestMasteryStateMachine` — 5 个测试
- `tests/test_cognitive_e2e_full.py::TestCognitiveNodeProfiles` — 4 个测试
- `tests/test_cognitive_e2e_full.py::TestConfidenceBeforeCompat` — 2 个测试
