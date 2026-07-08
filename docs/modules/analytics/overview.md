# Analytics（学情分析）

> 学习数据深度分析：掌握度雷达图、练习趋势、日历热力图、成就墙、学习统计。

---

## 1. 模块定位

Analytics 是学习数据的**深度分析面板**。提供多维度的学习数据可视化，帮助用户回顾学习表现、发现知识薄弱点、追踪学习习惯。

**解决**：用户如何查看自己的学习全貌 —— 掌握度分布、练习趋势、学习习惯、成就里程碑。

**不解决**：实时学习调度（由 planning 负责）；单一知识点的详细分析（由知识图谱负责）；具体练习执行（由 practice 负责）。

---

## 2. 核心功能

### 2.1 学情分析（主 Tab）

- 掌握度雷达图（`RadarChart`）
- 练习趋势折线图（`TrendChart`）
- 掌握度与错题分布（`MasteryErrorsCard`）
- 学习建议卡片（`SuggestionsCard`）
- 时间范围切换：近一周 / 近一月 / 全部

### 2.2 日历热力

- 日历热力图（学习频率可视化）
- 调用 `/api/progress/{user_id}/calendar`

### 2.3 成就墙

- 成就列表展示
- 成就统计
- 调用 `/api/practice/achievements`

### 2.4 学习统计

- 练习统计概览
- 行为数据（`/api/practice/behavior`）
- 习惯分析（`HabitTab`）
- 记忆留存面板（`RetentionPanel`）

---

## 3. 前端路由

- `/analytics` — 学情分析主页
- `/analytics?tab=calendar` — 日历热力
- `/analytics?tab=achievements` — 成就墙
- `/analytics?tab=stats` — 学习统计

---

## 4. 前端代码路径

- 前端页面: `frontend/src/app/analytics/`
- 分析内容: `frontend/src/app/analytics/_content.tsx`
- 核心组件: `frontend/src/components/analytics/`（RadarChart, StatsTab, AchievementsTab, CalendarTab）
- 共用组件: `frontend/src/components/dashboard/analytics/`（TrendChart, HeatmapGrid, HabitTab, RetentionPanel, OverviewCards, MasteryErrorsCard, SuggestionsCard, DailySummaryCard, ConfidenceCalibrationCard）

---

## 5. 后端 API

| 端点 | 用途 |
|------|------|
| `GET /api/practice/stats` | 练习统计数据 |
| `GET /api/practice/stats/overview` | 练习统计概览 |
| `GET /api/practice/behavior` | 学习行为数据 |
| `GET /api/practice/achievements` | 成就列表 |
| `GET /api/practice/achievements/stats` | 成就统计 |
| `GET /api/progress/{user_id}/calendar` | 日历热力图数据 |
| `GET /api/progress/{user_id}/summary` | 学习进度摘要 |

---

## 6. 模块联动

| 方向 | 内容 |
|------|------|
| 练习 → Analytics | 提供练习统计数据 |
| 知识图谱 → Analytics | 提供掌握度分布数据 |
| 学习进度 → Analytics | 提供日历热力和连续天数 |
| 成就系统 → Analytics | 提供成就列表和统计 |

---

## 7. 相关文档

- [`docs/modules/practice-system/overview.md`](../practice-system/overview.md) — 练习系统（提供练习数据）
- [`docs/modules/knowledge-graph/overview.md`](../knowledge-graph/overview.md) — 知识图谱（提供掌握度数据）