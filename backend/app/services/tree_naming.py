"""Naming / renaming helpers (mixin for TreeOpsService).

Covers _rename_node (private) and the four public rename_* methods.
"""

from __future__ import annotations

import time
import logging

logger = logging.getLogger(__name__)


class TreeNamingMixin:
    """Rename operations mixed into TreeOpsService."""

    # ------------------------------------------------------------------
    # _rename_node – shared implementation for all rename_* methods
    # ------------------------------------------------------------------
    def _rename_node(self, user_id: str, node_id: str, level: str, new_name: str):
        data = self._storage.load(user_id)
        collection = self._get_collection(data, level)
        node = collection.get(node_id)
        if not node:
            raise ValueError(f"{level.capitalize()} {node_id} not found")
        # 临时分区不可重命名
        if level == "partition" and getattr(node, "is_temp", False):
            raise ValueError("临时分区不可重命名")
        node.name = new_name
        node.updated_at = time.time()
        self._storage.save(user_id, data)
        logger.info(f"Renamed {level} {node_id} to {new_name}")
        # sync cognitive node label
        self._sync_cog_rename(user_id, node_id, level, new_name)
        return node

    # ------------------------------------------------------------------
    # Public rename helpers (delegating to _rename_node)
    # ------------------------------------------------------------------
    def rename_partition(self, user_id, partition_id, name):
        return self._rename_node(user_id, partition_id, "partition", name)

    def rename_domain(self, user_id, domain_id, name):
        return self._rename_node(user_id, domain_id, "domain", name)

    def rename_topic(self, user_id, topic_id, name):
        return self._rename_node(user_id, topic_id, "topic", name)

    def rename_conversation(self, user_id, conv_id, name):
        return self._rename_node(user_id, conv_id, "conversation", name)
