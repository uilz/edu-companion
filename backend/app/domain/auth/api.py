"""
认证 API — 注册/登录/刷新/当前用户

路由前缀: /api/auth
"""
from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from app.domain.auth.service import get_auth_service

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/auth", tags=["认证"])


# ── 请求/响应模型 ──

class RegisterRequest(BaseModel):
    username: str = Field(min_length=3, max_length=32, pattern=r"^[a-zA-Z0-9_\u4e00-\u9fff]+$")
    password: str = Field(min_length=6, max_length=64)
    email: str = Field(default="", max_length=128)
    display_name: str = Field(default="", max_length=64)


class LoginRequest(BaseModel):
    username: str
    password: str


class RefreshRequest(BaseModel):
    refresh_token: str


class ChangePasswordRequest(BaseModel):
    old_password: str
    new_password: str = Field(min_length=6, max_length=64)


class UpdateProfileRequest(BaseModel):
    display_name: str | None = None
    email: str | None = None


# ── 端点 ──

@router.post("/register", summary="用户注册")
async def register(body: RegisterRequest):
    """注册新用户"""
    svc = get_auth_service()
    try:
        result = svc.register(
            username=body.username,
            password=body.password,
            email=body.email,
            display_name=body.display_name,
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/login", summary="用户登录")
async def login(body: LoginRequest):
    """用户登录，返回 JWT"""
    svc = get_auth_service()
    try:
        result = svc.login(username=body.username, password=body.password)
        return result
    except ValueError as e:
        raise HTTPException(status_code=401, detail=str(e))


@router.post("/refresh", summary="刷新令牌")
async def refresh(body: RefreshRequest):
    """使用 refresh token 获取新的 access token"""
    svc = get_auth_service()
    try:
        return svc.refresh(body.refresh_token)
    except ValueError as e:
        raise HTTPException(status_code=401, detail=str(e))


@router.get("/me", summary="获取当前用户信息")
async def get_me(request: Request):
    """获取当前登录用户信息"""
    user = getattr(request.state, "user", None)
    if not user:
        raise HTTPException(status_code=401, detail="未登录")
    return user


@router.patch("/me", summary="更新当前用户资料")
async def update_me(body: UpdateProfileRequest, request: Request):
    """更新当前用户资料"""
    user = getattr(request.state, "user", None)
    if not user:
        raise HTTPException(status_code=401, detail="未登录")

    from domain.auth.repository import get_user_repo
    repo = get_user_repo()
    repo.update_profile(
        user_id=user["id"],
        display_name=body.display_name,
        email=body.email,
    )
    return repo.find_by_id(user["id"])


@router.post("/change-password", summary="修改密码")
async def change_password(body: ChangePasswordRequest, request: Request):
    """修改当前用户密码"""
    user = getattr(request.state, "user", None)
    if not user:
        raise HTTPException(status_code=401, detail="未登录")

    svc = get_auth_service()
    from domain.auth.repository import get_user_repo
    repo = get_user_repo()
    full_user = repo.find_by_username(user["username"])
    if not full_user:
        raise HTTPException(status_code=404, detail="用户不存在")

    if not svc.verify_password(body.old_password, full_user["password_hash"]):
        raise HTTPException(status_code=400, detail="旧密码错误")

    new_hash = svc.hash_password(body.new_password)
    from app.db.database import get_db
    db = get_db()
    from datetime import datetime
    db.execute(
        "UPDATE users SET password_hash = %s, updated_at = %s WHERE id = %s",
        (new_hash, datetime.now().isoformat(), user["id"]),
    )
    return {"ok": True}
