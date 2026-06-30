"""
TreeSync — 认知同步桩 (ADR 0023 Round4)

upsert_node / cog_delete_node 已在 TreeSyncMixin 中实现。
此模块保留为兼容性导出，供 test_refactor_tree_split 使用。
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


async def upsert_node(user_id: str, node_id: str, **kwargs) -> None:
    """Upsert a CognitiveNode (stub — 实际逻辑在 TreeSyncMixin._sync_skill)"""
    logger.debug("tree_sync.upsert_node: user=%s node=%s", user_id, node_id)


async def cog_delete_node(user_id: str, node_id: str) -> None:
    """Delete a CognitiveNode (stub — 实际逻辑在 TreeSyncMixin)"""
    logger.debug("tree_sync.cog_delete_node: user=%s node=%s", user_id, node_id)