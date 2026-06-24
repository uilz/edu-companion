"""
KnowledgeNodeService — 知识点 CRUD 服务

封装 CognitiveNode 仓储，提供 KnowledgeNode 视图。
"""
from __future__ import annotations
import logging
import time
from typing import Optional
from uuid import uuid4

from app.domain.cognitive import get_repo
from app.domain.cognitive.models import CognitiveNode, MetaInfo, Prerequisite, Unlock, Associate
from app.schemas.knowledge import KnowledgeNode as KnowledgeNodeSchema

logger = logging.getLogger(__name__)


class KnowledgeNodeService:
    """知识点服务 — 对 CognitiveNode 仓储的封装"""

    # ── CRUD ──

    def create_node(
        self, user_id: str, label: str, level: str = "topic",
        parent_id: str | None = None, brief: str = "",
        tags: list[str] | None = None, emoji: str = "", color: str = "",
        created_by: str = "user",
    ) -> KnowledgeNodeSchema:
        """创建知识点"""
        node = CognitiveNode(
            id=f"kn_{uuid4().hex[:12]}",
            label=label,
            level=level,
            parent=parent_id,
            brief=brief,
            tags=tags or [],
            created_by=created_by,
            emoji=emoji,
            color=color,
            node_type="explicit",
            is_visible=True,
            path_id=f"{label}.{level}",
            meta=MetaInfo(created_at=time.time(), updated_at=time.time()),
        )
        get_repo().upsert_node(node, user_id)

        # 发布 NodeCreated 事件 → 触发波纹边检测 + 秘书提案
        try:
            import asyncio
            from app.application.di import get_event_bus
            from shared.events import NodeCreated
            asyncio.ensure_future(
                get_event_bus().publish(NodeCreated(
                    user_id=user_id,
                    node_id=node.id,
                    parent_id=parent_id or "",
                    level=level,
                    created_by=created_by,
                ))
            )
        except Exception:
            logger.debug("NodeCreated 事件发布失败", exc_info=True)

        return self._to_schema(node)

    def get_node(self, user_id: str, node_id: str) -> Optional[KnowledgeNodeSchema]:
        """获取知识点"""
        node = get_repo().get_node(node_id, user_id)
        return self._to_schema(node) if node else None

    def update_node(self, user_id: str, node_id: str, **fields) -> Optional[KnowledgeNodeSchema]:
        """更新知识点字段"""
        node = get_repo().get_node(node_id, user_id)
        if not node:
            return None
        for key, value in fields.items():
            if hasattr(node, key):
                setattr(node, key, value)
        node.bump_version()
        get_repo().upsert_node(node, user_id)
        return self._to_schema(node)

    def delete_node(self, user_id: str, node_id: str) -> bool:
        """删除知识点 (级联删除子节点)"""
        node = get_repo().get_node(node_id, user_id)
        if not node:
            return False
        # 递归删除子节点
        for child_id in node.children:
            self.delete_node(user_id, child_id)
        get_repo().delete_node(node_id, user_id)
        return True

    def list_nodes(
        self, user_id: str, parent_id: str | None = None,
        level: str | None = None,
    ) -> list[KnowledgeNodeSchema]:
        """列出知识点"""
        if parent_id is not None:
            nodes = get_repo().get_children(parent_id, user_id)
        elif level is not None:
            nodes = get_repo().get_nodes_by_level(level, user_id)
        else:
            nodes = get_repo().list_all_nodes(user_id)
        return [self._to_schema(n) for n in nodes]

    def get_subtree(self, user_id: str, root_id: str) -> dict[str, KnowledgeNodeSchema]:
        """获取子树"""
        nodes = get_repo().get_subtree(root_id, user_id)
        return {nid: self._to_schema(n) for nid, n in nodes.items()}

    def search(self, user_id: str, query: str, limit: int = 20) -> list[KnowledgeNodeSchema]:
        """搜索知识点"""
        nodes = get_repo().search_by_text(query, user_id, limit)
        return [self._to_schema(n) for n in nodes]

    def add_prerequisite(self, user_id: str, node_id: str, prereq_id: str, prereq_type: str = "strict") -> bool:
        """添加前置知识点"""
        node = get_repo().get_node(node_id, user_id)
        if not node:
            return False
        if not any(p.id == prereq_id for p in node.prerequisites):
            node.prerequisites.append(Prerequisite(id=prereq_id, type=prereq_type))
            node.bump_version()
            get_repo().upsert_node(node, user_id)
        return True

    def remove_prerequisite(self, user_id: str, node_id: str, prereq_id: str) -> bool:
        """移除前置知识点"""
        node = get_repo().get_node(node_id, user_id)
        if not node:
            return False
        node.prerequisites = [p for p in node.prerequisites if p.id != prereq_id]
        node.bump_version()
        get_repo().upsert_node(node, user_id)
        return True

    def add_associate(self, user_id: str, node_id: str, target_id: str, strength: float = 0.5, rel_type: str = "analogy") -> bool:
        """添加关联知识点"""
        node = get_repo().get_node(node_id, user_id)
        if not node:
            return False
        if not any(a.id == target_id for a in node.associates):
            node.associates.append(Associate(id=target_id, strength=strength, type=rel_type))
            node.bump_version()
            get_repo().upsert_node(node, user_id)
        return True

    def set_visibility(self, user_id: str, node_id: str, visible: bool) -> bool:
        """设置节点可见性"""
        node = get_repo().get_node(node_id, user_id)
        if not node:
            return False
        node.is_visible = visible
        node.bump_version()
        get_repo().upsert_node(node, user_id)
        return True

    def reorder_children(self, user_id: str, parent_id: str, children_order: list[str]) -> bool:
        """重新排序子节点"""
        node = get_repo().get_node(parent_id, user_id)
        if not node:
            return False
        node.children = children_order
        node.bump_version()
        get_repo().upsert_node(node, user_id)
        return True

    # ── 转换 ──

    def _to_schema(self, node: CognitiveNode) -> KnowledgeNodeSchema:
        """CognitiveNode → KnowledgeNodeSchema"""
        return KnowledgeNodeSchema(
            id=node.id,
            user_id=node.id,  # 保留 user_id 占位
            parent_id=node.parent,
            label=node.label,
            level=node.level,
            brief=node.brief,
            tags=getattr(node, 'tags', []),
            created_by=getattr(node, 'created_by', 'user'),
            children_order=node.children,
            prerequisites=[p.model_dump() for p in node.prerequisites],
            unlocks=[u.model_dump() for u in node.unlocks],
            associates=[a.model_dump() for a in node.associates],
            emoji=node.emoji,
            color=node.color,
            sort_order=node.sort_order,
            is_visible=node.is_visible,
            node_type=node.node_type,
            mastery=node.belief.proficiency_mean,
            mastery_level=_get_mastery_label(node.belief.proficiency_mean),
            path_id=node.path_id,
            created_at=node.meta.created_at,
            updated_at=node.meta.updated_at,
            is_active=node.is_active,
        )


def _get_mastery_label(proficiency: float) -> str:
    if proficiency < 0.3:
        return "未接触"
    elif proficiency < 0.5:
        return "初学"
    elif proficiency < 0.7:
        return "掌握中"
    elif proficiency < 0.85:
        return "熟练"
    else:
        return "精通"


kn_svc = KnowledgeNodeService()