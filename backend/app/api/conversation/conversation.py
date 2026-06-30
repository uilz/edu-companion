"""
对话系统 API 路由

此文件为聚合路由器，从子模块导入并挂载：
  - conversation_routes.py  — REST 端点（树 CRUD、消息、工作空间、子支）
  - 统一消息端点（SSE 流式）— 在 conversation_routes 中通过 action 区分

所有路由前缀由 main.py 统一设置为 /api/conversations
"""

from __future__ import annotations

from fastapi import APIRouter  # type: ignore

from app.api.conversation.conversation_routes import router as rest_router

router = APIRouter()

router.include_router(rest_router)
