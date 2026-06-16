"""
练习系统领域服务 — PracticeService Protocol 实现

设计:
- 统一入口，委托到各子模块
- 通过 Repository 接口访问 DB
- 通过 EventBus 发布领域事件
- 不依赖 presentation 层
"""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Optional
from uuid import uuid4


if TYPE_CHECKING:
    from shared.protocols import (
        QuestionRepository,
        SessionRepository,
        ErrorBookRepository,
    )
    from app.infrastructure.event_bus import EventBus

logger = logging.getLogger("domain.practice")


class PracticeServiceImpl:
    """练习系统实现 — 统一入口，委托到子模块

    所有公共方法对应 PracticeService Protocol。
    内部委托到 app.services.practice 下的子模块。
    """

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
    # 核心路径
    # ═══════════════════════════════════════════════════════

    async def generate_questions(
        self, subject: str, user_id: str, topic: str = "", level: str = "medium",
        count: int = 5,
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
        self, user_id: str, question_ids: list[str], mode: str = "adaptive",
        sources: dict | None = None,
    ) -> dict:
        session_id = await self._sessions.create(user_id, question_ids)
        return {"session_id": session_id, "question_ids": question_ids, "mode": mode, "sources": sources}

    async def submit_answer(
        self,
        session_id: str,
        question_id: str,
        answer: str,
        user_id: str,
        time_spent: float = 0.0,
        hints_used: int = 0,
        explanation_text: str = "",
    ) -> dict:
        """提交答案 — 判对错 + 发布领域事件"""
        from shared.events import AnswerSubmitted, ErrorRecorded

        question = await self._questions.find_by_id(question_id)
        if not question:
            raise ValueError(f"Question not found: {question_id}")

        # 从 options 推导正确答案, fallback 到 answer 字段
        options = question.get("options") or []
        if isinstance(options, list) and any(o.get("is_correct") for o in options):
            correct_answers = [o["letter"] for o in options if o.get("is_correct")]
        else:
            correct_answers = question.get("answer") or []
            if isinstance(correct_answers, str):
                correct_answers = [correct_answers]

        user_answers = [answer] if isinstance(answer, str) else (answer or [])
        user_set = set(str(a).strip().upper() for a in user_answers)
        correct_set = set(str(a).strip().upper() for a in correct_answers)
        is_correct = user_set == correct_set

        feedback = {
            "is_correct": is_correct,
            "correct_answer": correct_answers,
            "explanation": question.get("explanation", ""),
        }

        await self._bus.publish(AnswerSubmitted(
            user_id=user_id,
            session_id=session_id,
            question_id=question_id,
            skill_id=question.get("skill_id", ""),
            is_correct=is_correct,
            answer=answer,
            correct_answer=correct_answers,
            time_spent=time_spent,
            hints_used=hints_used,
        ))

        if not is_correct:
            await self._bus.publish(ErrorRecorded(
                user_id=user_id,
                question_id=question_id,
                skill_id=question.get("skill_id", ""),
                error_type="careless",
                user_answer=answer,
                correct_answer=correct_answers,
            ))

        # 发布 PracticeSubmitted 事件 → 触发认知节点信念更新
        try:
            from app.services.common.event_service import event_service
            event_service.emit_practice_submitted(
                user_id=user_id,
                atom_node_ids=question.get("cognitive_node_ids", []),
                correctness=1.0 if is_correct else 0.0,
                latency_ms=time_spent * 1000,
            )
        except Exception:
            logger.warning("emit_practice_submitted failed", exc_info=True)

        return feedback

    async def get_hint(self, question_id: str, hint_level: int = 1) -> dict:
        return self.get_hint_for_question(question_id, hint_level - 1)

    async def get_knowledge_state(self, user_id: str, skill_id: str):
        from shared.knowledge_trace import get_cognitive_state
        return get_cognitive_state(user_id, skill_id)

    async def get_errors(self, user_id: str, resolved=None, limit=50) -> list[dict]:
        result = self.get_error_book(user_id, page_size=limit)
        return result.get("items", [])

    async def get_summary(self, branch_id: str) -> dict:
        return {"branch_id": branch_id, "practice_summary": {}}

    # ═══════════════════════════════════════════════════════
    # 认知更新
    # ═══════════════════════════════════════════════════════

    def update_cognitive_after_practice(
        self, user_id: str, skill_id: str, is_correct: bool, latency_ms: int = 0,
    ) -> dict:
        from app.services.practice.practice_service import update_cognitive_after_practice
        return update_cognitive_after_practice(user_id, skill_id, is_correct, latency_ms)

    # ═══════════════════════════════════════════════════════
    # 答案校验
    # ═══════════════════════════════════════════════════════

    def check_answer(self, user_answer: str, correct_answer: str) -> bool:
        from app.services.practice.practice_service import check_answer
        return check_answer(user_answer, correct_answer)

    def build_reply_text(self, is_correct: bool, correct_label: str, explanation: str) -> str:
        from app.services.practice.practice_service import build_reply_text
        return build_reply_text(is_correct, correct_label, explanation)

    # ═══════════════════════════════════════════════════════
    # 提示
    # ═══════════════════════════════════════════════════════

    def get_hint_for_question(self, question_id: str, current_level: int) -> dict | None:
        from app.services.practice.practice_service import get_hint_for_question
        return get_hint_for_question(question_id, current_level)

    def get_inline_hint(self, block_id: str, user_id: str) -> dict | None:
        from app.services.practice.practice_service import get_inline_hint
        return get_inline_hint(block_id, user_id)

    # ═══════════════════════════════════════════════════════
    # 错题本（基于 practice_attempts 聚合）
    # ═══════════════════════════════════════════════════════

    def get_error_book(
        self, user_id: str, bank_id: str | None = None,
        cognitive_node_id: str | None = None, min_wrongs: int = 1,
        sort_by: str = "wrongs_desc", page: int = 1, page_size: int = 20,
    ) -> dict:
        from app.services.practice.practice_error_book import get_error_book
        return get_error_book(user_id, bank_id, cognitive_node_id, min_wrongs, sort_by, page, page_size)

    def get_error_session_stats(self, user_id: str) -> dict:
        from app.services.practice.practice_error_book import get_error_session_stats
        return get_error_session_stats(user_id)

    def review_error_question(
        self, question_id: str, user_id: str,
        is_correct: bool = False, time_spent: int = 0,
    ) -> dict:
        from app.services.practice.practice_error_book import review_error_question
        return review_error_question(question_id, user_id, is_correct, time_spent)

    def clear_mastered_errors(self, user_id: str) -> dict:
        from app.services.practice.practice_error_book import clear_mastered_errors
        return clear_mastered_errors(user_id)

    def get_error_materials(self, question_id: str, user_id: str, limit: int = 3) -> list[dict]:
        from app.services.practice.practice_error_book import get_error_materials
        return get_error_materials(question_id, user_id, limit)

    # ═══════════════════════════════════════════════════════
    # 会话管理
    # ═══════════════════════════════════════════════════════

    def list_practice_sessions(self, user_id: str, limit: int = 20) -> dict:
        from app.services.practice.practice_service import list_practice_sessions
        return list_practice_sessions(user_id, limit)

    def complete_practice_session(self, session_id: str) -> dict | None:
        from app.services.practice.practice_service import complete_practice_session
        return complete_practice_session(session_id)

    def record_attempt(
        self, user_id: str, session_id: str, question_id: str,
        answer: str, is_correct: bool, time_spent_seconds: float, hints_used: int,
    ) -> None:
        from app.services.practice.practice_service import record_attempt
        return record_attempt(user_id, session_id, question_id, answer, is_correct, time_spent_seconds, hints_used)

    # ═══════════════════════════════════════════════════════
    # 统计
    # ═══════════════════════════════════════════════════════

    def compute_practice_stats(self, user_id: str, time_range: str = "week") -> dict:
        from app.services.practice.practice_service import compute_practice_stats
        return compute_practice_stats(user_id, time_range)

    def compute_behavior_report_data(self, user_id: str, time_range: str = "week") -> dict:
        from app.services.practice.practice_service import compute_behavior_report_data
        return compute_behavior_report_data(user_id, time_range)

    async def get_stats(self, user_id: str, time_range: str = "week") -> dict:
        """从 attempts 表聚合练习统计（异步版，委托给 services 层）"""
        from app.services.practice.practice_service import get_stats_db
        return await get_stats_db(user_id, time_range)

    async def get_behavior_report(self, user_id: str, time_range: str = "week") -> dict:
        """学习行为分析报告（异步版，委托给 services 层）"""
        from app.services.practice.practice_service import get_behavior_report_db
        return await get_behavior_report_db(user_id, time_range)

    # ═══════════════════════════════════════════════════════
    # 自适应选题
    # ═══════════════════════════════════════════════════════

    def adaptive_select(
        self, bank_id: str, user_id: str, count: int = 10,
        mode: str = "adaptive", exclude_ids: list[str] | None = None,
        target_difficulty: int | None = None,
        cognitive_node_ids: list[str] | None = None,
        bloom_distribution: dict[str, int] | None = None,
        sources: dict | None = None,
    ) -> list[dict]:
        from app.services.practice.practice_adaptive import adaptive_select_v2
        return adaptive_select_v2(
            bank_id, user_id, count, mode, exclude_ids,
            cognitive_node_ids=cognitive_node_ids,
        )

    # ═══════════════════════════════════════════════════════
    # AI 出题
    # ═══════════════════════════════════════════════════════

    async def generate_and_save(
        self, bank_id: str, user_id: str,
        subject: str = "", skill: str = "", bloom: str = "understand",
        difficulty: int = 3, count: int = 5, question_type: str = "choice",
        material_context: str | None = None,
        reference_mode: str | None = None,
    ) -> list[dict]:
        from app.services.practice.practice_question_gen import generate_and_save
        diff_float = difficulty / 5.0 if difficulty > 1 else float(difficulty)
        return await generate_and_save(
            bank_id=bank_id, user_id=user_id, subject=subject,
            skill_id=skill, bloom_level=bloom,
            difficulty=diff_float, count=count, content_type=question_type,
            material_context=material_context,
            reference_mode=reference_mode,
        )

    # ═══════════════════════════════════════════════════════
    # 题库管理
    # ═══════════════════════════════════════════════════════

    def resolve_bank_for_conversation(self, partition_id: str, topic: str = "") -> str:
        from app.services.practice.practice_question_bank import resolve_bank_for_conversation
        return resolve_bank_for_conversation(partition_id, topic)

    def resolve_bank_for_node(self, node_id: str) -> str:
        from app.services.practice.practice_question_bank import resolve_bank_for_node
        return resolve_bank_for_node(node_id)

    # ═══════════════════════════════════════════════════════
    # 复习调度
    # ═══════════════════════════════════════════════════════

    def get_due_reviews(self, user_id: str, limit: int = 10) -> list[dict]:
        from app.services.practice.practice_scheduler import get_due_questions
        return get_due_questions(user_id, limit)

    # ═══════════════════════════════════════════════════════
    # 考试模式
    # ═══════════════════════════════════════════════════════

    def create_exam(
        self, user_id: str, bank_id: str = "",
        count: int = 20, duration_minutes: int = 60,
        config: dict | None = None,
        cognitive_node_ids: list[str] | None = None,
    ) -> dict:
        from app.services.practice.practice_exam import create_exam
        return create_exam(user_id, bank_id, count, duration_minutes, config, cognitive_node_ids)

    # ═══════════════════════════════════════════════════════
    # 秘书联动
    # ═══════════════════════════════════════════════════════

    def check_and_generate_proposals(
        self, user_id: str, session_id: str, skill_id: str = "",
        is_correct: bool = True, proficiency: float = 0.5,
    ) -> list[dict]:
        from app.services.practice.practice_secretary_integration import check_and_generate_proposals
        count = check_and_generate_proposals(user_id, session_id)
        return [{"generated_count": count}]

    # ═══════════════════════════════════════════════════════
    # 练习→对话集成
    # ═══════════════════════════════════════════════════════

    async def integrate_practice_to_branch(
        self, user_id: str, session, partition_id: str, branch_id: str,
    ) -> dict | None:
        from app.services.practice.practice_integrator import integrate_practice_to_branch
        result = await integrate_practice_to_branch(user_id, session, partition_id, branch_id)
        if result is None:
            return None
        return {"node_id": result.id} if hasattr(result, "id") else {"status": "ok"}
