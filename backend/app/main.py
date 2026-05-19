"""
智能学习伴侣 - FastAPI 主入口

功能：
- WebSocket 实时聊天（流式输出）
- REST API（学习计划、练习题、进度跟踪、内容搜索）
- 健康检查端点
- CORS 支持
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.chat import router as chat_router
from app.api.study import router as study_router
from app.api.practice import router as practice_router
from app.api.practice_errors import router as practice_errors_router
from app.api.practice_analytics import router as practice_analytics_router
from app.api.practice_quality import router as practice_quality_router
from app.api.progress import router as progress_router
from app.api.content import router as content_router
from app.api.conversation import router as conversation_router
from app.api.material import router as material_router
from app.api.knowledge import router as knowledge_router
from app.api.multimodal import router as multimodal_router
from app.api.achievements import router as achievements_router
from app.api.search import router as search_router
from app.config import settings
from app.core.learner_model import learner_engine

# 配置日志
logging.basicConfig(
    level=logging.DEBUG if settings.debug else logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


def _init_uncategorized_partition():
    """P5: 确保「未分类」默认分区存在"""
    from app.services.storage import storage
    from app.schemas.conversation import Partition

    data = storage.load("default_user")
    uncat_id = "__uncategorized__"
    if uncat_id not in data.partitions:
        import time
        root_id = f"root_{uncat_id}"
        partition = Partition(
            id=uncat_id,
            name="未分类",
            subject="未分类",
            direction="subject",
            emoji="📦",
            color="#9CA3AF",
            root_id=root_id,
            created_at=time.time(),
            updated_at=time.time(),
            last_active_at=time.time(),
        )
        data.partitions[uncat_id] = partition
        storage.save("default_user", data)
        logger.info("📦 已创建「未分类」默认分区")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """
    应用生命周期管理

    启动时：
    - 初始化 LLM 服务
    - 初始化学习者模型引擎
    - 加载示例数据

    关闭时：
    - 清理资源
    """
    logger.info("🚀 %s v%s 启动中...", settings.app_name, settings.app_version)
    logger.info("📡 服务地址: %s:%s", settings.host, settings.port)
    logger.info("🤖 默认模型: %s", settings.default_model)

    # 初始化数据库
    from app.db.database import get_db
    db = get_db()
    logger.info("💾 PostgreSQL 已连接")

    # P5: 初始化「未分类」分区 + 资料元数据索引
    _init_uncategorized_partition()
    from app.services.materials_meta import materials_meta
    indexed = materials_meta.ensure_indexed()
    logger.info("📁 资料元数据初始化完成 (新注册 %d 个)", indexed)

    # 清理过期会话（定期执行）
    # MVP 版本在启动时清理一次
    cleaned = learner_engine.clean_expired_sessions()
    if cleaned > 0:
        logger.info("🧹 清理了 %d 个过期会话", cleaned)

    logger.info("✅ 应用启动完成")

    yield

    logger.info("👋 应用关闭")


# ── 创建 FastAPI 应用 ──
app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="基于 AI 的智能学习伴侣后端系统",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# ── CORS 中间件 ──
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── 注册路由 ──
# WebSocket 和 HTTP 聊天
app.include_router(chat_router)
# 学习计划
app.include_router(study_router)
# 练习题
app.include_router(practice_router)
# 练习子模块 (Phase 4D 拆分)
app.include_router(practice_errors_router)
app.include_router(practice_analytics_router)
app.include_router(practice_quality_router)
# 学习进度
app.include_router(progress_router)
# 内容搜索
app.include_router(content_router)
# 对话系统（树结构）
app.include_router(conversation_router, prefix="/api/conversations", tags=["conversations"])
app.include_router(material_router)
# 知识图谱 + 前置卡控
app.include_router(knowledge_router)
# 多模态（STT 转写）
app.include_router(multimodal_router)
# 成就系统
app.include_router(achievements_router)
# P1 全站搜索
app.include_router(search_router)


# ── 健康检查 ──
@app.get("/health", tags=["系统"])
async def health_check() -> dict[str, str]:
    """
    健康检查端点

    返回服务状态，用于负载均衡器和监控系统
    """
    return {
        "status": "healthy",
        "service": settings.app_name,
        "version": settings.app_version,
    }


@app.get("/", tags=["系统"])
async def root() -> dict[str, str]:
    """根路径 - 返回服务基本信息"""
    return {
        "service": settings.app_name,
        "version": settings.app_version,
        "docs": "/docs",
        "health": "/health",
    }


@app.get("/api/agents", tags=["系统"])
async def list_agents() -> list[dict[str, str]]:
    """
    列出所有可用的智能体

    返回:
        Agent列表及其描述
    """
    from app.core.orchestrator import orchestrator
    return orchestrator.get_available_agents()
