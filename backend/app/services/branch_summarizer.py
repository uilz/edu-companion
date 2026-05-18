"""
分支摘要服务
自动生成分支名称和摘要，定期更新分区上下文
"""

from __future__ import annotations

import logging
from app.services.storage import storage

logger = logging.getLogger(__name__)

# 降级模式：LLM不可用时使用规则引擎
FALLBACK_MODE = True


def summarize_branch_name(user_id: str, branch_id: str) -> str:
    """
    根据对话内容自动重命名分支
    
    规则：
    - ≤5条消息：取第一条消息的前20字
    - 5-20条：尝试LLM重命名
    - >20条：再次LLM重命名
    """
    data = storage.load(user_id)
    branch = data.branches.get(branch_id)
    if not branch:
        return ""

    messages = [data.nodes.get(nid) for nid in branch.path if data.nodes.get(nid)]
    msg_count = len(messages)

    if msg_count == 0:
        return branch.name or "新对话"

    if msg_count <= 5:
        # 初始命名：取第一条消息前20字
        first_msg = messages[0]
        text = first_msg.text_summary or str(first_msg.content_blocks)
        return text[:20] + ("..." if len(text) > 20 else "")

    else:
        # LLM重命名（降级用规则）
        return _llm_rename_branch(messages[-10:], branch.name)

    if msg_count > 20:
        # 再次重命名（反映主题演变）
        return _llm_rename_branch(messages[-15:], branch.name)

    return branch.name or "对话"


def _llm_rename_branch(recent_messages: list, current_name: str) -> str:
    """LLM生成分支名称，降级用规则"""
    if FALLBACK_MODE:
        # 降级：取最近一条用户消息的关键词
        for msg in reversed(recent_messages):
            if msg.role == "user":
                text = msg.text_summary or ""
                return text[:20] + ("..." if len(text) > 20 else "")
        return current_name

    # TODO: 接入LLM
    # prompt = f"根据以下对话摘要生成简短名称(≤15字):\\n{branch_summary}\\n当前名称:{current_name}"
    # return llm.generate(prompt)
    return current_name


def update_partition_context(user_id: str, partition_id: str) -> str:
    """
    更新分区上下文摘要
    
    合并所有分支摘要，生成分区级别的上下文
    LLM对话时注入这个摘要以省token
    """
    data = storage.load(user_id)
    partition = data.partitions.get(partition_id)
    if not partition:
        return ""

    branches = [b for b in data.branches.values() if b.partition_id == partition_id]
    active_branch = data.branches.get(partition.active_branch_id)

    # 构建分区摘要
    parts = [f"分区: {partition.name} ({partition.subject or '通用'})"]
    parts.append(f"共 {len(branches)} 条分支")

    if active_branch:
        msg_count = len(active_branch.path)
        parts.append(f"活跃分支: {active_branch.name or '未命名'} ({msg_count}条消息)")
        if active_branch.summary:
            parts.append(f"摘要: {active_branch.summary}")
        if active_branch.practice_summary:
            parts.append(f"练习: {active_branch.practice_summary}")

    context = " | ".join(parts)
    partition.context_summary = context
    storage.save(user_id, data)

    logger.info(f"分区 {partition_id} 上下文已更新")
    return context


def generate_branch_summary(user_id: str, branch_id: str) -> str:
    """
    为分支生成摘要
    
    触发条件：消息数 > 10 且距上次摘要 > 1小时，或手动触发
    """
    data = storage.load(user_id)
    branch = data.branches.get(branch_id)
    if not branch:
        return ""

    messages = [data.nodes.get(nid) for nid in branch.path if data.nodes.get(nid)]
    if len(messages) < 10:
        return branch.summary or ""

    # 降级：提取最近消息的文本摘要
    recent_texts = []
    for msg in messages[-10:]:
        text = msg.text_summary or ""
        if text:
            recent_texts.append(text[:50])

    summary = " > ".join(recent_texts[-5:])  # 最近5条的摘要链
    if len(summary) > 200:
        summary = summary[:197] + "..."

    branch.summary = summary
    branch.summary_dirty = False
    storage.save(user_id, data)

    logger.info(f"分支 {branch_id} 摘要已生成: {summary[:50]}...")
    return summary


def try_auto_rename_branch(user_id: str, branch_id: str, message_count: int) -> str | None:
    """
    根据消息数量自动重命名分支
    
    - 第5条消息：触发首次重命名
    - 第20条消息：触发二次重命名
    """
    if message_count == 5:
        new_name = summarize_branch_name(user_id, branch_id)
        logger.info(f"分支 {branch_id} 首次重命名: {new_name}")
        return new_name
    elif message_count == 20:
        new_name = summarize_branch_name(user_id, branch_id)
        logger.info(f"分支 {branch_id} 二次重命名: {new_name}")
        return new_name
    return None
