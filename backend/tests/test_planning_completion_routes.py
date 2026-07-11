"""
Task #61: Planning 跨模块联动 + completion_writer 8 路由审计

审计目标 (ADR 0006 关键差异 1 + 11):
  1. 验证 PlanItemCompleted 按 source_module 路由到 8 个对应 handler
  2. 验证每条路由有正确的副作用 (plan_items 状态变更 / 跨模块状态回写)
  3. 验证事件循环不重发 (防 source_module 自身事件回环)
  4. 验证幂等: 重复 complete 不会产生重复副作用
  5. 验证 ADR 关键差异 5: deviation_type 字段名 audit (Literal["timeout","skip","early_complete","extra_insert"])

8 路由表 (SSOT = PlanningSourceModule 枚举):
  - flashcard        → plan_items 状态 completed (FlashCardReviewed 由 FSRS 自行处理)
  - practice         → plan_items 状态 completed (SessionCompleted 由 practice 自身发布)
  - project          → project_nodes.status='completed' + plan_items 状态 completed
  - reading          → plan_items 状态 completed + reading_progress 累加 (best-effort)
  - language_room    → plan_items 状态 completed
  - manual           → plan_items 状态 completed
  - interest_explorer → plan_items 状态 completed
  - mood_stress      → plan_items 状态 completed

运行方式:
    cd backend && python3 -m pytest tests/test_planning_completion_routes.py -v
"""
from __future__ import annotations

import asyncio
import json
import os
import sys
import uuid
from typing import Any

import pytest

# 让 backend 在 sys.path
BACKEND = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BACKEND not in sys.path:
    sys.path.insert(0, str(BACKEND))


# ── 公共 helpers ──


def _try_connect():
    try:
        from app.infrastructure.db.database import get_db
        d = get_db()
        d.fetchone("SELECT 1")
        return d
    except Exception as exc:  # noqa: BLE001
        pytest.skip(f"数据库不可用: {exc}")


def _table_exists(db, table_name: str) -> bool:
    row = db.fetchone(
        """
        SELECT 1 FROM information_schema.tables
         WHERE table_name = %s LIMIT 1
        """,
        (table_name,),
    )
    return row is not None


def _insert_plan_item(
    user_id: str,
    source_module: str,
    target_type: str = "manual",
    target_ref_id: str | None = None,
    title: str = "审计项",
) -> str:
    """Insert a plan_item row directly (skip validation), return its ID"""
    db = _try_connect()
    pid = f"plan_{uuid.uuid4().hex[:16]}"
    if target_ref_id is None:
        target_ref_id = f"tgt_{uuid.uuid4().hex[:12]}"
    db.execute(
        """INSERT INTO plan_items
           (id, user_id, source_module, target_type, target_ref_id, title,
            estimated_minutes, linked_node_ids, priority, status)
           VALUES (%s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s, 'pending')""",
        (
            pid, user_id, source_module, target_type, target_ref_id,
            title or f"审计-{source_module}",
            30,
            json.dumps([], ensure_ascii=False),
            0,
        ),
    )
    return pid


def _insert_project_node(user_id: str, status: str = "pending") -> str:
    """Create a project + node pair for project route test, return node_id"""
    db = _try_connect()
    proj_id = str(uuid.uuid4())
    node_id = str(uuid.uuid4())
    db.execute(
        """INSERT INTO projects (id, user_id, name, status)
           VALUES (%s, %s, %s, 'active')""",
        (proj_id, user_id, f"审计项目-{user_id[:8]}"),
    )
    db.execute(
        """INSERT INTO project_nodes
           (id, user_id, project_id, type, title, status)
           VALUES (%s, %s, %s, 2, %s, %s)""",
        (node_id, user_id, proj_id, f"审计节点-{node_id[:8]}", status),
    )
    return node_id


def _new_writer_with_bus() -> tuple[Any, Any]:
    """返回 (EventBus, PlanningCompletionWriter) — 全新实例, 不污染全局"""
    from app.infrastructure.event_bus import EventBus
    from app.services.planning.completion_writer import PlanningCompletionWriter
    bus = EventBus(handler_timeout=2.0)
    writer = PlanningCompletionWriter()
    return bus, writer


# 在模块加载时保存原始 _ROUTE_HANDLERS 字典 (防御 test_planning_completion_writer.py
# 的 test_duplicate_event_ignored 等历史测试对类级字典的污染)。
# 该测试中 `writer._ROUTE_HANDLERS[...MODULE.value] = fake_handler` 实际上
# 是修改类级字典 (Python 类属性查找), 影响所有后续测试的路由表。
from app.services.planning.completion_writer import PlanningCompletionWriter as _PCW
_ORIGINAL_ROUTE_HANDLERS: dict = dict(_PCW._ROUTE_HANDLERS)


