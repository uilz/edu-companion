"""提案生成器 — 模板优先 + 可选 LLM 润色

生成策略:
  1. 基于诊断结果 + 分析洞察，匹配模板
  2. 模板填充具体知识点的 label / mastery
  3. 可选 LLM 润色（未来 Phase 7.2）
  4. 确保协商语气 + 多选项
"""

from __future__ import annotations

import logging
from typing import Any

from ..models import (
    DiagnosisReport,
    Proposal,
    ScoredInsight,
    ScopeSpec,
)
from ..analysis import (
    find_weakness_clusters,
    rank_forgetting_risk,
    find_overdue_reviews,
    rank_recommendations,
    analyze_error_patterns,
)

logger = logging.getLogger(__name__)

_USER_ID_DEFAULT = "default_user"

# ── 提案模板 ──

REVIEW_TEMPLATE = {
    "emoji": "📖",
    "title": "复习「{label}」",
    "description": "该知识点掌握度 {mastery:.0%}，遗忘风险较高，建议安排一次复习",
    "action_type": "review",
    "priority": 4,
}

PRACTICE_TEMPLATE = {
    "emoji": "✏️",
    "title": "练习「{label}」巩固",
    "description": "该知识点处于薄弱状态（掌握度 {mastery:.0%}），做题练习来巩固",
    "action_type": "practice",
    "priority": 5,
}

REST_TEMPLATE = {
    "emoji": "☕",
    "title": "休息一下",
    "description": "当前认知负荷偏高（{load:.0%}），休息一会效率更高",
    "action_type": "rest",
    "priority": 3,
}

EXPLORE_TEMPLATE = {
    "emoji": "🔗",
    "title": "探索关联知识「{label}」",
    "description": "该知识点与已掌握的领域存在连接，尝试跨域探索",
    "action_type": "explore",
    "priority": 2,
}

EXAM_PREP_TEMPLATE = {
    "emoji": "🎯",
    "title": "备考冲刺：{label}",
    "description": "该知识点在考试范围内且掌握度不足（{mastery:.0%}），建议重点突破",
    "action_type": "exam_prep",
    "priority": 5,
}


class ProposalGenerator:
    """提案生成器 — 基于分析和诊断结果"""

    def generate_from_diagnosis(
        self,
        report: DiagnosisReport,
        max_proposals: int = 5,
    ) -> list[Proposal]:
        """基于诊断报告生成提案"""
        proposals: list[Proposal] = []

        # 1. 薄弱点 → 练习提案（最多 3 个）
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

        # 2. 认知负荷高 → 休息提案
        if report.cognitive_load > 0.7:
            proposals.append(Proposal(
                emoji=REST_TEMPLATE["emoji"],
                title=REST_TEMPLATE["title"],
                description=REST_TEMPLATE["description"].format(load=report.cognitive_load),
                action_type=REST_TEMPLATE["action_type"],
                payload={"cognitive_load": report.cognitive_load},
                priority=REST_TEMPLATE["priority"],
                generated_by="diagnosis_engine",
                insight_source="assess_current_burden",
            ))

        # 排序：按 priority（1=最高）
        proposals.sort(key=lambda p: -p.priority)
        return proposals[:max_proposals]

    def generate_from_analysis(
        self,
        user_id: str = _USER_ID_DEFAULT,
        max_proposals: int = 5,
    ) -> list[Proposal]:
        """直接从分析层生成提案（不依赖诊断报告）"""
        proposals: list[Proposal] = []

        # 1. 推荐综合排序 → 练习/复习提案
        recommendations = rank_recommendations(user_id=user_id)
        for insight in recommendations.items[:3]:
            template = PRACTICE_TEMPLATE if insight.norm_urgency > 0.6 else REVIEW_TEMPLATE
            proposals.append(Proposal(
                emoji=template["emoji"],
                title=template["title"].format(
                    label=insight.label,
                    mastery=1.0 - insight.norm_urgency,
                ),
                description=template["description"].format(
                    label=insight.label,
                    mastery=1.0 - insight.norm_urgency,
                ),
                action_type=template["action_type"],
                payload={"kp_id": insight.node_id, "urgency": insight.norm_urgency},
                priority=template["priority"],
                generated_by="proposal_generator",
                insight_source="rank_recommendations",
            ))

        # 2. 认知负荷
        from ..analysis import assess_current_burden
        burden = assess_current_burden(user_id=user_id)
        if burden.items and burden.items[0].primary_value > 0.7:
            proposals.append(Proposal(
                emoji=REST_TEMPLATE["emoji"],
                title=REST_TEMPLATE["title"],
                description=REST_TEMPLATE["description"].format(
                    load=burden.items[0].primary_value,
                ),
                action_type="rest",
                payload={"cognitive_load": burden.items[0].primary_value},
                priority=3,
                generated_by="proposal_generator",
                insight_source="assess_current_burden",
            ))

        # 排序
        proposals.sort(key=lambda p: -p.priority)
        return proposals[:max_proposals]

    def generate_multi_option(
        self,
        report: DiagnosisReport,
    ) -> list[list[Proposal]]:
        """生成多选项（每组 2-3 个供用户选择）"""
        all_proposals = self.generate_from_diagnosis(report, max_proposals=9)

        # 分成三组
        groups = []
        for i in range(0, len(all_proposals), 3):
            group = all_proposals[i:i+3]
            if group:
                groups.append(group)
        return groups
