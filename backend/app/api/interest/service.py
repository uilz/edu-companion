"""
InterestExplorer API — Service Layer

负责业务编排:
- 标签管理 (3 层独立)
- 推送偏好 (frequency/time/比例)
- 信息源管理 (内置 / 用户自定义 / OPML)
- 推送 (今日 / 历史)
- 反馈 (read/later/dislike/imported)
- 跨模块导入 (5 个目标)
- 本地权重管理
- 从知识图谱创建标签
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Optional

from app.services.interest import store
from app.services.interest.source_fetcher import (
    BUILTIN_SOURCES,
    parse_opml,
    get_fetcher,
)
from app.services.interest.tag_matcher import (
    match_tags_against_item,
    compute_sampling_weights,
)
from app.services.interest.push_scheduler import get_scheduler
from app.services.interest.cross_module_importer import get_importer
from app.infrastructure.event_bus_utils import publish_event_safe
from shared.events import (
    CrossModuleTarget,
    InterestTagCreated,
    InterestTagUpdated,
    InterestTagDeleted,
    InterestTagFromKnowledgeCreated,
    InterestSourceEnabled,
    InterestSourceDisabled,
    InterestPushFeedbackRecorded,
    InterestContentImported,
    InterestLocalWeightAdjusted,
    InterestPrefsUpdated,
)

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════
# 1. 标签管理
# ═══════════════════════════════════════════


def list_tags_tree(user_id: str) -> list[dict]:
    """列出用户标签（树形结构）"""
    flat = store.list_tags(user_id)
    if not flat:
        return []
    by_id = {t["id"]: {**t, "children": []} for t in flat}
    roots: list[dict] = []
    for t in flat:
        node = by_id[t["id"]]
        if t.get("parent_id") and t["parent_id"] in by_id:
            by_id[t["parent_id"]]["children"].append(node)
        else:
            roots.append(node)
    return roots


async def create_tag(user_id: str, payload: dict) -> Optional[dict]:
    tag = store.create_tag(
        user_id=user_id,
        name=payload["name"],
        level=int(payload.get("level", 0)),
        parent_id=payload.get("parent_id"),
        weight=int(payload.get("weight", 1)),
        source=payload.get("source", "manual"),
        source_ref_id=payload.get("source_ref_id"),
        color=payload.get("color"),
    )
    if tag:
        publish_event_safe(InterestTagCreated(
            user_id=user_id,
            tag_id=tag["id"],
            name=tag["name"],
            level=tag.get("level", 0),
            parent_id=tag.get("parent_id"),
            weight=tag.get("weight", 1),
            source="manual" if tag.get("source") == "manual" else "system",
            cross_module_source=(
                "from_knowledge"
                if tag.get("source") == "from_knowledge"
                else ("from_reading" if tag.get("source") == "from_reading" else None)
            ),
        ))
    return tag


async def update_tag(
    user_id: str, tag_id: str, updates: dict
) -> Optional[dict]:
    tag = store.update_tag(user_id, tag_id, **updates)
    if tag:
        publish_event_safe(InterestTagUpdated(
            user_id=user_id,
            tag_id=tag_id,
            changed_fields=list(updates.keys()),
        ))
    return tag


async def delete_tag(user_id: str, tag_id: str) -> bool:
    ok = store.delete_tag(user_id, tag_id)
    if ok:
        publish_event_safe(InterestTagDeleted(
            user_id=user_id,
            tag_id=tag_id,
        ))
    return ok


async def create_tag_from_knowledge(
    user_id: str, knowledge_node_id: str, payload: dict
) -> Optional[dict]:
    """从知识图谱创建兴趣标签（跨模块引用）"""
    # 读取 CognitiveNode 信息
    node_info = _fetch_cognitive_node(user_id, knowledge_node_id)
    if not node_info:
        return None
    name = node_info.get("label") or node_info.get("name") or ""
    if not name:
        return None
    tag = store.create_tag(
        user_id=user_id,
        name=name[:128],
        level=int(payload.get("level", 0)),
        parent_id=payload.get("parent_id"),
        weight=int(payload.get("weight", 1)),
        source="from_knowledge",
        source_ref_id=knowledge_node_id,
        color=payload.get("color"),
    )
    if tag:
        publish_event_safe(InterestTagFromKnowledgeCreated(
            user_id=user_id,
            tag_id=tag["id"],
            knowledge_node_id=knowledge_node_id,
            tag_name=tag["name"],
            level=tag.get("level", 0),
        ))
    return tag


def _fetch_cognitive_node(user_id: str, node_id: str) -> Optional[dict]:
    try:
        from app.infrastructure.db.database import get_db
        db = get_db()
        # 真实表名: knowledge_nodes (PgCognitiveNodeRepository.upsert_node)
        row = db.fetchone(
            "SELECT * FROM knowledge_nodes WHERE id = %s AND user_id = %s",
            (node_id, user_id),
        )
        return dict(row) if row else None
    except Exception as e:
        logger.warning("_fetch_cognitive_node 失败: %s", e)
        return None


# ═══════════════════════════════════════════
# 2. 推送偏好
# ═══════════════════════════════════════════


def get_prefs(user_id: str) -> dict:
    return store.get_prefs(user_id)


def update_prefs(user_id: str, updates: dict) -> dict:
    before = store.get_prefs(user_id)
    new_prefs = store.upsert_prefs(user_id, updates)
    # 找出变更字段
    changed = [
        k for k in updates.keys()
        if str(before.get(k)) != str(new_prefs.get(k))
    ]
    if changed:
        # 委托给 publish_event_safe (自动处理 sync/async 上下文)
        publish_event_safe(InterestPrefsUpdated(
            user_id=user_id,
            changed_fields=changed,
        ))
    return new_prefs


# ═══════════════════════════════════════════
# 3. 信息源管理
# ═══════════════════════════════════════════


def list_sources(user_id: Optional[str] = None) -> list[dict]:
    """列出信息源（含 per-user 启用状态）

    返回的每个 source 都会附带 `user_enabled` 字段:
      - 用户私有源: 等于 sources.enabled
      - 系统源:     等于对应订阅记录的 enabled
    """
    sources = store.list_sources(user_id=user_id, enabled_only=False)
    if not sources:
        return []
    if not user_id:
        for s in sources:
            s["user_enabled"] = bool(s.get("enabled"))
        return sources

    # 加载用户所有订阅
    subs = {sub["source_id"]: sub for sub in store.list_user_subscriptions(user_id)}
    for s in sources:
        if s.get("user_id") is None:
            # 系统源
            sub = subs.get(s["id"])
            s["user_enabled"] = bool(sub and sub.get("enabled"))
        else:
            # 私有源
            s["user_enabled"] = bool(s.get("enabled"))
    return sources


async def create_source(user_id: str, payload: dict) -> Optional[dict]:
    src = store.create_source(
        user_id=user_id,
        name=payload["name"],
        type_=payload["type"],
        config=payload.get("config") or {},
        category=payload.get("category"),
        is_system=False,
        enabled=payload.get("enabled", True),
    )
    if src and src.get("enabled"):
        publish_event_safe(InterestSourceEnabled(
            user_id=user_id,
            source_id=src["id"],
            name=src["name"],
            type=src["type"],
        ))
    return src


async def set_source_enabled(
    user_id: str, source_id: str, enabled: bool
) -> bool:
    """启用 / 禁用 信息源

    - 系统源 (user_id IS NULL): 通过订阅表控制
    - 私有源 (user_id = x): 直接修改 sources.enabled + 同步订阅
    """
    src = store.get_source(source_id)
    if not src:
        return False
    is_system = src.get("user_id") is None

    if is_system:
        # 系统源: 走订阅表
        ok = store.set_subscription_enabled(user_id, source_id, enabled)
    else:
        # 私有源: 改源自身 + 同步订阅
        ok = store.set_source_enabled(source_id, enabled)
        store.ensure_subscription(user_id, source_id, enabled=enabled)

    if ok:
        if enabled:
            publish_event_safe(InterestSourceEnabled(
                user_id=user_id,
                source_id=source_id,
                name=src["name"],
                type=src["type"],
            ))
        else:
            publish_event_safe(InterestSourceDisabled(
                user_id=user_id,
                source_id=source_id,
                name=src["name"],
            ))
    return ok


def delete_source(source_id: str, user_id: Optional[str] = None) -> bool:
    """删除信息源 — 严格按用户隔离 (user_id 必传)"""
    return store.delete_source(source_id, user_id=user_id)


def import_opml(user_id: str, opml_xml: str) -> dict:
    """从 OPML 导入信息源"""
    try:
        items = parse_opml(opml_xml)
    except ValueError as e:
        return {"imported": 0, "skipped": 0, "items": [], "error": str(e)}

    imported: list[dict] = []
    skipped = 0
    for item in items:
        src = store.create_source(
            user_id=user_id,
            name=item["name"],
            type_=item["type"],
            config={"feed_url": item["feed_url"]},
            category=item.get("category"),
            is_system=False,
            enabled=True,
        )
        if src:
            imported.append(src)
        else:
            skipped += 1
    return {"imported": len(imported), "skipped": skipped, "items": imported}


def seed_builtin_sources() -> int:
    """初始化内置信息源（系统启动时调用）"""
    success = 0
    for src_def in BUILTIN_SOURCES:
        # 检查是否已存在
        existing = [
            s for s in store.list_sources(user_id=None)
            if s.get("is_system") and s.get("name") == src_def["name"]
        ]
        if existing:
            continue
        src = store.create_source(
            user_id=None,
            name=src_def["name"],
            type_=src_def["type"],
            config=src_def["config"],
            category=src_def.get("category"),
            is_system=True,
            enabled=True,
        )
        if src:
            success += 1
    return success


# ═══════════════════════════════════════════
# 4. 推送 (今日 / 历史)
# ═══════════════════════════════════════════


def get_today_pushes(user_id: str) -> dict:
    items = store.list_today_pushes(user_id)
    # 附加 feedback
    feedback_map = {
        f["push_id"]: f for f in store.list_feedback(user_id, limit=200)
    }
    enriched = []
    for it in items:
        it = dict(it)
        fid = feedback_map.get(it["id"])
        it["feedback"] = fid.get("feedback") if fid else None
        enriched.append(it)
    today = _today_iso()
    return {
        "user_id": user_id,
        "date": today,
        "items": enriched,
        "total": len(enriched),
    }


def get_history(
    user_id: str,
    push_type: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
) -> dict:
    items = store.list_push_records(
        user_id, push_type=push_type, limit=limit, offset=offset
    )
    feedback_map = {
        f["push_id"]: f for f in store.list_feedback(user_id, limit=limit)
    }
    enriched = []
    for it in items:
        it = dict(it)
        fid = feedback_map.get(it["id"])
        it["feedback"] = fid.get("feedback") if fid else None
        enriched.append(it)
    return {
        "items": enriched,
        "total": len(enriched),
        "limit": limit,
        "offset": offset,
    }


# ═══════════════════════════════════════════
# 5. 反馈
# ═══════════════════════════════════════════


async def record_feedback(
    user_id: str, push_id: str, feedback: str,
    target_module: Optional[str] = None,
    target_ref_id: Optional[str] = None,
) -> dict:
    rec = store.record_feedback(
        push_id=push_id,
        user_id=user_id,
        feedback=feedback,
        target_module=target_module,
        target_ref_id=target_ref_id,
    )

    # 反馈 = later 时，生成 FlashCard 临时状态
    card_id: Optional[str] = None
    if feedback == "later":
        card_id = await _mark_as_later(user_id, push_id)
    # 反馈 = dislike 时，本地权重调整
    weight_updated: Optional[dict] = None
    if feedback == "dislike":
        weight_updated = await _adjust_dislike_for_push(user_id, push_id)

    publish_event_safe(InterestPushFeedbackRecorded(
        user_id=user_id,
        push_id=push_id,
        feedback=feedback,
    ))

    return {
        "feedback": rec,
        "flashcard_id": card_id,
        "weight_adjusted": weight_updated,
    }


async def _mark_as_later(user_id: str, push_id: str) -> Optional[str]:
    """标记稍后读 = 创建 FlashCard (status='later', source='interest_explorer')"""
    push = store.get_push_record(user_id, push_id)
    if not push:
        return None
    try:
        from app.api.flashcard.service import FlashCardService
        svc = FlashCardService()
        card = svc.create_card(user_id, {
            "type": 1,
            "source": "interest_explorer",
            "cross_module_source": "interest_explorer",
            "front_text": push["title"][:500],
            "back_text": (push.get("summary") or push.get("url") or "")[:1000],
            "source_ref": {
                "module": "interest_explorer",
                "id": push_id,
                "url": push.get("url") or "",
                "title": push.get("title") or "",
            },
            "status": "later",
            "linked_node_ids": [],
            "tags": ["interest_explorer", "later"],
        })
        # 设置 status='later'
        if card and isinstance(card, dict) and card.get("id"):
            try:
                svc.update_card(user_id, card["id"], {"status": "later"})
            except Exception:
                pass
            return card["id"]
    except Exception as e:
        logger.warning("_mark_as_later 失败: %s", e)
    return None


async def _adjust_dislike_for_push(user_id: str, push_id: str) -> Optional[dict]:
    """对推送匹配的标签全部累计 dislike_score += 0.1"""
    push = store.get_push_record(user_id, push_id)
    if not push:
        return None
    tags = push.get("matched_tags") or []
    if not tags:
        return None
    results: list[dict] = []
    for tag_id in tags:
        wa = store.increment_dislike(user_id, tag_id, delta=0.1)
        results.append(wa)
        # 发布 InterestLocalWeightAdjusted（本地事件，不入 event_bus）
        # 仅记录到内存中，不影响其他模块
    return {"adjusted_tags": len(results), "details": results}


# ═══════════════════════════════════════════
# 6. 跨模块导入
# ═══════════════════════════════════════════


async def import_to_module(
    user_id: str,
    push_id: str,
    target_module: CrossModuleTarget,
) -> Optional[str]:
    """导入到 5 个目标模块之一（严格使用 CrossModuleTarget）"""
    push = store.get_push_record(user_id, push_id)
    if not push:
        return None
    importer = get_importer()
    target_ref_id = await importer.import_to(
        user_id=user_id,
        push_id=push_id,
        target_module=target_module,
        title=push["title"],
        url=push.get("url") or "",
        summary=push.get("summary") or "",
    )
    if target_ref_id:
        # 记录 feedback = imported
        store.record_feedback(
            push_id=push_id,
            user_id=user_id,
            feedback="imported",
            target_module=target_module.value,
            target_ref_id=target_ref_id,
        )
    return target_ref_id


# ═══════════════════════════════════════════
# 7. 本地权重
# ═══════════════════════════════════════════


def list_weight_adjustments(user_id: str) -> list[dict]:
    return store.list_weight_adjustments(user_id)


def reset_weights(user_id: str) -> int:
    return store.reset_weights(user_id)


def compute_sampling_weights_view(
    user_id: str, cross_disciplinary: bool = False
) -> list[dict]:
    weights = compute_sampling_weights(user_id, cross_disciplinary)
    tags = {t["id"]: t for t in store.list_tags(user_id)}
    out = []
    for tid, w in weights:
        t = tags.get(tid, {})
        out.append({
            "tag_id": tid,
            "tag_name": t.get("name"),
            "level": t.get("level"),
            "effective_weight": w,
        })
    return out


# ═══════════════════════════════════════════
# 8. 调度（手动触发）
# ═══════════════════════════════════════════


async def trigger_push(user_id: str) -> dict:
    """手动触发推送"""
    scheduler = get_scheduler()
    return await scheduler.run_for_user(user_id, force=True)


async def trigger_fetch_all() -> dict:
    """手动触发全量抓取"""
    fetcher = get_fetcher()
    return await fetcher.fetch_all_enabled()


# ═══════════════════════════════════════════
# 工具
# ═══════════════════════════════════════════


def _today_iso() -> str:
    return datetime.now(timezone.utc).date().isoformat()
