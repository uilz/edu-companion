"""内置模块: 疲劳管理 (FatigueManager)

功能: 检测用户疲劳信号，适时建议休息
触发条件:
  - 连续学习时长 > 45 分钟
  - 最近 10 题准确率 < 40%
  - 认知负荷 > 0.7
  - 安静时段 (22:00-08:00)
"""

from __future__ import annotations

import logging

from ..models import Proposal
from .context_engine import SessionContext
from .module_registry import SecretaryModule, ModuleMeta

logger = logging.getLogger(__name__)


class FatigueManagerModule(SecretaryModule):
    """疲劳管理模块"""

    @property
    def meta(self) -> ModuleMeta:
        return ModuleMeta(
            name="fatigue_manager",
            display_name="疲劳管理",
            emoji="😴",
            description="检测学习疲劳信号，适时建议休息",
            default_enabled=True,
            run_interval_seconds=600,
        )

    async def run_check(
        self, user_id: str, ctx: SessionContext | None = None,
    ) -> list[Proposal]:
        """检测疲劳信号"""
        from ..analysis import predict_fatigue_risk, _get_nodes

        nodes = _get_nodes(user_id)

        proposals: list[Proposal] = []

        # 1. 情境判断
        if ctx:
            # 安静时段 — 强烈建议休息
            if ctx.quiet_hours:
                if ctx.session_duration_min > 15:
                    proposals.append(Proposal(
                        emoji="🌙",
                        title="该休息了",
                        description="已经是休息时间了，建议先休息，明天再学习效果更好",
                        action_type="rest",
                        priority=5,
                        payload={"reason": "quiet_hours", "session_minutes": ctx.session_duration_min},
                        insight_source="fatigue_quiet_hours",
                    ))
                    return proposals  # 安静时段直接返回，不继续检查

            # 高认知负荷
            if ctx.cognitive_load > 0.7:
                proposals.append(Proposal(
                    emoji="😵",
                    title="看起来有些累了",
                    description=f"当前认知负荷偏高 ({ctx.cognitive_load:.0%})，建议休息 5-10 分钟再继续",
                    action_type="rest",
                    priority=4 if ctx.cognitive_load > 0.8 else 3,
                    payload={"reason": "high_cognitive_load", "load": ctx.cognitive_load},
                    insight_source="fatigue_high_load",
                ))

            # 长时间学习
            if ctx.session_duration_min > 45:
                duration_h = ctx.session_duration_min / 60
                proposals.append(Proposal(
                    emoji="💪",
                    title=f"已学习 {duration_h:.1f} 小时",
                    description="长时间专注学习很棒，但适当休息能提高效率。建议起身活动一下",
                    action_type="rest",
                    priority=3,
                    payload={"reason": "long_session", "duration_min": ctx.session_duration_min},
                    insight_source="fatigue_long_session",
                ))

        # 2. 分析层疲劳风险
        try:
            fatigue = predict_fatigue_risk(user_id, nodes=nodes)
            for item in fatigue.items[:2]:
                if item.norm_urgency > 0.6:
                    proposals.append(Proposal(
                        emoji="📉",
                        title=f"注意疲劳信号: {item.label}",
                        description="近期表现下降，可能是疲劳信号。建议安排轻松学习或休息",
                        action_type="rest",
                        priority=3,
                        payload={"kp_id": item.node_id, "urgency": item.norm_urgency},
                        insight_source="predict_fatigue_risk",
                    ))
        except Exception as e:
            logger.debug("疲劳分析检查: %s", e)

        return proposals
