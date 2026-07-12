"""
考试模式服务 — 计时/答题卡/自动交卷/成绩报告

核心流程：
1. create_exam() → 创建考试会话（含 deadline）
2. 前端倒计时 → GET /exam/{id}/time 校验剩余时间
3. 提交单题 → submit_answer()（复用已有逻辑）
4. 全部提交 → submit_all_exam() → 自动判分 → 成绩报告
5. 超时 → validate_exam_time() → 自动交卷
"""

import json
import logging
from datetime import datetime, timedelta
from typing import Optional


logger = logging.getLogger(__name__)


def create_exam_from_request(
    user_id: str,
    bank_id: str,
    body: dict,
) -> dict:
    """根据 API 请求体创建考试会话（仅做参数归一化，核心逻辑在 create_exam）。"""
    config = body.get("config") or {}
    if isinstance(config, dict):
        config["exam_type"] = body.get("exam_type", "standard")
    return create_exam(
        user_id=user_id,
        bank_id=bank_id,
        count=body.get("count", 20),
        duration_minutes=body.get("duration_minutes", body.get("time_limit", 60)),
        config=config,
        cognitive_node_ids=body.get("cognitive_node_ids"),
    )


def create_exam(
    user_id: str,
    bank_id: str = "",
    count: int = 20,
    duration_minutes: int = 60,
    config: Optional[dict] = None,
    cognitive_node_ids: Optional[list[str]] = None,
) -> dict:
    """
    创建考试会话。

    与普通练习的区别：
    1. session_type = 'exam'
    2. config 中写入 deadline（ISO格式）
    3. 状态机多一个 timeout 状态
    4. 所有题目一次性组好
    """
    from app.infrastructure.db.database import get_db
    from app.services.practice.practice_adaptive import adaptive_select
    db = get_db()

    now = datetime.now()
    deadline = now + timedelta(minutes=duration_minutes)

    cfg = {
        "mode": "exam",
        "duration_minutes": duration_minutes,
        "deadline": deadline.isoformat(),
        "question_count": count,
        "cognitive_node_ids": cognitive_node_ids or [],
        **(config or {}),
    }

    # 1. 组题（自适应模式）
    questions = adaptive_select(
        bank_id=bank_id,
        user_id=user_id,
        count=count,
        mode=cfg.get("selection_mode", "challenge"),
        cognitive_node_ids=cognitive_node_ids,
    )

    if not questions:
        logger.warning("考试无可用题目 bank=%s", bank_id)

    # 2. 创建会话
    session_id = f"exam_{bank_id}_{int(datetime.now().timestamp())}"
    now_iso = now.isoformat()

    node_ids = list(set(
        nid for q in questions
        for nid in (q.get("cognitive_node_ids") or [])
    ))

    db.execute(
        """INSERT INTO practice_sessions
           (id, user_id, bank_id, session_type, mode, config,
            status, total_count, cognitive_node_ids, created_at, started_at)
           VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
        (session_id, user_id, bank_id, "exam", "exam",
         json.dumps(cfg), "active", len(questions),
         node_ids, now_iso, now_iso),
    )

    # 3. 写入题目关联
    for i, q in enumerate(questions):
        sq_id = f"sq_{session_id}_{i}"
        db.execute(
            """INSERT INTO session_questions (id, session_id, question_id, sort_order, created_at)
               VALUES (%s, %s, %s, %s, %s)""",
            (sq_id, session_id, q["id"], i, now_iso),
        )

    logger.info("考试创建: %s, %d 题, %d分钟", session_id, len(questions), duration_minutes)

    # 4. 返回题目（不含答案）
    safe_questions = []
    for q in questions:
        safe_questions.append({
            "id": q["id"],
            "sort_order": len(safe_questions),
            "stem": q.get("stem", ""),
            "options": q.get("options", []),
            "question_type": q.get("question_type", "single"),
            "difficulty": q.get("difficulty", 3),
            "cognitive_node_ids": q.get("cognitive_node_ids") or [],
            "answered": False,
            "is_correct": None,
        })

    return {
        "session_id": session_id,
        "id": session_id,
        "bank_id": bank_id,
        "mode": "exam",
        "session_type": "exam",
        "status": "active",
        "total_count": len(safe_questions),
        "correct_count": 0,
        "wrong_count": 0,
        "score": None,
        "questions": safe_questions,
        "config": cfg,
        "cognitive_node_ids": node_ids,
        "deadline": deadline.isoformat(),
        "duration_minutes": duration_minutes,
        "created_at": now_iso,
        "started_at": now_iso,
        "finished_at": None,
        "duration_seconds": None,
    }


def get_exam_time(session_id: str, user_id: str) -> dict:
    """获取考试剩余时间及状态"""
    from app.infrastructure.db.database import get_db
    db = get_db()

    session = db.fetchone(
        "SELECT * FROM practice_sessions WHERE id = %s AND user_id = %s",
        (session_id, user_id),
    )
    if not session:
        return {"error": "考试不存在", "valid": False}

    if session["status"] not in ("active",):
        return {
            "valid": False,
            "status": session["status"],
            "remaining_seconds": 0,
            "message": f"考试已{session['status']}",
        }

    cfg = session.get("config") or {}
    if isinstance(cfg, str):
        cfg = json.loads(cfg)

    deadline_str = cfg.get("deadline")
    if not deadline_str:
        return {"valid": True, "remaining_seconds": 99999, "status": "active"}

    try:
        deadline = datetime.fromisoformat(deadline_str)
    except (ValueError, TypeError):
        return {"valid": True, "remaining_seconds": 99999, "status": "active"}

    now = datetime.now()
    # DB TIMESTAMPTZ 字段读出可能带 tzinfo, 而 datetime.now() 是 naive;
    # 需要 tzinfo 对齐才能相减。
    if hasattr(deadline, "tzinfo") and deadline.tzinfo is not None and now.tzinfo is None:
        from datetime import timezone
        now = now.replace(tzinfo=timezone.utc)
    elif hasattr(deadline, "tzinfo") and deadline.tzinfo is None and now.tzinfo is not None:
        from datetime import timezone
        deadline = deadline.replace(tzinfo=timezone.utc)
    remaining = (deadline - now).total_seconds()

    if remaining <= 0:
        # 超时 → 自动交卷
        _auto_submit_exam(session_id, db)
        return {
            "valid": False,
            "status": "timeout",
            "remaining_seconds": 0,
            "auto_submitted": True,
            "message": "考试时间到，已自动交卷",
        }

    # 同样处理 started_at 的 tzinfo
    started_at_raw = session["started_at"].isoformat() if hasattr(session["started_at"], 'isoformat') else session["started_at"]
    started_at_dt = datetime.fromisoformat(started_at_raw)
    if hasattr(started_at_dt, "tzinfo") and started_at_dt.tzinfo is not None and now.tzinfo is None:
        from datetime import timezone
        now_aware = now.replace(tzinfo=timezone.utc)
    else:
        now_aware = now
    elapsed = (now_aware - started_at_dt).total_seconds()
    return {
        "valid": True,
        "status": "active",
        "remaining_seconds": int(remaining),
        "elapsed_seconds": int(elapsed),
        "deadline": deadline_str,
        "auto_submitted": False,
    }


def submit_all_exam(session_id: str, user_id: str) -> dict:
    """一次性提交考试所有答案，生成成绩报告"""
    from app.infrastructure.db.database import get_db
    db = get_db()

    # 1. 检查考试状态
    session = db.fetchone(
        "SELECT * FROM practice_sessions WHERE id = %s AND user_id = %s",
        (session_id, user_id),
    )
    if not session:
        return {"error": "考试不存在"}

    if session["status"] not in ("active",):
        # 已交卷，返回已有成绩
        return get_exam_result(session_id, user_id)

    # 2. 判分：从 practice_attempts 读取答题状态
    sq_rows = db.fetchall(
        """SELECT sq.sort_order, sq.question_id,
                  q.answer, q.explanation,
                  q.question_type, q.options as raw_options, q.stem,
                  pa.user_answer, pa.is_correct, pa.time_spent_seconds
           FROM session_questions sq
           LEFT JOIN questions q ON sq.question_id = q.id
           LEFT JOIN practice_attempts pa ON pa.session_id = sq.session_id AND pa.question_id = sq.question_id
           WHERE sq.session_id = %s
           ORDER BY sq.sort_order""",
        (session_id,),
    )

    total = len(sq_rows)
    answered = 0
    correct = 0
    wrong = 0
    unanswered = 0
    score = 0.0
    question_results = []

    for sq in sq_rows:
        user_answer = sq.get("user_answer")
        is_correct = sq.get("is_correct")
        sort_order = sq.get("sort_order")

        if is_correct is True:
            correct += 1
            answered += 1
        elif is_correct is False:
            wrong += 1
            answered += 1
        else:
            unanswered += 1
            wrong += 1
            is_correct = False
            user_answer = []

        # 构造正确选项列表
        correct_answer = _extract_correct_answer(sq)

        question_results.append({
            "sort_order": sort_order,
            "question_id": sq["question_id"],
            "stem": sq.get("stem", "")[:80],
            "question_type": sq.get("question_type", ""),
            "user_answer": user_answer,
            "correct_answer": correct_answer,
            "is_correct": is_correct if is_correct is not None else False,
            "time_spent": sq.get("time_spent_seconds", 0),
        })

    # 3. 计分
    if total > 0:
        score = round((correct / total) * 100, 1)

    now = datetime.now().isoformat()
    duration = _calc_duration(session.get("started_at"), now)

    # 4. 完成会话
    db.execute(
        """UPDATE practice_sessions
           SET status = 'completed', correct_count = %s, wrong_count = %s,
               score = %s, finished_at = %s, duration_seconds = %s
           WHERE id = %s""",
        (correct, wrong, score, now, duration, session_id),
    )

    # 5. 触发成就检测
    from app.services.analytics.achievement_service import check_achievements
    try:
        check_achievements(user_id)
    except Exception as e:
        logger.debug("成就检测失败: %s", e)

    # 6. 触发秘书提案生成
    try:
        from app.services.practice.practice_secretary_integration import check_and_generate_proposals
        proposal_count = check_and_generate_proposals(
            user_id=user_id,
            session_id=session_id,
            session_type="exam",
        )
        if proposal_count > 0:
            logger.info("考试秘书提案: user=%s, count=%d", user_id, proposal_count)
    except Exception as e:
        logger.debug("考试秘书提案失败: %s", e)

    logger.info("考试交卷: %s, %d/%d 正确, 得分 %.1f", session_id, correct, total, score)

    return generate_exam_report(session_id, user_id, question_results, {
        "total": total, "answered": answered, "correct": correct,
        "wrong": wrong, "unanswered": unanswered, "score": score,
        "duration": duration, "finished_at": now,
    })


def get_exam_result(session_id: str, user_id: str) -> dict:
    """获取已完成的考试成绩报告"""
    from app.infrastructure.db.database import get_db
    db = get_db()

    session = db.fetchone(
        "SELECT * FROM practice_sessions WHERE id = %s AND user_id = %s",
        (session_id, user_id),
    )
    if not session:
        return {"error": "考试不存在"}

    sq_rows = db.fetchall(
        """SELECT sq.sort_order, sq.question_id,
                  q.stem, q.explanation, q.question_type, q.options as raw_options,
                  pa.user_answer, pa.is_correct, pa.time_spent_seconds
           FROM session_questions sq
           LEFT JOIN questions q ON sq.question_id = q.id
           LEFT JOIN practice_attempts pa ON pa.session_id = sq.session_id AND pa.question_id = sq.question_id
           WHERE sq.session_id = %s
           ORDER BY sq.sort_order""",
        (session_id,),
    )

    question_results = []
    total = len(sq_rows)
    correct = 0
    wrong = 0

    for sq in sq_rows:
        is_correct = sq.get("is_correct")
        question_results.append({
            "sort_order": sq.get("sort_order"),
            "question_id": sq["question_id"],
            "stem": (sq.get("stem") or "")[:80],
            "question_type": sq.get("question_type", ""),
            "user_answer": sq.get("user_answer"),
            "correct_answer": _extract_correct_answer(sq),
            "is_correct": is_correct if is_correct is not None else False,
            "analysis": sq.get("explanation", ""),
            "time_spent": sq.get("time_spent_seconds", 0),
        })
        if is_correct is True:
            correct += 1
        else:
            wrong += 1

    score = round((correct / total) * 100, 1) if total > 0 else 0

    return generate_exam_report(session_id, user_id, question_results, {
        "total": total,
        "answered": correct + wrong,
        "correct": correct,
        "wrong": wrong,
        "unanswered": 0,
        "score": score,
        "duration": session.get("duration_seconds", 0),
        "finished_at": session.get("finished_at", ""),
    })


def get_exam(session_id: str, user_id: str) -> dict:
    """获取进行中的考试详情（含题目+剩余时间+答题状态）"""
    from app.infrastructure.db.database import get_db
    db = get_db()

    session = db.fetchone(
        "SELECT * FROM practice_sessions WHERE id = %s AND user_id = %s",
        (session_id, user_id),
    )
    if not session:
        return {"error": "考试不存在"}

    cfg = session.get("config") or {}
    if isinstance(cfg, str):
        cfg = json.loads(cfg)

    # 获取剩余时间
    time_info = get_exam_time(session_id, user_id)

    # 如果是 timeout / completed，返回结果
    if not time_info.get("valid", True) or session["status"] != "active":
        if session["status"] in ("completed", "timeout"):
            return get_exam_result(session_id, user_id)
        return {
            "session_id": session_id,
            "status": session["status"],
            "error": f"考试已{session['status']}",
        }

    # 获取题目 + 答题状态（从 practice_attempts 读取）
    sq_rows = db.fetchall(
        """SELECT sq.sort_order, sq.question_id,
                  q.stem, q.options as raw_options, q.question_type, q.difficulty,
                  q.cognitive_node_ids,
                  pa.user_answer, pa.is_correct
           FROM session_questions sq
           LEFT JOIN questions q ON sq.question_id = q.id
           LEFT JOIN practice_attempts pa ON pa.session_id = sq.session_id AND pa.question_id = sq.question_id
           WHERE sq.session_id = %s
           ORDER BY sq.sort_order""",
        (session_id,),
    )

    questions = []
    for sq in sq_rows:
        options = sq.get("raw_options") or []
        if isinstance(options, str):
            try:
                options = json.loads(options)
            except Exception:
                options = []

        answered = sq.get("user_answer") is not None
        questions.append({
            "id": sq["question_id"],
            "sort_order": sq["sort_order"],
            "stem": sq.get("stem", ""),
            "options": options,
            "question_type": sq.get("question_type", "single"),
            "difficulty": sq.get("difficulty", 3),
            "cognitive_node_ids": sq.get("cognitive_node_ids") or [],
            "answered": answered,
            "is_correct": sq.get("is_correct"),
        })

    return {
        "session_id": session_id,
        "bank_id": session.get("bank_id", ""),
        "status": session["status"],
        "total_count": session.get("total_count", len(questions)),
        "questions": questions,
        "time_info": time_info,
        "config": cfg,
        "deadline": cfg.get("deadline", ""),
        "duration_minutes": cfg.get("duration_minutes", 60),
        "created_at": session.get("created_at", "").isoformat() if hasattr(session.get("created_at"), "isoformat") else str(session.get("created_at", "")),
    }


def submit_exam_answer(
    session_id: str,
    user_id: str,
    question_id: str,
    answer,
    time_spent: int = 0,
    is_final: bool = False,
) -> dict:
    """考试中逐题提交答案"""
    from app.infrastructure.db.database import get_db
    from app.services.practice.session_engine import check_answer
    db = get_db()

    session = db.fetchone(
        "SELECT * FROM practice_sessions WHERE id = %s AND user_id = %s",
        (session_id, user_id),
    )
    if not session:
        return {"error": "考试不存在"}
    if session["status"] != "active":
        return {"error": f"考试已{session['status']}，不可提交答案"}

    sq = db.fetchone(
        """SELECT sq.*, q.answer, q.explanation, q.question_type, q.options as raw_options
           FROM session_questions sq
           LEFT JOIN questions q ON sq.question_id = q.id
           WHERE sq.session_id = %s AND sq.question_id = %s""",
        (session_id, question_id),
    )
    if not sq:
        return {"error": "题目不属于该考试"}

    correct_answer = _extract_correct_answer(sq)
    is_correct = check_answer(answer, correct_answer, sq.get("question_type", "single"))

    user_answer_json = json.dumps(answer) if not isinstance(answer, str) else json.dumps([answer])

    explanation = sq.get("explanation", "")
    attempt_id = f"pa_{session_id}_{question_id}"
    db.execute(
        """INSERT INTO practice_attempts
           (id, session_id, question_id, user_id, user_answer, is_correct,
            time_spent_seconds, is_wrong, consecutive_correct, created_at)
           VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
           ON CONFLICT (id) DO UPDATE SET
               user_answer = EXCLUDED.user_answer,
               is_correct = EXCLUDED.is_correct,
               time_spent_seconds = EXCLUDED.time_spent_seconds""",
        (attempt_id, session_id, question_id, user_id, user_answer_json,
         is_correct, time_spent, not is_correct, 0,
         datetime.now().isoformat()),
    )

    db.execute(
        """UPDATE practice_sessions
           SET correct_count = (SELECT COUNT(*) FROM practice_attempts
                                WHERE session_id = %s AND is_correct = true),
               wrong_count = (SELECT COUNT(*) FROM practice_attempts
                              WHERE session_id = %s AND is_correct = false)
           WHERE id = %s""",
        (session_id, session_id, session_id),
    )

    result = {
        "question_id": question_id,
        "is_correct": is_correct,
        "correct_answer": correct_answer,
        "explanation": explanation,
        "time_spent": time_spent,
    }

    if is_final:
        result["final_submit"] = True
        result["exam_result"] = submit_all_exam(session_id, user_id)

    return result


def auto_submit_exam(session_id: str, user_id: str) -> Optional[dict]:
    """超时自动交卷（公开入口）"""
    from app.infrastructure.db.database import get_db
    db = get_db()

    session = db.fetchone(
        "SELECT * FROM practice_sessions WHERE id = %s AND user_id = %s",
        (session_id, user_id),
    )
    if not session:
        return None
    if session["status"] not in ("active",):
        return {"status": session["status"], "message": f"考试已{session['status']}"}

    _auto_submit_exam(session_id, db)
    return {"status": "timeout", "message": "考试时间到，已自动交卷", "session_id": session_id}


def grade_exam(session_id: str, user_id: str) -> Optional[dict]:
    """考试判分（生成完整成绩报告）"""
    from app.infrastructure.db.database import get_db
    db = get_db()

    session = db.fetchone(
        "SELECT * FROM practice_sessions WHERE id = %s AND user_id = %s",
        (session_id, user_id),
    )
    if not session:
        return None

    if session["status"] == "completed":
        return get_exam_result(session_id, user_id)

    if session["status"] == "active":
        _auto_submit_exam(session_id, db)

    sq_rows = db.fetchall(
        """SELECT sq.sort_order, sq.question_id,
                  q.answer, q.explanation,
                  q.question_type, q.options as raw_options, q.stem,
                  pa.user_answer, pa.is_correct, pa.time_spent_seconds
           FROM session_questions sq
           LEFT JOIN questions q ON sq.question_id = q.id
           LEFT JOIN practice_attempts pa ON pa.session_id = sq.session_id AND pa.question_id = sq.question_id
           WHERE sq.session_id = %s
           ORDER BY sq.sort_order""",
        (session_id,),
    )

    total = len(sq_rows)
    correct = sum(1 for sq in sq_rows if sq.get("is_correct") is True)
    wrong = sum(1 for sq in sq_rows if sq.get("is_correct") is False)
    unanswered = sum(1 for sq in sq_rows if sq.get("is_correct") is None)
    score = round((correct / total) * 100, 1) if total > 0 else 0

    now = datetime.now().isoformat()
    duration = _calc_duration(session.get("started_at"), now)

    question_results = []
    for sq in sq_rows:
        question_results.append({
            "sort_order": sq.get("sort_order"),
            "question_id": sq["question_id"],
            "stem": (sq.get("stem") or "")[:80],
            "question_type": sq.get("question_type", ""),
            "user_answer": sq.get("user_answer"),
            "correct_answer": _extract_correct_answer(sq),
            "is_correct": sq.get("is_correct") if sq.get("is_correct") is not None else False,
            "analysis": sq.get("explanation", ""),
            "time_spent": sq.get("time_spent_seconds", 0),
        })

    db.execute(
        """UPDATE practice_sessions
           SET status = 'completed', correct_count = %s, wrong_count = %s,
               score = %s, finished_at = %s, duration_seconds = %s
           WHERE id = %s""",
        (correct, wrong, score, now, duration, session_id),
    )

    try:
        from app.services.analytics.achievement_service import check_achievements
        check_achievements(user_id)
    except Exception:
        pass

    return generate_exam_report(session_id, user_id, question_results, {
        "total": total, "answered": correct + wrong, "correct": correct,
        "wrong": wrong, "unanswered": unanswered, "score": score,
        "duration": duration, "finished_at": now,
    })


def get_exam_answer_sheet(session_id: str, user_id: str) -> dict:
    """获取答题卡状态（用于前端导航）"""
    from app.infrastructure.db.database import get_db
    db = get_db()

    session = db.fetchone(
        "SELECT * FROM practice_sessions WHERE id = %s AND user_id = %s",
        (session_id, user_id),
    )
    if not session:
        return {"error": "考试不存在"}

    sq_rows = db.fetchall(
        """SELECT sq.sort_order, sq.question_id,
                  pa.is_correct, pa.user_answer
           FROM session_questions sq
           LEFT JOIN practice_attempts pa ON pa.session_id = sq.session_id AND pa.question_id = sq.question_id
           WHERE sq.session_id = %s
           ORDER BY sq.sort_order""",
        (session_id,),
    )

    items = []
    for sq in sq_rows:
        answered = sq.get("user_answer") is not None
        items.append({
            "index": sq["sort_order"],
            "question_id": sq["question_id"],
            "answered": answered,
            "is_correct": sq.get("is_correct"),
        })

    return {
        "session_id": session_id,
        "total": len(items),
        "answered": sum(1 for i in items if i["answered"]),
        "unanswered": sum(1 for i in items if not i["answered"]),
        "items": items,
    }


# ── 内部辅助 ──


def _auto_submit_exam(session_id: str, db) -> None:
    """超时自动交卷"""
    now = datetime.now().isoformat()
    db.execute(
        """UPDATE practice_sessions
           SET status = 'timeout', finished_at = %s
           WHERE id = %s AND status = 'active'""",
        (now, session_id),
    )
    # 未答的题标记为错误（写入 practice_attempts）
    unanswered = db.fetchall(
        """SELECT sq.question_id, sq.sort_order
           FROM session_questions sq
           WHERE sq.session_id = %s
             AND NOT EXISTS (
               SELECT 1 FROM practice_attempts pa
               WHERE pa.session_id = sq.session_id AND pa.question_id = sq.question_id
             )""",
        (session_id,),
    )
    for uq in unanswered:
        db.execute(
            """INSERT INTO practice_attempts
               (id, session_id, question_id, user_id, user_answer, is_correct,
                time_spent_seconds, is_wrong, consecutive_correct, created_at)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
               ON CONFLICT DO NOTHING""",
            (f"pa_{session_id}_{uq['question_id']}", session_id, uq["question_id"],
             "", json.dumps([]), False, 0, True, 0, now),
        )
    logger.info("自动交卷: %s, %d 题未答", session_id, len(unanswered))


def _calc_duration(started_at, finished_at) -> int:
    """计算考试用时（秒）"""
    try:
        if isinstance(started_at, str):
            start = datetime.fromisoformat(started_at)
        else:
            start = started_at
        if isinstance(finished_at, str):
            end = datetime.fromisoformat(finished_at)
        else:
            end = finished_at
        # 确保两边 tzinfo 一致，避免 offset-naive/aware 相减报错
        start_aware = hasattr(start, "tzinfo") and start.tzinfo is not None
        end_aware = hasattr(end, "tzinfo") and end.tzinfo is not None
        if start_aware and not end_aware:
            from datetime import timezone
            end = end.replace(tzinfo=timezone.utc)
        elif end_aware and not start_aware:
            from datetime import timezone
            start = start.replace(tzinfo=timezone.utc)
        return int((end - start).total_seconds())
    except Exception:
        return 0


def _extract_correct_answer(sq: dict) -> list:
    """从题目记录中提取正确选项列表"""
    raw = sq.get("raw_options") or sq.get("options") or []
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            return []

    if isinstance(raw, list):
        return [opt["letter"] for opt in raw if opt.get("is_correct")]
    return []


def generate_exam_report(
    session_id: str,
    user_id: str,
    question_results: list[dict],
    stats: dict,
) -> dict:
    """生成完整的考试成绩报告"""
    # 按题型统计
    type_stats = {}
    for qr in question_results:
        qtype = qr.get("question_type", "unknown")
        if qtype not in type_stats:
            type_stats[qtype] = {"total": 0, "correct": 0, "wrong": 0}
        type_stats[qtype]["total"] += 1
        if qr.get("is_correct"):
            type_stats[qtype]["correct"] += 1
        else:
            type_stats[qtype]["wrong"] += 1

    # 评分等级
    score = stats.get("score", 0)
    if score >= 90:
        grade = "优秀"
        grade_color = "green"
    elif score >= 75:
        grade = "良好"
        grade_color = "blue"
    elif score >= 60:
        grade = "及格"
        grade_color = "yellow"
    else:
        grade = "不及格"
        grade_color = "red"

    return {
        "session_id": session_id,
        "user_id": user_id,
        "status": "completed",
        "score": score,
        "grade": grade,
        "grade_color": grade_color,
        "stats": stats,
        "type_stats": type_stats,
        "question_results": question_results,
        "correct_ratio": round(stats.get("correct", 0) / max(stats.get("total", 1), 1), 3),
    }
