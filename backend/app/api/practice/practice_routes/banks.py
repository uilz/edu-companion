"""题库管理 — Bank CRUD + Question CRUD + Resolve"""
from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Query, Depends

from app.domain.auth.dependencies import current_user_id
from app.services.practice.practice_question_crud import (
    add_question, update_question, delete_question,
    toggle_favorite, toggle_slash, batch_import_questions,
)
from app.services.practice.practice_question_bank import (
    _ensure_tables, list_banks, get_bank, create_bank, update_bank, delete_bank,
    list_questions, get_question, resolve_bank_for_conversation, resolve_bank_for_node,
)

logger = logging.getLogger(__name__)
router = APIRouter()


# ═══════════════════════════════════════════════
# 题库管理
# ═══════════════════════════════════════════════

@router.get("/banks")
async def api_list_banks(user_id: str = Depends(current_user_id)):
    _ensure_tables()
    return list_banks(user_id)


@router.post("/banks")
async def api_create_bank(body: dict, user_id: str = Depends(current_user_id)):
    _ensure_tables()
    name = body.get("name", "").strip()
    if not name:
        raise HTTPException(400, "题库名称不能为空")
    return create_bank(
        user_id=user_id,
        name=name,
        description=body.get("description", ""),
        ref_node_id=body.get("ref_node_id"),
        ref_node_level=body.get("ref_node_level"),
    )


@router.get("/banks/{bank_id}")
async def api_get_bank(bank_id: str, user_id: str = Depends(current_user_id)):
    _ensure_tables()
    bank = get_bank(bank_id, user_id)
    if not bank:
        raise HTTPException(404, "题库不存在")
    return bank


@router.delete("/banks/{bank_id}")
async def api_delete_bank(bank_id: str, user_id: str = Depends(current_user_id)):
    _ensure_tables()
    ok = delete_bank(bank_id, user_id)
    if not ok:
        raise HTTPException(404, "题库不存在")
    return {"deleted": bank_id}


@router.patch("/banks/{bank_id}")
async def api_update_bank(bank_id: str, body: dict, user_id: str = Depends(current_user_id)):
    _ensure_tables()
    result = update_bank(
        bank_id=bank_id, user_id=user_id,
        name=body.get("name"),
        description=body.get("description"),
    )
    if not result:
        raise HTTPException(404, "题库不存在")
    return result


# ═══════════════════════════════════════════════
# 题目管理
# ═══════════════════════════════════════════════

@router.get("/banks/{bank_id}/questions")
async def api_list_questions(
    bank_id: str,
    user_id: str = Depends(current_user_id),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    question_type: Optional[str] = None,
    status: Optional[str] = None,
    cognitive_node_id: Optional[str] = None,
):
    _ensure_tables()
    return list_questions(
        bank_id, user_id,
        page=page, page_size=page_size,
        question_type=question_type,
        status=status,
        cognitive_node_id=cognitive_node_id,
    )


@router.post("/banks/{bank_id}/questions")
async def api_add_question(bank_id: str, body: dict, user_id: str = Depends(current_user_id)):
    _ensure_tables()
    stem = body.get("stem", "").strip()
    if not stem:
        raise HTTPException(400, "题干不能为空")
    answer = body.get("answer", [])
    if not answer:
        raise HTTPException(400, "答案不能为空")
    return add_question(
        bank_id=bank_id,
        user_id=user_id,
        question_type=body.get("question_type", "single"),
        stem=stem,
        answer=answer,
        options=body.get("options"),
        analysis=body.get("analysis", ""),
        difficulty=body.get("difficulty", 3),
        cognitive_node_ids=body.get("cognitive_node_ids"),
        source=body.get("source", "manual"),
        metadata=body.get("metadata"),
    )


@router.get("/questions/{question_id}")
async def api_get_question(question_id: str, user_id: str = Depends(current_user_id)):
    _ensure_tables()
    q = get_question(question_id, user_id)
    if not q:
        raise HTTPException(404, "题目不存在")
    return q


@router.patch("/questions/{question_id}")
async def api_update_question(question_id: str, body: dict, user_id: str = Depends(current_user_id)):
    _ensure_tables()
    q = update_question(question_id, user_id, **body)
    if not q:
        raise HTTPException(404, "题目不存在")
    return q


@router.delete("/questions/{question_id}")
async def api_delete_question(question_id: str, user_id: str = Depends(current_user_id)):
    _ensure_tables()
    ok = delete_question(question_id, user_id)
    if not ok:
        raise HTTPException(404, "题目不存在")
    return {"deleted": question_id}


@router.post("/questions/{question_id}/favorite")
async def api_toggle_favorite(question_id: str, user_id: str = Depends(current_user_id)):
    _ensure_tables()
    now_fav = toggle_favorite(question_id, user_id)
    return {"is_favorite": now_fav}


@router.post("/questions/{question_id}/slash")
async def api_toggle_slash(question_id: str, user_id: str = Depends(current_user_id)):
    _ensure_tables()
    now_slashed = toggle_slash(question_id, user_id)
    return {"is_slashed": now_slashed}


# ═══════════════════════════════════════════════
# 题库→对话/知识点解析
# ═══════════════════════════════════════════════

@router.post("/resolve/conversation")
async def api_resolve_conversation(body: dict, user_id: str = Depends(current_user_id)):
    _ensure_tables()
    conversation_id = body.get("conversation_id", "")
    if not conversation_id:
        raise HTTPException(400, "conversation_id 不能为空")
    bank_id = resolve_bank_for_conversation(
        conversation_id, user_id,
        user_specified_bank_id=body.get("bank_id"),
    )
    bank = get_bank(bank_id, user_id)
    return {"bank_id": bank_id, "bank": bank}


@router.post("/resolve/node")
async def api_resolve_node(body: dict, user_id: str = Depends(current_user_id)):
    node_id = body.get("node_id", "")
    if not node_id:
        raise HTTPException(400, "node_id 不能为空")
    bank_id = resolve_bank_for_node(node_id, user_id)
    bank = get_bank(bank_id, user_id)
    return {"bank_id": bank_id, "bank": bank}
