# Task #82 — Knowledge / Knowledge-Tree 模块全面优化 · 摸底报告

> 任务执行日期: 2026-07-04
> 范围: 知识图谱 (Knowledge) + 知识树 (Knowledge-Tree) + 认知节点 (CognitiveNode)
> 子任务: 端点 / 事件 / 前端 / 测试 / Bug 修复 / E2E / 文档

---

## A.1 后端端点清单 (4 个 routes 文件)

### 1. `backend/app/api/knowledge_tree.py` (33 端点)

| 类别 | 端点 | 方法 | 行为 |
|------|------|------|------|
| KnowledgeNode | `/api/knowledge-tree/nodes` | GET | 列出知识点 (支持 parent_id/level/search 过滤) |
|  | `/api/knowledge-tree/nodes/{node_id}` | GET | 获取单个知识点 |
|  | `/api/knowledge-tree/nodes/{node_id}/subtree` | GET | 获取子树 |
|  | `/api/knowledge-tree/nodes/{node_id}/conversations` | GET | 节点关联会话 |
|  | `/api/knowledge-tree/nodes` | POST | 创建节点 |
|  | `/api/knowledge-tree/nodes/{node_id}` | PUT | 更新节点 |
|  | `/api/knowledge-tree/nodes/{node_id}` | DELETE | 删除节点 (级联子节点) |
|  | `/api/knowledge-tree/nodes/{node_id}/prerequisites` | POST | 加前置 |
|  | `/api/knowledge-tree/nodes/{node_id}/prerequisites/{prereq_id}` | DELETE | 移前置 |
|  | `/api/knowledge-tree/nodes/{node_id}/associates` | POST | 加关联 |
|  | `/api/knowledge-tree/nodes/{node_id}/reorder` | PUT | 排序子节点 |
| Conversation | `/api/knowledge-tree/conversations` | GET | 列会话 |
|  | `/api/knowledge-tree/conversations/{conv_id}` | GET | 获取会话 |
|  | `/api/knowledge-tree/conversations` | POST | 创建会话 |
|  | `/api/knowledge-tree/conversations/{conv_id}` | PUT | 更新会话 |
|  | `/api/knowledge-tree/conversations/{conv_id}` | DELETE | 删除会话 |
|  | `/api/knowledge-tree/conversations/{conv_id}/knowledge-nodes/{node_id}` | POST | 会话加节点 |
|  | `/api/knowledge-tree/conversations/{conv_id}/knowledge-nodes/{node_id}` | DELETE | 会话移节点 |
| Navigation | `/api/knowledge-tree/navigation` | GET | 导航树 |
|  | `/api/knowledge-tree/navigation/{node_id}` | GET | 导航节点 |
|  | `/api/knowledge-tree/navigation/{node_id}/children` | GET | 导航子节点 |
|  | `/api/knowledge-tree/navigation` | POST | 创建导航节点 |
|  | `/api/knowledge-tree/navigation/{node_id}` | PUT | 更新导航节点 |
|  | `/api/knowledge-tree/navigation/{node_id}` | DELETE | 删除导航节点 |
|  | `/api/knowledge-tree/navigation/{node_id}/migrate` | POST | 迁移导航节点 |
| Message | `/api/knowledge-tree/conversations/{conv_id}/messages` | GET | 消息列表 |
|  | `/api/knowledge-tree/messages/{msg_id}` | GET | 单消息 |
|  | `/api/knowledge-tree/messages` | POST | 创建消息 |
|  | `/api/knowledge-tree/messages/{msg_id}` | PUT | 更新消息 |
|  | `/api/knowledge-tree/messages/{msg_id}` | DELETE | 删除消息 |
|  | `/api/knowledge-tree/messages/{msg_id}/knowledge-nodes/{node_id}` | POST | 消息加节点 |
| AI/解释 | `/api/knowledge-tree/explain` | POST | AI 解释 |
|  | `/api/knowledge-tree/retention` | GET | 艾宾浩斯遗忘曲线 |

### 2. `backend/app/api/knowledge_tree_ai.py` (5 端点)

