"""
共享工具函数 — 从各子模块抽取的纯函数，避免重复定义。
"""
from __future__ import annotations

import json
from typing import Any


def safe_json(val: Any, default: Any = None) -> Any:
    """将 JSON 字符串或原始 JSON 解析为 Python 对象"""
    if val is None:
        return default
    if isinstance(val, (list, dict)):
        return val
    if isinstance(val, str):
        try:
            return json.loads(val)
        except Exception:
            return default
    return default


def safe_iso(val: Any) -> str | None:
    """将 datetime 或时间值转为 ISO 字符串"""
    if val is None:
        return None
    if hasattr(val, "isoformat"):
        return val.isoformat()
    return str(val)


def safe_int(val: Any, default: int = 0) -> int:
    """将值转为 int"""
    if val is None:
        return default
    try:
        return int(val)
    except (ValueError, TypeError):
        return default