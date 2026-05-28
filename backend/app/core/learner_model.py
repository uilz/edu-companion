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
from app.core.knowledge_trace import bkt_engine
from app.schemas.learner import (
    ContentItem,
    KnowledgeState,
    LearnerProfile,
    PracticeQuestion,
    PracticeResult,
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
        # BKT 引擎
        self.bkt = bkt_engine

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

    def record_practice(
        self,
        user_id: str,
        skill_id: str,
        is_correct: bool,
        time_spent: float = 0.0,
    ) -> KnowledgeState:
        """
        记录一次练习结果并更新知识状态

        参数:
            user_id: 用户ID
            skill_id: 知识点ID
            is_correct: 是否正确
            time_spent: 花费时间（秒）
        """
        profile = self.get_or_create_profile(user_id)

        # 记录活动
        self._log_activity(user_id, {
            "type": "practice",
            "skill_id": skill_id,
            "is_correct": is_correct,
            "time_spent": time_spent,
            "p_known_after": 0.0,
            "timestamp": datetime.now().isoformat(),
        })

        logger.info(
            "练习记录: user=%s skill=%s correct=%s",
            user_id, skill_id, is_correct,
        )

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

    def get_study_plan(self, user_id: str) -> Optional[StudyPlan]:
        """获取用户的学习计划"""
        return self._study_plans.get(user_id)

    # ──────────────────────────────────────────────
    # 练习题管理
    # ──────────────────────────────────────────────

    def get_questions(
        self,
        subject: Optional[str] = None,
        skill_id: Optional[str] = None,
        difficulty: Optional[str] = None,
        limit: int = 5,
    ) -> list[PracticeQuestion]:
        """获取练习题"""
        all_questions: list[PracticeQuestion] = []

        if subject and subject in self._question_bank:
            all_questions = self._question_bank[subject]
        else:
            for questions in self._question_bank.values():
                all_questions.extend(questions)

        # 筛选
        if skill_id:
            all_questions = [q for q in all_questions if q.skill_id == skill_id]
        if difficulty:
            all_questions = [q for q in all_questions if q.difficulty.value == difficulty]

        return all_questions[:limit]

    def submit_answer(
        self,
        user_id: str,
        question_id: str,
        answer: str,
        time_spent: float = 0.0,
    ) -> Optional[PracticeResult]:
        """提交练习答案"""
        # 查找题目
        question = None
        for questions in self._question_bank.values():
            for q in questions:
                if q.question_id == question_id:
                    question = q
                    break
            if question:
                break

        if not question:
            logger.warning("题目未找到: %s", question_id)
            return None

        is_correct = answer.strip() == question.correct_answer.strip()

        # 更新知识状态
        state = self.record_practice(
            user_id, question.skill_id, is_correct, time_spent
        )

        return PracticeResult(
            question_id=question_id,
            user_answer=answer,
            is_correct=is_correct,
            time_spent_seconds=time_spent,
            knowledge_update={
                "skill_id": question.skill_id,
                "p_known_after": state.p_known,
                "mastery_level": self.bkt.get_mastery_level(state),
            },
        )

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

        # 找出已掌握和困难的知识点
        mastered: list[str] = []
        struggling: list[str] = []
        for skill_id, state in profile.knowledge_states.items():
            if self.bkt.get_mastery_level(state) == "已掌握":
                mastered.append(skill_id)
            elif state.p_known < 0.4:
                struggling.append(skill_id)

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
    # 内容搜索
    # ──────────────────────────────────────────────

    def search_content(
        self,
        query: str,
        subject: Optional[str] = None,
        content_type: Optional[str] = None,
        limit: int = 10,
    ) -> list[ContentItem]:
        """搜索学习内容"""
        results: list[ContentItem] = []

        all_content: list[ContentItem] = []
        if subject and subject in self._content_store:
            all_content = self._content_store[subject]
        else:
            for items in self._content_store.values():
                all_content.extend(items)

        # 简单的关键词匹配（MVP）
        query_lower = query.lower()
        for item in all_content:
            score = 0.0
            # 标题匹配
            if query_lower in item.title.lower():
                score += 0.5
            # 描述匹配
            if query_lower in item.description.lower():
                score += 0.3
            # 标签匹配
            for tag in item.tags:
                if query_lower in tag.lower():
                    score += 0.2

            if score > 0:
                item_copy = item.model_copy()
                item_copy.relevance_score = score
                results.append(item_copy)

        # 按相关性排序
        results.sort(key=lambda x: x.relevance_score, reverse=True)

        # 如果没有匹配结果，返回该科目的所有内容
        if not results and subject and subject in self._content_store:
            results = self._content_store[subject][:limit]

        return results[:limit]

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

    def get_session(self, session_id: str) -> Optional[dict[str, Any]]:
        """获取会话信息"""
        return self._sessions.get(session_id)

    def add_message_to_session(
        self, session_id: str, role: str, content: str
    ) -> None:
        """向会话添加消息"""
        session = self._sessions.get(session_id)
        if session:
            session["messages"].append({
                "role": role,
                "content": content,
                "timestamp": datetime.now().isoformat(),
            })
            # 限制历史消息数量
            max_messages = settings.max_history_messages
            if len(session["messages"]) > max_messages:
                session["messages"] = session["messages"][-max_messages:]

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
