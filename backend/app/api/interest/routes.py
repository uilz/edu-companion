"""
InterestExplorer REST API

依据: docs/modules/interest-explorer/overview.md + data-model.md + events.md + ADR 0007
路由前缀: /api/interest

设计原则:
- 严格使用 CrossModuleTarget 枚举
- 链接级别去重
- 3 层标签
- 本地权重（不发送到服务端）
- 不调用 LLM
- 推送复用秘书 Proposal 机制
"""

from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from app.api.interest.schemas import (
    InterestTagCreate,
    InterestTagUpdate,
    InterestTagResponse,
    InterestPushPrefsUpdate,
    InterestPushPrefsResponse,
    InterestSourceCreate,
    InterestSourceResponse,
    InterestSourceEnableUpdate,
    InterestOPMLImportRequest,
    InterestOPMLImportResponse,
    InterestPushResponse,
    InterestPushFeedbackRequest,
    InterestPushImportRequest,
    InterestTodayPushResponse,
    InterestPushHistoryResponse,
    InterestWeightAdjustmentResponse,
    InterestWeightResetResponse,
    InterestTagFromKnowledgeRequest,
    InterestTagFromKnowledgeResponse,
)
from app.api.interest import service as interest_service
from app.domain.auth.dependencies import current_user_id
from shared.events import CrossModuleTarget

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/interest", tags=["InterestExplorer 学术信息发现"])


# ═══════════════════════════════════════════
# 1. 兴趣标签管理
# ═══════════════════════════════════════════


@router.get(
    "/tags",
    summary="列出用户所有兴趣标签（含 dislike_score + 树形结构）",
)
async def list_tags(
    user_id: str = Depends(current_user_id),
):
    if not user_id:
        raise HTTPException(401, "请先登录")
    tree = interest_service.list_tags_tree(user_id)
    # 补充 dislike_score
    weight_map = {
        w["tag_id"]: w.get("dislike_score", 0.0)
        for w in interest_service.list_weight_adjustments(user_id)
    }

    def _inject(node: dict) -> dict:
        node = dict(node)
        node["dislike_score"] = weight_map.get(node["id"], 0.0)
        node["children"] = [_inject(c) for c in node.get("children", [])]
        return node

    return {"items": [_inject(t) for t in tree], "total": len(tree)}


@router.post(
    "/tags",
    response_model=InterestTagResponse,
    summary="创建兴趣标签",
)
async def create_tag(
    body: InterestTagCreate,
    user_id: str = Depends(current_user_id),
):
    if not user_id:
        raise HTTPException(401, "请先登录")
    if body.level not in (0, 1, 2):
        raise HTTPException(400, "level 必须是 0/1/2 (3 层)")
    if body.weight not in (1, 2):
        raise HTTPException(400, "weight 必须是 1 (主要) / 2 (次要)")

    tag = await interest_service.create_tag(
        user_id, body.model_dump()
    )
    if not tag:
        raise HTTPException(409, "标签已存在或创建失败")
    return tag


@router.patch(
    "/tags/{tag_id}",
    response_model=InterestTagResponse,
    summary="更新兴趣标签（重命名/调整权重/调整层级）",
)
async def update_tag(
    tag_id: str,
    body: InterestTagUpdate,
    user_id: str = Depends(current_user_id),
):
    if not user_id:
        raise HTTPException(401, "请先登录")
    payload = body.model_dump(exclude_none=True)
    if not payload:
        raise HTTPException(400, "至少提供一个更新字段")
    tag = await interest_service.update_tag(user_id, tag_id, payload)
    if not tag:
        raise HTTPException(404, "标签不存在")
    return tag


@router.delete(
    "/tags/{tag_id}",
    summary="删除兴趣标签",
)
async def delete_tag(
    tag_id: str,
    user_id: str = Depends(current_user_id),
):
    if not user_id:
        raise HTTPException(401, "请先登录")
    ok = await interest_service.delete_tag(user_id, tag_id)
    if not ok:
        raise HTTPException(404, "标签不存在")
    return {"deleted": True, "tag_id": tag_id}


