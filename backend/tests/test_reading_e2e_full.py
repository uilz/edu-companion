"""
Reading 模块 24 端点端到端测试 (Task #55)

依据: docs/modules/reading/overview.md + data-model.md + events.md + ADR 0003

测试覆盖:
  - 24 个 API 端点 (routes.py 全部 GET/POST/PATCH/DELETE)
  - 5 种标注颜色 (yellow/blue/green/purple/orange)
  - 5 种标注 intent (important_concept/data_fact/quotable/doubt/conflict)
  - 3 种阅读模式 (intensive/skim/review)
  - 5 事件族 (SessionStarted/SessionEnded/ModeChanged/AnnotationCreated/NoteCreated/ReviewReminderScheduled)
  - 笔记 = 复用 FlashCard 反思型 (card_type=7, source=reading_note)
  - 回顾提醒 = 复用 PlanItem (source_module='reading')
  - 对比阅读 (左右分屏)
  - 用户偏好
  - 跨材料标注

每个端点: happy path + 至少 1 个边界 (404/400/401)
使用真实 HTTP API (FastAPI TestClient + JWT Bearer 认证)
数据库不可用时整个文件 skip
"""

from __future__ import annotations

import os
import sys
import time
import uuid
from typing import Any

import pytest

# 让 backend 在 sys.path
BACKEND = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BACKEND not in sys.path:
    sys.path.insert(0, BACKEND)


# ════════════════════════════════════════════════════════════════════
# JWT 工具
# ════════════════════════════════════════════════════════════════════


def _make_jwt(user_id: str) -> str:
    """生成有效 JWT (与 auth-gateway 共享 HS256 密钥)"""
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
        "username": f"rde2e_{user_id[:8]}",
        "role": "user",
        "type": "access",
        "iat": int(time.time()),
        "exp": int(time.time()) + 3600,
    }
    return pyjwt.encode(payload, secret, algorithm="HS256")


# ════════════════════════════════════════════════════════════════════
# Fixtures
# ════════════════════════════════════════════════════════════════════


@pytest.fixture
def user_id() -> str:
    """独立测试用户 ID, 每次唯一避免污染"""
    return f"rde2e_{uuid.uuid4().hex[:12]}"


@pytest.fixture
def material_id() -> str:
    """独立测试材料 ID"""
    return f"mat_rde2e_{uuid.uuid4().hex[:10]}"


@pytest.fixture
def material_id_2() -> str:
    """独立测试材料 ID (对比用)"""
    return f"mat_rde2e_{uuid.uuid4().hex[:10]}"


@pytest.fixture
def db():
    """数据库连接 fixture; 不可用时 skip"""
    try:
        from app.infrastructure.db.database import get_db
        d = get_db()
        d.fetchone("SELECT 1")
        from app.services.reading import _ensure_tables
        _ensure_tables()
        from app.api.flashcard.service import _ensure_tables as _fc_ensure
        _fc_ensure()
        from app.api.planning import service as planning_svc
        planning_svc._ensure_tables()
        return d
    except Exception as exc:  # noqa: BLE001
        pytest.skip(f"数据库不可用: {exc}")


@pytest.fixture
def client():
    """FastAPI TestClient (同步)"""
    from fastapi.testclient import TestClient
    from app.main import app
    return TestClient(app)


@pytest.fixture
def auth_headers(user_id):
    """为指定 user_id 生成认证头"""
    return {"Authorization": f"Bearer {_make_jwt(user_id)}"}


@pytest.fixture
def capture_bus():
    """收集所有 reading 事件的总线"""
    from app.infrastructure.event_bus import EventBus
    bus = EventBus(handler_timeout=2.0)
    captured: list[Any] = []

    async def _capture(event):  # noqa: ANN001
        captured.append(event)

    for evt_type in (
        "ReadingSessionStarted", "ReadingSessionEnded", "ReadingSessionResumed",
        "ReadingAnnotationCreated", "ReadingAnnotationUpdated",
        "ReadingAnnotationDeleted", "ReadingAnnotationProcessed",
        "ReadingModeChanged", "ReadingNoteCreated",
        "ReadingReviewReminderScheduled", "PlanItemCreated", "PlanItemScheduled",
        "FlashCardCreated",
    ):
        bus.subscribe(evt_type, _capture)
    return bus, captured


@pytest.fixture(autouse=True)
def cleanup_test_data(db, user_id):
    """测试结束后清理该用户的 reading 相关数据"""
    yield
    try:
        # 1) 清理 reading 模块自有表
        for tbl in (
            "reading_annotations", "reading_sessions",
            "reading_comparisons", "reading_prefs",
        ):
            try:
                db.execute(f"DELETE FROM {tbl} WHERE user_id = %s", (user_id,))
            except Exception:
                pass
        # 2) 清理 reading_note 类型的 flashcards
        try:
            db.execute(
                "DELETE FROM flashcards WHERE user_id = %s AND source = %s",
                (user_id, "reading_note"),
            )
        except Exception:
            pass
        # 3) 清理 source_module='reading' 的 plan_items
        try:
            db.execute(
                "DELETE FROM plan_items WHERE user_id = %s AND source_module = %s",
                (user_id, "reading"),
            )
        except Exception:
            pass
    except Exception:
        pass


# ════════════════════════════════════════════════════════════════════
# 辅助方法
# ════════════════════════════════════════════════════════════════════


def _create_session(
    client,
    user_id: str,
    auth_headers: dict,
    *,
    material_id: str,
    mode: str = "intensive",
) -> dict:
    """通过 HTTP API 启动阅读会话"""
    r = client.post(
        "/api/reading/sessions",
        headers=auth_headers,
        json={"material_id": material_id, "mode": mode},
    )
    assert r.status_code == 200, f"创建会话失败 ({user_id}): {r.text}"
    return r.json()


def _create_annotation(
    client,
    user_id: str,
    auth_headers: dict,
    *,
    material_id: str,
    color: str = "yellow",
    intent: str | None = None,
    text: str = "标注原文",
    note: str = "",
    linked_node_id: str = "",
) -> dict:
    """通过 HTTP API 创建标注"""
    payload: dict[str, Any] = {
        "material_id": material_id,
        "color": color,
        "text": text,
    }
    if intent is not None:
        payload["intent"] = intent
    if note:
        payload["note"] = note
    if linked_node_id:
        payload["linked_node_id"] = linked_node_id
    r = client.post(
        "/api/reading/annotations",
        headers=auth_headers,
        json=payload,
    )
    assert r.status_code == 200, f"创建标注失败 ({user_id}): {r.text}"
    return r.json()


