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
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.learning.study import router as study_router
from app.api.practice.practice import router as practice_router
from app.api.learning.progress import router as progress_router
from app.api.conversation.conversation import router as conversation_router
from app.api.knowledge.knowledge import router as knowledge_router
from app.api.learning.partition_progress import router as partition_progress_router
from app.api.system.multimodal import router as multimodal_router
from app.api.system.achievements import router as achievements_router
from app.api.system.search import router as search_router
from app.api.system.secretary import router as secretary_router
from app.api.learning.cognitive import router as learning_router
from app.api.knowledge.knowledge_graph import router as knowledge_graph_router
from app.api.system.summaries import router as summaries_router

# Phase 10: 笔记/目标/探索项目
from app.api.learning.learning_enhance import router as learning_enhance_router

# Phase 10.7+: 文件管理
from app.api.system.files_api import router as files_router

# 认证系统 — 已迁移至独立认证网关 (auth-gateway:8001)
# 主后端仅保留认证中间件，用于调用网关验证令牌

# 解释卡片 CRUD
from app.api.practice.explain_cards import router as explain_cards_router

# v7.0 智能题库
from app.api.practice.v7_practice import router as v7_practice_router
from app.api.practice.v7_references import router as v7_references_router

# v8.0 学习数据管理
from app.api.system.v7_data import router as v7_data_router

from app.config import settings
from shared.learner_model import learner_engine

# Phase 9 D.3: 请求追踪
from app.middleware.trace import TraceMiddleware

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
    get_db()
    logger.info("💾 PostgreSQL 已连接")

    # 初始化资料元数据索引
    from app.services.materials.materials_meta import materials_meta
    indexed = materials_meta.ensure_indexed()
    logger.info("📁 资料元数据初始化完成 (新注册 %d 个)", indexed)

    # 恢复 stuck 文件（uploading → 重新索引）
    try:
        from app.api.system.files_api import recover_stuck_files
        await recover_stuck_files()
    except Exception as e:
        logger.warning("stuck 文件恢复跳过: %s", e)

    # Phase 5: 注入领域事件总线到 Orchestrator（多媒体生成触发）
    from app.application.di import container
    from app.api.conversation.ws_manager import manager as ws_manager

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

    # v6 Phase 4: 启动事件消费者（轮询 cognitive_events）
    try:
        from app.services.common.event_service import event_service
        event_service.start_consumer()
    except Exception as e:
        logger.warning("事件消费者启动失败: %s", e)

    # Phase 8: 初始化对话摘要表
    try:
        from app.services.common.summary_service import ensure_summaries_table
        ensure_summaries_table()
        logger.info("📋 conversation_summaries 表已就绪 (Phase 8)")
    except Exception as e:
        logger.warning("对话摘要表初始化失败: %s", e)

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
    except Exception:
        logger.debug("秘书主动检查器停止失败", exc_info=True)

    # v6 Phase 4: 停止事件消费者
    try:
        from app.services.common.event_service import event_service
        await event_service.stop_consumer()
        logger.info("🔄 事件消费者已停止")
    except Exception:
        logger.debug("事件消费者停止失败", exc_info=True)

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

# ── 全链路追踪中间件 (M4) ──
@app.middleware("http")
async def tracing_middleware(request, call_next):
    from infra.tracing import TraceContext, trace_id
    tid = request.headers.get("x-trace-id", TraceContext.new())
    trace_id.set(tid)
    response = await call_next(request)
    response.headers["x-trace-id"] = tid
    return response

