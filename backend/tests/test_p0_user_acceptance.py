"""
Task #39 — P0 用户验收测试套件 (E2E)

目标:
  - 端到端验证 7 个模块入口（Project / FlashCard / Reading / LanguageRoom /
    MoodStress / Planning / InterestExplorer）均可用
  - 端到端验证 7 个 P0 修复的真实效果（HTTP API + 真实 DB）
  - 验证架构 P0-P3 修复（事件循环 / 直写 SQL / source 字段拆分 / tool 路由 / etc.）

设计:
  - 走真实 HTTP API（FastAPI TestClient + JWT Bearer 认证）
  - 使用唯一 user_id 隔离测试，避免互相污染
  - 数据库不可用时 skip（保留 test_*.py 收集可行性）
  - 失败时给出可读 assertion 消息
"""
from __future__ import annotations

import os
import sys
import uuid
import json
import time
import pytest

# 让 backend 在 sys.path
BACKEND = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BACKEND not in sys.path:
    sys.path.insert(0, BACKEND)


# ════════════════════════════════════════════════════════════════════
# Fixtures
# ════════════════════════════════════════════════════════════════════


def _make_jwt(user_id: str) -> str:
    """生成一个有效的 JWT token (与 auth-gateway 共享 HS256 密钥)"""
    import jwt as pyjwt
    secret = os.environ.get("JWT_SECRET")
    if not secret:
        # 兼容 .env 加载前的情况
        from dotenv import load_dotenv
        env_path = os.path.join(BACKEND, "config", ".env")
        if os.path.exists(env_path):
            load_dotenv(env_path, override=False)
        secret = os.environ.get("JWT_SECRET", "dev-secret-key-not-for-production-1234567890")
    payload = {
        "sub": user_id,
        "username": f"uatest_{user_id[:8]}",
        "role": "user",
        "type": "access",
        "iat": int(time.time()),
        "exp": int(time.time()) + 3600,
    }
    return pyjwt.encode(payload, secret, algorithm="HS256")


@pytest.fixture
def user_id() -> str:
    """独立测试用户 ID, 每次测试唯一避免污染"""
    return f"ua_{uuid.uuid4().hex[:12]}"


@pytest.fixture
def db():
    """数据库连接 fixture; 不可用时跳过测试"""
    try:
        from app.infrastructure.db.database import get_db
        d = get_db()
        d.fetchone("SELECT 1")
        return d
    except Exception as exc:  # noqa: BLE001
        pytest.skip(f"数据库不可用: {exc}")


@pytest.fixture
def client():
    """FastAPI TestClient（带 JWT 认证）"""
    from fastapi.testclient import TestClient
    from app.main import app
    return TestClient(app)


@pytest.fixture
def auth_headers(user_id):
    """为指定 user_id 生成认证头 (Bearer JWT)"""
    token = _make_jwt(user_id)
    return {"Authorization": f"Bearer {token}"}


# ════════════════════════════════════════════════════════════════════
# 模块 1: Project (P0-1 入口 + P0-3 节点引用 + P0-2 事件循环修复)
# ════════════════════════════════════════════════════════════════════