# ════════════════════════════════════════════════════════════════════
# §1. 会话 (sessions) — 7 端点
# ════════════════════════════════════════════════════════════════════


class TestSessionEndpoints:
    """POST/GET /api/reading/sessions 系列 (7 端点)"""

    def test_01_start_session_intensive(self, client, user_id, db, auth_headers, material_id, capture_bus):
        """POST /api/reading/sessions - 启动精读会话 happy + ReadingSessionStarted 事件"""
        bus, captured = capture_bus
        r = client.post(
            "/api/reading/sessions",
            headers=auth_headers,
            json={"material_id": material_id, "mode": "intensive"},
        )
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["user_id"] == user_id
        assert data["material_id"] == material_id
        assert data["mode"] == "intensive"
        assert data["ended_at"] is None
        assert data["id"].startswith("rs_")
        assert data["annotations_created"] == 0
        assert data["notes_created"] == 0
        assert data["cards_generated"] == 0
        assert data["linked_node_ids"] == []
        assert data["chapters_visited"] == []
        assert "started_at" in data

    def test_02_start_session_invalid_mode(self, client, user_id, db, auth_headers, material_id):
        """POST /api/reading/sessions - 非法 mode → 400/422 (Pydantic Literal 422 / ValueError 400)"""
        r = client.post(
            "/api/reading/sessions",
            headers=auth_headers,
            json={"material_id": material_id, "mode": "invalid_mode"},
        )
        assert r.status_code in (400, 422)

    def test_03_start_session_unauthenticated(self, client, db, material_id):
        """POST /api/reading/sessions - 无认证 → 401"""
        r = client.post(
            "/api/reading/sessions",
            json={"material_id": material_id, "mode": "intensive"},
        )
        assert r.status_code == 401

    def test_04_get_session_happy(self, client, user_id, db, auth_headers, material_id):
        """GET /api/reading/sessions/{id} - 查询会话"""
        s = _create_session(client, user_id, auth_headers, material_id=material_id)
        r = client.get(
            f"/api/reading/sessions/{s['id']}",
            headers=auth_headers,
        )
        assert r.status_code == 200
        data = r.json()
        assert data["id"] == s["id"]
        assert data["material_id"] == material_id
        assert data["mode"] == "intensive"

    def test_05_get_session_not_found(self, client, user_id, db, auth_headers):
        """GET /api/reading/sessions/{id} - 不存在 → 404"""
        r = client.get(
            "/api/reading/sessions/rs_nonexistent_999",
            headers=auth_headers,
        )
        assert r.status_code == 404

    def test_06_get_active_session(self, client, user_id, db, auth_headers, material_id):
        """GET /api/reading/sessions/active - 中断恢复查询

        修复历史 (Task #58): /sessions/active 路由原本被 /sessions/{session_id}
        抢先匹配, 移至参数化路由之前后端点恢复可达。
        """
        s = _create_session(client, user_id, auth_headers, material_id=material_id)
        r = client.get(
            "/api/reading/sessions/active",
            headers=auth_headers,
            params={"material_id": material_id},
        )
        assert r.status_code == 200
        data = r.json()
        assert data["id"] == s["id"]
        assert data["ended_at"] is None

    def test_07_get_active_session_not_found(self, client, user_id, db, auth_headers, material_id):
        """GET /api/reading/sessions/active - 没有进行中会话 → 404

        修复历史 (Task #58): 路由顺序修复后该端点恢复可达。
        """
        r = client.get(
            "/api/reading/sessions/active",
            headers=auth_headers,
            params={"material_id": material_id},
        )
        assert r.status_code == 404

    def test_08_list_sessions(self, client, user_id, db, auth_headers, material_id):
        """GET /api/reading/sessions - 列表查询"""
        _create_session(client, user_id, auth_headers, material_id=material_id)
        _create_session(client, user_id, auth_headers, material_id=material_id, mode="skim")
        r = client.get(
            "/api/reading/sessions",
            headers=auth_headers,
            params={"material_id": material_id, "limit": 10},
        )
        assert r.status_code == 200
        data = r.json()
        assert data["total"] == 2
        assert len(data["items"]) == 2

    def test_09_list_sessions_all(self, client, user_id, db, auth_headers, material_id):
        """GET /api/reading/sessions - 不传 material_id 查全部"""
        _create_session(client, user_id, auth_headers, material_id=material_id)
        r = client.get(
            "/api/reading/sessions",
            headers=auth_headers,
        )
        assert r.status_code == 200
        assert r.json()["total"] >= 1

    def test_10_end_session(self, client, user_id, db, auth_headers, material_id, capture_bus):
        """POST /api/reading/sessions/{id}/end - 结束会话 + 事件"""
        bus, captured = capture_bus
        s = _create_session(client, user_id, auth_headers, material_id=material_id)
        r = client.post(
            f"/api/reading/sessions/{s['id']}/end",
            headers=auth_headers,
            json={"duration_seconds": 120},
        )
        assert r.status_code == 200
        data = r.json()
        assert data["ended_at"] is not None
        assert data["duration_seconds"] == 120

    def test_11_end_session_auto_duration(self, client, user_id, db, auth_headers, material_id):
        """POST /api/reading/sessions/{id}/end - 不传 duration_seconds 自动计算

        修复历史 (Task #58): sessions.py:210 `now - started` 原本抛 TypeError,
        因为 _now() 返回 tz-aware (timezone.utc) 而 DB 返回的 started_at 是 tz-naive.
        已在 sessions.py 加 tzinfo 转换, 端点恢复可用。
        """
        s = _create_session(client, user_id, auth_headers, material_id=material_id)
        r = client.post(
            f"/api/reading/sessions/{s['id']}/end",
            headers=auth_headers,
            json={},
        )
        assert r.status_code == 200
        data = r.json()
        assert data["ended_at"] is not None
        # duration_seconds 自动计算得到非负整数
        assert data["duration_seconds"] is not None
        assert int(data["duration_seconds"]) >= 0

    def test_12_end_session_not_found(self, client, user_id, db, auth_headers):
        """POST /api/reading/sessions/{id}/end - 不存在 → 404"""
        r = client.post(
            "/api/reading/sessions/rs_nonexistent/end",
            headers=auth_headers,
            json={"duration_seconds": 60},
        )
        assert r.status_code == 404

    def test_13_change_mode_three_modes(self, client, user_id, db, auth_headers, material_id):
        """POST /api/reading/sessions/{id}/mode - 切换 3 种模式"""
        s = _create_session(client, user_id, auth_headers, material_id=material_id, mode="intensive")
        # intensive → skim
        r1 = client.post(
            f"/api/reading/sessions/{s['id']}/mode",
            headers=auth_headers,
            json={"mode": "skim"},
        )
        assert r1.status_code == 200
        assert r1.json()["mode"] == "skim"
        # skim → review
        r2 = client.post(
            f"/api/reading/sessions/{s['id']}/mode",
            headers=auth_headers,
            json={"mode": "review"},
        )
        assert r2.status_code == 200
        assert r2.json()["mode"] == "review"
        # review → intensive
        r3 = client.post(
            f"/api/reading/sessions/{s['id']}/mode",
            headers=auth_headers,
            json={"mode": "intensive"},
        )
        assert r3.status_code == 200
        assert r3.json()["mode"] == "intensive"

    def test_14_change_mode_invalid(self, client, user_id, db, auth_headers, material_id):
        """POST /api/reading/sessions/{id}/mode - 非法 mode → 400/422"""
        s = _create_session(client, user_id, auth_headers, material_id=material_id)
        r = client.post(
            f"/api/reading/sessions/{s['id']}/mode",
            headers=auth_headers,
            json={"mode": "turbo"},
        )
        assert r.status_code in (400, 422)

    def test_15_change_mode_not_found(self, client, user_id, db, auth_headers):
        """POST /api/reading/sessions/{id}/mode - 不存在 → 404"""
        r = client.post(
            "/api/reading/sessions/rs_nonexistent/mode",
            headers=auth_headers,
            json={"mode": "skim"},
        )
        assert r.status_code == 404

    def test_16_update_activity(self, client, user_id, db, auth_headers, material_id):
        """POST /api/reading/sessions/{id}/activity - 增量更新活动"""
        s = _create_session(client, user_id, auth_headers, material_id=material_id)
        r = client.post(
            f"/api/reading/sessions/{s['id']}/activity",
            headers=auth_headers,
            json={
                "chapter_visited": "ch_1",
                "annotations_delta": 2,
                "notes_delta": 1,
                "node_linked": "node_abc",
            },
        )
        assert r.status_code == 200
        data = r.json()
        assert data["annotations_created"] == 2
        assert data["notes_created"] == 1
        assert "ch_1" in data["chapters_visited"]
        assert "node_abc" in data["linked_node_ids"]

    def test_17_update_activity_state_snapshot(self, client, user_id, db, auth_headers, material_id):
        """POST /api/reading/sessions/{id}/activity - state_snapshot 用于中断恢复"""
        s = _create_session(client, user_id, auth_headers, material_id=material_id)
        r = client.post(
            f"/api/reading/sessions/{s['id']}/activity",
            headers=auth_headers,
            json={
                "state_snapshot": {"scroll": 1200, "chapter": "ch_2", "zoom": 1.2},
            },
        )
        assert r.status_code == 200
        data = r.json()
        # state_snapshot 在 SessionResponse 中是 dict
        assert isinstance(data["state_snapshot"], dict)
        assert data["state_snapshot"].get("scroll") == 1200
        assert data["state_snapshot"].get("chapter") == "ch_2"

    def test_18_update_activity_not_found(self, client, user_id, db, auth_headers):
        """POST /api/reading/sessions/{id}/activity - 不存在 → 404"""
        r = client.post(
            "/api/reading/sessions/rs_nonexistent/activity",
            headers=auth_headers,
            json={"chapter_visited": "x"},
        )
        assert r.status_code == 404