| 端点 | 方法 | 行为 |
|------|------|------|
| `/api/knowledge-tree/ai/generate` | POST | AI 生成知识树 |
| `/api/knowledge-tree/ai/expand/{node_id}` | POST | AI 扩充节点 |
| `/api/knowledge-tree/ai/edit/{node_id}` | POST | AI 编辑节点 |
| `/api/knowledge-tree/ai/chat/{node_id}` | POST | AI 对话 (验证节点) |
| `/api/knowledge-tree/ai/recommendation` | GET | 知识树推荐 |

### 3. `backend/app/api/knowledge_tree_sse.py` (1 端点)

| 端点 | 方法 | 行为 |
|------|------|------|
| `/api/knowledge-tree/events` | GET | SSE 实时事件流 |

### 4. `backend/app/api/knowledge/knowledge.py` (1 端点)

| 端点 | 方法 | 行为 |
|------|------|------|
| `/api/knowledge/graph` | GET | 知识图谱 (nodes + edges + mastery + layout) |

**知识模块端点总计: 33 + 5 + 1 + 1 = 40 端点**

---

## A.2 事件清单 (Cognitive / Knowledge / Tree)

### 核心 8 个事件 (本模块域 SSOT)

| 事件 | 触发时机 | 字段 |
|------|---------|------|
| `NodeCreated` | 创建知识节点 | user_id, node_id, parent_id, level, created_by |
| `CognitiveNodeLinked` | 节点与其他实体链接变化 | user_id, node_id, link_type, target_ref_type, target_ref_id, action |
| `CognitiveNodeMetadataChanged` | 节点元数据变化 | user_id, node_id, changed_fields |
| `MessageClassified` | 消息分类确认 | user_id, message_id, conv_id, topic_node_ids, atom_node_ids |
| `PracticeSubmitted` | 练习提交 | user_id, atom_node_ids, correctness |
| `PendingCrossTopic` | 跨主题候选 | user_id, candidates |
| `ProposalAccepted` | 秘书提案采纳 | user_id, proposal_id, action_type, target_node_id |
| `InterestTagFromKnowledgeCreated` | 知识图谱创建兴趣标签 | user_id, tag_id, knowledge_node_id |

### 跨模块联动事件 (15 个 — 知识图谱作为目标/源)

| 源模块 | 事件 | 知识图谱作用 |
|--------|------|------------|
| FlashCard | `FlashCardCreated` (含 linked_node_ids) | 目标 (linked_node_ids) |
| FlashCard | `FlashCardReviewed` (含 linked_node_ids) | 目标 (驱动 Belief 0.1 小贡献) |
| Reading | `ReadingNoteCreated` (源=reading_note) | 目标 (经 FlashCard 路径) |
| Reading | `ReadingAnnotationCreated` (含 linked_node_id) | 目标 (单节点关联) |
| Reading | `ReadingAnnotationProcessed` (target_module=cognitive_node) | 目标 (生成节点) |
| Project | `ProjectNodeExported` (target_module=cognitive_node) | 目标 (导入项目节点为知识节点) |
| Project | `ProjectNodeCreated` | 源 (向认知域通知) |
| Planning | `PlanItemCompleted` (含 linked_node_ids) | 源 (驱动复习调度) |
| Error | `ErrorRecorded` (含 skill_id) | 源 (更新 error_clusters) |
| Session | `SessionCompleted` (含 skill_id 隐式) | 源 (驱动 Belief 整体重算) |
| Answer | `AnswerSubmitted` (含 skill_id) | 源 (驱动 Belief Beta 分布更新) |
| Interest | `InterestContentImported` (target_module=cognitive_node) | 目标 (创建/关联认知节点) |
| LanguageRoom | `LanguageRoomErrorMarked` (含 linked_node_ids) | 目标 (错误 → Belief) |
| LanguageRoom | `LanguageRoomCompleted` (含 linked_node_ids) | 目标 (复习触发) |

**知识模块事件总计: 8 (本域) + 15 (联动) = 23 事件**

---

## A.3 前端页面/组件

### 页面
- `/knowledge-tree` → `frontend/src/app/knowledge-tree/page.tsx` (1 页面)
- 历史遗留: `frontend/src/components/graph/pages/` 包含 3 个旧页面 (GraphDialoguePage, DialogueCardList, FocusMode)

