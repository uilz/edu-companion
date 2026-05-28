"""情境引擎 — 感知用户当前学习情境

作用:
  1. 判断"现在是适合提出建议的时机吗?"
  2. 避免打断深度专注状态
  3. 为提案排序提供上下文权重

数据源:
  - CognitiveNode.engagement (学习行为)
  - CognitiveNode.cognitive_load (认知负荷)
  - CognitiveNode.dialogue_contexts (最近对话)
  - EventBus (实时事件)
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone


logger = logging.getLogger(__name__)


class SessionContext:
    """用户当前会话情境快照"""

    def __init__(self) -> None:
        self.session_duration_min: float = 0
        self.current_subject: str = ""
        self.recent_accuracy: float = 0.7
        self.cognitive_load: float = 0.3
        self.questions_done_recently: int = 0
        self.engagement_streak: int = 0
        self.last_interaction_min: float = 0
        self.is_deep_focus: bool = False
        self.estimated_energy: str = "normal"  # high / normal / low
        self.quiet_hours: bool = False


class ContextEngine:
    """情境引擎 — 轻量、不阻塞、不查询 DB"""

    def __init__(self) -> None:
        self._last_session_check: dict[str, SessionContext] = {}

    async def assess(self, user_id: str, lookback_minutes: int = 5) -> SessionContext:
        """快速评估当前情境"""
        ctx = SessionContext()
        try:
            from app.cognitive.storage import list_all_nodes
            import asyncio

            nodes = await asyncio.to_thread(list_all_nodes, user_id)
            if not nodes:
                return ctx

            # 从任意节点提取 engagement
            engagements = [n.engagement for n in nodes if n.engagement]
            if engagements:
                e = engagements[0]
                ctx.engagement_streak = e.streak_current or 0
                ctx.questions_done_recently = sum(
                    n.practice_summary.total_attempts for n in nodes[:5] if n.practice_summary
                )

            # 认知负荷（取平均）
            loads = [n.cognitive_load.intrinsic for n in nodes if n.cognitive_load]
            if loads:
                ctx.cognitive_load = sum(loads[:5]) / min(len(loads[:5]), 5)
                ctx.estimated_energy = "low" if ctx.cognitive_load > 0.7 else "normal"

            # 最近对话上下文
            contexts = [n.dialogue_contexts for n in nodes if n.dialogue_contexts]
            if contexts:
                recent = contexts[0]
                if hasattr(recent, 'summary_text') and recent.summary_text:
                    ctx.current_subject = recent.summary_text[:50]

            # 安静时段检测 (22:00-08:00)
            hour = datetime.now(timezone.utc).hour + 8  # UTC+8
            ctx.quiet_hours = hour >= 22 or hour < 8

        except Exception as e:
            logger.debug("情境评估失败(数据不足): %s", e)

        self._last_session_check[user_id] = ctx
        return ctx

    def should_suggest(self, ctx: SessionContext) -> tuple[bool, str]:
        """判断当前是否适合主动提出建议"""
        if ctx.quiet_hours:
            return False, "安静时段，不打扰"
        if ctx.estimated_energy == "low":
            return False, "当前认知负荷偏高，不增加负担"
        if ctx.session_duration_min < 2:
            return False, "学习刚开始，不打断"
        if ctx.is_deep_focus:
            return False, "深度专注模式，不打扰"
        if ctx.questions_done_recently == 0 and ctx.engagement_streak == 0:
            return False, "冷启动用户，暂无数据"
        return True, "可以建议"

    def get_reason(self, ctx: SessionContext) -> str:
        """获取建议理由"""
        reasons = []
        if ctx.engagement_streak >= 3:
            reasons.append(f"连续学习 {ctx.engagement_streak} 天")
        if ctx.questions_done_recently > 50:
            reasons.append(f"已完成 {ctx.questions_done_recently} 题")
        if ctx.cognitive_load > 0.3:
            reasons.append("当前有一定认知负荷")
        return "，".join(reasons) if reasons else "日常提醒"