# ── 全局异常处理器 (M2) ──
from fastapi import Request
from fastapi.responses import JSONResponse
from fastapi.exceptions import HTTPException

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    # AppError 体系
    from app.core.errors import AppError
    if isinstance(exc, AppError):
        logger.warning(
            "AppError [%s] on %s %s: %s",
            exc.code, request.method, request.url.path, exc.detail,
            extra={"trace_id": request.headers.get("x-trace-id", "")},
        )
        return JSONResponse(
            status_code=exc.status_code,
            content=exc.to_dict(),
        )

    # HTTPException (FastAPI 内置)
    if isinstance(exc, HTTPException):
        return JSONResponse(
            status_code=exc.status_code,
            content={"error": "http_error", "detail": exc.detail},
        )

    # 未知异常
    logger.error(
        "Unhandled exception on %s %s: %s",
        request.method, request.url.path, exc, exc_info=True,
        extra={"trace_id": request.headers.get("x-trace-id", "")},
    )
    return JSONResponse(
        status_code=500,
        content={
            "error": "internal_error",
            "detail": str(exc) if settings.debug else "Internal server error",
        },
    )

# ── 注册中间件 ──
app.add_middleware(TraceMiddleware)

# ── 认证中间件 ──
from app.domain.auth.middleware import AuthMiddleware
app.add_middleware(AuthMiddleware)

# ── 注册路由 ──
# WebSocket 和 HTTP 聊天
# chat_router 已删除 — WS 端点在 conversation.py
# 学习计划
app.include_router(study_router)
# 练习题
app.include_router(practice_router)
# 学习进度
app.include_router(progress_router)
# 对话系统（树结构 + WebSocket）
app.include_router(conversation_router, prefix="/api/conversations", tags=["conversations"])
# 知识图谱 + 前置卡控
app.include_router(knowledge_router)
# 学习画像 (v3.0 PartitionProgress)
app.include_router(partition_progress_router)
# 多模态（STT 转写）
app.include_router(multimodal_router)
# 成就系统
app.include_router(achievements_router)
# P1 全站搜索
app.include_router(search_router)
app.include_router(secretary_router)
# 认知图驱动分类
app.include_router(learning_router)
app.include_router(knowledge_graph_router)
app.include_router(summaries_router)

# Phase 10: 笔记/目标/探索项目
app.include_router(learning_enhance_router)

# Phase 10.7+: 文件管理
app.include_router(files_router)

# 认证系统 — 已迁移至独立认证网关
# app.include_router(auth_router)  # 已移除

# v7.0 智能题库
app.include_router(v7_practice_router)
app.include_router(v7_references_router)

# 解释卡片 CRUD
app.include_router(explain_cards_router)

# v8.0 学习数据管理
app.include_router(v7_data_router)


# ── 健康检查 ──
@app.get("/health", tags=["系统"])
async def health_check() -> dict:
    """
    健康检查端点 — 检查 DB + 事件队列
    """
    checks: dict = {"status": "healthy", "service": settings.app_name, "version": settings.app_version}
    try:
        from app.db.database import get_db
        db = get_db()
        db.fetchone("SELECT 1")
        checks["db"] = True
    except Exception as e:
        checks["db"] = False
        checks["status"] = "degraded"
        logger.warning("Health check DB failed: %s", e)

    # Phase 7: 事件队列监控
    try:
        event_count = db.fetchone(
            "SELECT COUNT(*) as cnt FROM cognitive_events WHERE processed = false"
        )
        pending = event_count["cnt"] if event_count else 0
        checks["event_queue_pending"] = pending
        if pending > 50:
            checks["status"] = "degraded"
    except Exception:
        checks["event_queue_pending"] = -1

    # Phase 9 D.3: 连接池统计
    try:
        from app.db.database import get_db_pool_stats
        pool_stats = get_db_pool_stats()
        if pool_stats:
            checks["db_pool"] = pool_stats
    except Exception:
        pass

    return checks


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
    """列出所有可用的智能体"""
    return [
        {"name": "tutor", "description": "AI导师 — 解答问题、讲解知识、引导思考"},
        {"name": "coach", "description": "学习教练 — 制定计划、追踪进度、习惯养成"},
        {"name": "secretary", "description": "学习秘书 — 分析学情、主动提醒、任务管理"},
    ]
