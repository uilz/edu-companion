# 🍎 苹果果 文档

> AI 驱动的个人知识体系构建工具 — 自主学习规划、精准答疑、多模态交互、知识追踪。

## 快速开始

```bash
# 本地开发
pnpm install && pnpm dev          # 前端（Next.js :3000）
cd backend && poetry install && uvicorn main:app --reload  # 后端（FastAPI :8000）

# 生产部署
docker compose -f docker/docker-compose.yml up -d
```

## 文档结构怎么看

| 目录 | 内容 | 适合谁 |
|------|------|--------|
| [architecture/](architecture/overview.md) | 系统架构、分层设计、全局规则（含 AI Tool 架构） | 所有人 |
| [specs/](specs/) | 数据结构和核心规则定义 | 开发前必看 |
| [modules/](modules/) | 各模块实现方案（对话/认知/练习/秘书/图谱） | 对应模块开发者 |
| [design-language.md](design-language.md) | UI 设计规范（颜色、字体、组件） | 前端开发者 |
| [agents/](agents/domain.md) | AI 智能体与 Issue 管理 | 团队协作 |

### 新人 5 分钟路线

1. 先读 [architecture/overview.md](architecture/overview.md) — 了解系统全貌
2. 找到自己负责的模块，读对应 [specs/](specs/) 的数据定义
3. 再读 [modules/](modules/) 的实现方案

### 开发一个新功能

```
specs/ 看数据结构 → modules/ 看实现方案
```

### 修改数据结构

```
更新 specs/ 对应文档 → 同步检查所有依赖它的 modules/ 是否需要调整
```

---

## 快速导航

- [系统架构 v8.0](architecture/overview.md) — 分层重构后的最新架构
- [项目根 README](../README.md) — 项目介绍
- [PROGRESS.md](../PROGRESS.md) — 当前开发进度
- [CHANGELOG.md](../CHANGELOG.md) — 版本更新日志

### 核心模块

| 模块 | 规格 | 实现 |
|------|------|------|
| 对话系统 | [specs/02-conversation-messages.md](specs/02-conversation-messages.md) | [modules/conversation-system/](modules/conversation-system/) |
| 知识图谱 | [specs/03-knowledge-graph.md](specs/03-knowledge-graph.md) | [modules/knowledge-graph/](modules/knowledge-graph/) |
| 练习系统 | [specs/04-practice-system.md](specs/04-practice-system.md) | [modules/practice-system/](modules/practice-system/) |
| 秘书系统 | [specs/05-secretary-system.md](specs/05-secretary-system.md) | [modules/secretary-system/](modules/secretary-system/) |
| 认知引擎 | [specs/01-cognitive-node.md](specs/01-cognitive-node.md) | [modules/cognitive-engine/](modules/cognitive-engine/) |
| 多模态 | — | [modules/multimodal/](modules/multimodal/) |
| 文件管理 | — | [modules/file-management/](modules/file-management/) |
