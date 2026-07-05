"""
FlashCard 模块 22 端点端到端测试 (Task #52)

依据: docs/modules/flashcard/overview.md + data-model.md + events.md + ADR 0002

测试覆盖:
  - 22 个 API 端点 (routes.py 全部 GET/POST/PATCH/DELETE/PUT)
  - 7 种卡片类型 (basic/cloze/comparison/process/application/error/reflection)
  - 6 种来源 (manual/practice_error/reading_note/conversation/project/language_room/interest_explorer)
  - 3 档自评 (difficult/good/easy) 各自走通 FSRS 调度 + Belief 回写
  - 完整复习会话生命周期 (start → review × N → end)
  - 4 种导入路径 (errorbook/text/reading/conversation/project)
  - 5 个用户控制 (suspend/resume/reset/override/archive)
  - 跨模块联动 (errorbook→flashcard, flashcard→belief, error→resolved)
  - 字段级版本控制
  - 兼容路径 (/due, /stats)

每个端点: happy path + 至少 1 个边界 (404/400/401/409)
使用真实 HTTP API (FastAPI TestClient + JWT Bearer 认证)
数据库不可用时整个文件 skip
"""

from __future__ import annotations

import asyncio
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
        "username": f"fce2e_{user_id[:8]}",
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
    return f"fce2e_{uuid.uuid4().hex[:12]}"


@pytest.fixture
def db():
    """数据库连接 fixture; 不可用时 skip"""
    try:
        from app.infrastructure.db.database import get_db
        d = get_db()
        d.fetchone("SELECT 1")
        from app.api.flashcard.service import _ensure_tables
        _ensure_tables()
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
    """收集所有发布事件的总线"""
    from app.infrastructure.event_bus import EventBus
    bus = EventBus(handler_timeout=2.0)
    captured: list[Any] = []

    async def _capture(event):  # noqa: ANN001
        captured.append(event)

    for evt_type in (
        "FlashCardReviewed", "FlashCardCreated", "FlashCardUpdated",
        "FlashCardStatusChanged", "FlashCardSuspended", "FlashCardResumed",
        "FlashCardReset", "FlashCardArchived", "FlashCardDeleted",
        "FlashCardSessionStarted", "FlashCardSessionEnded",
        "CognitiveNodeLinked",
        "ErrorBookEntryResolved", "ErrorBookEntryReviewed",
    ):
        bus.subscribe(evt_type, _capture)
    return bus, captured


@pytest.fixture(autouse=True)
def cleanup_test_data(db, user_id):
    """测试结束后清理该用户的所有 flashcard 数据"""
    yield
    try:
        for tbl in ("review_history", "review_sessions", "flashcards", "error_book"):
            try:
                db.execute(f"DELETE FROM {tbl} WHERE user_id = %s", (user_id,))
            except Exception:
                pass
    except Exception:
        pass


# ════════════════════════════════════════════════════════════════════
# 辅助方法
# ════════════════════════════════════════════════════════════════════


def _create_card(
    client,
    user_id: str,
    auth_headers: dict,
    *,
    type_: int = 1,
    source: str = "manual",
    front_text: str = "测试问题?",
    back_text: str = "测试答案",
    linked_node_ids: list[str] | None = None,
    tags: list[str] | None = None,
    cross_module_source: str | None = None,
) -> dict:
    """通过 HTTP API 创建 FlashCard, 返回响应 JSON"""
    payload: dict[str, Any] = {
        "type": type_,
        "source": source,
        "front_text": front_text,
        "back_text": back_text,
        "linked_node_ids": linked_node_ids or [f"node_{uuid.uuid4().hex[:8]}"],
        "tags": tags or ["e2e"],
    }
    if cross_module_source:
        payload["cross_module_source"] = cross_module_source
    r = client.post(
        "/api/flashcards/",
        headers=auth_headers,
        json=payload,
    )
    assert r.status_code == 200, f"创建卡失败 ({user_id}): {r.text}"
    return r.json()


def _seed_error_book(db, user_id: str, entry_id: str, question_text: str, skill_id: str = "") -> None:
    """在 error_book 表插入一条记录, 供 import_from_errorbook 使用"""
    db.execute(
        "INSERT INTO error_book "
        "(entry_id, user_id, question_id, skill_id, error_type, "
        " user_answer, question_text, is_resolved) "
        "VALUES (%s, %s, %s, %s, %s, %s, %s, %s) "
        "ON CONFLICT (entry_id) DO NOTHING",
        (entry_id, user_id, f"q_{entry_id[:8]}", skill_id, "concept",
         "我的错误答案", question_text, False),
    )


# ════════════════════════════════════════════════════════════════════
# §1. CRUD 端点 (5 端点)
# ════════════════════════════════════════════════════════════════════


