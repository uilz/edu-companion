"""对话系统领域服务"""

from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from app.infrastructure.event_bus import EventBus
    from app.infrastructure.resilience import CircuitBreaker
    from shared.events import (
        SessionCompleted,
        StudyPlanGenerated,
        DailyGoalAchieved,
    )

logger = logging.getLogger("conversation")


class ConversationServiceImpl:
    """对话系统实现 — 含 LLM 调用 + 事件处理"""

    def __init__(self, llm, event_bus: EventBus, circuit: CircuitBreaker):
        self._llm = llm
        self._bus = event_bus
        self._circuit = circuit
        # WebSocket 已移除，使用 SSE/TokenBuffer 替代

    async def send_message(
        self, user_id: str, content: str,
        partition_id: str | None = None,
        branch_id: str | None = None,
    ) -> dict:
        """发送消息 → LLM 回复（委托到 domain/conversation/llm.py）"""
        pid = partition_id or ""
        if not pid and branch_id:
            from app.services.common import get_data_repo
            data = get_data_repo().load(user_id)
            for conv in data.conversations.values():
                if conv.id == branch_id:
                    if conv.partition_id:
                        pid = conv.partition_id
                    else:
                        for t in data.topics.values():
                            if t.id == conv.topic_id:
                                for d in data.domains.values():
                                    if d.id == t.domain_id:
                                        pid = d.partition_id
                                        break
        if not pid:
            return {"ok": False, "error": "cannot determine partition"}

        from .llm import send_and_reply
        return await send_and_reply(user_id, pid, content, conversation_id=branch_id)

    async def send_and_reply(
        self,
        user_id: str,
        partition_id: str,
        user_text: str,
        content_blocks: list | None = None,
        conversation_id: str = "",
        pending_quote: dict | None = None,
    ) -> dict:
        """完整流程：存用户消息 → 生成回复（含工具） → 存助手消息"""
        from .llm import send_and_reply
        return await send_and_reply(
            user_id, partition_id, user_text,
            content_blocks=content_blocks,
            conversation_id=conversation_id,
            pending_quote=pending_quote,
        )

    async def send_and_reply_stream(
        self,
        user_id: str,
        partition_id: str,
        user_text: str,
        content_blocks: list | None = None,
        conversation_id: str = "",
        pending_quote: dict | None = None,
    ):
        """完整流程（流式）：自动路由 → 存用户消息 → 预执行工具 → 流式生成回复 → 存助手消息"""
        from .llm import send_and_reply_stream
        async for event in send_and_reply_stream(
            user_id, partition_id, user_text,
            content_blocks=content_blocks,
            conversation_id=conversation_id,
            pending_quote=pending_quote,
        ):
            yield event

    # ── 事件监听器 ──

    async def on_session_completed(self, event: SessionCompleted) -> None:
        """练习完成 → 写入对话记忆，更新 branch 的 practice_summary"""
        user_id = getattr(event, "user_id", "?")
        session_id = getattr(event, "session_id", "?")
        accuracy = getattr(event, "accuracy", 0.0)

        logger.info(
            "Conversation: session completed user=%s session=%s accuracy=%.2f",
            user_id, session_id, accuracy,
        )

        # 更新对话 branch 的 practice_summary
        try:
            from app.services.common import get_data_repo
            data = get_data_repo().load(user_id)
            # Find branches that reference this session and update practice_summary
            updated = False
            for branch in data.conversations.values():
                if session_id in getattr(branch, "practice_sessions", []):
                    summary_parts = [
                        f"已练{getattr(event, 'total_questions', 0)}题",
                        f"正确率{accuracy:.0%}",
                        f"用时{getattr(event, 'duration_minutes', 0):.0f}分钟",
                    ]
                    branch.practice_summary = ",".join(summary_parts)
                    updated = True

            if updated:
                get_data_repo().save(user_id, data)
                logger.info("Conversation: practice_summary updated for session %s", session_id)
            else:
                # No branch references this session yet — find most recent branch and append
                for branch in data.conversations.values():
                    sessions = getattr(branch, "practice_sessions", [])
                    sessions.append(session_id)
                    summary_parts = [
                        f"已练{getattr(event, 'total_questions', 0)}题",
                        f"正确率{accuracy:.0%}",
                    ]
                    branch.practice_summary = ",".join(summary_parts)
                    get_data_repo().save(user_id, data)
                    logger.info("Conversation: practice_summary appended to branch for session %s", session_id)
                    break
        except Exception as exc:
            logger.warning("Conversation: failed to update branch practice_summary: %s", exc)

    async def on_knowledge_updated(self, event) -> None:
        """知识升级（CognitiveNodeUpdated） → LLM 上下文感知"""
        label = getattr(event, "label", "?") or getattr(event, "skill_id", "?")
        logger.debug(
            "Conversation: cognitive updated user=%s label=%s %.3f→%.3f",
            getattr(event, "user_id", "?"),
            label,
            getattr(event, "proficiency_before", 0),
            getattr(event, "proficiency_after", 0),
        )

    async def on_plan_generated(self, event: StudyPlanGenerated) -> None:
        """计划生成 → 向用户推送新计划"""
        logger.info(
            "Conversation: plan generated user=%s partition=%s items=%d",
            getattr(event, "user_id", "?"),
            getattr(event, "partition_id", "?"),
            len(getattr(event, "items", []) or []),
        )
        # WS 已移除，跳过推送通知
        pass

    async def on_goal_achieved(self, event: DailyGoalAchieved) -> None:
        """目标达成 → 推送祝贺"""
        logger.info(
            "Achievement: goal achieved user=%s goal=%s progress=%.0f%%",
            getattr(event, "user_id", "?"),
            getattr(event, "goal_type", "practice"),
            getattr(event, "progress_pct", 0.0),
        )
        # WS 已移除，跳过推送


    async def push_response_block(
        self, user_id: str, message_id: str,
        block_type: str, content: dict,
    ) -> None:
        """推送 ResponseBlock 到前端"""
        await self._push_block(user_id, message_id, block_type, content)

    async def _push_block(
        self, user_id: str, message_id: str,
        block_type: str, content: dict,
    ) -> None:
        """推送 ResponseBlock — WS 已移除，block_update 通过 TokenBuffer 推送"""
        logger.debug(
            "block_update (WS removed): user=%s msg=%s type=%s",
            user_id[:8], message_id[:8], block_type,
        )

    async def inject_practice_context(
        self, user_id: str, branch_id: str, context: dict,
    ) -> None:
        """注入练习上下文到对话系统"""
        logger.debug(
            "Conversation: practice context injected user=%s branch=%s keys=%s",
            user_id, branch_id[:8], list(context.keys()),
        )
