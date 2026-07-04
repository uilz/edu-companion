"""自适应组题 + 秘书联动 + 答题历史 + 推荐 + 提示 + 内联练习"""
from __future__ import annotations

import json as _json
import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel

from app.domain.auth.dependencies import current_user_id
from app.services.practice.practice_question_bank import _ensure_tables
from app.services.practice.practice_adaptive import adaptive_select
from app.services.practice.practice_stats import get_recommendations
from app.services.practice.engine import (
    get_hint_for_question,
    get_inline_hint,
    build_reply_text,
    update_cognitive_after_practice,
)

logger = logging.getLogger(__name__)
router = APIRouter()


# ═══════════════════════════════════════════════
# 自适应组题
# ═══════════════════════════════════════════════

@router.post("/adaptive/select")
async def api_adaptive_select(body: dict, user_id: str = Depends(current_user_id)):
    _ensure_tables()
    bank_id = body.get("bank_id", "")
    if not bank_id:
        raise HTTPException(400, "bank_id 不能为空")
    count = max(1, min(50, int(body.get("count", 10))))
    questions = adaptive_select(
        bank_id=bank_id,
        user_id=user_id,
        count=count,
        mode=body.get("mode", "adaptive"),
        cognitive_node_ids=body.get("cognitive_node_ids"),
        exclude_ids=body.get("exclude_ids"),
    )
    return {
        "selected": len(questions),
        "questions": questions,
        "params": {
            "bank_id": bank_id,
            "count": count,
            "mode": body.get("mode", "adaptive"),
        },
    }


# ═══════════════════════════════════════════════
# 秘书联动提案
# ═══════════════════════════════════════════════

@router.get("/secretary/proposals")
async def api_practice_secretary_proposals(
    user_id: str = Depends(current_user_id),
    limit: int = 5,
):
    from app.infrastructure.db.proposal_store import ProposalStore
    store = ProposalStore()
    proposals = store.get_pending_proposals(user_id, limit=limit)
    practice_types = {"practice_error_alert", "practice_mastery_stuck", "practice_review_reminder", "practice_reflection"}
    filtered = [p for p in proposals if p.action_type in practice_types]
    result = []
    for p in filtered:
        result.append({
            "id": p.id,
            "emoji": p.emoji or "💡",
            "title": p.title,
            "description": p.description,
            "action_type": p.action_type,
            "payload": p.payload,
            "priority": p.priority,
            "created_at": p.created_at,
        })
    return {"proposals": result[:limit], "total": len(filtered)}


@router.post("/secretary/proposals/{proposal_id}/accept")
async def api_secretary_accept_proposal(proposal_id: str, body: dict = None, user_id: str = Depends(current_user_id)):
    from app.infrastructure.db.proposal_store import ProposalStore
    store = ProposalStore()
    store.update_status(proposal_id, "accepted", user_id)
    return {"status": "accepted"}


@router.post("/secretary/proposals/{proposal_id}/dismiss")
async def api_secretary_dismiss_proposal(proposal_id: str, user_id: str = Depends(current_user_id)):
    from app.infrastructure.db.proposal_store import ProposalStore
    store = ProposalStore()
    store.update_status(proposal_id, "dismissed", user_id)
    return {"status": "dismissed"}


# ═══════════════════════════════════════════════
# 答题历史
# ═══════════════════════════════════════════════