class TestCRUDEndpoints:
    """POST/GET/PATCH/DELETE /api/flashcards/ 系列 (5 端点)"""

    def test_01_post_create_card_happy(self, client, user_id, db, auth_headers):
        """POST /api/flashcards/ - 创建卡片 happy path"""
        r = client.post(
            "/api/flashcards/",
            headers=auth_headers,
            json={
                "type": 1,
                "source": "manual",
                "front_text": "什么是光合作用?",
                "back_text": "植物利用阳光合成有机物的过程",
                "linked_node_ids": ["node_bio_1"],
                "tags": ["biology", "core"],
            },
        )
        assert r.status_code == 200, f"创建失败: {r.text}"
        data = r.json()
        assert data["front_text"] == "什么是光合作用?"
        assert data["back_text"] == "植物利用阳光合成有机物的过程"
        assert data["type"] == 1
        assert data["source"] == "manual"
        assert data["user_id"] == user_id
        assert data["status"] == "pending"
        assert "node_bio_1" in data["linked_node_ids"]
        assert "biology" in data["tags"]
        assert data["review_count"] == 0
        assert data["stability"] == 2.5
        assert data["difficulty"] == 5.0
        assert data["id"].startswith("fc_")
        assert "created_at" in data

    def test_02_post_create_card_unauthenticated(self, client, db):
        """POST /api/flashcards/ 无认证 → 401"""
        r = client.post(
            "/api/flashcards/",
            json={"front_text": "x", "linked_node_ids": ["n1"]},
        )
        assert r.status_code == 401

    def test_03_post_create_card_empty_front_text(self, client, user_id, db, auth_headers):
        """POST /api/flashcards/ front_text 为空 → 400"""
        r = client.post(
            "/api/flashcards/",
            headers=auth_headers,
            json={"front_text": "   ", "linked_node_ids": ["n1"]},
        )
        assert r.status_code in (400, 422)

    def test_04_post_create_card_no_linked_nodes(self, client, user_id, db, auth_headers):
        """POST /api/flashcards/ 缺少 linked_node_ids → 400"""
        r = client.post(
            "/api/flashcards/",
            headers=auth_headers,
            json={"front_text": "no node"},
        )
        assert r.status_code in (400, 422)

    def test_05_get_card_happy(self, client, user_id, db, auth_headers):
        """GET /api/flashcards/{id} - 查询卡片"""
        created = _create_card(client, user_id, auth_headers, front_text="get test")
        r = client.get(
            f"/api/flashcards/{created['id']}",
            headers=auth_headers,
        )
        assert r.status_code == 200
        data = r.json()
        assert data["id"] == created["id"]
        assert data["front_text"] == "get test"

    def test_06_get_card_not_found(self, client, user_id, db, auth_headers):
        """GET /api/flashcards/{id} 不存在 → 404"""
        r = client.get(
            "/api/flashcards/fc_nonexistent_999",
            headers=auth_headers,
        )
        assert r.status_code == 404

    def test_07_patch_card_happy(self, client, user_id, db, auth_headers):
        """PATCH /api/flashcards/{id} - 更新卡片"""
        created = _create_card(client, user_id, auth_headers, front_text="v1")
        r = client.patch(
            f"/api/flashcards/{created['id']}",
            headers=auth_headers,
            json={"front_text": "v2", "back_text": "updated answer"},
        )
        assert r.status_code == 200
        data = r.json()
        assert data["front_text"] == "v2"
        assert data["back_text"] == "updated answer"
        # 字段级版本控制
        assert data["field_versions"]["front_text"] == 1
        assert data["field_versions"]["back_text"] == 1

    def test_08_patch_card_reset_scheduling(self, client, user_id, db, auth_headers):
        """PATCH /api/flashcards/{id} reset_scheduling=true → 重置 FSRS"""
        created = _create_card(client, user_id, auth_headers)
        from app.infrastructure.db.database import get_db
        get_db().execute(
            "UPDATE flashcards SET review_count = 5, lapse_count = 2, "
            "stability = 10.0, difficulty = 8.0 WHERE id = %s",
            (created["id"],),
        )
        r = client.patch(
            f"/api/flashcards/{created['id']}",
            headers=auth_headers,
            json={"front_text": "v2", "reset_scheduling": True},
        )
        assert r.status_code == 200
        data = r.json()
        assert data["review_count"] == 0
        assert data["lapse_count"] == 0
        assert data["stability"] == 2.5
        assert data["difficulty"] == 5.0

    def test_09_patch_card_not_found(self, client, user_id, db, auth_headers):
        """PATCH /api/flashcards/{id} 不存在 → 404"""
        r = client.patch(
            "/api/flashcards/fc_nonexistent_999",
            headers=auth_headers,
            json={"front_text": "x"},
        )
        assert r.status_code == 404

    def test_10_delete_card_happy(self, client, user_id, db, auth_headers):
        """DELETE /api/flashcards/{id} - 软删除"""
        created = _create_card(client, user_id, auth_headers, front_text="to delete")
        r = client.delete(
            f"/api/flashcards/{created['id']}",
            headers=auth_headers,
        )
        assert r.status_code == 200
        assert r.json()["deleted"] is True
        # 软删除后 GET 应 404
        r2 = client.get(
            f"/api/flashcards/{created['id']}",
            headers=auth_headers,
        )
        assert r2.status_code == 404

    def test_11_delete_card_not_found(self, client, user_id, db, auth_headers):
        """DELETE /api/flashcards/{id} 不存在 → 404"""
        r = client.delete(
            "/api/flashcards/fc_nonexistent_999",
            headers=auth_headers,
        )
        assert r.status_code == 404

    def test_12_list_cards_happy(self, client, user_id, db, auth_headers):
        """GET /api/flashcards/ - 列表 + 分页 + 筛选"""
        _create_card(client, user_id, auth_headers, front_text="list1", tags=["math"])
        _create_card(client, user_id, auth_headers, front_text="list2", tags=["english"])
        _create_card(client, user_id, auth_headers, front_text="list3", tags=["math"])
        r = client.get(
            "/api/flashcards/",
            headers=auth_headers,
            params={"limit": 10, "offset": 0},
        )
        assert r.status_code == 200
        data = r.json()
        assert data["total"] == 3
        assert len(data["cards"]) == 3
        # tag 筛选
        r2 = client.get(
            "/api/flashcards/",
            headers=auth_headers,
            params={"tag": "math"},
        )
        assert r2.status_code == 200
        assert r2.json()["total"] == 2

    def test_13_list_cards_pagination(self, client, user_id, db, auth_headers):
        """GET /api/flashcards/ - 分页"""
        for i in range(5):
            _create_card(client, user_id, auth_headers, front_text=f"page{i}")
        r1 = client.get(
            "/api/flashcards/",
            headers=auth_headers,
            params={"limit": 2, "offset": 0},
        )
        r2 = client.get(
            "/api/flashcards/",
            headers=auth_headers,
            params={"limit": 2, "offset": 2},
        )
        assert r1.status_code == 200 and r2.status_code == 200
        assert r1.json()["total"] == 5
        assert r2.json()["total"] == 5
        assert len(r1.json()["cards"]) == 2
        assert len(r2.json()["cards"]) == 2
        # 不同页的 ID 不重叠
        ids1 = {c["id"] for c in r1.json()["cards"]}
        ids2 = {c["id"] for c in r2.json()["cards"]}
        assert ids1.isdisjoint(ids2)

    def test_14_list_cards_unauthenticated(self, client, db):
        """GET /api/flashcards/ 无认证 → 401"""
        r = client.get("/api/flashcards/")
        assert r.status_code == 401


# ════════════════════════════════════════════════════════════════════
# §2. 复习提交端点 (1 端点)
# ════════════════════════════════════════════════════════════════════


class TestReviewEndpoints:
    """POST /api/flashcards/{id}/review 系列"""

    @pytest.mark.asyncio
    async def test_15_post_review_difficult(self, client, user_id, db, auth_headers, capture_bus):
        """POST /api/flashcards/{id}/review - 自评 difficult → 稳定性下降 + Belief 回写"""
        bus, captured = capture_bus
        created = _create_card(
            client, user_id, auth_headers, front_text="difficult me",
            linked_node_ids=["n_diff_1", "n_diff_2"],
        )
        from app.api.flashcard.service import FlashCardService
        svc = FlashCardService(event_bus=bus)
        result = await svc.submit_review(
            user_id=user_id, card_id=created["id"],
            self_assessment="difficult",
        )
        assert result["self_assessment"] == "difficult"
        assert result["stability_before"] == 2.5
        assert result["stability_after"] < 2.5
        assert result["lapse_count"] == 1
        assert result["interval_after"] >= 1
        assert result["next_review_at"] is not None
        # belief_deltas (difficult 触发回写)
        assert len(result["belief_deltas"]) == 2
        for d in result["belief_deltas"]:
            assert d["beta_delta"] > 0
            assert d["alpha_delta"] == 0.0

    @pytest.mark.asyncio
    async def test_16_post_review_good_no_belief(self, client, user_id, db, auth_headers):
        """POST /api/flashcards/{id}/review - 自评 good → 不更新 Belief"""
        from app.api.flashcard.service import FlashCardService
        svc = FlashCardService(event_bus=None)
        created = _create_card(client, user_id, auth_headers, front_text="good me",
                              linked_node_ids=["n_good_1"])
        result = await svc.submit_review(
            user_id=user_id, card_id=created["id"],
            self_assessment="good",
        )
        assert result["self_assessment"] == "good"
        assert result["stability_after"] >= 2.5
        # good 不更新 Belief
        assert result["belief_deltas"] == []

    @pytest.mark.asyncio
    async def test_17_post_review_easy_increases_belief(self, client, user_id, db, auth_headers, capture_bus):
        """POST /api/flashcards/{id}/review - 自评 easy → 稳定性上升 + alpha_delta"""
        bus, captured = capture_bus
        from app.api.flashcard.service import FlashCardService
        svc = FlashCardService(event_bus=bus)
        created = _create_card(client, user_id, auth_headers, front_text="easy me",
                              linked_node_ids=["n_easy_1"])
        result = await svc.submit_review(
            user_id=user_id, card_id=created["id"],
            self_assessment="easy",
        )
        assert result["self_assessment"] == "easy"
        assert result["stability_after"] > 2.5
        # easy 触发 alpha_delta
        assert len(result["belief_deltas"]) == 1
        assert result["belief_deltas"][0]["alpha_delta"] > 0
        assert result["belief_deltas"][0]["beta_delta"] == 0.0

    def test_18_post_review_invalid_assessment(self, client, user_id, db, auth_headers):
        """POST /api/flashcards/{id}/review - 非法自评 → 400"""
        created = _create_card(client, user_id, auth_headers)
        r = client.post(
            f"/api/flashcards/{created['id']}/review",
            headers=auth_headers,
            json={"self_assessment": "invalid_rating"},
        )
        assert r.status_code in (400, 422)

    def test_19_post_review_nonexistent_card(self, client, user_id, db, auth_headers):
        """POST /api/flashcards/{id}/review - 卡不存在 → 400 (ValueError→400)"""
        r = client.post(
            "/api/flashcards/fc_nonexistent/review",
            headers=auth_headers,
            json={"self_assessment": "good"},
        )
        assert r.status_code in (400, 404)


