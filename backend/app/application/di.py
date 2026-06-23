"""
依赖注入容器 — 应用唯一装配点

所有模块的创建和注入在此完成，不依赖全局 import。
这是整个系统唯一的"胶水代码"。
"""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from app.config import settings
from app.infrastructure.event_bus import EventBus
from app.infrastructure.resilience import CircuitBreaker
from shared.events import DomainEvent
from dataclasses import asdict
from app.infrastructure.event_store import EventRecord

if TYPE_CHECKING:
    from shared.protocols import (
        PracticeService,
        PlanningService,
        AnalyticsService,
        HabitService,
        MaterialService,
        KnowledgeGraphService,
        MediaService,
    )
    from shared.protocols.cognitive import CognitiveNodeRepository
    from shared.protocols.knowledge_query import KnowledgeQueryService
    from app.domain.multimedia.service import MultimediaService

logger = logging.getLogger("di")


class AppContainer:
    """
    应用容器

    职责:
    1. 创建所有基础设施（DB, LLM, 事件总线）
    2. 创建领域服务并注入依赖
    3. 注册事件处理器（wire events）
    """

    def __init__(self, use_persistent: bool = True):
        # ── 基础设施 ──
        if use_persistent:
            from app.infrastructure.persistent_event_bus import PersistentEventBus
            self.event_bus = PersistentEventBus(
                handler_timeout=settings.event_bus_timeout,
            )
        else:
            self.event_bus = EventBus(handler_timeout=settings.event_bus_timeout)
        self.llm_circuit = CircuitBreaker("llm", failure_threshold=3)

        # ── v2 EventSystem: 统一事件存储 + 记忆 + 聚合 ──
        from app.infrastructure.event_store import EventStore
        from app.infrastructure.event_memory import EventMemory
        from app.infrastructure.event_aggregator import EventAggregator
        self.event_store = EventStore()
        self.event_memory = EventMemory()
        self.event_aggregator = EventAggregator()

        # ── DataRepository 仓储 ──
        self._init_data_repo()

        # ── CognitiveNode 仓储 ──
        self.cognitive_node_repo: CognitiveNodeRepository = self._create_cognitive_repo()

        # ── 领域服务（先创建无依赖的） ──
        self.practice_service: PracticeService = self._create_practice()
        self.session_bridge = self._create_session_bridge()
        self.planning_service: PlanningService = self._create_planning()
        self.analytics_service: AnalyticsService = self._create_analytics()
        self.habit_service: HabitService = self._create_habits()
        self.material_service: MaterialService = self._create_materials()
        self.knowledge_service: KnowledgeGraphService = self._create_knowledge()
        self.knowledge_query_service: KnowledgeQueryService = self._create_knowledge_query()
        self.media_service: MediaService = self._create_media()
        self.multimedia_service: MultimediaService = self._create_multimedia()

        # ── Knowledge v5 服务 (四实体解耦架构) ──
        self.knowledge_v5 = self._create_knowledge_v5()

        # ── 注册事件处理器 ──
        self._wire_events()

        # v6 Phase 4: 事件持久化桥接 (仅内存 EventBus 需要)
        if not use_persistent:
            try:
                from app.services.common.event_service import event_service
                event_service.subscribe_persist(self.event_bus)
            except Exception:
                logger.debug("EventService 持久化桥接失败", exc_info=True)

        logger.info("✅ AppContainer 初始化完成 (%d 个服务, %d 个事件订阅)",
                    10, len(self.event_bus._handlers))

    # ═══════════════════════════════════════════════════════
    # 服务工厂方法
    # ═══════════════════════════════════════════════════════

    def _create_cognitive_repo(self) -> CognitiveNodeRepository:
        from app.infrastructure.db.cognitive_repository import PgCognitiveNodeRepository
        from app.domain.cognitive import set_repo, init_cognitive
        repo = PgCognitiveNodeRepository()
        set_repo(repo)
        init_cognitive()  # 注册 CognitiveOperationRegistry (操作自动发现)
        return repo

    def _init_data_repo(self) -> None:
        from app.services.common import set_data_repo
        from app.services.common.storage import storage
        set_data_repo(storage)

    def _create_practice(self) -> PracticeService:
        from app.domain.practice.service import PracticeServiceImpl
        from app.infrastructure.db.repositories import (
            PostgresQuestionRepo,
            PostgresSessionRepo,
            PostgresErrorBookRepo,
        )

        return PracticeServiceImpl(
            question_repo=PostgresQuestionRepo(),
            session_repo=PostgresSessionRepo(),
            error_repo=PostgresErrorBookRepo(),
            event_bus=self.event_bus,
        )

    def _create_session_bridge(self):
        from app.domain.conversation.session_bridge import SessionBridge
        return SessionBridge()

    def _create_planning(self) -> PlanningService:
        from app.services.common.planning_stub import PlanningStub
        return PlanningStub()

    def _create_analytics(self) -> AnalyticsService:
        from app.services.common.analytics_stub import AnalyticsStub
        return AnalyticsStub()

    def _create_habits(self) -> HabitService:
        from app.services.common.habits_stub import HabitsStub
        return HabitsStub()

    def _create_materials(self) -> MaterialService:
        from app.services.common.materials_stub import MaterialsStub
        return MaterialsStub()

    def _create_knowledge(self) -> KnowledgeGraphService:
        from app.services.knowledge.knowledge_graph_service import KnowledgeGraphServiceImpl
        return KnowledgeGraphServiceImpl(
            practice=self.practice_service,
            event_bus=self.event_bus,
        )

    def _create_knowledge_query(self) -> KnowledgeQueryService:
        from app.services.knowledge.knowledge_query_service import KnowledgeQueryServiceImpl
        from app.domain.knowledge import set_knowledge_query
        svc = KnowledgeQueryServiceImpl()
        set_knowledge_query(svc)
        return svc

    def _create_media(self) -> MediaService:
        from app.services.common.media_stub import MediaStub
        return MediaStub()

    def _create_multimedia(self) -> MultimediaService:
        from app.domain.multimedia.service import MultimediaService
        from app.infrastructure.tts_client import EdgeTTSClient
        from app.infrastructure.svg_renderer import SVGRenderer

        tts = EdgeTTSClient()
        renderer = SVGRenderer()
        return MultimediaService(
            tts=tts,
            renderer=renderer,
            event_bus=self.event_bus,
        )

    def _create_knowledge_v5(self) -> dict:
        """创建 Knowledge v5 服务层 (四实体解耦架构)"""
        from app.services.knowledge_v2 import (
            KnowledgeNodeService, ConversationService,
            NavigationService, MessageService,
        )
        return {
            "knowledge_node": KnowledgeNodeService(),
            "conversation": ConversationService(),
            "navigation": NavigationService(),
            "message": MessageService(),
        }

    # ═══════════════════════════════════════════════════════
    # 事件订阅 — 模块联动的唯一配置点
    # ═══════════════════════════════════════════════════════

    def _wire_events(self) -> None:
        bus = self.event_bus

        # 答题 → 行为分析 + 习惯养成 + 知识图谱
        bus.subscribe("AnswerSubmitted", self.analytics_service.on_answer_submitted)
        bus.subscribe("AnswerSubmitted", self.habit_service.on_answer_submitted)
        bus.subscribe("AnswerSubmitted", self.knowledge_service.on_answer_submitted)

        # 错题 → 知识图谱 + 媒体推荐
        bus.subscribe("ErrorRecorded", self.knowledge_service.on_error_recorded)
        bus.subscribe("ErrorRecorded", self.media_service.on_error_recorded)

        # 会话完成 → 对话记忆写回 + 计划更新
        bus.subscribe("SessionCompleted", self.session_bridge.on_session_completed)
        bus.subscribe("SessionCompleted", self.planning_service.on_session_completed)

        # CognitiveNode 更新 → 计划重调 + ZPD 调度
        async def _on_cognitive_updated(event: DomainEvent) -> None:
            from shared.events import CognitiveNodeUpdated
            if not isinstance(event, CognitiveNodeUpdated):
                return
            logger.debug(
                "CognitiveNode updated: %s (%s) %.3f→%.3f",
                event.label, event.level,
                event.proficiency_before, event.proficiency_after,
            )
            # 计划重调
            try:
                await self.planning_service.on_knowledge_updated(event)
            except Exception:
                logger.debug("Planning service failed to handle CognitiveNodeUpdated")
            # ZPD 调度器重算
            try:
                from app.services.knowledge.zpd_scheduler import zpd_scheduler
                zpd_scheduler.on_knowledge_change(event.user_id, event.node_id)
            except Exception:
                logger.debug("ZPD scheduler not available, skipping")
        bus.subscribe("CognitiveNodeUpdated", _on_cognitive_updated)

        # AI 回复 → 多媒体生成
        bus.subscribe("AssistantReplied", self.multimedia_service.on_assistant_replied)

        # ── v2 EventSystem: 工作记忆生命周期 + 聚合 ──
        async def _on_session_completed(event: DomainEvent) -> None:
            from shared.events import SessionCompleted
            if not isinstance(event, SessionCompleted):
                return
            user_id = event.user_id
            session_id = event.session_id
            try:
                # 结束工作记忆
                self.event_memory.working_end(user_id, session_id)
                # 触发聚合
                agg_record = await self.event_aggregator.aggregate_practice_session(
                    user_id, session_id
                )
                if agg_record:
                    await self.event_store.append(
                        agg_record,
                        stream_type="practice",
                        stream_id=session_id,
                    )
            except Exception:
                logger.debug("EventMemory/Aggregator hook failed", exc_info=True)
        bus.subscribe("SessionCompleted", _on_session_completed)

        async def _on_assistant_replied(event: DomainEvent) -> None:
            from shared.events import AssistantReplied
            if not isinstance(event, AssistantReplied):
                return
            user_id = event.user_id
            conversation_id = event.conversation_id
            try:
                # 检查对话聚合阈值
                agg_record = await self.event_aggregator.on_event(
                    EventRecord(
                        user_id=user_id,
                        event_type="AssistantReplied",
                        stream_type="conversation",
                        stream_id=conversation_id,
                        payload=asdict(event),
                    )
                )
                if agg_record:
                    await self.event_store.append(
                        agg_record,
                        stream_type="conversation",
                        stream_id=conversation_id,
                    )
            except Exception:
                logger.debug("EventAggregator hook failed", exc_info=True)
        bus.subscribe("AssistantReplied", _on_assistant_replied)

        logger.info("🔗 注册 %d 个事件订阅", sum(len(v) for v in bus._handlers.values()))


# ── 全局容器实例（应用唯一单例） ──
container = AppContainer()
