"""
资料索引系统 — 数据库迁移脚本 v1.1 (DEPRECATED)

⚠️ 此文件已废弃。canonical materials/material_chunks 表定义在 database.py (SCHEMA_SQL) 中。
database.py 的 _migrate() 在启动时自动执行，此脚本不再需要。

如需运行: python -m app.db.migrate_materials
现在仅为空操作（no-op），保留供旧引用兼容。
"""
from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


async def run_migration(database_url: str | None = None) -> None:
    """(DEPRECATED) 迁移已由 database.py 的 _migrate() 自动处理"""
    logger.info("⚠️  migrate_materials.py 已废弃 — 建表迁移由 database.py 自动处理")
    return


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    import asyncio
    asyncio.run(run_migration())
