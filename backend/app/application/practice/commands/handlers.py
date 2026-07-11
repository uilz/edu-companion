"""练习命令处理器。

每个处理器负责一个命令的完整执行流程：加载聚合根、执行业务逻辑、持久化、发布事件。
"""

from __future__ import annotations

import logging
from typing import Any

from app.application.practice.commands.base import CommandHandler
from app.application.practice.commands.commands import (
    CompleteSessionCommand,
    SkipQuestionCommand,
    StartSessionCommand,
    SubmitAnswerCommand,
)
from app.application.practice.uow import PracticeUnitOfWork
from app.domain.practice.aggregate import PracticeAggregateRoot, PracticeDomainError
from app.services.practice import session_repository as session_repo
from app.services.practice.session_engine import check_answer, classify_error
from shared.events import AnswerSubmitted, ErrorRecorded, SessionCompleted

logger = logging.getLogger(__name__)


def _get_uow(context: dict | None) -> PracticeUnitOfWork:
    """从 context 获取 UoW，否则新建一个。"""
    if context and "uow" in context:
        return context["uow"]
    return PracticeUnitOfWork()


def _get_event_bus(context: dict | None):
    """从 context 获取事件总线，否则使用全局容器。"""
    if context and "event_bus" in context:
        return context["event_bus"]
    from app.application.di import container
    return container.event_bus


def _build_aggregate_from_session_row(session_row) -> PracticeAggregateRoot:
    """从 practice_sessions 行构建聚合根（用于首次加载）。

    session_row 可以是 dict 或 PracticeSession Pydantic 对象。
    """
    if hasattr(session_row, "model_dump"):
        data = session_row.model_dump()
    else:
        data = dict(session_row)
    return PracticeAggregateRoot(
        session_id=data["id"],
        user_id=data["user_id"],
        bank_id=data.get("bank_id", "") or "",
        session_type=data.get("session_type", "practice"),
        mode=data.get("mode", "adaptive"),
        status=data.get("status", "created"),
        question_ids=[],
        answered_question_ids=[],
        skipped_question_ids=[],
        correct_count=data.get("correct_count") or 0,
        wrong_count=data.get("wrong_count") or 0,
        score=(data.get("score") or 0.0) / 100.0
        if data.get("score") is not None
        else 0.0,
        version=0,
    )


def _load_or_create_aggregate(
    uow: PracticeUnitOfWork, session_id: str, user_id: str
) -> PracticeAggregateRoot:
    """加载聚合根；如不存在则从 practice_sessions 行重建。"""
    aggregate = uow.aggregates.get(session_id)
    if aggregate is not None:
        return aggregate

    session_row = session_repo.get_session(uow.sql_db, session_id, user_id)
    if session_row is None:
        raise PracticeDomainError(f"Session {session_id} not found")
    aggregate = _build_aggregate_from_session_row(session_row)
    return aggregate


def _get_question(db, question_id: str) -> dict | None:
    """从 questions 表获取题目。"""
    row = db.fetchone(
        "SELECT * FROM questions WHERE id = %s AND deleted_at IS NULL",
        (question_id,),
    )
    return dict(row) if row else None


def _safe_json(value, default):
    """安全解析 JSON 字段。"""
    import json
    if value is None:
        return default
    if isinstance(value, (list, dict)):
        return value
    if isinstance(value, str):
        try:
            return json.loads(value)
        except Exception:
            return default
    return default


def _get_cognitive_node_ids(question: dict) -> list[str]:
    """获取题目关联的认知节点 ID 列表。"""
    raw = question.get("cognitive_node_ids") if question else None
    result = _safe_json(raw, [])
    if isinstance(result, list):
        return [str(x) for x in result]
    return []


def _metacognition_feedback(confidence_before: int | None, is_correct: bool) -> str:
    """根据自信度和正确性返回元认知反馈文案。"""
    if confidence_before is None:
        return ""
    if confidence_before >= 3:
        return "你确实掌握了，自信是对的" if is_correct else "⚠️ 元认知偏差：你以为掌握了但其实没有。建议重新学习推导过程。"
    if is_correct:
        return "💡 谦逊的正确：你比你以为的更懂。试着给别人讲一遍确认。"
    return "还有提升空间，继续努力"


