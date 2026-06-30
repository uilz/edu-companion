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


# ═══════════════════════════════════════════
# 5. 错因模式识别 (ErrorPattern) — ADR 0011 S5
# ═══════════════════════════════════════════

class ErrorPatternModule(SecretaryModule):
    """错因模式识别模块 — 分析最近错题的错误类型分布，发现集中错因"""

    @property
    def meta(self) -> ModuleMeta:
        return ModuleMeta(
            name="error_pattern",
            display_name="错因模式识别",
            emoji="🔍",
            description="分析最近错题的错误类型分布，发现集中错因并给出建议",
            default_enabled=True,
            run_interval_seconds=600,
        )

    async def run_check(
        self, user_id: str, ctx: SessionContext | None = None,
    ) -> list[Proposal]:
        proposals: list[Proposal] = []

        try:
            patterns = self._analyze_error_patterns(user_id)
            if not patterns:
                return proposals

            # 检查是否有错因占比 > 40%
            total = sum(patterns.values())
            if total < 5:
                return proposals  # 错题太少，不够分析

            for error_type, count in sorted(patterns.items(), key=lambda x: -x[1]):
                ratio = count / total if total > 0 else 0
                if ratio < 0.4:
                    continue

                suggestion = self._get_suggestion(error_type, ratio)
                category_label = self._get_category_label(error_type)

                proposals.append(Proposal(
                    emoji="🔍",
                    title=f"错因集中: {category_label}",
                    description=(
                        f"最近 {total} 道错题中，{category_label}占 {ratio:.0%}（{count} 道）。"
                        f"{suggestion}"
                    ),
                    action_type="practice_error_pattern",
                    priority=3 if ratio > 0.6 else 4,
                    payload={
                        "error_type": error_type,
                        "count": count,
                        "total": total,
                        "ratio": ratio,
                        "suggestion": suggestion,
                    },
                    insight_source="error_pattern_analysis",
                ))
        except Exception as e:
            logger.debug("错因模式分析失败: %s", e)

        return proposals

    def _analyze_error_patterns(self, user_id: str) -> dict[str, int]:
        """统计最近 20 道错题的 error_type 分布"""
        from app.infrastructure.db.database import get_db
        db = get_db()
        try:
            rows = db.fetchall(
                """SELECT error_pattern, error_analysis
                   FROM practice_attempts
                   WHERE user_id = %s AND is_correct = FALSE
                   ORDER BY created_at DESC
                   LIMIT 20""",
                (user_id,),
            )
        except Exception:
            return {}

        patterns: dict[str, int] = {}
        for row in rows:
            error_type = (row.get("error_pattern") or "").strip()
            if not error_type:
                # 尝试从 error_analysis JSON 提取
                ea = row.get("error_analysis") or {}
                if isinstance(ea, str):
                    import json
                    try:
                        ea = json.loads(ea)
                    except Exception:
                        ea = {}
                error_type = (ea.get("error_type") or ea.get("distractor_type") or "").strip()

            if error_type:
                patterns[error_type] = patterns.get(error_type, 0) + 1

        return patterns

    def _get_category_label(self, error_type: str) -> str:
        """错误类型 → 中文标签"""
        labels = {
            "conceptual": "概念混淆",
            "concept_confusion": "概念混淆",
            "procedural": "步骤错误",
            "computation": "计算失误",
            "calculation_error": "计算失误",
            "sign_error": "符号错误",
            "reading": "审题不清",
            "careless": "粗心大意",
            "transfer": "知识迁移困难",
            "meta": "元认知问题",
        }
        return labels.get(error_type, error_type or "未知错因")

    def _get_suggestion(self, error_type: str, ratio: float) -> str:
        """根据错因类型给出建议"""
        suggestions = {
            "conceptual": "建议先复习相关概念，再做概念辨析练习。",
            "concept_confusion": "建议先复习相关概念，再做概念辨析练习。",
            "procedural": "建议放慢解题速度，每步都写下推理过程。",
            "computation": "建议练习计算基本功，可以从简单数值开始。",
            "calculation_error": "建议练习计算基本功，可以从简单数值开始。",
            "sign_error": "建议重点练习符号处理，注意正负号。",
            "reading": "建议仔细审题，圈出关键词。",
            "careless": "建议放慢速度，养成检查习惯。",
            "transfer": "建议多做变式题，对比不同题型的共同点。",
            "meta": "建议反思解题策略，思考是否有更优解法。",
        }
        # 如果占比很高，加大建议力度
        intense = "这个问题比较突出，" if ratio > 0.6 else ""
        return intense + suggestions.get(error_type, "建议针对性练习该知识点的同类题。")
