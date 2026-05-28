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
from app.schemas.learner import (
    ContentItem,
    KnowledgeState,
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
        # 示例练习题
        sample_questions = [
            PracticeQuestion(
                question_id="math_001",
                subject="数学",
                skill_id="algebra_linear",
                difficulty="easy",
                question_text="求解方程：2x + 5 = 13",
                options=["x=3", "x=4", "x=5", "x=6"],
                correct_answer="x=4",
                explanation="2x + 5 = 13 → 2x = 8 → x = 4",
                hints=["先将5移到等号右边", "然后两边同时除以2"],
            ),
            PracticeQuestion(
                question_id="math_002",
                subject="数学",
                skill_id="algebra_linear",
                difficulty="medium",
                question_text="求解方程组：x + y = 10, x - y = 4",
                options=["x=7, y=3", "x=6, y=4", "x=8, y=2", "x=5, y=5"],
                correct_answer="x=7, y=3",
                explanation="将两式相加得 2x = 14, 所以 x = 7, y = 3",
                hints=["可以把两个方程相加", "消去y变量"],
            ),
            PracticeQuestion(
                question_id="math_003",
                subject="数学",
                skill_id="geometry_area",
                difficulty="easy",
                question_text="一个长方形的长为8cm，宽为5cm，求面积",
                options=["40 cm²", "26 cm²", "13 cm²", "45 cm²"],
                correct_answer="40 cm²",
                explanation="面积 = 长 × 宽 = 8 × 5 = 40 cm²",
                hints=["长方形面积公式是 长×宽"],
            ),
            PracticeQuestion(
                question_id="chinese_001",
                subject="语文",
                skill_id="reading_comprehension",
                difficulty="medium",
                question_text="下列哪个成语的使用是正确的？",
                options=[
                    "他的演讲真是画龙点睛",
                    "这件事真是雪中送炭",
                    "他的建议画蛇添足",
                    "今天的天气秋高气爽",
                ],
                correct_answer="他的建议画蛇添足",
                explanation="画蛇添足比喻做多余的事，反而弄巧成拙，适合形容多余的建议",
                hints=[
                    "画龙点睛指在关键处加精辟之笔",
                    "雪中送炭指在困难时给予帮助",
                    "秋高气爽形容秋天天气",
                ],
            ),
            PracticeQuestion(
                question_id="english_001",
                subject="英语",
                skill_id="grammar_tense",
                difficulty="easy",
                question_text='选择正确的时态：She ___ (go) to school every day.',
                options=["go", "goes", "going", "went"],
                correct_answer="goes",
                explanation="第三人称单数（she）用 goes",
                hints=["注意主语是第三人称单数", "一般现在时的第三人称单数要加s"],
            ),
        ]

        self._question_bank["数学"] = [q for q in sample_questions if q.subject == "数学"]
        self._question_bank["语文"] = [q for q in sample_questions if q.subject == "语文"]
        self._question_bank["英语"] = [q for q in sample_questions if q.subject == "英语"]

        # 示例内容库
        sample_content = [
            ContentItem(
                content_id="content_001",
                title="线性方程组入门教程",
                subject="数学",
                content_type="article",
                description="从零开始学习如何解线性方程组",
                difficulty=0.4,
                tags=["代数", "方程组", "入门"],
            ),
            ContentItem(
                content_id="content_002",
                title="面积计算公式大全",
                subject="数学",
                content_type="video",
                description="各种图形面积计算方法的视频讲解",
                url="https://example.com/area-video",
                difficulty=0.3,
                tags=["几何", "面积", "公式"],
            ),
            ContentItem(
                content_id="content_003",
                title="成语辨析专项练习",
                subject="语文",
                content_type="exercise",
                description="常见易混淆成语的辨析练习",
                difficulty=0.5,
                tags=["成语", "辨析", "练习"],
            ),
            ContentItem(
                content_id="content_004",
                title="英语时态总结",
                subject="英语",
                content_type="article",
                description="英语12种时态的完整总结与例句",
                difficulty=0.5,
                tags=["语法", "时态", "总结"],
            ),
        ]

        self._content_store["数学"] = [c for c in sample_content if c.subject == "数学"]
        self._content_store["语文"] = [c for c in sample_content if c.subject == "语文"]
        self._content_store["英语"] = [c for c in sample_content if c.subject == "英语"]

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
    ) -> KnowledgeState:
        """获取用户在某个知识点的状态"""
        profile = self.get_or_create_profile(user_id)
        return profile.get_knowledge_state(skill_id)

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
            from app.cognitive.storage import list_all_nodes
            nodes = list_all_nodes(user_id)
            for node in nodes:
                if not node.belief or not node.practice_summary:
                    continue
                p = node.belief.proficiency_mean
                label = get_mastery_label(p, node.practice_summary.total_attempts)
                if label == "已掌握":
                    mastered.append(node.id)
                elif p < 0.4:
                    struggling.append(node.id)
        except Exception:
            pass

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