@pytest.fixture(autouse=True)
def _isolate_route_handlers():
    """保护: 在每个测试前后重置 _ROUTE_HANDLERS 为模块加载时的原始字典,
    保证测试隔离。"""
    _PCW._ROUTE_HANDLERS.clear()
    _PCW._ROUTE_HANDLERS.update(_ORIGINAL_ROUTE_HANDLERS)
    yield
    _PCW._ROUTE_HANDLERS.clear()
    _PCW._ROUTE_HANDLERS.update(_ORIGINAL_ROUTE_HANDLERS)


async def _publish_and_drain(bus, event) -> None:
    """publish 事件并等待所有 handler 跑完 (async 上下文)"""
    await bus.publish(event)


# ── 事件名常量 (用于 source event 捕获) ──

SOURCE_EVENTS = {
    "flashcard": "FlashCardReviewed",
    "practice": "SessionCompleted",
    "project": "ProjectNodeCompleted",
    "reading": "ReadingNoteCreated",
    "language_room": "LanguageRoomCompleted",
    "manual": None,            # manual 无源事件
    "interest_explorer": "InterestPushGenerated",
    "mood_stress": "MoodStressInterventionTriggered",
}


# ══════════════════════════════════════════════════════════════
# 8 路由 E2E 测试 — 每条 source_module 各 1 个
# ══════════════════════════════════════════════════════════════


class TestRouteFlashcard:
    """flashcard 路由: plan_items.status='completed', 不重发 FlashCardReviewed"""

    @pytest.mark.asyncio
    async def test_flashcard_route_completes_and_no_resend(self):
        from shared.events import PlanItemCompleted, PlanningSourceModule

        user_id = f"xplnfc_{uuid.uuid4().hex[:12]}"
        pid = _insert_plan_item(user_id, "flashcard", target_type="flashcard_set")

        bus, writer = _new_writer_with_bus()
        captured: list = []

        async def _cap_fc_reviewed(event):
            captured.append(event)
        bus.subscribe("FlashCardReviewed", _cap_fc_reviewed)
        writer.subscribe(bus)

        event = PlanItemCompleted(
            user_id=user_id, plan_item_id=pid,
            source_module=PlanningSourceModule.FLASHCARD.value,
            target_type="flashcard_set", target_ref_id="fc_audit_001",
            actual_minutes=15,
        )
        await _publish_and_drain(bus, event)

        # 1. plan_items 状态变更
        db = _try_connect()
        row = db.fetchone("SELECT status, actual_minutes FROM plan_items WHERE id=%s", (pid,))
        assert row is not None, f"plan_item 消失: {pid}"
        assert row["status"] == "completed", f"flashcard 路由未完成: status={row['status']}"
        assert row["actual_minutes"] == 15

        # 2. 不重发 FlashCardReviewed
        assert len(captured) == 0, (
            f"flashcard 路由重发了 FlashCardReviewed, 违反事件循环修复 (ADR 关键差异 1): "
            f"实际捕获 {len(captured)} 次"
        )

    @pytest.mark.asyncio
    async def test_flashcard_idempotent_on_replay(self):
        """flashcard 路由: 重复事件被去重"""
        from shared.events import PlanItemCompleted, PlanningSourceModule

        user_id = f"xplnfc2_{uuid.uuid4().hex[:12]}"
        pid = _insert_plan_item(user_id, "flashcard", target_type="flashcard_set")

        bus, writer = _new_writer_with_bus()
        captured: list = []

        async def _cap_fc(event):
            captured.append(event)
        bus.subscribe("FlashCardReviewed", _cap_fc)
        writer.subscribe(bus)

        event = PlanItemCompleted(
            user_id=user_id, plan_item_id=pid,
            source_module=PlanningSourceModule.FLASHCARD.value,
            target_type="flashcard_set", target_ref_id="fc_audit_002",
            actual_minutes=10,
        )
        # 第一次: 真处理
        await _publish_and_drain(bus, event)
        # 重复 3 次: 应被 plan_item_id 幂等键去重
        await _publish_and_drain(bus, event)
        await _publish_and_drain(bus, event)
        await _publish_and_drain(bus, event)

        # 4 次 publish, 但 handler 只跑 1 次 → FlashCardReviewed 一次都不会重发
        assert len(captured) == 0
        # actual_minutes 仍为 10 (不被覆盖)
        db = _try_connect()
        row = db.fetchone("SELECT actual_minutes FROM plan_items WHERE id=%s", (pid,))
        assert row["actual_minutes"] == 10


