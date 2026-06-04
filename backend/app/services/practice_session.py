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
    from app.services.practice_adaptive import adaptive_select
    db = get_db()

    cfg = {
        "mode": mode,
        "question_count": question_count,
        "cognitive_node_ids": cognitive_node_ids or [],
        **(config or {}),
    }

    # 1. 自适应选题
    questions = adaptive_select(
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

    db.execute(
        """INSERT INTO v7_practice_sessions
           (id, user_id, bank_id, session_type, mode, config,
            status, total_count, cognitive_node_ids, created_at, started_at)
           VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
        (session_id, user_id, bank_id, session_type, mode,
         json.dumps(cfg), "created", len(questions),
         node_ids, now, now),
    )

    # 3. 写入会话题目关联
    for i, q in enumerate(questions):
        sq_id = f"sq_{session_id}_{i}"
        db.execute(
            """INSERT INTO v7_session_questions (id, session_id, question_id, sort_order, created_at)
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
        "SELECT * FROM v7_practice_sessions WHERE id = %s AND user_id = %s",
        (session_id, user_id),
    )
    if not session:
        return None

    sq_rows = db.fetchall(
        """SELECT sq.*, q.stem, q.options, q.question_type, q.difficulty, q.cognitive_node_ids, q.metadata
           FROM v7_session_questions sq
           LEFT JOIN v7_questions q ON sq.question_id = q.id
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
    3. 更新 v7_session_questions
    4. 写入 v7_practice_attempts
    5. 更新会话统计数据
    6. **认知节点联动** — 调用 sync_from_practice_event() 更新所有关联知识节点的 Belief/BKT
    7. 返回判题结果 + 解析
    """
    from app.db.database import get_db
    from app.cognitive.storage import sync_from_practice_event
    db = get_db()

    # 1. 验证会话题目关联
    sq = db.fetchone(
        "SELECT * FROM v7_session_questions WHERE session_id = %s AND question_id = %s",
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
        "SELECT * FROM v7_questions WHERE id = %s AND deleted_at IS NULL",
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
        """UPDATE v7_session_questions
           SET user_answer = %s, is_correct = %s, time_spent_seconds = %s,
               hints_used = %s
           WHERE id = %s""",
        (json.dumps(user_answer or []), is_correct, time_spent, hints_used, sq["id"]),
    )

    # 5. 写入答题记录
    attempt_id = f"att_{session_id}_{question_id}_{int(datetime.now().timestamp())}"
    is_wrong = not is_correct

    # 获取该题历史的错题次数
    history = db.fetchone(
        "SELECT COUNT(*) as cnt FROM v7_practice_attempts WHERE question_id = %s AND user_id = %s AND is_wrong = true",
        (question_id, user_id),
    )
    prev_wrongs = history["cnt"] if history else 0

    # 连续正确 — 从最近记录查
    last_attempt = db.fetchone(
        "SELECT consecutive_correct FROM v7_practice_attempts WHERE question_id = %s AND user_id = %s ORDER BY created_at DESC LIMIT 1",
        (question_id, user_id),
    )
    consecutive = (last_attempt["consecutive_correct"] or 0) if last_attempt else 0
    consecutive = 0 if is_wrong else consecutive + 1

    node_ids = question.get("cognitive_node_ids") or []
    db.execute(
        """INSERT INTO v7_practice_attempts
           (id, session_id, question_id, user_id, user_answer, is_correct,
            time_spent_seconds, is_wrong, wrong_count, consecutive_correct,
            cognitive_node_ids, created_at)
           VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
        (attempt_id, session_id, question_id, user_id,
         json.dumps(user_answer or []), is_correct, time_spent,
         is_wrong, prev_wrongs + (1 if is_wrong else 0), consecutive,
         node_ids, now),
    )

    # 6. 更新会话统计
    update_session_stats(db, session_id)

    # ═══════════════════════════════════════════
    # 7. 认知节点联动：更新所有关联节点的 Belief + PracticeSummary + Trend
    # ═══════════════════════════════════════════
    for cid in node_ids:
        try:
            sync_from_practice_event(
                user_id=user_id,
                skill_id=cid,
                is_correct=is_correct,
                time_spent=float(time_spent),
                hints_used=hints_used,
            )
            logger.debug("认知节点更新: skill=%s, correct=%s", cid, is_correct)
        except Exception as e:
            logger.warning("认知节点更新失败 skill=%s: %s", cid, e)

    # 8. 判 mastery
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


def complete_session(session_id: str, user_id: str = DEFAULT_USER_ID) -> Optional[dict]:
    """完成会话：汇总统计"""
    from app.db.database import get_db
    db = get_db()

    session = db.fetchone(
        "SELECT * FROM v7_practice_sessions WHERE id = %s AND user_id = %s",
        (session_id, user_id),
    )
    if not session:
        return None

    if session["status"] == "completed":
        return get_session(session_id, user_id)

    total = session["total_count"]
    correct = db.fetchone(
        "SELECT COUNT(*) as cnt FROM v7_session_questions WHERE session_id = %s AND is_correct = true",
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
        duration = int((datetime.now() - start_dt).total_seconds())

    db.execute(
        """UPDATE v7_practice_sessions
           SET status = 'completed', correct_count = %s, wrong_count = %s,
               score = %s, finished_at = %s, duration_seconds = %s
           WHERE id = %s""",
        (correct_count, wrong_count, score, now, duration, session_id),
    )

    # 触发成就检测
    try:
        from app.services.achievement_service import check_achievements
        newly = check_achievements(user_id)
        if newly:
            logger.info("新成就解锁: user=%s, count=%d", user_id, len(newly))
    except Exception as e:
        logger.warning("成就检测失败: %s", e)

    # 触发秘书提案生成（错题诊断/掌握停滞/复习提醒/反思引导）
    try:
        from app.services.practice_secretary_integration import check_and_generate_proposals
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
    limit: int = 20,
    offset: int = 0,
) -> dict:
    """列出用户练习会话"""
    from app.db.database import get_db
    db = get_db()

    conditions = ["user_id = %s"]
    params = [user_id]
    if bank_id:
        conditions.append("bank_id = %s"); params.append(bank_id)
    if status:
        conditions.append("status = %s"); params.append(status)

    where = " AND ".join(conditions)
    total = db.fetchone(f"SELECT COUNT(*) as cnt FROM v7_practice_sessions WHERE {where}", tuple(params))
    total_count = total["cnt"] if total else 0

    rows = db.fetchall(
        f"""SELECT id, bank_id, session_type, mode, status, total_count,
                   correct_count, wrong_count, score, duration_seconds,
                   created_at, started_at, finished_at
            FROM v7_practice_sessions WHERE {where}
            ORDER BY created_at DESC LIMIT %s OFFSET %s""",
        tuple(params + [limit, offset]),
    )

    items = []
    for r in rows:
        items.append({
            "session_id": r["id"],
            "bank_id": r["bank_id"],
            "session_type": r["session_type"],
            "mode": r["mode"],
            "status": r["status"],
            "total_count": r["total_count"],
            "correct_count": r.get("correct_count", 0),
            "wrong_count": r.get("wrong_count", 0),
            "score": r.get("score"),
            "duration_seconds": r.get("duration_seconds"),
            "created_at": _safe_iso(r.get("created_at")),
            "started_at": _safe_iso(r.get("started_at")),
            "finished_at": _safe_iso(r.get("finished_at")),
        })

    return {
        "items": items,
        "total": total_count, "limit": limit, "offset": offset,
    }


# ── 内部辅助 ──


def update_session_stats(db, session_id: str):
    """根据答题记录重新计算会话统计"""
    stats = db.fetchone(
        """SELECT COUNT(*) as total,
                  SUM(CASE WHEN is_correct THEN 1 ELSE 0 END) as correct
           FROM v7_session_questions WHERE session_id = %s""",
        (session_id,),
    )
    if stats:
        total = stats["total"] or 0
        correct = stats["correct"] or 0
        wrong = total - correct
        score = round((correct / max(total, 1)) * 100, 1)
        db.execute(
            "UPDATE v7_practice_sessions SET correct_count = %s, wrong_count = %s, score = %s WHERE id = %s",
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
