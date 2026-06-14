"""
学习者数字孪生引擎（v7: PG 真存储 + 内存 cache）
管理学习者画像、连续天数、进度统计。
所有统计字段（practice_count/streak_days/total_sessions）从 PG 真实计算，不再使用内存 dict。
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timedelta
from typing import Any, Optional

from app.config import settings
from shared.constants import get_mastery_label
from app.schemas.learner import (
    ContentItem,
    LearnerProfile,
    PracticeQuestion,
    ProgressSummary,
    StudyPlan,
    StudyPlanItem,
)

logger = logging.getLogger(__name__)


class LearnerModelEngine:
    """
    学习者数字孪生引擎
    - 管理学习者画像（内存存储）
    - 跟踪知识状态
    - 生成学习计划
    - 记录学习活动
    """

    def __init__(self) -> None:
        # v7: 仅保留临时会话存储（用于 in-memory clean_expired_sessions）
        # 画像/统计字段全部从 PG 真实计算，不再维护内存 dict
        self._profiles: dict[str, LearnerProfile] = {}
        # 会话存储: session_id -> ConversationContext（临时缓存）
        self._sessions: dict[str, dict[str, Any]] = {}
        # 掌握度判定使用 shared.constants.get_mastery_label

    # ──────────────────────────────────────────────
    # 学习者画像管理
    # ──────────────────────────────────────────────

    def get_or_create_profile(self, user_id: str) -> LearnerProfile:
        """获取或创建学习者画像"""
        if user_id not in self._profiles:
            self._profiles[user_id] = LearnerProfile(user_id=user_id)
            self._activity_log[user_id] = []
            logger.info("为用户 %s 创建新画像", user_id)
        return self._profiles[user_id]

    def update_profile(
        self, user_id: str, updates: dict[str, Any]
    ) -> LearnerProfile:
        """更新学习者画像"""
        profile = self.get_or_create_profile(user_id)
        for key, value in updates.items():
            if hasattr(profile, key) and value is not None:
                setattr(profile, key, value)
        profile.updated_at = datetime.now()
        return profile

    # ──────────────────────────────────────────────
    # 知识状态管理
    # ──────────────────────────────────────────────

    def get_knowledge_state(
        self, user_id: str, skill_id: str
    ) -> dict:
        """获取用户在某个知识点的状态（从 CognitiveNode 真实读取）"""
        try:
            from app.domain.cognitive import get_repo
            node = get_repo().find_node_by_label(skill_id, user_id)
            if node:
                return {
                    "skill_id": skill_id,
                    "mastery": node.belief.proficiency_mean,
                    "precision": node.belief.proficiency_precision,
                    "total_attempts": node.practice_summary.total_attempts,
                    "correct_attempts": node.practice_summary.correct_attempts,
                    "trend": node.trend.direction,
                    "status": "active",
                }
        except Exception:
            logger.debug("CognitiveNode read failed, returning default", exc_info=True)
        return {"skill_id": skill_id, "mastery": 0.0, "status": "use_cognitive_node"}

    # ──────────────────────────────────────────────
    # 学习计划
    # ──────────────────────────────────────────────

    def generate_study_plan(self, user_id: str) -> StudyPlan:
        """
        根据学习者状态生成个性化学习计划

        策略：
        1. 找出需要练习的知识点
        2. 根据掌握程度分配时间
        3. 生成任务列表
        """
        profile = self.get_or_create_profile(user_id)

        # BKT knowledge_states removed — use CognitiveNode scheduling instead.
        recommendations: list[dict] = []

        # 生成计划项目
        items: list[StudyPlanItem] = []
        for i, rec in enumerate(recommendations):
            skill_id = str(rec["skill_id"])
            level = str(rec["level"])

            # 根据掌握程度估算时间
            if level == "初学":
                est_minutes = 45
                difficulty = 0.3
            elif level == "发展中":
                est_minutes = 30
                difficulty = 0.5
            else:
                est_minutes = 20
                difficulty = 0.7

            items.append(StudyPlanItem(
                task_id=f"plan_{user_id}_{i}",
                title=f"练习: {skill_id}",
                description=f"当前水平: {level}，目标: 掌握该知识点",
                subject=profile.subjects[0] if profile.subjects else "通用",
                skill_ids=[skill_id],
                estimated_minutes=est_minutes,
                difficulty=difficulty,
                priority=10 - i,  # 越靠前优先级越高
            ))

        plan = StudyPlan(
            user_id=user_id,
            items=items,
            week_number=datetime.now().isocalendar()[1],
        )

        self._study_plans[user_id] = plan
        logger.info("为用户 %s 生成学习计划，共 %d 项", user_id, len(items))
        return plan

    # ──────────────────────────────────────────────
    # 进度统计
    # ──────────────────────────────────────────────

    def get_progress_summary(self, user_id: str) -> ProgressSummary:
        """获取学习进度摘要（v7: 全部从 PG 真实读取）"""
        # ── 1. 答题统计：直接从 practice_attempts 聚合 ──
        total_questions = 0
        correct_answers = 0
        study_minutes = 0.0
        try:
            from app.infrastructure.db.database import get_db
            db = get_db()
            agg = db.fetchone(
                """SELECT COUNT(*) AS total,
                          SUM(CASE WHEN is_correct THEN 1 ELSE 0 END) AS correct,
                          COALESCE(SUM(time_spent_seconds), 0) AS total_seconds
                   FROM practice_attempts WHERE user_id = %s""",
                (user_id,),
            )
            if agg:
                total_questions = int(agg["total"] or 0)
                correct_answers = int(agg["correct"] or 0)
                study_minutes = round(int(agg["total_seconds"] or 0) / 60, 1)
        except Exception as e:
            logger.warning("Failed to read practice_attempts for %s: %s", user_id, e)

        accuracy_rate = (
            correct_answers / total_questions if total_questions > 0 else 0.0
        )

        # ── 2. 掌握/困难知识点：从 cognitive_nodes 读取（保持原行为） ──
        mastered: list[str] = []
        struggling: list[str] = []
        try:
            from app.domain.cognitive import get_repo
            nodes = get_repo().list_all_nodes(user_id)
            for node in nodes:
                if not node.belief or not node.practice_summary:
                    continue
                p = node.belief.proficiency_mean
                label = get_mastery_label(p, node.practice_summary.total_attempts)
                if label == "已掌握":
                    mastered.append(node.id)
                elif p < 0.4:
                    struggling.append(node.id)
        except Exception as e:
            logger.warning("Failed to read CognitiveNode mastery data: %s", e)

        # ── 3. recent_activity：从 practice_attempts 取最近 10 条 ──
        recent_activity: list[dict] = []
        try:
            from app.infrastructure.db.database import get_db
            db = get_db()
            rows = db.fetchall(
                """SELECT id, question_id, is_correct, time_spent_seconds, created_at
                   FROM practice_attempts WHERE user_id = %s
                   ORDER BY created_at DESC LIMIT 10""",
                (user_id,),
            ) or []
            for r in rows:
                recent_activity.append({
                    "type": "practice",
                    "id": r.get("id"),
                    "question_id": r.get("question_id"),
                    "is_correct": r.get("is_correct"),
                    "time_spent_seconds": r.get("time_spent_seconds"),
                    "created_at": str(r.get("created_at", "")),
                })
        except Exception as e:
            logger.warning("Failed to read recent activity for %s: %s", user_id, e)

        # ── 4. 建议生成 ──
        recommendations: list[str] = []
        if struggling:
            recommendations.append(f"建议重点复习: {', '.join(struggling[:3])}")
        if total_questions == 0:
            recommendations.append("还没有练习记录，开始你的第一次练习吧")
        elif accuracy_rate < 0.6:
            recommendations.append("正确率较低，建议降低难度巩固基础")
        elif accuracy_rate > 0.9:
            recommendations.append("掌握不错！可以尝试更高难度的挑战")

        return ProgressSummary(
            user_id=user_id,
            total_questions=total_questions,
            correct_answers=correct_answers,
            accuracy_rate=accuracy_rate,
            study_minutes=study_minutes,
            mastered_skills=mastered,
            struggling_skills=struggling,
            recent_activity=recent_activity,
            recommendations=recommendations,
        )

    def get_streak_days(self, user_id: str) -> int:
        """从 PG 真实计算连续学习天数（v7: 基于 practice_attempts.created_at）"""
        try:
            from app.infrastructure.db.database import get_db
            db = get_db()
            # 取出最近 365 天的练习日期去重
            rows = db.fetchall(
                """SELECT DISTINCT DATE(created_at) AS d
                   FROM practice_attempts
                   WHERE user_id = %s
                     AND created_at >= NOW() - INTERVAL '365 days'
                   ORDER BY d DESC""",
                (user_id,),
            ) or []
            if not rows:
                return 0
            from datetime import date, timedelta
            practice_dates = {r["d"] for r in rows if r.get("d")}
            # 从今天/昨天向前连续计数
            today = date.today()
            streak = 0
            cursor = today
            # 如果今天没练习，从昨天开始算
            if cursor not in practice_dates:
                cursor = cursor - timedelta(days=1)
            while cursor in practice_dates:
                streak += 1
                cursor = cursor - timedelta(days=1)
            return streak
        except Exception as e:
            logger.warning("Failed to compute streak for %s: %s", user_id, e)
            return 0

    def get_total_sessions(self, user_id: str) -> int:
        """从 PG 真实统计 session 数（v7: 包含已完成的 practice_sessions）"""
        try:
            from app.infrastructure.db.database import get_db
            db = get_db()
            row = db.fetchone(
                "SELECT COUNT(*) AS cnt FROM practice_sessions WHERE user_id = %s",
                (user_id,),
            )
            return int(row["cnt"]) if row else 0
        except Exception as e:
            logger.warning("Failed to count sessions for %s: %s", user_id, e)
            return 0

    # ──────────────────────────────────────────────
    # 会话管理
    # ──────────────────────────────────────────────

    def create_session(self, user_id: str, subject: Optional[str] = None) -> str:
        """创建新会话"""
        session_id = str(uuid.uuid4())
        self._sessions[session_id] = {
            "user_id": user_id,
            "subject": subject,
            "created_at": datetime.now(),
            "messages": [],
        }
        logger.info("创建会话: %s (用户: %s)", session_id, user_id)
        return session_id

    def clean_expired_sessions(self) -> int:
        """清理过期会话"""
        timeout = timedelta(minutes=settings.session_timeout_minutes)
        now = datetime.now()
        expired = [
            sid for sid, session in self._sessions.items()
            if now - session["created_at"] > timeout
        ]
        for sid in expired:
            del self._sessions[sid]
        return len(expired)


# ── 全局引擎实例 ──
learner_engine = LearnerModelEngine()
