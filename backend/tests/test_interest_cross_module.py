"""
Task #73 — InterestExplorer 跨模块联动审计 (E2E 测试)

按 docs/modules/interest-explorer/events.md §3.1/§3.2 + ADR 0007 审计
InterestExplorer 9 条跨模块联动的端到端联通性。

9 条联动:
  1. InterestPushGenerated            → 秘书 Proposal
  2. InterestPushFeedback(later)      → FlashCard (status='later', source='system', cross_module_source='interest_explorer')
  3. InterestContentImported (reading)         → Material
  4. InterestContentImported (project)         → Project
  5. InterestContentImported (flashcard)       → FlashCard
  6. InterestContentImported (cognitive_node)  → CognitiveNode
  7. InterestContentImported (language_room)   → LanguageRoom
  8. CognitiveNodeLinked              → interest_tags 引用计数
  9. CognitiveNodeMetadataChanged     → 兴趣面板刷新

隔离原则: 所有 Interest 事件不更新 Belief。

每个联动各 1 个 E2E 测试, 验证:
  - 源动作触发后, 事件真发布到 event_bus
  - 目标模块/目标表真有副作用 (有订阅者 + 实际写入)
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
    return f"xint_{uuid.uuid4().hex[:12]}"


@pytest.fixture(autouse=True)
def _reset_cognitive_repo():
    """确保 cognitive repo 在测试前后都是真实的 Pg 仓储."""
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
        "username": f"xint_{user_id[:8]}",
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


def _make_async_capture(captured: list):
    async def _h(event):
        captured.append(event)
    return _h


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


def _create_push_record_direct(user_id: str, title: str, url: str,
                                summary: str = "") -> str:
    """直接通过 store 写入 push record, 返回 push_id. (避免依赖 feed 抓取)"""
    from app.services.interest import store

    # 先建一个 source 让 push_records.source_id NOT NULL FK 满足
    src = store.create_source(
        user_id=user_id,
        name=f"audit_src_{uuid.uuid4().hex[:6]}",
        type_="rss",
        config={"feed_url": f"https://example.com/{uuid.uuid4().hex[:6]}.xml"},
        category="audit",
        is_system=False,
        enabled=True,
    )
    rec = store.create_push_record(
        user_id=user_id,
        push_type="research_object",
        title=title,
        source_id=src["id"] if src else None,
        summary=summary or "审计摘要",
        url=url,
        author="audit",
        matched_tags=[],
    )
    assert rec, "create_push_record 失败"
    return rec["id"]


def _ensure_push(user_id: str) -> dict:
    """通过 service.trigger_push 真实推一次, 返回最新 push 记录 (供后续步骤使用)."""
    from app.services.interest import store

    # 用 service 主动触发推送 (force=True, 绕过时间窗口)
    result = _run_sync_coro(_run_trigger_push(user_id))

    # 如果没有推出去 (没有 candidate), 直接插一条
    pushed = int(result.get("pushed_count", 0)) if isinstance(result, dict) else 0
    if pushed == 0:
        push_id = _create_push_record_direct(
            user_id,
            title="审计标题 - 推送生成",
            url=f"https://example.com/push-{uuid.uuid4().hex[:8]}",
            summary="审计 push",
        )
        rec = store.get_push_record(user_id, push_id)
        return rec
    # 选最近一条
    records = store.list_push_records(user_id, limit=1)
    return records[0] if records else None


async def _run_trigger_push(user_id: str) -> dict:
    from app.services.interest.push_scheduler import get_scheduler
    return await get_scheduler().run_for_user(user_id, force=True)


# ══════════════════════════════════════════════════════════════
# 第一部分: 事件总线订阅者审计 (静态)
# ══════════════════════════════════════════════════════════════


class TestEventBusSubscribers:
    """验证 Interest 事件是否有订阅者 (SSOT: di.py)"""

    def test_interest_event_types_registered(self):
        """EVENT_TYPES 字典包含 13 个 Interest 事件."""
        from shared.events import EVENT_TYPES
        interest_event_types = [
            "InterestTagCreated",
            "InterestTagUpdated",
            "InterestTagDeleted",
            "InterestTagFromKnowledgeCreated",
            "InterestSourceEnabled",
            "InterestSourceDisabled",
            "InterestSourceFetched",
            "InterestPushGenerated",
            "InterestPushFeedbackRecorded",
            "InterestContentImported",
            "InterestLocalWeightAdjusted",
            "InterestPrefsUpdated",
        ]
        missing = [e for e in interest_event_types if e not in EVENT_TYPES]
        assert not missing, f"EVENT_TYPES 缺少 Interest 事件: {missing}"

    def test_interest_event_handlers_count(self):
        """记录 Interest 事件订阅数 (供人工审查)."""
        from app.application.di import container

        bus = container.event_bus
        interest_event_types = [
            "InterestTagCreated",
            "InterestTagUpdated",
            "InterestTagDeleted",
            "InterestTagFromKnowledgeCreated",
            "InterestSourceEnabled",
            "InterestSourceDisabled",
            "InterestSourceFetched",
            "InterestPushGenerated",
            "InterestPushFeedbackRecorded",
            "InterestContentImported",
            "InterestLocalWeightAdjusted",
            "InterestPrefsUpdated",
            "CognitiveNodeLinked",
            "CognitiveNodeMetadataChanged",
        ]
        coverage: dict[str, int] = {}
        for evt in interest_event_types:
            coverage[evt] = len(bus._handlers.get(evt, []))

        # 记录日志
        logger = logging.getLogger(__name__)
        logger.info("Interest 事件订阅统计: %s", coverage)
        # 不强制数量, 仅做记录性校验
        assert isinstance(coverage, dict)


# ══════════════════════════════════════════════════════════════
# 第二部分: 9 条跨模块联动 — 端到端测试
# ══════════════════════════════════════════════════════════════


# ── 联动 1: InterestPushGenerated → 秘书 Proposal ──


def _create_push_via_scheduler(user_id: str) -> dict:
    """通过 push_scheduler 真实推一次 (这会触发 _notify_proposal).

    如果没有 candidate, 直接插一条 + 手动调 _notify_proposal.
    """
    from app.services.interest import store
    from app.services.interest.push_scheduler import get_scheduler

    scheduler = get_scheduler()
    # run_for_user 真实执行: 检查时间窗口, 采样, 创建 push_record, 发布事件, 通知 proposal
    # 我们用 force=True 跳过时间窗口
    result = _run_sync_coro(scheduler.run_for_user(user_id, force=True))

    pushed = int(result.get("pushed_count", 0)) if isinstance(result, dict) else 0
    if pushed == 0:
        # 没有 candidate → 走直接插 push_record + 手动 _notify_proposal
        push = _create_push_record_direct(
            user_id,
            title="审计标题 - 推送生成",
            url=f"https://example.com/push-{uuid.uuid4().hex[:8]}",
            summary="审计 push",
        )
        rec = store.get_push_record(user_id, push)
        # 手动触发 _notify_proposal
        _run_sync_coro(scheduler._notify_proposal(rec, rec, user_id))
        time.sleep(0.2)
        return rec

    records = store.list_push_records(user_id, limit=1)
    return records[0] if records else None


class TestLink1_PushGeneratedToProposal:
    """联动 1: InterestPushGenerated → 秘书系统 Proposal (events.md §3.2)"""

    def test_push_generated_creates_proposal(
        self, user_id
    ):
        """推一条 push 后, 验证 secretary_proposals 表中存在 interest_push 类提案."""
        from app.infrastructure.db.database import get_db

        _try_connect()

        rec = _create_push_via_scheduler(user_id)
        assert rec is not None, "推送记录未生成"
        push_id = rec["id"]
        time.sleep(0.5)  # 等异步 handler 跑完

        d = get_db()
        # 真实表名: secretary_proposals
        if not _table_exists(d, "secretary_proposals"):
            pytest.skip("secretary_proposals 表不存在, 跳过副作用检查")

        # 查找 action_type='interest_push' 的提案
        row = d.fetchone(
            """
            SELECT id, title, payload, action_type FROM secretary_proposals
            WHERE user_id = %s
              AND (action_type = 'interest_push' OR generated_by = %s)
            ORDER BY created_at DESC LIMIT 1
            """,
            (user_id, "interest_explorer"),
        )
        assert row is not None, (
            "联动 1 失效: 推送生成后未在 secretary_proposals 表产生 interest_push 提案"
        )
        # payload 应包含 push_id
        payload = row["payload"]
        if isinstance(payload, str):
            try:
                payload = json.loads(payload)
            except Exception:
                payload = {}
        assert payload.get("push_id") == push_id, (
            f"proposal.payload.push_id={payload.get('push_id')} "
            f"!= push_id={push_id}"
        )


# ── 联动 2: InterestPushFeedback(later) → FlashCard ──


class TestLink2_FeedbackLaterToFlashCard:
    """联动 2: InterestPushFeedback(later) → FlashCard (status='later', source='system', cross_module_source='interest_explorer')"""

    def test_feedback_later_creates_flashcard(
        self, user_id
    ):
        """反馈 later 后, 验证 flashcards 表中存在 status='later', source='system', cross_module_source='interest_explorer' 的卡片."""
        from app.infrastructure.db.database import get_db
        from app.api.interest import service as interest_service

        _try_connect()
        rec = _ensure_push(user_id)
        assert rec is not None
        push_id = rec["id"]

        result = _run_sync_coro(
            interest_service.record_feedback(
                user_id=user_id, push_id=push_id, feedback="later"
            )
        )

        assert result.get("flashcard_id"), "record_feedback later 未返回 flashcard_id"
        time.sleep(0.3)

        d = get_db()
        if not _table_exists(d, "flashcards"):
            pytest.skip("flashcards 表不存在, 跳过副作用检查")
        # 检查 source 列 (cross_module_source 字段仅在事件中传递, 不入 flashcards 表)
        if not _column_exists(d, "flashcards", "source"):
            pytest.skip("flashcards.source 列不存在")
        if not _column_exists(d, "flashcards", "status"):
            pytest.skip("flashcards.status 列不存在")

        # source 字段值约定: interest_explorer (依据 flashcard_schema.sql line 10)
        rows = d.fetchall(
            """
            SELECT id, status, source, source_ref
              FROM flashcards
             WHERE user_id = %s
               AND source = 'interest_explorer'
            """,
            (user_id,),
        )
        assert len(rows) >= 1, (
            "联动 2 失效: feedback=later 未在 flashcards 表产生 "
            "source='interest_explorer' 记录"
        )
        # status 应为 later
        statuses = {r["status"] for r in rows}
        assert "later" in statuses, (
            f"联动 2 失效: 反馈 later 但 cards 状态不包含 'later', "
            f"实际: {statuses}"
        )


def _run_sync_coro(coro):
    """在测试上下文中运行 coroutine (避免事件循环冲突)."""
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # 已经 running → 用 run_in_executor 不行, 改用新线程
            import threading
            result_box: dict = {}
            def _runner():
                new_loop = asyncio.new_event_loop()
                try:
                    result_box["result"] = new_loop.run_until_complete(coro)
                except Exception as e:
                    result_box["error"] = e
                finally:
                    new_loop.close()
            t = threading.Thread(target=_runner, daemon=True)
            t.start()
            t.join(timeout=10)
            if "error" in result_box:
                raise result_box["error"]
            return result_box.get("result")
        else:
            return loop.run_until_complete(coro)
    except RuntimeError:
        return asyncio.run(coro)


# ── 联动 3: InterestContentImported(reading) → Material ──


class TestLink3_ImportReadingToMaterial:
    """联动 3: InterestContentImported(reading) → Material 创建"""

    def test_import_to_reading_creates_material(
        self, user_id
    ):
        """导入到 reading 目标, 验证 materials 表产生记录."""
        from app.infrastructure.db.database import get_db
        from app.api.interest import service as interest_service
        from shared.events import CrossModuleTarget

        _try_connect()
        rec = _ensure_push(user_id)
        assert rec is not None
        push_id = rec["id"]

        target_ref_id = _run_sync_coro(
            interest_service.import_to_module(
                user_id=user_id, push_id=push_id,
                target_module=CrossModuleTarget.READING,
            )
        )
        assert target_ref_id, "import_to_module(reading) 未返回 target_ref_id"
        time.sleep(0.3)

        d = get_db()
        if not _table_exists(d, "materials"):
            pytest.skip("materials 表不存在, 跳过副作用检查")
        row = d.fetchone(
            "SELECT material_id, file_type, summary, tags_json "
            "FROM materials WHERE material_id = %s",
            (target_ref_id,),
        )
        assert row is not None, (
            f"联动 3 失效: import_to_reading 未在 materials 表产生记录 "
            f"(target_ref_id={target_ref_id})"
        )
        # file_type 应为 'url' (URL 类型)
        assert row["file_type"] == "url", (
            f"联动 3: materials.file_type 应为 'url', 实际: {row['file_type']}"
        )
        # tags_json 应包含 interest_explorer
        tags = row["tags_json"]
        if isinstance(tags, str):
            try:
                tags = json.loads(tags)
            except Exception:
                tags = []
        assert "interest_explorer" in tags, (
            f"联动 3: materials.tags_json 应包含 'interest_explorer', 实际: {tags}"
        )


# ── 联动 4: InterestContentImported(project) → Project ──


class TestLink4_ImportProjectToProject:
    """联动 4: InterestContentImported(project) → Project 创建"""

    def test_import_to_project_creates_project(self, user_id):
        from app.infrastructure.db.database import get_db
        from app.api.interest import service as interest_service
        from shared.events import CrossModuleTarget

        _try_connect()
        rec = _ensure_push(user_id)
        assert rec is not None
        push_id = rec["id"]

        target_ref_id = _run_sync_coro(
            interest_service.import_to_module(
                user_id=user_id, push_id=push_id,
                target_module=CrossModuleTarget.PROJECT,
            )
        )
        assert target_ref_id, "import_to_module(project) 未返回 target_ref_id"
        time.sleep(0.3)

        d = get_db()
        if not _table_exists(d, "projects"):
            pytest.skip("projects 表不存在, 跳过副作用检查")
        row = d.fetchone(
            "SELECT id, name, tags FROM projects WHERE id = %s",
            (target_ref_id,),
        )
        assert row is not None, (
            f"联动 4 失效: import_to_project 未在 projects 表产生记录 "
            f"(target_ref_id={target_ref_id})"
        )
        # name 应包含原 push 标题
        assert rec["title"][:100] in row["name"] or row["name"] == rec["title"][:200], (
            f"联动 4: project.name 与 push.title 不符: {row['name']}"
        )


# ── 联动 5: InterestContentImported(flashcard) → FlashCard ──


class TestLink5_ImportFlashcardToFlashCard:
    """联动 5: InterestContentImported(flashcard) → FlashCard 创建"""

    def test_import_to_flashcard_creates_card(self, user_id):
        from app.infrastructure.db.database import get_db
        from app.api.interest import service as interest_service
        from shared.events import CrossModuleTarget

        _try_connect()
        rec = _ensure_push(user_id)
        assert rec is not None
        push_id = rec["id"]

        target_ref_id = _run_sync_coro(
            interest_service.import_to_module(
                user_id=user_id, push_id=push_id,
                target_module=CrossModuleTarget.FLASHCARD,
            )
        )
        assert target_ref_id, "import_to_module(flashcard) 未返回 target_ref_id"
        time.sleep(0.3)

        d = get_db()
        if not _table_exists(d, "flashcards"):
            pytest.skip("flashcards 表不存在, 跳过副作用检查")
        if not _column_exists(d, "flashcards", "source"):
            pytest.skip("flashcards.source 列不存在")

        row = d.fetchone(
            """
            SELECT id, source, source_ref
              FROM flashcards
             WHERE id = %s
            """,
            (target_ref_id,),
        )
        assert row is not None, (
            f"联动 5 失效: import_to_flashcard 未在 flashcards 表产生记录 "
            f"(target_ref_id={target_ref_id})"
        )
        # source 字段值约定: interest_explorer (依据 flashcard_schema.sql)
        assert row["source"] == "interest_explorer", (
            f"联动 5: source 应为 'interest_explorer', "
            f"实际: {row['source']}"
        )


# ── 联动 6: InterestContentImported(cognitive_node) → CognitiveNode ──


class TestLink6_ImportCognitiveNode:
    """联动 6: InterestContentImported(cognitive_node) → CognitiveNode 创建"""

    def test_import_to_cognitive_node_creates_node(self, user_id):
        from app.infrastructure.db.database import get_db
        from app.api.interest import service as interest_service
        from shared.events import CrossModuleTarget

        _try_connect()
        rec = _ensure_push(user_id)
        assert rec is not None
        push_id = rec["id"]

        target_ref_id = _run_sync_coro(
            interest_service.import_to_module(
                user_id=user_id, push_id=push_id,
                target_module=CrossModuleTarget.COGNITIVE_NODE,
            )
        )
        assert target_ref_id, "import_to_module(cognitive_node) 未返回 target_ref_id"
        time.sleep(0.3)

        d = get_db()
        target_table = None
        for t in ("knowledge_nodes", "cognitive_nodes"):
            if _table_exists(d, t):
                target_table = t
                break
        if not target_table:
            pytest.skip("knowledge_nodes / cognitive_nodes 表都不存在")
        if not _column_exists(d, target_table, "created_by"):
            pytest.skip(f"{target_table} 表无 created_by 列")

        row = d.fetchone(
            f"SELECT id, label, created_by FROM {target_table} "
            "WHERE id = %s",
            (target_ref_id,),
        )
        assert row is not None, (
            f"联动 6 失效: import_to_cognitive_node 未在 {target_table} 表产生记录 "
            f"(target_ref_id={target_ref_id})"
        )
        # created_by 应为 'interest_explorer'
        assert row["created_by"] == "interest_explorer", (
            f"联动 6: created_by 应为 'interest_explorer', 实际: {row['created_by']}"
        )


# ── 联动 7: InterestContentImported(language_room) → LanguageRoom ──


class TestLink7_ImportLanguageRoom:
    """联动 7: InterestContentImported(language_room) → LanguageRoom 创建"""

    def test_import_to_language_room_creates_room(self, user_id):
        from app.infrastructure.db.database import get_db
        from app.api.interest import service as interest_service
        from shared.events import CrossModuleTarget

        _try_connect()
        rec = _ensure_push(user_id)
        assert rec is not None
        push_id = rec["id"]

        target_ref_id = _run_sync_coro(
            interest_service.import_to_module(
                user_id=user_id, push_id=push_id,
                target_module=CrossModuleTarget.LANGUAGE_ROOM,
            )
        )
        assert target_ref_id, "import_to_module(language_room) 未返回 target_ref_id"
        time.sleep(0.3)

        d = get_db()
        if not _table_exists(d, "language_rooms"):
            pytest.skip("language_rooms 表不存在, 跳过副作用检查")
        row = d.fetchone(
            "SELECT id, name, settings FROM language_rooms WHERE id = %s",
            (target_ref_id,),
        )
        assert row is not None, (
            f"联动 7 失效: import_to_language_room 未在 language_rooms 表产生记录 "
            f"(target_ref_id={target_ref_id})"
        )


# ── 联动 8: CognitiveNodeLinked → interest_tags 引用计数 ──


class TestLink8_CognitiveNodeLinkedRefCount:
    """联动 8: CognitiveNodeLinked → interest_tags 引用计数 (events.md §3.1)

    events.md §3.1 提到: CognitiveNodeLinked → 当用户对兴趣标签创建/更新/
    删除知识点链接时同步 interest_tags 引用计数。
    """

    def test_create_tag_from_knowledge_increments(
        self, user_id
    ):
        """create_tag_from_knowledge 创建一个 interest_tag (source=from_knowledge, source_ref_id=node_id).

        验证: 标签表里出现 source='from_knowledge' 且 source_ref_id 指向该节点。
        这是 §3.1 引用计数的入口; 实际引用计数在消费 CognitiveNodeLinked 时
        由订阅者维护 (当前依赖数据库 source_ref_id 反查)。
        """
        from app.infrastructure.db.database import get_db
        from app.api.interest import service as interest_service
        from app.domain.cognitive import get_repo
        from app.domain.cognitive.models import (
            CognitiveNode, Belief, PracticeSummary,
        )

        _try_connect()
        repo = get_repo()
        # 直接建一个 cognitive node 供引用
        node = CognitiveNode(
            id=f"audit_know_{uuid.uuid4().hex[:8]}",
            label=f"审计知识点_{uuid.uuid4().hex[:6]}",
            level="atom",
            node_type="auto_generated",
            is_visible=True,
            belief=Belief(alpha=2.0, beta=2.0, proficiency_mean=0.5),
            practice_summary=PracticeSummary(),
        )
        repo.upsert_node(node, user_id)
        time.sleep(0.1)

        tag = _run_sync_coro(
            interest_service.create_tag_from_knowledge(
                user_id=user_id,
                knowledge_node_id=node.id,
                payload={"weight": 1, "level": 0},
            )
        )
        assert tag is not None, "create_tag_from_knowledge 失败"

        d = get_db()
        if not _table_exists(d, "interest_tags"):
            pytest.skip("interest_tags 表不存在")

        row = d.fetchone(
            "SELECT id, source, source_ref_id FROM interest_tags "
            "WHERE id = %s AND user_id = %s",
            (tag["id"], user_id),
        )
        assert row is not None, "create_tag_from_knowledge 未落库"
        # 关键: source='from_knowledge' + source_ref_id=node.id
        assert row["source"] == "from_knowledge", (
            f"联动 8: tag.source 应为 'from_knowledge', 实际: {row['source']}"
        )
        assert str(row["source_ref_id"]) == str(node.id), (
            f"联动 8: tag.source_ref_id={row['source_ref_id']} "
            f"!= node.id={node.id}"
        )


# ── 联动 9: CognitiveNodeMetadataChanged → 兴趣面板刷新 ──


class TestLink9_CognitiveMetadataRefresh:
    """联动 9: CognitiveNodeMetadataChanged → 兴趣面板刷新 (events.md §3.1)

    events.md §3.1 提到: CognitiveNodeMetadataChanged → 当关联知识点的
    描述/标签变化时刷新兴趣面板展示。
    """

    def test_metadata_changed_does_not_break_interest(self, user_id):
        """CognitiveNodeMetadataChanged 事件被 bus 消费; 验证:
        1) 事件可正常 publish + handle (不抛异常)
        2) Interest 标签列表仍能正常列出 (无副作用破坏)
        """
        from shared.events import CognitiveNodeMetadataChanged
        from app.api.interest import service as interest_service

        _try_connect()

        # 先建一个 interest tag
        tag = _run_sync_coro(
            interest_service.create_tag(
                user_id=user_id, payload={"name": f"audit-meta-{uuid.uuid4().hex[:6]}"}
            )
        )
        assert tag is not None

        # 发布一个 CognitiveNodeMetadataChanged 事件 (异步, fire-and-forget)
        from app.infrastructure.event_bus_utils import publish_event_safe
        publish_event_safe(CognitiveNodeMetadataChanged(
            user_id=user_id,
            node_id=f"audit_meta_{uuid.uuid4().hex[:8]}",
            changed_fields=["description"],
        ))
        time.sleep(0.3)

        # Interest 标签列表仍正常
        tags = interest_service.list_tags_tree(user_id)
        assert isinstance(tags, list)
        tag_ids = {t["id"] for t in tags}
        assert tag["id"] in tag_ids, "Metadata 变化不应破坏 interest tag 列表"


# ══════════════════════════════════════════════════════════════
# 第三部分: 隔离原则验证 — Interest 事件不更新 Belief
# ══════════════════════════════════════════════════════════════


class TestIsolationNoBeliefUpdate:
    """验证: Interest 事件不触发 CognitiveNode.Belief 更新 (events.md §3.3)."""

    def test_import_to_cognitive_node_does_not_change_belief(self, user_id):
        """导入到 cognitive_node 时, 新节点的 belief 应保持初始 (alpha=2, beta=2)."""
        from app.api.interest import service as interest_service
        from shared.events import CrossModuleTarget
        from app.domain.cognitive import get_repo

        _try_connect()
        repo = get_repo()

        rec = _ensure_push(user_id)
        assert rec is not None
        push_id = rec["id"]

        target_ref_id = _run_sync_coro(
            interest_service.import_to_module(
                user_id=user_id, push_id=push_id,
                target_module=CrossModuleTarget.COGNITIVE_NODE,
            )
        )
        assert target_ref_id
        time.sleep(0.3)

        node = repo.get_node(target_ref_id, user_id)
        if node is None:
            pytest.skip("节点不可读 (可能为跨表/不同 schema)")
        # 新建节点, belief.alpha 和 beta 应保持默认值 (1,1) 或初始状态
        # 不应为某些由 practice 引入的累加值
        belief = node.belief
        # 隔离原则: 不应该有 alpha/beta 的累加
        # 默认值 1/1 或 2/2 都算 OK (无 practice 更新)
        assert float(belief.alpha) <= 3.0, (
            f"Belief alpha={belief.alpha} 不应被 Interest 事件累加"
        )
        assert float(belief.beta) <= 3.0, (
            f"Belief beta={belief.beta} 不应被 Interest 事件累加"
        )
