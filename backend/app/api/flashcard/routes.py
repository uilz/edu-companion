"""
FlashCard REST API

依据: docs/modules/flashcard/overview.md + ADR 0002
路由前缀: /api/flashcards

所有路由经过现有认证网关 (current_user_id 依赖)

路由顺序原则 (重要):
Starlette 按注册顺序匹配路径, 通配符 `/{card_id}` 会贪婪匹配
任何与具体路径段同名 (如 /due, /stats) 的请求, 必须先于 `/{card_id}` 注册
本文件按以下顺序组织, 防止 catch-all 拦截:
  1. 静态路径 (无 path param): /, /list/due, /due, /session/start, /stats, /stats/summary
  2. 跨段静态路径: /import-from-errorbook/{error_id}, /import-from-text, /import-from-text/confirm
  3. 通配符路径: /{card_id}, /{card_id}/review, /{card_id}/override, /{card_id}/suspend, /{card_id}/resume,
                 /{card_id}/reset, /{card_id}/archive, /{card_id}/preview
"""

from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from app.api.flashcard.schemas import (
    FlashCardCreate,
    FlashCardUpdate,
    ReviewSubmitRequest,
    ReviewResultResponse,
    FlashCardResponse,
    DueCardsResponse,
    ImportFromTextRequest,
    ImportFromTextResponse,
    ImportFromErrorBookResponse,
    StatsResponse,
    SelfAssessment,
)
from app.api.flashcard.service import (
    FlashCardService,
    get_flashcard_service,
)
from app.domain.auth.dependencies import current_user_id

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/flashcards", tags=["FlashCard 间隔重复记忆卡"])


def _get_service(user_id: str = Depends(current_user_id)) -> FlashCardService:
    """获取 service 并注入 event bus"""
    try:
        from app.application.di import container
        return get_flashcard_service(event_bus=container.event_bus)
    except Exception:
        return get_flashcard_service(event_bus=None)


def _to_response(card: dict | None) -> FlashCardResponse:
    if not card:
        raise HTTPException(404, "卡片不存在")
    return FlashCardResponse.model_validate(card)


# ════════════════════════════════════════════════════════════════════
# § A. 静态路径 (无 path param)
#    这些必须在 `/{card_id}` 之前注册, 否则会被通配符拦截
# ════════════════════════════════════════════════════════════════════

# ── A1. GET /api/flashcards/ — 列出卡片 (支持筛选) ──


