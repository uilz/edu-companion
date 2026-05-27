"""
对话内联练习处理器
InlinePracticeHandler

在对话流中嵌入练习题，不跳转到独立页面。
支持：选择题/填空题的生成、作答、反馈、知识状态更新。
"""
from __future__ import annotations

import logging
import uuid
from typing import Optional

from app.schemas.conversation import TextBlock, ResponseBlock
from app.schemas.practice import (
    BloomLevel,
    KnowledgeState,
    Question,
    AnswerType,
)
from app.services.shared_ks import shared_ks
from app.services.llm_service import llm_service

logger = logging.getLogger(__name__)

# 内联练习状态（内存缓存，练习块生命周期内有效）
_inline_states: dict[str, dict] = {}


class InlinePracticeHandler:
    """
    内联练习：在对话消息中嵌入练习组件
    
    流程：
    1. create_inline_question → 生成题并返回 ResponseBlock(type="practice")
    2. 前端渲染为可交互的练习组件（选择/填空）
    3. handle_answer → 学生作答 → 判对错 → 返回对话回复
    4. 知识状态自动更新
    """

    def create_inline_question(
        self,
        user_id: str,
        skill_id: str = "",
        bloom_level: BloomLevel = BloomLevel.UNDERSTAND,
        difficulty: float = 0.5,
        count: int = 1,
        content_type: str = "choice",
    ) -> list[ResponseBlock]:
        """
        生成内联练习题，返回 ResponseBlock 列表
        
        每个 ResponseBlock 的 type="practice"，
        前端检测到后渲染为交互式练习组件。
        """
        from app.services.question_generator import get_question_generator

        generator = get_question_generator(llm_service)

        if not skill_id or skill_id == "general_practice":
            skill_id = "calculus_derivative"
            logger.info("使用默认知识点: calculus_derivative")

        subject = self._subject_from_skill(skill_id)
        if bloom_level is None:
            bloom_level = BloomLevel.UNDERSTAND

        questions = generator.generate(
            subject=subject,
            skill_id=skill_id,
            bloom_level=bloom_level,
            difficulty=difficulty,
            count=count,
            content_type=content_type,
        )

        blocks = []
        for i, q in enumerate(questions):
            block_id = str(uuid.uuid4())

            # 存储内联状态
            _inline_states[block_id] = {
                "question": q,
                "skill_id": skill_id,
                "user_id": user_id,
                "hints_used": 0,
            }

            # 取第一个提示
            hints = q.hints or []
            first_hint = hints[0] if hints else "再想想思路"

            block = ResponseBlock(
                type="practice",
                status="waiting_answer",
                content={
                    "question_id": q.question_id,
                    "block_id": block_id,
                    "stem": q.text,
                    "options": [
                        {
                            "letter": opt.letter,
                            "text": opt.text,
                        }
                        for opt in (q.options or [])
                    ],
                    "answer_type": q.answer_type.value,
                    "skill_id": skill_id,
                    "difficulty": difficulty,
                    "hint": first_hint,
                },
                order=i,
                metadata={
                    "skill_id": skill_id,
                    "question_id": q.question_id,
                },
            )
            blocks.append(block)

        logger.info(
            "生成内联练习: skill=%s bloom=%s diff=%.2f count=%d",
            skill_id, bloom_level.value, difficulty, count,
        )
        return blocks

    def handle_answer(
        self,
        block_id: str,
        student_answer: str,
        explanation_text: Optional[str] = None,
    ) -> dict:
        """处理学生对内联练习的回答"""
        state = _inline_states.get(block_id)
        if not state:
            return {
                "is_correct": False,
                "reply_text": "这道题已经过期了，要不要重新来一道？📝",
                "knowledge_update": {},
                "recommendation": None,
            }

        question: Question = state["question"]
        skill_id: str = state["skill_id"]
        user_id: str = state["user_id"]
        hints_used: int = state.get("hints_used", 0)

        is_correct = self._check_answer(question, student_answer)

        # 更新共享知识状态
        ks = shared_ks.update_from_practice(
            user_id=user_id,
            skill_id=skill_id,
            is_correct=is_correct,
            hint_level=hints_used,
        )

        # ── Phase D1+D2: CognitiveNode update + events + error_book ──
        try:
            # 1. CognitiveNode 更新
            from app.cognitive.events import submit_practice
            p_before = ks.p_known if ks else 0.5
            submit_practice(
                user_id=user_id,
                node_id=skill_id,
                success=is_correct,
                latency_ms=0,
            )
            p_after = ks.p_known if ks else 0.5
        except Exception as exc:
            logger.warning("inline_practice: CognitiveNode update failed: %s", exc)
            p_before = p_before if 'p_before' in dir() else 0.5
            p_after = p_after if 'p_after' in dir() else 0.5

        try:
            # 2. AnswerSubmitted 事件
            from app.application.di import container
            from shared.events import AnswerSubmitted, ErrorRecorded
            import asyncio

            bus = container.event_bus
            answer_evt = AnswerSubmitted(
                user_id=user_id,
                session_id="",
                question_id=question.question_id,
                skill_id=skill_id,
                is_correct=is_correct,
                answer=student_answer,
                correct_answer=question.correct_answer,
                time_spent=0.0,
                hints_used=hints_used,
                p_known_before=p_before,
                p_known_after=p_after,
            )
            loop = asyncio.get_event_loop()
            if loop.is_running():
                loop.create_task(bus.publish(answer_evt))
            else:
                loop.run_until_complete(bus.publish(answer_evt))
        except Exception as exc:
            logger.warning("inline_practice: AnswerSubmitted publish failed: %s", exc)

        try:
            # 3. ErrorRecorded 事件 + 错题本写入（答错时）
            if not is_correct:
                from app.application.di import container
                from shared.events import ErrorRecorded
                import asyncio

                bus = container.event_bus
                error_evt = ErrorRecorded(
                    user_id=user_id,
                    question_id=question.question_id,
                    skill_id=skill_id,
                    error_type="inline_practice",
                    user_answer=student_answer,
                    correct_answer=question.correct_answer,
                )
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    loop.create_task(bus.publish(error_evt))
                else:
                    loop.run_until_complete(bus.publish(error_evt))

                # 写入 error_book 表
                from app.db.database import get_db
                import uuid as _uuid
                db = get_db()
                db.execute(
                    "INSERT INTO error_book "
                    "(entry_id, user_id, question_id, skill_id, error_type, "
                    "user_answer, correct_answer, question_text) "
                    "VALUES (%s, %s, %s, %s, %s, %s, %s, %s) "
                    "ON CONFLICT DO NOTHING",
                    (
                        str(_uuid.uuid4()),
                        user_id,
                        question.question_id,
                        skill_id,
                        "inline_practice",
                        student_answer,
                        question.correct_answer,
                        question.text[:500],
                    ),
                )
        except Exception as exc:
            logger.warning("inline_practice: ErrorRecorded/error_book failed: %s", exc)

        # 生成对话回复
        if is_correct:
            reply = self._correct_reply(question)
        else:
            reply = self._incorrect_reply(question, student_answer)

        # 清理状态
        del _inline_states[block_id]

        return {
            "is_correct": is_correct,
            "reply_text": reply,
            "knowledge_update": {
                "skill_id": skill_id,
                "p_known": ks.p_known if ks else 0,
            },
            "recommendation": None,
        }

    def get_hint(self, block_id: str) -> dict:
        """获取下一级提示"""
        state = _inline_states.get(block_id)
        if not state:
            return {"hint_text": "这道题已经过期了", "level": 0}

        hints = state["question"].hints or []
        current_level = state.get("hints_used", 0)

        if current_level >= len(hints):
            return {
                "hint_text": "已经给了全部提示，试试看？",
                "level": current_level,
            }

        hint_text = hints[current_level]
        state["hints_used"] = current_level + 1

        return {
            "hint_text": f"💡 提示 ({current_level + 1}/{len(hints)})：{hint_text}",
            "level": current_level + 1,
        }

    def skip_question(self, block_id: str) -> dict:
        """跳过当前题"""
        state = _inline_states.pop(block_id, None)
        if not state:
            return {"reply_text": "这道题已经过期了"}

        question: Question = state["question"]
        return {
            "reply_text": (
                f"好的，这题的答案是 **{question.correct_answer}**。\n"
                f"{(question.explanation or '')[:200]}\n\n"
                f"要继续练习还是聊聊这个知识点？"
            ),
        }

    # ── Private helpers ──

    def _check_answer(self, question: Question, student_answer: str) -> bool:
        is_choice = (
            question.answer_type == AnswerType.CHOICE
        )
        if is_choice:
            return student_answer.strip().upper() == question.correct_answer.strip().upper()
        return student_answer.strip().lower() == question.correct_answer.strip().lower()

    def _correct_reply(self, question: Question) -> str:
        explanation = question.explanation or ""
        lines = ["✅ 正确！"]
        if explanation:
            short = explanation[:150]
            if len(explanation) > 150:
                short += "..."
            lines.append(short)
        lines.append("\n要继续下一题，还是聊聊这个知识点？")
        return "\n".join(lines)

    def _incorrect_reply(
        self, question: Question, student_answer: str,
    ) -> str:
        hints = question.hints or []
        hint_text = hints[0] if hints else "再想想思路"

        lines = [
            f"❌ 不对哦。正确答案是 **{question.correct_answer}**。",
            f"\n💡 提示：{hint_text}",
            "\n想让我详细讲解一下吗？还是再试一题？",
        ]
        return "\n".join(lines)

    def _subject_from_skill(self, skill_id: str) -> str:
        if "calculus" in skill_id or "math" in skill_id:
            return "数学"
        if "physics" in skill_id:
            return "物理"
        if "linear" in skill_id:
            return "线代"
        if "english" in skill_id:
            return "英语"
        return "通用"


# 全局实例
inline_practice = InlinePracticeHandler()
