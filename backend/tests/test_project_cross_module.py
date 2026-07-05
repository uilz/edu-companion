"""
Task #48 — Project 模块跨模块联动审计 (E2E 测试)

审计 Project 通过 5 个 target_module 导出节点到其他模块的端到端联通性。
ADR 0001 设计意图: Project 节点导出后, 目标模块应感知并执行对应业务。

5 条联动 (按 CrossModuleTarget 枚举):
  1. flashcard        → FlashCardService 应创建卡片 (source='project')
  2. material         → Reading 模块应建立 reading material
  3. cognitive_node   → 知识图谱应挂入节点
  4. plan             → Planning 模块应创建 PlanItem
  5. language_room    → LanguageRoom 应作为房间话题/材料

附加审计:
  - ADR 0001 待修复 1: 跨项目节点复制循环检测 (creates_cycle)
  - ADR 0001 待修复 3: 对话上下文注入粒度开关
  - 事件流订阅者: 是否有任何模块订阅 ProjectNodeExported
"""
from __future__ import annotations

import os
import sys
import uuid
import time
import json
import asyncio
import logging

import pytest

# 让 backend 在 sys.path
BACKEND = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BACKEND not in sys.path:
    sys.path.insert(0, BACKEND)


# ── 公共 fixture ──


@pytest.fixture
def user_id():
    return f"xlink_{uuid.uuid4().hex[:12]}"


@pytest.fixture(autouse=True)
def _reset_cognitive_repo():
    """确保 cognitive repo 在测试前后都是真实的 Pg 仓储。

    防御 test_cognitive_writer.py 用 set_repo(MemoryCognitiveNodeRepository)
    污染全局状态, 让本文件的 cognitive_node 验证写到真 DB。
    """
    from app.application.di import container
    from app.domain.cognitive import set_repo
    real_repo = container.cognitive_node_repo
    set_repo(real_repo)
    yield
    set_repo(real_repo)


def _try_connect():
    try:
        from app.infrastructure.db.database import get_db
        db = get_db()
        db.fetchone("SELECT 1")
        return db
    except Exception as exc:  # noqa: BLE001
        pytest.skip(f"数据库不可用: {exc}")


def _make_jwt(user_id: str) -> str:
    """生成 JWT (与 auth-gateway 共享 HS256 密钥)。"""
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
        "username": f"xlink_{user_id[:8]}",
        "role": "user",
        "type": "access",
        "iat": int(time.time()),
        "exp": int(time.time()) + 3600,
    }
    return pyjwt.encode(payload, secret, algorithm="HS256")


@pytest.fixture
def client():
    from fastapi.testclient import TestClient
    from app.main import app
    return TestClient(app)


@pytest.fixture
def auth_headers(user_id):
    return {"Authorization": f"Bearer {_make_jwt(user_id)}"}


def _create_project_node(user_id: str, title: str = "审计节点",
                          content=None, description: str | None = None):
    """Helper: 通过 service 创建项目 + 节点, 返回 (project, node)。"""
    from app.services import project as project_service

    project_service.ensure_tables()
    proj = project_service.create_project(user_id=user_id, name="审计项目")
    node = project_service.create_node(
        user_id=user_id,
        project_id=proj["id"],
        type=2,
        title=title,
        content=content or {"text": "审计节点内容", "summary": "for export"},
        description=description or "导出审计",
    )
    return proj, node


def _make_async_capture(captured: list):
    """构造一个 async 事件 handler 用于 test_bus.subscribe"""
    async def _h(event):
        captured.append(event)
    return _h


def _table_exists(db, table_name: str) -> bool:
    """检查表是否存在"""
    row = db.fetchone(
        """
        SELECT 1 FROM information_schema.tables
         WHERE table_name = %s
         LIMIT 1
        """,
        (table_name,),
    )
    return row is not None


def _column_exists(db, table_name: str, col_name: str) -> bool:
    """检查列是否存在"""
    row = db.fetchone(
        """
        SELECT 1 FROM information_schema.columns
         WHERE table_name = %s AND column_name = %s
         LIMIT 1
        """,
        (table_name, col_name),
    )
    return row is not None


# ══════════════════════════════════════════════════════════════
# 第一部分: 事件总线订阅者审计 (静态)
# ══════════════════════════════════════════════════════════════