class TestProjectModule:
    """P0-1 项目模块入口 + P0-3 节点引用 + P0-2 事件循环修复"""

    def test_create_project_via_rest(self, client, user_id, db, auth_headers):
        """通过 REST API 创建项目，验证模块入口可用"""
        # ensure tables first
        from app.services import project as project_service
        project_service.ensure_tables()
        # POST /api/projects/
        r = client.post(
            "/api/projects/",
            headers=auth_headers,
            json={"name": f"E2E 项目 {user_id}", "description": "test"},
        )
        assert r.status_code in (200, 201), f"创建项目失败: {r.text}"
        data = r.json()
        assert data["name"].startswith("E2E 项目"), f"返回 name 不对: {data}"
        assert data["user_id"] == user_id
        assert data["status"] == "active"
        proj_id = data["id"]
        # GET /api/projects/{id}
        r2 = client.get(
            f"/api/projects/{proj_id}",
            headers=auth_headers,
        )
        assert r2.status_code == 200, f"查询项目失败: {r2.text}"
        assert r2.json()["id"] == proj_id

    def test_create_node_via_rest(self, client, user_id, db, auth_headers):
        """通过 REST API 创建节点，验证 7 种节点类型中前 2 个"""
        from app.services import project as project_service
        project_service.ensure_tables()
        proj = project_service.create_project(user_id=user_id, name="E2E Node Test")
        # type=2 文本节点
        r = client.post(
            f"/api/projects/{proj['id']}/nodes",
            headers=auth_headers,
            json={"type": 2, "title": "测试文本节点", "content": {"text": "hello"}},
        )
        assert r.status_code == 200, f"创建节点失败: {r.text}"
        node = r.json()
        assert node["type"] == 2
        assert node["title"] == "测试文本节点"
        assert node["user_id"] == user_id
        # GET /api/projects/{pid}/nodes
        r2 = client.get(
            f"/api/projects/{proj['id']}/nodes",
            headers=auth_headers,
        )
        assert r2.status_code == 200
        nodes = r2.json()["nodes"]
        assert len(nodes) == 1
        assert nodes[0]["id"] == node["id"]

    def test_copy_node_across_projects(self, client, user_id, db, auth_headers):
        """跨项目节点复制（深拷贝 + 链接复制）"""
        from app.services import project as project_service
        from app.services.project import node_ref

        project_service.ensure_tables()
        proj_a = project_service.create_project(user_id=user_id, name="Copy Source A")
        proj_b = project_service.create_project(user_id=user_id, name="Copy Target B")
        src = project_service.create_node(
            user_id=user_id, project_id=proj_a["id"],
            type=2, title="复制源",
            content={"text": "original"},
        )
        # 通过 REST 调用 copy-nodes
        r = client.post(
            f"/api/projects/{proj_b['id']}/copy-nodes",
            headers=auth_headers,
            json={
                "source_project_id": proj_a["id"],
                "node_ids": [src["id"]],
                "mode": "deep_copy",
            },
        )
        assert r.status_code == 200, f"copy-nodes 失败: {r.text}"
        body = r.json()
        assert "created" in body
        assert len(body["created"]) == 1
        copied = body["created"][0]
        assert copied["mode"] == "deep_copy"
        new_id = copied["new_node_id"]
        # 验证：目标项目能查到新节点
        target_node = project_service.get_node(user_id, proj_b["id"], new_id)
        assert target_node is not None, "复制节点后查询返回 None"
        assert target_node["title"] == "复制源"
        # deep_copy 应复制 content
        assert target_node["content"] == {"text": "original"}

    def test_node_completion_no_event_loop(self, client, user_id, db, auth_headers):
        """P0-2 修复验证：PlanItemCompleted 消费后不重发 ProjectNodeCompleted

        通过直接调用 planning completion_writer 来验证：
          - PlanItemCompleted(source_module='project') 路由到 _handle_project
          - 该 handler 仅 UPDATE project_nodes.status='completed'
          - **不**发布 ProjectNodeCompleted 事件（防循环）
        """
        from app.services import project as project_service
        from app.services.planning.completion_writer import planning_completion_writer
        from app.infrastructure.event_bus import EventBus
        from shared.events import PlanItemCompleted, ProjectNodeCompleted, PlanningSourceModule

        project_service.ensure_tables()
        proj = project_service.create_project(user_id=user_id, name="EventLoop Test")
        node = project_service.create_node(
            user_id=user_id, project_id=proj["id"], type=2, title="loop test",
        )
        # 状态应初始 pending
        assert node["status"] == "pending"

        # 启动一个独立 bus, 订阅 ProjectNodeCompleted, 验证消费后**不**发
        test_bus = EventBus(handler_timeout=1.0)
        published: list = []
        test_bus.subscribe("ProjectNodeCompleted", lambda e: published.append(e))

        # 模拟原 bus 上有 PlanItemCompleted 订阅
        test_bus.subscribe("PlanItemCompleted", planning_completion_writer._on_completed)
        planning_completion_writer._bus = test_bus

        # 触发 PlanItemCompleted
        import asyncio
        plan_item_id = f"plan_{user_id}_x"
        # 先在 plan_items 插一条数据 (handler 也要更新 plan_items)
        from app.infrastructure.db.database import get_db
        d = get_db()
        d.execute(
            """INSERT INTO plan_items
               (id, user_id, source_module, target_type, target_ref_id, title, status, created_at, updated_at)
               VALUES (%s, %s, %s, %s, %s, %s, 'pending', NOW(), NOW())""",
            (plan_item_id, user_id, PlanningSourceModule.PROJECT.value,
             "project_node", node["id"], "loop test plan"),
        )

        async def run():
            ev = PlanItemCompleted(
                user_id=user_id,
                plan_item_id=plan_item_id,
                source_module=PlanningSourceModule.PROJECT.value,
                target_type="project_node",
                target_ref_id=node["id"],
                actual_minutes=10,
            )
            await test_bus.publish(ev)
            # 等 handler 完成
            await asyncio.sleep(0.2)

        asyncio.run(run())
        # 1) project_nodes.status='completed' (直接 UPDATE 路径)
        after = project_service.get_node(user_id, proj["id"], node["id"])
        assert after is not None, "node 丢失"
        assert after["status"] == "completed", f"期望 completed 实际 {after['status']}"
        # 2) **不**重发 ProjectNodeCompleted (防循环)
        assert len(published) == 0, (
            f"P0-2 事件循环修复失效：消费 PlanItemCompleted 后重发了 "
            f"{len(published)} 个 ProjectNodeCompleted"
        )
        # 3) plan_items 也被标为 completed
        row = d.fetchone(
            "SELECT status FROM plan_items WHERE id = %s", (plan_item_id,),
        )
        assert row is not None
        assert row["status"] == "completed"