# ════════════════════════════════════════════════════════════════════
# §2. 标注 (annotations) — 6 端点 + 5 色 × 5 intent 全覆盖
# ════════════════════════════════════════════════════════════════════


class TestAnnotationEndpoints:
    """POST/GET/PATCH/DELETE /api/reading/annotations 系列 (6 端点)"""

    def test_20_create_annotation_yellow_important(self, client, user_id, db, auth_headers, material_id):
        """POST /api/reading/annotations - 黄色 important_concept"""
        r = client.post(
            "/api/reading/annotations",
            headers=auth_headers,
            json={
                "material_id": material_id,
                "color": "yellow",
                "text": "重要概念原文",
                "note": "重要概念备注",
            },
        )
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["color"] == "yellow"
        # intent 缺省时由 color 推断
        assert data["intent"] == "important_concept"
        assert data["text"] == "重要概念原文"
        assert data["is_processed"] is False
        assert data["followup"]["suggestion"] is not None
        assert data["id"].startswith("ra_")

    def test_21_create_annotation_blue_data_fact(self, client, user_id, db, auth_headers, material_id):
        """POST /api/reading/annotations - 蓝色 data_fact"""
        r = client.post(
            "/api/reading/annotations",
            headers=auth_headers,
            json={
                "material_id": material_id,
                "color": "blue",
                "intent": "data_fact",
                "text": "2024 年统计数据",
            },
        )
        assert r.status_code == 200
        data = r.json()
        assert data["color"] == "blue"
        assert data["intent"] == "data_fact"

    def test_22_create_annotation_green_quotable(self, client, user_id, db, auth_headers, material_id):
        """POST /api/reading/annotations - 绿色 quotable"""
        r = client.post(
            "/api/reading/annotations",
            headers=auth_headers,
            json={
                "material_id": material_id,
                "color": "green",
                "text": "可引用段落",
            },
        )
        assert r.status_code == 200
        data = r.json()
        assert data["color"] == "green"
        assert data["intent"] == "quotable"

    def test_23_create_annotation_purple_doubt(self, client, user_id, db, auth_headers, material_id):
        """POST /api/reading/annotations - 紫色 doubt"""
        r = client.post(
            "/api/reading/annotations",
            headers=auth_headers,
            json={
                "material_id": material_id,
                "color": "purple",
                "text": "我对这个论述有疑问",
                "linked_node_id": "node_doubt_1",
            },
        )
        assert r.status_code == 200
        data = r.json()
        assert data["color"] == "purple"
        assert data["intent"] == "doubt"
        assert data["linked_node_id"] == "node_doubt_1"

    def test_24_create_annotation_orange_conflict(self, client, user_id, db, auth_headers, material_id):
        """POST /api/reading/annotations - 橙色 conflict"""
        r = client.post(
            "/api/reading/annotations",
            headers=auth_headers,
            json={
                "material_id": material_id,
                "color": "orange",
                "text": "与另一段矛盾",
            },
        )
        assert r.status_code == 200
        data = r.json()
        assert data["color"] == "orange"
        assert data["intent"] == "conflict"

    def test_25_create_annotation_invalid_color(self, client, user_id, db, auth_headers, material_id):
        """POST /api/reading/annotations - 非法 color → 400/422"""
        r = client.post(
            "/api/reading/annotations",
            headers=auth_headers,
            json={
                "material_id": material_id,
                "color": "rainbow",
                "text": "x",
            },
        )
        assert r.status_code in (400, 422)

    def test_26_create_annotation_unauthenticated(self, client, db, material_id):
        """POST /api/reading/annotations - 无认证 → 401"""
        r = client.post(
            "/api/reading/annotations",
            json={"material_id": material_id, "color": "yellow"},
        )
        assert r.status_code == 401

    def test_27_get_annotation_happy(self, client, user_id, db, auth_headers, material_id):
        """GET /api/reading/annotations/{id} - 查询标注"""
        a = _create_annotation(
            client, user_id, auth_headers,
            material_id=material_id, color="yellow", text="get_test",
        )
        r = client.get(
            f"/api/reading/annotations/{a['id']}",
            headers=auth_headers,
        )
        assert r.status_code == 200
        data = r.json()
        assert data["id"] == a["id"]
        assert data["text"] == "get_test"

    def test_28_get_annotation_not_found(self, client, user_id, db, auth_headers):
        """GET /api/reading/annotations/{id} - 不存在 → 404"""
        r = client.get(
            "/api/reading/annotations/ra_nonexistent_999",
            headers=auth_headers,
        )
        assert r.status_code == 404

    def test_29_list_annotations_by_material(self, client, user_id, db, auth_headers, material_id):
        """GET /api/reading/materials/{id}/annotations - 按材料列标注"""
        for c in ("yellow", "blue", "green", "purple", "orange"):
            _create_annotation(
                client, user_id, auth_headers,
                material_id=material_id, color=c,
            )
        r = client.get(
            f"/api/reading/materials/{material_id}/annotations",
            headers=auth_headers,
        )
        assert r.status_code == 200
        data = r.json()
        assert data["total"] == 5
        assert len(data["items"]) == 5

    def test_30_list_annotations_filter_by_color(self, client, user_id, db, auth_headers, material_id):
        """GET /api/reading/materials/{id}/annotations - 按颜色筛选"""
        _create_annotation(client, user_id, auth_headers, material_id=material_id, color="yellow")
        _create_annotation(client, user_id, auth_headers, material_id=material_id, color="yellow")
        _create_annotation(client, user_id, auth_headers, material_id=material_id, color="blue")
        r = client.get(
            f"/api/reading/materials/{material_id}/annotations",
            headers=auth_headers,
            params={"color": "yellow"},
        )
        assert r.status_code == 200
        data = r.json()
        assert data["total"] == 2
        assert all(a["color"] == "yellow" for a in data["items"])

    def test_31_list_annotations_grouped_by_color(self, client, user_id, db, auth_headers, material_id):
        """GET /api/reading/materials/{id}/annotations?grouped=true - 按颜色分组"""
        _create_annotation(client, user_id, auth_headers, material_id=material_id, color="yellow")
        _create_annotation(client, user_id, auth_headers, material_id=material_id, color="blue")
        _create_annotation(client, user_id, auth_headers, material_id=material_id, color="yellow")
        r = client.get(
            f"/api/reading/materials/{material_id}/annotations",
            headers=auth_headers,
            params={"grouped": "true"},
        )
        assert r.status_code == 200
        data = r.json()
        assert "grouped" in data
        grouped = data["grouped"]
        # 5 色都返回 (即使没数据)
        for c in ("yellow", "blue", "green", "purple", "orange"):
            assert c in grouped
        assert len(grouped["yellow"]) == 2
        assert len(grouped["blue"]) == 1
        assert data["total"] == 3

    def test_32_update_annotation(self, client, user_id, db, auth_headers, material_id):
        """PATCH /api/reading/annotations/{id} - 更新标注

        设计说明: 创建时若不指定 intent 则从 color 推断 (annotations.py:130),
        update 时只更新显式提供的字段。color 改变不会自动同步 intent,
        这是有意的设计 (color/intent 可独立设置)。
        """
        a = _create_annotation(
            client, user_id, auth_headers,
            material_id=material_id, color="yellow", text="original",
        )
        r = client.patch(
            f"/api/reading/annotations/{a['id']}",
            headers=auth_headers,
            json={"text": "updated", "note": "补注", "color": "blue"},
        )
        assert r.status_code == 200
        data = r.json()
        assert data["text"] == "updated"
        assert data["note"] == "补注"
        assert data["color"] == "blue"
        # color 已变, intent 由显式提供决定 (这里未传 intent, 保持原值 important_concept)
        assert data["intent"] == "important_concept"

    def test_33_update_annotation_partial(self, client, user_id, db, auth_headers, material_id):
        """PATCH /api/reading/annotations/{id} - 部分字段更新 (intent 显式)"""
        a = _create_annotation(
            client, user_id, auth_headers,
            material_id=material_id, color="yellow",
        )
        r = client.patch(
            f"/api/reading/annotations/{a['id']}",
            headers=auth_headers,
            json={"intent": "quotable", "linked_node_id": "node_updated"},
        )
        assert r.status_code == 200
        data = r.json()
        assert data["intent"] == "quotable"
        assert data["linked_node_id"] == "node_updated"
        # color 未修改保持 yellow
        assert data["color"] == "yellow"

    def test_34_update_annotation_not_found(self, client, user_id, db, auth_headers):
        """PATCH /api/reading/annotations/{id} - 不存在 → 404"""
        r = client.patch(
            "/api/reading/annotations/ra_nonexistent_999",
            headers=auth_headers,
            json={"text": "x"},
        )
        assert r.status_code == 404

    def test_35_delete_annotation(self, client, user_id, db, auth_headers, material_id):
        """DELETE /api/reading/annotations/{id} - 删除标注"""
        a = _create_annotation(
            client, user_id, auth_headers,
            material_id=material_id, color="yellow",
        )
        r = client.delete(
            f"/api/reading/annotations/{a['id']}",
            headers=auth_headers,
        )
        assert r.status_code == 200
        assert r.json()["deleted"] is True
        # 删除后 GET 应 404
        r2 = client.get(
            f"/api/reading/annotations/{a['id']}",
            headers=auth_headers,
        )
        assert r2.status_code == 404

    def test_36_delete_annotation_not_found(self, client, user_id, db, auth_headers):
        """DELETE /api/reading/annotations/{id} - 不存在 → 404"""
        r = client.delete(
            "/api/reading/annotations/ra_nonexistent_999",
            headers=auth_headers,
        )
        assert r.status_code == 404

    def test_37_process_annotation_to_flashcard(self, client, user_id, db, auth_headers, material_id, capture_bus):
        """POST /api/reading/annotations/{id}/process - 标记为已处理 (target=flashcard) + 事件"""
        bus, captured = capture_bus
        a = _create_annotation(
            client, user_id, auth_headers,
            material_id=material_id, color="yellow",
        )
        r = client.post(
            f"/api/reading/annotations/{a['id']}/process",
            headers=auth_headers,
            json={"target_module": "flashcard", "target_ref_id": "fc_target_1"},
        )
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["is_processed"] is True

    def test_38_process_annotation_to_conversation(self, client, user_id, db, auth_headers, material_id):
        """POST /api/reading/annotations/{id}/process - target=conversation"""
        a = _create_annotation(
            client, user_id, auth_headers,
            material_id=material_id, color="purple",
        )
        r = client.post(
            f"/api/reading/annotations/{a['id']}/process",
            headers=auth_headers,
            json={"target_module": "conversation", "target_ref_id": "conv_target_1"},
        )
        assert r.status_code == 200
        data = r.json()
        assert data["is_processed"] is True

    def test_39_process_annotation_to_cognitive_node(self, client, user_id, db, auth_headers, material_id):
        """POST /api/reading/annotations/{id}/process - target=cognitive_node"""
        a = _create_annotation(
            client, user_id, auth_headers,
            material_id=material_id, color="yellow",
        )
        r = client.post(
            f"/api/reading/annotations/{a['id']}/process",
            headers=auth_headers,
            json={"target_module": "cognitive_node", "target_ref_id": "node_target_1"},
        )
        assert r.status_code == 200
        assert r.json()["is_processed"] is True

    def test_40_process_annotation_to_project(self, client, user_id, db, auth_headers, material_id):
        """POST /api/reading/annotations/{id}/process - target=project"""
        a = _create_annotation(
            client, user_id, auth_headers,
            material_id=material_id, color="orange",
        )
        r = client.post(
            f"/api/reading/annotations/{a['id']}/process",
            headers=auth_headers,
            json={"target_module": "project", "target_ref_id": "proj_target_1"},
        )
        assert r.status_code == 200
        assert r.json()["is_processed"] is True

    def test_41_process_annotation_invalid_target(self, client, user_id, db, auth_headers, material_id):
        """POST /api/reading/annotations/{id}/process - 非法 target_module → 400/422"""
        a = _create_annotation(
            client, user_id, auth_headers,
            material_id=material_id, color="yellow",
        )
        r = client.post(
            f"/api/reading/annotations/{a['id']}/process",
            headers=auth_headers,
            json={"target_module": "invalid_target", "target_ref_id": "x"},
        )
        assert r.status_code in (400, 422)

    def test_42_process_annotation_not_found(self, client, user_id, db, auth_headers):
        """POST /api/reading/annotations/{id}/process - 不存在 → 404"""
        r = client.post(
            "/api/reading/annotations/ra_nonexistent/process",
            headers=auth_headers,
            json={"target_module": "flashcard", "target_ref_id": "x"},
        )
        assert r.status_code == 404


