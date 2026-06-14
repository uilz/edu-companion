"""提案生成 + 执行引擎 — 模板提案生成 & 用户采纳后自动行动

合并自: proposal_generator.py (176 行), proposal_action_handler.py (219 行)
"""

from __future__ import annotations

import logging
from typing import Any

from ..models import DiagnosisReport, Proposal

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════
# 提案模板
# ═══════════════════════════════════════════

REVIEW_TEMPLATE = {
    "emoji": "📖", "title": "复习「{label}」",
    "description": "该知识点掌握度 {mastery:.0%}，遗忘风险较高，建议安排一次复习",
    "action_type": "review", "priority": 4,
}
PRACTICE_TEMPLATE = {
    "emoji": "✏️", "title": "练习「{label}」巩固",
    "description": "该知识点处于薄弱状态（掌握度 {mastery:.0%}），做题练习来巩固",
    "action_type": "practice", "priority": 5,
}
REST_TEMPLATE = {
    "emoji": "☕", "title": "休息一下",
    "description": "当前认知负荷偏高（{load:.0%}），休息一会效率更高",
    "action_type": "rest", "priority": 3,
}
EXPLORE_TEMPLATE = {
    "emoji": "🔗", "title": "探索关联知识「{label}」",
    "description": "该知识点与已掌握的领域存在连接，尝试跨域探索",
    "action_type": "explore", "priority": 2,
}
EXAM_PREP_TEMPLATE = {
    "emoji": "🎯", "title": "备考冲刺：{label}",
    "description": "该知识点在考试范围内且掌握度不足（{mastery:.0%}），建议重点突破",
    "action_type": "exam_prep", "priority": 5,
}


# ═══════════════════════════════════════════
# 提案生成器
# ═══════════════════════════════════════════

class ProposalGenerator:
    """提案生成器 — 基于分析和诊断结果"""

    def generate_from_diagnosis(
        self,
        report: DiagnosisReport,
        max_proposals: int = 5,
    ) -> list[Proposal]:
        proposals: list[Proposal] = []

        for wp in report.weak_points[:3]:
            template = PRACTICE_TEMPLATE if wp.mastery < 0.5 else REVIEW_TEMPLATE
            proposals.append(Proposal(
                emoji=template["emoji"],
                title=template["title"].format(label=wp.name, mastery=wp.mastery),
                description=template["description"].format(label=wp.name, mastery=wp.mastery),
                action_type=template["action_type"],
                payload={"kp_id": wp.knowledge_point_id, "mastery": wp.mastery},
                priority=template["priority"],
                generated_by="diagnosis_engine",
                insight_source="find_weakness_clusters",
            ))

        if report.cognitive_load > 0.7:
            proposals.append(Proposal(
                emoji=REST_TEMPLATE["emoji"], title=REST_TEMPLATE["title"],
                description=REST_TEMPLATE["description"].format(load=report.cognitive_load),
                action_type=REST_TEMPLATE["action_type"],
                payload={"cognitive_load": report.cognitive_load},
                priority=REST_TEMPLATE["priority"],
                generated_by="diagnosis_engine",
                insight_source="assess_current_burden",
            ))

        proposals.sort(key=lambda p: -p.priority)
        return proposals[:max_proposals]

    def generate_from_analysis(
        self,
        user_id: str,
        max_proposals: int = 5,
    ) -> list[Proposal]:
        proposals: list[Proposal] = []

        from ..analysis import rank_recommendations, assess_current_burden
        recommendations = rank_recommendations(user_id=user_id)
        for insight in recommendations.items[:3]:
            template = PRACTICE_TEMPLATE if insight.norm_urgency > 0.6 else REVIEW_TEMPLATE
            proposals.append(Proposal(
                emoji=template["emoji"],
                title=template["title"].format(label=insight.label, mastery=1.0 - insight.norm_urgency),
                description=template["description"].format(label=insight.label, mastery=1.0 - insight.norm_urgency),
                action_type=template["action_type"],
                payload={"kp_id": insight.node_id, "urgency": insight.norm_urgency},
                priority=template["priority"],
                generated_by="proposal_generator",
                insight_source="rank_recommendations",
            ))

        burden = assess_current_burden(user_id=user_id)
        if burden.items and burden.items[0].primary_value > 0.7:
            proposals.append(Proposal(
                emoji=REST_TEMPLATE["emoji"], title=REST_TEMPLATE["title"],
                description=REST_TEMPLATE["description"].format(load=burden.items[0].primary_value),
                action_type="rest", payload={"cognitive_load": burden.items[0].primary_value},
                priority=3, generated_by="proposal_generator",
                insight_source="assess_current_burden",
            ))

        proposals.sort(key=lambda p: -p.priority)
        return proposals[:max_proposals]

    def generate_multi_option(self, report: DiagnosisReport) -> list[list[Proposal]]:
        all_proposals = self.generate_from_diagnosis(report, max_proposals=9)
        groups = []
        for i in range(0, len(all_proposals), 3):
            group = all_proposals[i:i+3]
            if group:
                groups.append(group)
        return groups