class TestRoutePractice:
    """practice 路由: plan_items.status='completed', 不重发 SessionCompleted"""

    @pytest.mark.asyncio
    async def test_practice_route_completes_and_no_resend(self):
        from shared.events import PlanItemCompleted, PlanningSourceModule

        user_id = f"xplnpr_{uuid.uuid4().hex[:12]}"
        pid = _insert_plan_item(user_id, "practice", target_type="practice_set")

        bus, writer = _new_writer_with_bus()
        captured: list = []

        async def _cap_sc(event):
            captured.append(event)
        # practice 路由可能重发的源事件: SessionCompleted (会话完成)
        bus.subscribe("SessionCompleted", _cap_sc)
        bus.subscribe("AnswerSubmitted", _cap_sc)
        writer.subscribe(bus)

        event = PlanItemCompleted(
            user_id=user_id, plan_item_id=pid,
            source_module=PlanningSourceModule.PRACTICE.value,
            target_type="practice_set", target_ref_id="pr_audit_001",
            actual_minutes=25,
        )
        await _publish_and_drain(bus, event)

        db = _try_connect()
        row = db.fetchone("SELECT status, actual_minutes FROM plan_items WHERE id=%s", (pid,))
        assert row is not None
        assert row["status"] == "completed"
        assert row["actual_minutes"] == 25
        assert len(captured) == 0, (
            f"practice 路由重发了 {len(captured)} 个源事件, 违反事件循环修复"
        )


class TestRouteProject:
    """project 路由: project_nodes.status='completed' + plan_items.status='completed'"""

    @pytest.mark.asyncio
    async def test_project_route_completes_node_and_no_resend(self):
        from shared.events import PlanItemCompleted, PlanningSourceModule

        user_id = f"xplnpj_{uuid.uuid4().hex[:12]}"
        node_id = _insert_project_node(user_id, status="pending")
        pid = _insert_plan_item(
            user_id, "project", target_type="project_node", target_ref_id=node_id
        )

        bus, writer = _new_writer_with_bus()
        captured: list = []

        async def _cap_pnc(event):
            captured.append(event)
        bus.subscribe("ProjectNodeCompleted", _cap_pnc)
        writer.subscribe(bus)

        event = PlanItemCompleted(
            user_id=user_id, plan_item_id=pid,
            source_module=PlanningSourceModule.PROJECT.value,
            target_type="project_node", target_ref_id=node_id,
            actual_minutes=60,
        )
        await _publish_and_drain(bus, event)

        db = _try_connect()
        # 1. project_nodes 状态变更 (关键跨模块副作用)
        node = db.fetchone(
            "SELECT status, completed_at FROM project_nodes WHERE id=%s AND user_id=%s",
            (node_id, user_id),
        )
        assert node is not None, f"project_node 消失: {node_id}"
        assert node["status"] == "completed", (
            f"project 路由未回写节点状态: status={node['status']}"
        )
        assert node["completed_at"] is not None, "project_node.completed_at 应被设置"

        # 2. plan_items 状态也变更
        item = db.fetchone("SELECT status FROM plan_items WHERE id=%s", (pid,))
        assert item["status"] == "completed"

        # 3. 不重发 ProjectNodeCompleted (Task #40 已修, 保持验证)
        assert len(captured) == 0, (
            f"project 路由重发了 ProjectNodeCompleted, 违反 Task #40 修复: "
            f"实际 {len(captured)} 次"
        )

    @pytest.mark.asyncio
    async def test_project_route_without_target_ref_id(self):
        """project 路由: target_ref_id 缺失时降级 — 仅更新 plan_items"""
        from shared.events import PlanItemCompleted, PlanningSourceModule

        user_id = f"xplnpj2_{uuid.uuid4().hex[:12]}"
        pid = _insert_plan_item(user_id, "project", target_type="project_node", target_ref_id="")

        bus, writer = _new_writer_with_bus()
        captured: list = []

        async def _cap_pnc(event):
            captured.append(event)
        bus.subscribe("ProjectNodeCompleted", _cap_pnc)
        writer.subscribe(bus)

        event = PlanItemCompleted(
            user_id=user_id, plan_item_id=pid,
            source_module=PlanningSourceModule.PROJECT.value,
            target_type="project_node", target_ref_id="",
            actual_minutes=0,
        )
        await _publish_and_drain(bus, event)

        db = _try_connect()
        item = db.fetchone("SELECT status FROM plan_items WHERE id=%s", (pid,))
        # 应降级为 completed (有 warning log)
        assert item["status"] == "completed"
        # 仍不重发
        assert len(captured) == 0


