"""
Admin 鉴权依赖 — FastAPI Dependency

独立子应用 `app_admin` 强制使用此中间件，
杜绝"忘记加 is_admin 检查"的常见事故。

设计：
- 中间件直接本地解码 JWT（HS256，与主应用共享 JWT_SECRET）
- 不调外部认证网关（admin 进程独立部署，避免循环依赖）
- 强制要求 is_admin 角色（最低 super_admin），否则 401/403

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

import logging
from typing import Iterable, Optional

import jwt
from fastapi import Depends, HTTPException, Request, status
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request as StarletteRequest

from app.config import settings
from shared.constants import DEFAULT_USER_ID

logger = logging.getLogger(__name__)

JWT_SECRET = settings.openai_api_key or "edu-companion-jwt-secret-change-me"
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


class AdminAuthMiddleware(BaseHTTPMiddleware):
    """admin 进程的鉴权中间件（本地 JWT 解码，不调外部服务）"""

    async def dispatch(self, request: StarletteRequest, call_next):
        path = request.url.path

        # 公开路径
        if path in PUBLIC_PATHS or path.startswith("/admin/docs"):
            request.state.user = None
            request.state.user_id = DEFAULT_USER_ID
            return await call_next(request)

        token = self._extract_token(request)
        if not token:
            request.state.user = None
            request.state.user_id = DEFAULT_USER_ID
            return await call_next(request)

        payload = _decode_jwt(token)
        if not payload:
            request.state.user = None
            request.state.user_id = DEFAULT_USER_ID
            return await call_next(request)

        request.state.user = {
            "user_id": payload.get("sub", ""),
            "username": payload.get("username", ""),
            "role": payload.get("role", "user"),
        }
        request.state.user_id = request.state.user["user_id"]
        return await call_next(request)

    @staticmethod
    def _extract_token(request: StarletteRequest) -> Optional[str]:
        auth = request.headers.get("authorization", "")
        if auth.startswith("Bearer "):
            return auth[7:].strip()
        return request.cookies.get("access_token") or request.query_params.get("token")


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
