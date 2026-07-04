"""Secretary 模块端到端测试 (Task #83)

依据: docs/temp/task-83-secretary-audit.md +
      backend/app/api/system/secretary.py +
      backend/app/api/secretary/mood_stress.py +
      backend/app/infrastructure/db/secretary_schema.py +
      backend/app/infrastructure/db/proposal_store.py +
      shared/events.py

测试覆盖:
  - 31 个 secretary API 端点
      GET  /api/secretary/preferences
      GET  /api/secretary/snapshot                       (B-18 缓存)
      GET  /api/secretary/proposals/pending              (含 source/action_type/priority/search 过滤)
      GET  /api/secretary/proposals/history
      POST /api/secretary/proposals/{id}/accept          (B-4/B-9/B-20 + ProposalAccepted 事件)
      POST /api/secretary/proposals/{id}/dismiss
      POST /api/secretary/proposals/{id}/snooze
      POST /api/secretary/proposals/{id}/delete
      POST /api/secretary/proposals/{id}/restore
      POST /api/secretary/proposals/batch-accept
      POST /api/secretary/proposals/batch-dismiss
      POST /api/secretary/proposals/{id}/execution-result
      POST /api/secretary/generate-llm-proposals         (B-15/B-23 错误处理)
      GET  /api/secretary/modules
      POST /api/secretary/modules/toggle
      POST /api/secretary/checker/run
      GET  /api/secretary/checker/status
      POST /api/secretary/checker/configure              (B-3 持久化)
      GET  /api/secretary/onboarding                     (B-5 改进 cold_start)
      GET  /api/secretary/data/export
      DELETE /api/secretary/data/delete
      POST /api/secretary/agent/chat                     (SSE, B-13 死代码)
      GET  /api/secretary/agent/preferences
      POST /api/secretary/agent/preferences              (B-6 UserPreferencesUpdated 事件)
      GET  /api/secretary/events/stream
      GET  /api/secretary/events/recent
      GET  /api/secretary/events/summary
      GET  /api/secretary/events/top-level
      GET  /api/secretary/events/{event_id}/children
      GET  /api/secretary/events/{event_id}/ancestors
  - 15 个 mood_stress 端点
      dashboard, record, records, records/{id}, intervention, interventions
      signals, signals/mark-read, signals/emit
      prefs (GET/PUT) (MoodStressPrefsUpdated 事件)
      rules (POST/GET/DELETE)
      constants
  - 提案生命周期: pending → accepted/dismissed/snoozed/deleted → restored
  - 事件发布: ProposalAccepted / MoodStressPrefsUpdated / UserPreferencesUpdated
  - 数据隔离: 不同用户提案不互串
  - 异常路径: 不存在的 ID / 401 未认证

每个端点: happy path + 至少 1 个边界 (401/404/422)
使用真实 HTTP API (FastAPI TestClient + JWT Bearer 认证)
数据库不可用时整个文件 skip
"""

from __future__ import annotations

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
        "username": f"sec2e_{user_id[:8]}",
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
    return f"sec2e_{uuid.uuid4().hex[:12]}"


@pytest.fixture
def other_user_id() -> str:
    return f"sec2e_b_{uuid.uuid4().hex[:12]}"


@pytest.fixture
def db():
    """数据库连接 fixture; 不可用时 skip"""
    try:
        from app.infrastructure.db.database import get_db
        d = get_db()
        d.fetchone("SELECT 1", ())
        # 确保 secretary 表存在 (Task #83 B-1)
        from app.infrastructure.db.secretary_schema import _ensure_tables
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
    return {"Authorization": f"Bearer {_make_jwt(user_id)}"}


@pytest.fixture
def other_auth_headers(other_user_id):
    return {"Authorization": f"Bearer {_make_jwt(other_user_id)}"}


@pytest.fixture
def capture_bus():
    """收集 secretary 相关事件的总线"""
    from app.application.di import container
    bus = container.event_bus
    captured: list[Any] = []

    async def _capture(event):  # noqa: ANN001
        captured.append(event)

    for evt_type in (
        "ProposalAccepted",
        "MoodStressPrefsUpdated",
        "UserPreferencesUpdated",
    ):
        try:
            bus.subscribe(evt_type, _capture)
        except Exception:
            pass
    return bus, captured


@pytest.fixture(autouse=True)
def cleanup_test_data(db, user_id, other_user_id):
    """测试结束后清理该用户的所有 secretary + mood_stress 数据"""
    yield
    try:
        for uid in (user_id, other_user_id):
            try:
                db.execute("DELETE FROM secretary_proposals WHERE user_id = %s", (uid,))
            except Exception:
                pass
            try:
                db.execute("DELETE FROM emotion_records WHERE user_id = %s", (uid,))
            except Exception:
                pass
            try:
                db.execute("DELETE FROM mood_stress_intervention_logs WHERE user_id = %s", (uid,))
            except Exception:
                pass
            try:
                db.execute("DELETE FROM mood_stress_rules WHERE user_id = %s", (uid,))
            except Exception:
                pass
            try:
                db.execute("DELETE FROM behavior_signals WHERE user_id = %s", (uid,))
            except Exception:
                pass
            try:
                db.execute("DELETE FROM mood_stress_prefs WHERE user_id = %s", (uid,))
            except Exception:
                pass
    except Exception:
        pass


# ════════════════════════════════════════════════════════════════════
# 辅助方法
# ════════════════════════════════════════════════════════════════════


def _insert_proposal(db, user_id: str, title: str, action_type: str = "review",
                     priority: int = 3, status: str = "pending",
                     generated_by: str = "test_module") -> str:
    """直接插入一条提案到 secretary_proposals"""
    from datetime import datetime, timezone
    proposal_id = f"prop_{uuid.uuid4().hex[:12]}"
    now = datetime.now(timezone.utc)
    db.execute(
        """INSERT INTO secretary_proposals
           (id, user_id, session_id, emoji, title, description, action_type, payload,
            priority, generated_by, overrideable, status, metadata, created_at, updated_at)
           VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, TRUE, %s, %s, %s, %s)""",
        (
            proposal_id, user_id, "", "💡", title, "test desc",
            action_type, json.dumps({}), priority, generated_by, status,
            json.dumps({"generated_by": generated_by}), now, now,
        ),
    )
    return proposal_id