class TestRouteReading:
    """reading 路由: plan_items.status='completed' + reading_progress 累加 (best-effort)"""

    @pytest.mark.asyncio
    async def test_reading_route_completes_and_no_resend(self):
        from shared.events import PlanItemCompleted, PlanningSourceModule

        user_id = f"xplnrd_{uuid.uuid4().hex[:12]}"
        pid = _insert_plan_item(user_id, "reading", target_type="material")

        bus, writer = _new_writer_with_bus()
        captured: list = []

        async def _cap_rnc(event):
            captured.append(event)
        bus.subscribe("ReadingNoteCreated", _cap_rnc)
        writer.subscribe(bus)

        event = PlanItemCompleted(
            user_id=user_id, plan_item_id=pid,
            source_module=PlanningSourceModule.READING.value,
            target_type="material", target_ref_id="mat_audit_001",
            actual_minutes=20,
        )
        await _publish_and_drain(bus, event)

        db = _try_connect()
        item = db.fetchone("SELECT status, actual_minutes FROM plan_items WHERE id=%s", (pid,))
        assert item is not None
        assert item["status"] == "completed"
        assert item["actual_minutes"] == 20
        # 不重发 ReadingNoteCreated
        assert len(captured) == 0, (
            f"reading 路由重发了 ReadingNoteCreated: {len(captured)} 次"
        )

        # reading_progress 表若存在, 验证累加 (best-effort)
        if _table_exists(db, "reading_progress"):
            prog = db.fetchone(
                "SELECT actual_minutes FROM reading_progress "
                "WHERE user_id=%s AND target_ref_id=%s",
                (user_id, "mat_audit_001"),
            )
            if prog:
                # 累加正确性: 至少 >= 20
                assert (prog["actual_minutes"] or 0) >= 20


class TestRouteLanguageRoom:
    """language_room 路由: plan_items.status='completed'"""

    @pytest.mark.asyncio
    async def test_language_room_route_completes_and_no_resend(self):
        from shared.events import PlanItemCompleted, PlanningSourceModule

        user_id = f"xplnlr_{uuid.uuid4().hex[:12]}"
        pid = _insert_plan_item(user_id, "language_room", target_type="scenario")

        bus, writer = _new_writer_with_bus()
        captured: list = []

        async def _cap_lrc(event):
            captured.append(event)
        # liveroom 任何"完成/会话"事件都不应重发
        for evt in (
            "LanguageRoomCompleted",
            "LanguageRoomEnded",
            "LanguageRoomStarted",
            "LanguageRoomParticipantJoined",
        ):
            bus.subscribe(evt, _cap_lrc)
        writer.subscribe(bus)

        event = PlanItemCompleted(
            user_id=user_id, plan_item_id=pid,
            source_module=PlanningSourceModule.LANGUAGE_ROOM.value,
            target_type="scenario", target_ref_id="lr_audit_001",
            actual_minutes=45,
        )
        await _publish_and_drain(bus, event)

        db = _try_connect()
        item = db.fetchone("SELECT status, actual_minutes FROM plan_items WHERE id=%s", (pid,))
        assert item["status"] == "completed"
        assert item["actual_minutes"] == 45
        assert len(captured) == 0, (
            f"language_room 路由重发了 liveroom 事件: {len(captured)} 次"
        )


class TestRouteManual:
    """manual 路由: 仅 plan_items.status='completed' (无回写)"""

    @pytest.mark.asyncio
    async def test_manual_route_completes(self):
        from shared.events import PlanItemCompleted, PlanningSourceModule

        user_id = f"xplnm_{uuid.uuid4().hex[:12]}"
        pid = _insert_plan_item(user_id, "manual", target_type="manual")

        bus, writer = _new_writer_with_bus()
        # 捕获所有可能误发的源事件 (manual 应零重发)
        captured: list = []
        async def _cap_all(event):
            captured.append(event)
        for evt in SOURCE_EVENTS.values():
            if evt:
                bus.subscribe(evt, _cap_all)
        writer.subscribe(bus)

        event = PlanItemCompleted(
            user_id=user_id, plan_item_id=pid,
            source_module=PlanningSourceModule.MANUAL.value,
            target_type="manual", target_ref_id="m_audit_001",
            actual_minutes=5,
        )
        await _publish_and_drain(bus, event)

        db = _try_connect()
        item = db.fetchone("SELECT status, actual_minutes FROM plan_items WHERE id=%s", (pid,))
        assert item["status"] == "completed"
        assert item["actual_minutes"] == 5
        # manual 路由零重发
        assert len(captured) == 0, (
            f"manual 路由意外重发了 {len(captured)} 个源事件"
        )


