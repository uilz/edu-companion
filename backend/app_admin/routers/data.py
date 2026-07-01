"""全局数据管理 — data_admin+ 权限

GET    /overview            全局数据概览（跨用户聚合）
GET    /practice-sessions   跨用户练习会话（分页 + 过滤）
GET    /conversations       跨用户会话（分页 + 过滤）
DELETE /conversations/{id}  强制删除某会话
GET    /users/{user_id}/sessions  指定用户的所有练习会话
GET    /users/{user_id}/attempts  指定用户的练习明细
GET    /export/sessions     导出练习会话 CSV
GET    /export/users        导出用户 CSV
"""
from __future__ import annotations

import csv
import io
import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app_admin.deps import require_role

logger = logging.getLogger(__name__)

router = APIRouter()


class Overview(BaseModel):
    users_total: int = 0
    users_active: int = 0
    practice_sessions: int = 0
    practice_attempts: int = 0
    conversations: int = 0
    questions: int = 0
    question_banks: int = 0
    materials: int = 0
    cognitive_nodes: int = 0
    cognitive_events: int = 0


class SessionRow(BaseModel):
    id: str
    user_id: str
    username: str = ""
    status: str = ""
    total_count: int = 0
    correct_count: int = 0
    wrong_count: int = 0
    started_at: Optional[str] = None
    finished_at: Optional[str] = None


class AttemptRow(BaseModel):
    id: str
    session_id: str
    question_id: str
    is_correct: bool
    time_spent: float = 0
    created_at: Optional[str] = None
    stem: str = ""


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
            (SELECT COUNT(*) FROM practice_attempts) AS practice_attempts,
            (SELECT COUNT(*) FROM conversation_user_meta) AS conversations,
            (SELECT COUNT(*) FROM questions) AS questions,
            (SELECT COUNT(*) FROM question_banks) AS question_banks,
            (SELECT COUNT(*) FROM materials) AS materials,
            (SELECT COUNT(*) FROM knowledge_nodes) AS cognitive_nodes,
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
        where.append("ps.user_id = %s")
    if status_filter:
        params.append(status_filter)
        where.append("ps.status = %s")
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
    """跨用户会话"""
    repo = _repo()
    where = ["conversations != '{}'::jsonb"]
    params: list = []
    if user_id:
        params.append(user_id)
        where.append("user_id = %s")
    if type_filter:
        params.append(f'%"type":"{type_filter}"%')
        where.append("conversations::text ILIKE %s")
    where_sql = " WHERE " + " AND ".join(where)

    total = int((repo.query(f"SELECT COUNT(*) AS c FROM conversation_user_meta{where_sql}", tuple(params)) or [{"c": 0}])[0]["c"])
    offset = (page - 1) * page_size
    params.extend([page_size, offset])
    rows = repo.query(
        f"SELECT user_id, "
        f"  (SELECT COUNT(*) FROM jsonb_object_keys(conversations)) AS conv_count, "
        f"  updated_at "
        f"FROM conversation_user_meta{where_sql} "
        f"ORDER BY updated_at DESC LIMIT %s OFFSET %s",
        tuple(params),
    ) or []
    return {"items": rows, "total": total, "page": page, "page_size": page_size}


@router.delete("/conversations/{user_id}/{conv_id}")
async def delete_conversation(
    user_id: str,
    conv_id: str,
    actor: dict = Depends(require_role("data_admin")),
):
    repo = _repo()
    affected = repo.execute(
        "UPDATE conversation_user_meta SET conversations = conversations - %s, updated_at = NOW() "
        "WHERE user_id = %s",
        (conv_id, user_id),
    )
    logger.info("admin 删除会话: user=%s conv=%s actor=%s affected=%s",
                user_id, conv_id, actor.get("user_id"), affected)
    return {"ok": True, "affected": affected}


# ── Per-user drill-down ──

@router.get("/users/{uid}/sessions")
async def user_sessions(
    uid: str,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    _: dict = Depends(require_role("data_admin")),
):
    """指定用户的所有练习会话"""
    repo = _repo()
    total = int((repo.query("SELECT COUNT(*) AS c FROM practice_sessions WHERE user_id = %s", (uid,)) or [{"c": 0}])[0]["c"])
    offset = (page - 1) * page_size
    rows = repo.query(
        "SELECT id, user_id, status, total_count, correct_count, wrong_count, started_at, finished_at "
        "FROM practice_sessions WHERE user_id = %s ORDER BY started_at DESC LIMIT %s OFFSET %s",
        (uid, page_size, offset),
    ) or []
    return {"items": rows, "total": total, "user_id": uid, "page": page, "page_size": page_size}


@router.get("/users/{uid}/attempts")
async def user_attempts(
    uid: str,
    limit: int = Query(50, ge=1, le=500),
    _: dict = Depends(require_role("data_admin")),
):
    """指定用户的练习明细（最近 N 条）"""
    repo = _repo()
    rows = repo.query(
        "SELECT pa.id, pa.session_id, pa.question_id, pa.is_correct, "
        "       COALESCE(pa.time_spent, 0) AS time_spent, pa.created_at, "
        "       COALESCE(q.stem, '') AS stem "
        "FROM practice_attempts pa "
        "LEFT JOIN questions q ON q.id = pa.question_id "
        "WHERE pa.user_id = %s ORDER BY pa.created_at DESC LIMIT %s",
        (uid, limit),
    ) or []
    return {"items": rows, "count": len(rows), "user_id": uid}


# ── CSV Export ──

def _csv_response(rows: list[dict], filename: str) -> StreamingResponse:
    output = io.StringIO()
    if rows:
        w = csv.DictWriter(output, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@router.get("/export/sessions")
async def export_sessions(
    _: dict = Depends(require_role("data_admin")),
):
    """导出所有练习会话 CSV"""
    repo = _repo()
    rows = repo.query(
        "SELECT ps.id, ps.user_id, u.username, ps.status, "
        "       ps.total_count, ps.correct_count, ps.wrong_count, "
        "       ps.started_at, ps.finished_at "
        "FROM practice_sessions ps LEFT JOIN users u ON u.id = ps.user_id "
        "ORDER BY ps.started_at DESC"
    ) or []
    return _csv_response(rows, "practice_sessions.csv")


@router.get("/export/users")
async def export_users(
    _: dict = Depends(require_role("data_admin")),
):
    """导出用户 CSV"""
    repo = _repo()
    rows = repo.query(
        "SELECT id, username, email, display_name, role, is_active, last_login, created_at "
        "FROM users ORDER BY created_at DESC"
    ) or []
    return _csv_response(rows, "users.csv")
