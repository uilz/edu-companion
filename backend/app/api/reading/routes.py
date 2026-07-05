"""Reading REST API

依据 docs/modules/reading/overview.md + ADR 0003
路由前缀: /api/reading

设计原则：
  - 不重建 file-management / FlashCard / Planning
  - 笔记 = FlashCard 反思型（不建 reading_notes 表）
  - 回顾提醒 = PlanItem（不建独立提醒表）
  - 标注 = 独立表 reading_annotations（5 色多意图）

所有路由经过现有认证网关 (current_user_id 依赖)
"""
from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from app.api.reading.schemas import (
    AnnotationCreate,
    AnnotationUpdate,
    AnnotationResponse,
    AnnotationProcessRequest,
    SessionStartRequest,
    SessionEndRequest,
    SessionModeChangeRequest,
    SessionActivityRequest,
    SessionResponse,
    NoteCreateRequest,
    ReviewReminderRequest,
    ReviewReminderResponse,
    PrefsUpdateRequest,
    PrefsResponse,
    CompareCreateRequest,
    ComparePayloadResponse,
)
from app.domain.auth.dependencies import current_user_id
# 注意：不能用 `from app.services.reading import annotations` ，因为 __future__ annotations
# 会让 `annotations` 名指向 __future__._Feature 对象，破坏模块解析。
import app.services.reading.annotations as ann_svc  # noqa: E402
import app.services.reading.sessions as sess_svc  # noqa: E402
import app.services.reading.prefs as prefs_svc  # noqa: E402
import app.services.reading.compare as cmp_svc  # noqa: E402
import app.services.reading.notes as notes_svc  # noqa: E402
import app.services.reading.review_reminder as reminder_svc  # noqa: E402
from app.services.reading.annotations import COLOR_FOLLOWUP  # noqa: E402

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/reading", tags=["Reading 阅读加工"])


# ── 辅助函数 ──


def _annotation_to_response(ann: dict) -> AnnotationResponse:
    followup = COLOR_FOLLOWUP.get(ann.get("color", ""), {}).copy()
    return AnnotationResponse(
        id=ann["id"],
        user_id=ann["user_id"],
        material_id=ann["material_id"],
        chunk_id=ann.get("chunk_id"),
        start_offset=ann.get("start_offset"),
        end_offset=ann.get("end_offset"),
        color=ann["color"],
        intent=ann["intent"],
        text=ann.get("text"),
        note=ann.get("note"),
        linked_node_id=ann.get("linked_node_id"),
        is_processed=ann.get("is_processed", False),
        followup=followup,
        created_at=ann["created_at"],
        updated_at=ann["updated_at"],
    )


def _session_to_response(s: dict) -> SessionResponse:
    return SessionResponse(
        id=s["id"],
        user_id=s["user_id"],
        material_id=s["material_id"],
        mode=s.get("mode", "intensive"),
        started_at=s["started_at"],
        ended_at=s.get("ended_at"),
        duration_seconds=s.get("duration_seconds"),
        chapters_visited=s.get("chapters_visited") or [],
        annotations_created=int(s.get("annotations_created") or 0),
        notes_created=int(s.get("notes_created") or 0),
        cards_generated=int(s.get("cards_generated") or 0),
        linked_node_ids=s.get("linked_node_ids") or [],
        state_snapshot=s.get("state_snapshot") or {},
        last_active_at=s.get("last_active_at"),
    )


# ── 1. 会话 (sessions) ──


@router.post(
    "/sessions",
    response_model=SessionResponse,
    summary="开始阅读会话",
)
async def start_session(
    body: SessionStartRequest,
    user_id: str = Depends(current_user_id),
):
    if not user_id:
        raise HTTPException(401, "请先登录")
    try:
        s = sess_svc.start_session(
            user_id=user_id,
            material_id=body.material_id,
            mode=body.mode,
        )
    except ValueError as e:
        raise HTTPException(400, str(e))
    return _session_to_response(s)


# 注意: 静态路径 /sessions/active 必须定义在参数化路径 /sessions/{session_id} 之前,
# 否则 FastAPI 路由匹配会先命中后者, 把 "active" 当成 session_id,
# 导致 /sessions/active 端点永远不可达 (中断恢复失效).
@router.get(
    "/sessions/active",
    response_model=SessionResponse,
    summary="查询用户对某材料的未结束会话（用于中断恢复）",
)
async def get_active_session(
    material_id: str = Query(..., min_length=1),
    user_id: str = Depends(current_user_id),
):
    if not user_id:
        raise HTTPException(401, "请先登录")
    s = sess_svc.get_active_session(user_id, material_id)
    if not s:
        raise HTTPException(404, "没有进行中的会话")
    return _session_to_response(s)