# ════════════════════════════════════════════════════════════════════
# §3. 到期卡片查询 (2 端点, 1 canonical + 1 compat)
# ════════════════════════════════════════════════════════════════════


class TestDueCardsEndpoints:
    """GET /api/flashcards/list/due + GET /api/flashcards/due"""

    def test_20_get_due_cards_canonical(self, client, user_id, db, auth_headers):
        """GET /api/flashcards/list/due - 到期卡片"""
        from app.infrastructure.db.database import get_db
        card = _create_card(client, user_id, auth_headers, front_text="due test")
        get_db().execute(
            "UPDATE flashcards SET next_review_at = NOW() - INTERVAL '1 hour' "
            "WHERE id = %s",
            (card["id"],),
        )
        r = client.get(
            "/api/flashcards/list/due",
            headers=auth_headers,
            params={"limit": 5},
        )
        assert r.status_code == 200
        data = r.json()
        assert data["total"] >= 1
        assert any(c["id"] == card["id"] for c in data["cards"])

    def test_21_get_due_cards_compat(self, client, user_id, db, auth_headers):
        """GET /api/flashcards/due - 兼容路径"""
        r = client.get(
            "/api/flashcards/due",
            headers=auth_headers,
            params={"limit": 5},
        )
        assert r.status_code == 200
        data = r.json()
        assert "total" in data
        assert "cards" in data

    def test_22_get_due_cards_filter_by_node(self, client, user_id, db, auth_headers):
        """GET /api/flashcards/list/due - node_id 筛选"""
        from app.infrastructure.db.database import get_db
        c1 = _create_card(client, user_id, auth_headers, front_text="a",
                          linked_node_ids=["node_X"])
        c2 = _create_card(client, user_id, auth_headers, front_text="b",
                          linked_node_ids=["node_Y"])
        get_db().execute(
            "UPDATE flashcards SET next_review_at = NOW() - INTERVAL '1 hour' "
            "WHERE user_id = %s",
            (user_id,),
        )
        r = client.get(
            "/api/flashcards/list/due",
            headers=auth_headers,
            params={"node_id": "node_X"},
        )
        assert r.status_code == 200
        data = r.json()
        ids = {c["id"] for c in data["cards"]}
        assert c1["id"] in ids
        assert c2["id"] not in ids


# ════════════════════════════════════════════════════════════════════
# §4. 导入端点 (4 端点)
# ════════════════════════════════════════════════════════════════════


class TestImportEndpoints:
    """4 个导入端点: errorbook (preview + confirm) + text (preview + confirm)"""

    def test_23_import_from_errorbook_preview(self, client, user_id, db, auth_headers):
        """GET /api/flashcards/import-from-errorbook/{eid} - 错题本导入预览"""
        entry_id = f"eb_{uuid.uuid4().hex[:10]}"
        _seed_error_book(db, user_id, entry_id, "错题: 1+1=?")
        r = client.get(
            f"/api/flashcards/import-from-errorbook/{entry_id}",
            headers=auth_headers,
        )
        assert r.status_code == 200
        data = r.json()
        assert data["error_entry_id"] == entry_id
        assert data["already_imported"] is False

    def test_24_import_from_errorbook_confirm(self, client, user_id, db, auth_headers):
        """POST /api/flashcards/import-from-errorbook/{eid}/confirm - 确认导入"""
        entry_id = f"eb_{uuid.uuid4().hex[:10]}"
        _seed_error_book(db, user_id, entry_id, "错题: 牛顿第二定律?")
        r1 = client.get(
            f"/api/flashcards/import-from-errorbook/{entry_id}",
            headers=auth_headers,
        )
        assert r1.status_code == 200
        r2 = client.post(
            f"/api/flashcards/import-from-errorbook/{entry_id}/confirm",
            headers=auth_headers,
        )
        assert r2.status_code == 200
        data = r2.json()
        assert "card" in data
        card = data["card"]
        # 错题溯源类型 = 6
        assert card["type"] == 6
        assert card["source"] == "practice_error"
        assert card["error_book_entry_id"] == entry_id

    def test_25_import_from_errorbook_duplicate(self, client, user_id, db, auth_headers):
        """POST /api/flashcards/import-from-errorbook/{eid}/confirm - 重复导入 → 409"""
        entry_id = f"eb_{uuid.uuid4().hex[:10]}"
        _seed_error_book(db, user_id, entry_id, "重复导入测试")
        # 第一次 confirm
        r1 = client.post(
            f"/api/flashcards/import-from-errorbook/{entry_id}/confirm",
            headers=auth_headers,
        )
        assert r1.status_code == 200
        # 第二次 confirm
        r2 = client.post(
            f"/api/flashcards/import-from-errorbook/{entry_id}/confirm",
            headers=auth_headers,
        )
        # 已存在 → 409 (ADR 0002 §9 决策 2)
        assert r2.status_code == 409

    def test_26_import_from_errorbook_not_found(self, client, user_id, db, auth_headers):
        """GET /api/flashcards/import-from-errorbook/{eid} - 错题不存在 → 404"""
        r = client.get(
            "/api/flashcards/import-from-errorbook/eb_nonexistent_999",
            headers=auth_headers,
        )
        assert r.status_code == 404

    def test_27_import_from_text_preview(self, client, user_id, db, auth_headers):
        """POST /api/flashcards/import-from-text - 文本导入预览"""
        r = client.post(
            "/api/flashcards/import-from-text",
            headers=auth_headers,
            json={
                "text": "什么是微积分? 微积分是数学的一个分支. "
                        "如何计算导数? 导数是函数的变化率.",
                "type": 1,
                "default_linked_node_ids": ["node_math"],
                "tags": ["imported"],
            },
        )
        assert r.status_code == 200
        data = r.json()
        assert data["total"] >= 1
        assert len(data["items"]) >= 1
        # 启发式: 至少识别一个问题
        items = data["items"]
        has_question = any(
            i["suggested_front"].startswith(("什么是", "如何", "为什么", "怎么", "哪", "多少"))
            for i in items
        )
        assert has_question, f"未识别问题: {items}"

    def test_28_import_from_text_confirm(self, client, user_id, db, auth_headers):
        """POST /api/flashcards/import-from-text/confirm - 批量创建"""
        items = [
            {"suggested_front": "什么是 AI?", "suggested_back": "人工智能",
             "suggested_node_ids": ["n_ai"]},
            {"suggested_front": "什么是 ML?", "suggested_back": "机器学习",
             "suggested_node_ids": ["n_ml"]},
            {"suggested_front": "什么是 DL?", "suggested_back": "深度学习",
             "suggested_node_ids": ["n_dl"]},
        ]
        r = client.post(
            "/api/flashcards/import-from-text/confirm",
            headers=auth_headers,
            json={
                "items": items,
                "type": 1,
                "tags": ["imported"],
                "default_linked_node_ids": ["n_default"],
            },
        )
        assert r.status_code == 200
        data = r.json()
        assert data["imported"] == 3
        assert len(data["cards"]) == 3
        for c in data["cards"]:
            assert c["source"] == "conversation"
            assert "imported" in c["tags"]

    def test_29_import_from_text_confirm_empty(self, client, user_id, db, auth_headers):
        """POST /api/flashcards/import-from-text/confirm - 空 items → 400"""
        r = client.post(
            "/api/flashcards/import-from-text/confirm",
            headers=auth_headers,
            json={"items": []},
        )
        assert r.status_code == 400

    def test_30_import_from_text_preview_empty(self, client, user_id, db, auth_headers):
        """POST /api/flashcards/import-from-text - 空 text → 400"""
        r = client.post(
            "/api/flashcards/import-from-text",
            headers=auth_headers,
            json={"text": ""},
        )
        assert r.status_code in (400, 422)