class StartSessionCommandHandler(CommandHandler):
    """开始练习会话命令处理器。"""

    command_type = StartSessionCommand

    async def handle(self, command: StartSessionCommand, context: dict | None = None) -> dict:
        with _get_uow(context) as uow:
            aggregate = _load_or_create_aggregate(uow, command.session_id, command.user_id)
            sq_rows = session_repo.get_session_questions(uow.sql_db, command.session_id)
            question_ids = [r["question_id"] for r in sq_rows]

            event = aggregate.start(question_ids)
            uow.aggregates.save(
                aggregate,
                command_id=command.command_id,
                command_type="StartSessionCommand",
                payload={"question_ids": question_ids},
            )
            session_repo.update_session_status(uow.sql_db, command.session_id, "started")
            uow.commit()

        # TODO: 如需 SessionStarted 事件，在 shared/events.py 中新增后再发布。
        # 当前无订阅者，聚合根已记录 SessionStarted 命令记录。

        return {
            "session_id": command.session_id,
            "status": aggregate.status,
            "question_ids": question_ids,
            "version": aggregate.version,
            "event": event,
        }


class SubmitAnswerCommandHandler(CommandHandler):
    """提交答题命令处理器。"""

    command_type = SubmitAnswerCommand

    async def handle(self, command: SubmitAnswerCommand, context: dict | None = None) -> dict:
        with _get_uow(context) as uow:
            aggregate = _load_or_create_aggregate(uow, command.session_id, command.user_id)

            question = _get_question(uow.sql_db, command.question_id)
            if question is None:
                raise PracticeDomainError(f"Question {command.question_id} not found")

            correct_answer = _safe_json(question.get("answer"), [])
            explanation = question.get("explanation", "") or question.get("analysis", "")
            difficulty = question.get("difficulty")
            if isinstance(difficulty, (int, float)):
                difficulty = float(difficulty)

            user_answer_list = command.user_answer if isinstance(command.user_answer, list) else [command.user_answer]
            user_answer_str = _answer_to_str(user_answer_list)
            correct_answer_str = _answer_to_str(correct_answer)
            is_correct = check_answer(
                user_answer_list,
                correct_answer,
                question.get("question_type", "single"),
            )

            event = aggregate.submit_answer(
                command.question_id,
                is_correct,
                response_time_ms=command.response_time_ms,
            )

            # 错因分析
            error_pattern = ""
            error_analysis: dict[str, Any] = {}
            if not is_correct:
                error_pattern = classify_error(question, user_answer_list) or ""
                try:
                    from app.services.analytics.error_attribution import classify_llm
                    detail = classify_llm(
                        question_data=question,
                        user_answer=user_answer_list,
                        correct_answer=correct_answer,
                    )
                    if detail:
                        error_analysis = {"llm_detail": detail}
                except Exception:
                    pass

            # 写入答题记录
            attempt_id = session_repo.insert_attempt(
                uow.sql_db,
                command.session_id,
                command.question_id,
                command.user_id,
                is_correct,
                user_answer_list,
                command.response_time_ms // 1000,
                command.hints_used,
                error_pattern,
                error_analysis,
                command.confidence_before,
            )

            cognitive_node_ids = _get_cognitive_node_ids(question)

            # 构造 AnswerSubmitted 领域事件（同步路径 + 事件总线共用）
            answer_event = AnswerSubmitted(
                user_id=command.user_id,
                source_module="practice",
                attempt_id=attempt_id,
                session_id=command.session_id,
                question_id=command.question_id,
                skill_id=question.get("skill_id", ""),
                is_correct=is_correct,
                answer=user_answer_list,
                correct_answer=correct_answer if isinstance(correct_answer, list) else [correct_answer],
                response_time_seconds=float(command.response_time_ms) / 1000.0,
                hints_used=command.hints_used,
                confidence_before=command.confidence_before,
                difficulty=difficulty,
                cognitive_node_ids=cognitive_node_ids,
            )

            # 认知中心更新改为事件订阅（AnswerSubmitted）单一路径，避免双写。
            # 事件总线在 publish() 中同步等待 handler 完成，用户视角仍一致。

            # 更新会话统计
            session_repo.update_session_stats(uow.sql_db, command.session_id)

            # 保存聚合根与命令记录
            uow.aggregates.save(
                aggregate,
                command_id=command.command_id,
                command_type="SubmitAnswerCommand",
                payload={
                    "question_id": command.question_id,
                    "is_correct": is_correct,
                    "response_time_ms": command.response_time_ms,
                    "attempt_id": attempt_id,
                },
            )
            uow.commit()

        # 发布领域事件（跨模块联动）
        bus = _get_event_bus(context)
        try:
            await bus.publish(answer_event)
        except Exception as e:
            logger.warning("发布 AnswerSubmitted 失败: %s", e)

        if not is_correct:
            try:
                error_type = _extract_distractor_type(question, user_answer_list)
                await bus.publish(ErrorRecorded(
                    user_id=command.user_id,
                    question_id=command.question_id,
                    skill_id=question.get("skill_id", ""),
                    error_type=error_type,
                    user_answer=user_answer_str,
                    correct_answer=correct_answer_str,
                ))
            except Exception as e:
                logger.warning("发布 ErrorRecorded 失败: %s", e)

        return {
            "attempt_id": attempt_id,
            "is_correct": is_correct,
            "correct_answer": correct_answer,
            "explanation": explanation,
            "analysis": explanation,
            "error_type": error_pattern,
            "error_detail": error_analysis.get("llm_detail", ""),
            "metacognition_feedback": _metacognition_feedback(command.confidence_before, is_correct),
            "score": aggregate.score,
            "session_status": aggregate.status,
            "event": event,
        }