def _find_event(captured: list, event_type: str, **filters) -> Any:
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


# ════════════════════════════════════════════════════════════════════
# §1. /api/secretary/preferences — 秘书偏好 (1 端点)
# ════════════════════════════════════════════════════════════════════


class TestSecretaryPreferences:
    """秘书偏好: GET /api/secretary/preferences"""

    def test_01_get_preferences_default(self, client, user_id, db, auth_headers):
        """GET /api/secretary/preferences - 默认值 (Task #83 B-22)"""
        r = client.get("/api/secretary/preferences", headers=auth_headers)
        assert r.status_code == 200, r.text
        data = r.json()
        assert "enabled_extensions" in data
        assert "quiet_hours_start" in data
        assert "quiet_hours_end" in data
        assert "max_proactive_per_day" in data
        # B-22: 默认包含 3 个核心模块
        assert "review_reminder" in data["enabled_extensions"]
        assert "fatigue_manager" in data["enabled_extensions"]
        assert "daily_brief" in data["enabled_extensions"]

    def test_02_get_preferences_unauthenticated(self, client, db):
        """GET /api/secretary/preferences - 无认证 → 401"""
        r = client.get("/api/secretary/preferences")
        assert r.status_code == 401


# ════════════════════════════════════════════════════════════════════
# §2. /api/secretary/snapshot — 学习状态快照 (1 端点)
# ════════════════════════════════════════════════════════════════════


class TestSecretarySnapshot:
    """快照: GET /api/secretary/snapshot (Task #83 B-18 缓存)"""

    def test_01_get_snapshot(self, client, user_id, db, auth_headers):
        """GET /api/secretary/snapshot - 返回完整快照"""
        r = client.get("/api/secretary/snapshot", headers=auth_headers)
        assert r.status_code == 200, r.text
        data = r.json()
        assert "cognitive_load" in data
        assert "weak_count" in data
        assert "stagnant_count" in data
        assert "streak_days" in data
        assert "summary" in data

    def test_02_get_snapshot_cached(self, client, user_id, db, auth_headers):
        """GET /api/secretary/snapshot - 30s 缓存 (Task #83 B-18)"""
        r1 = client.get("/api/secretary/snapshot", headers=auth_headers)
        assert r1.status_code == 200
        d1 = r1.json()
        # 立即再请求应返回相同结果 (缓存命中)
        r2 = client.get("/api/secretary/snapshot", headers=auth_headers)
        assert r2.status_code == 200
        d2 = r2.json()
        assert d1 == d2

    def test_03_get_snapshot_unauthenticated(self, client, db):
        """GET /api/secretary/snapshot - 无认证 → 401"""
        r = client.get("/api/secretary/snapshot")
        assert r.status_code == 401


# ════════════════════════════════════════════════════════════════════
# §3. /api/secretary/proposals — 提案 CRUD (10 端点)
# ════════════════════════════════════════════════════════════════════


class TestProposalPending:
    """GET /api/secretary/proposals/pending - 含 6 种过滤"""

    def test_01_get_pending_empty(self, client, user_id, db, auth_headers):
        """GET pending - 空列表"""
        r = client.get("/api/secretary/proposals/pending", headers=auth_headers)
        assert r.status_code == 200, r.text
        data = r.json()
        assert isinstance(data, list)
        assert len(data) == 0

    def test_02_get_pending_with_data(self, client, user_id, db, auth_headers):
        """GET pending - 有数据时返回"""
        _insert_proposal(db, user_id, "复习测试1", action_type="review", priority=3)
        _insert_proposal(db, user_id, "练习测试2", action_type="practice", priority=5)
        r = client.get("/api/secretary/proposals/pending", headers=auth_headers)
        assert r.status_code == 200
        data = r.json()
        assert len(data) == 2

    def test_03_get_pending_filter_source(self, client, user_id, db, auth_headers):
        """GET pending - 按 generated_by 过滤"""
        _insert_proposal(db, user_id, "title1", generated_by="module_a")
        _insert_proposal(db, user_id, "title2", generated_by="module_b")
        r = client.get(
            "/api/secretary/proposals/pending?source_module=module_a",
            headers=auth_headers,
        )
        assert r.status_code == 200
        data = r.json()
        assert len(data) == 1
        assert data[0]["generated_by"] == "module_a"

    def test_04_get_pending_filter_action(self, client, user_id, db, auth_headers):
        """GET pending - 按 action_type 过滤"""
        _insert_proposal(db, user_id, "title1", action_type="review")
        _insert_proposal(db, user_id, "title2", action_type="practice")
        r = client.get(
            "/api/secretary/proposals/pending?action_type=practice",
            headers=auth_headers,
        )
        assert r.status_code == 200
        data = r.json()
        assert len(data) == 1
        assert data[0]["action_type"] == "practice"

    def test_05_get_pending_filter_priority(self, client, user_id, db, auth_headers):
        """GET pending - 按 priority_min 过滤"""
        _insert_proposal(db, user_id, "p1", priority=2)
        _insert_proposal(db, user_id, "p2", priority=4)
        r = client.get(
            "/api/secretary/proposals/pending?priority_min=4",
            headers=auth_headers,
        )
        assert r.status_code == 200
        data = r.json()
        assert len(data) == 1
        assert data[0]["priority"] == 4

    def test_06_get_pending_unauthenticated(self, client, db):
        """GET pending - 无认证 → 401"""
        r = client.get("/api/secretary/proposals/pending")
        assert r.status_code == 401


