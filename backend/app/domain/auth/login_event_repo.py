"""
登录事件仓储 — re-export from infrastructure

保持向后兼容：所有外部代码通过 get_login_event_repo() 获取实例。
"""
from __future__ import annotations

import logging
from typing import Optional

from app.infrastructure.db.auth_repository import LoginEventRepo as _LoginEventRepo

logger = logging.getLogger(__name__)


class LoginEventRepo(_LoginEventRepo):
    """登录事件数据仓储（继承 infrastructure 实现）"""
    pass


_login_event_repo: Optional[LoginEventRepo] = None


def get_login_event_repo() -> LoginEventRepo:
    """获取 LoginEventRepo 单例"""
    global _login_event_repo
    if _login_event_repo is None:
        _login_event_repo = LoginEventRepo()
    return _login_event_repo
