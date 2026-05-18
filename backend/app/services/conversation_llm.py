"""
对话系统 LLM 服务
基于树结构构建上下文，调用 LLM 生成回复
支持多模态响应块（ResponseBlock）集成
"""

from __future__ import annotations

import logging
from typing import AsyncGenerator

from app.schemas.conversation import (
    ContentBlock,
    TextBlock,
    TreeNode,
    Partition,
    Branch,
    ResponseBlock,
)
from app.services.llm_service import llm_service
from app.services.storage import storage
from app.services.tree_ops import tree_ops
from app.services.tool_executor import tool_executor, predict_tools, SLOW_TOOLS

logger = logging.getLogger(__name__)


# P0: Post-message hooks (meta history + branch auto-rename)
def _p0_post_message_hooks(user_id: str, partition_id: str, node: TreeNode) -> None:
    """消息存储后的P0钩子：异步写元历史 + 触发分支命名/摘要"""
    import asyncio
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            from app.services.meta_history import write_to_meta_history
            loop.create_task(write_to_meta_history(user_id, node))
            
            data = storage.load(user_id)
            branch = data.branches.get(node.branch_id) if node.branch_id else None
            if branch:
                msg_count = len(branch.path)
                from app.services.branch_summarizer import (
                    try_auto_rename_branch, generate_branch_summary, update_partition_context,
                )
                new_name = try_auto_rename_branch(user_id, node.branch_id, msg_count)
                if new_name:
                    branch.name = new_name
                if msg_count >= 10 and msg_count % 10 == 0:
                    generate_branch_summary(user_id, node.branch_id)
                if msg_count % 5 == 0:
                    update_partition_context(user_id, partition_id)
    except Exception:
        logger.debug("P0 hooks skipped")


# ── System Prompt ──\n
SYSTEM_PROMPT = """你是智能伴学助手"小智"。你的角色是帮助学生学习，特点：

1. 用通俗易懂的语言解释概念
2. 适当使用苏格拉底式提问引导思考
3. 涉及数学公式时使用 LaTeX 格式（$...$ 行内，$$...$$ 块级）
4. 回复简洁但完整，每次回复控制在合理长度
5. 用中文回复，适当使用 emoji
6. 如果涉及代码，使用代码块格式"""


def _build_context_messages(
    partition: Partition,
    branch: Branch,
    recent_messages: list[TreeNode],
    user_text: str,
) -> list[dict[str, str]]:
    """
    构建发给 LLM 的消息列表。
    使用紧凑格式节省 token。
    """
    messages: list[dict[str, str]] = []

    # 系统提示
    system_content = SYSTEM_PROMPT

    # P1: 注入练习上下文
    try:
        from app.services.practice_integrator import inject_practice_context
        practice_ctx = inject_practice_context(user_id, partition.id)
        if practice_ctx:
            system_content += f"\n\n{practice_ctx}"
    except Exception:
        pass

    # P2: 检测练习回顾查询，注入回顾数据
    try:
        from app.services.practice_recall import practice_recall
        if practice_recall.is_recall_query(user_text):
            from app.services.storage import storage as _storage
            from app.api.practice import _sessions as _p_sessions
            recall_sessions = list(_p_sessions.values())
            if recall_sessions:
                recall_text = practice_recall.generate_recall(
                    sessions=recall_sessions,
                    days=7,
                    subject_filter=partition.subject or "",
                )
                system_content += f"\n\n[练习回顾]\n{recall_text}\n\n请在回复中自然地引用这些练习数据来回答用户。"
    except Exception:
        pass

    # P2: 上下文感知练习选题建议
    try:
        from app.services.context_trigger import context_trigger
        from app.services.storage import storage as _storage2
        data = _storage2.load(user_id)
        if branch:
            recent_msgs = []
            for nid in branch.path[-5:]:
                node = data.nodes.get(nid)
                if node and not node.is_deleted:
                    recent_msgs.append(node)
            ctx = context_trigger.trigger(
                user_id=user_id,
                branch=branch,
                recent_messages=recent_msgs,
            )
            system_content += f"\n\n[选题建议] 当前对话主题涉及: {ctx['skill_ids']}, Bloom: {ctx['bloom_level']}, 推荐难度: {ctx['difficulty']:.2f}"
            if ctx.get('confused'):
                system_content += ", ⚠️ 检测到困惑信号"
    except Exception:
        pass

    # 添加分区上下文
    if partition.context_summary:
        system_content += f"\n\n当前分区：{partition.name}"
        system_content += f"\n分区摘要：{partition.context_summary}"

    messages.append({"role": "system", "content": system_content})

    # 添加历史消息（最多最近8条）
    for msg in recent_messages[-8:]:
        if msg.is_deleted:
            continue
        # 提取文本内容
        text_parts = []
        for block in msg.content_blocks:
            if isinstance(block, TextBlock):
                text_parts.append(block.text)
            elif hasattr(block, "text"):
                text_parts.append(block.text)
        text = " ".join(text_parts) if text_parts else "[媒体内容]"

        # 截断过长的消息
        if len(text) > 500:
            text = text[:500] + "..."

        role = msg.role if msg.role in ("user", "assistant") else "assistant"
        messages.append({"role": role, "content": text})

    # 添加当前用户消息
    messages.append({"role": "user", "content": user_text})

    return messages


