"""
对话系统 API 路由 v5.0 归一化

此文件为聚合路由器，从子模块导入并挂载：
  - conversation_routes.py  — REST 端点（树 CRUD、消息、工作空间、子支）
  - stream_sse.py           — SSE 流式对话（替代 WebSocket）

所有路由前缀由 main.py 统一设置为 /api/conversations
"""

from __future__ import annotations

from fastapi import APIRouter  # type: ignore

from app.api.conversation.conversation_routes import router as rest_router
from app.api.conversation.stream_sse import router as sse_router

router = APIRouter()

# REST 端点（无额外 prefix，路径已包含完整前缀如 /tree/{level}）
router.include_router(rest_router)

# SSE 流式端点（路径如 /stream/{cid}）
router.include_router(sse_router)
