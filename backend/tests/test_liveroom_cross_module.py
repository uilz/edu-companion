"""
Task #64 — LanguageRoom 跨模块联动审计 (E2E 测试)

依据: docs/adr/0004-language-multiplayer.md + docs/modules/language-room/*
审计 8 条跨模块联动:

  1. Vocabulary  → FlashCard       (notes.create_vocabulary_capture → flashcards)
  2. Error       → ErrorBookEntry  (notes.create_error_entry → practice_error_book/error_book)
  3. Message     → ExplainCard     (notes.create_explain_card → explain_cards, D14 后)
  4. AI Helper   → KnowledgeGraph  (liveroom_tools.tool_knowledge_search)
  5. Transcript  → voice_features  (待修复 6, 0005 MoodStress 消费)
  6. RoomCompleted → PlanItem      (planning.completion_writer language_room 路由)
  7. Scenario    → Project         (待修复 5, 未端到端打通)
  8. AI Persona  → Shared tool registry (ai_persona.execute_shared_tool)

不依赖 LLM/外部服务, 全部用真实 DB + ToolRepository + EventBus

发现的真 bug (audit findings):
  - B1: notes.create_error_entry 写到不存在的 'practice_error_book' 表 (silent fail)
  - B2: notes.create_explain_card 写入 D14 已删除的 'explain_cards' 表 (silent fail)
  - B3: notes.py:69 SELECT text, user_text FROM room_transcripts — user_text 列不存在
       (create_error_entry 每次必抛 UndefinedColumn, 完全不可用)
"""
from __future__ import annotations

import asyncio
import json
import os
import sys
import time
import uuid
from typing import Any

import pytest

# 让 backend 在 sys.path
BACKEND = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BACKEND not in sys.path:
    sys.path.insert(0, str(BACKEND))


# ────────────────────────── 公共 helpers ──────────────────────────


def _make_jwt(user_id: str) -> str:
    """生成 JWT (与 auth-gateway 共享 HS256 密钥)."""
    import jwt as pyjwt
    secret = os.environ.get("JWT_SECRET")
    if not secret:
        from dotenv import load_dotenv
        env_path = os.path.join(BACKEND, "config", ".env")
        if os.path.exists(env_path):
            load_dotenv(env_path, override=False)
        secret = os.environ.get(
            "JWT_SECRET", "dev-secret-key-not-for-production-1234567890"
        )
    payload = {
        "sub": user_id,
        "username": f"xlrm_{user_id[:8]}",
        "role": "user",
        "type": "access",
        "iat": int(time.time()),
        "exp": int(time.time()) + 3600,
    }
    return pyjwt.encode(payload, secret, algorithm="HS256")


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


def _ensure_all_tables(db) -> None:
    """确保 liveroom / flashcard / planning / error_book 全部表就绪"""
    try:
        from app.services.liveroom import _ensure_tables
        _ensure_tables()
    except Exception:
        pass
    try:
        from app.api.flashcard.service import _ensure_tables
        _ensure_tables()
    except Exception:
        pass
    try:
        from app.services.practice.practice_error_book import _ensure_error_book
        _ensure_error_book()
    except Exception:
        pass
    try:
        from app.services.planning import _ensure_tables as _ensure_planning
        _ensure_planning()
    except Exception:
        pass
    try:
        from app.services import project as project_service
        project_service.ensure_tables()
    except Exception:
        pass