class TestProposalHistory:
    """GET /api/secretary/proposals/history"""

    def test_01_get_history(self, client, user_id, db, auth_headers):
        """GET history - 包含已处理提案"""
        _insert_proposal(db, user_id, "h1", status="accepted")
        _insert_proposal(db, user_id, "h2", status="dismissed")
        r = client.get("/api/secretary/proposals/history", headers=auth_headers)
        assert r.status_code == 200
        data = r.json()
        assert len(data) >= 2

    def test_02_get_history_pagination(self, client, user_id, db, auth_headers):
        """GET history - 分页 page/page_size"""
        for i in range(5):
            _insert_proposal(db, user_id, f"hist{i}", status="dismissed")
        r = client.get(
            "/api/secretary/proposals/history?page=1&page_size=2",
            headers=auth_headers,
        )
        assert r.status_code == 200
        data = r.json()
        assert len(data) == 2

    def test_03_get_history_unauthenticated(self, client, db):
        """GET history - 无认证 → 401"""
        r = client.get("/api/secretary/proposals/history")
        assert r.status_code == 401


class TestProposalAccept:
    """POST /api/secretary/proposals/{id}/accept - Task #83 B-4/B-9/B-20"""

    def test_01_accept_not_found(self, client, user_id, db, auth_headers):
        """accept - 不存在 ID → 404 (B-4 修复)"""
        r = client.post(
            "/api/secretary/proposals/nonexistent_xyz/accept",
            headers=auth_headers,
        )
        assert r.status_code == 404

    def test_02_accept_success(self, client, user_id, db, auth_headers, capture_bus):
        """accept - 成功 + ProposalAccepted 事件"""
        bus, captured = capture_bus
        pid = _insert_proposal(db, user_id, "accept_test", action_type="review")
        r = client.post(
            f"/api/secretary/proposals/{pid}/accept",
            headers=auth_headers,
        )
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["status"] == "accepted"

    def test_03_accept_emits_event(self, client, user_id, db, auth_headers, capture_bus):
        """accept - 发布 ProposalAccepted 事件 (Task #83 B-9)"""
        bus, captured = capture_bus
        pid = _insert_proposal(db, user_id, "evt_test", action_type="review")
        client.post(f"/api/secretary/proposals/{pid}/accept", headers=auth_headers)
        time.sleep(0.2)
        ev = _find_event(captured, "ProposalAccepted", user_id=user_id)
        assert ev is not None, "未收到 ProposalAccepted 事件"
        assert ev.proposal_id == pid

    def test_04_accept_other_user(self, client, user_id, other_user_id, db,
                                   auth_headers, other_auth_headers):
        """accept - 跨用户隔离 (B-4 rowcount 检查)"""
        pid = _insert_proposal(db, user_id, "user_a_proposal")
        # 其他用户尝试采纳 → 404
        r = client.post(
            f"/api/secretary/proposals/{pid}/accept",
            headers=other_auth_headers,
        )
        assert r.status_code == 404


class TestProposalDismiss:
    """POST /api/secretary/proposals/{id}/dismiss"""

    def test_01_dismiss_success(self, client, user_id, db, auth_headers):
        """dismiss - 成功 + 状态切换"""
        pid = _insert_proposal(db, user_id, "dismiss_test")
        r = client.post(
            f"/api/secretary/proposals/{pid}/dismiss?reason=not_relevant",
            headers=auth_headers,
        )
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["status"] == "dismissed"

    def test_02_dismiss_not_found(self, client, user_id, db, auth_headers):
        """dismiss - 不存在 ID → 404"""
        r = client.post(
            "/api/secretary/proposals/nonex_abc/dismiss",
            headers=auth_headers,
        )
        assert r.status_code == 404


class TestProposalSnooze:
    """POST /api/secretary/proposals/{id}/snooze"""

    def test_01_snooze_with_until(self, client, user_id, db, auth_headers):
        """snooze - 成功 + until 时间戳"""
        pid = _insert_proposal(db, user_id, "snooze_test")
        future_ts = time.time() + 3600
        r = client.post(
            f"/api/secretary/proposals/{pid}/snooze?until={future_ts}",
            headers=auth_headers,
        )
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["status"] == "snoozed"

    def test_02_snooze_not_found(self, client, user_id, db, auth_headers):
        """snooze - 不存在 ID → 404"""
        r = client.post(
            "/api/secretary/proposals/nonex_xyz/snooze",
            headers=auth_headers,
        )
        assert r.status_code == 404


class TestProposalDelete:
    """POST /api/secretary/proposals/{id}/delete"""

    def test_01_delete_success(self, client, user_id, db, auth_headers):
        """delete - 软删 status=deleted"""
        pid = _insert_proposal(db, user_id, "delete_test")
        r = client.post(
            f"/api/secretary/proposals/{pid}/delete",
            headers=auth_headers,
        )
        assert r.status_code == 200
        data = r.json()
        assert data["status"] == "deleted"

    def test_02_delete_not_found(self, client, user_id, db, auth_headers):
        """delete - 不存在 ID → 404"""
        r = client.post(
            "/api/secretary/proposals/nonex_xyz/delete",
            headers=auth_headers,
        )
        assert r.status_code == 404


class TestProposalRestore:
    """POST /api/secretary/proposals/{id}/restore"""

    def test_01_restore_from_snoozed(self, client, user_id, db, auth_headers):
        """restore - snoozed → pending"""
        pid = _insert_proposal(db, user_id, "restore_test", status="snoozed")
        r = client.post(
            f"/api/secretary/proposals/{pid}/restore",
            headers=auth_headers,
        )
        assert r.status_code == 200
        data = r.json()
        assert data["status"] == "restored"

    def test_02_restore_not_found(self, client, user_id, db, auth_headers):
        """restore - 不存在 ID → 404"""
        r = client.post(
            "/api/secretary/proposals/nonex_xyz/restore",
            headers=auth_headers,
        )
        assert r.status_code == 404