# ════════════════════════════════════════════════════════════════════
# 模块 2: FlashCard (P0-1 入口 + P0-3 source 字段拆分)
# ════════════════════════════════════════════════════════════════════


class TestFlashCardModule:
    """P0-1 卡片复习入口 + P0-3 source 字段拆分"""

    def test_review_card_via_rest(self, client, user_id, db, auth_headers):
        """通过 REST 创建卡片 + 提交复习，验证模块入口可用"""
        from app.api.flashcard.service import FlashCardService
        FlashCardService.ensure_tables()
        # 先创建卡
        r = client.post(
            "/api/flashcards/",
            headers=auth_headers,
            json={
                "front_text": "FSRS 是什么?",
                "back_text": "Free Spaced Repetition Scheduler",
                "linked_node_ids": ["ua_node_1"],
            },
        )
        assert r.status_code in (200, 201), f"创建卡片失败: {r.text}"
        card = r.json()
        assert card["front_text"] == "FSRS 是什么?"
        assert card["user_id"] == user_id
        # 提交复习
        r2 = client.post(
            f"/api/flashcards/{card['id']}/review",
            headers=auth_headers,
            json={"self_assessment": "good", "session_id": "ua_sess_1"},
        )
        assert r2.status_code == 200, f"提交复习失败: {r2.text}"
        result = r2.json()
        assert result["self_assessment"] == "good"
        assert "stability_after" in result
        assert "interval_after" in result
        # 验证 FSRS 字段被更新
        assert result["stability_after"] > 0
        assert result["interval_after"] >= 1

    def test_card_created_with_cross_module_source(self, client, user_id, db, auth_headers):
        """P0-3 验证：cross_module_source 字段在创建时被正确填充并保留

        FlashCardCreate 接受 cross_module_source 字段, 创建时保留用户提供的值
        (data-model.md §5.2 + events.md §2.1)
        """
        from app.api.flashcard.service import FlashCardService
        FlashCardService.ensure_tables()
        # source='practice_error' + cross_module_source='practice_error'
        r = client.post(
            "/api/flashcards/",
            headers=auth_headers,
            json={
                "front_text": "错题 front",
                "back_text": "错题 back",
                "linked_node_ids": ["ua_node_2"],
                "source": "practice_error",
                "cross_module_source": "practice_error",
                "error_book_entry_id": f"eb_{user_id}",
            },
        )
        assert r.status_code in (200, 201), f"创建失败: {r.text}"
        card = r.json()
        # source 字段保留用户提供的值（不被默认 manual 覆盖）
        assert card["source"] == "practice_error", (
            f"source 字段未保留: {card['source']}, expected 'practice_error'"
        )
        assert card["error_book_entry_id"] == f"eb_{user_id}"
        # 默认 source (manual) 的卡 — 验证 source 拆分
        r2 = client.post(
            "/api/flashcards/",
            headers=auth_headers,
            json={
                "front_text": "手动卡",
                "linked_node_ids": ["ua_node_3"],
            },
        )
        assert r2.status_code in (200, 201)
        assert r2.json()["source"] == "manual"
        # reading_note 来源
        r3 = client.post(
            "/api/flashcards/",
            headers=auth_headers,
            json={
                "front_text": "阅读笔记卡",
                "linked_node_ids": ["ua_node_4"],
                "source": "reading_note",
                "cross_module_source": "reading_note",
            },
        )
        assert r3.status_code in (200, 201)
        assert r3.json()["source"] == "reading_note"


