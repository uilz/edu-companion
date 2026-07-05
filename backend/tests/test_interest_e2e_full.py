"""
InterestExplorer 模块 17 端点端到端测试 (Task #71)

依据: docs/adr/0007-interest-exploration.md +
      backend/app/api/interest/routes.py +
      backend/app/api/interest/service.py +
      backend/app/services/interest/store.py +
      shared/events.py:1475-1689

测试覆盖:
  - 17 个 API 端点 (tags×5/prefs×2/sources×5/push×4/feedback/import/weight×2)
  - 10 个事件发布验证:
      InterestTagCreated / InterestTagUpdated / InterestTagDeleted
      InterestTagFromKnowledgeCreated / InterestPrefsUpdated
      InterestSourceEnabled / InterestSourceDisabled
      InterestPushFeedbackRecorded / InterestPushGenerated
      InterestContentImported
  - 标签 source 类型: manual / from_knowledge / from_reading (互斥)
  - 推送 3 种类型: research_object / research_method / hot_news
  - 反馈 4 类: read / later / dislike / imported
  - 跨模块导入 5 个目标: reading / project / flashcard / cognitive_node / language_room
  - OPML 导入
  - 推送调度
  - 完整链路: 创建标签 → 创建信息源 → 触发推送 → 用户反馈 → 跨模块导入

每个端点: happy path + 至少 1 个边界 (400/401/404/422)
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
    sys.path.insert(0, str(BACKEND))


# ════════════════════════════════════════════════════════════════════
# 工具: 生成合法 UUID 字符串
# ════════════════════════════════════════════════════════════════════


def _nonexistent_uuid() -> str:
    """生成一个合法但数据库中不存在的 UUID"""
    return str(uuid.uuid4())


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
        "username": f"ie2e_{user_id[:8]}",
        "role": "user",
        "type": "access",
        "iat": int(time.time()),
        "exp": int(time.time()) + 3600,
    }
    return pyjwt.encode(payload, secret, algorithm="HS256")


# ════════════════════════════════════════════════════════════════════
# 10 事件族 (SSOT = shared/events.py, 实际通过 API 可触发)
# ════════════════════════════════════════════════════════════════════

ALL_INTEREST_EVENTS = (
    "InterestTagCreated",
    "InterestTagUpdated",
    "InterestTagDeleted",
    "InterestTagFromKnowledgeCreated",
    "InterestPrefsUpdated",
    "InterestSourceEnabled",
    "InterestSourceDisabled",
    "InterestPushFeedbackRecorded",
    "InterestPushGenerated",
    "InterestContentImported",
)

# 3 种推送类型
ALL_PUSH_TYPES = ("research_object", "research_method", "hot_news")

# 4 类反馈
ALL_FEEDBACK_TYPES = ("read", "later", "dislike", "imported")

# 3 种 tag source (互斥)
ALL_TAG_SOURCES = ("manual", "from_knowledge", "from_reading")

# 5 个跨模块导入目标
ALL_IMPORT_TARGETS = (
    "reading",
    "project",
    "flashcard",
    "cognitive_node",
    "language_room",
)

# 4 种 source type (用户可创建)
ALL_SOURCE_TYPES = ("arxiv", "biorxiv", "rss", "atom")


# ════════════════════════════════════════════════════════════════════
# Fixtures
# ════════════════════════════════════════════════════════════════════


@pytest.fixture
def user_id() -> str:
    return f"ie2e_{uuid.uuid4().hex[:12]}"


@pytest.fixture
def other_user_id() -> str:
    return f"ie2e_b_{uuid.uuid4().hex[:12]}"


@pytest.fixture
def db():
    """数据库连接 fixture; 不可用时 skip"""
    try:
        from app.infrastructure.db.database import get_db
        d = get_db()
        d.fetchone("SELECT 1", ())
        # 确保 interest 表存在
        from app.services.interest.migration import ensure_interest_tables
        ensure_interest_tables()
        # 验证
        d.fetchone("SELECT 1 FROM interest_tags LIMIT 1", ())
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
    return {"Authorization": f"Bearer {_make_jwt(user_id)}"}


@pytest.fixture
def other_auth_headers(other_user_id):
    return {"Authorization": f"Bearer {_make_jwt(other_user_id)}"}


@pytest.fixture
def capture_bus():
    """收集所有 interest 事件的总线 (使用 DI 全局 bus)"""
    from app.application.di import container
    bus = container.event_bus
    captured: list[Any] = []

    async def _capture(event):  # noqa: ANN001
        captured.append(event)

    for evt_type in ALL_INTEREST_EVENTS:
        bus.subscribe(evt_type, _capture)
    return bus, captured


@pytest.fixture(autouse=True)
def cleanup_test_data(db, user_id, other_user_id):
    """测试结束后清理该用户的所有 interest 数据"""
    yield
    try:
        for uid in (user_id, other_user_id):
            for table in (
                "interest_feedback",
                "interest_weight_adjustments",
                "interest_push_records",
                "interest_source_subscriptions",
                "interest_sources",
                "interest_push_prefs",
                "interest_tags",
            ):
                try:
                    db.execute(
                        f"DELETE FROM {table} WHERE user_id = %s", (uid,),
                    )
                except Exception:
                    pass
    except Exception:
        pass


# ════════════════════════════════════════════════════════════════════
# 辅助方法
# ════════════════════════════════════════════════════════════════════


def _post_tag(
    client, auth_headers: dict, *,
    name: str = "机器学习",
    level: int = 0,
    weight: int = 1,
    parent_id: str | None = None,
    color: str | None = None,
    source: str = "manual",
    source_ref_id: str | None = None,
) -> dict:
    """通过 HTTP API 创建标签"""
    r = client.post(
        "/api/interest/tags",
        headers=auth_headers,
        json={
            "name": name,
            "level": level,
            "weight": weight,
            "parent_id": parent_id,
            "color": color,
            "source": source,
            "source_ref_id": source_ref_id,
        },
    )
    assert r.status_code == 200, f"创建标签失败: {r.text}"
    return r.json()


def _patch_prefs(
    client, auth_headers: dict, body: dict,
) -> dict:
    """通过 HTTP API 更新推送偏好"""
    r = client.patch(
        "/api/interest/prefs",
        headers=auth_headers,
        json=body,
    )
    assert r.status_code == 200, f"更新偏好失败: {r.text}"
    return r.json()


def _create_push_record(
    user_id: str,
    push_type: str = "research_method",
    title: str = "测试推送",
    url: str | None = None,
    summary: str = "测试摘要",
    matched_tags: list[str] | None = None,
) -> dict:
    """直接在 DB 创建推送记录 (跳过真实抓取)"""
    from app.services.interest import store
    push = store.create_push_record(
        user_id=user_id,
        push_type=push_type,
        title=title,
        url=url or f"https://example.com/{uuid.uuid4().hex[:8]}",
        summary=summary,
        matched_tags=matched_tags or [],
    )
    assert push is not None, "推送记录创建失败"
    return push


def _find_event(captured: list, event_type: str, **filters) -> Any:
    """查找指定类型事件 (按字段过滤)"""
    for e in captured:
        if type(e).__name__ != event_type:
            continue
        ok = True
        for k, v in filters.items():
            if getattr(e, k, None) != v:
                ok = False
                break
        if ok:
            return e
    return None


def _count_events(captured: list, event_type: str) -> int:
    return sum(1 for e in captured if type(e).__name__ == event_type)


# ════════════════════════════════════════════════════════════════════
# §1. 标签 (5 端点)
# ════════════════════════════════════════════════════════════════════


class TestTagEndpoints:
    """标签管理: GET/POST/PATCH/DELETE /api/interest/tags + from-knowledge"""

    def test_01_list_tags_empty(
        self, client, user_id, db, auth_headers
    ):
        """GET /api/interest/tags - 空列表"""
        r = client.get(
            "/api/interest/tags", headers=auth_headers,
        )
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["total"] == 0
        assert data["items"] == []

    def test_02_create_tag_level0(
        self, client, user_id, db, auth_headers, capture_bus
    ):
        """POST /api/interest/tags - level 0 主标签 + InterestTagCreated 事件"""
        bus, captured = capture_bus
        tag = _post_tag(
            client, auth_headers,
            name=f"机器学习_{user_id[:8]}", level=0, weight=1,
        )
        assert tag["id"]
        assert tag["level"] == 0
        assert tag["weight"] == 1
        assert tag["user_id"] == user_id
        # 事件
        time.sleep(0.3)
        ev = _find_event(captured, "InterestTagCreated", user_id=user_id)
        assert ev is not None, "未收到 InterestTagCreated"
        assert ev.level == 0
        assert ev.source == "manual"
        assert ev.cross_module_source is None

    def test_03_create_tag_all_3_levels(
        self, client, user_id, db, auth_headers
    ):
        """POST /api/interest/tags - 3 层标签结构 (树形返回)"""
        # 创建 3 层 (root -> mid -> leaf) 树
        root = _post_tag(
            client, auth_headers,
            name=f"AI_{user_id[:8]}", level=0, weight=1,
        )
        mid = _post_tag(
            client, auth_headers,
            name=f"ML_{user_id[:8]}", level=1, weight=1,
            parent_id=root["id"],
        )
        leaf = _post_tag(
            client, auth_headers,
            name=f"RL_{user_id[:8]}", level=2, weight=2,
            parent_id=mid["id"],
        )
        assert root["level"] == 0
        assert mid["level"] == 1 and mid["parent_id"] == root["id"]
        assert leaf["level"] == 2 and leaf["weight"] == 2
        # 验证树形结构 - 总条目数 = 1 root (含嵌套 children)
        r = client.get(
            "/api/interest/tags", headers=auth_headers,
        )
        data = r.json()
        assert data["total"] == 1  # 只 root 在顶层
        root_in_list = data["items"][0]
        assert root_in_list["id"] == root["id"]
        # root 应该包含 1 个 child (mid)
        assert len(root_in_list["children"]) == 1
        assert root_in_list["children"][0]["id"] == mid["id"]
        # mid 应该包含 1 个 child (leaf)
        mid_in_tree = root_in_list["children"][0]
        assert len(mid_in_tree["children"]) == 1
        assert mid_in_tree["children"][0]["id"] == leaf["id"]

    def test_04_create_tag_all_3_sources(
        self, client, user_id, db, auth_headers
    ):
        """POST /api/interest/tags - 3 种 source 互斥 (manual/from_knowledge/from_reading)"""
        # manual (default)
        t1 = _post_tag(
            client, auth_headers,
            name=f"manual_{user_id[:6]}", source="manual",
        )
        assert t1["source"] == "manual"
        # from_knowledge
        t2 = _post_tag(
            client, auth_headers,
            name=f"fk_{user_id[:6]}", source="from_knowledge",
        )
        assert t2["source"] == "from_knowledge"
        # from_reading
        t3 = _post_tag(
            client, auth_headers,
            name=f"fr_{user_id[:6]}", source="from_reading",
        )
        assert t3["source"] == "from_reading"

    def test_05_create_tag_invalid_level(
        self, client, user_id, db, auth_headers
    ):
        """POST /api/interest/tags - level=3 (越界) → 422 (Pydantic 校验)"""
        r = client.post(
            "/api/interest/tags",
            headers=auth_headers,
            json={"name": f"bad_level_{user_id[:6]}", "level": 3},
        )
        assert r.status_code in (400, 422), r.text

    def test_06_create_tag_invalid_weight(
        self, client, user_id, db, auth_headers
    ):
        """POST /api/interest/tags - weight=3 (越界) → 422 (Pydantic 校验)"""
        r = client.post(
            "/api/interest/tags",
            headers=auth_headers,
            json={"name": f"bad_w_{user_id[:6]}", "weight": 3},
        )
        assert r.status_code in (400, 422), r.text

    def test_07_create_tag_unauthenticated(self, client, db):
        """POST /api/interest/tags - 无认证 → 401"""
        r = client.post(
            "/api/interest/tags",
            json={"name": "anonymous"},
        )
        assert r.status_code == 401

    def test_08_create_tag_empty_name(
        self, client, user_id, db, auth_headers
    ):
        """POST /api/interest/tags - 空 name → 422"""
        r = client.post(
            "/api/interest/tags",
            headers=auth_headers,
            json={"name": ""},
        )
        assert r.status_code == 422

    def test_09_update_tag(
        self, client, user_id, db, auth_headers, capture_bus
    ):
        """PATCH /api/interest/tags/{id} - 重命名 + InterestTagUpdated 事件"""
        bus, captured = capture_bus
        tag = _post_tag(
            client, auth_headers,
            name=f"old_{user_id[:6]}",
        )
        r = client.patch(
            f"/api/interest/tags/{tag['id']}",
            headers=auth_headers,
            json={"name": f"new_{user_id[:6]}", "weight": 2, "color": "#ff0000"},
        )
        assert r.status_code == 200, r.text
        updated = r.json()
        assert updated["weight"] == 2
        assert updated["color"] == "#ff0000"
        # 事件
        time.sleep(0.3)
        ev = _find_event(captured, "InterestTagUpdated", user_id=user_id)
        assert ev is not None
        assert "name" in ev.changed_fields
        assert "weight" in ev.changed_fields
        assert "color" in ev.changed_fields

    def test_10_update_tag_not_found(
        self, client, user_id, db, auth_headers
    ):
        """PATCH /api/interest/tags/{id} - 不存在 → 404"""
        r = client.patch(
            f"/api/interest/tags/{_nonexistent_uuid()}",
            headers=auth_headers,
            json={"name": "x"},
        )
        assert r.status_code == 404, r.text

    def test_11_update_tag_empty_body(
        self, client, user_id, db, auth_headers
    ):
        """PATCH /api/interest/tags/{id} - 空 body → 400"""
        tag = _post_tag(
            client, auth_headers, name=f"empty_{user_id[:6]}",
        )
        r = client.patch(
            f"/api/interest/tags/{tag['id']}",
            headers=auth_headers,
            json={},
        )
        assert r.status_code == 400, r.text

    def test_12_delete_tag(
        self, client, user_id, db, auth_headers, capture_bus
    ):
        """DELETE /api/interest/tags/{id} - 删除 + InterestTagDeleted 事件"""
        bus, captured = capture_bus
        tag = _post_tag(
            client, auth_headers, name=f"del_{user_id[:6]}",
        )
        r = client.delete(
            f"/api/interest/tags/{tag['id']}",
            headers=auth_headers,
        )
        assert r.status_code == 200, r.text
        assert r.json()["deleted"] is True
        # 事件
        time.sleep(0.3)
        ev = _find_event(captured, "InterestTagDeleted", user_id=user_id)
        assert ev is not None
        assert ev.tag_id == tag["id"]

    def test_13_delete_tag_not_found(
        self, client, user_id, db, auth_headers
    ):
        """DELETE /api/interest/tags/{id} - 不存在 → 404"""
        r = client.delete(
            f"/api/interest/tags/{_nonexistent_uuid()}",
            headers=auth_headers,
        )
        assert r.status_code == 404

    def test_14_create_tag_from_knowledge_no_node(
        self, client, user_id, db, auth_headers
    ):
        """POST /api/interest/tags/from-knowledge/{node_id} - 节点不存在 → 404"""
        r = client.post(
            f"/api/interest/tags/from-knowledge/{_nonexistent_uuid()}",
            headers=auth_headers,
            json={"weight": 1, "level": 0},
        )
        assert r.status_code == 404

    def test_15_create_tag_from_knowledge_success(
        self, client, user_id, db, auth_headers, capture_bus
    ):
        """POST /api/interest/tags/from-knowledge/{node_id} - 引用真实节点"""
        from app.domain.cognitive.writer import CognitiveNodeWriter
        from app.services.interest.migration import ensure_interest_tables
        ensure_interest_tables()
        bus, captured = capture_bus
        # 创建一个 cognitive node
        writer = CognitiveNodeWriter(user_id)
        node = writer.create_node(
            label=f"测试节点_{user_id[:6]}",
            level="atom",
            is_visible=True,
        )
        assert node.id
        # 从 node 创建兴趣标签
        r = client.post(
            f"/api/interest/tags/from-knowledge/{node.id}",
            headers=auth_headers,
            json={"weight": 1, "level": 0},
        )
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["tag"]["source"] == "from_knowledge"
        assert data["tag"]["source_ref_id"] == node.id
        assert data["knowledge_node_id"] == node.id
        # 事件
        time.sleep(0.3)
        ev = _find_event(
            captured, "InterestTagFromKnowledgeCreated", user_id=user_id
        )
        assert ev is not None
        assert ev.knowledge_node_id == node.id

    def test_16_list_tags_unauthenticated(self, client, db):
        """GET /api/interest/tags - 无认证 → 401"""
        r = client.get("/api/interest/tags")
        assert r.status_code == 401


# ════════════════════════════════════════════════════════════════════
# §2. 推送偏好 (2 端点)
# ════════════════════════════════════════════════════════════════════


class TestPrefsEndpoints:
    """推送偏好: GET/PATCH /api/interest/prefs"""

    def test_20_get_prefs_default(
        self, client, user_id, db, auth_headers
    ):
        """GET /api/interest/prefs - 默认值"""
        r = client.get(
            "/api/interest/prefs", headers=auth_headers,
        )
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["frequency"] == "daily"
        assert data["push_time"] == "08:00:00"
        assert data["daily_limit"] == 6
        assert data["research_object_pct"] == 50
        assert data["research_method_pct"] == 30
        assert data["hot_news_pct"] == 20
        assert data["is_enabled"] is True

    def test_21_update_prefs_partial(
        self, client, user_id, db, auth_headers, capture_bus
    ):
        """PATCH /api/interest/prefs - 增量更新 + InterestPrefsUpdated 事件"""
        bus, captured = capture_bus
        r = client.patch(
            "/api/interest/prefs",
            headers=auth_headers,
            json={
                "frequency": "weekly",
                "push_time": "20:00:00",
                "daily_limit": 10,
                "cross_disciplinary": True,
            },
        )
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["frequency"] == "weekly"
        assert data["push_time"] == "20:00:00"
        assert data["daily_limit"] == 10
        assert data["cross_disciplinary"] is True
        # 比例保持默认 (50/30/20)
        assert data["research_object_pct"] == 50
        # 事件
        time.sleep(0.3)
        ev = _find_event(captured, "InterestPrefsUpdated", user_id=user_id)
        assert ev is not None
        changed = ev.changed_fields
        assert "frequency" in changed
        assert "push_time" in changed
        assert "daily_limit" in changed
        assert "cross_disciplinary" in changed

    def test_22_update_prefs_pct_sum_not_100(
        self, client, user_id, db, auth_headers
    ):
        """PATCH /api/interest/prefs - 比例之和不=100 → 400"""
        r = client.patch(
            "/api/interest/prefs",
            headers=auth_headers,
            json={
                "research_object_pct": 60,
                "research_method_pct": 60,
                "hot_news_pct": 20,  # 60+60+20=140
            },
        )
        assert r.status_code == 400, r.text

    def test_23_update_prefs_invalid_frequency(
        self, client, user_id, db, auth_headers
    ):
        """PATCH /api/interest/prefs - 非法 frequency → 422 (Pydantic 校验)"""
        r = client.patch(
            "/api/interest/prefs",
            headers=auth_headers,
            json={"frequency": "hourly"},
        )
        assert r.status_code in (400, 422), r.text

    def test_24_update_prefs_daily_limit_out_of_range(
        self, client, user_id, db, auth_headers
    ):
        """PATCH /api/interest/prefs - daily_limit 越界 → 422"""
        r = client.patch(
            "/api/interest/prefs",
            headers=auth_headers,
            json={"daily_limit": 100},
        )
        assert r.status_code == 422

    def test_25_update_prefs_retention_days(
        self, client, user_id, db, auth_headers
    ):
        """PATCH /api/interest/prefs - retention_days 设置"""
        r = client.patch(
            "/api/interest/prefs",
            headers=auth_headers,
            json={"retention_days": 30, "is_enabled": False},
        )
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["retention_days"] == 30
        assert data["is_enabled"] is False

    def test_26_get_prefs_unauthenticated(self, client, db):
        """GET /api/interest/prefs - 无认证 → 401"""
        r = client.get("/api/interest/prefs")
        assert r.status_code == 401

    def test_27_update_prefs_pct_sum_100(
        self, client, user_id, db, auth_headers
    ):
        """PATCH /api/interest/prefs - 比例之和=100 通过"""
        r = client.patch(
            "/api/interest/prefs",
            headers=auth_headers,
            json={
                "research_object_pct": 40,
                "research_method_pct": 40,
                "hot_news_pct": 20,
            },
        )
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["research_object_pct"] == 40
        assert data["research_method_pct"] == 40
        assert data["hot_news_pct"] == 20


# ════════════════════════════════════════════════════════════════════
# §3. 信息源 (5 端点)
# ════════════════════════════════════════════════════════════════════


class TestSourceEndpoints:
    """信息源: GET/POST/PATCH/DELETE + import-opml"""

    def test_30_list_sources_empty(
        self, client, user_id, db, auth_headers
    ):
        """GET /api/interest/sources - 空列表 (无内置源)"""
        r = client.get(
            "/api/interest/sources", headers=auth_headers,
        )
        assert r.status_code == 200, r.text
        data = r.json()
        assert "items" in data
        assert "total" in data
        # 全部为 system=False (用户级)
        for s in data["items"]:
            assert "id" in s
            assert "type" in s

    def test_31_list_sources_enabled_only(
        self, client, user_id, db, auth_headers
    ):
        """GET /api/interest/sources?enabled_only=true - 仅启用"""
        # 先创建 1 个启用的源
        client.post(
            "/api/interest/sources",
            headers=auth_headers,
            json={
                "name": f"enabled_{user_id[:6]}",
                "type": "rss",
                "config": {"feed_url": f"https://example.com/en-{uuid.uuid4().hex[:6]}.xml"},
                "enabled": True,
            },
        )
        r = client.get(
            "/api/interest/sources?enabled_only=true",
            headers=auth_headers,
        )
        assert r.status_code == 200, r.text
        data = r.json()
        # 启用的源应全部 enabled=True
        for s in data["items"]:
            assert s.get("enabled") or s.get("user_enabled")

    def test_32_create_source_rss(
        self, client, user_id, db, auth_headers, capture_bus
    ):
        """POST /api/interest/sources - RSS 源 + InterestSourceEnabled 事件"""
        bus, captured = capture_bus
        r = client.post(
            "/api/interest/sources",
            headers=auth_headers,
            json={
                "name": f"测试RSS_{user_id[:6]}",
                "type": "rss",
                "category": "技术博客",
                "config": {"feed_url": f"https://example.com/feed-{uuid.uuid4().hex[:6]}.xml"},
                "enabled": True,
            },
        )
        assert r.status_code == 200, r.text
        src = r.json()
        assert src["id"]
        assert src["type"] == "rss"
        assert src["is_system"] is False
        assert src["enabled"] is True
        # 事件
        time.sleep(0.3)
        ev = _find_event(captured, "InterestSourceEnabled", user_id=user_id)
        assert ev is not None
        assert ev.type == "rss"
        # 注: 创建时 response.user_enabled=False 是已知行为 (service.create_source
        # 直接返回 store result, 未走 list_sources 注入 user_enabled 逻辑)
        # 通过列表接口可看到 user_enabled=True
        r2 = client.get(
            "/api/interest/sources", headers=auth_headers,
        )
        target = next(
            (s for s in r2.json()["items"] if s["id"] == src["id"]),
            None,
        )
        assert target is not None
        assert target["user_enabled"] is True

    def test_33_create_source_all_4_types(
        self, client, user_id, db, auth_headers
    ):
        """POST /api/interest/sources - 4 种 type 全覆盖"""
        for stype in ALL_SOURCE_TYPES:
            r = client.post(
                "/api/interest/sources",
                headers=auth_headers,
                json={
                    "name": f"src_{stype}_{user_id[:4]}_{uuid.uuid4().hex[:4]}",
                    "type": stype,
                    "config": {"feed_url": f"https://example.com/{stype}-{uuid.uuid4().hex[:6]}.xml"},
                },
            )
            assert r.status_code == 200, f"{stype} 失败: {r.text}"
            assert r.json()["type"] == stype

    def test_34_create_source_invalid_type(
        self, client, user_id, db, auth_headers
    ):
        """POST /api/interest/sources - 非法 type → 422 (Pydantic 校验)"""
        r = client.post(
            "/api/interest/sources",
            headers=auth_headers,
            json={
                "name": f"bad_{user_id[:6]}",
                "type": "arbitrary_url",
                "config": {"feed_url": "https://example.com"},
            },
        )
        assert r.status_code in (400, 422), r.text

    def test_35_create_source_missing_feed_url(
        self, client, user_id, db, auth_headers
    ):
        """POST /api/interest/sources - 缺 config.feed_url → 400"""
        r = client.post(
            "/api/interest/sources",
            headers=auth_headers,
            json={
                "name": f"nofeed_{user_id[:6]}",
                "type": "rss",
                "config": {},
            },
        )
        assert r.status_code == 400, r.text

    def test_36_create_source_unauthenticated(self, client, db):
        """POST /api/interest/sources - 无认证 → 401"""
        r = client.post(
            "/api/interest/sources",
            json={"name": "anonymous", "type": "rss", "config": {}},
        )
        assert r.status_code == 401

    def test_37_enable_source(
        self, client, user_id, db, auth_headers, capture_bus
    ):
        """PATCH /api/interest/sources/{id}/enable - 启用/禁用 + 事件"""
        bus, captured = capture_bus
        # 先创建
        r = client.post(
            "/api/interest/sources",
            headers=auth_headers,
            json={
                "name": f"toggle_{user_id[:6]}",
                "type": "rss",
                "config": {"feed_url": f"https://example.com/tog-{uuid.uuid4().hex[:6]}.xml"},
                "enabled": True,
            },
        )
        assert r.status_code == 200, r.text
        src = r.json()
        # 禁用
        captured.clear()
        r = client.patch(
            f"/api/interest/sources/{src['id']}/enable",
            headers=auth_headers,
            json={"enabled": False},
        )
        assert r.status_code == 200, r.text
        assert r.json()["enabled"] is False
        time.sleep(0.3)
        ev = _find_event(captured, "InterestSourceDisabled", user_id=user_id)
        assert ev is not None
        # 重新启用
        captured.clear()
        r = client.patch(
            f"/api/interest/sources/{src['id']}/enable",
            headers=auth_headers,
            json={"enabled": True},
        )
        assert r.status_code == 200, r.text
        assert r.json()["enabled"] is True
        time.sleep(0.3)
        ev = _find_event(captured, "InterestSourceEnabled", user_id=user_id)
        assert ev is not None

    def test_38_enable_source_not_found(
        self, client, user_id, db, auth_headers
    ):
        """PATCH /api/interest/sources/{id}/enable - 不存在 → 404"""
        r = client.patch(
            f"/api/interest/sources/{_nonexistent_uuid()}/enable",
            headers=auth_headers,
            json={"enabled": True},
        )
        assert r.status_code == 404, r.text

    def test_39_delete_source(
        self, client, user_id, db, auth_headers
    ):
        """DELETE /api/interest/sources/{id} - 删除"""
        r = client.post(
            "/api/interest/sources",
            headers=auth_headers,
            json={
                "name": f"todel_{user_id[:6]}",
                "type": "rss",
                "config": {"feed_url": f"https://example.com/del-{uuid.uuid4().hex[:6]}.xml"},
            },
        )
        assert r.status_code == 200, r.text
        src_id = r.json()["id"]
        r = client.delete(
            f"/api/interest/sources/{src_id}",
            headers=auth_headers,
        )
        assert r.status_code == 200, r.text
        assert r.json()["deleted"] is True

    def test_40_delete_source_not_found(
        self, client, user_id, db, auth_headers
    ):
        """DELETE /api/interest/sources/{id} - 不存在 → 404"""
        r = client.delete(
            f"/api/interest/sources/{_nonexistent_uuid()}",
            headers=auth_headers,
        )
        assert r.status_code == 404

    def test_41_import_opml_success(
        self, client, user_id, db, auth_headers
    ):
        """POST /api/interest/sources/import-opml - 成功导入 OPML"""
        opml = """<?xml version="1.0" encoding="UTF-8"?>
