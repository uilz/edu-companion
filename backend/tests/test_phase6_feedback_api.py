"""Phase 6 — 答题反馈 API 测试。

验证：
- submit_answer 返回 attempt_id 且与 practice_attempts.id / AnswerSubmitted.attempt_id 一致。
- GET /api/practice/feedback/{attempt_id} 返回信息增益、掌握度变化、元认知建议。
- 404 / 跨用户隔离 / 兜底投影逻辑。
"""
from __future__ import annotations

import json
import os
import sys
import time
import uuid
from typing import Any

import pytest

BACKEND = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BACKEND not in sys.path:
    sys.path.insert(0, str(BACKEND))


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
        "username": f"p6fb_{user_id[:8]}",
        "role": "user",
        "type": "access",
        "iat": int(time.time()),
        "exp": int(time.time()) + 3600,
    }
    return pyjwt.encode(payload, secret, algorithm="HS256")


@pytest.fixture
def user_id() -> str:
    return f"p6fb_{uuid.uuid4().hex[:12]}"


@pytest.fixture
def user_id_b() -> str:
    return f"p6fb_{uuid.uuid4().hex[:12]}"


@pytest.fixture
def db():
    try:
        from app.infrastructure.db.database import get_db
        d = get_db()
        d.fetchone("SELECT 1")
        from app.services.practice.practice_question_bank import _ensure_tables
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
def auth_headers_b(user_id_b):
    return {"Authorization": f"Bearer {_make_jwt(user_id_b)}"}


@pytest.fixture(autouse=True)
def cleanup_test_data(db, user_id, user_id_b):
    yield
    try:
        for tbl in (
            "practice_attempts", "session_questions", "practice_sessions",
            "questions", "question_banks",
        ):
            try:
                db.execute(f"DELETE FROM {tbl} WHERE user_id = %s", (user_id,))
                db.execute(f"DELETE FROM {tbl} WHERE user_id = %s", (user_id_b,))
            except Exception:
                pass
        # 清理 cognitive 相关测试数据
        for tbl in ("cognitive_events", "practice_events", "cognitive_node_projections"):
            try:
                db.execute(f"DELETE FROM {tbl} WHERE user_id = %s", (user_id,))
                db.execute(f"DELETE FROM {tbl} WHERE user_id = %s", (user_id_b,))
            except Exception:
                pass
        try:
            db.execute("DELETE FROM knowledge_nodes WHERE user_id = %s", (user_id,))
            db.execute("DELETE FROM knowledge_nodes WHERE user_id = %s", (user_id_b,))
        except Exception:
            pass
    except Exception:
        pass


def _create_bank(client, auth_headers: dict, name: str = "测试题库") -> dict:
    r = client.post(
        "/api/practice/banks", headers=auth_headers, json={"name": name}
    )
    assert r.status_code == 200, f"建题库失败: {r.text}"
    return r.json()


def _add_question(
    client,
    auth_headers: dict,
    bank_id: str,
    *,
    stem: str = "1+1=?",
    answer: list[str] = None,
    node_id: str | None = None,
) -> dict:
    if answer is None:
        answer = ["A"]
    node_id = node_id or f"kn_p6fb_{uuid.uuid4().hex[:8]}"
    payload = {
        "question_type": "single",
        "stem": stem,
        "answer": answer,
        "options": [
            {"letter": "A", "text": "2", "distractor_type": ""},
            {"letter": "B", "text": "3", "distractor_type": "careless"},
        ],
        "analysis": f"解析-{stem[:10]}",
        "difficulty": 3,
        "cognitive_node_ids": [node_id],
        "source": "manual",
    }
    r = client.post(
        f"/api/practice/banks/{bank_id}/questions",
        headers=auth_headers,
        json=payload,
    )
    assert r.status_code == 200, f"加题目失败: {r.text}"
    return r.json()


def _create_session(client, auth_headers: dict, bank_id: str, count: int = 1) -> dict:
    r = client.post(
        "/api/practice/sessions",
        headers=auth_headers,
        json={"bank_id": bank_id, "mode": "adaptive", "count": count},
    )
    assert r.status_code == 200, f"建会话失败: {r.text}"
    return r.json()


