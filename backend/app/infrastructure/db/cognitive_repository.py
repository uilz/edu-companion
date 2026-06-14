"""
PgCognitiveNodeRepository — PostgreSQL 适配器

实现 CognitiveNodeRepository Protocol，委托到 storage.py 的函数。
"""
from __future__ import annotations

from typing import Optional

from app.domain.cognitive.models import CognitiveNode
from app.infrastructure.db import cognitive_storage as _s


class PgCognitiveNodeRepository:
    """PostgreSQL 适配器 — 实现 CognitiveNodeRepository Protocol

    所有方法委托到 app.domain.cognitive.storage 的模块级函数。
    保持向后兼容——直接 import storage 的旧代码仍然可用。
    """

    def upsert_node(self, node: CognitiveNode, user_id: str = "default") -> None:
        _s.upsert_node(node, user_id)

    def get_node(self, node_id: str, user_id: str = "default") -> Optional[CognitiveNode]:
        return _s.get_node(node_id, user_id)

    def delete_node(self, node_id: str, user_id: str = "default") -> None:
        _s.delete_node(node_id, user_id)

    def get_children(self, parent_id: str, user_id: str = "default") -> list[CognitiveNode]:
        return _s.get_children(parent_id, user_id)

    def get_visible_children(self, parent_id: str, user_id: str = "default") -> list[CognitiveNode]:
        return _s.get_visible_children(parent_id, user_id)

    def get_nodes_by_level(self, level: str, user_id: str = "default") -> list[CognitiveNode]:
        return _s.get_nodes_by_level(level, user_id)

    def list_all_nodes(self, user_id: str = "default") -> list[CognitiveNode]:
        return _s.list_all_nodes(user_id)

    def search_nodes(
        self,
        query_embedding: list[float],
        user_id: str = "default",
        level: str = "topic",
        limit: int = 10,
        min_similarity: float = 0.3,
    ) -> list[dict]:
        return _s.search_nodes(query_embedding, user_id, level, limit, min_similarity)

    def search_by_text(
        self,
        query: str,
        user_id: str = "default",
        limit: int = 20,
    ) -> list[CognitiveNode]:
        """文本搜索节点（ILIKE 匹配 label/id）"""
        return _s.search_nodes(query, user_id, limit)

    def vector_search(
        self,
        query_embedding: list[float],
        user_id: str = "default",
        level: str | None = None,
        limit: int = 10,
        min_similarity: float = 0.1,
    ) -> list[dict]:
        return _s.vector_search(query_embedding, user_id, level, limit, min_similarity)

    def find_node_by_path(self, path_id: str, user_id: str = "default") -> Optional[CognitiveNode]:
        return _s.find_node_by_path(path_id, user_id)

    def find_node_by_label(
        self, label: str, user_id: str = "default", level: str | None = None
    ) -> Optional[CognitiveNode]:
        return _s.find_node_by_label(label, user_id, level)

    def get_subtree(self, root_id: str, user_id: str = "default") -> dict[str, CognitiveNode]:
        return _s.get_subtree(root_id, user_id)

    def get_suggested_count(self, parent_id: str, user_id: str = "default") -> int:
        return _s.get_suggested_count(parent_id, user_id)

    def get_child_count(self, parent_id: str, user_id: str = "default") -> int:
        return _s.get_child_count(parent_id, user_id)

    def set_node_visible(self, node_id: str, user_id: str = "default") -> None:
        _s.set_node_visible(node_id, user_id)

    def get_urgent_nodes(self, user_id: str = "default", top_k: int = 10) -> list[dict]:
        return _s.get_urgent_nodes(user_id, top_k)

    def sync_from_practice_event(
        self,
        user_id: str,
        skill_id: str,
        is_correct: bool,
        response_time_ms: float = 500.0,
        topic: str = "",
        question_id: str = "",
        error_type: str = "",
    ) -> dict:
        return _s.sync_from_practice_event(
            user_id, skill_id, is_correct,
            response_time_ms, topic, question_id, error_type,
        )

    def update_extra_fields(
        self,
        node_id: str,
        user_id: str,
        created_by: str,
        description: str = "",
        metadata: str = "",
    ) -> None:
        db = _s.get_db()
        fields = {"created_by": created_by}
        if description:
            fields["description"] = description
        if metadata:
            fields["metadata"] = metadata
        set_expr = ", ".join(f"{k} = %s" for k in fields)
        values = list(fields.values())
        values.extend([node_id, user_id])
        db.execute(
            f"UPDATE cognitive_nodes SET {set_expr} WHERE id = %s AND user_id = %s",
            values,
        )

    def add_to_parent_children(self, node_id: str, parent_id: str, user_id: str = "default") -> None:
        import json as _json
        db = _s.get_db()
        db.execute(
            "UPDATE cognitive_nodes SET children = children || %s::jsonb, "
            "updated_at = NOW() WHERE id = %s AND user_id = %s "
            "AND NOT (children @> %s::jsonb)",
            (_json.dumps([node_id]), parent_id, user_id, _json.dumps([node_id])),
        )