async def generate_reply(
    user_id: str,
    partition_id: str,
    user_text: str,
) -> str:
    """
    生成助手回复（非流式）。
    1. 加载分区上下文
    2. 构建消息列表
    3. 调用 LLM
    4. 返回完整回复
    """
    data = storage.load(user_id)
    partition = data.partitions.get(partition_id)
    if not partition:
        raise ValueError(f"Partition {partition_id} not found")

    branch = data.branches.get(partition.active_branch_id)
    if not branch:
        raise ValueError(f"Active branch not found")

    # 获取最近消息
    recent_messages = []
    for nid in branch.path[-8:]:
        node = data.nodes.get(nid)
        if node and not node.is_deleted:
            recent_messages.append(node)

    # 构建上下文
    llm_messages = _build_context_messages(partition, branch, recent_messages, user_text)

    # 调用 LLM
    reply = await llm_service.generate(
        messages=llm_messages,
        task_type="chat",
        temperature=0.7,
        max_tokens=2048,
    )

    return reply


async def generate_reply_with_tools(
    user_id: str,
    partition_id: str,
    user_text: str,
) -> list[ResponseBlock]:
    """
    生成助手回复，集成工具调用。
    返回 ResponseBlock 列表：第一个是文本回复，后续是工具结果块。
    """
    data = storage.load(user_id)
    partition = data.partitions.get(partition_id)
    if not partition:
        raise ValueError(f"Partition {partition_id} not found")

    branch = data.branches.get(partition.active_branch_id)
    if not branch:
        raise ValueError(f"Active branch not found")

    # 获取最近消息
    recent_messages = []
    for nid in branch.path[-8:]:
        node = data.nodes.get(nid)
        if node and not node.is_deleted:
            recent_messages.append(node)

    # 意图预判
    detected_tools = predict_tools(user_text)
    logger.info("Detected tools: %s for text: %s", detected_tools, user_text[:50])

    # 构建上下文
    llm_messages = _build_context_messages(partition, branch, recent_messages, user_text)

    response_blocks: list[ResponseBlock] = []
    order = 0

    if detected_tools:
        # 注入工具定义给 LLM
        tools = tool_executor.get_tools_for_llm(detected_tools)
        if tools:
            llm_messages.append({
                "role": "system",
                "content": f"你可以使用以下工具来辅助回答：{[t['function']['name'] for t in tools]}。"
                           "如果用户请求需要工具支持，请调用相应的工具。"
            })

        # 先调用 LLM 获取文本回复
        try:
            reply = await llm_service.generate(
                messages=llm_messages,
                task_type="chat",
                temperature=0.7,
                max_tokens=2048,
            )
        except Exception as e:
            logger.error("LLM generation failed: %s", e)
            reply = "抱歉，生成回复时遇到了问题。"

        # 创建文本 ResponseBlock
        text_block = ResponseBlock(
            type="text",
            status="ready",
            content={"text": reply},
            order=order,
        )
        response_blocks.append(text_block)
        order += 1

        # 执行工具
        for tool_name in detected_tools:
            tool_block = await tool_executor.execute(tool_name, {"query": user_text, "subject": user_text})

            # 补充工具参数（基于用户输入）
            if tool_name == "search_bilibili":
                tool_block = await tool_executor.execute(tool_name, {"query": user_text, "limit": 3})
            elif tool_name == "generate_practice":
                tool_block = await tool_executor.execute(tool_name, {
                    "subject": "通用",
                    "knowledge_point": user_text[:50],
                    "difficulty": "进阶",
                    "count": 1,
                })
            elif tool_name == "generate_image":
                tool_block = await tool_executor.execute(tool_name, {"prompt": user_text})
            elif tool_name == "generate_mindmap":
                tool_block = await tool_executor.execute(tool_name, {"topic": user_text, "depth": 3})
            elif tool_name == "generate_document":
                tool_block = await tool_executor.execute(tool_name, {"topic": user_text, "format": "markdown"})

            tool_block.order = order
            response_blocks.append(tool_block)
            order += 1

            # 慢任务：提交后台作业
            if tool_name in SLOW_TOOLS:
                from app.services.background_jobs import job_manager
                job = await job_manager.submit(
                    user_id=user_id,
                    tool_name=tool_name,
                    params=tool_block.content.get("params", {}),
                    block_id=tool_block.id,
                    partition_id=partition_id,
                    branch_id=branch.id if branch else "",
                )
                # 存储 ResponseBlock
                data.response_blocks[tool_block.id] = tool_block
                storage.save(user_id, data)
    else:
        # 无工具调用，纯文本回复
        try:
            reply = await llm_service.generate(
                messages=llm_messages,
                task_type="chat",
                temperature=0.7,
                max_tokens=2048,
            )
        except Exception as e:
            logger.error("LLM generation failed: %s", e)
            reply = "抱歉，生成回复时遇到了问题。"

        text_block = ResponseBlock(
            type="text",
            status="ready",
            content={"text": reply},
            order=0,
        )
        response_blocks.append(text_block)

    # 存储所有 ResponseBlocks
    data = storage.load(user_id)
    for block in response_blocks:
        data.response_blocks[block.id] = block
    storage.save(user_id, data)

    return response_blocks


