"""
用户自定义 LLM 配置仓储 — re-export from infrastructure

保持向后兼容：所有外部代码通过 get_user_llm_config_repo() 获取实例。
"""
from __future__ import annotations

import logging
from typing import Optional

from app.infrastructure.db.auth_repository import UserLlmConfigRepo as _UserLlmConfigRepo

logger = logging.getLogger(__name__)


class UserLlmConfigRepo(_UserLlmConfigRepo):
    """用户 LLM 配置数据仓储（继承 infrastructure 实现）"""
    pass


_config_repo: Optional[UserLlmConfigRepo] = None


def get_user_llm_config_repo() -> UserLlmConfigRepo:
    """获取 UserLlmConfigRepo 单例"""
    global _config_repo
    if _config_repo is None:
        _config_repo = UserLlmConfigRepo()
    return _config_repo
