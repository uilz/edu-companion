"""
Phase 5 测试 — 规划壳主动生成计划项 + 秘书中转 + 用户确认

验收范围:
  1. PlanItemSuggested / PlanItemRequested 事件序列化/反序列化契约
  2. PlanningProactiveGenerator 基于 CognitiveNodeMetadataChanged / SessionCompleted 生成建议
  3. SecretaryEventHandler 将 PlanItemSuggested 转为 PlanItemRequested（带策略过滤）
  4. PlanningEventHandler 对 requires_user_confirmation=True 写入 plan_item_confirmations
  5. 接受 / 忽略 confirmation 的状态迁移与幂等
  6. 完整端到端链路：学习事件 → 建议 → 秘书中转 → 待确认计划项
"""

from __future__ import annotations

import asyncio
import os
import sys
import uuid
from typing import Any
from unittest.mock import patch

import pytest

BACKEND = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BACKEND not in sys.path:
    sys.path.insert(0, str(BACKEND))


# ═══════════════════════════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════════════════════════


@pytest.fixture
def user_id() -> str:
    return f"p5_{uuid.uuid4().hex[:12]}"


@pytest.fixture
def db():
    try:
        from app.infrastructure.db.database import get_db
        d = get_db()
        d.fetchone("SELECT 1")
        from app.services.planning import _ensure_tables
        _ensure_tables()
        return d
    except Exception as exc:  # noqa: BLE001
        pytest.skip(f"数据库不可用: {exc}")


@pytest.fixture
def clean_bus():
    """提供隔离 EventBus，避免污染全局处理器。"""
    from app.infrastructure.event_bus import EventBus

    return EventBus(handler_timeout=2.0)


@pytest.fixture
def cleanup_test_data(db, user_id):
    """测试结束后清理本测试产生的数据。"""
    yield
    for tbl in ("plan_items", "plan_item_confirmations"):
        try:
            db.execute(f"DELETE FROM {tbl} WHERE user_id = %s", (user_id,))
        except Exception:
            pass


# ═══════════════════════════════════════════════════════════════════
# §1. 事件契约测试
# ═══════════════════════════════════════════════════════════════════


class TestPlanItemEventContracts:
    """PlanItemSuggested / PlanItemRequested 序列化与 EVENT_TYPES 注册"""

    def test_plan_item_suggested_serialization_roundtrip(self):
        from shared.events import PlanItemSuggested, EVENT_TYPES

        event = PlanItemSuggested(
            user_id="u1",
            suggestion_id="sug_123",
            trigger_event_type="SessionCompleted",
            target_type="review",
            target_ref_id="node_1",
            title="复习节点",
            description="掌握度下降",
            priority=3,
            estimated_minutes=15,
            linked_node_ids=["node_1"],
            reason="low_mastery",
        )
        payload = event.to_dict() if hasattr(event, "to_dict") else event.__dict__
        cls = EVENT_TYPES.get(event.event_type)
        assert cls is PlanItemSuggested
        restored = cls(**payload)
        assert restored.suggestion_id == "sug_123"
        assert restored.target_type == "review"
        assert restored.priority == 3

    def test_plan_item_requested_has_metadata_field(self):
        from shared.events import PlanItemRequested

        event = PlanItemRequested(
            user_id="u1",
            request_id="req_abc",
            target_type="review",
            target_ref_id="node_1",
            title="复习节点",
            metadata={"suggestion_id": "sug_123", "requested_by": "secretary"},
        )
        assert event.metadata.get("suggestion_id") == "sug_123"

    def test_event_types_registration(self):
        from shared.events import EVENT_TYPES, PlanItemSuggested, PlanItemRequested

        assert "PlanItemSuggested" in EVENT_TYPES
        assert "PlanItemRequested" in EVENT_TYPES
        assert EVENT_TYPES["PlanItemSuggested"] is PlanItemSuggested
        assert EVENT_TYPES["PlanItemRequested"] is PlanItemRequested


# ═══════════════════════════════════════════════════════════════════
# §2. PlanningProactiveGenerator
# ═══════════════════════════════════════════════════════════════════


