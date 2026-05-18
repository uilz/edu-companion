"""
练习系统领域服务 — PracticeService Protocol 实现

设计:
- 纯业务逻辑，不 import 具体基础设施
- 通过 Repository 接口访问 DB
- 通过 EventBus 发布领域事件
- 不依赖 presentation 层
"""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING
from uuid import uuid4

from infra.resilience import with_timeout
from infra.tracing import span
from shared.events import (
    AnswerSubmitted,
    ErrorRecorded,
    KnowledgeStateUpdated,
    SessionCompleted,
)

if TYPE_CHECKING:
    from shared.protocols import (
        KnowledgeStateRepository,
        QuestionRepository,
        SessionRepository,
        ErrorBookRepository,
    )
    from infra.event_bus import EventBus

logger = logging.getLogger("domain.practice")


class BKTEngine:
    """BKT 知识追踪引擎（纯算法，无外部依赖）"""

    @staticmethod
    def update(p_known: float, p_learn: float, p_guess: float,
               p_slip: float, is_correct: bool) -> float:
        """BKT 单步更新 → 返回新的 p_known"""
        if is_correct:
            p_correct = p_known * (1 - p_slip) + (1 - p_known) * p_learn
            if p_correct < 1e-10:
                return p_known
            return p_known * (1 - p_slip) / p_correct
        else:
            p_incorrect = p_known * p_slip + (1 - p_known) * (1 - p_guess)
            if p_incorrect < 1e-10:
                return p_known
            return p_known * p_slip / p_incorrect

    @staticmethod
    def get_mastery(p_known: float) -> str:
        if p_known < 0.3:
            return "初学"
        elif p_known < 0.6:
            return "发展中"
        elif p_known < 0.95:
            return "接近掌握"
        else:
            return "已掌握"


class PracticeServiceImpl:
    """练习系统实现"""

    def __init__(
        self,
        question_repo: QuestionRepository,
        session_repo: SessionRepository,
        ks_repo: KnowledgeStateRepository,
        error_repo: ErrorBookRepository,
        event_bus: EventBus,
    ):
        self._questions = question_repo
        self._sessions = session_repo
        self._ks = ks_repo
        self._errors = error_repo
        self._bus = event_bus
        self._bkt = BKTEngine()

    # ═══════════════════════════════════════════════════════
    # 核心方法: submit_answer — 改造为事件驱动
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
        提交答案 — 核心联动点

        同步路径（必须返回给用户）:
          1. 找到题目
          2. BKT 更新知识状态
          3. 保存知识状态到 DB
          4. 返回反馈

        异步路径（事件驱动）:
          4. 发布 AnswerSubmitted → analytics + habits + knowledge 并行处理
          5. 如果答错 → 发布 ErrorRecorded → error_book + media
          6. 如果掌握度升级 → 发布 KnowledgeStateUpdated → planning + conversation
        """
        async with span("submit_answer"):

            # 1. 获取题目
            question = await self._questions.find_by_id(question_id)
            if not question:
                raise ValueError(f"Question not found: {question_id}")

            # 2. 判对错
            is_correct = answer.strip().upper() == question["correct_answer"].strip().upper()

            # 3. BKT 更新知识状态
            old_state = await self._ks.load("default_user", question["skill_id"])
            old_p = old_state["p_known"] if old_state else 0.3
            old_mastery = self._bkt.get_mastery(old_p)

            new_p = self._bkt.update(
                p_known=old_p,
                p_learn=old_state.get("p_learned", 0.3) if old_state else 0.3,
                p_guess=old_state.get("p_guess", 0.25) if old_state else 0.25,
                p_slip=old_state.get("p_slip", 0.1) if old_state else 0.1,
                is_correct=is_correct,
            )
            new_mastery = self._bkt.get_mastery(new_p)

            # 4. 保存知识状态（同步，需确认持久化）
            await self._ks.save("default_user", question["skill_id"], {
                "p_known": new_p,
                "p_learned": old_state.get("p_learned", 0.3) if old_state else 0.3,
                "p_guess": old_state.get("p_guess", 0.25) if old_state else 0.25,
                "p_slip": old_state.get("p_slip", 0.1) if old_state else 0.1,
                "mastery_level": new_mastery,
            })

            # 5. 同步返回反馈
            feedback = {
                "is_correct": is_correct,
                "correct_answer": question["correct_answer"],
                "explanation": question.get("explanation", ""),
                "p_known_after": new_p,
                "mastery_level": new_mastery,
            }

            # 6. 发布领域事件（fire-and-forget）
            await self._bus.publish(AnswerSubmitted(
                user_id="default_user",
                session_id=session_id,
                question_id=question_id,
                skill_id=question["skill_id"],
                is_correct=is_correct,
                answer=answer,
                correct_answer=question["correct_answer"],
                time_spent=time_spent,
                hints_used=hints_used,
                p_known_before=old_p,
                p_known_after=new_p,
            ))

            # 答错 → 错题事件
            if not is_correct:
                await self._bus.publish(ErrorRecorded(
                    user_id="default_user",
                    question_id=question_id,
                    skill_id=question["skill_id"],
                    error_type="careless",
                    user_answer=answer,
                    correct_answer=question["correct_answer"],
                ))

            # 掌握度升级 → 知识状态事件
            if old_mastery != new_mastery:
                await self._bus.publish(KnowledgeStateUpdated(
                    user_id="default_user",
                    skill_id=question["skill_id"],
                    old_mastery=old_mastery,
                    new_mastery=new_mastery,
                    p_known_before=old_p,
                    p_known_after=new_p,
                    attempt_count=old_state.get("attempt_count", 0) + 1 if old_state else 1,
                ))

            return feedback

    # ═══════════════════════════════════════════════════════
    # 其他方法（骨架）
    # ═══════════════════════════════════════════════════════

    async def generate_questions(
        self, subject: str, topic: str, level: str, count: int
    ) -> list:
        """LLM 生成题目"""
        # TODO: 调用 LLM via question_generator
        return []

    async def create_session(
        self, user_id: str, question_ids: list[str], mode: str = "adaptive"
    ) -> dict:
        session_id = await self._sessions.create(user_id, question_ids)
        return {"session_id": session_id, "question_ids": question_ids, "mode": mode}

    async def get_knowledge_state(self, user_id: str, skill_id: str) -> dict | None:
        return await self._ks.load(user_id, skill_id)

    async def get_errors(self, user_id: str, resolved=None, limit=20) -> dict:
        entries = await self._errors.find_unresolved(user_id, limit)
        return {"entries": entries, "total": len(entries)}

    async def get_stats(self, user_id: str, time_range: str = "week") -> dict:
        # TODO: 从 attempts 表聚合
        return {"overview": {}}

    async def get_behavior_report(self, user_id: str, time_range: str = "week") -> dict:
        # TODO: 调用 analytics service
        return {}
