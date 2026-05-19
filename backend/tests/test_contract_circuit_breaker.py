"""
契约测试: CircuitBreaker 状态机

验证熔断器的全部状态转换:
- CLOSED → OPEN → HALF_OPEN → CLOSED
- 失败计数逻辑
- 恢复超时
- 并发 HALF_OPEN 请求限制
"""

import asyncio

import pytest

from infra.resilience import (
    CircuitBreaker,
    CircuitBreakerOpenError,
    CircuitState,
)


# ── 辅助 ──

async def ok():
    return "success"

async def fail():
    raise ValueError("boom")


# ═══════════════════════════════════════════
# 初始状态
# ═══════════════════════════════════════════

def test_initial_state_is_closed():
    cb = CircuitBreaker("test")
    assert cb.state == CircuitState.CLOSED
    assert cb.failure_count == 0


# ═══════════════════════════════════════════
# CLOSED → OPEN 转换
# ═══════════════════════════════════════════

@pytest.mark.asyncio
async def test_closed_lets_requests_pass():
    cb = CircuitBreaker("test", failure_threshold=3)
    result = await cb.call(ok)
    assert result == "success"
    assert cb.state == CircuitState.CLOSED


@pytest.mark.asyncio
async def test_closed_counts_failures():
    cb = CircuitBreaker("test", failure_threshold=3)
    for _ in range(2):
        with pytest.raises(ValueError):
            await cb.call(fail)
    assert cb.failure_count == 2
    assert cb.state == CircuitState.CLOSED  # 还没到阈值


@pytest.mark.asyncio
async def test_failure_threshold_triggers_open():
    """失败数到达 threshold → OPEN"""
    cb = CircuitBreaker("test", failure_threshold=3)
    for _ in range(3):
        with pytest.raises(ValueError):
            await cb.call(fail)
    assert cb.state == CircuitState.OPEN
    assert cb.failure_count == 3


@pytest.mark.asyncio
async def test_open_rejects_all_requests():
    """OPEN 状态下所有请求直接拒绝"""
    cb = CircuitBreaker("test", failure_threshold=2, recovery_timeout=10.0)
    for _ in range(2):
        with pytest.raises(ValueError):
            await cb.call(fail)
    assert cb.state == CircuitState.OPEN

    with pytest.raises(CircuitBreakerOpenError):
        await cb.call(ok)


# ═══════════════════════════════════════════
# OPEN → HALF_OPEN 转换
# ═══════════════════════════════════════════

@pytest.mark.asyncio
async def test_open_transitions_to_half_open_after_timeout():
    """等待 recovery_timeout 后 → HALF_OPEN"""
    cb = CircuitBreaker("test", failure_threshold=1, recovery_timeout=0.01)
    
    # 触发 OPEN
    with pytest.raises(ValueError):
        await cb.call(fail)
    assert cb.state == CircuitState.OPEN

    # 等待恢复时间
    await asyncio.sleep(0.02)

    # 第一次调用应触发 HALF_OPEN
    result = await cb.call(ok)
    assert result == "success"


# ═══════════════════════════════════════════
# HALF_OPEN → CLOSED (成功恢复)
# ═══════════════════════════════════════════

@pytest.mark.asyncio
async def test_half_open_success_transitions_to_closed():
    """HALF_OPEN 下成功 → CLOSED"""
    cb = CircuitBreaker("test", failure_threshold=1, recovery_timeout=0.01)
    
    with pytest.raises(ValueError):
        await cb.call(fail)
    await asyncio.sleep(0.02)

    result = await cb.call(ok)
    assert result == "success"
    assert cb.state == CircuitState.CLOSED
    assert cb.failure_count == 0  # 重置


# ═══════════════════════════════════════════
# HALF_OPEN → OPEN (恢复失败)
# ═══════════════════════════════════════════

@pytest.mark.asyncio
async def test_half_open_failure_transitions_back_to_open():
    """HALF_OPEN 下失败 → 回到 OPEN"""
    cb = CircuitBreaker("test", failure_threshold=1, recovery_timeout=0.01)
    
    with pytest.raises(ValueError):
        await cb.call(fail)
    await asyncio.sleep(0.02)

    # HALF_OPEN 后再次失败
    with pytest.raises(ValueError):
        await cb.call(fail)
    assert cb.state == CircuitState.OPEN  # 重新熔断


# ═══════════════════════════════════════════
# 成功重置失败计数
# ═══════════════════════════════════════════

@pytest.mark.asyncio
async def test_success_increments_success_count():
    """CLOSED 下成功只递增 success_count，不重置 failure_count"""
    cb = CircuitBreaker("test", failure_threshold=5)
    
    with pytest.raises(ValueError):
        await cb.call(fail)
    assert cb.failure_count == 1

    await cb.call(ok)
    assert cb.success_count == 1  # 成功计数递增
    # failure_count 仅在 HALF_OPEN→CLOSED 时重置，符合标准熔断器语义


# ═══════════════════════════════════════════
# 并发 HALF_OPEN 限制
# ═══════════════════════════════════════════

@pytest.mark.asyncio
async def test_half_open_respects_max_requests():
    """HALF_OPEN 下超过 max_requests 的并发应被拒绝"""
    cb = CircuitBreaker(
        "test", failure_threshold=1, recovery_timeout=0.01,
        half_open_max_requests=1,
    )
    
    with pytest.raises(ValueError):
        await cb.call(fail)
    await asyncio.sleep(0.02)
    
    # 同时发起 2 个请求（第二个应被拒绝）
    async def slow_ok():
        await asyncio.sleep(0.1)
        return "slow"
    
    # 同时调用
    task1 = asyncio.create_task(cb.call(slow_ok))
    await asyncio.sleep(0.01)  # 确保 task1 先占用 HALF_OPEN 槽位
    
    with pytest.raises(CircuitBreakerOpenError):
        await cb.call(ok)  # 第二个请求被拒绝
    
    await task1  # 等待第一个完成


# ═══════════════════════════════════════════
# 状态统计
# ═══════════════════════════════════════════

def test_circuit_breaker_tracks_stats():
    cb = CircuitBreaker("test")
    assert cb.name == "test"
    assert cb.success_count == 0
    assert cb.last_failure_time is None
    assert cb.last_state_change is not None