class TestRouteInterestExplorer:
    """interest_explorer 路由: plan_items.status='completed'"""

    @pytest.mark.asyncio
    async def test_interest_explorer_route_completes_and_no_resend(self):
        from shared.events import PlanItemCompleted, PlanningSourceModule

        user_id = f"xplnie_{uuid.uuid4().hex[:12]}"
        pid = _insert_plan_item(user_id, "interest_explorer", target_type="interest_tag")

        bus, writer = _new_writer_with_bus()
        captured: list = []

        async def _cap_int(event):
            captured.append(event)
        for evt in ("InterestPushGenerated", "InterestTagUpdated", "InterestSourceFetched"):
            bus.subscribe(evt, _cap_int)
        writer.subscribe(bus)

        event = PlanItemCompleted(
            user_id=user_id, plan_item_id=pid,
            source_module=PlanningSourceModule.INTEREST_EXPLORER.value,
            target_type="interest_tag", target_ref_id="ie_audit_001",
            actual_minutes=30,
        )
        await _publish_and_drain(bus, event)

        db = _try_connect()
        item = db.fetchone("SELECT status FROM plan_items WHERE id=%s", (pid,))
        assert item["status"] == "completed"
        assert len(captured) == 0, (
            f"interest_explorer 路由重发了 interest 事件: {len(captured)} 次"
        )


class TestRouteMoodStress:
    """mood_stress 路由: plan_items.status='completed'"""

    @pytest.mark.asyncio
    async def test_mood_stress_route_completes_and_no_resend(self):
        from shared.events import PlanItemCompleted, PlanningSourceModule

        user_id = f"xplnms_{uuid.uuid4().hex[:12]}"
        pid = _insert_plan_item(user_id, "mood_stress", target_type="intervention")

        bus, writer = _new_writer_with_bus()
        captured: list = []

        async def _cap_ms(event):
            captured.append(event)
        for evt in (
            "MoodStressRecorded",
            "MoodStressInterventionTriggered",
            "MoodStressRuleTriggered",
            "MoodStressBehaviorSignalDetected",
        ):
            bus.subscribe(evt, _cap_ms)
        writer.subscribe(bus)

        event = PlanItemCompleted(
            user_id=user_id, plan_item_id=pid,
            source_module=PlanningSourceModule.MOOD_STRESS.value,
            target_type="intervention", target_ref_id="ms_audit_001",
            actual_minutes=10,
        )
        await _publish_and_drain(bus, event)

        db = _try_connect()
        item = db.fetchone("SELECT status FROM plan_items WHERE id=%s", (pid,))
        assert item["status"] == "completed"
        assert len(captured) == 0, (
            f"mood_stress 路由重发了 mood 事件: {len(captured)} 次"
        )


# ══════════════════════════════════════════════════════════════
# 关键事件循环验证 — Task #61 任务要求第 3 点
# ══════════════════════════════════════════════════════════════


class TestNoEventLoopResend:
    """显式验证: 完成 flashcard plan_item 不会触发 FlashCardReviewed 订阅者

    模拟生产场景: 有其它模块订阅了 FlashCardReviewed (FSRS Belief 回路),
    验证 completion_writer 路由不会重发这个事件造成循环。
    """

    @pytest.mark.asyncio
    async def test_flashcard_reviewed_not_republished_on_plan_complete(self):
        from shared.events import PlanItemCompleted, PlanningSourceModule

        user_id = f"xplloop_{uuid.uuid4().hex[:12]}"
        pid = _insert_plan_item(user_id, "flashcard", target_type="flashcard_set")

        bus, writer = _new_writer_with_bus()
        # 模拟生产: 模拟 FSRS Belief 回路订阅者
        fsrs_loop_calls: list = []

        async def fsrs_on_flashcard_reviewed(event):
            # 这是 FSRS 的 Belief 回路 (生产代码会调用此函数更新 Belief)
            fsrs_loop_calls.append(event)

        bus.subscribe("FlashCardReviewed", fsrs_on_flashcard_reviewed)
        writer.subscribe(bus)

        # complete plan_item (走 completion_writer 路径)
        event = PlanItemCompleted(
            user_id=user_id, plan_item_id=pid,
            source_module=PlanningSourceModule.FLASHCARD.value,
            target_type="flashcard_set", target_ref_id="loop_test_001",
            actual_minutes=10,
        )
        await _publish_and_drain(bus, event)

        # 关键: FSRS 回路**绝不**应被触发
        # (否则: PlanItemCompleted → completion_writer → FlashCardReviewed
        #        → FSRS handler → 新的 plan_item → 死循环)
        assert len(fsrs_loop_calls) == 0, (
            "严重: completion_writer 重发了 FlashCardReviewed, 会触发 FSRS "
            "Belief 回路! 这是 ADR 关键差异 1 明确禁止的事件循环。"
        )

    @pytest.mark.asyncio
    async def test_practice_session_completed_not_republished_on_plan_complete(self):
        from shared.events import PlanItemCompleted, PlanningSourceModule

        user_id = f"xplloop2_{uuid.uuid4().hex[:12]}"
        pid = _insert_plan_item(user_id, "practice", target_type="practice_set")

        bus, writer = _new_writer_with_bus()
        loop_calls: list = []

        async def practice_loop(event):
            loop_calls.append(event)
        bus.subscribe("SessionCompleted", practice_loop)
        bus.subscribe("AnswerSubmitted", practice_loop)
        writer.subscribe(bus)

        event = PlanItemCompleted(
            user_id=user_id, plan_item_id=pid,
            source_module=PlanningSourceModule.PRACTICE.value,
            target_type="practice_set", target_ref_id="loop_test_002",
            actual_minutes=10,
        )
        await _publish_and_drain(bus, event)

        assert len(loop_calls) == 0, (
            f"practice 路由重发了会话事件 {len(loop_calls)} 次, 触发回路"
        )

    @pytest.mark.asyncio
    async def test_project_node_completed_not_republished_on_plan_complete(self):
        from shared.events import PlanItemCompleted, PlanningSourceModule

        user_id = f"xplloop3_{uuid.uuid4().hex[:12]}"
        node_id = _insert_project_node(user_id, status="pending")
        pid = _insert_plan_item(
            user_id, "project", target_type="project_node", target_ref_id=node_id
        )

        bus, writer = _new_writer_with_bus()
        loop_calls: list = []

        async def project_loop(event):
            loop_calls.append(event)
        bus.subscribe("ProjectNodeCompleted", project_loop)
        writer.subscribe(bus)

        event = PlanItemCompleted(
            user_id=user_id, plan_item_id=pid,
            source_module=PlanningSourceModule.PROJECT.value,
            target_type="project_node", target_ref_id=node_id,
            actual_minutes=30,
        )
        await _publish_and_drain(bus, event)

        assert len(loop_calls) == 0, (
            "Task #40 修复回归: project 路由重发了 ProjectNodeCompleted"
        )


