"""Task #7 测试：PgCognitiveNodeRepository 新架构适配器"""

from __future__ import annotations

import time
import uuid

from app.domain.cognitive.models import CognitiveNode
from app.infrastructure.db import get_db_session
from app.infrastructure.db.cognitive_repository import PgCognitiveNodeRepository
from app.infrastructure.db.models.cognitive import KnowledgeNodeORM


def _make_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


def _create_node(session, user_id: str, node_id: str, label: str, level: str = "atom"):
    node = session.query(KnowledgeNodeORM).filter_by(user_id=user_id, id=node_id).first()
    if node is None:
        node = KnowledgeNodeORM(
            id=node_id,
            user_id=user_id,
            label=label,
            level=level,
            node_type="test",
            is_visible=True,
        )
        session.add(node)
        session.commit()
    return node


def test_get_node_assembles_view() -> None:
    """get_node 应从 knowledge_nodes + projection 组装出 CognitiveNode。"""
    user_id = _make_id("user")
    node_id = _make_id("atom")

    with get_db_session() as session:
        _create_node(session, user_id, node_id, "适配器测试节点")

    repo = PgCognitiveNodeRepository()
    node = repo.get_node(node_id, user_id)

    assert node is not None
    assert node.id == node_id
    assert node.label == "适配器测试节点"
    assert node.level == "atom"
    assert node.belief is not None
    assert node.belief.proficiency_mean == 0.3  # 默认 BKT proficiency
    assert node.trend is not None
    assert node.scheduling is not None


def test_sync_from_practice_event_updates_projection() -> None:
    """sync_from_practice_event 应写入 practice_events 并更新 projection。"""
    user_id = _make_id("user")
    node_id = _make_id("atom")

    with get_db_session() as session:
        _create_node(session, user_id, node_id, "练习同步节点")

    repo = PgCognitiveNodeRepository()
    result = repo.sync_from_practice_event(
        user_id=user_id,
        skill_id=node_id,
        is_correct=True,
        response_time_ms=1200.0,
        question_id=_make_id("q"),
    )
    assert result["status"] == "ok", result

    node = repo.get_node(node_id, user_id)
    assert node is not None
    assert node.practice_summary.total_attempts == 1
    assert node.practice_summary.correct_attempts == 1
    assert node.belief.proficiency_mean > 0.3


def test_upsert_node_persists_entity_only() -> None:
    """upsert_node 只写实体字段，不影响 projection 默认值。"""
    user_id = _make_id("user")
    node_id = _make_id("atom")

    repo = PgCognitiveNodeRepository()
    node = CognitiveNode(
        id=node_id,
        label="手动创建节点",
        level="atom",
        path_id="test.path",
        node_type="explicit",
        is_visible=True,
        is_core=True,
        emoji="🧪",
        tags=["test"],
    )
    repo.upsert_node(node, user_id)

    fetched = repo.get_node(node_id, user_id)
    assert fetched is not None
    assert fetched.label == "手动创建节点"
    assert fetched.path_id == "test.path"
    assert fetched.is_core is True
    assert fetched.emoji == "🧪"
    assert fetched.tags == ["test"]


def test_list_all_nodes_and_urgent_nodes() -> None:
    """list_all_nodes 与 get_urgent_nodes 应返回视图。"""
    user_id = _make_id("user")
    node_id = _make_id("atom")

    with get_db_session() as session:
        _create_node(session, user_id, node_id, "队列节点")

    repo = PgCognitiveNodeRepository()
    # 先练习一次产生 scheduling 状态
    repo.sync_from_practice_event(
        user_id=user_id,
        skill_id=node_id,
        is_correct=False,
        response_time_ms=3000.0,
    )

    all_nodes = repo.list_all_nodes(user_id)
    assert any(n.id == node_id for n in all_nodes)

    urgent = repo.get_urgent_nodes(user_id, top_k=10)
    assert len(urgent) >= 1
    assert any(item["node_id"] == node_id for item in urgent)


def test_delete_node_soft_delete() -> None:
    """delete_node 应软删除节点。"""
    user_id = _make_id("user")
    node_id = _make_id("atom")

    with get_db_session() as session:
        _create_node(session, user_id, node_id, "待删除节点")

    repo = PgCognitiveNodeRepository()
    assert repo.get_node(node_id, user_id) is not None

    repo.delete_node(node_id, user_id)
    assert repo.get_node(node_id, user_id) is None
