"""
认证中间件 — 调用独立认证网关验证用户身份

策略：
1. 从请求中提取 JWT token
2. 调用认证网关 /api/auth/verify 验证令牌
3. 将验证结果注入 request.state.user 和 request.state.user_id
4. 未携带 token / token 无效：除公开路径外，**返回 401**，不再隐式 fallback 到 default_user

认证网关地址：http://127.0.0.1:18001
"""
from __future__ import annotations

import logging
import urllib.request
import urllib.error
import json
from typing import Optional, Any

logger = logging.getLogger(__name__)

# 认证网关地址
AUTH_GATEWAY_URL = "http://127.0.0.1:18001"

# 不需要认证的路径前缀
# 注意：不要把 "/" 放进来 — 所有路径都以 "/" 开头，会导致 is_public 永远 True
PUBLIC_PATHS = {
    "/api/auth",
    "/docs",
    "/redoc",
    "/openapi.json",
    "/health",
}


class AuthMiddleware:
    """认证中间件 — 纯 ASGI 实现"""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)

        path = scope.get("path", "")

        # 静态资源等跳过
        if not path.startswith("/api") and path not in ("/health", "/"):
            return await self.app(scope, receive, send)

        # 公开路径
        is_public = any(path.startswith(p) for p in PUBLIC_PATHS)
        if is_public:
            return await self.app(scope, receive, send)

        # 提取 token
        token = self._extract_token_from_scope(scope)
        user = self._verify_token(token) if token else None

        if not user:
            # 未认证：返回 401
            body = json.dumps({"detail": "未登录或令牌已失效，请重新登录"}).encode("utf-8")
            await send({
                "type": "http.response.start",
                "status": 401,
                "headers": [(b"content-type", b"application/json")],
            })
            await send({"type": "http.response.body", "body": body})
            return

        # 注入 user 信息到 scope.state（FastAPI 路由可读取）
        scope = dict(scope)
        scope["state"] = dict(scope.get("state") or {})
        scope["state"]["user"] = user
        scope["state"]["user_id"] = user["user_id"]
        return await self.app(scope, receive, send)

    @staticmethod
    def _extract_token_from_scope(scope) -> Optional[str]:
        # 1. Authorization header
        for k, v in scope.get("headers", []):
            if k == b"authorization" and v.startswith(b"Bearer "):
                return v[7:].strip().decode("utf-8", "ignore")
        # 2. query param token
        qs = scope.get("query_string", b"").decode("utf-8", "ignore")
        for kv in qs.split("&"):
            if kv.startswith("token="):
                return kv.split("=", 1)[1]
        # 3. cookie access_token (查 header)
        for k, v in scope.get("headers", []):
            if k == b"cookie":
                cookie_str = v.decode("utf-8", "ignore")
                for part in cookie_str.split(";"):
                    name, _, val = part.strip().partition("=")
                    if name == "access_token":
                        return val
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


def get_request_user_id(request: Any) -> str:
    """从请求状态获取当前用户 ID（供 API 层使用）"""
    return getattr(request.state, "user_id", None)


def get_request_user(request: Any) -> Optional[dict]:
    """从请求状态获取当前用户信息（供 API 层使用）"""
    return getattr(request.state, "user", None)