class TestFeedbackApi:
    def test_submit_returns_attempt_id_consistent_with_db(self, client, user_id, db, auth_headers):
        """submit_answer 返回 attempt_id，且与 practice_attempts.id 一致。"""
        bank = _create_bank(client, auth_headers)
        q = _add_question(client, auth_headers, bank["id"], answer=["A"])
        s = _create_session(client, auth_headers, bank["id"], count=1)
        qid = s["questions"][0]["id"]

        r = client.post(
            f"/api/practice/sessions/{s['session_id']}/submit",
            headers=auth_headers,
            json={"question_id": qid, "answer": ["A"], "time_spent": 10, "confidence_before": 4},
        )
        assert r.status_code == 200, r.text
        data = r.json()
        assert "attempt_id" in data
        attempt_id = data["attempt_id"]
        assert attempt_id.startswith("att_")

        row = db.fetchone(
            "SELECT id FROM practice_attempts WHERE session_id = %s AND question_id = %s AND user_id = %s",
            (s["session_id"], qid, user_id),
        )
        assert row is not None
        assert row["id"] == attempt_id

    def test_feedback_404_for_missing_attempt(self, client, user_id, auth_headers):
        """不存在的 attempt_id 返回 404。"""
        r = client.get(
            "/api/practice/feedback/att_nonexistent",
            headers=auth_headers,
        )
        assert r.status_code == 404

    def test_feedback_isolation_across_users(self, client, user_id, user_id_b, db, auth_headers, auth_headers_b):
        """用户 B 不能访问用户 A 的 attempt feedback。"""
        bank = _create_bank(client, auth_headers)
        q = _add_question(client, auth_headers, bank["id"], answer=["A"])
        s = _create_session(client, auth_headers, bank["id"], count=1)
        qid = s["questions"][0]["id"]

        r = client.post(
            f"/api/practice/sessions/{s['session_id']}/submit",
            headers=auth_headers,
            json={"question_id": qid, "answer": ["A"], "time_spent": 5},
        )
        attempt_id = r.json()["attempt_id"]

        r_b = client.get(
            f"/api/practice/feedback/{attempt_id}",
            headers=auth_headers_b,
        )
        assert r_b.status_code == 404

    def test_feedback_returns_basic_structure(self, client, user_id, db, auth_headers):
        """GET /feedback/{attempt_id} 返回符合契约的结构。"""
        bank = _create_bank(client, auth_headers)
        q = _add_question(client, auth_headers, bank["id"], answer=["A"])
        s = _create_session(client, auth_headers, bank["id"], count=1)
        qid = s["questions"][0]["id"]

        submit_r = client.post(
            f"/api/practice/sessions/{s['session_id']}/submit",
            headers=auth_headers,
            json={"question_id": qid, "answer": ["A"], "time_spent": 8, "confidence_before": 2},
        )
        attempt_id = submit_r.json()["attempt_id"]

        fb = client.get(
            f"/api/practice/feedback/{attempt_id}",
            headers=auth_headers,
        )
        assert fb.status_code == 200, fb.text
        data = fb.json()
        assert data["attempt_id"] == attempt_id
        assert data["session_id"] == s["session_id"]
        assert data["question_id"] == qid
        assert "is_correct" in data
        assert "feedback" in data
        assert "metacognition" in data
        assert "suggestions" in data

        feedback = data["feedback"]
        assert "information_gain" in feedback
        assert "proficiency_before" in feedback
        assert "proficiency_after" in feedback
        assert "nodes" in feedback

        metacognition = data["metacognition"]
        assert "advice" in metacognition
        assert "bias" in metacognition

    def test_feedback_with_cognitive_reward(self, client, user_id, db, auth_headers):
        """手动写入 cognitive_reward 后，feedback API 应返回 is_final=true 与 belief 变化。"""
        bank = _create_bank(client, auth_headers)
        node_id = f"kn_p6fb_{uuid.uuid4().hex[:8]}"
        # 确保知识节点存在
        db.execute(
            """INSERT INTO knowledge_nodes
               (id, user_id, label, level, parent_id, path_id, is_core, is_visible,
                is_active, node_type, brief, emoji, color, sort_order, tags,
                created_by, created_at, updated_at)
               VALUES (%s, %s, %s, 'atom', NULL, '', FALSE, TRUE, TRUE,
                'auto_generated', '', '', '', 0, '[]'::jsonb, 'test', NOW(), NOW())
               ON CONFLICT (id) DO NOTHING""",
            (node_id, user_id, f"Node {node_id}"),
        )
        q = _add_question(client, auth_headers, bank["id"], answer=["A"], node_id=node_id)
        s = _create_session(client, auth_headers, bank["id"], count=1)
        qid = s["questions"][0]["id"]

        submit_r = client.post(
            f"/api/practice/sessions/{s['session_id']}/submit",
            headers=auth_headers,
            json={"question_id": qid, "answer": ["A"], "time_spent": 8},
        )
        attempt_id = submit_r.json()["attempt_id"]

        # 手动创建 practice_event 与 cognitive_reward（模拟认知中心已处理）
        pe_id = f"pe_p6fb_{uuid.uuid4().hex[:8]}"
        db.execute(
            """INSERT INTO practice_events
               (id, user_id, node_id, session_id, question_id, actor_type,
                source_type, source_id, timestamp, success, latency_ms, weight,
                difficulty, hints_used, time_spent, idempotency_key, created_at)
               VALUES (%s, %s, %s, %s, %s, 'user', 'practice', %s, %s, TRUE,
                       0, 1.0, 3, 0, 8, %s, NOW())
               ON CONFLICT (id) DO NOTHING""",
            (pe_id, user_id, node_id, s["session_id"], qid, s["session_id"],
             time.time(), pe_id),
        )
        cr_id = f"cr_{pe_id}_{node_id}"
        db.execute(
            """INSERT INTO cognitive_events
               (id, user_id, event_type, actor_type, source_type, source_id,
                node_id, payload, status, created_at)
               VALUES (%s, %s, 'cognitive_reward', 'system', 'practice_response',
                       %s, %s, %s::jsonb, 'ready', NOW())
               ON CONFLICT (id) DO NOTHING""",
            (
                cr_id, user_id, pe_id, node_id,
                json.dumps({
                    "node_id": node_id,
                    "reward_value": 0.42,
                    "belief_before": {"alpha": 2.0, "beta": 2.0},
                    "belief_after": {"alpha": 2.5, "beta": 1.8},
                    "uncertainty_before": 0.30,
                    "uncertainty_after": 0.24,
                    "uncertainty_reduction_percent": 20.0,
                }),
            ),
        )

        fb = client.get(
            f"/api/practice/feedback/{attempt_id}",
            headers=auth_headers,
        )
        assert fb.status_code == 200, fb.text
        data = fb.json()
        assert data["is_final"] is True
        assert data["feedback"]["information_gain"] == pytest.approx(0.42, abs=0.01)
        assert data["feedback"]["proficiency_before"] == pytest.approx(0.5, abs=0.01)
        assert data["feedback"]["proficiency_after"] == pytest.approx(0.5814, abs=0.01)
        assert data["feedback"]["uncertainty_reduction_percent"] == pytest.approx(20.0, abs=0.1)
        assert len(data["feedback"]["nodes"]) == 1
        assert data["feedback"]["nodes"][0]["node_id"] == node_id