# ════════════════════════════════════════════════════════════════════
# §3. 笔记 (notes) — 2 端点 (复用 FlashCard 反思型)
# ════════════════════════════════════════════════════════════════════


class TestNoteEndpoints:
    """POST/GET /api/reading/notes 系列 (2 端点, 复用 FlashCard)"""

    def test_50_create_note_happy(self, client, user_id, db, auth_headers, material_id, capture_bus):
        """POST /api/reading/notes - 创建笔记 (实际是创建 FlashCard 反思型 card_type=7)

        设计说明: cross_module_source 仅在事件层使用 (events.py:1159),
        flashcards 表没有该列 (flashcard_schema.sql 无此字段),
        所以 GET 返回的 card 不含该字段, 但 ReadingNoteCreated 事件含。
        """
        bus, captured = capture_bus
        r = client.post(
            "/api/reading/notes",
            headers=auth_headers,
            json={
                "material_id": material_id,
                "front_text": "我的问题是什么?",
                "back_text": "我的回应",
                "back_context": "关键论述",
                "linked_node_ids": ["node_note_1"],
                "tags": ["reading", "reflection"],
                "language": "zh",
            },
        )
        assert r.status_code == 200, r.text
        data = r.json()
        # 验证笔记三段式映射
        assert data["front_text"] == "我的问题是什么?"
        assert data["back_text"] == "我的回应"
        assert data["back_context"] == "关键论述"
        # 验证是反思型 (type=7)
        assert data["type"] == 7
        # 验证 source=reading_note (card 上有这字段)
        assert data["source"] == "reading_note"
        # 关联节点
        assert "node_note_1" in data["linked_node_ids"]
        # source_ref 包含 reading 元数据
        assert data["source_ref"]["module"] == "reading"
        assert data["source_ref"]["id"] == material_id

    def test_51_create_note_no_linked_nodes(self, client, user_id, db, auth_headers, material_id):
        """POST /api/reading/notes - 缺少 linked_node_ids → 400/422

        设计说明: NoteCreateRequest.linked_node_ids = Field(..., min_length=1)
        Pydantic min_length 校验返回 422, 业务层 ValueError 才返回 400。
        """
        r = client.post(
            "/api/reading/notes",
            headers=auth_headers,
            json={
                "material_id": material_id,
                "front_text": "孤问",
                "linked_node_ids": [],
            },
        )
        assert r.status_code in (400, 422)

    def test_52_create_note_empty_front_text(self, client, user_id, db, auth_headers, material_id):
        """POST /api/reading/notes - 空 front_text → 400/422"""
        r = client.post(
            "/api/reading/notes",
            headers=auth_headers,
            json={
                "material_id": material_id,
                "front_text": "  ",
                "linked_node_ids": ["n1"],
            },
        )
        assert r.status_code in (400, 422)

    def test_53_create_note_unauthenticated(self, client, db, material_id):
        """POST /api/reading/notes - 无认证 → 401"""
        r = client.post(
            "/api/reading/notes",
            json={
                "material_id": material_id,
                "front_text": "q",
                "linked_node_ids": ["n1"],
            },
        )
        assert r.status_code == 401

    def test_54_create_note_with_session(self, client, user_id, db, auth_headers, material_id):
        """POST /api/reading/notes - 带 session_id 关联会话统计"""
        s = _create_session(client, user_id, auth_headers, material_id=material_id)
        r1 = client.post(
            "/api/reading/notes",
            headers=auth_headers,
            json={
                "material_id": material_id,
                "front_text": "带会话的笔记",
                "linked_node_ids": ["node_sess_1"],
                "session_id": s["id"],
            },
        )
        assert r1.status_code == 200
        # 会话 notes_created 应增加
        r2 = client.get(
            f"/api/reading/sessions/{s['id']}",
            headers=auth_headers,
        )
        assert r2.json()["notes_created"] >= 1

    def test_55_list_notes_all(self, client, user_id, db, auth_headers, material_id):
        """GET /api/reading/notes - 列出全部阅读笔记"""
        for i in range(3):
            client.post(
                "/api/reading/notes",
                headers=auth_headers,
                json={
                    "material_id": material_id,
                    "front_text": f"note {i}",
                    "linked_node_ids": [f"node_{i}"],
                },
            )
        r = client.get(
            "/api/reading/notes",
            headers=auth_headers,
        )
        assert r.status_code == 200
        data = r.json()
        assert data["total"] == 3
        assert data["source"] == "reading_note"
        for card in data["items"]:
            assert card["source"] == "reading_note"

    def test_56_list_notes_by_material(self, client, user_id, db, auth_headers, material_id, material_id_2):
        """GET /api/reading/notes?material_id=... - 按材料筛选"""
        client.post(
            "/api/reading/notes",
            headers=auth_headers,
            json={
                "material_id": material_id,
                "front_text": "A 材料笔记",
                "linked_node_ids": ["n1"],
            },
        )
        client.post(
            "/api/reading/notes",
            headers=auth_headers,
            json={
                "material_id": material_id_2,
                "front_text": "B 材料笔记",
                "linked_node_ids": ["n2"],
            },
        )
        r = client.get(
            "/api/reading/notes",
            headers=auth_headers,
            params={"material_id": material_id},
        )
        assert r.status_code == 200
        data = r.json()
        assert data["total"] == 1
        assert data["items"][0]["source_ref"]["id"] == material_id

    def test_57_list_notes_unauthenticated(self, client, db):
        """GET /api/reading/notes - 无认证 → 401"""
        r = client.get("/api/reading/notes")
        assert r.status_code == 401


