"""
分支摘要服务
自动生成分支名称和摘要，定期更新分区上下文
"""

from __future__ import annotations

import logging
from app.services.common import get_data_repo
from app.infrastructure.llm.llm_service import llm_service

logger = logging.getLogger(__name__)

# 降级模式：LLM不可用时使用规则引擎
FALLBACK_MODE = False  # 启用 LLM 命名


def _weighted_recent_messages(messages: list, last_n: int = 8) -> list:
    """
    从消息列表中提取最近N条，后几轮权重更大、中长消息权重更大。
    返回按权重排序的消息文本列表（用于 LLM 上下文）。
    """
    if not messages:
        return []

    msg_items = []
    total = len(messages)
    for i, msg in enumerate(messages):
        text = (msg.text_summary or "").strip()
        if not text:
            continue
        # 位置权重：越靠后越高 (1.0 ~ 2.0)
        position_weight = 1.0 + (i / max(total, 1))
        # 长度权重：15-60字的消息权重最高（信息量适中）
        length = len(text)
        if length < 5:
            length_weight = 0.3
        elif length < 15:
            length_weight = 0.6
        elif length <= 60:
            length_weight = 1.0
        elif length <= 120:
            length_weight = 0.8
        else:
            length_weight = 0.5
        # 角色权重：用户消息比 AI 回复更有命名价值
        role_weight = 1.2 if msg.role == "user" else 0.6
        # 综合权重
        weight = position_weight * length_weight * role_weight
        msg_items.append((weight, text[:80]))  # 截断到80字

    # 按权重排序，取前 last_n
    msg_items.sort(key=lambda x: -x[0])
    return [text for _, text in msg_items[:last_n]]


async def summarize_branch_name(user_id: str, branch_id: str) -> str:
    """
    根据对话内容自动重命名对话（DirectoryNode 版本）
    """
    data = get_data_repo().load(user_id)
    branch = data.directory_nodes.get(branch_id)
    if not branch or branch.node_type != "conv":
        return ""

    msg_ids = branch.conv_message_ids or []
    messages = [data.nodes.get(nid) for nid in msg_ids if data.nodes.get(nid)]
    msg_count = len(messages)

    if msg_count == 0:
        return branch.name or "新对话"

    if msg_count <= 5:
        first_msg = messages[0]
        text = first_msg.text_summary or ""
        return text[:20] + ("..." if len(text) > 20 else "")

    recent_texts = _weighted_recent_messages(messages, last_n=8)
    return await _llm_rename_branch(recent_texts, branch.name)


async def _llm_rename_branch(recent_texts: list[str], current_name: str) -> str:
    """LLM 生成分支名称，降级用规则"""
    if not recent_texts:
        return current_name

    if FALLBACK_MODE:
        # 降级：取权重最高的消息前20字
        best = recent_texts[0] if recent_texts else ""
        return best[:20] + ("..." if len(best) > 20 else "")

    try:
        # 构建上下文：给最近最重要的几条消息
        context = "\n".join(f"{i+1}. {t}" for i, t in enumerate(recent_texts))
        prompt = (
            f"根据以下对话片段，生成一个简短的对话标题（≤12字，不要超过）：\n\n"
            f"{context}\n\n"
            f"当前标题: {current_name or '无'}\n"
            f"要求：概括对话的核心主题，具体而不空洞。只输出标题本身，不要引号。"
        )
        result = await llm_service.generate(
            messages=[{"role": "user", "content": prompt}],
            task_type="summary",
            temperature=0.3,
            max_tokens=200,
        )
        name = (result or "").strip().strip('"''"「」')
        if name and len(name) <= 15:
            logger.info(f"LLM 生成分支名称: {name}")
            return name
        # 过长则截断
        return name[:15] if name else current_name
    except Exception as e:
        logger.warning(f"LLM 分支命名失败，降级用规则: {e}")
        best = recent_texts[0] if recent_texts else ""
        return best[:20] + ("..." if len(best) > 20 else "")


def update_partition_context(user_id: str, dir_id: str) -> str:
    """
    更新分区上下文摘要（DirectoryNode 版本）
    合并所有子对话摘要，生成目录级别的上下文
    """
    data = get_data_repo().load(user_id)
    partition = data.directory_nodes.get(dir_id)
    if not partition:
        return ""

    # 收集该目录下的所有对话节点
    branches = [
        n for n in data.directory_nodes.values()
        if n.node_type == "conv" and n.parent_id == dir_id
    ]
    # 最活跃对话（updated_at 最新）
    branches_sorted = sorted(branches, key=lambda n: n.updated_at, reverse=True)
    active_branch = branches_sorted[0] if branches_sorted else None

    # 构建摘要
    parts = [f"目录: {partition.name}"]
    parts.append(f"共 {len(branches)} 个对话")

    if active_branch:
        msg_count = len(active_branch.conv_message_ids or [])
        parts.append(f"活跃对话: {active_branch.name or '未命名'} ({msg_count}条消息)")
        summary = (active_branch.metadata or {}).get("summary", "")
        if summary:
            parts.append(f"摘要: {summary}")

    context = " | ".join(parts)
    partition.context_summary = context
    get_data_repo().save(user_id, data)

    logger.info(f"目录 {dir_id} 上下文已更新")
    return context


def generate_branch_summary(user_id: str, branch_id: str) -> str:
    """
    为对话生成摘要（DirectoryNode 版本）
    """
    data = get_data_repo().load(user_id)
    branch = data.directory_nodes.get(branch_id)
    if not branch or branch.node_type != "conv":
        return ""

    msg_ids = branch.conv_message_ids or []
    messages = [data.nodes.get(nid) for nid in msg_ids if data.nodes.get(nid)]
    if len(messages) < 10:
        meta = branch.metadata or {}
        return meta.get("summary", "")

    recent_texts = []
    for msg in messages[-10:]:
        text = msg.text_summary or ""
        if text:
            recent_texts.append(text[:50])

    summary = " > ".join(recent_texts[-5:])
    if len(summary) > 200:
        summary = summary[:197] + "..."

    if not branch.metadata:
        branch.metadata = {}
    branch.metadata["summary"] = summary
    branch.metadata["summary_dirty"] = False
    get_data_repo().save(user_id, data)

    logger.info(f"对话 {branch_id} 摘要已生成: {summary[:50]}...")
    return summary


async def try_auto_rename_branch(user_id: str, branch_id: str, message_count: int) -> str | None:
    """
    根据消息数量自动重命名分支

    - 第5条消息：触发首次重命名
    - 第20条消息：触发二次重命名
    """

    if message_count == 5:
        new_name = await summarize_branch_name(user_id, branch_id)
        logger.info(f"分支 {branch_id} 首次重命名: {new_name}")
        return new_name
    elif message_count == 20:
        new_name = await summarize_branch_name(user_id, branch_id)
        logger.info(f"分支 {branch_id} 二次重命名: {new_name}")
        return new_name
    return None
