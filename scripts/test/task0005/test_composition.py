"""Task #5 Composition 组块形成测试"""

from __future__ import annotations

import time
import uuid

from app.domain.cognitive.events import CognitiveEventHandler, CognitiveEventRecord
from app.infrastructure.db import get_db_session
from app.infrastructure.db.models.cognitive import KnowledgeNodeORM


def _make_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


def _create_atom(session, user_id: str, node_id: str, label: str):
    node = session.query(KnowledgeNodeORM).filter_by(user_id=user_id, id=node_id).first()
    if node is None:
        node = KnowledgeNodeORM(
            id=node_id,
            user_id=user_id,
            label=label,
            level="atom",
            node_type="test",
            is_visible=True,
        )
        session.add(node)
        session.commit()
    return node


def test_composition_forming() -> None:
    user_id = _make_id("user")
    session_id = "comp_test_session"
    node_a = _make_id("atom")
    node_b = _make_id("atom")

    with get_db_session() as session:
        _create_atom(session, user_id, node_a, "组块节点 A")
        _create_atom(session, user_id, node_b, "组块节点 B")

        handler = CognitiveEventHandler(session)

        # 同一 session 内两个节点各练习多次，且都成功以提升 proficiency
        for i in range(12):
            for node_id in (node_a, node_b):
                event = CognitiveEventRecord(
                    id=_make_id("ev"),
                    event_type="practice_response",
                    user_id=user_id,
                    source_type="test",
                    source_id=_make_id("src"),
                    payload={
                        "node_id": node_id,
                        "session_id": session_id,
                        "question_id": _make_id("q"),
                        "timestamp": time.time() + i,
                        "success": True,
                        "latency_ms": 1000.0,
                        "weight": 1.0,
                        "difficulty": 0.0,
                        "time_spent": 5.0,
                    },
                )
                handler.process_event(event)

        from app.infrastructure.db.cognitive_projection_repository import (
            CognitiveProjectionRepository,
        )

        repo = CognitiveProjectionRepository(session)
        proj_a = repo.get(node_a)
        proj_b = repo.get(node_b)

        assert proj_a is not None
        assert proj_b is not None
        print(f"A proficiency={proj_a.bkt_proficiency} stability={proj_a.trend_stability}")
        print(f"B proficiency={proj_b.bkt_proficiency} stability={proj_b.trend_stability}")
        print(f"A chunk_id={proj_a.comp_chunk_id} status={proj_a.comp_chunking_status}")
        print(f"B chunk_id={proj_b.comp_chunk_id} status={proj_b.comp_chunking_status}")

        # 如果 proficiency/stability 都达标，应该形成组块
        if proj_a.bkt_proficiency >= 0.8 and proj_b.bkt_proficiency >= 0.8:
            assert proj_a.comp_chunk_id == proj_b.comp_chunk_id
            assert proj_a.comp_chunk_id.startswith("chunk_")
            assert proj_a.comp_chunking_status in ("forming", "formed")

        # 检查子表成员
        members = repo.list_composition_members(proj_a.comp_chunk_id)
        member_ids = {m.node_id for m in members}
        assert node_a in member_ids
        assert node_b in member_ids

        print("test_composition_forming OK")


if __name__ == "__main__":
    test_composition_forming()
