"""AI 出题 — generate / generate-from-materials / bulk / similar / explain / generate-from-conversation"""
from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, Depends

from app.domain.auth.dependencies import current_user_id
from app.services.practice.practice_question_bank import (
    _ensure_tables, get_bank, resolve_bank_for_conversation,
)
from app.services.practice.practice_question_gen import (
    generate_and_save, handle_question_generation, generate_for_conversation,
)

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/generate")
async def api_generate(body: dict, user_id: str = Depends(current_user_id)):
    """AI 出题（自然语言指定参数）"""
    _ensure_tables()
    user_message = body.get("message", "").strip()
    if not user_message:
        raise HTTPException(400, "请描述你想练习什么内容")
    bank_id = body.get("bank_id")
    conversation_id = body.get("conversation_id")
    node_id = body.get("node_id")
    material_ids = body.get("material_ids")
    result = await handle_question_generation(
        user_message=user_message,
        user_id=user_id,
        bank_id=bank_id,
        conversation_id=conversation_id,
        node_id=node_id,
        material_ids=material_ids,
    )
    return result


@router.post("/generate-from-materials")
async def api_generate_from_materials(body: dict, user_id: str = Depends(current_user_id)):
    """基于指定资料出题"""
    _ensure_tables()
    material_ids = body.get("material_ids", [])
    if not material_ids:
        raise HTTPException(400, "请指定至少一个资料")

    subject = body.get("subject", "通用")
    skill_id = body.get("skill_id", subject)
    bloom_level = body.get("bloom_level", "apply")
    difficulty = float(body.get("difficulty", 0.5))
    count = max(1, min(10, int(body.get("count", 5))))
    content_type = body.get("content_type", "choice")
    bank_id = body.get("bank_id")

    if not bank_id:
        bank_id = resolve_bank_for_conversation(f"materials_{hash(str(material_ids))}", user_id)

    from app.services.practice.practice_question_gen import get_material_context
    material_context = await get_material_context(material_ids, user_id)

    saved = await generate_and_save(
        bank_id=bank_id,
        user_id=user_id,
        subject=subject,
        skill_id=skill_id,
        bloom_level=bloom_level,
        difficulty=difficulty,
        count=count,
        content_type=content_type,
        material_context=material_context,
    )

    bank = get_bank(bank_id, user_id)
    return {
        "bank_id": bank_id,
        "bank_name": bank["name"] if bank else "",
        "generated": len(saved),
        "questions": saved,
        "has_material_context": material_context is not None,
        "material_count": len(material_ids),
        "params": {
            "subject": subject,
            "skill_id": skill_id,
            "bloom_level": bloom_level,
            "difficulty": difficulty,
            "count": count,
            "content_type": content_type,
        },
    }


@router.post("/generate-bulk")
async def api_generate_bulk(body: dict, user_id: str = Depends(current_user_id)):
    """批量出题：一次对多个知识点生成不同 Bloom 层次的题目"""
    _ensure_tables()
    bank_id = body.get("bank_id", "")
    if not bank_id:
        raise HTTPException(400, "bank_id 不能为空")
    plans = body.get("plans", [])
    if not plans:
        raise HTTPException(400, "plans 不能为空，格式: [{skill_id, subject, bloom_level, count}]")
    from app.services.practice.practice_question_gen import bulk_generate
    return await bulk_generate(bank_id=bank_id, plans=plans, user_id=user_id, material_ids=body.get("material_ids"))


@router.post("/questions/{question_id}/similar")
async def api_generate_similar(question_id: str, body: dict, user_id: str = Depends(current_user_id)):
    """基于已有题目生成同类变体"""
    _ensure_tables()
    count = max(1, min(10, int(body.get("count", 3))))
    from app.services.practice.practice_question_gen import generate_similar
    questions = await generate_similar(question_id, user_id, count)
    return {"generated": len(questions), "questions": questions}


@router.get("/questions/{question_id}/explain")
async def api_explain_question(question_id: str, user_id: str = Depends(current_user_id), style: str = "detailed"):
    """AI 深入讲解某道题"""
    _ensure_tables()
    from app.services.practice.practice_question_gen import explain_question
    return await explain_question(question_id, user_id, style)


@router.post("/generate-from-conversation")
async def api_generate_from_conversation(body: dict, user_id: str = Depends(current_user_id)):
    """对话场景出题：自动识别对话内容并生成题目"""
    _ensure_tables()
    conversation_id = body.get("conversation_id", "")
    if not conversation_id:
        raise HTTPException(400, "conversation_id 不能为空")
    user_message = body.get("message", "").strip()
    if not user_message:
        raise HTTPException(400, "请描述你想练习什么内容")
    context = body.get("context")

    result = await generate_for_conversation(
        conversation_id=conversation_id,
        user_message=user_message,
        user_id=user_id,
        conversation_context=context,
        material_ids=body.get("material_ids"),
    )
    return result