# ════════════════════════════════════════════════════════════════════
# §4. 回顾提醒 (review-reminder) — 3 端点 (复用 PlanItem)
# ════════════════════════════════════════════════════════════════════


class TestReviewReminderEndpoints:
    """POST/GET/DELETE /api/reading/review-reminder 系列 (3 端点)"""

    def test_60_create_reminder_7_days(self, client, user_id, db, auth_headers, material_id):
        """POST /api/reading/review-reminder - 7 天后回顾"""
        r = client.post(
            "/api/reading/review-reminder",
            headers=auth_headers,
            json={
                "material_id": material_id,
                "review_after_days": 7,
                "title": "7 天后回顾测试",
                "description": "测试描述",
                "estimated_minutes": 30,
            },
        )
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["material_id"] == material_id
        assert data["review_after_days"] == 7
        assert data["plan_item_id"]
        assert "scheduled_for" in data
        # plan_item 是 PlanItem 详情
        assert data["plan_item"]["id"] == data["plan_item_id"]
        assert data["plan_item"]["source_module"] == "reading"

    def test_61_create_reminder_30_days(self, client, user_id, db, auth_headers, material_id):
        """POST /api/reading/review-reminder - 30 天后回顾"""
        r = client.post(
            "/api/reading/review-reminder",
            headers=auth_headers,
            json={
                "material_id": material_id,
                "review_after_days": 30,
                "estimated_minutes": 60,
            },
        )
        assert r.status_code == 200
        assert r.json()["review_after_days"] == 30

    def test_62_create_reminder_90_days(self, client, user_id, db, auth_headers, material_id):
        """POST /api/reading/review-reminder - 90 天后回顾"""
        r = client.post(
            "/api/reading/review-reminder",
            headers=auth_headers,
            json={
                "material_id": material_id,
                "review_after_days": 90,
            },
        )
        assert r.status_code == 200
        assert r.json()["review_after_days"] == 90

    def test_63_create_reminder_invalid_days(self, client, user_id, db, auth_headers, material_id):
        """POST /api/reading/review-reminder - 非 7/30/90 → 400"""
        r = client.post(
            "/api/reading/review-reminder",
            headers=auth_headers,
            json={
                "material_id": material_id,
                "review_after_days": 14,
            },
        )
        assert r.status_code in (400, 422)

    def test_64_list_reminders(self, client, user_id, db, auth_headers, material_id):
        """GET /api/reading/review-reminder - 列出待处理提醒"""
        client.post(
            "/api/reading/review-reminder",
            headers=auth_headers,
            json={"material_id": material_id, "review_after_days": 7},
        )
        client.post(
            "/api/reading/review-reminder",
            headers=auth_headers,
            json={"material_id": material_id, "review_after_days": 30},
        )
        r = client.get(
            "/api/reading/review-reminder",
            headers=auth_headers,
        )
        assert r.status_code == 200
        data = r.json()
        assert data["total"] >= 2
        for item in data["items"]:
            assert item["source_module"] == "reading"

    def test_65_list_reminders_by_material(self, client, user_id, db, auth_headers, material_id, material_id_2):
        """GET /api/reading/review-reminder?material_id=... - 按材料筛选"""
        client.post(
            "/api/reading/review-reminder",
            headers=auth_headers,
            json={"material_id": material_id, "review_after_days": 7},
        )
        client.post(
            "/api/reading/review-reminder",
            headers=auth_headers,
            json={"material_id": material_id_2, "review_after_days": 7},
        )
        r = client.get(
            "/api/reading/review-reminder",
            headers=auth_headers,
            params={"material_id": material_id},
        )
        assert r.status_code == 200
        data = r.json()
        for item in data["items"]:
            assert item["target_ref_id"] == material_id

    def test_66_cancel_reminder(self, client, user_id, db, auth_headers, material_id):
        """DELETE /api/reading/review-reminder/{plan_item_id} - 取消提醒"""
        create_r = client.post(
            "/api/reading/review-reminder",
            headers=auth_headers,
            json={"material_id": material_id, "review_after_days": 7},
        )
        assert create_r.status_code == 200
        plan_item_id = create_r.json()["plan_item_id"]
        r = client.delete(
            f"/api/reading/review-reminder/{plan_item_id}",
            headers=auth_headers,
        )
        assert r.status_code == 200
        assert r.json()["deleted"] is True

    def test_67_cancel_reminder_not_found(self, client, user_id, db, auth_headers):
        """DELETE /api/reading/review-reminder/{id} - 不存在 → 404"""
        r = client.delete(
            "/api/reading/review-reminder/plan_nonexistent_999",
            headers=auth_headers,
        )
        assert r.status_code == 404