async def generate_reply_stream(
    user_id: str,
    partition_id: str,
    user_text: str,
) -> AsyncGenerator[str, None]:
    """
    生成助手回复（流式）。
    逐 token 产出回复文本。
    """
    data = storage.load(user_id)
    partition = data.partitions.get(partition_id)
    if not partition:
        raise ValueError(f"Partition {partition_id} not found")

    branch = data.branches.get(partition.active_branch_id)
    if not branch:
        raise ValueError(f"Active branch not found")

    # 获取最近消息
    recent_messages = []
    for nid in branch.path[-8:]:
        node = data.nodes.get(nid)
        if node and not node.is_deleted:
            recent_messages.append(node)

    # 构建上下文
    llm_messages = _build_context_messages(partition, branch, recent_messages, user_text)

    # 流式调用 LLM
    async for chunk in llm_service.generate_stream(
        messages=llm_messages,
        task_type="chat",
        temperature=0.7,
        max_tokens=2048,
    ):
        yield chunk


async def send_and_reply(
    user_id: str,
    partition_id: str,
    user_text: str,
    content_blocks: list[ContentBlock] | None = None,
) -> dict:
    """
    完整流程：存用户消息 → 生成回复（含工具） → 存助手消息。
    返回两条消息和 response_blocks。
    """
    # 1. 存用户消息
    blocks = content_blocks or [TextBlock(text=user_text)]
    user_node = tree_ops.add_message(
        user_id, partition_id, "user", blocks, user_text
    )

    # P0: 异步写入元历史 + 触发分支自动命名
    _p0_post_message_hooks(user_id, partition_id, user_node)

    # 2. 生成回复（含工具调用）
    response_blocks = await generate_reply_with_tools(user_id, partition_id, user_text)

    # 提取文本内容用于存储助手消息
    text_parts = []
    for block in response_blocks:
        if block.type == "text":
            text_parts.append(block.content.get("text", ""))
    reply_text = "\n\n".join(text_parts) if text_parts else ""

    # 3. 存助手消息
    reply_blocks = [TextBlock(text=reply_text)] if reply_text else [TextBlock(text="[工具响应]")]
    assistant_node = tree_ops.add_message(
        user_id, partition_id, "assistant", reply_blocks, reply_text
    )

    # P0: 异步写入助手消息的元历史
    _p0_post_message_hooks(user_id, partition_id, assistant_node)

    return {
        "user_message": user_node,
        "assistant_message": assistant_node,
        "partition_id": partition_id,
        "response_blocks": [b.model_dump() for b in response_blocks],
    }


