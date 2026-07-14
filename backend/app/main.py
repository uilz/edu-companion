"""
苹果果学习助手 - FastAPI 主入口

功能：
- WebSocket 实时聊天（流式输出）
- REST API（学习计划、练习题、进度跟踪、内容搜索）
- 健康检查端点
- CORS 支持
"""
from __future__ import annotations

import asyncio
import json
import logging
from typing import AsyncGenerator

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware

from app.api.learning.study import router as study_router
from app.api.learning.progress import router as progress_router
from app.api.conversation.conversation import router as conversation_router
from app.api.session.session import router as session_router
from app.api.growth.growth import router as growth_router
from app.api.profile.profile import router as profile_router
from app.api.learning.partition_progress import router as partition_progress_router
from app.api.system.multimodal import router as multimodal_router
from app.api.system.achievements import router as achievements_router
from app.api.system.search import router as search_router
from app.api.system.secretary import router as secretary_router
from app.api.learning.cognitive import router as learning_router
from app.api.system.summaries import router as summaries_router

# 笔记/目标/探索项目
from app.api.learning.learning_enhance import router as learning_enhance_router
from app.api.learning.explain import router as learning_explain_router
from app.api.analytics.retention import router as analytics_router

# 文件管理
from app.api.system.files_routes import router as files_router, recover_stuck_files

# 解释卡片
from app.api.conversations.explain_cards import router as explain_cards_router

# 智能题库
from app.api.practice.practice_routes import router as practice_routes_router

# 学习数据管理
from app.api.system.data_routes import router as data_router

# 事件系统（客户端驱动聚合）+ 工具定义 API
from app.infrastructure.scheduler.events_api import router as events_router, _tools_router

# 知识树系统 (四实体解耦架构) — 统一入口 /api/trees
from app.api.trees import router as trees_router

# 认知图谱（/api/knowledge-graph）
from app.api.knowledge_graph import router as kg_router
from app.api.knowledge_graph_ai import router as kg_ai_router
from app.api.knowledge_graph_sse import router as kg_sse_router

# 项目工作台
from app.api.project import router as project_router

# 规划模块（ADR 0006）
from app.api.planning import router as planning_router

# 学习活动流（Phase 2 统一设计系统）
from app.api.learning_activity import router as learning_activity_router

# 阅读模块（ADR 0003）
from app.api.reading import router as reading_router

# LanguageRoom 实时语音房间（ADR 0004）
from app.api.liveroom import router as liveroom_router

# InterestExplorer 学术信息发现（ADR 0007）
from app.api.interest.routes import router as interest_router

# 用户自定义 LLM 配置
from app.domain.auth.settings_api import router as settings_router

# 认证 API（登录历史、活跃会话、踢出设备等）
from app.domain.auth.api import router as auth_router

from app.config import settings
from shared.learner_model import learner_engine

# 请求追踪
from app.middleware.trace import TraceMiddleware