@router.get("/history/answers")
async def api_answer_history(
    user_id: str = Depends(current_user_id),
    question_id: Optional[str] = None,
    session_id: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
):
    _ensure_tables()
    from app.infrastructure.db.database import get_db
    db = get_db()

    conditions = ["a.user_id = %s"]
    params: list = [user_id]

    if question_id:
        conditions.append("a.question_id = %s")
        params.append(question_id)
    if session_id:
        conditions.append("a.session_id = %s")
        params.append(session_id)

    where = " AND ".join(conditions)

    total = db.fetchone(
        f"SELECT COUNT(*) as cnt FROM practice_attempts a WHERE {where}",
        tuple(params),
    )
    total_count = total["cnt"] if total else 0

    rows = db.fetchall(
        f"""SELECT a.id, a.session_id, a.question_id, a.user_answer,
                   a.is_correct, a.time_spent_seconds, a.is_wrong,
                   a.wrong_count, a.consecutive_correct, a.cognitive_node_ids,
                   a.created_at,
                   q.stem, q.options, q.question_type, q.difficulty, q.answer
            FROM practice_attempts a
            LEFT JOIN questions q ON a.question_id = q.id
            WHERE {where}
            ORDER BY a.created_at DESC
            LIMIT %s OFFSET %s""",
        tuple(params + [min(limit, 200), max(offset, 0)]),
    )

    items = []
    for r in rows:
        items.append({
            "attempt_id": r["id"],
            "session_id": r["session_id"],
            "question_id": r["question_id"],
            "user_answer": _json.loads(r["user_answer"]) if isinstance(r["user_answer"], str) else r["user_answer"],
            "is_correct": r["is_correct"],
            "time_spent_seconds": r.get("time_spent_seconds", 0),
            "is_wrong": r.get("is_wrong", False),
            "wrong_count": r.get("wrong_count", 0),
            "consecutive_correct": r.get("consecutive_correct", 0),
            "cognitive_node_ids": r.get("cognitive_node_ids") or [],
            "created_at": r["created_at"].isoformat() if hasattr(r["created_at"], "isoformat") else str(r["created_at"]),
            "question_stem": (r.get("stem") or "")[:120],
            "question_type": r.get("question_type", ""),
            "difficulty": r.get("difficulty", 3),
            "correct_answer": _json.loads(r["answer"]) if isinstance(r.get("answer"), str) else (r.get("answer") or []),
        })

    return {
        "items": items,
        "total": total_count,
        "limit": limit,
        "offset": offset,
    }


# ═══════════════════════════════════════════════
# 练习推荐
# ═══════════════════════════════════════════════

@router.get("/recommendations")
async def api_practice_recommendations(
    user_id: str = Depends(current_user_id),
    limit: int = 5,
):
    """综合推荐：薄弱知识点 + 待复习题目 + 推荐题库 + 学习建议"""
    _ensure_tables()
    return get_recommendations(user_id, limit=min(limit, 20))


# ═══════════════════════════════════════════════
# 提示 + 内联练习
# ═══════════════════════════════════════════════


class _HintRequest(BaseModel):
    question_id: str
    current_level: int = 0


class _InlineAnswerRequest(BaseModel):
    block_id: str
    answer: str


class _InlineHintRequest(BaseModel):
    block_id: str


@router.post("/hint")
async def get_hint(req: _HintRequest):
    """获取提示"""
    result = get_hint_for_question(req.question_id, req.current_level)
    if result is None:
        raise HTTPException(status_code=404, detail="Question not found")
    return result


@router.post("/inline/answer")
async def inline_answer(req: _InlineAnswerRequest, user_id: str = Depends(current_user_id)):
    """对话内联练习 — 提交答案，读取 response_block 内容校验"""
    from app.services.common import get_data_repo
    from shared.knowledge_trace import get_cognitive_state
    from shared.constants import get_mastery_label

    data = get_data_repo().load(user_id)
    block = data.response_blocks.get(req.block_id)
    if not block:
        raise HTTPException(404, "Practice block not found")

    content = block.content or {}
    correct_answer = content.get("correct_answer", "").strip().upper()
    explanation = content.get("explanation") or content.get("reply_expected", "") or ""
    skill_id = content.get("skill_id", "")
    is_correct = req.answer.strip().upper() == correct_answer

    # 更新知识状态
    knowledge_update = {}
    if skill_id:
        state = get_cognitive_state(user_id, skill_id)
        cog = update_cognitive_after_practice(
            user_id=user_id,
            skill_id=skill_id,
            is_correct=is_correct,
        )
        knowledge_update = {
            "skill_id": skill_id,
            "p_known_before": cog["p_before"],
            "p_known_after": cog["p_after"],
            "mastery_level": get_mastery_label(state.p_known, state.attempt_count),
            "cognitive_proficiency": cog["cognitive_proficiency"],
        }

    correct_label = content.get("correct_answer", "")
    reply_text = build_reply_text(is_correct, correct_label, explanation)

    return {
        "is_correct": is_correct,
        "reply_text": reply_text,
        "knowledge_update": knowledge_update,
    }


