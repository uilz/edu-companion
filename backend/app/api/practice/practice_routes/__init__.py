"""智能题库系统 API — 子域拆分

路由前缀: /api/practice
"""
from __future__ import annotations

from fastapi import APIRouter

from . import banks, generation, sessions, errors, stats, import_routes, misc, quality_routes, references

router = APIRouter(prefix="/api/practice", tags=["题库"])
router.include_router(banks.router)
router.include_router(generation.router)
router.include_router(sessions.router)
router.include_router(errors.router)
router.include_router(stats.router)
router.include_router(import_routes.router)
router.include_router(misc.router)
router.include_router(quality_routes.router)
router.include_router(references.router)
