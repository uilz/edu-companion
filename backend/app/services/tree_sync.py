"""Cognitive node synchronisation helpers (mixin for TreeOpsService).

Provides _sync_cog_create / _sync_cog_delete / _sync_cog_rename which are
called by the CRUD and naming mixins.
"""

from __future__ import annotations

import time
import logging

logger = logging.getLogger(__name__)

from app.cognitive.models import CognitiveNode, MetaInfo
from app.cognitive.storage import upsert_node, delete_node as cog_delete_node


class TreeSyncMixin:
    """Cognitive-graph sync helpers mixed into TreeOpsService."""

    # ── 临时分区检测 ──
    def _is_under_temp_partition(self, entity, level: str, data) -> bool:
        """判断一个实体是否位于临时分区下（临时分区不接入图谱）。"""
        if level == "partition":
            return getattr(entity, "is_temp", False)
        # Walk up the parent chain
        if level == "domain":
            partition = data.partitions.get(getattr(entity, "partition_id", ""))
        elif level == "topic":
            domain = data.domains.get(getattr(entity, "domain_id", ""))
            partition = data.partitions.get(getattr(domain, "partition_id", "")) if domain else None
        elif level == "conversation":
            topic = data.topics.get(getattr(entity, "topic_id", ""))
            domain = data.domains.get(getattr(topic, "domain_id", "")) if topic else None
            partition = data.partitions.get(getattr(domain, "partition_id", "")) if domain else None
        else:
            return False
        return bool(partition and getattr(partition, "is_temp", False))

    # ────────────────────────────────────────────────────────
    # Sync: create / upsert cognitive node
    # ────────────────────────────────────────────────────────
    def _sync_cog_create(
        self,
        user_id: str,
        entity,
        level: str,
        name: str,
        emoji: str,
        parent_id: str | None,
        data,
        auto_created: bool = False,
    ) -> None:
        """After a tree entity is created, upsert the corresponding CognitiveNode."""
        if level not in ("partition", "domain", "topic", "conversation"):
            return

        # ── 临时分区下的实体不接入认知图谱 ──
        if self._is_under_temp_partition(entity, level, data):
            return

        cog_parent = None if level == "partition" else parent_id
        # build path_id (append short uuid to avoid duplicates)
        path_id = name
        if cog_parent:
            parent_level = self.LEVELS[self.LEVELS.index(level) - 1]
            parent_coll = self._get_collection(data, parent_level)
            parent_entity = parent_coll.get(cog_parent)
            if parent_entity:
                path_id = getattr(parent_entity, "name", name) + "." + name
        path_id += "." + entity.id[:8]

        cog_node = CognitiveNode(
            id=entity.id,
            label=(emoji + " " + name) if emoji else name,
            level=level,
            parent=cog_parent,
            path_id=path_id,
            node_type="auto_generated" if auto_created else "explicit",
            is_visible=not auto_created,  # 临时节点不进图谱
            meta=MetaInfo(created_at=time.time()),
        )
        upsert_node(cog_node, user_id)

    # ────────────────────────────────────────────────────────
    # Sync: delete cognitive node
    # ────────────────────────────────────────────────────────
    def _sync_cog_delete(
        self, user_id: str, node_id: str, level: str
    ) -> None:
        """Delete the corresponding CognitiveNode (best-effort)."""
        if level not in ("partition", "domain", "topic", "conversation"):
            return
        try:
            # 先检查实体是否在临时分区下（可能从未创建认知节点）
            from app.cognitive.storage import get_node as cog_get_node
            cog = cog_get_node(node_id, user_id)
            if not cog:
                return
            cog_delete_node(node_id, user_id)
        except Exception:
            logger.warning(
                f"Failed to delete cognitive node {node_id}", exc_info=True
            )

    # ────────────────────────────────────────────────────────
    # Sync: rename cognitive node label
    # ────────────────────────────────────────────────────────
    def _sync_cog_rename(
        self, user_id: str, node_id: str, level: str, new_name: str
    ) -> None:
        """Update the CognitiveNode label to reflect a rename.
        Also promotes the node to visible + explicit (临时→普通)."""
        if level not in ("partition", "domain", "topic", "conversation"):
            return
        try:
            from app.cognitive.storage import get_node as cog_get_node

            cog = cog_get_node(node_id, user_id)
            if cog:
                old_emoji = (
                    cog.label.split(" ")[0]
                    if cog.label and len(cog.label.split(" ")) > 1
                    else ""
                )
                cog.label = (old_emoji + " " + new_name) if old_emoji else new_name
                cog.is_visible = True  # 临时→普通：进入图谱
                cog.node_type = "explicit"
                upsert_node(cog, user_id)
            else:
                # 如果认知节点不存在（从未接入图谱），创建一个新的
                try:
                    tree_data = self._storage.load(user_id)
                    entity = self._get_collection(tree_data, level).get(node_id)
                    if entity and not self._is_under_temp_partition(entity, level, tree_data):
                        path_id = new_name + "." + node_id[:8]
                        cog_node = CognitiveNode(
                            id=node_id,
                            label=new_name,
                            level=level,
                            parent=None,
                            path_id=path_id,
                            node_type="explicit",
                            is_visible=True,
                            meta=MetaInfo(created_at=time.time()),
                        )
                        upsert_node(cog_node, user_id)
                except Exception:
                    pass
        except Exception:
            logger.warning(
                f"Failed to rename cognitive node {node_id}", exc_info=True
            )
