"""
ReplyHooks — AssistantReplied 事件驱动的对话副作用

替代 reply_pipeline.py PostProcessor 链中的非阻塞副作用处理器：
- CognitiveSync: 对话 → CognitiveNode 联动
- KnowledgeEvidence: 对话知识证据分析
- MetaHistory: 分支重命名 / 图谱更新

这些 hooks 通过事件总线订阅 AssistantReplied，在管线外部异步执行，
不再阻塞回复管线的 done 事件发布。
"""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from shared.events import AssistantReplied

logger = logging.getLogger(__name__)


class ReplyHooks:
    """AssistantReplied 事件监听器集合"""

    def subscribe(self, event_bus) -> None:
        """订阅 AssistantReplied 事件"""
        event_bus.subscribe("AssistantReplied", self._on_assistant_replied)
        logger.info("ReplyHooks: subscribed to AssistantReplied")

    async def _on_assistant_replied(self, event) -> None:
        """分发到各 hook，不抛异常"""
        await asyncio.gather(
            self._cognitive_sync(event),
            self._knowledge_evidence(event),
            self._meta_history(event),
            return_exceptions=True,
        )

    async def _cognitive_sync(self, event) -> None:
        """对话 → CognitiveNode 联动 (通过 SourceParser 缓存读取 skill_ids)"""
        from app.domain.conversation.reply_pipeline import SourceParser

        assistant_message_id = getattr(event, "assistant_message_id", "")
        if not assistant_message_id:
            return

        skill_ids = SourceParser._skill_ids_by_node.pop(assistant_message_id, [])
        if not skill_ids:
            return

        user_id = getattr(event, "user_id", "")
        conv_id = getattr(event, "conv_id", "")
        try:
            from app.services.common import get_data_repo
            from app.services.knowledge.cognitive_sync import _cognify_dialogue_context

            data = get_data_repo().load(user_id)
            conversation = data.directory_nodes.get(conv_id)
            if conversation and conversation.node_type == "conv":
                await _cognify_dialogue_context(
                    user_id, conversation, list(skill_ids),
                    context_type="lower",
                )
                logger.debug("ReplyHooks: cognitive sync done for %d skills", len(skill_ids))
        except Exception:
            logger.debug("ReplyHooks: cognitive sync failed (non-critical)", exc_info=True)

    async def _knowledge_evidence(self, event) -> None:
        """对话知识证据分析"""
        user_id = getattr(event, "user_id", "")
        dir_id = getattr(event, "dir_id", "")
        user_text = getattr(event, "user_text", "")
        reply_text = getattr(event, "content", "")
        conv_id = getattr(event, "conv_id", "")

        if not user_text and not reply_text:
            return

        try:
            from app.services.knowledge.cognitive_sync import _analyze_conversation_evidence
            await _analyze_conversation_evidence(
                user_id, dir_id, user_text, reply_text,
                conv_id=conv_id,
            )
            logger.debug("ReplyHooks: knowledge evidence analyzed")
        except Exception:
            logger.debug("ReplyHooks: knowledge evidence failed (non-critical)", exc_info=True)

    async def _meta_history(self, event) -> None:
        """消息后处理钩子：分支重命名 / 图谱更新"""
        user_id = getattr(event, "user_id", "")
        dir_id = getattr(event, "dir_id", "")
        assistant_message_id = getattr(event, "assistant_message_id", "")

        if not assistant_message_id:
            return

        try:
            from app.services.common import get_data_repo
            from app.domain.knowledge import get_knowledge_query

            data = get_data_repo().load(user_id)
            assistant_node = data.nodes.get(assistant_message_id)
            if assistant_node:
                get_knowledge_query().post_message_hooks(
                    user_id, dir_id, assistant_node,
                )
                logger.debug("ReplyHooks: meta history hooks done")
        except Exception:
            logger.debug("ReplyHooks: meta history failed (non-critical)", exc_info=True)


# 全局单例，由 di.py 在 _wire_events 中订阅
reply_hooks = ReplyHooks()
