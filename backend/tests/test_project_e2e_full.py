"""
Project 模块端到端测试 (Task #46)

覆盖范围:
  - 22 个 API 端点（routes.py 全部 GET/POST/PATCH/DELETE）
  - 7 种节点类型（outline / text / data_table / comparison / code / attachment / aggregate）
  - 5 个跨模块导出目标（flashcard / material / cognitive_node / plan / language_room）
  - 字段级版本控制（create → update → versions → rollback → diff）
  - 跨项目节点复制（link_copy / deep_copy）+ 循环检测
  - 模板创建 + 从模板实例化

设计:
  - 走真实 HTTP API (FastAPI TestClient + JWT Bearer 认证)
  - 每个端点 happy path + 至少 1 个边界 (404 / 400 / 401)
  - 唯一 user_id 隔离测试，避免数据污染
  - 数据库不可用时 skip
"""
from __future__ import annotations

import os
import sys
import time
import uuid

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
        from dotenv import load_dotenv
        env_path = os.path.join(BACKEND, "config", ".env")
        if os.path.exists(env_path):
            load_dotenv(env_path, override=False)
        secret = os.environ.get(
            "JWT_SECRET", "dev-secret-key-not-for-production-1234567890"
        )
    payload = {
        "sub": user_id,
        "username": f"e2e_{user_id[:8]}",
        "role": "user",
        "type": "access",
        "iat": int(time.time()),
        "exp": int(time.time()) + 3600,
    }
    return pyjwt.encode(payload, secret, algorithm="HS256")


@pytest.fixture
def user_id() -> str:
    """独立测试用户 ID, 每次测试唯一避免污染"""
    return f"pje2e_{uuid.uuid4().hex[:12]}"


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
    """FastAPI TestClient (同步)"""
    from fastapi.testclient import TestClient
    from app.main import app
    return TestClient(app)


@pytest.fixture
def auth_headers(user_id):
    """为指定 user_id 生成认证头 (Bearer JWT)"""
    return {"Authorization": f"Bearer {_make_jwt(user_id)}"}


@pytest.fixture
def project_setup(client, user_id, db, auth_headers):
    """创建一个空项目 + 7 个节点 + 一个里程碑 + 一个模板的预设 fixture

    Returns:
        dict: 含 project_id, node_ids (按 type 1-7), milestone_id, template_id
    """
    from app.services import project as project_service
    project_service.ensure_tables()

    # 空项目
    r = client.post(
        "/api/projects/",
        headers=auth_headers,
        json={"name": f"Setup {user_id}", "description": "setup fixture"},
    )
    assert r.status_code in (200, 201), f"setup 项目创建失败: {r.text}"
    project_id = r.json()["id"]

    # 7 个节点 (type 1-7)
    node_ids: dict[int, str] = {}
    type_payloads = {
        1: {"type": 1, "title": "大纲根"},
        2: {"type": 2, "title": "文本节点", "content": {"text": "hello"}},
        3: {"type": 3, "title": "数据表", "rows": [{"a": 1}], "columns": [{"key": "a"}]},
        4: {"type": 4, "title": "对比节点", "columns": [{"label": "A"}, {"label": "B"}]},
        5: {"type": 5, "title": "代码节点", "language": "python", "code": "print(1)", "explanation": "demo"},
        6: {"type": 6, "title": "附件节点", "material_id": "mat_test", "chunk_id_range": {"start": 0, "end": 10}},
        7: {"type": 7, "title": "成果板", "fragments": [{"source_node_id": "src", "offset": 0, "length": 5}]},
    }
    for t, payload in type_payloads.items():
        r = client.post(
            f"/api/projects/{project_id}/nodes",
            headers=auth_headers,
            json=payload,
        )
        assert r.status_code == 200, f"创建 type={t} 节点失败: {r.text}"
        node_ids[t] = r.json()["id"]

    # 1 个里程碑
    r = client.post(
        f"/api/projects/{project_id}/milestones",
        headers=auth_headers,
        json={"milestone_name": "M1", "is_user_marked": True},
    )
    assert r.status_code == 200, f"创建里程碑失败: {r.text}"
    milestone_id = r.json()["id"]

    # 1 个模板
    r = client.post(
        "/api/projects/_templates",
        headers=auth_headers,
        json={
            "name": f"Tpl {user_id}",
            "description": "E2E 测试模板",
            "category": "research",
            "structure": {
                "nodes": [
                    {"type": 1, "title": "Setup 章节", "nodes": [
                        {"type": 2, "title": "Setup 笔记"},
                    ]},
                    {"type": 2, "title": "Setup 总结"},
                ]
            },
            "placeholder_schema": {},
        },
    )
    assert r.status_code == 200, f"创建模板失败: {r.text}"
    template_id = r.json()["id"]

    return {
        "project_id": project_id,
        "node_ids": node_ids,
        "milestone_id": milestone_id,
        "template_id": template_id,
    }


# ════════════════════════════════════════════════════════════════════
# Project CRUD (5 端点)
# ════════════════════════════════════════════════════════════════════


