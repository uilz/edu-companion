"""
Knowledge Tree API 集成测试

覆盖 /api/trees 下的核心端点。
"""
from __future__ import annotations

import os
import time
import uuid

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services.knowledge_tree import kt_svc, tn_svc, cl_svc


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def user_id():
    return f"kt_api_user_{uuid.uuid4().hex[:12]}"


def _make_jwt(user_id: str) -> str:
    import jwt as pyjwt
    secret = os.environ.get("JWT_SECRET")
    if not secret:
        from dotenv import load_dotenv
        env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "config", ".env")
        if os.path.exists(env_path):
            load_dotenv(env_path, override=False)
        secret = os.environ.get("JWT_SECRET", "dev-secret-key-not-for-production-1234567890")
    payload = {
        "sub": user_id,
        "username": f"kt_{user_id[:8]}",
        "role": "user",
        "type": "access",
        "iat": int(time.time()),
        "exp": int(time.time()) + 3600,
    }
    return pyjwt.encode(payload, secret, algorithm="HS256")


def auth_headers(user_id: str):
    return {"Authorization": f"Bearer {_make_jwt(user_id)}"}


def cleanup_user(user_id: str) -> None:
    from app.infrastructure.db.database import get_db
    db = get_db()
    db.execute("DELETE FROM tree_node_cognitive_links WHERE user_id = %s", (user_id,))
    db.execute("DELETE FROM tree_edges WHERE user_id = %s", (user_id,))
    db.execute("DELETE FROM tree_nodes WHERE user_id = %s", (user_id,))
    db.execute("DELETE FROM knowledge_trees WHERE user_id = %s", (user_id,))


class TestTreeApi:
    def test_create_and_get_tree(self, client, user_id):
        resp = client.post("/api/trees", headers=auth_headers(user_id), json={"title": "API测试树", "tree_type": "project"})
        assert resp.status_code == 200
        tree = resp.json()["tree"]
        assert tree["title"] == "API测试树"
        tree_id = tree["id"]

        resp = client.get(f"/api/trees/{tree_id}", headers=auth_headers(user_id))
        assert resp.status_code == 200
        assert resp.json()["tree"]["id"] == tree_id

        cleanup_user(user_id)

    def test_list_trees(self, client, user_id):
        client.post("/api/trees", headers=auth_headers(user_id), json={"title": "树A"})
        client.post("/api/trees", headers=auth_headers(user_id), json={"title": "树B"})
        resp = client.get("/api/trees", headers=auth_headers(user_id))
        assert resp.status_code == 200
        titles = {t["title"] for t in resp.json()["trees"]}
        assert "树A" in titles
        assert "树B" in titles
        cleanup_user(user_id)

    def test_update_tree(self, client, user_id):
        resp = client.post("/api/trees", headers=auth_headers(user_id), json={"title": "旧"})
        tree_id = resp.json()["tree"]["id"]
        resp = client.patch(f"/api/trees/{tree_id}", headers=auth_headers(user_id), json={"title": "新", "default_layout": "force"})
        assert resp.status_code == 200
        assert resp.json()["tree"]["title"] == "新"
        assert resp.json()["tree"]["default_layout"] == "force"
        cleanup_user(user_id)