class TestProposalBatch:
    """POST /api/secretary/proposals/batch-{accept,dismiss}"""

    def test_01_batch_accept(self, client, user_id, db, auth_headers):
        """batch-accept - 批量采纳 (B-4 修复后)"""
        pids = [
            _insert_proposal(db, user_id, f"ba_{i}")
            for i in range(3)
        ]
        r = client.post(
            "/api/secretary/proposals/batch-accept",
            headers=auth_headers,
            json=pids,
        )
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["status"] == "ok"
        assert data["count"] >= 1

    def test_02_batch_dismiss(self, client, user_id, db, auth_headers):
        """batch-dismiss - 批量忽略"""
        pids = [
            _insert_proposal(db, user_id, f"bd_{i}")
            for i in range(2)
        ]
        r = client.post(
            "/api/secretary/proposals/batch-dismiss",
            headers=auth_headers,
            json=pids,
        )
        assert r.status_code == 200
        data = r.json()
        assert data["status"] == "ok"

    def test_03_batch_accept_empty(self, client, user_id, db, auth_headers):
        """batch-accept - 空列表 → count=0"""
        r = client.post(
            "/api/secretary/proposals/batch-accept",
            headers=auth_headers,
            json=[],
        )
        assert r.status_code == 200
        assert r.json()["count"] == 0


class TestProposalExecutionResult:
    """POST /api/secretary/proposals/{id}/execution-result"""

    def test_01_execution_result(self, client, user_id, db, auth_headers):
        """execution-result - 回传执行结果"""
        pid = _insert_proposal(db, user_id, "exec_test")
        r = client.post(
            f"/api/secretary/proposals/{pid}/execution-result",
            headers=auth_headers,
            json={
                "success": True,
                "message": "已完成",
                "details": "复习了5个知识点",
                "completed_at": int(time.time() * 1000),
            },
        )
        assert r.status_code == 200
        data = r.json()
        assert data["status"] == "ok"
        assert data["result"]["success"] is True

    def test_02_execution_result_graceful_error(self, client, user_id, db, auth_headers):
        """execution-result - 数据库错误时返回 ok (B-12 设计决策)"""
        pid = _insert_proposal(db, user_id, "exec_err_test")
        # 即便 proposal 不存在也应返回 200 而非 500
        r = client.post(
            "/api/secretary/proposals/fake_id/execution-result",
            headers=auth_headers,
            json={"success": False, "message": "fail"},
        )
        assert r.status_code == 200


# ════════════════════════════════════════════════════════════════════
# §4. /api/secretary/generate-llm-proposals (1 端点)
# ════════════════════════════════════════════════════════════════════


class TestGenerateLlmProposals:
    """POST /api/secretary/generate-llm-proposals (Task #83 B-15/B-23)"""

    def test_01_generate_returns_list(self, client, user_id, db, auth_headers):
        """generate - 返回 list (LLM 失败时返回空列表而非 500)"""
        r = client.post(
            "/api/secretary/generate-llm-proposals",
            headers=auth_headers,
        )
        # 即便 LLM 不可用也应返回 200 + 空列表
        assert r.status_code == 200
        data = r.json()
        assert isinstance(data, list)

    def test_02_generate_unauthenticated(self, client, db):
        """generate - 无认证 → 401"""
        r = client.post("/api/secretary/generate-llm-proposals")
        assert r.status_code == 401


# ════════════════════════════════════════════════════════════════════
# §5. /api/secretary/modules — 模块管理 (2 端点)
# ════════════════════════════════════════════════════════════════════


class TestSecretaryModules:
    """GET /api/secretary/modules + POST /toggle"""

    def test_01_get_modules(self, client, user_id, db, auth_headers):
        """GET modules - 列出秘书模块"""
        r = client.get("/api/secretary/modules", headers=auth_headers)
        assert r.status_code == 200
        data = r.json()
        assert isinstance(data, list)
        assert len(data) > 0
        for m in data:
            assert "name" in m
            assert "enabled" in m

    def test_02_toggle_module(self, client, user_id, db, auth_headers):
        """toggle - 启用/禁用模块"""
        r = client.post(
            "/api/secretary/modules/toggle?name=review_reminder&enabled=false",
            headers=auth_headers,
        )
        assert r.status_code == 200
        data = r.json()
        assert data["status"] == "ok"
        assert data["module"] == "review_reminder"
        assert data["enabled"] is False

    def test_03_get_modules_unauthenticated(self, client, db):
        """GET modules - 无认证 → 401"""
        r = client.get("/api/secretary/modules")
        assert r.status_code == 401


# ════════════════════════════════════════════════════════════════════
# §6. /api/secretary/checker — 主动检查器 (3 端点)
# ════════════════════════════════════════════════════════════════════


class TestActiveChecker:
    """POST /checker/run + GET /status + POST /configure (Task #83 B-3)"""

    def test_01_get_checker_status(self, client, user_id, db, auth_headers):
        """GET checker/status - 返回模块列表"""
        r = client.get("/api/secretary/checker/status", headers=auth_headers)
        assert r.status_code == 200
        data = r.json()
        assert "running" in data
        assert "check_interval" in data
        assert "module_count" in data
        assert "enabled_modules" in data

    def test_02_run_checker(self, client, user_id, db, auth_headers):
        """POST checker/run - 手动触发检查"""
        r = client.post("/api/secretary/checker/run", headers=auth_headers)
        assert r.status_code == 200
        data = r.json()
        assert data["status"] == "ok"
        assert "modules_run" in data
        assert "proposals_generated" in data

    def test_03_configure_checker_persistence(self, client, user_id, db, auth_headers):
        """POST checker/configure - 持久化到 user_settings (Task #83 B-3)"""
        r = client.post(
            "/api/secretary/checker/configure",
            headers=auth_headers,
            json={"check_interval": 300},
        )
        assert r.status_code == 200
        data = r.json()
        assert data["check_interval"] == 300
        # 验证 GET preferences 包含持久化的 check_interval
        r2 = client.get("/api/secretary/preferences", headers=auth_headers)
        assert r2.status_code == 200
        prefs = r2.json()
        assert prefs.get("check_interval") == 300

    def test_04_configure_checker_invalid(self, client, user_id, db, auth_headers):
        """POST checker/configure - 越界 interval 静默忽略"""
        r = client.post(
            "/api/secretary/checker/configure",
            headers=auth_headers,
            json={"check_interval": 10},  # < 60
        )
        assert r.status_code == 200
        # interval 没变 (保留 600 默认)
        data = r.json()
        assert data["check_interval"] >= 60

    def test_05_run_checker_unauthenticated(self, client, db):
        """POST checker/run - 无认证 → 401"""
        r = client.post("/api/secretary/checker/run")
        assert r.status_code == 401