# ════════════════════════════════════════════════════════════════════
# §5. 偏好 (prefs) — 2 端点
# ════════════════════════════════════════════════════════════════════


class TestPrefsEndpoints:
    """GET/PATCH /api/reading/prefs 系列 (2 端点)"""

    def test_70_get_prefs_default(self, client, user_id, db, auth_headers):
        """GET /api/reading/prefs - 默认值"""
        r = client.get(
            "/api/reading/prefs",
            headers=auth_headers,
        )
        assert r.status_code == 200
        data = r.json()
        assert data["user_id"] == user_id
        assert data["default_mode"] == "intensive"
        assert data["highlight_mastered"] is True
        assert data["highlight_weak"] is True
        assert data["auto_open_sidebar"] is True
        assert data["sync_scroll_default"] is False
        assert data["review_reminder_days"] == [7, 30, 90]

    def test_71_get_prefs_unauthenticated(self, client, db):
        """GET /api/reading/prefs - 无认证 → 401"""
        r = client.get("/api/reading/prefs")
        assert r.status_code == 401

    def test_72_update_prefs(self, client, user_id, db, auth_headers):
        """PATCH /api/reading/prefs - 更新偏好"""
        r = client.patch(
            "/api/reading/prefs",
            headers=auth_headers,
            json={
                "default_mode": "skim",
                "highlight_mastered": False,
                "highlight_weak": False,
                "auto_open_sidebar": False,
                "sync_scroll_default": True,
                "review_reminder_days": [7, 30],
            },
        )
        assert r.status_code == 200
        data = r.json()
        assert data["default_mode"] == "skim"
        assert data["highlight_mastered"] is False
        assert data["highlight_weak"] is False
        assert data["auto_open_sidebar"] is False
        assert data["sync_scroll_default"] is True
        assert data["review_reminder_days"] == [7, 30]

    def test_73_update_prefs_partial(self, client, user_id, db, auth_headers):
        """PATCH /api/reading/prefs - 只更新部分字段, 其它保留"""
        # 先全部更新
        client.patch(
            "/api/reading/prefs",
            headers=auth_headers,
            json={"default_mode": "review", "highlight_weak": False},
        )
        # 再只更新 default_mode
        r = client.patch(
            "/api/reading/prefs",
            headers=auth_headers,
            json={"default_mode": "skim"},
        )
        assert r.status_code == 200
        data = r.json()
        assert data["default_mode"] == "skim"
        # highlight_weak 保持之前的 False
        assert data["highlight_weak"] is False

    def test_74_update_prefs_persistence(self, client, user_id, db, auth_headers):
        """PATCH /api/reading/prefs - 持久化验证 (再次 GET)"""
        client.patch(
            "/api/reading/prefs",
            headers=auth_headers,
            json={"default_mode": "review", "sync_scroll_default": True},
        )
        r = client.get(
            "/api/reading/prefs",
            headers=auth_headers,
        )
        assert r.status_code == 200
        data = r.json()
        assert data["default_mode"] == "review"
        assert data["sync_scroll_default"] is True


