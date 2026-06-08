"""
对话数据存储引擎

仅支持 PostgreSQL 后端（废弃 JSON 文件存储）。

通过 DataRepository Port 对外暴露（见 shared/protocols/data_repository.py）。
"""

from __future__ import annotations

from app.services.common.pg_storage import PgStorageEngine

# 全局单例 — 始终使用 PG 存储引擎
storage: PgStorageEngine = PgStorageEngine()
