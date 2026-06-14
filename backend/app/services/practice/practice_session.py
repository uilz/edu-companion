"""
练习会话管理 — 全生命周期（门面模式）

公共 API 保持向后兼容，内部实现委托给:
- session_engine.py — 纯评分/状态机逻辑
- session_repository.py — 持久化操作
"""

import json
import logging
from datetime import datetime
from typing import Optional

from app.services.practice.session_engine import (
    validate_transition,
    check_answer,
    compute_stats,
    classify_error,
    safe_json,
    safe_iso,
    safe_int,
)
from app.services.practice import session_repository as repo

logger = logging.getLogger(__name__)


def create_session(
    bank_id: str,
    user_id: str,
    session_type: str = "practice",
    mode: str = "adaptive",
    question_count: int = 10,
    config: Optional[dict] = None,
    exclude_ids: Optional[list[str]] = None,
    cognitive_node_ids: Optional[list[str]] = None,
) -> dict:
    """
    创建练习会话。

    流程:
    1. 自适应选题
    2. 创建会话记录 (status=created)
    3. 写入会话题目关联
    4. 返回会话信息（含题目列表，不含答案）
    """
    from app.infrastructure.db.database import get_db
    from app.services.practice.practice_adaptive import adaptive_select_v2
    from app.services.practice.practice_conversation import create_practice_conversation
    db = get_db()

    cfg = {
        "mode": mode,
        "question_count": question_count,
        "cognitive_node_ids": cognitive_node_ids or [],
        **(config or {}),
    }

    # 1. 自适应选题
    questions = adaptive_select_v2(
        bank_id=bank_id,
        user_id=user_id,
        count=question_count,
        mode=mode,
        exclude_ids=exclude_ids,
        cognitive_node_ids=cognitive_node_ids,
    )
    if not questions:
        logger.warning("无可用题目，创建空会话 bank=%s", bank_id)

    # 2. 创建会话
    now = datetime.now().isoformat()
    session_id = f"ses_{bank_id}_{int(datetime.now().timestamp())}"
    node_ids = list(set(nid for q in questions for nid in (q.get("cognitive_node_ids") or [])))

    # 获取题库名称
    bank_name = ""
    try:
        bank_row = db.fetchone("SELECT name FROM question_banks WHERE id = %s", (bank_id,))
        if bank_row:
            bank_name = bank_row.get("name", "")
    except Exception:
        pass

    repo.insert_session(db, session_id, bank_id, user_id, node_ids, session_type, mode, question_count, cfg, now)
    repo.insert_session_questions(db, session_id, questions, now)

    # 3. 可选：创建对话（从题库名称生成标题）
    if config and config.get("create_conversation", True):
        title = f"{bank_name or '练习'} · {mode}"
        create_practice_conversation(user_id, session_id, title, config.get("tree_node_id"))

    # 4. 返回（移除答案）
    for q in questions:
        q.pop("answer", None)
        q.pop("analysis", None)

    return {
        "id": session_id,
        "bank_id": bank_id,
        "bank_name": bank_name,
        "user_id": user_id,
        "session_type": session_type,
        "mode": mode,
        "question_count": question_count,
        "status": "created",
        "questions": questions,
        "node_ids": node_ids,
        "config": cfg,
        "created_at": now,
    }


def get_session(session_id: str, user_id: str) -> Optional[dict]:
    """获取会话详情（含答题状态）"""
    from app.infrastructure.db.database import get_db
    db = get_db()

    session = repo.get_session(db, session_id, user_id)
    if not session:
        return None

    # 获取题目列表（含用户答题状态）
    questions = db.fetchall(
        """SELECT sq.*, q.question_type, q.bloom_level, q.difficulty, q.content, q.options, q.analysis
           FROM session_questions sq
           JOIN questions q ON q.id = sq.question_id
           WHERE sq.session_id = %s
           ORDER BY sq.created_at""",
        (session_id,),
    )

    for q in questions:
        q["options"] = safe_json(q.get("options"), [])
        q["user_answer"] = safe_json(q.get("user_answer"), None)

    return {
        "id": session["id"],
        "bank_id": session["bank_id"],
        "user_id": session["user_id"],
        "session_type": session["session_type"],
        "mode": session["mode"],
        "question_count": safe_int(session["question_count"]),
        "correct_count": safe_int(session["correct_count"]),
        "wrong_count": safe_int(session["wrong_count"]),
        "score": float(session.get("score", 0) or 0),
        "status": session["status"],
        "node_ids": safe_json(session.get("node_ids"), []),
        "config": safe_json(session.get("config"), {}),
        "questions": questions,
        "created_at": safe_iso(session.get("created_at")),
        "started_at": safe_iso(session.get("started_at")),
        "finished_at": safe_iso(session.get("finished_at")),
    }


