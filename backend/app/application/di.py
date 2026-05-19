"""
Phase 4: 依赖注入容器 — 唯一的全局组装点

所有模块在此装配，通过 Protocol 接口互相注入。
消除 35 个全局单例，集中为 1 个 AppContainer。

用法:
    from app.application.di import container
    result = await container.practice.submit_answer(...)

依赖规则:
    - DI 容器是唯一知道具体实现的模块
    - 所有 domain service 只通过 Protocol 引用彼此
"""

from __future__ import annotations

import logging

from app.infra.event_bus import EventBus
from app.infra.resilience import safe_async

logger = logging.getLogger("di")


class AppContainer:
    """
    应用容器 — 唯一知道所有具体实现的模块。

    组装顺序: 基础设施 → 领域服务 → 事件订阅
    每个 domain service 只看到其他模块的 Protocol 接口。
    """

    def __init__(self) -> None:
        # ── 基础设施 ──
        self.event_bus = EventBus()

        # ── 存储后端 ──
        from app.services.storage import storage
        self.storage = storage

        # ── LLM 客户端 ──
        from app.services.llm_service import llm_service
        self.llm = llm_service

        # ── 核心引擎（注入存储）─
        from app.core.knowledge_trace import BKTEngine
        self.bkt_engine = BKTEngine(storage=self.storage)

        from app.core.learner_model import LearnerModelEngine
        self.learner_engine = LearnerModelEngine()

        from app.core.orchestrator import Orchestrator
        self.orchestrator = Orchestrator(
            llm=self.llm,
            learner_engine=self.learner_engine,
        )

        # ── 领域服务 ──
        # 注意：当前 domain 逻辑仍在 services/ 目录下
        # Phase 4C-4D 中将迁移到 domain/ 目录
        from app.services.zpd_scheduler import ZPDScheduler
        self.zpd_scheduler = ZPDScheduler()

        from app.services.question_generator import QuestionGenerator
        self.question_generator = QuestionGenerator(llm_service=self.llm)

        from app.services.behavior_analyzer import LearningBehaviorAnalyzer
        self.behavior_analyzer = LearningBehaviorAnalyzer()

        from app.services.habit_formation import HabitFormation
        self.habit_formation = HabitFormation()

        from app.services.achievement_engine import AchievementEngine
        self.achievement_engine = AchievementEngine()

        from app.services.adaptive_planner import AdaptivePlanGenerator
        self.adaptive_planner = AdaptivePlanGenerator(bkt_engine=self.bkt_engine)

        from app.services.quality_analyzer import QualityAnalyzer
        self.quality_analyzer = QualityAnalyzer()

        from app.services.media_search import MediaSearchService
        self.media_search = MediaSearchService()

        # ── 事件订阅（模块联动） ──
        self._wire_events()

        logger.info("AppContainer initialized: %d domain services, %d event subscriptions",
                    9, len(self.event_bus.stats.get("subscriptions", {})))

    def _wire_events(self) -> None:
        """注册领域事件处理器 — 所有跨模块联动在此定义"""
        bus = self.event_bus

        # 答题 → 行为分析 + 习惯养成
        bus.subscribe("AnswerSubmitted", safe_async("analytics")(self._on_answer_submitted))
        # 答题 → 成就检测
        bus.subscribe("AnswerSubmitted", safe_async("achievements")(self._on_answer_achievements))
        # 知识升级 → 学习计划重调
        bus.subscribe("KnowledgeStateUpdated", safe_async("planning")(self._on_knowledge_updated))

    async def _on_answer_submitted(self, event) -> None:
        """答题 → 更新行为分析 + 习惯养成"""
        try:
            self.behavior_analyzer.analyze(event.user_id)
            self.habit_formation.check_daily_goal(event.user_id)
        except Exception:
            pass

    async def _on_answer_achievements(self, event) -> None:
        """答题 → 检测成就解锁"""
        try:
            from app.api.achievements import _collect_stats, _load_existing, _save_achievements
            stats = _collect_stats(event.user_id)
            existing = _load_existing(event.user_id)
            new_ach = self.achievement_engine.check_all(event.user_id, stats, existing)
            if new_ach:
                from app.shared.events import AchievementUnlocked
                for a in new_ach:
                    existing[a["id"]] = {"level": a["level"], "unlocked_at": a["unlocked_at"]}
                    await self.event_bus.publish(AchievementUnlocked(
                        user_id=event.user_id,
                        achievement_id=a["id"],
                        name=a.get("name", ""),
                        level=a.get("level", 1),
                    ))
                _save_achievements(event.user_id, existing)
        except Exception:
            pass

    async def _on_knowledge_updated(self, event) -> None:
        """知识升级 → 重调学习计划"""
        try:
            self.adaptive_planner.on_knowledge_updated(event)
        except Exception:
            pass


# ── 全局唯一实例 ──
container = AppContainer()
