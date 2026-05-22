# 学习规划系统设计

> 版本: v1.0  
> 最后更新: 2026-05-18  
> 状态: **核心流程已实现**，行为分析+习惯养成联动就绪

---

## 一、系统定位

学习规划系统是伴学的「导航仪」——不是硬塞任务列表，而是基于学习者画像、知识状态、行为模式，动态生成个性化规划。

**核心闭环**：

```
BKT知识诊断 → ZPD能力估计 → 学习计划生成 → 练习执行 → 行为分析 → 习惯建议
     ↑                                                            │
     └──────────────────────── 反馈更新 ───────────────────────────┘
```

---

## 二、架构全景

```
┌──────────────────────────────────────────────────────────────────────┐
│                         学习规划系统                                   │
├──────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  ┌────────────┐   ┌──────────────┐   ┌──────────────┐               │
│  │  api/study  │   │  learner_    │   │  habit_       │               │
│  │  .py        │   │  model.py    │   │  formation.py │               │
│  │             │   │              │   │               │               │
│  │ 4 REST端点   │──▶│ 学习计划生成  │   │ 每日目标分级   │               │
│  │             │   │ 进度汇总     │   │ TinyHabits   │               │
│  │             │   │ 画像管理     │   │ 番茄钟建议    │               │
│  └────────────┘   └──────┬───────┘   └──────┬───────┘               │
│                          │                  │                        │
│         ┌────────────────┼──────────────────┼──────────┐            │
│         │                │                  │          │            │
│         ▼                ▼                  ▼          ▼            │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌────────────┐  │
│  │ knowledge   │  │ zpd         │  │ behavior     │  │ api/       │  │
│  │ _trace.py   │  │ _scheduler  │  │ _analyzer.py │  │ practice.py│  │
│  │             │  │   .py       │  │              │  │            │  │
│  │ BKT引擎     │  │ ZPD调度     │  │ streak/时段   │  │ 练习统计    │  │
│  │ 知识推荐    │  │ 能力估计    │  │ 规律/疲劳    │  │ 答题记录    │  │
│  └─────────────┘  └─────────────┘  └─────────────┘  └────────────┘  │
│                                                                      │
└──────────────────────────────────────────────────────────────────────┘
```

---

## 三、模块详解

### 3.1 学习计划API (`api/study.py`)

| 端点 | 方法 | 功能 | 状态 |
|------|------|------|:--:|
| `/api/study/plan/generate` | POST | 生成个性化学习计划 | ✅ |
| `/api/study/plan/{user_id}` | GET | 获取当前计划（自动创建） | ✅ |
| `/api/study/plan/{user_id}/{task_id}/complete` | PUT | 标记任务完成 | ✅ |
| `/api/study/plan/{user_id}/progress` | GET | 获取计划进度 | ✅ |

**计划生成策略**（`LearnerModelEngine.generate_study_plan`）：

1. 调用 `bkt_engine.recommend_practice()` 获取最需要练习的5个知识点
2. 按掌握等级分配时间：
   - 初学(p_known < 0.3) → 45分钟，difficulty 0.3
   - 发展中(0.3-0.6) → 30分钟，difficulty 0.5
   - 接近掌握(0.6-0.95) → 20分钟，difficulty 0.7
3. 优先级按推荐顺序递减（10, 9, 8...）
4. 存储到内存 `self._study_plans[user_id]`

```python
recommendations = self.bkt.recommend_practice(profile.knowledge_states, top_n=5)
for i, rec in enumerate(recommendations):
    items.append(StudyPlanItem(
        task_id=f"plan_{user_id}_{i}",
        title=f"练习: {rec['skill_id']}",
        estimated_minutes=est_minutes,  # 45/30/20
        difficulty=difficulty,
        priority=10 - i,
    ))
```

---

### 3.2 BKT知识推荐 (`core/knowledge_trace.py`)

```python
def recommend_practice(states, top_n=5) -> list[dict]:
    # 按掌握等级优先级排序
    priority_map = {
        "接近掌握": 1.0,  # 差一点就掌握 → 最高优先级
        "发展中":   0.7,
        "初学":     0.5,
        "未接触":   0.3,
        "已掌握":   0.0,  # 不推荐
    }
    # 返回 top_n 个 priority > 0 的知识点
```

