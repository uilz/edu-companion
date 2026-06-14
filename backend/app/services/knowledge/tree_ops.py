"""
树形对话操作服务 v5.0 — re-export from tree_service.py

保持向后兼容：所有外部代码通过 app.services.knowledge.tree_ops 导入。
"""
from __future__ import annotations

from app.services.knowledge.tree_service import TreeOpsService, tree_ops

__all__ = ["TreeOpsService", "tree_ops"]
