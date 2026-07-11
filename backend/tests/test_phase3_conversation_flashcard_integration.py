"""
Phase 3 测试 — 对话笔记 ↔ 闪卡双向同步 + 答题微行为遥测 + 诊断信号

验收范围:
  1. conversation_note_service CRUD
  2. ConversationNoteCreatedAsFlashcard → 闪卡创建 + flashcard_id 回填
  3. FlashCardUpdated → 反向同步内容回 conversation_notes
  4. telemetry_service 保存遥测 + 发布 PracticeAnswerBehaviorRecorded
  5. diagnostic_signal_builder 生成诊断信号并落库
  6. secretary_event_handler 对两种事件生成提案
"""

from __future__ import annotations

import asyncio
import os
import sys
import time
import uuid
from typing import Any
from unittest.mock import MagicMock

import pytest

BACKEND = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BACKEND not in sys.path:
    sys.path.insert(0, str(BACKEND))


# ═══════════════════════════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════════════════════════


def _try_connect():
    try:
        from app.infrastructure.db.database import get_db
        d = get_db()
        d.fetchone("SELECT 1")
        return d
    except Exception as exc:  # noqa: BLE001
        pytest.skip(f"数据库不可用: {exc}")


@pytest.fixture
def user_id() -> str:
    return f"p3_{uuid.uuid4().hex[:12]}"


@pytest.fixture
def db():
    return _try_connect()


@pytest.fixture
def clean_bus(monkeypatch):
    """提供隔离 EventBus，并替换 container.event_bus，避免污染全局处理器。"""
    from app.infrastructure.event_bus import EventBus
    from app.application.di import container

    bus = EventBus(handler_timeout=2.0)
    monkeypatch.setattr(container, "event_bus", bus)
    return bus


@pytest.fixture
def cleanup_test_data(db, user_id):
    """测试结束后清理本测试产生的数据。"""
    yield
    for tbl in (
        "diagnostic_signals",
        "answer_telemetry",
        "conversation_notes",
        "flashcards",
    ):
        try:
            db.execute(f"DELETE FROM {tbl} WHERE user_id = %s", (user_id,))
        except Exception:
            pass


def _table_exists(db, table_name: str) -> bool:
    row = db.fetchone(
        "SELECT 1 FROM information_schema.tables WHERE table_name = %s LIMIT 1",
        (table_name,),
    )
    return row is not None


def _ensure_phase3_tables(db):
    """确保 flashcards、conversation_notes、answer_telemetry、diagnostic_signals 表存在。"""
    from app.api.flashcard.service import _ensure_tables as _ensure_flashcard_tables
    _ensure_flashcard_tables()
    for tbl in ("conversation_notes", "answer_telemetry", "diagnostic_signals"):
        if not _table_exists(db, tbl):
            pytest.skip(f"{tbl} 表不存在，请先执行 alembic upgrade head")


# ═══════════════════════════════════════════════════════════════════
# §1. Conversation Note CRUD
# ═══════════════════════════════════════════════════════════════════


