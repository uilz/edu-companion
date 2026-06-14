"""
用户仓储 — re-export from infrastructure

保持向后兼容：所有外部代码通过 get_user_repo() 获取实例。
"""
from __future__ import annotations

import logging
from typing import Optional

from app.infrastructure.db.auth_repository import UserRepo as _UserRepo

logger = logging.getLogger(__name__)


class UserRepo(_UserRepo):
    """用户数据仓储（继承 infrastructure 实现）"""
    pass


_user_repo: Optional[UserRepo] = None


def get_user_repo() -> UserRepo:
    """获取 UserRepo 单例"""
    global _user_repo
    if _user_repo is None:
        _user_repo = UserRepo()
    return _user_repo
