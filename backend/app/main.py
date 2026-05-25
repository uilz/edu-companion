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
from app.api.knowledge_graph import router as knowledge_graph_router
from app.api.partition_progress import router as partition_progress_router
from app.api.learning_events import router as learning_events_router
from app.api.multimodal import router as multimodal_router
from app.api.achievements import router as achievements_router
from app.api.search import router as search_router
from app.api.secretary import router as secretary_router
from app.api.phase8 import router as phase8_router
from app.config import settings
from app.core.learner_model import learner_engine

# 配置日志
logging.basicConfig(
    level=logging.DEBUG if settings.debug else logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


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
    logger.info("🤖 文本模型: %s", settings.text_model)
    logger.info("🧠 推理模型: %s", settings.text_reasoning_model)

    # 初始化数据库
    from app.db.database import get_db
    db = get_db()
    logger.info("💾 PostgreSQL 已连接")

    # 初始化资料元数据索引
    from app.services.materials_meta import materials_meta
    indexed = materials_meta.ensure_indexed()
    logger.info("📁 资料元数据初始化完成 (新注册 %d 个)", indexed)

    # Phase 5: 注入领域事件总线到 Orchestrator（多媒体生成触发）
    from app.application.di import container
    from app.core.orchestrator import orchestrator
    from app.api.chat import manager as ws_manager
    orchestrator._bus = container.event_bus
    logger.info("🎬 Orchestrator 已注入 EventBus (Phase 5)")

    # Phase 5: 注入 WebSocket 管理器到 ConversationService（block_update 推送）
    container.conversation_service.set_ws_manager(ws_manager)
    logger.info("📡 ConversationService 已注入 WebSocket Manager (Phase 5)")

    # Phase 7.4: 发现内置模块 + 启动秘书主动检查器
    try:
        from app.domain.secretary.engines.module_registry import module_registry
        count = module_registry.discover_builtin()
        logger.info("🔌 秘书模块注册: %d 个内置模块 (Phase 7.4)", count)
    except Exception as e:
        logger.warning("秘书模块注册失败: %s", e)

    try:
        from app.domain.secretary.engines.active_checker import active_checker
        active_checker.start()
        logger.info("🔍 秘书主动检查器已启动 (Phase 7.4)")
    except Exception as e:
        logger.warning("秘书主动检查器启动失败: %s", e)

    # Phase 7.5+: 订阅领域事件
    try:
        from app.domain.secretary.engines.secretary_event_handler import secretary_event_handler
        secretary_event_handler.subscribe(container.event_bus)
        logger.info("📡 秘书事件处理器已订阅 (Phase 7.5)")
    except Exception as e:
        logger.warning("秘书事件处理器订阅失败: %s", e)

    cleaned = learner_engine.clean_expired_sessions()
    if cleaned > 0:
        logger.info("🧹 清理了 %d 个过期会话", cleaned)

    logger.info("✅ 应用启动完成")

    yield

    # Phase 7.3: 停止秘书主动检查器
    try:
        from app.domain.secretary.engines.active_checker import active_checker
        await active_checker.stop()
        logger.info("🔍 秘书主动检查器已停止")
    except Exception as e:
        pass

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
app.include_router(knowledge_graph_router)
# 学习画像 (v3.0 PartitionProgress)
app.include_router(partition_progress_router)
# 学习事件记录 (v3.0)
app.include_router(learning_events_router)
# 多模态（STT 转写）
app.include_router(multimodal_router)
# 成就系统
app.include_router(achievements_router)
# P1 全站搜索
app.include_router(search_router)
app.include_router(secretary_router)
# Phase 8 认知图驱动分类
app.include_router(phase8_router)


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