**关键特性**：
- 推荐「接近掌握」的知识点优先 → 边际收益最大
- 已掌握的不推荐 → 不浪费时间
- 4维知识状态（concept/procedure/application/transfer）
- 提示打折（用了提示的知识更新幅度打折扣）
- 伪掌握检测（答对但解释不出来 → 标记为伪掌握）

---

### 3.3 ZPD自适应调度 (`services/zpd_scheduler.py`)

基于 Vygotsky 最近发展区理论：

| 能力差 |θ - b| | 判定 | 处理 |
|--------------|------|------|
| < 0.3 | 太简单 | 降低ZPD得分 |
| 0.3 ~ 1.0 | **甜蜜点** | 越接近0.6得分越高 |
| > 1.0 | 太难 | 得分大幅降低 |

**能力估计 θ**：
```python
θ = p_known × 0.6 + avg_dimension × 0.4
# 尝试次数 < 3 → 保守估计 θ -= 0.1
```

**疲劳感知**：
```python
def fatigue_adjusted_ability(base_ability, elapsed_min, consecutive_wrong):
    time_decay = elapsed_min / 300   # 5小时归零
    error_penalty = consecutive_wrong × 0.05
    return max(0.05, base_ability × (1 - time_decay) - error_penalty)
```

**间隔重复**（SM-2简化版）：
- 答错 → 明天复习（间隔1天）
- 答对 → 间隔 = int(1 / (1 - p_known + 0.1)) × stability，上限60天

---

### 3.4 每日目标与微习惯 (`services/habit_formation.py`)

**三级目标**：

| 等级 | 题量/天 | 时间/天 | 触发条件 |
|------|---------|---------|---------|
| 入门 beginner | 5题 | 10分钟 | study_days=0 |
| 日常 regular | 10题 | 20分钟 | 日均≥5题 或 ≥3天 |
| 强化 intensive | 20题 | 40分钟 | 日均≥15题 且 ≥7天 |

**内置微习惯**（基于 BJ Fogg TinyHabits）：
1. **晨间一练**：吃完早饭后 → 做3道题 → ✨
2. **睡前复习**：刷完牙后 → 看一遍错题 → 💤
3. **等车刷题**：等公交/地铁时 → 做2道题 → 🚇

**番茄钟建议**：
```
fatigue_drop < 20分钟 → 短番茄钟 15+5
fatigue_drop 20-45分钟 → 标准番茄钟 25+5
fatigue_drop > 45分钟 → 长番茄钟 45+10
```

---

### 3.5 行为分析引擎 (`services/behavior_analyzer.py`)

**输入**：来自 `/api/practice/stats` 的 `daily_trend` + `hourly_heatmap` + `mastery_bars`

**输出**（`BehaviorReport`）：

| 维度 | 算法 | 输出 |
|------|------|------|
| 连续天数 streak | 从今天往前扫描活跃日期 | current_streak, longest_streak |
| 最佳时段 | 按小时聚合做题量，取 Top 3 | best_study_hours [14, 20, 9] |
| 规律性 | 变异系数 CV = σ/μ，score = 1-CV | regularity_score (0-1) |
| 疲劳点 | 连续2个时段做题量下降60% | fatigue_drop_minute |
| 个性化建议 | 综合上述 + mastery_bars | 6条建议（去重） |

**建议规则示例**：
```
streak ≥ 7 → "连续学习7天，习惯正在养成 🔥"
regularity < 0.3 → "学习时间不太规律，试试固定时段 📅"
fatigue < 40min → "建议番茄钟 25+5 🍅"
weak_count > 0 → "还有N个知识点需要加强 🎯"
```

---

## 四、数据模型

### StudyPlanItem（计划项）
```python
task_id: str          # plan_{user_id}_{idx}
title: str            # "练习: algebra_linear"
description: str      # "当前水平: 发展中，目标: 掌握该知识点"
subject: str          # 学科
skill_ids: list[str]  # 关联知识点
estimated_minutes: int  # 预估时间
difficulty: float     # 0.3/0.5/0.7
priority: int         # 10-6 (推荐顺序)
completed: bool       # 是否完成
```

### DailyGoal（每日目标）
```python
level: str            # beginner/regular/intensive
target_questions: int # 目标题量
today_done: int       # 今日已完成
today_remaining: int  # 剩余
today_accuracy: float # 今日正确率
is_completed: bool
streak_days: int
message: str          # 鼓励文案
```