# 配置日志
logging.basicConfig(
    level=logging.DEBUG if settings.debug else logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


async def _retry_index_failed():
    """启动时重试 index_failed 文件（S3-Q3: 定时重试）"""
    from app.infrastructure.db.database import get_db
    db = get_db()

    rows = db.fetchall(
        "SELECT * FROM materials WHERE status = 'index_failed'"
    )
    if not rows:
        return

    logger.info("🔄 重试 index_failed: %d 个文件...", len(rows))
    from app.api.system.files_routes.upload import _index_background
    for row in rows:
        from pathlib import Path
        storage_path = row.get("storage_path", "")
        if storage_path and Path(storage_path).exists():
            asyncio.ensure_future(_index_background(
                row["user_id"], row["material_id"], storage_path,
                row["file_name"], row["file_type"],
                row.get("file_size", 0), row["purpose"],
            ))
            logger.debug("  重试: %s", row["file_name"])
        else:
            logger.warning("  跳过(文件丢失): %s", row.get("file_name", ""))
    logger.info("🔄 index_failed 重试完成")


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
    from app.infrastructure.db.database import get_db
    get_db()
    logger.info("💾 PostgreSQL 已连接")

    # 资料元数据索引已废弃
    # 旧 ensure_indexed() 调用已移除

    # 恢复 stuck 文件（uploading → 重新索引）
    try:
        await recover_stuck_files()
    except Exception as e:
        logger.warning("stuck 文件恢复跳过: %s", e)

    # pgvector 迁移已移除 — 需要时手动触发 reindex

    # 重试 index_failed 文件（S3-Q3: 定时重试）
    try:
        await _retry_index_failed()
    except Exception as e:
        logger.warning("index_failed 重试跳过: %s", e)

    # 注入领域事件总线到 Orchestrator（多媒体生成触发）
    from app.application.di import container

    # 发现内置模块 + 初始化秘书系统
    try:
        from app.domain.secretary.engines.module_registry import module_registry
        count = module_registry.discover_builtin()
        logger.info("🔌 秘书模块注册: %d 个内置模块", count)
    except Exception as e:
        logger.warning("秘书模块注册失败: %s", e)

    # 初始化统一工具仓库（ToolRepository）
    try:
        from app.infrastructure.llm.tool_repository import get_tool_repository
        repo = get_tool_repository()
        # 发现秘书工具
        import os
        secretary_tools_dir = os.path.join(os.path.dirname(__file__), "domain/secretary/tools")
        repo.discover([secretary_tools_dir])
        # 注册 LLM 原生工具
        from app.infrastructure.llm.tool_repository import TOOL_DEFINITIONS
        repo.register_raw_tools(TOOL_DEFINITIONS)
        # 注册知识树操作工具
        from app.infrastructure.llm.knowledge_ops_tools import TOOL_DEFINITIONS as KTOOL_DEFINITIONS
        repo.register_raw_tools(KTOOL_DEFINITIONS)
        # 注册 LanguageRoom 工具 (ADR 0004 决策 5)
        from app.infrastructure.llm.liveroom_tools import TOOL_DEFINITIONS as LROOM_DEFINITIONS
        repo.register_raw_tools(LROOM_DEFINITIONS)
        logger.info("🔧 ToolRepository 已初始化 (%d 个工具)", len(repo.list_tools()))
    except Exception as e:
        logger.warning("ToolRepository 初始化失败: %s", e)

    try:
        from app.infrastructure.db.secretary_schema import _ensure_tables as _ensure_secretary_tables
        _ensure_secretary_tables()
        from app.infrastructure.db.proposal_store import ProposalStore
        _store = ProposalStore()
        from app.domain.secretary.engines.active_checker import active_checker
        active_checker._store = _store
        from app.domain.secretary.engines.policy_engine import policy_engine
        policy_engine.set_store(_store)
        from app.domain.secretary.engines.silent_task_manager import silent_task_manager
        silent_task_manager.set_event_bus(container.event_bus)
        from app.infrastructure.db.user_profile_store import user_profile_store
        logger.info("📝 秘书 Infra 注入完成")
    except Exception as e:
        logger.warning("秘书 Infra 注入失败: %s", e)

    # 订阅领域事件
    try:
        from app.infrastructure.db.proposal_store import ProposalStore
        from app.domain.secretary.engines.secretary_event_handler import secretary_event_handler
        from app.domain.secretary.engines.silent_task_manager import silent_task_manager
        secretary_event_handler._store = ProposalStore()
        secretary_event_handler._silent_task_manager = silent_task_manager
        secretary_event_handler.subscribe(container.event_bus)
        logger.info("📡 秘书事件处理器已订阅")
    except Exception as e:
        logger.warning("秘书事件处理器订阅失败: %s", e)

    # 订阅 Planning 事件（ADR 0006：完成回写不重发源事件）
    try:
        from app.services.planning.completion_writer import planning_completion_writer
        planning_completion_writer.subscribe(container.event_bus)
        logger.info("📡 PlanningCompletionWriter 已订阅事件总线")
    except Exception as e:
        logger.warning("PlanningCompletionWriter 订阅失败: %s", e)

    # Task #56: 订阅 Secretary → Conversation 上下文注入
    try:
        from app.domain.conversation.context_hooks import conversation_context_hook
        conversation_context_hook.subscribe(container.event_bus)
        logger.info("📡 ConversationContextHook 已订阅事件总线")
    except Exception as e:
        logger.warning("ConversationContextHook 订阅失败: %s", e)

    # Task #56: 订阅 Secretary → Planning 计划项请求
    try:
        from app.api.planning.event_handler import planning_event_handler
        planning_event_handler.subscribe(container.event_bus)
        logger.info("📡 PlanningEventHandler 已订阅事件总线")
    except Exception as e:
        logger.warning("PlanningEventHandler 订阅失败: %s", e)

    # Task #61: 订阅 Planning 主动生成器
    try:
        from app.api.planning.proactive_generator import planning_proactive_generator
        planning_proactive_generator.subscribe(container.event_bus)
        logger.info("📡 PlanningProactiveGenerator 已订阅事件总线")
    except Exception as e:
        logger.warning("PlanningProactiveGenerator 订阅失败: %s", e)

    # 初始化 Planning 数据表
    try:
        from app.services.planning import _ensure_tables as _ensure_planning_tables
        _ensure_planning_tables()
        logger.info("📋 planning_* 表已就绪")
    except Exception as e:
        logger.warning("Planning 表初始化失败: %s", e)

    # 初始化 Reading 数据表 (ADR 0003)
    try:
        from app.services.reading import _ensure_tables as _ensure_reading_tables
        _ensure_reading_tables()
        logger.info("📖 reading_* 表已就绪")
    except Exception as e:
        logger.warning("Reading 表初始化失败: %s", e)

    # 初始化 LanguageRoom 数据表 (ADR 0004)
    try:
        from app.services.liveroom import _ensure_tables as _ensure_liveroom_tables
        _ensure_liveroom_tables()
        logger.info("🎙️ liveroom_* 表已就绪")
        # 种子化系统预置 AI 角色
        try:
            from app.services.liveroom.ai_persona import seed_default_personas
            seed_default_personas()
        except Exception as e:
            logger.warning("默认 AI 角色种子化失败: %s", e)
        # 种子化系统预置场景
        try:
            from app.services.liveroom.ai_persona import seed_default_scenarios
            seed_default_scenarios()
        except Exception as e:
            logger.warning("默认场景种子化失败: %s", e)
    except Exception as e:
        logger.warning("LanguageRoom 表初始化失败: %s", e)

    # 确保 FlashCard 表存在
    try:
        from app.api.flashcard.service import FlashCardService
        FlashCardService.ensure_tables()
        logger.info("📇 flashcards 表已就绪")
    except Exception as e:
        logger.warning("FlashCard 表初始化失败: %s", e)

    # 初始化 InterestExplorer 数据表 (ADR 0007)
    try:
        from app.services.interest.migration import ensure_interest_tables
        ensure_interest_tables()
        # 种子内置信息源
        from app.api.interest import service as interest_api_service
        interest_api_service.seed_builtin_sources()
        logger.info("🔍 interest_* 表已就绪 + 内置源已种子")
    except Exception as e:
        logger.warning("InterestExplorer 初始化失败: %s", e)

    # ── 初始化对话摘要表 ──
    try:
        from app.services.common.summary_service import ensure_summaries_table
        ensure_summaries_table()
        logger.info("📋 conversation_summaries 表已就绪")
    except Exception as e:
        logger.warning("对话摘要表初始化失败: %s", e)

    cleaned = learner_engine.clean_expired_sessions()
    if cleaned > 0:
        logger.info("🧹 清理了 %d 个过期会话", cleaned)

    # ═══════════════════════════════════════════
    # 中央调度器 — 统一管理所有服务端后台任务
    # ═══════════════════════════════════════════
    from app.infrastructure.scheduler import BackgroundScheduler
    from app.infrastructure.scheduler.tasks import (
        event_bus_poll,
        event_consumer,
        event_cleanup,
        silent_task_tick,
    )

    app.state.scheduler = BackgroundScheduler()
    app.state.scheduler.add_task("event_bus", 0.5, event_bus_poll)
    app.state.scheduler.add_task("event_consumer", 5.0, event_consumer)
    app.state.scheduler.add_task("event_cleanup", 3600, event_cleanup)  # 每小时清理过期事件
    app.state.scheduler.add_task("silent_task", 60.0, silent_task_tick)  # ADR 0019

    # InterestExplorer 推送调度（ADR 0007）
    # 每 30 分钟检查一次推送时间窗口
    try:
        from app.services.interest.push_scheduler import interest_push_tick
        app.state.scheduler.add_task("interest_push", 1800, interest_push_tick)
        logger.info("🔍 InterestExplorer 推送任务已注册")
    except Exception as e:
        logger.warning("InterestExplorer 调度注册失败: %s", e)

    await app.state.scheduler.start_all()
    logger.info("✅ 中央调度器已启动: %d 个后台任务", len(app.state.scheduler._tasks))

    logger.info("✅ 应用启动完成")

    yield

    # ═══════════════════════════════════════════
    # 中央调度器关闭
    # ═══════════════════════════════════════════
    if hasattr(app.state, 'scheduler'):
        await app.state.scheduler.stop_all()
        logger.info("👋 中央调度器已停止，所有后台任务已关闭")

    logger.info("👋 应用关闭")


# ── 创建 FastAPI 应用 ──
app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="基于 AI 的苹果果学习助手后端系统",
    lifespan=lifespan,
    docs_url=None if not settings.debug else "/docs",
    redoc_url=None if not settings.debug else "/redoc",
)


