"""秘书数据生命周期服务 (Task #168)

处理用户秘书相关数据的导出（可移植性）与删除（遗忘权）。
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)


def export_secretary_data(user_id: str) -> dict[str, Any]:
    """导出所有秘书相关个人数据。"""
    from app.services.common import get_data_repo
    from app.infrastructure.db.proposal_store import ProposalStore

    data = {
        "user_id": user_id,
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "preferences": {},
        "proposals": [],
        "policy_memory": {},
    }

    try:
        user_data = get_data_repo().load(user_id)
        data["preferences"] = user_data.secretary_prefs
    except Exception as e:
        data["preferences_error"] = str(e)

    try:
        store = ProposalStore()
        db = store._get_db()
        rows = db.fetchall(
            "SELECT id, title, action_type, priority, status, created_at "
            "FROM secretary_proposals WHERE user_id = %s ORDER BY created_at DESC LIMIT 200",
            (user_id,),
        )
        if rows:
            data["proposals"] = [
                {
                    "id": r["id"],
                    "title": r["title"],
                    "action_type": r["action_type"],
                    "priority": r["priority"],
                    "status": r["status"],
                    "created_at": str(r["created_at"]) if r["created_at"] else None,
                }
                for r in rows
            ]
    except Exception as e:
        data["proposal_error"] = str(e)

    try:
        user_data = get_data_repo().load(user_id)
        data["policy_memory"] = user_data.policy_memory
    except Exception as e:
        data["policy_memory_error"] = str(e)

    return data


def delete_secretary_data(user_id: str) -> dict[str, Any]:
    """删除所有秘书相关个人数据。"""
    from app.services.common import get_data_repo
    from app.infrastructure.db.proposal_store import ProposalStore

    deleted = {"proposals": False, "prefs": False, "policy_memory": False}

    try:
        store = ProposalStore()
        store._get_db().execute("DELETE FROM secretary_proposals WHERE user_id = %s", (user_id,))
        deleted["proposals"] = True
    except Exception as e:
        logger.error("Failed to delete proposals for user %s: %s", user_id, e)

    try:
        user_data = get_data_repo().load(user_id)
        user_data.secretary_prefs = {}
        user_data.policy_memory = {}
        get_data_repo().save(user_id, user_data)
        deleted["prefs"] = True
        deleted["policy_memory"] = True
    except Exception as e:
        logger.error("Failed to clear secretary data via storage: %s", e)

    return {"status": "deleted", "details": deleted}
