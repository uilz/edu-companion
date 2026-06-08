"""用户管理 — super_admin 专属

GET    /                      用户列表（分页 + 模糊搜索 + 角色过滤）
GET    /{user_id}             单个用户详情
PATCH  /{user_id}             修改角色 / 启停 / 显示名
POST   /{user_id}/ban         封禁
POST   /{user_id}/unban       解封
POST   /create                创建用户
POST   /{user_id}/reset-pwd   重置密码
GET    /{user_id}/login-log   登录历史
POST   /bulk/role             批量改角色
POST   /bulk/ban              批量封禁
POST   /bulk/unban            批量解封
"""
from __future__ import annotations

import hashlib
import logging
import time
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from app_admin.deps import require_role

logger = logging.getLogger(__name__)

router = APIRouter()


# ── Pydantic models ──

class UserRow(BaseModel):
    id: str
    username: str
    email: str = ""
    display_name: str = ""
    role: str = "user"
    is_active: bool = True
    last_login: Optional[str] = None
    created_at: str = ""
    avatar_url: str = ""


class UserListResponse(BaseModel):
    items: list[UserRow]
    total: int
    page: int
    page_size: int


class UpdateUserBody(BaseModel):
    role: Optional[str] = Field(None, pattern="^(user|analyst|data_admin|super_admin)$")
    is_active: Optional[bool] = None
    display_name: Optional[str] = None


class CreateUserBody(BaseModel):
    username: str = Field(..., min_length=2, max_length=32, pattern=r"^[a-zA-Z0-9_\u4e00-\u9fff]+$")
    password: str = Field(..., min_length=4, max_length=64)
    email: str = ""
    display_name: str = ""
    role: str = Field(default="user", pattern="^(user|analyst|data_admin|super_admin)$")


class ResetPwdBody(BaseModel):
    new_password: str = Field(..., min_length=4, max_length=64)


class BulkRoleBody(BaseModel):
    user_ids: list[str]
    role: str = Field(..., pattern="^(user|analyst|data_admin|super_admin)$")


class BulkActionBody(BaseModel):
    user_ids: list[str]


# ── Helpers ──

def _repo():
    from app.services.common import get_admin_repo
    return get_admin_repo()


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
        avatar_url=r.get("avatar_url", ""),
    )


def _hash_password(password: str) -> str:
    """简易 SHA-256 哈希（与 auth-gateway auth_service 一致）"""
    return hashlib.sha256(password.encode()).hexdigest()


# ── Endpoints ──

