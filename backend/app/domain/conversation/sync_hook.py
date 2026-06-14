"""
SyncHook — 事件驱动的认知节点同步

替代 TreeSyncMixin 的隐式调用。
TreeMutate 产出领域事件后，SyncHook 订阅并执行同步。
"""

from __future__ import annotations

import asyncio
import logging

logger = logging.getLogger(__name__)


class SyncHook:
    """认知节点同步钩子 — 订阅领域事件，执行图同步"""

    def __init__(self) -> None:
        self._subscribed = False

    def subscribe(self, event_bus) -> None:
        """订阅领域事件"""
        if self._subscribed:
            return
        # 订阅 AssistantReplied → 触发知识点同步
        try:
            from shared.events import AssistantReplied
            event_bus.subscribe(AssistantReplied, self._on_reply)
            self._subscribed = True
            logger.info("SyncHook: subscribed to AssistantReplied")
        except Exception:
            logger.warning("SyncHook: subscribe failed", exc_info=True)

    async def _on_reply(self, event) -> None:
        """AI 回复后，提取知识点并同步到认知图"""
        try:
            user_id = getattr(event, "user_id", "")
            content = getattr(event, "content", "")
            skill_ids = getattr(event, "skill_ids", [])

            if not skill_ids:
                return

            from app.services.knowledge.tree_service import TreeSyncMixin
            syncer = TreeSyncMixin()
            partition_id = getattr(event, "partition_id", "")
            conversation_id = getattr(event, "conversation_id", "")

            for skill_id in skill_ids:
                await syncer._sync_skill(user_id, skill_id, partition_id, conversation_id)
            logger.debug("SyncHook: synced %d knowledge nodes", len(skill_ids))
        except Exception:
            logger.debug("SyncHook: sync error (non-critical)", exc_info=True)

    async def sync_after_message(
        self, user_id: str, content: str,
        partition_id: str = "", conversation_id: str = "",
    ) -> None:
        """手动触发同步"""
        import re
        skill_ids = re.findall(r"\[KNOWLEDGE:(\w+)\]", content)
        if not skill_ids:
            return
        try:
            from app.services.knowledge.tree_service import TreeSyncMixin
            syncer = TreeSyncMixin()
            for skill_id in skill_ids:
                await syncer._sync_skill(user_id, skill_id, partition_id, conversation_id)
        except Exception:
            logger.debug("SyncHook: manual sync error", exc_info=True)


# 全局单例
sync_hook = SyncHook()