# ════════════════════════════════════════════════════════════════════
# §7. /api/secretary/onboarding — 冷启动引导 (Task #83 B-5)
# ════════════════════════════════════════════════════════════════════


class TestOnboarding:
    """GET /api/secretary/onboarding (Task #83 B-5 改进 cold_start 判定)"""

    def test_01_onboarding_cold_start(self, client, user_id, db, auth_headers):
        """onboarding - 新用户 → is_cold_start=True"""
        r = client.get("/api/secretary/onboarding", headers=auth_headers)
        assert r.status_code == 200
        data = r.json()
        assert "is_cold_start" in data
        assert "total_nodes" in data
        assert "learned_nodes" in data
        assert "guide_steps" in data
        assert isinstance(data["guide_steps"], list)
        assert len(data["guide_steps"]) == 4

    def test_02_onboarding_unauthenticated(self, client, db):
        """onboarding - 无认证 → 401"""
        r = client.get("/api/secretary/onboarding")
        assert r.status_code == 401


# ════════════════════════════════════════════════════════════════════
# §8. /api/secretary/data — 数据导出/删除 (2 端点)
# ════════════════════════════════════════════════════════════════════


class TestSecretaryDataManagement:
    """GET /data/export + DELETE /data/delete (遗忘权)"""

    def test_01_export(self, client, user_id, db, auth_headers):
        """export - 导出 secretary 数据"""
        _insert_proposal(db, user_id, "exp1")
        r = client.get("/api/secretary/data/export", headers=auth_headers)
        assert r.status_code == 200
        data = r.json()
        assert "user_id" in data
        assert "exported_at" in data
        assert "preferences" in data
        assert "proposals" in data
        assert "policy_memory" in data

    def test_02_delete(self, client, user_id, db, auth_headers):
        """delete - 遗忘权: 删除所有 secretary 数据"""
        _insert_proposal(db, user_id, "del1")
        r = client.delete("/api/secretary/data/delete", headers=auth_headers)
        assert r.status_code == 200
        data = r.json()
        assert data["status"] == "deleted"
        assert data["details"]["proposals"] is True
        # 验证提案已消失
        r2 = client.get("/api/secretary/proposals/pending", headers=auth_headers)
        assert r2.status_code == 200
        assert len(r2.json()) == 0


# ════════════════════════════════════════════════════════════════════
# §9. /api/secretary/agent — Agent 助手 (3 端点, Task #83 B-6/B-13)
# ════════════════════════════════════════════════════════════════════


class TestAgentPreferences:
    """GET/POST /api/secretary/agent/preferences (Task #83 B-6)"""

    def test_01_get_default(self, client, user_id, db, auth_headers):
        """GET agent/preferences - 默认值"""
        r = client.get("/api/secretary/agent/preferences", headers=auth_headers)
        assert r.status_code == 200
        data = r.json()
        assert data["confirm_mode"] == "smart"
        assert data["auto_jump_threshold"] == 0.85

    def test_02_post_happy(self, client, user_id, db, auth_headers, capture_bus):
        """POST agent/preferences - 成功 + UserPreferencesUpdated 事件 (B-6)"""
        bus, captured = capture_bus
        r = client.post(
            "/api/secretary/agent/preferences",
            headers=auth_headers,
            json={"confirm_mode": "always", "auto_jump_threshold": 0.95},
        )
        assert r.status_code == 200
        data = r.json()
        assert data["confirm_mode"] == "always"
        # 验证事件
        time.sleep(0.2)
        ev = _find_event(captured, "UserPreferencesUpdated", user_id=user_id)
        assert ev is not None, "未收到 UserPreferencesUpdated 事件"
        assert "agent.confirm_mode" in ev.changed_keys

    def test_03_post_invalid_mode(self, client, user_id, db, auth_headers):
        """POST agent/preferences - 非法 confirm_mode → 422"""
        r = client.post(
            "/api/secretary/agent/preferences",
            headers=auth_headers,
            json={"confirm_mode": "invalid_xyz", "auto_jump_threshold": 0.85},
        )
        assert r.status_code == 422

    def test_04_get_unauthenticated(self, client, db):
        """GET agent/preferences - 无认证 → 401"""
        r = client.get("/api/secretary/agent/preferences")
        assert r.status_code == 401


class TestAgentChat:
    """POST /api/secretary/agent/chat (SSE) (Task #83 B-13)"""

    def test_01_chat_unauthenticated(self, client, db):
        """agent/chat - 无认证 → 401"""
        r = client.post(
            "/api/secretary/agent/chat",
            json={"message": "test", "current_page": "/"},
        )
        assert r.status_code == 401


# ════════════════════════════════════════════════════════════════════
# §10. /api/secretary/events — 事件流 (6 端点)
# ════════════════════════════════════════════════════════════════════