@router.post("/inline/hint")
async def inline_hint(req: _InlineHintRequest, user_id: str = Depends(current_user_id)):
    """对话内联练习 — 获取提示"""
    result = get_inline_hint(req.block_id, user_id)
    if result is None:
        raise HTTPException(404, "Practice block not found")
    return result


# ──────────────────────────────────────────────
# 独立练习答题提交（源自 practice.py）
# ──────────────────────────────────────────────


class _SubmitAnswerRequest(BaseModel):
    session_id: str
    question_id: str
    answer: str
    time_spent_seconds: float = 0.0
    hints_used: int = 0
    confidence_before: int | None = None


def _get_metacognition_feedback(confidence_before: int | None, is_correct: bool) -> str:
    if confidence_before is None:
        return ""
    if confidence_before >= 3:
        if is_correct:
            return "你确实掌握了，自信是对的"
        return "⚠️ 元认知偏差：你以为掌握了但其实没有。建议重新学习推导过程。"
    else:
        if is_correct:
            return "💡 谦逊的正确：你比你以为的更懂。试着给别人讲一遍确认。"
        return "还有提升空间，继续努力"


@router.post("/submit")
async def submit_answer(req: _SubmitAnswerRequest, user_id: str = Depends(current_user_id)):
    """独立练习 — 提交单题答案

    路径: /api/practice/submit (与 /api/practice/sessions/{id}/submit 共用逻辑)
    """
    from app.infrastructure.db.database import get_db
    from app.services.practice.practice_service import check_answer
    from app.services.practice.engine import update_cognitive_after_practice, record_attempt, publish_practice_events
    from app.services.practice.practice_session import _get_metacognition_feedback

    db = get_db()
    row = db.fetchone("SELECT * FROM questions WHERE id = %s", (req.question_id,))
    if not row:
        raise HTTPException(status_code=404, detail="Question not found")

    # 校验 session 归属 (跨用户提交防护)
    if req.session_id:
        from app.services.practice.session_repository import get_session
        owner = get_session(db, req.session_id, user_id)
        if not owner:
            raise HTTPException(status_code=404, detail="Session not found or not owned by user")

    correct_answer = (row.get("answer") or "").strip()
    is_correct = check_answer(req.answer, correct_answer)
    explanation = row.get("analysis", "") or row.get("explanation", "")
    skill_id = row.get("skill_id", "")

    knowledge_update = None
    if skill_id:
        cog = update_cognitive_after_practice(
            user_id=user_id,
            skill_id=skill_id,
            is_correct=is_correct,
            latency_ms=int(req.time_spent_seconds * 1000),
            confidence_before=req.confidence_before,
        )
        knowledge_update = {
            "skill_id": skill_id,
            "p_known_before": round(cog["p_before"], 4),
            "p_known_after": round(cog["p_after"], 4),
            "mastery_level": cog["mastery_label"],
        }

    record_attempt(
        user_id=user_id,
        session_id=req.session_id,
        question_id=req.question_id,
        answer=req.answer,
        is_correct=is_correct,
        time_spent_seconds=req.time_spent_seconds,
        hints_used=req.hints_used,
        confidence_before=req.confidence_before,
    )

    # 发布领域事件 (SSOT = engine.publish_practice_events)
    await publish_practice_events(
        user_id=user_id,
        session_id=req.session_id,
        question_id=req.question_id,
        question=dict(row) if not isinstance(row, dict) else row,
        is_correct=is_correct,
        user_answer=req.answer,
        correct_answer=correct_answer,
        time_spent_seconds=int(req.time_spent_seconds),
        hints_used=req.hints_used,
    )

    return {
        "is_correct": is_correct,
        "correct_answer": correct_answer,
        "explanation": explanation,
        "knowledge_update": knowledge_update,
        "metacognition_feedback": _get_metacognition_feedback(req.confidence_before, is_correct),
    }