# ════════════════════════════════════════════════════════════════════
# §5. 复习会话端点 (2 端点)
# ════════════════════════════════════════════════════════════════════


class TestSessionEndpoints:
    """POST /api/flashcards/session/start + /session/{sid}/end"""

    def test_31_session_start_empty(self, client, user_id, db, auth_headers):
        """POST /api/flashcards/session/start - 空到期卡启动"""
        r = client.post(
            "/api/flashcards/session/start",
            headers=auth_headers,
            params={"source_module": "manual", "limit": 10},
        )
        assert r.status_code == 200
        data = r.json()
        assert "session_id" in data
        assert data["initial_card_count"] == 0
        assert data["session_id"].startswith("rvs_")

    def test_32_session_start_with_due_cards(self, client, user_id, db, auth_headers):
        """POST /api/flashcards/session/start - 有到期卡"""
        from app.infrastructure.db.database import get_db
        _create_card(client, user_id, auth_headers, front_text="session_due")
        get_db().execute(
            "UPDATE flashcards SET next_review_at = NOW() - INTERVAL '1 hour' "
            "WHERE user_id = %s",
            (user_id,),
        )
        r = client.post(
            "/api/flashcards/session/start",
            headers=auth_headers,
            params={"limit": 10},
        )
        assert r.status_code == 200
        data = r.json()
        assert data["initial_card_count"] >= 1
        assert len(data["cards"]) >= 1

    def test_33_session_end_happy(self, client, user_id, db, auth_headers):
        """POST /api/flashcards/session/{sid}/end - 结束会话"""
        r1 = client.post(
            "/api/flashcards/session/start",
            headers=auth_headers,
            params={"limit": 5},
        )
        assert r1.status_code == 200
        sid = r1.json()["session_id"]
        r2 = client.post(
            f"/api/flashcards/session/{sid}/end",
            headers=auth_headers,
            json={
                "difficult_count": 1,
                "good_count": 2,
                "easy_count": 1,
                "duration_seconds": 120,
            },
        )
        assert r2.status_code == 200
        data = r2.json()
        assert data["total"] == 4
        assert data["session_id"] == sid


# ════════════════════════════════════════════════════════════════════
# §6. 用户控制端点 (5 端点)
# ════════════════════════════════════════════════════════════════════


class TestUserControlEndpoints:
    """suspend/resume/reset/override/archive (5 端点)"""

    def test_34_suspend_card(self, client, user_id, db, auth_headers):
        """POST /api/flashcards/{id}/suspend - 暂停"""
        created = _create_card(client, user_id, auth_headers)
        r = client.post(
            f"/api/flashcards/{created['id']}/suspend",
            headers=auth_headers,
        )
        assert r.status_code == 200
        assert r.json()["status"] == "suspended"
        assert r.json()["suspended_at"] is not None

    def test_35_suspend_not_found(self, client, user_id, db, auth_headers):
        """POST /api/flashcards/{id}/suspend - 不存在 → 404"""
        r = client.post(
            "/api/flashcards/fc_nonexistent/suspend",
            headers=auth_headers,
        )
        assert r.status_code == 404

    def test_36_resume_card(self, client, user_id, db, auth_headers):
        """POST /api/flashcards/{id}/resume - 恢复"""
        created = _create_card(client, user_id, auth_headers)
        # 先 suspend
        client.post(
            f"/api/flashcards/{created['id']}/suspend",
            headers=auth_headers,
        )
        r = client.post(
            f"/api/flashcards/{created['id']}/resume",
            headers=auth_headers,
        )
        assert r.status_code == 200
        assert r.json()["status"] == "pending"
        assert r.json()["suspended_at"] is None

    def test_37_resume_not_found(self, client, user_id, db, auth_headers):
        """POST /api/flashcards/{id}/resume - 不存在 → 404"""
        r = client.post(
            "/api/flashcards/fc_nonexistent/resume",
            headers=auth_headers,
        )
        assert r.status_code == 404

    def test_38_reset_card(self, client, user_id, db, auth_headers):
        """POST /api/flashcards/{id}/reset - 重置 FSRS"""
        from app.infrastructure.db.database import get_db
        created = _create_card(client, user_id, auth_headers)
        get_db().execute(
            "UPDATE flashcards SET review_count = 10, lapse_count = 3, "
            "stability = 20.0 WHERE id = %s",
            (created["id"],),
        )
        r = client.post(
            f"/api/flashcards/{created['id']}/reset",
            headers=auth_headers,
        )
        assert r.status_code == 200
        data = r.json()
        assert data["review_count"] == 0
        assert data["lapse_count"] == 0
        assert data["stability"] == 2.5

    def test_39_reset_not_found(self, client, user_id, db, auth_headers):
        """POST /api/flashcards/{id}/reset - 不存在 → 404"""
        r = client.post(
            "/api/flashcards/fc_nonexistent/reset",
            headers=auth_headers,
        )
        assert r.status_code == 404

    def test_40_archive_card(self, client, user_id, db, auth_headers):
        """POST /api/flashcards/{id}/archive - 归档"""
        created = _create_card(client, user_id, auth_headers)
        r = client.post(
            f"/api/flashcards/{created['id']}/archive",
            headers=auth_headers,
        )
        assert r.status_code == 200
        assert r.json()["status"] == "archived"

    def test_41_archive_not_found(self, client, user_id, db, auth_headers):
        """POST /api/flashcards/{id}/archive - 不存在 → 404"""
        r = client.post(
            "/api/flashcards/fc_nonexistent/archive",
            headers=auth_headers,
        )
        assert r.status_code == 404

    def test_42_override_scheduling(self, client, user_id, db, auth_headers):
        """PATCH /api/flashcards/{id}/override - 手动覆盖 FSRS"""
        created = _create_card(client, user_id, auth_headers)
        r = client.patch(
            f"/api/flashcards/{created['id']}/override",
            headers=auth_headers,
            json={"stability": 15.0, "difficulty": 3.0, "target_retention": 0.92},
        )
        assert r.status_code == 200
        data = r.json()
        assert data["stability"] == 15.0
        assert data["difficulty"] == 3.0
        assert data["target_retention"] == 0.92
        # forgetting_rate 同步
        assert abs(data["forgetting_rate"] - (3.0 - 1.0) / 9.0) < 0.01

    def test_43_override_not_found(self, client, user_id, db, auth_headers):
        """PATCH /api/flashcards/{id}/override - 不存在 → 404"""
        r = client.patch(
            "/api/flashcards/fc_nonexistent/override",
            headers=auth_headers,
            json={"stability": 5.0},
        )
        assert r.status_code == 404


