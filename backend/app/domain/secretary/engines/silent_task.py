"""内置模块: 静默后台任务 (SilentTask)

功能: 内部记账/数据整理的后台任务，不产生任何提案
行为:
  - run_check() 始终返回空列表
  - on_activate() 中初始化内部计数器并记录启动
  - run_check() 中做轻量内部记账（运行时统计），但不产生用户可见输出
  - 适合用来维护模块注册表的统计数据、预热缓存等

设计原则:
  - 对用户完全透明，不产生任何通知或提案
  - 只在日志和注册表统计中留下痕迹
"""

from __future__ import annotations

import logging
import time

from ..models import Proposal
from .context_engine import SessionContext
from .module_registry import SecretaryModule, ModuleMeta

logger = logging.getLogger(__name__)


class SilentTaskModule(SecretaryModule):
    """静默后台任务模块 — 内部记账，不产生提案"""

    def __init__(self) -> None:
        super().__init__()
        self._activated_at: float = 0.0
        self._check_count: int = 0
        self._last_bookkeeping: float = 0.0

    @property
    def meta(self) -> ModuleMeta:
        return ModuleMeta(
            name="silent_task",
            display_name="后台任务",
            emoji="⚙️",
            description="内部记账与数据整理的后台任务，用户不可见",
            default_enabled=True,
            run_interval_seconds=300,  # 每 5 分钟运行一次
        )

    async def on_activate(self) -> None:
        """模块激活时初始化内部状态"""
        self._activated_at = time.time()
        self._check_count = 0
        self._last_bookkeeping = self._activated_at
        logger.info(
            "静默后台任务已激活，时间戳: %.3f",
            self._activated_at,
        )

    async def on_deactivate(self) -> None:
        """模块停用时记录统计摘要"""
        elapsed = time.time() - self._activated_at
        logger.info(
            "静默后台任务停用 — 累计运行 %.1f 秒，执行 %d 次检查",
            elapsed,
            self._check_count,
        )

    async def run_check(
        self, user_id: str, ctx: SessionContext | None = None,
    ) -> list[Proposal]:
        """执行内部记账，不产生任何用户可见提案"""
        now = time.time()
        self._check_count += 1

        # 内部记账：每隔 10 次检查记录一次日志
        if self._check_count % 10 == 0:
            elapsed_since_activation = now - self._activated_at
            logger.debug(
                "静默任务记账 [user=%s]: 已激活 %.1f 秒, 检查 %d 次",
                user_id,
                elapsed_since_activation,
                self._check_count,
            )
            self._last_bookkeeping = now

        # 绝对不产生任何提案
        return []