# ──────────────────────────────────────────────
# 自信度校准报告（源自 practice.py）
# ──────────────────────────────────────────────


@router.get("/confidence-report")
async def get_confidence_report(
    user_id: str = Depends(current_user_id),
    subject: str | None = None,
    days: int = 30,
):
    """自信度校准报告：按学科的偏差趋势、均值、建议"""
    from datetime import datetime, timedelta
    from app.infrastructure.db.database import get_db

    db = get_db()
    cutoff = (datetime.now() - timedelta(days=days)).isoformat()

    query = """SELECT pa.confidence_before, pa.is_correct, pa.created_at,
                      COALESCE(q.metadata->>'subject', 'general') as subject
               FROM practice_attempts pa
               LEFT JOIN questions q ON q.id = pa.question_id
               WHERE pa.user_id = %s
                 AND pa.confidence_before IS NOT NULL
                 AND pa.created_at >= %s
               ORDER BY pa.created_at DESC"""
    rows = db.fetchall(query, (user_id, cutoff))

    if not rows:
        return {
            "user_id": user_id,
            "days": days,
            "overall_bias": 0,
            "by_subject": [],
            "suggestion": "暂无自信度数据。开始练习时选择自信度，系统将为你提供校准分析。",
        }

    by_subject: dict[str, list[dict]] = {}
    for r in rows:
        subj = r.get("subject", "general") or "general"
        cb = r.get("confidence_before")
        ic = r.get("is_correct", False)
        if subj not in by_subject:
            by_subject[subj] = []
        by_subject[subj].append({
            "confidence_before": cb,
            "is_correct": ic,
            "gap": cb - (4 if ic else 0),
        })

    if subject and subject in by_subject:
        subjects_to_report = {subject: by_subject[subject]}
    else:
        subjects_to_report = by_subject

    subject_results = []
    all_gaps = []

    for subj, items in sorted(subjects_to_report.items()):
        gaps = [it["gap"] for it in items]
        all_gaps.extend(gaps)
        avg_gap = sum(gaps) / len(gaps) if gaps else 0

        subject_results.append({
            "subject": subj,
            "sample_count": len(items),
            "mean_bias": round(avg_gap, 2),
            "direction": "overconfident" if avg_gap > 1 else ("underconfident" if avg_gap < -1 else "accurate"),
        })

    overall_bias = round(sum(all_gaps) / len(all_gaps), 2) if all_gaps else 0

    if overall_bias > 1.5:
        suggestion = "你有较明显的过度自信倾向，建议多做检验性练习，确认理解深度后再下结论。"
    elif overall_bias < -1.5:
        suggestion = "你往往低估自己，实际掌握度比预想高。建议尝试给别人讲解，增强信心。"
    elif abs(overall_bias) <= 0.5:
        suggestion = "你的自我评估非常准确，元认知能力优秀！继续保持。"
    else:
        suggestion = "自信度校准良好，略有偏差，继续关注。"

    return {
        "user_id": user_id,
        "days": days,
        "overall_bias": overall_bias,
        "by_subject": subject_results,
        "suggestion": suggestion,
    }


# ──────────────────────────────────────────────
# 自我解释评估（源自 practice.py）
# ──────────────────────────────────────────────


class _SelfExplainRequest(BaseModel):
    explanation_text: str
    knowledge_node_id: str
    prompt_type: str = "retell"


