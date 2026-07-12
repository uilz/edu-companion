"""对话内联练习服务

处理对话中嵌入的练习块（practice block）提交与提示。
"""
from __future__ import annotations

from app.services.practice.engine import publish_practice_events, build_reply_text
from app.services.practice.practice_service import get_inline_hint


async def submit_inline_answer(
    user_id: str,
    block_id: str,
    answer: str,
) -> dict:
    """对话内联练习 — 提交答案，读取 response_block 内容校验。"""
    from app.services.common import get_data_repo

    data = get_data_repo().load(user_id)
    block = data.response_blocks.get(block_id)
    if not block:
        raise ValueError("Practice block not found")

    content = block.content or {}
    correct_answer = content.get("correct_answer", "").strip().upper()
    explanation = content.get("explanation") or content.get("reply_expected", "") or ""
    skill_id = content.get("skill_id", "")
    is_correct = answer.strip().upper() == correct_answer

    # 内联练习只发布 AnswerSubmitted 事件，认知更新由认知中心订阅处理。
    # 不再直接调用 update_cognitive_after_practice 双写认知状态。
    if skill_id:
        await publish_practice_events(
            user_id=user_id,
            session_id=block_id,
            question_id=block_id,
            question={
                "skill_id": skill_id,
                "cognitive_node_ids": [skill_id],
            },
            is_correct=is_correct,
            user_answer=answer,
            correct_answer=content.get("correct_answer", ""),
            time_spent_seconds=0,
            hints_used=0,
        )

    correct_label = content.get("correct_answer", "")
    reply_text = build_reply_text(is_correct, correct_label, explanation)

    return {
        "is_correct": is_correct,
        "reply_text": reply_text,
        "knowledge_update": {},
    }


def get_inline_hint_for_block(user_id: str, block_id: str) -> dict | None:
    """对话内联练习 — 获取提示。"""
    return get_inline_hint(block_id, user_id)