### 组件 (3 个目录)
- `frontend/src/components/knowledge-tree/` — 9 文件 (KnowledgeTreePage + TopBar + SidebarTreeNode + PanelLayout + LayerPanel + StatusBar + ContextMenu + DialogContainer + FloatDialogWrapper + index.ts)
- `frontend/src/components/graph/graphs/` — 4 文件 (ForceGraph + MindMapGraph + DAGGraph + FocusGraph)
- `frontend/src/components/graph/panels/` — 7 文件
- `frontend/src/components/graph/nodes/` — 1 文件
- `frontend/src/components/graph/modals/` — 4 文件
- `frontend/src/components/graph/pages/` — 3 文件

### Zustand Stores
- `frontend/src/store/conversation/tree-store.ts` — 树/图谱数据
- 缺失 `expandAncestors` 方法 (StudySidebar 引用)

---

## A.4 现有测试清单 (9 文件, 129 测试)

| 文件 | 测试数 | 覆盖 |
|------|--------|------|
| `test_cognitive_operation_registry.py` | 13 | 认知操作注册表 |
| `test_cognitive_storage.py` | 8 | 认知存储 |
| `test_cognitive_writer.py` | 17 | 认知写入器 |
| `test_refactor_cognitive_repo.py` | 18 | 仓储重构 |
| `test_refactor_embedding_utils.py` | 8 | Embedding 工具 |
| `test_refactor_tree_split.py` | 16 | 树拆分 |
| `test_refactor_zpd_scheduler.py` | 10 | ZPD 调度 |
| `test_tree_directory.py` | 25 | 树目录 |
| `test_phase9_cognitive_sync.py` | 14 | Phase 9 认知同步 |

---

## A.5 已知 Bug

### B-1 `StudySidebar.tsx:57` `expandAncestors` 不存在
- 引用: `useTreeStore.getState().expandAncestors(path)` 在 `frontend/src/components/conversation/panels/StudySidebar.tsx:57`
- 实际: `useTreeStore` 没有此方法
- 影响: 启动时祖先链展开静默失败 (TypeError at runtime, 但被 try-catch 吞掉)
- 修复: 在 `tree-store.ts` 中实现 `expandAncestors(path: string[])`

### B-2 `ForceGraph.tsx:91-97` d3 类型
- 实际: 已用 `d3Module: any` 规避 (`let d3Module: any = null;`) + `as any` cast
- 状态: **非真问题** (历史已修)