@router.get(
    "/sessions/{session_id}",
    response_model=SessionResponse,
    summary="查询阅读会话",
)
async def get_session(
    session_id: str,
    user_id: str = Depends(current_user_id),
):
    if not user_id:
        raise HTTPException(401, "请先登录")
    s = sess_svc.get_session(user_id, session_id)
    if not s:
        raise HTTPException(404, "会话不存在")
    return _session_to_response(s)


@router.get(
    "/sessions",
    summary="查询用户的阅读会话列表",
)
async def list_sessions(
    material_id: Optional[str] = None,
    limit: int = Query(50, ge=1, le=200),
    user_id: str = Depends(current_user_id),
):
    if not user_id:
        raise HTTPException(401, "请先登录")
    items = sess_svc.list_sessions(user_id, material_id=material_id, limit=limit)
    return {
        "items": [_session_to_response(s).model_dump(mode="json") for s in items],
        "total": len(items),
    }


@router.post(
    "/sessions/{session_id}/end",
    response_model=SessionResponse,
    summary="结束阅读会话 (触发 ReadingSessionEnded 事件)",
)
async def end_session(
    session_id: str,
    body: SessionEndRequest,
    user_id: str = Depends(current_user_id),
):
    if not user_id:
        raise HTTPException(401, "请先登录")
    s = sess_svc.end_session(
        user_id, session_id, duration_seconds=body.duration_seconds,
    )
    if not s:
        raise HTTPException(404, "会话不存在")
    return _session_to_response(s)


@router.post(
    "/sessions/{session_id}/mode",
    response_model=SessionResponse,
    summary="切换阅读模式 (触发 ReadingModeChanged 事件)",
)
async def change_session_mode(
    session_id: str,
    body: SessionModeChangeRequest,
    user_id: str = Depends(current_user_id),
):
    if not user_id:
        raise HTTPException(401, "请先登录")
    try:
        s = sess_svc.change_mode(user_id, session_id, body.mode)
    except ValueError as e:
        raise HTTPException(400, str(e))
    if not s:
        raise HTTPException(404, "会话不存在")
    return _session_to_response(s)


@router.post(
    "/sessions/{session_id}/activity",
    response_model=SessionResponse,
    summary="增量更新会话活动",
)
async def update_session_activity(
    session_id: str,
    body: SessionActivityRequest,
    user_id: str = Depends(current_user_id),
):
    if not user_id:
        raise HTTPException(401, "请先登录")
    s = sess_svc.update_session_activity(
        user_id, session_id,
        chapter_visited=body.chapter_visited,
        state_snapshot=body.state_snapshot,
        annotations_delta=body.annotations_delta,
        notes_delta=body.notes_delta,
        cards_delta=body.cards_delta,
        node_linked=body.node_linked,
    )
    if not s:
        raise HTTPException(404, "会话不存在")
    return _session_to_response(s)


# ── 2. 标注 (annotations) ──


@router.post(
    "/annotations",
    response_model=AnnotationResponse,
    summary="创建标注 (5 色多意图)",
)
async def create_annotation(
    body: AnnotationCreate,
    user_id: str = Depends(current_user_id),
):
    if not user_id:
        raise HTTPException(401, "请先登录")
    try:
        ann = ann_svc.create_annotation(
            user_id=user_id,
            material_id=body.material_id,
            color=body.color,
            intent=body.intent,
            chunk_id=body.chunk_id,
            start_offset=body.start_offset,
            end_offset=body.end_offset,
            text=body.text,
            note=body.note,
            linked_node_id=body.linked_node_id,
        )
    except ValueError as e:
        raise HTTPException(400, str(e))
    return _annotation_to_response(ann)


@router.get(
    "/annotations/{annotation_id}",
    response_model=AnnotationResponse,
    summary="查询标注",
)
async def get_annotation(
    annotation_id: str,
    user_id: str = Depends(current_user_id),
):
    if not user_id:
        raise HTTPException(401, "请先登录")
    ann = ann_svc.get_annotation(user_id, annotation_id)
    if not ann:
        raise HTTPException(404, "标注不存在")
    return _annotation_to_response(ann)


