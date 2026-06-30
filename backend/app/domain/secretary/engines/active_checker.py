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
from .context_engine import ContextEngine

logger = logging.getLogger(__name__)


class ActiveChecker:
    """主动检查器 — 基于模块注册表的周期性检查"""

    def __init__(self, user_id: str = "", proposal_store=None) -> None:
        self._user_id = user_id
        self._running = False
        self._task: asyncio.Task | None = None
        self._check_interval = 600  # 10分钟
        self._context_engine = ContextEngine()
        self._last_proposal_count = 0
        self._store = proposal_store

    async def run_check(self, user_id: str = "") -> dict[str, Any]:
        """执行一次模块化主动检查"""
        from .module_registry import module_registry

        uid = user_id or self._user_id
        if not uid:
            return {"error": "user_id required", "modules_run": 0, "proposals_generated": 0, "reasons": []}

        findings: dict[str, Any] = {
            "modules_run": 0,
            "proposals_generated": 0,
            "reasons": [],
        }

        # 1. 评估用户情境
        ctx = await self._context_engine.assess(uid)

        # 2. 运行所有已启用模块
        proposals = await module_registry.run_enabled_checks(uid, ctx)

        # 2.5 策略引擎过滤
        from .policy_engine import policy_engine
        daily_used = await policy_engine.get_daily_usage(uid)
        proposals = await policy_engine.filter(
            proposals,
            user_id=uid,
            quiet_hours=ctx.quiet_hours if ctx else False,
            daily_used=daily_used,
            max_daily=5,
            session_id="_active_check",
        )
        findings["filtered_count"] = len(proposals)
        findings["modules_run"] = len(module_registry._enabled)
        findings["proposals_generated"] = len(proposals)

        if not proposals:
            return findings

        # 3. 构造理由
        for p in proposals:
            findings["reasons"].append(f"{p.emoji} {p.title}")

        # 4. 持久化（save_proposal 内部已处理指纹去重）
        from hashlib import md5
        for p in proposals:
            fingerprint = md5(
                f"{p.title}|{p.insight_source}|{p.action_type}".encode()
            ).hexdigest()
            p.payload = {**(p.payload or {}), "_fingerprint": fingerprint}

        findings["proposals_generated"] = len(proposals)

        # 5. 持久化 + 推送黑板
        if self._store:
            for p in proposals:
                try:
                    self._store.save_proposal(p, user_id=uid, session_id="_active_check")
                except Exception as e:
                    logger.warning("Proposal save failed for active check: %s", e)

        # 推送到黑板
        try:
            from ..secretary_service import SecretaryService
            service = SecretaryService()
            await service.push_to_blackboard("_active_check", proposals)
        except Exception as e:
            logger.debug("黑板推送失败: %s", e)

        logger.info("📋 秘书主动检查: %d 个模块执行，生成 %d 条提案", findings["modules_run"], findings["proposals_generated"])
        return findings

    async def _loop(self) -> None:
        """后台循环"""
        logger.info("🔍 秘书主动检查器启动 (间隔 %ds)", self._check_interval)
        while self._running:
            try:
                findings = await self.run_check()
                if findings["proposals_generated"] > 0:
                    logger.info("📋 生成 %d 条提案: %s", findings["proposals_generated"], "; ".join(findings["reasons"][:3]))
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.warning("主动检查异常: %s", e)
            await asyncio.sleep(self._check_interval)

    def start(self) -> None:
        """启动后台检查循环（保留兼容，推荐由中央调度器管理）

        主动检查最终应由客户端驱动（requestIdleCallback 定时调用 API）。
        """
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
active_checker = ActiveChecker()  # store 由 main.py 启动时注入（见 app/main.py）
