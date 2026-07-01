"""
CognitiveNode 统一查询模块

替代 knowledge_bridge.py + shared_knowledge.py 的所有读取操作。
所有知识状态查询走 CognitiveNode 唯一数据源。
"""

from __future__ import annotations

import logging
from typing import Optional

from app.domain.cognitive import get_repo
from app.domain.cognitive.models import CognitiveNode

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════
# 上下文生成（注入 LLM system prompt）
# ═══════════════════════════════════════════


def get_knowledge_context(user_id: str) -> str:
    """生成注入 LLM system prompt 的知识上下文"""
    try:
        nodes = get_repo().list_all_nodes(user_id)
        practiced = [
            n for n in nodes
            if n.practice_summary and n.practice_summary.total_attempts > 0
        ]
        if not practiced:
            return ""

        practiced.sort(key=lambda n: n.belief.proficiency_mean)
        weak = [n for n in practiced if n.belief.proficiency_mean < 0.4]
        mastered = [n for n in practiced if n.belief.proficiency_mean >= 0.8]
        urgent = get_repo().get_urgent_nodes(user_id, 5)

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
                lines.append(f"  🔄 {n.label or n.id}: 紧迫度={n.scheduling.urgency:.2f}")
        lines.append(f"共 {len(practiced)} 个知识点有练习数据")
        return "\n".join(lines)
    except Exception as e:
        logger.warning(f"get_knowledge_context failed: {e}")
        return ""


def get_skill_context(skill_ids: list[str], user_id: str) -> str:
    """获取特定技能的知识上下文"""
    try:
        lines = []
        for sid in skill_ids:
            node = get_repo().get_node(sid, user_id)
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
        return "\n".join(lines) if lines else ""
    except Exception as e:
        logger.warning(f"get_skill_context failed: {e}")
        return ""


def get_cognitive_profile(user_id: str) -> str:
    """返回 CognitiveNode 的格式化画像摘要"""
    try:
        nodes = get_repo().list_all_nodes(user_id)
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

        return "\n".join([
            "【认知画像】",
            f"  知识点总数: {total}",
            f"  平均掌握度: {avg_mastery:.0%}",
            f"  薄弱知识点: {weak_count}",
            f"  已掌握知识点: {mastered_count}",
            f"  进步中: {improving}",
            f"  下降中: {declining}",
        ])
    except Exception as e:
        logger.warning(f"get_cognitive_profile failed: {e}")
        return ""


def get_event_queue_length(user_id: str) -> int:
    """获取未处理事件队列长度"""
    try:
        from app.infrastructure.db.database import get_db
        db = get_db()
        row = db.fetchone(
            "SELECT COUNT(*) as cnt FROM events WHERE user_id = %s AND status = 'pending'",
            (user_id,),
        )
        return row["cnt"] if row else 0
    except Exception:
        return -1


def get_all_skills_summary(user_id: str) -> dict:
    """获取所有技能的摘要"""
    try:
        nodes = get_repo().list_all_nodes(user_id)
        practiced = [
            n for n in nodes
            if n.practice_summary and n.practice_summary.total_attempts > 0
        ]
        return {
            "total_skills": len(practiced),
            "skills": {
                n.id: {
                    "label": n.label,
                    "mastery": n.belief.proficiency_mean,
                    "attempts": n.practice_summary.total_attempts,
                    "trend": n.trend.direction if n.trend else "stable",
                }
                for n in practiced
            },
        }
    except Exception as e:
        logger.warning(f"get_all_skills_summary failed: {e}")
        return {"total_skills": 0, "skills": {}}


def get_skill_detail(skill_id: str, user_id: str) -> Optional[dict]:
    """获取单个技能详情"""
    try:
        node = get_repo().get_node(skill_id, user_id)
        if not node:
            return None
        return {
            "id": node.id,
            "label": node.label,
            "mastery": node.belief.proficiency_mean,
            "alpha": node.belief.alpha,
            "beta": node.belief.beta,
            "attempts": node.practice_summary.total_attempts if node.practice_summary else 0,
            "success_rate": node.practice_summary.recent_success_rate_7d if node.practice_summary else 0.0,
            "trend": node.trend.direction if node.trend else "stable",
            "urgency": node.scheduling.urgency if node.scheduling else 0.0,
        }
    except Exception as e:
        logger.warning(f"get_skill_detail failed: {e}")
        return None


def get_weak_skills(user_id: str, limit: int = 5) -> list[str]:
    """获取薄弱技能列表"""
    try:
        nodes = get_repo().list_all_nodes(user_id)
        practiced = [
            n for n in nodes
            if n.practice_summary and n.practice_summary.total_attempts > 0
        ]
        weak = sorted(practiced, key=lambda n: n.belief.proficiency_mean)
        return [n.id for n in weak[:limit] if n.belief.proficiency_mean < 0.5]
    except Exception as e:
        logger.warning(f"get_weak_skills failed: {e}")
        return []


def get_mastered_skills(user_id: str) -> list[str]:
    """获取已掌握技能列表"""
    try:
        nodes = get_repo().list_all_nodes(user_id)
        return [
            n.id for n in nodes
            if n.practice_summary
            and n.practice_summary.total_attempts > 0
            and n.belief.proficiency_mean >= 0.8
        ]
    except Exception as e:
        logger.warning(f"get_mastered_skills failed: {e}")
        return []


# ═══════════════════════════════════════════
# 对话证据分析（零 LLM 成本）
# ═══════════════════════════════════════════


def detect_dialogue_evidence(text: str) -> tuple[Optional[str], float]:
    """快速关键词检测对话证据（零 token）

    Returns:
        (evidence_type, confidence) 或 (None, 0.0)
    """
    text_lower = text.lower()

    # 正确解释信号
    for sig in ["我懂了", "明白了", "原来如此", "理解了", "原来是",
                "就是说", "所以", "意味着", "等于说", "换言之",
                "i see", "got it", "makes sense"]:
        if sig in text_lower:
            return "correct_explanation", 0.6

    # 主动深入信号
    for sig in ["然后呢", "再深入", "详细讲讲", "更深层", "背后原理"]:
        if sig in text_lower:
            return "requested_deeper", 0.3

    # 困惑信号
    for sig in ["不理解", "搞不懂", "什么意思", "为什么这样", "没懂"]:
        if sig in text_lower:
            return "asked_clarification", 0.2

    # 自我纠错信号
    for sig in ["我以为", "原来是错的", "搞错了", "想错了"]:
        if sig in text_lower:
            return "self_corrected", 0.5

    return None, 0.0


async def analyze_dialogue_evidence(
    user_text: str,
    assistant_reply: str,
    skill_ids: list[str],
) -> list[dict]:
    """分析一轮对话中的知识证据（零 LLM 成本）

    替代 knowledge_bridge.deep_evidence_analysis。
    证据通过 cognitive/events.py 写入 CognitiveNode。
    """
    evidence_list = []

    # 快速检测用户消息
    ev_type, confidence = detect_dialogue_evidence(user_text)
    if ev_type:
        for skill_id in skill_ids[:2]:
            evidence_list.append({
                "skill_id": skill_id,
                "type": ev_type,
                "confidence": confidence,
            })

    # 检测助手回复中的积极反馈
    if len(user_text) > 30 and len(assistant_reply) > 50:
        positive = ["对", "没错", "正确", "很好", "正是", "good", "yes"]
        if any(ind in assistant_reply.lower() for ind in positive):
            for skill_id in skill_ids[:2]:
                evidence_list.append({
                    "skill_id": skill_id,
                    "type": "correct_explanation",
                    "confidence": 0.5,
                })

    return evidence_list
