"""Task #P0-2: PlanningCompletionWriter 单元测试

验证:
1. PlanItemCompleted → 各 source_module 路由到对应 handler
2. 防循环: handler 不重发源事件 (ProjectNodeCompleted / FlashCardReviewed / SessionCompleted 等)
3. 幂等性: 同一 plan_item_id 重复事件只处理一次
4. PlanningSourceModule 枚举与 _ROUTE_HANDLERS 一一对应
5. 订阅生命周期: subscribe / unsubscribe 配对

运行方式:
    cd backend && python3 -m pytest tests/test_planning_completion_writer.py -v
"""
import asyncio
import sys
from pathlib import Path
from unittest.mock import MagicMock, AsyncMock, patch

BACKEND = Path(__file__).resolve().parent.parent
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

import pytest

from shared.events import (
    PlanItemCompleted,
    PlanningSourceModule,
)


class TestPlanningCompletionWriterRouting:
    """路由表覆盖性测试 — 所有 PlanningSourceModule 枚举值都有 handler"""

    def test_all_source_modules_have_handlers(self):
        """每个 PlanningSourceModule 枚举值在 _ROUTE_HANDLERS 中有对应 handler"""
        from app.services.planning.completion_writer import PlanningCompletionWriter
        for module in PlanningSourceModule:
            assert module.value in PlanningCompletionWriter._ROUTE_HANDLERS, (
                f"missing handler for {module.value}"
            )

    def test_routes_count_matches_enum(self):
        """_ROUTES 与 _ROUTE_HANDLERS key 数一致"""
        from app.services.planning.completion_writer import PlanningCompletionWriter
        assert len(PlanningCompletionWriter._ROUTES) == len(PlanningCompletionWriter._ROUTE_HANDLERS)

    def test_routes_keys_are_enum_values(self):
        """_ROUTE_HANDLERS 的 key 全部来自 PlanningSourceModule 枚举值"""
        from app.services.planning.completion_writer import PlanningCompletionWriter
        valid_values = {m.value for m in PlanningSourceModule}
        for k in PlanningCompletionWriter._ROUTE_HANDLERS.keys():
            assert k in valid_values, f"unexpected route key: {k}"


class TestPlanningCompletionWriterIdempotency:
    """幂等性测试 — 同一 plan_item_id 只处理一次"""

    @pytest.mark.asyncio
    async def test_duplicate_event_ignored(self):
        """重复事件被去重, 不再触发 handler"""
        from app.services.planning.completion_writer import PlanningCompletionWriter

        writer = PlanningCompletionWriter()
        # 用一个 stub handler 模拟路由
        called = []
        async def fake_handler(self, event):
            called.append(event.plan_item_id)
        writer._ROUTE_HANDLERS[PlanningSourceModule.MANUAL.value] = fake_handler

        event = PlanItemCompleted(
            plan_item_id="pi_001",
            user_id="u1",
            source_module=PlanningSourceModule.MANUAL.value,
            target_ref_id="x",
        )
        await writer._on_completed(event)
        await writer._on_completed(event)  # 重复
        await writer._on_completed(event)  # 重复

        assert called == ["pi_001"], f"handler 应只被调 1 次, 实际 {len(called)} 次"

    @pytest.mark.asyncio
    async def test_different_ids_each_processed(self):
        """不同 plan_item_id 各自处理"""
        from app.services.planning.completion_writer import PlanningCompletionWriter

        writer = PlanningCompletionWriter()
        called = []
        async def fake_handler(self, event):
            called.append(event.plan_item_id)
        writer._ROUTE_HANDLERS[PlanningSourceModule.MANUAL.value] = fake_handler

        for i in range(3):
            await writer._on_completed(PlanItemCompleted(
                plan_item_id=f"pi_{i}",
                user_id="u1",
                source_module=PlanningSourceModule.MANUAL.value,
                target_ref_id="x",
            ))

        assert called == ["pi_0", "pi_1", "pi_2"]


