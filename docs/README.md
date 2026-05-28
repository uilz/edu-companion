# 项目文档

## 📚 文档结构

| 路径 | 内容 |
|------|------|
| `../README.md` | 项目总览、架构、快速开始 |
| `architecture.md` | 当前系统架构设计 |
| `archive/architecture-v3.md` | 系统架构设计 v3（Phase 1-15，已归档） |
| `PROGRESS.md` | 开发进度追踪（含 Phase 1-15） |
| `phase1/` | MVP 练习系统设计 (已归档) |
| `phase2/` | 错题本、知识图谱、学习日历 (已归档) |
| `phase3/` | 统一搜索、多模态、学习规划 (已归档) |
| `phase4/` | 对话系统 v4 设计 (已归档) |
| `phase5/` | 模块联动升级、对话实现计划 (已归档) |
| `phase6/` | CognitiveNode 认知节点系统 (已归档) |
| `phase7/` | 秘书系统 Secretary (已归档) |
| `phase8/` | 知识图谱树+分类器+融合会话 (已归档) |

## 🔧 近期重构

| 重构项 | 说明 |
|--------|------|
| **Phase 1-16 ✅** | 全部功能阶段完成（MVP→认知追踪→系统整合） |
| **Phase R1-R6 ✅** | 代码重构：数据层统一、模块合并、Zustand、死代码清理 |
| **BKT 退役** | knowledge_trace.py 重写为 CognitiveNode 实现 |
| **CognitiveNode 统一** | 数据源唯一存储，移除多数据源依赖 |
| **前端 Zustand** | useConversation 993→243行(-72%)，引入 conversation-store |
| **存储引擎** | PG 为主，JSON 备降；infra/database.py 已删除 |

## 💡 设计原则

1. **统一数据源**：cognitive_nodes 为知识结构唯一存储
2. **5 层级树**：partition → domain → topic → concept → atom
3. **事件驱动**：通过 EventBus 解耦模块间通信
4. **双存储后端**：PG 为主，JSON 文件为备降
5. **CognitiveNode 全面追踪**：15 子系统 + 22 方程的贝叶斯知识追踪
6. **后台全量生长，前台渐进可见**：节点仅由学习行为触发可见

## ⚡ 快速入口

| 文件 | 说明 |
|------|------|
| `backend/app/services/conversation_llm.py` | AI 对话核心逻辑 |
| `backend/app/api/conversation.py` | 对话系统 API 路由 |
| `backend/app/api/phase8.py` | Phase 8 图谱+分类 API |
| `backend/app/services/tree_ops.py` | 侧栏树 CRUD 操作 |
| `backend/app/services/pg_storage.py` | PostgreSQL 存储引擎 |
| `backend/app/cognitive/` | CognitiveNode 认知模型 + 存储 |
| `frontend/src/components/conversation/Phase8Sidebar.tsx` | 知识图谱树侧栏（替换旧的 PartitionSidebar） |