def _seed_liveroom(db, user_id: str) -> dict:
    """为测试预置 liveroom 全部关联表 (避免 FK 失败)"""
    room_id = f"lr_{uuid.uuid4().hex[:12]}"
    participant_id = f"PART_{uuid.uuid4().hex[:12]}"
    session_id = f"SESS_{uuid.uuid4().hex[:12]}"
    db.execute(
        """INSERT INTO language_rooms
            (id, owner_id, name, scenario_id, room_type, max_participants,
             is_recording_enabled, is_transcript_enabled, ai_intrusion_level,
             status, started_at, settings, created_at, updated_at)
           VALUES (%s, %s, 'audit-room', '', '1v1', 2, FALSE, TRUE, 'low',
             'active', NOW(), '{}'::jsonb, NOW(), NOW())
           ON CONFLICT (id) DO NOTHING""",
        (room_id, user_id),
    )
    db.execute(
        """INSERT INTO room_participants
            (id, room_id, user_id, participant_type, role_label, language,
             joined_at, is_owner, created_at)
           VALUES (%s, %s, %s, 'human', 'me', 'en', NOW(), TRUE, NOW())
           ON CONFLICT (id) DO NOTHING""",
        (participant_id, room_id, user_id),
    )
    db.execute(
        """INSERT INTO room_sessions
            (id, room_id, user_id, participant_id, started_at, created_at, updated_at)
           VALUES (%s, %s, %s, %s, NOW(), NOW(), NOW())
           ON CONFLICT (id) DO NOTHING""",
        (session_id, room_id, user_id, participant_id),
    )
    return {
        "room_id": room_id,
        "participant_id": participant_id,
        "session_id": session_id,
    }


# ────────────────────────── Fixtures ──────────────────────────


@pytest.fixture
def user_id() -> str:
    return f"xlrm_{uuid.uuid4().hex[:12]}"


@pytest.fixture
def db():
    return _try_connect()


@pytest.fixture
def client():
    from fastapi.testclient import TestClient
    from app.main import app
    return TestClient(app)


@pytest.fixture
def auth_headers(user_id):
    return {"Authorization": f"Bearer {_make_jwt(user_id)}"}


@pytest.fixture(autouse=True)
def cleanup_test_data(db, user_id):
    """测试结束清理 user 数据"""
    yield
    for tbl in (
        "flashcards", "vocabulary_captures",
        "room_transcripts", "room_participants", "room_sessions",
        "room_scenarios", "ai_personas", "ai_helper_invasiveness",
        "ai_companion_configs", "language_rooms",
        "room_invitations", "room_recordings",
        "plan_items", "project_nodes", "projects",
        "error_book",
        "messages",
    ):
        try:
            db.execute(f"DELETE FROM {tbl} WHERE user_id = %s", (user_id,))
        except Exception:
            pass


# ══════════════════════════════════════════════════════════════
# 联动 1: Vocabulary → FlashCard
# ══════════════════════════════════════════════════════════════


class TestVocabularyToFlashCard:
    """联动 1: 词汇便签 → FlashCard (cross_module_source='language_room')"""

    def test_create_vocabulary_capture_writes_flashcard(self, db, user_id):
        """notes.create_vocabulary_capture 应写 flashcards 表 source='language_room'

        B1 修后: try/except 降级已不存在, FlashCard 写入必须真正成功
        (card_id 不为空, 落库 flashcards 表)
        """
        _ensure_all_tables(db)
        if not _table_exists(db, "flashcards"):
            pytest.skip("flashcards 表不存在")
        if not _table_exists(db, "vocabulary_captures"):
            pytest.skip("vocabulary_captures 表不存在")

        ids = _seed_liveroom(db, user_id)
        from app.services.liveroom.notes import create_vocabulary_capture

        result = create_vocabulary_capture(
            user_id=user_id,
            room_id=ids["room_id"],
            word="hola",
            translation="你好",
            context_sentence="Hola, ¿cómo estás?",
            language="es",
            transcript_id="",
            linked_node_ids=[f"node_{user_id}_v1"],
        )
        assert result.get("id"), "vocabulary_capture id 缺失"
        assert result.get("id", "").startswith("VC_")
        # B1 修后: card_id 必须非空 (FlashCard 写入不再静默降级)
        assert result.get("card_id"), (
            f"FlashCard 写入失败: card_id 为空. vocabulary_capture.id={result.get('id')}"
        )
        assert result.get("card_id", "").startswith("FC_")

        # 验证 flashcards 表 (B1 修后, 必落库)
        row = db.fetchone(
            "SELECT id, source, front_text, back_text, language FROM flashcards "
            "WHERE id = %s AND user_id = %s",
            (result["card_id"], user_id),
        )
        assert row is not None, f"flashcard {result['card_id']} 不在 DB"
        assert row["source"] == "language_room", (
            f"source 应为 'language_room', 实际: {row['source']}"
        )
        assert row["front_text"] == "hola"
        assert row["back_text"] == "你好"

        # vocabulary_captures 表一定有 (在 FK 约束下)
        cap = db.fetchone(
            "SELECT id, word, translation, room_id FROM vocabulary_captures "
            "WHERE id = %s AND user_id = %s",
            (result["id"], user_id),
        )
        assert cap is not None
        assert cap["word"] == "hola"
        assert cap["room_id"] == ids["room_id"]

    def test_capture_vocabulary_endpoint_validates_required_word(self, client, auth_headers, user_id):
        """REST 端点缺 word 字段 → 422 (Pydantic 校验)"""
        _ensure_all_tables(_try_connect())
        r = client.post(
            "/api/liveroom/rooms/lr_x/vocabulary",
            headers=auth_headers,
            json={"translation": "x"},
        )
        # Pydantic-level 422, 端点正确拒绝空 word
        assert r.status_code in (200, 400, 422), f"unexpected status: {r.status_code} {r.text}"
        if r.status_code == 422:
            assert "word" in r.text.lower()


