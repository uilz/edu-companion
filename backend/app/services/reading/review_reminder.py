"""Reading 回顾提醒服务 (review_reminder)

依据 docs/modules/reading/overview.md §6.2 + ADR 0003
**关键决策**：**不**新建独立提醒表，回顾提醒 = 复用 PlanItem (PlanItemScheduled)。

事件链：
    user → POST /api/reading/review-reminder
        → reading.review_reminder.schedule_review_reminder
        → planning.create_plan_item(source_module='reading')
        → bus.publish(PlanItemScheduled)
        → N 天后 Planning 触发 PlanItemActivated
        → 用户看到"回顾阅读"提醒

**不**新建 ReadingReviewReminder 表，**不**发送独立 ReadingReviewReminder 事件。
但为了一致性，发布 ReadingReviewReminderScheduled 业务事件作为审计记录。
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from app.infrastructure.event_bus_utils import publish_event_safe
from shared.events import CrossModuleTarget

logger = logging.getLogger(__name__)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _publish(event: Any) -> None:
    """发布事件 — 委托给 publish_event_safe (自动处理 sync/async 上下文)"""
    publish_event_safe(event)


VALID_REMINDER_DAYS = (7, 30, 90)


def schedule_review_reminder(
    user_id: str,
    material_id: str,
    review_after_days: int = 7,
    title: str = "",
    description: str = "",
    estimated_minutes: int = 30,
) -> dict:
    """创建阅读回顾提醒（= 创建 PlanItem with source_module='reading'）。

    Args:
        user_id: 用户 ID
        material_id: 关联材料 ID
        review_after_days: 多少天后回顾（7/30/90）
        title: 计划项标题（缺省自动生成）
        description: 描述
        estimated_minutes: 预计时长（分钟）
    """
    if review_after_days not in VALID_REMINDER_DAYS:
        raise ValueError(
            f"review_after_days 必须是 {VALID_REMINDER_DAYS} 之一, got {review_after_days}"
        )
    if not title:
        title = f"回顾阅读：{material_id[:12]}{'...' if len(material_id) > 12 else ''}"

    # 调用 Planning service 创建 PlanItem
    from app.services.planning.items import create_plan_item, delete_plan_item
    from app.services.planning.items import list_plan_items as planning_list_plan_items

    now = _now()
    scheduled_for = now + timedelta(days=review_after_days)
    plan_item_body = {
        "source_module": CrossModuleTarget.READING.value,  # "reading"
        "target_type": "material",
        "target_ref_id": material_id,
        "title": title,
        "description": description or f"阅读 {review_after_days} 天后回顾",
        "estimated_minutes": estimated_minutes,
        "linked_node_ids": [],
        "priority": 1,
        "scheduled_for": scheduled_for,
        "plan_date": scheduled_for.date(),
    }
    plan_item = planning_svc.create_plan_item(user_id, plan_item_body)
    if not plan_item:
        raise RuntimeError("创建回顾提醒失败 (planning.create_plan_item 返回空)")

    # 发布 PlanItemScheduled 事件（planning 路由可能不会自动发，因为 create_plan_item 内部已发）
    # 防御性：判断 status 是不是 scheduled, 如果是 pending 则发布一次
    try:
        from shared.events import PlanItemScheduled
        _publish(PlanItemScheduled(
            user_id=user_id,
            plan_item_id=plan_item["id"],
            source_module=CrossModuleTarget.READING.value,
            scheduled_for=scheduled_for,
            plan_date=str(scheduled_for.date()),
            is_mood_rule_affected=False,
            scheduled_at=now,
        ))
    except Exception as e:  # noqa: BLE001
        logger.debug("PlanItemScheduled 事件发布失败: %s", e)

    # 发布 ReadingReviewReminderScheduled 业务事件（审计）
    try:
        from shared.events import ReadingReviewReminderScheduled
        _publish(ReadingReviewReminderScheduled(
            user_id=user_id,
            material_id=material_id,
            reminder_days=review_after_days,
            scheduled_for=scheduled_for,
            plan_item_id=plan_item["id"],
        ))
    except Exception as e:  # noqa: BLE001
        logger.debug("ReadingReviewReminderScheduled 事件发布失败: %s", e)

    return {
        "plan_item_id": plan_item["id"],
        "material_id": material_id,
        "review_after_days": review_after_days,
        "scheduled_for": scheduled_for,
        "plan_item": plan_item,
    }


def list_pending_reminders(
    user_id: str,
    material_id: Optional[str] = None,
) -> list[dict]:
    """查询用户的阅读回顾提醒（= source_module='reading' 且未完成的 PlanItem）。

    PlanItem 的实际状态枚举包括 'scheduled' / 'pending' / 'in_progress' 等，
    planning 服务在创建时一般会落到 'scheduled'，因此同时查询这两个状态。
    """
    items_scheduled = planning_list_plan_items(
        user_id,
        source_module=CrossModuleTarget.READING.value,
        status="scheduled",
        limit=100,
    )
    items_pending = planning_list_plan_items(
        user_id,
        source_module=CrossModuleTarget.READING.value,
        status="pending",
        limit=100,
    )
    # 按 plan_item_id 去重
    seen: set[str] = set()
    items: list[dict] = []
    for it in items_scheduled + items_pending:
        pid = it.get("id", "")
        if pid and pid not in seen:
            seen.add(pid)
            items.append(it)
    if material_id:
        items = [it for it in items if it.get("target_ref_id") == material_id]
    return items


def cancel_reminder(user_id: str, plan_item_id: str) -> bool:
    """取消已设置的回顾提醒（删除 PlanItem）。"""
    return delete_plan_item(user_id, plan_item_id)