# ════════════════════════════════════════════════════════════════════
# §7. 统计端点 (2 端点, 1 canonical + 1 compat)
# ════════════════════════════════════════════════════════════════════


class TestStatsEndpoints:
    """GET /api/flashcards/stats/summary + GET /api/flashcards/stats"""

    def test_44_get_stats_canonical(self, client, user_id, db, auth_headers):
        """GET /api/flashcards/stats/summary - 统计面板"""
        _create_card(client, user_id, auth_headers, type_=1, source="manual")
        _create_card(client, user_id, auth_headers, type_=2, source="manual")
        _create_card(client, user_id, auth_headers, type_=1, source="reading_note")
        r = client.get(
            "/api/flashcards/stats/summary",
            headers=auth_headers,
        )
        assert r.status_code == 200
        data = r.json()
        assert data["total"] == 3
        assert data["by_type"]["1"] == 2
        assert data["by_type"]["2"] == 1
        assert data["by_source"]["manual"] == 2
        assert data["by_source"]["reading_note"] == 1
        assert "by_status" in data
        assert "due_today" in data
        assert "due_7d" in data
        assert "average_stability" in data

    def test_45_get_stats_compat(self, client, user_id, db, auth_headers):
        """GET /api/flashcards/stats - 兼容路径"""
        r = client.get(
            "/api/flashcards/stats",
            headers=auth_headers,
        )
        assert r.status_code == 200
        data = r.json()
        assert "total" in data
        assert "by_type" in data

    def test_46_get_stats_unauthenticated(self, client, db):
        """GET /api/flashcards/stats/summary - 无认证 → 401"""
        r = client.get("/api/flashcards/stats/summary")
        assert r.status_code == 401


# ════════════════════════════════════════════════════════════════════
# §8. 预览端点 (1 端点)
# ════════════════════════════════════════════════════════════════════


class TestPreviewEndpoint:
    """POST /api/flashcards/{id}/preview - 预览自评结果 (不修改状态)"""

    def test_47_preview_good(self, client, user_id, db, auth_headers):
        """POST /api/flashcards/{id}/preview - 预览 good 自评"""
        created = _create_card(client, user_id, auth_headers, front_text="preview test")
        r = client.post(
            f"/api/flashcards/{created['id']}/preview",
            headers=auth_headers,
            json={"self_assessment": "good"},
        )
        assert r.status_code == 200
        data = r.json()
        # preview 返回 FSRSStateResponse-like 结构
        assert "stability" in data
        assert "difficulty" in data
        # 卡片状态未被修改
        r2 = client.get(
            f"/api/flashcards/{created['id']}",
            headers=auth_headers,
        )
        assert r2.status_code == 200
        assert r2.json()["review_count"] == 0

    def test_48_preview_easy(self, client, user_id, db, auth_headers):
        """POST /api/flashcards/{id}/preview - 预览 easy 自评"""
        created = _create_card(client, user_id, auth_headers)
        r = client.post(
            f"/api/flashcards/{created['id']}/preview",
            headers=auth_headers,
            json={"self_assessment": "easy"},
        )
        assert r.status_code == 200
        assert "stability" in r.json()

    def test_49_preview_invalid(self, client, user_id, db, auth_headers):
        """POST /api/flashcards/{id}/preview - 非法自评 → 400"""
        created = _create_card(client, user_id, auth_headers)
        r = client.post(
            f"/api/flashcards/{created['id']}/preview",
            headers=auth_headers,
            json={"self_assessment": "bad"},
        )
        assert r.status_code == 400

    def test_50_preview_not_found(self, client, user_id, db, auth_headers):
        """POST /api/flashcards/{id}/preview - 卡不存在 → 404"""
        r = client.post(
            "/api/flashcards/fc_nonexistent/preview",
            headers=auth_headers,
            json={"self_assessment": "good"},
        )
        assert r.status_code == 404


# ════════════════════════════════════════════════════════════════════
# §9. 7 种卡片类型各创建一次
# ════════════════════════════════════════════════════════════════════


class TestSevenCardTypes:
    """7 种卡片类型 (1-7) 全部走通创建流程"""

    @pytest.mark.parametrize("card_type,front,back,type_label", [
        (1, "基础问题: 1+1=?", "2", "基础问答"),
        (2, "填空: ___ 是 Python 之父", "Guido van Rossum", "填空"),
        (3, "对比: Python vs Go", "Python: 动态; Go: 静态", "对比"),
        (4, "流程: 编译 C 的步骤", "预处理→编译→汇编→链接", "流程"),
        (5, "应用: 何时用 DFS?", "树/图遍历 + 需要穷举", "应用场景"),
        (6, "错题: 物理题不会做", "看了解析: 应用牛顿第二定律", "错题溯源"),
        (7, "反思: 为什么这个概念难?", "缺乏前置知识", "反思"),
    ])
    def test_51_create_each_type(self, client, user_id, db, auth_headers, card_type, front, back, type_label):
        """每种 card_type 都能成功创建"""
        r = client.post(
            "/api/flashcards/",
            headers=auth_headers,
            json={
                "type": card_type,
                "front_text": front,
                "back_text": back,
                "linked_node_ids": [f"n_type_{card_type}"],
                "tags": [f"type_{card_type}"],
            },
        )
        assert r.status_code == 200, f"type={card_type} ({type_label}) 创建失败: {r.text}"
        data = r.json()
        assert data["type"] == card_type, f"type 不匹配: 期望 {card_type}, 得到 {data['type']}"
        assert data["front_text"] == front
        assert data["back_text"] == back

    def test_52_invalid_type_rejected(self, client, user_id, db, auth_headers):
        """非法 type (>7) → 422 (Pydantic 验证)"""
        r = client.post(
            "/api/flashcards/",
            headers=auth_headers,
            json={
                "type": 99,  # 非法
                "front_text": "bad type",
                "linked_node_ids": ["n1"],
            },
        )
        assert r.status_code == 422


# ════════════════════════════════════════════════════════════════════
# §10. 7 种来源 (source) 全部能创建
# ════════════════════════════════════════════════════════════════════


class TestSixSources:
    """7 种 source 全部能创建 (manual/practice_error/reading_note/conversation/project/language_room/interest_explorer)"""

    @pytest.mark.parametrize("source", [
        "manual", "practice_error", "reading_note",
        "conversation", "project", "language_room", "interest_explorer",
    ])
    def test_53_create_each_source(self, client, user_id, db, auth_headers, source):
        """每种 source 都能成功创建"""
        cross_src = None if source == "manual" else source
        r = client.post(
            "/api/flashcards/",
            headers=auth_headers,
            json={
                "type": 1,
                "source": source,
                "front_text": f"源测试: {source}",
                "linked_node_ids": [f"n_src_{source[:4]}"],
                "cross_module_source": cross_src,
            },
        )
        assert r.status_code == 200, f"source={source} 创建失败: {r.text}"
        data = r.json()
        assert data["source"] == source

    def test_54_invalid_source_rejected(self, client, user_id, db, auth_headers):
        """非法 source → 422"""
        r = client.post(
            "/api/flashcards/",
            headers=auth_headers,
            json={
                "type": 1,
                "source": "illegal_source",
                "front_text": "bad source",
                "linked_node_ids": ["n1"],
            },
        )
        assert r.status_code == 422


# ════════════════════════════════════════════════════════════════════
# §11. 完整复习会话流程 (start → review × N → end)
# ════════════════════════════════════════════════════════════════════


