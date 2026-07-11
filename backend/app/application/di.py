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

        # ── EventSystem: 统一事件存储 + 记忆 + 聚合 ──
        from app.infrastructure.event_store import EventStore
        from app.infrastructure.event_memory import EventMemory
        from app.infrastructure.event_aggregator import EventHierarchyAggregator
        self.event_store = EventStore()
        self.event_memory = EventMemory()
        self.event_aggregator = EventHierarchyAggregator()

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

        # ── Knowledge 服务 (四实体解耦架构) ──
        self.knowledge_services = self._create_knowledge_services()

        # ── 注册事件处理器 ──
        self._wire_events()

        # 事件持久化桥接 (仅内存 EventBus 需要)
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

    def _create_knowledge_services(self) -> dict:
        """创建 Knowledge 服务层 (四实体解耦架构)"""
        from app.services.knowledge_tree import (
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

        # 答题 → 认知中心: 练习事件驱动信念更新（投影更新单一路径）
        async def _on_answer_submitted_to_cognitive(event: DomainEvent) -> None:
            from shared.events import AnswerSubmitted
            if not isinstance(event, AnswerSubmitted):
                return
            try:
                from app.domain.cognitive.events import CognitiveEventHandler
                from app.infrastructure.db.session import get_db_session
                with get_db_session() as session:
                    handler = CognitiveEventHandler(session)
                    handler.handle_answer_submitted(event)
                    session.commit()
            except Exception:
                logger.debug("Cognitive handler failed for AnswerSubmitted", exc_info=True)
        bus.subscribe("AnswerSubmitted", _on_answer_submitted_to_cognitive)

        # 错题 → 知识图谱 + 媒体推荐
        bus.subscribe("ErrorRecorded", self.knowledge_service.on_error_recorded)
        bus.subscribe("ErrorRecorded", self.media_service.on_error_recorded)

        # 会话完成 → 对话记忆写回 + 计划更新
        bus.subscribe("SessionCompleted", self.session_bridge.on_session_completed)
        bus.subscribe("SessionCompleted", self.planning_service.on_session_completed)

        # CognitiveNode 元数据/链接变化 → 计划重调 + ZPD 调度
        # 旧 CognitiveNodeUpdated 已拆分为 CognitiveNodeLinked / CognitiveNodeMetadataChanged。
        # 掌握度（Belief）变化由 cognitive engine 内部处理，不再走 DomainEvent 总线。
        async def _on_cognitive_metadata_changed(event: DomainEvent) -> None:
            from shared.events import CognitiveNodeMetadataChanged
            if not isinstance(event, CognitiveNodeMetadataChanged):
                return
            logger.debug(
                "CognitiveNode metadata changed: %s fields=%s",
                event.node_id, event.changed_fields,
            )
            # 计划重调
            try:
                await self.planning_service.on_knowledge_updated(event)
            except Exception:
                logger.debug("Planning service failed to handle CognitiveNodeMetadataChanged")
            # ZPD 调度器重算
            try:
                from app.services.knowledge.zpd_scheduler import zpd_scheduler
                zpd_scheduler.on_knowledge_change(event.user_id, event.node_id)
            except Exception:
                logger.debug("ZPD scheduler not available, skipping")
        bus.subscribe("CognitiveNodeMetadataChanged", _on_cognitive_metadata_changed)

        # CognitiveNode 链接变化 → 知识图谱展示更新
        async def _on_cognitive_linked(event: DomainEvent) -> None:
            from shared.events import CognitiveNodeLinked
            if not isinstance(event, CognitiveNodeLinked):
                return
            logger.debug(
                "CognitiveNode link %s: %s -> %s/%s (%s)",
                event.action, event.node_id,
                event.target_ref_type, event.target_ref_id, event.link_type,
            )
        bus.subscribe("CognitiveNodeLinked", _on_cognitive_linked)

        # AI 回复 → 多媒体生成
        bus.subscribe("AssistantReplied", self.multimedia_service.on_assistant_replied)

        # AI 回复 → 对话副作用 (认知同步 / 知识证据 / 元历史)
        from app.domain.conversation.reply_hooks import reply_hooks
        reply_hooks.subscribe(bus)

        # ═══ Project 跨模块联动 — ProjectNodeExported 派发 (Task #50) ═══
        # Project 节点导出时, 根据 target_module 自动创建目标实体。
        # 5 target: flashcard / material / cognitive_node / plan / language_room
        from app.application.handlers.project_export_handlers import (
            handle_project_node_exported,
        )
        bus.subscribe("ProjectNodeExported", handle_project_node_exported)

        # ═══ EventSystem: 旧事件迁移 → EventBus 统一订阅 ═══

        # MessageClassified → 可见性级联 + 结构扩展检查
        async def _on_message_classified(event: DomainEvent) -> None:
            from shared.events import MessageClassified
            if not isinstance(event, MessageClassified):
                return
            try:
                from app.domain.cognitive import get_repo
                from app.infrastructure.db.proposal_store import ProposalStore
                from app.domain.secretary.models import Proposal
                repo = get_repo()
                node_ids = event.topic_node_ids + event.atom_node_ids
                for nid in node_ids:
                    try:
                        _cascade_ancestor_visibility(nid, event.user_id, repo)
                    except Exception:
                        pass
                # 结构扩展建议
                if event.topic_node_ids:
                    parent_candidates: set = set()
                    for tid in event.topic_node_ids:
                        node = repo.get_node(tid, event.user_id)
                        if node and node.parent:
                            parent_candidates.add(node.parent)
                    for pid in parent_candidates:
                        try:
                            children = repo.get_children(pid, event.user_id)
                            active = [c for c in children if c.is_visible and c.is_active]
                            if len(active) >= 3:
                                label = _get_node_label(pid, event.user_id, repo)
                                ProposalStore().save_proposal(
                                    Proposal(emoji="🌿", title=f"探索「{label}」下的更多专题",
                                        description=f"该分类下已有 {len(active)} 个活跃子专题，需要生成更多拓展方向吗？",
                                        action_type="explore", priority=2,
                                        payload={"parent_id": pid, "parent_label": label, "visible_count": len(active)},
                                        generated_by="event_handler", insight_source="structure_expansion"),
                                    user_id=event.user_id)
                        except Exception:
                            pass
            except Exception:
                logger.debug("MessageClassified handler failed", exc_info=True)
        bus.subscribe("MessageClassified", _on_message_classified)

        # NodeCreated → 波纹边检测 + 提案生成
        async def _on_node_created(event: DomainEvent) -> None:
            from shared.events import NodeCreated
            if not isinstance(event, NodeCreated):
                return
            try:
                from app.domain.cognitive import get_repo
                from app.infrastructure.db.cognitive_edge_storage import upsert_edge, get_edges_for_node
                from app.domain.cognitive.edge_models import KnowledgeEdge
                from datetime import datetime, timezone
                repo = get_repo()
                node = repo.get_node(event.node_id, event.user_id)
                if not node or not node.embedding:
                    return
                neighbors = repo.vector_search(node.embedding, event.user_id, level=event.level, limit=5, min_similarity=0.3)
                neighbors = [n for n in neighbors if n.get("id") != event.node_id]
                existing_edges = get_edges_for_node(event.node_id, event.user_id)
                existing_targets = {e.target_node_id if e.source_node_id == event.node_id else e.source_node_id for e in existing_edges}
                pending_edges = []
                for nbr in neighbors[:3]:
                    nid = nbr.get("id")
                    if nid in existing_targets:
                        continue
                    sim = nbr.get("similarity", 0.5)
                    edge = KnowledgeEdge(user_id=event.user_id, source_node_id=event.node_id,
                        target_node_id=nid, edge_type="related_to", strength=sim,
                        trust_score=sim * 0.8, edge_status="pending_confirm", created_by="system")
                    upsert_edge(edge)
                    pending_edges.append({"edge_id": edge.id, "source_label": node.label,
                        "target_label": nbr.get("label", nid), "similarity": sim, "target_node_id": nid})
                if pending_edges:
                    from app.infrastructure.db.proposal_store import ProposalStore
                    from app.domain.secretary.models import Proposal
                    top = pending_edges[0]
                    ProposalStore().save_proposal(
                        Proposal(emoji="🔗", title=f"关联知识点「{top['target_label']}」",
                            description=f"新知识点「{top['source_label']}」与已学「{top['target_label']}」语义相似度 {top['similarity']:.0%}，是否建立关联？",
                            action_type="explore", priority=3,
                            payload={"edge_id": top["edge_id"], "source_node_id": event.node_id,
                                "target_node_id": top["target_node_id"], "source_label": top["source_label"],
                                "target_label": top["target_label"], "similarity": top["similarity"], "pending_count": len(pending_edges)},
                            generated_by="event_handler", insight_source="ripple_edge"),
                        user_id=event.user_id)
            except Exception:
                logger.debug("NodeCreated handler failed", exc_info=True)
        bus.subscribe("NodeCreated", _on_node_created)

        # ProposalAccepted → 执行秘书提案动作
        async def _on_proposal_accepted(event: DomainEvent) -> None:
            from shared.events import ProposalAccepted
            if not isinstance(event, ProposalAccepted):
                return
            try:
                if event.action_type == "explore" and event.target_node_id:
                    from app.domain.cognitive.growth_engine import growth_engine
                    growth_engine.mark_expanded(event.user_id, event.target_node_id)
            except Exception:
                logger.debug("ProposalAccepted handler failed", exc_info=True)
        bus.subscribe("ProposalAccepted", _on_proposal_accepted)

        # PendingCrossTopic → 跨主题关联提案
        async def _on_pending_cross_topic(event: DomainEvent) -> None:
            from shared.events import PendingCrossTopic
            if not isinstance(event, PendingCrossTopic):
                return
            try:
                from app.domain.cognitive import get_repo
                from app.infrastructure.db.cognitive_edge_storage import get_edges_for_node
                from app.infrastructure.db.proposal_store import ProposalStore
                from app.domain.secretary.models import Proposal
                repo = get_repo()
                for cand in event.candidates[:2]:
                    cid = cand.get("id", "")
                    clabel = cand.get("label", "")
                    cscore = cand.get("score", 0)
                    if not cid:
                        continue
                    node = repo.get_node(cid, event.user_id)
                    if not node:
                        continue
                    edges = get_edges_for_node(cid, event.user_id)
                    if edges:
                        continue
                    ProposalStore().save_proposal(
                        Proposal(emoji="🔀", title=f"关联新话题「{clabel}」",
                            description=f"本次对话涉及了「{clabel}」相关内容（匹配度 {cscore:.0%}），是否需要关联到当前知识图谱？",
                            action_type="explore", priority=2,
                            payload={"candidate_node_id": cid, "candidate_label": clabel, "score": cscore, "source": "deep_immersion_deferred"},
                            generated_by="event_handler", insight_source="pending_cross_topic"),
                        user_id=event.user_id)
            except Exception:
                logger.debug("PendingCrossTopic handler failed", exc_info=True)
        bus.subscribe("PendingCrossTopic", _on_pending_cross_topic)

        # ═══ 跨模块反馈桥梁 ═══

        # CognitiveNodeMetadataChanged → 练习系统: 元数据/层级变化 → 调整练习难度
        async def _on_cognitive_to_practice(event: DomainEvent) -> None:
            from shared.events import CognitiveNodeMetadataChanged
            if not isinstance(event, CognitiveNodeMetadataChanged):
                return
            try:
                # 通知练习系统节点元数据已变化，下次选题时自适应调整
                await self.practice_service.on_knowledge_updated(event)
            except Exception:
                logger.debug("Practice service failed to handle CognitiveNodeMetadataChanged")
        bus.subscribe("CognitiveNodeMetadataChanged", _on_cognitive_to_practice)

        # AssistantReplied → 秘书系统: 对话内容 → 更新秘书上下文
        async def _on_assistant_to_secretary(event: DomainEvent) -> None:
            from shared.events import AssistantReplied
            if not isinstance(event, AssistantReplied):
                return
            try:
                from app.domain.secretary.engines.policy_engine import policy_engine
                # 秘书感知对话活动，记录交互
                policy_engine.record_interaction(event.user_id, None, "conversation_active")
            except Exception:
                logger.debug("Secretary policy engine not available")
        bus.subscribe("AssistantReplied", _on_assistant_to_secretary)

        # SessionCompleted → 知识树: 练习完成 → 刷新知识树掌握度展示
        async def _on_practice_to_knowledge_tree(event: DomainEvent) -> None:
            from shared.events import SessionCompleted
            if not isinstance(event, SessionCompleted):
                return
            try:
                from app.services.knowledge.zpd_scheduler import zpd_scheduler
                zpd_scheduler.on_session_completed(event.user_id, event.session_id)
            except Exception:
                logger.debug("ZPD scheduler not available")
        bus.subscribe("SessionCompleted", _on_practice_to_knowledge_tree)

        # ═══ Phase 3: 对话笔记 ↔ 闪卡双向同步 ═══
        async def _on_conversation_note_created_as_flashcard(event: DomainEvent) -> None:
            from shared.events import ConversationNoteCreatedAsFlashcard
            if not isinstance(event, ConversationNoteCreatedAsFlashcard):
                return
            try:
                from app.services.flashcard.conversation_note_handler import conversation_note_flashcard_handler
                await conversation_note_flashcard_handler._on_note_created_as_flashcard(event)
            except Exception:
                logger.debug("ConversationNote→Flashcard handler failed", exc_info=True)
        bus.subscribe("ConversationNoteCreatedAsFlashcard", _on_conversation_note_created_as_flashcard)

        async def _on_flashcard_updated_reverse_sync(event: DomainEvent) -> None:
            from shared.events import FlashCardUpdated
            if not isinstance(event, FlashCardUpdated):
                return
            try:
                from app.services.conversation.conversation_note_service import on_flashcard_updated
                await on_flashcard_updated(event)
            except Exception:
                logger.debug("FlashCardUpdated reverse sync failed", exc_info=True)
        bus.subscribe("FlashCardUpdated", _on_flashcard_updated_reverse_sync)

        # ═══ Phase 3: 答题微行为 → DiagnosticSignal ═══
        async def _on_practice_behavior_recorded(event: DomainEvent) -> None:
            from shared.events import PracticeAnswerBehaviorRecorded
            if not isinstance(event, PracticeAnswerBehaviorRecorded):
                return
            try:
                from app.domain.cognitive.diagnostic_signal_builder import diagnostic_signal_builder
                await diagnostic_signal_builder._on_behavior_recorded(event)
            except Exception:
                logger.debug("DiagnosticSignal builder failed", exc_info=True)
        bus.subscribe("PracticeAnswerBehaviorRecorded", _on_practice_behavior_recorded)

        # ── EventSystem: 工作记忆生命周期 ──
        async def _on_session_completed(event: DomainEvent) -> None:
            from shared.events import SessionCompleted
            if not isinstance(event, SessionCompleted):
                return
            user_id = event.user_id
            session_id = event.session_id
            try:
                self.event_memory.working_end(user_id, session_id)
            except Exception:
                logger.debug("EventMemory hook failed", exc_info=True)
        bus.subscribe("SessionCompleted", _on_session_completed)

        async def _on_assistant_replied(event: DomainEvent) -> None:
            from shared.events import AssistantReplied
            if not isinstance(event, AssistantReplied):
                return
            user_id = event.user_id
            conv_id = event.conv_id
            try:
                self.event_memory.working_event(
                    user_id, conv_id,
                    EventRecord(
                        user_id=user_id,
                        event_type="AssistantReplied",
                        stream_type="conversation",
                        stream_id=conv_id,
                        payload=asdict(event),
                    )
                )
            except Exception:
                    logger.debug("EventMemory hook failed", exc_info=True)
        bus.subscribe("AssistantReplied", _on_assistant_replied)

        # ── Task #50: ProjectNodeExported 跨模块联动 5 订阅者 ──
        from app.application.handlers.project_export_handlers import (
            handle_project_node_exported,
        )
        bus.subscribe("ProjectNodeExported", handle_project_node_exported)

        logger.info("🔗 注册 %d 个事件订阅", sum(len(v) for v in bus._handlers.values()))


# ── 全局容器实例（应用唯一单例） ──
container = AppContainer()


def get_event_bus():
    """获取全局事件总线 (供 API 层 / services 层懒加载)"""
    return container.event_bus


def get_event_store():
    """获取全局事件存储"""
    return container.event_store


def get_event_memory():
    """获取全局事件记忆"""
    return container.event_memory


# ── 事件处理辅助函数 ──


def _cascade_ancestor_visibility(node_id: str, user_id: str, repo=None) -> None:
    """级联更新祖先可见性"""
    if repo is None:
        from app.domain.cognitive import get_repo
        repo = get_repo()
    visited = set()
    current_id = node_id
    while current_id and current_id not in visited:
        visited.add(current_id)
        node = repo.get_node(current_id, user_id)
        if node is None:
            break
        if node.is_visible:
            break
        repo.set_node_visible(current_id, user_id, visible=True)
        current_id = node.parent


def _get_node_label(node_id: str, user_id: str, repo=None) -> str:
    """获取节点 label（安全降级）"""
    try:
        if repo is None:
            from app.domain.cognitive import get_repo
            repo = get_repo()
        node = repo.get_node(node_id, user_id)
        if node:
            return node.label or node_id
    except Exception:
        pass
    return node_id or "unknown"