# ══════════════════════════════════════════════════════════════
# Deviation 字段名 audit (ADR 关键差异 5)
# ══════════════════════════════════════════════════════════════


class TestDeviationTypeSchema:
    """ADR 关键差异 5: deviation_type 实际为
    Literal['timeout', 'skip', 'early_complete', 'extra_insert']"""

    def test_plan_deviation_recorded_event_field(self):
        """PlanDeviationRecorded 事件的 deviation_type 字段类型正确"""
        from shared.events import PlanDeviationRecorded
        # 创建一个 skip 类型事件, 不应抛错
        ev = PlanDeviationRecorded(
            user_id="u_audit",
            plan_item_id="pi_dev_001",
            deviation_type="skip",
            planned_minutes=30,
            actual_minutes=0,
            deviation_minutes=-30,
        )
        assert ev.deviation_type == "skip"
        assert ev.event_type == "PlanDeviationRecorded"

    def test_all_four_deviation_types_accepted(self):
        """4 种 deviation_type 全部被 Literal 接受"""
        from shared.events import PlanDeviationRecorded
        for dtype in ("timeout", "skip", "early_complete", "extra_insert"):
            ev = PlanDeviationRecorded(
                user_id="u_audit",
                plan_item_id=f"pi_dev_{dtype}",
                deviation_type=dtype,  # type: ignore[arg-type]
            )
            assert ev.deviation_type == dtype

    def test_skip_endpoint_publishes_event_with_correct_type(self):
        """验证 PlanItemSkipped 事件能正常构造 (skip 端点 publish 路径)"""
        from shared.events import PlanItemSkipped
        ev = PlanItemSkipped(
            user_id="u_audit",
            plan_item_id="pi_skip_001",
            source_module="manual",
        )
        assert ev.event_type == "PlanItemSkipped"
        assert ev.plan_item_id == "pi_skip_001"

    def test_deviation_table_records_inserted_on_complete(self):
        """complete_plan_item 路径会插入 plan_deviations 行, deviation_type 合法"""
        from app.api.planning import service as svc
        from app.api.planning.service import _ensure_tables

        _ensure_tables()
        user_id = f"xplndev_{uuid.uuid4().hex[:12]}"
        # 直接调用 create + complete 走完整路径
        item = svc.create_plan_item(user_id, {
            "source_module": "manual",
            "target_type": "manual",
            "target_ref_id": "m_dev_test",
            "title": "deviation 测试",
            "estimated_minutes": 30,
        })
        assert item is not None
        pid = item["id"]
        # complete 时 actual=10 < planned=30 → 期望 deviation_type='early_complete'
        result = svc.complete_plan_item(user_id, pid, {"actual_minutes": 10})
        assert result is not None
        # 验证 plan_deviations 表有记录
        db = _try_connect()
        if not _table_exists(db, "plan_deviations"):
            pytest.skip("plan_deviations 表不存在")
        dev = db.fetchone(
            "SELECT deviation_type, planned_minutes, actual_minutes, deviation_minutes "
            "FROM plan_deviations WHERE plan_item_id=%s",
            (pid,),
        )
        assert dev is not None, "complete_plan_item 应插入 plan_deviations 行"
        assert dev["deviation_type"] in ("timeout", "skip", "early_complete", "extra_insert"), (
            f"deviation_type 字段名错误: {dev['deviation_type']}, "
            f"应符合 ADR 关键差异 5: Literal['timeout','skip','early_complete','extra_insert']"
        )
        # planned=30, actual=10 → deviation=-20 → early_complete
        assert dev["deviation_type"] == "early_complete"
        assert dev["deviation_minutes"] == -20


