"""
Common 服务模块 — 统一入口

外部代码应通过 get_data_repo() 获取 DataRepository 实例，
通过 get_admin_repo() 获取 AdminRepository 实例。
"""
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from shared.protocols.data_repository import DataRepository, AdminRepository

from app.services.common.storage import storage

_data_repo_instance: DataRepository | None = None
_admin_repo_instance: AdminRepository | None = None


def get_data_repo() -> DataRepository:
    """获取 DataRepository 单例（从 DI 容器初始化）"""
    global _data_repo_instance
    if _data_repo_instance is None:
        _data_repo_instance = storage
    return _data_repo_instance


def set_data_repo(repo: DataRepository) -> None:
    """设置 DataRepository 实例（由 DI 容器调用或测试覆写）"""
    global _data_repo_instance
    _data_repo_instance = repo


def get_admin_repo() -> AdminRepository:
    """获取 AdminRepository 单例（从 DI 容器初始化）"""
    global _admin_repo_instance
    if _admin_repo_instance is None:
        _admin_repo_instance = storage
    return _admin_repo_instance


def set_admin_repo(repo: AdminRepository) -> None:
    """设置 AdminRepository 实例（由 DI 容器调用或测试覆写）"""
    global _admin_repo_instance
    _admin_repo_instance = repo
