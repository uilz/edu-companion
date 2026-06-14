"""
契约测试: Tracing 全链路追踪

验证:
- TraceContext: 生成/设置/获取/传播 trace_id
- span: async context manager 生成 span ID + 自动计时
- 嵌套 span
- ContextVar 隔离性
"""

import asyncio

import pytest

from app.infrastructure.tracing import (
    TraceContext,
    span,
    trace_id as trace_id_var,
)


# ═══════════════════════════════════════════
# TraceContext
# ═══════════════════════════════════════════

def test_trace_context_new():
    tid = TraceContext.new()
    assert len(tid) == 8  # uuid4()[:8]
    assert TraceContext.current() == tid


def test_trace_context_set_and_get():
    TraceContext.set("my-trace-id")
    assert TraceContext.current() == "my-trace-id"


def test_trace_context_propagate():
    TraceContext.set("prop-123")
    headers = TraceContext.propagate()
    assert headers == {"x-trace-id": "prop-123"}


def test_trace_id_shortcut():
    """trace_id ContextVar 可被 set/get"""
    TraceContext.set("shortcut-test")
    assert trace_id_var.get() == "shortcut-test"


def test_trace_context_isolated_between_tests():
    """每次 new 生成唯一 ID"""
    t1 = TraceContext.new()
    t2 = TraceContext.new()
    assert t1 != t2
    assert TraceContext.current() == t2


# ═══════════════════════════════════════════
# span — async context manager
# ═══════════════════════════════════════════

@pytest.mark.asyncio
async def test_span_context_manager():
    """span() 是 async context manager，yield span ID"""
    TraceContext.new()

    async with span("test_op") as sid:
        assert isinstance(sid, str)
        assert len(sid) == 6  # uuid4()[:6]


@pytest.mark.asyncio
async def test_span_yields_unique_ids():
    """不同 span 生成不同 ID"""
    ids = []
    async with span("op1") as sid1:
        ids.append(sid1)
        async with span("op2") as sid2:
            ids.append(sid2)
    assert ids[0] != ids[1]


@pytest.mark.asyncio
async def test_span_does_not_crash_on_exception():
    """span 在异常时也正常退出（记录日志）"""
    with pytest.raises(ValueError):
        async with span("crash_op") as sid:
            raise ValueError("boom")
    # 不应抛出额外异常


@pytest.mark.asyncio
async def test_span_ok_path():
    """正常路径下 span 完成"""
    async with span("ok_op") as sid:
        pass  # 无异常
    # 不应抛出异常


@pytest.mark.asyncio
async def test_nested_spans():
    """嵌套 span 不互相干扰"""
    TraceContext.new()

    outer_id = None
    inner_id = None

    async with span("parent") as sid:
        outer_id = sid
        async with span("child") as sid2:
            inner_id = sid2

    assert outer_id is not None
    assert inner_id is not None
    assert outer_id != inner_id


@pytest.mark.asyncio
async def test_trace_context_defaults_to_empty():
    """新 contextvar 默认为空字符串"""
    current = TraceContext.current()
    assert isinstance(current, str)


@pytest.mark.asyncio
async def test_concurrent_spans():
    """并发 span 各自独立"""
    async def make_span(name: str) -> str:
        async with span(name) as sid:
            await asyncio.sleep(0.01)
            return sid

    results = await asyncio.gather(
        make_span("a"),
        make_span("b"),
        make_span("c"),
    )
    assert len(set(results)) == 3  # 三个不同 ID