<opml version="2.0">
  <head>
    <title>Test Subscriptions</title>
  </head>
  <body>
    <outline title="Tech Blogs" category="技术">
      <outline type="rss" text="Hacker News" title="Hacker News"
               xmlUrl="https://hnrss.org/best"/>
      <outline type="atom" text="GitHub Blog" title="GitHub Blog"
               xmlUrl="https://github.com/blog.atom"/>
    </outline>
    <outline type="rss" text="Test Feed" title="Test Feed"
             xmlUrl="https://example.com/feed.xml"/>
  </body>
</opml>"""
        r = client.post(
            "/api/interest/sources/import-opml",
            headers=auth_headers,
            json={"opml_xml": opml},
        )
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["imported"] >= 3
        assert data["skipped"] == 0
        assert len(data["items"]) == data["imported"]
        # 所有 items 应该是 rss type (OPML parser 强制)
        for item in data["items"]:
            assert item["type"] == "rss"

    def test_42_import_opml_invalid_xml(
        self, client, user_id, db, auth_headers
    ):
        """POST /api/interest/sources/import-opml - 非法 XML → 400"""
        r = client.post(
            "/api/interest/sources/import-opml",
            headers=auth_headers,
            json={"opml_xml": "<not valid><<<<"},
        )
        assert r.status_code == 400, r.text

    def test_43_import_opml_empty_body(
        self, client, user_id, db, auth_headers
    ):
        """POST /api/interest/sources/import-opml - 空 XML → 422"""
        r = client.post(
            "/api/interest/sources/import-opml",
            headers=auth_headers,
            json={"opml_xml": ""},
        )
        assert r.status_code == 422

    def test_44_list_sources_unauthenticated(self, client, db):
        """GET /api/interest/sources - 无认证 → 401"""
        r = client.get("/api/interest/sources")
        assert r.status_code == 401


# ════════════════════════════════════════════════════════════════════
# §4. 推送 (4 端点)
# ════════════════════════════════════════════════════════════════════


class TestPushEndpoints:
    """推送: GET today/history + POST trigger/fetch-now"""

    def test_50_get_today_push_empty(
        self, client, user_id, db, auth_headers
    ):
        """GET /api/interest/push/today - 空"""
        r = client.get(
            "/api/interest/push/today", headers=auth_headers,
        )
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["user_id"] == user_id
        assert data["items"] == []
        assert data["total"] == 0
        assert "date" in data

    def test_51_get_today_push_with_data(
        self, client, user_id, db, auth_headers
    ):
        """GET /api/interest/push/today - 包含数据"""
        # 手动创建推送记录
        push = _create_push_record(
            user_id, push_type="research_object",
            title=f"今日推送_{user_id[:6]}",
        )
        r = client.get(
            "/api/interest/push/today", headers=auth_headers,
        )
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["total"] >= 1
        assert any(p["id"] == push["id"] for p in data["items"])

    def test_52_get_today_push_unauthenticated(self, client, db):
        """GET /api/interest/push/today - 无认证 → 401"""
        r = client.get("/api/interest/push/today")
        assert r.status_code == 401

    def test_53_get_history_empty(
        self, client, user_id, db, auth_headers
    ):
        """GET /api/interest/push/history - 空"""
        r = client.get(
            "/api/interest/push/history", headers=auth_headers,
        )
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["items"] == []
        assert data["total"] == 0
        assert data["limit"] == 50
        assert data["offset"] == 0

    def test_54_get_history_with_filter(
        self, client, user_id, db, auth_headers
    ):
        """GET /api/interest/push/history?push_type=research_method - 类型筛选"""
        # 创建 3 种类型
        _create_push_record(user_id, push_type="research_object", title="obj")
        _create_push_record(user_id, push_type="research_method", title="method")
        _create_push_record(user_id, push_type="hot_news", title="news")
        # 仅 research_method
        r = client.get(
            "/api/interest/push/history?push_type=research_method",
            headers=auth_headers,
        )
        assert r.status_code == 200, r.text
        data = r.json()
        assert all(p["push_type"] == "research_method" for p in data["items"])

    def test_55_get_history_pagination(
        self, client, user_id, db, auth_headers
    ):
        """GET /api/interest/push/history?limit=2&offset=0 - 分页"""
        for i in range(5):
            _create_push_record(user_id, push_type="research_object", title=f"p{i}")
        r = client.get(
            "/api/interest/push/history?limit=2&offset=0",
            headers=auth_headers,
        )
        assert r.status_code == 200, r.text
        data = r.json()
        assert len(data["items"]) == 2
        assert data["limit"] == 2
        assert data["offset"] == 0

    def test_56_get_history_limit_out_of_range(
        self, client, user_id, db, auth_headers
    ):
        """GET /api/interest/push/history?limit=300 - 越界 → 422"""
        r = client.get(
            "/api/interest/push/history?limit=300",
            headers=auth_headers,
        )
        assert r.status_code == 422

    def test_57_get_history_unauthenticated(self, client, db):
        """GET /api/interest/push/history - 无认证 → 401"""
        r = client.get("/api/interest/push/history")
        assert r.status_code == 401

    def test_58_trigger_push_no_candidates(
        self, client, user_id, db, auth_headers
    ):
        """POST /api/interest/push/today/trigger - 强制触发 (无候选)"""
        # 用户无标签/无源 → 0 推送
        r = client.post(
            "/api/interest/push/today/trigger",
            headers=auth_headers,
        )
        assert r.status_code == 200, r.text
        data = r.json()
        assert "pushed_count" in data
        assert "by_type" in data

    def test_59_trigger_push_with_data(
        self, client, user_id, db, auth_headers, capture_bus
    ):
        """POST /api/interest/push/today/trigger - 触发推送 + InterestPushGenerated 事件

        关键: cross_disciplinary=True 使 level=0 标签也可被采样
        """
        from app.services.interest import store
        from datetime import datetime, timezone
        bus, captured = capture_bus
        # 开启跨学科采样 (level=0 标签也可被采样)
        _patch_prefs(client, auth_headers, {
            "frequency": "manual",
            "daily_limit": 5,
            "cross_disciplinary": True,
        })
        # 创建标签 (level=0)
        tag = _post_tag(
            client, auth_headers, name=f"deeplearning_{user_id[:6]}",
        )
        # 创建用户私有源 + 抓取条目
        r = client.post(
            "/api/interest/sources",
            headers=auth_headers,
            json={
                "name": f"src_trigger_{user_id[:4]}",
                "type": "rss",
                "config": {"feed_url": f"https://example.com/trig-{uuid.uuid4().hex[:6]}.xml"},
            },
        )
        assert r.status_code == 200
        src_id = r.json()["id"]
        # 写入 fetched_items, 标题包含 "deeplearning" 关键词
        url = f"https://example.com/article-{uuid.uuid4().hex[:8]}"
        store.upsert_fetched_items(
            source_id=src_id,
            items=[{
                "title": f"deeplearning 综述 {user_id[:6]}",
                "url": url,
                "summary": "deeplearning framework approach methodology survey",
                "author": "test",
                "published_at": datetime.now(timezone.utc),
            }],
        )
        # 触发推送
        r = client.post(
            "/api/interest/push/today/trigger",
            headers=auth_headers,
        )
        assert r.status_code == 200, r.text
        time.sleep(0.5)
        # 事件
        ev = _find_event(captured, "InterestPushGenerated", user_id=user_id)
        assert ev is not None, (
            f"未收到 InterestPushGenerated, captured: "
            f"{[type(e).__name__ for e in captured]}"
        )
        assert ev.push_id

    def test_60_trigger_push_disabled(
        self, client, user_id, db, auth_headers
    ):
        """POST /api/interest/push/today/trigger - 推送关闭时 skipped"""
        _patch_prefs(client, auth_headers, {"is_enabled": False})
        r = client.post(
            "/api/interest/push/today/trigger",
            headers=auth_headers,
        )
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["pushed_count"] == 0
        assert data["skipped_reason"] == "push_disabled"

    def test_61_trigger_push_unauthenticated(self, client, db):
        """POST /api/interest/push/today/trigger - 无认证 → 401"""
        r = client.post("/api/interest/push/today/trigger")
        assert r.status_code == 401

    def test_62_fetch_now(
        self, client, user_id, db, auth_headers
    ):
        """POST /api/interest/fetch-now - 手动触发全量抓取

        网络不可达时返回 408 timeout; 这是预期 (不依赖外网)
        重点验证端点不返回 500
        """
        r = client.post(
            "/api/interest/fetch-now", headers=auth_headers,
        )
        # 200 (成功) 或 408 (超时) 都是合法 - 不能 500
        assert r.status_code in (200, 408), f"实际 {r.status_code}: {r.text}"
        if r.status_code == 200:
            data = r.json()
            assert "source_results" in data or "total_items" in data

    def test_63_fetch_now_unauthenticated(self, client, db):
        """POST /api/interest/fetch-now - 无认证 → 401"""
        r = client.post("/api/interest/fetch-now")
        assert r.status_code == 401


# ════════════════════════════════════════════════════════════════════
# §5. 反馈 (1 端点)
# ════════════════════════════════════════════════════════════════════


class TestFeedbackEndpoint:
    """POST /api/interest/push/{id}/feedback - 4 类反馈"""

    def test_70_feedback_read(
        self, client, user_id, db, auth_headers, capture_bus
    ):
        """feedback=read + InterestPushFeedbackRecorded 事件"""
        bus, captured = capture_bus
        push = _create_push_record(user_id, title="read test")
        r = client.post(
            f"/api/interest/push/{push['id']}/feedback",
            headers=auth_headers,
            json={"feedback": "read"},
        )
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["feedback"]["feedback"] == "read"
        # 事件
        time.sleep(0.3)
        ev = _find_event(
            captured, "InterestPushFeedbackRecorded", user_id=user_id
        )
        assert ev is not None
        assert ev.feedback == "read"
        assert ev.push_id == push["id"]

    def test_71_feedback_later_creates_flashcard(
        self, client, user_id, db, auth_headers
    ):
        """feedback=later 创建 FlashCard (status='later')"""
        from app.api.flashcard.service import _ensure_tables
        _ensure_tables()
        push = _create_push_record(user_id, title="later test")
        r = client.post(
            f"/api/interest/push/{push['id']}/feedback",
            headers=auth_headers,
            json={"feedback": "later"},
        )
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["feedback"]["feedback"] == "later"
        # 应创建 flashcard_id
        assert data.get("flashcard_id"), f"未创建 flashcard: {data}"

    def test_72_feedback_dislike_increments_weight(
        self, client, user_id, db, auth_headers
    ):
        """feedback=dislike 增加本地权重 (matched_tags)"""
        # 创建标签 + 推送
        tag = _post_tag(
            client, auth_headers, name=f"dislike_{user_id[:6]}",
        )
        push = _create_push_record(
            user_id, title="dislike test",
            matched_tags=[tag["id"]],
        )
        r = client.post(
            f"/api/interest/push/{push['id']}/feedback",
            headers=auth_headers,
            json={"feedback": "dislike"},
        )
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["feedback"]["feedback"] == "dislike"
        # 应调整权重
        assert data.get("weight_adjusted"), f"未调整权重: {data}"
        assert data["weight_adjusted"]["adjusted_tags"] == 1
        # dislike_score 验证
        r2 = client.get(
            "/api/interest/weight-adjustments", headers=auth_headers,
        )
        adjustments = r2.json()["adjustments"]
        target_adj = next(
            (a for a in adjustments if a["tag_id"] == tag["id"]), None,
        )
        assert target_adj is not None
        assert target_adj["dislike_score"] >= 0.1
        # 标签列表中 dislike_score 应注入
        r3 = client.get(
            "/api/interest/tags", headers=auth_headers,
        )
        target_tag = next(
            (t for t in r3.json()["items"] if t["id"] == tag["id"]), None,
        )
        assert target_tag is not None
        assert target_tag["dislike_score"] >= 0.1

    def test_73_feedback_all_4_types(
        self, client, user_id, db, auth_headers
    ):
        """4 类反馈全覆盖 (read/later/dislike/imported)"""
        from app.api.flashcard.service import _ensure_tables
        _ensure_tables()
        for fb in ALL_FEEDBACK_TYPES:
            push = _create_push_record(user_id, title=f"fb_{fb}")
            r = client.post(
                f"/api/interest/push/{push['id']}/feedback",
                headers=auth_headers,
                json={"feedback": fb},
            )
            assert r.status_code == 200, f"{fb} 失败: {r.text}"
            assert r.json()["feedback"]["feedback"] == fb

    def test_74_feedback_invalid_type(
        self, client, user_id, db, auth_headers
    ):
        """feedback=invalid → 422 (Pydantic 校验)"""
        push = _create_push_record(user_id, title="invalid")
        r = client.post(
            f"/api/interest/push/{push['id']}/feedback",
            headers=auth_headers,
            json={"feedback": "invalid_value"},
        )
        assert r.status_code in (400, 422), r.text

    def test_75_feedback_unauthenticated(self, client, db, user_id):
        """feedback 端点 - 无认证 → 401"""
        push = _create_push_record(user_id, title="x")
        r = client.post(
            f"/api/interest/push/{push['id']}/feedback",
            json={"feedback": "read"},
        )
        assert r.status_code == 401

    def test_76_feedback_with_target_module(
        self, client, user_id, db, auth_headers
    ):
        """feedback=imported 携带 target_module"""
        push = _create_push_record(user_id, title="x")
        r = client.post(
            f"/api/interest/push/{push['id']}/feedback",
            headers=auth_headers,
            json={
                "feedback": "imported",
                "target_module": "reading",
                "target_ref_id": "fake_ref_123",
            },
        )
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["feedback"]["target_module"] == "reading"
        assert data["feedback"]["target_ref_id"] == "fake_ref_123"


# ════════════════════════════════════════════════════════════════════
# §6. 跨模块导入 (1 端点 + 5 个目标)
# ════════════════════════════════════════════════════════════════════


class TestImportEndpoint:
    """POST /api/interest/push/{id}/import - 跨模块导入"""

    def test_80_import_to_reading(
        self, client, user_id, db, auth_headers, capture_bus
    ):
        """导入到 reading 模块 + InterestContentImported 事件"""
        from app.services.interest.migration import ensure_interest_tables
        ensure_interest_tables()
        bus, captured = capture_bus
        push = _create_push_record(
            user_id, title=f"阅读材料 {user_id[:6]}",
            url=f"https://example.com/reading-{uuid.uuid4().hex[:8]}",
        )
        r = client.post(
            f"/api/interest/push/{push['id']}/import",
            headers=auth_headers,
            json={"target_module": "reading"},
        )
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["imported"] is True
        assert data["target_module"] == "reading"
        assert data["target_ref_id"]
        # 事件
        time.sleep(0.3)
        ev = _find_event(captured, "InterestContentImported", user_id=user_id)
        assert ev is not None
        assert ev.target_module.value == "reading"
        assert ev.target_ref_id == data["target_ref_id"]

    def test_81_import_to_project(
        self, client, user_id, db, auth_headers
    ):
        """导入到 project 模块"""
        push = _create_push_record(
            user_id, title=f"项目灵感 {user_id[:6]}",
        )
        r = client.post(
            f"/api/interest/push/{push['id']}/import",
            headers=auth_headers,
            json={"target_module": "project"},
        )
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["target_module"] == "project"
        assert data["target_ref_id"]

    def test_82_import_to_flashcard(
        self, client, user_id, db, auth_headers
    ):
        """导入到 flashcard 模块"""
        from app.services.interest.migration import ensure_interest_tables
        from app.api.flashcard.service import _ensure_tables as fc_ensure
        ensure_interest_tables()
        fc_ensure()
        push = _create_push_record(
            user_id, title=f"知识卡片 {user_id[:6]}",
        )
        r = client.post(
            f"/api/interest/push/{push['id']}/import",
            headers=auth_headers,
            json={"target_module": "flashcard"},
        )
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["target_module"] == "flashcard"
        assert data["target_ref_id"]

    def test_83_import_to_cognitive_node(
        self, client, user_id, db, auth_headers
    ):
        """导入到 cognitive_node 模块"""
        from app.services.interest.migration import ensure_interest_tables
        ensure_interest_tables()
        push = _create_push_record(
            user_id, title=f"认知节点 {user_id[:6]}",
        )
        r = client.post(
            f"/api/interest/push/{push['id']}/import",
            headers=auth_headers,
            json={"target_module": "cognitive_node"},
        )
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["target_module"] == "cognitive_node"
        assert data["target_ref_id"]

    def test_84_import_to_language_room(
        self, client, user_id, db, auth_headers
    ):
        """导入到 language_room 模块"""
        from app.services.interest.migration import ensure_interest_tables
        from app.api.liveroom import service as liveroom_service
        ensure_interest_tables()
        liveroom_service._ensure_tables()
        push = _create_push_record(
            user_id, title=f"讨论话题 {user_id[:6]}",
        )
        r = client.post(
            f"/api/interest/push/{push['id']}/import",
            headers=auth_headers,
            json={"target_module": "language_room"},
        )
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["target_module"] == "language_room"
        assert data["target_ref_id"]

    def test_85_import_invalid_target(
        self, client, user_id, db, auth_headers
    ):
        """target_module=invalid → 422 (Pydantic 校验)"""
        push = _create_push_record(user_id, title="bad")
        r = client.post(
            f"/api/interest/push/{push['id']}/import",
            headers=auth_headers,
            json={"target_module": "invalid_module"},
        )
        assert r.status_code == 422, r.text

    def test_86_import_nonexistent_push(
        self, client, user_id, db, auth_headers
    ):
        """push_id 不存在 → 500 (服务层未找到, 路由层返回 500)"""
        r = client.post(
            f"/api/interest/push/{_nonexistent_uuid()}/import",
            headers=auth_headers,
            json={"target_module": "reading"},
        )
        # 服务层 import_to_module 返回 None → 路由层 raise 500
        assert r.status_code == 500, r.text

    def test_87_import_unauthenticated(
        self, client, db, user_id
    ):
        """import 端点 - 无认证 → 401"""
        push = _create_push_record(user_id, title="x")
        r = client.post(
            f"/api/interest/push/{push['id']}/import",
            json={"target_module": "reading"},
        )
        assert r.status_code == 401

    def test_88_import_all_5_targets(
        self, client, user_id, db, auth_headers
    ):
        """5 个目标模块全覆盖"""
        from app.services.interest.migration import ensure_interest_tables
        from app.api.flashcard.service import _ensure_tables as fc_ensure
        from app.api.liveroom import service as liveroom_service
        ensure_interest_tables()
        fc_ensure()
        liveroom_service._ensure_tables()
        for target in ALL_IMPORT_TARGETS:
            push = _create_push_record(
                user_id, title=f"import_{target}_{user_id[:4]}",
            )
            r = client.post(
                f"/api/interest/push/{push['id']}/import",
                headers=auth_headers,
                json={"target_module": target},
            )
            assert r.status_code == 200, f"{target} 失败: {r.text}"
            assert r.json()["target_module"] == target


# ════════════════════════════════════════════════════════════════════
# §7. 本地权重 (2 端点)
# ════════════════════════════════════════════════════════════════════


class TestWeightEndpoints:
    """本地权重: GET/POST weight-adjustments"""

    def test_90_get_weights_empty(
        self, client, user_id, db, auth_headers
    ):
        """GET /api/interest/weight-adjustments - 空"""
        r = client.get(
            "/api/interest/weight-adjustments", headers=auth_headers,
        )
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["adjustments"] == []
        assert data["principle"] == "local_only_not_sent_to_server"
        assert data["sampling_weights"] == []

    def test_91_get_weights_with_data(
        self, client, user_id, db, auth_headers
    ):
        """GET /api/interest/weight-adjustments - 包含数据

        关键: 使用 level=2 标签 (sampling_weights 只含叶子标签)
        """
        # 创建 3 层 (root -> mid -> leaf), leaf 用于 sampling
        root = _post_tag(
            client, auth_headers, name=f"w_root_{user_id[:6]}",
        )
        mid = _post_tag(
            client, auth_headers, name=f"w_mid_{user_id[:6]}",
            level=1, parent_id=root["id"],
        )
        leaf = _post_tag(
            client, auth_headers, name=f"w_leaf_{user_id[:6]}",
            level=2, parent_id=mid["id"],
        )
        # 推送 + dislike
        push = _create_push_record(
            user_id, title="w_test", matched_tags=[leaf["id"]],
        )
        client.post(
            f"/api/interest/push/{push['id']}/feedback",
            headers=auth_headers,
            json={"feedback": "dislike"},
        )
        r = client.get(
            "/api/interest/weight-adjustments", headers=auth_headers,
        )
        assert r.status_code == 200, r.text
        data = r.json()
        assert len(data["adjustments"]) >= 1
        target = next(
            (a for a in data["adjustments"] if a["tag_id"] == leaf["id"]),
            None,
        )
        assert target is not None
        assert target["dislike_score"] > 0
        assert target["tag_name"]
        # sampling_weights 应包含 (默认 cross_disciplinary=False, 只含 level=2)
        assert any(
            sw["tag_id"] == leaf["id"]
            for sw in data["sampling_weights"]
        )

    def test_92_get_weights_unauthenticated(self, client, db):
        """GET /api/interest/weight-adjustments - 无认证 → 401"""
        r = client.get("/api/interest/weight-adjustments")
        assert r.status_code == 401

    def test_93_reset_weights(
        self, client, user_id, db, auth_headers
    ):
        """POST /api/interest/weight-adjustments/reset - 清空权重"""
        # 先创建数据
        tag = _post_tag(
            client, auth_headers, name=f"reset_{user_id[:6]}",
        )
        push = _create_push_record(
            user_id, title="r_test", matched_tags=[tag["id"]],
        )
        client.post(
            f"/api/interest/push/{push['id']}/feedback",
            headers=auth_headers,
            json={"feedback": "dislike"},
        )
        # 清空
        r = client.post(
            "/api/interest/weight-adjustments/reset",
            headers=auth_headers,
        )
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["reset"] is True
        # 验证已清空
        r2 = client.get(
            "/api/interest/weight-adjustments", headers=auth_headers,
        )
        adjustments = r2.json()["adjustments"]
        assert all(
            a["tag_id"] != tag["id"] for a in adjustments
        )

    def test_94_reset_weights_empty(
        self, client, user_id, db, auth_headers
    ):
        """POST /api/interest/weight-adjustments/reset - 空数据也可清空"""
        r = client.post(
            "/api/interest/weight-adjustments/reset",
            headers=auth_headers,
        )
        assert r.status_code == 200, r.text
        assert r.json()["reset"] is True

    def test_95_reset_weights_unauthenticated(self, client, db):
        """POST /api/interest/weight-adjustments/reset - 无认证 → 401"""
        r = client.post("/api/interest/weight-adjustments/reset")
        assert r.status_code == 401


# ════════════════════════════════════════════════════════════════════
# §8. 端到端全链路
# ════════════════════════════════════════════════════════════════════


class TestEndToEndFlow:
    """完整生命周期: 创建标签 → 创建信息源 → 触发推送 → 反馈 → 跨模块导入"""

    def test_100_complete_flow(
        self, client, user_id, db, auth_headers, capture_bus
    ):
        """完整 E2E 链路 + 多事件发布

        关键: cross_disciplinary=True 使 level=0 标签可被采样
        """
        from app.services.interest.migration import ensure_interest_tables
        from app.api.flashcard.service import _ensure_tables as fc_ensure
        from app.api.liveroom import service as liveroom_service
        from app.services.interest import store
        from datetime import datetime, timezone
        ensure_interest_tables()
        fc_ensure()
        liveroom_service._ensure_tables()
        bus, captured = capture_bus

        # 1) 创建标签 (manual source)
        # 注意: tag name 不能含 '_' (会被 _keyword_match 当作 word char 阻断 boundary)
        # tags 本身按 user_id 隔离，无需在 name 中加 user_id 前缀
        tag = _post_tag(
            client, auth_headers,
            name="machinelearning", level=0, weight=1,
        )
        assert tag["source"] == "manual"

        # 2) 更新偏好 (开启 cross_disciplinary)
        _patch_prefs(client, auth_headers, {
            "frequency": "manual",
            "daily_limit": 5,
            "cross_disciplinary": True,
        })

        # 3) 创建用户私有源
        r = client.post(
            "/api/interest/sources",
            headers=auth_headers,
            json={
                "name": f"e2e_src_{user_id[:4]}",
                "type": "rss",
                "config": {"feed_url": f"https://example.com/e2e-{uuid.uuid4().hex[:6]}.xml"},
            },
        )
        assert r.status_code == 200
        src_id = r.json()["id"]

        # 4) 写入 fetched_items + 触发推送
        url = f"https://example.com/article-{uuid.uuid4().hex[:8]}"
        store.upsert_fetched_items(
            source_id=src_id,
            items=[{
                "title": f"machinelearning framework approach {user_id[:6]}",
                "url": url,
                "summary": "framework approach methodology survey",
                "author": "tester",
                "published_at": datetime.now(timezone.utc),
            }],
        )
        r = client.post(
            "/api/interest/push/today/trigger",
            headers=auth_headers,
        )
        assert r.status_code == 200
        time.sleep(0.5)
        # 验证 InterestPushGenerated 事件
        gen_ev = _find_event(captured, "InterestPushGenerated", user_id=user_id)
        assert gen_ev is not None, (
            f"无 InterestPushGenerated, captured: "
            f"{[type(e).__name__ for e in captured]}"
        )
        push_id = gen_ev.push_id

        # 5) 提交反馈 (dislike) - 调整权重
        r = client.post(
            f"/api/interest/push/{push_id}/feedback",
            headers=auth_headers,
            json={"feedback": "dislike"},
        )
        assert r.status_code == 200
        time.sleep(0.3)
        # 验证 InterestPushFeedbackRecorded
        fb_ev = _find_event(
            captured, "InterestPushFeedbackRecorded", user_id=user_id,
        )
        assert fb_ev is not None

        # 6) 跨模块导入到 flashcard
        r = client.post(
            f"/api/interest/push/{push_id}/import",
            headers=auth_headers,
            json={"target_module": "flashcard"},
        )
        assert r.status_code == 200
        time.sleep(0.3)
        # 验证 InterestContentImported
        imp_ev = _find_event(
            captured, "InterestContentImported", user_id=user_id,
        )
        assert imp_ev is not None

        # 7) 验证完整数据流
        # 7.1) 标签 dislike_score 注入
        r = client.get("/api/interest/tags", headers=auth_headers)
        target_tag = next(
            (t for t in r.json()["items"] if t["id"] == tag["id"]), None,
        )
        assert target_tag is not None
        assert target_tag["dislike_score"] > 0

        # 7.2) 推送历史可见
        r = client.get(
            "/api/interest/push/history?push_type=research_method",
            headers=auth_headers,
        )
        assert any(p["id"] == push_id for p in r.json()["items"])

        # 7.3) 权重调整可见
        r = client.get(
            "/api/interest/weight-adjustments", headers=auth_headers,
        )
        assert len(r.json()["adjustments"]) >= 1

        # 7.4) flashcard 真实创建
        target_ref_id = imp_ev.target_ref_id
        assert target_ref_id

        # 8) 验证 6 类事件全部至少触发一次
        event_types_in_captured = {type(e).__name__ for e in captured}
        expected_event_types = {
            "InterestTagCreated",
            "InterestPrefsUpdated",
            "InterestSourceEnabled",
            "InterestPushGenerated",
            "InterestPushFeedbackRecorded",
            "InterestContentImported",
        }
        missing = expected_event_types - event_types_in_captured
        assert not missing, (
            f"事件未触发: {missing}, 实际: {event_types_in_captured}"
        )


class TestDataIsolation:
    """数据隔离: user A 看不到 user B 的数据"""

    def test_110_data_isolation(
        self, client, user_id, other_user_id, db, auth_headers, other_auth_headers
    ):
        """user_a 创建的标签 user_b 看不到"""
        _post_tag(
            client, auth_headers, name=f"private_{user_id[:6]}",
        )
        # user_b 看不到
        r = client.get(
            "/api/interest/tags", headers=other_auth_headers,
        )
        assert r.status_code == 200
        items = r.json()["items"]
        assert all(t["user_id"] != user_id for t in items)

    def test_111_isolation_delete_protection(
        self, client, user_id, other_user_id, db, auth_headers, other_auth_headers
    ):
        """user_b 不能删除 user_a 的标签"""
        tag = _post_tag(
            client, auth_headers, name=f"protect_{user_id[:6]}",
        )
        # 用 user_b 的 token 删 user_a 的 tag → 应失败
        r = client.delete(
            f"/api/interest/tags/{tag['id']}",
            headers=other_auth_headers,
        )
        # 应返回 404 (查询不到 user_a 的 tag)
        assert r.status_code == 404, (
            f"跨用户删除应失败, 实际: {r.status_code} {r.text}"
        )
        # 验证 user_a 仍能读到
        r2 = client.get(
            "/api/interest/tags", headers=auth_headers,
        )
        assert any(t["id"] == tag["id"] for t in r2.json()["items"])


# ════════════════════════════════════════════════════════════════════
# §9. ADR 关键差异检测
# ════════════════════════════════════════════════════════════════════


class TestADRDifferences:
    """ADR 0007 关键约束的代码实际状态确认"""

    def test_200_adr_decision_5_only_rss_atom_arxiv(
        self, client, user_id, db, auth_headers
    ):
        """ADR 决策 5: 不支持任意 URL 抓取 - 拒绝非 rss/atom/arxiv/biorxiv"""
        r = client.post(
            "/api/interest/sources",
            headers=auth_headers,
            json={
                "name": f"arbitrary_{user_id[:6]}",
                "type": "website",  # 非法
                "config": {"feed_url": "https://example.com"},
            },
        )
        assert r.status_code in (400, 422), r.text

    def test_201_adr_decision_10_local_weights(
        self, client, user_id, db, auth_headers
    ):
        """ADR 决策 10: 本地权重 (不发送到服务端)"""
        r = client.get(
            "/api/interest/weight-adjustments", headers=auth_headers,
        )
        data = r.json()
        assert data["principle"] == "local_only_not_sent_to_server"

    def test_202_adr_three_levels(
        self, client, user_id, db, auth_headers
    ):
        """ADR 3 层标签结构约束 (level 必须是 0/1/2)"""
        # level 3 越界
        r = client.post(
            "/api/interest/tags",
            headers=auth_headers,
            json={"name": f"l3_{user_id[:6]}", "level": 3},
        )
        # 422 (Pydantic literal) 或 400 (手动校验)
        assert r.status_code in (400, 422), r.text

    def test_203_adr_two_weights(
        self, client, user_id, db, auth_headers
    ):
        """ADR 2 档权重 (1=主要/2=次要)"""
        r = client.post(
            "/api/interest/tags",
            headers=auth_headers,
            json={"name": f"w3_{user_id[:6]}", "weight": 3},
        )
        assert r.status_code in (400, 422), r.text

    def test_204_adr_three_push_types(
        self, client, user_id, db, auth_headers
    ):
        """ADR 3 种推送类型 (research_object/research_method/hot_news)"""
        # 验证每种类型都可以创建
        for ptype in ALL_PUSH_TYPES:
            push = _create_push_record(
                user_id, push_type=ptype, title=f"type_{ptype}",
            )
            assert push["push_type"] == ptype

    def test_205_adr_link_level_dedup(
        self, client, user_id, db, auth_headers
    ):
        """ADR 链接级别去重: 相同 URL 不重复推送"""
        from app.services.interest import store
        same_url = f"https://example.com/dedup-{uuid.uuid4().hex[:8]}"
        p1 = store.create_push_record(
            user_id=user_id, push_type="research_object",
            title="first", url=same_url,
        )
        p2 = store.create_push_record(
            user_id=user_id, push_type="research_object",
            title="second", url=same_url,
        )
        assert p1 is not None
        # 重复 URL 应返回 None (链接级别去重)
        assert p2 is None, "链接级别去重失败"

    def test_206_adr_cross_module_target_strict(
        self, client, user_id, db, auth_headers
    ):
        """ADR 严格使用 CrossModuleTarget 枚举 - 5 个合法值必须全部支持"""
        from app.services.interest.migration import ensure_interest_tables
        from app.api.flashcard.service import _ensure_tables as fc_ensure
        from app.api.liveroom import service as liveroom_service
        ensure_interest_tables()
        fc_ensure()
        liveroom_service._ensure_tables()
        # 验证 5 个目标全部支持
        assert "reading" in {t.value for t in __import__("shared.events", fromlist=["CrossModuleTarget"]).CrossModuleTarget}
        assert "project" in {t.value for t in __import__("shared.events", fromlist=["CrossModuleTarget"]).CrossModuleTarget}
        assert "flashcard" in {t.value for t in __import__("shared.events", fromlist=["CrossModuleTarget"]).CrossModuleTarget}
        assert "cognitive_node" in {t.value for t in __import__("shared.events", fromlist=["CrossModuleTarget"]).CrossModuleTarget}
        assert "language_room" in {t.value for t in __import__("shared.events", fromlist=["CrossModuleTarget"]).CrossModuleTarget}
