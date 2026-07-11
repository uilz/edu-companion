"""
PracticeEngine — 练习系统统一入口模块

将分散在 14 个子模块中的函数汇聚为一个干净的小接口。
不重复任何逻辑，纯粹做 re-export。
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime
from typing import Any, Optional

from app.infrastructure.event_bus_utils import publish_event_safe

logger = logging.getLogger(__name__)

# ── 工具函数 ──
from shared.utils import safe_json, safe_iso, safe_int  # noqa: F401


# ════════════════════════════════════════════════════════════════════
# 领域事件发布 (SSOT = shared/events.py)
#   3 个 practice 事件在所有答题 / 完成路径上统一发布
#   - AnswerSubmitted / ErrorRecorded / SessionCompleted
#   替代了 domain/practice/service.py 中未被任何路由调用的旧实现
# ════════════════════════════════════════════════════════════════════


def _to_answer_list(value: Any) -> list[str]:
    """把用户答案归一化为 list[str]。"""
    if value is None:
        return []
    if isinstance(value, list):
        return [str(v) for v in value]
    if isinstance(value, str):
        stripped = value.strip()
        if not stripped:
            return []
        # 兼容旧 API 中用逗号拼接的多选答案
        return [v.strip() for v in stripped.split(",") if v.strip()]
    return [str(value)]


async def publish_practice_events(
    *,
    user_id: str,
    session_id: str,
    question_id: str,
    question: dict,
    is_correct: bool,
    user_answer: Any,
    correct_answer: Any,
    time_spent_seconds: int = 0,
    hints_used: int = 0,
) -> None:
    """发布答题事件: AnswerSubmitted + ErrorRecorded(错时)。

    认知节点更新统一由认知中心订阅 AnswerSubmitted 处理，练习模块不再直接发布
    PracticeSubmitted 或直接调用认知 repository。

    调用方:
      - practice_session.submit_answer (会话模式)
      - misc.py /api/practice/submit (独立模式)
    """
    try:
        from shared.events import (
            AnswerSubmitted,
            ErrorRecorded,
        )
        from app.application.di import container

        skill_id = (question.get("skill_id", "") or "") if isinstance(question, dict) else ""
        cognitive_node_ids: list[str] = []
        if isinstance(question, dict):
            raw = question.get("cognitive_node_ids", [])
            if isinstance(raw, list):
                cognitive_node_ids = [str(x) for x in raw]
            elif isinstance(raw, str):
                try:
                    import json as _json
                    cognitive_node_ids = [str(x) for x in _json.loads(raw)]
                except Exception:
                    cognitive_node_ids = []

        answer_list = _to_answer_list(user_answer)
        correct_list = _to_answer_list(correct_answer)
        user_ans_str = ",".join(answer_list)
        correct_ans_str = ",".join(correct_list)

        # 1. AnswerSubmitted (主事件，单一路径)
        await container.event_bus.publish(AnswerSubmitted(
            user_id=user_id,
            source_module="practice",
            attempt_id=str(uuid.uuid4())[:16],
            session_id=session_id,
            question_id=question_id,
            skill_id=skill_id,
            is_correct=is_correct,
            answer=answer_list,
            correct_answer=correct_list,
            response_time_seconds=float(time_spent_seconds or 0),
            hints_used=hints_used or 0,
        ))

        # 2. ErrorRecorded (答错时)
        if not is_correct:
            error_type = "careless"
            try:
                options_raw = question.get("options", []) if isinstance(question, dict) else []
                if isinstance(options_raw, str):
                    options_raw = safe_json(options_raw, [])
                if isinstance(options_raw, list):
                    user_set = set(str(a).strip().upper() for a in (user_answer or []))
                    for o in options_raw:
                        if not isinstance(o, dict):
                            continue
                        if str(o.get("letter", "")).strip().upper() in user_set:
                            error_type = o.get("distractor_type") or "careless"
                            break
            except Exception:
                pass

            await container.event_bus.publish(ErrorRecorded(
                user_id=user_id,
                source_module="practice",
                question_id=question_id,
                skill_id=skill_id,
                error_type=error_type,
                user_answer=user_ans_str,
                correct_answer=correct_ans_str,
            ))
    except Exception as e:
        logger.debug("publish_practice_events failed: %s", e)


def _get_metacognition_feedback(confidence_before, is_correct: bool) -> str:
    """根据自信度和正确性返回元认知反馈文案"""
    if confidence_before is None:
        return ""
    if confidence_before >= 3:
        if is_correct:
            return "你确实掌握了，自信是对的"
        return "⚠️ 元认知偏差：你以为掌握了但其实没有。建议重新学习推导过程。"
    if is_correct:
        return "💡 谦逊的正确：你比你以为的更懂。试着给别人讲一遍确认。"
    return "还有提升空间，继续努力"


class PracticeEngine:
    """练习系统统一入口 — 负责答题提交与事件发布。

    设计原则：
    - 所有学习行为只产生事件，不直接修改认知状态。
    - 练习模块通过 PersistentEventBus 发布 AnswerSubmitted / ErrorRecorded。
    - 认知中心通过订阅 AnswerSubmitted 消费并更新投影。
    - 旧 sync_from_practice_event / PracticeSubmitted 直接调用已彻底移除。
    """

    @staticmethod
    def submit_answer(
        session_id: str,
        question_id: str,
        user_id: str,
        user_answer: Optional[list] = None,
        time_spent: int = 0,
        hints_used: int = 0,
        confidence_before: int = None,
    ) -> dict:
        """提交答题：校验、记录、发布事件，返回基本反馈。"""
        from app.infrastructure.db.database import get_db
        from app.services.practice import session_repository as repo
        from app.services.practice.session_engine import check_answer, classify_error
        from shared.events import AnswerSubmitted, ErrorRecorded

        db = get_db()

        # 1. 验证会话 & 题目归属
        session = repo.get_session(db, session_id, user_id)
        if not session:
            return {"error": "会话不存在或不属于当前用户", "is_correct": False}
        sq = repo.get_session_question(db, session_id, question_id)
        if not sq:
            return {"error": "题目不属于该会话", "is_correct": False}
        existing = db.fetchone(
            "SELECT is_correct, user_answer FROM practice_attempts WHERE session_id = %s AND question_id = %s",
            (session_id, question_id),
        )
        if existing:
            question = db.fetchone(
                "SELECT * FROM questions WHERE id = %s AND deleted_at IS NULL",
                (question_id,),
            )
            correct_answer = safe_json(question.get("answer"), []) if question else []
            explanation = (question.get("explanation", "") or question.get("analysis", "")) if question else ""
            return {
                "is_correct": existing["is_correct"],
                "correct_answer": correct_answer,
                "analysis": explanation,
                "explanation": explanation,
                "consecutive_correct": 0,
                "mastered": existing["is_correct"],
                "wrong_count_increased": not existing["is_correct"],
                "already_answered": True,
            }

        question = db.fetchone(
            "SELECT * FROM questions WHERE id = %s AND deleted_at IS NULL",
            (question_id,),
        )
        if not question:
            return {"error": "题目不存在", "is_correct": False}

        correct_answer = safe_json(question.get("answer"), [])
        explanation = question.get("explanation", "") or question.get("analysis", "")

        # 2. 判对错
        is_correct = check_answer(user_answer, correct_answer, question.get("question_type", "single"))
        now = datetime.now().isoformat()

        # 3. 错因分析
        error_pattern = ""
        error_analysis: dict[str, Any] = {}
        if not is_correct:
            error_pattern = classify_error(question, user_answer) or ""
            try:
                from app.services.analytics.error_attribution import classify_llm
                error_detail = classify_llm(
                    question_data=question,
                    user_answer=user_answer,
                    correct_answer=correct_answer,
                )
                error_analysis = {"llm_detail": error_detail} if error_detail else {}
            except Exception:
                pass

        # 4. 写入答题记录
        repo.insert_attempt(
            db, session_id, question_id, user_id, is_correct, user_answer or [],
            time_spent, hints_used, error_pattern, error_analysis, confidence_before, now,
        )

        # 5. 更新会话统计
        repo.update_session_stats(db, session_id)

        # 6. 发布领域事件（单一事实来源 = AnswerSubmitted）
        correlation_id = f"{session_id}:{question_id}:{int(datetime.now().timestamp() * 1000)}"
        skill_id = question.get("skill_id", "") or ""
        cognitive_node_ids = safe_json(question.get("cognitive_node_ids"), [])
        if isinstance(cognitive_node_ids, str):
            cognitive_node_ids = safe_json(cognitive_node_ids, [])
        if not isinstance(cognitive_node_ids, list):
            cognitive_node_ids = []

        answer_list = _to_answer_list(user_answer)
        correct_list = _to_answer_list(correct_answer)
        user_ans_str = ",".join(answer_list)
        correct_ans_str = ",".join(correct_list)

        answer_event = AnswerSubmitted(
            user_id=user_id,
            source_module="practice",
            source_id=session_id,
            correlation_id=correlation_id,
            attempt_id=str(uuid.uuid4())[:16],
            session_id=session_id,
            question_id=question_id,
            skill_id=skill_id,
            is_correct=is_correct,
            answer=answer_list,
            correct_answer=correct_list,
            response_time_seconds=float(time_spent or 0),
            hints_used=hints_used or 0,
            confidence_before=confidence_before,
            difficulty=question.get("difficulty"),
            cognitive_node_ids=[str(x) for x in cognitive_node_ids],
            submitted_at=datetime.now(),
        )
        publish_event_safe(answer_event)

        # 发布 ErrorRecorded
        if not is_correct:
            error_type = "careless"
            try:
                options_raw = question.get("options", [])
                if isinstance(options_raw, str):
                    options_raw = safe_json(options_raw, [])
                if isinstance(options_raw, list):
                    user_set = set(str(a).strip().upper() for a in (user_answer or []))
                    for option in options_raw:
                        if not isinstance(option, dict):
                            continue
                        if str(option.get("letter", "")).strip().upper() in user_set:
                            error_type = option.get("distractor_type") or "careless"
                            break
            except Exception:
                pass

            publish_event_safe(ErrorRecorded(
                user_id=user_id,
                source_module="practice",
                source_id=question_id,
                correlation_id=correlation_id,
                caused_by_event_id=answer_event.event_id,
                question_id=question_id,
                skill_id=skill_id,
                error_type=error_type,
                user_answer=user_ans_str,
                correct_answer=correct_ans_str,
            ))

        return {
            "is_correct": is_correct,
            "correct_answer": correct_answer,
            "analysis": explanation,
            "explanation": explanation,
            "consecutive_correct": 0,
            "mastered": is_correct,
            "wrong_count_increased": not is_correct,
            "error_type": error_pattern,
            "error_detail": error_analysis.get("llm_detail", ""),
            "metacognition_feedback": _get_metacognition_feedback(confidence_before, is_correct),
            "submitted_event_id": answer_event.event_id,
        }


def submit_answer(
    session_id: str,
    question_id: str,
    user_id: str,
    user_answer: Optional[list] = None,
    time_spent: int = 0,
    hints_used: int = 0,
    confidence_before: int = None,
) -> dict:
    """模块级便捷入口，等价于 PracticeEngine.submit_answer。"""
    return PracticeEngine.submit_answer(
        session_id=session_id,
        question_id=question_id,
        user_id=user_id,
        user_answer=user_answer,
        time_spent=time_spent,
        hints_used=hints_used,
        confidence_before=confidence_before,
    )


async def publish_session_completed(
    *,
    user_id: str,
    session_id: str,
    total_questions: int = 0,
    correct_count: int = 0,
    accuracy: float = 0.0,
    duration_minutes: float = 0.0,
) -> None:
    """发布会话完成事件: SessionCompleted

    调用方:
      - practice_session.complete_session
    """
    try:
        from shared.events import SessionCompleted
        from app.application.di import container
        await container.event_bus.publish(SessionCompleted(
            user_id=user_id,
            session_id=session_id,
            total_questions=total_questions,
            correct_count=correct_count,
            accuracy=accuracy,
            duration_minutes=duration_minutes,
        ))
    except Exception as e:
        logger.debug("publish_session_completed failed: %s", e)


# ── 会话管理 (practice_session) ──
# 注意：submit_answer 已上移到本模块的 PracticeEngine / 模块级函数，
# 不再从 practice_session 重新导出，避免循环导入与定义覆盖。
from app.services.practice.practice_session import (
    get_session,
    start_session,
    pause_session,
    resume_session,
    cancel_session,
    complete_session,
    get_session_result,
    list_sessions,
    delete_session,
)

# ── 题库管理 (practice_question_bank) ──
from app.services.practice.practice_question_bank import (
    list_banks,
    get_bank,
    create_bank,
    update_bank,
    delete_bank,
    list_questions,
    get_question,
    get_question_preview,
    search_questions,
    resolve_bank_for_conversation,
    resolve_bank_for_node,
    _ensure_tables,
)

# ── 题目 CRUD (practice_question_crud) ──
from app.services.practice.practice_question_crud import (
    add_question,
    update_question,
    delete_question,
    toggle_favorite,
    toggle_slash,
    batch_import_questions,
    copy_questions_to_bank,
    reorder_questions_in_bank,
)

# ── AI 出题 (practice_question_gen) ──
from app.services.practice.practice_question_gen import (
    generate_and_save,
    generate_similar,
    explain_question,
    bulk_generate,
    get_material_context,
    handle_question_generation,
    generate_for_conversation,
)

# ── 自适应选题 (practice_adaptive) ──
from app.services.practice.practice_adaptive import (
    adaptive_select,
)

# ── 错题本 (practice_error_book) ──
from app.services.practice.practice_error_book import (
    get_error_book,
    review_error_question,
    get_error_materials,
    get_error_session_stats,
    clear_mastered_errors,
)

# ── 统计 (practice_stats) ──
from app.services.practice.practice_stats import (
    get_overview,
    get_daily_trend,
    get_session_history,
    get_error_distribution,
    get_weak_skills,
    get_recommendations,
)

# ── 考试 (practice_exam) ──
from app.services.practice.practice_exam import (
    create_exam,
    submit_exam_answer,
    grade_exam,
    get_exam_result,
    get_exam,
    get_exam_time,
    get_exam_answer_sheet,
    submit_all_exam,
    auto_submit_exam,
    generate_exam_report,
)

# ── 复习调度 (practice_scheduler) ──
from app.services.practice.practice_scheduler import (
    get_due_questions,
    get_review_stats,
)

# ── 判题引擎 (session_engine) ──
from app.services.practice.session_engine import (
    check_answer,
    validate_transition,
    compute_stats,
    classify_error,
)

# ── 旧版练习服务 (practice_service) ──
from app.services.practice.practice_service import (
    get_cognitive_proficiency,
    build_reply_text,
    get_hint_for_question,
    get_inline_hint,
    list_practice_sessions,
    complete_practice_session,
    record_attempt,
    compute_practice_stats,
    compute_behavior_report_data,
    get_stats_db,
    get_behavior_report_db,
)

# ── 秘书联动 (practice_secretary_integration) ──
from app.services.practice.practice_secretary_integration import (
    check_and_generate_proposals,
)

# ── 练习→对话集成 (practice_integrator) ──
from app.services.practice.practice_integrator import (
    integrate_practice_to_branch,
)