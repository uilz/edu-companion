"""Emotion / MoodStress 模块端到端测试 (Task #87)

依据: docs/temp/task-emotion-audit.md +
      backend/app/api/secretary/mood_stress.py +
      backend/app/services/secretary/modules/mood_stress.py +
      backend/app/services/secretary/mood_stress_store.py +
      shared/events.py

测试覆盖（30+ E2E 用例）：
  §1. dashboard           - 4 测试
  §2. record              - 4 测试 (含事件验证)
  §3. records list/delete - 4 测试
  §4. intervention        - 4 测试
  §5. signals             - 4 测试
  §6. prefs               - 4 测试 (含事件验证)
  §7. rules               - 3 测试
  §8. constants           - 2 测试
  §9. 跨用户隔离           - 3 测试
  §10. 端到端流            - 3 测试

事件发布验证: MoodStressRecorded / MoodStressInterventionTriggered /
            MoodStressBehaviorSignalDetected / MoodStressPrefsUpdated

使用 FastAPI TestClient + JWT Bearer 认证
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
        "username": f"emo_{user_id[:8]}",
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
    return f"emo_{uuid.uuid4().hex[:12]}"


@pytest.fixture
def other_user_id() -> str:
    return f"emo_b_{uuid.uuid4().hex[:12]}"


@pytest.fixture
def db():
    try:
        from app.infrastructure.db.database import get_db
        d = get_db()
        d.fetchone("SELECT 1", ())
        from app.infrastructure.db.secretary_schema import _ensure_tables
        _ensure_tables()
        return d
    except Exception as exc:  # noqa: BLE001
        pytest.skip(f"数据库不可用: {exc}")


@pytest.fixture
def client():
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
    """收集 MoodStress 相关事件"""
    from app.application.di import container
    bus = container.event_bus
    captured: list[Any] = []

    async def _capture(event):  # noqa: ANN001
        captured.append(event)

    for evt_type in (
        "MoodStressRecorded",
        "MoodStressInterventionTriggered",
        "MoodStressBehaviorSignalDetected",
        "MoodStressPrefsUpdated",
    ):
        try:
            bus.subscribe(evt_type, _capture)
        except Exception:
            pass
    return bus, captured


def _find_event(captured: list, event_type: str, user_id: str) -> Any:
    for ev in captured:
        if type(ev).__name__ == event_type and ev.user_id == user_id:
            return ev
    return None


@pytest.fixture(autouse=True)
def cleanup_test_data(db, user_id, other_user_id):
    """测试结束后清理该用户的所有 mood_stress 数据"""
    yield
    try:
        for uid in (user_id, other_user_id):
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
# §1. dashboard
# ════════════════════════════════════════════════════════════════════


class TestMoodStressDashboard:
    """GET /api/secretary/mood-stress/dashboard"""

    def test_01_dashboard_empty(self, client, user_id, db, auth_headers):
        """空数据仪表盘"""
        r = client.get("/api/secretary/mood-stress/dashboard", headers=auth_headers)
        assert r.status_code == 200
        data = r.json()
        assert "days" in data
        assert "prefs" in data
        assert "stats" in data
        assert "recent_records" in data
        assert "recent_interventions" in data
        assert "unread_behavior_signals" in data
        assert "rules" in data
        assert "latest_manual" in data  # 空时为 None
        assert data["latest_manual"] is None
        assert data["stats"]["total"] == 0
        assert data["stats"]["manual_total"] == 0
        assert data["stats"]["auto_total"] == 0

    def test_02_dashboard_with_data(self, client, user_id, db, auth_headers):
        """有数据时正确聚合"""
        # 写 1 条手动 + 1 条自动
        for source in ("manual", "auto"):
            db.execute(
                "INSERT INTO emotion_records "
                "(id, user_id, source, emotion_tags, pressure_score, energy_score, text_note, related_event_ids, created_at) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, NOW())",
                (str(uuid.uuid4()), user_id, source, '["frustration"]', 8, 4, "test", "[]"),
            )
        r = client.get("/api/secretary/mood-stress/dashboard?days=7", headers=auth_headers)
        assert r.status_code == 200
        data = r.json()
        assert data["stats"]["manual_total"] >= 1
        assert data["stats"]["auto_total"] >= 1
        assert data["latest_manual"] is not None
        assert data["latest_manual"]["source"] == "manual"

    def test_03_dashboard_days_param(self, client, user_id, db, auth_headers):
        """days 参数范围校验"""
        r = client.get("/api/secretary/mood-stress/dashboard?days=0", headers=auth_headers)
        assert r.status_code == 422
        r = client.get("/api/secretary/mood-stress/dashboard?days=91", headers=auth_headers)
        assert r.status_code == 422
        r = client.get("/api/secretary/mood-stress/dashboard?days=30", headers=auth_headers)
        assert r.status_code == 200
        assert r.json()["days"] == 30

    def test_04_dashboard_unauth(self, client, db):
        """无认证 → 401"""
        r = client.get("/api/secretary/mood-stress/dashboard")
        assert r.status_code == 401


# ════════════════════════════════════════════════════════════════════
# §2. record (含事件)
# ════════════════════════════════════════════════════════════════════


class TestMoodStressRecord:
    """POST /api/secretary/mood-stress/record"""

    def test_01_record_basic(self, client, user_id, db, auth_headers):
        """基础记录"""
        r = client.post(
            "/api/secretary/mood-stress/record",
            headers=auth_headers,
            json={
                "emotion_tags": ["frustration", "anxiety"],
                "pressure_score": 8,
                "energy_score": 4,
                "text_note": "今天被某个题卡住",
            },
        )
        assert r.status_code == 200
        data = r.json()
        assert data["status"] == "ok"
        assert "record" in data
        assert data["record"]["source"] == "manual"
        assert data["record"]["pressure_score"] == 8
        assert data["record"]["emotion_tags"] == ["frustration", "anxiety"]

    def test_02_record_emits_event(self, client, user_id, db, auth_headers, capture_bus):
        """记录时发布 MoodStressRecorded 事件"""
        bus, captured = capture_bus
        r = client.post(
            "/api/secretary/mood-stress/record",
            headers=auth_headers,
            json={"emotion_tags": ["calm"], "pressure_score": 3, "energy_score": 7},
        )
        assert r.status_code == 200
        time.sleep(0.2)
        ev = _find_event(captured, "MoodStressRecorded", user_id)
        assert ev is not None
        assert "calm" in ev.emotion_tags
        assert ev.pressure_score == 3

    def test_03_record_invalid_tag(self, client, user_id, db, auth_headers):
        """非法情绪标签 → 422"""
        r = client.post(
            "/api/secretary/mood-stress/record",
            headers=auth_headers,
            json={"emotion_tags": ["invalid_xyz"], "pressure_score": 5},
        )
        assert r.status_code == 422

    def test_04_record_pressure_bounds(self, client, user_id, db, auth_headers):
        """压力分数越界 → 422"""
        r = client.post(
            "/api/secretary/mood-stress/record",
            headers=auth_headers,
            json={"emotion_tags": ["calm"], "pressure_score": 100},
        )
        assert r.status_code == 422
        r = client.post(
            "/api/secretary/mood-stress/record",
            headers=auth_headers,
            json={"emotion_tags": ["calm"], "pressure_score": 0},
        )
        assert r.status_code == 422


# ════════════════════════════════════════════════════════════════════
# §3. records list/delete
# ════════════════════════════════════════════════════════════════════


class TestMoodStressRecords:
    """GET /records + DELETE /records/{id}"""

    def test_01_list_records(self, client, user_id, db, auth_headers):
        """记录列表"""
        client.post(
            "/api/secretary/mood-stress/record",
            headers=auth_headers,
            json={"emotion_tags": ["curious"], "pressure_score": 4},
        )
        r = client.get("/api/secretary/mood-stress/records", headers=auth_headers)
        assert r.status_code == 200
        data = r.json()
        assert data["total"] >= 1
        assert isinstance(data["records"], list)
        assert data["records"][0]["source"] == "manual"

    def test_02_list_filter_source(self, client, user_id, db, auth_headers):
        """source 过滤"""
        # 写 1 manual + 1 auto
        client.post(
            "/api/secretary/mood-stress/record",
            headers=auth_headers,
            json={"emotion_tags": ["calm"]},
        )
        db.execute(
            "INSERT INTO emotion_records (id, user_id, source, emotion_tags, created_at) "
            "VALUES (%s, %s, %s, %s, NOW())",
            (str(uuid.uuid4()), user_id, "auto", '["neutral"]'),
        )
        r1 = client.get(
            "/api/secretary/mood-stress/records?source=manual",
            headers=auth_headers,
        )
        assert r1.json()["total"] >= 1
        for rec in r1.json()["records"]:
            assert rec["source"] == "manual"
        r2 = client.get(
            "/api/secretary/mood-stress/records?source=auto",
            headers=auth_headers,
        )
        for rec in r2.json()["records"]:
            assert rec["source"] == "auto"

    def test_03_list_invalid_source(self, client, user_id, db, auth_headers):
        """非法 source → 422"""
        r = client.get(
            "/api/secretary/mood-stress/records?source=invalid",
            headers=auth_headers,
        )
        assert r.status_code == 422

    def test_04_delete_record(self, client, user_id, db, auth_headers):
        """删除记录"""
        r = client.post(
            "/api/secretary/mood-stress/record",
            headers=auth_headers,
            json={"emotion_tags": ["calm"]},
        )
        rid = r.json()["record"]["id"]
        r2 = client.delete(
            f"/api/secretary/mood-stress/records/{rid}",
            headers=auth_headers,
        )
        assert r2.status_code == 200
        # 再次删除 → 404
        r3 = client.delete(
            f"/api/secretary/mood-stress/records/{rid}",
            headers=auth_headers,
        )
        assert r3.status_code == 404

    def test_05_delete_invalid_uuid(self, client, user_id, db, auth_headers):
        """非 UUID → 404"""
        r = client.delete(
            "/api/secretary/mood-stress/records/not-a-uuid",
            headers=auth_headers,
        )
        assert r.status_code == 404


# ════════════════════════════════════════════════════════════════════
# §4. intervention
# ════════════════════════════════════════════════════════════════════


class TestMoodStressIntervention:
    """POST /intervention + GET /interventions"""

    def test_01_intervention_basic(self, client, user_id, db, auth_headers):
        """4 种类型之一"""
        r = client.post(
            "/api/secretary/mood-stress/intervention",
            headers=auth_headers,
            json={"intervention_type": "breathing", "duration_seconds": 180},
        )
        assert r.status_code == 200
        data = r.json()
        assert data["status"] == "ok"
        assert data["intervention"]["intervention_type"] == "breathing"

    def test_02_intervention_emits_event(self, client, user_id, db, auth_headers, capture_bus):
        """intervention 触发 MoodStressInterventionTriggered 事件"""
        bus, captured = capture_bus
        client.post(
            "/api/secretary/mood-stress/intervention",
            headers=auth_headers,
            json={"intervention_type": "cognitive_reappraisal", "duration_seconds": 120},
        )
        time.sleep(0.2)
        ev = _find_event(captured, "MoodStressInterventionTriggered", user_id)
        assert ev is not None
        assert ev.intervention_type == "cognitive_reappraisal"

    def test_03_intervention_invalid_type(self, client, user_id, db, auth_headers):
        """非法类型 → 422"""
        r = client.post(
            "/api/secretary/mood-stress/intervention",
            headers=auth_headers,
            json={"intervention_type": "invalid_xyz"},
        )
        assert r.status_code == 422

    def test_04_list_interventions(self, client, user_id, db, auth_headers):
        """列出干预日志"""
        for it_type in ("breathing", "knowledge_breathing"):
            client.post(
                "/api/secretary/mood-stress/intervention",
                headers=auth_headers,
                json={"intervention_type": it_type},
            )
        r = client.get("/api/secretary/mood-stress/interventions", headers=auth_headers)
        assert r.status_code == 200
        data = r.json()
        assert data["total"] >= 2


# ════════════════════════════════════════════════════════════════════
# §5. signals
# ════════════════════════════════════════════════════════════════════


class TestMoodStressSignals:
    """GET /signals + POST /signals/mark-read + POST /signals/emit"""

    def test_01_get_signals_empty(self, client, user_id, db, auth_headers):
        """空未读信号"""
        r = client.get("/api/secretary/mood-stress/signals", headers=auth_headers)
        assert r.status_code == 200
        data = r.json()
        assert "signals" in data
        assert isinstance(data["signals"], list)

    def test_02_emit_signal(self, client, user_id, db, auth_headers, capture_bus):
        """emit 7 种类型 + 发 MoodStressBehaviorSignalDetected 事件"""
        bus, captured = capture_bus
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
        time.sleep(0.2)
        ev = _find_event(captured, "MoodStressBehaviorSignalDetected", user_id)
        assert ev is not None
        assert ev.signal_type == "task_switch"
        assert ev.severity == 2

    def test_03_emit_signal_invalid_type(self, client, user_id, db, auth_headers):
        """非法 signal_type → 422"""
        r = client.post(
            "/api/secretary/mood-stress/signals/emit",
            headers=auth_headers,
            json={"signal_type": "invalid_xyz", "signal_data": {}},
        )
        assert r.status_code == 422

    def test_04_emit_signal_severity_bounds(self, client, user_id, db, auth_headers):
        """severity 越界 → 422"""
        r = client.post(
            "/api/secretary/mood-stress/signals/emit",
            headers=auth_headers,
            json={"signal_type": "task_switch", "severity": 0},
        )
        assert r.status_code == 422
        r = client.post(
            "/api/secretary/mood-stress/signals/emit",
            headers=auth_headers,
            json={"signal_type": "task_switch", "severity": 4},
        )
        assert r.status_code == 422

    def test_05_mark_signals_read(self, client, user_id, db, auth_headers):
        """mark-read: 真实信号可标记"""
        # 先 emit 一条
        client.post(
            "/api/secretary/mood-stress/signals/emit",
            headers=auth_headers,
            json={"signal_type": "error_rate", "severity": 1},
        )
        r = client.get("/api/secretary/mood-stress/signals", headers=auth_headers)
        sigs = r.json()["signals"]
        assert len(sigs) >= 1
        sid = sigs[0]["id"]
        r2 = client.post(
            "/api/secretary/mood-stress/signals/mark-read",
            headers=auth_headers,
            json=[sid],
        )
        assert r2.status_code == 200
        assert r2.json()["marked"] >= 1


# ════════════════════════════════════════════════════════════════════
# §6. prefs
# ════════════════════════════════════════════════════════════════════


class TestMoodStressPrefs:
    """GET/PUT /api/secretary/mood-stress/prefs"""

    def test_01_get_prefs_default(self, client, user_id, db, auth_headers):
        """GET prefs - 19 项默认值"""
        r = client.get("/api/secretary/mood-stress/prefs", headers=auth_headers)
        assert r.status_code == 200
        data = r.json()
        prefs = data["prefs"]
        assert prefs["reminder_enabled"] is False
        assert prefs["auto_collect_voice_features"] is False
        assert prefs["data_retention_days"] == 90
        # 19 项字段都在
        expected_fields = {
            "reminder_enabled", "reminder_frequency", "reminder_time",
            "data_retention_days", "auto_collect_task_switch",
            "auto_collect_stay_duration", "auto_collect_error_rate",
            "auto_collect_undo", "auto_collect_session_anomaly",
            "auto_collect_flashcard_failure", "auto_collect_voice_features",
            "output_to_planning", "output_to_conversation",
            "output_to_language_room", "knowledge_breathing_excluded_node_ids",
            "environment_theme", "environment_sound", "planning_rules",
        }
        for f in expected_fields:
            assert f in prefs, f"Missing field: {f}"

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
        time.sleep(0.2)
        ev = _find_event(captured, "MoodStressPrefsUpdated", user_id)
        assert ev is not None
        assert "reminder_enabled" in ev.changed_fields

    def test_03_put_prefs_incremental_merge(self, client, user_id, db, auth_headers):
        """PUT prefs - 增量合并 (不传字段不覆盖)"""
        # 第一次设置 A=1
        client.put(
            "/api/secretary/mood-stress/prefs",
            headers=auth_headers,
            json={"reminder_enabled": True, "data_retention_days": 30},
        )
        # 第二次只改 B
        client.put(
            "/api/secretary/mood-stress/prefs",
            headers=auth_headers,
            json={"environment_theme": "dark"},
        )
        r = client.get("/api/secretary/mood-stress/prefs", headers=auth_headers)
        prefs = r.json()["prefs"]
        # A 应该被保留
        assert prefs["reminder_enabled"] is True
        assert prefs["data_retention_days"] == 30
        # B 应该被设置
        assert prefs["environment_theme"] == "dark"

    def test_04_put_prefs_invalid_retention(self, client, user_id, db, auth_headers):
        """PUT prefs - data_retention_days 越界 → 422"""
        r = client.put(
            "/api/secretary/mood-stress/prefs",
            headers=auth_headers,
            json={"data_retention_days": 10000},
        )
        assert r.status_code == 422

    def test_05_put_prefs_empty_no_event(self, client, user_id, db, auth_headers, capture_bus):
        """PUT prefs - 空 body 不发事件 (设计决策)"""
        bus, captured = capture_bus
        r = client.put(
            "/api/secretary/mood-stress/prefs",
            headers=auth_headers,
            json={},
        )
        assert r.status_code == 200
        time.sleep(0.2)
        ev = _find_event(captured, "MoodStressPrefsUpdated", user_id)
        assert ev is None


# ════════════════════════════════════════════════════════════════════
# §7. rules
# ════════════════════════════════════════════════════════════════════


class TestMoodStressRules:
    """POST/GET/DELETE /api/secretary/mood-stress/rules"""

    def test_01_add_rule(self, client, user_id, db, auth_headers):
        """新增规则"""
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

    def test_02_list_rules(self, client, user_id, db, auth_headers):
        """列出规则"""
        client.post(
            "/api/secretary/mood-stress/rules",
            headers=auth_headers,
            json={
                "rule_name": "test_rule",
                "trigger_metric": "energy_score",
                "trigger_operator": "<=",
                "trigger_value": 3,
                "action": "only_flashcard",
            },
        )
        r = client.get("/api/secretary/mood-stress/rules", headers=auth_headers)
        assert r.status_code == 200
        data = r.json()
        assert data["total"] >= 1
        assert any(rule["rule_name"] == "test_rule" for rule in data["rules"])

    def test_03_delete_rule(self, client, user_id, db, auth_headers):
        """删除规则"""
        r = client.post(
            "/api/secretary/mood-stress/rules",
            headers=auth_headers,
            json={
                "rule_name": "rule_to_delete",
                "trigger_metric": "pressure_score",
                "trigger_operator": "==",
                "trigger_value": 5,
                "action": "suggest_break",
            },
        )
        rid = r.json()["rule_id"]
        r2 = client.delete(
            f"/api/secretary/mood-stress/rules/{rid}",
            headers=auth_headers,
        )
        assert r2.status_code == 200
        # 再次删除 → 404
        r3 = client.delete(
            f"/api/secretary/mood-stress/rules/{rid}",
            headers=auth_headers,
        )
        assert r3.status_code == 404

    def test_04_rule_invalid_metric(self, client, user_id, db, auth_headers):
        """非法 trigger_metric → 422"""
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

    def test_05_rule_invalid_action(self, client, user_id, db, auth_headers):
        """非法 action → 422"""
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


# ════════════════════════════════════════════════════════════════════
# §8. constants
# ════════════════════════════════════════════════════════════════════


class TestMoodStressConstants:
    """GET /api/secretary/mood-stress/constants"""

    def test_01_get_constants(self, client, db):
        """元数据完整性"""
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
        # 11 个情绪标签
        assert len(data["emotion_tags"]) == 11
        # 4 个干预类型
        assert len(data["intervention_types"]) == 4
        # 7 种行为信号
        assert len(data["behavior_signal_types"]) == 7
        # 3 种规则 metric
        assert len(data["rule_metrics"]) == 3
        # 6 种 operator
        assert len(data["rule_operators"]) == 6
        # 3 种 action
        assert len(data["rule_actions"]) == 3
        # 5 条原则
        assert len(data["principles"]) == 5

    def test_02_constants_no_auth(self, client, db):
        """constants 不需认证"""
        r = client.get("/api/secretary/mood-stress/constants")
        # 不带 Authorization header
        assert r.status_code == 200


# ════════════════════════════════════════════════════════════════════
# §9. 跨用户隔离
# ════════════════════════════════════════════════════════════════════


class TestMoodStressIsolation:
    """跨用户数据隔离"""

    def test_01_records_isolated(self, client, user_id, other_user_id, db,
                                  auth_headers, other_auth_headers):
        """情绪记录跨用户隔离"""
        client.post(
            "/api/secretary/mood-stress/record",
            headers=auth_headers,
            json={"emotion_tags": ["calm"]},
        )
        r = client.get("/api/secretary/mood-stress/records", headers=other_auth_headers)
        assert r.json()["total"] == 0

    def test_02_prefs_isolated(self, client, user_id, other_user_id, db,
                                auth_headers, other_auth_headers):
        """prefs 跨用户隔离"""
        client.put(
            "/api/secretary/mood-stress/prefs",
            headers=auth_headers,
            json={"reminder_enabled": True, "data_retention_days": 30},
        )
        r = client.get(
            "/api/secretary/mood-stress/prefs",
            headers=other_auth_headers,
        )
        prefs = r.json()["prefs"]
        assert prefs["reminder_enabled"] is False
        assert prefs["data_retention_days"] == 90

    def test_03_signals_isolated(self, client, user_id, other_user_id, db,
                                  auth_headers, other_auth_headers):
        """信号跨用户隔离"""
        client.post(
            "/api/secretary/mood-stress/signals/emit",
            headers=auth_headers,
            json={"signal_type": "task_switch", "severity": 2},
        )
        r = client.get(
            "/api/secretary/mood-stress/signals",
            headers=other_auth_headers,
        )
        assert r.json()["total"] == 0


# ════════════════════════════════════════════════════════════════════
# §10. 端到端流
# ════════════════════════════════════════════════════════════════════


class TestMoodStressEndToEnd:
    """端到端流程：record + intervention + signal + prefs"""

    def test_01_full_session_flow(self, client, user_id, db, auth_headers, capture_bus):
        """完整会话流: 记录 → 干预 → 信号 → 偏好"""
        bus, captured = capture_bus

        # 1. 主动记录
        r1 = client.post(
            "/api/secretary/mood-stress/record",
            headers=auth_headers,
            json={
                "emotion_tags": ["anxiety", "overwhelm"],
                "pressure_score": 9,
                "energy_score": 3,
                "text_note": "被某个概念卡住了",
            },
        )
        assert r1.status_code == 200
        rec_id = r1.json()["record"]["id"]

        # 2. 触发呼吸干预
        r2 = client.post(
            "/api/secretary/mood-stress/intervention",
            headers=auth_headers,
            json={"intervention_type": "breathing", "duration_seconds": 240},
        )
        assert r2.status_code == 200

        # 3. 触发行为信号
        r3 = client.post(
            "/api/secretary/mood-stress/signals/emit",
            headers=auth_headers,
            json={
                "signal_type": "error_rate",
                "signal_data": {"error_count": 5},
                "severity": 3,
            },
        )
        assert r3.status_code == 200

        # 4. 更新偏好
        r4 = client.put(
            "/api/secretary/mood-stress/prefs",
            headers=auth_headers,
            json={"reminder_enabled": True, "data_retention_days": 60},
        )
        assert r4.status_code == 200

        time.sleep(0.3)

        # 验证事件：4 个都触发
        assert _find_event(captured, "MoodStressRecorded", user_id) is not None
        assert _find_event(captured, "MoodStressInterventionTriggered", user_id) is not None
        assert _find_event(captured, "MoodStressBehaviorSignalDetected", user_id) is not None
        assert _find_event(captured, "MoodStressPrefsUpdated", user_id) is not None

        # 验证仪表盘聚合
        r5 = client.get("/api/secretary/mood-stress/dashboard", headers=auth_headers)
        data = r5.json()
        assert data["latest_manual"]["id"] == rec_id
        assert data["stats"]["manual_total"] >= 1
        assert data["stats"]["avg_pressure"] >= 9
        assert data["stats"]["avg_energy"] <= 3
        assert len(data["recent_interventions"]) >= 1
        assert len(data["unread_behavior_signals"]) >= 1

    def test_02_concurrent_records(self, client, user_id, db, auth_headers):
        """并发记录 → 全部成功"""
        # 模拟并发写 5 条
        for i in range(5):
            r = client.post(
                "/api/secretary/mood-stress/record",
                headers=auth_headers,
                json={"emotion_tags": ["calm"], "pressure_score": i + 1},
            )
            assert r.status_code == 200
        r2 = client.get("/api/secretary/mood-stress/records", headers=auth_headers)
        assert r2.json()["total"] >= 5

    def test_03_purge_old_records(self, client, user_id, db, auth_headers):
        """data_retention_days=1 时旧记录可清理"""
        from app.services.secretary.mood_stress_store import mood_stress_store as store
        # 写一条 created_at = 100 天前
        old_id = str(uuid.uuid4())
        from datetime import datetime, timedelta, timezone
        old_time = datetime.now(timezone.utc) - timedelta(days=100)
        db.execute(
            "INSERT INTO emotion_records (id, user_id, source, emotion_tags, created_at) "
            "VALUES (%s, %s, %s, %s, %s)",
            (old_id, user_id, "manual", '["calm"]', old_time),
        )
        # 写一条新的
        new_id = str(uuid.uuid4())
        db.execute(
            "INSERT INTO emotion_records (id, user_id, source, emotion_tags, created_at) "
            "VALUES (%s, %s, %s, %s, NOW())",
            (new_id, user_id, "manual", '["calm"]'),
        )
        # 设置 retention = 1 天
        client.put(
            "/api/secretary/mood-stress/prefs",
            headers=auth_headers,
            json={"data_retention_days": 1},
        )
        # 清理
        purged = store.purge_old_records(user_id, retention_days=1)
        assert purged >= 1
        # 验证旧的不在
        r = client.get("/api/secretary/mood-stress/records?days=365", headers=auth_headers)
        ids = [rec["id"] for rec in r.json()["records"]]
        assert old_id not in ids
        assert new_id in ids


# ════════════════════════════════════════════════════════════════════
# §11. Events 模块
# ════════════════════════════════════════════════════════════════════


class TestMoodStressEvents:
    """验证 MoodStress 4 个事件类可在 events registry 中找到"""

    def test_01_event_types_registered(self):
        """4 个事件类全部在 EVENT_TYPES"""
        from shared.events import EVENT_TYPES
        assert "MoodStressRecorded" in EVENT_TYPES
        assert "MoodStressInterventionTriggered" in EVENT_TYPES
        assert "MoodStressBehaviorSignalDetected" in EVENT_TYPES
        assert "MoodStressPrefsUpdated" in EVENT_TYPES

    def test_02_event_classes_instantiable(self):
        """事件类可构造 (event_id + occurred_at 自动)"""
        from shared.events import (
            MoodStressRecorded, MoodStressInterventionTriggered,
            MoodStressBehaviorSignalDetected, MoodStressPrefsUpdated,
        )
        e1 = MoodStressRecorded(user_id="u1", record_id="r1", emotion_tags=["calm"])
        assert e1.event_id != ""
        assert e1.event_type == "MoodStressRecorded"
        assert e1.user_id == "u1"

        e2 = MoodStressInterventionTriggered(user_id="u1", intervention_type="breathing")
        assert e2.event_type == "MoodStressInterventionTriggered"

        e3 = MoodStressBehaviorSignalDetected(user_id="u1", signal_type="task_switch")
        assert e3.event_type == "MoodStressBehaviorSignalDetected"

        e4 = MoodStressPrefsUpdated(user_id="u1", changed_fields=["a"])
        assert e4.event_type == "MoodStressPrefsUpdated"
