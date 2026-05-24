"""主动检查器 — 基于模块注册表的扩展式检查

检查流程:
  1. 从 module_registry 获取所有已启用模块
  2. 每个模块独立执行 run_check()
  3. 收集所有提案并通过黑板推送 + WS 通知
  4. 模块可独立启用/禁用/扩展
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any

from .context_engine import ContextEngine, SessionContext

logger = logging.getLogger(__name__)


class ActiveChecker:
    """主动检查器 — 基于模块注册表的周期性检查"""

    def __init__(self, user_id: str = "default_user") -> None:
        self._user_id = user_id
        self._running = False
        self._task: asyncio.Task | None = None
        self._check_interval = 600  # 10分钟
        self._context_engine = ContextEngine()
        self._last_proposal_count = 0

    async def run_check(self) -> dict[str, Any]:
        """执行一次模块化主动检查"""
        from .module_registry import module_registry
        from ..proposal_store import ProposalStore

        findings: dict[str, Any] = {
            "modules_run": 0,
            "proposals_generated": 0,
            "reasons": [],
        }

        # 1. 评估用户情境
        ctx = await self._context_engine.assess(self._user_id)

        # 2. 运行所有已启用模块
        proposals = await module_registry.run_enabled_checks(self._user_id, ctx)
        findings["modules_run"] = len(module_registry._enabled)
        findings["proposals_generated"] = len(proposals)

        if not proposals:
            return findings

        # 3. 构造理由
        for p in proposals:
            findings["reasons"].append(f"{p.emoji} {p.title}")

        # 4. 去重 — 只推送新提案
        has_new = len(proposals) != self._last_proposal_count
        self._last_proposal_count = len(proposals)

        if not has_new:
            return findings

        # 5. 持久化 + 推送黑板 + WS 通知
        store = ProposalStore()

        # 持久化
        for p in proposals:
            try:
                store.save_proposal(p, user_id=self._user_id, session_id="_active_check")
            except Exception:
                pass

        # 推送到黑板
        try:
            from ..secretary_service import SecretaryService
            service = SecretaryService()
            await service.push_to_blackboard("_active_check", proposals)
        except Exception as e:
            logger.debug("黑板推送失败: %s", e)

        # WS 通知
        try:
            from app.api.chat import manager as ws_manager
            if ws_manager and hasattr(ws_manager, 'broadcast'):
                await ws_manager.broadcast({
                    "type": "secretary_update",
                    "content": {
                        "reason": findings["reasons"],
                        "proposal_count": len(proposals),
                    }
                })
        except Exception:
            pass

        logger.info("📋 秘书主动检查: %d 个模块执行，生成 %d 条提案", findings["modules_run"], findings["proposals_generated"])
        return findings

    async def _loop(self) -> None:
        """后台循环"""
        logger.info("🔍 秘书主动检查器启动 (间隔 %ds, 模块数 %d)", self._check_interval, self._count_modules())
        while self._running:
            try:
                findings = await self.run_check()
                if findings["proposals_generated"] > 0:
                    logger.info("📋 生成 %d 条提案: %s", findings["proposals_generated"], "; ".join(findings["reasons"][:3]))
                else:
                    logger.debug("主动检查: 无新事项")
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.warning("主动检查异常: %s", e)
            await asyncio.sleep(self._check_interval)

    def _count_modules(self) -> int:
        try:
            from .module_registry import module_registry
            return len(module_registry._modules)
        except Exception:
            return 0

    def start(self) -> None:
        """启动后台检查循环"""
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._loop())

    async def stop(self) -> None:
        """停止后台检查循环"""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None


# ── 全局实例 ──
active_checker = ActiveChecker()
