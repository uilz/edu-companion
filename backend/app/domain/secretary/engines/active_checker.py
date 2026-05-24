"""主动检查器 — 定时执行轻量检查，生成提案并推送到黑板

检查频率: 每 10 分钟
检查项:
  1. 复习到期项 (find_overdue_reviews)
  2. 停滞知识点 (detect_stagnant_topics)
  3. 疲劳信号 (predict_fatigue_risk)
  4. 数据不足时不生成提案
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any

from ..models import ScopeSpec
from ..analysis import find_overdue_reviews, detect_stagnant_topics, predict_fatigue_risk

logger = logging.getLogger(__name__)


class ActiveChecker:
    """主动检查器 — 周期性检查和黑板推送"""

    def __init__(self, user_id: str = "default_user") -> None:
        self._user_id = user_id
        self._running = False
        self._task: asyncio.Task | None = None
        self._check_interval = 600  # 10分钟
        self._last_check_counts: dict[str, int] = {"overdue": 0, "stagnant": 0, "fatigue": 0}

    async def run_check(self) -> dict[str, Any]:
        """执行一次主动检查"""
        from ..secretary_service import SecretaryService

        service = SecretaryService()
        findings: dict[str, Any] = {
            "overdue": [], "stagnant": [], "fatigue": None,
            "ctx": {"should_push": True, "reasons": []},
        }

        # 1. 复习到期项
        try:
            overdue = find_overdue_reviews(self._user_id)
            findings["overdue"] = overdue.items[:5] if hasattr(overdue, 'items') else []
            if findings["overdue"]:
                findings["ctx"]["reasons"].append(f"{len(findings['overdue'])} 个知识点需要复习")
        except Exception as e:
            logger.debug("复习检查: %s", e)

        # 2. 停滞知识点
        try:
            stagnant = detect_stagnant_topics(self._user_id)
            findings["stagnant"] = stagnant.items[:5] if hasattr(stagnant, 'items') else []
            if findings["stagnant"]:
                findings["ctx"]["reasons"].append(f"{len(findings['stagnant'])} 个知识点停滞")
        except Exception as e:
            logger.debug("停滞检查: %s", e)

        # 3. 疲劳信号
        try:
            fatigue = predict_fatigue_risk(self._user_id)
            findings["fatigue"] = fatigue.items[:3] if hasattr(fatigue, 'items') else []
            if findings["fatigue"]:
                findings["ctx"]["reasons"].append("检测到疲劳风险")
        except Exception as e:
            logger.debug("疲劳检查: %s", e)

        # 4. 判定是否真的要推送
        has_new = (
            len(findings["overdue"]) != self._last_check_counts.get("overdue", 0)
            or len(findings["stagnant"]) != self._last_check_counts.get("stagnant", 0)
        )
        self._last_check_counts = {
            "overdue": len(findings["overdue"]),
            "stagnant": len(findings["stagnant"]),
        }

        findings["ctx"]["should_push"] = has_new and len(findings["ctx"]["reasons"]) > 0
        return findings

    async def _loop(self) -> None:
        """后台循环"""
        logger.info("🔍 秘书主动检查器启动 (间隔 %ds)", self._check_interval)
        while self._running:
            try:
                findings = await self.run_check()
                if findings["ctx"]["should_push"]:
                    logger.info("📋 主动检查发现新事项: %s", findings["ctx"]["reasons"])
                    # 生成提案并推送到黑板
                    from ..secretary_service import SecretaryService
                    service = SecretaryService()
                    report, proposals = await service.diagnose_and_suggest(
                        self._user_id, max_proposals=2,
                    )
                    # 推送到黑板 (仅推session级别)
                    from app.core.blackboard import blackboard
                    await service.push_to_blackboard("_active_check", proposals, report)

                    # 推送 WS 通知（如果可用）
                    try:
                        from app.api.chat import manager as ws_manager
                        if ws_manager and hasattr(ws_manager, 'broadcast'):
                            await ws_manager.broadcast({
                                "type": "secretary_update",
                                "content": {
                                    "reason": findings["ctx"]["reasons"],
                                    "proposal_count": len(proposals),
                                }
                            })
                    except Exception:
                        pass
                else:
                    logger.debug("主动检查: 无新事项")
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.warning("主动检查异常: %s", e)
            await asyncio.sleep(self._check_interval)

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