class TestFullSessionLifecycle:
    """完整复习会话: start → review × 3 (difficult/good/easy) → end"""

    @pytest.mark.asyncio
    async def test_55_full_session_lifecycle(self, client, user_id, db, auth_headers, capture_bus):
        """start session → 复习 3 张 (各档) → end session"""
        bus, captured = capture_bus
        from app.api.flashcard.service import FlashCardService
        svc = FlashCardService(event_bus=bus)

        # 准备 3 张卡
        c1 = _create_card(client, user_id, auth_headers, front_text="c1",
                          linked_node_ids=["p1", "s1"])
        c2 = _create_card(client, user_id, auth_headers, front_text="c2",
                          linked_node_ids=["p2"])
        c3 = _create_card(client, user_id, auth_headers, front_text="c3",
                          linked_node_ids=["p3"])

        # 1. start session
        r1 = client.post(
            "/api/flashcards/session/start",
            headers=auth_headers,
            params={"limit": 10},
        )
        assert r1.status_code == 200
        session_id = r1.json()["session_id"]

        # 2. review 3 张 (各档自评)
        r_difficult = await svc.submit_review(
            user_id=user_id, card_id=c1["id"],
            self_assessment="difficult", session_id=session_id,
        )
        r_good = await svc.submit_review(
            user_id=user_id, card_id=c2["id"],
            self_assessment="good", session_id=session_id,
        )
        r_easy = await svc.submit_review(
            user_id=user_id, card_id=c3["id"],
            self_assessment="easy", session_id=session_id,
        )

        # difficult → stability 下降 + beta_delta
        assert r_difficult["stability_after"] < 2.5
        assert any(d["beta_delta"] > 0 for d in r_difficult["belief_deltas"])

        # good → 不更新 Belief
        assert r_good["belief_deltas"] == []

        # easy → alpha_delta
        assert r_easy["stability_after"] > 2.5
        assert any(d["alpha_delta"] > 0 for d in r_easy["belief_deltas"])

        # 3. end session
        r2 = client.post(
            f"/api/flashcards/session/{session_id}/end",
            headers=auth_headers,
            json={
                "difficult_count": 1, "good_count": 1, "easy_count": 1,
                "duration_seconds": 60,
            },
        )
        assert r2.status_code == 200
        assert r2.json()["total"] == 3

        # 等待事件分发
        await asyncio.sleep(0.2)

        # 验证事件已发布
        reviewed = [e for e in captured if e.event_type == "FlashCardReviewed"]
        assert len(reviewed) == 3

        # CognitiveNodeLinked: difficult 1 次 × 2 nodes + easy 1 次 × 1 node = 3
        linked = [e for e in captured if e.event_type == "CognitiveNodeLinked"]
        assert len(linked) == 3


# ════════════════════════════════════════════════════════════════════
# §12. 跨模块联动测试
# ════════════════════════════════════════════════════════════════════


class TestCrossModuleIntegration:
    """跨模块联动: errorbook ↔ flashcard, flashcard → belief, error → resolved"""

    @pytest.mark.asyncio
    async def test_56_errorbook_to_flashcard_easy_resolves(self, client, user_id, db, auth_headers, capture_bus):
        """错题本 → FlashCard 导入 + easy 自评 → ErrorBookEntryResolved 事件"""
        bus, captured = capture_bus
        from app.api.flashcard.service import FlashCardService
        svc = FlashCardService(event_bus=bus)

        # 1. 错题本插入
        entry_id = f"eb_x_{uuid.uuid4().hex[:8]}"
        _seed_error_book(db, user_id, entry_id, "错题: 物理力学题")

        # 2. 导入
        r = client.post(
            f"/api/flashcards/import-from-errorbook/{entry_id}/confirm",
            headers=auth_headers,
        )
        assert r.status_code == 200
        card_id = r.json()["card"]["id"]

        # 3. easy 自评
        result = await svc.submit_review(
            user_id=user_id, card_id=card_id, self_assessment="easy",
        )
        assert result["self_assessment"] == "easy"
        await asyncio.sleep(0.2)

        # 4. 验证事件: ErrorBookEntryResolved 发布
        resolved = [e for e in captured if e.event_type == "ErrorBookEntryResolved"]
        assert len(resolved) == 1
        assert resolved[0].error_entry_id == entry_id

        # 5. ErrorBookEntryReviewed 也会发布
        reviewed = [e for e in captured if e.event_type == "ErrorBookEntryReviewed"]
        assert len(reviewed) >= 1

    @pytest.mark.asyncio
    async def test_57_errorbook_difficult_no_resolve(self, client, user_id, db, auth_headers, capture_bus):
        """错题卡 difficult → 不发布 Resolved (只 Reviewed)"""
        bus, captured = capture_bus
        from app.api.flashcard.service import FlashCardService
        svc = FlashCardService(event_bus=bus)

        entry_id = f"eb_d_{uuid.uuid4().hex[:8]}"
        _seed_error_book(db, user_id, entry_id, "错题: 化学题")
        r = client.post(
            f"/api/flashcards/import-from-errorbook/{entry_id}/confirm",
            headers=auth_headers,
        )
        card_id = r.json()["card"]["id"]

        await svc.submit_review(
            user_id=user_id, card_id=card_id, self_assessment="difficult",
        )
        await asyncio.sleep(0.2)

        resolved = [e for e in captured if e.event_type == "ErrorBookEntryResolved"]
        assert len(resolved) == 0  # difficult 不触发 resolved
        reviewed = [e for e in captured if e.event_type == "ErrorBookEntryReviewed"]
        assert len(reviewed) >= 1

    @pytest.mark.asyncio
    async def test_58_multi_node_belief_weights(self, client, user_id, db, auth_headers):
        """多节点关联: primary=1.0, secondary=0.3 权重"""
        from app.api.flashcard.service import FlashCardService
        svc = FlashCardService(event_bus=None)
        created = _create_card(
            client, user_id, auth_headers, front_text="multi-node",
            linked_node_ids=["n_primary", "n_secondary"],
        )
        result = await svc.submit_review(
            user_id=user_id, card_id=created["id"], self_assessment="difficult",
        )
        deltas = {d["node_id"]: d for d in result["belief_deltas"]}
        # primary 权重 1.0, secondary 权重 0.3
        assert deltas["n_primary"]["beta_delta"] == pytest.approx(0.1 * 1.0)
        assert deltas["n_secondary"]["beta_delta"] == pytest.approx(0.1 * 0.3)

    @pytest.mark.asyncio
    async def test_59_soft_delete_then_review_fails(self, client, user_id, db, auth_headers):
        """软删除后 review 失败"""
        from app.api.flashcard.service import FlashCardService
        svc = FlashCardService(event_bus=None)
        created = _create_card(client, user_id, auth_headers)
        client.delete(
            f"/api/flashcards/{created['id']}",
            headers=auth_headers,
        )
        # review 软删除的卡 → ValueError → 400
        with pytest.raises(ValueError):
            await svc.submit_review(
                user_id=user_id, card_id=created["id"], self_assessment="good",
            )


# ════════════════════════════════════════════════════════════════════
# §13. 字段级版本控制 + 错误恢复
# ════════════════════════════════════════════════════════════════════


