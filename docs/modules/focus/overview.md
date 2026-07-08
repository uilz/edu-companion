# Focus（专注模式）

> 知识图谱驱动的深度对话学习空间，结合可视化图形、对话和练习。

---

## 1. 模块定位

Focus 是**知识图谱驱动的深度对话学习空间**。用户选择一个知识领域或主题，进入沉浸式对话学习，同时可查看知识图谱可视化、发起练习。

**解决**：用户如何围绕一个知识点深入探索 —— 对话讨论 + 可视化图谱 + 即时练习。

**不解决**：多领域的整体规划（由 planning 负责）；碎片化复习（由 FlashCard 负责）；文件阅读（由 reading 负责）。

---

## 2. 核心功能

| 功能 | 说明 |
|------|------|
| 知识图谱可视化 | 选中节点后展示 FocusGraph / ForceGraph 交互式图形 |
| 对话学习 | 围绕选中知识点的上下文对话，支持消息编辑、版本切换 |
| 即时练习 | 内嵌 PracticePanel，可随时发起练习 |
| 目录导航 | 按领域（Domain）和主题（Topic）组织对话目录 |
| 知识节点详情 | 点击节点查看关联卡片数、掌握度、练习入口 |

---

## 3. 前端路由

- `/focus` — 专注模式主页

---

## 4. 前端代码路径

- 前端页面: `frontend/src/app/focus/`
- 核心组件: `frontend/src/components/focus/FocusPage.tsx`
- 图形组件: `frontend/src/components/graph/graphs/FocusGraph.tsx`, `ForceGraph.tsx`
- 对话组件: `frontend/src/components/conversation/core/MessageList.tsx`, `ChatInput.tsx`
- 练习组件: `frontend/src/components/practice/panels/PracticePanel.tsx`

---

## 5. 后端 API

Focus 模块复用现有 API，不新建独立端点：

- 对话: `WebSocket` 连接 + `api/conversation/*`
- 知识图谱: `api/knowledge/*`
- 练习: `api/practice/*`

---

## 6. 模块联动

| 方向 | 内容 |
|------|------|
| 知识图谱 → Focus | 提供领域/主题目录和节点数据 |
| 对话 → Focus | 提供上下文对话能力 |
| 练习 → Focus | 内嵌练习面板，即时练习 |
| FlashCard → Focus | 节点详情中展示关联卡片 |

---

## 7. 相关文档

- [`docs/modules/knowledge-graph/overview.md`](../knowledge-graph/overview.md) — 知识图谱（目录和节点数据）
- [`docs/modules/conversation-system/overview.md`](../conversation-system/overview.md) — 对话系统
- [`docs/modules/practice-system/overview.md`](../practice-system/overview.md) — 练习系统