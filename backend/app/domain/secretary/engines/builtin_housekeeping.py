"""内置模块: 临时会话清理 + 静默后台任务 — 运维类模块组

合并自: builtin_temp_conv_cleanup.py, silent_task.py
"""

from __future__ import annotations

import logging

from ..models import Proposal
from .context_engine import SessionContext
from .module_registry import SecretaryModule, ModuleMeta

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════
# 1. 临时会话清理 (TempConversationCleanup)
# ═══════════════════════════════════════════

class TempConversationCleanupModule(SecretaryModule):
    """临时会话清理模块（已废弃 — 临时会话机制已移除）"""

    @property
    def meta(self) -> ModuleMeta:
        return ModuleMeta(
            name="temp_conv_cleanup",
            display_name="临时会话清理",
            emoji="🧹",
            description="已废弃",
            default_enabled=False,
            run_interval_seconds=86400,
        )

    async def run_check(
        self, user_id: str, ctx: SessionContext | None = None,
    ) -> list[Proposal]:
        return []


# ═══════════════════════════════════════════
# 2. 静默后台任务 (SilentTask)
# ═══════════════════════════════════════════

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
            run_interval_seconds=300,
        )

    async def on_activate(self) -> None:
        self._activated_at = time.time()
        self._check_count = 0
        self._last_bookkeeping = self._activated_at
        logger.info("静默后台任务已激活，时间戳: %.3f", self._activated_at)

    async def on_deactivate(self) -> None:
        elapsed = time.time() - self._activated_at
        logger.info("静默后台任务停用 — 累计运行 %.1f 秒，执行 %d 次检查", elapsed, self._check_count)

    async def run_check(
        self, user_id: str, ctx: SessionContext | None = None,
    ) -> list[Proposal]:
        now = time.time()
        self._check_count += 1
        if self._check_count % 10 == 0:
            elapsed_since_activation = now - self._activated_at
            logger.debug("静默任务记账 [user=%s]: 已激活 %.1f 秒, 检查 %d 次",
                         user_id, elapsed_since_activation, self._check_count)
            self._last_bookkeeping = now
        return []
