"""用户管理 — super_admin 专属

GET    /              用户列表（分页）
GET    /{user_id}     单个用户详情
PATCH  /{user_id}     修改角色 / 启停
POST   /{user_id}/ban 封禁（is_active=false）
POST   /{user_id}/unban 解封
"""
from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from app_admin.deps import require_role

logger = logging.getLogger(__name__)

router = APIRouter()


class UserRow(BaseModel):
    id: str
    username: str
    email: str = ""
    display_name: str = ""
    role: str = "user"
    is_active: bool = True
    last_login: Optional[str] = None
    created_at: str = ""


class UserListResponse(BaseModel):
    items: list[UserRow]
    total: int
    page: int
    page_size: int


class UpdateUserBody(BaseModel):
    role: Optional[str] = Field(None, pattern="^(user|analyst|data_admin|super_admin)$")
    is_active: Optional[bool] = None
    display_name: Optional[str] = None


def _row_to_model(r: dict) -> UserRow:
    return UserRow(
        id=r.get("id", ""),
        username=r.get("username", ""),
        email=r.get("email", ""),
        display_name=r.get("display_name", ""),
        role=r.get("role", "user"),
        is_active=bool(r.get("is_active", True)),
        last_login=str(r.get("last_login") or "") or None,
        created_at=str(r.get("created_at") or ""),
    )


def _repo():
    from app.services.common import get_admin_repo
    return get_admin_repo()


@router.get("", response_model=UserListResponse)
async def list_users(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    q: Optional[str] = None,
    role: Optional[str] = None,
    _user: dict = Depends(require_role("super_admin")),
):
    """用户列表（分页 + 模糊搜索 + 角色过滤）"""
    repo = _repo()
    if not repo:
        raise HTTPException(503, "AdminRepository 不可用")

    where = []
    params: list = []
    if q:
        params.append(f"%{q}%")
        where.append(f"(username ILIKE %s OR email ILIKE %s OR display_name ILIKE %s)")
    if role:
        params.append(role)
        where.append(f"role = %s")

    where_sql = (" WHERE " + " AND ".join(where)) if where else ""

    # 总数
    total_rows = repo.query(f"SELECT COUNT(*) AS c FROM users{where_sql}", tuple(params))
    total = int(total_rows[0]["c"]) if total_rows else 0

    # 列表
    offset = (page - 1) * page_size
    params.extend([page_size, offset])
    rows = repo.query(
        f"SELECT id, username, email, display_name, role, is_active, last_login, created_at "
        f"FROM users{where_sql} ORDER BY created_at DESC LIMIT %s OFFSET %s",
        tuple(params),
    )
    return UserListResponse(
        items=[_row_to_model(r) for r in (rows or [])],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/{user_id}", response_model=UserRow)
async def get_user(
    user_id: str,
    _user: dict = Depends(require_role("super_admin")),
):
    repo = _repo()
    rows = repo.query("SELECT * FROM users WHERE id = %s", (user_id,))
    if not rows:
        raise HTTPException(404, "用户不存在")
    return _row_to_model(rows[0])


@router.patch("/{user_id}", response_model=UserRow)
async def update_user(
    user_id: str,
    body: UpdateUserBody,
    _user: dict = Depends(require_role("super_admin")),
):
    repo = _repo()
    sets: list[str] = []
    params: list = []
    if body.role is not None:
        params.append(body.role)
        sets.append("role = %s")
    if body.is_active is not None:
        params.append(body.is_active)
        sets.append("is_active = %s")
    if body.display_name is not None:
        params.append(body.display_name)
        sets.append("display_name = %s")
    if not sets:
        raise HTTPException(400, "没有要更新的字段")

    sets.append("updated_at = NOW()")
    params.append(user_id)
    repo.execute(
        f"UPDATE users SET {', '.join(sets)} WHERE id = %s",
        tuple(params),
    )
    logger.info("admin 更新用户: id=%s fields=%s", user_id, list(body.model_dump(exclude_none=True).keys()))
    return await get_user(user_id, _user=_user)  # type: ignore


@router.post("/{user_id}/ban")
async def ban_user(
    user_id: str,
    _user: dict = Depends(require_role("super_admin")),
):
    repo = _repo()
    repo.execute("UPDATE users SET is_active = FALSE, updated_at = NOW() WHERE id = %s", (user_id,))
    logger.info("admin 封禁用户: id=%s", user_id)
    return {"ok": True, "user_id": user_id, "is_active": False}


@router.post("/{user_id}/unban")
async def unban_user(
    user_id: str,
    _user: dict = Depends(require_role("super_admin")),
):
    repo = _repo()
    repo.execute("UPDATE users SET is_active = TRUE, updated_at = NOW() WHERE id = %s", (user_id,))
    logger.info("admin 解封用户: id=%s", user_id)
    return {"ok": True, "user_id": user_id, "is_active": True}
