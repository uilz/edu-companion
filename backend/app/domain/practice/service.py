"""
练习系统领域服务 — PracticeService Protocol 实现

设计:
- 纯业务逻辑，不 import 具体基础设施
- 通过 Repository 接口访问 DB
- 通过 EventBus 发布领域事件
- 不依赖 presentation 层

注意: submit_answer 的实际执行路径是 api/practice.py → cognitive/events.submit_practice()。
本模块的 submit_answer 发布 AnswerSubmitted 事件供下游消费。
"""
from __future__ import annotations
from shared.constants import DEFAULT_USER_ID

import logging
from typing import TYPE_CHECKING
from uuid import uuid4

from infra.resilience import with_timeout
from infra.tracing import span
from shared.events import (
    AnswerSubmitted,
    ErrorRecorded,
    SessionCompleted,
)

if TYPE_CHECKING:
    from shared.protocols import (
        QuestionRepository,
        SessionRepository,
        ErrorBookRepository,
    )
    from infra.event_bus import EventBus

logger = logging.getLogger("domain.practice")


class PracticeServiceImpl:
    """练习系统实现 — 精简版（BKT 已迁移至 CognitiveNode）"""

    def __init__(
        self,
        question_repo: QuestionRepository,
        session_repo: SessionRepository,
        error_repo: ErrorBookRepository,
        event_bus: EventBus,
    ):
        self._questions = question_repo
        self._sessions = session_repo
        self._errors = error_repo
        self._bus = event_bus

    # ═══════════════════════════════════════════════════════
    # 核心方法: submit_answer
    # ═══════════════════════════════════════════════════════

    @with_timeout(5.0)
    async def submit_answer(
        self,
        session_id: str,
        question_id: str,
        answer: str,
        time_spent: float = 0.0,
        hints_used: int = 0,
    ) -> dict:
        """
        提交答案 — 发布领域事件供下游消费。

        注意: 知识状态更新由 api/practice.py → cognitive/events.submit_practice() 处理。
        本方法只负责判对错 + 发布事件。
        """
        async with span("submit_answer"):
            # 1. 获取题目
            question = await self._questions.find_by_id(question_id)
            if not question:
                raise ValueError(f"Question not found: {question_id}")

            # 2. 判对错
            is_correct = answer.strip().upper() == question["correct_answer"].strip().upper()

            # 3. 同步返回反馈
            feedback = {
                "is_correct": is_correct,
                "correct_answer": question["correct_answer"],
                "explanation": question.get("explanation", ""),
            }

            # 4. 发布领域事件（fire-and-forget）
            await self._bus.publish(AnswerSubmitted(
                user_id=DEFAULT_USER_ID,
                session_id=session_id,
                question_id=question_id,
                skill_id=question["skill_id"],
                is_correct=is_correct,
                answer=answer,
                correct_answer=question["correct_answer"],
                time_spent=time_spent,
                hints_used=hints_used,
            ))

            # 答错 → 错题事件
            if not is_correct:
                await self._bus.publish(ErrorRecorded(
                    user_id=DEFAULT_USER_ID,
                    question_id=question_id,
                    skill_id=question["skill_id"],
                    error_type="careless",
                    user_answer=answer,
                    correct_answer=question["correct_answer"],
                ))

            return feedback

    # ═══════════════════════════════════════════════════════
    # 其他方法
    # ═══════════════════════════════════════════════════════

    async def generate_questions(
        self, subject: str, topic: str, level: str, count: int
    ) -> list:
        """从题库查询题目（按学科/难度筛选）"""
        try:
            results = []
            all_qs = await self._questions.find_by_skill(topic, count * 3)
            for q in all_qs:
                if len(results) >= count:
                    break
                q_level = q.get("difficulty", "").lower()
                if level and q_level and q_level != level.lower():
                    continue
                if subject and q.get("subject", "").lower() != subject.lower():
                    continue
                results.append(q)
            return results[:count]
        except Exception as e:
            logger.warning("generate_questions failed: %s", e)
            return []

    async def create_session(
        self, user_id: str, question_ids: list[str], mode: str = "adaptive"
    ) -> dict:
        session_id = await self._sessions.create(user_id, question_ids)
        return {"session_id": session_id, "question_ids": question_ids, "mode": mode}

    async def get_errors(self, user_id: str, resolved=None, limit=20) -> dict:
        entries = await self._errors.find_unresolved(user_id, limit)
        return {"entries": entries, "total": len(entries)}

    async def get_stats(self, user_id: str, time_range: str = "week") -> dict:
        """从 attempts 表聚合练习统计"""
        from datetime import datetime, timedelta
        from app.db.database import get_db

        try:
            db = get_db()
            now = datetime.now()
            days = {"week": 7, "month": 30, "all": 365}.get(time_range, 7)
            cutoff = (now - timedelta(days=days)).isoformat()
            prev_cutoff = (now - timedelta(days=days * 2)).isoformat()

            rows = db.fetchall(
                "SELECT * FROM attempts WHERE user_id = %s AND submitted_at >= %s",
                (user_id, cutoff))
            total = len(rows)
            correct = sum(1 for r in rows if r.get("is_correct"))

            prev_rows = db.fetchall(
                "SELECT * FROM attempts WHERE user_id = %s "
                "AND submitted_at >= %s AND submitted_at < %s",
                (user_id, prev_cutoff, cutoff))
            prev_total = len(prev_rows)
            prev_correct = sum(1 for r in prev_rows if r.get("is_correct"))

            daily = {}
            for r in rows:
                day = _ds(r.get("submitted_at"))[:10]
                daily.setdefault(day, {"total": 0, "correct": 0})
                daily[day]["total"] += 1
                if r.get("is_correct"):
                    daily[day]["correct"] += 1

            return {
                "overview": {
                    "total_questions": total,
                    "correct_answers": correct,
                    "accuracy": round(correct / total, 3) if total > 0 else 0.0,
                    "prev_week": {
                        "total_questions": prev_total,
                        "correct_answers": prev_correct,
                        "accuracy": round(prev_correct / prev_total, 3) if prev_total > 0 else 0.0,
                    },
                },
                "daily_trend": [
                    {"date": d, **s}
                    for d, s in sorted(daily.items())
                ],
            }
        except Exception as e:
            logger.warning("get_stats aggregation failed: %s", e)
            return {"overview": {}}

    async def get_behavior_report(self, user_id: str, time_range: str = "week") -> dict:
        """调用 analytics service 生成行为分析报告"""
        from datetime import datetime, timedelta
        from app.db.database import get_db
        from app.services.analytics.behavior_analyzer import behavior_analyzer

        try:
            db = get_db()
            now = datetime.now()
            days = {"week": 7, "month": 30, "all": 365}.get(time_range, 7)
            cutoff = (now - timedelta(days=days)).isoformat()

            rows = db.fetchall(
                "SELECT * FROM attempts WHERE user_id = %s AND submitted_at >= %s",
                (user_id, cutoff))
            sess_rows = db.fetchall(
                "SELECT * FROM practice_sessions WHERE user_id = %s AND started_at >= %s",
                (user_id, cutoff))

            total_sessions = len(sess_rows)
            total_minutes = sum(r.get("estimated_minutes", 0) for r in sess_rows)

            daily_trend = {}
            for r in rows:
                day = str(r.get("submitted_at", ""))[:10]
                daily_trend.setdefault(day, {"questions": 0, "correct": 0})
                daily_trend[day]["questions"] += 1
                if r.get("is_correct"):
                    daily_trend[day]["correct"] += 1

            data = {
                "daily_trend": [
                    {"date": d, **s} for d, s in sorted(daily_trend.items())
                ],
                "total_sessions": total_sessions,
                "total_minutes": total_minutes,
            }

            report = behavior_analyzer.analyze(**data)
            return {
                "behavior": {
                    "current_streak": getattr(report, "current_streak", 0),
                    "longest_streak": getattr(report, "longest_streak", 0),
                    "best_study_hours": getattr(report, "best_study_hours", []),
                    "regularity_score": getattr(report, "regularity_score", 0.0),
                    "recommendations": getattr(report, "recommendations", []),
                },
                "total_sessions": total_sessions,
                "total_minutes": total_minutes,
            }
        except Exception as e:
            logger.warning("get_behavior_report failed: %s", e)
            return {}


def _ds(v) -> str:
    """Safely convert value to string for date slicing."""
    return str(v) if v else ""
