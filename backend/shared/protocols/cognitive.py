"""
CognitiveNode Repository Protocol — 认知节点仓储契约

为 CognitiveNode 存储层提供清晰的接缝，允许测试时注入 MemoryFake。
"""
from __future__ import annotations

from typing import Optional, Protocol, runtime_checkable

from app.domain.cognitive.models import CognitiveNode


@runtime_checkable
class CognitiveNodeRepository(Protocol):
    """CognitiveNode 存储契约"""

    def upsert_node(self, node: CognitiveNode, user_id: str = "default") -> None:
        """插入或更新一个 CognitiveNode"""
        ...

    def get_node(self, node_id: str, user_id: str = "default") -> Optional[CognitiveNode]:
        """获取单个节点"""
        ...

    def delete_node(self, node_id: str, user_id: str = "default") -> None:
        """删除节点（软删除）"""
        ...

    def get_children(self, parent_id: str, user_id: str = "default") -> list[CognitiveNode]:
        """获取某父节点下的所有子节点"""
        ...

    def get_visible_children(self, parent_id: str, user_id: str = "default") -> list[CognitiveNode]:
        """获取可见子节点"""
        ...

    def get_nodes_by_level(self, level: str, user_id: str = "default") -> list[CognitiveNode]:
        """按层级获取节点列表"""
        ...

    def list_all_nodes(self, user_id: str = "default") -> list[CognitiveNode]:
        """获取用户所有节点"""
        ...

    def search_nodes(
        self,
        query_embedding: list[float],
        user_id: str = "default",
        level: str = "topic",
        limit: int = 10,
        min_similarity: float = 0.3,
    ) -> list[dict]:
        """向量搜索节点"""
        ...

    def search_by_text(
        self,
        query: str,
        user_id: str = "default",
        limit: int = 20,
    ) -> list[CognitiveNode]:
        """文本搜索节点（ILIKE 匹配 label/id）"""
        ...

    def vector_search(
        self,
        query_embedding: list[float],
        user_id: str = "default",
        level: str | None = None,
        limit: int = 10,
        min_similarity: float = 0.1,
    ) -> list[dict]:
        """向量检索：按余弦相似度计算（Python 端 fallback）"""
        ...

    def find_node_by_path(self, path_id: str, user_id: str = "default") -> Optional[CognitiveNode]:
        """通过 path_id 查找节点"""
        ...

    def find_node_by_label(
        self, label: str, user_id: str = "default", level: str | None = None
    ) -> Optional[CognitiveNode]:
        """通过 label 查找节点"""
        ...

    def get_subtree(self, root_id: str, user_id: str = "default") -> dict[str, CognitiveNode]:
        """获取子树"""
        ...

    def get_suggested_count(self, parent_id: str, user_id: str = "default") -> int:
        """获取已建议子节点数量"""
        ...

    def get_child_count(self, parent_id: str, user_id: str = "default") -> int:
        """获取子节点数量"""
        ...

    def set_node_visible(self, node_id: str, user_id: str = "default") -> None:
        """设置节点可见"""
        ...

    def get_urgent_nodes(self, user_id: str = "default", top_k: int = 10) -> list[dict]:
        """获取紧急度最高的节点"""
        ...

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
        """从练习事件同步到认知节点"""
        ...

    # ── Writer helpers ──

    def update_extra_fields(
        self,
        node_id: str,
        user_id: str,
        created_by: str,
        description: str = "",
        metadata: str = "",
    ) -> None:
        """写入 pydantic model 未声明的额外 DB 字段"""
        ...

    def add_to_parent_children(self, node_id: str, parent_id: str, user_id: str = "default") -> None:
        """将 node_id 追加到父节点 children 列表（去重）"""
        ...
