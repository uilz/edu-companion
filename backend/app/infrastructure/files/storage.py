"""
文件系统 DB 工具函数 (原 infrastructure/media/material_common.py)
"""
from __future__ import annotations

import logging
import os

logger = logging.getLogger(__name__)

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


__all__ = ["get_pool"]