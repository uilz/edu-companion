"""
资料服务公共模块
共享的连接池管理和 Embedding 计算
"""
from __future__ import annotations

import logging
import os

from app.services.common.classifier import compute_embedding  # re-export

logger = logging.getLogger(__name__)

# 模块级连接池（全局共享）
_pool = None


async def get_pool():
    """获取或创建全局 asyncpg 连接池"""
    global _pool
    if _pool is None:
        import asyncpg
        db_url = os.getenv("DATABASE_URL", "")
        if db_url:
            _pool = await asyncpg.create_pool(db_url)
        else:
            raise RuntimeError("DATABASE_URL not set")
    return _pool


__all__ = ["get_pool", "compute_embedding"]
