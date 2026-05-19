"""
契约测试: EventBus 集成测试

验证异步事件总线:
- 订阅/发布/取消订阅
- handler 异常隔离（不影响其他 handler）
- handler 超时保护
- 并发发布
- 零订阅者静默处理
"""

import asyncio

import pytest

from shared.events import (
    DomainEvent,
    AnswerSubmitted,
    SessionCompleted,
    KnowledgeStateUpdated,
    DailyGoalAchieved,
)
from infra.event_bus import EventBus


# ── 辅助 Handler ──

async def _noop(event: DomainEvent) -> None:
    pass


# ═══════════════════════════════════════════
# 订阅 / 取消订阅
# ═══════════════════════════════════════════

@pytest.mark.asyncio
async def test_subscribe_and_publish():
    received = []

    async def handler(event: DomainEvent):
        received.append(event)

    bus = EventBus()
    bus.subscribe("AnswerSubmitted", handler)

    event = AnswerSubmitted(user_id="u1", skill_id="calculus")
    await bus.publish(event)

    assert len(received) == 1
    assert received[0].user_id == "u1"


@pytest.mark.asyncio
async def test_unsubscribe():
    received = []

    async def handler(event: DomainEvent):
        received.append(event)

    bus = EventBus()
    bus.subscribe("AnswerSubmitted", handler)
    bus.unsubscribe("AnswerSubmitted", handler)

    await bus.publish(AnswerSubmitted())
    assert len(received) == 0


@pytest.mark.asyncio
async def test_publish_zero_handlers_is_silent():
    """没有订阅者时不报错"""
    bus = EventBus()
    await bus.publish(AnswerSubmitted())  # 不应抛出异常


# ═══════════════════════════════════════════
# Handler 异常隔离
# ═══════════════════════════════════════════

@pytest.mark.asyncio
async def test_handler_exception_does_not_affect_others():
    """一个 handler 异常不影响其他 handler"""
    received_a = []
    received_b = []

    async def handler_a(event: DomainEvent):
        received_a.append(event)

    async def handler_bad(event: DomainEvent):
        raise RuntimeError("handler crashed")

    bus = EventBus()
    bus.subscribe("AnswerSubmitted", handler_a)
    bus.subscribe("AnswerSubmitted", handler_bad)

    # 不应抛出异常
    await bus.publish(AnswerSubmitted(user_id="u1"))

    assert len(received_a) == 1  # handler_a 正常执行
    assert received_a[0].user_id == "u1"


@pytest.mark.asyncio
async def test_handler_exception_does_not_affect_publisher():
    """发布者不应感知 handler 异常"""
    bus = EventBus()

    async def bad_handler(event: DomainEvent):
        raise RuntimeError("crash")

    bus.subscribe("AnswerSubmitted", bad_handler)

    # 发布应正常返回
    await bus.publish(AnswerSubmitted())
    # 不应抛出异常


# ═══════════════════════════════════════════
# Handler 超时保护
# ═══════════════════════════════════════════

@pytest.mark.asyncio
async def test_handler_timeout():
    """超时的 handler 不应阻塞发布者"""
    bus = EventBus(handler_timeout=0.05)

    async def slow_handler(event: DomainEvent):
        await asyncio.sleep(10.0)  # 远超 timeout

    bus.subscribe("AnswerSubmitted", slow_handler)

    start = asyncio.get_event_loop().time()
    await bus.publish(AnswerSubmitted())
    elapsed = asyncio.get_event_loop().time() - start

    # 发布应在 timeout 内返回（加上一些调度开销）
    assert elapsed < 1.0, f"publish took {elapsed:.2f}s, expected < 1.0s"


# ═══════════════════════════════════════════
# 多种事件类型隔离
# ═══════════════════════════════════════════

@pytest.mark.asyncio
async def test_different_event_types_are_isolated():
    """不同事件类型各自路由"""
    received_answer = []
    received_session = []

    async def on_answer(event: DomainEvent):
        received_answer.append(event)

    async def on_session(event: DomainEvent):
        received_session.append(event)

    bus = EventBus()
    bus.subscribe("AnswerSubmitted", on_answer)
    bus.subscribe("SessionCompleted", on_session)

    await bus.publish(AnswerSubmitted(user_id="u1"))
    await bus.publish(SessionCompleted(session_id="s1"))

    assert len(received_answer) == 1
    assert len(received_session) == 1
    assert received_answer[0].user_id == "u1"
    assert received_session[0].session_id == "s1"


# ═══════════════════════════════════════════
# 并发发布
# ═══════════════════════════════════════════

@pytest.mark.asyncio
async def test_concurrent_publish():
    """多个事件并发发布，handler 各自收到正确的事件"""
    received = []

    async def handler(event: DomainEvent):
        await asyncio.sleep(0.01)
        received.append(event)

    bus = EventBus()
    bus.subscribe("AnswerSubmitted", handler)

    events = [
        AnswerSubmitted(user_id=f"u{i}", question_id=f"q{i}")
        for i in range(10)
    ]

    await asyncio.gather(*[bus.publish(e) for e in events])

    assert len(received) == 10
    user_ids = {e.user_id for e in received}
    assert len(user_ids) == 10  # 每个都不同


# ═══════════════════════════════════════════
# 统计
# ═══════════════════════════════════════════

@pytest.mark.asyncio
async def test_event_bus_tracks_published_count():
    bus = EventBus()
    bus.subscribe("AnswerSubmitted", _noop)

    for _ in range(5):
        await bus.publish(AnswerSubmitted())

    assert bus._published_count == 5


@pytest.mark.asyncio
async def test_event_bus_tracks_error_count():
    bus = EventBus()

    async def bad_handler(event: DomainEvent):
        raise RuntimeError("fail")

    bus.subscribe("AnswerSubmitted", bad_handler)

    for _ in range(3):
        await bus.publish(AnswerSubmitted())

    assert bus._error_count == 3
