"""Task #5 综合测试：认知事件处理与投影重建"""

from __future__ import annotations

import time
import uuid

from app.domain.cognitive.events import CognitiveEventHandler, CognitiveEventRecord
from app.infrastructure.db import get_db_session
from app.infrastructure.db.models.cognitive import KnowledgeNodeORM
from app.infrastructure.db.projection_builder import ProjectionBuilder


def _make_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


def _create_node(session, user_id: str, node_id: str, label: str, level: str = "atom", is_core: bool = False):
    node = session.query(KnowledgeNodeORM).filter_by(user_id=user_id, id=node_id).first()
    if node is None:
        node = KnowledgeNodeORM(
            id=node_id,
            user_id=user_id,
            label=label,
            level=level,
            node_type="test",
            is_visible=True,
            is_core=is_core,
        )
        session.add(node)
        session.commit()
    return node


def test_practice_and_decay() -> None:
    user_id = _make_id("user")
    node_id = _make_id("atom")

    with get_db_session() as session:
        _create_node(session, user_id, node_id, "衰减测试节点")
        handler = CognitiveEventHandler(session)

        # 两次正确练习
        for i in range(2):
            event = CognitiveEventRecord(
                id=_make_id("ev"),
                event_type="practice_response",
                user_id=user_id,
                source_type="test",
                source_id=_make_id("src"),
                payload={
                    "node_id": node_id,
                    "session_id": "s1",
                    "question_id": _make_id("q"),
                    "timestamp": time.time() - 86400.0 * (1 - i),  # 昨天和今天
                    "success": True,
                    "latency_ms": 1500.0,
                    "weight": 1.0,
                    "difficulty": 0.0,
                    "confidence_before": 0.8,
                    "time_spent": 10.0,
                },
            )
            result = handler.process_event(event)
            assert result["status"] == "ok", result

        # daily_tick 触发遗忘衰减
        tick = CognitiveEventRecord(
            id=_make_id("tick"),
            event_type="daily_tick",
            user_id=user_id,
            source_type="test",
            source_id="",
        )
        result = handler.process_event(tick)
        assert result["status"] == "ok"
        assert result["processed_nodes"] >= 1

        print("test_practice_and_decay OK")


def test_edge_and_goal_alignment() -> None:
    user_id = _make_id("user")
    goal_id = _make_id("topic")
    atom_id = _make_id("atom")

    with get_db_session() as session:
        _create_node(session, user_id, goal_id, "目标主题", level="topic", is_core=True)
        _create_node(session, user_id, atom_id, "原子节点", level="atom")

        handler = CognitiveEventHandler(session)

        # 创建边 atom -> topic (unlock)
        edge_event = CognitiveEventRecord(
            id=_make_id("ev"),
            event_type="edge_created",
            user_id=user_id,
            source_type="test",
            source_id="",
            payload={
                "source_id": atom_id,
                "target_id": goal_id,
                "edge_type": "unlock",
                "strength": 0.8,
            },
        )
        result = handler.process_event(edge_event)
        assert result["status"] == "ok", result

        # 检查目标对齐投影
        from app.infrastructure.db.cognitive_projection_repository import CognitiveProjectionRepository

        repo = CognitiveProjectionRepository(session)
        projection = repo.get(atom_id)
        assert projection is not None
        assert projection.goal_distance == 1, projection.goal_distance
        assert projection.goal_on_critical_path is True

        print("test_edge_and_goal_alignment OK")


def test_projection_rebuild() -> None:
    user_id = _make_id("user")
    node_id = _make_id("atom")

    with get_db_session() as session:
        _create_node(session, user_id, node_id, "重建测试节点")

        handler = CognitiveEventHandler(session)
        for i in range(3):
            event = CognitiveEventRecord(
                id=_make_id("ev"),
                event_type="practice_response",
                user_id=user_id,
                source_type="test",
                source_id=_make_id("src"),
                payload={
                    "node_id": node_id,
                    "session_id": "rebuild",
                    "question_id": _make_id("q"),
                    "timestamp": time.time() - 3600.0 * (2 - i),
                    "success": True,
                    "latency_ms": 1000.0,
                    "weight": 1.0,
                },
            )
            handler.process_event(event)

        # 重建
        builder = ProjectionBuilder(session)
        builder.rebuild_node(user_id, node_id)

        repo = builder._projection_repo
        projection = repo.get(node_id)
        assert projection is not None
        assert projection.bkt_proficiency > 0.3

        print("test_projection_rebuild OK")


def main() -> None:
    test_practice_and_decay()
    test_edge_and_goal_alignment()
    test_projection_rebuild()
    print("\nAll cognitive event tests passed.")


if __name__ == "__main__":
    main()
