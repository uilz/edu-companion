"""题库导入 — 文件导入 + 批量导入 + 导入历史"""
from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Depends

from app.domain.auth.dependencies import current_user_id
from app.services.practice.practice_question_bank import _ensure_tables
from app.services.practice.practice_question_crud import batch_import_questions
from app.services.practice.practice_import import get_import_history

logger = logging.getLogger(__name__)
router = APIRouter()


# ═══════════════════════════════════════════════
# 导入（文件）
# ═══════════════════════════════════════════════

@router.post("/import/upload")
async def api_import_upload(body: dict, user_id: str = Depends(current_user_id)):
    """上传文件并解析预览（支持 docx/xlsx/txt/json）"""
    _ensure_tables()
    file_path = body.get("file_path", "").strip()
    if not file_path:
        raise HTTPException(400, "file_path 不能为空")
    file_type = body.get("file_type", "")
    bank_id = body.get("bank_id", "")
    from app.services.practice.practice_import import preview_import
    try:
        return preview_import(file_path, user_id, file_type, bank_id)
    except FileNotFoundError as e:
        raise HTTPException(404, str(e))
    except ValueError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        logger.error("导入解析失败: %s", e)
        raise HTTPException(500, f"解析失败: {e}")


@router.post("/import/preview")
async def api_import_preview(body: dict, user_id: str = Depends(current_user_id)):
    """解析原始文本为题目预览（无需上传文件）"""
    _ensure_tables()
    text = body.get("text", "").strip()
    if not text:
        raise HTTPException(400, "text 不能为空")
    from app.services.practice.practice_import import (
        parse_questions_from_text, ai_correct_question, match_cognitive_nodes,
    )
    questions = parse_questions_from_text(text)
    for q in questions:
        q = ai_correct_question(q)
        q["suggested_node_ids"] = match_cognitive_nodes(q, user_id)
    high = sum(1 for q in questions if q.get("confidence", 0) >= 0.8)
    return {
        "questions": questions,
        "stats": {"total": len(questions), "high_confidence": high, "low_confidence": len(questions) - high},
    }


@router.post("/import/confirm")
async def api_import_confirm(body: dict, user_id: str = Depends(current_user_id)):
    """确认导入题目到题库"""
    _ensure_tables()
    bank_id = body.get("bank_id", "").strip()
    if not bank_id:
        raise HTTPException(400, "bank_id 不能为空")
    questions = body.get("questions", [])
    if not questions:
        raise HTTPException(400, "questions 不能为空")
    from app.services.practice.practice_import import confirm_import
    return confirm_import(questions, bank_id, user_id)


@router.post("/import/batch")
async def api_batch_import(body: dict, user_id: str = Depends(current_user_id)):
    """批量导入题目"""
    _ensure_tables()
    bank_id = body.get("bank_id", "")
    questions = body.get("questions", [])
    if not bank_id:
        raise HTTPException(400, "bank_id 不能为空")
    if not questions:
        raise HTTPException(400, "questions 不能为空")
    saved = batch_import_questions(bank_id, user_id, questions)
    return {"imported": len(saved), "questions": saved}


@router.get("/import/history")
async def api_import_history(
    user_id: str = Depends(current_user_id),
    bank_id: Optional[str] = None,
    limit: int = 20,
    offset: int = 0,
):
    _ensure_tables()
    return get_import_history(
        user_id=user_id, bank_id=bank_id,
        limit=min(limit, 100), offset=max(offset, 0),
    )
