"""
GrowthEngine — 全方向自动生长引擎

职责：
1. ensure_ancestors: 创建节点时沿 path_id 向上补全缺失的父节点
2. suggest_lateral_expansion: 扫描父节点下已激活子节点，生成秘书扩展提案
3. ripple_cross_domain: 新节点创建后异步波纹跨域关联
"""
from __future__ import annotations

import logging
from uuid import uuid4

from app.cognitive.models import CognitiveNode
from app.cognitive.storage import (
    find_node_by_path, get_node, get_children, get_visible_children,
    upsert_node, vector_search,
)
from app.cognitive.edge_models import KnowledgeEdge
from app.cognitive.edge_storage import upsert_edge

logger = logging.getLogger(__name__)

LEVEL_ORDER = ["partition", "domain", "topic", "concept", "atom"]


class GrowthEngine:
    """全方向自动生长引擎"""

    def ensure_ancestors(
        self,
        user_id: str,
        path_id: str,
        level: str,
        path_labels: dict[str, str] | None = None,
    ) -> list[str]:
        """
        沿 path_id 逐级检查并补全缺失的父节点，创建为 auto_generated。

        参数：
            path_id: "大学物理.电磁学.静电场"
            level: 当前节点层级（如 "topic"）
            path_labels: {段名: 标签}，用于设置 label（可选）

        返回：
            创建的节点 ID 列表
        """
        if not path_id:
            return []

        segments = path_id.split(".")
        created_ids = []
        parent_id = None
        current_path = ""

        for i, seg in enumerate(segments):
            if i >= len(LEVEL_ORDER):
                break
            current_path = seg if i == 0 else current_path + "." + seg
            seg_level = LEVEL_ORDER[i]

            existing = find_node_by_path(current_path, user_id)
            if existing:
                parent_id = existing.id
                continue

            # 需要创建
            label = (path_labels or {}).get(seg, seg)
            node_id = str(uuid4())
            node = CognitiveNode(
                id=node_id,
                label=label,
                path_id=current_path,
                level=seg_level,
                parent=parent_id,
                is_core=False,
                node_type="auto_generated",
                is_visible=(seg_level == "partition"),  # 分区本身可见
                subsystems={"growth": {"state": "initial", "ancestor_completed": True}},
            )
            upsert_node(node, user_id)
            created_ids.append(node_id)
            parent_id = node_id

        return created_ids

    def suggest_lateral_expansion(
        self, user_id: str, parent_node_id: str,
    ) -> list[dict]:
        """
        扫描父节点下可见子节点数 ≥ 3 且未扩展过，返回秘书提案数据。

        返回：
        [{
            "type": "lateral_expansion",
            "parent_id": ...,
            "parent_label": ...,
            "visible_count": N,
        }, ...]
        """
        visible = get_visible_children(parent_node_id, user_id)
        if len(visible) < 3:
            return []

        parent = get_node(parent_node_id, user_id)
        if not parent:
            return []

        growth = parent.subsystems.get("growth", {})
        if growth.get("state") == "expanded":
            return []

        return [{
            "type": "lateral_expansion",
            "parent_id": parent_node_id,
            "parent_label": parent.label,
            "visible_count": len(visible),
        }]

    def ripple_cross_domain(self, user_id: str, node_id: str) -> None:
        """
        新节点创建后异步执行：
        1. 语义检索高度相似节点 → 按置信度创建边
        2. 信任度 > 0.9 设为 auto_active，否则 pending_confirm
        """
        node = get_node(node_id, user_id)
        if not node or not node.embedding:
            return

        # 检索相似节点
        similar = vector_search(
            node.embedding, user_id,
            min_similarity=0.75, limit=5,
        )
        for sim in similar:
            if sim["id"] == node_id:
                continue
            # 创建边
            edge = KnowledgeEdge(
                user_id=user_id,
                source_node_id=node_id,
                target_node_id=sim["id"],
                edge_type="related_to",
                strength=sim["similarity"],
                confidence=sim["similarity"],
                trust_score=sim["similarity"] * 0.8,
                edge_status="auto_active" if sim["similarity"] > 0.9 else "pending_confirm",
            )
            try:
                upsert_edge(edge)
            except Exception as e:
                logger.debug(f"波纹建边失败: {e}")

    def mark_expanded(self, user_id: str, parent_node_id: str) -> None:
        """标记父节点已扩展过（抑制重复提案）"""
        node = get_node(parent_node_id, user_id)
        if not node:
            return
        subs = dict(node.subsystems)
        subs["growth"] = {"state": "expanded"}
        node.subsystems = subs
        upsert_node(node, user_id)


# 全局实例
growth_engine = GrowthEngine()
