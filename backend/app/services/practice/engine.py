"""
PracticeEngine — 练习系统统一入口模块

将分散在 14 个子模块中的函数汇聚为一个干净的小接口。
不重复任何逻辑，纯粹做 re-export。
"""

# ── 工具函数 ──
from shared.utils import safe_json, safe_iso, safe_int  # noqa: F401

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
    adaptive_select_v2,
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