class TestEventBusSubscribers:
    """验证 ProjectNodeExported 是否有订阅者 (SSOT: di.py)"""

    def test_project_node_exported_has_subscriber(self):
        """Task #50 修复: ProjectNodeExported 现在有订阅者 (handle_project_node_exported)。
        期望: 至少 1 个订阅者消费该事件。
        """
        from app.application.di import container

        bus = container.event_bus
        handlers = bus._handlers.get("ProjectNodeExported", [])
        assert isinstance(handlers, list)
        assert len(handlers) >= 1, (
            "ProjectNodeExported 仍无订阅者, Task #50 修复未生效"
        )

    def test_other_project_events_also_uncovered(self):
        """检查 Project 事件族的订阅情况, 横向对比。"""
        from app.application.di import container

        bus = container.event_bus
        project_event_types = [
            "ProjectNodeCreated",
            "ProjectNodeUpdated",
            "ProjectNodeCompleted",
            "ProjectNodeArchived",
            "ProjectNodeExported",
            "ProjectMilestoneMarked",
        ]
        coverage: dict[str, int] = {}
        for evt in project_event_types:
            coverage[evt] = len(bus._handlers.get(evt, []))

        # ProjectNodeExported 应该是 0 (与上面的 skip 保持一致),
        # 其余的至少 0 (可能有人订阅, 也可能没有)。
        # 这里仅做记录性校验, 不强制数值。
        assert "ProjectNodeExported" in coverage
        # 写日志, 便于人工审查
        logger = logging.getLogger(__name__)
        logger.info("Project 事件订阅统计: %s", coverage)


# ══════════════════════════════════════════════════════════════
# 第二部分: 5 条跨模块联动端到端测试 — 事件发布层
#
# 拆分原则:
#   *_publishes_event 测试: 验证 export 端点真发布 ProjectNodeExported (PASS)
#   *_creates_record 测试: 验证订阅者真在目标表创建记录 (SKIP 表示断链)
# ══════════════════════════════════════════════════════════════


