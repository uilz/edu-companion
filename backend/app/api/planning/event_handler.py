"""PlanningEventHandler — 规划壳事件消费者

当前消费：
  - PlanItemRequested: 秘书编排器请求创建计划项。
    * requires_user_confirmation=False → 直接创建 plan item（幂等，按 request_id 去重）
    * requires_user_confirmation=True  → 写入 plan_item_confirmations 表，供前端确认
"""

from __future__ import annotations

import logging
from typing import Any

from shared.events import PlanItemRequested

logger = logging.getLogger(__name__)


class PlanningEventHandler:
    """规划领域事件处理器"""

    def __init__(self) -> None:
        self._bus: Any | None = None
        self._subscribed = False

    def subscribe(self, bus: Any) -> None:
        if self._subscribed:
            return
        self._bus = bus
        bus.subscribe("PlanItemRequested", self._on_plan_item_requested)
        self._subscribed = True
        logger.info("PlanningEventHandler: subscribed to PlanItemRequested")

    def unsubscribe(self) -> None:
        if not self._bus or not self._subscribed:
            return
        self._bus.unsubscribe("PlanItemRequested", self._on_plan_item_requested)
        self._subscribed = False
        logger.info("PlanningEventHandler: unsubscribed")

    async def _on_plan_item_requested(self, event: Any) -> None:
        if not isinstance(event, PlanItemRequested):
            return

        user_id = event.user_id
        request_id = event.request_id

        logger.debug(
            "收到 PlanItemRequested: user=%s request_id=%s target=%s confirmation=%s",
            user_id, request_id, event.target_type, event.requires_user_confirmation,
        )

        try:
            from shared.events import PlanningSourceModule
            from app.services.planning import (
                create_confirmation,
                create_plan_item,
                find_confirmation_by_request_id,
                find_plan_item_by_request_id,
            )

            # 幂等去重：同一 request_id 不重复创建 plan item
            existing_item = find_plan_item_by_request_id(user_id, request_id)
            if existing_item:
                logger.debug("PlanItem request_id=%s 已存在 plan item，跳过", request_id)
                return

            if event.requires_user_confirmation:
                # 幂等去重：同一 request_id 不重复创建 confirmation
                existing_confirmation = find_confirmation_by_request_id(user_id, request_id)
                if existing_confirmation:
                    logger.debug("PlanItem request_id=%s 已存在 confirmation，跳过", request_id)
                    return

                confirmation_metadata = {"requested_by": "secretary", "requires_confirmation": True}
                event_metadata = event.metadata if isinstance(event.metadata, dict) else {}
                if event_metadata.get("suggestion_id"):
                    confirmation_metadata["suggestion_id"] = event_metadata["suggestion_id"]

                create_confirmation(
                    user_id=user_id,
                    body={
                        "request_id": request_id,
                        "source_module": PlanningSourceModule.SECRETARY.value,
                        "target_type": event.target_type,
                        "target_ref_id": event.target_ref_id,
                        "title": event.title,
                        "description": event.description,
                        "priority": event.priority,
                        "estimated_minutes": event.estimated_minutes or 10,
                        "linked_node_ids": list(event.linked_node_ids or []),
                        "proposed_scheduled_for": event.proposed_scheduled_for,
                        "metadata": confirmation_metadata,
                    },
                )
                logger.info(
                    "已创建待确认计划项: user=%s request_id=%s",
                    user_id, request_id,
                )
                return

            item = create_plan_item(
                user_id=user_id,
                body={
                    "source_module": PlanningSourceModule.SECRETARY.value,
                    "target_type": event.target_type,
                    "target_ref_id": event.target_ref_id,
                    "title": event.title,
                    "description": event.description,
                    "estimated_minutes": event.estimated_minutes or 10,
                    "linked_node_ids": list(event.linked_node_ids or []),
                    "priority": event.priority,
                    "scheduled_for": event.proposed_scheduled_for,
                    "metadata": {
                        "request_id": request_id,
                        "requested_by": "secretary",
                        "requires_confirmation": False,
                    },
                },
            )
            logger.info(
                "已自动创建计划项: user=%s plan_item_id=%s request_id=%s",
                user_id, item.get("id"), request_id,
            )
        except Exception:
            logger.exception("处理 PlanItemRequested 失败")


# 全局单例，由 di.py / main.py 订阅
planning_event_handler = PlanningEventHandler()
