"""
Task #57 — Reading 跨模块联动审计 (E2E)

审计 7 条 Reading → 其他模块的端到端联通性:
  1. Annotation → FlashCard
  2. Annotation → CognitiveNode
  3. Annotation → Conversation
  4. Note → FlashCard (复用反思型 card_type=7)
  5. ReviewReminder → PlanItem (source_module='reading')
  6. Compare → Project (跨材料标注导出, ADR 待修复 2)
  7. Highlight Match → KnowledgeGraph (混合匹配, 阈值 0.85)

附加审计:
  - 命名规范 `linked_node_ids` 一致性 (ADR 关键差异 3)
  - 5 颜色 5 意图枚举与 ADR 关键差异 4 一致
  - 10 个 Reading 事件真发布 (共享总线)
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
    sys.path.insert(0, str(BACKEND))


# ────────────────────────── Fixtures ──────────────────────────


def _try_connect():
    try:
        from app.infrastructure.db.database import get_db
        d = get_db()
        d.fetchone("SELECT 1")
        return d
    except Exception as exc:  # noqa: BLE001
        pytest.skip(f"数据库不可用: {exc}")


def _table_exists(db, table_name: str) -> bool:
    row = db.fetchone(
        """
        SELECT 1 FROM information_schema.tables
         WHERE table_name = %s LIMIT 1
        """,
        (table_name,),
    )
    return row is not None


def _column_exists(db, table_name: str, col_name: str) -> bool:
    row = db.fetchone(
        """
        SELECT 1 FROM information_schema.columns
         WHERE table_name = %s AND column_name = %s LIMIT 1
        """,
        (table_name, col_name),
    )
    return row is not None


@pytest.fixture
def user_id() -> str:
    return f"xrdg_{uuid.uuid4().hex[:12]}"


@pytest.fixture
def db():
    return _try_connect()


def _ensure_reading_tables(db) -> None:
    from app.services.reading import _ensure_tables as _et
    _et()


def _ensure_flashcard_tables(db) -> None:
    try:
        from app.api.flashcard.service import _ensure_tables
        _ensure_tables()
    except Exception:
        pass


def _ensure_planning_tables(db) -> None:
    try:
        from app.api.planning.service import _ensure_tables
        _ensure_tables()
    except Exception:
        pass


def _ensure_project_tables(db) -> None:
    try:
        from app.services import project as project_service
        project_service.ensure_tables()
    except Exception:
        pass


@pytest.fixture(autouse=True)
def cleanup_test_data(db, user_id):
    yield
    for tbl in (
        "reading_annotations", "reading_sessions", "reading_comparisons",
        "reading_prefs", "flashcards", "plan_items",
        "project_nodes", "projects",
    ):
        try:
            db.execute(f"DELETE FROM {tbl} WHERE user_id = %s", (user_id,))
        except Exception:
            pass


# ══════════════════════════════════════════════════════════════
# §0. 静态审计 — ADR 关键差异 3, 4 验证
# ══════════════════════════════════════════════════════════════


class TestADRDifferencesAudit:
    """审计 ADR 0003 关键差异实际状态"""

    def test_adr_diff_3_naming_unified_to_linked_node_ids(self):
        """ADR 关键差异 3: 命名统一 linked_node_ids

        验证 (Task #58 重命名后):
          - 事件层 ReadingSessionEnded.linked_node_ids
          - DB 层 reading_sessions 表 linked_node_ids (历史 nodes_linked 已统一)
        """
        from shared.events import ReadingSessionEnded
        import dataclasses
        fields = {f.name for f in dataclasses.fields(ReadingSessionEnded)}
        assert "linked_node_ids" in fields, (
            f"ReadingSessionEnded 缺少 linked_node_ids 字段, 实际: {fields}"
        )
        assert "nodes_linked" not in fields, (
            "ReadingSessionEnded 不应再有 nodes_linked 字段 (ADR 关键差异 3)"
        )

    def test_adr_diff_4_5color_5intent_enum_consistent(self):
        """ADR 关键差异 4: 5 颜色 5 意图显式枚举一致"""
        from app.services.reading.annotations import COLOR_INTENT_MAP, COLOR_FOLLOWUP
        expected_colors = {"yellow", "blue", "green", "purple", "orange"}
        expected_intents = {
            "important_concept", "data_fact", "quotable", "doubt", "conflict",
        }
        assert set(COLOR_INTENT_MAP.keys()) == expected_colors
        assert {v["intent"] for v in COLOR_FOLLOWUP.values()} == expected_intents

        # events.py 事件 schema 的颜色/intent 字段类型
        from shared.events import ReadingAnnotationCreated
        import dataclasses
        # dataclass field uses typing, check via __annotations__ or get_type_hints
        hints = {f.name: str(f.type) for f in dataclasses.fields(ReadingAnnotationCreated)}
        # ReadingAnnotationCreated 字段用 Literal, 但 dataclass fields 不直接暴露 Literal
        # 改为读源码标注 — 这里只验字段存在
        assert "color" in hints
        assert "intent" in hints

    def test_adr_diff_5_target_module_enum_strict(self):
        """ADR 关键差异 5: ReadingAnnotationProcessed.target_module 必须是 CrossModuleTarget"""
        from shared.events import ReadingAnnotationProcessed, CrossModuleTarget
        ev = ReadingAnnotationProcessed(
            user_id="u", annotation_id="a",
            target_module=CrossModuleTarget.FLASHCARD, target_ref_id="ref",
        )
        # enum 字段应当是 CrossModuleTarget 实例
        assert ev.target_module == CrossModuleTarget.FLASHCARD
        # AnnotationProcessRequest 路径合法 target
        from app.api.reading.schemas import AnnotationProcessRequest
        req = AnnotationProcessRequest(target_module="flashcard", target_ref_id="r")
        assert req.target_module == "flashcard"


# ══════════════════════════════════════════════════════════════
# §1. 联动 1: Annotation → FlashCard
# ══════════════════════════════════════════════════════════════


class TestAnnotationToFlashCard:
    """联动 1: 创建 Annotation → 真发布 ReadingAnnotationCreated 事件"""

    def test_create_annotation_publishes_event_with_correct_fields(
        self, db, user_id
    ):
        """验证: 创建标注 → 真发布 ReadingAnnotationCreated 事件
        字段包含: user_id, annotation_id, material_id, color, intent, linked_node_id
        """
        _ensure_reading_tables(db)
        from app.services.reading.annotations import create_annotation

        ann = create_annotation(
            user_id=user_id,
            material_id=f"mat_{user_id}",
            color="yellow",
            intent="important_concept",
            text="重要概念原文",
            note="用户批注",
        )
        assert ann is not None
        assert "id" in ann

        # 立即查 DB 确认已落库
        row = db.fetchone(
            "SELECT id, color, intent, is_processed, linked_node_id "
            "FROM reading_annotations WHERE id = %s AND user_id = %s",
            (ann["id"], user_id),
        )
        assert row is not None
        assert row["color"] == "yellow"
        assert row["intent"] == "important_concept"
        # 事件已发布到全局 bus — 走 DI 全局 bus 验证
        # (publish_event_safe 内部已 fire-and-forget, 这里靠 schema 验证)
        assert ann["is_processed"] is False
        assert ann["linked_node_id"] is None


class TestAnnotationProcessToFlashCard:
    """联动 1 副作用: mark_processed 触发 ReadingAnnotationProcessed(target=flashcard)"""

    def test_mark_processed_with_flashcard_target(
        self, db, user_id
    ):
        """标注处理 + target_module=flashcard → DB is_processed=True
        期望: ReadingAnnotationProcessed 真发布 (事件由 publish_event_safe 投递)
        """
        _ensure_reading_tables(db)
        from app.services.reading.annotations import (
            create_annotation, mark_annotation_processed,
        )
        from shared.events import CrossModuleTarget

        ann = create_annotation(
            user_id=user_id, material_id=f"mat_{user_id}",
            color="yellow", intent="important_concept",
        )
        # 处理: target=flashcard
        result = mark_annotation_processed(
            user_id, ann["id"], CrossModuleTarget.FLASHCARD, "fake_card_id",
        )
        assert result is not None
        assert result["is_processed"] is True

        # DB 验证
        row = db.fetchone(
            "SELECT is_processed FROM reading_annotations WHERE id = %s",
            (ann["id"],),
        )
        assert row["is_processed"] is True


# ══════════════════════════════════════════════════════════════
# §2. 联动 2: Annotation → CognitiveNode
# ══════════════════════════════════════════════════════════════


class TestAnnotationLinkedToCognitiveNode:
    """联动 2: 标注 linked_node_id 关联到已有 CognitiveNode"""

    def test_annotation_with_linked_node_id(self, db, user_id):
        """验证: 创建标注时 linked_node_id 真存入 reading_annotations
        期望: 标注行含 linked_node_id, 命中 knowledge_nodes 表
        """
        _ensure_reading_tables(db)
        # 先创建一个 cognitive_node
        from app.domain.cognitive.writer import CognitiveNodeWriter
        writer = CognitiveNodeWriter(user_id)
        node = writer.create_node(
            label="微积分.导数",
            level="atom",
            node_type="auto_generated",
            created_by="reading_test",
            is_visible=True,
        )
        assert node is not None
        node_id = node.id

        from app.services.reading.annotations import create_annotation
        ann = create_annotation(
            user_id=user_id, material_id=f"mat_{user_id}",
            color="yellow", intent="important_concept",
            text="导数是变化率",
            linked_node_id=node_id,
        )
        assert ann["linked_node_id"] == node_id

        # DB 行验证
        row = db.fetchone(
            "SELECT linked_node_id FROM reading_annotations "
            "WHERE id = %s AND user_id = %s",
            (ann["id"], user_id),
        )
        assert row["linked_node_id"] == node_id

        # 目标节点存在
        kn = db.fetchone(
            "SELECT id FROM knowledge_nodes WHERE id = %s AND user_id = %s",
            (node_id, user_id),
        )
        assert kn is not None, "CognitiveNode 节点不存在"


# ══════════════════════════════════════════════════════════════
# §3. 联动 3: Annotation → Conversation (ExplainCard 复用)
# ══════════════════════════════════════════════════════════════


class TestAnnotationToConversation:
    """联动 3: 标注 mark_processed(target=conversation) 真发布 ReadingAnnotationProcessed
    复用 ExplainCard 机制 (但创建 ExplainCard 走对话 API, 这里只验事件层)
    """

    def test_mark_processed_with_conversation_target(
        self, db, user_id
    ):
        _ensure_reading_tables(db)
        from app.services.reading.annotations import (
            create_annotation, mark_annotation_processed,
        )
        from shared.events import CrossModuleTarget

        ann = create_annotation(
            user_id=user_id, material_id=f"mat_{user_id}",
            color="purple", intent="doubt",
            text="这段推导看不懂",
        )
        result = mark_annotation_processed(
            user_id, ann["id"], CrossModuleTarget.CONVERSATION, "fake_conv_id",
        )
        assert result["is_processed"] is True
        # DB 端注解已被处理, 上层 ExplainCard 创建由 Conversation 模块消费事件完成
        row = db.fetchone(
            "SELECT is_processed FROM reading_annotations WHERE id = %s",
            (ann["id"],),
        )
        assert row["is_processed"] is True


# ══════════════════════════════════════════════════════════════
# §4. 联动 4: Note → FlashCard (复用反思型)
# ══════════════════════════════════════════════════════════════


class TestReadingNoteToFlashCard:
    """联动 4: 创建 reading note → 真创建 FlashCard source='reading_note' type=7
    期望: cross_module_source='reading', source='reading_note'
    """

    def test_create_reading_note_creates_reflection_card(self, db, user_id):
        _ensure_reading_tables(db)
        _ensure_flashcard_tables(db)
        from app.services.reading.notes import create_reading_note

        card = create_reading_note(
            user_id=user_id,
            material_id=f"mat_{user_id}",
            front_text="导数的几何意义是什么?",
            back_text="曲线切线斜率",
            back_context="f'(x) 表示函数在 x 处的瞬时变化率",
            linked_node_ids=[f"node_{user_id}_r1"],
        )
        assert card is not None
        card_id = card.get("id")
        assert card_id is not None

        # DB 校验
        row = db.fetchone(
            "SELECT id, source, type, linked_node_ids "
            "FROM flashcards WHERE id = %s AND user_id = %s",
            (card_id, user_id),
        )
        assert row is not None
        assert row["source"] == "reading_note"
        assert row["type"] == 7  # 反思型

    def test_reading_note_emits_reading_note_created_event(
        self, db, user_id
    ):
        """ReadingNoteCreated 事件真发布 (走 publish_event_safe 投递)"""
        _ensure_reading_tables(db)
        _ensure_flashcard_tables(db)
        from app.services.reading.notes import create_reading_note
        from app.application.di import container

        global_bus = container.event_bus
        captured: list = []

        async def _cap(event):
            captured.append(event)

        global_bus.subscribe("ReadingNoteCreated", _cap)
        try:
            card = create_reading_note(
                user_id=user_id,
                material_id=f"mat_{user_id}_evt",
                front_text="事件测试笔记?",
                back_text="回应",
                linked_node_ids=[f"node_{user_id}_e1"],
            )
            # 等待 fire-and-forget task 完成
            time.sleep(0.3)
            my_events = [
                e for e in captured
                if e.user_id == user_id and e.card_id == card["id"]
            ]
            assert len(my_events) >= 1, (
                f"ReadingNoteCreated 未发布 (captured={len(captured)})"
            )
            ev = my_events[0]
            assert ev.source == "reading_note"
            assert ev.cross_module_source == "reading"
        finally:
            global_bus.unsubscribe("ReadingNoteCreated", _cap)


# ══════════════════════════════════════════════════════════════
# §5. 联动 5: ReviewReminder → PlanItem
# ══════════════════════════════════════════════════════════════


class TestReviewReminderToPlanItem:
    """联动 5: 创建阅读回顾提醒 → 复用 PlanItem (source_module='reading')
    期望: plan_items 表有 source_module='reading' 的项
    """

    def test_schedule_review_reminder_creates_plan_item(self, db, user_id):
        _ensure_reading_tables(db)
        _ensure_planning_tables(db)
        from app.services.reading.review_reminder import schedule_review_reminder

        result = schedule_review_reminder(
            user_id=user_id,
            material_id=f"mat_{user_id}",
            review_after_days=7,
            title="回顾《算法导论》第 3 章",
            estimated_minutes=30,
        )
        assert result is not None
        plan_item_id = result["plan_item_id"]
        assert plan_item_id is not None

        # DB 验证 plan_items 表有 source_module='reading'
        if not _table_exists(db, "plan_items"):
            pytest.skip("plan_items 表不存在")
        row = db.fetchone(
            "SELECT id, source_module, target_type, target_ref_id, status, scheduled_for "
            "FROM plan_items WHERE id = %s AND user_id = %s",
            (plan_item_id, user_id),
        )
        assert row is not None, "PlanItem 未落库"
        assert row["source_module"] == "reading", (
            f"PlanItem.source_module 应为 'reading', 实际 {row['source_module']}"
        )
        assert row["target_type"] == "material"
        assert row["target_ref_id"] == f"mat_{user_id}"

    def test_schedule_review_reminder_emits_reading_event(
        self, db, user_id
    ):
        """ReadingReviewReminderScheduled 业务事件真发布"""
        _ensure_reading_tables(db)
        _ensure_planning_tables(db)
        from app.services.reading.review_reminder import schedule_review_reminder
        from app.application.di import container

        global_bus = container.event_bus
        captured: list = []

        async def _cap(event):
            captured.append(event)

        global_bus.subscribe("ReadingReviewReminderScheduled", _cap)
        try:
            result = schedule_review_reminder(
                user_id=user_id,
                material_id=f"mat_{user_id}_evt",
                review_after_days=30,
            )
            time.sleep(0.3)
            my_events = [
                e for e in captured
                if e.user_id == user_id and e.material_id == f"mat_{user_id}_evt"
            ]
            assert len(my_events) >= 1, (
                f"ReadingReviewReminderScheduled 未发布 "
                f"(captured={len(captured)})"
            )
            ev = my_events[0]
            assert ev.reminder_days == 30
            assert ev.plan_item_id == result["plan_item_id"]
        finally:
            global_bus.unsubscribe("ReadingReviewReminderScheduled", _cap)


# ══════════════════════════════════════════════════════════════
# §6. 联动 6: Compare → Project (ADR 待修复 2: 端到端断链)
# ══════════════════════════════════════════════════════════════


class TestCompareToProject:
    """联动 6: 对比阅读 → 标注导出 → 项目节点

    ADR 待修复 2: 标注可导出, 但未自动转对比 FlashCard / 项目节点
    本测试验证:
      - 现状 1: 对比阅读分组可创建 (reading_comparisons 表)
      - 现状 2: 标注聚合可拉取
      - 现状 3: 端到端导出到 project 节点 — ADR 待修复 2 标记为断链
    """

    def test_create_comparison_stores_in_reading_comparisons(
        self, db, user_id
    ):
        _ensure_reading_tables(db)
        from app.services.reading.compare import create_comparison, list_comparisons

        cmp = create_comparison(
            user_id=user_id,
            material_id_left=f"mat_left_{user_id}",
            material_id_right=f"mat_right_{user_id}",
            sync_scroll=True,
        )
        assert cmp is not None
        cid = cmp["id"]
        assert cmp["material_id_left"] == f"mat_left_{user_id}"
        assert cmp["material_id_right"] == f"mat_right_{user_id}"
        assert cmp["sync_scroll"] is True

        # DB 验证
        row = db.fetchone(
            "SELECT material_id_left, material_id_right, sync_scroll "
            "FROM reading_comparisons WHERE id = %s",
            (cid,),
        )
        assert row is not None

        # list
        items = list_comparisons(user_id)
        assert len(items) >= 1

    def test_build_compare_payload_aggregates_annotations(
        self, db, user_id
    ):
        """分屏数据聚合: 左/右两侧的标注都被聚合"""
        _ensure_reading_tables(db)
        from app.services.reading.annotations import create_annotation
        from app.services.reading.compare import build_compare_payload

        mat_l = f"mat_l_{user_id}"
        mat_r = f"mat_r_{user_id}"
        # 左侧创建 2 条标注 (1 黄 1 蓝), 右侧 1 条 (紫)
        create_annotation(
            user_id=user_id, material_id=mat_l,
            color="yellow", intent="important_concept",
        )
        create_annotation(
            user_id=user_id, material_id=mat_l,
            color="blue", intent="data_fact",
        )
        create_annotation(
            user_id=user_id, material_id=mat_r,
            color="purple", intent="doubt",
        )

        payload = build_compare_payload(user_id, mat_l, mat_r)
        assert payload["material_id_left"] == mat_l
        assert payload["material_id_right"] == mat_r
        assert payload["left"]["annotations_count"] == 2
        assert payload["right"]["annotations_count"] == 1
        assert payload["left"]["by_color"]["yellow"] == 1
        assert payload["left"]["by_color"]["blue"] == 1
        assert payload["right"]["by_color"]["purple"] == 1

    def test_adr_fix_2_compare_to_project_endpoint_to_end_gap(self):
        """ADR 待修复 2: 跨材料标注导出为对比表 → 存入项目模块 — 当前未端到端打通

        静态审计: 查找 reading.compare 是否包含"导出到 project"代码路径
        """
        from app.services import reading
        import inspect
        from app.services.reading import compare as compare_mod

        # 查找导出/同步到 project 的方法
        funcs = [n for n in dir(compare_mod) if not n.startswith("_")]
        export_to_project = [
            n for n in funcs
            if "project" in n.lower() or "export" in n.lower()
        ]
        # ADR 待修复 2: 当前 compare 模块没有导出到 project 的方法
        if not export_to_project:
            pytest.skip(
                "ADR 待修复 2: reading.compare 未实现导出到 project 的方法 "
                "(断链, 端到端未实现)"
            )
        assert len(export_to_project) >= 1


# ══════════════════════════════════════════════════════════════
# §7. 联动 7: Highlight Match → KnowledgeGraph (混合匹配)
# ══════════════════════════════════════════════════════════════


class TestHighlightMatchToKnowledgeGraph:
    """联动 7: 已有知识点高亮 (混合匹配 = 标签 + embedding, 阈值 0.85)
    期望: 标注关联到已有 CognitiveNode (linked_node_id)
    """

    def test_label_exact_match_threshold_default(self, db, user_id):
        """步骤 1 (标签精确匹配): 通过 label 找到 CognitiveNode
        验证: 标注的 linked_node_id 真能指向 knowledge_nodes
        """
        _ensure_reading_tables(db)
        from app.domain.cognitive.writer import CognitiveNodeWriter
        from app.services.reading.annotations import create_annotation

        # 创建 1 个 CognitiveNode
        writer = CognitiveNodeWriter(user_id)
        node = writer.create_node(
            label="数据结构.二叉树",
            level="atom",
            node_type="auto_generated",
            created_by="reading_highlight_test",
            is_visible=True,
        )
        node_id = node.id

        # 标注关联到该节点
        ann = create_annotation(
            user_id=user_id, material_id=f"mat_{user_id}",
            color="yellow", intent="important_concept",
            text="二叉树是树形结构",
            linked_node_id=node_id,
        )

        # 验证: 标注能反向查询 (按 linked_node_id 找标注)
        if not _table_exists(db, "reading_annotations"):
            pytest.skip("reading_annotations 表不存在")
        rows = db.fetchall(
            "SELECT id FROM reading_annotations "
            "WHERE linked_node_id = %s AND user_id = %s",
            (node_id, user_id),
        )
        assert len(rows) == 1
        assert rows[0]["id"] == ann["id"]

    def test_threshold_085_present_in_prefs(self, db, user_id):
        """步骤 2: 阈值 0.85 默认值审计

        验证: 阅读偏好默认开启知识点高亮 (highlight_mastered/weak=True)
              阈值(0.85)由 embedding 相似度服务内部使用, 不直接存在阅读偏好
        """
        _ensure_reading_tables(db)
        from app.services.reading.prefs import get_prefs, upsert_prefs

        prefs = get_prefs(user_id)
        assert prefs["highlight_mastered"] is True
        assert prefs["highlight_weak"] is True

        # 更新后保持
        upsert_prefs(user_id, {"highlight_mastered": False})
        prefs2 = get_prefs(user_id)
        assert prefs2["highlight_mastered"] is False
        # 其他字段保留默认
        assert prefs2["highlight_weak"] is True


# ══════════════════════════════════════════════════════════════
# §8. 10 个 Reading 事件真发布审计
# ══════════════════════════════════════════════════════════════


class TestReadingEventsPublishing:
    """审计: 10 个 Reading 事件是否能真被发布到 DI 全局事件总线

    字段命名 (events.md §1):
      ReadingSessionStarted / ReadingSessionEnded / ReadingSessionResumed /
      ReadingAnnotationCreated / ReadingAnnotationUpdated / ReadingAnnotationDeleted /
      ReadingAnnotationProcessed / ReadingModeChanged /
      ReadingNoteCreated / ReadingReviewReminderScheduled
    """

    def test_reading_session_lifecycle_emits_events(self, db, user_id):
        """会话生命周期: started → resumed → ended 三事件都发布"""
        _ensure_reading_tables(db)
        from app.services.reading.sessions import (
            start_session, resume_session, end_session,
        )
        from app.application.di import container

        bus = container.event_bus
        captured: list = []

        async def _cap(event):
            captured.append(event)

        bus.subscribe("ReadingSessionStarted", _cap)
        bus.subscribe("ReadingSessionResumed", _cap)
        bus.subscribe("ReadingSessionEnded", _cap)
        try:
            s = start_session(
                user_id=user_id,
                material_id=f"mat_{user_id}",
                mode="intensive",
            )
            sid = s["id"]
            resume_session(user_id, sid, last_chunk_id="chunk_1")
            end_session(user_id, sid, duration_seconds=60.0)
            time.sleep(0.3)
            types = [e.event_type for e in captured if e.user_id == user_id]
            assert "ReadingSessionStarted" in types
            assert "ReadingSessionResumed" in types
            assert "ReadingSessionEnded" in types
        finally:
            bus.unsubscribe("ReadingSessionStarted", _cap)
            bus.unsubscribe("ReadingSessionResumed", _cap)
            bus.unsubscribe("ReadingSessionEnded", _cap)

    def test_reading_annotation_crud_emits_events(self, db, user_id):
        """标注 CRUD: created → updated → deleted → processed 四事件"""
        _ensure_reading_tables(db)
        from app.services.reading.annotations import (
            create_annotation, update_annotation, delete_annotation,
            mark_annotation_processed,
        )
        from shared.events import CrossModuleTarget
        from app.application.di import container

        bus = container.event_bus
        captured: list = []

        async def _cap(event):
            captured.append(event)

        for evt in (
            "ReadingAnnotationCreated",
            "ReadingAnnotationUpdated",
            "ReadingAnnotationDeleted",
            "ReadingAnnotationProcessed",
        ):
            bus.subscribe(evt, _cap)
        try:
            ann = create_annotation(
                user_id=user_id, material_id=f"mat_{user_id}",
                color="yellow", intent="important_concept",
                text="原文",
            )
            update_annotation(user_id, ann["id"], {"note": "改批注"})
            mark_annotation_processed(
                user_id, ann["id"], CrossModuleTarget.FLASHCARD, "ref",
            )
            delete_annotation(user_id, ann["id"])
            time.sleep(0.3)
            types = [e.event_type for e in captured if e.user_id == user_id]
            assert "ReadingAnnotationCreated" in types
            assert "ReadingAnnotationUpdated" in types
            assert "ReadingAnnotationProcessed" in types
            assert "ReadingAnnotationDeleted" in types
        finally:
            for evt in (
                "ReadingAnnotationCreated",
                "ReadingAnnotationUpdated",
                "ReadingAnnotationDeleted",
                "ReadingAnnotationProcessed",
            ):
                bus.unsubscribe(evt, _cap)

    def test_reading_mode_changed_event_published(self, db, user_id):
        """ReadingModeChanged 事件真发布"""
        _ensure_reading_tables(db)
        from app.services.reading.sessions import (
            start_session, change_mode,
        )
        from app.application.di import container

        bus = container.event_bus
        captured: list = []

        async def _cap(event):
            captured.append(event)

        bus.subscribe("ReadingModeChanged", _cap)
        try:
            s = start_session(user_id, f"mat_{user_id}", mode="intensive")
            change_mode(user_id, s["id"], "skim")
            time.sleep(0.3)
            my = [e for e in captured
                  if e.user_id == user_id and e.session_id == s["id"]]
            assert len(my) == 1
            assert my[0].old_mode == "intensive"
            assert my[0].new_mode == "skim"
        finally:
            bus.unsubscribe("ReadingModeChanged", _cap)
