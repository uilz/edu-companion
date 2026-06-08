"""
练习会话管理 — 全生命周期

流程:
1. create_session() → 自适应选题 → 创建会话 + 写入会话题目关联
2. submit_answer() → 判对错 → 更新 attempt 表 + 会话题目状态
3. complete_session() → 统计得分 → 完成
"""

import json
import logging
import random
from datetime import datetime
from typing import Optional

from shared.constants import DEFAULT_USER_ID

logger = logging.getLogger(__name__)


def create_session(
    bank_id: str,
    user_id: str = DEFAULT_USER_ID,
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
    from app.db.database import get_db
    from app.services.practice.practice_adaptive import adaptive_select_v2
    from app.services.practice.practice_conversation import create_practice_conversation
    db = get_db()

    cfg = {
        "mode": mode,
        "question_count": question_count,
        "cognitive_node_ids": cognitive_node_ids or [],
        **(config or {}),
    }


    # 1. 用 v2 自适应选题（6:3:1 分层 + AI fallback）
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

    node_ids = list(set(
        nid for q in questions
        for nid in (q.get("cognitive_node_ids") or [])
    ))

    # 获取题库名称
    bank_name = ""
    try:
        bank_row = db.fetchone("SELECT name FROM question_banks WHERE id = %s", (bank_id,))
        if bank_row:
            bank_name = bank_row.get("name", "")
    except Exception:
        pass

    # 创建 Conversation(type="practice")
    conv_id = create_practice_conversation(
        user_id=user_id,
        session_id=session_id,
        bank_id=bank_id,
        bank_name=bank_name,
        question_count=len(questions),
        mode=mode,
    )

    db.execute(
        """INSERT INTO practice_sessions
           (id, user_id, bank_id, session_type, mode, config,
            status, total_count, cognitive_node_ids, conversation_id, created_at, started_at)
           VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
        (session_id, user_id, bank_id, session_type, mode,
         json.dumps(cfg), "created", len(questions),
         node_ids, conv_id, now, now),
    )

    # 3. 写入会话题目关联
    for i, q in enumerate(questions):
        sq_id = f"sq_{session_id}_{i}"
        db.execute(
            """INSERT INTO session_questions (id, session_id, question_id, sort_order, created_at)
               VALUES (%s, %s, %s, %s, %s)""",
            (sq_id, session_id, q["id"], i, now),
        )

    logger.info("会话创建: %s, %d 题, mode=%s", session_id, len(questions), mode)

    return {
        "session_id": session_id,
        "bank_id": bank_id,
        "mode": mode,
        "total_questions": len(questions),
        "status": "created",
        "questions": questions,
        "config": cfg,
        "created_at": now,
    }


def get_session(session_id: str, user_id: str = DEFAULT_USER_ID) -> Optional[dict]:
    """获取会话详情（含题目状态）"""
    from app.db.database import get_db
    db = get_db()

    session = db.fetchone(
        "SELECT * FROM practice_sessions WHERE id = %s AND user_id = %s",
        (session_id, user_id),
    )
    if not session:
        return None

    sq_rows = db.fetchall(
        """SELECT sq.*, q.stem, q.options, q.question_type, q.difficulty, q.cognitive_node_ids, q.metadata
           FROM session_questions sq
           LEFT JOIN questions q ON sq.question_id = q.id
           WHERE sq.session_id = %s
           ORDER BY sq.sort_order""",
        (session_id,),
    )

    questions = []
    for sq in sq_rows:
        item = {
            "id": sq["question_id"],
            "sort_order": sq["sort_order"],
            "stem": sq.get("stem", ""),
            "options": _safe_json(sq.get("options"), []),
            "question_type": sq.get("question_type", ""),
            "difficulty": sq.get("difficulty", 3),
            "cognitive_node_ids": sq.get("cognitive_node_ids") or [],
            "answered": sq.get("user_answer") is not None,
            "is_correct": sq.get("is_correct"),
            "time_spent": sq.get("time_spent_seconds", 0),
            "hints_used": sq.get("hints_used", 0),
        }
        # 如果已作答且正确/错误，答案不可见（但题目状态已定）
        questions.append(item)

    return {
        "session_id": session["id"],
        "bank_id": session["bank_id"],
        "mode": session["mode"],
        "session_type": session["session_type"],
        "status": session["status"],
        "total_count": session["total_count"],
        "correct_count": session.get("correct_count", 0),
        "wrong_count": session.get("wrong_count", 0),
        "score": session.get("score"),
        "config": _safe_json(session.get("config"), {}),
        "cognitive_node_ids": session.get("cognitive_node_ids") or [],
        "conversation_id": session.get("conversation_id", ""),
        "questions": questions,
        "created_at": _safe_iso(session.get("created_at")),
        "started_at": _safe_iso(session.get("started_at")),
        "finished_at": _safe_iso(session.get("finished_at")),
    }


def submit_answer(
    session_id: str,
    question_id: str,
    user_id: str = DEFAULT_USER_ID,
    user_answer: Optional[list] = None,
    time_spent: int = 0,
    hints_used: int = 0,
) -> dict:
    """
    提交答题。

    流程:
    1. 验证会话 & 题目归属
    2. 判对错（与正确答案比较）
    3. 更新 session_questions
    4. 写入 practice_attempts（含 LLM 错因分析）
    5. 更新会话统计数据
    6. **认知节点联动** — 调用 sync_from_practice_event() 更新所有关联知识节点的 Belief/BKT
    7. 返回判题结果 + 解析
    """
    from app.db.database import get_db
    from app.cognitive import get_repo
    db = get_db()

    # 1. 验证会话题目关联
    sq = db.fetchone(
        "SELECT * FROM session_questions WHERE session_id = %s AND question_id = %s",
        (session_id, question_id),
    )
    if not sq:
        return {"error": "题目不属于该会话", "is_correct": False}

    if sq.get("user_answer") is not None:
        return {
            "error": "题目已作答，不可重复提交",
            "is_correct": sq.get("is_correct"),
            "already_answered": True,
        }

    # 2. 获取题目正确答案
    question = db.fetchone(
        "SELECT * FROM questions WHERE id = %s AND deleted_at IS NULL",
        (question_id,),
    )
    if not question:
        return {"error": "题目不存在", "is_correct": False}

    correct_answer = _safe_json(question.get("answer"), [])
    analysis = question.get("analysis", "")

    # 3. 判对错
    is_correct = _check_answer(user_answer, correct_answer, question.get("question_type", "single"))
    now = datetime.now().isoformat()

    # 4. 更新会话题目关联
    db.execute(
        """UPDATE session_questions
           SET user_answer = %s, is_correct = %s, time_spent_seconds = %s,
               hints_used = %s
           WHERE id = %s""",
        (json.dumps(user_answer or []), is_correct, time_spent, hints_used, sq["id"]),
    )

    # 6. 写入答题记录
    attempt_id = f"att_{session_id}_{question_id}_{int(datetime.now().timestamp())}"
    is_wrong = not is_correct

    # 获取该题历史的错题次数
    history = db.fetchone(
        "SELECT COUNT(*) as cnt FROM practice_attempts WHERE question_id = %s AND user_id = %s AND is_wrong = true",
        (question_id, user_id),
    )
    prev_wrongs = history["cnt"] if history else 0

    # 连续正确 — 从最近记录查
    last_attempt = db.fetchone(
        "SELECT consecutive_correct FROM practice_attempts WHERE question_id = %s AND user_id = %s ORDER BY created_at DESC LIMIT 1",
        (question_id, user_id),
    )
    consecutive = (last_attempt["consecutive_correct"] or 0) if last_attempt else 0
    consecutive = 0 if is_wrong else consecutive + 1

    # LLM 错因分析：答错时调用 LLM 分类
    error_pattern = ""
    if is_wrong and user_answer:
        try:
            error_pattern = _classify_error(
                question_stem=question.get("stem", ""),
                question_answer=str(correct_answer),
                user_answer_str=str(user_answer),
                analysis_hint=analysis,
            )
        except Exception as e:
            logger.debug("错因分析LLM调用失败: %s", e)

    node_ids = question.get("cognitive_node_ids") or []
    db.execute(
        """INSERT INTO practice_attempts
           (id, session_id, question_id, user_id, user_answer, is_correct,
            time_spent_seconds, is_wrong, wrong_count, consecutive_correct,
            cognitive_node_ids, error_pattern, created_at)
           VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
        (attempt_id, session_id, question_id, user_id,
         json.dumps(user_answer or []), is_correct, time_spent,
         is_wrong, prev_wrongs + (1 if is_wrong else 0), consecutive,
         node_ids, error_pattern, now),
    )

    # 6. 更新会话统计
    update_session_stats(db, session_id)

    # ═══════════════════════════════════════════
    # 7. 认知节点联动：更新所有关联节点的 Belief + PracticeSummary + Trend
    # ═══════════════════════════════════════════
    for cid in node_ids:
        try:
            get_repo().sync_from_practice_event(
                user_id=user_id,
                skill_id=cid,
                is_correct=is_correct,
                time_spent=float(time_spent),
                hints_used=hints_used,
            )
            logger.debug("认知节点更新: skill=%s, correct=%s", cid, is_correct)
        except Exception as e:
            logger.warning("认知节点更新失败 skill=%s: %s", cid, e)

    # ═══════════════════════════════════════════
    # 8. 写入 Conversation 消息
    # ═══════════════════════════════════════════
    try:
        session = db.fetchone(
            "SELECT conversation_id FROM practice_sessions WHERE id = %s",
            (session_id,),
        )
        conv_id = session["conversation_id"] if session else ""
        if conv_id:
            from app.services.practice.practice_conversation import add_practice_answer_message
            add_practice_answer_message(
                user_id=user_id,
                conversation_id=conv_id,
                session_id=session_id,
                question_id=question_id,
                stem=question.get("stem", ""),
                user_answer=user_answer or [],
                is_correct=is_correct,
                correct_answer=correct_answer,
                time_spent=time_spent,
                hints_used=hints_used,
                analysis=analysis,
            )
    except Exception as e:
        logger.debug("练习消息写入 Conversation 失败: %s", e)

    # 9. 判 mastery
    mastered = consecutive >= 3

    logger.info(
        "答题提交: session=%s, q=%s, correct=%s, time=%ds, consecutive=%d",
        session_id, question_id, is_correct, time_spent, consecutive,
    )

    return {
        "is_correct": is_correct,
        "correct_answer": correct_answer,
        "analysis": analysis,
        "consecutive_correct": consecutive,
        "mastered": mastered,
        "wrong_count_increased": is_wrong,
    }


def start_session(session_id: str, user_id: str = DEFAULT_USER_ID) -> Optional[dict]:
    """开始会话：将状态从 created 变为 active"""
    from app.db.database import get_db
    db = get_db()
    session = db.fetchone(
        "SELECT * FROM practice_sessions WHERE id = %s AND user_id = %s",
        (session_id, user_id),
    )
    if not session:
        return None
    if session["status"] != "created":
        return {"error": f"当前状态不允许开始: {session['status']}"}
    now = datetime.now().isoformat()
    db.execute(
        "UPDATE practice_sessions SET status = 'active', started_at = %s WHERE id = %s",
        (now, session_id),
    )
    return get_session(session_id, user_id)


def pause_session(session_id: str, user_id: str = DEFAULT_USER_ID) -> Optional[dict]:
    """暂停会话：将 active 变为 paused"""
    from app.db.database import get_db
    db = get_db()
    session = db.fetchone(
        "SELECT * FROM practice_sessions WHERE id = %s AND user_id = %s",
        (session_id, user_id),
    )
    if not session:
        return None
    if session["status"] != "active":
        return {"error": f"当前状态不允许暂停: {session['status']}"}
    now = datetime.now().isoformat()
    cfg = _safe_json(session.get("config"), {})
    pauses = cfg.get("pauses", [])
    pauses.append({"paused_at": now, "resumed_at": None})
    cfg["pauses"] = pauses
    db.execute(
        "UPDATE practice_sessions SET status = 'paused', config = %s WHERE id = %s",
        (json.dumps(cfg), session_id),
    )
    return get_session(session_id, user_id)


def resume_session(session_id: str, user_id: str = DEFAULT_USER_ID) -> Optional[dict]:
    """恢复会话：将 paused 变为 active"""
    from app.db.database import get_db
    db = get_db()
    session = db.fetchone(
        "SELECT * FROM practice_sessions WHERE id = %s AND user_id = %s",
        (session_id, user_id),
    )
    if not session:
        return None
    if session["status"] != "paused":
        return {"error": f"当前状态不允许恢复: {session['status']}"}
    now = datetime.now().isoformat()
    cfg = _safe_json(session.get("config"), {})
    pauses = cfg.get("pauses", [])
    if pauses and pauses[-1].get("resumed_at") is None:
        pauses[-1]["resumed_at"] = now
    cfg["pauses"] = pauses
    db.execute(
        "UPDATE practice_sessions SET status = 'active', config = %s WHERE id = %s",
        (json.dumps(cfg), session_id),
    )
    return get_session(session_id, user_id)


def cancel_session(session_id: str, user_id: str = DEFAULT_USER_ID) -> Optional[dict]:
    """取消会话：将任何非完成态变为 cancelled"""
    from app.db.database import get_db
    db = get_db()
    session = db.fetchone(
        "SELECT * FROM practice_sessions WHERE id = %s AND user_id = %s",
        (session_id, user_id),
    )
    if not session:
        return None
    if session["status"] in ("completed", "cancelled"):
        logger.info(f"会话 {session_id} 已为 {session['status']}，跳过取消")
        return get_session(session_id, user_id)
    now = datetime.now().isoformat()
    db.execute(
        "UPDATE practice_sessions SET status = 'cancelled', finished_at = %s WHERE id = %s",
        (now, session_id),
    )
    return get_session(session_id, user_id)


def get_session_result(session_id: str, user_id: str = DEFAULT_USER_ID) -> Optional[dict]:
    """获取会话结果报告（含题单名称、每题详情）"""
    from app.db.database import get_db
    db = get_db()
    session = get_session(session_id, user_id)
    if not session:
        return None
    if session["status"] not in ("completed", "timeout"):
        return {"session_id": session_id, "status": session["status"], "message": "会话尚未完成"}

    # 题单名称
    bank_name = ""
    if session.get("bank_id"):
        try:
            b = db.fetchone(
                "SELECT name FROM question_banks WHERE id = %s",
                (session["bank_id"],),
            )
            bank_name = b["name"] if b else ""
        except Exception:
            pass

    sq_rows = db.fetchall(
        """SELECT sq.*, q.question_type, q.difficulty, q.cognitive_node_ids, q.stem,
                  q.options, q.answer, q.analysis
           FROM session_questions sq
           LEFT JOIN questions q ON sq.question_id = q.id
           WHERE sq.session_id = %s
           ORDER BY sq.sort_order""",
        (session_id,),
    )
    detail = []
    for sq in sq_rows:
        detail.append({
            "index": sq["sort_order"],
            "question_id": sq["question_id"],
            "stem": sq.get("stem", ""),
            "question_type": sq.get("question_type", ""),
            "difficulty": sq.get("difficulty", 3),
            "is_correct": sq.get("is_correct"),
            "user_answer": _safe_json(sq.get("user_answer"), None),
            "correct_answer": _safe_json(sq.get("answer"), None),
            "time_spent": sq.get("time_spent_seconds", 0),
            "hints_used": sq.get("hints_used", 0),
            "options": _safe_json(sq.get("options"), None),
            "explanation": sq.get("analysis", ""),
        })
    answered = sum(1 for d in detail if d["is_correct"] is not None)
    correct = sum(1 for d in detail if d["is_correct"] is True)

    return {
        "session_id": session_id,
        "status": session["status"],
        "total": session["total_count"],
        "answered": answered,
        "correct": correct,
        "wrong": answered - correct,
        "unanswered": session["total_count"] - answered,
        "score": session.get("score"),
        "duration_seconds": session.get("duration_seconds"),
        "mode": session["mode"],
        "session_type": session["session_type"],
        "bank_id": session.get("bank_id", ""),
        "bank_name": bank_name,
        "detail": detail,
        "created_at": session.get("created_at"),
        "started_at": session.get("started_at"),
        "finished_at": session.get("finished_at"),
    }


def complete_session(session_id: str, user_id: str = DEFAULT_USER_ID) -> Optional[dict]:
    """完成会话：汇总统计"""
    from app.db.database import get_db
    db = get_db()

    session = db.fetchone(
        "SELECT * FROM practice_sessions WHERE id = %s AND user_id = %s",
        (session_id, user_id),
    )
    if not session:
        return None

    if session["status"] == "completed":
        return get_session(session_id, user_id)

    total = session["total_count"]
    correct = db.fetchone(
        "SELECT COUNT(*) as cnt FROM session_questions WHERE session_id = %s AND is_correct = true",
        (session_id,),
    )
    correct_count = correct["cnt"] if correct else 0
    wrong_count = total - correct_count
    score = round((correct_count / max(total, 1)) * 100, 1)

    now = datetime.now().isoformat()
    start = session.get("started_at")
    duration = None
    if start:
        if isinstance(start, str):
            from datetime import datetime as dt2
            start_dt = dt2.fromisoformat(start)
        else:
            start_dt = start
        # 确保两边都是 naive 或都是 aware，避免 offset-naive/aware 相减报错
        now_dt = datetime.now()
        if hasattr(start_dt, "tzinfo") and start_dt.tzinfo is not None:
            from datetime import timezone
            now_dt = now_dt.replace(tzinfo=timezone.utc)
        duration = int((now_dt - start_dt).total_seconds())

    db.execute(
        """UPDATE practice_sessions
           SET status = 'completed', correct_count = %s, wrong_count = %s,
               score = %s, finished_at = %s, duration_seconds = %s
           WHERE id = %s""",
        (correct_count, wrong_count, score, now, duration, session_id),
    )

    # 更新 Conversation 元数据
    try:
        from app.services.practice.practice_conversation import update_conversation_on_complete
        update_conversation_on_complete(
            user_id=user_id,
            session_id=session_id,
            correct_count=correct_count,
            wrong_count=wrong_count,
            score=score,
            duration_seconds=duration,
        )
    except Exception as e:
        logger.debug("Conversation 更新失败: %s", e)

    # 触发成就检测
    try:
        from app.services.analytics.achievement_service import check_achievements
        newly = check_achievements(user_id)
        if newly:
            logger.info("新成就解锁: user=%s, count=%d", user_id, len(newly))
    except Exception as e:
        logger.warning("成就检测失败: %s", e)

    # 触发秘书提案生成（错题诊断/掌握停滞/复习提醒/反思引导）
    try:
        from app.services.practice.practice_secretary_integration import check_and_generate_proposals
        proposal_count = check_and_generate_proposals(
            user_id=user_id,
            session_id=session_id,
            session_type=session.get("session_type", "practice"),
        )
        if proposal_count > 0:
            logger.info("秘书提案: user=%s, count=%d", user_id, proposal_count)
    except Exception as e:
        logger.warning("秘书提案生成失败: %s", e)

    logger.info("会话完成: %s, %d/%d, score=%.1f%%, duration=%ds",
                session_id, correct_count, total, score, duration or 0)

    result = get_session(session_id, user_id)
    result["score"] = score
    result["duration_seconds"] = duration
    return result


def list_sessions(
    user_id: str = DEFAULT_USER_ID,
    bank_id: Optional[str] = None,
    status: Optional[str] = None,
    session_type: Optional[str] = None,
    mode: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    score_min: Optional[float] = None,
    score_max: Optional[float] = None,
    duration_min: Optional[int] = None,
    duration_max: Optional[int] = None,
    question_count_min: Optional[int] = None,
    sort_by: str = "created_at",
    sort_order: str = "desc",
    limit: int = 20,
    offset: int = 0,
    cursor: Optional[str] = None,
) -> dict:
    """列出用户练习会话 — 支持筛选/排序/双分页

    筛选参数:
      bank_id, status, session_type, mode, date_from/date_to (ISO格式),
      score_min/score_max (0~100), duration_min/duration_max (秒),
      question_count_min

    排序参数:
      sort_by: created_at | started_at | finished_at | score | duration_seconds | total_count
      sort_order: asc | desc

    双分页（二选一）:
      offset/limit — 传统页码分页
      cursor — 游标分页（值为上一页最后一条的 created_at ISO 时间戳）
    """
    from app.db.database import get_db
    db = get_db()

    conditions = ["user_id = %s"]
    params = [user_id]

    if bank_id:
        conditions.append("bank_id = %s"); params.append(bank_id)
    if status:
        conditions.append("status = %s"); params.append(status)
    if session_type:
        conditions.append("session_type = %s"); params.append(session_type)
    if mode:
        conditions.append("mode = %s"); params.append(mode)
    if date_from:
        conditions.append("started_at >= %s"); params.append(date_from)
    if date_to:
        conditions.append("started_at <= %s"); params.append(date_to)
    if score_min is not None:
        conditions.append("score >= %s"); params.append(score_min)
    if score_max is not None:
        conditions.append("score <= %s"); params.append(score_max)
    if duration_min is not None:
        conditions.append("duration_seconds >= %s"); params.append(duration_min)
    if duration_max is not None:
        conditions.append("duration_seconds <= %s"); params.append(duration_max)
    if question_count_min is not None:
        conditions.append("total_count >= %s"); params.append(question_count_min)

    where = " AND ".join(conditions)

    # 游标分页：cursor 是上一页最后一条的 created_at
    if cursor:
        conditions.append("created_at < %s"); params.append(cursor)
        where = " AND ".join(conditions)

    # 排序（防 SQL 注入校验）
    allowed_sort = {
        "created_at", "started_at", "finished_at",
        "score", "duration_seconds", "total_count",
    }
    if sort_by not in allowed_sort:
        sort_by = "created_at"
    if sort_order not in ("asc", "desc"):
        sort_order = "desc"

    total = None
    if not cursor:
        # 无游标时返回 total（页码分页需要）
        t = db.fetchone(
            f"SELECT COUNT(*) as cnt FROM practice_sessions WHERE {where}",
            tuple(params),
        )
        total = t["cnt"] if t else 0

    if cursor:
        rows = db.fetchall(
            f"""SELECT id, bank_id, session_type, mode, config, status, total_count,
                       correct_count, wrong_count, score, duration_seconds,
                       conversation_id, created_at, started_at, finished_at
                FROM practice_sessions WHERE {where}
                ORDER BY {sort_by} {sort_order}
                LIMIT %s""",
            tuple(params + [limit + 1]),
        )
    else:
        rows = db.fetchall(
            f"""SELECT id, bank_id, session_type, mode, config, status, total_count,
                       correct_count, wrong_count, score, duration_seconds,
                       conversation_id, created_at, started_at, finished_at
                FROM practice_sessions WHERE {where}
                ORDER BY {sort_by} {sort_order}
                LIMIT %s OFFSET %s""",
            tuple(params + [limit + 1, offset]),
        )

    has_more = len(rows) > limit
    if has_more:
        rows = rows[:limit]

    items = []
    for r in rows:
        bank_name = ""
        if r["bank_id"]:
            try:
                b = db.fetchone(
                    "SELECT name FROM question_banks WHERE id = %s",
                    (r["bank_id"],),
                )
                bank_name = b["name"] if b else ""
            except Exception:
                pass

        items.append({
            "session_id": r["id"],
            "bank_id": r["bank_id"],
            "bank_name": bank_name,
            "session_type": r["session_type"],
            "mode": r["mode"],
            "status": r["status"],
            "total_count": r["total_count"],
            "correct_count": r.get("correct_count", 0),
            "wrong_count": r.get("wrong_count", 0),
            "score": r.get("score"),
            "duration_seconds": r.get("duration_seconds"),
            "conversation_id": r.get("conversation_id", ""),
            "created_at": _safe_iso(r.get("created_at")),
            "started_at": _safe_iso(r.get("started_at")),
            "finished_at": _safe_iso(r.get("finished_at")),
        })

    next_cursor = None
    if has_more and items:
        next_cursor = items[-1]["created_at"]

    return {
        "items": items,
        "total": total,
        "limit": limit,
        "offset": offset if not cursor else None,
        "cursor": cursor,
        "next_cursor": next_cursor,
        "has_more": has_more,
    }


# ── 内部辅助 ──


def update_session_stats(db, session_id: str):
    """根据答题记录重新计算会话统计"""
    stats = db.fetchone(
        """SELECT COUNT(*) as total,
                  SUM(CASE WHEN is_correct THEN 1 ELSE 0 END) as correct
           FROM session_questions WHERE session_id = %s""",
        (session_id,),
    )
    if stats:
        total = stats["total"] or 0
        correct = stats["correct"] or 0
        wrong = total - correct
        score = round((correct / max(total, 1)) * 100, 1)
        db.execute(
            "UPDATE practice_sessions SET correct_count = %s, wrong_count = %s, score = %s WHERE id = %s",
            (correct, wrong, score, session_id),
        )


def _check_answer(
    user_answer: Optional[list],
    correct_answer: list,
    question_type: str,
) -> bool:
    """判题逻辑"""
    if not user_answer:
        return False

    user_set = set(str(a).strip().upper() for a in user_answer if a)
    correct_set = set(str(a).strip().upper() for a in correct_answer if a)

    if not user_set and not correct_set:
        return True
    if not user_set or not correct_set:
        return False

    return user_set == correct_set


def _safe_json(val, default=None):
    if val is None:
        return default
    if isinstance(val, (list, dict)):
        return val
    if isinstance(val, str):
        try:
            return json.loads(val)
        except Exception:
            return default
    return default


def _safe_iso(val):
    if val is None:
        return None
    if hasattr(val, "isoformat"):
        return val.isoformat()
    return str(val)


def delete_session(session_id: str, user_id: str = DEFAULT_USER_ID) -> bool:
    """硬删除练习会话及关联数据（session_questions, practice_attempts）

    返回 True 表示已删除，False 表示会话不存在。
    """
    from app.db.database import get_db
    db = get_db()

    session = db.fetchone(
        "SELECT id FROM practice_sessions WHERE id = %s AND user_id = %s",
        (session_id, user_id),
    )
    if not session:
        return False

    # 清理关联数据
    db.execute("DELETE FROM practice_attempts WHERE session_id = %s", (session_id,))
    db.execute("DELETE FROM session_questions WHERE session_id = %s", (session_id,))
    db.execute("DELETE FROM practice_sessions WHERE id = %s", (session_id,))
    return True


# ── LLM 错因分类 ──

_ERROR_CATEGORIES = [
    "概念混淆",      # 对知识点理解错误
    "计算失误",      # 计算过程出错（如加减乘除、代入错误）
    "审题不清",      # 未正确理解题目要求
    "公式记错",      # 公式/定理记忆错误
    "逻辑推理错误",  # 推理过程出问题
    "粗心大意",      # 非知识性错误（如笔误、看错数）
    "缺少思路",      # 完全不知道如何下手
    "时间不足",      # 时间压力导致错误
    "其他",          # 无法归类的错误
]


def _classify_error(
    question_stem: str,
    question_answer: str,
    user_answer_str: str,
    analysis_hint: str = "",
) -> str:
    """
    使用 LLM 对错题进行错因分类。

    分类依据:
    - 题目内容 (question_stem)
    - 正确答案 (question_answer)
    - 用户答案 (user_answer_str)
    - 题目解析提示 (analysis_hint)

    返回错误类型标签，失败时返回空字符串。
    """
    categories_str = "、".join(_ERROR_CATEGORIES)
    prompt = f"""你是一位教学诊断专家。请根据以下信息，判断学生的错误类型。

【题目】{question_stem[:500]}
【正确答案】{question_answer[:300]}
【学生答案】{user_answer_str[:300]}
【题目解析】{analysis_hint[:300]}

请从以下分类中选出最匹配的一个（仅输出分类名称）：
{categories_str}"""

    try:
        from app.llm import chat
        response = chat(prompt, max_tokens=16, temperature=0.1)
        result = response.strip().rstrip("。，")
        # 校验结果是否在已知分类中
        if result in _ERROR_CATEGORIES:
            return result
        # 模糊匹配
        for cat in _ERROR_CATEGORIES:
            if cat in result or result in cat:
                return cat
        return "其他"
    except Exception:
        return ""