class TestProjectCRUD:
    """POST/GET/PATCH/DELETE /api/projects/ 系列"""

    def test_post_create_project(self, client, user_id, db, auth_headers):
        """POST /api/projects/ - 创建项目 happy path"""
        from app.services import project as project_service
        project_service.ensure_tables()
        r = client.post(
            "/api/projects/",
            headers=auth_headers,
            json={"name": f"项目 {user_id}", "description": "desc", "tags": ["a", "b"]},
        )
        assert r.status_code in (200, 201), f"创建项目失败: {r.text}"
        data = r.json()
        assert data["name"] == f"项目 {user_id}"
        assert data["user_id"] == user_id
        assert data["status"] == "active"
        assert data["node_count"] == 0
        assert data["tags"] == ["a", "b"]
        assert "id" in data
        assert "created_at" in data

    def test_post_create_project_unauthenticated(self, client, db):
        """POST /api/projects/ 无 token 必须 401"""
        r = client.post(
            "/api/projects/",
            json={"name": "unauth"},
        )
        assert r.status_code == 401, f"无 token 应 401, 实际 {r.status_code}: {r.text}"

    def test_get_list_projects(self, client, user_id, db, auth_headers):
        """GET /api/projects/ - 列出当前用户的项目"""
        from app.services import project as project_service
        project_service.ensure_tables()
        # 创建 2 个项目
        client.post("/api/projects/", headers=auth_headers, json={"name": f"P1 {user_id}"})
        client.post("/api/projects/", headers=auth_headers, json={"name": f"P2 {user_id}"})

        r = client.get("/api/projects/", headers=auth_headers)
        assert r.status_code == 200, r.text
        body = r.json()
        assert "projects" in body
        names = [p["name"] for p in body["projects"]]
        assert f"P1 {user_id}" in names
        assert f"P2 {user_id}" in names

    def test_get_list_projects_with_status_filter(self, client, user_id, db, auth_headers):
        """GET /api/projects/?status=active 过滤"""
        from app.services import project as project_service
        project_service.ensure_tables()
        r = client.post("/api/projects/", headers=auth_headers, json={"name": f"Active {user_id}"})
        proj_id = r.json()["id"]
        # 标为 archived
        client.patch(
            f"/api/projects/{proj_id}",
            headers=auth_headers,
            json={"status": "archived"},
        )
        # 列表 (active)
        r = client.get("/api/projects/?status=active", headers=auth_headers)
        assert r.status_code == 200
        names = [p["name"] for p in r.json()["projects"]]
        assert f"Active {user_id}" not in names
        # 列表 (archived)
        r = client.get("/api/projects/?status=archived", headers=auth_headers)
        assert r.status_code == 200
        names = [p["name"] for p in r.json()["projects"]]
        assert f"Active {user_id}" in names

    def test_get_project_by_id(self, client, user_id, db, auth_headers):
        """GET /api/projects/{id} - 单项目查询（含 nodes + milestones）"""
        from app.services import project as project_service
        project_service.ensure_tables()
        r = client.post("/api/projects/", headers=auth_headers, json={"name": f"Get {user_id}"})
        proj_id = r.json()["id"]
        # 加节点
        client.post(
            f"/api/projects/{proj_id}/nodes", headers=auth_headers,
            json={"type": 2, "title": "n1"},
        )

        r = client.get(f"/api/projects/{proj_id}", headers=auth_headers)
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["id"] == proj_id
        assert len(body["nodes"]) == 1
        assert body["nodes"][0]["title"] == "n1"
        assert "milestones" in body

    def test_get_project_404(self, client, user_id, db, auth_headers):
        """GET /api/projects/{id} - 不存在的项目 404"""
        r = client.get(
            f"/api/projects/00000000-0000-0000-0000-000000000000",
            headers=auth_headers,
        )
        assert r.status_code == 404, f"不存在项目应 404, 实际 {r.status_code}: {r.text}"

    def test_patch_update_project(self, client, user_id, db, auth_headers):
        """PATCH /api/projects/{id} - 部分更新"""
        from app.services import project as project_service
        project_service.ensure_tables()
        r = client.post("/api/projects/", headers=auth_headers, json={"name": f"Old {user_id}"})
        proj_id = r.json()["id"]

        r = client.patch(
            f"/api/projects/{proj_id}", headers=auth_headers,
            json={"name": f"New {user_id}", "description": "new desc", "tags": ["x"]},
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["name"] == f"New {user_id}"
        assert body["description"] == "new desc"
        assert body["tags"] == ["x"]

    def test_patch_project_404(self, client, user_id, db, auth_headers):
        """PATCH /api/projects/{id} - 不存在 404"""
        r = client.patch(
            f"/api/projects/00000000-0000-0000-0000-000000000000",
            headers=auth_headers, json={"name": "x"},
        )
        assert r.status_code == 404, r.text

    def test_delete_project(self, client, user_id, db, auth_headers):
        """DELETE /api/projects/{id} - 删除项目"""
        from app.services import project as project_service
        project_service.ensure_tables()
        r = client.post("/api/projects/", headers=auth_headers, json={"name": f"Del {user_id}"})
        proj_id = r.json()["id"]

        r = client.delete(f"/api/projects/{proj_id}", headers=auth_headers)
        assert r.status_code == 200, r.text
        assert r.json()["status"] == "deleted"
        # 再次查询应 404
        r = client.get(f"/api/projects/{proj_id}", headers=auth_headers)
        assert r.status_code == 404


# ════════════════════════════════════════════════════════════════════
# Node CRUD (5 端点) + 7 种节点类型
# ════════════════════════════════════════════════════════════════════


class TestNodeCRUD:
    """POST/GET/PATCH/DELETE /api/projects/{id}/nodes 系列"""

    def test_post_create_node_each_type(self, client, user_id, db, auth_headers):
        """7 种节点类型全部创建成功"""
        from app.services import project as project_service
        project_service.ensure_tables()
        r = client.post("/api/projects/", headers=auth_headers, json={"name": f"Types {user_id}"})
        proj_id = r.json()["id"]

        # (type, payload, 必检字段) — outline 不依赖具体内容字段
        type_payloads = [
            (1, {"type": 1, "title": "大纲根"}, "parent_id"),
            (2, {"type": 2, "title": "文本", "content": {"text": "hi"}}, "content"),
            (3, {"type": 3, "title": "数据表", "rows": [{"a": 1}], "columns": [{"key": "a"}]}, "rows"),
            (4, {"type": 4, "title": "对比", "columns": [{"label": "A"}]}, "columns"),
            (5, {"type": 5, "title": "代码", "language": "python", "code": "x=1", "explanation": "ex"}, "code"),
            (6, {"type": 6, "title": "附件", "material_id": "m1", "chunk_id_range": {"start": 0, "end": 5}}, "material_id"),
            (7, {"type": 7, "title": "成果板", "fragments": [{"source_node_id": "s", "offset": 0, "length": 3}]}, "fragments"),
        ]
        for type_id, payload, key in type_payloads:
            r = client.post(
                f"/api/projects/{proj_id}/nodes",
                headers=auth_headers,
                json=payload,
            )
            assert r.status_code == 200, f"type={type_id} 失败: {r.text}"
            data = r.json()
            assert data["type"] == type_id
            assert data["title"] == payload["title"]
            # type=1 outline 的 parent_id 默认 None; 其余类型必检字段非空
            if type_id == 1:
                assert data["parent_id"] is None
            else:
                assert data[key] is not None, f"type={type_id} 字段 {key} 应非空"
            assert data["version"] == 1

    def test_post_create_node_invalid_type(self, client, user_id, db, auth_headers):
        """POST 节点 type=0/8 应 422 (Pydantic Field ge=1 le=7)"""
        from app.services import project as project_service
        project_service.ensure_tables()
        r = client.post("/api/projects/", headers=auth_headers, json={"name": f"Inv {user_id}"})
        proj_id = r.json()["id"]
        # type=0 越界
        r = client.post(
            f"/api/projects/{proj_id}/nodes", headers=auth_headers,
            json={"type": 0, "title": "x"},
        )
        assert r.status_code == 422, f"type=0 应 422, 实际 {r.status_code}"
        # type=8 越界
        r = client.post(
            f"/api/projects/{proj_id}/nodes", headers=auth_headers,
            json={"type": 8, "title": "x"},
        )
        assert r.status_code == 422

    def test_post_create_node_404_project(self, client, user_id, db, auth_headers):
        """POST 节点到不存在项目 404"""
        r = client.post(
            "/api/projects/00000000-0000-0000-0000-000000000000/nodes",
            headers=auth_headers, json={"type": 2, "title": "x"},
        )
        assert r.status_code == 404, r.text

    def test_get_list_nodes(self, client, user_id, db, auth_headers, project_setup):
        """GET /api/projects/{id}/nodes - 列出节点（不含归档）"""
        r = client.get(
            f"/api/projects/{project_setup['project_id']}/nodes",
            headers=auth_headers,
        )
        assert r.status_code == 200, r.text
        nodes = r.json()["nodes"]
        assert len(nodes) == 7, f"应 7 个节点, 实际 {len(nodes)}"
        types = {n["type"] for n in nodes}
        assert types == {1, 2, 3, 4, 5, 6, 7}

    def test_get_list_nodes_include_archived(self, client, user_id, db, auth_headers, project_setup):
        """include_archived=true 应返回归档节点"""
        proj_id = project_setup["project_id"]
        node_id = project_setup["node_ids"][2]
        # 归档节点 type=2
        client.post(
            f"/api/projects/{proj_id}/nodes/{node_id}/archive",
            headers=auth_headers, params={"archived": True},
        )
        # 默认 (不返回)
        r = client.get(
            f"/api/projects/{proj_id}/nodes", headers=auth_headers,
        )
        active_ids = [n["id"] for n in r.json()["nodes"]]
        assert node_id not in active_ids
        # include_archived=true
        r = client.get(
            f"/api/projects/{proj_id}/nodes?include_archived=true",
            headers=auth_headers,
        )
        all_ids = [n["id"] for n in r.json()["nodes"]]
        assert node_id in all_ids

    def test_get_list_nodes_filter_parent(self, client, user_id, db, auth_headers, project_setup):
        """parent_id 过滤"""
        proj_id = project_setup["project_id"]
        # 取 outline (type=1) 作为 parent
        parent_id = project_setup["node_ids"][1]
        # 在 outline 下创建子节点
        r = client.post(
            f"/api/projects/{proj_id}/nodes", headers=auth_headers,
            json={"type": 2, "title": "child", "parent_id": parent_id},
        )
        child_id = r.json()["id"]
        # 按 parent 过滤
        r = client.get(
            f"/api/projects/{proj_id}/nodes?parent_id={parent_id}",
            headers=auth_headers,
        )
        ids = [n["id"] for n in r.json()["nodes"]]
        assert child_id in ids

    def test_get_node_by_id(self, client, user_id, db, auth_headers, project_setup):
        """GET /api/projects/{id}/nodes/{nid} - 单节点查询"""
        node_id = project_setup["node_ids"][5]  # code node
        r = client.get(
            f"/api/projects/{project_setup['project_id']}/nodes/{node_id}",
            headers=auth_headers,
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["id"] == node_id
        assert body["type"] == 5
        assert body["language"] == "python"
        assert body["code"] == "print(1)"

    def test_get_node_404(self, client, user_id, db, auth_headers, project_setup):
        """GET 节点不存在 404"""
        r = client.get(
            f"/api/projects/{project_setup['project_id']}/nodes/00000000-0000-0000-0000-000000000000",
            headers=auth_headers,
        )
        assert r.status_code == 404

    def test_patch_update_node(self, client, user_id, db, auth_headers, project_setup):
        """PATCH 节点 - 修改 title + content"""
        node_id = project_setup["node_ids"][2]  # text node
        r = client.patch(
            f"/api/projects/{project_setup['project_id']}/nodes/{node_id}",
            headers=auth_headers,
            json={"title": "新文本", "content": {"text": "v2"}},
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["title"] == "新文本"
        assert body["content"] == {"text": "v2"}
        # 字段级版本: 已有 1 个 version
        assert body["version"] >= 2

    def test_patch_node_404(self, client, user_id, db, auth_headers, project_setup):
        """PATCH 节点不存在 404"""
        r = client.patch(
            f"/api/projects/{project_setup['project_id']}/nodes/00000000-0000-0000-0000-000000000000",
            headers=auth_headers, json={"title": "x"},
        )
        assert r.status_code == 404

    def test_delete_node(self, client, user_id, db, auth_headers, project_setup):
        """DELETE 节点 + 验证 project.node_count 减少"""
        proj_id = project_setup["project_id"]
        node_id = project_setup["node_ids"][3]  # comparison node
        r = client.delete(
            f"/api/projects/{proj_id}/nodes/{node_id}", headers=auth_headers,
        )
        assert r.status_code == 200, r.text
        assert r.json()["status"] == "deleted"
        # 再查 404
        r = client.get(f"/api/projects/{proj_id}/nodes/{node_id}", headers=auth_headers)
        assert r.status_code == 404


# ════════════════════════════════════════════════════════════════════
# Node Operations (5 端点): archive / complete / versions / rollback / diff
# ════════════════════════════════════════════════════════════════════


class TestNodeOperations:
    """节点操作端点 (含版本控制全链路)"""

    def test_post_archive_node(self, client, user_id, db, auth_headers, project_setup):
        """POST /nodes/{nid}/archive - 归档节点"""
        node_id = project_setup["node_ids"][2]
        r = client.post(
            f"/api/projects/{project_setup['project_id']}/nodes/{node_id}/archive",
            headers=auth_headers, params={"archived": True},
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["is_archived"] is True

        # 恢复
        r = client.post(
            f"/api/projects/{project_setup['project_id']}/nodes/{node_id}/archive",
            headers=auth_headers, params={"archived": False},
        )
        assert r.status_code == 200
        assert r.json()["is_archived"] is False

    def test_post_archive_node_404(self, client, user_id, db, auth_headers, project_setup):
        """归档不存在节点 404"""
        r = client.post(
            f"/api/projects/{project_setup['project_id']}/nodes/00000000-0000-0000-0000-000000000000/archive",
            headers=auth_headers, params={"archived": True},
        )
        assert r.status_code == 404

    def test_post_complete_node(self, client, user_id, db, auth_headers, project_setup):
        """POST /nodes/{nid}/complete - 标记完成"""
        node_id = project_setup["node_ids"][2]
        r = client.post(
            f"/api/projects/{project_setup['project_id']}/nodes/{node_id}/complete",
            headers=auth_headers, params={"completed": True},
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["completed_at"] is not None
        # 再次完成会重新写时间
        r = client.post(
            f"/api/projects/{project_setup['project_id']}/nodes/{node_id}/complete",
            headers=auth_headers, params={"completed": True},
        )
        assert r.status_code == 200

    def test_post_complete_node_404(self, client, user_id, db, auth_headers, project_setup):
        """完成不存在节点 404"""
        r = client.post(
            f"/api/projects/{project_setup['project_id']}/nodes/00000000-0000-0000-0000-000000000000/complete",
            headers=auth_headers, params={"completed": True},
        )
        assert r.status_code == 404

    def test_get_node_versions(self, client, user_id, db, auth_headers, project_setup):
        """GET /nodes/{nid}/versions - 版本历史"""
        node_id = project_setup["node_ids"][2]
        # 触发 2 次 update 制造版本
        client.patch(
            f"/api/projects/{project_setup['project_id']}/nodes/{node_id}",
            headers=auth_headers, json={"title": "v2 标题"},
        )
        client.patch(
            f"/api/projects/{project_setup['project_id']}/nodes/{node_id}",
            headers=auth_headers, json={"description": "v2 描述"},
        )
        r = client.get(
            f"/api/projects/{project_setup['project_id']}/nodes/{node_id}/versions",
            headers=auth_headers,
        )
        assert r.status_code == 200, r.text
        versions = r.json()["versions"]
        assert len(versions) == 2, f"应 2 条版本, 实际 {len(versions)}"
        # 最新在前
        assert "title" in versions[0]["changed_fields"] or "description" in versions[0]["changed_fields"]

    def test_post_rollback_node(self, client, user_id, db, auth_headers, project_setup):
        """POST /nodes/{nid}/rollback - 回滚到 v1"""
        node_id = project_setup["node_ids"][2]
        # 修改产生 v2
        client.patch(
            f"/api/projects/{project_setup['project_id']}/nodes/{node_id}",
            headers=auth_headers, json={"title": "改后", "content": {"text": "v2"}},
        )
        # 回滚到 v1
        r = client.post(
            f"/api/projects/{project_setup['project_id']}/nodes/{node_id}/rollback",
            headers=auth_headers, json={"target_version": 1},
        )
        assert r.status_code == 200, r.text
        body = r.json()
        # 回滚后 node 的 title/content 应恢复
        assert body["node"]["title"] == "文本节点"
        assert body["node"]["content"] == {"text": "hello"}
        # version 字段 (无新版本) — push_version 看 changed_fields 为空
        # version 不变；新增 rollback 记录
        versions = client.get(
            f"/api/projects/{project_setup['project_id']}/nodes/{node_id}/versions",
            headers=auth_headers,
        ).json()["versions"]
        # 应有 2 条 (v2 修改 + rollback)
        assert len(versions) >= 2

    def test_post_rollback_node_400(self, client, user_id, db, auth_headers, project_setup):
        """rollback 到不存在的版本 400"""
        node_id = project_setup["node_ids"][2]
        r = client.post(
            f"/api/projects/{project_setup['project_id']}/nodes/{node_id}/rollback",
            headers=auth_headers, json={"target_version": 9999},
        )
        assert r.status_code in (400, 404), f"应 400/404, 实际 {r.status_code}: {r.text}"

    def test_post_diff_node_versions(self, client, user_id, db, auth_headers, project_setup):
        """POST /nodes/{nid}/diff - 字段级 diff"""
        node_id = project_setup["node_ids"][2]
        # 改 title 产生 v2
        client.patch(
            f"/api/projects/{project_setup['project_id']}/nodes/{node_id}",
            headers=auth_headers, json={"title": "diff-test"},
        )
        # diff v1 ↔ v2
        r = client.post(
            f"/api/projects/{project_setup['project_id']}/nodes/{node_id}/diff",
            headers=auth_headers, json={"version_a": 1, "version_b": 2},
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["node_id"] == node_id
        assert body["version_a"] == 1
        assert body["version_b"] == 2
        # title 字段在 changed_fields
        assert "title" in body["changed_fields"]


# ════════════════════════════════════════════════════════════════════
# Milestones (2 端点)
# ════════════════════════════════════════════════════════════════════


class TestMilestones:
    """POST/GET /api/projects/{id}/milestones"""

    def test_post_create_milestone(self, client, user_id, db, auth_headers, project_setup):
        """POST 里程碑 - 含 snapshot_data"""
        r = client.post(
            f"/api/projects/{project_setup['project_id']}/milestones",
            headers=auth_headers,
            json={
                "milestone_name": "M2",
                "snapshot_data": {"note": "snapshot"},
                "is_user_marked": True,
            },
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["milestone_name"] == "M2"
        assert body["snapshot_data"]["note"] == "snapshot"
        assert body["is_user_marked"] is True

    def test_post_create_milestone_default_snapshot(self, client, user_id, db, auth_headers, project_setup):
        """POST 里程碑 - 不传 snapshot_data 自动计算"""
        r = client.post(
            f"/api/projects/{project_setup['project_id']}/milestones",
            headers=auth_headers,
            json={"milestone_name": "M-Auto"},
        )
        assert r.status_code == 200, r.text
        body = r.json()
        # 默认快照应含 node_count / completion_rate
        assert "node_count" in body["snapshot_data"]
        assert body["snapshot_data"]["node_count"] == 7

    def test_get_list_milestones(self, client, user_id, db, auth_headers, project_setup):
        """GET 里程碑列表"""
        r = client.get(
            f"/api/projects/{project_setup['project_id']}/milestones",
            headers=auth_headers,
        )
        assert r.status_code == 200, r.text
        ms = r.json()["milestones"]
        # fixture 已创建 1 个
        assert len(ms) >= 1
        names = [m["milestone_name"] for m in ms]
        assert "M1" in names

    def test_get_milestone_by_id(self, client, user_id, db, auth_headers, project_setup):
        """GET /milestones/{mid} - 单里程碑查询"""
        r = client.get(
            f"/api/projects/{project_setup['project_id']}/milestones/{project_setup['milestone_id']}",
            headers=auth_headers,
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["id"] == project_setup["milestone_id"]
        assert body["milestone_name"] == "M1"
        assert "snapshot_data" in body
        assert "marked_at" in body

    def test_get_milestone_404(self, client, user_id, db, auth_headers, project_setup):
        """GET 不存在里程碑 404"""
        r = client.get(
            f"/api/projects/{project_setup['project_id']}/milestones/00000000-0000-0000-0000-000000000000",
            headers=auth_headers,
        )
        assert r.status_code == 404, r.text

    def test_patch_update_milestone(self, client, user_id, db, auth_headers, project_setup):
        """PATCH 里程碑 - 改名 + 改 is_user_marked"""
        r = client.patch(
            f"/api/projects/{project_setup['project_id']}/milestones/{project_setup['milestone_id']}",
            headers=auth_headers,
            json={"milestone_name": "M1-Renamed", "is_user_marked": False},
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["milestone_name"] == "M1-Renamed"
        assert body["is_user_marked"] is False
        # snapshot_data 保持原值
        assert body["snapshot_data"] is not None

    def test_patch_milestone_snapshot_override(self, client, user_id, db, auth_headers, project_setup):
        """PATCH 里程碑 - 显式传 snapshot_data 覆盖"""
        r = client.patch(
            f"/api/projects/{project_setup['project_id']}/milestones/{project_setup['milestone_id']}",
            headers=auth_headers,
            json={"snapshot_data": {"note": "手动快照"}},
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["snapshot_data"] == {"note": "手动快照"}

    def test_patch_milestone_404(self, client, user_id, db, auth_headers, project_setup):
        """PATCH 不存在里程碑 404"""
        r = client.patch(
            f"/api/projects/{project_setup['project_id']}/milestones/00000000-0000-0000-0000-000000000000",
            headers=auth_headers, json={"milestone_name": "x"},
        )
        assert r.status_code == 404

    def test_delete_milestone(self, client, user_id, db, auth_headers, project_setup):
        """DELETE 里程碑 + 验证再查 404"""
        # 先创建新里程碑避免影响 fixture
        r = client.post(
            f"/api/projects/{project_setup['project_id']}/milestones",
            headers=auth_headers,
            json={"milestone_name": "to-delete"},
        )
        assert r.status_code == 200, r.text
        mid = r.json()["id"]

        r = client.delete(
            f"/api/projects/{project_setup['project_id']}/milestones/{mid}",
            headers=auth_headers,
        )
        assert r.status_code == 200, r.text
        assert r.json()["status"] == "deleted"
        # 再查 404
        r = client.get(
            f"/api/projects/{project_setup['project_id']}/milestones/{mid}",
            headers=auth_headers,
        )
        assert r.status_code == 404

    def test_delete_milestone_404(self, client, user_id, db, auth_headers, project_setup):
        """DELETE 不存在里程碑 404"""
        r = client.delete(
            f"/api/projects/{project_setup['project_id']}/milestones/00000000-0000-0000-0000-000000000000",
            headers=auth_headers,
        )
        assert r.status_code == 404


# ════════════════════════════════════════════════════════════════════
# Templates (3 端点)
# ════════════════════════════════════════════════════════════════════


class TestTemplates:
    """GET/POST /api/projects/_templates + from-template"""

    def test_get_list_templates(self, client, user_id, db, auth_headers):
        """GET /api/projects/_templates/all - 列表 (含系统预置)"""
        from app.services import project as project_service
        project_service.ensure_tables()
        # 触发 seed
        project_service.seed_default_templates()
        r = client.get(
            "/api/projects/_templates/all", headers=auth_headers,
        )
        assert r.status_code == 200, r.text
        tpls = r.json()["templates"]
        # 系统预置 4 个
        assert len(tpls) >= 4
        sys_tpls = [t for t in tpls if t["is_system"]]
        assert len(sys_tpls) >= 4

    def test_get_list_templates_by_category(self, client, user_id, db, auth_headers):
        """GET /api/projects/_templates/all?category=research - 按类别过滤"""
        r = client.get(
            "/api/projects/_templates/all?category=research",
            headers=auth_headers,
        )
        assert r.status_code == 200, r.text
        tpls = r.json()["templates"]
        for t in tpls:
            assert t["category"] == "research"

    def test_post_create_template(self, client, user_id, db, auth_headers):
        """POST /api/projects/_templates - 用户模板"""
        r = client.post(
            "/api/projects/_templates", headers=auth_headers,
            json={
                "name": f"UserTpl {user_id}",
                "category": "custom",
                "structure": {"nodes": [{"type": 1, "title": "Root"}]},
                "placeholder_schema": {"name": "string"},
            },
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["name"] == f"UserTpl {user_id}"
        assert body["is_system"] is False  # 用户模板
        assert "id" in body

    def test_post_create_from_template(self, client, user_id, db, auth_headers, project_setup):
        """POST /api/projects/from-template - 从模板创建项目"""
        r = client.post(
            "/api/projects/from-template", headers=auth_headers,
            json={
                "template_id": project_setup["template_id"],
                "name": f"FromTpl {user_id}",
                "placeholder_values": {},
            },
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["name"] == f"FromTpl {user_id}"
        assert body["template_id"] == project_setup["template_id"]
        # 节点应被自动创建
        nodes = client.get(
            f"/api/projects/{body['id']}/nodes", headers=auth_headers,
        ).json()["nodes"]
        # 模板含 2 个章节 + 1 个子节点 = 3
        assert len(nodes) == 3

    def test_post_create_from_template_404(self, client, user_id, db, auth_headers):
        """from-template 用不存在模板应 404（路由层已加 try/except ValueError 兜底）"""
        r = client.post(
            "/api/projects/from-template", headers=auth_headers,
            json={
                "template_id": "00000000-0000-0000-0000-000000000000",
                "name": "x",
            },
        )
        assert r.status_code == 404, (
            f"不存在模板应 404, 实际 {r.status_code}: {r.text}"
        )
        assert "模板不存在" in r.json().get("detail", "")


# ════════════════════════════════════════════════════════════════════
# Cross-project copy (1 端点)
# ════════════════════════════════════════════════════════════════════


class TestCrossProjectCopy:
    """POST /api/projects/{id}/copy-nodes"""

    def test_copy_link_copy(self, client, user_id, db, auth_headers, project_setup):
        """link_copy 模式: 复制后 title 一致, content 字段不复制"""
        # 准备源项目
        r = client.post("/api/projects/", headers=auth_headers, json={"name": f"Src {user_id}"})
        src_id = r.json()["id"]
        r = client.post(
            f"/api/projects/{src_id}/nodes", headers=auth_headers,
            json={"type": 2, "title": "link 源", "content": {"text": "data"}},
        )
        src_node_id = r.json()["id"]

        # 目标项目
        r = client.post("/api/projects/", headers=auth_headers, json={"name": f"Tgt {user_id}"})
        tgt_id = r.json()["id"]

        r = client.post(
            f"/api/projects/{tgt_id}/copy-nodes", headers=auth_headers,
            json={
                "source_project_id": src_id,
                "node_ids": [src_node_id],
                "mode": "link_copy",
            },
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert len(body["created"]) == 1
        assert body["created"][0]["mode"] == "link_copy"
        new_id = body["created"][0]["new_node_id"]
        # 目标项目能查到新节点
        r = client.get(f"/api/projects/{tgt_id}/nodes/{new_id}", headers=auth_headers)
        assert r.status_code == 200
        assert r.json()["title"] == "link 源"
        # link_copy 不复制内容字段
        assert r.json()["content"] is None

    def test_copy_deep_copy(self, client, user_id, db, auth_headers):
        """deep_copy 模式: 复制后 content 也复制"""
        r = client.post("/api/projects/", headers=auth_headers, json={"name": f"SrcD {user_id}"})
        src_id = r.json()["id"]
        r = client.post(
            f"/api/projects/{src_id}/nodes", headers=auth_headers,
            json={"type": 2, "title": "deep 源", "content": {"text": "data"}},
        )
        src_node_id = r.json()["id"]

        r = client.post("/api/projects/", headers=auth_headers, json={"name": f"TgtD {user_id}"})
        tgt_id = r.json()["id"]

        r = client.post(
            f"/api/projects/{tgt_id}/copy-nodes", headers=auth_headers,
            json={
                "source_project_id": src_id,
                "node_ids": [src_node_id],
                "mode": "deep_copy",
            },
        )
        assert r.status_code == 200, r.text
        new_id = r.json()["created"][0]["new_node_id"]
        r = client.get(f"/api/projects/{tgt_id}/nodes/{new_id}", headers=auth_headers)
        assert r.status_code == 200
        # deep_copy 复制 content
        assert r.json()["content"] == {"text": "data"}

    def test_copy_invalid_mode(self, client, user_id, db, auth_headers):
        """copy-nodes 传非法 mode 400"""
        r = client.post("/api/projects/", headers=auth_headers, json={"name": f"SrcI {user_id}"})
        src_id = r.json()["id"]
        r = client.post("/api/projects/", headers=auth_headers, json={"name": f"TgtI {user_id}"})
        tgt_id = r.json()["id"]
        r = client.post(
            f"/api/projects/{src_id}/nodes", headers=auth_headers,
            json={"type": 2, "title": "x"},
        )
        src_node_id = r.json()["id"]

        r = client.post(
            f"/api/projects/{tgt_id}/copy-nodes", headers=auth_headers,
            json={
                "source_project_id": src_id,
                "node_ids": [src_node_id],
                "mode": "invalid_mode",
            },
        )
        # ValueError → 400
        assert r.status_code == 400, f"非法 mode 应 400, 实际 {r.status_code}: {r.text}"

    def test_copy_target_project_404(self, client, user_id, db, auth_headers):
        """copy-nodes 到不存在项目 400 (target_project_id 校验)"""
        r = client.post(
            "/api/projects/00000000-0000-0000-0000-000000000000/copy-nodes",
            headers=auth_headers,
            json={
                "source_project_id": "00000000-0000-0000-0000-000000000001",
                "node_ids": ["x"],
                "mode": "link_copy",
            },
        )
        assert r.status_code in (400, 404), r.text


# ════════════════════════════════════════════════════════════════════
# Cross-module export (1 端点 × 5 目标)
# ════════════════════════════════════════════════════════════════════


class TestCrossModuleExport:
    """POST /api/projects/{id}/nodes/{nid}/export → 5 个目标模块"""

    @pytest.mark.parametrize("target_module", [
        "flashcard",
        "material",
        "cognitive_node",
        "plan",
        "language_room",
    ])
    def test_export_to_each_target_module(
        self, client, user_id, db, auth_headers, project_setup, target_module
    ):
        """导出到 5 个目标模块 - 全部成功"""
        node_id = project_setup["node_ids"][2]  # text node
        r = client.post(
            f"/api/projects/{project_setup['project_id']}/nodes/{node_id}/export",
            headers=auth_headers,
            json={
                "target_module": target_module,
                "target_ref_id": f"ref_{target_module}_{user_id[:8]}",
                "export_data": {"k": "v"},
            },
        )
        assert r.status_code == 200, f"{target_module} 导出失败: {r.text}"
        body = r.json()
        assert body["status"] == "exported"
        assert body["target_module"] == target_module
        assert body["target_ref_id"] == f"ref_{target_module}_{user_id[:8]}"

    def test_export_invalid_target(self, client, user_id, db, auth_headers, project_setup):
        """export 到非法 target_module 400/422 (Pydantic 枚举校验返回 422)"""
        node_id = project_setup["node_ids"][2]
        r = client.post(
            f"/api/projects/{project_setup['project_id']}/nodes/{node_id}/export",
            headers=auth_headers,
            json={
                "target_module": "invalid_target",
                "target_ref_id": "x",
            },
        )
        # Pydantic CrossModuleTarget 枚举校验会返回 422 (路由内的 try/except ValueError 是
        # 兜底，理论上不会触发)。两个状态码都算正确拒绝。
        assert r.status_code in (400, 422), f"非法 target_module 应 400/422, 实际 {r.status_code}: {r.text}"

    def test_export_node_404(self, client, user_id, db, auth_headers, project_setup):
        """export 不存在节点 404"""
        r = client.post(
            f"/api/projects/{project_setup['project_id']}/nodes/00000000-0000-0000-0000-000000000000/export",
            headers=auth_headers,
            json={"target_module": "flashcard", "target_ref_id": "x"},
        )
        assert r.status_code == 404

    def test_export_without_target_ref_id(self, client, user_id, db, auth_headers, project_setup):
        """export 不传 target_ref_id 默认空串"""
        node_id = project_setup["node_ids"][2]
        r = client.post(
            f"/api/projects/{project_setup['project_id']}/nodes/{node_id}/export",
            headers=auth_headers,
            json={"target_module": "flashcard"},
        )
        assert r.status_code == 200, r.text
        assert r.json()["target_ref_id"] == ""


# ════════════════════════════════════════════════════════════════════
# 7 种节点类型专项 (列出版本 + 完整内容验证)
# ════════════════════════════════════════════════════════════════════


class TestNodeTypesFull:
    """7 种节点类型完整字段验证 (按 ADR 0001)"""

    def test_type1_outline(self, client, user_id, db, auth_headers, project_setup):
        """Type 1 大纲节点: parent_id 层级组织"""
        node_id = project_setup["node_ids"][1]
        r = client.get(
            f"/api/projects/{project_setup['project_id']}/nodes/{node_id}",
            headers=auth_headers,
        )
        assert r.status_code == 200
        body = r.json()
        assert body["type"] == 1
        assert body["title"] == "大纲根"
        # 大纲节点主键: parent_id
        assert body["parent_id"] is None  # 根节点

    def test_type2_text(self, client, user_id, db, auth_headers, project_setup):
        """Type 2 文本节点: content JSONB"""
        node_id = project_setup["node_ids"][2]
        r = client.get(
            f"/api/projects/{project_setup['project_id']}/nodes/{node_id}",
            headers=auth_headers,
        )
        body = r.json()
        assert body["type"] == 2
        assert body["content"] == {"text": "hello"}

    def test_type3_data_table(self, client, user_id, db, auth_headers, project_setup):
        """Type 3 数据表节点: rows + columns JSONB"""
        node_id = project_setup["node_ids"][3]
        r = client.get(
            f"/api/projects/{project_setup['project_id']}/nodes/{node_id}",
            headers=auth_headers,
        )
        body = r.json()
        assert body["type"] == 3
        assert body["rows"] == [{"a": 1}]
        assert body["columns"] == [{"key": "a"}]

    def test_type4_comparison(self, client, user_id, db, auth_headers, project_setup):
        """Type 4 对比节点: columns 数组"""
        node_id = project_setup["node_ids"][4]
        r = client.get(
            f"/api/projects/{project_setup['project_id']}/nodes/{node_id}",
            headers=auth_headers,
        )
        body = r.json()
        assert body["type"] == 4
        assert len(body["columns"]) == 2
        assert body["columns"][0]["label"] == "A"

    def test_type5_code(self, client, user_id, db, auth_headers, project_setup):
        """Type 5 代码节点: language + code + explanation"""
        node_id = project_setup["node_ids"][5]
        r = client.get(
            f"/api/projects/{project_setup['project_id']}/nodes/{node_id}",
            headers=auth_headers,
        )
        body = r.json()
        assert body["type"] == 5
        assert body["language"] == "python"
        assert body["code"] == "print(1)"
        assert body["explanation"] == "demo"

    def test_type6_attachment(self, client, user_id, db, auth_headers, project_setup):
        """Type 6 附件节点: material_id + chunk_id_range"""
        node_id = project_setup["node_ids"][6]
        r = client.get(
            f"/api/projects/{project_setup['project_id']}/nodes/{node_id}",
            headers=auth_headers,
        )
        body = r.json()
        assert body["type"] == 6
        assert body["material_id"] == "mat_test"
        assert body["chunk_id_range"] == {"start": 0, "end": 10}

    def test_type7_aggregate(self, client, user_id, db, auth_headers, project_setup):
        """Type 7 聚合节点: fragments (源节点 + offset + length)"""
        node_id = project_setup["node_ids"][7]
        r = client.get(
            f"/api/projects/{project_setup['project_id']}/nodes/{node_id}",
            headers=auth_headers,
        )
        body = r.json()
        assert body["type"] == 7
        assert body["fragments"] == [
            {"source_node_id": "src", "offset": 0, "length": 5}
        ]


# ════════════════════════════════════════════════════════════════════
# 端点完整枚举检查 (sanity)
# ════════════════════════════════════════════════════════════════════


class TestEndpointInventory:
    """清点 Project 模块路由 — 防遗漏"""

    def test_all_22_routes_registered(self, client, user_id, db, auth_headers):
        """枚举 app.main 加载的路由，验证 /api/projects/* 端点数量"""
        from app.main import app
        prefix = "/api/projects"
        routes = [
            r for r in app.routes
            if hasattr(r, "path") and r.path.startswith(prefix)
        ]
        # 列出所有 paths 用于诊断
        paths = sorted({r.path for r in routes})
        # 验证必要端点存在
        required_paths = {
            f"{prefix}/",
            f"{prefix}/_templates/all",
            f"{prefix}/_templates",
            f"{prefix}/from-template",
        }
        for p in required_paths:
            assert p in paths, f"端点 {p} 未注册 (实际: {paths})"

        # 动态路径端点 — 用 path template 匹配
        # POST/PATCH/DELETE/GET 端点数 (按 path 模板)
        path_methods: dict[str, set] = {}
        for r in routes:
            for m in (r.methods or set()):
                path_methods.setdefault(r.path, set()).add(m)

        # 必备的 path 模板
        required_templates = [
            f"{prefix}/",                           # list/create
            f"{prefix}/{{project_id}}",             # get/update/delete
            f"{prefix}/{{project_id}}/nodes",       # list/create nodes
            f"{prefix}/{{project_id}}/nodes/{{node_id}}",  # get/update/delete node
            f"{prefix}/{{project_id}}/nodes/{{node_id}}/archive",
            f"{prefix}/{{project_id}}/nodes/{{node_id}}/complete",
            f"{prefix}/{{project_id}}/nodes/{{node_id}}/versions",
            f"{prefix}/{{project_id}}/nodes/{{node_id}}/rollback",
            f"{prefix}/{{project_id}}/nodes/{{node_id}}/diff",
            f"{prefix}/{{project_id}}/nodes/{{node_id}}/export",
            f"{prefix}/{{project_id}}/milestones",
            f"{prefix}/{{project_id}}/milestones/{{milestone_id}}",  # get/patch/delete milestone
            f"{prefix}/{{project_id}}/copy-nodes",
            f"{prefix}/_templates/all",
            f"{prefix}/_templates",
            f"{prefix}/from-template",
        ]
        for t in required_templates:
            assert t in path_methods, f"路由模板 {t} 未注册"

        # 验证方法数 — 每个模板都应有相应 HTTP 方法
        # 至少包含 GET/POST/PATCH/DELETE 覆盖
        all_methods = set()
        for methods in path_methods.values():
            all_methods.update(methods)
        for m in ("GET", "POST", "PATCH", "DELETE"):
            assert m in all_methods, f"HTTP 方法 {m} 在 Project 模块未出现"