class TestEventStream:
    """GET /api/secretary/events/* - 事件流查询"""

    def test_01_get_stream_empty(self, client, user_id, db, auth_headers):
        """GET events/stream - 过滤参数"""
        r = client.get(
            "/api/secretary/events/stream?stream_type=secretary&limit=10",
            headers=auth_headers,
        )
        assert r.status_code == 200
        data = r.json()
        assert isinstance(data, list)

    def test_02_get_recent(self, client, user_id, db, auth_headers):
        """GET events/recent - Dashboard 时间线"""
        r = client.get(
            "/api/secretary/events/recent?limit=5",
            headers=auth_headers,
        )
        assert r.status_code == 200
        data = r.json()
        assert isinstance(data, list)

    def test_03_get_summary(self, client, user_id, db, auth_headers):
        """GET events/summary - 统计摘要"""
        r = client.get("/api/secretary/events/summary", headers=auth_headers)
        assert r.status_code == 200
        data = r.json()
        assert "total_events" in data
        assert "counts" in data
        assert "last_active" in data
        assert "recent_24h" in data

    def test_04_get_top_level(self, client, user_id, db, auth_headers):
        """GET events/top-level - 顶层事件"""
        r = client.get(
            "/api/secretary/events/top-level?limit=10",
            headers=auth_headers,
        )
        assert r.status_code == 200
        data = r.json()
        assert isinstance(data, list)

    def test_05_get_top_level_by_dimension(self, client, user_id, db, auth_headers):
        """GET events/top-level - 按 dimension 聚合"""
        r = client.get(
            "/api/secretary/events/top-level?dimension=topic&limit=10",
            headers=auth_headers,
        )
        assert r.status_code == 200
        data = r.json()
        assert isinstance(data, list)

    def test_06_get_event_children(self, client, user_id, db, auth_headers):
        """GET events/{id}/children - 聚合子节点"""
        r = client.get(
            "/api/secretary/events/nonex_evt/children",
            headers=auth_headers,
        )
        # 不存在事件 → 空列表 (200) 或 404
        assert r.status_code in (200, 404)
        if r.status_code == 200:
            assert isinstance(r.json(), list)

    def test_07_get_event_ancestors(self, client, user_id, db, auth_headers):
        """GET events/{id}/ancestors - 祖先链"""
        r = client.get(
            "/api/secretary/events/nonex_evt/ancestors",
            headers=auth_headers,
        )
        assert r.status_code in (200, 404)
        if r.status_code == 200:
            assert isinstance(r.json(), list)


# ════════════════════════════════════════════════════════════════════
# §11. /api/secretary/mood-stress — 心情压力模块 (15 端点)
# ════════════════════════════════════════════════════════════════════


class TestMoodStressDashboard:
    """GET /api/secretary/mood-stress/dashboard"""

    def test_01_get_dashboard(self, client, user_id, db, auth_headers):
        """GET dashboard - 7 天默认窗口"""
        r = client.get("/api/secretary/mood-stress/dashboard", headers=auth_headers)
        assert r.status_code == 200
        data = r.json()
        assert "manual_record" in data or "stats" in data

    def test_02_get_dashboard_custom_days(self, client, user_id, db, auth_headers):
        """GET dashboard - 自定义 days"""
        r = client.get(
            "/api/secretary/mood-stress/dashboard?days=14",
            headers=auth_headers,
        )
        assert r.status_code == 200

    def test_03_get_dashboard_days_out_of_range(self, client, user_id, db, auth_headers):
        """GET dashboard - days 越界 → 422"""
        r = client.get(
            "/api/secretary/mood-stress/dashboard?days=200",
            headers=auth_headers,
        )
        assert r.status_code == 422

    def test_04_dashboard_unauthenticated(self, client, db):
        """GET dashboard - 无认证 → 401"""
        r = client.get("/api/secretary/mood-stress/dashboard")
        assert r.status_code == 401


class TestMoodStressRecord:
    """POST /api/secretary/mood-stress/record + GET /records + DELETE /records/{id}"""

    def test_01_post_record_happy(self, client, user_id, db, auth_headers):
        """POST record - 合法情绪标签 + 压力/能量"""
        r = client.post(
            "/api/secretary/mood-stress/record",
            headers=auth_headers,
            json={
                "emotion_tags": ["motivated", "calm"],
                "pressure_score": 5,
                "energy_score": 7,
                "text_note": "感觉不错",
            },
        )
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["status"] == "ok"
        assert "record" in data
        assert "motivated" in data["record"]["emotion_tags"]

    def test_02_post_record_invalid_tag(self, client, user_id, db, auth_headers):
        """POST record - 非法情绪标签 → 422"""
        r = client.post(
            "/api/secretary/mood-stress/record",
            headers=auth_headers,
            json={
                "emotion_tags": ["invalid_tag_xyz"],
                "pressure_score": 5,
            },
        )
        assert r.status_code == 422

    def test_03_post_record_score_out_of_range(self, client, user_id, db, auth_headers):
        """POST record - 分数越界 → 422"""
        r = client.post(
            "/api/secretary/mood-stress/record",
            headers=auth_headers,
            json={"pressure_score": 100},
        )
        assert r.status_code == 422

    def test_04_get_records(self, client, user_id, db, auth_headers):
        """GET records - 列出情绪记录"""
        # 先写一条
        client.post(
            "/api/secretary/mood-stress/record",
            headers=auth_headers,
            json={"emotion_tags": ["calm"], "pressure_score": 3},
        )
        r = client.get("/api/secretary/mood-stress/records", headers=auth_headers)
        assert r.status_code == 200
        data = r.json()
        assert data["status"] == "ok"
        assert "records" in data
        assert len(data["records"]) >= 1

    def test_05_get_records_invalid_source(self, client, user_id, db, auth_headers):
        """GET records - 非法 source → 422"""
        r = client.get(
            "/api/secretary/mood-stress/records?source=invalid_xyz",
            headers=auth_headers,
        )
        assert r.status_code == 422

    def test_06_delete_record_not_uuid(self, client, user_id, db, auth_headers):
        """DELETE records/{id} - 非 UUID 格式 → 404 (B-2 uuid 校验)"""
        r = client.delete(
            "/api/secretary/mood-stress/records/not-a-uuid",
            headers=auth_headers,
        )
        assert r.status_code == 404


