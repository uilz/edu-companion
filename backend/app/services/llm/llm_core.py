"""
LLM 核心模块：基础工具函数 + LLM 调用（非流式 / 流式）

包含:
- _find_active_conversation: 活跃对话查找
- detect_frustration: 情绪检测兼容接口
- parse_sources / _resolve_skill_ids: 引用溯源
- generate_reply: 非流式 LLM 调用
- generate_reply_stream: 流式 LLM 调用
"""

from __future__ import annotations

import logging
import re
from typing import AsyncGenerator

from app.schemas.conversation import (
    ResponseBlock,
    TreeNode,
)
from app.services.llm.llm_service import llm_service
from app.services.common.storage import storage
from app.services.conversation.context_builder import _build_context_messages
from app.services.analytics.emotion_analyzer import emotion_analyzer

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════
# 基础工具函数
# ═══════════════════════════════════════════════

def _find_active_conversation(data, partition_id: str):
    """通过 topic → domain 找到分区下的活跃对话（v4 数据模型）"""
    for topic in data.topics.values():
        domain = data.domains.get(topic.domain_id)
        if domain and domain.partition_id == partition_id:
            cid = topic.active_conversation_id
            if cid and cid in data.conversations:
                return data.conversations[cid]
    return None


# ═══════════════════════════════════════════════
# 情绪分析与引用溯源
# ═══════════════════════════════════════════════

# 向后兼容的快捷函数
def detect_frustration(text: str) -> bool:
    """检测用户消息是否包含挫败信号（兼容旧接口，委托 emotion_analyzer）"""
    result = emotion_analyzer.quick_detect(text)
    return result == "frustration"


# ── 引用溯源解析 ──

SOURCE_PATTERN = re.compile(r'\[来源:\s*([^\]]+)\]')

def parse_sources(text: str) -> tuple[str, list[str]]:
    """从回复文本中提取 [来源: xxx] 标记，返回 (清理后文本, 来源列表)"""
    sources = SOURCE_PATTERN.findall(text)
    cleaned = SOURCE_PATTERN.sub('', text).strip()
    # 清理多余空行
    cleaned = re.sub(r'\n{3,}', '\n\n', cleaned)
    return cleaned, sources


def _resolve_skill_ids(labels: list[str], partition_id: str, user_id: str) -> list[str]:
    """将 [来源: xxx] 中的知识点标签映射为 skill_id"""
    from app.services.common.storage import storage
    data = storage.load(user_id)
    graph = data.knowledge_graphs.get(partition_id)
    if not graph or not graph.nodes:
        return []
    # 构建 label → id 映射（精确匹配 + 模糊匹配）
    label_map: dict[str, str] = {}
    for node_id, node in graph.nodes.items():
        label_map[node.label] = node_id
        # 也存短名
        if len(node.label) > 4:
            label_map[node.label[:4]] = node_id

    skill_ids = []
    for label in labels:
        sid = label_map.get(label)
        if not sid:
            # 模糊匹配：查找包含该标签的节点
            for nl, nid in label_map.items():
                if label in nl or nl in label:
                    sid = nid
                    break
        if sid and sid not in skill_ids:
            skill_ids.append(sid)
    return skill_ids


# ═══════════════════════════════════════════════
# 回复生成（非流式 / 流式）
# ═══════════════════════════════════════════════

async def generate_reply(
    user_id: str,
    partition_id: str,
    user_text: str,
) -> str:
    """生成助手回复（非流式）。

    流程:
        1. 加载分区 & 活跃对话
        2. 获取最近 8 条消息
        3. 构建完整 LLM 上下文（含情绪 / 知识图谱 / 练习上下文）
        4. 调用 LLM 生成
        5. 返回纯文本回复
    """
    data = storage.load(user_id)
    partition = data.partitions.get(partition_id)
    if not partition:
        raise ValueError(f"Partition {partition_id} not found")

    conversation = _find_active_conversation(data, partition_id)
    if not conversation:
        raise ValueError(f"Active conversation not found")

    # 获取最近消息
    recent_messages = []
    for nid in conversation.path[-8:]:
        node = data.nodes.get(nid)
        if node and not node.is_deleted:
            recent_messages.append(node)

    # 构建上下文
    llm_messages = _build_context_messages(partition, conversation, recent_messages, user_text, user_id)

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
    extra_tool_context: str = "",
) -> AsyncGenerator[str, None]:
    """生成助手回复（流式，逐 token 产出）。

    extra_tool_context: 预先执行工具后注入的上下文（如练习题结果）。

    Yields:
        文本 chunk（str），调用方逐片段拼接。
    """
    data = storage.load(user_id)
    partition = data.partitions.get(partition_id)
    if not partition:
        raise ValueError(f"Partition {partition_id} not found")

    conversation = _find_active_conversation(data, partition_id)
    if not conversation:
        raise ValueError(f"Active conversation not found")

    # 获取最近消息
    recent_messages = []
    for nid in conversation.path[-8:]:
        node = data.nodes.get(nid)
        if node and not node.is_deleted:
            recent_messages.append(node)

    # 构建上下文
    llm_messages = _build_context_messages(partition, conversation, recent_messages, user_text, user_id)

    # 注入预执行的工具结果
    if extra_tool_context:
        llm_messages.append({"role": "system", "content": extra_tool_context})

    # Socratic hint: if too many consecutive questions, suggest direct explanation
    _conv_meta = getattr(conversation, 'metadata', None) or {}
    _sq_ct = _conv_meta.get('socratic_question_count', 0)
    if _sq_ct >= 3:
        llm_messages.append({
            "role": "system",
            "content": "提示：你已经连续问了多个问题，学生可能感到困惑。请尝试直接解释知识点，减少提问，用陈述句帮助学生理解。",
        })

    # 流式调用 LLM
    async for chunk in llm_service.generate_stream(
        messages=llm_messages,
        task_type="chat",
        temperature=0.7,
        max_tokens=2048,
    ):
        yield chunk
