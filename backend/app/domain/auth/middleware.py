"""
认证中间件 — 调用独立认证网关验证用户身份

策略：
1. 从请求中提取 JWT token
2. 调用认证网关 /api/auth/verify 验证令牌
3. 将验证结果注入 request.state.user 和 request.state.user_id
4. 未携带令牌时使用 default_user（兼容期）

认证网关地址：http://127.0.0.1:8001
"""
from __future__ import annotations

import logging
import urllib.request
import urllib.error
import json
from typing import Optional

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from shared.constants import DEFAULT_USER_ID

logger = logging.getLogger(__name__)

# 认证网关地址
AUTH_GATEWAY_URL = "http://127.0.0.1:18001"

# 不需要认证的路径前缀
PUBLIC_PATHS = {
    "/api/auth",
    "/docs",
    "/redoc",
    "/openapi.json",
    "/health",
    "/",
}


class AuthMiddleware(BaseHTTPMiddleware):
    """认证中间件 — 调用独立认证网关"""

    async def dispatch(self, request: Request, call_next):
        path = request.url.path

        # 静态资源等跳过
        if not path.startswith("/api") and path not in ("/health", "/"):
            request.state.user = None
            request.state.user_id = DEFAULT_USER_ID
            return await call_next(request)

        # 公开路径跳过认证
        is_public = any(path.startswith(p) for p in PUBLIC_PATHS)
        if is_public:
            request.state.user = None
            request.state.user_id = DEFAULT_USER_ID
            return await call_next(request)

        # 提取 token
        token = self._extract_token(request)

        if token:
            user = self._verify_token(token)
            if user:
                request.state.user = user
                request.state.user_id = user["user_id"]
                return await call_next(request)

        # 兼容期：未认证时使用 default_user
        request.state.user = None
        request.state.user_id = DEFAULT_USER_ID
        return await call_next(request)

    @staticmethod
    def _extract_token(request: Request) -> Optional[str]:
        """从请求中提取 JWT"""
        # 1. Authorization header
        auth_header = request.headers.get("authorization", "")
        if auth_header.startswith("Bearer "):
            return auth_header[7:].strip()

        # 2. 查询参数（WebSocket 兼容）
        token = request.query_params.get("token")
        if token:
            return token

        # 3. Cookie
        token = request.cookies.get("access_token")
        if token:
            return token

        return None

    @staticmethod
    def _verify_token(token: str) -> Optional[dict]:
        """调用认证网关验证令牌"""
        try:
            data = json.dumps({"token": token}).encode("utf-8")
            req = urllib.request.Request(
                f"{AUTH_GATEWAY_URL}/api/auth/verify",
                data=data,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=2) as resp:
                result = json.loads(resp.read().decode("utf-8"))
                if result.get("valid"):
                    return {
                        "user_id": result["user_id"],
                        "username": result["username"],
                        "role": result.get("role", "user"),
                    }
        except Exception as e:
            logger.warning("认证网关验证失败: %s", e)
        return None


def get_request_user_id(request: Request) -> str:
    """从请求状态获取当前用户 ID（供 API 层使用）"""
    return getattr(request.state, "user_id", DEFAULT_USER_ID)


def get_request_user(request: Request) -> Optional[dict]:
    """从请求状态获取当前用户信息（供 API 层使用）"""
    return getattr(request.state, "user", None)