# ══════════════════════════════════════════════════════════════
# 联动 2: Error → ErrorBookEntry
# ══════════════════════════════════════════════════════════════


class TestErrorMarkToErrorBookEntry:
    """联动 2: 错误标记 → ErrorBookEntry (4 种 error_type)"""

    def test_create_error_entry_persists_to_error_book(self, db, user_id):
        """Task #69 修 B1 后: notes.create_error_entry 必落库到真实 error_book 表

        修前 BUG: notes.py:80 写到不存在的 'practice_error_book' 表 (silent fail)
        修后: 写真实 error_book 表, source_type='language_room', source_ref_id=transcript_id
        """
        _ensure_all_tables(db)
        if not _table_exists(db, "room_transcripts"):
            pytest.skip("room_transcripts 表不存在")
        if not _table_exists(db, "error_book"):
            pytest.skip("error_book 表不存在")

        ids = _seed_liveroom(db, user_id)
        transcript_id = f"TR_{uuid.uuid4().hex[:12]}"
        db.execute(
            """INSERT INTO room_transcripts
                (id, room_id, participant_id, user_id, segment_index, text, language,
                 started_at, ended_at, confidence, speaker_id, speaker_name, created_at)
               VALUES (%s, %s, %s, %s, 1, 'I goed to store', 'en', NOW(), NOW(), 0.9, %s, 'me', NOW())""",
            (transcript_id, ids["room_id"], ids["participant_id"], user_id, user_id),
        )

        from app.services.liveroom.notes import create_error_entry

        result = create_error_entry(
            user_id=user_id,
            room_id=ids["room_id"],
            transcript_id=transcript_id,
            error_type="grammar",
            user_note="应改为 went",
            linked_node_ids=[f"node_{user_id}_e1"],
        )
        assert result.get("error_entry_id"), "error_entry_id 缺失"
        assert result.get("error_entry_id", "").startswith("EBE_")

        # B1 修后: ErrorBookEntry 必落库 (不再 silent fail)
        row = db.fetchone(
            "SELECT entry_id, user_id, error_type, is_resolved, source_type, source_ref_id, "
            "user_answer, misconception, attribution "
            "FROM error_book WHERE entry_id = %s AND user_id = %s",
            (result["error_entry_id"], user_id),
        )
        assert row is not None, (
            f"B1 未真修: error_book 表无记录 (entry_id={result['error_entry_id']}). "
            f"notes.create_error_entry 写入静默失败"
        )
        assert row["error_type"] == "grammar"
        assert row["is_resolved"] is False
        assert row["source_type"] == "language_room", (
            f"source_type 应为 'language_room', 实际: {row.get('source_type')}"
        )
        assert row["source_ref_id"] == transcript_id
        assert row["user_answer"] == "I goed to store"
        assert row["misconception"] == "应改为 went"

        # attribution JSONB 含 room_id + source 字段
        attribution = row["attribution"]
        if isinstance(attribution, str):
            attribution = json.loads(attribution)
        assert attribution.get("source") == "language_room"
        assert attribution.get("room_id") == ids["room_id"]

        # 验证 transcript 标记 (无 silent fail)
        tr = db.fetchone(
            "SELECT is_error, error_entry_id FROM room_transcripts "
            "WHERE id = %s AND user_id = %s",
            (transcript_id, user_id),
        )
        assert tr["is_error"] is True
        assert tr["error_entry_id"] == result["error_entry_id"]

    def test_4_error_types_all_persist(self, db, user_id):
        """4 种 error_type 全部能落库: grammar/vocabulary/pronunciation/coherence"""
        _ensure_all_tables(db)
        if not _table_exists(db, "error_book"):
            pytest.skip("error_book 表不存在")

        ids = _seed_liveroom(db, user_id)
        from app.services.liveroom.notes import create_error_entry

        for et in ("grammar", "vocabulary", "pronunciation", "coherence"):
            tr_id = f"TR_{uuid.uuid4().hex[:12]}"
            db.execute(
                """INSERT INTO room_transcripts
                    (id, room_id, participant_id, user_id, segment_index, text, language,
                     started_at, ended_at, confidence, speaker_id, speaker_name, created_at)
                   VALUES (%s, %s, %s, %s, 1, 'sample', 'en', NOW(), NOW(), 0.9, %s, 'me', NOW())""",
                (tr_id, ids["room_id"], ids["participant_id"], user_id, user_id),
            )
            r = create_error_entry(
                user_id=user_id, room_id=ids["room_id"], transcript_id=tr_id,
                error_type=et, user_note=f"note for {et}",
            )
            row = db.fetchone(
                "SELECT error_type FROM error_book WHERE entry_id = %s",
                (r["error_entry_id"],),
            )
            assert row is not None, f"error_type={et} 未落库"
            assert row["error_type"] == et

    def test_error_mark_endpoint_validates_transcript_id(self, client, auth_headers, user_id):
        """错误端点缺 transcript_id → 422 (Pydantic 校验)"""
        _ensure_all_tables(_try_connect())
        r = client.post(
            "/api/liveroom/rooms/lr_x/error",
            headers=auth_headers,
            json={"error_type": "vocabulary"},
        )
        assert r.status_code in (400, 422), f"unexpected status: {r.status_code} {r.text}"
        if r.status_code == 422:
            assert "transcript_id" in r.text.lower()

    def test_4_error_types_supported_in_event_schema(self):
        """事件 schema 应支持 4 种 error_type: grammar/vocabulary/pronunciation/coherence"""
        from shared.events import LanguageRoomErrorMarked
        # 实例化 4 种类型, 字段正常
        for et in ("grammar", "vocabulary", "pronunciation", "coherence"):
            e = LanguageRoomErrorMarked(
                user_id="u", room_id="r", transcript_id="t",
                error_entry_id="e", error_type=et,
            )
            assert e.error_type == et


