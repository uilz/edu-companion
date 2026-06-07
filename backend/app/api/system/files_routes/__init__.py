"""文件管理 API — 子域拆分：上传/浏览/管理"""
from __future__ import annotations

from fastapi import APIRouter

from .upload import router as upload_router
from .browse import router as browse_router
from .manage import router as manage_router
from .upload import recover_stuck_files

router = APIRouter()
router.include_router(upload_router)
router.include_router(browse_router)
router.include_router(manage_router)

__all__ = ["router", "recover_stuck_files"]