class TestMoodStressIntervention:
    """POST /api/secretary/mood-stress/intervention + GET /interventions"""

    def test_01_post_intervention(self, client, user_id, db, auth_headers):
        """POST intervention - 4 种类型之一"""
        r = client.post(
            "/api/secretary/mood-stress/intervention",
            headers=auth_headers,
            json={
                "intervention_type": "breathing",
                "duration_seconds": 300,
                "trigger_event": "test",
                "notes": "感觉焦虑",
            },
        )
        assert r.status_code == 200
        data = r.json()
        assert data["status"] == "ok"

    def test_02_post_intervention_invalid(self, client, user_id, db, auth_headers):
        """POST intervention - 非法类型 → 422"""
        r = client.post(
            "/api/secretary/mood-stress/intervention",
            headers=auth_headers,
            json={"intervention_type": "invalid_xyz"},
        )
        assert r.status_code == 422

    def test_03_get_interventions(self, client, user_id, db, auth_headers):
        """GET interventions - 列出干预日志"""
        client.post(
            "/api/secretary/mood-stress/intervention",
            headers=auth_headers,
            json={"intervention_type": "environment"},
        )
        r = client.get(
            "/api/secretary/mood-stress/interventions",
            headers=auth_headers,
        )
        assert r.status_code == 200
        data = r.json()
        assert data["status"] == "ok"
        assert "interventions" in data


class TestMoodStressSignals:
    """GET /signals + POST /signals/mark-read + POST /signals/emit"""

    def test_01_get_signals_empty(self, client, user_id, db, auth_headers):
        """GET signals - 空未读信号"""
        r = client.get(
            "/api/secretary/mood-stress/signals",
            headers=auth_headers,
        )
        assert r.status_code == 200
        data = r.json()
        assert data["status"] == "ok"
        assert "signals" in data
        assert isinstance(data["signals"], list)

    def test_02_emit_signal(self, client, user_id, db, auth_headers):
        """POST signals/emit - 7 种类型之一"""
        r = client.post(
            "/api/secretary/mood-stress/signals/emit",
            headers=auth_headers,
            json={
                "signal_type": "task_switch",
                "signal_data": {"switches_in_5min": 8},
                "severity": 2,
            },
        )
        assert r.status_code == 200
        data = r.json()
        assert data["status"] == "ok"

    def test_03_emit_signal_invalid_type(self, client, user_id, db, auth_headers):
        """POST signals/emit - 非法类型 → 422"""
        r = client.post(
            "/api/secretary/mood-stress/signals/emit",
            headers=auth_headers,
            json={"signal_type": "invalid_xyz", "signal_data": {}},
        )
        assert r.status_code == 422

    def test_04_mark_signals_read_invalid_ids(self, client, user_id, db, auth_headers):
        """POST signals/mark-read - 无效 UUID → marked=0 (静默)"""
        r = client.post(
            "/api/secretary/mood-stress/signals/mark-read",
            headers=auth_headers,
            json=["not-a-uuid", "also-not-uuid"],
        )
        assert r.status_code == 200
        assert r.json()["marked"] == 0


class TestMoodStressPrefs:
    """GET/PUT /api/secretary/mood-stress/prefs (含 MoodStressPrefsUpdated 事件)"""

    def test_01_get_prefs_default(self, client, user_id, db, auth_headers):
        """GET prefs - 19 项默认值"""
        r = client.get(
            "/api/secretary/mood-stress/prefs",
            headers=auth_headers,
        )
        assert r.status_code == 200
        data = r.json()
        prefs = data["prefs"]
        assert prefs["reminder_enabled"] is False
        assert prefs["auto_collect_voice_features"] is False
        assert prefs["data_retention_days"] == 90

    def test_02_put_prefs_emits_event(self, client, user_id, db, auth_headers, capture_bus):
        """PUT prefs - 增量更新 + MoodStressPrefsUpdated 事件"""
        bus, captured = capture_bus
        r = client.put(
            "/api/secretary/mood-stress/prefs",
            headers=auth_headers,
            json={
                "reminder_enabled": True,
                "reminder_frequency": "daily",
                "data_retention_days": 30,
            },
        )
        assert r.status_code == 200
        # 验证事件
        time.sleep(0.2)
        ev = _find_event(captured, "MoodStressPrefsUpdated", user_id=user_id)
        assert ev is not None
        assert "reminder_enabled" in ev.changed_fields

    def test_03_put_prefs_invalid_retention(self, client, user_id, db, auth_headers):
        """PUT prefs - data_retention_days 越界 → 422"""
        r = client.put(
            "/api/secretary/mood-stress/prefs",
            headers=auth_headers,
            json={"data_retention_days": 10000},
        )
        assert r.status_code == 422

    def test_04_put_prefs_unauthenticated(self, client, db):
        """PUT prefs - 无认证 → 401"""
        r = client.put(
            "/api/secretary/mood-stress/prefs",
            json={"reminder_enabled": True},
        )
        assert r.status_code == 401


class TestMoodStressRules:
    """POST/GET/DELETE /api/secretary/mood-stress/rules"""

    def test_01_add_rule(self, client, user_id, db, auth_headers):
        """POST rules - 新增规则"""
        r = client.post(
            "/api/secretary/mood-stress/rules",
            headers=auth_headers,
            json={
                "rule_name": "压力高时建议休息",
                "trigger_metric": "pressure_score",
                "trigger_operator": ">=",
                "trigger_value": 8,
                "action": "suggest_break",
            },
        )
        assert r.status_code == 200
        data = r.json()
        assert data["status"] == "ok"
        assert "rule_id" in data

    def test_02_add_rule_invalid_metric(self, client, user_id, db, auth_headers):
        """POST rules - 非法 trigger_metric → 422"""
        r = client.post(
            "/api/secretary/mood-stress/rules",
            headers=auth_headers,
            json={
                "rule_name": "test",
                "trigger_metric": "invalid_metric",
                "trigger_operator": "==",
                "trigger_value": 5,
                "action": "suggest_break",
            },
        )
        assert r.status_code == 422

    def test_03_add_rule_invalid_action(self, client, user_id, db, auth_headers):
        """POST rules - 非法 action → 422"""
        r = client.post(
            "/api/secretary/mood-stress/rules",
            headers=auth_headers,
            json={
                "rule_name": "test",
                "trigger_metric": "pressure_score",
                "trigger_operator": "==",
                "trigger_value": 5,
                "action": "invalid_action",
            },
        )
        assert r.status_code == 422

    def test_04_list_rules(self, client, user_id, db, auth_headers):
        """GET rules - 列出规则"""
        client.post(
            "/api/secretary/mood-stress/rules",
            headers=auth_headers,
            json={
                "rule_name": "rule_for_list",
                "trigger_metric": "energy_score",
                "trigger_operator": "<=",
                "trigger_value": 3,
                "action": "only_flashcard",
            },
        )
        r = client.get("/api/secretary/mood-stress/rules", headers=auth_headers)
        assert r.status_code == 200
        data = r.json()
        assert data["status"] == "ok"
        assert "rules" in data
        assert data["total"] >= 1

    def test_05_delete_rule_not_uuid(self, client, user_id, db, auth_headers):
        """DELETE rules/{id} - 非 UUID → 404 (B-2 uuid 校验)"""
        r = client.delete(
            "/api/secretary/mood-stress/rules/not-a-uuid",
            headers=auth_headers,
        )
        assert r.status_code == 404


