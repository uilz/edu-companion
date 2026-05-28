"""共享常量与工具函数"""

# 默认用户 ID — 单用户模式下使用的全局常量
DEFAULT_USER_ID = "default_user"


def get_user_id(user_id: str | None = None) -> str:
    """获取用户ID，None时回退默认"""
    return user_id or DEFAULT_USER_ID