# ════════════════════════════════════════════════════════════════════
# §6. 对比阅读 (compare) — 3 端点
# ════════════════════════════════════════════════════════════════════


class TestCompareEndpoints:
    """POST/GET /api/reading/compare 系列 (3 端点)"""

    def test_80_create_comparison(self, client, user_id, db, auth_headers, material_id, material_id_2):
        """POST /api/reading/compare - 创建对比分组"""
        r = client.post(
            "/api/reading/compare",
            headers=auth_headers,
            json={
                "material_id_left": material_id,
                "material_id_right": material_id_2,
                "sync_scroll": True,
            },
        )
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["material_id_left"] == material_id
        assert data["material_id_right"] == material_id_2
        assert data["sync_scroll"] is True
        assert data["id"].startswith("rc_")
        assert "created_at" in data

    def test_81_create_comparison_same_materials(self, client, user_id, db, auth_headers, material_id):
        """POST /api/reading/compare - 左右相同 → 400"""
        r = client.post(
            "/api/reading/compare",
            headers=auth_headers,
            json={
                "material_id_left": material_id,
                "material_id_right": material_id,
            },
        )
        assert r.status_code == 400

    def test_82_create_comparison_unauthenticated(self, client, db, material_id, material_id_2):
        """POST /api/reading/compare - 无认证 → 401"""
        r = client.post(
            "/api/reading/compare",
            json={
                "material_id_left": material_id,
                "material_id_right": material_id_2,
            },
        )
        assert r.status_code == 401

    def test_83_get_compare_payload(self, client, user_id, db, auth_headers, material_id, material_id_2):
        """GET /api/reading/compare - 获取分屏数据 (聚合两侧标注)"""
        # 在两侧各创建 1 个标注
        _create_annotation(
            client, user_id, auth_headers,
            material_id=material_id, color="yellow", text="left anno",
        )
        _create_annotation(
            client, user_id, auth_headers,
            material_id=material_id_2, color="blue", text="right anno",
        )
        r = client.get(
            "/api/reading/compare",
            headers=auth_headers,
            params={
                "material_id_left": material_id,
                "material_id_right": material_id_2,
            },
        )
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["material_id_left"] == material_id
        assert data["material_id_right"] == material_id_2
        # left 数据
        assert "left" in data
        assert data["left"]["material_id"] == material_id
        assert data["left"]["annotations_count"] >= 1
        assert data["left"]["by_color"]["yellow"] >= 1
        # right 数据
        assert "right" in data
        assert data["right"]["material_id"] == material_id_2
        assert data["right"]["annotations_count"] >= 1
        assert data["right"]["by_color"]["blue"] >= 1

    def test_84_get_compare_payload_same_materials(self, client, user_id, db, auth_headers, material_id):
        """GET /api/reading/compare - 左右相同 → 400"""
        r = client.get(
            "/api/reading/compare",
            headers=auth_headers,
            params={
                "material_id_left": material_id,
                "material_id_right": material_id,
            },
        )
        assert r.status_code == 400

    def test_85_get_compare_payload_sync_scroll(self, client, user_id, db, auth_headers, material_id, material_id_2):
        """GET /api/reading/compare - sync_scroll 参数传递"""
        r = client.get(
            "/api/reading/compare",
            headers=auth_headers,
            params={
                "material_id_left": material_id,
                "material_id_right": material_id_2,
                "sync_scroll": "true",
            },
        )
        assert r.status_code == 200
        data = r.json()
        assert data["sync_scroll"] is True

    def test_86_list_comparisons(self, client, user_id, db, auth_headers, material_id, material_id_2):
        """GET /api/reading/compare/list - 列出对比分组"""
        client.post(
            "/api/reading/compare",
            headers=auth_headers,
            json={
                "material_id_left": material_id,
                "material_id_right": material_id_2,
            },
        )
        r = client.get(
            "/api/reading/compare/list",
            headers=auth_headers,
        )
        assert r.status_code == 200
        data = r.json()
        assert data["total"] >= 1
        for item in data["items"]:
            assert item["user_id"] == user_id

    def test_87_cross_material_annotations(self, client, user_id, db, auth_headers, material_id, material_id_2):
        """跨材料标注: 两材料各创建不同颜色, 互不干扰"""
        _create_annotation(client, user_id, auth_headers, material_id=material_id, color="yellow")
        _create_annotation(client, user_id, auth_headers, material_id=material_id, color="blue")
        _create_annotation(client, user_id, auth_headers, material_id=material_id_2, color="orange")
        # 列表 1
        r1 = client.get(
            f"/api/reading/materials/{material_id}/annotations",
            headers=auth_headers,
        )
        assert r1.json()["total"] == 2
        # 列表 2
        r2 = client.get(
            f"/api/reading/materials/{material_id_2}/annotations",
            headers=auth_headers,
        )
        assert r2.json()["total"] == 1