### B-3 `OverviewTab.tsx:143` `user` null
- 实际: `OverviewTab.tsx` 已删除 (任务 #78)
- 状态: **已修复** (无需操作)

---

## A.6 ADR 差异

### ADR `docs/old/archive/2026-phases/phases/03-capability-upgrade/knowledge-graph-design.md`
- 设计 7 层知识图谱 (concept → atom)
- 旧设计使用硬编码 SKILL_TO_SUBJECT, 当前实现已迁移为动态加载 (`checker.load_from_knowledge_tree`)
- ✓ 一致: 知识树优先, 硬编码兜底

### ADR `docs/old/archive/2026-phases/phases/11-knowledge-tree-redesign/`
- 设计四实体解耦: KnowledgeNode / Conversation / Navigation / Message
- 当前实现已采用 (knowledge_tree.py 中)
- ✓ 一致

---

## A.7 跨模块联动矩阵

| 源 | 事件 | 目标 | 实现位置 |
|----|------|------|----------|
| Cognitive | `CognitiveNodeLinked` | InterestExplorer (引用计数) | `app/application/di.py:241` |
| Cognitive | `CognitiveNodeMetadataChanged` | Planning (重调) + ZPD (重算) | `di.py:219, 233` |
| Cognitive | `CognitiveNodeLinked` | InterestExplorer (刷新) | `di.py:250` |
| Cognitive | `CognitiveNodeMetadataChanged` | InterestExplorer (面板刷新) | 隐式, 需补 |
| Cognitive | `Mastery` 变化 (Belief) | 无 (内部更新) | `cognitive_storage` 内部 |
| Project | `ProjectNodeExported (target=cognitive_node)` | KnowledgeNode 创建 | `project_export_handlers.py` |
| Reading | `ReadingAnnotationCreated` | KnowledgeNode (linked_node_id) | `reading` 服务 |
| Reading | `ReadingAnnotationProcessed (target=cognitive_node)` | KnowledgeNode 创建 | `reading` 服务 |
| Reading | `ReadingNoteCreated` | KnowledgeNode (经 FlashCard) | `reading` 服务 |
| Interest | `InterestContentImported (target=cognitive_node)` | KnowledgeNode 关联 | `interest` 服务 |
| LanguageRoom | `LanguageRoomErrorMarked` | KnowledgeNode (linked_node_ids) | `liveroom` 服务 |

---

## A.8 认知状态机 (Belief Beta 分布)

### Belief 状态字段
- `alpha: float = 2.0` (成功先验)
- `beta: float = 2.0` (失败先验)
- `proficiency_mean: float = 0.5` (α/(α+β))
- `proficiency_precision: float = 4.0` (α+β)
- `peak_proficiency: float = 0.5` (历史最高)
- `last_updated: float`

### 更新规则
- 答对 → α += 1 (mastery 上升)
- 答错 → β += 1 (mastery 下降)
- mastery_label: < 0.3 未接触 | < 0.5 初学 | < 0.7 掌握中 | < 0.85 熟练 | ≥ 0.85 精通

### 触发点
- `AnswerSubmitted` 事件 → `knowledge_graph_service.on_answer_submitted` → `cognitive_repo.sync_from_practice_event`
- `ErrorRecorded` 事件 → `error_clusters` 累加
- `FlashCardReviewed` 事件 → `belief_writer.write_belief` → 发布 `CognitiveNodeLinked`
- `LanguageRoomErrorMarked` 事件 → 经 ErrorBookEntry → 触发 `AnswerSubmitted` 同步路径

### 间隔重复 (FSRS)
- 由 `FlashCard` 模块 FSRS 调度
- 知识图谱的 `scheduling.next_review` 是简化版 (无 FSRS)
- ★ 知识节点当前无独立间隔重复 (无 `next_review` 调度)

### ZPD 自适应
- `ZPDScheduler.select_questions` 基于 `ZPD_OPTIMAL = 0.6` (最优难度差)
- `on_knowledge_change` 仅为日志 (no-op), 未来可触发 `plan_session` 增量重算
- ★ 当前 ZPD 与知识图谱松耦合, 需规划深度联动

---

## A.9 数据架构

### 表结构
- `cognitive_nodes` (JSONB 存储) — 知识节点主表
- `navigation_nodes` — 导航树 (user_id, parent_id, node_type, kind, name, path, knowledge_area_id)
- `conversation_user_meta.directory_nodes` — 旧版分区 (兼容)
- `cognitive_node_links` — 节点链接 (FlashCard / Project / Reading / Interest 引用)
- `cognitive_node_edges` — 边 (prerequisites, unlocks, associates)

### 服务分层
```
api/knowledge_tree.py
  → services/knowledge_tree/
    ├── knowledge_node_service.py  (CRUD)
    ├── conversation_service.py
    ├── navigation_service.py
    ├── message_service.py
    └── event_bus_service.py  (SSE)

api/knowledge/knowledge.py
  → services/knowledge/
    ├── knowledge_graph_service.py  (事件同步)
    ├── knowledge_state.py  (BKT 状态)
    ├── cognitive_queries.py
    ├── cognitive_sync.py
    ├── knowledge_expander.py
    ├── knowledge_query_service.py
    ├── tree_directory.py
    ├── tree_messages.py
    ├── tree_service.py
    ├── tree_sub_branch.py
    ├── tree_sync.py
    └── zpd_scheduler.py
```

---

## A.10 总结

- **端点数**: 40 (4 routes 文件)
- **事件数**: 23 (8 本域 + 15 跨域)
- **页面数**: 1 (`/knowledge-tree`)
- **组件数**: ~30 (knowledge-tree + graph 合并)
- **测试数**: 129 (9 文件)
- **待修 Bug**: 1 (B-1 expandAncestors 真实存在; B-2/B-3 已修)
- **改进空间**: 间隔重复与知识节点联动、ZPD 与知识图谱深度联动