class TestPlanningCompletionWriterNoResend:
    """防循环测试 — handler 不应重发源事件"""

    @pytest.mark.asyncio
    async def test_project_handler_does_not_publish_project_node_completed(self):
        """_handle_project 不应 publish_event(ProjectNodeCompleted)"""
        from app.services.planning.completion_writer import PlanningCompletionWriter
        import inspect

        src = inspect.getsource(PlanningCompletionWriter._handle_project)
        # 不应有 publish_event 形式的 ProjectNodeCompleted 调用
        assert "publish_event(ProjectNodeCompleted" not in src, (
            "_handle_project 不应重发 ProjectNodeCompleted"
        )
        assert "bus.publish(ProjectNodeCompleted" not in src
        # 注释里允许提到 "不重发" 说明, 但不应有真正的发布调用

    @pytest.mark.asyncio
    async def test_flashcard_handler_does_not_publish_review(self):
        """_handle_flashcard 不应 publish_event(FlashCardReviewed)"""
        from app.services.planning.completion_writer import PlanningCompletionWriter
        import inspect

        src = inspect.getsource(PlanningCompletionWriter._handle_flashcard)
        assert "publish_event(FlashCardReviewed" not in src
        assert "bus.publish(FlashCardReviewed" not in src

    @pytest.mark.asyncio
    async def test_practice_handler_does_not_publish_session_completed(self):
        """_handle_practice 不应 publish_event(SessionCompleted)"""
        from app.services.planning.completion_writer import PlanningCompletionWriter
        import inspect

        src = inspect.getsource(PlanningCompletionWriter._handle_practice)
        assert "publish_event(SessionCompleted" not in src
        assert "bus.publish(SessionCompleted" not in src

    @pytest.mark.asyncio
    async def test_unknown_source_module_noop(self):
        """未注册的 source_module 不应抛错"""
        from app.services.planning.completion_writer import PlanningCompletionWriter

        writer = PlanningCompletionWriter()
        event = PlanItemCompleted(
            plan_item_id="pi_xyz",
            user_id="u1",
            source_module="non_existent_module",
            target_ref_id="x",
        )
        # 不应抛错
        await writer._on_completed(event)


class TestPlanningCompletionWriterSubscribe:
    """订阅生命周期"""

    def _make_fake_bus(self):
        """构造一个让 isinstance(bus, EventBus) 通过的 mock"""
        from app.infrastructure.event_bus import EventBus
        bus = MagicMock(spec=EventBus)
        return bus

    def test_subscribe_idempotent(self):
        """重复 subscribe 不会重复注册"""
        from app.services.planning.completion_writer import PlanningCompletionWriter

        bus = self._make_fake_bus()
        writer = PlanningCompletionWriter()
        writer.subscribe(bus)
        writer.subscribe(bus)  # 重复
        # 应只 subscribe 一次 (6 个事件名: PlanItemCompleted/Skipped/Extended/Started/Scheduled + MoodStressRuleTriggered)
        assert bus.subscribe.call_count == 6

    def test_unsubscribe_clears_state(self):
        """unsubscribe 后 _subscribed 标志被清除"""
        from app.services.planning.completion_writer import PlanningCompletionWriter

        bus = self._make_fake_bus()
        writer = PlanningCompletionWriter()
        writer.subscribe(bus)
        assert writer._subscribed is True
        writer.unsubscribe()
        assert writer._subscribed is False
        # unsubscribe 也应调用 6 次
        assert bus.unsubscribe.call_count == 6

    def test_non_bus_object_skipped(self):
        """传入非 EventBus 实例应跳过"""
        from app.services.planning.completion_writer import PlanningCompletionWriter

        writer = PlanningCompletionWriter()
        writer.subscribe("not a bus")  # type: ignore[arg-type]
        assert writer._subscribed is False
