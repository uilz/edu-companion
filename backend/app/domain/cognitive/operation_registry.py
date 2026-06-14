"""
CognitiveOperationRegistry — 认知操作注册/派发中心

类 ToolRepository 模式:
- 注册: @register(name, description, params_schema)
- 派发: execute(name, **params) → result
- 发现: discover(["cognitive/operations/"]) — 应用启动时调用一次

每个操作是最小的 CognitiveNode 子系统修改单元.
"""

from __future__ import annotations

import importlib.util
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

logger = logging.getLogger(__name__)


@dataclass
class CognitiveOperation:
    """可注册的认知操作"""
    name: str
    description: str
    params_schema: dict = field(default_factory=dict)  # {"param": {"type": "string", "required": true, ...}}
    handler: Callable | None = None


class CognitiveOperationRegistry:
    """认知操作注册中心 — 单例"""

    def __init__(self):
        self._operations: dict[str, CognitiveOperation] = {}

    # ── 注册 ──

    def register(
        self,
        name: str,
        description: str = "",
        params_schema: dict | None = None,
    ):
        """装饰器注册操作"""
        def wrapper(fn):
            if name in self._operations:
                logger.warning("Operation %s already registered, overwriting", name)
            self._operations[name] = CognitiveOperation(
                name=name,
                description=description or fn.__doc__ or "",
                params_schema=params_schema or {},
                handler=fn,
            )
            logger.debug("Registered operation: %s", name)
            return fn
        return wrapper

    # ── 派发 ──

    def execute(self, name: str, **params) -> Any:
        """按名派发操作, 返回操作结果"""
        op = self._operations.get(name)
        if op is None or op.handler is None:
            raise ValueError(f"Unknown operation: {name}. Available: {list(self._operations.keys())}")
        logger.info("Executing operation: %s params=%s", name, params)
        return op.handler(**params)

    # ── 查询 ──

    def get(self, name: str) -> CognitiveOperation | None:
        return self._operations.get(name)

    def list_operations(self) -> list[dict]:
        """列出所有可用操作"""
        return [
            {
                "name": op.name,
                "description": op.description,
                "params_schema": op.params_schema,
            }
            for op in self._operations.values()
        ]

    # ── 自动发现 ──

    def discover(self, source_dirs: list[str]) -> int:
        """扫描目录, 发现并注册操作

        扫描 source_dirs 下所有 *_operations.py 文件,
        加载模块触发 @register 装饰器完成注册.
        """
        total = 0
        for src_dir in source_dirs:
            base = Path(src_dir)
            if not base.exists():
                logger.warning("Operation source directory not found: %s", src_dir)
                continue

            for py_file in sorted(base.glob("*_operations.py")):
                module_name = f"cognitive_ops.{py_file.stem}"

                spec = importlib.util.spec_from_file_location(
                    module_name, str(py_file),
                )
                if spec is None or spec.loader is None:
                    logger.warning("Cannot load spec for %s", py_file)
                    continue

                module = importlib.util.module_from_spec(spec)
                try:
                    spec.loader.exec_module(module)
                    logger.info("Discovered operations from: %s", py_file.name)
                    total += 1
                except Exception as e:
                    logger.error("Failed to load %s: %s", py_file.name, e)

        logger.info("OperationRegistry discover complete: %d files scanned, %d operations registered",
                     total, len(self._operations))
        return total


# ── 全局单例 ──

_registry: CognitiveOperationRegistry | None = None


def get_registry() -> CognitiveOperationRegistry:
    global _registry
    if _registry is None:
        _registry = CognitiveOperationRegistry()
    return _registry


def init_registry(operations_dir: str | None = None) -> CognitiveOperationRegistry:
    """初始化 + discover (应用启动时调用一次)"""
    reg = get_registry()
    if operations_dir:
        reg.discover([operations_dir])
    return reg
