"""
AdminError — 管理系统错误记录模型
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class AdminError:
    """管理系统错误记录"""
    id: str
    source: str  # e.g. "post_processor", "cognitive_sync", "knowledge_evidence"
    processor_name: str  # e.g. "CognitiveSyncHook"
    user_id: str
    error_type: str  # exception type name
    error_message: str
    traceback: str
    context: dict  # relevant context (conv_id, dir_id, etc.)
    occurred_at: float
    acknowledged: bool = False
