"""
Phase 4 测试 — 秘书编排器：对话上下文注入 + 计划项主动请求

验收范围:
  1. ConversationContextInjected 事件被对话壳缓存 (context_hooks)
  2. SecretaryContext Provider 将缓存渲染为 system prompt
  3. PlanItemRequested 事件被规划壳自动创建为 plan item（幂等）
  4. 需要用户确认的 PlanItemRequested 不自动创建
"""

from __future__ import annotations

import asyncio
import os
import sys
import uuid
from typing import Any
from unittest.mock import MagicMock

import pytest

BACKEND = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BACKEND not in sys.path:
    sys.path.insert(0, str(BACKEND))


# ═══════════════════════════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════════════════════════


@pytest.fixture
def user_id() -> str:
    return f"p4_{uuid.uuid4().hex[:12]}"


@pytest.fixture
def db():
    try:
        from app.infrastructure.db.database import get_db
        d = get_db()
        d.fetchone("SELECT 1")
        return d
    except Exception as exc:  # noqa: BLE001
        pytest.skip(f"数据库不可用: {exc}")


@pytest.fixture
def clean_bus(monkeypatch):
    """提供隔离 EventBus，并替换 container.event_bus，避免污染全局处理器。"""
    from app.infrastructure.event_bus import EventBus
    from app.application.di import container

    bus = EventBus(handler_timeout=2.0)
    monkeypatch.setattr(container, "event_bus", bus)
    return bus


@pytest.fixture
def cleanup_test_data(db, user_id):
    """测试结束后清理本测试产生的数据。"""
    yield
    for tbl in ("plan_items",):
        try:
            db.execute(f"DELETE FROM {tbl} WHERE user_id = %s", (user_id,))
        except Exception:
            pass


# ═══════════════════════════════════════════════════════════════════
# §1. Conversation Context Injection
# ═══════════════════════════════════════════════════════════════════


class TestConversationContextInjection:
    """秘书向对话壳注入上下文的端到端链路"""

    def test_context_hook_caches_injected_event(self, clean_bus):
        from app.domain.conversation.context_hooks import (
            ConversationContextHook,
            get_injected_context,
            clear_injected_context,
        )
        from shared.events import ConversationContextInjected

        user_id = "ctx_test_user"
        conv_id = "ctx_test_conv"
        clear_injected_context(user_id, conv_id)

        hook = ConversationContextHook()
        hook.subscribe(clean_bus)

        payload = {
            "active_goals": [{"title": "完成微积分复习"}],
            "due_plan_items": [{"title": "复习导数"}],
            "pending_proposals": [{"title": "练习积分"}],
            "recent_learning_summary": "状态良好",
        }
        event = ConversationContextInjected(
            user_id=user_id,
            source_module="secretary",
            conv_id=conv_id,
            injection_type="learning_state",
            payload=payload,
        )

        asyncio.run(clean_bus.publish(event))

        cached = get_injected_context(user_id, conv_id)
        assert cached is not None
        assert cached["active_goals"][0]["title"] == "完成微积分复习"
        assert cached["recent_learning_summary"] == "状态良好"

        hook.unsubscribe()
        clear_injected_context(user_id, conv_id)

    @pytest.mark.asyncio
    async def test_secretary_context_provider_renders_injected_context(self, clean_bus):
        from app.domain.conversation.context_hooks import (
            ConversationContextHook,
            store_injected_context,
            clear_injected_context,
        )
        from app.domain.conversation.context_pipeline import SecretaryContext, ContextInput

        user_id = "ctx_provider_user"
        conv_id = "ctx_provider_conv"
        clear_injected_context(user_id, conv_id)

        # 直接缓存上下文（不依赖事件总线）
        store_injected_context(
            user_id=user_id,
            conv_id=conv_id,
            payload={
                "active_goals": [{"title": "目标 A"}],
                "due_plan_items": [{"title": "待办 B"}],
                "pending_proposals": [{"title": "提案 C"}],
                "recent_learning_summary": "摘要 D",
                "suggested_topics": ["topic1"],
            },
        )

        provider = SecretaryContext()
        result = await provider.build(ContextInput(
            user_id=user_id,
            dir_id="dir_1",
            user_text="你好",
            conv_id=conv_id,
        ))

        assert result is not None
        text = result.text
        assert "目标 A" in text
        assert "待办 B" in text
        assert "提案 C" in text
        assert "摘要 D" in text
        assert "topic1" in text

        clear_injected_context(user_id, conv_id)

    def test_context_expires_after_ttl(self, clean_bus):
        from app.domain.conversation.context_hooks import (
            store_injected_context,
            get_injected_context,
            clear_injected_context,
        )

        user_id = "ctx_ttl_user"
        conv_id = "ctx_ttl_conv"
        clear_injected_context(user_id, conv_id)

        store_injected_context(user_id, conv_id, {"data": "old"})

        # 刚写入应可读
        assert get_injected_context(user_id, conv_id, max_age_seconds=300) is not None

        # 极短 TTL 下应过期
        assert get_injected_context(user_id, conv_id, max_age_seconds=0.0) is None

        clear_injected_context(user_id, conv_id)