class TestTreeNodeApi:
    def test_create_and_list_nodes(self, client, user_id):
        resp = client.post("/api/trees", headers=auth_headers(user_id), json={"title": "节点测试树"})
        tree_id = resp.json()["tree"]["id"]

        resp = client.post(f"/api/trees/{tree_id}/nodes", headers=auth_headers(user_id), json={"label": "根"})
        assert resp.status_code == 200
        root_id = resp.json()["node"]["id"]

        resp = client.get(f"/api/trees/{tree_id}/nodes", headers=auth_headers(user_id))
        assert resp.status_code == 200
        assert len(resp.json()["nodes"]) == 1

        cleanup_user(user_id)

    def test_update_and_move_node(self, client, user_id):
        resp = client.post("/api/trees", headers=auth_headers(user_id), json={"title": "移动测试树"})
        tree_id = resp.json()["tree"]["id"]
        root = client.post(f"/api/trees/{tree_id}/nodes", headers=auth_headers(user_id), json={"label": "根"}).json()["node"]
        child = client.post(f"/api/trees/{tree_id}/nodes", headers=auth_headers(user_id), json={"label": "游离"}).json()["node"]

        resp = client.patch(
            f"/api/trees/{tree_id}/nodes/{child['id']}", headers=auth_headers(user_id),
            json={"color": "#ff0000"},
        )
        assert resp.status_code == 200
        assert resp.json()["node"]["color"] == "#ff0000"

        resp = client.post(
            f"/api/trees/{tree_id}/nodes/{child['id']}/move", headers=auth_headers(user_id),
            json={"new_parent_id": root["id"]},
        )
        assert resp.status_code == 200
        assert resp.json()["node"]["parent_id"] == root["id"]

        cleanup_user(user_id)


class TestTreeEdgeApi:
    def test_create_and_delete_edge(self, client, user_id):
        resp = client.post("/api/trees", headers=auth_headers(user_id), json={"title": "边测试树"})
        tree_id = resp.json()["tree"]["id"]
        n1 = client.post(f"/api/trees/{tree_id}/nodes", headers=auth_headers(user_id), json={"label": "n1"}).json()["node"]
        n2 = client.post(f"/api/trees/{tree_id}/nodes", headers=auth_headers(user_id), json={"label": "n2"}).json()["node"]

        resp = client.post(
            f"/api/trees/{tree_id}/edges", headers=auth_headers(user_id),
            json={"source_node_id": n1["id"], "target_node_id": n2["id"], "edge_type": "related", "strength": 0.8},
        )
        assert resp.status_code == 200
        edge_id = resp.json()["edge"]["id"]

        resp = client.get(f"/api/trees/{tree_id}/edges", headers=auth_headers(user_id))
        assert resp.status_code == 200
        assert len(resp.json()["edges"]) == 1

        resp = client.delete(f"/api/trees/{tree_id}/edges/{edge_id}", headers=auth_headers(user_id))
        assert resp.status_code == 200
        assert resp.json()["ok"] is True

        cleanup_user(user_id)


class TestCognitiveLinkApi:
    def test_link_cognitive_node(self, client, user_id):
        resp = client.post("/api/trees", headers=auth_headers(user_id), json={"title": "关联测试树"})
        tree_id = resp.json()["tree"]["id"]
        node = client.post(f"/api/trees/{tree_id}/nodes", headers=auth_headers(user_id), json={"label": "贝叶斯"}).json()["node"]

        resp = client.post(
            f"/api/trees/{tree_id}/nodes/{node['id']}/link-cognitive", headers=auth_headers(user_id),
            json={"cognitive_node_id": "kn_demo_1", "link_role": "primary"},
        )
        assert resp.status_code == 200
        assert resp.json()["link"]["cognitive_node_id"] == "kn_demo_1"

        resp = client.delete(
            f"/api/trees/{tree_id}/nodes/{node['id']}/link-cognitive/kn_demo_1", headers=auth_headers(user_id),
        )
        assert resp.status_code == 200
        assert resp.json()["ok"] is True

        cleanup_user(user_id)


class TestViewportApi:
    def test_save_and_get_viewport(self, client, user_id):
        resp = client.post("/api/trees", headers=auth_headers(user_id), json={"title": "视图测试树"})
        tree_id = resp.json()["tree"]["id"]

        resp = client.put(
            f"/api/trees/{tree_id}/viewport", headers=auth_headers(user_id),
            json={"zoom": 1.5, "pan_x": 100, "view_mode": "graph"},
        )
        assert resp.status_code == 200
        viewport = resp.json()["viewport"]
        assert viewport["zoom"] == 1.5
        assert viewport["pan_x"] == 100
        assert viewport["view_mode"] == "graph"

        resp = client.get(f"/api/trees/{tree_id}/viewport", headers=auth_headers(user_id))
        assert resp.status_code == 200
        assert resp.json()["viewport"]["zoom"] == 1.5

        cleanup_user(user_id)
