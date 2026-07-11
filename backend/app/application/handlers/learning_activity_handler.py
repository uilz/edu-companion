"""LearningActivityEventHandler — 跨壳学习活动流记录器

订阅各模块核心学习事件，统一写入 learning_activities 表，
为秘书仪表盘、知识树详情、学习 timeline 等场景提供数据。

设计要点:
  1. 只读副作用：不发布新事件，不触发业务状态变更。
  2. 幂等性：通过 (source_event_id, source_event_type) 组合去重。
  3. 错误隔离：任何事件处理失败只记录日志，不影响原始事件链。
  4. 深链接：尽量生成可回跳的客户端路径，供前端直接跳转。
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from shared.events import (
    AnswerSubmitted,
    ErrorBookEntryResolved,
    ErrorBookEntryReviewed,
    FlashCardCreated,
    FlashCardReviewed,
    FlashCardSessionEnded,
    MaterialProgressUpdated,
    PlanItemCompleted,
    PlanItemStarted,
    ReadingAnnotationCreated,
    ReadingMaterialCompleted,
    ReadingSessionEnded,
    SessionCompleted,
    TreeNodeCreated,
    TreeNodeLinkedToCognitiveNode,
)

logger = logging.getLogger(__name__)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _deep_link(module: str, ref_id: str, sub_id: str = "") -> str:
    """生成前端深链接。"""
    if module == "practice":
        return f"/practice/history/{ref_id}" if ref_id else "/practice"
    if module == "flashcard":
        if sub_id == "session":
            return "/flashcard/review"
        return f"/flashcard?card_id={ref_id}" if ref_id else "/flashcard"
    if module == "reading":
        return f"/reading/materials/{ref_id}" if ref_id else "/reading"
    if module == "knowledge_tree":
        return f"/knowledge-tree?tree_id={ref_id}" if ref_id else "/knowledge-tree"
    if module == "planning":
        return f"/planning?item_id={ref_id}" if ref_id else "/planning"
    if module == "error_book":
        return f"/practice/errors?entry_id={ref_id}" if ref_id else "/practice/errors"
    return ""


def _upsert_activity(record: dict[str, Any]) -> str | None:
    """写入或跳过 learning_activities 表，返回 activity id。"""
    from app.infrastructure.db.session import get_db_session
    from app.infrastructure.db.models.learning_activity import LearningActivityORM
    from sqlalchemy.exc import IntegrityError

    user_id = record.get("user_id")
    idempotency_key = record.get("idempotency_key")
    if not user_id:
        return None

    try:
        with get_db_session() as session:
            # 幂等：同一用户 + 同一业务键只记录一次
            if idempotency_key:
                existing = session.query(LearningActivityORM).filter_by(
                    user_id=user_id,
                    idempotency_key=idempotency_key,
                ).first()
                if existing:
                    return existing.id

            activity = LearningActivityORM(
                user_id=user_id,
                activity_type=record.get("activity_type", "unknown"),
                module=record.get("module", "unknown"),
                source_event_id=record.get("source_event_id") or None,
                source_event_type=record.get("source_event_type") or None,
                idempotency_key=idempotency_key,
                title=record.get("title", ""),
                description=record.get("description", ""),
                status=record.get("status", "completed"),
                timestamp=record.get("timestamp") or _now(),
                deep_link=record.get("deep_link", ""),
                meta=record.get("meta") or {},
            )
            session.add(activity)
            try:
                session.commit()
            except IntegrityError:
                # 并发唯一索引冲突时回滚并返回已存在记录
                session.rollback()
                existing = session.query(LearningActivityORM).filter_by(
                    user_id=user_id,
                    idempotency_key=idempotency_key,
                ).first()
                return existing.id if existing else None
            return activity.id
    except Exception:
        logger.exception("写入 learning_activities 失败: %s", record.get("source_event_type"))
        return None


# ────────────────────────────────────────────────────────────────────
# 事件映射辅助
# ────────────────────────────────────────────────────────────────────


def _record_answer_submitted(event: AnswerSubmitted) -> dict[str, Any]:
    correct_text = "正确" if event.is_correct else "错误"
    return {
        "user_id": event.user_id,
        "activity_type": "answer_submitted",
        "module": "practice",
        "source_event_id": event.event_id,
        "source_event_type": event.event_type,
        "idempotency_key": f"answer:{event.attempt_id}",
        "title": f"练习答题{correct_text}",
        "description": f"答了 1 题，耗时 {event.response_time_seconds:.1f} 秒，使用提示 {event.hints_used} 次。",
        "status": "completed",
        "timestamp": event.submitted_at or event.occurred_at or _now(),
        "deep_link": _deep_link("practice", event.session_id),
        "meta": {
            "attempt_id": event.attempt_id,
            "session_id": event.session_id,
            "question_id": event.question_id,
            "skill_id": event.skill_id,
            "is_correct": event.is_correct,
            "response_time_seconds": event.response_time_seconds,
            "hints_used": event.hints_used,
            "cognitive_node_ids": event.cognitive_node_ids,
        },
    }


def _record_session_completed(event: SessionCompleted) -> dict[str, Any]:
    session_type_label = {"practice": "练习", "exam": "考试", "review": "复习"}.get(
        event.session_type, event.session_type
    )
    return {
        "user_id": event.user_id,
        "activity_type": "session_completed",
        "module": "practice",
        "source_event_id": event.event_id,
        "source_event_type": event.event_type,
        "idempotency_key": f"session:{event.session_id}",
        "title": f"完成{session_type_label}会话",
        "description": (
            f"共 {event.total_questions} 题，正确 {event.correct_count} 题，"
            f"正确率 {event.accuracy:.0%}，时长 {event.duration_minutes:.0f} 分钟。"
        ),
        "status": "completed",
        "timestamp": event.occurred_at or _now(),
        "deep_link": _deep_link("practice", event.session_id),
        "meta": {
            "session_id": event.session_id,
            "session_type": event.session_type,
            "total_questions": event.total_questions,
            "correct_count": event.correct_count,
            "accuracy": event.accuracy,
            "duration_minutes": event.duration_minutes,
            "score": event.score,
            "passing_score": event.passing_score,
        },
    }


def _record_flashcard_reviewed(event: FlashCardReviewed) -> dict[str, Any]:
    assessment_label = {"difficult": "困难", "good": "良好", "easy": "简单"}.get(
        event.self_assessment, event.self_assessment
    )
    reviewed_at_key = event.reviewed_at.isoformat(timespec="seconds") if event.reviewed_at else ""
    return {
        "user_id": event.user_id,
        "activity_type": "card_reviewed",
        "module": "flashcard",
        "source_event_id": event.event_id,
        "source_event_type": event.event_type,
        "idempotency_key": f"fc_review:{event.card_id}:{event.session_id}:{reviewed_at_key}",
        "title": f"复习闪卡：{assessment_label}",
        "description": f"自评 {assessment_label}，下次复习间隔 {event.interval_after} 天。",
        "status": "completed",
        "timestamp": event.reviewed_at or event.occurred_at or _now(),
        "deep_link": _deep_link("flashcard", event.card_id),
        "meta": {
            "card_id": event.card_id,
            "session_id": event.session_id,
            "self_assessment": event.self_assessment,
            "interval_before": event.interval_before,
            "interval_after": event.interval_after,
            "stability_after": event.stability_after,
            "difficulty_after": event.difficulty_after,
            "linked_node_ids": event.linked_node_ids,
        },
    }


def _record_flashcard_created(event: FlashCardCreated) -> dict[str, Any]:
    source = event.cross_module_source or event.source or "manual"
    return {
        "user_id": event.user_id,
        "activity_type": "card_created",
        "module": "flashcard",
        "source_event_id": event.event_id,
        "source_event_type": event.event_type,
        "idempotency_key": f"fc_create:{event.card_id}",
        "title": "创建闪卡",
        "description": f"来源：{source}",
        "status": "completed",
        "timestamp": event.created_at or event.occurred_at or _now(),
        "deep_link": _deep_link("flashcard", event.card_id),
        "meta": {
            "card_id": event.card_id,
            "source": event.source,
            "cross_module_source": event.cross_module_source,
            "linked_node_ids": event.linked_node_ids,
        },
    }


def _record_flashcard_session_ended(event: FlashCardSessionEnded) -> dict[str, Any]:
    duration_min = event.duration_seconds / 60.0
    return {
        "user_id": event.user_id,
        "activity_type": "session_ended",
        "module": "flashcard",
        "source_event_id": event.event_id,
        "source_event_type": event.event_type,
        "idempotency_key": f"fc_session:{event.session_id}",
        "title": "完成闪卡复习会话",
        "description": (
            f"复习 {event.total_cards} 张，困难 {event.difficult_count} / "
            f"良好 {event.good_count} / 简单 {event.easy_count}，"
            f"时长 {duration_min:.1f} 分钟。"
        ),
        "status": "completed",
        "timestamp": event.ended_at or event.occurred_at or _now(),
        "deep_link": _deep_link("flashcard", event.session_id, sub_id="session"),
        "meta": {
            "session_id": event.session_id,
            "total_cards": event.total_cards,
            "difficult_count": event.difficult_count,
            "good_count": event.good_count,
            "easy_count": event.easy_count,
            "duration_seconds": event.duration_seconds,
        },
    }


def _record_reading_session_ended(event: ReadingSessionEnded) -> dict[str, Any]:
    duration_min = event.duration_seconds / 60.0
    return {
        "user_id": event.user_id,
        "activity_type": "session_ended",
        "module": "reading",
        "source_event_id": event.event_id,
        "source_event_type": event.event_type,
        "idempotency_key": f"reading_session:{event.session_id}",
        "title": "完成阅读会话",
        "description": (
            f"时长 {duration_min:.1f} 分钟，标注 {event.annotations_count} 个，"
            f"笔记 {event.notes_count} 条，生成卡片 {event.cards_generated} 张。"
        ),
        "status": "completed",
        "timestamp": event.ended_at or event.occurred_at or _now(),
        "deep_link": _deep_link("reading", event.material_id),
        "meta": {
            "session_id": event.session_id,
            "material_id": event.material_id,
            "duration_seconds": event.duration_seconds,
            "annotations_count": event.annotations_count,
            "notes_count": event.notes_count,
            "cards_generated": event.cards_generated,
            "linked_node_ids": event.linked_node_ids,
        },
    }


def _record_reading_annotation_created(event: ReadingAnnotationCreated) -> dict[str, Any]:
    intent_label = {
        "important_concept": "重要概念",
        "data_fact": "数据事实",
        "quotable": "可引用",
        "doubt": "疑问",
        "conflict": "冲突",
    }.get(event.intent, event.intent)
    return {
        "user_id": event.user_id,
        "activity_type": "annotation_created",
        "module": "reading",
        "source_event_id": event.event_id,
        "source_event_type": event.event_type,
        "idempotency_key": f"reading_annotation:{event.annotation_id}",
        "title": "阅读标注",
        "description": f"意图：{intent_label}",
        "status": "completed",
        "timestamp": event.created_at or event.occurred_at or _now(),
        "deep_link": _deep_link("reading", event.material_id),
        "meta": {
            "annotation_id": event.annotation_id,
            "material_id": event.material_id,
            "chunk_id": event.chunk_id,
            "color": event.color,
            "intent": event.intent,
            "linked_node_id": event.linked_node_id,
        },
    }


def _record_reading_material_completed(event: ReadingMaterialCompleted) -> dict[str, Any]:
    return {
        "user_id": event.user_id,
        "activity_type": "material_completed",
        "module": "reading",
        "source_event_id": event.event_id,
        "source_event_type": event.event_type,
        "idempotency_key": f"reading_completed:{event.material_id}:{event.session_id}",
        "title": "阅读材料完成",
        "description": f"进度 {event.progress_pct:.0%}，时长 {event.duration_seconds / 60:.1f} 分钟。",
        "status": "completed",
        "timestamp": event.completed_at or event.occurred_at or _now(),
        "deep_link": _deep_link("reading", event.material_id),
        "meta": {
            "material_id": event.material_id,
            "session_id": event.session_id,
            "progress_pct": event.progress_pct,
            "duration_seconds": event.duration_seconds,
        },
    }


def _record_reading_progress_updated(event: MaterialProgressUpdated) -> dict[str, Any]:
    # 进度更新过于频繁，只记录关键阈值（>=95% 视为完成）
    if event.progress_pct < 0.95:
        return {}
    return {
        "user_id": event.user_id,
        "activity_type": "material_progress_milestone",
        "module": "reading",
        "source_event_id": event.event_id,
        "source_event_type": event.event_type,
        "idempotency_key": f"reading_progress:{event.material_id}:{event.session_id}",
        "title": "阅读进度达成",
        "description": f"材料进度达到 {event.progress_pct:.0%}",
        "status": "completed",
        "timestamp": event.updated_at or event.occurred_at or _now(),
        "deep_link": _deep_link("reading", event.material_id),
        "meta": {
            "material_id": event.material_id,
            "session_id": event.session_id,
            "progress_pct": event.progress_pct,
            "last_chunk_id": event.last_chunk_id,
            "last_offset": event.last_offset,
        },
    }


def _record_tree_node_created(event: TreeNodeCreated) -> dict[str, Any]:
    return {
        "user_id": event.user_id,
        "activity_type": "node_created",
        "module": "knowledge_tree",
        "source_event_id": event.event_id,
        "source_event_type": event.event_type,
        "idempotency_key": f"tree_node:{event.node_id}",
        "title": f"创建知识树节点：{event.label}",
        "description": f"节点类型：{event.node_type}",
        "status": "completed",
        "timestamp": event.created_at or event.occurred_at or _now(),
        "deep_link": _deep_link("knowledge_tree", event.tree_id),
        "meta": {
            "tree_id": event.tree_id,
            "node_id": event.node_id,
            "parent_id": event.parent_id,
            "label": event.label,
            "node_type": event.node_type,
            "linked_cognitive_node_ids": event.linked_cognitive_node_ids,
        },
    }


def _record_tree_node_linked(event: TreeNodeLinkedToCognitiveNode) -> dict[str, Any]:
    return {
        "user_id": event.user_id,
        "activity_type": "node_linked",
        "module": "knowledge_tree",
        "source_event_id": event.event_id,
        "source_event_type": event.event_type,
        "idempotency_key": f"tree_link:{event.tree_node_id}:{event.cognitive_node_id}",
        "title": "知识树节点关联认知节点",
        "description": f"关联角色：{event.link_role}",
        "status": "completed",
        "timestamp": event.linked_at or event.occurred_at or _now(),
        "deep_link": _deep_link("knowledge_tree", event.tree_id),
        "meta": {
            "tree_id": event.tree_id,
            "tree_node_id": event.tree_node_id,
            "cognitive_node_id": event.cognitive_node_id,
            "link_role": event.link_role,
        },
    }


def _record_plan_item_completed(event: PlanItemCompleted) -> dict[str, Any]:
    return {
        "user_id": event.user_id,
        "activity_type": "item_completed",
        "module": "planning",
        "source_event_id": event.event_id,
        "source_event_type": event.event_type,
        "idempotency_key": f"plan_completed:{event.plan_item_id}",
        "title": "完成计划项",
        "description": f"实际耗时 {event.actual_minutes} 分钟。",
        "status": "completed",
        "timestamp": event.completed_at or event.occurred_at or _now(),
        "deep_link": _deep_link("planning", event.plan_item_id),
        "meta": {
            "plan_item_id": event.plan_item_id,
            "source_module": event.source_module,
            "target_type": event.target_type,
            "target_ref_id": event.target_ref_id,
            "actual_minutes": event.actual_minutes,
            "linked_node_ids": event.linked_node_ids,
        },
    }


def _record_plan_item_started(event: PlanItemStarted) -> dict[str, Any]:
    return {
        "user_id": event.user_id,
        "activity_type": "item_started",
        "module": "planning",
        "source_event_id": event.event_id,
        "source_event_type": event.event_type,
        "idempotency_key": f"plan_started:{event.plan_item_id}",
        "title": "开始计划项",
        "description": f"来源模块：{event.source_module}",
        "status": "completed",
        "timestamp": event.started_at or event.occurred_at or _now(),
        "deep_link": _deep_link("planning", event.plan_item_id),
        "meta": {
            "plan_item_id": event.plan_item_id,
            "source_module": event.source_module,
        },
    }


def _record_error_book_reviewed(event: ErrorBookEntryReviewed) -> dict[str, Any]:
    assessment_label = {"difficult": "困难", "good": "良好", "easy": "简单"}.get(
        event.self_assessment, event.self_assessment
    )
    return {
        "user_id": event.user_id,
        "activity_type": "entry_reviewed",
        "module": "error_book",
        "source_event_id": event.event_id,
        "source_event_type": event.event_type,
        "idempotency_key": f"error_review:{event.error_entry_id}:{event.review_count}",
        "title": "复习错题",
        "description": f"自评 {assessment_label}，复习第 {event.review_count} 次。",
        "status": "completed",
        "timestamp": event.reviewed_at or event.occurred_at or _now(),
        "deep_link": _deep_link("error_book", event.error_entry_id),
        "meta": {
            "error_entry_id": event.error_entry_id,
            "self_assessment": event.self_assessment,
            "review_count": event.review_count,
            "is_resolved": event.is_resolved,
        },
    }


def _record_error_book_resolved(event: ErrorBookEntryResolved) -> dict[str, Any]:
    method_label = {
        "manual": "手动标记",
        "auto_after_review": "复习后自动",
        "import": "外部导入",
    }.get(event.resolution_method, event.resolution_method)
    return {
        "user_id": event.user_id,
        "activity_type": "entry_resolved",
        "module": "error_book",
        "source_event_id": event.event_id,
        "source_event_type": event.event_type,
        "idempotency_key": f"error_resolved:{event.error_entry_id}",
        "title": "错题已掌握",
        "description": f"掌握方式：{method_label}",
        "status": "completed",
        "timestamp": event.resolved_at or event.occurred_at or _now(),
        "deep_link": _deep_link("error_book", event.error_entry_id),
        "meta": {
            "error_entry_id": event.error_entry_id,
            "resolution_method": event.resolution_method,
        },
    }


# ────────────────────────────────────────────────────────────────────
# 事件处理器类
# ────────────────────────────────────────────────────────────────────


class LearningActivityEventHandler:
    """学习活动流事件处理器"""

    def __init__(self) -> None:
        self._bus: Any | None = None
        self._subscribed = False

    def subscribe(self, bus: Any) -> None:
        if self._subscribed:
            return
        self._bus = bus

        from app.infrastructure.event_bus import EventBus
        from app.infrastructure.persistent_event_bus import PersistentEventBus
        if not isinstance(bus, (EventBus, PersistentEventBus)):
            logger.warning("传入的对象不是 EventBus 实例（%s），跳过订阅", type(bus).__module__)
            return

        bus.subscribe("AnswerSubmitted", self._on_answer_submitted)
        bus.subscribe("SessionCompleted", self._on_session_completed)
        bus.subscribe("FlashCardReviewed", self._on_flashcard_reviewed)
        bus.subscribe("FlashCardCreated", self._on_flashcard_created)
        bus.subscribe("FlashCardSessionEnded", self._on_flashcard_session_ended)
        bus.subscribe("ReadingSessionEnded", self._on_reading_session_ended)
        bus.subscribe("ReadingAnnotationCreated", self._on_reading_annotation_created)
        bus.subscribe("ReadingMaterialCompleted", self._on_reading_material_completed)
        bus.subscribe("MaterialProgressUpdated", self._on_reading_progress_updated)
        bus.subscribe("TreeNodeCreated", self._on_tree_node_created)
        bus.subscribe("TreeNodeLinkedToCognitiveNode", self._on_tree_node_linked)
        bus.subscribe("PlanItemCompleted", self._on_plan_item_completed)
        bus.subscribe("PlanItemStarted", self._on_plan_item_started)
        bus.subscribe("ErrorBookEntryReviewed", self._on_error_book_reviewed)
        bus.subscribe("ErrorBookEntryResolved", self._on_error_book_resolved)

        self._subscribed = True
        logger.info("📚 LearningActivityEventHandler 已订阅 %d 个事件类型")

    def unsubscribe(self) -> None:
        if not self._bus or not self._subscribed:
            return
        self._bus.unsubscribe("AnswerSubmitted", self._on_answer_submitted)
        self._bus.unsubscribe("SessionCompleted", self._on_session_completed)
        self._bus.unsubscribe("FlashCardReviewed", self._on_flashcard_reviewed)
        self._bus.unsubscribe("FlashCardCreated", self._on_flashcard_created)
        self._bus.unsubscribe("FlashCardSessionEnded", self._on_flashcard_session_ended)
        self._bus.unsubscribe("ReadingSessionEnded", self._on_reading_session_ended)
        self._bus.unsubscribe("ReadingAnnotationCreated", self._on_reading_annotation_created)
        self._bus.unsubscribe("ReadingMaterialCompleted", self._on_reading_material_completed)
        self._bus.unsubscribe("MaterialProgressUpdated", self._on_reading_progress_updated)
        self._bus.unsubscribe("TreeNodeCreated", self._on_tree_node_created)
        self._bus.unsubscribe("TreeNodeLinkedToCognitiveNode", self._on_tree_node_linked)
        self._bus.unsubscribe("PlanItemCompleted", self._on_plan_item_completed)
        self._bus.unsubscribe("PlanItemStarted", self._on_plan_item_started)
        self._bus.unsubscribe("ErrorBookEntryReviewed", self._on_error_book_reviewed)
        self._bus.unsubscribe("ErrorBookEntryResolved", self._on_error_book_resolved)
        self._subscribed = False
        logger.info("📚 LearningActivityEventHandler 已取消订阅")

    # ── 事件处理入口 ──

    async def _on_answer_submitted(self, event: Any) -> None:
        if not isinstance(event, AnswerSubmitted):
            return
        _upsert_activity(_record_answer_submitted(event))

    async def _on_session_completed(self, event: Any) -> None:
        if not isinstance(event, SessionCompleted):
            return
        _upsert_activity(_record_session_completed(event))

    async def _on_flashcard_reviewed(self, event: Any) -> None:
        if not isinstance(event, FlashCardReviewed):
            return
        _upsert_activity(_record_flashcard_reviewed(event))

    async def _on_flashcard_created(self, event: Any) -> None:
        if not isinstance(event, FlashCardCreated):
            return
        _upsert_activity(_record_flashcard_created(event))

    async def _on_flashcard_session_ended(self, event: Any) -> None:
        if not isinstance(event, FlashCardSessionEnded):
            return
        _upsert_activity(_record_flashcard_session_ended(event))

    async def _on_reading_session_ended(self, event: Any) -> None:
        if not isinstance(event, ReadingSessionEnded):
            return
        _upsert_activity(_record_reading_session_ended(event))

    async def _on_reading_annotation_created(self, event: Any) -> None:
        if not isinstance(event, ReadingAnnotationCreated):
            return
        _upsert_activity(_record_reading_annotation_created(event))

    async def _on_reading_material_completed(self, event: Any) -> None:
        if not isinstance(event, ReadingMaterialCompleted):
            return
        _upsert_activity(_record_reading_material_completed(event))

    async def _on_reading_progress_updated(self, event: Any) -> None:
        if not isinstance(event, MaterialProgressUpdated):
            return
        record = _record_reading_progress_updated(event)
        if record:
            _upsert_activity(record)

    async def _on_tree_node_created(self, event: Any) -> None:
        if not isinstance(event, TreeNodeCreated):
            return
        _upsert_activity(_record_tree_node_created(event))

    async def _on_tree_node_linked(self, event: Any) -> None:
        if not isinstance(event, TreeNodeLinkedToCognitiveNode):
            return
        _upsert_activity(_record_tree_node_linked(event))

    async def _on_plan_item_completed(self, event: Any) -> None:
        if not isinstance(event, PlanItemCompleted):
            return
        _upsert_activity(_record_plan_item_completed(event))

    async def _on_plan_item_started(self, event: Any) -> None:
        if not isinstance(event, PlanItemStarted):
            return
        _upsert_activity(_record_plan_item_started(event))

    async def _on_error_book_reviewed(self, event: Any) -> None:
        if not isinstance(event, ErrorBookEntryReviewed):
            return
        _upsert_activity(_record_error_book_reviewed(event))

    async def _on_error_book_resolved(self, event: Any) -> None:
        if not isinstance(event, ErrorBookEntryResolved):
            return
        _upsert_activity(_record_error_book_resolved(event))


# 全局单例
learning_activity_event_handler = LearningActivityEventHandler()