# ═══════════════════════════════════════════════════════════════════
# §2. PlanItemRequested Handling
# ═══════════════════════════════════════════════════════════════════


class TestPlanItemRequestedHandling:
    """秘书发布 PlanItemRequested → 规划壳自动创建 plan item"""

    def test_plan_item_requested_creates_item_without_confirmation(
        self, db, user_id, clean_bus, cleanup_test_data
    ):
        from app.api.planning.event_handler import PlanningEventHandler
        from app.services.planning.items import find_plan_item_by_request_id
        from shared.events import PlanItemRequested

        handler = PlanningEventHandler()
        handler.subscribe(clean_bus)

        request_id = f"req_{uuid.uuid4().hex[:12]}"
        event = PlanItemRequested(
            user_id=user_id,
            source_module="secretary",
            request_id=request_id,
            target_type="flashcard",
            target_ref_id=f"fc_{uuid.uuid4().hex[:8]}",
            title="复习闪卡：测试",
            description="自动创建的计划项",
            priority=2,
            linked_node_ids=["node_1"],
            requires_user_confirmation=False,
            estimated_minutes=15,
        )

        asyncio.run(clean_bus.publish(event))

        # 验证 plan item 已创建
        item = find_plan_item_by_request_id(user_id, request_id)
        assert item is not None
        assert item["title"] == "复习闪卡：测试"
        assert item["target_type"] == "flashcard"
        assert item["metadata"].get("request_id") == request_id
        assert item["estimated_minutes"] == 15

        handler.unsubscribe()

    def test_plan_item_requested_is_idempotent(self, db, user_id, clean_bus, cleanup_test_data):
        from app.api.planning.event_handler import PlanningEventHandler
        from app.services.planning.items import find_plan_item_by_request_id
        from shared.events import PlanItemRequested

        handler = PlanningEventHandler()
        handler.subscribe(clean_bus)

        request_id = f"req_{uuid.uuid4().hex[:12]}"
        event = PlanItemRequested(
            user_id=user_id,
            source_module="secretary",
            request_id=request_id,
            target_type="practice",
            target_ref_id=f"q_{uuid.uuid4().hex[:8]}",
            title="练习题目",
            description="",
            priority=1,
            linked_node_ids=[],
            requires_user_confirmation=False,
        )

        asyncio.run(clean_bus.publish(event))
        first_id = find_plan_item_by_request_id(user_id, request_id)["id"]

        # 再次发布同一 request_id
        asyncio.run(clean_bus.publish(event))
        second_id = find_plan_item_by_request_id(user_id, request_id)["id"]

        assert first_id == second_id

        handler.unsubscribe()

    def test_plan_item_requested_with_confirmation_is_not_created(
        self, db, user_id, clean_bus, cleanup_test_data
    ):
        from app.api.planning.event_handler import PlanningEventHandler
        from app.services.planning.items import find_plan_item_by_request_id
        from shared.events import PlanItemRequested

        handler = PlanningEventHandler()
        handler.subscribe(clean_bus)

        request_id = f"req_{uuid.uuid4().hex[:12]}"
        event = PlanItemRequested(
            user_id=user_id,
            source_module="secretary",
            request_id=request_id,
            target_type="manual",
            target_ref_id="ref_1",
            title="需要确认的计划",
            description="",
            priority=2,
            linked_node_ids=[],
            requires_user_confirmation=True,
        )

        asyncio.run(clean_bus.publish(event))

        item = find_plan_item_by_request_id(user_id, request_id)
        assert item is None

        handler.unsubscribe()
