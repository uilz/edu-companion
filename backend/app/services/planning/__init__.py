"""Planning 模块初始化 + 建表确保"""
from __future__ import annotations

import logging
import os
from typing import Optional

logger = logging.getLogger(__name__)


def _ensure_tables() -> None:
    """确保 Planning 模块所有表存在（幂等）"""
    from app.infrastructure.db.database import get_db
    db = get_db()
    sql_path_options = [
        "app/infrastructure/db/planning_schema.sql",
        os.path.join(os.path.dirname(__file__), "../infrastructure/db/planning_schema.sql"),
        "/home/deploy/edu-companion/backend/app/infrastructure/db/planning_schema.sql",
    ]
    sql_path: Optional[str] = None
    for p in sql_path_options:
        if os.path.exists(p):
            sql_path = p
            break
    if not sql_path:
        logger.error("找不到 planning_schema.sql 建表文件")
        return
    with open(sql_path) as f:
        sql = f.read()
    for statement in sql.split(";"):
        s = statement.strip()
        if not s:
            continue
        try:
            db.execute(s)
        except Exception as e:
            logger.warning("建表异常: %s", e)
