"""
认证 API 网关 — 独立认证服务

职责：
- 用户注册/登录/密码管理
- JWT 令牌签发/验证/刷新
- 用户信息查询与更新
- 默认用户自动创建（迁移兼容）

端口：8001

独立特性：
- 不依赖业务后端任何模块
- 独立数据库连接池
- 独立 JWT 密钥管理
"""
from __future__ import annotations

import logging
from typing import Optional

from fastapi import FastAPI, APIRouter, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

# ── 请求/响应模型 ──

class RegisterRequest(BaseModel):
    username: str = Field(min_length=3, max_length=32, pattern=r"^[a-zA-Z0-9_\u4e00-\u9fff]+$")
    password: str = Field(min_length=6, max_length=64)
    email: str = Field(default="", max_length=128)
    display_name: str = Field(default="", max_length=64)


class LoginRequest(BaseModel):
    username: str
    password: str


class EmailLoginRequest(BaseModel):
    email: str
    password: str


class RefreshRequest(BaseModel):
    refresh_token: str


class ChangePasswordRequest(BaseModel):
    old_password: str
    new_password: str = Field(min_length=6, max_length=64)


class UpdateProfileRequest(BaseModel):
    display_name: str | None = None
    email: str | None = None


class TokenVerifyRequest(BaseModel):
    token: str


class TokenVerifyResponse(BaseModel):
    valid: bool
    user_id: str | None = None
    username: str | None = None
    role: str | None = None


# ── 创建 FastAPI 应用 ──
app = FastAPI(
    title="Auth Gateway",
    version="1.0.0",
    description="独立认证 API 网关服务",
    docs_url="/docs",
    redoc_url="/redoc",
)

# ── CORS ──
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

router = APIRouter(prefix="/api/auth", tags=["认证"])


# ── 端点 ──

@router.post("/register", summary="用户注册")
async def register(body: RegisterRequest):
    """注册新用户"""
    from auth_app.auth_service import get_auth_service
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
    from auth_app.auth_service import get_auth_service
    svc = get_auth_service()
    try:
        result = svc.login(username=body.username, password=body.password)
        return result
    except ValueError as e:
        raise HTTPException(status_code=401, detail=str(e))


@router.post("/login/email", summary="邮箱登录")
async def login_by_email(body: EmailLoginRequest):
    """使用邮箱登录，返回 JWT"""
    from auth_app.auth_service import get_auth_service
    svc = get_auth_service()
    try:
        result = svc.login_by_email(email=body.email, password=body.password)
        return result
    except ValueError as e:
        raise HTTPException(status_code=401, detail=str(e))


@router.post("/refresh", summary="刷新令牌")
async def refresh(body: RefreshRequest):
    """使用 refresh token 获取新的 access token"""
    from auth_app.auth_service import get_auth_service
    svc = get_auth_service()
    try:
        return svc.refresh(body.refresh_token)
    except ValueError as e:
        raise HTTPException(status_code=401, detail=str(e))


@router.get("/me", summary="获取当前用户信息")
async def get_me(request: Request):
    """获取当前登录用户信息"""
    from auth_app.auth_service import get_auth_service
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="未登录")

    token = auth_header.split(" ", 1)[1]
    svc = get_auth_service()
    user = svc.get_current_user(token)
    if not user:
        raise HTTPException(status_code=401, detail="令牌无效")
    return user


@router.post("/verify", summary="验证令牌")
async def verify_token(body: TokenVerifyRequest):
    """验证令牌有效性（供业务后端调用）"""
    from auth_app.auth_service import get_auth_service
    svc = get_auth_service()
    user = svc.get_current_user(body.token)
    if user:
        return TokenVerifyResponse(
            valid=True,
            user_id=user["user_id"],
            username=user["username"],
            role=user.get("role", "user"),
        )
    return TokenVerifyResponse(valid=False)


@router.patch("/me", summary="更新当前用户资料")
async def update_me(body: UpdateProfileRequest, request: Request):
    """更新当前用户资料"""
    from auth_app.auth_service import get_auth_service
    from auth_app.user_repo import get_user_repo

    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="未登录")

    token = auth_header.split(" ", 1)[1]
    svc = get_auth_service()
    user = svc.get_current_user(token)
    if not user:
        raise HTTPException(status_code=401, detail="令牌无效")

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
    from auth_app.auth_service import get_auth_service
    from auth_app.user_repo import get_user_repo, hash_password, verify_password

    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="未登录")

    token = auth_header.split(" ", 1)[1]
    svc = get_auth_service()
    user = svc.get_current_user(token)
    if not user:
        raise HTTPException(status_code=401, detail="令牌无效")

    repo = get_user_repo()
    full_user = repo.find_by_username(user["username"])
    if not full_user:
        raise HTTPException(status_code=404, detail="用户不存在")

    if not verify_password(body.old_password, full_user["password_hash"]):
        raise HTTPException(status_code=400, detail="旧密码错误")

    new_hash = hash_password(body.new_password)
    from auth_app.database import get_db_instance
    db = get_db_instance()
    db.execute(
        "UPDATE users SET password_hash = %s, updated_at = CURRENT_TIMESTAMP WHERE id = %s",
        (new_hash, user["user_id"]),
    )
    return {"ok": True}


# ── 兼容性端点：为现有 default_user 自动创建账号 ──

@router.post("/ensure-default", summary="确保默认用户存在（开发用）")
async def ensure_default_user():
    """如果 default_user 不存在则自动创建，用于迁移兼容"""
    from auth_app.auth_service import get_auth_service
    from auth_app.user_repo import get_user_repo

    svc = get_auth_service()
    repo = get_user_repo()
    existing = repo.find_by_username("default_user")
    if existing:
        safe_user = {k: v for k, v in existing.items() if k != "password_hash"}
        access_token = svc.jwt.create_access_token(existing["id"], "default_user", existing.get("role", "user"))
        refresh_token = svc.jwt.create_refresh_token(existing["id"])
        return {
            "user": safe_user,
            "access_token": access_token,
            "refresh_token": refresh_token,
            "created": False,
        }

    result = svc.register(username="default_user", password="default123", display_name="默认用户")
    result["created"] = True
    return result


app.include_router(router)


# ── 健康检查 ──
@app.get("/health", tags=["系统"])
async def health_check() -> dict:
    try:
        from auth_app.database import get_db_instance
        db = get_db_instance()
        db.fetchone("SELECT 1")
        db_status = True
    except Exception:
        db_status = False

    return {
        "status": "healthy" if db_status else "degraded",
        "service": "auth-gateway",
        "version": "1.0.0",
        "database": db_status,
    }


@app.get("/", tags=["系统"])
async def root() -> dict[str, str]:
    return {
        "service": "auth-gateway",
        "version": "1.0.0",
        "docs": "/docs",
        "health": "/health",
    }