class TestPlanningProactiveGenerator:
    """规划壳主动生成 PlanItemSuggested"""

    def test_cognitive_metadata_changed_generates_suggestion(self, clean_bus):
        from app.api.planning.proactive_generator import PlanningProactiveGenerator
        from app.domain.cognitive.models import CognitiveNode
        from shared.events import CognitiveNodeMetadataChanged, PlanItemSuggested
        from unittest.mock import MagicMock

        captured: list[Any] = []
        clean_bus.subscribe("PlanItemSuggested", lambda ev: captured.append(ev))

        gen = PlanningProactiveGenerator()
        gen.subscribe(clean_bus)

        node = CognitiveNode(id="node_low", label="薄弱节点")
        node.belief.proficiency_mean = 0.3
        node.belief.alpha = 1.0
        node.belief.beta = 1.0
        mock_repo = MagicMock()
        mock_repo.get_node.return_value = node

        with patch("app.domain.cognitive.get_repo", return_value=mock_repo):
            event = CognitiveNodeMetadataChanged(
                user_id="u1",
                node_id="node_low",
                changed_fields=["belief", "scheduling"],
            )
            asyncio.run(clean_bus.publish(event))

        assert any(isinstance(e, PlanItemSuggested) for e in captured)
        gen.unsubscribe()

    def test_session_completed_low_accuracy_generates_practice_suggestion(self, clean_bus):
        from app.api.planning.proactive_generator import PlanningProactiveGenerator
        from shared.events import SessionCompleted, PlanItemSuggested

        captured: list[Any] = []
        clean_bus.subscribe("PlanItemSuggested", lambda ev: captured.append(ev))

        gen = PlanningProactiveGenerator()
        gen.subscribe(clean_bus)

        event = SessionCompleted(
            user_id="u1",
            session_id="sess_1",
            accuracy=0.3,
            duration_minutes=25,
        )
        asyncio.run(clean_bus.publish(event))

        suggestions = [e for e in captured if isinstance(e, PlanItemSuggested)]
        assert any(s.target_type == "practice" and s.reason == "low_accuracy_session" for s in suggestions)
        gen.unsubscribe()

    def test_session_completed_high_accuracy_generates_explore_suggestion(self, clean_bus):
        from app.api.planning.proactive_generator import PlanningProactiveGenerator
        from shared.events import SessionCompleted, PlanItemSuggested

        captured: list[Any] = []
        clean_bus.subscribe("PlanItemSuggested", lambda ev: captured.append(ev))

        gen = PlanningProactiveGenerator()
        gen.subscribe(clean_bus)

        event = SessionCompleted(
            user_id="u1",
            session_id="sess_2",
            accuracy=0.85,
            duration_minutes=30,
        )
        asyncio.run(clean_bus.publish(event))

        suggestions = [e for e in captured if isinstance(e, PlanItemSuggested)]
        assert any(s.target_type == "explore" and s.reason == "high_accuracy_expansion" for s in suggestions)
        gen.unsubscribe()


# ═══════════════════════════════════════════════════════════════════
# §3. SecretaryEventHandler 中转
# ═══════════════════════════════════════════════════════════════════


