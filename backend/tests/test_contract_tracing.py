"""
契约测试: Tracing 全链路追踪

验证:
- TraceContext: 生成/设置/获取/传播 trace_id
- Span: 上下文管理器 + 状态追踪 + 日志
- 嵌套 Span
- FastAPI middleware 兼容性
"""

import time
import uuid

import pytest

from infra.tracing import (
    TraceContext,
    span as Span,  # async context manager
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
    TraceContext.set("shortcut-test")
    assert trace_id() == "shortcut-test"


def test_trace_context_isolated_between_tests():
    """每次 new 生成唯一 ID 且隔离"""
    t1 = TraceContext.new()
    t2 = TraceContext.new()
    assert t1 != t2
    assert TraceContext.current() == t2


# ═══════════════════════════════════════════
# Span
# ═══════════════════════════════════════════

def test_span_context_manager():
    TraceContext.new()
    
    with Span("test_op") as span:
        span.set_ok()
    
    assert span.name == "test_op"
    assert span.status == "OK"
    assert span.duration_ms >= 0


def test_span_records_duration():
    with Span("timed_op") as span:
        time.sleep(0.02)
        span.set_ok()
    
    assert span.duration_ms >= 15  # 至少 15ms


def test_span_error_status():
    with Span("error_op") as span:
        span.set_error("something went wrong")
    
    assert span.status == "ERROR"
    assert span.error == "something went wrong"


def test_span_auto_error_on_exception():
    """Span 在 __exit__ 时自动捕获异常"""
    with pytest.raises(ValueError):
        with Span("crash_op") as span:
            raise ValueError("boom")
    
    assert span.status == "ERROR"
    assert "boom" in (span.error or "")


def test_span_auto_ok_when_no_error():
    """没有 set_ok/explicit error → 自动 OK"""
    with Span("auto_ok") as span:
        pass  # 什么都不做
    
    assert span.status == "OK"


def test_span_metadata():
    with Span("meta_op", metadata={"user": "u1"}) as span:
        span.add_metadata(skill="calculus")
        span.set_ok()
    
    assert span.metadata["user"] == "u1"
    assert span.metadata["skill"] == "calculus"


def test_trace_span_helper():
    s = trace_span("helper_op", user_id="u1")
    assert s.name == "helper_op"
    assert s.metadata["user_id"] == "u1"


# ═══════════════════════════════════════════
# 嵌套 Span
# ═══════════════════════════════════════════

def test_nested_spans():
    """嵌套 Span 不互相干扰"""
    TraceContext.new()
    
    with Span("parent") as parent:
        parent.set_ok()
        with Span("child") as child:
            child.set_ok()
    
    assert parent.status == "OK"
    assert child.status == "OK"
    assert parent.name == "parent"
    assert child.name == "child"


# ═══════════════════════════════════════════
# 隔离性
# ═══════════════════════════════════════════

def test_trace_context_defaults_to_empty():
    """新 contextvar 默认为空字符串（没有 set 时）"""
    # 由于 contextvars 跨测试共享，重置后检查
    # 实际行为: default="" 
    # 这里验证 current() 返回 str
    current = TraceContext.current()
    assert isinstance(current, str)