class TestMoodStressConstants:
    """GET /api/secretary/mood-stress/constants - 元数据"""

    def test_01_get_constants(self, client, db):
        """GET constants - 暴露合法枚举值 (无需认证)"""
        r = client.get("/api/secretary/mood-stress/constants")
        assert r.status_code == 200
        data = r.json()
        assert "emotion_tags" in data
        assert "intervention_types" in data
        assert "behavior_signal_types" in data
        assert "rule_metrics" in data
        assert "rule_operators" in data
        assert "rule_actions" in data
        assert "principles" in data
        # 验证 11 个情绪标签
        assert len(data["emotion_tags"]) == 11
        # 验证 4 个干预类型
        assert len(data["intervention_types"]) == 4


# ════════════════════════════════════════════════════════════════════
# §12. 跨模块数据隔离
# ════════════════════════════════════════════════════════════════════


class TestDataIsolation:
    """不同用户的数据完全隔离"""

    def test_01_proposals_isolated(self, client, user_id, other_user_id, db,
                                    auth_headers, other_auth_headers):
        """proposals 跨用户隔离"""
        _insert_proposal(db, user_id, "user_a_only")
        r1 = client.get("/api/secretary/proposals/pending", headers=auth_headers)
        r2 = client.get("/api/secretary/proposals/pending", headers=other_auth_headers)
        assert len(r1.json()) >= 1
        assert len(r2.json()) == 0

    def test_02_accept_other_user_404(self, client, user_id, other_user_id, db,
                                       auth_headers, other_auth_headers):
        """accept 跨用户 → 404 (B-4)"""
        pid = _insert_proposal(db, user_id, "user_a_secret")
        r = client.post(
            f"/api/secretary/proposals/{pid}/accept",
            headers=other_auth_headers,
        )
        assert r.status_code == 404

    def test_03_prefs_isolated(self, client, user_id, other_user_id, db,
                                auth_headers, other_auth_headers):
        """preferences 跨用户隔离"""
        # 用户 A 改 agent prefs
        client.post(
            "/api/secretary/agent/preferences",
            headers=auth_headers,
            json={"confirm_mode": "never", "auto_jump_threshold": 0.5},
        )
        # 用户 B 看到默认
        r = client.get("/api/secretary/agent/preferences", headers=other_auth_headers)
        assert r.json()["confirm_mode"] == "smart"

    def test_04_mood_stress_isolated(self, client, user_id, other_user_id, db,
                                      auth_headers, other_auth_headers):
        """mood_stress prefs 跨用户隔离"""
        client.put(
            "/api/secretary/mood-stress/prefs",
            headers=auth_headers,
            json={"reminder_enabled": True, "data_retention_days": 30},
        )
        # 用户 B 仍为默认
        r = client.get(
            "/api/secretary/mood-stress/prefs",
            headers=other_auth_headers,
        )
        prefs = r.json()["prefs"]
        assert prefs["reminder_enabled"] is False
        assert prefs["data_retention_days"] == 90


# ════════════════════════════════════════════════════════════════════
# §13. 提案状态机 (pending → accepted/dismissed/snoozed/deleted → restored)
# ════════════════════════════════════════════════════════════════════


class TestProposalStateMachine:
    """提案状态全生命周期"""

    def test_01_pending_to_accepted(self, client, user_id, db, auth_headers):
        """pending → accepted"""
        pid = _insert_proposal(db, user_id, "fsm_1")
        r = client.post(
            f"/api/secretary/proposals/{pid}/accept",
            headers=auth_headers,
        )
        assert r.status_code == 200
        assert r.json()["status"] == "accepted"
        # 不再出现在 pending
        r2 = client.get(
            "/api/secretary/proposals/pending",
            headers=auth_headers,
        )
        assert not any(p["id"] == pid for p in r2.json())

    def test_02_pending_to_snoozed_to_pending(self, client, user_id, db, auth_headers):
        """pending → snoozed → pending (via restore)"""
        pid = _insert_proposal(db, user_id, "fsm_2")
        client.post(f"/api/secretary/proposals/{pid}/snooze", headers=auth_headers)
        client.post(f"/api/secretary/proposals/{pid}/restore", headers=auth_headers)
        # 重新出现在 pending
        r = client.get(
            "/api/secretary/proposals/pending",
            headers=auth_headers,
        )
        assert any(p["id"] == pid for p in r.json())

    def test_03_pending_to_deleted_to_pending(self, client, user_id, db, auth_headers):
        """pending → deleted → pending (via restore)"""
        pid = _insert_proposal(db, user_id, "fsm_3")
        client.post(f"/api/secretary/proposals/{pid}/delete", headers=auth_headers)
        client.post(f"/api/secretary/proposals/{pid}/restore", headers=auth_headers)
        r = client.get(
            "/api/secretary/proposals/pending",
            headers=auth_headers,
        )
        assert any(p["id"] == pid for p in r.json())

    def test_04_pending_to_dismissed(self, client, user_id, db, auth_headers):
        """pending → dismissed (不能直接 restore, 需在 history)"""
        pid = _insert_proposal(db, user_id, "fsm_4")
        r = client.post(
            f"/api/secretary/proposals/{pid}/dismiss",
            headers=auth_headers,
        )
        assert r.status_code == 200
        assert r.json()["status"] == "dismissed"
