"""共享常量与工具函数"""

from shared.constants import DEFAULT_USER_ID  # noqa: F401 — re-exported for app/ code

def get_user_id(user_id: str | None = None) -> str:
    """获取用户ID，None时回退默认"""
    return user_id or DEFAULT_USER_ID
