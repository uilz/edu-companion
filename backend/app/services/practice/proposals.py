"""Practice 秘书提案联动

提供 Practice 域相关的 secretary proposals 查询与状态更新。
"""
from __future__ import annotations

from typing import Optional


_PRACTICE_ACTION_TYPES = {
    "practice_error_alert",
    "practice_mastery_stuck",
    "practice_review_reminder",
    "practice_reflection",
}


def get_practice_proposals(user_id: str, limit: int = 5) -> dict:
    """获取 practice 相关的待处理秘书提案。"""
    from app.infrastructure.db.proposal_store import ProposalStore
    store = ProposalStore()
    proposals = store.get_pending_proposals(user_id, limit=limit)
    filtered = [p for p in proposals if p.action_type in _PRACTICE_ACTION_TYPES]
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


def accept_proposal(proposal_id: str, user_id: str) -> dict:
    """接受提案。"""
    from app.infrastructure.db.proposal_store import ProposalStore
    store = ProposalStore()
    store.update_status(proposal_id, "accepted", user_id)
    return {"status": "accepted"}


def dismiss_proposal(proposal_id: str, user_id: str) -> dict:
    """忽略提案。"""
    from app.infrastructure.db.proposal_store import ProposalStore
    store = ProposalStore()
    store.update_status(proposal_id, "dismissed", user_id)
    return {"status": "dismissed"}
