"""
MemoryCognitiveNodeRepository — 内存 fake 实现

用于测试场景，无需数据库即可操作 CognitiveNode。
"""
from __future__ import annotations

import copy
import time
from typing import Optional

from app.domain.cognitive.models import CognitiveNode


# 简单的事件记录结构（取代 infrastructure Event 模型）
class _FakeEvent:
    """内存 fake 用的事件记录，仅支持 status/id/event_type/payload 字段"""
    def __init__(self, event_id: str = "", event_type: str = "", status: str = "pending", payload: dict | None = None):
        self.id = event_id
        self.event_type = event_type
        self.status = status
        self.payload = payload or {}


class MemoryCognitiveNodeRepository:
    """CognitiveNode 内存 fake — 不依赖 PostgreSQL

    所有数据保存在内存字典中，适合测试和原型开发。

    与 ProductionCognitiveNodeRepository 实现同一接口（CognitiveNodeRepository Protocol）。
    """

    def __init__(self):
        self._nodes: dict[str, dict[str, CognitiveNode]] = {}  # user_id → {node_id → node}
        self._events: list[_FakeEvent] = []

    # ── CRUD ──

    def upsert_node(self, node: CognitiveNode, user_id: str = "default") -> None:
        self._nodes.setdefault(user_id, {})[node.id] = copy.deepcopy(node)

    def get_node(self, node_id: str, user_id: str = "default") -> Optional[CognitiveNode]:
        nodes = self._nodes.get(user_id, {})
        raw = nodes.get(node_id)
        return copy.deepcopy(raw) if raw else None

    def delete_node(self, node_id: str, user_id: str = "default") -> None:
        nodes = self._nodes.get(user_id, {})
        if node_id in nodes:
            nodes[node_id] = None  # 标记删除

    def get_children(self, parent_id: str, user_id: str = "default") -> list[CognitiveNode]:
        nodes = self._nodes.get(user_id, {}).values()
        return [copy.deepcopy(n) for n in nodes if n and n.parent == parent_id]

    def get_visible_children(self, parent_id: str, user_id: str = "default") -> list[CognitiveNode]:
        return [n for n in self.get_children(parent_id, user_id) if n.is_visible]

    def get_nodes_by_level(self, level: str, user_id: str = "default") -> list[CognitiveNode]:
        nodes = self._nodes.get(user_id, {}).values()
        return [copy.deepcopy(n) for n in nodes if n and n.level == level]

    def list_all_nodes(self, user_id: str = "default") -> list[CognitiveNode]:
        nodes = self._nodes.get(user_id, {}).values()
        return [copy.deepcopy(n) for n in nodes if n]

    def find_node_by_path(self, path_id: str, user_id: str = "default") -> Optional[CognitiveNode]:
        nodes = self._nodes.get(user_id, {}).values()
        for n in nodes:
            if n and n.path_id == path_id:
                return copy.deepcopy(n)
        return None

    def find_node_by_label(
        self, label: str, user_id: str = "default", level: str | None = None
    ) -> Optional[CognitiveNode]:
        nodes = self._nodes.get(user_id, {}).values()
        for n in nodes:
            if n and n.label == label:
                if level is None or n.level == level:
                    return copy.deepcopy(n)
        return None

    def get_subtree(self, root_id: str, user_id: str = "default") -> dict[str, CognitiveNode]:
        result = {}
        all_nodes = self._nodes.get(user_id, {})
        root = all_nodes.get(root_id)
        if not root:
            return result
        result[root_id] = copy.deepcopy(root)
        for n in all_nodes.values():
            if n and n.parent == root_id:
                result.update(self.get_subtree(n.id, user_id))
        return result

    # ── 辅助查询 ──

    def get_suggested_count(self, parent_id: str, user_id: str = "default") -> int:
        nodes = self._nodes.get(user_id, {}).values()
        return sum(1 for n in nodes if n and n.parent == parent_id and n.node_type == "suggested")

    def get_child_count(self, parent_id: str, user_id: str = "default") -> int:
        nodes = self._nodes.get(user_id, {}).values()
        return sum(1 for n in nodes if n and n.parent == parent_id)

    def set_node_visible(self, node_id: str, user_id: str = "default") -> None:
        nodes = self._nodes.get(user_id, {})
        if node_id in nodes and nodes[node_id]:
            nodes[node_id].is_visible = True

    def get_urgent_nodes(self, user_id: str = "default", top_k: int = 10) -> list[dict]:
        # 内存实现：返回空列表
        return []

    # ── 向量搜索 ──

    def search_nodes(
        self,
        query_embedding: list[float],
        user_id: str = "default",
        level: str = "topic",
        limit: int = 10,
        min_similarity: float = 0.3,
    ) -> list[dict]:
        # 内存实现：返回空列表（向量搜索需要数据库）
        return []

    def search_by_text(
        self,
        query: str,
        user_id: str = "default",
        limit: int = 20,
    ) -> list[CognitiveNode]:
        """文本搜索节点（内存实现：简单前缀匹配）"""
        all_nodes = self.list_all_nodes(user_id)
        q = query.lower()
        return [n for n in all_nodes if q in n.label.lower() or q in n.id.lower()][:limit]

    def vector_search(
        self,
        query_embedding: list[float],
        user_id: str = "default",
        level: str | None = None,
        limit: int = 10,
        min_similarity: float = 0.1,
    ) -> list[dict]:
        # 内存实现：返回空列表（向量搜索需要数据库）
        return []

    # ── 认知事件 (已废弃, 仅保留兼容) ──

    def append_event(self, event: _FakeEvent) -> None:
        self._events.append(event)

    def get_unprocessed_events(self, limit: int = 100) -> list[_FakeEvent]:
        return [e for e in self._events if e.status == "pending"][:limit]

    def mark_event_processed(self, event_id: str) -> None:
        for e in self._events:
            if e.id == event_id:
                e.status = "done"
                break

    def query_events(
        self,
        node_id: str | None = None,
        event_type: str | None = None,
        limit: int = 50,
    ) -> list[_FakeEvent]:
        results = self._events
        if node_id:
            results = [e for e in results if e.payload.get("node_id") == node_id]
        if event_type:
            results = [e for e in results if e.event_type == event_type]
        return results[:limit]

    # ── Sync ──

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
        # 内存实现：简单更新节点
        node = self.get_node(skill_id, user_id)
        if node:
            self.upsert_node(node, user_id)
        return {"status": "ok", "node_id": skill_id}

    # ── Writer helpers ──

    def update_extra_fields(
        self,
        node_id: str,
        user_id: str,
        created_by: str,
        description: str = "",
        metadata: str = "",
    ) -> None:
        # 内存实现：no-op（额外字段存储在内存中不需要）
        pass

    def add_to_parent_children(self, node_id: str, parent_id: str, user_id: str = "default") -> None:
        nodes = self._nodes.get(user_id, {})
        parent = nodes.get(parent_id)
        if parent and node_id not in (parent.children or []):
            parent.children = (parent.children or []) + [node_id]