@router.post("/self-explain")
async def evaluate_self_explain(req: _SelfExplainRequest, user_id: str = Depends(current_user_id)):
    """评估学生的自我解释质量，结果写入 CognitiveNode"""
    import json, time
    from app.domain.cognitive import get_repo
    from app.domain.cognitive.models import Metacognition

    repo = get_repo()
    node = repo.get_node(req.knowledge_node_id, user_id)
    concept_name = node.label if node else req.knowledge_node_id

    evaluation_prompt = f"""你是一个学习评估助手。
学生刚学习了「{concept_name}」。现在他用自己话做了如下解释：
「{req.explanation_text}」
请评估：
1. 准确性（A/B/C）——包含重大错误吗？
2. 完整性（完整/部分/缺失核心）——抓住了关键点吗？
3. 清晰度（清晰/模糊/混乱）——容易理解吗？
4. 一句话反馈（告诉学生哪里说得好、哪里可以改进）
输出格式（严格 JSON）：{{ "accuracy": "A|B|C", "completeness": "完整|部分|缺失核心", "clarity": "清晰|模糊|混乱", "feedback": "一句话反馈" }}"""

    from app.infrastructure.llm.llm_service import llm_service
    try:
        raw = await llm_service.generate(
            messages=[{"role": "user", "content": evaluation_prompt}],
            task_type="explain",
            temperature=0.3,
            max_tokens=512,
        )
        clean = raw.strip()
        if clean.startswith("```"):
            clean = clean.split("```")[1]
            if clean.startswith("json"):
                clean = clean[4:]
        result = json.loads(clean.strip())
    except Exception as e:
        logger.warning(f"LLM 自我解释评估失败: {e}, raw={raw if 'raw' in dir() else 'N/A'}")
        result = {"accuracy": "B", "completeness": "部分", "clarity": "模糊", "feedback": "评估暂不可用，请稍后重试"}

    try:
        node = repo.get_node(req.knowledge_node_id, user_id)
        if node:
            node.deep_processing.task_instances.append({
                "type": "self_explain",
                "prompt_type": req.prompt_type,
                "explanation_text": req.explanation_text[:500],
                "result": result,
                "timestamp": time.time(),
            })
            accuracy_score = {"A": 0.9, "B": 0.6, "C": 0.3}.get(result.get("accuracy", "B"), 0.6)
            completeness_score = {"完整": 0.9, "部分": 0.5, "缺失核心": 0.2}.get(result.get("completeness", "部分"), 0.5)
            clarity_score = {"清晰": 0.9, "模糊": 0.5, "混乱": 0.2}.get(result.get("clarity", "模糊"), 0.5)
            overall = (accuracy_score + completeness_score + clarity_score) / 3

            old_meta = node.metacognition
            new_calibration = old_meta.calibration_error * 0.7 + abs(old_meta.self_assessment - overall) * 0.3
            node.metacognition = Metacognition(
                self_assessment=overall,
                calibration_error=round(new_calibration, 4),
                direction="accurate" if new_calibration < 0.3 else (
                    "overconfident" if overall > old_meta.self_assessment else "underconfident"
                ),
            )
            repo.upsert_node(node, user_id)
    except Exception as e:
        logger.warning(f"写入 CognitiveNode 失败: {e}")

    return {
        "accuracy": result.get("accuracy", "B"),
        "completeness": result.get("completeness", "部分"),
        "clarity": result.get("clarity", "模糊"),
        "feedback": result.get("feedback", ""),
        "concept_name": concept_name,
    }


# ──────────────────────────────────────────────
# 统一知识状态 API（源自 practice.py）
# ──────────────────────────────────────────────


@router.get("/knowledge/state")
async def get_knowledge_state(user_id: str = Depends(current_user_id)):
    """获取统一知识状态"""
    from app.domain.knowledge import get_knowledge_query
    return get_knowledge_query().get_all_skills_summary(user_id)