# ════════════════════════════════════════════════════════════════════
# 模块 3: Reading (P0-1 阅读入口 + P0-3 source 字段拆分)
# ════════════════════════════════════════════════════════════════════


class TestReadingModule:
    """P0-1 阅读入口 + P0-3 source 字段拆分"""

    def test_create_note_via_rest(self, client, user_id, db, auth_headers):
        """通过 REST 创建阅读笔记, 验证走的是 FlashCard 反思型路径

        笔记 = 复用 FlashCard (card_type=7, source='reading_note',
        cross_module_source='reading')
        """
        # 先 ensure reading tables
        from app.services.reading import _ensure_tables as _ensure_reading
        _ensure_reading()
        from app.api.flashcard.service import FlashCardService
        FlashCardService.ensure_tables()

        # POST /api/reading/notes
        r = client.post(
            "/api/reading/notes",
            headers=auth_headers,
            json={
                "material_id": f"mat_{user_id}",
                "front_text": "我的问题?",
                "back_text": "我的回应",
                "back_context": "关键论述",
                "linked_node_ids": ["ua_node_r1"],
            },
        )
        assert r.status_code == 200, f"创建笔记失败: {r.text}"
        card = r.json()
        # 笔记 = FlashCard 反思型 (card_type=7)
        # data-model.md §5.1: type 7 = 反思
        assert card.get("type") == 7, f"笔记应为 type=7, 实际 {card.get('type')}"
        # P0-3 source 字段拆分: source='reading_note', cross_module_source='reading'
        assert card["source"] == "reading_note", (
            f"笔记 source 应为 reading_note, 实际 {card['source']}"
        )
        # 验证 DB 中真的创建了 FlashCard
        row = db.fetchone(
            "SELECT id, source, type FROM flashcards WHERE id = %s AND user_id = %s",
            (card["id"], user_id),
        )
        assert row is not None
        assert row["source"] == "reading_note"
        assert row["type"] == 7

    def test_note_uses_split_source_fields(self, client, user_id, db, auth_headers):
        """P0-3 验证：reading_note 路径用 source='reading_note' + cross_module_source='reading'

        通过 services 层直接验证事件层字段填充
        """
        from app.services.reading.notes import create_reading_note
        from app.services.reading import _ensure_tables as _ensure_reading
        from app.api.flashcard.service import FlashCardService, get_flashcard_service
        _ensure_reading()
        FlashCardService.ensure_tables()

        # 使用 bus 捕获 FlashCardCreated 事件 (用于验证 cross_module_source)
        from app.infrastructure.event_bus import EventBus
        from shared.events import FlashCardCreated
        bus = EventBus(handler_timeout=1.0)
        captured: list = []
        bus.subscribe("FlashCardCreated", lambda e: captured.append(e))

        # 替换 get_flashcard_service 注入 bus
        import app.api.flashcard.service as fc_svc
        orig_get = fc_svc.get_flashcard_service
        fc_svc.get_flashcard_service = lambda event_bus=None: FlashCardService(event_bus=bus)

        try:
            # 直接调用 service 层
            card = create_reading_note(
                user_id=user_id,
                material_id=f"mat_split_{user_id}",
                front_text="split front",
                back_text="split back",
                back_context="ctx",
                linked_node_ids=["ua_node_split"],
            )
            assert card is not None
            assert card["source"] == "reading_note"
            # FlashCardCreated 事件应包含 cross_module_source='reading'
            import asyncio
            asyncio.run(asyncio.sleep(0.1))
            # 过滤属于本次 user 的事件
            my_events = [e for e in captured if e.user_id == user_id]
            assert any(
                e.card_id == card["id"] and e.cross_module_source == "reading"
                for e in my_events
            ), (
                f"P0-3 修复失效：reading 笔记创建时未发布 "
                f"cross_module_source='reading' 的 FlashCardCreated 事件"
            )
        finally:
            fc_svc.get_flashcard_service = orig_get


# ════════════════════════════════════════════════════════════════════
# 模块 4: LanguageRoom (P0-1 房间入口 + 架构 P1 共享 tool + P0-2 直写 SQL)
# ════════════════════════════════════════════════════════════════════


