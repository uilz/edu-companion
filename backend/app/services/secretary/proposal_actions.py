"""秘书提案动作执行服务 (Task #168)

封装 proposal accept/dismiss 后的副作用：
  - 执行提案动作 (action_handler.execute)
  - 记录策略交互 (policy_engine.record_interaction)
  - 写入用户画像关系记忆
  - 触发学习路径调整 (plan_bridge)
  - 发布 ProposalAccepted 事件

API 路由仅负责状态更新与 HTTP 错误映射，所有业务编排下沉到本服务。
"""

from __future__ import annotations

import logging
import time
from typing import Any

from app.domain.secretary.models import Proposal

logger = logging.getLogger(__name__)


async def execute_accepted_action(proposal: Proposal | None, user_id: str) -> dict[str, Any]:
    """执行已采纳提案的完整副作用链路。

    Returns:
        {"status": "accepted", "action_result": ..., "plan_adjustment": ...}
    """
    action_result = None
    plan_adjustment = None

    if proposal is None:
        return {"status": "accepted", "action_result": None, "plan_adjustment": None}

    from app.domain.secretary.engines.proposal_service import action_handler
    from app.domain.secretary.engines.policy_engine import policy_engine

    try:
        action_result = await action_handler.execute(proposal, user_id)
        logger.info("提案动作执行: %s → %s", proposal.action_type, action_result.get("success"))

        policy_engine.record_interaction(user_id, proposal, "accepted")
        _update_relation_memory(user_id, proposal, "accept")

        if action_result.get("success"):
            try:
                from app.domain.secretary.engines.secretary_plan_bridge import plan_bridge
                plan_adjustment = await plan_bridge.on_proposal_accepted(proposal, user_id)
            except Exception as pe:
                logger.warning("plan_bridge.on_proposal_accepted 失败: %s", pe)
                plan_adjustment = None

        await _publish_accepted_event(proposal, user_id)
    except Exception as e:
        logger.warning("提案动作/计划调整失败: %s", e)

    return {
        "status": "accepted",
        "action_result": action_result,
        "plan_adjustment": plan_adjustment,
    }


async def record_dismiss(proposal: Proposal | None, user_id: str) -> dict[str, Any] | None:
    """记录提案忽略后的策略反馈。

    Returns:
        {"status": "dismissed", "policy": ...} 或 None（当 proposal 不存在或失败）
    """
    if proposal is None:
        return None

    try:
        from app.domain.secretary.engines.policy_engine import policy_engine
        result = policy_engine.record_interaction(user_id, proposal, "dismissed")
        _update_relation_memory(user_id, proposal, "dismiss")
        return {"status": "dismissed", "policy": result}
    except Exception as e:
        logger.warning("Policy record_interaction failed on dismiss: %s", e)
        return None


def _update_relation_memory(user_id: str, proposal: Proposal, action: str) -> None:
    """同步写入 UserOrchestrationProfile 关系记忆"""
    try:
        from app.infrastructure.db.user_profile_store import user_profile_store
        kp_id = (proposal.payload or {}).get("kp_id", "")
        user_profile_store.update_relation_memory(user_id, proposal.action_type, kp_id, action)
    except Exception as e:
        logger.debug("UserOrchestrationProfile 关系记忆更新失败: %s", e)


async def _publish_accepted_event(proposal: Proposal, user_id: str) -> None:
    """发布 ProposalAccepted 事件供跨模块联动"""
    try:
        from app.application.di import get_event_bus
        from shared.events import ProposalAccepted

        payload = proposal.payload or {}
        target_ref_id = (
            payload.get("target_ref_id", "")
            or payload.get("target_node_id", "")
            or payload.get("parent_id", "")
            or payload.get("kp_id", "")
        )
        target_module = payload.get("target_module", "")
        linked_node_ids = payload.get("linked_node_ids", []) or []
        if target_ref_id and target_ref_id not in linked_node_ids:
            linked_node_ids = list(linked_node_ids) + [target_ref_id]

        await get_event_bus().publish(ProposalAccepted(
            user_id=user_id,
            source_module="secretary",
            proposal_id=proposal.id,
            action_type=proposal.action_type,
            target_module=target_module,
            target_ref_id=target_ref_id,
            linked_node_ids=linked_node_ids,
        ))
    except Exception as e:
        logger.debug("ProposalAccepted 事件发射失败: %s", e)


def build_execution_result_payload(body: dict) -> dict:
    """构造提案执行结果回传的 metadata 载荷"""
    return {
        "success": body.get("success", True),
        "message": body.get("message", ""),
        "details": body.get("details"),
        "completed_at": body.get("completed_at", int(time.time() * 1000)),
    }