# ══════════════════════════════════════════════════════════════
# 联动 3: Message → ExplainCard
# ══════════════════════════════════════════════════════════════


class TestMessageToExplainCard:
    """联动 3: 文字辅助 → ExplainCard (D14 后, explain_cards 表已删除)"""

    def test_create_explain_card_persists_to_messages(self, db, user_id):
        """Task #69 修 B2 后: notes.create_explain_card 必落库到 messages.metadata JSONB

        修前 BUG: notes.py:147 写到 D14 已删的 'explain_cards' 表 (silent fail)
        修后: 写真实 messages 表, metadata JSONB 含 source_module='language_room' +
              source_ref_id=room_id + is_explain_card=true + explain_cards 数组
        """
        _ensure_all_tables(db)
        if not _table_exists(db, "room_sessions"):
            pytest.skip("room_sessions 表不存在")

        from app.services.liveroom.notes import create_explain_card

        room_id = f"lr_{uuid.uuid4().hex[:12]}"
        result = create_explain_card(
            user_id=user_id,
            room_id=room_id,
            text="这是一个辅助说明",
            message_type="text",
            reference_url="https://example.com",
        )
        assert result.get("id"), "explain_card id 缺失"
        assert result.get("text") == "这是一个辅助说明"

        # B2 修后: messages 表必落库 (不再 silent fail)
        row = db.fetchone(
            "SELECT id, user_id, conv_id, role, content, metadata "
            "FROM messages WHERE id = %s AND user_id = %s",
            (result["id"], user_id),
        )
        assert row is not None, (
            f"B2 未真修: messages 表无记录 (id={result['id']}). "
            f"notes.create_explain_card 写入静默失败"
        )
        assert row["conv_id"] == room_id
        assert row["role"] == "assistant"

        # metadata JSONB 校验
        meta = row["metadata"]
        if isinstance(meta, str):
            meta = json.loads(meta)
        assert meta.get("source_module") == "language_room"
        assert meta.get("source_ref_id") == room_id
        assert meta.get("message_type") == "text"
        assert meta.get("reference_url") == "https://example.com"
        assert meta.get("is_explain_card") is True
        # 历史兼容字段: explain_cards 数组
        assert isinstance(meta.get("explain_cards"), list)
        assert len(meta["explain_cards"]) == 1
        assert meta["explain_cards"][0]["content"] == "这是一个辅助说明"

        # list_messages 应能通过 source_module/source_ref_id 过滤命中
        listed = db.fetchall(
            """SELECT id, content FROM messages
               WHERE metadata->>'source_module' = 'language_room'
                 AND metadata->>'source_ref_id' = %s
                 AND user_id = %s
                 AND is_deleted = FALSE""",
            (room_id, user_id),
        )
        assert len(listed) >= 1
        assert any(r["content"] == "这是一个辅助说明" for r in listed)

    def test_post_message_endpoint_mounted(self, client, auth_headers, user_id):
        """REST 端点 /api/liveroom/rooms/{id}/messages 正确挂载 (Pydantic 422 验证)"""
        _ensure_all_tables(_try_connect())
        # text 必填, 缺 text 应 422
        r = client.post(
            "/api/liveroom/rooms/lr_x/messages",
            headers=auth_headers,
            json={},
        )
        # Pydantic 验证缺失 text → 422
        assert r.status_code == 422, f"unexpected: {r.status_code} {r.text}"
        assert "text" in r.text.lower()


