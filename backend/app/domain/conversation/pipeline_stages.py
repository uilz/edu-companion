"""
Pipeline Stages — ReplyPipeline 的阶段组件

Stage Protocol 定义管线阶段的统一接口。每个阶段实现 invoke(ctx) 产出 ReplyEvent 流。
管线的上下文 (PipelineCtx) 在阶段间传递，携带用户输入和阶段产出。

5 个阶段:
  Stage 1 (ClassifyStage): 分类器 → context_switch 推荐
  Stage 2 (SaveMessageStage): 存用户消息 → user_message 事件
  Stage 3 (ToolLoopStage): LLM tool loop → token/tool_calls/block_update
  Stage 4 (PostProcessStage): 后处理器链 → 认知/来源/存储
  Stage 5 (DoneStage): 产出 done 事件

设计原则:
  - 每个阶段可在本地独立测试 (mock 上下游 ctx)
  - Error 传播: 阶段内的异常被上层 ReplyPipeline 捕获，不中止后续阶段
  - 只有 Stage 3 (tool loop) 的异常需要特殊处理 (生成错误回复)
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from uuid import uuid4
from dataclasses import dataclass, field
from typing import Any, AsyncGenerator, Protocol

from app.schemas.conversation import (
    ContentBlock,
    TextBlock,
    ResponseBlock,
    QuoteBlock,
    DirectoryNode,
)
from app.services.common import get_data_repo
from app.services.knowledge.tree_service import tree_ops
from app.services.common.classifier_service import classifier_service
from app.infrastructure.llm.tool_executor import tool_executor, SLOW_TOOLS
from app.services.analytics.emotion_analyzer import emotion_analyzer
from app.domain.knowledge import get_knowledge_query

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════
# 回复事件类型 (共享定义，供 reply_pipeline.py 导入)
# ═══════════════════════════════════════════════


@dataclass
class ReplyEvent:
    """管线产出的事件"""
    type: str
    data: dict = field(default_factory=dict)
    content: str = ""
    block: dict | None = None
    message: dict | None = None
    switch_detail: dict | None = None
    stage: str = ""


# ═══════════════════════════════════════════════
# PostProcessInput (共享定义)
# ═══════════════════════════════════════════════


@dataclass
class PostProcessInput:
    """进入后处理器的数据"""
    user_id: str
    dir_id: str
    user_text: str
    reply_text: str
    conv_id: str
    assistant_node: Any
    response_blocks: list[ResponseBlock]
    conversation: Any = None


# ═══════════════════════════════════════════════
# 费曼模式工具白名单 (共享定义)
# ═══════════════════════════════════════════════

FEYNMAN_ALLOWED_TOOLS = frozenset({
    "rename_conversation",
    "knowledge_search_nodes",
    "knowledge_get_node_context",
    "knowledge_recommend",
})


# ═══════════════════════════════════════════════
# Stage Protocol & Context
# ═══════════════════════════════════════════════


@dataclass
class ToolResult:
    """工具结果提交 — 用于用户对 ask_question 的答案作为 tool result 注入"""
    tool_call_id: str
    answers: str  # 用户回答文本


@dataclass
class PipelineCtx:
    """管线上下文 — 在阶段间传递输入参数和产出。可变字段由阶段写入。"""
    user_id: str
    dir_id: str
    user_text: str
    conv_id: str = ""
    pending_quote: dict | None = None
    knowledge_node_id: str | None = None
    content_blocks: list[ContentBlock] | None = None
    agent_label: str = "tutor"
    tool_result: ToolResult | None = None  # 工具结果提交（非空时触发注入）

    # Stage 产出 (可变)
    assistant_node: Any = None
    response_blocks: list[ResponseBlock] = field(default_factory=list)
    stream_content_blocks: list[dict] = field(default_factory=list)
    full_reply: str = ""
    conversation: Any = None  # DirectoryNode
    _suspended: bool = False  # 管线是否挂起等待用户回答
    _cancelled: bool = False  # 管线是否被用户中断（stop）


class PipelineStage(Protocol):
    """管线阶段接口。invoke 产出 ReplyEvent 流，通过 ctx 读写上下文。"""
    name: str

    async def invoke(self, ctx: PipelineCtx) -> AsyncGenerator[ReplyEvent, None]:
        ...


# ═══════════════════════════════════════════════
# Stage 1: 分类器
# ═══════════════════════════════════════════════


class ClassifyStage:
    """分类器阶段 — 对首条消息运行分类器，产出 context_switch 推荐。"""
    name = "classify"

    async def invoke(self, ctx: PipelineCtx) -> AsyncGenerator[ReplyEvent, None]:
        yield ReplyEvent(type="stage", stage="classifying")
        _stage1_route: dict | None = None
        # 当前分类器为桩，未启用
        if _stage1_route and _stage1_route.get("should_recommend_switch"):
            yield ReplyEvent(
                type="context_switch",
                switch_detail=_stage1_route["switch_detail"],
                data={
                    "switch_detail": _stage1_route["switch_detail"],
                    "target_dir_id": _stage1_route.get("target_dir_id", ""),
                    "target_domain_name": _stage1_route.get("target_domain_name", ""),
                    "target_topic_name": _stage1_route.get("target_topic_name", ""),
                    "dir_id": ctx.dir_id,
                    "conv_id": ctx.conv_id,
                    "full_path": _stage1_route.get("full_path", ""),
                },
            )


# ═══════════════════════════════════════════════
# Stage 2: 存用户消息
# ═══════════════════════════════════════════════


class SaveMessageStage:
    """存用户消息阶段 — 持久化用户消息 + 情绪追踪 + 元历史钩子。"""
    name = "save_message"

    async def invoke(self, ctx: PipelineCtx) -> AsyncGenerator[ReplyEvent, None]:
        blocks = ctx.content_blocks or [TextBlock(text=ctx.user_text)]
        if ctx.pending_quote:
            blocks = [
                QuoteBlock(
                    quoted_text=ctx.pending_quote.get("quoted_text", ""),
                    source_message_id=ctx.pending_quote.get("source_message_id", ""),
                    source_conv_id=ctx.pending_quote.get("source_conv_id", ""),
                    char_start=ctx.pending_quote.get("char_start", 0),
                    char_end=ctx.pending_quote.get("char_end", 0),
                ),
                *blocks,
            ]
        user_node = tree_ops.add_message(
            ctx.user_id, ctx.dir_id, "user", blocks, ctx.user_text,
            conv_id=ctx.conv_id,
        )
        get_knowledge_query().post_message_hooks(ctx.user_id, ctx.dir_id, user_node)

        # Update last_active timestamp
        _uid = getattr(user_node, "directory_id", None) or getattr(user_node, "conv_id", None) or ctx.conv_id
        if _uid:
            _data = get_data_repo().load(ctx.user_id)
            _conv = _data.directory_nodes.get(_uid)
            if _conv and _conv.node_type == "conv":
                _conv.metadata["last_active"] = time.time()
                _conv.updated_at = time.time()
                get_data_repo().save(ctx.user_id, _data)

        # 异步情绪追踪
        try:
            loop = asyncio.get_running_loop()
            if loop.is_running():
                loop.create_task(emotion_analyzer.classify(ctx.user_text, ctx.user_id))
        except Exception:
            logger.debug("异步情绪分类创建失败", exc_info=True)

        yield ReplyEvent(
            type="user_message",
            message=user_node.model_dump(mode="json"),
        )

        if not ctx.conv_id:
            new_conv_id = getattr(user_node, "directory_id", None) or getattr(user_node, "conv_id", None)
            if new_conv_id:
                ctx.conv_id = new_conv_id
                yield ReplyEvent(
                    type="conversation_created",
                    data={"conv_id": ctx.conv_id},
                )


# ═══════════════════════════════════════════════
# 挂起管线注册表 (方案A: 一次LLM调用的挂起/恢复模式)
# ═══════════════════════════════════════════════

@dataclass
class _SuspendedLoopState:
    """挂起的工具循环状态 — 等待用户回答 ask_question 后恢复"""
    llm_messages: list[dict]
    tools: list[dict]
    _round: int
    ctx: PipelineCtx  # 浅拷贝的管线上下文（含 response_blocks/stream_content_blocks/full_reply）


_suspended_states: dict[str, _SuspendedLoopState] = {}  # conv_id → state


def _suspend_loop(conv_id: str, state: _SuspendedLoopState) -> None:
    """保存挂起状态"""
    _suspended_states[conv_id] = state


def _pop_suspended(conv_id: str) -> _SuspendedLoopState | None:
    """取出并清除挂起状态"""
    return _suspended_states.pop(conv_id, None)


def _has_suspended(conv_id: str) -> bool:
    """检查是否有挂起的管线"""
    return conv_id in _suspended_states


# ═══════════════════════════════════════════════
# Stage 3: LLM Tool Loop
# ═══════════════════════════════════════════════


class ToolLoopStage:
    """LLM tool loop 阶段 — 真实流式文本回复 + 工具调用执行循环。

    支持挂起/恢复：当 LLM 调用 ask_question 工具时，循环挂起等待用户回答，
    用户提交答案后恢复同一循环继续执行。一次管线调用 = 一次 LLM 计费周期。
    """
    name = "tool_loop"

    async def invoke(self, ctx: PipelineCtx) -> AsyncGenerator[ReplyEvent, None]:
        yield ReplyEvent(type="stage", stage="thinking")
        from app.infrastructure.llm.llm_service import llm_service
        from app.domain.conversation.context_pipeline import build_llm_messages
        from app.infrastructure.llm.tool_repository import get_tool_repository, TOOL_DISPLAY_NAMES, SUSPENDING_TOOLS
        from app.infrastructure.llm.tool_dispatch import _summarize_tool_result

        # ── 恢复模式：从挂起状态继续 ──
        resume_state = getattr(ctx, '_resume_state', None)
        if resume_state is not None:
            llm_messages = resume_state["llm_messages"]
            tools = resume_state["tools"]
            _round = resume_state["_round"]
            order = len(ctx.response_blocks)  # 继续累加 order
            logger.info("ToolLoopStage resume: round=%d, conv=%s", _round, ctx.conv_id[:8])
        else:
            # ── 正常模式：从零构建上下文 ──
            enriched_text = ctx.user_text
            if ctx.pending_quote:
                qt = ctx.pending_quote.get("quoted_text", "")
                if qt:
                    enriched_text = f"（引用上文：「{qt}」）\n{ctx.user_text}"

            data = get_data_repo().load(ctx.user_id)
            partition = data.directory_nodes.get(ctx.dir_id)
            ctx.conversation = _find_conversation(data, ctx.dir_id, ctx.conv_id)
            recent = _get_recent_messages(ctx.conversation, data, 8)

            llm_messages = await build_llm_messages(
                partition, ctx.conversation, recent, enriched_text, ctx.user_id,
                agent_label=ctx.agent_label,
                tool_result=ctx.tool_result,
            )

            # 知识树探索会话上下文注入
            if ctx.knowledge_node_id:
                _inject_knowledge_tree_context(llm_messages, ctx.user_id, ctx.knowledge_node_id)

            tools = get_tool_repository().to_llm_schema()

            # 费曼模式工具白名单
            conv_mode = "tutor"
            if ctx.conversation:
                conv_mode = ctx.conversation.metadata.get("mode", "tutor")
            if conv_mode == "feynman":
                tools = [t for t in tools if t["function"]["name"] in FEYNMAN_ALLOWED_TOOLS]

            # 首条消息 AI 自动命名提示
            if ctx.conversation and len(ctx.conversation.conv_message_ids) <= 2:
                llm_messages.append({
                    "role": "system",
                    "content": "这是该对话的第一条消息。请使用 rename_conversation 工具为当前对话设置一个好标题（2-8字），"
                               "概括用户问题的核心主题。这样用户后续能快速定位此对话。",
                })

            ctx.response_blocks = []
            order = 0
            ctx.full_reply = ""
            ctx.stream_content_blocks = []
            _round = 0

        while True:
            tool_calls = None
            try:
                async for ev in llm_service.generate_stream_with_tools(
                    messages=llm_messages, task_type="chat",
                    temperature=0.7, max_tokens=2048, tools=tools,
                    user_id=ctx.user_id,
                ):
                    if ev["type"] == "token":
                        ctx.full_reply += ev["content"]
                        yield ReplyEvent(type="token", content=ev["content"])
                        _append_block(ctx.stream_content_blocks, {"type": "text", "text": ev["content"]})
                    elif ev["type"] == "reasoning":
                        yield ReplyEvent(type="reasoning", content=ev["content"])
                        _append_block(ctx.stream_content_blocks, {"type": "reasoning", "text": ev["content"], "status": "streaming"})
                    elif ev["type"] == "tool_calls":
                        tool_calls = ev["tool_calls"]
            except Exception as e:
                logger.error("LLM tool loop failed at round %d: %s", _round, e)
                ctx.full_reply = f"抱歉，生成回复时遇到了问题：{str(e)[:200]}"
                yield ReplyEvent(type="token", content=ctx.full_reply)
                break

            if not tool_calls:
                break

            # 执行工具
            logger.info(
                "LLM tool calls (round %d): %s",
                _round, [tc["function"]["name"] for tc in tool_calls],
            )

            # 将需要挂起的工具（如 ask_question）与普通工具分离
            suspending_tcs = [tc for tc in tool_calls if tc["function"]["name"] in SUSPENDING_TOOLS]
            other_tcs = [tc for tc in tool_calls if tc["function"]["name"] not in SUSPENDING_TOOLS]

            # 先 yield tool_calls 事件（前端展示用，显示全部）
            yield ReplyEvent(
                type="tool_calls",
                data={
                    "tool_calls": [
                        _build_tool_call_display(tc, _round, TOOL_DISPLAY_NAMES)
                        for tc in tool_calls
                    ],
                    "conv_id": ctx.conv_id or "",
                },
            )

            # ── 处理非 ask_question 的工具（正常执行）──
            if other_tcs:
                llm_messages.append({
                    "role": "assistant", "content": None,
                    "tool_calls": other_tcs,
                })
                for tc in other_tcs:
                    yield ReplyEvent(
                        type="tool_call_update",
                        data={"tool_call_id": tc.get("id", ""), "status": "running"},
                    )
                    tool_name = tc["function"]["name"]
                    try:
                        args = json.loads(tc["function"]["arguments"])
                    except (json.JSONDecodeError, KeyError):
                        args = {}

                    try:
                        tool_block = await _execute_single_tool(
                            tool_name, args, ctx, tc, order,
                        )
                        if tool_block:
                            ctx.response_blocks.append(tool_block)
                            order += 1

                            if tool_name in SLOW_TOOLS:
                                from app.services.common.background_jobs import job_manager
                                await job_manager.submit(
                                    user_id=ctx.user_id, tool_name=tool_name,
                                    params=args, block_id=tool_block.id,
                                    dir_id=ctx.dir_id, conv_id=ctx.conv_id,
                                )

                            yield ReplyEvent(
                                type="tool_block",
                                block=tool_block.model_dump(mode="json"),
                                data={"tool_call_id": tc.get("id", "")},
                            )
                            _append_tool_to_stream(ctx.stream_content_blocks, tool_block, tool_name, TOOL_DISPLAY_NAMES)
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

            # ── 处理需要挂起的工具（等待外部输入后恢复循环）──
            if suspending_tcs:
                tc = suspending_tcs[0]  # 每次只处理一个挂起工具
                tool_name = tc["function"]["name"]
                try:
                    args = json.loads(tc["function"]["arguments"])
                except (json.JSONDecodeError, KeyError):
                    args = {}

                yield ReplyEvent(
                    type="tool_call_update",
                    data={"tool_call_id": tc.get("id", ""), "status": "running"},
                )

                tool_block = await _execute_single_tool(
                    tool_name, args, ctx, tc, order,
                )
                if tool_block:
                    ctx.response_blocks.append(tool_block)
                    order += 1
                    yield ReplyEvent(
                        type="tool_block",
                        block=tool_block.model_dump(mode="json"),
                        data={"tool_call_id": tc.get("id", "")},
                    )
                    _append_tool_to_stream(ctx.stream_content_blocks, tool_block, tool_name, TOOL_DISPLAY_NAMES)

                # 只追加 assistant(tool_calls)，不追加 tool result → 挂起等待用户
                llm_messages.append({
                    "role": "assistant", "content": ctx.full_reply or None,
                    "tool_calls": [tc],
                })

                _suspend_loop(ctx.conv_id, _SuspendedLoopState(
                    llm_messages=llm_messages,
                    tools=tools,
                    _round=_round,
                    ctx=ctx,
                ))
                ctx._suspended = True
                logger.info("ToolLoopStage suspended for %s, conv=%s", tool_name, ctx.conv_id[:8])
                yield ReplyEvent(
                    type="pipeline_suspended",
                    data={"tool_call_id": tc.get("id", "")},
                )
                return

            _round += 1


# ═══════════════════════════════════════════════
# Stage 4: PostProcess
# ═══════════════════════════════════════════════


class PostProcessStage:
    """后处理阶段 — 持久化 assistant 消息 + 执行 blocking 处理器链。"""
    name = "post_process"

    def __init__(self, processors: list | None = None) -> None:
        from app.domain.conversation.reply_pipeline import _default_post_processors
        self._processors = processors or _default_post_processors()

    async def invoke(self, ctx: PipelineCtx) -> AsyncGenerator[ReplyEvent, None]:

        # 标记 reasoning 为 done
        for b in ctx.stream_content_blocks:
            if b.get("type") == "reasoning" and b.get("status") == "streaming":
                b["status"] = "done"

        ctx.assistant_node = tree_ops.add_message(
            ctx.user_id, ctx.dir_id, "assistant",
            ctx.stream_content_blocks, ctx.full_reply,
            conv_id=ctx.conv_id,
            agent_label=ctx.agent_label,
        )

        pp_input = PostProcessInput(
            user_id=ctx.user_id,
            dir_id=ctx.dir_id,
            user_text=ctx.user_text,
            reply_text=ctx.full_reply,
            conv_id=ctx.conv_id,
            assistant_node=ctx.assistant_node,
            response_blocks=ctx.response_blocks,
            conversation=ctx.conversation,
        )

        for processor in self._processors:
            try:
                if processor.is_blocking:
                    await processor.process(pp_input)
                else:
                    asyncio.create_task(processor.process(pp_input))
            except Exception as e:
                logger.debug("PostProcessor %s failed", type(processor).__name__, exc_info=True)
                self._report_error(type(processor).__name__, ctx.user_id, e, ctx.conv_id, ctx.dir_id)

        yield ReplyEvent(type="stage", stage="post_process")

    def _report_error(self, processor_name: str, user_id: str, exc: Exception,
                      conv_id: str, dir_id: str) -> None:
        try:
            from app.services.admin.error_service import admin_error_service
            admin_error_service.report_error(
                source="post_processor",
                processor_name=processor_name,
                user_id=user_id,
                exception=exc,
                context={"conv_id": conv_id, "dir_id": dir_id},
            )
        except Exception:
            pass


# ═══════════════════════════════════════════════
# Stage 5: Done
# ═══════════════════════════════════════════════


class DoneStage:
    """Done 阶段 — 产出管线完成事件，携带 assistant 消息和 response_blocks。"""
    name = "done"

    async def invoke(self, ctx: PipelineCtx) -> AsyncGenerator[ReplyEvent, None]:
        data: dict = {
            "assistant_message": ctx.assistant_node.model_dump(mode="json") if ctx.assistant_node else {},
            "response_blocks": [b.model_dump(mode="json") for b in ctx.response_blocks],
            "reply_text": ctx.full_reply,
        }
        if ctx._cancelled:
            data["cancelled"] = True
        yield ReplyEvent(type="done", data=data)


# ═══════════════════════════════════════════════
# Tool Loop 辅助函数
# ═══════════════════════════════════════════════


def _append_block(blocks: list, block: dict) -> None:
    """同类型相邻则合并 text，否则追加"""
    if blocks and blocks[-1].get("type") == block.get("type"):
        if block.get("type") in ("reasoning", "text"):
            blocks[-1]["text"] += block.get("text", "")
        return
    blocks.append(block)


def _build_tool_call_display(tc: dict, round_num: int, display_names: dict) -> dict:
    return {
        "tool_call_id": tc.get("id", ""),
        "tool_name": tc["function"]["name"],
        "arguments": json.loads(tc["function"]["arguments"]) if isinstance(tc["function"]["arguments"], str) else tc["function"]["arguments"],
        "tool_round": round_num,
        **display_names.get(tc["function"]["name"], {}),
    }


async def _execute_single_tool(
    tool_name: str, args: dict, ctx: PipelineCtx,
    tc: dict, order: int,
) -> ResponseBlock | None:
    """执行单个工具调用"""
    if tool_name == "rename_conversation":
        new_name = args.get("name", "")
        if new_name:
            try:
                tree_ops.rename_node(ctx.user_id, ctx.conv_id, new_name)
                return ResponseBlock(
                    id=f"rename_{uuid4().hex[:8]}",
                    type="rename_conversation", status="success",
                    content={"name": new_name},
                    conv_id=ctx.conv_id, dir_id=ctx.dir_id,
                )
            except Exception as e:
                return ResponseBlock(
                    id=f"rename_{uuid4().hex[:8]}",
                    type="rename_conversation", status="failed",
                    content={"error": str(e)},
                    conv_id=ctx.conv_id, dir_id=ctx.dir_id,
                )
        return ResponseBlock(
            id=f"rename_{uuid4().hex[:8]}",
            type="rename_conversation", status="failed",
            content={"error": "缺少 name 参数"},
            conv_id=ctx.conv_id, dir_id=ctx.dir_id,
        )

    tool_block = await tool_executor.execute(tool_name, args, user_id=ctx.user_id)
    tool_block.order = order
    tool_block.tool_name = tool_name
    tool_block.conv_id = ctx.conv_id
    tool_block.dir_id = ctx.dir_id

    # 为 ask_question 块持久化 tool_call_id，便于后续答案提交作为 tool result
    if tool_name == "ask_question" and tc.get("id"):
        content = tool_block.content or {}
        content["tool_call_id"] = tc["id"]
        tool_block.content = content

    return tool_block


def _append_tool_to_stream(stream_blocks: list, tool_block: ResponseBlock,
                           tool_name: str, display_names: dict) -> None:
    """将 tool block 追加到流式 content_blocks"""
    tn_display = display_names.get(tool_name, {})
    stream_blocks.append({
        "type": "tool",
        "tool_call_id": getattr(tool_block, "id", "") or "",
        "tool_name": tool_name,
        "display_name": tn_display.get("zh", tool_name),
        "icon": tn_display.get("icon", "🔧"),
        "arguments": {},
        "status": "done" if tool_block.status in ("success", "ready") else "error",
        "result_block_type": getattr(tool_block, "type", "") or getattr(tool_block, "block_type", None),
        "result_content": getattr(tool_block, "content", None),
        "conv_id": getattr(tool_block, "conv_id", "") or "",
        "dir_id": getattr(tool_block, "dir_id", "") or "",
        "error": getattr(tool_block, "status", None) == "failed" and getattr(tool_block, "content", {}).get("error", "") or None,
        "tool_round": getattr(tool_block, "order", 0),
    })


def _find_conversation(data, dir_id: str, conv_id: str = ""):
    """查找活跃对话"""
    if conv_id:
        return data.directory_nodes.get(conv_id)
    convs = sorted(
        (dn for dn in data.directory_nodes.values()
         if dn.node_type == "conv" and dn.parent_id == dir_id),
        key=lambda x: x.updated_at, reverse=True,
    )
    return convs[0] if convs else None


def _get_recent_messages(conversation, data, count: int = 8) -> list:
    """获取最近 N 条消息"""
    if not conversation:
        return []
    messages = []
    for nid in conversation.conv_message_ids[-count:]:
        node = data.nodes.get(nid)
        if node and not node.is_deleted:
            messages.append(node)
    return messages


def _inject_knowledge_tree_context(llm_messages: list, user_id: str, knowledge_node_id: str) -> None:
    """注入知识树探索上下文到 LLM system prompt"""
    try:
        from app.services.knowledge_tree.knowledge_node_service import kn_svc
        bound_node = kn_svc.get_node(user_id, knowledge_node_id)
        if bound_node:
            scope_ids = _get_descendant_ids(user_id, knowledge_node_id)
            scope_labels = {}
            for sid in scope_ids:
                sn = kn_svc.get_node(user_id, sid)
                if sn:
                    scope_labels[sid] = sn.label
            ctx_prompt = (
                f"## 当前知识树探索上下文\n"
                f"- 绑定节点: {bound_node.label}（ID: {knowledge_node_id}）\n"
                f"- 层级: {bound_node.level}\n"
                f"- 描述: {bound_node.brief or '无'}\n"
                f"- 作用域内节点（你可通过 knowledge_* 工具操作）:\n"
                + "\n".join(f"  [{sid}] {label}" for sid, label in scope_labels.items()) +
                "\n\n## 严格规则\n"
                f"1. 你只能编辑、扩充、删除上列作用域内的节点。\n"
                f"2. 如果用户提及作用域外的节点，告知其不在当前探索范围内。\n"
                f"3. 使用 knowledge_* 工具来执行操作，不要用 [ACTION:] 标记。\n"
                f"4. 如果用户完成探索，可以建议他们回到知识树视图查看变更。\n"
            )
            llm_messages.insert(0, {"role": "system", "content": ctx_prompt})
    except Exception as e:
        logger.debug("知识树上下文注入失败: %s", e)


def _get_descendant_ids(user_id: str, node_id: str) -> list[str]:
    """获取节点的所有子孙节点 ID"""
    try:
        from app.services.knowledge_tree.knowledge_node_service import kn_svc
        result = [node_id]
        children = kn_svc.get_children(user_id, node_id)
        for child in children:
            result.extend(_get_descendant_ids(user_id, child.id))
        return result
    except Exception:
        return [node_id]