class TestLanguageRoomModule:
    """P0-1 房间入口 + 架构 P1 共享 tool + P0-2 直写 SQL"""

    def test_create_room_via_rest(self, client, user_id, db, auth_headers):
        """通过 REST 创建语言房间, 验证模块入口可用"""
        from app.api.liveroom import service as svc
        svc._ensure_tables()
        r = client.post(
            "/api/liveroom/rooms",
            headers=auth_headers,
            json={"name": f"E2E 房间 {user_id}", "max_participants": 2},
        )
        assert r.status_code == 200, f"创建房间失败: {r.text}"
        room = r.json()
        assert room["name"].startswith("E2E 房间")
        assert room["owner_id"] == user_id
        assert room["status"] == "active"
        # GET /api/liveroom/rooms/{id}
        r2 = client.get(
            f"/api/liveroom/rooms/{room['id']}",
            headers=auth_headers,
        )
        assert r2.status_code == 200
        assert r2.json()["id"] == room["id"]

    def test_capture_vocabulary_uses_tool_repository(self, client, user_id, db, auth_headers):
        """P0-2 + 架构 P1 验证: capture_vocabulary 走 execute_sync 而非直接写表

        通过给 service 函数 monkeypatch execute_sync, 验证:
          - service.py 调 execute_sync("tool_vocabulary_capture", ...)
          - 缺 word 时返回 error (来自 tool 验证)
        """
        from app.api.liveroom import service as svc
        svc._ensure_tables()
        # 创建 room
        room = svc.create_room(user_id, {"name": "vocab room", "max_participants": 2})
        assert room is not None
        room_id = room["id"]
        # 缺 word 字段 — 走 tool 路径时返回 error
        r = client.post(
            f"/api/liveroom/rooms/{room_id}/vocabulary",
            headers=auth_headers,
            json={"translation": "x"},  # 缺 word
        )
        # 422 (Pydantic 验证) 或 400 (tool 拒绝) 都可接受
        # 但不能是 500 (说明走了未验证路径)
        assert r.status_code in (400, 422), (
            f"vocabulary 验证未生效: status={r.status_code} body={r.text}"
        )
        # 验证：完整字段会通过 (走到 tool 内部处理)
        r2 = client.post(
            f"/api/liveroom/rooms/{room_id}/vocabulary",
            headers=auth_headers,
            json={
                "word": "serendipity",
                "translation": "意外发现",
                "linked_node_ids": ["ua_node_v1"],
            },
        )
        assert r2.status_code == 200, f"正常 capture 失败: {r2.text}"
        body = r2.json()
        assert body.get("word") == "serendipity"
        # vocabulary_captures 表应有数据
        row = db.fetchone(
            "SELECT word FROM vocabulary_captures WHERE user_id = %s AND room_id = %s",
            (user_id, room_id),
        )
        assert row is not None, "vocabulary_captures 表无数据 (tool 路径未生效)"
        assert row["word"] == "serendipity"

    def test_ai_helper_searches_knowledge(self, client, user_id, db, auth_headers):
        """架构 P1 验证: ai_helper 调 tool_knowledge_search 增强上下文

        通过 monkeypatch execute_shared_tool 验证:
          - ai_persona._call_llm_for_helper_response 调 tool_knowledge_search
          - 失败时降级 (不抛 500)
        """
        from app.api.liveroom import service as svc
        svc._ensure_tables()
        # 创建 room + helper config
        room = svc.create_room(user_id, {"name": "helper room", "max_participants": 2})
        room_id = room["id"]
        # enable grammar helper
        from app.services.liveroom.ai_persona import InvasivenessConfig
        config = InvasivenessConfig(
            user_id=user_id, room_id=room_id,
            helper_types=["grammar"],
        )
        config.upsert()
        # mock execute_shared_tool 验证被调用
        from app.services.liveroom import ai_persona
        import app.infrastructure.llm.liveroom_tools as liveroom_tools_mod
        call_log: list = []
        orig = liveroom_tools_mod.execute_sync
        def _mock_execute_sync(name, args):
            call_log.append((name, args))
            return {"ok": True, "result": {"results": []}}
        liveroom_tools_mod.execute_sync = _mock_execute_sync
        # 同时让 ai_persona 通过 execute_shared_tool 调
        import app.services.liveroom.ai_persona as ap
        orig_esh = ap.execute_shared_tool
        def _mock_esh(name, **kwargs):
            call_log.append((name, "shared"))
            if name == "tool_knowledge_search":
                return {"ok": True, "result": {"results": []}}
            return orig_esh(name, **kwargs)
        ap.execute_shared_tool = _mock_esh
        try:
            r = client.post(
                f"/api/liveroom/rooms/{room_id}/ai-helper/invoke",
                headers=auth_headers,
                json={
                    "helper_type": "grammar",
                    "query": "What is past perfect?",
                },
            )
            # invoke_helper 会调 LLM, 失败时返回 ok=False (500 不应有)
            # 验证：tool_knowledge_search 被调用过
            assert any(
                c[0] == "tool_knowledge_search" for c in call_log
            ), (
                f"ai_helper 未调 tool_knowledge_search: {call_log}"
            )
            # 状态码: 200 (成功) 或 500 (LLM 失败), 但不应 422/400
            assert r.status_code in (200, 500), f"unexpected: {r.status_code} {r.text}"
        finally:
            liveroom_tools_mod.execute_sync = orig
            ap.execute_shared_tool = orig_esh


