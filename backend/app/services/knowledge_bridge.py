"""
KnowledgeBridge — 统一知识状态桥接服务

连接练习系统（BKT）和对话系统，维护 SharedKnowledgeState。

职责：
1. 监听练习完成事件 → 同步 BKT 到共享状态
2. 分析对话消息 → 提取知识证据
3. 生成对话 LLM 可用的知识上下文
4. 提供 API 可查询的统一状态视图
"""

from __future__ import annotations

import logging
from typing import Optional

from shared.constants import DEFAULT_USER_ID
from app.domain.learning.shared_knowledge import (
    EvidenceType,
    shared_knowledge,
)
from app.cognitive.storage import get_node, list_all_nodes, get_urgent_nodes
from app.cognitive.models import CognitiveNode

logger = logging.getLogger(__name__)


class KnowledgeBridge:
    """知识桥接服务"""

    def __init__(self):
        self.state = shared_knowledge

    # ── CognitiveNode context generation ──

    def get_knowledge_context(self, user_id: str = DEFAULT_USER_ID) -> str:
        """生成注入 LLM system prompt 的知识上下文

        优先从 CognitiveNode 读取，如果无数据则回退到 SharedKnowledgeState。
        """
        try:
            nodes = list_all_nodes(user_id)
            if not nodes:
                # fallback to legacy
                return self.state.to_context_string()

            # Filter to nodes that have practice data
            practiced = [
                n for n in nodes
                if n.practice_summary and n.practice_summary.total_attempts > 0
            ]

            if not practiced:
                return self.state.to_context_string()

            # Sort by proficiency
            practiced.sort(key=lambda n: n.belief.proficiency_mean)

            # Weak nodes (proficiency < 0.4)
            weak = [n for n in practiced if n.belief.proficiency_mean < 0.4]

            # Mastered nodes (proficiency >= 0.8)
            mastered = [n for n in practiced if n.belief.proficiency_mean >= 0.8]

            # Urgent nodes for review
            urgent = get_urgent_nodes(5, user_id)

            lines = ["【学生知识状态】"]

            if weak:
                lines.append("薄弱知识点：")
                for n in weak[:5]:
                    trend = n.trend.direction if n.trend else "stable"
                    emoji = "📉" if trend in ("descending", "volatile") else "⚠️"
                    lines.append(
                        f"  {emoji} {n.label or n.id}: "
                        f"掌握度={n.belief.proficiency_mean:.0%}, "
                        f"趋势={trend}, "
                        f"练习次数={n.practice_summary.total_attempts}"
                    )

            if mastered:
                lines.append("已掌握知识点：")
                for n in mastered[:5]:
                    lines.append(f"  ✅ {n.label or n.id}: 掌握度={n.belief.proficiency_mean:.0%}")

            if urgent:
                lines.append("待复习知识点：")
                for n in urgent[:3]:
                    lines.append(
                        f"  🔄 {n.label or n.id}: "
                        f"紧迫度={n.scheduling.urgency:.2f}"
                    )

            lines.append(f"共 {len(practiced)} 个知识点有练习数据")

            return "\n".join(lines)
        except Exception as e:
            logger.warning(f"get_knowledge_context CognitiveNode failed: {e}, falling back")
            return self.state.to_context_string()

    def get_skill_context(self, skill_ids: list[str], user_id: str = DEFAULT_USER_ID) -> str:
        """获取特定技能的知识上下文

        优先从 CognitiveNode 读取，回退到 SharedKnowledgeState。
        """
        try:
            lines = []
            for sid in skill_ids:
                node = get_node(sid, user_id)
                if node:
                    mastery = node.belief.proficiency_mean
                    status = "✅" if mastery >= 0.8 else "📖" if mastery >= 0.4 else "⚠️"
                    trend = node.trend.direction if node.trend else "stable"
                    attempts = node.practice_summary.total_attempts if node.practice_summary else 0
                    recent_rate = node.practice_summary.recent_success_rate_7d if node.practice_summary else 0.0
                    lines.append(
                        f"{status} {node.label or sid}: mastery={mastery:.0%} "
                        f"(α={node.belief.alpha:.1f}, β={node.belief.beta:.1f}, "
                        f"trend={trend}, n={attempts}, "
                        f"7d_rate={recent_rate:.0%})"
                    )
                else:
                    # fallback to SharedKnowledgeState
                    skill = self.state.get_skill(sid)
                    if skill:
                        s = "✅" if skill.is_mastered else "📖" if skill.is_learning else "⚠️"
                        lines.append(
                            f"{s} {sid}: mastery={skill.unified_mastery:.0%} "
                            f"(BKT={skill.bkt_p_known:.0%}, conv={skill.conversation_mastery_score:.0%}, "
                            f"n={skill.evidence_count})"
                        )
            return "\n".join(lines) if lines else ""
        except Exception as e:
            logger.warning(f"get_skill_context CognitiveNode failed: {e}, falling back")
            # Full fallback
            lines = []
            for sid in skill_ids:
                skill = self.state.get_skill(sid)
                if skill:
                    status = "✅" if skill.is_mastered else "📖" if skill.is_learning else "⚠️"
                    lines.append(
                        f"{status} {sid}: mastery={skill.unified_mastery:.0%} "
                        f"(BKT={skill.bkt_p_known:.0%}, conv={skill.conversation_mastery_score:.0%}, "
                        f"n={skill.evidence_count})"
                    )
            return "\n".join(lines) if lines else ""

    def get_cognitive_profile(self, user_id: str = DEFAULT_USER_ID) -> str:
        """返回 CognitiveNode 的格式化画像摘要，供 LLM system prompt 注入"""
        try:
            nodes = list_all_nodes(user_id)
            if not nodes:
                return ""

            practiced = [
                n for n in nodes
                if n.practice_summary and n.practice_summary.total_attempts > 0
            ]

            if not practiced:
                return ""

            total = len(practiced)
            avg_mastery = sum(n.belief.proficiency_mean for n in practiced) / total
            weak_count = sum(1 for n in practiced if n.belief.proficiency_mean < 0.4)
            mastered_count = sum(1 for n in practiced if n.belief.proficiency_mean >= 0.8)
            improving = sum(1 for n in practiced if n.trend and n.trend.direction in ("ascending", "improving"))
            declining = sum(1 for n in practiced if n.trend and n.trend.direction in ("descending", "volatile"))

            profile_lines = [
                "【认知画像】",
                f"  知识点总数: {total}",
                f"  平均掌握度: {avg_mastery:.0%}",
                f"  薄弱知识点: {weak_count}",
                f"  已掌握知识点: {mastered_count}",
                f"  进步中: {improving}",
                f"  下降中: {declining}",
            ]

            return "\n".join(profile_lines)
        except Exception as e:
            logger.warning(f"get_cognitive_profile failed: {e}")
            return ""

    # ── Practice → Shared State ──

    async def sync_from_practice_session(
        self,
        skills_tested: list[str],
        accuracy: float,
        correct_skills: list[str],
        struggling_skills: list[str],
    ):
        """
        从练习 session 同步知识状态
        
        Args:
            skills_tested: 本次练习涉及的技能
            accuracy: 总体正确率
            correct_skills: 答对了哪些技能
            struggling_skills: 薄弱技能
        """
        for skill_id in skills_tested:
            if skill_id in correct_skills:
                # 答对 → p_known +=
                current = self.state.get_skill(skill_id)
                old_mastery = current.unified_mastery if current else 0.0
                new_mastery = old_mastery + (1.0 - old_mastery) * 0.15 * accuracy
                self.state.update_from_practice(
                    skill_id, new_mastery, confidence=0.6, attempt_count=1,
                )
            elif skill_id in struggling_skills:
                # 薄弱 → p_known -=
                current = self.state.get_skill(skill_id)
                old_mastery = current.unified_mastery if current else 0.5
                new_mastery = old_mastery * 0.85
                self.state.update_from_practice(
                    skill_id, new_mastery, confidence=0.4, attempt_count=1,
                )

        logger.info(
            f"KnowledgeBridge: synced {len(skills_tested)} skills from practice "
            f"(correct={len(correct_skills)}, weak={len(struggling_skills)})"
        )

    # ── Conversation → Shared State ──

    async def analyze_user_message(
        self,
        user_text: str,
        skill_ids: Optional[list[str]] = None,
        branch_id: str = "",
    ) -> list[dict]:
        """
        分析用户对话消息，提取知识证据。
        
        用 LLM 判断消息中体现的知识状态。
        返回提取到的证据列表。
        """
        if not skill_ids:
            return []

        evidence_list = []
        
        # 快速关键词分析（零 LLM 成本）
        quick_evidence = self._quick_evidence_detect(user_text)
        
        for skill_id in skill_ids:
            ev_type, confidence = quick_evidence
            if ev_type:
                self.state.add_conversation_evidence(
                    skill_id=skill_id,
                    evidence_type=ev_type,
                    confidence=confidence,
                    source_text=user_text[:200],
                    branch_id=branch_id,
                )
                evidence_list.append({
                    "skill_id": skill_id,
                    "type": ev_type.value,
                    "confidence": confidence,
                })

        return evidence_list

    def _quick_evidence_detect(self, text: str) -> tuple[Optional[EvidenceType], float]:
        """快速关键词检测对话证据（零 token）"""
        text_lower = text.lower()

        # 正确解释信号
        correct_signals = [
            "我懂了", "明白了", "原来如此", "理解了", "原来是",
            "就是说", "所以", "意味着", "等于说", "换言之",
            "i see", "got it", "makes sense"
        ]
        for sig in correct_signals:
            if sig in text_lower:
                return EvidenceType.CORRECT_EXPLANATION, 0.6

        # 主动深入信号
        deeper_signals = ["然后呢", "再深入", "详细讲讲", "更深层", "背后原理"]
        for sig in deeper_signals:
            if sig in text_lower:
                return EvidenceType.REQUESTED_DEEPER, 0.3

        # 困惑信号
        confusion_signals = ["不理解", "搞不懂", "什么意思", "为什么这样", "没懂"]
        for sig in confusion_signals:
            if sig in text_lower:
                return EvidenceType.ASKED_CLARIFICATION, 0.2

        # 错误理解信号
        wrong_signals = ["我以为", "原来是错的", "搞错了", "想错了"]
        for sig in wrong_signals:
            if sig in text_lower:
                return EvidenceType.SELF_CORRECTED, 0.5

        return None, 0.0

    # ── LLM 深度证据分析（备选） ──

    async def deep_evidence_analysis(
        self,
        user_text: str,
        assistant_reply: str,
        skill_ids: list[str],
        branch_id: str = "",
    ) -> list[dict]:
        """
        用 LLM 深度分析一轮对话中的知识证据。
        在 assistant 回复后调用，分析整个问答回合。
        """
        # 简化实现：基于文本长度和模式判断
        evidence_list = []

        # 如果用户消息 + 回复都较长且积极 → 可能是正确解释
        if len(user_text) > 30 and len(assistant_reply) > 50:
            positive_indicators = ["对", "没错", "正确", "很好", "正是", "good", "yes"]
            if any(ind in assistant_reply.lower() for ind in positive_indicators):
                for skill_id in skill_ids[:2]:
                    self.state.add_conversation_evidence(
                        skill_id=skill_id,
                        evidence_type=EvidenceType.CORRECT_EXPLANATION,
                        confidence=0.5,
                        source_text=user_text[:200],
                        branch_id=branch_id,
                    )
                    evidence_list.append({"skill_id": skill_id, "type": "correct_explanation"})

        return evidence_list

    # ── 上下文生成 ──

    # ── 状态查询 ──

    def get_all_skills_summary(self) -> dict:
        """获取所有技能的摘要"""
        return self.state.to_dict()

    def get_skill_detail(self, skill_id: str) -> Optional[dict]:
        """获取单个技能详情"""
        skill = self.state.get_skill(skill_id)
        return skill.to_dict() if skill else None

    def get_weak_skills(self, limit: int = 5) -> list[str]:
        """获取薄弱技能列表（用于针对性推荐）"""
        return self.state.get_all_weak()[:limit]

    def get_mastered_skills(self) -> list[str]:
        """获取已掌握技能列表"""
        return self.state.get_all_mastered()


# ── 全局实例 ──

knowledge_bridge = KnowledgeBridge()
