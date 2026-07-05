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

from app.schemas.practice import PracticeSession

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
            subject_filter: 可选的主题过滤（仅用于回复文案，session 无 subject 字段）

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

        if not recent_sessions:
            if subject_filter:
                return (
                    f"你在{subject_filter}上还没有做过练习哦。"
                    f"要不要现在来几道？📝"
                )
            return f"过去{days}天还没有做过练习，要不要现在开始？📝"

        # 汇总统计（替代旧的 s.question_ids）
        total_questions = sum(s.total_count or 0 for s in recent_sessions)
        total_correct = sum(s.correct_count or 0 for s in recent_sessions)
        accuracy = total_correct / total_questions if total_questions > 0 else 0

        # 从 DB 查询各 session 的知识点级表现（替代旧的 s.attempts / a.skill_id）
        from app.infrastructure.db.database import get_db
        db = get_db()

        session_ids = [s.id for s in recent_sessions if s.id]
        skill_performance: dict[str, list[int]] = {}  # node_id → [total, correct]
        if session_ids:
            placeholders = ", ".join("%s" for _ in session_ids)
            rows = db.fetchall(
                f"""SELECT pa.is_correct, pa.cognitive_node_ids
                    FROM practice_attempts pa
                    WHERE pa.session_id IN ({placeholders})""",
                tuple(session_ids),
            )

            for row in rows:
                is_correct = row.get("is_correct", False)
                node_ids = row.get("cognitive_node_ids") or []
                if isinstance(node_ids, (list, tuple)):
                    pass
                elif isinstance(node_ids, str):
                    import json
                    try:
                        node_ids = json.loads(node_ids)
                    except (json.JSONDecodeError, TypeError):
                        node_ids = []
                else:
                    node_ids = []

                for node_id in node_ids:
                    if node_id not in skill_performance:
                        skill_performance[node_id] = [0, 0]
                    skill_performance[node_id][0] += 1
                    if is_correct:
                        skill_performance[node_id][1] += 1

        weak_skills: list[tuple[str, float]] = []
        strong_skills: list[tuple[str, float]] = []
        for node_id, (total, correct) in skill_performance.items():
            rate = correct / total if total > 0 else 0
            if total >= 2 and rate < 0.5:
                weak_skills.append((node_id, rate))
            elif total >= 3 and rate > 0.85:
                strong_skills.append((node_id, rate))

        # 按正确率排序
        weak_skills.sort(key=lambda x: x[1])
        strong_skills.sort(key=lambda x: -x[1])

        # 构建回复
        lines: list[str] = []
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
