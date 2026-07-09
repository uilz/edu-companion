"""Task #5 端到端测试：submit_practice 事件处理与投影更新"""

from __future__ import annotations

import time
import uuid

from app.domain.cognitive.events import CognitiveEventHandler, CognitiveEventRecord
from app.infrastructure.db import get_db_session
from app.infrastructure.db.models.cognitive import KnowledgeNodeORM


def _make_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


def main() -> None:
    user_id = "test_user_001"
    node_id = _make_id("atom")

    with get_db_session() as session:
        # 准备节点
        node = (
            session.query(KnowledgeNodeORM)
            .filter_by(user_id=user_id, id=node_id)
            .first()
        )
        if node is None:
            node = KnowledgeNodeORM(
                id=node_id,
                user_id=user_id,
                label="测试原子节点",
                level="atom",
                node_type="auto_generated",
                is_visible=False,
            )
            session.add(node)
            session.commit()

        handler = CognitiveEventHandler(session)

        # 发送多次练习事件
        for i in range(5):
            event = CognitiveEventRecord(
                id=_make_id("ev"),
                event_type="practice_response",
                user_id=user_id,
                source_type="test",
                source_id=_make_id("src"),
                payload={
                    "node_id": node_id,
                    "session_id": "test_session",
                    "question_id": _make_id("q"),
                    "timestamp": time.time(),
                    "success": i % 2 == 0,
                    "latency_ms": 2000.0,
                    "weight": 1.0,
                    "difficulty": 0.2,
                    "confidence_before": 0.7,
                    "time_spent": 8.0,
                },
            )
            result = handler.process_event(event)
            print(f"event {i}: {result}")

        # 检查投影
        from app.infrastructure.db.cognitive_projection_repository import (
            CognitiveProjectionRepository,
        )

        projection_repo = CognitiveProjectionRepository(session)
        projection = projection_repo.get(node_id)
        if projection is None:
            print("ERROR: projection not created")
            return

        print("\nProjection state:")
        print(f"  bkt_proficiency: {projection.bkt_proficiency}")
        print(f"  act_base_level: {projection.act_base_level}")
        print(f"  trend_direction: {projection.trend_direction}")
        print(f"  sched_urgency: {projection.sched_urgency}")
        print(f"  meta_direction: {projection.meta_direction}")
        print(f"  eng_xp: {projection.eng_xp}")
        print(f"  pred_error_flag: {projection.pred_error_flag}")


if __name__ == "__main__":
    main()
