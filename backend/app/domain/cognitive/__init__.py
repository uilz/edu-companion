"""
CognitiveNode 模块 — 统一入口

外部代码应通过 get_repo() 获取 CognitiveNodeRepository 实例。

CognitiveOperationRegistry 导出用于外部模块调用认知操作。
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from shared.protocols.cognitive import CognitiveNodeRepository

from app.domain.cognitive.operation_registry import (
    CognitiveOperationRegistry,
    get_registry,
    init_registry,
)

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


def init_cognitive() -> None:
    """初始化 cognitive 模块 (应用启动时调用一次)"""
    ops_dir = str(Path(__file__).parent / "operations")
    init_registry(ops_dir)


__all__ = [
    "get_repo", "set_repo",
    "CognitiveOperationRegistry", "get_registry", "init_registry", "init_cognitive",
]