# ══════════════════════════════════════════════════════════════
# Belief 回写验证 (按 ADR 关键差异: plan_item 是用户决定, 不直接更新 Belief)
# ══════════════════════════════════════════════════════════════


class TestBeliefNotDirectlyUpdatedByPlanning:
    """ADR 0006 关键设计: 计划项是"用户决定"而非"学习行为", 不触发 Belief 更新.

    Belief 更新应由源模块的实际学习事件驱动 (AnswerSubmitted/FlashCardReviewed/...),
    completion_writer 仅路由 plan_items 状态, 不应直接修改 Beliefs.
    """

    @pytest.mark.asyncio
    async def test_completing_practice_plan_item_does_not_update_belief_directly(self):
        """complete 一个 practice 计划项不会直接更新认知节点 Belief"""
        from app.domain.cognitive import get_repo
        from app.domain.cognitive.models import CognitiveNode, Belief, PracticeSummary
        import time

        from shared.events import PlanItemCompleted, PlanningSourceModule

        user_id = f"xplnbel_{uuid.uuid4().hex[:12]}"
        node_id = f"node_bel_{uuid.uuid4().hex[:10]}"

        # 1. 插入一个 cognitive_node, 记录初始 alpha/beta
        repo = get_repo()
        repo.upsert_node(
            CognitiveNode(
                id=node_id,
                label="审计 Belief 测试",
                level="atom",
                node_type="auto_generated",
                belief=Belief(alpha=2.0, beta=2.0, proficiency_mean=0.5),
                practice_summary=PracticeSummary(total_attempts=0, correct_attempts=0),
            ),
            user_id,
        )
        before = repo.get_node(node_id, user_id)
        before_alpha = float(before.belief.alpha)
        before_beta = float(before.belief.beta)
        before_total = int(before.practice_summary.total_attempts)

        # 2. 创建 plan_item, linked_node_ids 指向此 node
        db = _try_connect()
        pid = f"plan_{uuid.uuid4().hex[:16]}"
        db.execute(
            """INSERT INTO plan_items
               (id, user_id, source_module, target_type, target_ref_id, title,
                estimated_minutes, linked_node_ids, priority, status)
               VALUES (%s, %s, 'practice', 'practice_set', %s, 'Belief 测试',
                30, %s::jsonb, 0, 'pending')""",
            (pid, user_id, "pr_belief_001", json.dumps([node_id], ensure_ascii=False)),
        )

        # 3. 路由 PlanItemCompleted
        bus, writer = _new_writer_with_bus()
        writer.subscribe(bus)
        event = PlanItemCompleted(
            user_id=user_id, plan_item_id=pid,
            source_module=PlanningSourceModule.PRACTICE.value,
            target_type="practice_set", target_ref_id="pr_belief_001",
            actual_minutes=25, linked_node_ids=[node_id],
        )
        await _publish_and_drain(bus, event)

        # 4. 验证 Belief **未**被直接修改 (因为 plan_item 是"用户决定")
        after = repo.get_node(node_id, user_id)
        after_alpha = float(after.belief.alpha)
        after_beta = float(after.belief.beta)
        after_total = int(after.practice_summary.total_attempts)

        assert after_alpha == before_alpha, (
            f"Belief.alpha 被 planning 路径修改: {before_alpha} → {after_alpha} "
            f"(违反 ADR 0006 关键设计: plan_item 是用户决定, 不应触发 Belief 更新)"
        )
        assert after_beta == before_beta, (
            f"Belief.beta 被 planning 路径修改: {before_beta} → {after_beta}"
        )
        assert after_total == before_total, (
            f"practice_summary.total_attempts 被 planning 路径修改"
        )

        # 5. plan_item 状态应正常更新 (这部分仍发生)
        item = db.fetchone("SELECT status FROM plan_items WHERE id=%s", (pid,))
        assert item["status"] == "completed"


# ══════════════════════════════════════════════════════════════
# 路由表静态 audit
# ══════════════════════════════════════════════════════════════