class SkipQuestionCommandHandler(CommandHandler):
    """跳过题目命令处理器。"""

    command_type = SkipQuestionCommand

    async def handle(self, command: SkipQuestionCommand, context: dict | None = None) -> dict:
        with _get_uow(context) as uow:
            aggregate = _load_or_create_aggregate(uow, command.session_id, command.user_id)
            event = aggregate.skip_question(command.question_id)
            uow.aggregates.save(
                aggregate,
                command_id=command.command_id,
                command_type="SkipQuestionCommand",
                payload={"question_id": command.question_id},
            )
            uow.commit()

        return {
            "session_id": command.session_id,
            "question_id": command.question_id,
            "status": aggregate.status,
            "version": aggregate.version,
            "event": event,
        }


class CompleteSessionCommandHandler(CommandHandler):
    """完成会话命令处理器。"""

    command_type = CompleteSessionCommand

    async def handle(self, command: CompleteSessionCommand, context: dict | None = None) -> dict:
        with _get_uow(context) as uow:
            aggregate = _load_or_create_aggregate(uow, command.session_id, command.user_id)
            event = aggregate.complete(command.duration_seconds)

            session_repo.update_session_status(
                uow.sql_db,
                command.session_id,
                "completed",
                {"finished_at": _now_iso()},
            )
            stats = session_repo.update_session_stats(uow.sql_db, command.session_id)

            uow.aggregates.save(
                aggregate,
                command_id=command.command_id,
                command_type="CompleteSessionCommand",
                payload={"duration_seconds": command.duration_seconds},
            )
            uow.commit()

        bus = _get_event_bus(context)
        try:
            await bus.publish(SessionCompleted(
                user_id=command.user_id,
                session_id=command.session_id,
                total_questions=stats.get("total", 0),
                correct_count=stats.get("correct", 0),
                accuracy=aggregate.score,
                duration_minutes=float(command.duration_seconds) / 60.0,
            ))
        except Exception as e:
            logger.warning("发布 SessionCompleted 失败: %s", e)

        return {
            "session_id": command.session_id,
            "status": aggregate.status,
            "score": aggregate.score,
            "total": stats.get("total", 0),
            "correct": stats.get("correct", 0),
            "wrong": stats.get("wrong", 0),
            "version": aggregate.version,
            "event": event,
        }


def _answer_to_str(answer: Any) -> str:
    """将答案归一化为字符串。"""
    if isinstance(answer, list):
        return ",".join(str(a) for a in answer) if answer else ""
    return str(answer or "")


def _extract_distractor_type(question: dict, user_answer: Any) -> str:
    """从选项中提取错因类型。"""
    try:
        options_raw = question.get("options", [])
        if isinstance(options_raw, str):
            options_raw = _safe_json(options_raw, [])
        if not isinstance(options_raw, list):
            return "careless"
        user_set = set(str(a).strip().upper() for a in (user_answer or []))
        for o in options_raw:
            if not isinstance(o, dict):
                continue
            if str(o.get("letter", "")).strip().upper() in user_set:
                return o.get("distractor_type") or "careless"
    except Exception:
        pass
    return "careless"


def _now_iso() -> str:
    from datetime import datetime
    return datetime.now().isoformat()