async def send_and_reply_stream(
    user_id: str,
    partition_id: str,
    user_text: str,
    content_blocks: list[ContentBlock] | None = None,
) -> AsyncGenerator[dict, None]:
    """
    完整流程（流式）：存用户消息 → 流式生成回复 → 存助手消息。
    产出事件：{"type": "token", "content": ...} / {"type": "done", "assistant_message": ...}
    """
    # 1. 存用户消息
    blocks = content_blocks or [TextBlock(text=user_text)]
    user_node = tree_ops.add_message(
        user_id, partition_id, "user", blocks, user_text
    )

    # P0: async meta history
    _p0_post_message_hooks(user_id, partition_id, user_node)

    yield {"type": "user_message", "message": user_node}

    # 2. 流式生成回复
    full_reply = ""
    async for chunk in generate_reply_stream(user_id, partition_id, user_text):
        full_reply += chunk
        yield {"type": "token", "content": chunk}

    # 3. 存助手消息
    reply_blocks = [TextBlock(text=full_reply)]
    assistant_node = tree_ops.add_message(
        user_id, partition_id, "assistant", reply_blocks, full_reply
    )

    # P0: async meta history for assistant
    _p0_post_message_hooks(user_id, partition_id, assistant_node)

    # 4. 检测工具调用并生成响应块
    detected_tools = predict_tools(user_text)
    response_blocks = []

    if detected_tools:
        order = 0
        for tool_name in detected_tools:
            tool_block = await tool_executor.execute(tool_name, {
                "query": user_text,
                "subject": user_text,
                "topic": user_text,
                "prompt": user_text,
            })
            tool_block.order = order
            response_blocks.append(tool_block)
            order += 1

            # 慢任务：提交后台作业
            if tool_name in SLOW_TOOLS:
                from app.services.background_jobs import job_manager
                job = await job_manager.submit(
                    user_id=user_id,
                    tool_name=tool_name,
                    params=tool_block.content.get("params", {}),
                    block_id=tool_block.id,
                    partition_id=partition_id,
                    branch_id="",
                )

        # 存储响应块
        data = storage.load(user_id)
        for block in response_blocks:
            data.response_blocks[block.id] = block
        storage.save(user_id, data)

    yield {
        "type": "done",
        "assistant_message": assistant_node,
        "response_blocks": [b.model_dump() for b in response_blocks],
    }
