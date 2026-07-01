"""
Admin 鉴权依赖 — FastAPI Dependency

独立子应用 `app_admin` 强制使用此中间件，
杜绝"忘记加 is_admin 检查"的常见事故。

设计：
- 中间件直接本地解码 JWT（HS256，与主应用共享 JWT_SECRET）
- 不调外部认证网关（admin 进程独立部署，避免循环依赖）
- 强制要求 is_admin 角色（最低 super_admin），否则 401/403
- 认证通过后 fire-and-forget 刷新 last_active_at（与主应用共用节流策略）

使用：
    from app_admin.deps import require_admin, require_role

    @router.get("/users")
    async def list_users(_: dict = Depends(require_admin)):
        ...

    @router.post("/users/{id}/role")
    async def set_role(_: dict = Depends(require_role("super_admin"))):
        ...
"""
from __future__ import annotations

import asyncio
import logging
import os
from pathlib import Path
from typing import Optional

import jwt
from fastapi import Depends, HTTPException, Request, status

logger = logging.getLogger(__name__)

# ── 加载 auth-gateway 的 .env 配置（与网关共享 JWT_SECRET）──
_AUTH_GATEWAY_ENV = Path(__file__).resolve().parents[2] / "auth-gateway" / "config" / ".env"
if _AUTH_GATEWAY_ENV.exists():
    with open(_AUTH_GATEWAY_ENV) as _f:
        for _line in _f:
            _line = _line.strip()
            if not _line or _line.startswith("#") or "=" not in _line:
                continue
            _key, _, _val = _line.partition("=")
            os.environ.setdefault(_key.strip(), _val.strip())

# JWT 密钥必须与 auth-gateway 一致
JWT_SECRET = os.getenv("JWT_SECRET")
if not JWT_SECRET:
    raise RuntimeError("JWT_SECRET environment variable is not set")
JWT_ALGORITHM = "HS256"


# RBAC 角色等级（数值越大权限越高）
ROLE_RANK: dict[str, int] = {
    "user": 0,
    "analyst": 10,       # 只读 BI / 监控
    "data_admin": 20,    # 跨用户 CRUD 数据
    "super_admin": 30,   # 全部权限（含用户管理、角色分配）
}


# ═══════════════════════════════════════════════════════════
# 本地 JWT 验证中间件（admin 进程独立使用，不调外部网关）
# 纯 ASGI 实现，避免 BaseHTTPMiddleware request.state 不传播的问题
# ═══════════════════════════════════════════════════════════

PUBLIC_PATHS = {
    "/admin/health",
    "/admin/docs",
    "/admin/openapi.json",
    "/docs",
    "/redoc",
    "/openapi.json",
    "/",
}


def _decode_jwt(token: str) -> Optional[dict]:
    """本地解码 JWT（HS256，admin 进程共用主应用的 JWT_SECRET）"""
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        if payload.get("type") not in (None, "access"):
            return None
        return payload
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None


class AdminAuthMiddleware:
    """admin 进程的鉴权中间件 — 纯 ASGI 实现

    仅做 JWT 解码 + RBAC 角色校验。admin 本地运行不对外开放，
    无需 IP 白名单、冷却、限流等复杂安全机制。"""

    def __init__(self, app):
        self.app = app

    @staticmethod
    def _extract_token(scope: dict) -> Optional[str]:
        """从 ASGI scope 提取 Bearer token"""
        # 1. Authorization header
        for k, v in scope.get("headers", []):
            if k == b"authorization" and v.startswith(b"Bearer "):
                return v[7:].strip().decode("utf-8", "ignore")
        # 2. Cookie
        for k, v in scope.get("headers", []):
            if k == b"cookie":
                for part in v.decode("utf-8", "ignore").split(";"):
                    name, _, val = part.strip().partition("=")
                    if name == "access_token":
                        return val
        return None

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)

        path = scope.get("path", "")

        # 公开路径，不限制
        if path in PUBLIC_PATHS or path.startswith("/admin/docs"):
            return await self.app(scope, receive, send)

        # 提取 token 并验证
        token = self._extract_token(scope)
        user = None
        if token:
            payload = _decode_jwt(token)
            if payload:
                user = {
                    "user_id": payload.get("sub", ""),
                    "username": payload.get("username", ""),
                    "role": payload.get("role", "user"),
                }

        # 注入到 scope.state
        scope = dict(scope)
        scope["state"] = dict(scope.get("state") or {})
        scope["state"]["user"] = user
        scope["state"]["user_id"] = user["user_id"] if user else None
        # fire-and-forget 触发 last_active_at 刷新（5 分钟节流）
        if user:
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    asyncio.create_task(_admin_touch_active(user["user_id"]))
            except RuntimeError:
                pass
        return await self.app(scope, receive, send)

    @staticmethod
    async def _send_json_response(send, status_code: int, body: dict):
        """发送 JSON 响应"""
        import json
        data = json.dumps(body, ensure_ascii=False).encode("utf-8")
        await send({
            "type": "http.response.start",
            "status": status_code,
            "headers": [
                (b"content-type", b"application/json; charset=utf-8"),
                (b"content-length", str(len(data)).encode()),
            ],
        })
        await send({
            "type": "http.response.body",
            "body": data,
        })


# ═══════════════════════════════════════════════════════════
# 角色依赖
# ═══════════════════════════════════════════════════════════

def _resolve_user(request: Request) -> Optional[dict]:
    """从 request.state 提取用户（由 AdminAuthMiddleware 注入）"""
    user = getattr(request.state, "user", None)
    if user and isinstance(user, dict) and user.get("user_id"):
        return user
    return None


def get_current_user_optional(request: Request) -> Optional[dict]:
    return _resolve_user(request)


async def require_admin(request: Request) -> dict:
    """要求 super_admin 角色"""
    user = _resolve_user(request)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="未认证（admin 子应用需要 super_admin 角色）",
        )
    role = user.get("role", "user")
    if ROLE_RANK.get(role, 0) < ROLE_RANK["super_admin"]:
        logger.warning("admin 鉴权拒绝: user=%s role=%s", user.get("user_id"), role)
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"需要 super_admin 角色（当前：{role}）",
        )
    return user


# ── 活跃时间节流刷新 ──

ADMIN_LAST_ACTIVE_THROTTLE_SEC = 300


async def _admin_touch_active(user_id: str) -> None:
    """异步刷新 last_active_at（DB 内 5 分钟节流，失败仅记日志）"""
    try:
        from app.infrastructure.db.auth_repository import UserRepo
        UserRepo().touch_last_active(user_id, throttle_sec=ADMIN_LAST_ACTIVE_THROTTLE_SEC)
    except Exception as e:
        logger.debug("admin touch_last_active failed for %s: %s", user_id, e)


def require_role(min_role: str):
    """要求最低角色等级（RBAC 等级制）

    示例：
        Depends(require_role("analyst"))     ← analyst / data_admin / super_admin 均可
        Depends(require_role("data_admin"))  ← data_admin / super_admin 可
    """
    threshold = ROLE_RANK.get(min_role, 0)
    if threshold <= 0:
        raise ValueError(f"非法角色：{min_role}")

    async def _checker(request: Request) -> dict:
        user = _resolve_user(request)
        if not user:
            raise HTTPException(401, "未认证")
        role = user.get("role", "user")
        if ROLE_RANK.get(role, 0) < threshold:
            raise HTTPException(403, f"需要 {min_role}+ 角色（当前：{role}）")
        return user

    return _checker
