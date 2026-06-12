"""
认证中间件 — 本地 JWT 解码（不调外部网关）

策略：
1. 从请求中提取 JWT token
2. 本地解码 JWT（HS256，与 auth-gateway 共享 JWT_SECRET）
3. 将验证结果注入 request.state.user 和 request.state.user_id
4. 未携带 token / token 无效：除公开路径外，**返回 401**

性能：本地 HMAC-SHA256 解码 ~0.01ms，对比 HTTP 调网关 3-10ms
"""
from __future__ import annotations

import logging
import os
from typing import Optional, Any

import jwt

logger = logging.getLogger(__name__)

# JWT 密钥必须与 auth-gateway 一致
JWT_SECRET = os.getenv("JWT_SECRET")
if not JWT_SECRET:
    raise RuntimeError("JWT_SECRET environment variable is not set")
JWT_ALGORITHM = "HS256"

# 不需要认证的路径前缀
PUBLIC_PATHS = frozenset({
    "/api/auth/login",
    "/api/auth/register",
    "/api/auth/refresh",
    "/api/auth/verify",
    "/docs",
    "/redoc",
    "/openapi.json",
    "/health",
})


class AuthMiddleware:
    """认证中间件 — 纯 ASGI 实现，本地解码 JWT"""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)

        path = scope.get("path", "")

        # 非 API 路径跳过
        if not path.startswith("/api") and path not in ("/health", "/"):
            return await self.app(scope, receive, send)

        # 公开路径直接放行
        if path in PUBLIC_PATHS:
            return await self.app(scope, receive, send)

        # 提取并验证 token
        token = self._extract_token(scope)
        user = self._verify_token(token) if token else None

        if not user:
            body = ("{\"detail\":\"未登录或令牌已失效，请重新登录\"}").encode("utf-8")
            await send({
                "type": "http.response.start",
                "status": 401,
                "headers": [(b"content-type", b"application/json")],
            })
            await send({"type": "http.response.body", "body": body})
            return

        # 注入用户信息
        scope = dict(scope)
        scope["state"] = dict(scope.get("state") or {})
        scope["state"]["user"] = user
        scope["state"]["user_id"] = user["user_id"]
        return await self.app(scope, receive, send)

    @staticmethod
    def _extract_token(scope: dict) -> Optional[str]:
        """从 ASGI scope 提取 JWT token"""
        # 1. Authorization header
        for k, v in scope.get("headers", []):
            if k == b"authorization" and v.startswith(b"Bearer "):
                return v[7:].strip().decode("utf-8", "ignore")
        # 2. Query param
        qs = scope.get("query_string", b"").decode("utf-8", "ignore")
        for kv in qs.split("&"):
            if kv.startswith("token="):
                return kv.split("=", 1)[1]
        # 3. Cookie
        for k, v in scope.get("headers", []):
            if k == b"cookie":
                for part in v.decode("utf-8", "ignore").split(";"):
                    name, _, val = part.strip().partition("=")
                    if name == "access_token":
                        return val
        return None

    @staticmethod
    def _verify_token(token: str) -> Optional[dict]:
        """本地解码 JWT（HS256，共享 JWT_SECRET）"""
        try:
            payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
            if payload.get("type") not in (None, "access"):
                return None
            return {
                "user_id": payload["sub"],
                "username": payload.get("username", ""),
                "role": payload.get("role", "user"),
            }
        except jwt.ExpiredSignatureError:
            return None
        except jwt.InvalidTokenError:
            return None


def get_request_user_id(request: Any) -> str:
    """从请求状态获取当前用户 ID"""
    return getattr(request.state, "user_id", None)


def get_request_user(request: Any) -> Optional[dict]:
    """从请求状态获取当前用户信息"""
    return getattr(request.state, "user", None)
