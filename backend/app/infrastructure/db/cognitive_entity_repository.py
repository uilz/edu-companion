"""KnowledgeNode 实体层 Repository（瘦实体表）"""

from __future__ import annotations

from typing import Optional

from sqlalchemy.orm import Session

from app.infrastructure.db.models.cognitive import KnowledgeNodeORM


class CognitiveEntityRepository:
    """只操作 knowledge_nodes 核心身份与元数据。"""

    def __init__(self, session: Session):
        self._session = session

    def get(self, user_id: str, node_id: str) -> Optional[KnowledgeNodeORM]:
        return (
            self._session.query(KnowledgeNodeORM)
            .filter_by(user_id=user_id, id=node_id)
            .first()
        )

    def get_by_label(
        self, user_id: str, label: str, level: Optional[str] = None
    ) -> Optional[KnowledgeNodeORM]:
        q = self._session.query(KnowledgeNodeORM).filter(
            KnowledgeNodeORM.user_id == user_id,
            KnowledgeNodeORM.label.ilike(label),
        )
        if level:
            q = q.filter(KnowledgeNodeORM.level == level)
        return q.first()

    def list_by_parent(self, user_id: str, parent_id: Optional[str] = None) -> list[KnowledgeNodeORM]:
        return (
            self._session.query(KnowledgeNodeORM)
            .filter_by(user_id=user_id, parent_id=parent_id)
            .order_by(KnowledgeNodeORM.sort_order, KnowledgeNodeORM.created_at)
            .all()
        )

    def list_by_level(self, user_id: str, level: str) -> list[KnowledgeNodeORM]:
        return (
            self._session.query(KnowledgeNodeORM)
            .filter_by(user_id=user_id, level=level)
            .all()
        )

    def list_all(self, user_id: str) -> list[KnowledgeNodeORM]:
        return (
            self._session.query(KnowledgeNodeORM)
            .filter_by(user_id=user_id)
            .all()
        )

    def search(self, user_id: str, query: str, limit: int = 20) -> list[KnowledgeNodeORM]:
        return (
            self._session.query(KnowledgeNodeORM)
            .filter(
                KnowledgeNodeORM.user_id == user_id,
                KnowledgeNodeORM.label.ilike(f"%{query}%"),
            )
            .limit(limit)
            .all()
        )

    def upsert(self, node: KnowledgeNodeORM) -> KnowledgeNodeORM:
        existing = self.get(node.user_id, node.id)
        if existing is None:
            self._session.add(node)
        else:
            self._session.merge(node)
        self._session.commit()
        return node

    def update_fields(self, user_id: str, node_id: str, **fields) -> Optional[KnowledgeNodeORM]:
        node = self.get(user_id, node_id)
        if node is None:
            return None
        for key, value in fields.items():
            if hasattr(node, key):
                setattr(node, key, value)
        self._session.commit()
        return node

    def delete(self, user_id: str, node_id: str) -> bool:
        node = self.get(user_id, node_id)
        if node is None:
            return False
        # 级联子节点
        children = self.list_by_parent(user_id, node_id)
        for child in children:
            self.delete(user_id, child.id)
        self._session.delete(node)
        self._session.commit()
        return True
