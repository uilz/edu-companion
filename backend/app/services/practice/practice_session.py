"""
练习会话管理 — 全生命周期 (门面模式)

变更:
- D3: 上下文使用 PracticeSession Pydantic 对象
- D9: submit_answer 不再写 session_questions 状态, 走 practice_attempts
- D5: analysis → explanation
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


def _get_metacognition_feedback(confidence_before, is_correct: bool) -> str:
    """根据自信度和正确性返回元认知反馈文案"""
    if confidence_before is None:
        return ""
    if confidence_before >= 3:
        if is_correct:
            return "你确实掌握了，自信是对的"
        else:
            return "⚠️ 元认知偏差：你以为掌握了但其实没有。建议重新学习推导过程。"
    else:
        if is_correct:
            return "💡 谦逊的正确：你比你以为的更懂。试着给别人讲一遍确认。"
        else:
            return "还有提升空间，继续努力"


async def _publish_practice_events(
    *,
    user_id: str,
    session_id: str,
    question_id: str,
    question: dict,
    is_correct: bool,
    user_answer,
    correct_answer,
    time_spent_seconds: int,
    hints_used: int,
) -> None:
    """发布练习答题领域事件 — 委托到 engine.publish_practice_events (SSOT 单一来源)"""
    from app.services.practice.engine import publish_practice_events
    await publish_practice_events(
        user_id=user_id,
        session_id=session_id,
        question_id=question_id,
        question=question,
        is_correct=is_correct,
        user_answer=user_answer,
        correct_answer=correct_answer,
        time_spent_seconds=time_spent_seconds,
        hints_used=hints_used,
    )


def _session_to_dict(session) -> dict:
    """将 PracticeSession 转为前端 dict (兼容 API 响应)"""
    if session is None:
        return None
    return {
        "session_id": session.id,
        "id": session.id,
        "bank_id": session.bank_id,
        "user_id": session.user_id,
        "session_type": session.session_type,
        "mode": session.mode,
        "total_count": session.total_count,
        "correct_count": session.correct_count,
        "wrong_count": session.wrong_count,
        "score": session.score,
        "status": session.status,
        "node_ids": session.cognitive_node_ids,
        "cognitive_node_ids": session.cognitive_node_ids,
        "config": session.config,
        "conv_id": session.conv_id,
        "created_at": safe_iso(session.created_at),
        "started_at": safe_iso(session.started_at),
        "finished_at": safe_iso(session.finished_at),
        "duration_seconds": session.duration_seconds,
    }


async def create_session(
    bank_id: str,
    user_id: str,
    session_type: str = "practice",
    mode: str = "adaptive",
    question_count: int = 10,
    config: Optional[dict] = None,
    exclude_ids: Optional[list[str]] = None,
    cognitive_node_ids: Optional[list[str]] = None,
    sources: Optional[dict] = None,
    question_ids: Optional[list[str]] = None,
) -> dict:
    """
    创建练习会话，支持多来源混合组卷。

    sources 配置 (可选，不传则全部从题库自适应选题):
        {
            "bank": 6,      # 从题库选题
            "errors": 2,    # 从错题本选题
            "variants": 1,  # 从已有题目生成变式
            "new": 1,       # AI 生成新题
        }
    """
    from app.infrastructure.db.database import get_db
    from app.services.practice.practice_adaptive import adaptive_select
    from app.services.practice.practice_conversation import create_practice_conversation
    db = get_db()

    cfg = {
        "mode": mode,
        "question_count": question_count,
        "cognitive_node_ids": cognitive_node_ids or [],
        "sources": sources or {"bank": question_count},
        **(config or {}),
    }

    questions = await _collect_questions_from_sources(
        bank_id=bank_id,
        user_id=user_id,
        count=question_count,
        mode=mode,
        sources=sources or {"bank": question_count},
        exclude_ids=exclude_ids,
        cognitive_node_ids=cognitive_node_ids,
    )

    # 强制包含指定题目（复习单题、错题回顾时使用）
    if question_ids:
        existing_ids = {q.get("id") for q in questions if q.get("id")}
        for qid in question_ids:
            if qid not in existing_ids:
                row = db.fetchone("SELECT * FROM questions WHERE id = %s AND deleted_at IS NULL", (qid,))
                if row:
                    questions.insert(0, dict(row))
                    existing_ids.add(qid)
        # 裁剪到目标数量
        questions = questions[:question_count]

    if not questions:
        logger.warning("无可用题目，创建空会话 bank=%s", bank_id)

    now = datetime.now().isoformat()
    session_id = f"ses_{bank_id}_{int(datetime.now().timestamp())}"
    node_ids = list(set(nid for q in questions for nid in (q.get("cognitive_node_ids") or [])))

    bank_name = ""
    try:
        bank_row = db.fetchone("SELECT name FROM question_banks WHERE id = %s", (bank_id,))
        if bank_row:
            bank_name = bank_row.get("name", "")
    except Exception:
        pass

    repo.insert_session(db, session_id, bank_id, user_id, node_ids, session_type, mode, question_count, cfg, now)
    repo.insert_session_questions(db, session_id, questions, now)

    if config and config.get("create_conversation", True):
        title = f"{bank_name or '练习'} · {mode}"
        create_practice_conversation(user_id, session_id, title, config.get("tree_node_id"))

    # 返回（移除答案和解析）
    for q in questions:
        q.pop("answer", None)
        q.pop("explanation", None)
        q.pop("analysis", None)

    return {
        "session_id": session_id,
        "id": session_id,
        "bank_id": bank_id,
        "bank_name": bank_name,
        "user_id": user_id,
        "session_type": session_type,
        "mode": mode,
        "question_count": question_count,
        "total_count": question_count,
        "status": "created",
        "questions": questions,
        "node_ids": node_ids,
        "cognitive_node_ids": node_ids,
        "config": cfg,
        "sources": sources,
        "created_at": now,
        "started_at": now,
        "finished_at": None,
        "correct_count": 0,
        "wrong_count": 0,
        "score": None,
        "duration_seconds": None,
    }


async def _collect_questions_from_sources(
    bank_id: str,
    user_id: str,
    count: int,
    mode: str,
    sources: dict,
    exclude_ids: Optional[list[str]] = None,
    cognitive_node_ids: Optional[list[str]] = None,
) -> list[dict]:
    """
    从多个来源收集题目，按 sources 配置的比例混合。

    来源:
    - bank: 从题库自适应选题
    - errors: 从错题本选题 (错最多的优先)
    - variants: 从已有题目生成变式
    - new: AI 生成新题
    """
    from app.services.practice.practice_adaptive import adaptive_select

    all_questions = []
    exclude = set(exclude_ids or [])

    # 1. 题库选题
    bank_count = sources.get("bank", 0)
    if bank_count > 0:
        bank_questions = adaptive_select(
            bank_id=bank_id,
            user_id=user_id,
            count=bank_count,
            mode=mode,
            exclude_ids=list(exclude),
            cognitive_node_ids=cognitive_node_ids,
        )
        for q in bank_questions:
            q["_source"] = "bank"
        all_questions.extend(bank_questions)
        exclude.update(q["id"] for q in bank_questions)
        logger.info("题库选题: %d", len(bank_questions))

    # 2. 错题本选题
    error_count = sources.get("errors", 0)
    if error_count > 0:
        error_questions = await _collect_from_error_book(
            bank_id=bank_id,
            user_id=user_id,
            count=error_count,
            exclude_ids=list(exclude),
            cognitive_node_ids=cognitive_node_ids,
        )
        for q in error_questions:
            q["_source"] = "errors"
        all_questions.extend(error_questions)
        exclude.update(q["id"] for q in error_questions)
        logger.info("错题选题: %d", len(error_questions))

    # 3. 变式生成
    variant_count = sources.get("variants", 0)
    if variant_count > 0:
        variant_questions = await _collect_variants(
            bank_id=bank_id,
            user_id=user_id,
            count=variant_count,
            exclude_ids=list(exclude),
            cognitive_node_ids=cognitive_node_ids,
        )
        for q in variant_questions:
            q["_source"] = "variants"
        all_questions.extend(variant_questions)
        exclude.update(q["id"] for q in variant_questions)
        logger.info("变式选题: %d", len(variant_questions))

    # 4. AI 新题
    new_count = sources.get("new", 0)
    if new_count > 0:
        new_questions = await _collect_new_questions(
            bank_id=bank_id,
            user_id=user_id,
            count=new_count,
            cognitive_node_ids=cognitive_node_ids,
        )
        for q in new_questions:
            q["_source"] = "new"
        all_questions.extend(new_questions)
        logger.info("AI 新题: %d", len(new_questions))

    # 如果指定来源不够，题库补足
    total = len(all_questions)
    if total < count:
        shortage = count - total
        logger.info("来源不足 %d 题，题库补足", shortage)
        extra = adaptive_select(
            bank_id=bank_id,
            user_id=user_id,
            count=shortage,
            mode=mode,
            exclude_ids=list(exclude),
            cognitive_node_ids=cognitive_node_ids,
        )
        for q in extra:
            q["_source"] = "bank"
        all_questions.extend(extra)

    return all_questions[:count]


def _collect_from_error_book(
    bank_id: str,
    user_id: str,
    count: int,
    exclude_ids: list[str],
    cognitive_node_ids: Optional[list[str]] = None,
) -> list[dict]:
    """从错题本选取错题（错最多的优先）"""
    from app.infrastructure.db.database import get_db
    db = get_db()

    conditions = ["att.user_id = %s", "att.is_wrong = true", "q.bank_id = %s"]
    params = [user_id, bank_id]

    if cognitive_node_ids:
        conditions.append("q.cognitive_node_ids && %s")
        params.append(cognitive_node_ids)

    if exclude_ids:
        placeholders = ",".join(["%s"] * len(exclude_ids))
        conditions.append(f"att.question_id NOT IN ({placeholders})")
        params.extend(exclude_ids)

    where = " AND ".join(conditions)

    rows = db.fetchall(
        f"""SELECT att.question_id, q.bank_id, q.stem, q.options, q.question_type,
                  q.difficulty, q.cognitive_node_ids,
                  COUNT(*) as wrongs
           FROM practice_attempts att
           JOIN questions q ON att.question_id = q.id AND q.deleted_at IS NULL
           WHERE {where}
           GROUP BY att.question_id, q.bank_id, q.stem, q.options, q.question_type,
                    q.difficulty, q.cognitive_node_ids
           ORDER BY wrongs DESC
           LIMIT %s""",
        tuple(params) + (count,),
    )

    result = []
    for r in rows:
        options = r.get("options") or []
        if isinstance(options, str):
            try:
                options = json.loads(options)
            except Exception:
                options = []
        result.append({
            "id": r["question_id"],
            "bank_id": r["bank_id"],
            "question_type": r["question_type"],
            "stem": r["stem"],
            "options": options,
            "difficulty": r.get("difficulty", 3),
            "cognitive_node_ids": r.get("cognitive_node_ids") or [],
            "_wrongs": r.get("wrongs", 0),
        })
    return result


async def _collect_variants(
    bank_id: str,
    user_id: str,
    count: int,
    exclude_ids: list[str],
    cognitive_node_ids: Optional[list[str]] = None,
) -> list[dict]:
    """从题库现有题目生成变式"""
    from app.infrastructure.db.database import get_db
    db = get_db()

    # 随机选一道题做变式
    conditions = ["q.bank_id = %s", "q.deleted_at IS NULL", "q.status = 'active'"]
    params = [bank_id]

    if cognitive_node_ids:
        conditions.append("q.cognitive_node_ids && %s")
        params.append(cognitive_node_ids)

    if exclude_ids:
        placeholders = ",".join(["%s"] * len(exclude_ids))
        conditions.append(f"q.id NOT IN ({placeholders})")
        params.extend(exclude_ids)

    where = " AND ".join(conditions)

    row = db.fetchone(
        f"SELECT id FROM questions WHERE {where} ORDER BY RANDOM() LIMIT 1",
        tuple(params),
    )

    if not row:
        return []

    try:
        from app.services.practice.practice_question_gen import generate_similar
        variants = await generate_similar(
            question_id=row["id"],
            user_id=user_id,
            count=min(count, 3),
        )
        result = []
        for v in variants:
            result.append({
                "id": v["id"],
                "bank_id": bank_id,
                "question_type": v.get("question_type", "single"),
                "stem": v.get("stem", ""),
                "options": v.get("options", []),
                "difficulty": v.get("difficulty", 3),
                "cognitive_node_ids": v.get("cognitive_node_ids") or [],
            })
        return result
    except Exception as e:
        logger.warning("变式生成失败: %s", e)
        return []


async def _collect_new_questions(
    bank_id: str,
    user_id: str,
    count: int,
    cognitive_node_ids: Optional[list[str]] = None,
) -> list[dict]:
    """AI 生成新题"""
    try:
        from app.services.practice.practice_question_gen import generate_and_save

        skill_id = cognitive_node_ids[0] if cognitive_node_ids else ""

        subject = ""
        try:
            from app.infrastructure.db.database import get_db
            db = get_db()
            bank = db.fetchone("SELECT metadata FROM question_banks WHERE id = %s", (bank_id,))
            if bank:
                meta = bank.get("metadata") or {}
                if isinstance(meta, str):
                    import json as _j
                    meta = _j.loads(meta)
                subject = meta.get("subject", "") or ""
        except Exception:
            pass
        if not subject:
            subject = "通用"

        saved = await generate_and_save(
            bank_id=bank_id,
            user_id=user_id,
            subject=subject,
            skill_id=skill_id,
            count=min(count, 5),
            content_type="choice",
        )
        result = []
        for q in saved:
            result.append({
                "id": q["id"],
                "bank_id": bank_id,
                "question_type": q.get("question_type", "single"),
                "stem": q.get("stem", ""),
                "options": q.get("options", []),
                "difficulty": q.get("difficulty", 3),
                "cognitive_node_ids": q.get("cognitive_node_ids") or [],
            })
        return result
    except Exception as e:
        logger.warning("AI 新题生成失败: %s", e)
        return []


def get_session(session_id: str, user_id: str) -> Optional[dict]:
    """获取会话详情 (含答题状态, D9: 从 practice_attempts 聚合)"""
    from app.infrastructure.db.database import get_db
    db = get_db()

    session = repo.get_session(db, session_id, user_id)
    if not session:
        return None

    # 获取题目列表 (无状态 session_questions)
    sq_rows = repo.get_session_questions(db, session_id)
    question_ids = [r["question_id"] for r in sq_rows]

    # 获取答题状态 (从 practice_attempts 聚合)
    question_map = {r["question_id"]: r for r in sq_rows}
    if question_ids:
        attempt_rows = db.fetchall(
            """SELECT question_id, user_answer, is_correct, time_spent_seconds
               FROM practice_attempts WHERE session_id = %s AND question_id = ANY(%s)""",
            (session_id, question_ids),
        )
        attempt_map = {r["question_id"]: r for r in attempt_rows}
    else:
        attempt_map = {}

    questions = db.fetchall(
        """SELECT q.id, q.question_type, q.stem, q.options, q.explanation,
                  q.difficulty, q.source
           FROM questions q
           WHERE q.id = ANY(%s) AND q.deleted_at IS NULL""",
        (question_ids,),
    )
    # 按 session_questions 排序
    q_data = {q["id"]: q for q in questions}
    ordered = []
    for sq in sq_rows:
        qid = sq["question_id"]
        if qid in q_data:
            q = dict(q_data[qid])
            q["options"] = safe_json(q.get("options"), [])
            q["sort_order"] = sq.get("sort_order", 0)
            # 注入答题状态
            att = attempt_map.get(qid)
            answered = att is not None
            q["answered"] = answered
            q["correct"] = att["is_correct"] if att else None
            q["user_answer"] = safe_json(att["user_answer"], None) if att else None
            q["is_correct"] = att["is_correct"] if att else None
            q["time_spent"] = att["time_spent_seconds"] if att else 0
            q["hints_used"] = 0
            ordered.append(q)

    result = _session_to_dict(session)
    result["questions"] = ordered
    return result


def submit_answer(
    session_id: str,
    question_id: str,
    user_id: str,
    user_answer: Optional[list] = None,
    time_spent: int = 0,
    hints_used: int = 0,
    confidence_before: int = None,
) -> dict:
    """
    提交答题 (D9: session_questions 不再存状态, 仅 practice_attempts).

    流程:
    1. 验证会话 & 题目归属
    2. 判对错
    3. 写入 practice_attempts (含错因分析)
    4. 更新会话统计
    5. 认知节点联动
    """
    from app.infrastructure.db.database import get_db
    from app.domain.cognitive import get_repo
    db = get_db()

    # 1. 验证 (D9: 从 practice_attempts 检查是否已答)
    #    先校验 session 归属当前 user (防止跨用户提交)
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
        # 已答过，返回之前的结果而不是报错
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
    error_analysis = {}
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

    # 4. 写入答题记录 (D9: 唯一记录源)
    repo.insert_attempt(db, session_id, question_id, user_id, is_correct, user_answer or [],
                         time_spent, hints_used, error_pattern, error_analysis, confidence_before, now)

    # 5. 更新会话统计
    repo.update_session_stats(db, session_id)

    # 6. 认知节点联动
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

    # 7. 发布领域事件 (SSOT: shared/events.py)
    #   - AnswerSubmitted  → analytics/habit/knowledge 3 个订阅者
    #   - ErrorRecorded    → knowledge/media 2 个订阅者
    #   - PracticeSubmitted → cognitive service
    # publish_practice_events 是 async; submit_answer 是 sync (FastAPI sync route);
    # 用 asyncio 异步 fire-and-forget 让事件真正进入总线。
    try:
        import asyncio
        from app.services.practice.engine import publish_practice_events
        coro = publish_practice_events(
            user_id=user_id,
            session_id=session_id,
            question_id=question_id,
            question=dict(question) if question else {},
            is_correct=is_correct,
            user_answer=user_answer or [],
            correct_answer=correct_answer,
            time_spent_seconds=time_spent,
            hints_used=hints_used,
        )
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # FastAPI 已经在 event loop 中 → create_task
                asyncio.ensure_future(coro)
            else:
                loop.run_until_complete(coro)
        except RuntimeError:
            # 无 event loop (线程上下文)
            try:
                asyncio.run(coro)
            except Exception:
                pass
    except Exception as e:
        logger.debug("Practice 事件发布失败: %s", e)

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
    }


def start_session(session_id: str, user_id: str) -> Optional[dict]:
    from app.infrastructure.db.database import get_db
    db = get_db()

    session = repo.get_session(db, session_id, user_id)
    if not session:
        return None
    if not validate_transition(session.status, "started"):
        return None

    now = datetime.now().isoformat()
    repo.update_session_status(db, session_id, "started", {"started_at": now})
    return {"session_id": session_id, "id": session_id, "status": "started", "started_at": now}


def pause_session(session_id: str, user_id: str) -> Optional[dict]:
    from app.infrastructure.db.database import get_db
    db = get_db()

    session = repo.get_session(db, session_id, user_id)
    if not session:
        return None
    if not validate_transition(session.status, "paused"):
        return None

    repo.update_session_status(db, session_id, "paused")
    return {"session_id": session_id, "id": session_id, "status": "paused"}


def resume_session(session_id: str, user_id: str) -> Optional[dict]:
    from app.infrastructure.db.database import get_db
    db = get_db()

    session = repo.get_session(db, session_id, user_id)
    if not session:
        return None
    if not validate_transition(session.status, "started"):
        return None

    repo.update_session_status(db, session_id, "started")
    return {"session_id": session_id, "id": session_id, "status": "started"}


def cancel_session(session_id: str, user_id: str) -> Optional[dict]:
    from app.infrastructure.db.database import get_db
    db = get_db()

    session = repo.get_session(db, session_id, user_id)
    if not session:
        return None
    if not validate_transition(session.status, "cancelled"):
        return None

    repo.update_session_status(db, session_id, "cancelled")
    return {"session_id": session_id, "id": session_id, "status": "cancelled"}


def get_session_result(session_id: str, user_id: str) -> Optional[dict]:
    from app.infrastructure.db.database import get_db
    db = get_db()

    session = repo.get_session(db, session_id, user_id)
    if not session:
        return None

    stats = repo.update_session_stats(db, session_id)
    return {
        "session_id": session.id,
        "id": session.id,
        "status": session.status,
        "score": stats["score"],
        "total": stats["total"],
        "correct": stats["correct"],
        "wrong": stats["wrong"],
        "created_at": safe_iso(session.created_at),
        "started_at": safe_iso(session.started_at),
        "finished_at": safe_iso(session.finished_at),
    }


def complete_session(session_id: str, user_id: str) -> Optional[dict]:
    from app.infrastructure.db.database import get_db
    from app.services.practice.practice_conversation import complete_practice_conversation
    db = get_db()

    session = repo.get_session(db, session_id, user_id)
    if not session:
        return None
    if not validate_transition(session.status, "completed"):
        return None

    now = datetime.now().isoformat()
    stats = repo.update_session_stats(db, session_id)
    repo.update_session_status(db, session_id, "completed", {"finished_at": now})

    try:
        complete_practice_conversation(session_id, user_id, stats)
    except Exception as e:
        logger.debug("练习对话完成失败: %s", e)

    # 发布 SessionCompleted 事件 (SSOT: shared/events.py + engine.publish_session_completed)
    #   订阅者: session_bridge.on_session_completed / planning_service / secretary / knowledge_tree
    try:
        from app.services.practice.engine import publish_session_completed
        import asyncio
        total = stats.get("total", 0) or 0
        correct = stats.get("correct", 0) or 0
        accuracy = (correct / total) if total > 0 else 0.0
        # 时长 (秒→分钟)
        duration_seconds = 0
        if session.started_at and session.finished_at:
            try:
                start = datetime.fromisoformat(session.started_at)
                end = datetime.fromisoformat(now)
                duration_seconds = max(0, (end - start).total_seconds())
            except Exception:
                pass
        coro = publish_session_completed(
            user_id=user_id,
            session_id=session_id,
            total_questions=total,
            correct_count=correct,
            accuracy=accuracy,
            duration_minutes=duration_seconds / 60.0,
        )
        # event_bus.publish 是 async; 在同步上下文用 asyncio.create_task
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                asyncio.create_task(coro)
            else:
                loop.run_until_complete(coro)
        except RuntimeError:
            # 无 event loop (如线程上下文), 走 fire-and-forget
            asyncio.run(coro)
    except Exception as e:
        logger.debug("SessionCompleted 事件发布失败: %s", e)

    return {
        "session_id": session.id,
        "id": session.id,
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
    session_type: str = None,
    mode: str = None,
    date_from: str = None,
    date_to: str = None,
    score_min: float = None,
    score_max: float = None,
    limit: int = 50,
    offset: int = 0,
) -> dict:
    """列出用户练习会话 → {items, total, has_more} for API"""
    from app.infrastructure.db.database import get_db
    db = get_db()
    sessions, total = repo.list_sessions(
        db, user_id, bank_id, status, session_type,
        mode=mode, date_from=date_from, date_to=date_to,
        score_min=score_min, score_max=score_max,
        limit=limit, offset=offset,
    )
    items = [_session_to_dict(s) for s in sessions]
    return {
        "items": items,
        "total": total,
        "has_more": (offset + len(items)) < total,
        "next_cursor": None,
    }


def delete_session(session_id: str, user_id: str) -> bool:
    from app.infrastructure.db.database import get_db
    db = get_db()
    return repo.delete_session(db, session_id, user_id)