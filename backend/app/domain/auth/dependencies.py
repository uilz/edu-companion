"""
FastAPI 依赖注入 — 当前用户

用法:
    @router.get("/something")
    async def handler(user_id: str = Depends(current_user_id)):
        ...

这样所有端点自动从认证中间件获取 user_id，
同时保持查询参数 ?user_id=xxx 的向后兼容。
"""
from __future__ import annotations

from fastapi import Depends, Request

from shared.constants import DEFAULT_USER_ID, get_user_id_from_request


def current_user_id(request: Request) -> str:
    """依赖注入：获取当前用户 ID

    优先级：
    1. 认证中间件注入的 request.state.user_id
    2. 查询参数 user_id
    3. 默认值 DEFAULT_USER_ID
    """
    return get_user_id_from_request(request)


def require_auth(request: Request) -> str:
    """依赖注入：要求已认证用户，否则 401"""
    user = getattr(request.state, "user", None)
    if not user:
        from fastapi import HTTPException
        raise HTTPException(status_code=401, detail="请先登录")
    return request.state.user_id
