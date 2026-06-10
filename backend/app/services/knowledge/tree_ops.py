"""树形对话操作服务 v4.0（归一化版）
层级：分区 → 领域 → 专题 → 对话 → 消息节点
内联分支：编辑消息在当前对话内创建新版本，不另开对话线程

This module is now a thin facade.  The actual logic lives in:
  - tree_hierarchy.py  – Partition/Domain/Topic/Conversation CRUD
  - tree_messages.py   – Message CRUD
  - tree_context.py    – Context query / switch
  - tree_sub_branch.py – Sub-branch operations
  - tree_sync.py       – Cognitive-node graph synchronisation helpers
  - tree_naming.py     – Naming / renaming helpers
"""

from __future__ import annotations

from app.services.knowledge.tree_hierarchy import TreeHierarchyMixin
from app.services.knowledge.tree_messages import TreeMessagesMixin
from app.services.knowledge.tree_context import TreeContextMixin
from app.services.knowledge.tree_sub_branch import TreeSubBranchMixin
from app.services.knowledge.tree_sync import TreeSyncMixin
from app.services.knowledge.tree_naming import TreeNamingMixin
from app.services.common import get_data_repo


class TreeOpsService(
    TreeHierarchyMixin, TreeMessagesMixin, TreeContextMixin,
    TreeSubBranchMixin, TreeSyncMixin, TreeNamingMixin,
):
    """所有树形结构操作（归一化版本）—— composed from focused sub-modules."""

    def __init__(self):
        self._storage = get_data_repo()

    def _get_data_repo(self):
        return self._storage


tree_ops = TreeOpsService()
