"""题库管理 — Bank CRUD + Question CRUD + Resolve"""
from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Query, Depends

from app.domain.auth.dependencies import current_user_id
from app.services.practice.practice_question_crud import (
    add_question, update_question, delete_question,
    toggle_favorite, toggle_slash, batch_import_questions, copy_questions_to_bank, reorder_questions_in_bank,
)
from app.services.practice.practice_question_bank import (
    _ensure_tables, list_banks, get_bank, create_bank, update_bank, delete_bank,
    list_questions, get_question, get_question_preview, search_questions,
    resolve_bank_for_conversation, resolve_bank_for_node,
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
async def api_get_bank(
    bank_id: str,
    user_id: str = Depends(current_user_id),
    preview: bool = Query(True, description="是否包含题目预览"),
    preview_count: int = Query(5, ge=0, le=50, description="预览题目数量"),
):
    _ensure_tables()
    bank = get_bank(bank_id, user_id)
    if not bank:
        raise HTTPException(404, "题库不存在")

    # 附带题目预览
    if preview:
        questions = list_questions(
            bank_id, user_id,
            page=1, page_size=preview_count,
        )
        bank["question_preview"] = questions.get("items", [])
        bank["total_questions"] = questions.get("total", 0)
    else:
        # 仅统计数量
        from app.infrastructure.db.database import get_db
        db = get_db()
        row = db.fetchone(
            "SELECT COUNT(*) as cnt FROM questions WHERE bank_id = %s AND deleted_at IS NULL",
            (bank_id,),
        )
        bank["total_questions"] = row["cnt"] if row else 0

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


@router.get("/banks/search")
async def api_search_banks(
    keyword: str = Query("", description="搜索关键词"),
    user_id: str = Depends(current_user_id),
):
    """按名称/描述搜索题库"""
    _ensure_tables()
    banks = list_banks(user_id)
    if keyword:
        kw = keyword.lower()
        banks = [
            b for b in banks
            if kw in (b.get("name") or "").lower()
            or kw in (b.get("description") or "").lower()
        ]
    return {"total": len(banks), "items": banks}


@router.get("/questions/search")
async def api_search_questions(
    keyword: str = Query("", description="搜索关键词"),
    bank_id: Optional[str] = Query(None, description="按题库过滤"),
    question_type: Optional[str] = Query(None, description="题目类型"),
    bloom_level: Optional[str] = Query(None, description="Bloom层次"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    user_id: str = Depends(current_user_id),
):
    """跨题库搜索题目"""
    _ensure_tables()
    return search_questions(
        keyword=keyword, bank_id=bank_id,
        question_type=question_type, bloom_level=bloom_level,
        page=page, page_size=page_size,
        user_id=user_id,
    )


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


@router.post("/banks/{bank_id}/questions/copy")
async def api_copy_questions(bank_id: str, body: dict, user_id: str = Depends(current_user_id)):
    """从其他题库复制题目到当前题库"""
    _ensure_tables()
    question_ids = body.get("question_ids", [])
    source_bank_id = body.get("source_bank_id")
    if not question_ids and not source_bank_id:
        raise HTTPException(400, "question_ids 或 source_bank_id 必填")
    result = copy_questions_to_bank(
        target_bank_id=bank_id,
        user_id=user_id,
        question_ids=question_ids,
        source_bank_id=source_bank_id,
    )
    return {"copied": len(result), "questions": result}


@router.put("/banks/{bank_id}/questions/reorder")
async def api_reorder_questions(bank_id: str, body: dict, user_id: str = Depends(current_user_id)):
    """批量调整题目顺序 (question_ids 按新顺序排列)"""
    _ensure_tables()
    question_ids = body.get("question_ids", [])
    if not question_ids:
        raise HTTPException(400, "question_ids 不能为空")
    ok = reorder_questions_in_bank(bank_id, question_ids, user_id)
    return {"ok": ok}


@router.get("/questions/{question_id}")
async def api_get_question(question_id: str, user_id: str = Depends(current_user_id)):
    _ensure_tables()
    q = get_question(question_id, user_id)
    if not q:
        raise HTTPException(404, "题目不存在")
    return q


@router.get("/questions/{question_id}/preview")
async def api_preview_question(
    question_id: str,
    user_id: str = Depends(current_user_id),
    include_similar: bool = True,
    include_materials: bool = True,
):
    """题目富预览：详情 + 相似题 + 关联资料 + 答题统计 + 知识点"""
    _ensure_tables()
    preview = get_question_preview(
        question_id, user_id,
        include_similar=include_similar,
        include_materials=include_materials,
    )
    if "error" in preview:
        raise HTTPException(404, preview["error"])
    return preview


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
