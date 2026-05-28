# Phase 1: 数据层统一 — Implementation Plan

**Date**: 2026-05-27
**Goal**: 消除 cognitive_nodes / conversation tree 双数据系统，让 CognitiveNode 成为唯一真相源

## Current State

- partition/domain/topic 同时存储在 `user_meta` JSONB（domains/topics字段）和 `cognitive_nodes` 表
- `tree_ops.py` 双写同步（5处），静默失败导致数据漂移
- `phase8.py` 读取时合并两个数据源
- sidebar 需要维护两套缓存（childMap + convCache）

## Target State

- partition/domain/topic 只存在 `cognitive_nodes` 表
- `tree_ops.py` 只写 cognitive_nodes
- `phase8.py` 只从 cognitive_nodes 读
- sidebar 只需一套缓存

## Execution Steps

### Step 1: Schema Extension
- 给 `cognitive_nodes` 加 `emoji`, `color`, `sort_order` 字段
- File: `backend/app/db/cognitive_schema.sql`

### Step 2: Migration Script
- 从 `user_meta` JSONB 读出 domains/topics，写入 cognitive_nodes
- 备份 JSONB 到 `_backup` 列
- File: `backend/scripts/migrate_user_meta_to_cognitive.py`

### Step 3: Rewrite phase8.py get_graph_nodes
- 全部从 cognitive_nodes 读，不再读 UserData
- File: `backend/app/api/phase8.py`

### Step 4: Rewrite tree_ops.py
- 只写 cognitive_nodes，删除双写逻辑
- File: `backend/app/services/tree_ops.py`

### Step 5: Simplify pg_storage.py
- 不再读写 domains/topics JSONB
- File: `backend/app/services/pg_storage.py`

### Step 6: Frontend Cleanup
- sidebar 去掉双缓存
- File: `frontend/src/components/conversation/Phase8Sidebar.tsx`

### Step 7: Clean JSONB
- 删除 user_meta 的 domains/topics/knowledge_graphs 列
- File: `backend/app/db/conversation_schema.sql`

## Files to Modify

| File | Change |
|------|--------|
| `backend/app/db/cognitive_schema.sql` | Add emoji, color, sort_order |
| `backend/app/cognitive/storage.py` | Support new fields |
| `backend/app/cognitive/models.py` | Add emoji, color, sort_order to CognitiveNode |
| `backend/scripts/migrate_user_meta_to_cognitive.py` | NEW: migration script |
| `backend/app/api/phase8.py` | Rewrite get_graph_nodes |
| `backend/app/services/tree_ops.py` | Remove dual-write |
| `backend/app/services/pg_storage.py` | Remove domains/topics read/write |
| `backend/app/api/knowledge_graph.py` | Remove _sync_graph_to_cognitive |
| `frontend/src/components/conversation/Phase8Sidebar.tsx` | Simplify cache |

## Validation

1. Migration script: compare before/after data integrity
2. API test: `curl /api/v2/graph/nodes` returns correct tree
3. Sidebar test: create partition → domain → topic → conversation → all visible
4. Secretary test: proposals still generated correctly
5. Planner test: study plan still generated correctly

## Risks

- Migration may fail if user_meta JSONB is corrupted
- Dual-write removal may break conversation creation
- Frontend cache simplification may cause display issues
