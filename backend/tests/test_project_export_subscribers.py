"""
Task #50 — ProjectNodeExported 5 订阅者单元/集成测试

5 个 target_module 各 1 个测试, 验证 handler 真在目标表产生记录。

测试策略:
  - 隔离 EventBus, 直接 publish ProjectNodeExported 事件
  - handler 由 handler 模块直接调用 (避免被 di 容器污染)
  - 验证副作用: 目标表有 1 条新记录
"""
from __future__ import annotations

import asyncio
import json
import os
import sys
import time
import uuid
from typing import Any

import pytest

BACKEND = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BACKEND not in sys.path:
    sys.path.insert(0, BACKEND)


def _try_connect():
    try:
        from app.infrastructure.db.database import get_db
        db = get_db()
        db.fetchone("SELECT 1")
        return db
    except Exception as exc:  # noqa: BLE001
        pytest.skip(f"数据库不可用: {exc}")


def _table_exists(db, table_name: str) -> bool:
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
    row = db.fetchone(
        """
        SELECT 1 FROM information_schema.columns
         WHERE table_name = %s AND column_name = %s
         LIMIT 1
        """,
        (table_name, col_name),
    )
    return row is not None


@pytest.fixture
def user_id():
    return f"xsub_{uuid.uuid4().hex[:12]}"


@pytest.fixture(autouse=True)
def _reset_cognitive_repo():
    """每个测试前后恢复全局 cognitive repo 为真实 Pg 仓储。

    test_cognitive_writer.py 会用 set_repo(MemoryCognitiveNodeRepository) 替换全局
    仓储, 污染后续测试。这里强制 reset 为 Pg 仓储, 保证 handler 真写入数据库。
    """
    from app.application.di import container
    from app.domain.cognitive import set_repo
    real_repo = container.cognitive_node_repo
    # 测试开始前: 立即重置为真实仓储
    set_repo(real_repo)
    yield
    # 测试结束后: 再 reset 一次, 避免污染其他测试
    set_repo(real_repo)


def _create_project_node(user_id: str, title: str = "订阅者测试节点",
                          content: dict | None = None,
                          description: str | None = None):
    """通过 service 创建项目 + 节点, 返回 (project, node)"""
    from app.services import project as project_service

    project_service.ensure_tables()
    proj = project_service.create_project(user_id=user_id, name="订阅者测试项目")
    node = project_service.create_node(
        user_id=user_id,
        project_id=proj["id"],
        type=2,
        title=title,
        content=content or {"text": "测试内容", "summary": "for subscriber"},
        description=description or "订阅者测试描述",
    )
    return proj, node


async def _call_handler(target_module: str, user_id: str,
                         project_id: str, node_id: str,
                         export_data: dict | None = None) -> None:
    """直接调用 handle_project_node_exported (绕开 routes._publish)"""
    from shared.events import ProjectNodeExported, CrossModuleTarget
    from app.application.handlers.project_export_handlers import (
        handle_project_node_exported,
    )

    event = ProjectNodeExported(
        project_id=project_id,
        user_id=user_id,
        node_id=node_id,
        target_module=CrossModuleTarget(target_module),
        target_ref_id="",
        export_data=export_data or {},
    )
    await handle_project_node_exported(event)


# ────────────────────────────────────────────────────────────
# 1. Project → FlashCard 订阅者
# ────────────────────────────────────────────────────────────


class TestFlashcardSubscriber:
    """验证 export target=flashcard 触发 flashcards 表新增一条 source='project' 记录"""

    def test_flashcard_subscriber_creates_card(self, user_id):
        from app.infrastructure.db.database import get_db
        from app.services import project as project_service

        db = _try_connect()
        project_service.ensure_tables()
        proj, node = _create_project_node(user_id)

        # 直接调用 handler (走 async path)
        asyncio.run(_call_handler(
            "flashcard", user_id, proj["id"], node["id"],
            export_data={"front": "什么是 X?", "back": "X 是 Y"},
        ))
        time.sleep(0.1)

        # 验证: flashcards 表有新记录, source='project' 或 cross_module_source 命中
        if not _table_exists(db, "flashcards"):
            pytest.skip("flashcards 表不存在")

        rows = db.fetchall(
            "SELECT id, source, source_ref FROM flashcards WHERE user_id = %s",
            (user_id,),
        )
        assert len(rows) >= 1, f"handler 未创建任何 FlashCard (user={user_id})"

        # 至少一条应含 front_text='什么是 X?'
        matched = db.fetchall(
            "SELECT id, front_text, back_text FROM flashcards "
            "WHERE user_id = %s AND front_text = %s",
            (user_id, "什么是 X?"),
        )
        assert len(matched) >= 1, "handler 未创建含正确 front_text 的卡片"


# ────────────────────────────────────────────────────────────
# 2. Project → Material 订阅者
# ────────────────────────────────────────────────────────────


class TestMaterialSubscriber:
    """验证 export target=material 触发 materials 表新增一条记录"""

    def test_material_subscriber_creates_material(self, user_id):
        from app.infrastructure.db.database import get_db
        from app.services import project as project_service

        db = _try_connect()
        project_service.ensure_tables()
        proj, node = _create_project_node(user_id)

        asyncio.run(_call_handler(
            "material", user_id, proj["id"], node["id"],
        ))
        time.sleep(0.1)

        if not _table_exists(db, "materials"):
            pytest.skip("materials 表不存在")

        rows = db.fetchall(
            "SELECT material_id, file_name, user_id FROM materials WHERE user_id = %s",
            (user_id,),
        )
        assert len(rows) >= 1, f"handler 未创建任何 Material (user={user_id})"