# ── 安全响应头中间件 ──
@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    csp = (
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline'; "
        "style-src 'self' 'unsafe-inline'; "
        "img-src 'self' data: blob:; "
        "connect-src 'self' ws: wss:; "
        "font-src 'self'; "
        "frame-src 'self' blob:; "
        "media-src 'self' blob:; "
        "frame-ancestors 'self'; "
        "base-uri 'self'"
    )
    response.headers["Content-Security-Policy"] = csp
    return response


# ── 请求超时中间件 ──
# 对 SSE 流式端点跳过超时，其余请求受 settings.request_timeout 约束
_STREAMING_PATH_SUFFIXES = ("/message",)


@app.middleware("http")
async def request_timeout(request: Request, call_next):
    # SSE 流式端点（POST /tree/conversation/{cid}/message）需要长连接，跳过超时
    path = request.url.path
    if any(path.endswith(suffix) for suffix in _STREAMING_PATH_SUFFIXES):
        # 但只跳过实际产生 stream 的（即 POST 且 action 非 stop）
        # 简化：message 后缀的长连接全跳过，不超时
        return await call_next(request)

    try:
        return await asyncio.wait_for(call_next(request), timeout=settings.request_timeout)
    except asyncio.TimeoutError:
        return Response(
            content=json.dumps({"error": "timeout", "detail": "请求超时，请重试"}),
            media_type="application/json",
            status_code=408,
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
    from app.infrastructure.tracing import TraceContext, trace_id
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
    # HTTPException (FastAPI 内置)
    if isinstance(exc, HTTPException):
        return JSONResponse(
            status_code=exc.status_code,
            content={"error": "http_error", "detail": exc.detail},
        )

    # 未知异常 — 记录完整堆栈后返回通用错误
    logger.exception(
        "未处理异常 [%s] %s: %s",
        request.method, request.url.path, exc,
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
# 学习进度
app.include_router(progress_router)
# 对话系统（树结构 + WebSocket）
app.include_router(conversation_router, prefix="/api/conversations", tags=["conversations"])
# 学习会话 (AppleGo Domain Model v1.2)
app.include_router(session_router)
# 成长记录 (AppleGo Domain Model v1.2)
app.include_router(growth_router)
app.include_router(profile_router)
# 学习画像 (PartitionProgress)
app.include_router(partition_progress_router)
# 多模态（STT 转写）
app.include_router(multimodal_router)
# 成就系统
app.include_router(achievements_router)
# P1 全站搜索
app.include_router(search_router)
app.include_router(secretary_router)

# MoodStress 心情压力模块 API
from app.api.secretary.mood_stress import router as mood_stress_router  # noqa: E402
app.include_router(mood_stress_router)
app.include_router(learning_router)
app.include_router(summaries_router)

# 笔记/目标/探索项目
app.include_router(learning_enhance_router)

# 文件管理
app.include_router(files_router)


# 用户自定义 LLM 配置（非认证 — 保留在主后端）
app.include_router(settings_router)

# 认证 API（登录历史、活跃会话、踢出设备等）
app.include_router(auth_router)

# 智能题库
app.include_router(practice_routes_router)

# 解释卡片
app.include_router(explain_cards_router)

# FlashCard 间隔重复记忆卡
from app.api.flashcard.routes import router as flashcard_router
app.include_router(flashcard_router)

# 学习数据管理
app.include_router(data_router)

# 通用学习解释
app.include_router(learning_explain_router)

# 学情分析
app.include_router(analytics_router)

# 事件系统（客户端驱动聚合）
app.include_router(events_router)
app.include_router(_tools_router)

# 知识树系统 (四实体解耦架构)
app.include_router(trees_router)

# 认知图谱
app.include_router(kg_router)
app.include_router(kg_ai_router)
app.include_router(kg_sse_router)

# 知识图谱 (硬编码 / 动态加载)
from app.api.knowledge.knowledge import router as knowledge_graph_router
app.include_router(knowledge_graph_router)

# 规划（ADR 0006）
app.include_router(planning_router)

# 学习活动流（Phase 2 统一设计系统）
app.include_router(learning_activity_router)

# 阅读（ADR 0003）
app.include_router(reading_router)

# 项目工作台
app.include_router(project_router)

# LanguageRoom 实时语音房间（ADR 0004）
app.include_router(liveroom_router)

# InterestExplorer 学术信息发现 (ADR 0007)
app.include_router(interest_router)


# ── 健康检查 ──
@app.get("/health", tags=["系统"])
async def health_check() -> dict:
    """
    健康检查端点 — 检查 DB + 事件队列
    """
    checks: dict = {"status": "healthy", "service": settings.app_name, "version": settings.app_version}
    try:
        from app.infrastructure.db.database import get_db
        db = get_db()
        db.fetchone("SELECT 1")
        checks["db"] = True
    except Exception as e:
        checks["db"] = False
        checks["status"] = "degraded"
        logger.warning("Health check DB failed: %s", e)

    # 事件队列监控
    try:
        event_count = db.fetchone(
            "SELECT COUNT(*) as cnt FROM events WHERE status = 'pending'"
        )
        pending = event_count["cnt"] if event_count else 0
        checks["event_queue_pending"] = pending
        if pending > 50:
            checks["status"] = "degraded"
    except Exception:
        checks["event_queue_pending"] = -1

    # 连接池统计
    try:
        from app.infrastructure.db.database import get_db_pool_stats
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
