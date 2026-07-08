# Dashboard（智能驾驶舱）

> 首页驾驶舱，汇聚各模块待办与状态，提供今日聚焦入口。

---

## 1. 模块定位

Dashboard 是整个学习系统的**首页入口**。以 Cockpit 组件接管 `/` 和 `/dashboard` 路由，展示今日该做什么、关键数据卡片、AI 推荐和当日时间线，不替代各模块的完整功能。

**解决**：用户打开应用后第一时间了解"今天该做什么"，快速进入学习状态。

**不解决**：深度数据分析和图表（由 analytics 模块负责）；详细的计划编排（由 planning 模块负责）；具体执行和追踪（由各业务模块负责）。

---

## 2. 核心功能

| 功能 | 说明 |
|------|------|
| 每日焦点 | 今日该做什么（调用 `/api/planning/daily`） |
| 数据卡片 | 练习统计、连续天数、今日进度（调用 `/api/practice/stats/overview`） |
| 连续天数 | 学习连续打卡天数（调用 `/api/progress/{user_id}/summary`） |
| AI 推荐 | 兴趣引擎推送今日内容（调用 `/api/interest/push/today`） |
| 时间线 | 今日已安排的计划项列表（调用 `/api/planning/daily`） |

---

## 3. 前端路由

- `/` — 首页（Cockpit 接管）
- `/dashboard` — 智能驾驶舱（Cockpit 接管）

---

## 4. 前端代码路径

- 前端页面: `frontend/src/app/dashboard/`
- 核心组件: `frontend/src/components/dashboard/Cockpit.tsx`
- 辅助组件: `frontend/src/components/dashboard/NodeDetailCard.tsx`
- 分析子组件: `frontend/src/components/dashboard/analytics/`（OverviewCards, TrendChart, HeatmapGrid, SuggestionsCard 等）

---

## 5. 后端 API

| 端点 | 用途 |
|------|------|
| `GET /api/planning/daily` | 获取每日计划 |
| `GET /api/practice/stats/overview` | 获取练习统计概览 |
| `GET /api/progress/{user_id}/summary` | 获取学习进度摘要 |
| `GET /api/interest/push/today` | 获取今日兴趣推荐 |

---

## 6. 模块联动

| 方向 | 内容 |
|------|------|
| Planning → Dashboard | 提供每日待办项和计划时间线 |
| 练习 → Dashboard | 提供练习统计概览 |
| 知识图谱 → Dashboard | 提供薄弱知识点提醒 |
| 兴趣探索 → Dashboard | 提供每日推荐内容 |
| 学习进度 → Dashboard | 提供连续打卡天数 |

---

## 7. 相关文档

- [`docs/modules/planning/overview.md`](../planning/overview.md) — 规划模块（提供每日计划数据）
- [`docs/modules/analytics/overview.md`](../analytics/overview.md) — 学情分析（提供深度数据分析）