"""自适应组题 + 秘书联动 + 答题历史 + 推荐 + 提示 + 内联练习

本文件仅做 HTTP 参数转换与错误映射，所有业务逻辑委托给
app.services.practice 下各子域服务。
"""
from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel

from app.domain.auth.dependencies import current_user_id
from app.services.practice.practice_question_bank import _ensure_tables
from app.services.practice.practice_adaptive import adaptive_select
from app.services.practice.practice_stats import get_recommendations
from app.services.practice.practice_service import (
    get_hint_for_question,
)
from app.services.practice.proposals import (
    get_practice_proposals,
    accept_proposal,
    dismiss_proposal,
)
from app.services.practice.answer_history import get_answer_history
from app.services.practice.inline import submit_inline_answer, get_inline_hint_for_block
from app.services.practice.standalone import submit_standalone_answer
from app.services.practice.confidence import get_confidence_report
from app.services.practice.self_explain import evaluate_self_explanation

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
    return get_practice_proposals(user_id, limit=limit)


@router.post("/secretary/proposals/{proposal_id}/accept")
async def api_secretary_accept_proposal(proposal_id: str, body: dict = None, user_id: str = Depends(current_user_id)):
    return accept_proposal(proposal_id, user_id)


@router.post("/secretary/proposals/{proposal_id}/dismiss")
async def api_secretary_dismiss_proposal(proposal_id: str, user_id: str = Depends(current_user_id)):
    return dismiss_proposal(proposal_id, user_id)


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
    return get_answer_history(
        user_id=user_id,
        question_id=question_id,
        session_id=session_id,
        limit=limit,
        offset=offset,
    )


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
    """对话内联练习 — 提交答案"""
    try:
        return await submit_inline_answer(user_id=user_id, block_id=req.block_id, answer=req.answer)
    except ValueError as e:
        raise HTTPException(404, str(e))


@router.post("/inline/hint")
async def inline_hint(req: _InlineHintRequest, user_id: str = Depends(current_user_id)):
    """对话内联练习 — 获取提示"""
    result = get_inline_hint_for_block(user_id, req.block_id)
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


@router.post("/submit")
async def submit_answer(req: _SubmitAnswerRequest, user_id: str = Depends(current_user_id)):
    """独立练习 — 提交单题答案

    路径: /api/practice/submit (与 /api/practice/sessions/{id}/submit 共用事件源)
    """
    _ensure_tables()
    try:
        return await submit_standalone_answer(
            user_id=user_id,
            session_id=req.session_id,
            question_id=req.question_id,
            answer=req.answer,
            time_spent_seconds=req.time_spent_seconds,
            hints_used=req.hints_used,
            confidence_before=req.confidence_before,
        )
    except ValueError as e:
        raise HTTPException(404, str(e))


# ──────────────────────────────────────────────
# 答题遥测（前端微行为采集）
# ──────────────────────────────────────────────


class _TelemetrySubmitRequest(BaseModel):
    telemetry_id: str
    session_id: str = ""
    question_id: str
    attempt_id: str
    raw_events: list[dict] = []
    derived: dict = {}


@router.post("/telemetry")
async def submit_practice_telemetry(
    req: _TelemetrySubmitRequest,
    user_id: str = Depends(current_user_id),
):
    """接收前端答题遥测数据，落库并发布 PracticeAnswerBehaviorRecorded。"""
    if not user_id:
        raise HTTPException(401, "请先登录")
    try:
        from app.services.practice.telemetry_service import save_telemetry
        result = save_telemetry(
            user_id=user_id,
            telemetry_id=req.telemetry_id,
            session_id=req.session_id,
            question_id=req.question_id,
            attempt_id=req.attempt_id,
            raw_events=req.raw_events,
            derived=req.derived,
        )
    except ValueError as e:
        raise HTTPException(400, str(e))
    except Exception:
        logger.exception("保存答题遥测失败")
        raise HTTPException(500, "Internal server error")
    return result


# ──────────────────────────────────────────────
# 自信度校准报告（源自 practice.py）
# ──────────────────────────────────────────────


@router.get("/confidence-report")
async def get_confidence_report_endpoint(
    user_id: str = Depends(current_user_id),
    subject: str | None = None,
    days: int = 30,
):
    """自信度校准报告：按学科的偏差趋势、均值、建议"""
    _ensure_tables()
    return get_confidence_report(user_id=user_id, subject=subject, days=days)


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
    return await evaluate_self_explanation(
        user_id=user_id,
        knowledge_node_id=req.knowledge_node_id,
        explanation_text=req.explanation_text,
        prompt_type=req.prompt_type,
    )


# ──────────────────────────────────────────────
# 统一知识状态 API（源自 practice.py）
# ──────────────────────────────────────────────


@router.get("/knowledge/state")
async def get_knowledge_state(user_id: str = Depends(current_user_id)):
    """获取统一知识状态"""
    from app.domain.knowledge import get_knowledge_query
    return get_knowledge_query().get_all_skills_summary(user_id)
