"""内置模块: 复习/疲劳/备考/扩展 — 学习行为相关模块组

合并自: builtin_review_reminder.py, builtin_fatigue_manager.py, exam_mode.py, builtin_lateral_expansion.py
"""

from __future__ import annotations

import logging
from datetime import datetime

from ..models import Proposal
from .context_engine import SessionContext
from .module_registry import SecretaryModule, ModuleMeta

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════
# 1. 复习提醒 (ReviewReminder)
# ═══════════════════════════════════════════

class ReviewReminderModule(SecretaryModule):
    """复习提醒模块"""

    @property
    def meta(self) -> ModuleMeta:
        return ModuleMeta(
            name="review_reminder",
            display_name="复习提醒",
            emoji="🔁",
            description="定期提醒复习已学知识点，防止遗忘",
            default_enabled=True,
            run_interval_seconds=600,
        )

    async def run_check(
        self, user_id: str, ctx: SessionContext | None = None,
    ) -> list[Proposal]:
        from ..analysis import _get_nodes, find_overdue_reviews, detect_stagnant_topics
        nodes = _get_nodes(user_id)
        proposals: list[Proposal] = []

        try:
            overdue = find_overdue_reviews(user_id, nodes=nodes)
            for item in overdue[:3]:
                urgency = item.get("urgency", 0)
                mastery = item.get("mastery", 0)
                proposals.append(Proposal(
                    emoji="📖",
                    title=f"复习提醒: {item.get('label', '')}",
                    description=f"紧迫度 {round(urgency*10,1)}/10，掌握度 {mastery}%。建议安排 15 分钟快速回顾",
                    action_type="review",
                    priority=4 if urgency > 0.7 else 3,
                    payload={"kp_id": item.get("node_id", ""), "urgency": urgency, "mastery": mastery},
                    insight_source="find_overdue_reviews",
                ))
        except Exception as e:
            logger.debug("复习到期检查: %s", e)

        try:
            stagnant = detect_stagnant_topics(user_id, nodes=nodes)
            for item in stagnant[:2]:
                days_since = item.get("days_since", 0)
                if days_since > 5:
                    proposals.append(Proposal(
                        emoji="⏰",
                        title=f"停滞知识点: {item.get('label', '')}",
                        description=f"已 {days_since:.0f} 天未练习，建议安排专题复习",
                        action_type="review",
                        priority=3,
                        payload={"kp_id": item.get("node_id", ""), "stagnation_days": days_since},
                        insight_source="detect_stagnant_topics",
                    ))
        except Exception as e:
            logger.debug("停滞知识点检查: %s", e)

        return proposals


# ═══════════════════════════════════════════
# 2. 疲劳管理 (FatigueManager)
# ═══════════════════════════════════════════

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
        from ..analysis import predict_fatigue_risk, _get_nodes
        nodes = _get_nodes(user_id)
        proposals: list[Proposal] = []

        if ctx:
            if ctx.quiet_hours:
                if ctx.session_duration_min > 15:
                    proposals.append(Proposal(
                        emoji="🌙",
                        title="该休息了",
                        description="已经是休息时间了，建议先休息，明天再学习效果更好",
                        action_type="rest",
                        priority=1,
                        payload={"reason": "quiet_hours"},
                        insight_source="assess_current_burden",
                    ))
                    return proposals

        fatigue = predict_fatigue_risk(user_id)
        if fatigue.get("risk_level", 0) > 0.6:
            proposals.append(Proposal(
                emoji="😴",
                title="疲劳信号提醒",
                description=f"连续学习时间较长，建议休息 {fatigue.get('recommended_rest_min', 10)} 分钟",
                action_type="rest",
                priority=2,
                payload={"risk": fatigue, "reason": "fatigue"},
                insight_source="predict_fatigue_risk",
            ))

        return proposals


# ═══════════════════════════════════════════
# 3. 备考模式 (ExamMode)
# ═══════════════════════════════════════════

class ExamModeModule(SecretaryModule):
    """备考模式 — 考试检测 + 冲刺清单"""

    @property
    def meta(self) -> ModuleMeta:
        return ModuleMeta(
            name="exam_mode",
            display_name="备考模式",
            emoji="📚",
            description="检测考试事件，生成冲刺复习清单",
            default_enabled=False,
            run_interval_seconds=3600,
            version="1.0.0",
            author="系统内置",
        )

    async def run_check(self, user_id: str, ctx: SessionContext | None = None) -> list[Proposal]:
        proposals = []
        upcoming_exams = self._detect_upcoming_exams(user_id, ctx)
        for exam in upcoming_exams:
            days_left = exam["days_left"]
            if days_left <= 7:
                urgency = "high" if days_left <= 3 else "medium"
                priority = 1 if urgency == "high" else 3
                proposals.append(Proposal(
                    id=f"exam_{exam['name']}_{datetime.now().timestamp():.0f}",
                    emoji="📚",
                    title=f"📚 {exam['name']} 备考冲刺",
                    description=f"距 {exam['name']} 还有{days_left}天，"
                               f"已进入{'冲刺阶段' if urgency == 'high' else '备考期'}。"
                               f"建议优先复习相关的高频考点和薄弱点。",
                    action_type="review",
                    payload={"exam_name": exam["name"], "exam_date": exam["date"],
                             "days_left": days_left, "urgency": urgency},
                    priority=priority,
                    generated_by="exam_mode",
                    overrideable=True,
                ))
        return proposals

    def _detect_upcoming_exams(self, user_id: str, ctx: SessionContext | None = None) -> list[dict]:
        return []


# ═══════════════════════════════════════════
# 4. 横向扩展 (LateralExpansion)
# ═══════════════════════════════════════════

class LateralExpansionModule(SecretaryModule):
    """横向扩展提案模块"""

    @property
    def meta(self) -> ModuleMeta:
        return ModuleMeta(
            name="lateral_expansion",
            display_name="知识结构扩展",
            emoji="🌱",
            description="检测知识树可扩展方向，建议新增专题",
            default_enabled=True,
            run_interval_seconds=600,
        )

    async def run_check(
        self, user_id: str, ctx: SessionContext | None = None,
    ) -> list[Proposal]:
        from app.domain.cognitive.growth_engine import growth_engine
        from app.domain.cognitive import get_repo
        proposals: list[Proposal] = []

        for level in ("partition", "domain", "topic"):
            parents = get_repo().get_nodes_by_level(level, user_id)
            for parent in parents:
                try:
                    suggestions = growth_engine.suggest_lateral_expansion(user_id, parent.id)
                    for s in suggestions:
                        proposals.append(Proposal(
                            emoji="🌿",
                            title=f"扩展「{s['parent_label']}」的知识结构",
                            description=(f"该分类下已有 {s['visible_count']} 个活跃子专题。"
                                        "需要自动生成更多分支方向吗？"),
                            action_type="lateral_expansion",
                            priority=2,
                            payload={"parent_id": s["parent_id"], "parent_label": s["parent_label"],
                                     "visible_count": s["visible_count"]},
                            insight_source="lateral_expansion",
                        ))
                except Exception as e:
                    logger.debug("横向扩展扫描异常[%s/%s]: %s", level, parent.id, e)

        return proposals