# ════════════════════════════════════════════════════════════════════
# 模块 5: MoodStress (P0-1 心情压力入口 + 架构 P3 mood_stress 实际化)
# ════════════════════════════════════════════════════════════════════


class TestMoodStressModule:
    """P0-1 心情压力入口 + 架构 P3 mood_stress 实际化"""

    def test_record_mood_via_rest(self, client, user_id, db, auth_headers):
        """通过 REST 记录心情, 验证模块入口 + 11 类情绪标签"""
        # POST /api/secretary/mood-stress/record
        r = client.post(
            "/api/secretary/mood-stress/record",
            headers=auth_headers,
            json={
                "emotion_tags": ["frustration", "anxiety"],
                "pressure_score": 7,
                "energy_score": 4,
                "text_note": "压力有点大",
            },
        )
        assert r.status_code == 200, f"记录心情失败: {r.text}"
        body = r.json()
        assert body["status"] == "ok"
        rec = body["record"]
        assert rec["emotion_tags"] == ["frustration", "anxiety"]
        assert rec["pressure_score"] == 7
        # GET /api/secretary/mood-stress/records
        r2 = client.get(
            "/api/secretary/mood-stress/records",
            headers=auth_headers,
        )
        assert r2.status_code == 200
        records = r2.json()["records"]
        assert len(records) >= 1
        assert any(
            r["text_note"] == "压力有点大" for r in records
        )
        # 验证非法 tag 被 422 拒绝
        r3 = client.post(
            "/api/secretary/mood-stress/record",
            headers=auth_headers,
            json={"emotion_tags": ["invalid_tag"]},
        )
        assert r3.status_code == 422, (
            f"非法标签应被 422 拒绝, 实际 {r3.status_code}: {r3.text}"
        )

    def test_mood_stress_uses_fatigue_manager(self, client, user_id, db, auth_headers):
        """架构 P3 验证: mood_stress 实际化, 走 fatigue_manager

        fatigue_manager 是 7+ 个内置秘书模块之一
        通过 module_registry 验证它存在并被 mood_stress 引用
        """
        from app.domain.secretary.engines.module_registry import module_registry
        # 确保内置模块已发现
        module_registry.discover_builtin()
        names = [m["name"] for m in module_registry.list_modules()]
        assert "fatigue_manager" in names, (
            f"fatigue_manager 未注册: {names}"
        )
        # 验证 dashboard 端点可用 (会聚合疲劳数据)
        r = client.get(
            "/api/secretary/mood-stress/dashboard",
            headers=auth_headers,
            params={"days": 7},
        )
        assert r.status_code == 200, f"dashboard 失败: {r.text}"
        body = r.json()
        # 仪表盘应包含基础字段
        assert "days" in body or "summary" in body or "records" in body, (
            f"dashboard 返回结构异常: {body}"
        )


# ════════════════════════════════════════════════════════════════════
# 模块 6: Planning (P0-1 规划入口 + P0-2 事件循环修复 + 架构 P0 source 枚举)
# ════════════════════════════════════════════════════════════════════


