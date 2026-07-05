"""
Planning 完成回写链路 (ADR 0006)

PlanItemCompleted → 根据 source_module 路由到对应模块的状态更新
**关键**：回写不重发源事件（防循环）。

路由表 (由 PlanningSourceModule 枚举统一管理, 新增模块仅需追加枚举值 + handler):
  - flashcard       → 标记 plan_items 状态为 completed（卡片复习事件由 FSRS 自行处理）
  - practice        → 标记 plan_items 状态为 completed（会话事件由 practice 自身发布）
  - project         → 更新 ProjectNode.status = 'completed'（**不**重发 ProjectNodeCompleted）
  - reading         → 标记 plan_items 状态为 completed（阅读进度由 reading 自身记录）
  - language_room   → 标记 plan_items 状态为 completed
  - manual          → 标记 plan_items 状态为 completed
  - interest_explorer → 标记 plan_items 状态为 completed（兴趣探索完成事件由自身发布）
  - mood_stress     → 标记 plan_items 状态为 completed（心情压力调节事件由自身发布）

幂等性：
  - 通过 plan_item_id 做幂等键 (一次完整事件流中)
  - 已经在 'completed' 状态的 plan_item 直接返回，不重复处理
"""
from __future__ import annotations

import logging
from typing import Any, Optional

from shared.events import PlanningSourceModule

logger = logging.getLogger("planning.completion_writer")


