"""KnowledgeEdge 统一边表 Repository（SQLAlchemy 2.0）"""

from __future__ import annotations

from typing import Any, Optional

from sqlalchemy import and_, or_
from sqlalchemy.orm import Session

from app.infrastructure.db.models.cognitive import KnowledgeEdgeORM, KnowledgeNodeORM


class CognitiveEdgeRepository:
    """只操作 knowledge_edges 统一边表。"""

    def __init__(self, session: Session):
        self._session = session

    # ── 基础 CRUD ──

    def get(self, edge_id: str) -> Optional[KnowledgeEdgeORM]:
        return self._session.query(KnowledgeEdgeORM).filter_by(id=edge_id).first()

    def get_by_endpoints(
        self,
        user_id: str,
        source_id: str,
        target_id: str,
        edge_type: str,
    ) -> Optional[KnowledgeEdgeORM]:
        return (
            self._session.query(KnowledgeEdgeORM)
            .filter_by(
                user_id=user_id,
                source_id=source_id,
                target_id=target_id,
                edge_type=edge_type,
            )
            .first()
        )

    def list_for_node(
        self,
        user_id: str,
        node_id: str,
        edge_type: Optional[str] = None,
    ) -> list[KnowledgeEdgeORM]:
        q = self._session.query(KnowledgeEdgeORM).filter(
            KnowledgeEdgeORM.user_id == user_id,
            or_(
                KnowledgeEdgeORM.source_id == node_id,
                KnowledgeEdgeORM.target_id == node_id,
            ),
        )
        if edge_type:
            q = q.filter_by(edge_type=edge_type)
        return q.order_by(KnowledgeEdgeORM.edge_type, KnowledgeEdgeORM.strength.desc()).all()

    def list_outgoing(
        self,
        user_id: str,
        source_id: str,
        edge_type: Optional[str] = None,
    ) -> list[KnowledgeEdgeORM]:
        q = self._session.query(KnowledgeEdgeORM).filter_by(
            user_id=user_id, source_id=source_id
        )
        if edge_type:
            q = q.filter_by(edge_type=edge_type)
        return q.order_by(KnowledgeEdgeORM.strength.desc()).all()

    def list_incoming(
        self,
        user_id: str,
        target_id: str,
        edge_type: Optional[str] = None,
    ) -> list[KnowledgeEdgeORM]:
        q = self._session.query(KnowledgeEdgeORM).filter_by(
            user_id=user_id, target_id=target_id
        )
        if edge_type:
            q = q.filter_by(edge_type=edge_type)
        return q.order_by(KnowledgeEdgeORM.strength.desc()).all()

    def list_by_type(self, user_id: str, edge_type: str) -> list[KnowledgeEdgeORM]:
        return (
            self._session.query(KnowledgeEdgeORM)
            .filter_by(user_id=user_id, edge_type=edge_type)
            .order_by(KnowledgeEdgeORM.strength.desc())
            .all()
        )

    def list_all(self, user_id: str) -> list[KnowledgeEdgeORM]:
        return (
            self._session.query(KnowledgeEdgeORM)
            .filter_by(user_id=user_id)
            .order_by(KnowledgeEdgeORM.edge_type)
            .all()
        )

    # ── 写入 ──

    def upsert(self, edge: KnowledgeEdgeORM) -> KnowledgeEdgeORM:
        existing = self.get_by_endpoints(
            edge.user_id, edge.source_id, edge.target_id, edge.edge_type
        )
        if existing is None:
            self._session.add(edge)
        else:
            existing.strength = edge.strength
            existing.edge_metadata = edge.edge_metadata
            self._session.merge(existing)
        self._session.commit()
        return existing if existing else edge

    def create_or_update(
        self,
        user_id: str,
        source_id: str,
        target_id: str,
        edge_type: str,
        strength: float = 0.5,
        edge_metadata: Optional[dict[str, Any]] = None,
    ) -> KnowledgeEdgeORM:
        edge = self.get_by_endpoints(user_id, source_id, target_id, edge_type)
        if edge is None:
            edge = KnowledgeEdgeORM(
                user_id=user_id,
                source_id=source_id,
                target_id=target_id,
                edge_type=edge_type,
                strength=strength,
                edge_metadata=edge_metadata or {},
            )
            self._session.add(edge)
        else:
            edge.strength = strength
            if edge_metadata is not None:
                edge.edge_metadata = edge_metadata
            self._session.merge(edge)
        self._session.commit()
        return edge

    def update_strength(self, edge_id: str, strength: float) -> Optional[KnowledgeEdgeORM]:
        edge = self.get(edge_id)
        if edge is None:
            return None
        edge.strength = max(0.0, min(1.0, strength))
        self._session.commit()
        return edge

    def update_metadata(
        self, edge_id: str, metadata: dict[str, Any]
    ) -> Optional[KnowledgeEdgeORM]:
        edge = self.get(edge_id)
        if edge is None:
            return None
        edge.edge_metadata = metadata
        self._session.commit()
        return edge

    def delete(self, edge_id: str) -> bool:
        edge = self.get(edge_id)
        if edge is None:
            return False
        self._session.delete(edge)
        self._session.commit()
        return True

    def delete_by_endpoints(
        self,
        user_id: str,
        source_id: str,
        target_id: str,
        edge_type: str,
    ) -> bool:
        edge = self.get_by_endpoints(user_id, source_id, target_id, edge_type)
        if edge is None:
            return False
        self._session.delete(edge)
        self._session.commit()
        return True

    # ── 图遍历辅助 ──

    def get_neighbors(
        self,
        user_id: str,
        node_id: str,
        edge_type: Optional[str] = None,
    ) -> list[KnowledgeNodeORM]:
        """返回与 node_id 通过指定类型边相连的所有节点（含双向）。"""
        q = (
            self._session.query(KnowledgeNodeORM)
            .join(
                KnowledgeEdgeORM,
                or_(
                    and_(
                        KnowledgeEdgeORM.source_id == node_id,
                        KnowledgeEdgeORM.target_id == KnowledgeNodeORM.id,
                    ),
                    and_(
                        KnowledgeEdgeORM.target_id == node_id,
                        KnowledgeEdgeORM.source_id == KnowledgeNodeORM.id,
                    ),
                ),
            )
            .filter(
                KnowledgeEdgeORM.user_id == user_id,
                KnowledgeNodeORM.user_id == user_id,
            )
        )
        if edge_type:
            q = q.filter(KnowledgeEdgeORM.edge_type == edge_type)
        return q.all()

    def list_edges_between(
        self,
        user_id: str,
        source_id: str,
        target_id: str,
    ) -> list[KnowledgeEdgeORM]:
        return (
            self._session.query(KnowledgeEdgeORM)
            .filter(
                KnowledgeEdgeORM.user_id == user_id,
                or_(
                    and_(
                        KnowledgeEdgeORM.source_id == source_id,
                        KnowledgeEdgeORM.target_id == target_id,
                    ),
                    and_(
                        KnowledgeEdgeORM.source_id == target_id,
                        KnowledgeEdgeORM.target_id == source_id,
                    ),
                ),
            )
            .all()
        )