class TestSecretaryPlanItemSuggestedHandling:
    """秘书编排器订阅 PlanItemSuggested 并发布 PlanItemRequested"""

    def test_plan_item_suggested_converted_to_requested(self, clean_bus):
        from app.domain.secretary.engines.secretary_event_handler import SecretaryEventHandler
        from shared.events import PlanItemSuggested, PlanItemRequested

        handler = SecretaryEventHandler()
        handler.subscribe(clean_bus)

        requested: list[Any] = []
        clean_bus.subscribe("PlanItemRequested", lambda ev: requested.append(ev))

        with patch(
            "app.api.planning.service.find_confirmation_by_suggestion_id",
            return_value=None,
        ) as mock_find, patch(
            "app.api.planning.service.count_pending_confirmations",
            return_value=0,
        ):
            suggestion = PlanItemSuggested(
                user_id="u1",
                suggestion_id="sug_xyz",
                target_type="review",
                target_ref_id="node_1",
                title="复习节点",
                description="掌握度低",
                priority=2,
                estimated_minutes=10,
            )
            asyncio.run(clean_bus.publish(suggestion))

            mock_find.assert_called_once_with("u1", "sug_xyz")

        assert len(requested) == 1
        ev = requested[0]
        assert isinstance(ev, PlanItemRequested)
        assert ev.request_id == "req_sug_xyz"
        assert ev.metadata.get("suggestion_id") == "sug_xyz"
        assert ev.requires_user_confirmation is True
        handler.unsubscribe()

    def test_duplicate_suggestion_is_idempotent(self, clean_bus, db, user_id, cleanup_test_data):
        from app.domain.secretary.engines.secretary_event_handler import SecretaryEventHandler
        from app.api.planning import service as svc
        from shared.events import PlanItemSuggested, PlanItemRequested

        handler = SecretaryEventHandler()
        handler.subscribe(clean_bus)

        requested: list[Any] = []
        clean_bus.subscribe("PlanItemRequested", lambda ev: requested.append(ev))

        svc.create_confirmation(
            user_id=user_id,
            body={
                "request_id": f"req_sug_dup",
                "suggestion_id": "sug_dup",
                "source_module": "secretary",
                "target_type": "review",
                "target_ref_id": "node_1",
                "title": "复习节点",
                "description": "掌握度低",
            },
        )

        suggestion = PlanItemSuggested(
            user_id=user_id,
            suggestion_id="sug_dup",
            target_type="review",
            target_ref_id="node_1",
            title="复习节点",
            description="掌握度低",
        )
        asyncio.run(clean_bus.publish(suggestion))

        # 因 suggestion_id 已存在 confirmation，不应再发请求
        assert len([e for e in requested if getattr(e, "metadata", {}).get("suggestion_id") == "sug_dup"]) == 0
        handler.unsubscribe()

    def test_high_priority_suggestion_skipped_when_fatigued(self, clean_bus, db, user_id, cleanup_test_data):
        from app.domain.secretary.engines.secretary_event_handler import SecretaryEventHandler
        from shared.events import PlanItemSuggested, PlanItemRequested

        handler = SecretaryEventHandler()
        handler.subscribe(clean_bus)

        requested: list[Any] = []
        clean_bus.subscribe("PlanItemRequested", lambda ev: requested.append(ev))

        # 模拟高疲劳
        with patch(
            "app.domain.secretary.analysis.predict_fatigue_risk",
            return_value={"risk_level": "high"},
        ), patch(
            "app.api.planning.service.find_confirmation_by_suggestion_id",
            return_value=None,
        ), patch(
            "app.api.planning.service.count_pending_confirmations",
            return_value=0,
        ):
            suggestion = PlanItemSuggested(
                user_id=user_id,
                suggestion_id="sug_fatigue",
                target_type="review",
                target_ref_id="node_1",
                title="复习节点",
                description="掌握度低",
                priority=3,
            )
            asyncio.run(clean_bus.publish(suggestion))

        # priority >= 3 在高疲劳时应被跳过
        assert len(requested) == 0
        handler.unsubscribe()


# ═══════════════════════════════════════════════════════════════════
# §4. PlanningEventHandler 确认模式
# ═══════════════════════════════════════════════════════════════════


class TestPlanningEventHandlerConfirmationMode:
    """PlanItemRequested requires_user_confirmation=True 时写入 confirmation 表"""

    def test_requested_with_confirmation_creates_pending_record(
        self, db, user_id, clean_bus, cleanup_test_data
    ):
        from app.api.planning.event_handler import PlanningEventHandler
        from app.api.planning import service as svc
        from shared.events import PlanItemRequested

        handler = PlanningEventHandler()
        handler.subscribe(clean_bus)

        event = PlanItemRequested(
            user_id=user_id,
            request_id=f"req_confirm_{user_id}",
            target_type="review",
            target_ref_id="node_1",
            title="复习节点",
            description="掌握度低",
            requires_user_confirmation=True,
            metadata={"suggestion_id": "sug_abc"},
        )
        asyncio.run(clean_bus.publish(event))

        confirmation = svc.find_confirmation_by_request_id(user_id, event.request_id)
        assert confirmation is not None
        assert confirmation["status"] == "pending"
        assert confirmation["metadata"].get("suggestion_id") == "sug_abc"
        handler.unsubscribe()

    def test_requested_without_confirmation_creates_plan_item(
        self, db, user_id, clean_bus, cleanup_test_data
    ):
        from app.api.planning.event_handler import PlanningEventHandler
        from app.api.planning import service as svc
        from shared.events import PlanItemRequested

        handler = PlanningEventHandler()
        handler.subscribe(clean_bus)

        event = PlanItemRequested(
            user_id=user_id,
            request_id=f"req_auto_{user_id}",
            target_type="review",
            target_ref_id="node_1",
            title="自动创建节点",
            description="无需确认",
            requires_user_confirmation=False,
        )
        asyncio.run(clean_bus.publish(event))

        item = svc.find_plan_item_by_request_id(user_id, event.request_id)
        assert item is not None
        assert item["source_module"] == "secretary"
        handler.unsubscribe()


