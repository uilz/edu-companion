# 项目文档

## 📚 文档结构

| 路径 | 内容 |
|------|------|
| `../README.md` | 项目总览、架构、快速开始 |
| `architecture-v3.md` | 系统架构设计 v3 |
| `PROGRESS.md` | 开发进度追踪 |
| `phase1/` | MVP 练习系统设计 (已归档) |
| `phase2/` | 错题本、知识图谱、学习日历 (已归档) |
| `phase3/` | 统一搜索、多模态、学习规划 (已归档) |
| `phase4/` | 对话系统 v4 设计 (已归档) |
| `phase5/` | 模块联动升级、对话实现计划 (已归档) |
| `phase6/` | CognitiveNode 认知节点系统 (已归档) |

## 🔧 最近重构（2026-05）

见 `../README.md` 的「近期重构」章节。

## 💡 设计原则

1. **分层架构**：API 路由薄，业务逻辑在 `services/`，数据在 `schemas/`，基础设施在 `infra/`
2. **对话系统 4 层结构**：分区 → 领域 → 专题 → 对话
3. **事件驱动**：通过 EventBus 解耦模块间通信
4. **双存储后端**：PG 为主，JSON 文件为备降
5. **BKT 知识追踪**：基于贝叶斯知识追踪的掌握度评估

## ⚡ 快速入口

| 文件 | 说明 |
|------|------|
| `backend/app/services/conversation_llm.py` | AI 对话核心逻辑 |
| `backend/app/api/conversation.py` | 对话系统 API 路由 |
| `backend/app/services/tree_ops.py` | 侧栏树 CRUD 操作 |
| `backend/app/services/pg_storage.py` | PostgreSQL 存储引擎 |