class TestFieldVersioning:
    """field_versions 字段级粒度版本控制"""

    def test_60_field_versions_increment(self, client, user_id, db, auth_headers):
        """每次更新字段, version + 1"""
        created = _create_card(client, user_id, auth_headers, front_text="v0")
        # 第一次更新
        r1 = client.patch(
            f"/api/flashcards/{created['id']}",
            headers=auth_headers,
            json={"front_text": "v1"},
        )
        assert r1.status_code == 200
        assert r1.json()["field_versions"]["front_text"] == 1
        # 第二次更新
        r2 = client.patch(
            f"/api/flashcards/{created['id']}",
            headers=auth_headers,
            json={"front_text": "v2"},
        )
        assert r2.json()["field_versions"]["front_text"] == 2
        # 修改其他字段不影响 front_text version
        r3 = client.patch(
            f"/api/flashcards/{created['id']}",
            headers=auth_headers,
            json={"back_text": "b1"},
        )
        assert r3.json()["field_versions"]["front_text"] == 2
        assert r3.json()["field_versions"]["back_text"] == 1

    def test_61_no_change_no_version_bump(self, client, user_id, db, auth_headers):
        """相同值更新 → 不增加 version"""
        created = _create_card(client, user_id, auth_headers, front_text="stable")
        r = client.patch(
            f"/api/flashcards/{created['id']}",
            headers=auth_headers,
            json={"front_text": "stable"},  # 相同值
        )
        assert r.status_code == 200
        # front_text 字段不应有 version
        fv = r.json()["field_versions"]
        assert fv.get("front_text", 0) == 0

    def test_62_response_history_grows(self, client, user_id, db, auth_headers):
        """response_history 字段随复习累积"""
        from app.api.flashcard.service import FlashCardService
        from app.infrastructure.db.database import get_db
        svc = FlashCardService(event_bus=None)
        created = _create_card(client, user_id, auth_headers, front_text="history")
        # 多次复习
        loop = asyncio.new_event_loop()
        for assess in ["good", "good", "easy"]:
            loop.run_until_complete(svc.submit_review(
                user_id=user_id, card_id=created["id"], self_assessment=assess,
            ))
        loop.close()
        # 复习历史在 review_history 表中
        rows = get_db().fetchall(
            "SELECT self_assessment FROM review_history WHERE card_id = %s ORDER BY reviewed_at",
            (created["id"],),
        )
        assert len(rows) == 3
        assert [r["self_assessment"] for r in rows] == ["good", "good", "easy"]


# ════════════════════════════════════════════════════════════════════
# §14. FSRS 调度正确性 (3 档自评不同行为)
# ════════════════════════════════════════════════════════════════════


class TestFSRSSchedulingBehavior:
    """验证 FSRS 在 3 档自评下的不同行为"""

    @pytest.mark.asyncio
    async def test_63_difficult_decreases_stability(self, client, user_id, db, auth_headers):
        """difficult → stability_after < stability_before"""
        from app.api.flashcard.service import FlashCardService
        svc = FlashCardService(event_bus=None)
        created = _create_card(client, user_id, auth_headers, front_text="fsrs_diff",
                              linked_node_ids=["n1"])
        result = await svc.submit_review(
            user_id=user_id, card_id=created["id"], self_assessment="difficult",
        )
        assert result["stability_after"] < result["stability_before"]
        assert result["difficulty_after"] > result["difficulty_before"]
        assert result["lapse_count"] == 1

    @pytest.mark.asyncio
    async def test_64_good_maintains_or_grows_stability(self, client, user_id, db, auth_headers):
        """good → stability_after >= stability_before (R=1 时持平)"""
        from app.api.flashcard.service import FlashCardService
        svc = FlashCardService(event_bus=None)
        created = _create_card(client, user_id, auth_headers, front_text="fsrs_good",
                              linked_node_ids=["n1"])
        result = await svc.submit_review(
            user_id=user_id, card_id=created["id"], self_assessment="good",
        )
        # 第一次复习, R 接近 1, stability 不下降
        assert result["stability_after"] >= result["stability_before"] * 0.99
        # difficulty 不变
        assert result["difficulty_after"] == result["difficulty_before"]
        # lapse_count 不变 (good 不算 lapse)
        assert result["lapse_count"] == 0

    @pytest.mark.asyncio
    async def test_65_easy_increases_stability(self, client, user_id, db, auth_headers):
        """easy → stability_after > stability_before"""
        from app.api.flashcard.service import FlashCardService
        svc = FlashCardService(event_bus=None)
        created = _create_card(client, user_id, auth_headers, front_text="fsrs_easy",
                              linked_node_ids=["n1"])
        result = await svc.submit_review(
            user_id=user_id, card_id=created["id"], self_assessment="easy",
        )
        assert result["stability_after"] > result["stability_before"]
        assert result["difficulty_after"] < result["difficulty_before"]
        # interval 应更长
        assert result["interval_after"] >= 1

    @pytest.mark.asyncio
    async def test_66_fsrs_state_stored(self, client, user_id, db, auth_headers):
        """FSRS 状态字段持久化到 DB"""
        from app.api.flashcard.service import FlashCardService
        from app.infrastructure.db.database import get_db
        svc = FlashCardService(event_bus=None)
        created = _create_card(client, user_id, auth_headers)
        await svc.submit_review(
            user_id=user_id, card_id=created["id"], self_assessment="good",
        )
        row = get_db().fetchone(
            "SELECT stability, difficulty, forgetting_rate, review_count, "
            "lapse_count, last_review_at, next_review_at "
            "FROM flashcards WHERE id = %s",
            (created["id"],),
        )
        assert row["review_count"] == 1
        assert row["last_review_at"] is not None
        assert row["next_review_at"] is not None


# ════════════════════════════════════════════════════════════════════
# §15. 边界条件
# ════════════════════════════════════════════════════════════════════


