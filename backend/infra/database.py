"""
数据库层 — 向后兼容重导出

仓储实现已迁移至 app.db.repositories，此文件仅保留兼容性重导出。
"""
from __future__ import annotations

# 重导出仓储类（di.py 等文件通过 from infra.database import ... 引用）
from app.db.repositories import (
    PostgresQuestionRepo,
    PostgresSessionRepo,
    PostgresErrorBookRepo,
)

__all__ = [
    "PostgresQuestionRepo",
    "PostgresSessionRepo",
    "PostgresErrorBookRepo",
]
