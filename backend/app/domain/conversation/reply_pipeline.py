"""
ReplyPipeline — 统一回复管线

invoke() 为单一入口，产出 ReplyEvent 流。非流式消费只需监听 done 事件。

内部 5 阶段：
  Stage 1: auto_resolve → context_switch 事件
  Stage 2: 存用户消息 → user_message 事件
  Stage 3: LLM tool loop（工具调用 → 文本回复）
  Stage 4: PostProcessor 链（追问/来源/存储/sync）
  Stage 5: done 事件
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
from dataclasses import dataclass, field
from typing import Any, AsyncGenerator, Protocol

from app.schemas.conversation import (
    ContentBlock,
    TextBlock,
    TreeNode,
    ResponseBlock,
    QuoteBlock,
)
from app.services.common import get_data_repo
from app.services.knowledge.tree_ops import tree_ops
from app.services.common.classifier import classifier
from app.services.llm.tool_executor import tool_executor, SLOW_TOOLS
from app.services.analytics.emotion_analyzer import emotion_analyzer
from app.domain.knowledge import get_knowledge_query

logger = logging.getLogger(__name__)

MAX_TOOL_ROUNDS = 5
AGENT_LABEL = "tutor"


# ═══════════════════════════════════════════════
# 事件类型
# ═══════════════════════════════════════════════


@dataclass
class ReplyEvent:
    """管线产出的事件"""
    type: str  # context_switch | user_message | tool_block | token | done | error
    data: dict = field(default_factory=dict)

    # 便捷字段（type 特定）
    content: str = ""                   # token
    block: dict | None = None           # tool_block
    message: dict | None = None         # user_message
    switch_detail: dict | None = None   # context_switch


# ═══════════════════════════════════════════════
# PostProcessor 接口
# ═══════════════════════════════════════════════


@dataclass
class PostProcessInput:
    """进入后处理器的数据"""
    user_id: str
    partition_id: str
    user_text: str
    reply_text: str
    conversation_id: str
    assistant_node: TreeNode
    response_blocks: list[ResponseBlock]
    conversation: Any = None


class PostProcessor(Protocol):
    """后处理器接口"""

    is_blocking: bool  # True → await, False → create_task

    async def process(self, input: PostProcessInput) -> None: ...


# ═══════════════════════════════════════════════
# 内置 PostProcessor
# ═══════════════════════════════════════════════

FOLLOW_UP_RE = re.compile(
    r'<!--FOLLOW_UP-->\s*\n?(.*?)\n?<!--/FOLLOW_UP-->',
    re.DOTALL,
)


class FollowUpParser(PostProcessor):
    """追问问题解析 → 写入 assistant node metadata"""
    is_blocking = True

    async def process(self, input: PostProcessInput) -> None:
        match = FOLLOW_UP_RE.search(input.reply_text)
        if not match:
            return
        raw = match.group(1).strip()
        questions = [
            q.strip().lstrip('0123456789.、）) ')
            for q in raw.split('\n')
            if q.strip()
        ][:3]
        if not questions:
            return
        data = get_data_repo().load(input.user_id)
        if input.assistant_node.id in data.nodes:
            data.nodes[input.assistant_node.id].metadata = (
                data.nodes[input.assistant_node.id].metadata or {}
            )
            data.nodes[input.assistant_node.id].metadata["follow_up_questions"] = questions
            get_data_repo().save(input.user_id, data)
            logger.info("Follow-up questions extracted: %d questions", len(questions))


class SourceParser(PostProcessor):
    """来源解析 → 提取 [来源: xxx] 标注 → 写入 discussed_skill_ids"""
    is_blocking = True

    async def process(self, input: PostProcessInput) -> None:
        from app.services.llm.llm_core import parse_sources, _resolve_skill_ids

        _, source_labels = parse_sources(input.reply_text)
        if not source_labels:
            return

        skill_ids = _resolve_skill_ids(source_labels, input.partition_id, input.user_id)
        if not skill_ids:
            return

        data = get_data_repo().load(input.user_id)
        if input.assistant_node.id in data.nodes:
            data.nodes[input.assistant_node.id].discussed_skill_ids = skill_ids
            get_data_repo().save(input.user_id, data)
            logger.info("消息 %s 标注知识点: %s", input.assistant_node.id[:8], skill_ids)

            from app.services.analytics.learning_events import record_event
            from app.schemas.learning_event import EventType
            conv_id = input.conversation.id if input.conversation else None
            for sid in skill_ids:
                record_event(
                    EventType.SKILL_DISCUSSED,
                    user_id=input.user_id,
                    partition_id=input.partition_id,
                    conversation_id=conv_id,
                    skill_ids=[sid],
                )


class SocraticCounter(PostProcessor):
    """苏格拉底追问计数"""
    is_blocking = True

    async def process(self, input: PostProcessInput) -> None:
        data = get_data_repo().load(input.user_id)
        conv = data.conversations.get(input.conversation_id)
        if not conv:
            return
        meta = getattr(conv, 'metadata', None) or {}
        count = meta.get('socratic_question_count', 0)

        stripped = input.reply_text.strip()
        if stripped and (stripped.endswith('?') or stripped.endswith('？')):
            count += 1
        else:
            count = 0

        conv.metadata = meta
        conv.metadata['socratic_question_count'] = count
        get_data_repo().save(input.user_id, data)
        if count >= 3:
            logger.info("Socratic limit: %d consecutive questions in conv %s", count, input.conversation_id[:8])


class ResponseBlockSaver(PostProcessor):
    """回填 response_blocks 的 message_id 并持久化"""
    is_blocking = True

    async def process(self, input: PostProcessInput) -> None:
        if not input.response_blocks:
            return
        data = get_data_repo().load(input.user_id)
        for block in input.response_blocks:
            block.message_id = input.assistant_node.id
            data.response_blocks[block.id] = block
        get_data_repo().save(input.user_id, data)


class CognitiveSyncHook(PostProcessor):
    """对话 → CognitiveNode 联动"""
    is_blocking = False

    async def process(self, input: PostProcessInput) -> None:
        from app.services.knowledge.cognitive_sync import _cognify_dialogue_context

        skill_ids = set()
        for block in input.response_blocks:
            node = getattr(block, 'message_id', None)
            if node:
                data = get_data_repo().load(input.user_id)
                nd = data.nodes.get(node)
                if nd:
                    for sid in getattr(nd, 'discussed_skill_ids', []):
                        skill_ids.add(sid)
        if skill_ids and input.conversation:
            await _cognify_dialogue_context(
                input.user_id, input.conversation, list(skill_ids),
                context_type="lower",
            )


class KnowledgeEvidenceHook(PostProcessor):
    """对话知识证据分析"""
    is_blocking = False

    async def process(self, input: PostProcessInput) -> None:
        from app.services.knowledge.cognitive_sync import _analyze_conversation_evidence
        await _analyze_conversation_evidence(
            input.user_id, input.partition_id,
            input.user_text, input.reply_text,
            conversation_id=input.conversation_id,
        )


class MetaHistoryHook(PostProcessor):
    """消息后处理钩子：元历史 / 分支重命名 / 图谱更新"""
    is_blocking = False

    async def process(self, input: PostProcessInput) -> None:
        get_knowledge_query().post_message_hooks(
            input.user_id, input.partition_id, input.assistant_node,
        )


# ═══════════════════════════════════════════════
# ReplyPipeline
# ═══════════════════════════════════════════════


class ReplyPipeline:
    """回复管线 — 单一入口 invoke()，产出 ReplyEvent 流"""

    def __init__(
        self,
        post_processors: list[PostProcessor] | None = None,
        agent_label: str = AGENT_LABEL,
    ) -> None:
        self._post_processors = post_processors or _default_post_processors()
        self.agent_label = agent_label

    # ── 公开 API ──

    async def invoke(
        self,
        user_id: str,
        partition_id: str,
        user_text: str,
        content_blocks: list[ContentBlock] | None = None,
        conversation_id: str = "",
        pending_quote: dict | None = None,
    ) -> AsyncGenerator[ReplyEvent, None]:
        """流式执行完整回复流程，产出事件序列"""
        try:
            async for event in self._run(
                user_id, partition_id, user_text,
                content_blocks=content_blocks,
                conversation_id=conversation_id,
                pending_quote=pending_quote,
            ):
                yield event
        except Exception as e:
            logger.error("ReplyPipeline failed: %s", e, exc_info=True)
            yield ReplyEvent(type="error", data={"error": str(e)})

    # ── 内部阶段 ──

    async def _run(
        self,
        user_id: str,
        partition_id: str,
        user_text: str,
        content_blocks: list[ContentBlock] | None = None,
        conversation_id: str = "",
        pending_quote: dict | None = None,
    ) -> AsyncGenerator[ReplyEvent, None]:
        # ═══════════════════════════════════════════
        # Stage 1: auto_resolve → context_switch
        # ═══════════════════════════════════════════
        route = await asyncio.to_thread(
            classifier.auto_resolve,
            user_id, user_text,
            current_partition_id=partition_id,
            current_conversation_id=conversation_id,
        )
        if route["should_recommend_switch"]:
            yield ReplyEvent(
                type="context_switch",
                switch_detail=route["switch_detail"],
                data={
                    "switch_detail": route["switch_detail"],
                    "target_partition_id": route.get("target_partition_id", ""),
                    "target_domain_name": route.get("target_domain_name", ""),
                    "target_topic_name": route.get("target_topic_name", ""),
                    "partition_id": partition_id,
                    "conversation_id": conversation_id,
                    "full_path": route.get("full_path", ""),
                },
            )

        # ═══════════════════════════════════════════
        # Stage 2: 存用户消息
        # ═══════════════════════════════════════════
        blocks = content_blocks or [TextBlock(text=user_text)]
        if pending_quote:
            blocks = [
                QuoteBlock(
                    quoted_text=pending_quote.get("quoted_text", ""),
                    source_message_id=pending_quote.get("source_message_id", ""),
                    source_conversation_id=pending_quote.get("source_conversation_id", ""),
                    char_start=pending_quote.get("char_start", 0),
                    char_end=pending_quote.get("char_end", 0),
                ),
                *blocks,
            ]
        user_node = tree_ops.add_message(
            user_id, partition_id, "user", blocks, user_text,
            conversation_id=conversation_id,
        )
        get_knowledge_query().post_message_hooks(user_id, partition_id, user_node)

        # 异步情绪追踪
        try:
            loop = asyncio.get_running_loop()
            if loop.is_running():
                loop.create_task(emotion_analyzer.classify(user_text, user_id))
        except Exception:
            logger.debug("异步情绪分类创建失败", exc_info=True)

        yield ReplyEvent(
            type="user_message",
            message=user_node.model_dump(mode="json"),
        )

        if not conversation_id and user_node.conversation_id:
            conversation_id = user_node.conversation_id
            yield ReplyEvent(
                type="conversation_created",
                data={"conversation_id": conversation_id},
            )

        # ═══════════════════════════════════════════
        # Stage 3: LLM tool loop
        # ═══════════════════════════════════════════
        from app.services.llm.llm_service import llm_service, _parse_tool_calls_response
        from app.services.conversation.context_pipeline import build_llm_messages
        from app.services.llm.tool_repository import get_tool_repository

        enriched_text = user_text
        if pending_quote:
            qt = pending_quote.get("quoted_text", "")
            if qt:
                enriched_text = f"（引用上文：「{qt}」）\n{user_text}"

        data = get_data_repo().load(user_id)
        partition = data.partitions.get(partition_id)
        conversation = _find_conversation(data, partition_id, conversation_id)
        recent = _get_recent_messages(conversation, data, 8)

        llm_messages = await build_llm_messages(
            partition, conversation, recent, enriched_text, user_id,
            agent_label=self.agent_label,
        )
        tools = get_tool_repository().to_llm_schema()

        response_blocks: list[ResponseBlock] = []
        order = 0
        full_reply = ""

        for _round in range(MAX_TOOL_ROUNDS):
            try:
                response_text = await llm_service.generate(
                    messages=llm_messages, task_type="chat",
                    temperature=0.7, max_tokens=2048, tools=tools,
                    user_id=user_id,
                )
            except Exception as e:
                logger.error("LLM tool loop failed at round %d: %s", _round, e)
                full_reply = f"抱歉，生成回复时遇到了问题：{str(e)[:200]}"
                yield ReplyEvent(type="token", content=full_reply)
                break

            tool_calls = _parse_tool_calls_response(response_text)

            if not tool_calls:
                # ── 文本回复：流式 yield tokens，退出 loop ──
                full_reply = response_text
                for chunk in _chunk_text(response_text):
                    yield ReplyEvent(type="token", content=chunk)
                break

            # ── 有 tool_calls：执行工具 ──
            logger.info(
                "LLM tool calls (round %d): %s",
                _round, [tc["function"]["name"] for tc in tool_calls],
            )

            # 追加 assistant tool_call 消息
            llm_messages.append({
                "role": "assistant",
                "content": None,
                "tool_calls": tool_calls,
            })

            for tc in tool_calls:
                tool_name = tc["function"]["name"]
                try:
                    args = json.loads(tc["function"]["arguments"])
                except (json.JSONDecodeError, KeyError):
                    args = {}

                try:
                    tool_block = await tool_executor.execute(
                        tool_name, args, user_id=user_id,
                    )
                    tool_block.order = order
                    response_blocks.append(tool_block)
                    order += 1

                    if tool_name in SLOW_TOOLS:
                        from app.services.common.background_jobs import job_manager
                        await job_manager.submit(
                            user_id=user_id, tool_name=tool_name,
                            params=args, block_id=tool_block.id,
                            partition_id=partition_id,
                            conversation_id=conversation_id,
                        )
                        data.response_blocks[tool_block.id] = tool_block

                    yield ReplyEvent(
                        type="tool_block",
                        block=tool_block.model_dump(mode="json"),
                    )

                    # 追加 tool result 消息
                    from app.services.llm.tool_dispatch import _summarize_tool_result
                    llm_messages.append({
                        "role": "tool",
                        "tool_call_id": tc.get("id", ""),
                        "content": json.dumps({
                            "tool": tool_name,
                            "result": _summarize_tool_result(tool_name, tool_block),
                        }, ensure_ascii=False),
                    })
                except Exception as e:
                    logger.error("Tool %s failed at round %d: %s", tool_name, _round, e)
                    llm_messages.append({
                        "role": "tool",
                        "tool_call_id": tc.get("id", ""),
                        "content": json.dumps({"error": str(e)}),
                    })

        else:
            # 超过 MAX_TOOL_ROUNDS 仍产出工具 → 强行收尾
            logger.warning("Max tool rounds (%d) reached, forcing text reply", MAX_TOOL_ROUNDS)
            full_reply = "已完成上述工具调用，还有什么需要帮助的吗？"
            yield ReplyEvent(type="token", content=full_reply)

        # ═══════════════════════════════════════════
        # Stage 4: PostProcessor 链
        # ═══════════════════════════════════════════
        assistant_node = tree_ops.add_message(
            user_id, partition_id, "assistant",
            [TextBlock(text=full_reply)], full_reply,
            conversation_id=conversation_id,
            agent_label=self.agent_label,
        )

        cleaned_reply = _clean_follow_up(full_reply)
        if cleaned_reply != full_reply:
            tree_ops.update_message_content(user_id, assistant_node.id, cleaned_reply)
            full_reply = cleaned_reply
            data = get_data_repo().load(user_id)
            assistant_node = data.nodes.get(assistant_node.id) or assistant_node

        pp_input = PostProcessInput(
            user_id=user_id,
            partition_id=partition_id,
            user_text=user_text,
            reply_text=full_reply,
            conversation_id=conversation_id,
            assistant_node=assistant_node,
            response_blocks=response_blocks,
            conversation=conversation,
        )
        for processor in self._post_processors:
            try:
                if processor.is_blocking:
                    await processor.process(pp_input)
                else:
                    asyncio.create_task(processor.process(pp_input))
            except Exception:
                logger.debug(
                    "PostProcessor %s failed", type(processor).__name__,
                    exc_info=True,
                )

        # ═══════════════════════════════════════════
        # Stage 5: done
        # ═══════════════════════════════════════════
        yield ReplyEvent(
            type="done",
            data={
                "assistant_message": assistant_node.model_dump(mode="json"),
                "response_blocks": [b.model_dump(mode="json") for b in response_blocks],
                "reply_text": full_reply,
            },
        )


# ═══════════════════════════════════════════════
# 辅助函数
# ═══════════════════════════════════════════════


def _find_conversation(data, partition_id: str, conversation_id: str = ""):
    """查找活跃对话"""
    if conversation_id:
        return data.conversations.get(conversation_id)
    partition = data.partitions.get(partition_id)
    if partition:
        for topic in data.topics.values():
            domain = data.domains.get(topic.domain_id)
            if domain and domain.partition_id == partition_id:
                cid = topic.active_conversation_id
                if cid and cid in data.conversations:
                    return data.conversations[cid]
    return None


def _get_recent_messages(conversation, data, count: int = 8) -> list[TreeNode]:
    """获取最近 N 条消息"""
    if not conversation:
        return []
    messages = []
    for nid in conversation.path[-count:]:
        node = data.nodes.get(nid)
        if node and not node.is_deleted:
            messages.append(node)
    return messages


def _clean_follow_up(text: str) -> str:
    """移除 FOLLOW_UP 标记块"""
    return FOLLOW_UP_RE.sub('', text).strip()


def _chunk_text(text: str, size: int = 5) -> list[str]:
    """将文本按字符拆分，模拟流式输出"""
    return [text[i:i + size] for i in range(0, len(text), size)]


def _default_post_processors() -> list[PostProcessor]:
    return [
        SocraticCounter(),
        FollowUpParser(),
        SourceParser(),
        MetaHistoryHook(),
        ResponseBlockSaver(),
        CognitiveSyncHook(),
        KnowledgeEvidenceHook(),
    ]