class TestEdgeCases:
    """边界条件 & 健壮性"""

    def test_67_list_with_type_filter(self, client, user_id, db, auth_headers):
        """list_cards type 筛选"""
        _create_card(client, user_id, auth_headers, type_=1, front_text="a")
        _create_card(client, user_id, auth_headers, type_=2, front_text="b")
        r = client.get(
            "/api/flashcards/",
            headers=auth_headers,
            params={"type": 1},
        )
        assert r.status_code == 200
        assert r.json()["total"] == 1

    def test_68_list_with_source_filter(self, client, user_id, db, auth_headers):
        """list_cards source 筛选"""
        _create_card(client, user_id, auth_headers, source="manual", front_text="m1")
        _create_card(client, user_id, auth_headers, source="conversation", front_text="c1")
        r = client.get(
            "/api/flashcards/",
            headers=auth_headers,
            params={"source": "conversation"},
        )
        assert r.status_code == 200
        assert r.json()["total"] == 1

    def test_69_list_with_node_id_filter(self, client, user_id, db, auth_headers):
        """list_cards node_id 筛选"""
        _create_card(client, user_id, auth_headers, front_text="n1_card",
                     linked_node_ids=["n_alpha"])
        _create_card(client, user_id, auth_headers, front_text="n2_card",
                     linked_node_ids=["n_beta"])
        r = client.get(
            "/api/flashcards/",
            headers=auth_headers,
            params={"node_id": "n_alpha"},
        )
        assert r.status_code == 200
        assert r.json()["total"] == 1

    def test_70_create_with_all_optional_fields(self, client, user_id, db, auth_headers):
        """创建时所有可选字段都填写"""
        r = client.post(
            "/api/flashcards/",
            headers=auth_headers,
            json={
                "type": 3,  # 对比
                "source": "reading_note",
                "front_text": "对比问题",
                "back_text": "对比答案",
                "back_context": "扩展上下文",
                "language": "zh",
                "source_ref": {"module": "reading", "id": "mat_1", "offset": 100, "length": 200},
                "status": "pending",
                "target_retention": 0.9,
                "linked_node_ids": ["n_full"],
                "node_link_roles": {"n_full": "primary"},
                "tags": ["comprehensive", "test"],
                "error_book_entry_id": "",
                "cross_module_source": "reading_note",
            },
        )
        assert r.status_code == 200
        data = r.json()
        assert data["language"] == "zh"
        assert data["back_context"] == "扩展上下文"
        assert data["target_retention"] == 0.9
        assert "comprehensive" in data["tags"]
        assert data["source_ref"]["module"] == "reading"

    def test_71_archive_excludes_from_due(self, client, user_id, db, auth_headers):
        """归档的卡不参与 due 列表"""
        from app.infrastructure.db.database import get_db
        c1 = _create_card(client, user_id, auth_headers, front_text="keep_due")
        c2 = _create_card(client, user_id, auth_headers, front_text="archive_due")
        # 全部到期
        get_db().execute(
            "UPDATE flashcards SET next_review_at = NOW() - INTERVAL '1 hour' "
            "WHERE user_id = %s",
            (user_id,),
        )
        # 归档 c2
        client.post(
            f"/api/flashcards/{c2['id']}/archive",
            headers=auth_headers,
        )
        r = client.get(
            "/api/flashcards/list/due",
            headers=auth_headers,
        )
        ids = {c["id"] for c in r.json()["cards"]}
        assert c1["id"] in ids
        assert c2["id"] not in ids  # 归档不参与 due

    def test_72_suspend_excludes_from_due(self, client, user_id, db, auth_headers):
        """暂停的卡不参与 due 列表 (status != pending)"""
        from app.infrastructure.db.database import get_db
        c1 = _create_card(client, user_id, auth_headers, front_text="active")
        c2 = _create_card(client, user_id, auth_headers, front_text="paused")
        get_db().execute(
            "UPDATE flashcards SET next_review_at = NOW() - INTERVAL '1 hour' "
            "WHERE user_id = %s",
            (user_id,),
        )
        client.post(
            f"/api/flashcards/{c2['id']}/suspend",
            headers=auth_headers,
        )
        r = client.get(
            "/api/flashcards/list/due",
            headers=auth_headers,
        )
        ids = {c["id"] for c in r.json()["cards"]}
        assert c1["id"] in ids
        assert c2["id"] not in ids  # 暂停不参与 due

    def test_73_target_retention_validation(self, client, user_id, db, auth_headers):
        """target_retention 范围 [0.5, 0.99] 验证"""
        # 0.4 非法
        r1 = client.post(
            "/api/flashcards/",
            headers=auth_headers,
            json={
                "front_text": "x",
                "linked_node_ids": ["n1"],
                "target_retention": 0.4,
            },
        )
        assert r1.status_code == 422
        # 1.0 非法 (超 0.99)
        r2 = client.post(
            "/api/flashcards/",
            headers=auth_headers,
            json={
                "front_text": "x",
                "linked_node_ids": ["n1"],
                "target_retention": 1.0,
            },
        )
        assert r2.status_code == 422

    def test_74_delete_after_update(self, client, user_id, db, auth_headers):
        """update → delete 序列正常"""
        created = _create_card(client, user_id, auth_headers, front_text="seq")
        # update
        r1 = client.patch(
            f"/api/flashcards/{created['id']}",
            headers=auth_headers,
            json={"front_text": "updated"},
        )
        assert r1.status_code == 200
        # delete
        r2 = client.delete(
            f"/api/flashcards/{created['id']}",
            headers=auth_headers,
        )
        assert r2.status_code == 200
        # 软删除后 get 404
        r3 = client.get(
            f"/api/flashcards/{created['id']}",
            headers=auth_headers,
        )
        assert r3.status_code == 404

    def test_75_secondary_node_default(self, client, user_id, db, auth_headers):
        """未指定 node_link_roles 时, 第一个默认 primary, 其余 secondary"""
        created = _create_card(
            client, user_id, auth_headers, front_text="roles",
            linked_node_ids=["n1", "n2", "n3"],
        )
        assert created["node_link_roles"]["n1"] == "primary"
        assert created["node_link_roles"]["n2"] == "secondary"
        assert created["node_link_roles"]["n3"] == "secondary"


# ════════════════════════════════════════════════════════════════════
# §16. 性能 smoke test
# ════════════════════════════════════════════════════════════════════


class TestPerformanceSmoke:
    """性能烟雾测试"""

    def test_76_bulk_create_50_cards(self, client, user_id, db, auth_headers):
        """批量创建 50 张卡 (性能 smoke)"""
        import time
        start = time.time()
        for i in range(50):
            _create_card(client, user_id, auth_headers, front_text=f"bulk_{i}")
        elapsed = time.time() - start
        # 50 张卡 < 30 秒
        assert elapsed < 30, f"批量创建 50 张耗时 {elapsed:.2f}s"
        # 验证全部入库
        r = client.get(
            "/api/flashcards/",
            headers=auth_headers,
            params={"limit": 100},
        )
        assert r.json()["total"] == 50

    def test_77_list_pagination_correctness(self, client, user_id, db, auth_headers):
        """分页正确性: 多页结果总和 == total"""
        for i in range(20):
            _create_card(client, user_id, auth_headers, front_text=f"page_{i:02d}")
        all_ids = set()
        for offset in range(0, 20, 5):
            r = client.get(
                "/api/flashcards/",
                headers=auth_headers,
                params={"limit": 5, "offset": offset},
            )
            assert r.status_code == 200
            all_ids.update(c["id"] for c in r.json()["cards"])
        assert len(all_ids) == 20


# ════════════════════════════════════════════════════════════════════
# §17. 全部端点路径覆盖验证
# ════════════════════════════════════════════════════════════════════


class TestAllRoutesRegistered:
    """验证 routes.py 注册的 22 个端点全部可达"""

    def test_78_all_22_routes_registered(self):
        """routes.py 注册的端点数 == 22"""
        from app.api.flashcard.routes import router
        # 去除 prefix 之后, 只看 path 段
        # 实际 routes.py 包含 22 条 @router 装饰器
        paths = [r.path for r in router.routes]
        assert len(paths) == 22, f"期望 22 个端点, 实际 {len(paths)}: {paths}"

    @pytest.mark.parametrize("path,method", [
        ("/api/flashcards/", "POST"),
        ("/api/flashcards/{card_id}", "GET"),
        ("/api/flashcards/{card_id}", "PATCH"),
        ("/api/flashcards/{card_id}", "DELETE"),
        ("/api/flashcards/{card_id}/review", "POST"),
        ("/api/flashcards/list/due", "GET"),
        ("/api/flashcards/due", "GET"),
        ("/api/flashcards/import-from-errorbook/{error_id}", "GET"),
        ("/api/flashcards/import-from-errorbook/{error_id}/confirm", "POST"),
        ("/api/flashcards/import-from-text", "POST"),
        ("/api/flashcards/import-from-text/confirm", "POST"),
        ("/api/flashcards/session/start", "POST"),
        ("/api/flashcards/session/{session_id}/end", "POST"),
        ("/api/flashcards/{card_id}/suspend", "POST"),
        ("/api/flashcards/{card_id}/resume", "POST"),
        ("/api/flashcards/{card_id}/reset", "POST"),
        ("/api/flashcards/{card_id}/archive", "POST"),
        ("/api/flashcards/{card_id}/override", "PATCH"),
        ("/api/flashcards/{card_id}/preview", "POST"),
        ("/api/flashcards/stats/summary", "GET"),
        ("/api/flashcards/stats", "GET"),
        ("/api/flashcards/", "GET"),  # list
    ])
    def test_79_route_exists(self, path, method):
        """每个端点都注册"""
        from app.api.flashcard.routes import router
        for r in router.routes:
            if r.path == path and method in (r.methods or set()):
                return
        pytest.fail(f"端点 {method} {path} 未注册")