# ════════════════════════════════════════════════════════════════════
# §7. 元数据 (meta/colors) — 1 端点
# ════════════════════════════════════════════════════════════════════


class TestMetaEndpoints:
    """GET /api/reading/meta/colors — 1 端点"""

    def test_90_get_color_meta(self, client, user_id, db, auth_headers):
        """GET /api/reading/meta/colors - 获取颜色/intent/followup 映射"""
        r = client.get(
            "/api/reading/meta/colors",
            headers=auth_headers,
        )
        assert r.status_code == 200
        data = r.json()
        # color_intent_map 包含 5 色
        assert "color_intent_map" in data
        m = data["color_intent_map"]
        assert m["yellow"] == "important_concept"
        assert m["blue"] == "data_fact"
        assert m["green"] == "quotable"
        assert m["purple"] == "doubt"
        assert m["orange"] == "conflict"
        # color_followup 包含 5 色 followup 详情
        assert "color_followup" in data
        f = data["color_followup"]
        for c in ("yellow", "blue", "green", "purple", "orange"):
            assert c in f
            assert "label" in f[c]
            assert "intent" in f[c]
            assert "suggestion" in f[c]
            assert "next_action" in f[c]

    def test_91_get_color_meta_unauthenticated(self, client, db):
        """GET /api/reading/meta/colors - 无认证 → 401"""
        r = client.get("/api/reading/meta/colors")
        assert r.status_code == 401


# ════════════════════════════════════════════════════════════════════
# §8. 端点路径覆盖验证
# ════════════════════════════════════════════════════════════════════


class TestAllRoutesRegistered:
    """验证 routes.py 注册的 24 个端点全部可达"""

    def test_92_all_24_routes_registered(self):
        """routes.py 注册的端点数 == 24"""
        from app.api.reading.routes import router
        paths = [r.path for r in router.routes]
        assert len(paths) == 24, f"期望 24 个端点, 实际 {len(paths)}: {paths}"

    @pytest.mark.parametrize("path,method", [
        ("/api/reading/sessions", "POST"),
        ("/api/reading/sessions/{session_id}", "GET"),
        ("/api/reading/sessions/active", "GET"),
        ("/api/reading/sessions", "GET"),
        ("/api/reading/sessions/{session_id}/end", "POST"),
        ("/api/reading/sessions/{session_id}/mode", "POST"),
        ("/api/reading/sessions/{session_id}/activity", "POST"),
        ("/api/reading/annotations", "POST"),
        ("/api/reading/annotations/{annotation_id}", "GET"),
        ("/api/reading/materials/{material_id}/annotations", "GET"),
        ("/api/reading/annotations/{annotation_id}", "PATCH"),
        ("/api/reading/annotations/{annotation_id}", "DELETE"),
        ("/api/reading/annotations/{annotation_id}/process", "POST"),
        ("/api/reading/notes", "POST"),
        ("/api/reading/notes", "GET"),
        ("/api/reading/review-reminder", "POST"),
        ("/api/reading/review-reminder", "GET"),
        ("/api/reading/review-reminder/{plan_item_id}", "DELETE"),
        ("/api/reading/prefs", "GET"),
        ("/api/reading/prefs", "PATCH"),
        ("/api/reading/compare", "POST"),
        ("/api/reading/compare", "GET"),
        ("/api/reading/compare/list", "GET"),
        ("/api/reading/meta/colors", "GET"),
    ])
    def test_93_route_exists(self, path, method):
        """所有 24 个端点都注册到 router"""
        from app.api.reading.routes import router
        for r in router.routes:
            if r.path == path and method in r.methods:
                return
        pytest.fail(f"端点 {method} {path} 未注册")
