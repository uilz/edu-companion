"""秘书-计划桥接 — 将秘书分析结果转化为学习路径调整

工作流程:
  1. 秘书提案被采纳（review/practice 类型）
  2. 桥接器获取该技能的最新分析数据
  3. 调用 AdaptivePlanGenerator 重新生成计划
  4. 将计划调整结果写入 plan_snapshots

触发点:
  - 提案被采纳时 (proposal_action_handler 通知)
  - 主动检查发现重大变化 (active_checker)
  - API 手动触发
"""

from __future__ import annotations
from shared.constants import DEFAULT_USER_ID
import logging
from ..models import Proposal

logger = logging.getLogger(__name__)


class SecretaryPlanBridge:
    """秘书分析与自适应计划之间的桥接器"""

    def __init__(self) -> None:
        self._planner = None

    @property
    def planner(self):
        if self._planner is None:
            from app.services.analytics.adaptive_planner import AdaptivePlanGenerator
            self._planner = AdaptivePlanGenerator()
        return self._planner

    async def on_proposal_accepted(
        self, proposal: Proposal, user_id: str = DEFAULT_USER_ID,
    ) -> dict[str, Any]:
        """提案被采纳时触发计划调整"""
        action_type = proposal.action_type
        payload = proposal.payload or {}
        kp_id = payload.get("kp_id", "")

        if action_type not in ("review", "practice", "explore"):
            return {"adjusted": False, "reason": f"动作类型 {action_type} 不触发计划调整"}

        reason = f"secretary:{action_type}:{proposal.id}"
        if kp_id:
            reason += f":{kp_id}"

        try:
            plan = await self.planner.generate(user_id, reason=reason)
            logger.info(
                "计划已调整: user=%s reason=%s items=%d changes=%d",
                user_id, reason, len(plan.get("plan", {}).get("items", [])),
                plan.get("changes", {}).get("change_count", 0),
            )
            return {
                "adjusted": True,
                "reason": reason,
                "plan_summary": {
                    "total_items": len(plan.get("plan", {}).get("items", [])),
                    "change_count": plan.get("changes", {}).get("change_count", 0),
                    "changes": plan.get("changes", {}),
                },
            }
        except Exception as e:
            logger.warning("计划调整失败: %s", e)
            return {"adjusted": False, "reason": str(e)}

    async def get_plan_summary(
        self, user_id: str = DEFAULT_USER_ID,
    ) -> dict[str, Any]:
        """获取当前学习计划摘要"""
        try:
            plan = await self.planner.generate(user_id, reason="secretary:summary")
            return {
                "available": True,
                "items": plan.get("plan", {}).get("items", [])[:5],
                "total_items": plan.get("plan", {}).get("total_items", 0),
                "daily_questions": plan.get("plan", {}).get("daily_questions", 5),
                "habit_level": plan.get("plan", {}).get("habit_level", "beginner"),
                "difficulty_bias": plan.get("plan", {}).get("difficulty_bias", 0),
            }
        except Exception as e:
            logger.warning("获取计划摘要失败: %s", e)
            return {"available": False, "error": str(e)}


# ── 全局实例 ──
plan_bridge = SecretaryPlanBridge()