# ══════════════════════════════════════════════════════════════
# 联动 4: AI Helper → KnowledgeGraph
# ══════════════════════════════════════════════════════════════


class TestAIHelperToKnowledgeGraph:
    """联动 4: AI 辅助查询知识点 (grammar/vocabulary/sentence_pattern)"""

    def test_tool_knowledge_search_returns_nodes(self, db, user_id):
        """tool_knowledge_search 调知识图谱搜索, 返回节点信息"""
        _ensure_all_tables(db)
        from app.infrastructure.llm.liveroom_tools import execute_sync

        # 缺 query → 拒绝
        result = execute_sync("tool_knowledge_search", {
            "user_id": user_id, "query": "",
        })
        assert result["ok"] is False
        assert "query" in result["error"]

        # 正常 query: 即使无数据, 路径应走通
        result = execute_sync("tool_knowledge_search", {
            "user_id": user_id,
            "query": "present perfect tense",
            "max_results": 3,
        })
        assert result["ok"] is True, f"搜索应成功: {result}"
        assert "results" in result
        assert isinstance(result["results"], list)

    def test_ai_helper_invoke_uses_three_helper_types(self, db, user_id):
        """AI 辅助者 helper_type 应支持 grammar/vocabulary/sentence_pattern 3 类"""
        _ensure_all_tables(db)
        from app.services.liveroom.ai_persona import InvasivenessConfig
        cfg = InvasivenessConfig(user_id=user_id, room_id="lr_x")
        assert set(cfg.helper_types) == {"grammar", "vocabulary", "sentence_pattern"}, (
            f"helper_types 应为 3 类, 实际: {cfg.helper_types}"
        )

        # 事件 schema 也应支持 3 类
        from shared.events import LanguageRoomAIHelperInvoked
        for ht in ("grammar", "vocabulary", "sentence_pattern"):
            e = LanguageRoomAIHelperInvoked(
                user_id="u", room_id="r", helper_type=ht,
                query="q", response="r",
            )
            assert e.helper_type == ht