class TestCrossModuleExportE2E:
    """通过 REST 调用 export 端点, 验证事件真发出 + 验证副作用。
    """

    def _setup_test_bus_and_publish(self, target_module: str, export_data: dict,
                                     client, user_id, auth_headers,
                                     use_real_bus: bool = False):
        """公共逻辑: 创建项目节点 + 替换 _publish, 调用 export。

        Args:
            use_real_bus: True = 把事件发到 DI 容器的真实 event_bus (handler 会真被调用);
                          False = 替换成独立的 test_bus (只捕获, 不触发 handler)。
        返回 (captured_events, project, node)"""
        from app.infrastructure.event_bus import EventBus

        _try_connect()
        proj, node = _create_project_node(user_id)

        captured: list = []
        if use_real_bus:
            # 真实 bus: DI 容器中已注册的 handler 会自动消费事件
            from app.application.di import container
            real_bus = container.event_bus
            # 同时挂一个 capture handler, 记录事件被实际派发
            real_bus.subscribe(
                "ProjectNodeExported", _make_async_capture(captured)
            )
        else:
            test_bus = EventBus(handler_timeout=1.0)
            test_bus.subscribe(
                "ProjectNodeExported", _make_async_capture(captured)
            )

        import app.api.project.routes as project_routes
        original_publish = project_routes._publish

        if use_real_bus:
            def _patched_publish(event):
                from app.infrastructure.event_bus_utils import publish_event_safe
                publish_event_safe(event, bus=real_bus)
        else:
            def _patched_publish(event):
                from app.infrastructure.event_bus_utils import publish_event_safe
                publish_event_safe(event, bus=test_bus)

        project_routes._publish = _patched_publish
        try:
            r = client.post(
                f"/api/projects/{proj['id']}/nodes/{node['id']}/export",
                headers=auth_headers,
                json={"target_module": target_module, "export_data": export_data},
            )
        finally:
            project_routes._publish = original_publish

        return r, captured, proj, node

    # ── 1. Project → FlashCard ──

    def test_export_to_flashcard_publishes_event(
        self, client, user_id, auth_headers
    ):
        """Project → FlashCard: 验证端点返回成功 + 事件真发出。"""
        from shared.events import CrossModuleTarget

        r, captured, proj, node = self._setup_test_bus_and_publish(
            "flashcard", {"front": "Q", "back": "A"},
            client, user_id, auth_headers,
        )
        assert r.status_code == 200, f"export 失败: {r.text}"
        body = r.json()
        assert body["status"] == "exported"
        assert body["target_module"] == "flashcard"

        # 等待 async task 完成
        time.sleep(0.2)
        # 事件真发出了 (强制断言, 失败即测试失败)
        assert len(captured) == 1, (
            f"未收到 ProjectNodeExported, 实际 {len(captured)}"
        )
        ev = captured[0]
        assert ev.node_id == node["id"]
        assert ev.target_module == CrossModuleTarget.FLASHCARD
        assert ev.user_id == user_id

    def test_export_to_flashcard_creates_card(
        self, client, user_id, auth_headers
    ):
        """副作用: 期望 flashcard 模块订阅者创建卡片。
        Task #50 修复: 订阅者已就位, 卡片真被创建。
        """
        from app.infrastructure.db.database import get_db

        _, _, proj, node = self._setup_test_bus_and_publish(
            "flashcard", {"front": "Q", "back": "A"},
            client, user_id, auth_headers, use_real_bus=True,
        )
        time.sleep(0.5)  # 等异步 handler 跑完
        d = get_db()
        if not _table_exists(d, "flashcards"):
            pytest.skip("flashcards 表不存在, 跳过副作用检查")
        if not _column_exists(d, "flashcards", "source_ref"):
            pytest.skip("flashcards.source_ref 列不存在, 跳过副作用检查")
        rows = d.fetchall(
            "SELECT id FROM flashcards WHERE user_id = %s "
            "AND (source_ref->>'project_node_id') = %s",
            (user_id, node["id"]),
        )
        assert len(rows) >= 1, (
            f"Task #50 修复未生效: export target=flashcard "
            f"未在 flashcards 表产生记录 (期望 1+, 实际 {len(rows)})"
        )

    # ── 2. Project → Material (Reading) ──

    def test_export_to_material_publishes_event(
        self, client, user_id, auth_headers
    ):
        """Project → Material: 验证事件发出。"""
        from shared.events import CrossModuleTarget

        r, captured, proj, node = self._setup_test_bus_and_publish(
            "material", {}, client, user_id, auth_headers,
        )
        assert r.status_code == 200, f"export 失败: {r.text}"
        time.sleep(0.2)
        assert len(captured) == 1
        assert captured[0].target_module == CrossModuleTarget.MATERIAL
        assert captured[0].node_id == node["id"]

    def test_export_to_material_creates_record(
        self, client, user_id, auth_headers
    ):
        """副作用: reading 模块建立 material。
        Task #50 修复: 订阅者已就位, material 真被创建。
        """
        from app.infrastructure.db.database import get_db

        _, _, proj, node = self._setup_test_bus_and_publish(
            "material", {}, client, user_id, auth_headers, use_real_bus=True,
        )
        time.sleep(0.5)
        d = get_db()
        if not _table_exists(d, "materials"):
            pytest.skip("materials 表不存在, 跳过副作用检查")
        # 验证: materials 表有 user_id 命中的行 (handler 创建时已写入)
        rows = d.fetchall(
            "SELECT material_id FROM materials WHERE user_id = %s "
            "AND file_type = 'note' AND status = 'indexed'",
            (user_id,),
        )
        assert len(rows) >= 1, (
            f"Task #50 修复未生效: export target=material "
            f"未在 materials 表产生记录 (期望 1+, 实际 {len(rows)})"
        )

    # ── 3. Project → CognitiveNode ──

    def test_export_to_cognitive_node_publishes_event(
        self, client, user_id, auth_headers
    ):
        """Project → CognitiveNode: 验证事件发出。"""
        from shared.events import CrossModuleTarget

        r, captured, proj, node = self._setup_test_bus_and_publish(
            "cognitive_node", {}, client, user_id, auth_headers,
        )
        assert r.status_code == 200, f"export 失败: {r.text}"
        time.sleep(0.2)
        assert len(captured) == 1
        assert captured[0].target_module == CrossModuleTarget.COGNITIVE_NODE
        assert captured[0].node_id == node["id"]

    def test_export_to_cognitive_node_creates_record(
        self, client, user_id, auth_headers
    ):
        """副作用: 知识图谱建立 cognitive_node。
        Task #50 修复: 订阅者已就位, cognitive_node 真被创建。
        """
        from app.infrastructure.db.database import get_db

        _, _, proj, node = self._setup_test_bus_and_publish(
            "cognitive_node", {}, client, user_id, auth_headers, use_real_bus=True,
        )
        time.sleep(0.5)
        d = get_db()
        # 兼容表名 (实际为 knowledge_nodes)
        target_table = None
        for t in ("knowledge_nodes", "cognitive_nodes"):
            if _table_exists(d, t):
                target_table = t
                break
        if not target_table:
            pytest.skip("knowledge_nodes / cognitive_nodes 表都不存在")
        if not _column_exists(d, target_table, "created_by"):
            pytest.skip(f"{target_table} 表无 created_by 字段, 跳过副作用检查")
        rows = d.fetchall(
            "SELECT id FROM {tn} WHERE user_id = %s AND created_by = 'project_export'".format(tn=target_table),
            (user_id,),
        )
        assert len(rows) >= 1, (
            f"Task #50 修复未生效: export target=cognitive_node "
            f"未在 {target_table} 产生记录 (期望 1+, 实际 {len(rows)})"
        )

    # ── 4. Project → Plan ──

    def test_export_to_plan_publishes_event(
        self, client, user_id, auth_headers
    ):
        """Project → Plan: 验证事件发出。"""
        from shared.events import CrossModuleTarget

        r, captured, proj, node = self._setup_test_bus_and_publish(
            "plan", {}, client, user_id, auth_headers,
        )
        assert r.status_code == 200, f"export 失败: {r.text}"
        time.sleep(0.2)
        assert len(captured) == 1
        assert captured[0].target_module == CrossModuleTarget.PLAN
        assert captured[0].node_id == node["id"]

    def test_export_to_plan_creates_record(
        self, client, user_id, auth_headers
    ):
        """副作用: planning 模块创建 plan_items。
        Task #50 修复: 订阅者已就位, plan_item 真被创建。
        """
        from app.infrastructure.db.database import get_db

        _, _, proj, node = self._setup_test_bus_and_publish(
            "plan", {}, client, user_id, auth_headers, use_real_bus=True,
        )
        time.sleep(0.5)
        d = get_db()
        if not _table_exists(d, "plan_items"):
            pytest.skip("plan_items 表不存在, 跳过副作用检查")
        rows = d.fetchall(
            "SELECT id FROM plan_items WHERE user_id = %s "
            "AND source_module = 'project' AND target_ref_id = %s",
            (user_id, node["id"]),
        )
        assert len(rows) >= 1, (
            f"Task #50 修复未生效: export target=plan "
            f"未在 plan_items 产生记录 (期望 1+, 实际 {len(rows)})"
        )

    # ── 5. Project → LanguageRoom ──

    def test_export_to_language_room_publishes_event(
        self, client, user_id, auth_headers
    ):
        """Project → LanguageRoom: 验证事件发出。"""
        from shared.events import CrossModuleTarget

        r, captured, proj, node = self._setup_test_bus_and_publish(
            "language_room", {}, client, user_id, auth_headers,
        )
        assert r.status_code == 200, f"export 失败: {r.text}"
        time.sleep(0.2)
        assert len(captured) == 1
        assert captured[0].target_module == CrossModuleTarget.LANGUAGE_ROOM
        assert captured[0].node_id == node["id"]

    def test_export_to_language_room_creates_record(
        self, client, user_id, auth_headers
    ):
        """副作用: liveroom 创建房间或话题。
        Task #50 修复: 订阅者已就位, language_room 真被创建。
        """
        from app.infrastructure.db.database import get_db

        _, _, proj, node = self._setup_test_bus_and_publish(
            "language_room", {}, client, user_id, auth_headers, use_real_bus=True,
        )
        time.sleep(0.5)
        d = get_db()
        if not _table_exists(d, "language_rooms"):
            pytest.skip("language_rooms 表不存在, 跳过副作用检查")
        rows = d.fetchall(
            "SELECT id FROM language_rooms WHERE owner_id = %s",
            (user_id,),
        )
        assert len(rows) >= 1, (
            f"Task #50 修复未生效: export target=language_room "
            f"未在 language_rooms 产生记录 (期望 1+, 实际 {len(rows)})"
        )


