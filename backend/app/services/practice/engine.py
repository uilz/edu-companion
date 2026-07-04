"""
PracticeEngine — 练习系统统一入口模块

将分散在 14 个子模块中的函数汇聚为一个干净的小接口。
不重复任何逻辑，纯粹做 re-export。
"""
from __future__ import annotations

import logging
from typing import Any, Optional

logger = logging.getLogger(__name__)

# ── 工具函数 ──
from shared.utils import safe_json, safe_iso, safe_int  # noqa: F401


# ════════════════════════════════════════════════════════════════════
# 领域事件发布 (SSOT = shared/events.py)
#   4 个 practice 事件在所有答题 / 完成路径上统一发布
#   - AnswerSubmitted / ErrorRecorded / PracticeSubmitted / SessionCompleted
#   替代了 domain/practice/service.py 中未被任何路由调用的旧实现
# ════════════════════════════════════════════════════════════════════


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
    """发布答题事件: AnswerSubmitted + ErrorRecorded(错时) + PracticeSubmitted

    调用方:
      - practice_session.submit_answer (会话模式)
      - misc.py /api/practice/submit (独立模式)
    """
    try:
        from shared.events import (
            AnswerSubmitted,
            ErrorRecorded,
            PracticeSubmitted,
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

        # 归一化为字符串
        if isinstance(user_answer, list):
            user_ans_str = ",".join(str(a) for a in user_answer) if user_answer else ""
        else:
            user_ans_str = str(user_answer or "")
        if isinstance(correct_answer, list):
            correct_ans_str = ",".join(str(a) for a in correct_answer) if correct_answer else ""
        else:
            correct_ans_str = str(correct_answer or "")

        # 1. AnswerSubmitted (主事件)
        await container.event_bus.publish(AnswerSubmitted(
            user_id=user_id,
            session_id=session_id,
            question_id=question_id,
            skill_id=skill_id,
            is_correct=is_correct,
            answer=user_ans_str,
            correct_answer=correct_ans_str,
            time_spent=float(time_spent_seconds or 0),
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
                question_id=question_id,
                skill_id=skill_id,
                error_type=error_type,
                user_answer=user_ans_str,
                correct_answer=correct_ans_str,
            ))

        # 3. PracticeSubmitted (驱动认知节点掌握度)
        await container.event_bus.publish(PracticeSubmitted(
            user_id=user_id,
            atom_node_ids=cognitive_node_ids,
            correctness=1.0 if is_correct else 0.0,
            latency_ms=float(time_spent_seconds or 0) * 1000.0,
        ))
    except Exception as e:
        logger.debug("publish_practice_events failed: %s", e)


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
from app.services.practice.practice_session import (
    get_session,
    submit_answer,
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
    update_cognitive_after_practice,
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