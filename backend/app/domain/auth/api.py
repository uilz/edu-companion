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
async def login(body: LoginRequest, request: Request):
    """用户登录，返回 JWT"""
    svc = get_auth_service()
    try:
        result = svc.login(username=body.username, password=body.password)
    except ValueError as e:
        raise HTTPException(status_code=401, detail=str(e))

    # 记录登录事件（设备/IP/区域）
    try:
        from app.domain.auth.login_event_repo import get_login_event_repo
        from app.domain.auth.ua_parser import parse_user_agent, parse_ip_region

        user_id = result["user"]["id"]
        ip = request.headers.get("x-forwarded-for", "").split(",")[0].strip()
        if not ip:
            ip = request.client.host if request.client else ""
        ua = request.headers.get("user-agent", "")
        ua_info = parse_user_agent(ua)
        ip_info = parse_ip_region(ip)

        repo = get_login_event_repo()
        repo.record_login(
            user_id=user_id,
            ip_address=ip,
            user_agent=ua[:500],  # 截断防止过长
            country=ip_info["country"],
            region=ip_info["region"],
            city=ip_info["city"],
            device_type=ua_info["device_type"],
            browser=ua_info["browser"],
            os=ua_info["os"],
        )
    except Exception as e:
        logger.warning("记录登录事件失败: %s", e)

    return result


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
        user_id=user["user_id"],
        display_name=body.display_name,
        email=body.email,
    )
    return repo.find_by_id(user["user_id"])


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
    repo = get_user_repo()
    repo.update_password(user["user_id"], new_hash)
    return {"ok": True}


class DeactivateRequest(BaseModel):
    password: str = Field(min_length=1)


@router.get("/me/login-history", summary="获取当前用户登录历史")
async def get_my_login_history(request: Request, limit: int = 20):
    """获取当前用户的登录历史"""
    user = getattr(request.state, "user", None)
    if not user:
        raise HTTPException(status_code=401, detail="未登录")

    from app.domain.auth.login_event_repo import get_login_event_repo
    repo = get_login_event_repo()
    events = repo.get_user_login_history(user["user_id"], limit=limit)
    online = repo.get_user_online_status(user["user_id"])
    active_sessions = repo.get_user_active_sessions(user["user_id"])
    ip_analysis = repo.get_ip_analysis(user["user_id"])

    return {
        "online": online,
        "active_sessions": active_sessions,
        "login_history": events,
        "ip_analysis": ip_analysis,
    }


@router.get("/me/active-sessions", summary="获取当前用户活跃会话")
async def get_my_active_sessions(request: Request):
    """获取当前用户的活跃会话"""
    user = getattr(request.state, "user", None)
    if not user:
        raise HTTPException(status_code=401, detail="未登录")

    from app.domain.auth.login_event_repo import get_login_event_repo
    repo = get_login_event_repo()
    return {"sessions": repo.get_user_active_sessions(user["user_id"])}


@router.post("/me/logout-other-devices", summary="踢出其他设备")
async def logout_other_devices(request: Request):
    """使其他设备下线（递增 token_version，使旧 token 失效）"""
    user = getattr(request.state, "user", None)
    if not user:
        raise HTTPException(status_code=401, detail="未登录")

    from app.domain.auth.login_event_repo import get_login_event_repo
    
    user_id = user["user_id"]
    
    # 递增 token_version 使其他设备的 token 失效
    repo = get_user_repo()
    repo.increment_token_version(user_id)
    
    # 清除其他设备的 is_current 标记
    repo.clear_login_sessions(user_id)
    
    # 重新标记当前会话为 is_current
    # 当前会话通过当前请求的 IP + UA 来识别
    ip = request.headers.get("x-forwarded-for", "").split(",")[0].strip()
    if not ip:
        ip = request.client.host if request.client else ""
    ua = request.headers.get("user-agent", "")
    db.execute(
        """UPDATE login_events SET is_current = TRUE 
           WHERE user_id = %s AND ip_address = %s AND user_agent = %s
           ORDER BY created_at DESC LIMIT 1""",
        (user_id, ip, ua[:500]),
    )
    
    return {"ok": True, "message": "其他设备已下线"}


@router.post("/deactivate", summary="注销账号")
async def deactivate_account(body: DeactivateRequest, request: Request):
    """注销当前用户账号（软删除）"""
    user = getattr(request.state, "user", None)
    if not user:
        raise HTTPException(status_code=401, detail="未登录")

    svc = get_auth_service()
    from domain.auth.repository import get_user_repo
    repo = get_user_repo()
    full_user = repo.find_by_username(user["username"])
    if not full_user:
        raise HTTPException(status_code=404, detail="用户不存在")

    if not svc.verify_password(body.password, full_user["password_hash"]):
        raise HTTPException(status_code=400, detail="密码错误")

    repo = get_user_repo()
    repo.deactivate_account(user["user_id"], full_user["username"])
    return {"ok": True, "message": "账号已注销"}