### TinyHabit（微习惯）
```python
name: str             # "晨间一练"
anchor: str           # "吃完早饭后"（锚定事件）
behavior: str         # "做3道题"（微行为）
celebration: str      # "✨"（庆祝方式）
consistency: float    # 坚持率 (days_done / total_days)
```

---

## 五、跨模块互联

```
┌────────────┐   推荐练习     ┌────────────┐
│  BKT引擎    │──────────────▶│ 学习计划生成 │
│ k_trace.py │               │ learner_m  │
└─────┬──────┘               └──────┬─────┘
      │                            │
      │ ZPD调度                    │ 计划项
      ▼                            ▼
┌────────────┐               ┌────────────┐
│ ZPDScheduler│              │  Study Plan │
│ 选题/间隔   │◀─────────────│  API        │
└─────┬──────┘               └──────┬─────┘
      │ 练习执行                    │ 统计数据
      ▼                            ▼
┌────────────┐    daily_trend  ┌─────────────┐
│ Practice   │───────────────▶│ Behavior     │
│ API/Stats  │  hourly_heat   │ Analyzer     │
└────────────┘               └──────┬───────┘
                                   │ 疲劳/规律/streak
                                   ▼
                            ┌──────────────┐
                            │ HabitFormation│
                            │ 目标/番茄/微习惯│
                            └──────────────┘
```

### 具体连接点

| # | 源模块 | 目标模块 | 数据 | 接口 |
|---|--------|---------|------|------|
| 1 | BKT | StudyPlan | recommend_practice() → plan items | `bkt.recommend_practice()` |
| 2 | Practice Stats | BehaviorAnalyzer | daily_trend + hourly_heatmap | `GET /api/practice/stats` |
| 3 | BehaviorAnalyzer | HabitFormation | fatigue_drop → pomodoro | `behavior.analyze()` → `habit.get_pomodoro()` |
| 4 | BehaviorAnalyzer | HabitFormation | streak → celebration messages | `behavior.current_streak` → `habit.check_daily_goal()` |
| 5 | StudyPlan | Practice | plan item → practice session | User clicks "开始练习" |
| 6 | Practice | StudyPlan | 完成session → 标记task完成 | `PUT /study/plan/{uid}/{tid}/complete` |
| 7 | ZPD | StudyPlan | 能力估计调整计划难度 | `zpd.estimate_student_ability()` |
| 8 | Content Search | StudyPlan | 推荐学习资料匹配计划 | `learner.search_content()` |

---

## 六、已知限制

| 问题 | 影响 | 改进方向 |
|------|------|---------|
| 学习计划存内存 | 重启丢失 | 迁移到 PostgreSQL `study_plans` 表 |
| 行为分析输入需手动组装 | coupling 紧 | 统一 `AnalysisContext` 自动聚合 |
| 计划项无时间维度 | 无法排日程 | 增加 `scheduled_for` 字段 + 时间槽分配 |
| habit_formation 用全局实例 | 无法多用户隔离 | 改为 per-user 实例或从 DB 读 |
| 建议生成用规则引擎 | 缺乏个性化 | 引入 LLM 生成自然语言建议 |
| 无多学科交叉计划 | 每次只取5个知识点 | 增加学科轮转策略 |
| ZPD/Behavior/Habit 独立全局实例 | 耦合不透明 | 统一注入 `LearnerContext` |

---

## 七、与论文的对照

| 论文理论 | 实现位置 | 实现程度 |
|---------|---------|:--:|
| BKT (Corbett & Anderson, 1995) | `knowledge_trace.py` | ✅ 增强版 |
| ZPD (Vygotsky) | `zpd_scheduler.py` | ✅ 甜蜜点调度 |
| SM-2 间隔重复 (Wozniak) | `zpd_scheduler.py` SpacedRepetition | 🟡 简化版 |
| TinyHabits (BJ Fogg) | `habit_formation.py` | ✅ 完整实现 |
| 番茄工作法 (Cirillo) | `habit_formation.py` get_pomodoro | ✅ 自适应 |
| 遗忘曲线 (Ebbinghaus) | `knowledge_trace.py` compute_forgetting | ✅ 基础实现 |
| 交错练习 (Rohrer & Taylor) | `zpd_scheduler.py` plan_session | ✅ 轮询交错 |