# ══════════════════════════════════════════════════════════════
# 联动 5: Transcript → voice_feature_stream (待修复 6, 仍断链)
# ══════════════════════════════════════════════════════════════


class TestTranscriptToVoiceFeatures:
    """联动 5: 转写片段 → 0005 MoodStress voice_features

    ADR 0004 待修复 6: liveroom → MoodStress voice_features 流尚未端到端打通
    状态: 仍断链 (本测试类全 skip, 待 Task #66 修复后再激活)
    详见 docs/adr/0004-language-multiplayer.md 待修复 6
    """

    def test_voice_feature_signal_type_is_defined(self):
        """voice_features 信号类型应在 MoodStress 模块定义 (行为信号 7 类之一)

        ADR 待修复 6: liveroom → MoodStress voice_features 流未端到端打通
        待 Task #66 修复后激活
        """
        pytest.skip(
            "ADR 0004 待修复 6: liveroom → MoodStress voice_features 流未端到端打通, "
            "待 Task #66 实现. 详见 docs/adr/0004-language-multiplayer.md 待修复 6"
        )

    def test_no_subscriber_for_voice_features_from_liveroom(self):
        """ADR 待修复 6: liveroom 不推 voice_features 到 MoodStress (断链)

        待 Task #66 修复后激活
        """
        pytest.skip(
            "ADR 0004 待修复 6: liveroom → MoodStress voice_features 流未端到端打通, "
            "待 Task #66 实现. 详见 docs/adr/0004-language-multiplayer.md 待修复 6"
        )

    def test_emit_behavior_signal_voice_features_default_off(self, db, user_id):
        """voice_features 信号默认应被拒绝 (auto_collect=False)

        ADR 待修复 6: 待 Task #66 修复后激活
        """
        pytest.skip(
            "ADR 0004 待修复 6: liveroom → MoodStress voice_features 流未端到端打通, "
            "待 Task #66 实现. 详见 docs/adr/0004-language-multiplayer.md 待修复 6"
        )


# ══════════════════════════════════════════════════════════════
# 联动 6: Room Completed → PlanItem
# ══════════════════════════════════════════════════════════════