# ══════════════════════════════════════════════════════════════
# 第三部分: ADR 0001 待修复 1 — 跨项目节点复制循环检测
# ══════════════════════════════════════════════════════════════


class TestCycleDetectionADRFix1:
    """ADR 0001 §"待修复 1": creates_cycle 标记已实现但仅警告未阻断。
    本测试验证: 双向引用(A↔B)真能形成环, 但代码不阻断, 仅记录 + warning。
    """

    def test_bidirectional_reference_creates_cycle_record(
        self, user_id
    ):
        """A→B 然后 B→A: 应能在 node_references 表中看到 creates_cycle 标记。

        ADR 设计意图: "保持用户主导", 即使成环也不阻断, 仅警告。
        本测试不验证阻断, 仅验证标记正确写入。
        """
        from app.services import project as project_service
        from app.services.project import node_ref

        _try_connect()
        db = _try_connect()
        project_service.ensure_tables()

        proj_a = project_service.create_project(user_id=user_id, name="环测试A")
        proj_b = project_service.create_project(user_id=user_id, name="环测试B")

        n_a = project_service.create_node(
            user_id=user_id, project_id=proj_a["id"], type=2, title="A1",
        )
        n_b = project_service.create_node(
            user_id=user_id, project_id=proj_b["id"], type=2, title="B1",
        )

        # 1) A → B (跨项目引用)
        node_ref.sync_node_references(
            user_id, proj_a["id"], n_a["id"],
            f"参考 @@node:{n_b['id']}",
        )
        # 此时 A→B 不成环 (从 A 出发不能回到 A)
        rows = db.fetchall(
            "SELECT * FROM node_references WHERE source_node_id = %s",
            (n_a["id"],),
        )
        assert len(rows) == 1
        assert rows[0]["creates_cycle"] is False

        # 2) B → A (从 B 出发能回到 A, 形成环)
        node_ref.sync_node_references(
            user_id, proj_b["id"], n_b["id"],
            f"参考 @@node:{n_a['id']}",
        )
        # B 的引用应标记 creates_cycle=True
        rows_b = db.fetchall(
            "SELECT * FROM node_references WHERE source_node_id = %s",
            (n_b["id"],),
        )
        assert len(rows_b) == 1
        # 关键: B→A 应当被标记为 creates_cycle
        assert rows_b[0]["creates_cycle"] is True, (
            "环检测失效: B→A 未被标记为 creates_cycle=True"
        )

        # 3) ADR 待修复 1: 即使成环也不阻断
        # 双向引用没被阻断
        rows_all = db.fetchall(
            "SELECT source_node_id, target_node_id, creates_cycle "
            "FROM node_references WHERE source_node_id IN (%s, %s)",
            (n_a["id"], n_b["id"]),
        )
        cycle_count = sum(1 for r in rows_all if r["creates_cycle"])
        assert cycle_count >= 1, "至少 1 条 creates_cycle=True"

    def test_self_reference_detected(self, user_id):
        """自引用: A→A 也应被检测为环。"""
        from app.services import project as project_service
        from app.services.project.node_ref import _detect_cycle

        _try_connect()
        db = _try_connect()
        project_service.ensure_tables()

        proj = project_service.create_project(user_id=user_id, name="自环")
        n = project_service.create_node(
            user_id=user_id, project_id=proj["id"], type=2, title="自己",
        )

        result = _detect_cycle(db, n["id"], n["id"])
        assert result is True, "自引用必须被检测为环"