class TestConversationNoteCrud:
    """对话笔记服务基础 CRUD"""

    def test_create_note_requires_front_text(self, db, user_id):
        from app.services.conversation.conversation_note_service import create_note
        with pytest.raises(ValueError, match="front_text"):
            create_note(user_id=user_id, conv_id="c1", source_message_id="m1", front_text="")

    def test_create_note_returns_note_with_source_ref(self, db, user_id, clean_bus, cleanup_test_data):
        _ensure_phase3_tables(db)
        from app.services.conversation.conversation_note_service import create_note

        note = create_note(
            user_id=user_id,
            conv_id="conv_1",
            source_message_id="msg_1",
            front_text="什么是导数？",
            back_text="变化率",
            linked_node_ids=["node_1"],
            tags=["微积分"],
            auto_create_flashcard=False,
        )

        assert note["front_text"] == "什么是导数？"
        assert note["back_text"] == "变化率"
        assert note["conv_id"] == "conv_1"
        assert note["source_message_id"] == "msg_1"
        assert note["linked_node_ids"] == ["node_1"]
        assert note["tags"] == ["微积分"]
        assert note["status"] == "draft"
        assert note["source_ref"]["module"] == "conversation"
        assert note["source_ref"]["metadata"]["note_id"] == note["id"]

    def test_update_note_bumps_field_versions(self, db, user_id, clean_bus, cleanup_test_data):
        _ensure_phase3_tables(db)
        from app.services.conversation.conversation_note_service import create_note, update_note

        note = create_note(
            user_id=user_id,
            conv_id="conv_1",
            source_message_id="msg_1",
            front_text="原始问题",
            auto_create_flashcard=False,
        )
        updated = update_note(
            user_id=user_id,
            note_id=note["id"],
            front_text="更新后问题",
            back_text="答案",
        )
        assert updated["front_text"] == "更新后问题"
        assert updated["back_text"] == "答案"
        assert updated["field_versions"].get("front_text") == 1
        assert updated["field_versions"].get("back_text") == 1

    def test_delete_note_removes_row(self, db, user_id, clean_bus, cleanup_test_data):
        _ensure_phase3_tables(db)
        from app.services.conversation.conversation_note_service import create_note, delete_note, get_note

        note = create_note(
            user_id=user_id,
            conv_id="conv_1",
            source_message_id="msg_1",
            front_text="待删除",
            auto_create_flashcard=False,
        )
        assert delete_note(user_id=user_id, note_id=note["id"]) is True
        assert get_note(user_id=user_id, note_id=note["id"]) is None

    def test_list_notes_by_conv(self, db, user_id, clean_bus, cleanup_test_data):
        _ensure_phase3_tables(db)
        from app.services.conversation.conversation_note_service import create_note, list_notes_by_conv

        create_note(user_id=user_id, conv_id="conv_a", source_message_id="m1", front_text="A", auto_create_flashcard=False)
        create_note(user_id=user_id, conv_id="conv_a", source_message_id="m2", front_text="B", auto_create_flashcard=False)
        create_note(user_id=user_id, conv_id="conv_b", source_message_id="m3", front_text="C", auto_create_flashcard=False)

        notes = list_notes_by_conv(user_id=user_id, conv_id="conv_a")
        assert len(notes) == 2
        assert [n["front_text"] for n in notes] == ["B", "A"]


# ═══════════════════════════════════════════════════════════════════
# §2. ConversationNote → FlashCard
# ═══════════════════════════════════════════════════════════════════


class TestConversationNoteToFlashcard:
    """对话笔记创建时自动发布事件，闪卡处理器创建闪卡并回填 ID"""

    def test_note_created_event_creates_flashcard_and_backfills_id(
        self, db, user_id, clean_bus, cleanup_test_data
    ):
        _ensure_phase3_tables(db)
        from app.services.conversation.conversation_note_service import create_note, get_note
        from app.services.flashcard.conversation_note_handler import ConversationNoteFlashcardHandler

        # 使用新实例避免全局单例 _subscribed 状态导致无法订阅到 clean_bus
        handler = ConversationNoteFlashcardHandler()
        handler.subscribe(clean_bus)

        # 同步测试上下文下 publish_event_safe 退化到 asyncio.run，handler 完成后才返回
        note = create_note(
            user_id=user_id,
            conv_id="conv_1",
            source_message_id="msg_1",
            front_text="对话中的问题？",
            back_text="答案",
            linked_node_ids=["node_1"],
            tags=["对话笔记"],
            auto_create_flashcard=True,
        )

        refreshed = get_note(user_id=user_id, note_id=note["id"])
        assert refreshed["status"] == "synced"
        assert refreshed["flashcard_id"] is not None
        assert refreshed["flashcard_id"].startswith("fc_")

        # 验证闪卡已创建
        row = db.fetchone(
            "SELECT id, source, type, front_text, back_text, linked_node_ids, tags, source_ref "
            "FROM flashcards WHERE id = %s AND user_id = %s",
            (refreshed["flashcard_id"], user_id),
        )
        assert row is not None
        assert row["source"] == "conversation"
        assert row["type"] == 7
        assert row["front_text"] == "对话中的问题？"

        handler.unsubscribe()

    def test_auto_create_flashcard_false_does_not_backfill(self, db, user_id, clean_bus, cleanup_test_data):
        _ensure_phase3_tables(db)
        from app.services.conversation.conversation_note_service import create_note

        note = create_note(
            user_id=user_id,
            conv_id="conv_1",
            source_message_id="msg_1",
            front_text="仅笔记",
            auto_create_flashcard=False,
        )
        assert note["flashcard_id"] is None
        assert note["status"] == "draft"


# ═══════════════════════════════════════════════════════════════════
# §3. FlashCardUpdated → ConversationNote reverse sync
# ═══════════════════════════════════════════════════════════════════


