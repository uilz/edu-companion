"""
契约测试: Resilience 机制

验证:
- with_timeout: 超时保护
- with_retry: 指数退避重试
- fallback: 降级返回默认值
- safe_async: 静默吞异常
"""

import asyncio

import pytest

from app.infrastructure.resilience import (
    with_timeout,
    with_retry,
    fallback,
    safe_async,
    ServiceTimeoutError,
    RetryExhaustedError,
)


# ═══════════════════════════════════════════
# with_timeout
# ═══════════════════════════════════════════

@pytest.mark.asyncio
async def test_with_timeout_passes_fast_call():
    @with_timeout(5.0)
    async def fast():
        return "ok"

    result = await fast()
    assert result == "ok"


@pytest.mark.asyncio
async def test_with_timeout_raises_on_slow_call():
    @with_timeout(0.05)
    async def slow():
        await asyncio.sleep(10.0)
        return "never"

    with pytest.raises(ServiceTimeoutError):
        await slow()


@pytest.mark.asyncio
async def test_with_timeout_preserves_function_name():
    @with_timeout(5.0)
    async def my_func():
        return "ok"

    assert my_func.__name__ == "my_func"


# ═══════════════════════════════════════════
# with_retry
# ═══════════════════════════════════════════

@pytest.mark.asyncio
async def test_with_retry_passes_on_first_attempt():
    call_count = 0

    @with_retry(max_attempts=3, base_delay=0.01)
    async def work():
        nonlocal call_count
        call_count += 1
        return "done"

    result = await work()
    assert result == "done"
    assert call_count == 1


@pytest.mark.asyncio
async def test_with_retry_retries_on_timeout():
    call_count = 0

    @with_retry(max_attempts=3, base_delay=0.01)
    async def flaky():
        nonlocal call_count
        call_count += 1
        if call_count < 3:
            raise ServiceTimeoutError("timeout")
        return "finally"

    result = await flaky()
    assert result == "finally"
    assert call_count == 3


@pytest.mark.asyncio
async def test_with_retry_exhausted():
    call_count = 0

    @with_retry(max_attempts=2, base_delay=0.01)
    async def always_fails():
        nonlocal call_count
        call_count += 1
        raise ServiceTimeoutError("always")

    with pytest.raises(RetryExhaustedError):
        await always_fails()
    assert call_count == 2


@pytest.mark.asyncio
async def test_with_retry_non_retryable_exception_passes_through():
    """非可重试异常直接传播，不重试"""
    call_count = 0

    @with_retry(max_attempts=3, base_delay=0.01)
    async def value_error():
        nonlocal call_count
        call_count += 1
        raise ValueError("not retryable")

    with pytest.raises(ValueError):
        await value_error()
    assert call_count == 1  # 不重试


@pytest.mark.asyncio
async def test_with_retry_exponential_backoff():
    """验证指数退避: 0.5, 1.0, 2.0"""
    delays = []

    @with_retry(max_attempts=4, base_delay=0.1)
    async def flaky():
        delays.append(asyncio.get_event_loop().time())
        raise ServiceTimeoutError("retry")

    with pytest.raises(RetryExhaustedError):
        await flaky()

    # 验证有 4 次调用，间隔递增
    assert len(delays) == 4
    intervals = [delays[i+1] - delays[i] for i in range(3)]
    # 指数递增: 0.1, 0.2, 0.4
    assert intervals[0] < intervals[1] < intervals[2]


# ═══════════════════════════════════════════
# fallback
# ═══════════════════════════════════════════

@pytest.mark.asyncio
async def test_fallback_returns_value_on_success():
    @fallback("default")
    async def work():
        return "real"

    assert await work() == "real"


@pytest.mark.asyncio
async def test_fallback_returns_default_on_failure():
    @fallback("safe_default")
    async def crash():
        raise RuntimeError("boom")

    result = await crash()
    assert result == "safe_default"


@pytest.mark.asyncio
async def test_fallback_preserves_none():
    """None 也是合法的 fallback 值"""
    @fallback(None)
    async def crash():
        raise RuntimeError("boom")

    result = await crash()
    assert result is None


# ═══════════════════════════════════════════
# safe_async
# ═══════════════════════════════════════════

@pytest.mark.asyncio
async def test_safe_async_returns_value_on_success():
    @safe_async("test")
    async def work():
        return 42

    assert await work() == 42


@pytest.mark.asyncio
async def test_safe_async_returns_none_on_failure():
    @safe_async("test")
    async def crash():
        raise RuntimeError("silent crash")

    result = await crash()
    assert result is None  # 吞异常


@pytest.mark.asyncio
async def test_safe_async_does_not_raise():
    """safe_async 绝不应向上抛出异常"""
    @safe_async("critical")
    async def always_crash():
        raise Exception("should be swallowed")

    # 不应 raise
    result = await always_crash()
    assert result is None