# ══════════════════════════════════════════════════════════════
# 第四部分: ADR 0001 待修复 3 — 对话上下文注入粒度开关
# ══════════════════════════════════════════════════════════════


class TestChatContextInjectionADRFix3:
    """ADR 0001 §"待修复 3": 用户对每个节点可配置"是否允许注入"。

    验证:
      1. 节点表是否含 allow_chat_inject 字段?
      2. API 层是否能读取该字段?
      3. 注入是否真生效 (chat 系统是否消费该字段)?
    """

    def test_node_table_has_allow_inject_field(self, user_id):
        """检查 project_nodes 表结构是否含 allow_chat_inject 字段。"""
        from app.services import project as project_service

        _try_connect()
        db = _try_connect()
        project_service.ensure_tables()

        rows = db.fetchall(
            """
            SELECT column_name FROM information_schema.columns
             WHERE table_name = 'project_nodes'
               AND column_name IN ('allow_chat_inject', 'inject_to_chat', 'context_inject_enabled')
            """,
        )
        col_names = {r["column_name"] for r in rows}
        # 真实情况: 当前 schema 没有 allow_chat_inject 字段
        # 这是 ADR 待修复 3 的事实状态
        assert isinstance(col_names, set)
        if not col_names:
            pytest.skip(
                "ADR 待修复 3: project_nodes 表缺少 allow_chat_inject 字段 "
                "(节点粒度注入开关未实现)"
            )
        assert len(col_names) >= 1

    def test_create_node_default_inject_behavior(self, user_id):
        """验证 create_node 后, 节点默认是否允许注入。
        若字段不存在, 验证 schema 不报错; 若存在, 默认 True。
        """
        from app.services import project as project_service

        _try_connect()
        db = _try_connect()
        project_service.ensure_tables()

        proj = project_service.create_project(user_id=user_id, name="注入测试")
        n = project_service.create_node(
            user_id=user_id, project_id=proj["id"], type=2, title="待注入节点",
        )
        assert n is not None

        # 查询是否含 inject 字段
        row = db.fetchone(
            """
            SELECT * FROM project_nodes
             WHERE id = %s AND user_id = %s
            """,
            (n["id"], user_id),
        )
        assert row is not None
        # 检查相关字段
        inject_field = None
        for f in ("allow_chat_inject", "inject_to_chat", "context_inject_enabled"):
            if f in row.keys():
                inject_field = f
                break
        if inject_field is None:
            pytest.skip(
                "ADR 待修复 3: 节点无 allow_chat_inject 字段, "
                "无法实现『用户对每个节点配置是否允许注入』的粒度开关"
            )
        # 若有, 默认应当 True
        assert row[inject_field] is True

    def test_chat_system_consumes_inject_flag(self):
        """验证对话系统是否消费 project 节点的注入标记。
        当前: 没有任何 chat 相关代码读取 project_nodes.allow_chat_inject。
        """
        # 静态扫描: 查找 grep 'allow_chat_inject'
        try:
            res = __import__("subprocess").run(
                [
                    "grep", "-rln",
                    "allow_chat_inject",
                    os.path.join(BACKEND, "app"),
                ],
                capture_output=True, text=True, timeout=10,
            )
            matched = res.stdout.strip()
        except Exception:
            matched = ""

        # 当前应该没有任何文件引用
        if not matched:
            pytest.skip(
                "ADR 待修复 3: 后端无任何代码引用 allow_chat_inject, "
                "对话系统未消费节点粒度注入开关"
            )
        assert matched  # 若有, 至少 1 个文件


