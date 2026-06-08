"""
CognitiveNode 模块 — 统一入口

外部代码应通过 get_repo() 获取 CognitiveNodeRepository 实例，
不应直接 import app.cognitive.storage。

storage.py 是 PgCognitiveNodeRepository 的内部实现细节。
"""
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from shared.protocols.cognitive import CognitiveNodeRepository

_repo_instance: CognitiveNodeRepository | None = None


def get_repo() -> CognitiveNodeRepository:
    """获取 CognitiveNodeRepository 单例（从 DI 容器初始化）"""
    global _repo_instance
    if _repo_instance is None:
        from app.application.di import container
        _repo_instance = container.cognitive_node_repo
    return _repo_instance


def set_repo(repo: CognitiveNodeRepository) -> None:
    """设置 CognitiveNodeRepository 实例（由 DI 容器调用或测试覆写）"""
    global _repo_instance
    _repo_instance = repo
