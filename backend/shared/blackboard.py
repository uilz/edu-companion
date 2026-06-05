"""Redis 黑板 — 秘书系统与 Orchestrator 的异步共享上下文

键格式: bb:secretary:{session_id}
TTL: 300 秒
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any

logger = logging.getLogger(__name__)

# Redis 连接配置
_REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/0")


class Blackboard:
    """基于 Redis 的轻量黑板"""

    def __init__(self, redis_url: str = _REDIS_URL):
        self._redis_url = redis_url
        self._client = None

    async def _get_client(self):
        if self._client is None:
            import redis.asyncio as aioredis
            self._client = aioredis.from_url(
                self._redis_url,
                decode_responses=True,
            )
            # 连通性测试
            try:
                await self._client.ping()
            except Exception as e:
                logger.warning(f"Redis 连接失败: {e}，黑板功能降级")
                self._client = None
        return self._client

    async def set(self, key: str, value: dict, ttl: int = 300) -> bool:
        """写入黑板"""
        client = await self._get_client()
        if client is None:
            return False
        try:
            await client.setex(key, ttl, json.dumps(value, ensure_ascii=False))
            return True
        except Exception as e:
            logger.error(f"Blackboard.set({key}) failed: {e}")
            return False

    async def get(self, key: str) -> dict[str, Any] | None:
        """读取黑板"""
        client = await self._get_client()
        if client is None:
            return None
        try:
            raw = await client.get(key)
            if raw is None:
                return None
            return json.loads(raw)
        except Exception as e:
            logger.error(f"Blackboard.get({key}) failed: {e}")
            return None

    async def delete(self, key: str) -> bool:
        """删除黑板条目"""
        client = await self._get_client()
        if client is None:
            return False
        try:
            await client.delete(key)
            return True
        except Exception as e:
            logger.error(f"Blackboard.delete({key}) failed: {e}")
            return False

    async def exists(self, key: str) -> bool:
        """检查条目是否存在"""
        client = await self._get_client()
        if client is None:
            return False
        try:
            return bool(await client.exists(key))
        except Exception as e:
            logger.error(f"Blackboard.exists({key}) failed: {e}")
            return False


# 全局单例
blackboard = Blackboard()
