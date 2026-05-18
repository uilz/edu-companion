"""
对话中的"练习回顾"
PracticeRecallInConversation

当学生在对话中问"我导数掌握得怎么样？"或"最近练习情况"时，
生成基于实际练习数据的自然语言回复。
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Optional

from app.schemas.practice import PracticeSession, AttemptRecord

logger = logging.getLogger(__name__)


class PracticeRecallInConversation:
    """
    在对话中回答关于练习表现的问题
    
    触发关键词：
    - "掌握得怎么样|学得怎么样|练得怎么样"
    - "薄弱|弱点|薄弱点"
    - "练习情况|做题情况|正确率"
    - "复习建议|学习建议"
    """

    RECALL_KEYWORDS = [
        r"掌握得怎么样|学得怎么样|练得怎么样",
        r"薄弱|弱点|薄弱点|哪里差",
        r"练习情况|做题情况|正确率",
        r"复习建议|学习建议|怎么复习",
        r"学了什么|练了什么",
    ]

    def is_recall_query(self, text: str) -> bool:
        """判断用户消息是否是练习回顾查询"""
        import re
        text_lower = text.lower()
        for pattern in self.RECALL_KEYWORDS:
            if re.search(pattern, text_lower):
                return True
        return False

    def generate_recall(
        self,
        sessions: list[PracticeSession],
        days: int = 7,
        subject_filter: Optional[str] = None,
    ) -> str:
        """
        生成练习回顾自然语言回复
        
        参数:
            sessions: 最近的练习session列表
            days: 时间范围（天数）
            subject_filter: 可选的主题过滤
        
        返回:
            可直接发送给用户的自然语言回复
        """
        now = datetime.now()
        cutoff = now - timedelta(days=days)

        # 过滤时间范围
        recent_sessions = [
            s for s in sessions
            if s.started_at and s.started_at >= cutoff
        ]

        if subject_filter:
            recent_sessions = [
                s for s in recent_sessions
                if subject_filter.lower() in (
                    (s.subject or "").lower()
                )
            ]

        if not recent_sessions:
            if subject_filter:
                return (
                    f"你在{subject_filter}上还没有做过练习哦。"
                    f"要不要现在来几道？📝"
                )
            return f"过去{days}天还没有做过练习，要不要现在开始？📝"

        # 汇总统计
        total_questions = sum(len(s.question_ids or []) for s in recent_sessions)
        total_correct = sum(s.correct_count or 0 for s in recent_sessions)
        accuracy = total_correct / total_questions if total_questions > 0 else 0

        # 找薄弱和擅长
        skill_performance: dict[str, tuple[int, int]] = {}
        for s in recent_sessions:
            for a in (s.attempts or []):
                if not hasattr(a, "skill_id"):
                    continue
                sid = a.skill_id or "未知"
                if sid not in skill_performance:
                    skill_performance[sid] = (0, 0)
                total, correct = skill_performance[sid]
                skill_performance[sid] = (total + 1, correct + (1 if a.is_correct else 0))

        weak_skills = []
        strong_skills = []
        for sid, (total, correct) in skill_performance.items():
            rate = correct / total if total > 0 else 0
            if total >= 2 and rate < 0.5:
                weak_skills.append((sid, rate))
            elif total >= 3 and rate > 0.85:
                strong_skills.append((sid, rate))

        # 构建回复
        lines = []
        time_desc = f"过去{days}天" if days > 1 else "今天"

        if subject_filter:
            lines.append(f"📊 {time_desc}你在{subject_filter}的练习情况：")
        else:
            lines.append(f"📊 {time_desc}的练习情况：")

        lines.append(
            f"共 {total_questions} 题，正确 {total_correct} 题，"
            f"正确率 {accuracy:.0%}"
        )

        # 练习频率
        active_days = len(set(
            s.started_at.date() for s in recent_sessions
            if s.started_at
        ))
        if active_days >= 5:
            lines.append(f"练习 {active_days} 天，很勤奋！🔥")
        elif active_days >= 3:
            lines.append(f"练习 {active_days} 天，保持得不错 💪")
        else:
            lines.append(f"练习 {active_days} 天，可以多练练 ✨")

        # 薄弱点
        if weak_skills:
            weak_str = "、".join(
                f"{s}({r:.0%})" for s, r in weak_skills[:3]
            )
            lines.append(f"\n🔴 需要加强的：{weak_str}")

        # 擅长点
        if strong_skills:
            strong_str = "、".join(
                f"{s}({r:.0%})" for s, r in strong_skills[:3]
            )
            lines.append(f"🟢 掌握扎实的：{strong_str}")

        # 学习建议
        if weak_skills:
            lines.append(
                f"\n💡 建议：{'、'.join(s for s, _ in weak_skills[:2])}"
                f" 需要重点复习。要针对这些薄弱点来几道题吗？"
            )
        elif accuracy >= 0.9:
            lines.append("\n🌟 表现太棒了！要不要挑战一些更难的题？")

        return "\n".join(lines)


# 全局实例
practice_recall = PracticeRecallInConversation()