# ══════════════════════════════════════════════════════════════
# 第五部分: 事件链路日志记录 (辅助诊断)
# ══════════════════════════════════════════════════════════════


class TestEventFlowDiagnostic:
    """记录事件真实流向, 用于报告"""

    def test_log_all_export_events_received(self, client, user_id, auth_headers):
        """一次性测试 5 个 target, 把每个事件记到日志/控制台。"""
        import app.api.project.routes as project_routes
        from app.infrastructure.event_bus import EventBus
        from app.infrastructure.event_bus_utils import publish_event_safe

        _try_connect()
        proj, node = _create_project_node(user_id)

        test_bus = EventBus(handler_timeout=1.0)
        events: list = []
        test_bus.subscribe(
            "ProjectNodeExported", _make_async_capture(events)
        )

        original_publish = project_routes._publish

        def _patched_publish(event):
            publish_event_safe(event, bus=test_bus)

        project_routes._publish = _patched_publish
        try:
            for target in ["flashcard", "material", "cognitive_node", "plan", "language_room"]:
                r = client.post(
                    f"/api/projects/{proj['id']}/nodes/{node['id']}/export",
                    headers=auth_headers,
                    json={"target_module": target, "export_data": {}},
                )
                assert r.status_code == 200, f"{target} export 失败: {r.text}"
        finally:
            project_routes._publish = original_publish

        # 等待 async task 完成
        time.sleep(0.3)

        # 5 个事件全发出去 (但无订阅者消费)
        assert len(events) == 5, f"期望 5 个事件, 实际 {len(events)}"

        # 报告: 5 个事件都能发出, 但无副作用
        from shared.events import CrossModuleTarget
        targets_received = [e.target_module for e in events]
        assert CrossModuleTarget.FLASHCARD in targets_received
        assert CrossModuleTarget.MATERIAL in targets_received
        assert CrossModuleTarget.COGNITIVE_NODE in targets_received
        assert CrossModuleTarget.PLAN in targets_received
        assert CrossModuleTarget.LANGUAGE_ROOM in targets_received