@router.post(
    "/tags/from-knowledge/{node_id}",
    response_model=InterestTagFromKnowledgeResponse,
    summary="从知识图谱节点创建兴趣标签（跨模块引用）",
)
async def create_tag_from_knowledge(
    node_id: str,
    body: InterestTagFromKnowledgeRequest,
    user_id: str = Depends(current_user_id),
):
    if not user_id:
        raise HTTPException(401, "请先登录")
    tag = await interest_service.create_tag_from_knowledge(
        user_id, node_id, body.model_dump()
    )
    if not tag:
        raise HTTPException(404, "知识图谱节点不存在或创建失败")
    return {"tag": tag, "knowledge_node_id": node_id}


# ═══════════════════════════════════════════
# 2. 推送偏好
# ═══════════════════════════════════════════


@router.get(
    "/prefs",
    response_model=InterestPushPrefsResponse,
    summary="获取推送偏好",
)
async def get_prefs(
    user_id: str = Depends(current_user_id),
):
    if not user_id:
        raise HTTPException(401, "请先登录")
    return interest_service.get_prefs(user_id)


@router.patch(
    "/prefs",
    response_model=InterestPushPrefsResponse,
    summary="更新推送偏好（频率/时间/比例/跨学科/保留期）",
)
async def update_prefs(
    body: InterestPushPrefsUpdate,
    user_id: str = Depends(current_user_id),
):
    if not user_id:
        raise HTTPException(401, "请先登录")
    payload = body.model_dump(exclude_none=True)
    try:
        return interest_service.update_prefs(user_id, payload)
    except ValueError as e:
        raise HTTPException(400, str(e))


# ═══════════════════════════════════════════
# 3. 信息源管理
# ═══════════════════════════════════════════


@router.get(
    "/sources",
    summary="列出信息源（系统内置 + 用户自定义）",
)
async def list_sources(
    user_id: str = Depends(current_user_id),
    enabled_only: bool = Query(False),
):
    if not user_id:
        raise HTTPException(401, "请先登录")
    sources = interest_service.list_sources(user_id)
    if enabled_only:
        sources = [s for s in sources if s.get("enabled")]
    return {"items": sources, "total": len(sources)}


@router.post(
    "/sources",
    response_model=InterestSourceResponse,
    summary="新增信息源（仅支持 RSS/Atom，不支持任意 URL）",
)
async def create_source(
    body: InterestSourceCreate,
    user_id: str = Depends(current_user_id),
):
    if not user_id:
        raise HTTPException(401, "请先登录")
    if body.type not in ("arxiv", "biorxiv", "rss", "atom"):
        raise HTTPException(
            400,
            "不支持任意 URL 抓取（决策 5）。仅支持 rss/atom/arxiv/biorxiv 协议",
        )
    cfg = body.config or {}
    if body.type in ("rss", "atom", "arxiv", "biorxiv"):
        if not cfg.get("feed_url"):
            raise HTTPException(400, "config.feed_url 必填")
    src = await interest_service.create_source(user_id, body.model_dump())
    if not src:
        raise HTTPException(409, "信息源已存在")
    return src


@router.patch(
    "/sources/{source_id}/enable",
    response_model=InterestSourceResponse,
    summary="启用 / 禁用信息源",
)
async def enable_source(
    source_id: str,
    body: InterestSourceEnableUpdate,
    user_id: str = Depends(current_user_id),
):
    if not user_id:
        raise HTTPException(401, "请先登录")
    ok = await interest_service.set_source_enabled(
        user_id, source_id, body.enabled
    )
    if not ok:
        raise HTTPException(404, "信息源不存在")
    from app.services.interest import store
    return store.get_source(source_id)


@router.delete(
    "/sources/{source_id}",
    summary="删除信息源",
)
async def delete_source(
    source_id: str,
    user_id: str = Depends(current_user_id),
):
    if not user_id:
        raise HTTPException(401, "请先登录")
    ok = interest_service.delete_source(source_id, user_id=user_id)
    if not ok:
        raise HTTPException(404, "信息源不存在或不属于当前用户")
    return {"deleted": True, "source_id": source_id}


@router.post(
    "/sources/import-opml",
    response_model=InterestOPMLImportResponse,
    summary="导入 OPML 订阅列表（仅解析 RSS/Atom 项）",
)
async def import_opml(
    body: InterestOPMLImportRequest,
    user_id: str = Depends(current_user_id),
):
    if not user_id:
        raise HTTPException(401, "请先登录")
    result = interest_service.import_opml(user_id, body.opml_xml)
    if "error" in result:
        raise HTTPException(400, result["error"])
    return result


# ═══════════════════════════════════════════
# 4. 推送（今日 / 历史）
# ═══════════════════════════════════════════