@router.get(
    "/materials/{material_id}/annotations",
    summary="查询某材料的所有标注（可按颜色分组）",
)
async def list_annotations(
    material_id: str,
    color: Optional[str] = None,
    chunk_id: Optional[str] = None,
    grouped: bool = Query(False, description="按颜色分组（侧栏使用）"),
    limit: int = Query(200, ge=1, le=500),
    user_id: str = Depends(current_user_id),
):
    if not user_id:
        raise HTTPException(401, "请先登录")
    if grouped:
        grouped_data = ann_svc.list_annotations_grouped_by_color(user_id, material_id)
        return {
            "material_id": material_id,
            "grouped": grouped_data,
            "total": sum(len(v) for v in grouped_data.values()),
        }
    items = ann_svc.list_annotations(
        user_id, material_id=material_id, color=color, chunk_id=chunk_id, limit=limit,
    )
    return {
        "items": [_annotation_to_response(a).model_dump(mode="json") for a in items],
        "total": len(items),
    }


@router.patch(
    "/annotations/{annotation_id}",
    response_model=AnnotationResponse,
    summary="更新标注",
)
async def update_annotation(
    annotation_id: str,
    body: AnnotationUpdate,
    user_id: str = Depends(current_user_id),
):
    if not user_id:
        raise HTTPException(401, "请先登录")
    ann = ann_svc.update_annotation(
        user_id, annotation_id,
        body.model_dump(exclude_none=True),
    )
    if not ann:
        raise HTTPException(404, "标注不存在")
    return _annotation_to_response(ann)


@router.delete(
    "/annotations/{annotation_id}",
    summary="删除标注",
)
async def delete_annotation(
    annotation_id: str,
    user_id: str = Depends(current_user_id),
):
    if not user_id:
        raise HTTPException(401, "请先登录")
    ok = ann_svc.delete_annotation(user_id, annotation_id)
    if not ok:
        raise HTTPException(404, "标注不存在")
    return {"deleted": True, "annotation_id": annotation_id}


@router.post(
    "/annotations/{annotation_id}/process",
    response_model=AnnotationResponse,
    summary="标记标注已处理 (触发 ReadingAnnotationProcessed 事件)",
)
async def process_annotation(
    annotation_id: str,
    body: AnnotationProcessRequest,
    user_id: str = Depends(current_user_id),
):
    if not user_id:
        raise HTTPException(401, "请先登录")
    from shared.events import CrossModuleTarget
    try:
        target = CrossModuleTarget(body.target_module)
    except ValueError:
        raise HTTPException(400, f"invalid target_module: {body.target_module}")
    ann = ann_svc.mark_annotation_processed(
        user_id, annotation_id, target, body.target_ref_id,
    )
    if not ann:
        raise HTTPException(404, "标注不存在")
    return _annotation_to_response(ann)


# ── 3. 笔记 (notes) — 复用 FlashCard 反思型 ──


@router.post(
    "/notes",
    summary="创建阅读笔记 (实际是创建 FlashCard 反思型 card_type=7)",
)
async def create_note(
    body: NoteCreateRequest,
    user_id: str = Depends(current_user_id),
):
    if not user_id:
        raise HTTPException(401, "请先登录")
    try:
        card = notes_svc.create_reading_note(
            user_id=user_id,
            material_id=body.material_id,
            front_text=body.front_text,
            back_text=body.back_text,
            back_context=body.back_context,
            linked_node_ids=body.linked_node_ids,
            chunk_id=body.chunk_id,
            chunk_id_range=body.chunk_id_range,
            tags=body.tags,
            language=body.language,
            session_id=body.session_id,
        )
    except ValueError as e:
        raise HTTPException(400, str(e))
    return card


@router.get(
    "/notes",
    summary="列出阅读笔记 (FlashCard source='reading_note')",
)
async def list_notes(
    material_id: Optional[str] = None,
    limit: int = Query(100, ge=1, le=500),
    user_id: str = Depends(current_user_id),
):
    if not user_id:
        raise HTTPException(401, "请先登录")
    cards = notes_svc.list_reading_notes(user_id, material_id=material_id, limit=limit)
    return {
        "items": cards,
        "total": len(cards),
        "source": "reading_note",
        "note": "笔记 = FlashCard 反思型, 自动获得 FSRS 调度",
    }


# ── 4. 回顾提醒 (review-reminder) — 复用 PlanItem ──


