"""KnowledgeEdge 存储层 — knowledge_edges 表 CRUD"""
from __future__ import annotations

import math
import time
import logging
from typing import Optional

from app.cognitive.edge_models import KnowledgeEdge
from app.db.database import get_db

logger = logging.getLogger(__name__)


def upsert_edge(edge: KnowledgeEdge) -> None:
    """插入或更新一条知识边"""
    db = get_db()
    from datetime import datetime, timezone
    now_iso = datetime.now(timezone.utc).isoformat()
    db.execute("""
        INSERT INTO knowledge_edges
            (id, user_id, source_node_id, target_node_id, edge_type,
             strength, confidence, trust_score, edge_status,
             created_by, created_at, last_evaluated_at)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (source_node_id, target_node_id, edge_type)
        DO UPDATE SET
            strength = EXCLUDED.strength,
            confidence = EXCLUDED.confidence,
            trust_score = EXCLUDED.trust_score,
            edge_status = EXCLUDED.edge_status,
            last_evaluated_at = EXCLUDED.last_evaluated_at
    """, (
        edge.id, edge.user_id, edge.source_node_id, edge.target_node_id,
        edge.edge_type, edge.strength, edge.confidence, edge.trust_score,
        edge.edge_status, edge.created_by, now_iso, now_iso,
    ))


def get_edge(edge_id: str) -> Optional[KnowledgeEdge]:
    """通过 ID 获取边"""
    db = get_db()
    row = db.fetchone(
        "SELECT * FROM knowledge_edges WHERE id = %s", (edge_id,),
    )
    if not row:
        return None
    return _row_to_edge(row)


def get_edges_for_node(node_id: str, user_id: str) -> list[KnowledgeEdge]:
    """获取某节点的所有关联边（出边 + 入边）"""
    db = get_db()
    rows = db.fetchall(
        "SELECT * FROM knowledge_edges "
        "WHERE (source_node_id = %s OR target_node_id = %s) AND user_id = %s",
        (node_id, node_id, user_id),
    )
    return [_row_to_edge(r) for r in rows]


def get_edges_by_status(
    status: str, user_id: str, limit: int = 50,
) -> list[KnowledgeEdge]:
    """按边状态检索"""
    db = get_db()
    rows = db.fetchall(
        "SELECT * FROM knowledge_edges "
        "WHERE edge_status = %s AND user_id = %s LIMIT %s",
        (status, user_id, limit),
    )
    return [_row_to_edge(r) for r in rows]


def get_lazy_trust(edge_id: str) -> float:
    """惰性获取信任度：读时计算衰减并写回"""
    edge = get_edge(edge_id)
    if not edge:
        return 0.0
    now = time.time()
    days = (now - edge.last_evaluated_at) / 86400.0
    if days <= 0:
        return edge.trust_score
    decay = math.exp(-0.015 * days)
    new_score = edge.trust_score * decay
    # 变化超过 0.01 才写库
    if abs(new_score - edge.trust_score) >= 0.01:
        from datetime import datetime, timezone
        now_iso = datetime.now(timezone.utc).isoformat()
        db = get_db()
        db.execute(
            "UPDATE knowledge_edges SET trust_score = %s, last_evaluated_at = %s WHERE id = %s",
            (new_score, now_iso, edge_id),
        )
    return max(0.0, min(1.0, new_score))


def update_edge_status(edge_id: str, new_status: str) -> None:
    """更新边状态（确认/拒绝/重置）"""
    db = get_db()
    db.execute(
        "UPDATE knowledge_edges SET edge_status = %s WHERE id = %s",
        (new_status, edge_id),
    )


def delete_edge(edge_id: str) -> None:
    """删除边"""
    db = get_db()
    db.execute("DELETE FROM knowledge_edges WHERE id = %s", (edge_id,))


def _row_to_edge(row: dict) -> KnowledgeEdge:
    """数据库行 → KnowledgeEdge"""
    ts = row.get("created_at")
    created_at = ts.timestamp() if hasattr(ts, "timestamp") else float(ts or 0)
    last_ev = row.get("last_evaluated_at")
    last_evaluated_at = last_ev.timestamp() if hasattr(last_ev, "timestamp") else float(last_ev or 0)
    return KnowledgeEdge(
        id=row["id"],
        user_id=row["user_id"],
        source_node_id=row["source_node_id"],
        target_node_id=row["target_node_id"],
        edge_type=row.get("edge_type", "related_to"),
        strength=row.get("strength", 0.5),
        confidence=row.get("confidence"),
        trust_score=row.get("trust_score", 0.5),
        edge_status=row.get("edge_status", "suggested"),
        created_by=row.get("created_by", "system"),
        created_at=created_at,
        last_evaluated_at=last_evaluated_at,
    )