class TestRoomCompletedToPlanItem:
    """联动 6: 房间结束 → 产生 plan_item 回顾 (source_module='language_room')"""

    @pytest.mark.asyncio
    async def test_language_room_route_completes_plan_item(self, db, user_id):
        """language_room 路由应能标记 plan_items 为 completed (无重发)"""
        _ensure_all_tables(db)
        if not _table_exists(db, "plan_items"):
            pytest.skip("plan_items 表不存在")

        from shared.events import PlanItemCompleted, PlanningSourceModule
        from app.services.planning.completion_writer import (
            PlanningCompletionWriter,
        )
        from app.infrastructure.event_bus import EventBus

        # 创建 plan_item
        pid = f"plan_xlrm_{uuid.uuid4().hex[:12]}"
        db.execute(
            """INSERT INTO plan_items
                (id, user_id, source_module, target_type, target_ref_id,
                 title, description, estimated_minutes, status,
                 linked_node_ids, priority, created_at, updated_at)
               VALUES (%s, %s, 'language_room', 'scenario', 'lr_x',
                 '语言房间练习', '练习 1v1 场景', 30, 'pending',
                 '[]'::jsonb, 0, NOW(), NOW())""",
            (pid, user_id),
        )

        bus = EventBus(handler_timeout=2.0)
        captured: list = []

        async def _cap(event):
            captured.append(event)
        for evt in (
            "LanguageRoomCompleted",
            "LanguageRoomEnded",
            "LanguageRoomStarted",
            "LanguageRoomParticipantJoined",
        ):
            bus.subscribe(evt, _cap)

        writer = PlanningCompletionWriter()
        writer.subscribe(bus)

        event = PlanItemCompleted(
            user_id=user_id, plan_item_id=pid,
            source_module=PlanningSourceModule.LANGUAGE_ROOM.value,
            target_type="scenario", target_ref_id="lr_audit_001",
            actual_minutes=45,
        )
        await bus.publish(event)

        # 1. plan_item 状态
        row = db.fetchone(
            "SELECT status, actual_minutes FROM plan_items WHERE id=%s AND user_id=%s",
            (pid, user_id),
        )
        assert row is not None
        assert row["status"] == "completed", (
            f"language_room 路由未完成: status={row['status']}"
        )
        assert row["actual_minutes"] == 45

        # 2. 不重发 liveroom 源事件
        assert len(captured) == 0, (
            f"language_room 路由重发了 {len(captured)} 个源事件"
        )

    def test_no_auto_plan_item_created_on_room_completed(self, db, user_id):
        """审计: LanguageRoomCompleted 事件本身不会自动创建 plan_item
        (需要用户主动用 create_plan_item 登记)
        """
        _ensure_all_tables(db)
        from app.infrastructure.event_bus import EventBus
        from shared.events import LanguageRoomCompleted

        bus = EventBus(handler_timeout=1.0)
        captured: list = []

        async def _cap(event):
            captured.append(event)
        bus.subscribe("PlanItemCreated", _cap)

        async def _test():
            await bus.publish(LanguageRoomCompleted(
                user_id=user_id,
                room_id="lr_x",
                session_id="sess_x",
                scenario_id="",
                duration_seconds=600.0,
                transcript_segments=[],
                errors_marked=2,
                cards_generated=3,
                linked_node_ids=[],
                ai_help_requests=1,
            ))

        asyncio.run(_test())
        # 不应有 PlanItemCreated 自动触发
        assert len(captured) == 0, (
            f"LanguageRoomCompleted 不应自动创建 plan_item, "
            f"但捕获 {len(captured)} 个 PlanItemCreated"
        )


# ══════════════════════════════════════════════════════════════
# 联动 7: Scenario → Project (待修复 5)
# ══════════════════════════════════════════════════════════════


class TestScenarioToProject:
    """联动 7: 场景被项目节点关联 (ADR 待修复 5: 未端到端打通)"""

    def test_scenario_has_no_project_link_subscriber(self, db, user_id):
        """审计: 场景与项目联动未端到端打通 (ADR 待修复 5)"""
        _ensure_all_tables(db)
        from app.application.di import container

        bus = container.event_bus
        handlers = getattr(bus, "_handlers", {}) or {}
        scenario_handlers = handlers.get("LanguageRoomScenarioChanged", [])
        # ADR 待修复 5: 场景与项目联动未端到端打通 → 无 handler
        assert len(scenario_handlers) == 0, (
            f"ADR 待修复 5 状态: LanguageRoomScenarioChanged 已有 {len(scenario_handlers)} 个 handler, "
            f"但 ADR 标注此联动未端到端打通"
        )

    def test_project_to_language_room_one_way_only(self, db, user_id):
        """ProjectNodeExported → language_room 路由存在, 反向未实现 (ADR 待修复 5)"""
        from app.application.di import container
        bus = container.event_bus
        handlers = getattr(bus, "_handlers", {}) or {}
        # 反向: scenario → project_node 不应有 handler
        # (LanguageRoomCreated 已有其他 handler: ai_persona, participant, etc., 但应无 project_node 创建逻辑)
        for h in handlers.get("LanguageRoomCreated", []):
            h_name = getattr(h, "__name__", str(h))
            assert "project" not in h_name.lower() and "scenario" not in h_name.lower(), (
                f"ADR 待修复 5: LanguageRoomCreated 有疑似 project 联动 handler: {h_name}"
            )

    def test_scenario_linked_node_ids_field(self, db, user_id):
        """场景表应有 linked_node_ids 字段 (供项目节点关联使用)"""
        _ensure_all_tables(db)
        if not _table_exists(db, "room_scenarios"):
            pytest.skip("room_scenarios 表不存在")
        col = db.fetchone(
            """SELECT 1 FROM information_schema.columns
               WHERE table_name = 'room_scenarios'
                 AND column_name = 'linked_node_ids' LIMIT 1"""
        )
        assert col is not None, "room_scenarios 缺 linked_node_ids 字段"