def submit_answer(
    session_id: str,
    question_id: str,
    user_id: str,
    user_answer: Optional[list] = None,
    time_spent: int = 0,
    hints_used: int = 0,
) -> dict:
    """
    提交答题。

    流程:
    1. 验证会话 & 题目归属
    2. 判对错
    3. 更新 session_questions
    4. 写入 practice_attempts（含错因分析）
    5. 更新会话统计
    6. 认知节点联动 — sync_from_practice_event()
    """
    from app.infrastructure.db.database import get_db
    from app.domain.cognitive import get_repo
    db = get_db()

    # 1. 验证
    sq = repo.get_session_question(db, session_id, question_id)
    if not sq:
        return {"error": "题目不属于该会话", "is_correct": False}
    if sq.get("user_answer") is not None:
        return {
            "error": "题目已作答，不可重复提交",
            "is_correct": sq.get("is_correct"),
            "already_answered": True,
        }

    question = db.fetchone(
        "SELECT * FROM questions WHERE id = %s AND deleted_at IS NULL",
        (question_id,),
    )
    if not question:
        return {"error": "题目不存在", "is_correct": False}

    correct_answer = safe_json(question.get("answer"), [])
    analysis = question.get("analysis", "")

    # 2. 判对错（纯函数）
    is_correct = check_answer(user_answer, correct_answer, question.get("question_type", "single"))
    now = datetime.now().isoformat()

    # 3. 错因分类
    error_type = ""
    error_detail = ""
    if not is_correct:
        error_type = classify_error(question, user_answer) or ""
        try:
            from app.services.analytics.error_attribution import classify_llm
            error_detail = classify_llm(
                question_data=question,
                user_answer=user_answer,
                correct_answer=correct_answer,
            )
        except Exception:
            pass

    # 4. 更新会话题目
    repo.update_session_question(db, session_id, question_id, is_correct, user_answer or [],
                                  time_spent, hints_used, error_type, now)

    # 5. 写入答题记录
    repo.insert_attempt(db, session_id, question_id, user_id, is_correct, user_answer or [],
                         time_spent, hints_used, error_type, error_detail, analysis, now)

    # 6. 更新会话统计
    repo.update_session_stats(db, session_id)

    # 7. 认知节点联动
    try:
        cognitive_node_ids = safe_json(question.get("cognitive_node_ids"), [])
        for node_id in cognitive_node_ids:
            get_repo().sync_from_practice_event(
                user_id=user_id,
                skill_id=node_id,
                is_correct=is_correct,
                response_time_ms=float(time_spent * 1000),
                topic=question.get("subject", ""),
                question_id=question_id,
            )
    except Exception as e:
        logger.debug("认知节点同步失败: %s", e)

    return {
        "is_correct": is_correct,
        "correct_answer": correct_answer,
        "analysis": analysis,
        "error_type": error_type,
        "error_detail": error_detail,
    }


def start_session(session_id: str, user_id: str) -> Optional[dict]:
    """开始会话（created → started）"""
    from app.infrastructure.db.database import get_db
    db = get_db()

    session = repo.get_session(db, session_id, user_id)
    if not session:
        return None
    if not validate_transition(session["status"], "started"):
        return None

    now = datetime.now().isoformat()
    repo.update_session_status(db, session_id, "started", {"started_at": now})
    return {"id": session_id, "status": "started", "started_at": now}


def pause_session(session_id: str, user_id: str) -> Optional[dict]:
    """暂停会话（started → paused）"""
    from app.infrastructure.db.database import get_db
    db = get_db()

    session = repo.get_session(db, session_id, user_id)
    if not session:
        return None
    if not validate_transition(session["status"], "paused"):
        return None

    repo.update_session_status(db, session_id, "paused")
    return {"id": session_id, "status": "paused"}


def resume_session(session_id: str, user_id: str) -> Optional[dict]:
    """恢复会话（paused → started）"""
    from app.infrastructure.db.database import get_db
    db = get_db()

    session = repo.get_session(db, session_id, user_id)
    if not session:
        return None
    if not validate_transition(session["status"], "started"):
        return None

    repo.update_session_status(db, session_id, "started")
    return {"id": session_id, "status": "started"}


def cancel_session(session_id: str, user_id: str) -> Optional[dict]:
    """取消会话（任一状态 → cancelled）"""
    from app.infrastructure.db.database import get_db
    db = get_db()

    session = repo.get_session(db, session_id, user_id)
    if not session:
        return None
    if not validate_transition(session["status"], "cancelled"):
        return None

    repo.update_session_status(db, session_id, "cancelled")
    return {"id": session_id, "status": "cancelled"}


def get_session_result(session_id: str, user_id: str) -> Optional[dict]:
    """获取会话结果统计"""
    from app.infrastructure.db.database import get_db
    db = get_db()

    session = repo.get_session(db, session_id, user_id)
    if not session:
        return None

    stats = repo.update_session_stats(db, session_id)
    return {
        "id": session_id,
        "status": session["status"],
        "score": stats["score"],
        "total": stats["total"],
        "correct": stats["correct"],
        "wrong": stats["wrong"],
        "created_at": safe_iso(session.get("created_at")),
        "started_at": safe_iso(session.get("started_at")),
        "finished_at": safe_iso(session.get("finished_at")),
    }


def complete_session(session_id: str, user_id: str) -> Optional[dict]:
    """完成会话（started → completed）"""
    from app.infrastructure.db.database import get_db
    from app.services.practice.practice_conversation import complete_practice_conversation
    db = get_db()

    session = repo.get_session(db, session_id, user_id)
    if not session:
        return None
    if not validate_transition(session["status"], "completed"):
        return None

    now = datetime.now().isoformat()
    stats = repo.update_session_stats(db, session_id)
    repo.update_session_status(db, session_id, "completed", {"finished_at": now})

    # 完成关联练习对话
    try:
        complete_practice_conversation(session_id, user_id, stats)
    except Exception as e:
        logger.debug("练习对话完成失败: %s", e)

    return {
        "id": session_id,
        "status": "completed",
        "score": stats["score"],
        "total": stats["total"],
        "correct": stats["correct"],
        "wrong": stats["wrong"],
        "finished_at": now,
    }


def list_sessions(
    user_id: str,
    bank_id: str = None,
    status: str = None,
    limit: int = 50,
    offset: int = 0,
) -> list[dict]:
    """列出用户练习会话"""
    from app.infrastructure.db.database import get_db
    db = get_db()
    return repo.list_sessions(db, user_id, bank_id, status, limit, offset)


def delete_session(session_id: str, user_id: str) -> bool:
    """删除练习会话及关联数据"""
    from app.infrastructure.db.database import get_db
    db = get_db()
    return repo.delete_session(db, session_id, user_id)