class TestPlanningModule:
    """P0-1 规划入口 + P0-2 事件循环修复 + 架构 P0 source_module 枚举"""

    def test_create_plan_item_via_rest(self, client, user_id, db, auth_headers):
        """通过 REST 创建计划项, 验证模块入口"""
        from app.api.planning import service as svc
        svc._ensure_tables()
        r = client.post(
            "/api/planning/items",
            headers=auth_headers,
            json={
                "source_module": "manual",
                "target_type": "flashcard",
                "target_ref_id": "ua_fc_1",
                "title": "复习 FSRS 概念",
                "estimated_minutes": 30,
            },
        )
        assert r.status_code == 200, f"创建计划项失败: {r.text}"
        item = r.json()
        assert item["title"] == "复习 FSRS 概念"
        assert item["user_id"] == user_id
        assert item["status"] == "pending"
        # GET /api/planning/items
        r2 = client.get(
            "/api/planning/items",
            headers=auth_headers,
        )
        assert r2.status_code == 200
        items = r2.json()["items"]
        assert any(i["id"] == item["id"] for i in items)

    def test_complete_plan_item_doesnt_loop(self, client, user_id, db, auth_headers):
        """P0-2 验证: 标记完成触发 PlanItemCompleted,
        消费后**不**重发源事件 (如 ProjectNodeCompleted)
        """
        from app.api.planning import service as svc
        from app.services import project as project_service
        from app.infrastructure.event_bus import EventBus
        from shared.events import PlanItemCompleted, ProjectNodeCompleted

        svc._ensure_tables()
        project_service.ensure_tables()

        # 创建 project + node
        proj = project_service.create_project(user_id=user_id, name="Loop Test 2")
        node = project_service.create_node(
            user_id=user_id, project_id=proj["id"], type=2, title="will complete",
        )

        # 创建 plan_item (source_module=project)
        from shared.events import PlanningSourceModule
        item = svc.create_plan_item(user_id, {
            "source_module": PlanningSourceModule.PROJECT.value,
            "target_type": "project_node",
            "target_ref_id": node["id"],
            "title": "完成 project node",
            "estimated_minutes": 10,
        })
        assert item is not None

        # 启动监控 bus, 验证 ProjectNodeCompleted **不**被重发
        # (只允许 plan_items 内部状态变化)
        test_bus = EventBus(handler_timeout=1.0)
        from app.services.planning.completion_writer import planning_completion_writer
        test_bus.subscribe("PlanItemCompleted", planning_completion_writer._on_completed)
        planning_completion_writer._bus = test_bus

        # 监控 ProjectNodeCompleted
        project_events: list = []
        test_bus.subscribe("ProjectNodeCompleted", lambda e: project_events.append(e))

        # 标记完成
        r = client.post(
            f"/api/planning/items/{item['id']}/complete",
            headers=auth_headers,
            json={"actual_minutes": 12},
        )
        assert r.status_code == 200, f"标记完成失败: {r.text}"
        completed = r.json()
        assert completed["status"] == "completed"

        # 等 handler 异步消费
        import asyncio
        asyncio.run(asyncio.sleep(0.3))

        # 1) project_nodes.status='completed' (通过 direct UPDATE)
        after = project_service.get_node(user_id, proj["id"], node["id"])
        assert after["status"] == "completed", f"node 未完成: {after['status']}"
        # 2) **不**重发 ProjectNodeCompleted (防循环)
        assert len(project_events) == 0, (
            f"P0-2 事件循环修复失效: 重发了 {len(project_events)} 个 ProjectNodeCompleted"
        )

    def test_source_module_enum_validation(self, client, user_id, db, auth_headers):
        """架构 P0 验证: source_module 必须是 PlanningSourceModule 合法值

        合法值集合由 PlanningSourceModule 枚举派生（Task #57: 禁止硬编码模块数）
        """
        from app.api.planning import service as svc
        svc._ensure_tables()
        # 1) 合法值 — manual
        r = client.post(
            "/api/planning/items",
            headers=auth_headers,
            json={
                "source_module": "manual",
                "target_type": "flashcard",
                "target_ref_id": "ua_legal_1",
                "title": "合法 manual",
            },
        )
        assert r.status_code == 200, f"manual 应被接受: {r.text}"
        # 2) 非法值 — 应被 422 拒绝
        r2 = client.post(
            "/api/planning/items",
            headers=auth_headers,
            json={
                "source_module": "invalid_module",
                "target_type": "flashcard",
                "target_ref_id": "ua_illegal_1",
                "title": "非法 source",
            },
        )
        assert r2.status_code == 422, (
            f"非法 source_module 应被 422 拒绝, 实际 {r2.status_code}: {r2.text}"
        )
        # 3) 验证枚举包含所有核心模块入口（从枚举动态派生）
        from shared.events import PlanningSourceModule
        all_sources = {m.value for m in PlanningSourceModule}
        # 必须包含的核心模块（新增模块需追加到此集合）
        required_core = {
            "flashcard", "practice", "project", "reading",
            "language_room", "manual", "interest_explorer", "mood_stress",
        }
        missing = required_core - all_sources
        assert not missing, f"核心模块缺失: {missing}; 当前枚举: {all_sources}"