@router.get(
    "/push/today",
    response_model=InterestTodayPushResponse,
    summary="今日推送（按用户时区）",
)
async def get_today_push(
    user_id: str = Depends(current_user_id),
):
    if not user_id:
        raise HTTPException(401, "请先登录")
    return interest_service.get_today_pushes(user_id)


@router.get(
    "/push/history",
    response_model=InterestPushHistoryResponse,
    summary="推送历史（分页 + 类型筛选）",
)
async def get_history(
    user_id: str = Depends(current_user_id),
    push_type: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    if not user_id:
        raise HTTPException(401, "请先登录")
    return interest_service.get_history(
        user_id, push_type=push_type, limit=limit, offset=offset
    )


@router.post(
    "/push/today/trigger",
    summary="手动触发推送（绕过时间窗口）",
)
async def trigger_push(
    user_id: str = Depends(current_user_id),
):
    if not user_id:
        raise HTTPException(401, "请先登录")
    return await interest_service.trigger_push(user_id)


@router.post(
    "/fetch-now",
    summary="手动触发全量抓取（管理员 / 调试用）",
)
async def trigger_fetch(
    user_id: str = Depends(current_user_id),
):
    if not user_id:
        raise HTTPException(401, "请先登录")
    return await interest_service.trigger_fetch_all()


# ═══════════════════════════════════════════
# 5. 反馈
# ═══════════════════════════════════════════


@router.post(
    "/push/{push_id}/feedback",
    summary="对推送记录反馈 (read / later / dislike / imported)",
)
async def record_feedback(
    push_id: str,
    body: InterestPushFeedbackRequest,
    user_id: str = Depends(current_user_id),
):
    if not user_id:
        raise HTTPException(401, "请先登录")
    if body.feedback not in ("read", "later", "dislike", "imported"):
        raise HTTPException(400, "feedback 必须是 read/later/dislike/imported")
    result = await interest_service.record_feedback(
        user_id=user_id,
        push_id=push_id,
        feedback=body.feedback,
        target_module=body.target_module.value if body.target_module else None,
        target_ref_id=body.target_ref_id,
    )
    return result


# ═══════════════════════════════════════════
# 6. 跨模块导入 (5 个目标)
# ═══════════════════════════════════════════


@router.post(
    "/push/{push_id}/import",
    summary="将推送内容导入到 5 个目标模块之一",
)
async def import_push(
    push_id: str,
    body: InterestPushImportRequest,
    user_id: str = Depends(current_user_id),
):
    if not user_id:
        raise HTTPException(401, "请先登录")
    target = body.target_module
    valid_targets = {
        CrossModuleTarget.READING,
        CrossModuleTarget.PROJECT,
        CrossModuleTarget.FLASHCARD,
        CrossModuleTarget.COGNITIVE_NODE,
        CrossModuleTarget.LANGUAGE_ROOM,
    }
    if target not in valid_targets:
        raise HTTPException(
            400,
            f"target_module 必须是 CrossModuleTarget 之一: "
            f"reading/project/flashcard/cognitive_node/language_room",
        )
    target_ref_id = await interest_service.import_to_module(
        user_id, push_id, target
    )
    if not target_ref_id:
        raise HTTPException(500, "导入失败")
    return {
        "imported": True,
        "push_id": push_id,
        "target_module": target.value,
        "target_ref_id": target_ref_id,
    }


# ═══════════════════════════════════════════
# 7. 本地权重（不发送到服务端）
# ═══════════════════════════════════════════


@router.get(
    "/weight-adjustments",
    summary="查看本地权重调整（不发送到服务端，仅本地采样概率）",
)
async def get_weights(
    user_id: str = Depends(current_user_id),
):
    if not user_id:
        raise HTTPException(401, "请先登录")
    adjustments = interest_service.list_weight_adjustments(user_id)
    sampling = interest_service.compute_sampling_weights_view(user_id)
    return {
        "adjustments": adjustments,
        "sampling_weights": sampling,
        "principle": "local_only_not_sent_to_server",
    }


@router.post(
    "/weight-adjustments/reset",
    response_model=InterestWeightResetResponse,
    summary="清空本地权重（恢复默认）",
)
async def reset_weights(
    user_id: str = Depends(current_user_id),
):
    if not user_id:
        raise HTTPException(401, "请先登录")
    cleared = interest_service.reset_weights(user_id)
    return {"reset": True, "cleared_count": cleared}