# ────────────────────────────────────────────────────────────
# 3. Project → CognitiveNode 订阅者
# ────────────────────────────────────────────────────────────


class TestCognitiveNodeSubscriber:
    """验证 export target=cognitive_node 触发 cognitive_nodes 表新增一条记录"""

    def test_cognitive_node_subscriber_creates_node(self, user_id):
        from app.infrastructure.db.database import get_db
        from app.services import project as project_service

        db = _try_connect()
        project_service.ensure_tables()
        proj, node = _create_project_node(user_id, title="认知节点测试标题")

        asyncio.run(_call_handler(
            "cognitive_node", user_id, proj["id"], node["id"],
        ))
        time.sleep(0.1)

        # CognitiveNode 表实际名为 knowledge_nodes (Phase 7 schema)
        # 检查表名 (兼容可能的别名 cognitive_nodes)
        target_table = None
        for t in ("knowledge_nodes", "cognitive_nodes"):
            if _table_exists(db, t):
                target_table = t
                break
        if not target_table:
            pytest.skip("knowledge_nodes / cognitive_nodes 表都不存在")

        rows = db.fetchall(
            "SELECT id, label, user_id FROM {tn} WHERE user_id = %s".format(tn=target_table),
            (user_id,),
        )
        # 至少有 1 行 (handler 必定创建了)
        assert len(rows) >= 1, f"handler 未创建任何 CognitiveNode (user={user_id})"

        # 验证 metadata / created_by 标记为 project_export
        if _column_exists(db, target_table, "created_by"):
            proj_created = db.fetchall(
                "SELECT id FROM {tn} "
                "WHERE user_id = %s AND created_by = 'project_export'".format(tn=target_table),
                (user_id,),
            )
            assert len(proj_created) >= 1, (
                "{}.created_by 字段未标记为 project_export".format(target_table)
            )


# ────────────────────────────────────────────────────────────
# 4. Project → Plan 订阅者
# ────────────────────────────────────────────────────────────


class TestPlanSubscriber:
    """验证 export target=plan 触发 plan_items 表新增一条 source_module='project' 记录"""

    def test_plan_subscriber_creates_item(self, user_id):
        from app.infrastructure.db.database import get_db
        from app.services import project as project_service

        db = _try_connect()
        project_service.ensure_tables()
        proj, node = _create_project_node(user_id)

        asyncio.run(_call_handler(
            "plan", user_id, proj["id"], node["id"],
        ))
        time.sleep(0.1)

        if not _table_exists(db, "plan_items"):
            pytest.skip("plan_items 表不存在")

        rows = db.fetchall(
            "SELECT id, source_module, target_ref_id FROM plan_items "
            "WHERE user_id = %s AND source_module = 'project' "
            "AND target_ref_id = %s",
            (user_id, node["id"]),
        )
        assert len(rows) >= 1, (
            f"handler 未创建 source_module='project' 的 PlanItem (user={user_id})"
        )


# ────────────────────────────────────────────────────────────
# 5. Project → LanguageRoom 订阅者
# ────────────────────────────────────────────────────────────


class TestLanguageRoomSubscriber:
    """验证 export target=language_room 触发 language_rooms 表新增一条记录"""

    def test_language_room_subscriber_creates_room(self, user_id):
        from app.infrastructure.db.database import get_db
        from app.services import project as project_service

        db = _try_connect()
        project_service.ensure_tables()
        proj, node = _create_project_node(user_id)

        asyncio.run(_call_handler(
            "language_room", user_id, proj["id"], node["id"],
        ))
        time.sleep(0.1)

        if not _table_exists(db, "language_rooms"):
            pytest.skip("language_rooms 表不存在")

        rows = db.fetchall(
            "SELECT id, owner_id, name FROM language_rooms WHERE owner_id = %s",
            (user_id,),
        )
        assert len(rows) >= 1, f"handler 未创建任何 LanguageRoom (user={user_id})"


# ────────────────────────────────────────────────────────────
# 6. 通用: 派发器测试 — 验证未注册的 target 不会触发任何 handler
# ────────────────────────────────────────────────────────────


class TestDispatcherUnknownTarget:
    """验证: 未知 target_module 时, 派发器安静跳过, 不抛错"""

    def test_unknown_target_does_not_raise(self, user_id):
        from app.services import project as project_service

        _try_connect()
        project_service.ensure_tables()
        proj, node = _create_project_node(user_id)

        # 构造一个 target 为不合法值的 event, 应不抛错
        from shared.events import ProjectNodeExported
        from app.application.handlers.project_export_handlers import (
            handle_project_node_exported,
        )
        # 用一个合法但 handler 不会处理的字符串 — 实际 enum 不允许,
        # 但派发器应处理这种边界情况
        event = ProjectNodeExported(
            project_id=proj["id"],
            user_id=user_id,
            node_id=node["id"],
            target_module="invalid_target",
            export_data={},
        )
        # 不应抛异常
        asyncio.run(handle_project_node_exported(event))


# ────────────────────────────────────────────────────────────
# 7. DI 容器验证: 启动后 bus 真注册了 ProjectNodeExported 订阅
# ────────────────────────────────────────────────────────────


class TestDISubscription:
    """验证 di.py 启动后, ProjectNodeExported 至少 1 个订阅者 (Task #50 修复)"""

    def test_di_has_project_node_exported_subscriber(self):
        from app.application.di import container
        bus = container.event_bus
        handlers = bus._handlers.get("ProjectNodeExported", [])
        assert len(handlers) >= 1, (
            "DI 容器未注册 ProjectNodeExported 订阅者 "
            "(Task #50 修复未生效)"
        )
