"""
Admin 子应用 — 独立 FastAPI 应用（端口 8001）

设计：
- 独立进程、独立端口，便于独立部署 / 灰度 / 审计
- 复用主应用的所有 shared/* 与 app/cognitive/* 仓库
- 强制使用 require_admin / require_role 鉴权，无认证网关 fallback
- 注册到主应用的 /admin/* 反向代理（可选）或直接 8001 访问

启动：
    cd backend && venv/bin/python -m app_admin.main
"""
from __future__ import annotations

import logging
import sys
from pathlib import Path

# 让 app_admin 能 import backend.app.* 与 shared.*
_BACKEND_ROOT = Path(__file__).resolve().parent.parent
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app_admin.deps import AdminAuthMiddleware  # noqa: E402

from app_admin.routers import users, data, monitor, analytics, settings  # noqa: E402

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("app_admin")

_fastapi_app = FastAPI(
    title="Edu Companion Admin",
    version="1.0.0",
    description="独立管理子应用 — 跨用户 CRUD / 监控 / BI / 用户角色",
    docs_url="/admin/docs",
    openapi_url="/admin/openapi.json",
)

# CORS（独立部署时 admin 前端 3001 可访问）
_fastapi_app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3001", "http://127.0.0.1:3001"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 挂载 5 个模块路由（必须在中间件 wrap 之前）
_fastapi_app.include_router(users.router, prefix="/api/admin/users", tags=["用户管理"])
_fastapi_app.include_router(data.router, prefix="/api/admin/data", tags=["全局数据"])
_fastapi_app.include_router(monitor.router, prefix="/api/admin/monitor", tags=["系统监控"])
_fastapi_app.include_router(analytics.router, prefix="/api/admin/analytics", tags=["BI 分析"])
_fastapi_app.include_router(settings.router, prefix="/api/admin/settings", tags=["系统设置"])


@_fastapi_app.get("/admin/health")
async def health():
    return {"ok": True, "service": "app_admin", "version": "1.0.0"}


@_fastapi_app.get("/")
async def root():
    return {
        "service": "Edu Companion Admin",
        "docs": "/admin/docs",
        "modules": ["/api/admin/users", "/api/admin/data", "/api/admin/monitor", "/api/admin/analytics"],
    }


# 纯 ASGI 中间件 wrap（uvicorn 加载的 `app` 是 wrap 后的版本）
app = AdminAuthMiddleware(_fastapi_app)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app_admin.main:app", host="0.0.0.0", port=8001, reload=False, log_level="info")