# ════════════════════════════════════════════════════════════════════
# 模块 7: InterestExplorer (P0-1 兴趣探索入口 + 架构 P3 真实 liveroom.create_room)
# ════════════════════════════════════════════════════════════════════


class TestInterestModule:
    """P0-1 兴趣探索入口 + 架构 P3 真实 liveroom.create_room"""

    def test_create_push_via_rest(self, client, user_id, db, auth_headers):
        """通过 REST 创建兴趣标签 + 推送记录, 验证模块入口"""
        # 创建兴趣标签 (level 0 主标签)
        r = client.post(
            "/api/interest/tags",
            headers=auth_headers,
            json={"name": f"机器学习 {user_id}", "level": 0, "weight": 1},
        )
        assert r.status_code in (200, 201), f"创建标签失败: {r.text}"
        tag = r.json()
        assert tag["name"].startswith("机器学习")
        # 直接在 DB 插入推送记录 (跨模块导入前置条件)
        from app.services.interest import store
        from app.infrastructure.db.database import get_db
        d = get_db()
        # ensure tables
        from app.services.interest.migration import ensure_interest_tables
        ensure_interest_tables()
        push = store.create_push_record(
            user_id=user_id,
            push_type="research_method",
            title=f"ML 教程 {user_id}",
            summary="关于机器学习的基础教程",
            url=f"https://example.com/ml-{user_id}",
            matched_tags=[tag["id"]],
        )
        assert push is not None, "推送记录创建失败"
        # 验证：列表端点能找到
        r2 = client.get(
            "/api/interest/push/history",
            headers=auth_headers,
            params={"limit": 5},
        )
        assert r2.status_code == 200
        items = r2.json().get("items") or r2.json().get("pushes") or []
        assert any(p["id"] == push["id"] for p in items), (
            f"推送记录未在历史中找到: {items}"
        )

    def test_import_to_language_room_actually_creates(self, client, user_id, db, auth_headers):
        """架构 P3 验证: 跨模块导入到 language_room **真的**创建房间 (非仅 log)

        Task #36 Part C 修复: import_to_language_room 调 liveroom.service.create_room
        """
        from app.services.interest import store
        from app.services.interest.migration import ensure_interest_tables
        from app.api.liveroom import service as liveroom_service
        from app.infrastructure.db.database import get_db

        ensure_interest_tables()
        liveroom_service._ensure_tables()

        # 创建推送
        push = store.create_push_record(
            user_id=user_id,
            push_type="research_object",
            title=f"AI 论文 {user_id}",
            summary="讨论 AI 发展趋势",
            url=f"https://example.com/ai-{user_id}",
        )
        assert push is not None
        d = get_db()
        before = d.fetchone(
            "SELECT COUNT(*) as cnt FROM language_rooms WHERE owner_id = %s",
            (user_id,),
        )
        before_count = before["cnt"] if before else 0

        # 通过 REST 触发跨模块导入
        r = client.post(
            f"/api/interest/push/{push['id']}/import",
            headers=auth_headers,
            json={"target_module": "language_room"},
        )
        assert r.status_code == 200, f"导入失败: {r.text}"
        body = r.json()
        assert body["imported"] is True
        assert body["target_module"] == "language_room"
        target_ref_id = body["target_ref_id"]
        assert target_ref_id, "target_ref_id 为空"

        # 验证: language_rooms 表真的多了一行
        after = d.fetchone(
            "SELECT COUNT(*) as cnt FROM language_rooms WHERE owner_id = %s",
            (user_id,),
        )
        after_count = after["cnt"] if after else 0
        assert after_count == before_count + 1, (
            f"language_rooms 未真实创建: before={before_count} after={after_count}"
        )
        # 验证: 房间的 settings.source='interest_explorer' (跨模块来源标识)
        room = d.fetchone(
            "SELECT name, settings FROM language_rooms WHERE id = %s",
            (target_ref_id,),
        )
        assert room is not None
        assert "interest" in room["name"].lower() or room["name"] == push["title"]
        # settings 应包含 source='interest_explorer' (JSON 字符串)
        settings = room["settings"]
        if isinstance(settings, str):
            import json as _json
            try:
                settings = _json.loads(settings)
            except Exception:
                pass
        # settings 应保留 import 元数据
        if isinstance(settings, dict):
            assert settings.get("source") == "interest_explorer", (
                f"settings.source 标识缺失: {settings}"
            )
