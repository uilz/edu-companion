"""秘书系统数据库 schema — 幂等建表

封装 backend/app/infrastructure/db/secretary_schema.sql 内的所有 DDL。
所有 SQL 用 IF NOT EXISTS 模式，重复调用安全。

调用方式：
    from app.infrastructure.db.secretary_schema import _ensure_tables
    _ensure_tables()
"""

from __future__ import annotations

import logging
import os
from pathlib import Path

logger = logging.getLogger(__name__)

_SCHEMA_FILE = Path(__file__).parent / "secretary_schema.sql"
_ENSURED = False


def _ensure_tables() -> None:
    """幂等执行 secretary_schema.sql 中所有 DDL"""
    global _ENSURED
    if _ENSURED:
        return
    try:
        from app.infrastructure.db.database import get_db
        db = get_db()
        sql = _SCHEMA_FILE.read_text(encoding="utf-8")
        # 拆分语句并逐条执行 (DDL 不能合并为一条)
        for stmt in sql.split(";"):
            s = stmt.strip()
            if not s or s.startswith("--"):
                continue
            try:
                db.execute(s)
            except Exception as e:
                # 兼容已有表 + ALTER 重复执行
                logger.debug("DDL 已存在或失败 (忽略): %s | %s", s[:60], e)
        _ENSURED = True
        logger.info("Secretary schema 已确保")
    except Exception as e:
        logger.warning("Secretary schema 初始化失败: %s", e)