@router.get("", response_model=UserListResponse)
async def list_users(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    q: Optional[str] = None,
    role: Optional[str] = None,
    is_active: Optional[bool] = None,
    _user: dict = Depends(require_role("super_admin")),
):
    """用户列表（分页 + 模糊搜索 + 角色 + 状态过滤）"""
    repo = _repo()
    if not repo:
        raise HTTPException(503, "AdminRepository 不可用")

    where = []
    params: list = []
    if q:
        params.extend([f"%{q}%"] * 3)
        where.append(f"(username ILIKE %s OR email ILIKE %s OR display_name ILIKE %s)")
    if role:
        params.append(role)
        where.append(f"role = %s")
    if is_active is not None:
        params.append(is_active)
        where.append(f"is_active = %s")

    where_sql = (" WHERE " + " AND ".join(where)) if where else ""

    total_rows = repo.query(f"SELECT COUNT(*) AS c FROM users{where_sql}", tuple(params))
    total = int(total_rows[0]["c"]) if total_rows else 0

    offset = (page - 1) * page_size
    params.extend([page_size, offset])
    rows = repo.query(
        f"SELECT id, username, email, display_name, role, is_active, last_login, created_at, avatar_url "
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
    return await get_user(user_id, _user=_user)


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


@router.post("/create")
async def create_user(
    body: CreateUserBody,
    _user: dict = Depends(require_role("super_admin")),
):
    """创建新用户"""
    repo = _repo()

    # 检查用户名重复
    existing = repo.query("SELECT id FROM users WHERE username = %s", (body.username,))
    if existing:
        raise HTTPException(409, f"用户名 '{body.username}' 已存在")

    user_id = f"u_{hashlib.md5(f'{body.username}{time.time()}'.encode()).hexdigest()[:12]}"
    password_hash = _hash_password(body.password)
    repo.execute(
        """INSERT INTO users (id, username, email, password_hash, display_name, role, created_at, updated_at)
           VALUES (%s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)""",
        (user_id, body.username, body.email, password_hash, body.display_name or body.username, body.role),
    )
    logger.info("admin 创建用户: id=%s username=%s role=%s", user_id, body.username, body.role)
    return {"ok": True, "user_id": user_id, "username": body.username, "role": body.role}


@router.post("/{user_id}/reset-pwd")
async def reset_password(
    user_id: str,
    body: ResetPwdBody,
    _user: dict = Depends(require_role("super_admin")),
):
    """重置用户密码"""
    repo = _repo()
    existing = repo.query("SELECT id FROM users WHERE id = %s", (user_id,))
    if not existing:
        raise HTTPException(404, "用户不存在")

    password_hash = _hash_password(body.new_password)
    repo.execute("UPDATE users SET password_hash = %s, updated_at = NOW() WHERE id = %s",
                 (password_hash, user_id))
    logger.info("admin 重置密码: id=%s", user_id)
    return {"ok": True, "message": "密码已重置"}


@router.get("/{user_id}/login-log")
async def login_log(
    user_id: str,
    limit: int = Query(20, ge=1, le=100),
    _user: dict = Depends(require_role("super_admin")),
):
    """用户登录历史（基于 users.last_login + cognitive_events 登录事件）"""
    repo = _repo()

    # 先查用户信息
    user_rows = repo.query("SELECT id, username, last_login FROM users WHERE id = %s", (user_id,))
    if not user_rows:
        raise HTTPException(404, "用户不存在")

    # 从 cognitive_events 查 login 事件
    events = repo.query(
        "SELECT event_id, timestamp, payload FROM cognitive_events "
        "WHERE user_id = %s AND event_type = 'login' "
        "ORDER BY timestamp DESC LIMIT %s",
        (user_id, limit),
    ) or []

    return {
        "user_id": user_id,
        "username": user_rows[0].get("username", ""),
        "last_login": str(user_rows[0].get("last_login") or "") or None,
        "recent_logins": [
            {
                "event_id": e.get("event_id"),
                "timestamp": str(e.get("timestamp") or ""),
                "payload": e.get("payload"),
            }
            for e in events
        ],
    }


@router.post("/bulk/role")
async def bulk_set_role(
    body: BulkRoleBody,
    _user: dict = Depends(require_role("super_admin")),
):
    """批量修改用户角色"""
    if not body.user_ids:
        raise HTTPException(400, "user_ids 不能为空")

    repo = _repo()
    affected = 0
    for uid in body.user_ids:
        r = repo.execute("UPDATE users SET role = %s, updated_at = NOW() WHERE id = %s",
                         (body.role, uid))
        affected += r or 0
    logger.info("admin 批量改角色: count=%d role=%s", len(body.user_ids), body.role)
    return {"ok": True, "affected": affected, "role": body.role}


@router.post("/bulk/ban")
async def bulk_ban(
    body: BulkActionBody,
    _user: dict = Depends(require_role("super_admin")),
):
    if not body.user_ids:
        raise HTTPException(400, "user_ids 不能为空")
    repo = _repo()
    affected = 0
    for uid in body.user_ids:
        r = repo.execute("UPDATE users SET is_active = FALSE, updated_at = NOW() WHERE id = %s", (uid,))
        affected += r or 0
    logger.info("admin 批量封禁: count=%d", len(body.user_ids))
    return {"ok": True, "affected": affected}


@router.post("/bulk/unban")
async def bulk_unban(
    body: BulkActionBody,
    _user: dict = Depends(require_role("super_admin")),
):
    if not body.user_ids:
        raise HTTPException(400, "user_ids 不能为空")
    repo = _repo()
    affected = 0
    for uid in body.user_ids:
        r = repo.execute("UPDATE users SET is_active = TRUE, updated_at = NOW() WHERE id = %s", (uid,))
        affected += r or 0
    logger.info("admin 批量解封: count=%d", len(body.user_ids))
    return {"ok": True, "affected": affected}
