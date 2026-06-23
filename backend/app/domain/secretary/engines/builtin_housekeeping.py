"""内置模块: 临时会话清理 + 静默后台任务 — 运维类模块组

合并自: builtin_temp_conv_cleanup.py, silent_task.py
"""

from __future__ import annotations

import logging
import time

from ..models import Proposal
from .context_engine import SessionContext
from .module_registry import SecretaryModule, ModuleMeta

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════
# 1. 临时会话清理 (TempConversationCleanup)
# ═══════════════════════════════════════════

class TempConversationCleanupModule(SecretaryModule):
    """临时会话清理模块"""

    @property
    def meta(self) -> ModuleMeta:
        return ModuleMeta(
            name="temp_conv_cleanup",
            display_name="临时会话清理",
            emoji="🧹",
            description="定期清理 48h 过期的临时会话",
            default_enabled=True,
            run_interval_seconds=3600,
        )

    async def run_check(
        self, user_id: str, ctx: SessionContext | None = None,
    ) -> list[Proposal]:
        # TODO: 这些 infrastructure 导入应通过 DI 注入，而非在方法内懒加载
        from app.services.common import get_data_repo
        from app.infrastructure.db.cognitive_link_storage import get_links_for_conversation, remove_link

        cutoff = time.time() - 48 * 3600
        cleaned = 0

        try:
            from app.infrastructure.db.database import get_db
            db = get_db()
            rows = db.fetchall(
                "SELECT id FROM conversations WHERE is_temporary = true AND created_at < to_timestamp(%s)",
                (cutoff,),
            )
            for row in rows:
                cid = row["id"]
                try:
                    links = get_links_for_conversation(cid)
                    for link in links:
                        remove_link(link.id)
                except Exception:
                    pass
                db.execute("DELETE FROM conversations WHERE id = %s", (cid,))
                cleaned += 1
        except Exception as e:
            logger.debug("PG 临时会话清理: %s", e)

        # JSON 后端
        try:
            repo = get_data_repo()
            for uid in [user_id]:
                data = repo.load(uid)
                if not data:
                    continue
                conv_ids = [
                    cid for cid, conv in data.conversations.items()
                    if getattr(conv, "is_temporary", False) and
                    (getattr(conv, "created_at", 0) or 0) < cutoff
                ]
                for cid in conv_ids:
                    del data.conversations[cid]
                    cleaned += 1
                if conv_ids:
                    repo.save(uid, data)
        except Exception as e:
            logger.debug("JSON 临时会话清理: %s", e)

        if cleaned:
            logger.info("清理了 %d 个过期临时会话", cleaned)
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
