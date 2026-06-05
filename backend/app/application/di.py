"""
依赖注入容器 — 应用唯一装配点

所有模块的创建和注入在此完成，不依赖全局 import。
这是整个系统唯一的"胶水代码"。
"""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from infra.event_bus import EventBus
from infra.resilience import CircuitBreaker
from shared.events import DomainEvent

if TYPE_CHECKING:
    from shared.protocols import (
        PracticeService,
        ConversationService,
        PlanningService,
        AnalyticsService,
        HabitService,
        MaterialService,
        KnowledgeGraphService,
        MediaService,
    )
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

    def __init__(self):
        # ── 基础设施 ──
        self.event_bus = EventBus(handler_timeout=5.0)
        self.llm_circuit = CircuitBreaker("llm", failure_threshold=3)

        # ── 领域服务（先创建无依赖的） ──
        self.practice_service: PracticeService = self._create_practice()
        self.conversation_service: ConversationService = self._create_conversation()
        self.planning_service: PlanningService = self._create_planning()
        self.analytics_service: AnalyticsService = self._create_analytics()
        self.habit_service: HabitService = self._create_habits()
        self.material_service: MaterialService = self._create_materials()
        self.knowledge_service: KnowledgeGraphService = self._create_knowledge()
        self.media_service: MediaService = self._create_media()
        self.multimedia_service: MultimediaService = self._create_multimedia()

        # ── 注册事件处理器 ──
        self._wire_events()

        # v6 Phase 4: 事件持久化桥接
        try:
            from app.services.common.event_service import event_service
            event_service.subscribe_persist(self.event_bus)
        except Exception:
            logger.debug("EventService 持久化桥接失败", exc_info=True)

        logger.info("✅ AppContainer 初始化完成 (%d 个服务, %d 个事件订阅)",
                    9, len(self.event_bus._handlers))

    # ═══════════════════════════════════════════════════════
    # 服务工厂方法
    # ═══════════════════════════════════════════════════════

    def _create_practice(self) -> PracticeService:
        from app.domain.practice.service import PracticeServiceImpl
        from infra.database import (
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

    def _create_conversation(self) -> ConversationService:
        from app.domain.conversation.service import ConversationServiceImpl
        from infra.llm import LLMClient
        return ConversationServiceImpl(
            llm=LLMClient(),
            event_bus=self.event_bus,
            circuit=self.llm_circuit,
        )

    def _create_planning(self) -> PlanningService:
        from app.domain.planning.service import PlanningServiceImpl
        return PlanningServiceImpl(
            practice=self.practice_service,
            event_bus=self.event_bus,
        )

    def _create_analytics(self) -> AnalyticsService:
        from app.domain.analytics.service import AnalyticsServiceImpl
        return AnalyticsServiceImpl(
            practice=self.practice_service,
            event_bus=self.event_bus,
        )

    def _create_habits(self) -> HabitService:
        from app.domain.habits.service import HabitServiceImpl
        return HabitServiceImpl(
            event_bus=self.event_bus,
        )

    def _create_materials(self) -> MaterialService:
        from app.domain.materials.service import MaterialServiceImpl
        return MaterialServiceImpl(
            event_bus=self.event_bus,
        )

    def _create_knowledge(self) -> KnowledgeGraphService:
        from app.domain.knowledge.service import KnowledgeGraphServiceImpl
        return KnowledgeGraphServiceImpl(
            practice=self.practice_service,
            event_bus=self.event_bus,
        )

    def _create_media(self) -> MediaService:
        from app.domain.media.service import MediaServiceImpl
        return MediaServiceImpl()

    def _create_multimedia(self) -> MultimediaService:
        from app.domain.multimedia.service import MultimediaService
        from infra.tts_client import EdgeTTSClient
        from infra.svg_renderer import SVGRenderer

        tts = EdgeTTSClient()
        renderer = SVGRenderer()
        return MultimediaService(
            tts=tts,
            renderer=renderer,
            event_bus=self.event_bus,
        )

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
        bus.subscribe("SessionCompleted", self.conversation_service.on_session_completed)
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

        logger.info("🔗 注册 %d 个事件订阅", sum(len(v) for v in bus._handlers.values()))


# ── 全局容器实例（应用唯一单例） ──
container = AppContainer()