class PlanningCompletionWriter:
    """PlanItemCompleted → 路由到各源模块状态更新（不回发源事件）"""

    # 路由表：source_module → handler name (SSOT = PlanningSourceModule 枚举)
    _ROUTES: tuple[PlanningSourceModule, ...] = tuple(PlanningSourceModule)

    def __init__(self) -> None:
        self._bus: Any = None
        self._subscribed = False
        # 幂等：plan_item_id → 事件 ID
        self._seen: dict[str, str] = {}

    def subscribe(self, bus: Any) -> None:
        """订阅 PlanItemCompleted 事件"""
        if self._subscribed:
            return
        from app.infrastructure.event_bus import EventBus
        from app.infrastructure.persistent_event_bus import PersistentEventBus
        if not isinstance(bus, (EventBus, PersistentEventBus)):
            logger.warning("传入的对象不是 EventBus 实例（%s），跳过订阅",
                           type(bus).__module__)
            return
        bus.subscribe("PlanItemCompleted", self._on_completed)
        bus.subscribe("PlanItemSkipped", self._on_skipped)
        bus.subscribe("PlanItemExtended", self._on_extended)
        bus.subscribe("PlanItemStarted", self._on_started)
        bus.subscribe("PlanItemScheduled", self._on_scheduled)
        bus.subscribe("MoodStressRuleTriggered", self._on_mood_rule)
        self._bus = bus
        self._subscribed = True
        logger.info("📡 PlanningCompletionWriter 已订阅: PlanItemCompleted/Skipped/Extended/Started/Scheduled + MoodStressRuleTriggered")

    def unsubscribe(self) -> None:
        if not self._bus or not self._subscribed:
            return
        self._bus.unsubscribe("PlanItemCompleted", self._on_completed)
        self._bus.unsubscribe("PlanItemSkipped", self._on_skipped)
        self._bus.unsubscribe("PlanItemExtended", self._on_extended)
        self._bus.unsubscribe("PlanItemStarted", self._on_started)
        self._bus.unsubscribe("PlanItemScheduled", self._on_scheduled)
        self._bus.unsubscribe("MoodStressRuleTriggered", self._on_mood_rule)
        self._subscribed = False
        logger.info("📡 PlanningCompletionWriter 已取消订阅")

    # ── 事件 handler ──

    async def _on_completed(self, event) -> None:
        """完成回写主入口（不重发源事件）"""
        from shared.events import PlanItemCompleted
        if not isinstance(event, PlanItemCompleted):
            return
        pid = event.plan_item_id
        if not pid:
            return
        # 幂等去重（同一 plan_item_id 在事件流中只处理一次）
        if pid in self._seen:
            logger.debug("PlanItemCompleted 重复事件，忽略: plan_item_id=%s", pid)
            return
        self._seen[pid] = event.event_id

        try:
            handler = self._ROUTE_HANDLERS.get(event.source_module)
            if handler is None:
                logger.debug("PlanItemCompleted 未匹配路由: source_module=%s", event.source_module)
                return
            await handler(self, event)
            logger.info(
                "PlanItemCompleted 回写完成: plan_item_id=%s source=%s target=%s",
                pid, event.source_module, event.target_ref_id,
            )
        except Exception as e:
            logger.exception("PlanItemCompleted 回写失败: plan_item_id=%s err=%s", pid, e)

    async def _on_skipped(self, event) -> None:
        from shared.events import PlanItemSkipped
        if not isinstance(event, PlanItemSkipped):
            return
        try:
            await self._update_plan_item_status(
                plan_item_id=event.plan_item_id,
                status="skipped",
                skipped_at=event.skipped_at,
            )
        except Exception as e:
            logger.exception("PlanItemSkipped 处理失败: %s", e)

    async def _on_extended(self, event) -> None:
        from shared.events import PlanItemExtended
        if not isinstance(event, PlanItemExtended):
            return
        try:
            await self._extend_plan_item(
                plan_item_id=event.plan_item_id,
                extra_minutes=event.extended_minutes,
            )
        except Exception as e:
            logger.exception("PlanItemExtended 处理失败: %s", e)

    async def _on_started(self, event) -> None:
        from shared.events import PlanItemStarted
        if not isinstance(event, PlanItemStarted):
            return
        try:
            await self._update_plan_item_status(
                plan_item_id=event.plan_item_id,
                status="in_progress",
                started_at=event.started_at,
            )
        except Exception as e:
            logger.exception("PlanItemStarted 处理失败: %s", e)

    async def _on_scheduled(self, event) -> None:
        from shared.events import PlanItemScheduled
        if not isinstance(event, PlanItemScheduled):
            return
        try:
            from app.infrastructure.db.database import get_db
            db = get_db()
            db.execute(
                """UPDATE plan_items SET status='scheduled', scheduled_for=%s,
                   is_mood_rule_affected=%s, updated_at=NOW() WHERE id=%s""",
                (event.scheduled_for, event.is_mood_rule_affected, event.plan_item_id),
            )
        except Exception as e:
            logger.exception("PlanItemScheduled 处理失败: %s", e)

    async def _on_mood_rule(self, event) -> None:
        """MoodStress 规则触发时，标记受影响待办项（**只标记，不自动修改**）"""
        from shared.events import MoodStressRuleTriggered
        if not isinstance(event, MoodStressRuleTriggered):
            return
        try:
            if event.action != "postpone_high_intensity":
                # 其它规则不在规划做标记
                return
            from app.infrastructure.db.database import get_db
            db = get_db()
            # 仅标记 source_module=project 的 pending/scheduled 项
            db.execute(
                """UPDATE plan_items SET is_mood_rule_affected=TRUE, updated_at=NOW()
                   WHERE user_id=%s AND source_module=%s
                     AND status IN ('pending','scheduled')""",
                (event.user_id, PlanningSourceModule.PROJECT.value),
            )
            logger.info("MoodStress 规则已标记: user=%s action=%s", event.user_id, event.action)
        except Exception as e:
            logger.exception("MoodStressRuleTriggered 标记失败: %s", e)

    # ── 路由 handlers ──

    async def _handle_flashcard(self, event) -> None:
        """flashcard 来源：只更新 plan_items 状态

        FlashCardReviewed 事件由 FlashCard 自身发布，本回写**不**重发。
        """
        await self._update_plan_item_status(
            plan_item_id=event.plan_item_id,
            status="completed",
            actual_minutes=event.actual_minutes,
            completed_at=event.completed_at,
        )

    async def _handle_practice(self, event) -> None:
        """practice 来源：只更新 plan_items 状态

        SessionCompleted 事件由 practice 自身发布，本回写**不**重发。
        """
        await self._update_plan_item_status(
            plan_item_id=event.plan_item_id,
            status="completed",
            actual_minutes=event.actual_minutes,
            completed_at=event.completed_at,
        )

    async def _handle_project(self, event) -> None:
        """project 来源：更新 ProjectNode.status='completed'（**不**重发 ProjectNodeCompleted）

        关键防循环：直接 UPDATE project_nodes 表，**不**发布 ProjectNodeCompleted 事件。
        """
        from app.infrastructure.db.database import get_db
        db = get_db()
        # target_ref_id 约定为 project_node_id
        target = event.target_ref_id
        if not target:
            logger.warning("project 计划项缺少 target_ref_id，无法回写: plan_item_id=%s", event.plan_item_id)
            await self._update_plan_item_status(
                plan_item_id=event.plan_item_id,
                status="completed",
                actual_minutes=event.actual_minutes,
                completed_at=event.completed_at,
            )
            return
        # 直接更新节点状态 — 不发 ProjectNodeCompleted
        try:
            db.execute(
                """UPDATE project_nodes SET status='completed',
                   completed_at=COALESCE(completed_at, NOW()),
                   updated_at=NOW() WHERE id=%s AND user_id=%s""",
                (target, event.user_id),
            )
        except Exception as e:
            # project_nodes 表可能不存在（项目模块未启用），降级
            logger.debug("project_nodes UPDATE 失败（可能表不存在）: %s", e)

        await self._update_plan_item_status(
            plan_item_id=event.plan_item_id,
            status="completed",
            actual_minutes=event.actual_minutes,
            completed_at=event.completed_at,
        )

    async def _handle_reading(self, event) -> None:
        """reading 来源：标记 plan_items 完成（阅读进度由 reading 自身记录）"""
        await self._update_plan_item_status(
            plan_item_id=event.plan_item_id,
            status="completed",
            actual_minutes=event.actual_minutes,
            completed_at=event.completed_at,
        )
        # 记录 reading 进度（best-effort，reading 表若不存在则忽略）
        try:
            from app.infrastructure.db.database import get_db
            db = get_db()
            db.execute(
                """INSERT INTO reading_progress (user_id, target_ref_id, last_plan_item_id,
                   actual_minutes, completed_at)
                   VALUES (%s, %s, %s, %s, NOW())
                   ON CONFLICT (user_id, target_ref_id) DO UPDATE
                   SET actual_minutes = reading_progress.actual_minutes + EXCLUDED.actual_minutes,
                       last_plan_item_id = EXCLUDED.last_plan_item_id,
                       completed_at = EXCLUDED.completed_at""",
                (event.user_id, event.target_ref_id, event.plan_item_id, event.actual_minutes),
            )
        except Exception as e:
            logger.debug("reading_progress 写入跳过（表可能不存在）: %s", e)

    async def _handle_language_room(self, event) -> None:
        """language_room 来源：标记 plan_items 完成（房间会话由自身记录）"""
        await self._update_plan_item_status(
            plan_item_id=event.plan_item_id,
            status="completed",
            actual_minutes=event.actual_minutes,
            completed_at=event.completed_at,
        )

    async def _handle_manual(self, event) -> None:
        """manual 来源：仅标记 plan_items 完成"""
        await self._update_plan_item_status(
            plan_item_id=event.plan_item_id,
            status="completed",
            actual_minutes=event.actual_minutes,
            completed_at=event.completed_at,
        )

    async def _handle_interest_explorer(self, event) -> None:
        """interest_explorer 来源：仅标记 plan_items 完成

        Interest 探索完成事件由 interest_explorer 自身发布，本回写**不**重发。
        """
        await self._update_plan_item_status(
            plan_item_id=event.plan_item_id,
            status="completed",
            actual_minutes=event.actual_minutes,
            completed_at=event.completed_at,
        )

    async def _handle_mood_stress(self, event) -> None:
        """mood_stress 来源：仅标记 plan_items 完成

        MoodStress 调节完成事件由 mood_stress 自身发布，本回写**不**重发。
        """
        await self._update_plan_item_status(
            plan_item_id=event.plan_item_id,
            status="completed",
            actual_minutes=event.actual_minutes,
            completed_at=event.completed_at,
        )

    # 路由 handler 字典 (SSOT = PlanningSourceModule 枚举, 键使用 .value 字符串)
    _ROUTE_HANDLERS: dict[str, Any] = {
        PlanningSourceModule.FLASHCARD.value: _handle_flashcard,
        PlanningSourceModule.PRACTICE.value: _handle_practice,
        PlanningSourceModule.PROJECT.value: _handle_project,
        PlanningSourceModule.READING.value: _handle_reading,
        PlanningSourceModule.LANGUAGE_ROOM.value: _handle_language_room,
        PlanningSourceModule.MANUAL.value: _handle_manual,
        PlanningSourceModule.INTEREST_EXPLORER.value: _handle_interest_explorer,
        PlanningSourceModule.MOOD_STRESS.value: _handle_mood_stress,
        PlanningSourceModule.INTEREST.value: _handle_manual,
        PlanningSourceModule.SECRETARY.value: _handle_manual,
        PlanningSourceModule.SYSTEM.value: _handle_manual,
    }

    # ── DB helpers ──

    async def _update_plan_item_status(
        self,
        *,
        plan_item_id: str,
        status: str,
        actual_minutes: Optional[int] = None,
        completed_at = None,
        started_at = None,
        skipped_at = None,
    ) -> None:
        from app.infrastructure.db.database import get_db
        db = get_db()
        sets = ["status=%s", "updated_at=NOW()"]
        params: list = [status]
        if actual_minutes is not None:
            sets.append("actual_minutes=%s")
            params.append(actual_minutes)
        if completed_at is not None:
            sets.append("completed_at=%s")
            params.append(completed_at)
        if started_at is not None:
            sets.append("started_at=%s")
            params.append(started_at)
        if skipped_at is not None:
            sets.append("skipped_at=%s")
            params.append(skipped_at)
        params.append(plan_item_id)
        db.execute(
            f"UPDATE plan_items SET {', '.join(sets)} WHERE id=%s",
            tuple(params),
        )

    async def _extend_plan_item(self, *, plan_item_id: str, extra_minutes: int) -> None:
        from app.infrastructure.db.database import get_db
        db = get_db()
        # 累加 estimated_minutes，状态置 extended
        db.execute(
            """UPDATE plan_items
               SET estimated_minutes = COALESCE(estimated_minutes, 0) + %s,
                   status = 'extended',
                   updated_at = NOW()
               WHERE id = %s""",
            (extra_minutes, plan_item_id),
        )


# 全局单例
planning_completion_writer = PlanningCompletionWriter()

# 兜底: 在 import 时主动尝试订阅 DI 全局 bus
# 这样保证: TestClient 在 lifespan 之外 (例如 import 早于 lifespan) 也能让
# PlanItemCompleted 路由到回写 handler, **不**影响单元测试 (test_subscribe_idempotent
# 等用 new PlanningCompletionWriter() 而非单例, 不会被此块污染)
if not planning_completion_writer._subscribed:
    try:
        from app.application.di import get_event_bus
        bus = get_event_bus()
        if bus is not None:
            planning_completion_writer.subscribe(bus)
    except Exception:
        # DI 容器尚未就绪 (例如某些测试场景提前 import), 跳过
        # 后续 main.py lifespan 会再调 subscribe
        pass