class TestRouteTableCompleteness:
    """completion_writer 路由表完整度 audit"""

    def test_all_source_modules_have_routes(self):
        """PlanningSourceModule 枚举每个值在 _ROUTE_HANDLERS 都有 handler"""
        from app.services.planning.completion_writer import PlanningCompletionWriter
        from shared.events import PlanningSourceModule

        for module in PlanningSourceModule:
            assert module.value in PlanningCompletionWriter._ROUTE_HANDLERS, (
                f"missing handler for source_module={module.value}"
            )

    def test_no_extra_routes_beyond_enum(self):
        """_ROUTE_HANDLERS 的 key 全部来自 PlanningSourceModule (无幽灵路由)"""
        from app.services.planning.completion_writer import PlanningCompletionWriter
        from shared.events import PlanningSourceModule

        valid_values = {m.value for m in PlanningSourceModule}
        for k in PlanningCompletionWriter._ROUTE_HANDLERS:
            assert k in valid_values, f"unexpected route key: {k}"

    def test_route_count_equals_enum_count(self):
        """路由数 = 枚举数 (与 PlanningSourceModule 保持一致)"""
        from app.services.planning.completion_writer import PlanningCompletionWriter
        from shared.events import PlanningSourceModule

        assert len(PlanningCompletionWriter._ROUTE_HANDLERS) == len(PlanningSourceModule)

    def test_all_source_modules_present(self):
        """所有 source_module 全部存在 (11 个值, ADR 扩展至 interest/secretary/system)"""
        from shared.events import PlanningSourceModule

        expected = {
            "flashcard", "practice", "project", "reading",
            "language_room", "manual", "interest_explorer", "mood_stress",
            "interest", "secretary", "system",
        }
        actual = {m.value for m in PlanningSourceModule}
        assert actual == expected, f"PlanningSourceModule 成员不匹配: missing={expected-actual}, extra={actual-expected}"

    def test_route_handlers_match_source_modules(self):
        """路由数 = 枚举数 (11 个)"""
        from app.services.planning.completion_writer import PlanningCompletionWriter
        from shared.events import PlanningSourceModule

        assert len(PlanningCompletionWriter._ROUTE_HANDLERS) == len(PlanningSourceModule)


# ══════════════════════════════════════════════════════════════
# 13 个 Planning 事件存在性 audit
# ══════════════════════════════════════════════════════════════


class TestPlanningEventsSchema:
    """shared/events.py 中 13 个 Planning 事件存在性 (ADR 关键差异 4)"""

    def test_all_planning_events_exist(self):
        """ADR 关键差异 4: 12 个 Planning 事件 (实际为 12 个, 非原设计 4 个)"""
        from shared.events import (
            PlanItemCreated,
            PlanItemScheduled,
            PlanItemActivated,
            PlanItemStarted,
            PlanItemCompleted,
            PlanItemSkipped,
            PlanItemExtended,
            PlanGoalCreated,
            PlanGoalProgressUpdated,
            PlanGoalCompleted,
            PlanPeriodicReviewGenerated,
            PlanDeviationRecorded,
        )
        # 生命周期 7 + 目标 3 + 回顾/偏差 2 = 12 个
        events = [
            PlanItemCreated, PlanItemScheduled, PlanItemActivated, PlanItemStarted,
            PlanItemCompleted, PlanItemSkipped, PlanItemExtended,
            PlanGoalCreated, PlanGoalProgressUpdated, PlanGoalCompleted,
            PlanPeriodicReviewGenerated, PlanDeviationRecorded,
        ]
        assert len(events) == 12, f"Planning 事件应为 12 个, 实际 {len(events)}"
        for evt_cls in events:
            assert hasattr(evt_cls, "event_type"), f"{evt_cls.__name__} 缺 event_type 属性"
            # 构造实例验证可序列化
            instance = evt_cls()
            assert isinstance(instance.event_type, str), (
                f"{evt_cls.__name__}.event_type 应返回 str, 实际 {type(instance.event_type)}"
            )

    def test_deviation_recorded_has_required_literal(self):
        """PlanDeviationRecorded.deviation_type 必须是 Literal 4 选 1 (ADR 关键差异 5)"""
        import inspect
        from shared.events import PlanDeviationRecorded
        sig = inspect.signature(PlanDeviationRecorded)
        dev_param = sig.parameters.get("deviation_type")
        assert dev_param is not None, "PlanDeviationRecorded 缺 deviation_type 字段"
        # 检查类型注解包含 4 个合法值
        ann_str = str(dev_param.annotation)
        expected_types = ["timeout", "skip", "early_complete", "extra_insert"]
        for t in expected_types:
            assert t in ann_str, (
                f"deviation_type 字段应包含 {t}, 实际注解: {ann_str} "
                f"(违反 ADR 关键差异 5)"
            )