# ═══════════════════════════════════════════════════════════════════
# §5. Confirmation 接受 / 忽略
# ═══════════════════════════════════════════════════════════════════


class TestPlanItemConfirmationLifecycle:
    """确认请求的生命周期与幂等"""

    def test_accept_confirmation_creates_plan_item(self, db, user_id, cleanup_test_data):
        from app.api.planning import service as svc

        confirmation = svc.create_confirmation(
            user_id=user_id,
            body={
                "request_id": f"req_accept_{user_id}",
                "suggestion_id": "sug_accept",
                "source_module": "secretary",
                "target_type": "review",
                "target_ref_id": "node_1",
                "title": "复习节点",
                "description": "掌握度低",
            },
        )

        item = svc.accept_confirmation(user_id, confirmation["id"])
        assert item["title"] == "复习节点"
        assert item["metadata"].get("suggestion_id") == "sug_accept"

        confirmation2 = svc.get_confirmation(user_id, confirmation["id"])
        assert confirmation2["status"] == "accepted"

    def test_accept_confirmation_is_idempotent(self, db, user_id, cleanup_test_data):
        from app.api.planning import service as svc

        confirmation = svc.create_confirmation(
            user_id=user_id,
            body={
                "request_id": f"req_idem_{user_id}",
                "source_module": "secretary",
                "target_type": "review",
                "target_ref_id": "node_1",
                "title": "复习节点",
            },
        )

        item1 = svc.accept_confirmation(user_id, confirmation["id"])
        item2 = svc.accept_confirmation(user_id, confirmation["id"])
        assert item1["id"] == item2["id"]

    def test_dismiss_confirmation_updates_status(self, db, user_id, cleanup_test_data):
        from app.api.planning import service as svc

        confirmation = svc.create_confirmation(
            user_id=user_id,
            body={
                "request_id": f"req_dismiss_{user_id}",
                "source_module": "secretary",
                "target_type": "review",
                "target_ref_id": "node_1",
                "title": "复习节点",
            },
        )

        dismissed = svc.dismiss_confirmation(user_id, confirmation["id"])
        assert dismissed["status"] == "dismissed"


# ═══════════════════════════════════════════════════════════════════
# §6. 端到端链路
# ═══════════════════════════════════════════════════════════════════


class TestProactiveGenerationEndToEnd:
    """完整链路：SessionCompleted → PlanItemSuggested → PlanItemRequested → confirmation"""

    def test_session_completed_to_confirmation(
        self, db, user_id, clean_bus, cleanup_test_data
    ):
        from app.api.planning.proactive_generator import PlanningProactiveGenerator
        from app.domain.secretary.engines.secretary_event_handler import SecretaryEventHandler
        from app.api.planning.event_handler import PlanningEventHandler
        from app.api.planning import service as svc
        from shared.events import SessionCompleted

        proactive = PlanningProactiveGenerator()
        secretary = SecretaryEventHandler()
        planning = PlanningEventHandler()

        proactive.subscribe(clean_bus)
        secretary.subscribe(clean_bus)
        planning.subscribe(clean_bus)

        event = SessionCompleted(
            user_id=user_id,
            session_id="sess_e2e",
            accuracy=0.3,
            duration_minutes=25,
        )
        asyncio.run(clean_bus.publish(event))

        # 应生成 pending confirmation
        confirmations = svc.list_confirmations(user_id, status="pending")
        assert any(
            c["target_type"] == "practice" and c["user_id"] == user_id
            for c in confirmations
        ), f"未找到生成的 confirmation: {confirmations}"

        proactive.unsubscribe()
        secretary.unsubscribe()
        planning.unsubscribe()
