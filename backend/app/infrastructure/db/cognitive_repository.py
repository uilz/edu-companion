"""
PgCognitiveNodeRepository — 新架构视图适配器

实现 CognitiveNodeRepository Protocol，但底层不再读写旧 JSONB 大字段，
而是从 knowledge_nodes（实体层）+ cognitive_node_projections（派生状态层）+
knowledge_edges + 事件子表组装 CognitiveNode 视图。
"""

from __future__ import annotations

import logging
from typing import Optional

from sqlalchemy import func

from app.domain.cognitive import events as _cognitive_events
from app.domain.cognitive.models import CognitiveNode
from app.infrastructure.db import get_db_session
from app.infrastructure.db.cognitive_entity_repository import CognitiveEntityRepository
from app.infrastructure.db.cognitive_view_mapper import build_cognitive_node
from app.infrastructure.db.models.cognitive import (
    CognitiveNodeProjectionORM,
    KnowledgeNodeORM,
)

logger = logging.getLogger(__name__)


class PgCognitiveNodeRepository:
    """PostgreSQL 适配器 — 基于新事件溯源架构的 CognitiveNode 视图。"""

    # ── 读取 ──

    def get_node(self, node_id: str, user_id: str = "default") -> Optional[CognitiveNode]:
        with get_db_session() as session:
            entity_repo = CognitiveEntityRepository(session)
            entity = entity_repo.get(user_id, node_id)
            if entity is None or entity.deleted_at is not None:
                return None
            return build_cognitive_node(session, entity)

    def get_children(self, parent_id: str, user_id: str = "default") -> list[CognitiveNode]:
        with get_db_session() as session:
            entity_repo = CognitiveEntityRepository(session)
            entities = entity_repo.list_by_parent(user_id, parent_id)
            return [
                build_cognitive_node(session, e)
                for e in entities
                if e.deleted_at is None
            ]

    def get_visible_children(
        self, parent_id: str, user_id: str = "default"
    ) -> list[CognitiveNode]:
        with get_db_session() as session:
            entity_repo = CognitiveEntityRepository(session)
            entities = entity_repo.list_by_parent(user_id, parent_id)
            return [
                build_cognitive_node(session, e)
                for e in entities
                if e.deleted_at is None and e.is_visible
            ]

    def get_nodes_by_level(self, level: str, user_id: str = "default") -> list[CognitiveNode]:
        with get_db_session() as session:
            entity_repo = CognitiveEntityRepository(session)
            entities = entity_repo.list_by_level(user_id, level)
            return [
                build_cognitive_node(session, e)
                for e in entities
                if e.deleted_at is None
            ]

    def list_all_nodes(self, user_id: str = "default") -> list[CognitiveNode]:
        with get_db_session() as session:
            entity_repo = CognitiveEntityRepository(session)
            entities = entity_repo.list_all(user_id)
            return [
                build_cognitive_node(session, e)
                for e in entities
                if e.deleted_at is None
            ]

    def search_nodes(
        self,
        query_embedding: list[float],
        user_id: str = "default",
        level: str = "topic",
        limit: int = 10,
        min_similarity: float = 0.3,
    ) -> list[dict]:
        """向量搜索节点（Python 端计算余弦相似度）。"""
        return self.vector_search(
            query_embedding,
            user_id=user_id,
            level=level,
            limit=limit,
            min_similarity=min_similarity,
        )

    def search_by_text(
        self,
        query: str,
        user_id: str = "default",
        limit: int = 20,
    ) -> list[CognitiveNode]:
        with get_db_session() as session:
            entity_repo = CognitiveEntityRepository(session)
            entities = entity_repo.search(user_id, query, limit=limit)
            return [
                build_cognitive_node(session, e)
                for e in entities
                if e.deleted_at is None
            ]

    def vector_search(
        self,
        query_embedding: list[float],
        user_id: str = "default",
        level: str | None = None,
        limit: int = 10,
        min_similarity: float = 0.1,
    ) -> list[dict]:
        """向量检索：按余弦相似度在 Python 端计算。"""
        query_norm = _cosine_normalize(query_embedding)

        with get_db_session() as session:
            entity_repo = CognitiveEntityRepository(session)
            entities = entity_repo.list_all(user_id)

            results = []
            for entity in entities:
                if entity.deleted_at is not None:
                    continue
                if level and entity.level != level:
                    continue
                embed = entity.embedding
                if not embed:
                    continue
                sim = _cosine_similarity(query_norm, embed)
                if sim < min_similarity:
                    continue
                results.append({
                    "id": entity.id,
                    "label": entity.label,
                    "path_id": entity.path_id or "",
                    "level": entity.level,
                    "is_visible": entity.is_visible,
                    "similarity": round(sim, 6),
                })

            results.sort(key=lambda x: -x["similarity"])
            return results[:limit]

    def find_node_by_path(
        self, path_id: str, user_id: str = "default"
    ) -> Optional[CognitiveNode]:
        with get_db_session() as session:
            entity_repo = CognitiveEntityRepository(session)
            entity = (
                session.query(KnowledgeNodeORM)
                .filter_by(user_id=user_id, path_id=path_id, deleted_at=None)
                .first()
            )
            if entity is None:
                return None
            return build_cognitive_node(session, entity)

    def find_node_by_label(
        self, label: str, user_id: str = "default", level: str | None = None
    ) -> Optional[CognitiveNode]:
        with get_db_session() as session:
            entity_repo = CognitiveEntityRepository(session)
            entity = entity_repo.get_by_label(user_id, label, level=level)
            if entity is None or entity.deleted_at is not None:
                return None
            return build_cognitive_node(session, entity)

    def get_subtree(self, root_id: str, user_id: str = "default") -> dict[str, CognitiveNode]:
        """获取以 root_id 为根的整个子树（递归 CTE）。"""
        with get_db_session() as session:
            from sqlalchemy import text
            rows = session.execute(
                text("""
                    WITH RECURSIVE subtree AS (
                        SELECT * FROM knowledge_nodes
                        WHERE id = :root_id AND user_id = :user_id AND deleted_at IS NULL
                        UNION ALL
                        SELECT kn.* FROM knowledge_nodes kn
                        JOIN subtree ON kn.parent_id = subtree.id
                        WHERE kn.user_id = :user_id AND kn.deleted_at IS NULL
                    )
                    SELECT * FROM subtree
                """),
                {"root_id": root_id, "user_id": user_id},
            ).mappings().all()

            result: dict[str, CognitiveNode] = {}
            for row in rows:
                entity = session.get(KnowledgeNodeORM, row["id"])
                if entity:
                    result[entity.id] = build_cognitive_node(session, entity)
            return result

    def get_suggested_count(self, parent_id: str, user_id: str = "default") -> int:
        with get_db_session() as session:
            count = (
                session.query(func.count(KnowledgeNodeORM.id))
                .filter(
                    KnowledgeNodeORM.user_id == user_id,
                    KnowledgeNodeORM.parent_id == parent_id,
                    KnowledgeNodeORM.is_visible == False,
                    KnowledgeNodeORM.deleted_at.is_(None),
                    KnowledgeNodeORM.node_type.in_(["auto_generated", "suggested"]),
                )
                .scalar()
            )
            return count or 0

    def get_child_count(self, parent_id: str, user_id: str = "default") -> int:
        with get_db_session() as session:
            count = (
                session.query(func.count(KnowledgeNodeORM.id))
                .filter(
                    KnowledgeNodeORM.user_id == user_id,
                    KnowledgeNodeORM.parent_id == parent_id,
                    KnowledgeNodeORM.is_visible == True,
                    KnowledgeNodeORM.deleted_at.is_(None),
                )
                .scalar()
            )
            return count or 0

    def get_urgent_nodes(
        self, user_id: str = "default", top_k: int = 10
    ) -> list[dict]:
        with get_db_session() as session:
            projections = (
                session.query(CognitiveNodeProjectionORM)
                .filter_by(user_id=user_id)
                .order_by(CognitiveNodeProjectionORM.sched_urgency.desc())
                .limit(top_k)
                .all()
            )

            results = []
            for proj in projections:
                entity = CognitiveEntityRepository(session).get(user_id, proj.node_id)
                if entity is None or entity.deleted_at is not None:
                    continue
                node = build_cognitive_node(session, entity, projection=proj)
                results.append({
                    "node_id": node.id,
                    "label": node.label,
                    "level": node.level,
                    "urgency": node.scheduling.urgency,
                    "proficiency_mean": node.belief.proficiency_mean,
                    "direction": node.trend.direction,
                    "stagnation_days": node.trend.stagnation_days,
                    "action_type": node.scheduling.next_action_type,
                    "reason": "",
                })
            return results

    # ── 写入 ──

    def upsert_node(self, node: CognitiveNode, user_id: str = "default") -> None:
        """只写实体层字段；派生状态由事件/投影层维护。"""
        with get_db_session() as session:
            entity_repo = CognitiveEntityRepository(session)
            existing = entity_repo.get(user_id, node.id)
            if existing is None:
                entity = KnowledgeNodeORM(
                    id=node.id,
                    user_id=user_id,
                    label=node.label,
                    level=node.level,
                    parent_id=node.parent,
                    path_id=node.path_id or "",
                    node_type=node.node_type or "explicit",
                    is_visible=node.is_visible,
                    is_active=node.is_active,
                    is_core=node.is_core,
                    brief=node.brief or "",
                    emoji=node.emoji or "",
                    color=node.color or "",
                    sort_order=node.sort_order or 0,
                    tags=list(node.tags or []),
                    created_by=node.created_by or "user",
                    embedding=node.embedding,
                )
            else:
                entity = existing
                entity.label = node.label
                entity.level = node.level
                entity.parent_id = node.parent
                entity.path_id = node.path_id or ""
                entity.node_type = node.node_type or entity.node_type
                entity.is_visible = node.is_visible
                entity.is_active = node.is_active
                entity.is_core = node.is_core
                entity.brief = node.brief or ""
                entity.emoji = node.emoji or ""
                entity.color = node.color or ""
                entity.sort_order = node.sort_order or 0
                entity.tags = list(node.tags or [])
                entity.created_by = node.created_by or entity.created_by
                entity.embedding = node.embedding
            entity_repo.upsert(entity)

    def delete_node(self, node_id: str, user_id: str = "default") -> None:
        """软删除节点（级联子节点、投影、事件由 DB 外键/触发器处理）。"""
        with get_db_session() as session:
            entity_repo = CognitiveEntityRepository(session)
            entity = entity_repo.get(user_id, node_id)
            if entity is None:
                return
            # 级联软删除子节点
            _soft_delete_subtree(session, entity)
            session.commit()

    def set_node_visible(self, node_id: str, user_id: str = "default") -> None:
        """设置节点可见，并级联设置所有祖先节点可见。"""
        with get_db_session() as session:
            entity_repo = CognitiveEntityRepository(session)
            entity = entity_repo.get(user_id, node_id)
            if entity is None:
                return

            entity.is_visible = True
            entity_repo.upsert(entity)

            # 级联父节点
            parent_id = entity.parent_id
            visited = {node_id}
            while parent_id and parent_id not in visited:
                visited.add(parent_id)
                parent = entity_repo.get(user_id, parent_id)
                if parent is None:
                    break
                parent.is_visible = True
                entity_repo.upsert(parent)
                parent_id = parent.parent_id

    def update_extra_fields(
        self,
        node_id: str,
        user_id: str,
        created_by: str,
        description: str = "",
        metadata: str = "",
    ) -> None:
        """写入 pydantic model 未声明的额外 DB 字段。"""
        fields: dict = {"created_by": created_by}
        if description:
            fields["brief"] = description
        if metadata:
            logger.debug("update_extra_fields: metadata 字段在新 schema 中无对应列，已忽略")
        with get_db_session() as session:
            CognitiveEntityRepository(session).update_fields(
                user_id, node_id, **fields
            )

    def add_to_parent_children(
        self, node_id: str, parent_id: str, user_id: str = "default"
    ) -> None:
        """将 node_id 设置为 parent_id 的子节点（更新 parent_id 关系）。"""
        with get_db_session() as session:
            entity_repo = CognitiveEntityRepository(session)
            child = entity_repo.get(user_id, node_id)
            if child is None:
                return
            child.parent_id = parent_id
            entity_repo.upsert(child)

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
        """通过事件总线写入 practice_response 事件，由 ProjectionBuilder 更新投影。"""
        try:
            result = _cognitive_events.submit_practice(
                user_id=user_id,
                node_id=skill_id,
                success=is_correct,
                latency_ms=response_time_ms,
                question_id=question_id,
                difficulty=0.0,
                time_spent=response_time_ms / 1000.0,
            )
            return {"status": "ok", "result": result}
        except Exception as e:
            logger.warning("sync_from_practice_event failed: %s", e)
            return {"status": "error", "error": str(e)}


# ── 辅助 ──


def _soft_delete_subtree(session, entity: KnowledgeNodeORM) -> None:
    """递归软删除子树。"""
    entity.deleted_at = func.now()
    session.merge(entity)
    for child in entity.children or []:
        _soft_delete_subtree(session, child)


def _cosine_normalize(vec: list[float]) -> tuple[list[float], float]:
    norm = sum(v * v for v in vec) ** 0.5
    if norm == 0:
        return vec, 0.0
    return [v / norm for v in vec], norm


def _cosine_similarity(
    norm_a: tuple[list[float], float] | list[float],
    norm_b: tuple[list[float], float] | list[float],
) -> float:
    if isinstance(norm_a, tuple):
        a = norm_a[0]
    else:
        a, _ = _cosine_normalize(norm_a)
    if isinstance(norm_b, tuple):
        b = norm_b[0]
    else:
        b, _ = _cosine_normalize(norm_b)
    dot = sum(av * bv for av, bv in zip(a, b))
    return max(-1.0, min(1.0, dot))
