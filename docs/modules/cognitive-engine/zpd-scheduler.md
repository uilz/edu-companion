# ZPD 自适应调度器

## 1. 概述

ZPDScheduler 实现 Vygotsky 最近发展区 (Zone of Proximal Development) 算法：
- 题目难度应在学生能力附近的"甜蜜点"
- 太简单 → 学生无聊
- 太难 → 学生挫败
- 甜蜜点 → 学生获得最大成长

## 2. 核心参数

```python
ZPD_MIN_GAP = 0.3   # |θ - b| < 0.3 → 太简单
ZPD_MAX_GAP = 1.0   # |θ - b| > 1.0 → 太难
ZPD_OPTIMAL = 0.6   # 甜蜜点
```

**修复 (B2 2026-07-04)**：原注释写 `[0.3, 1.2]`，代码是 `1.0`，现统一为 `1.0`。

## 3. 打分公式

```python
difficulty_gap = |student_ability - question.difficulty|

if difficulty_gap < ZPD_MIN_GAP:
    zpd_score = 1.0 - difficulty_gap / ZPD_MIN_GAP * 0.5  # 0.5 ~ 1.0
elif difficulty_gap <= ZPD_MAX_GAP:
    zpd_score = 1.0 - |difficulty_gap - ZPD_OPTIMAL| / ZPD_MAX_GAP  # 0.4 ~ 1.0
else:
    zpd_score = max(0.1, 1.0 - difficulty_gap / 2.0)  # 0.1 ~ 0.5

quality_bonus = question.quality_score * 0.3
novelty = 1.0 if question.usage_count == 0 else max(0.3, 1.0 / log(usage_count + 2))
novelty_bonus = novelty * 0.2

total_score = zpd_score + quality_bonus + novelty_bonus
```

## 4. 学生能力估计

```python
def estimate_student_ability(skill_id, user_id):
    try:
        node = get_repo().get_node(skill_id, user_id)
        if node and node.belief:
            return node.belief.proficiency_mean  # Beta mean
    except Exception:
        pass
    return 0.3  # fallback (新用户或找不到节点)
```

**数据源**：CognitiveNode.belief.proficiency_mean (Beta α/(α+β))

## 5. 疲劳感知能力调整

```python
def fatigue_adjusted_ability(base, session_elapsed_min, consecutive_wrong):
    time_decay = session_elapsed_min / 300  # 5 小时归零
    error_penalty = consecutive_wrong * 0.05
    adjusted = max(0.05, base * (1.0 - time_decay) - error_penalty)
    return adjusted
```

| elapsed | consecutive_wrong | 调整后 (base=0.5) |
|---------|------------------|------------------|
| 0 | 0 | 0.50 |
| 60 | 3 | 0.45 |
| 300 | 10 | 0.05 (floor) |
| 600 | 10 | 0.05 (floor) |

## 6. 跨技能会话规划

```python
def plan_session(question_pool, target_skills, duration_minutes=30):
    questions_per_skill = max(2, duration_minutes // (len(target_skills) * 5))
    # 1. 每技能按 ZPD 选题
    # 2. 轮询交错排列
```

## 7. 与认知节点的联动

| 触发 | 行为 |
|------|------|
| `CognitiveNodeUpdated` 事件 | `on_knowledge_change(user_id, node_id)` 回调 |
| 当前实现 | no-op（仅日志） |
| 未来扩展 | 增量重算 plan_session |

## 8. 已知边界

- ZPD 仅基于 1 个 ability 估计，不考虑知识图谱
- 疲劳调整是启发式，没有数据驱动
- `on_knowledge_change` 是个 no-op

## 9. 测试覆盖

- `tests/test_refactor_zpd_scheduler.py` — 10 个测试
- `tests/test_cognitive_e2e_full.py::TestZPDScheduler` — 7 个测试

## 10. 演进方向

1. 多维能力向量（不只 proficiency_mean，还有 speed, accuracy）
2. 基于历史答题数据的 fatigue 校准
3. 与 `scheduler.urgency` 字段联动（已有但未使用）
4. 知识图谱约束（blocked_skills 已有，但需要更复杂的图算法）
