"""
Phase 4: 共享状态管理

集中管理跨模块共享的运行时状态。
消除 api ⇄ services 循环依赖。

依赖规则: 零外部依赖（只依赖 Python 标准库）
"""

from __future__ import annotations

from typing import Any

# practice.py 维护的活跃会话池
# key: session_id, value: session dict
active_practice_sessions: dict[str, dict[str, Any]] = {}