# ═══════════════════════════════════════════
# 提案执行器
# ═══════════════════════════════════════════

class ProposalActionHandler:
    """提案采纳行动执行器"""

    def __init__(self) -> None:
        self._executors = {
            "review": self._execute_review,
            "practice": self._execute_practice,
            "rest": self._execute_rest,
            "brief": self._execute_brief,
            "explore": self._execute_explore,
        }

    async def execute(self, proposal: Proposal, user_id: str) -> dict[str, Any]:
        executor = self._executors.get(proposal.action_type)
        if not executor:
            return {
                "action_type": proposal.action_type, "success": False,
                "message": f"未知动作类型: {proposal.action_type}",
                "context": None, "payload": proposal.payload or {},
            }
        result = await executor(proposal, user_id)
        logger.info("执行提案动作: type=%s proposal=%s success=%s",
                     proposal.action_type, proposal.id, result["success"])
        return result

    async def _execute_review(self, proposal: Proposal, user_id: str) -> dict[str, Any]:
        kp_id = (proposal.payload or {}).get("kp_id", "")
        if not kp_id:
            return {"action_type": "review", "success": False,
                    "message": "未指定复习知识点", "context": None, "payload": {}}
        context_text = None
        try:
            from app.domain.cognitive import get_repo
            node = get_repo().get_node(user_id, kp_id)
            if node and node.belief:
                import json as _json
                belief = node.belief
                if isinstance(belief, str):
                    belief = _json.loads(belief)
                proficiency = belief.get("proficiency_mean", 0.0)
                recent_practice = ""
                if node.practice_summary:
                    acc = node.practice_summary.accuracy or 0
                    recent_practice = f"最近正确率 {acc:.0%}"
                context_text = f"📖 你选择了复习「{kp_id}」。当前掌握度 {proficiency:.0%}。{recent_practice}"
        except Exception as e:
            logger.debug("获取知识点详情失败: %s", e)
            context_text = f"📖 开始复习「{kp_id}」"
        return {"action_type": "review", "success": True,
                "message": f"好的，我们来复习「{kp_id}」！",
                "context": context_text, "payload": {"kp_id": kp_id, **proposal.payload}}

    async def _execute_practice(self, proposal: Proposal, user_id: str) -> dict[str, Any]:
        kp_id = (proposal.payload or {}).get("kp_id", "")
        context_text = "📝 开始专项练习"
        if kp_id:
            context_text = f"📝 针对「{kp_id}」进行专项练习"
        return {"action_type": "practice", "success": True,
                "message": "好的，为你安排针对性练习！",
                "context": context_text, "payload": {"kp_id": kp_id, **proposal.payload}}

    async def _execute_rest(self, proposal: Proposal, user_id: str) -> dict[str, Any]:
        payload = proposal.payload or {}
        duration_min = payload.get("session_minutes", 0)
        context_text = "☕ 休息时间"
        if duration_min > 45:
            context_text = f"☕ 已学习 {duration_min//60}h{duration_min%60}m，建议休息 10 分钟"
        return {"action_type": "rest", "success": True,
                "message": "休息一下，学习效率更高哦！",
                "context": context_text, "payload": payload}

    async def _execute_brief(self, proposal: Proposal, user_id: str) -> dict[str, Any]:
        payload = proposal.payload or {}
        date = payload.get("date", "今天")
        details = []
        try:
            from app.domain.cognitive import get_repo
            nodes = get_repo().list_all_nodes(user_id)
            if nodes:
                subjects = {}
                for n in nodes:
                    if n.practice_summary and n.practice_summary.accuracy:
                        subjects[n.id] = {"accuracy": n.practice_summary.accuracy,
                                          "attempts": n.practice_summary.total_attempts or 0}
                details = [f"  • {k}: 正确率 {v['accuracy']:.0%} ({v['attempts']} 题)"
                           for k, v in list(subjects.items())[:5]]
        except Exception as e:
            logger.warning("Failed to fetch cognitive node data for briefing: %s", e)
        context_parts = [f"📊 {date} 学习简报"]
        if details:
            context_parts.append("详细数据:")
            context_parts.extend(details)
        else:
            context_parts.append("暂无详细练习数据")
        return {"action_type": "brief", "success": True,
                "message": f"这是 {date} 的学习小结！",
                "context": "\n".join(context_parts[:8]),
                "payload": {"date": date, "detail_count": len(details), **payload}}

    async def _execute_explore(self, proposal: Proposal, user_id: str) -> dict[str, Any]:
        kp_id = (proposal.payload or {}).get("kp_id", "")
        context_text = "🔍 扩展学习"
        if kp_id:
            context_text = f"🔍 推荐「{kp_id}」的扩展资源"
        return {"action_type": "explore", "success": True,
                "message": "为你推荐一些扩展学习资源！",
                "context": context_text, "payload": {"kp_id": kp_id, **proposal.payload}}


# ── 全局实例 ──
action_handler = ProposalActionHandler()