@router.get(
    "/",
    summary="列出卡片 (支持筛选)",
)
async def list_cards(
    user_id: str = Depends(current_user_id),
    status: Optional[str] = None,
    type: Optional[int] = None,
    source: Optional[str] = None,
    tag: Optional[str] = None,
    node_id: Optional[str] = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    if not user_id:
        raise HTTPException(401, "请先登录")
    svc = _get_service(user_id)
    return svc.list_cards(
        user_id,
        status=status,
        type_=type,
        source=source,
        tag=tag,
        node_id=node_id,
        limit=limit,
        offset=offset,
    )


# ── A2. GET /api/flashcards/list/due — 查询到期卡片 (canonical) ──


@router.get(
    "/list/due",
    response_model=DueCardsResponse,
    summary="查询到期卡片 (FSRS 调度结果)",
)
async def get_due_cards(
    user_id: str = Depends(current_user_id),
    limit: int = Query(20, ge=1, le=200),
    node_id: Optional[str] = None,
):
    if not user_id:
        raise HTTPException(401, "请先登录")
    svc = _get_service(user_id)
    data = svc.get_due_cards(user_id, limit=limit, node_id=node_id)
    return DueCardsResponse.model_validate(data)


# ── A3. GET /api/flashcards/due — 查询到期卡片 (兼容路径) ──


# 兼容旧路径: GET /api/flashcards/due
@router.get(
    "/due",
    response_model=DueCardsResponse,
    summary="查询到期卡片 (兼容路径)",
    include_in_schema=False,
)
async def get_due_cards_compat(
    user_id: str = Depends(current_user_id),
    limit: int = Query(20, ge=1, le=200),
    node_id: Optional[str] = None,
):
    return await get_due_cards(user_id=user_id, limit=limit, node_id=node_id)


# ── A4. GET /api/flashcards/stats/summary — 统计面板 ──


@router.get(
    "/stats/summary",
    response_model=StatsResponse,
    summary="统计面板数据",
)
async def get_stats(
    user_id: str = Depends(current_user_id),
):
    if not user_id:
        raise HTTPException(401, "请先登录")
    svc = _get_service(user_id)
    return StatsResponse.model_validate(svc.get_stats(user_id))


# ── A5. GET /api/flashcards/stats — 统计 (兼容路径) ──


# 兼容旧路径
@router.get(
    "/stats",
    response_model=StatsResponse,
    summary="统计面板 (兼容路径)",
    include_in_schema=False,
)
async def get_stats_compat(
    user_id: str = Depends(current_user_id),
):
    return await get_stats(user_id=user_id)


# ── A6. POST /api/flashcards/session/start — 开始复习会话 ──


@router.post(
    "/session/start",
    summary="开始复习会话",
)
async def start_review_session(
    user_id: str = Depends(current_user_id),
    source_module: str = "manual",
    limit: int = Query(20, ge=1, le=200),
):
    if not user_id:
        raise HTTPException(401, "请先登录")
    svc = _get_service(user_id)
    return svc.start_session(user_id, source_module=source_module, limit=limit)


# ════════════════════════════════════════════════════════════════════
# § B. 跨段静态路径 (有 2+ 段, 与 /{card_id} 不冲突, 但也提前注册)
# ════════════════════════════════════════════════════════════════════

# ── B1. POST /api/flashcards/ — 创建 FlashCard ──


@router.post(
    "/",
    response_model=FlashCardResponse,
    summary="创建 FlashCard",
)
async def create_card(
    body: FlashCardCreate,
    user_id: str = Depends(current_user_id),
):
    if not user_id:
        raise HTTPException(401, "请先登录")
    if not body.front_text.strip():
        raise HTTPException(400, "front_text 不能为空")
    if not body.linked_node_ids:
        raise HTTPException(400, "至少关联一个 CognitiveNode (linked_node_ids)")
    svc = _get_service(user_id)
    try:
        card = svc.create_card(user_id, body.model_dump())
    except ValueError as e:
        raise HTTPException(400, str(e))
    return _to_response(card)


# ── B2. GET /api/flashcards/import-from-errorbook/{error_id} — 错题本导入预览 ──


@router.get(
    "/import-from-errorbook/{error_id}",
    response_model=ImportFromErrorBookResponse,
    summary="从错题本导入预览",
)
async def import_from_errorbook(
    error_id: str,
    user_id: str = Depends(current_user_id),
):
    if not user_id:
        raise HTTPException(401, "请先登录")
    svc = _get_service(user_id)
    try:
        data = svc.import_from_errorbook(user_id, error_id)
    except ValueError as e:
        raise HTTPException(404, str(e))
    return ImportFromErrorBookResponse.model_validate(data)


# ── B3. POST /api/flashcards/import-from-errorbook/{error_id}/confirm — 确认导入 ──


@router.post(
    "/import-from-errorbook/{error_id}/confirm",
    summary="确认从错题本导入",
)
async def confirm_import_from_errorbook(
    error_id: str,
    user_id: str = Depends(current_user_id),
    extra: dict = {},
):
    if not user_id:
        raise HTTPException(401, "请先登录")
    svc = _get_service(user_id)
    try:
        result = svc.confirm_import_from_errorbook(user_id, error_id, extra)
    except ValueError as e:
        raise HTTPException(404, str(e))
    if not result.get("created"):
        raise HTTPException(409, result.get("message", "已存在对应 FlashCard"))
    return result  # 返回 {"created": True, "card": {...}} 完整结构


# ── B4. POST /api/flashcards/import-from-text — 文本导入预览 ──


@router.post(
    "/import-from-text",
    response_model=ImportFromTextResponse,
    summary="从对话/阅读文本导入预览",
)
async def import_from_text(
    body: ImportFromTextRequest,
    user_id: str = Depends(current_user_id),
):
    if not user_id:
        raise HTTPException(401, "请先登录")
    svc = _get_service(user_id)
    try:
        data = svc.import_from_text(user_id, body.model_dump())
    except ValueError as e:
        raise HTTPException(400, str(e))
    return ImportFromTextResponse.model_validate(data)


# ── B5. POST /api/flashcards/import-from-text/confirm — 确认文本导入 ──


@router.post(
    "/import-from-text/confirm",
    summary="确认文本导入 (批量创建)",
)
async def confirm_import_from_text(
    body: dict,
    user_id: str = Depends(current_user_id),
):
    if not user_id:
        raise HTTPException(401, "请先登录")
    items = body.get("items", [])
    if not items:
        raise HTTPException(400, "items 不能为空")
    default_payload = {
        "type": body.get("type", 1),
        "tags": body.get("tags", []),
        "default_linked_node_ids": body.get("default_linked_node_ids", []),
        "language": body.get("language", ""),
    }
    svc = _get_service(user_id)
    cards = svc.confirm_import_from_text(user_id, items, default_payload)
    return {"imported": len(cards), "cards": cards}


# ── B6. POST /api/flashcards/session/{session_id}/end — 结束复习会话 ──


@router.post(
    "/session/{session_id}/end",
    summary="结束复习会话",
)
async def end_review_session(
    session_id: str,
    body: dict = {},
    user_id: str = Depends(current_user_id),
):
    if not user_id:
        raise HTTPException(401, "请先登录")
    svc = _get_service(user_id)
    return svc.end_session(
        user_id=user_id,
        session_id=session_id,
        difficult_count=int(body.get("difficult_count", 0)),
        good_count=int(body.get("good_count", 0)),
        easy_count=int(body.get("easy_count", 0)),
        duration_seconds=int(body.get("duration_seconds", 0)),
    )


# ════════════════════════════════════════════════════════════════════
# § C. 通配符路径 (含 {card_id})
#    必须在所有静态路径之后注册, 否则会拦截同名的具体路径
# ════════════════════════════════════════════════════════════════════

# ── C1. GET /api/flashcards/{card_id} — 查询卡片详情 ──


@router.get(
    "/{card_id}",
    response_model=FlashCardResponse,
    summary="查询卡片详情",
)
async def get_card(
    card_id: str,
    user_id: str = Depends(current_user_id),
):
    if not user_id:
        raise HTTPException(401, "请先登录")
    svc = _get_service(user_id)
    card = svc.get_card(user_id, card_id)
    if not card:
        raise HTTPException(404, "卡片不存在或已删除")
    return _to_response(card)


# ── C2. PATCH /api/flashcards/{card_id} — 更新 ──


@router.patch(
    "/{card_id}",
    response_model=FlashCardResponse,
    summary="更新卡片 (字段级粒度版本控制)",
)
async def update_card(
    card_id: str,
    body: FlashCardUpdate,
    user_id: str = Depends(current_user_id),
):
    if not user_id:
        raise HTTPException(401, "请先登录")
    svc = _get_service(user_id)
    payload = body.model_dump(exclude_none=True)
    reset = payload.pop("reset_scheduling", False)
    card = svc.update_card(user_id, card_id, payload, reset_scheduling=reset)
    if not card:
        raise HTTPException(404, "卡片不存在或已删除")
    return _to_response(card)


# ── C3. DELETE /api/flashcards/{card_id} — 删除 (软删除) ──


@router.delete(
    "/{card_id}",
    summary="软删除卡片",
)
async def delete_card(
    card_id: str,
    user_id: str = Depends(current_user_id),
):
    if not user_id:
        raise HTTPException(401, "请先登录")
    svc = _get_service(user_id)
    ok = svc.soft_delete(user_id, card_id)
    if not ok:
        raise HTTPException(404, "卡片不存在或已删除")
    return {"deleted": True, "card_id": card_id}


# ── C4. POST /api/flashcards/{card_id}/review — 提交复习自评 ──


@router.post(
    "/{card_id}/review",
    response_model=ReviewResultResponse,
    summary="提交复习自评 (FSRS 调度 + Belief 回写)",
)
async def submit_review(
    card_id: str,
    body: ReviewSubmitRequest,
    user_id: str = Depends(current_user_id),
):
    if not user_id:
        raise HTTPException(401, "请先登录")
    svc = _get_service(user_id)
    try:
        result = await svc.submit_review(
            user_id=user_id,
            card_id=card_id,
            self_assessment=body.self_assessment,
            session_id=body.session_id,
        )
    except ValueError as e:
        raise HTTPException(400, str(e))
    return ReviewResultResponse.model_validate(result)


# ── C5. PATCH /api/flashcards/{card_id}/override — 手动覆盖 FSRS 参数 ──


@router.patch(
    "/{card_id}/override",
    response_model=FlashCardResponse,
    summary="手动覆盖 FSRS 参数 (满足用户可手动覆盖任意参数约束)",
)
async def override_card(
    card_id: str,
    body: dict,
    user_id: str = Depends(current_user_id),
):
    if not user_id:
        raise HTTPException(401, "请先登录")
    svc = _get_service(user_id)
    card = svc.override_scheduling(
        user_id,
        card_id,
        stability=body.get("stability"),
        difficulty=body.get("difficulty"),
        target_retention=body.get("target_retention"),
        next_review_at=body.get("next_review_at"),
    )
    if not card:
        raise HTTPException(404, "卡片不存在或已删除")
    return _to_response(card)


# ── C6. POST /api/flashcards/{card_id}/suspend — 暂停卡片 ──


@router.post(
    "/{card_id}/suspend",
    response_model=FlashCardResponse,
    summary="暂停卡片",
)
async def suspend_card(
    card_id: str,
    user_id: str = Depends(current_user_id),
):
    if not user_id:
        raise HTTPException(401, "请先登录")
    svc = _get_service(user_id)
    card = svc.suspend(user_id, card_id)
    if not card:
        raise HTTPException(404, "卡片不存在或已删除")
    return _to_response(card)


# ── C7. POST /api/flashcards/{card_id}/resume — 恢复卡片 ──


@router.post(
    "/{card_id}/resume",
    response_model=FlashCardResponse,
    summary="恢复卡片",
)
async def resume_card(
    card_id: str,
    user_id: str = Depends(current_user_id),
):
    if not user_id:
        raise HTTPException(401, "请先登录")
    svc = _get_service(user_id)
    card = svc.resume(user_id, card_id)
    if not card:
        raise HTTPException(404, "卡片不存在或已删除")
    return _to_response(card)


# ── C8. POST /api/flashcards/{card_id}/reset — 重置调度 ──


@router.post(
    "/{card_id}/reset",
    response_model=FlashCardResponse,
    summary="重置调度 (清空复习历史)",
)
async def reset_card(
    card_id: str,
    user_id: str = Depends(current_user_id),
):
    if not user_id:
        raise HTTPException(401, "请先登录")
    svc = _get_service(user_id)
    card = svc.reset_scheduling(user_id, card_id)
    if not card:
        raise HTTPException(404, "卡片不存在或已删除")
    return _to_response(card)


# ── C9. POST /api/flashcards/{card_id}/archive — 归档卡片 ──


@router.post(
    "/{card_id}/archive",
    response_model=FlashCardResponse,
    summary="归档卡片",
)
async def archive_card(
    card_id: str,
    user_id: str = Depends(current_user_id),
):
    if not user_id:
        raise HTTPException(401, "请先登录")
    svc = _get_service(user_id)
    card = svc.archive(user_id, card_id)
    if not card:
        raise HTTPException(404, "卡片不存在或已删除")
    return _to_response(card)


# ── C10. POST /api/flashcards/{card_id}/preview — FSRS 预览 (不修改状态) ──


@router.post(
    "/{card_id}/preview",
    summary="预览自评结果 (不修改状态)",
)
async def preview_review(
    card_id: str,
    body: dict,
    user_id: str = Depends(current_user_id),
):
    if not user_id:
        raise HTTPException(401, "请先登录")
    svc = _get_service(user_id)
    card = svc.get_card(user_id, card_id)
    if not card:
        raise HTTPException(404, "卡片不存在")
    from app.services.flashcard.fsrs_scheduler import FSRScheduler, FSRSState
    state = FSRSState(
        stability=card.get("stability") or 2.5,
        difficulty=card.get("difficulty") or 5.0,
        forgetting_rate=card.get("forgetting_rate") or 0.0,
        last_review_at=card.get("last_review_at"),
        next_review_at=card.get("next_review_at"),
        review_count=card.get("review_count") or 0,
        lapse_count=card.get("lapse_count") or 0,
        target_retention=card.get("target_retention") or 0.85,
    )
    assessment = body.get("self_assessment", "good")
    if assessment not in ("difficult", "good", "easy"):
        raise HTTPException(400, "self_assessment 必须是 difficult/good/easy")
    preview = FSRScheduler.preview(state, assessment)  # type: ignore[arg-type]
    # 补充 stability/difficulty (before + after) 便于前端展示
    return {
        "stability": state.stability,
        "difficulty": state.difficulty,
        "stability_after": preview["stability_after"],
        "difficulty_after": preview["difficulty_after"],
        "interval_days": preview["interval_days"],
        "next_review_at": preview["next_review_at"],
    }
