"""ConversationContextHook — 消费秘书注入的对话上下文

秘书系统通过 ConversationContextInjected 事件向对话壳推送学习状态、
待办计划与 pending proposals。本模块缓存该上下文，供 ReplyPipeline 的
ContextProvider 读取并渲染为 LLM system prompt。

缓存设计：
  - 以 (user_id, conv_id) 为键，保存最近一次注入 payload + 时间戳。
  - 默认 5 分钟 TTL，超过则视为过期，不再注入 LLM 上下文。
  - 不持久化：重启后丢失，依赖前一次 /secretary/context 调用或消息触发重新注入。
"""

from __future__ import annotations

import logging
import time
from typing import Any

from shared.events import ConversationContextInjected

logger = logging.getLogger(__name__)

# (user_id, conv_id) -> {"payload": dict, "ts": float}
_context_cache: dict[tuple[str, str], dict[str, Any]] = {}

DEFAULT_TTL_SECONDS = 300


def _cache_key(user_id: str, conv_id: str | None) -> tuple[str, str]:
    return (user_id, conv_id or "")


def store_injected_context(
    user_id: str,
    conv_id: str | None,
    payload: dict[str, Any],
) -> None:
    """存储秘书注入的上下文"""
    _context_cache[_cache_key(user_id, conv_id)] = {
        "payload": payload,
        "ts": time.time(),
    }


def get_injected_context(
    user_id: str,
    conv_id: str | None,
    max_age_seconds: float = DEFAULT_TTL_SECONDS,
) -> dict[str, Any] | None:
    """读取最近注入的上下文，过期返回 None"""
    entry = _context_cache.get(_cache_key(user_id, conv_id))
    if not entry:
        return None
    if time.time() - entry["ts"] > max_age_seconds:
        return None
    return entry["payload"]


def clear_injected_context(user_id: str, conv_id: str | None) -> None:
    """清理指定上下文（测试/重置用）"""
    _context_cache.pop(_cache_key(user_id, conv_id), None)


class ConversationContextHook:
    """订阅 ConversationContextInjected 并缓存 payload"""

    def __init__(self) -> None:
        self._bus: Any | None = None
        self._subscribed = False

    def subscribe(self, bus: Any) -> None:
        if self._subscribed:
            return
        self._bus = bus
        bus.subscribe("ConversationContextInjected", self._on_context_injected)
        self._subscribed = True
        logger.info("ConversationContextHook: subscribed to ConversationContextInjected")

    def unsubscribe(self) -> None:
        if not self._bus or not self._subscribed:
            return
        self._bus.unsubscribe("ConversationContextInjected", self._on_context_injected)
        self._subscribed = False
        logger.info("ConversationContextHook: unsubscribed")

    async def _on_context_injected(self, event: Any) -> None:
        if not isinstance(event, ConversationContextInjected):
            return
        try:
            store_injected_context(
                user_id=event.user_id,
                conv_id=event.conv_id,
                payload=event.payload or {},
            )
            logger.debug(
                "对话上下文已缓存: user=%s conv=%s",
                event.user_id,
                event.conv_id,
            )
        except Exception:
            logger.debug("缓存对话上下文失败", exc_info=True)


# 全局单例，由 di.py 订阅
conversation_context_hook = ConversationContextHook()
