"""
学习者数字孪生引擎（MVP版本 - 内存存储）
管理学习者画像、知识状态、学习记录
后续可替换为数据库持久化
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timedelta
from typing import Any, Optional

from app.config import settings
from shared.constants import get_mastery_label
from shared.learner_sample_data import get_sample_questions, get_sample_content
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
        # 内存存储（MVP）: user_id -> LearnerProfile
        self._profiles: dict[str, LearnerProfile] = {}
        # 会话存储: session_id -> ConversationContext
        self._sessions: dict[str, dict[str, Any]] = {}
        # 学习记录: user_id -> list[dict]
        self._activity_log: dict[str, list[dict[str, Any]]] = {}
        # 学习计划: user_id -> StudyPlan
        self._study_plans: dict[str, StudyPlan] = {}
        # 练习题库（内存）: subject -> list[PracticeQuestion]
        self._question_bank: dict[str, list[PracticeQuestion]] = {}
        # 内容库（内存）: subject -> list[ContentItem]
        self._content_store: dict[str, list[ContentItem]] = {}
        # 掌握度判定使用 shared.constants.get_mastery_label

        # 初始化示例数据
        self._init_sample_data()

    def _init_sample_data(self) -> None:
        """初始化示例数据（MVP用）"""
        self._question_bank = get_sample_questions()
        self._content_store = get_sample_content()
        logger.info("示例数据初始化完成")

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
            from app.cognitive import get_repo
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
        """获取学习进度摘要"""
        profile = self.get_or_create_profile(user_id)
        activities = self._activity_log.get(user_id, [])

        # 计算统计
        total_questions = len(
            [a for a in activities if a.get("type") == "practice"]
        )
        correct_answers = len(
            [a for a in activities if a.get("type") == "practice" and a.get("is_correct")]
        )

        accuracy_rate = (
            correct_answers / total_questions if total_questions > 0 else 0.0
        )

        # 找出已掌握和困难的知识点（从 CognitiveNode 读取）
        mastered: list[str] = []
        struggling: list[str] = []
        try:
            from app.cognitive import get_repo
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

        # 生成建议
        recommendations: list[str] = []
        if struggling:
            recommendations.append(f"建议重点复习: {', '.join(struggling[:3])}")
        if accuracy_rate < 0.6:
            recommendations.append("正确率较低，建议降低难度巩固基础")
        elif accuracy_rate > 0.9:
            recommendations.append("掌握不错！可以尝试更高难度的挑战")

        return ProgressSummary(
            user_id=user_id,
            total_questions=total_questions,
            correct_answers=correct_answers,
            accuracy_rate=accuracy_rate,
            study_minutes=profile.total_study_minutes,
            mastered_skills=mastered,
            struggling_skills=struggling,
            recent_activity=activities[-10:],  # 最近10条活动
            recommendations=recommendations,
        )

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

    # ──────────────────────────────────────────────
    # 内部工具方法
    # ──────────────────────────────────────────────

    def _log_activity(self, user_id: str, activity: dict[str, Any]) -> None:
        """记录学习活动"""
        if user_id not in self._activity_log:
            self._activity_log[user_id] = []
        self._activity_log[user_id].append(activity)

        # 限制记录数量
        if len(self._activity_log[user_id]) > 1000:
            self._activity_log[user_id] = self._activity_log[user_id][-500:]


# ── 全局引擎实例 ──
learner_engine = LearnerModelEngine()
