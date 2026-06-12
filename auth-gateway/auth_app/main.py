"""
认证 API 网关 — 独立认证服务

职责：
- 用户注册/登录/密码管理
- JWT 令牌签发/验证/刷新
- 用户信息查询与更新
- WebSocket 代理：将 WS 连接透明转发到主后端（含 JWT 验证 + user_id 注入）

端口：18001

（可选）HTTP 反向代理：通过 ReverseProxyMiddleware 将非 /api/auth/* 请求转发到后端。
部署 Nginx 统一网关后此层为 fallback，Nginx 路由：/api/auth/* → auth-gateway，/api/* → backend。

独立特性：
- 不依赖业务后端任何模块
- 独立数据库连接池
- 独立 JWT 密钥管理

架构关系详见 ../CONTEXT-MAP.md
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import shutil
import time
import uuid
from pathlib import Path
from typing import Optional
from urllib.parse import parse_qs

import websockets
from fastapi import FastAPI, APIRouter, HTTPException, Request, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, model_validator

import httpx

# 确保 .env 在 JWTService 单例创建前加载
from auth_app import database  # noqa: F401

logger = logging.getLogger(__name__)

# ── 登录限流（防止暴力破解）──
# key: 用户名/邮箱/IP, value: (attempts, first_attempt_time)
_login_attempts: dict[str, tuple[int, float]] = {}
_LOGIN_RATE_LIMIT = 5  # 5次尝试
_LOGIN_RATE_WINDOW = 60  # 60秒窗口


def _check_login_rate_limit(key: str) -> bool:
    """检查登录尝试是否超过限制"""
    now = time.time()
    attempts, first_time = _login_attempts.get(key, (0, now))

    # 窗口过期，重置计数
    if now - first_time > _LOGIN_RATE_WINDOW:
        _login_attempts[key] = (1, now)
        return True

    # 检查是否超过限制
    if attempts >= _LOGIN_RATE_LIMIT:
        return False

    # 增加计数
    _login_attempts[key] = (attempts + 1, first_time)
    return True


def _clear_login_rate_limit(key: str) -> None:
    """登录成功后清除限流记录"""
    _login_attempts.pop(key, None)


# ── 请求/响应模型 ──

class RegisterRequest(BaseModel):
    username: str = Field(min_length=3, max_length=32, pattern=r"^[a-zA-Z0-9_\u4e00-\u9fff]+$")
    password: str = Field(min_length=8, max_length=64)
    email: str = Field(default="", max_length=128)
    display_name: str = Field(default="", max_length=64)
    turnstile_token: str = Field(default="", max_length=2048, description="Cloudflare Turnstile 令牌")

    @model_validator(mode="after")
    def validate_password_complexity(self):
        password = self.password
        if len(password) < 8:
            raise ValueError("密码至少需要8个字符")
        if not any(c.isupper() for c in password):
            raise ValueError("密码需要包含至少一个大写字母")
        if not any(c.islower() for c in password):
            raise ValueError("密码需要包含至少一个小写字母")
        if not any(c.isdigit() for c in password):
            raise ValueError("密码需要包含至少一个数字")
        return self


class LoginRequest(BaseModel):
    username: str
    password: str
    turnstile_token: str = Field(default="", max_length=2048, description="Cloudflare Turnstile 令牌")


class EmailLoginRequest(BaseModel):
    email: str
    password: str
    turnstile_token: str = Field(default="", max_length=2048, description="Cloudflare Turnstile 令牌")


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
# 生产环境关闭 docs（通过 ENV=production 或 APP_DEBUG=false 控制）
is_production = os.getenv("ENV") == "production" or os.getenv("APP_DEBUG") == "false"
docs_url = None if is_production else "/docs"
redoc_url = None if is_production else "/redoc"

app = FastAPI(
    title="Auth Gateway",
    version="1.0.0",
    description="独立认证 API 网关服务",
    docs_url=docs_url,
    redoc_url=redoc_url,
)


# ── 安全响应头中间件 ──
@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    csp = (
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline'; "
        "style-src 'self' 'unsafe-inline'; "
        "img-src 'self' data: blob:; "
        "connect-src 'self' ws: wss:; "
        "font-src 'self'; "
        "frame-ancestors 'none'; "
        "base-uri 'self'"
    )
    response.headers["Content-Security-Policy"] = csp
    return response


# ── 请求超时中间件 ──
REQUEST_TIMEOUT = 30  # 30秒超时
@app.middleware("http")
async def request_timeout(request: Request, call_next):
    try:
        return await asyncio.wait_for(call_next(request), timeout=REQUEST_TIMEOUT)
    except asyncio.TimeoutError:
        return Response(
            content=json.dumps({"error": "timeout", "detail": "请求超时，请重试"}),
            media_type="application/json",
            status_code=408,
        )


# ── CORS ──
cors_origins = os.getenv("CORS_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

router = APIRouter(prefix="/api/auth", tags=["认证"])


# ── 端点 ──

@router.post("/register", summary="用户注册")
async def register(body: RegisterRequest, request: Request):
    """注册新用户（需 Turnstile 验证）"""
    from auth_app.auth_service import get_auth_service
    from auth_app.security import (
        verify_turnstile_token,
        get_system_config,
        get_cooling_manager,
        get_ip_control_manager,
    )

    client_ip = request.client.host if request.client else "unknown"

    # 1) 检查注册开关
    if not get_system_config().is_registration_enabled():
        raise HTTPException(status_code=403, detail="注册功能已关闭，请联系管理员")

    # 2) IP 黑名单检查
    if get_ip_control_manager().is_blacklisted(client_ip):
        logger.warning("注册拒绝: IP %s 在黑名单中", client_ip)
        raise HTTPException(status_code=403, detail="您的 IP 已被限制访问")

    # 3) 冷却检查
    cooling_level = get_cooling_manager().check_and_apply(client_ip)
    if cooling_level >= 2:
        raise HTTPException(status_code=429, detail="请求过于频繁，请稍后再试")
    if cooling_level >= 1:
        # Level 1: 强制 Turnstile 验证
        if not await verify_turnstile_token(body.turnstile_token, client_ip):
            raise HTTPException(status_code=400, detail="请完成人机验证后重试")
    else:
        # 正常模式: Turnstile token 可选，若有则验证
        if body.turnstile_token:
            if not await verify_turnstile_token(body.turnstile_token, client_ip):
                raise HTTPException(status_code=400, detail="人机验证失败，请重试")

    svc = get_auth_service()
    try:
        result = svc.register(
            username=body.username,
            password=body.password,
            email=body.email,
            display_name=body.display_name,
        )
        # 注册成功，清除失败记录
        get_cooling_manager().clear_register_fails(client_ip)
        return result
    except ValueError as e:
        # 注册失败，记录冷却
        get_cooling_manager().record_register_failure(client_ip)
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/login", summary="用户登录")
async def login(body: LoginRequest, request: Request):
    """用户登录，返回 JWT"""
    from auth_app.auth_service import get_auth_service
    from auth_app.security import (
        verify_turnstile_token,
        get_system_config,
        get_cooling_manager,
        get_ip_control_manager,
    )

    client_ip = request.client.host if request.client else "unknown"

    # 1) 检查登录开关
    if not get_system_config().is_login_enabled():
        raise HTTPException(status_code=403, detail="登录功能已关闭，请联系管理员")

    # 2) IP 黑名单检查
    if get_ip_control_manager().is_blacklisted(client_ip):
        logger.warning("登录拒绝: IP %s 在黑名单中", client_ip)
        raise HTTPException(status_code=403, detail="您的 IP 已被限制访问")

    # 3) 冷却检查
    cooling_level = get_cooling_manager().check_and_apply(client_ip)
    if cooling_level >= 2:
        raise HTTPException(status_code=429, detail="请求过于频繁，请稍后再试")
    if cooling_level >= 1:
        # Level 1: 强制 Turnstile 验证
        if not await verify_turnstile_token(body.turnstile_token, client_ip):
            raise HTTPException(status_code=400, detail="请完成人机验证后重试")

    # 4) 限流检查（原有）
    rate_limit_key = f"login_{body.username}_{client_ip}"
    if not _check_login_rate_limit(rate_limit_key):
        raise HTTPException(status_code=429, detail="登录尝试过于频繁，请稍后再试")

    svc = get_auth_service()
    try:
        result = svc.login(username=body.username, password=body.password)
        # 登录成功，清除限流记录
        _clear_login_rate_limit(rate_limit_key)
        get_cooling_manager().clear_login_fails(client_ip)
    except ValueError as e:
        # 登录失败，记录冷却
        get_cooling_manager().record_login_failure(client_ip)
        raise HTTPException(status_code=401, detail=str(e))

    # 记录登录事件（设备/IP/区域）
    try:
        _record_login_event(request, result["user"]["id"])
    except Exception as e:
        logger.warning("记录登录事件失败: %s", e)

    return result


@router.post("/login/email", summary="邮箱登录")
async def login_by_email(body: EmailLoginRequest, request: Request):
    """使用邮箱登录，返回 JWT"""
    from auth_app.auth_service import get_auth_service
    from auth_app.security import (
        verify_turnstile_token,
        get_system_config,
        get_cooling_manager,
        get_ip_control_manager,
    )

    client_ip = request.client.host if request.client else "unknown"

    # 1) 检查登录开关
    if not get_system_config().is_login_enabled():
        raise HTTPException(status_code=403, detail="登录功能已关闭，请联系管理员")

    # 2) IP 黑名单检查
    if get_ip_control_manager().is_blacklisted(client_ip):
        logger.warning("登录拒绝: IP %s 在黑名单中", client_ip)
        raise HTTPException(status_code=403, detail="您的 IP 已被限制访问")

    # 3) 冷却检查
    cooling_level = get_cooling_manager().check_and_apply(client_ip)
    if cooling_level >= 2:
        raise HTTPException(status_code=429, detail="请求过于频繁，请稍后再试")
    if cooling_level >= 1:
        # Level 1: 强制 Turnstile 验证
        if not await verify_turnstile_token(body.turnstile_token, client_ip):
            raise HTTPException(status_code=400, detail="请完成人机验证后重试")

    # 4) 限流检查（原有）
    rate_limit_key = f"login_{body.email}_{client_ip}"
    if not _check_login_rate_limit(rate_limit_key):
        raise HTTPException(status_code=429, detail="登录尝试过于频繁，请稍后再试")

    svc = get_auth_service()
    try:
        result = svc.login_by_email(email=body.email, password=body.password)
        # 登录成功，清除限流记录
        _clear_login_rate_limit(rate_limit_key)
        get_cooling_manager().clear_login_fails(client_ip)
    except ValueError as e:
        # 登录失败，记录冷却
        get_cooling_manager().record_login_failure(client_ip)
        raise HTTPException(status_code=401, detail=str(e))

    # 记录登录事件
    try:
        _record_login_event(request, result["user"]["id"])
    except Exception as e:
        logger.warning("记录登录事件失败: %s", e)

    return result


def _record_login_event(request: Request, user_id: str) -> None:
    """记录登录事件到 login_events 表（同设备1小时内去重）"""
    import uuid
    from auth_app.database import get_db_instance

    db = get_db_instance()

    # 确保 login_events 表存在
    db.execute("""
        CREATE TABLE IF NOT EXISTS login_events (
            event_id     TEXT PRIMARY KEY,
            user_id      TEXT NOT NULL,
            ip_address   TEXT DEFAULT '',
            country      TEXT DEFAULT '',
            region       TEXT DEFAULT '',
            city         TEXT DEFAULT '',
            user_agent   TEXT DEFAULT '',
            device_type  TEXT DEFAULT '',
            browser      TEXT DEFAULT '',
            os           TEXT DEFAULT '',
            is_current   BOOLEAN DEFAULT FALSE,
            created_at   TIMESTAMP NOT NULL DEFAULT NOW()
        )
    """)

    # 提取 IP
    ip = request.headers.get("x-forwarded-for", "").split(",")[0].strip()
    if not ip:
        ip = request.client.host if request.client else ""

    # 解析 UA
    ua = request.headers.get("user-agent", "")
    ua_info = _parse_user_agent(ua)

    # 解析 IP 区域
    ip_info = _parse_ip_region(ip)

    # 检查同设备1小时内是否有记录（去重）
    existing = db.fetchone(
        """SELECT event_id FROM login_events
           WHERE user_id = %s
             AND ip_address = %s
             AND device_type = %s
             AND browser = %s
             AND os = %s
             AND created_at > NOW() - INTERVAL '1 hour'
           ORDER BY created_at DESC
           LIMIT 1""",
        (user_id, ip, ua_info["device_type"], ua_info["browser"], ua_info["os"]),
    )
    if existing:
        event_id = existing["event_id"]
        # 更新已有记录时间并标记为当前
        db.execute(
            "UPDATE login_events SET created_at = NOW() WHERE event_id = %s",
            (event_id,),
        )
        db.execute(
            "UPDATE login_events SET is_current = FALSE WHERE user_id = %s AND is_current = TRUE",
            (user_id,),
        )
        db.execute(
            "UPDATE login_events SET is_current = TRUE WHERE event_id = %s",
            (event_id,),
        )
        return

    # 清除之前的 is_current 标记
    db.execute(
        "UPDATE login_events SET is_current = FALSE WHERE user_id = %s AND is_current = TRUE",
        (user_id,),
    )

    # 插入新记录
    event_id = f"le_{uuid.uuid4().hex[:12]}"
    db.execute(
        """INSERT INTO login_events
           (event_id, user_id, ip_address, country, region, city,
            user_agent, device_type, browser, os, is_current, created_at)
           VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, TRUE, NOW())""",
        (event_id, user_id, ip, ip_info["country"], ip_info["region"], ip_info["city"],
         ua[:500], ua_info["device_type"], ua_info["browser"], ua_info["os"]),
    )


def _parse_user_agent(ua: str) -> dict:
    """解析 User-Agent"""
    if not ua:
        return {"device_type": "unknown", "browser": "unknown", "os": "unknown"}
    ua_lower = ua.lower()
    device_type = "desktop"
    if any(k in ua_lower for k in ["mobile", "android", "iphone", "ipod"]):
        device_type = "mobile"
    elif "ipad" in ua_lower or "tablet" in ua_lower:
        device_type = "tablet"
    browser = "unknown"
    if "edg/" in ua_lower or "edge" in ua_lower:
        browser = "Edge"
    elif "opr/" in ua_lower or "opera" in ua_lower:
        browser = "Opera"
    elif "firefox" in ua_lower:
        browser = "Firefox"
    elif "chrome" in ua_lower and "edg/" not in ua_lower:
        browser = "Chrome"
    elif "safari" in ua_lower and "chrome" not in ua_lower:
        browser = "Safari"
    os_name = "unknown"
    if "windows" in ua_lower:
        os_name = "Windows"
    elif "mac os" in ua_lower or "macos" in ua_lower:
        os_name = "macOS"
    elif "android" in ua_lower:
        os_name = "Android"
    elif "iphone" in ua_lower or "ipad" in ua_lower:
        os_name = "iOS"
    elif "linux" in ua_lower:
        os_name = "Linux"
    return {"device_type": device_type, "browser": browser, "os": os_name}


def _parse_ip_region(ip: str) -> dict:
    """解析 IP 区域"""
    if not ip or ip in ("127.0.0.1", "::1", "localhost"):
        return {"country": "本地", "region": "本地", "city": "本地网络"}
    if ip.startswith(("192.168.", "10.", "172.16.", "172.17.", "172.18.",
                       "172.19.", "172.2", "172.3")):
        return {"country": "内网", "region": "内网", "city": "局域网"}
    return {"country": "", "region": "", "city": ""}


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
    """获取当前登录用户信息（从数据库查询完整资料）"""
    from auth_app.auth_service import get_auth_service
    from auth_app.user_repo import get_user_repo

    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="未登录")

    token = auth_header.split(" ", 1)[1]
    svc = get_auth_service()
    token_user = svc.get_current_user(token)
    if not token_user:
        raise HTTPException(status_code=401, detail="令牌无效")

    # 从数据库查询完整用户资料（含 display_name、email、avatar_url 等）
    repo = get_user_repo()
    full_user = repo.find_by_id(token_user["user_id"])
    if not full_user:
        raise HTTPException(status_code=404, detail="用户不存在")

    return {k: v for k, v in full_user.items() if k != "password_hash"}


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
    updated = repo.find_by_id(user["user_id"])
    return {k: v for k, v in updated.items() if k != "password_hash"} if updated else {"ok": True}


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


# ── 头像存储 ──
AVATAR_DIR = Path(__file__).resolve().parent.parent / "avatars"
AVATAR_DIR.mkdir(parents=True, exist_ok=True)

# ── 头像上传端点 ──

@router.post("/avatar", summary="上传头像")
async def upload_avatar(request: Request, file: UploadFile = File(...)):
    """上传用户头像，返回头像 URL"""
    from auth_app.auth_service import get_auth_service
    from auth_app.user_repo import get_user_repo

    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="未登录")

    token = auth_header.split(" ", 1)[1]
    svc = get_auth_service()
    token_user = svc.get_current_user(token)
    if not token_user:
        raise HTTPException(status_code=401, detail="令牌无效")

    # 校验文件类型
    allowed = {"image/jpeg", "image/png", "image/gif", "image/webp"}
    if file.content_type not in allowed:
        raise HTTPException(status_code=400, detail="仅支持 JPG/PNG/GIF/WebP 格式")

    # 限制文件大小（5MB）
    contents = await file.read()
    if len(contents) > 5 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="头像文件不能超过 5MB")

    # 生成唯一文件名
    ext = {"image/jpeg": "jpg", "image/png": "png", "image/gif": "gif", "image/webp": "webp"}[file.content_type]
    filename = f"{token_user['user_id']}_{uuid.uuid4().hex[:8]}.{ext}"
    save_path = AVATAR_DIR / filename

    with open(save_path, "wb") as f:
        f.write(contents)

    # 更新用户 avatar_url
    avatar_url = f"/avatars/{filename}"
    repo = get_user_repo()
    repo.update_avatar(token_user["user_id"], avatar_url)

    return {"ok": True, "avatar_url": avatar_url}


# ═══════════════════════════════════════════════════════════
# 管理员安全配置 API（JWT super_admin 保护）
# ═══════════════════════════════════════════════════════════

def _require_admin(request: Request) -> dict:
    """验证请求是否为 super_admin 角色"""
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="未登录")
    token = auth_header.split(" ", 1)[1]
    from auth_app.jwt_service import get_jwt_service
    user = get_jwt_service().verify_token(token)
    if not user:
        raise HTTPException(status_code=401, detail="令牌无效")
    if user.get("role") != "super_admin":
        raise HTTPException(status_code=403, detail="需要 super_admin 权限")
    return user


# ── 系统配置管理 ──

@router.get("/admin/config", summary="获取系统安全配置")
async def admin_get_config(request: Request):
    """获取系统安全配置（super_admin）"""
    _require_admin(request)
    from auth_app.security import get_system_config
    cfg = get_system_config()
    return cfg.get_all()


@router.put("/admin/config", summary="更新系统安全配置")
async def admin_update_config(body: dict, request: Request):
    """更新系统安全配置（super_admin）
    
    支持字段:
      registration_enabled: "true" | "false"
      login_enabled: "true" | "false"
    """
    _require_admin(request)
    from auth_app.security import get_system_config
    cfg = get_system_config()
    allowed_keys = {"registration_enabled", "login_enabled"}
    updated = {}
    for key, value in body.items():
        if key in allowed_keys:
            cfg.set(key, str(value).lower())
            updated[key] = str(value).lower()
    return {"ok": True, "updated": updated}


# ── IP 管控管理 ──

@router.get("/admin/ip-controls", summary="列出 IP 管控列表")
async def admin_list_ip_controls(request: Request):
    """列出所有 IP 黑白名单（super_admin）"""
    _require_admin(request)
    from auth_app.security import get_ip_control_manager
    mgr = get_ip_control_manager()
    return {
        "blacklist": mgr.list_blacklist(),
        "whitelist": mgr.list_whitelist(),
    }


class AddIPControlRequest(BaseModel):
    ip: str
    list_type: str = Field(pattern=r"^(blacklist|whitelist)$")
    reason: str = ""
    expires_minutes: int = 0


@router.post("/admin/ip-controls", summary="添加 IP 管控")
async def admin_add_ip_control(body: AddIPControlRequest, request: Request):
    """添加 IP 到黑白名单（super_admin）"""
    admin_user = _require_admin(request)
    from auth_app.security import get_ip_control_manager
    mgr = get_ip_control_manager()
    created_by = admin_user.get("username", "admin")

    if body.list_type == "blacklist":
        mgr.add_blacklist(body.ip, reason=body.reason, expires_minutes=body.expires_minutes, created_by=created_by)
    else:
        mgr.add_whitelist(body.ip, reason=body.reason, created_by=created_by)

    return {"ok": True, "detail": f"IP {body.ip} 已加入{body.list_type}"}


@router.delete("/admin/ip-controls/{record_id}", summary="删除 IP 管控")
async def admin_delete_ip_control(record_id: int, request: Request):
    """删除 IP 管控记录（super_admin）"""
    _require_admin(request)
    from auth_app.security import get_ip_control_manager
    mgr = get_ip_control_manager()
    if mgr.delete_by_id(record_id):
        return {"ok": True, "detail": f"记录 {record_id} 已删除"}
    raise HTTPException(status_code=404, detail="记录不存在")


# ── 冷却状态管理 ──

@router.get("/admin/cooling", summary="获取攻击冷却状态")
async def admin_get_cooling(request: Request):
    """获取当前攻击冷却状态（super_admin）"""
    _require_admin(request)
    from auth_app.security import get_cooling_manager
    return get_cooling_manager().get_status()


@router.delete("/admin/cooling/{ip}", summary="解除某 IP 的冷却")
async def admin_remove_cooling(ip: str, request: Request):
    """手动解除某 IP 的冷却状态（super_admin）"""
    _require_admin(request)
    from auth_app.security import get_cooling_manager, get_ip_control_manager
    get_cooling_manager().remove_cooling(ip)
    # 也从 IP 黑名单中解除临时封禁
    try:
        get_ip_control_manager().remove(ip, "blacklist")
    except Exception:
        pass
    return {"ok": True, "detail": f"IP {ip} 冷却已解除"}


app.include_router(router)

# ── 静态文件（头像） ──
app.mount("/avatars", StaticFiles(directory=str(AVATAR_DIR)), name="avatars")


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


# ═══════════════════════════════════════════════════════════
# 反向代理中间件
# 将非认证 API 请求透明转发到主后端 (8000)
# 使认证网关成为统一的对外入口
#
# TODO: 部署 Nginx 统一网关后 HTTP 代理层可移除
#   Nginx 路由：/api/auth/* → auth-gateway, /api/* → backend
#   届时可删除：_proxy(), httpx.AsyncClient, _is_local(), _LOCAL_PREFIXES 等
# ═══════════════════════════════════════════════════════════

PROXY_TARGET = os.getenv("PROXY_TARGET", "http://127.0.0.1:8000")

# 认证网关自行处理的路径前缀
_LOCAL_PREFIXES = frozenset({
    "/api/auth/", "/avatars/",
})

# 认证网关自行处理的精确路径
_LOCAL_PATHS = frozenset({
    "/health", "/", "/docs", "/redoc", "/openapi.json",
})

# 以 _LOCAL_PREFIXES 开头但不应本地处理、应代理到主后端的路径
_PROXY_PATHS = frozenset({
    "/api/auth/me/login-history",
    "/api/auth/me/active-sessions",
})

# ═══════════════════════════════════════════════════════════
# WebSocket 安全配置
# ═══════════════════════════════════════════════════════════

# 允许的 Origin（逗号分隔，空 = 允许所有，生产应配置具体值）
_ALLOWED_ORIGINS = os.getenv("WS_ALLOWED_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000,http://192.168.13.133:3000,http://localhost:8080,http://127.0.0.1:8080,http://192.168.13.133:8080").split(",")

# 单 IP 最大 WS 连接数
_MAX_WS_PER_IP = int(os.getenv("WS_MAX_CONNECTIONS_PER_IP", "30"))

# WS 消息大小上限（字节）
_MAX_WS_MESSAGE_SIZE = int(os.getenv("WS_MAX_MESSAGE_SIZE", str(1024 * 1024)))  # 默认 1MB

# WS 连接追踪 {client_host: set[task]}
_ws_connections: dict[str, set[asyncio.Task]] = {}
_ws_lock = asyncio.Lock()


class ReverseProxyMiddleware:
    """ASGI 反向代理中间件（HTTP + WebSocket）"""

    def __init__(self, inner):
        self.inner = inner
        self.client = httpx.AsyncClient(
            base_url=PROXY_TARGET,
            timeout=60.0,
            follow_redirects=True,
        )

    async def __call__(self, scope, receive, send):
        # WebSocket 代理
        if scope["type"] == "websocket":
            return await self._proxy_ws(scope, receive, send)

        # HTTP 代理
        if scope["type"] != "http":
            return await self.inner(scope, receive, send)

        path = scope.get("path", "")

        # 认证网关本地处理
        if self._is_local(path):
            return await self.inner(scope, receive, send)

        # 反向代理到主后端
        await self._proxy(scope, receive, send)

    @staticmethod
    def _is_local(path: str) -> bool:
        if path in _LOCAL_PATHS:
            return True
        for prefix in _LOCAL_PREFIXES:
            if path.startswith(prefix):
                # 检查是否属于应代理的例外路径
                for proxy_path in _PROXY_PATHS:
                    if path.startswith(proxy_path):
                        return False
                return True
        return False

    async def _proxy_ws(self, scope, receive, send):
        """WebSocket 反向代理 — 安全加固版

        安全措施：
        1. JWT 验证：从 query ?token=xxx 提取并验证
        2. Origin 检查：只允许配置的来源
        3. 连接数限制：单 IP 上限 _MAX_WS_PER_IP
        4. 消息大小限制：超过 _MAX_WS_MESSAGE_SIZE 断开
        """
        path = scope.get("path", "/")
        qs = scope.get("query_string", b"").decode()
        client_ip = self._get_client_ip(scope)

        # ── 1. JWT 验证 ──
        params = parse_qs(qs, keep_blank_values=True)
        token = params.get("token", [""])[0]
        if not token:
            logger.warning("WS 拒绝: 无 token (ip=%s, path=%s)", client_ip, path)
            await send({"type": "websocket.close", "code": 4001})
            return

        from auth_app.jwt_service import get_jwt_service
        user = get_jwt_service().verify_token(token)
        if not user:
            logger.warning("WS 拒绝: token 无效 (ip=%s, path=%s)", client_ip, path)
            await send({"type": "websocket.close", "code": 4001})
            return

        # ── 2. Origin 检查 ──
        origin = ""
        for k, v in scope.get("headers", []):
            if k.decode("utf-8", "ignore").lower() == "origin":
                origin = v.decode("utf-8", "ignore")
                break
        if _ALLOWED_ORIGINS and origin:
            origin_ok = False
            for allowed in _ALLOWED_ORIGINS:
                allowed = allowed.strip()
                if allowed and (origin == allowed or origin.startswith(allowed.rstrip("/") + "/")):
                    origin_ok = True
                    break
            if not origin_ok:
                logger.warning("WS 拒绝: Origin 不允许 (origin=%s, ip=%s)", origin, client_ip)
                await send({"type": "websocket.close", "code": 4003})
                return

        # ── 3. 连接数限制 ──
        async with _ws_lock:
            ip_connections = _ws_connections.setdefault(client_ip, set())
            if len(ip_connections) >= _MAX_WS_PER_IP:
                logger.warning("WS 拒绝: 连接数超限 (ip=%s, count=%d)", client_ip, len(ip_connections))
                await send({"type": "websocket.close", "code": 4003})
                return

            # ── 构建目标 WS URL（不转发 token，注入 user_id）──
            # 过滤掉 token 参数，避免后端日志/调试泄漏
            clean_qs_parts = [p for p in qs.split("&") if not p.startswith("token=") and p]
            # 注入 user_id（从 JWT 解析得到）
            user_id = user.get("user_id", "")
            clean_qs_parts.append(f"user_id={user_id}")
            clean_qs = "&".join(clean_qs_parts) if clean_qs_parts else ""
            target_path_no_qs = path.split("?")[0]
            target_path = f"{target_path_no_qs}?{clean_qs}" if clean_qs else target_path_no_qs

            target_ws_base = PROXY_TARGET.replace("http://", "ws://").replace("https://", "wss://")
            target_url = f"{target_ws_base}{target_path}"

            # 提取 headers（过滤 WS 握手专用头）
            extra_headers = []
            for k, v in scope.get("headers", []):
                key = k.decode("utf-8", "ignore")
                val = v.decode("utf-8", "ignore")
                if key.lower() not in (
                    "host", "upgrade", "connection",
                    "sec-websocket-key", "sec-websocket-version",
                    "sec-websocket-extensions", "origin",
                ):
                    extra_headers.append((key, val))

            # 注册连接追踪
            proxy_task = asyncio.current_task()
            ip_connections.add(proxy_task)

        # ── 先 accept 客户端 WS 连接（避免 uvicorn 裸 403 拒绝）──
        # 若后端连接失败，通过 WS 发错误消息给客户端
        await send({"type": "websocket.accept"})

        _backend_ws: websockets.WebSocketClientProtocol | None = None
        try:
            _backend_ws = await websockets.connect(
                target_url,
                additional_headers=extra_headers,
                ping_interval=20,
                ping_timeout=10,
                max_size=10 * 1024 * 1024,  # 10MB
            )
        except Exception as e:
            logger.error("WS 后端连接失败 (path=%s, ip=%s): %s", path, client_ip, e)
            err_msg = json.dumps({"type": "error", "message": "后端服务暂不可用，请稍后重试"})
            try:
                await send({"type": "websocket.send", "text": err_msg})
            except Exception:
                pass
            try:
                await send({"type": "websocket.close", "code": 1011})
            except Exception:
                pass
            # 清理连接追踪
            async with _ws_lock:
                ip_set = _ws_connections.get(client_ip)
                if ip_set:
                    ip_set.discard(proxy_task)
                    if not ip_set:
                        _ws_connections.pop(client_ip, None)
            return

        backend_ws = _backend_ws

        async def client_to_backend():
            """转发客户端消息 → 后端（含消息大小校验）"""
            while True:
                msg = await receive()
                if msg["type"] == "websocket.receive":
                    if "text" in msg and len(msg["text"]) > _MAX_WS_MESSAGE_SIZE:
                        logger.warning("WS 消息超限: %d bytes (ip=%s)", len(msg["text"]), client_ip)
                        await backend_ws.close(code=1009)
                        break
                    if "bytes" in msg and len(msg["bytes"]) > _MAX_WS_MESSAGE_SIZE:
                        logger.warning("WS 消息超限: %d bytes (ip=%s)", len(msg["bytes"]), client_ip)
                        await backend_ws.close(code=1009)
                        break
                    if "text" in msg:
                        await backend_ws.send(msg["text"])
                    elif "bytes" in msg:
                        await backend_ws.send(msg["bytes"])
                elif msg["type"] == "websocket.disconnect":
                    break

        async def backend_to_client():
            """转发后端消息 → 客户端"""
            async for msg in backend_ws:
                if isinstance(msg, str):
                    await send({"type": "websocket.send", "text": msg})
                elif isinstance(msg, bytes):
                    await send({"type": "websocket.send", "bytes": msg})

        # 双向并发转发
        tasks = [
            asyncio.create_task(client_to_backend()),
            asyncio.create_task(backend_to_client()),
        ]
        try:
            await asyncio.gather(*tasks)
        except Exception:
            for t in tasks:
                t.cancel()
        finally:
            # 清理连接追踪
            async with _ws_lock:
                ip_set = _ws_connections.get(client_ip)
                if ip_set:
                    ip_set.discard(proxy_task)
                    if not ip_set:
                        _ws_connections.pop(client_ip, None)

    @staticmethod
    def _get_client_ip(scope) -> str:
        """从 scope 提取客户端 IP"""
        # 优先取 X-Forwarded-For（通过代理转发时）
        for k, v in scope.get("headers", []):
            if k.decode("utf-8", "ignore").lower() == "x-forwarded-for":
                return v.decode("utf-8", "ignore").split(",")[0].strip()
        # 其次取 peer 地址
        client_info = scope.get("client")
        if client_info:
            return client_info[0]
        return "unknown"

    async def _proxy(self, scope, receive, send):
        """读取请求 → 转发到主后端 → 返回响应"""
        # 读取请求体
        body = b""
        more = True
        while more:
            msg = await receive()
            if msg["type"] == "http.request":
                body += msg.get("body", b"")
                more = msg.get("more_body", False)
            else:
                break

        # 构建转发请求
        method = scope.get("method", "GET")
        path = scope.get("path", "/")
        qs = scope.get("query_string", b"").decode()
        url = f"{path}?{qs}" if qs else path

        # 提取 headers（过滤掉 host）
        headers = {}
        for k, v in scope.get("headers", []):
            key = k.decode("utf-8", "ignore").lower()
            if key == "host":
                continue
            headers[key] = v.decode("utf-8", "ignore")

        try:
            resp = await self.client.request(
                method=method,
                url=url,
                headers=headers,
                content=body,
            )

            # 构建响应 headers
            resp_headers = []
            for k, v in resp.headers.items():
                k_lower = k.lower()
                if k_lower in ("transfer-encoding", "content-encoding", "content-length"):
                    continue
                # 修正 Location 重定向地址
                if k_lower == "location" and v.startswith("http://127.0.0.1:8000"):
                    v = v.replace("http://127.0.0.1:8000", "")
                resp_headers.append([k.encode(), v.encode()])

            await send({
                "type": "http.response.start",
                "status": resp.status_code,
                "headers": resp_headers,
            })
            await send({
                "type": "http.response.body",
                "body": resp.content,
            })

        except httpx.ConnectError:
            logger.error("主后端不可达: %s", PROXY_TARGET)
            await send({
                "type": "http.response.start",
                "status": 502,
                "headers": [[b"content-type", b"application/json"]],
            })
            await send({
                "type": "http.response.body",
                "body": b'{"error":"upstream_unavailable","detail":"\xe4\xb8\xbb\xe5\x90\x8e\xe7\xab\xaf\xe6\x9c\x8d\xe5\x8a\xa1\xe4\xb8\x8d\xe5\x8f\xaf\xe7\x94\xa8"}',
            })
        except Exception as e:
            logger.error("反向代理错误: %s", e)
            await send({
                "type": "http.response.start",
                "status": 500,
                "headers": [[b"content-type", b"application/json"]],
            })
            await send({
                "type": "http.response.body",
                "body": b'{"error":"proxy_error"}',
            })


# 用反向代理中间件包装 app（uvicorn 加载的 app 是 wrap 后的版本）
app = ReverseProxyMiddleware(app)