class TestFlashcardToConversationNoteReverseSync:
    """闪卡内容更新后，反向同步回对话笔记"""

    @pytest.mark.asyncio
    async def test_flashcard_update_syncs_content_fields_back_to_note(
        self, db, user_id, clean_bus, cleanup_test_data
    ):
        _ensure_phase3_tables(db)
        from app.services.conversation.conversation_note_service import create_note, on_flashcard_updated
        from app.api.flashcard.service import FlashCardService

        # 1. 创建笔记并手动设置 flashcard_id（模拟事件已处理）
        note = create_note(
            user_id=user_id,
            conv_id="conv_1",
            source_message_id="msg_1",
            front_text="原始问题",
            back_text="原始答案",
            auto_create_flashcard=False,
        )

        svc = FlashCardService(event_bus=clean_bus)
        card = svc.create_card(user_id, {
            "front_text": "原始问题",
            "back_text": "原始答案",
            "source": "conversation",
            "cross_module_source": "conversation",
        })

        # 手动关联
        from app.services.conversation.conversation_note_service import link_flashcard
        link_flashcard(user_id, note["id"], card["id"])

        # 2. 更新闪卡内容字段
        svc.update_card(user_id, card["id"], {
            "front_text": "更新后问题",
            "back_text": "更新后答案",
            "tags": ["新标签"],
        })

        # 3. 构造 FlashCardUpdated 事件调用反向同步 handler
        from shared.events import FlashCardUpdated
        event = FlashCardUpdated(
            user_id=user_id,
            card_id=card["id"],
            changed_fields=["front_text", "back_text", "tags"],
            updated_at=svc.get_card(user_id, card["id"])["updated_at"],
        )
        await on_flashcard_updated(event)

        # 4. 验证笔记已被更新
        from app.services.conversation.conversation_note_service import get_note
        refreshed = get_note(user_id=user_id, note_id=note["id"])
        assert refreshed["front_text"] == "更新后问题"
        assert refreshed["back_text"] == "更新后答案"
        assert refreshed["field_versions"].get("front_text") >= 1
        assert refreshed["field_versions"].get("back_text") >= 1

    @pytest.mark.asyncio
    async def test_reverse_sync_skips_when_note_is_newer(
        self, db, user_id, clean_bus, cleanup_test_data
    ):
        _ensure_phase3_tables(db)
        from app.services.conversation.conversation_note_service import create_note, on_flashcard_updated
        from app.api.flashcard.service import FlashCardService
        from shared.events import FlashCardUpdated
        from datetime import datetime, timezone, timedelta

        note = create_note(
            user_id=user_id,
            conv_id="conv_1",
            source_message_id="msg_1",
            front_text="笔记侧",
            auto_create_flashcard=False,
        )
        svc = FlashCardService(event_bus=clean_bus)
        card = svc.create_card(user_id, {"front_text": "闪卡侧", "source": "conversation"})
        from app.services.conversation.conversation_note_service import link_flashcard
        link_flashcard(user_id, note["id"], card["id"])

        # 模拟一个发生在笔记创建之前的闪卡更新事件
        old_time = datetime.now(timezone.utc) - timedelta(hours=1)
        event = FlashCardUpdated(
            user_id=user_id,
            card_id=card["id"],
            changed_fields=["front_text"],
            updated_at=old_time,
        )
        await on_flashcard_updated(event)

        from app.services.conversation.conversation_note_service import get_note
        refreshed = get_note(user_id=user_id, note_id=note["id"])
        assert refreshed["front_text"] == "笔记侧"


# ═══════════════════════════════════════════════════════════════════
# §4. Answer Telemetry
# ═══════════════════════════════════════════════════════════════════


