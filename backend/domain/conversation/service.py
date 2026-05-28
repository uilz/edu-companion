"""对话系统领域服务 — 含 Phase 5 多媒体 WebSocket 推送"""

from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from infra.event_bus import EventBus
    from infra.resilience import CircuitBreaker
    from shared.events import (
        SessionCompleted,
        KnowledgeStateUpdated,
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
        # WebSocket 管理器（延迟注入）
        self._ws_manager: Any = None

    def set_ws_manager(self, ws_manager: Any) -> None:
        """注入 WebSocket ConnectionManager（from app.api.chat）"""
        self._ws_manager = ws_manager

    async def send_message(
        self, user_id: str, content: str,
        partition_id: str | None = None,
        branch_id: str | None = None,
    ) -> dict:
        return {}

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
            from app.services.storage import storage
            data = storage.load(user_id)
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
                storage.save(user_id, data)
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
                    storage.save(user_id, data)
                    logger.info("Conversation: practice_summary appended to branch for session %s", session_id)
                    break
        except Exception as exc:
            logger.warning("Conversation: failed to update branch practice_summary: %s", exc)

    async def on_knowledge_updated(self, event: KnowledgeStateUpdated) -> None:
        """知识升级 → LLM 上下文感知"""
        logger.debug(
            "Conversation: knowledge updated user=%s skill=%s %s→%s",
            getattr(event, "user_id", "?"),
            getattr(event, "skill_id", "?"),
            getattr(event, "old_mastery", "?"),
            getattr(event, "new_mastery", "?"),
        )

    async def on_plan_generated(self, event: StudyPlanGenerated) -> None:
        """计划生成 → 向用户推送新计划"""
        logger.info(
            "Conversation: plan generated user=%s partition=%s items=%d",
            getattr(event, "user_id", "?"),
            getattr(event, "partition_id", "?"),
            len(getattr(event, "items", []) or []),
        )
        # 如有 WS 管理器，推送通知
        if self._ws_manager:
            try:
                await self._ws_manager.send_json(
                    getattr(event, "user_id", ""),
                    {"type": "plan_updated", "payload": {}},
                )
            except Exception:
                pass

    async def on_goal_achieved(self, event: DailyGoalAchieved) -> None:
        """目标达成 → 推送祝贺"""
        logger.info(
            "Achievement: goal achieved user=%s goal=%s progress=%.0f%%",
            getattr(event, "user_id", "?"),
            getattr(event, "goal_type", "practice"),
            getattr(event, "progress_pct", 0.0),
        )
        if self._ws_manager:
            try:
                await self._ws_manager.send_json(
                    getattr(event, "user_id", ""),
                    {"type": "goal_achieved", "payload": {"goal": getattr(event, "goal_type", "practice")}},
                )
            except Exception:
                pass


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
        """通过 WebSocket 推送 block_update 消息"""
        if not self._ws_manager:
            logger.warning("WS manager not injected — skipping block push")
            return

        payload = {
            "type": "block_update",
            "payload": {
                "message_id": message_id,
                "block": {
                    "type": block_type,
                    "status": "ready",
                    "content": content,
                },
            },
        }
        try:
            await self._ws_manager.send_json(user_id, payload)
            logger.debug(
                "📤 block_update: user=%s type=%s msg=%s",
                user_id, block_type, message_id[:8],
            )
        except Exception as e:
            logger.error("Failed to push block_update: %s", e)

    async def inject_practice_context(
        self, user_id: str, branch_id: str, context: dict,
    ) -> None:
        """注入练习上下文到对话系统"""
        logger.debug(
            "Conversation: practice context injected user=%s branch=%s keys=%s",
            user_id, branch_id[:8], list(context.keys()),
        )