@router.post(
    "/review-reminder",
    response_model=ReviewReminderResponse,
    summary="创建阅读回顾提醒 (实际是创建 PlanItem source_module='reading')",
)
async def create_review_reminder(
    body: ReviewReminderRequest,
    user_id: str = Depends(current_user_id),
):
    if not user_id:
        raise HTTPException(401, "请先登录")
    try:
        result = reminder_svc.schedule_review_reminder(
            user_id=user_id,
            material_id=body.material_id,
            review_after_days=body.review_after_days,
            title=body.title,
            description=body.description,
            estimated_minutes=body.estimated_minutes,
        )
    except ValueError as e:
        raise HTTPException(400, str(e))
    except Exception as e:  # noqa: BLE001
        logger.exception("create_review_reminder failed: %s", e)
        raise HTTPException(500, f"创建回顾提醒失败: {e}")
    return ReviewReminderResponse(
        plan_item_id=result["plan_item_id"],
        material_id=result["material_id"],
        review_after_days=result["review_after_days"],
        scheduled_for=result["scheduled_for"],
        plan_item=result.get("plan_item", {}),
    )


@router.get(
    "/review-reminder",
    summary="查询待处理的阅读回顾提醒",
)
async def list_review_reminders(
    material_id: Optional[str] = None,
    user_id: str = Depends(current_user_id),
):
    if not user_id:
        raise HTTPException(401, "请先登录")
    items = reminder_svc.list_pending_reminders(user_id, material_id=material_id)
    return {"items": items, "total": len(items)}


@router.delete(
    "/review-reminder/{plan_item_id}",
    summary="取消已设置的回顾提醒",
)
async def cancel_review_reminder(
    plan_item_id: str,
    user_id: str = Depends(current_user_id),
):
    if not user_id:
        raise HTTPException(401, "请先登录")
    ok = reminder_svc.cancel_reminder(user_id, plan_item_id)
    if not ok:
        raise HTTPException(404, "提醒不存在")
    return {"deleted": True, "plan_item_id": plan_item_id}


# ── 5. 偏好 (prefs) ──


@router.get(
    "/prefs",
    response_model=PrefsResponse,
    summary="获取阅读偏好",
)
async def get_reading_prefs(user_id: str = Depends(current_user_id)):
    if not user_id:
        raise HTTPException(401, "请先登录")
    return PrefsResponse(**prefs_svc.get_prefs(user_id))


@router.patch(
    "/prefs",
    response_model=PrefsResponse,
    summary="更新阅读偏好",
)
async def update_reading_prefs(
    body: PrefsUpdateRequest,
    user_id: str = Depends(current_user_id),
):
    if not user_id:
        raise HTTPException(401, "请先登录")
    updated = prefs_svc.upsert_prefs(user_id, body.model_dump(exclude_none=True))
    return PrefsResponse(**updated)


# ── 6. 对比阅读 (compare) ──


@router.post(
    "/compare",
    summary="创建对比阅读分组",
)
async def create_comparison(
    body: CompareCreateRequest,
    user_id: str = Depends(current_user_id),
):
    if not user_id:
        raise HTTPException(401, "请先登录")
    if body.material_id_left == body.material_id_right:
        raise HTTPException(400, "左右两侧材料不能相同")
    return cmp_svc.create_comparison(
        user_id=user_id,
        material_id_left=body.material_id_left,
        material_id_right=body.material_id_right,
        sync_scroll=body.sync_scroll,
    )


@router.get(
    "/compare",
    response_model=ComparePayloadResponse,
    summary="获取对比阅读分屏数据",
)
async def get_compare_payload(
    material_id_left: str = Query(..., min_length=1),
    material_id_right: str = Query(..., min_length=1),
    sync_scroll: Optional[bool] = None,
    user_id: str = Depends(current_user_id),
):
    if not user_id:
        raise HTTPException(401, "请先登录")
    if material_id_left == material_id_right:
        raise HTTPException(400, "左右两侧材料不能相同")
    payload = cmp_svc.build_compare_payload(
        user_id, material_id_left, material_id_right, sync_scroll=sync_scroll,
    )
    return ComparePayloadResponse(**payload)


@router.get(
    "/compare/list",
    summary="查询对比阅读分组列表",
)
async def list_comparisons(
    limit: int = Query(50, ge=1, le=200),
    user_id: str = Depends(current_user_id),
):
    if not user_id:
        raise HTTPException(401, "请先登录")
    items = cmp_svc.list_comparisons(user_id, limit=limit)
    return {"items": items, "total": len(items)}


# ── 7. 元数据 (color followup map) ──


@router.get(
    "/meta/colors",
    summary="获取 5 色标注 → 后续动作的映射（前后端共享元数据）",
)
async def get_color_followup_map(user_id: str = Depends(current_user_id)):
    if not user_id:
        raise HTTPException(401, "请先登录")
    return {
        "color_intent_map": ann_svc.COLOR_INTENT_MAP,
        "color_followup": ann_svc.COLOR_FOLLOWUP,
    }