class TestAnswerTelemetry:
    """答题微行为遥测落库与事件发布"""

    def test_save_telemetry_persists_and_publishes_event(
        self, db, user_id, clean_bus, cleanup_test_data
    ):
        _ensure_phase3_tables(db)
        from app.services.practice.telemetry_service import save_telemetry, get_telemetry_by_attempt
        from shared.events import PracticeAnswerBehaviorRecorded

        captured: list[Any] = []

        async def _capture(event):
            captured.append(event)

        clean_bus.subscribe("PracticeAnswerBehaviorRecorded", _capture)

        telemetry_id = f"tel_{uuid.uuid4().hex[:12]}"
        attempt_id = f"att_{uuid.uuid4().hex[:12]}"
        derived = {
            "time_on_question_ms": 12000,
            "hesitation_ms": 5000,
            "answer_change_count": 2,
            "total_hover_ms": 8000,
            "avg_text_pause_ms": 1200,
            "hint_count": 1,
        }

        result = save_telemetry(
            user_id=user_id,
            telemetry_id=telemetry_id,
            session_id="sess_1",
            question_id="q_1",
            attempt_id=attempt_id,
            raw_events=[{"type": "hover", "ts": 0, "duration_ms": 2000}],
            derived=derived,
        )

        # 验证落库
        assert result["telemetry_id"] == telemetry_id
        row = get_telemetry_by_attempt(attempt_id)
        assert row is not None
        assert row["derived"]["time_on_question_ms"] == 12000
        assert len(row["raw_events"]) == 1

        # 验证事件
        time.sleep(0.1)
        assert len(captured) == 1
        event = captured[0]
        assert isinstance(event, PracticeAnswerBehaviorRecorded)
        assert event.user_id == user_id
        assert event.attempt_id == attempt_id
        assert event.time_on_question_ms == 12000
        assert event.hesitation_ms == 5000

    def test_save_telemetry_idempotent(self, db, user_id, clean_bus, cleanup_test_data):
        _ensure_phase3_tables(db)
        from app.services.practice.telemetry_service import save_telemetry, get_telemetry_by_attempt

        telemetry_id = f"tel_{uuid.uuid4().hex[:12]}"
        attempt_id = f"att_{uuid.uuid4().hex[:12]}"

        save_telemetry(
            user_id=user_id,
            telemetry_id=telemetry_id,
            session_id="sess_1",
            question_id="q_1",
            attempt_id=attempt_id,
            raw_events=[{"type": "hover"}],
            derived={"time_on_question_ms": 1000},
        )
        save_telemetry(
            user_id=user_id,
            telemetry_id=telemetry_id,
            session_id="sess_1",
            question_id="q_1",
            attempt_id=attempt_id,
            raw_events=[{"type": "hover"}, {"type": "select"}],
            derived={"time_on_question_ms": 2000},
        )

        row = get_telemetry_by_attempt(attempt_id)
        assert row["derived"]["time_on_question_ms"] == 2000
        assert len(row["raw_events"]) == 2

    def test_save_telemetry_validates_required_fields(self, db, user_id, clean_bus):
        from app.services.practice.telemetry_service import save_telemetry
        with pytest.raises(ValueError, match="不能为空"):
            save_telemetry(user_id=user_id, telemetry_id="", session_id="", question_id="q", attempt_id="a", raw_events=[], derived={})


# ═══════════════════════════════════════════════════════════════════
# §5. Diagnostic Signal Builder
# ═══════════════════════════════════════════════════════════════════


class TestDiagnosticSignalBuilder:
    """由 PracticeAnswerBehaviorRecorded 生成诊断信号"""

    def test_build_diagnostic_signal_detects_hesitation(self):
        from app.domain.cognitive.diagnostic_signal_builder import build_diagnostic_signal
        from shared.events import PracticeAnswerBehaviorRecorded

        event = PracticeAnswerBehaviorRecorded(
            user_id="u1",
            telemetry_id="t1",
            attempt_id="a1",
            question_id="q1",
            time_on_question_ms=12000,
            hesitation_ms=6000,
            answer_change_count=0,
            total_hover_ms=2000,
            avg_text_pause_ms=500,
            hint_count=0,
        )
        signal = build_diagnostic_signal(event)
        assert signal["suggested_action"] == "review"
        assert signal["signals"]["hesitation_ratio"] == 0.5
        assert "犹豫" in signal["interpretation"]

    def test_build_diagnostic_signal_detects_indecision(self):
        from app.domain.cognitive.diagnostic_signal_builder import build_diagnostic_signal
        from shared.events import PracticeAnswerBehaviorRecorded

        event = PracticeAnswerBehaviorRecorded(
            user_id="u1",
            telemetry_id="t1",
            attempt_id="a1",
            question_id="q1",
            time_on_question_ms=3000,
            hesitation_ms=200,
            answer_change_count=3,
            total_hover_ms=1000,
            avg_text_pause_ms=200,
            hint_count=0,
        )
        signal = build_diagnostic_signal(event)
        assert signal["suggested_action"] == "explain"
        assert "多次改选" in signal["interpretation"]

    def test_builder_persists_signal_via_event_handler(
        self, db, user_id, clean_bus, cleanup_test_data
    ):
        _ensure_phase3_tables(db)
        from app.domain.cognitive.diagnostic_signal_builder import diagnostic_signal_builder
        from shared.events import PracticeAnswerBehaviorRecorded

        diagnostic_signal_builder.subscribe(clean_bus)

        event = PracticeAnswerBehaviorRecorded(
            user_id=user_id,
            telemetry_id=f"tel_{uuid.uuid4().hex[:12]}",
            attempt_id=f"att_{uuid.uuid4().hex[:12]}",
            question_id="q1",
            time_on_question_ms=15000,
            hesitation_ms=7000,
            answer_change_count=1,
            total_hover_ms=3000,
            avg_text_pause_ms=800,
            hint_count=1,
        )
        asyncio.run(clean_bus.publish(event))

        row = db.fetchone(
            "SELECT * FROM diagnostic_signals WHERE attempt_id = %s AND user_id = %s",
            (event.attempt_id, user_id),
        )
        assert row is not None
        assert row["suggested_action"] == "review"
        assert row["signals"]["hesitation_ratio"] > 0.4

        diagnostic_signal_builder.unsubscribe()