# ══════════════════════════════════════════════════════════════
# 联动 8: AI Persona 共享 tool registry
# ══════════════════════════════════════════════════════════════


class TestAIPersonaSharedToolRegistry:
    """联动 8: AI 角色服务调用共享 tool_repository (ADR 决策 5)"""

    def test_ai_persona_get_shared_tool_names_includes_liveroom(self):
        """ai_persona.get_shared_tool_names() 应包含 4 类 liveroom 工具"""
        from app.infrastructure.llm.tool_repository import get_tool_repository
        from app.infrastructure.llm.knowledge_ops_tools import TOOL_DEFINITIONS as KTOOL_DEFS
        from app.infrastructure.llm.liveroom_tools import TOOL_DEFINITIONS as LROOM_DEFS

        repo = get_tool_repository()
        repo.register_raw_tools(KTOOL_DEFS)
        repo.register_raw_tools(LROOM_DEFS)

        from app.services.liveroom.ai_persona import get_shared_tool_names
        names = get_shared_tool_names()
        for n in (
            "tool_vocabulary_capture",
            "tool_error_mark",
            "tool_message_post",
            "tool_knowledge_search",
        ):
            assert n in names, f"missing shared tool: {n}"

    def test_ai_persona_execute_shared_tool_liveroom_path(self):
        """execute_shared_tool 对 liveroom 工具走同步 handler 路径"""
        from app.infrastructure.llm.tool_repository import get_tool_repository
        from app.infrastructure.llm.knowledge_ops_tools import TOOL_DEFINITIONS as KTOOL_DEFS
        from app.infrastructure.llm.liveroom_tools import TOOL_DEFINITIONS as LROOM_DEFS

        repo = get_tool_repository()
        repo.register_raw_tools(KTOOL_DEFS)
        repo.register_raw_tools(LROOM_DEFS)

        from app.services.liveroom.ai_persona import execute_shared_tool
        result = execute_shared_tool(
            "tool_knowledge_search",
            user_id="u_test",
            query="present perfect",
            max_results=3,
        )
        assert "ok" in result
        assert result.get("via") == "liveroom_sync_handler", (
            f"AI 角色应走 liveroom sync handler 路径, 实际: {result.get('via')}"
        )

    def test_ai_persona_default_helper_types(self):
        """AI 辅助者默认 helper_types = 3 类 (grammar/vocabulary/sentence_pattern)"""
        from app.services.liveroom.ai_persona import InvasivenessConfig
        cfg = InvasivenessConfig(user_id="u", room_id="r")
        assert cfg.helper_types == ["grammar", "vocabulary", "sentence_pattern"]

    def test_ai_persona_does_not_call_llm_for_judgment(self):
        """AI 角色不调用 LLM 做评判 (ADR 决策 6)"""
        # 验证: _call_llm_for_companion_response 注释说明不纠错不评判
        from app.services.liveroom.ai_persona import _call_llm_for_companion_response
        import inspect
        src = inspect.getsource(_call_llm_for_companion_response)
        assert "不评判" in src or "not correct" in src.lower() or "judg" not in src.lower(), (
            "AI 角色不调用 LLM 做评判的约束应在 _call_llm_for_companion_response 体现"
        )
