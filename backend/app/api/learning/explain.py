"""
通用学习解释 API

端点:
  POST /api/learning/explain  — 用 AI 解释知识点或用户选中的文字
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, Depends

from app.domain.auth.dependencies import current_user_id

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/learning", tags=["通用学习"])


@router.post("/explain")
async def explain_text(
    body: dict,
    user_id: str = Depends(current_user_id),
):
    """
    用 AI 解释知识点或用户选中的文字。

    请求体:
    {
      "text": "选中/提问的文本",
      "node_id": "可选ID",
      "style": "simple | conversation"
    }
    """
    text = body.get("text", "")
    node_id = body.get("node_id")
    style = body.get("style", "simple")

    if not text.strip():
        return {"explanation": "请提供需要解释的文本"}

    from app.infrastructure.llm.llm_service import llm_service

    if style == "conversation":
        system_prompt = (
            "你是苹果果，以苏格拉底式对话引导用户自主思考。"
            "根据上下文，用简洁易懂的语言回答学生的问题。"
            "如果适合，可以反问引导学生深入思考。不要超过200字。"
        )
        user_prompt = f"学生提问：{text}"
    else:
        context_hint = f"（知识点ID: {node_id}）" if node_id else ""
        system_prompt = (
            "你是苹果果。用简洁易懂的语言解释知识点，"
            "适合自主学习场景。可以适当举例子。控制在300字以内。"
        )
        user_prompt = f"请解释以下内容{context_hint}：\n{text}"

    try:
        raw = await llm_service.generate(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.5,
            max_tokens=1024,
        )
        return {"explanation": raw.strip(), "content": raw.strip()}
    except Exception as e:
        logger.warning("AI 解释生成失败: %s", e)
        return {"explanation": "AI 解释暂不可用，请稍后再试。", "content": "AI 解释暂不可用，请稍后再试。"}
