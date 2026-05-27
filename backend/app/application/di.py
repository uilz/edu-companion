"""
依赖注入容器 — 应用唯一装配点

所有模块的创建和注入在此完成，不依赖全局 import。
这是整个系统唯一的"胶水代码"。
"""
from __future__ import annotations
from app.shared.constants import DEFAULT_USER_ID

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
    from shared.protocols.multimedia import AudioSynthesizer, ImageRenderer
    from domain.multimedia.service import MultimediaService

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

        logger.info("✅ AppContainer 初始化完成 (%d 个服务, %d 个事件订阅)",
                    9, len(self.event_bus._handlers))

    # ═══════════════════════════════════════════════════════
    # 服务工厂方法（后续替换为真实实现）
    # ═══════════════════════════════════════════════════════

    def _create_practice(self) -> PracticeService:
        from domain.practice.service import PracticeServiceImpl
        from infra.database import (
            PostgresQuestionRepo,
            PostgresSessionRepo,
            PostgresKnowledgeStateRepo,
            PostgresErrorBookRepo,
        )
        return PracticeServiceImpl(
            question_repo=PostgresQuestionRepo(),
            session_repo=PostgresSessionRepo(),
            ks_repo=PostgresKnowledgeStateRepo(),
            error_repo=PostgresErrorBookRepo(),
            event_bus=self.event_bus,
        )

    def _create_conversation(self) -> ConversationService:
        from domain.conversation.service import ConversationServiceImpl
        from infra.llm import LLMClient
        return ConversationServiceImpl(
            llm=LLMClient(),
            event_bus=self.event_bus,
            circuit=self.llm_circuit,
        )

    def _create_planning(self) -> PlanningService:
        from domain.planning.service import PlanningServiceImpl
        return PlanningServiceImpl(
            practice=self.practice_service,
            event_bus=self.event_bus,
        )

    def _create_analytics(self) -> AnalyticsService:
        from domain.analytics.service import AnalyticsServiceImpl
        return AnalyticsServiceImpl(
            practice=self.practice_service,
            event_bus=self.event_bus,
        )

    def _create_habits(self) -> HabitService:
        from domain.habits.service import HabitServiceImpl
        return HabitServiceImpl(
            event_bus=self.event_bus,
        )

    def _create_materials(self) -> MaterialService:
        from domain.materials.service import MaterialServiceImpl
        return MaterialServiceImpl(
            event_bus=self.event_bus,
        )

    def _create_knowledge(self) -> KnowledgeGraphService:
        from domain.knowledge.service import KnowledgeGraphServiceImpl
        return KnowledgeGraphServiceImpl(
            practice=self.practice_service,
            event_bus=self.event_bus,
        )

    def _create_media(self) -> MediaService:
        from domain.media.service import MediaServiceImpl
        return MediaServiceImpl()

    def _create_multimedia(self) -> MultimediaService:
        from domain.multimedia.service import MultimediaService
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

        # Phase 9 精简: 不重复写 cognitive_nodes (已由 submit_practice 写入)
        # 只发布 CognitiveNodeUpdated 事件通知下游 (ZPD, Dashboard 等)
        async def _on_answer_to_cognitive(event: DomainEvent) -> None:
            from shared.events import AnswerSubmitted, CognitiveNodeUpdated
            if not isinstance(event, AnswerSubmitted):
                return
            proficiency_before = event.p_known_before
            # 获取 cognitive_nodes 中更新后的掌握度
            from app.cognitive.storage import find_node_by_label
            node = find_node_by_label(event.skill_id, event.user_id or DEFAULT_USER_ID)
            proficiency_after = node.belief.proficiency_mean if node else event.p_known_after
            await bus.publish(CognitiveNodeUpdated(
                user_id=event.user_id or DEFAULT_USER_ID,
                node_id=node.id if node else event.skill_id,
                label=event.skill_id,
                level="atom",
                proficiency_before=proficiency_before,
                proficiency_after=proficiency_after,
                update_type="practice",
            ))
        bus.subscribe("AnswerSubmitted", _on_answer_to_cognitive)
        logger.info("🧠 Phase 9: AnswerSubmitted → CognitiveNode sync + event published")

        # 错题 → 知识图谱 + 媒体推荐
        bus.subscribe("ErrorRecorded", self.knowledge_service.on_error_recorded)
        bus.subscribe("ErrorRecorded", self.media_service.on_error_recorded)

        # 会话完成 → 对话记忆写回 + 计划更新
        bus.subscribe("SessionCompleted", self.conversation_service.on_session_completed)
        bus.subscribe("SessionCompleted", self.planning_service.on_session_completed)

        # 知识升级 → 计划重调 + 对话通知
        bus.subscribe("KnowledgeStateUpdated", self.planning_service.on_knowledge_updated)
        bus.subscribe("KnowledgeStateUpdated", self.conversation_service.on_knowledge_updated)

        # Phase 9: CognitiveNode 更新 → ZPD 调度重计算
        from app.cognitive.storage import get_node
        async def _on_cognitive_updated(event: DomainEvent) -> None:
            from shared.events import CognitiveNodeUpdated
            if not isinstance(event, CognitiveNodeUpdated):
                return
            logger.debug(
                "CognitiveNode updated: %s (%s) %.3f→%.3f",
                event.label, event.level,
                event.proficiency_before, event.proficiency_after,
            )
            # 触发 ZPD 调度器重算
            try:
                from app.services.zpd_scheduler import zpd_scheduler
                zpd_scheduler.on_knowledge_change(event.user_id, event.node_id)
            except Exception:
                logger.debug("ZPD scheduler not available, skipping cognitive update reaction")
        bus.subscribe("CognitiveNodeUpdated", _on_cognitive_updated)
        logger.info("🧠 Phase 9: CognitiveNodeUpdated → ZPD reschedule handler registered")

        # Phase 5: AI 回复 → 多媒体生成
        bus.subscribe("AssistantReplied", self.multimedia_service.on_assistant_replied)

        # Phase 5: 音频/配图完成 → 对话推送
        bus.subscribe("AudioSynthesized", self.conversation_service.on_audio_synthesized)
        bus.subscribe("ImageRendered", self.conversation_service.on_image_rendered)

        logger.info("🔗 注册 %d 个事件订阅", sum(len(v) for v in bus._handlers.values()))


# ── 全局容器实例（应用唯一单例） ──
container = AppContainer()
