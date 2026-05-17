"""
对话系统 LLM 服务
基于树结构构建上下文，调用 LLM 生成回复
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
)
from app.services.llm_service import llm_service
from app.services.storage import storage
from app.services.tree_ops import tree_ops

logger = logging.getLogger(__name__)

# ── System Prompt ──

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
    完整流程：存用户消息 → 生成回复 → 存助手消息。
    返回两条消息。
    """
    # 1. 存用户消息
    blocks = content_blocks or [TextBlock(text=user_text)]
    user_node = tree_ops.add_message(
        user_id, partition_id, "user", blocks, user_text
    )

    # 2. 生成回复
    reply_text = await generate_reply(user_id, partition_id, user_text)

    # 3. 存助手消息
    reply_blocks = [TextBlock(text=reply_text)]
    assistant_node = tree_ops.add_message(
        user_id, partition_id, "assistant", reply_blocks, reply_text
    )

    return {
        "user_message": user_node,
        "assistant_message": assistant_node,
        "partition_id": partition_id,
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

    yield {"type": "done", "assistant_message": assistant_node}