# ═══════════════════════════════════════════════════════════════════
# §6. Secretary Event Handler Proposals
# ═══════════════════════════════════════════════════════════════════


class TestSecretaryEventHandlerPhase3:
    """秘书对 Phase 3 新事件生成提案"""

    @pytest.mark.asyncio
    async def test_conversation_note_created_as_flashcard_generates_planning_proposal(
        self, clean_bus
    ):
        from app.domain.secretary.engines.secretary_event_handler import SecretaryEventHandler
        from shared.events import ConversationNoteCreatedAsFlashcard

        mock_store = MagicMock()
        handler = SecretaryEventHandler(store=mock_store)
        handler.subscribe(clean_bus)

        event = ConversationNoteCreatedAsFlashcard(
            user_id="u1",
            conv_id="c1",
            note_id="note_1",
            source_message_id="m1",
            front_text="重要概念",
            back_text="解释",
        )
        await clean_bus.publish(event)

        assert mock_store.save_proposal.called
        call_args = mock_store.save_proposal.call_args
        proposal = call_args.args[0]
        assert proposal.action_type == "planning"
        assert "闪卡" in proposal.title
        assert call_args.kwargs["user_id"] == "u1"

    @pytest.mark.asyncio
    async def test_practice_behavior_recorded_generates_review_proposal(
        self, clean_bus
    ):
        from app.domain.secretary.engines.secretary_event_handler import SecretaryEventHandler
        from shared.events import PracticeAnswerBehaviorRecorded

        mock_store = MagicMock()
        handler = SecretaryEventHandler(store=mock_store)
        handler.subscribe(clean_bus)

        event = PracticeAnswerBehaviorRecorded(
            user_id="u1",
            telemetry_id="t1",
            attempt_id="a1",
            question_id="q1",
            time_on_question_ms=12000,
            hesitation_ms=6000,
            answer_change_count=0,
            total_hover_ms=1000,
            avg_text_pause_ms=300,
            hint_count=0,
        )
        await clean_bus.publish(event)

        calls = mock_store.save_proposal.call_args_list
        assert any(call.args[0].action_type == "review" for call in calls)

    @pytest.mark.asyncio
    async def test_practice_behavior_recorded_generates_practice_proposal_on_many_changes(
        self, clean_bus
    ):
        from app.domain.secretary.engines.secretary_event_handler import SecretaryEventHandler
        from shared.events import PracticeAnswerBehaviorRecorded

        mock_store = MagicMock()
        handler = SecretaryEventHandler(store=mock_store)
        handler.subscribe(clean_bus)

        event = PracticeAnswerBehaviorRecorded(
            user_id="u1",
            telemetry_id="t1",
            attempt_id="a1",
            question_id="q1",
            time_on_question_ms=3000,
            hesitation_ms=200,
            answer_change_count=3,
            total_hover_ms=1000,
            avg_text_pause_ms=200,
            hint_count=0,
        )
        await clean_bus.publish(event)

        calls = mock_store.save_proposal.call_args_list
        assert any(call.args[0].action_type == "practice" for call in calls)
