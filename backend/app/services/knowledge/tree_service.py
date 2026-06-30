"""
TreeService — 树形对话操作深模块（DirectoryNode 版）

取代旧版 Partition/Domain/Topic/Conversation 四层模型。
所有节点统一用 DirectoryNode, 通过 node_type (dir/conv) 和 kind 区分。

对外暴露 TreeOpsService 类和 tree_ops 单例。
内部按区域组织，但不再拆分为 7 个碎片文件。
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any

from app.domain.cognitive import get_repo
from app.domain.cognitive.models import CognitiveNode, MetaInfo
from app.schemas.conversation import UserData
from app.schemas.directory_node import DirectoryNode, MessageNode
from app.services.common import get_data_repo

# 大模块保持独立（避免单一文件过大）
from app.services.knowledge.tree_directory import TreeDirectoryMixin
from app.services.knowledge.tree_messages import TreeMessagesMixin
from app.services.knowledge.tree_sub_branch import TreeSubBranchMixin

logger = logging.getLogger(__name__)


# ══════════════════════════════════════════════
# Async helpers
# ══════════════════════════════════════════════

async def _async_retry(coro_factory, retries: int = 2, delay: float = 0.5):
    """Execute coroutine with retry on exception."""
    for attempt in range(retries + 1):
        try:
            return await coro_factory()
        except Exception:
            if attempt < retries:
                logger.debug("retrying sync operation (attempt %d/%d)", attempt + 1, retries)
                await asyncio.sleep(delay * (attempt + 1))
            else:
                raise


# ══════════════════════════════════════════════
# Mixin: Cognitive graph sync (moved from tree_sync.py)
# ══════════════════════════════════════════════

class TreeSyncMixin:
    """Cognitive-graph sync helpers mixed into TreeOpsService."""

    async def _sync_skill(
        self,
        user_id: str,
        skill_id: str,
        dir_id: str = "",
        conv_id: str = "",
    ) -> None:
        """After a reply mentions a knowledge concept, upsert a CognitiveNode."""
        try:
            await _async_retry(
                lambda: self._do_sync_skill(user_id, skill_id, conv_id),
                retries=1,
            )
        except Exception:
            logger.exception("_sync_skill failed for %s", skill_id)

    async def _do_sync_skill(
        self, user_id: str, skill_id: str, conv_id: str,
    ) -> None:
        """Inner sync logic (wrapped by _async_retry)."""
        cog = get_repo().get_node(skill_id, user_id)
        if cog:
            if cog.meta:
                cog.meta.last_accessed_at = time.time()
            get_repo().upsert_node(cog, user_id)
            return

        path_id = f"skill.{skill_id[:8]}"
        cog_node = CognitiveNode(
            id=skill_id,
            label=skill_id,
            level="topic",
            parent=conv_id or None,
            path_id=path_id,
            node_type="auto_generated",
            is_visible=True,
            meta=MetaInfo(
                created_at=time.time(),
                last_accessed_at=time.time(),
            ),
        )
        get_repo().upsert_node(cog_node, user_id)


# ══════════════════════════════════════════════
# Mixin: Naming / renaming (moved from tree_naming.py)
# ══════════════════════════════════════════════

class TreeNamingMixin:
    """Rename operations mixed into TreeOpsService.

    所有重命名委托给 TreeDirectoryMixin.rename_node。
    """

    def _rename_node(self, user_id: str, node_id: str, level: str, new_name: str):
        """统一重命名入口 — 委托给 TreeDirectoryMixin.rename_node。"""
        return self.rename_node(user_id, node_id, new_name)

    # ── 兼容桩 ──

    def rename_partition(self, user_id, node_id, name):
        return self.rename_node(user_id, node_id, name)

    def rename_domain(self, user_id, node_id, name):
        return self.rename_node(user_id, node_id, name)

    def rename_topic(self, user_id, node_id, name):
        return self.rename_node(user_id, node_id, name)

    def rename_conversation(self, user_id, node_id, name):
        return self.rename_node(user_id, node_id, name)


# ══════════════════════════════════════════════
# Mixin: Context query / switch (moved from tree_context.py)
# ══════════════════════════════════════════════

class TreeContextMixin:
    """获取上下文 / 切换活跃对话."""

    def get_dir_context(self, user_id: str, dir_id: str) -> dict:
        """获取目录上下文（含最新对话消息）。"""
        data = self._get_data_repo().load(user_id)
        dir_node = data.directory_nodes.get(dir_id)
        if not dir_node:
            raise ValueError(f"目录 {dir_id} 不存在")

        convs = [
            dn for dn in data.directory_nodes.values()
            if dn.parent_id == dir_id and dn.node_type == "conv"
        ]
        convs.sort(key=lambda x: x.updated_at, reverse=True)
        active_conv = convs[0] if convs else None

        messages = []
        if active_conv:
            for mid in active_conv.conv_message_ids:
                node = data.nodes.get(mid)
                if node:
                    messages.append(node)

        return {
            "directory": dir_node,
            "conversation": active_conv,
            "messages": messages,
        }

    def switch_conversation(
        self, user_id: str, conv_id: str,
        dir_id: str | None = None,
    ) -> DirectoryNode:
        """切换活跃对话（当前无实际状态变更，保留为兼容）。"""
        data = self._get_data_repo().load(user_id)
        conv = data.directory_nodes.get(conv_id)
        if not conv or conv.node_type != "conv":
            raise ValueError(f"对话 {conv_id} 不存在")

        conv.updated_at = time.time()
        self._get_data_repo().save(user_id, data)
        return conv


# ══════════════════════════════════════════════
# Main service class
# ══════════════════════════════════════════════

class TreeOpsService(
    TreeDirectoryMixin, TreeMessagesMixin, TreeContextMixin,
    TreeSubBranchMixin, TreeSyncMixin, TreeNamingMixin,
):
    """所有树形结构操作（DirectoryNode 版本）—— composed from focused sub-modules.

    公有方法一览:
    目录操作: create_dir, create_conv, delete_node, rename_node,
              get_node, list_children, build_tree, find_conv, find_active_conv, migrate_conv
              create_partition, delete_partition, create_domain, delete_domain,
              create_topic, delete_topic, create_conversation, delete_conversation
    消息操作: add_message, modify_message, delete_message, update_message_content
    子分支:   create_sub_branch, get_sub_branches, get_sub_branch_parent,
              delete_sub_branch, update_sub_branch_summary
    上下文:   get_dir_context, switch_conversation
    同步:     _sync_skill (内部使用)
    重命名:   _rename_node, rename_partition, rename_domain, rename_topic, rename_conversation
    """

    def __init__(self):
        self._storage = get_data_repo()

    def _get_data_repo(self):
        return self._storage


tree_ops = TreeOpsService()
