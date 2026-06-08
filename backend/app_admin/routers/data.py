"""全局数据管理 — data_admin+ 权限

GET    /overview           全局数据概览（跨用户聚合）
GET    /practice-sessions  跨用户练习会话（分页 + 过滤）
GET    /conversations      跨用户会话（分页 + 过滤）
DELETE /conversations/{id} 强制删除某会话
"""
from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from app_admin.deps import require_role

logger = logging.getLogger(__name__)

router = APIRouter()


class Overview(BaseModel):
    users_total: int = 0
    users_active: int = 0
    practice_sessions: int = 0
    conversations: int = 0
    questions: int = 0
    question_banks: int = 0
    explain_cards: int = 0
    materials: int = 0
    cognitive_nodes: int = 0
    cognitive_events: int = 0


class PracticeSessionRow(BaseModel):
    id: str
    user_id: str
    username: str = ""
    status: str = ""
    question_count: int = 0
    correct_count: int = 0
    started_at: Optional[str] = None
    ended_at: Optional[str] = None


class ConversationRow(BaseModel):
    id: str
    user_id: str
    username: str = ""
    type: str = ""
    title: str = ""
    message_count: int = 0
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


def _repo():
    from app.services.common import get_admin_repo
    return get_admin_repo()


@router.get("/overview", response_model=Overview)
async def data_overview(_: dict = Depends(require_role("data_admin"))):
    repo = _repo()
    if not repo:
        raise HTTPException(503, "AdminRepository 不可用")
    rows = repo.query("""
        SELECT
            (SELECT COUNT(*) FROM users) AS users_total,
            (SELECT COUNT(*) FROM users WHERE is_active = TRUE) AS users_active,
            (SELECT COUNT(*) FROM practice_sessions) AS practice_sessions,
            (SELECT COUNT(*) FROM conversation_user_meta) AS conversations,
            (SELECT COUNT(*) FROM questions) AS questions,
            (SELECT COUNT(*) FROM question_banks) AS question_banks,
            (SELECT COUNT(*) FROM explain_cards) AS explain_cards,
            (SELECT COUNT(*) FROM materials) AS materials,
            (SELECT COUNT(*) FROM cognitive_nodes) AS cognitive_nodes,
            (SELECT COUNT(*) FROM cognitive_events) AS cognitive_events
    """)
    if not rows:
        return Overview()
    r = rows[0]
    return Overview(**{k: int(r.get(k, 0) or 0) for k in Overview.model_fields})


@router.get("/practice-sessions")
async def list_practice_sessions(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    user_id: Optional[str] = None,
    status_filter: Optional[str] = Query(None, alias="status"),
    _: dict = Depends(require_role("data_admin")),
):
    repo = _repo()
    where = []
    params: list = []
    if user_id:
        params.append(user_id)
        where.append(f"ps.user_id = %s")
    if status_filter:
        params.append(status_filter)
        where.append(f"ps.status = %s")
    where_sql = (" WHERE " + " AND ".join(where)) if where else ""

    total = int((repo.query(f"SELECT COUNT(*) AS c FROM practice_sessions ps{where_sql}", tuple(params)) or [{"c": 0}])[0]["c"])
    offset = (page - 1) * page_size
    params.extend([page_size, offset])
    rows = repo.query(
        f"SELECT ps.id, ps.user_id, u.username, ps.status, "
        f"       COALESCE(ps.total_count, 0) AS total_count, "
        f"       COALESCE(ps.correct_count, 0) AS correct_count, "
        f"       COALESCE(ps.wrong_count, 0) AS wrong_count, "
        f"       ps.started_at, ps.finished_at "
        f"FROM practice_sessions ps LEFT JOIN users u ON u.id = ps.user_id"
        f"{where_sql} ORDER BY ps.started_at DESC NULLS LAST LIMIT %s OFFSET %s",
        tuple(params),
    ) or []
    return {"items": rows, "total": total, "page": page, "page_size": page_size}


@router.get("/conversations")
async def list_conversations(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    user_id: Optional[str] = None,
    type_filter: Optional[str] = Query(None, alias="type"),
    _: dict = Depends(require_role("data_admin")),
):
    """跨用户会话（conversations 是 JSONB object: {conv_id: Conversation}）"""
    repo = _repo()
    where = ["conversations != '{}'::jsonb"]
    params: list = []
    if user_id:
        params.append(user_id)
        where.append("user_id = %s")
    if type_filter:
        # conversations::text like '%"type":"<type>"%'
        params.append(f'%"type":"{type_filter}"%')
        where.append("conversations::text ILIKE %s")
    where_sql = " WHERE " + " AND ".join(where)

    total = int((repo.query(f"SELECT COUNT(*) AS c FROM conversation_user_meta{where_sql}", tuple(params)) or [{"c": 0}])[0]["c"])
    offset = (page - 1) * page_size
    params.extend([page_size, offset])
    # 用 jsonb_object_keys 数 key 数量
    rows = repo.query(
        f"SELECT user_id, "
        f"  (SELECT COUNT(*) FROM jsonb_object_keys(conversations)) AS conv_count, "
        f"  updated_at "
        f"FROM conversation_user_meta{where_sql} "
        f"ORDER BY updated_at DESC LIMIT %s OFFSET %s",
        tuple(params),
    ) or []
    return {"items": rows, "total": total, "page": page, "page_size": page_size}


@router.delete("/conversations/{user_id}/{conversation_id}")
async def delete_conversation(
    user_id: str,
    conversation_id: str,
    actor: dict = Depends(require_role("data_admin")),
):
    """从 conversation_user_meta.conversations JSONB object 中删除指定 key"""
    repo = _repo()
    affected = repo.execute(
        "UPDATE conversation_user_meta SET conversations = conversations - %s, updated_at = NOW() "
        "WHERE user_id = %s",
        (conversation_id, user_id),
    )
    logger.info("admin 删除会话: user=%s conv=%s actor=%s affected=%s",
                user_id, conversation_id, actor.get("user_id"), affected)
    return {"ok": True, "affected": affected}
