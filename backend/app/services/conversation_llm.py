"""
对话系统 LLM 服务
基于树结构构建上下文，调用 LLM 生成回复
支持多模态响应块（ResponseBlock）集成
"""

from __future__ import annotations

import logging
import re
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

# ── System Prompt ──

SYSTEM_PROMPT = """你是「苹小果」，一个温暖的智能伴学助手。你像一位耐心的学长/学姐，陪伴学生度过学习中的每一个时刻。

## 人格特质
- **温暖陪伴**：用亲切自然的语气交流，像朋友一样。适当使用 emoji 传递温度 🌱
- **情绪感知**：如果学生表现出挫败、焦虑或疲惫，先共情安慰，再给建议。不说"别紧张"这类否定情绪的话，而是"这确实不容易，你已经很努力了"
- **真诚鼓励**：表扬具体行为（"这道题的思路很清晰"），不空洞夸赞
- **耐心启发**：对于概念性问题，先反问引导学生自己思考，再给出答案。如"你觉得这个现象背后的原因可能是什么？"
- **适度幽默**：在合适的时候可以轻松一下，但不过度

## 回答规范
- 用通俗易懂的语言解释概念，避免堆砌术语
- 涉及数学公式使用 LaTeX 格式（$...$ 行内，$$...$$ 块级）
- 涉及代码使用代码块格式，标注语言
- 回复简洁但完整，每次控制在合理长度
- **引用溯源**：如果回答涉及具体知识点，在末尾用 [来源: 知识点名称] 标注。如 [来源: 导数与微分] [来源: 牛顿第二定律]
- 涉及多个知识点时，分别标注

## 场景策略
- **学生提问概念**："为什么XXX？" → 先反问引导思考 → 再解释核心原理 → 举例说明
- **学生做错题**：先理解错因 → 针对性解释 → 鼓励重试 → 标注相关知识点
- **学生说累/难**：先共情 → 简短建议（休息/换个方式）→ 不强行推学习
- **学生求鼓励**：回顾其进步 → 具体肯定 → 设定小目标

## 安全边界
- 不替代专业心理咨询，如果学生表现出严重心理问题，建议寻求专业帮助
- 不提供考试作弊、论文代写等违规帮助
- 涉及医学、法律等专业领域时，声明建议仅供参考"""

# ── Frustration detection keywords ──

FRUSTRATION_SIGNALS = [
    "好难", "太难了", "不会", "不懂", "搞不定", "放弃了", "崩溃",
    "学不会", "做不对", "又错了", "好烦", "不想学了", "累死了",
    "我太笨了", "学不下去", "怎么办", "救救我", "完了", "挂了",
    "😭", "😫", "😩", "😤", "💀", "我好菜", "废物",
]

def detect_frustration(text: str) -> bool:
    """检测用户消息是否包含挫败信号"""
    return any(signal in text for signal in FRUSTRATION_SIGNALS)


# ── 引用溯源解析 ──

SOURCE_PATTERN = re.compile(r'\[来源:\s*([^\]]+)\]')

def parse_sources(text: str) -> tuple[str, list[str]]:
    """从回复文本中提取 [来源: xxx] 标记，返回 (清理后文本, 来源列表)"""
    sources = SOURCE_PATTERN.findall(text)
    cleaned = SOURCE_PATTERN.sub('', text).strip()
    # 清理多余空行
    cleaned = re.sub(r'\n{3,}', '\n\n', cleaned)
    return cleaned, sources


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

    # P0: 挫败检测 → 注入鼓励上下文
    if detect_frustration(user_text):
        frustration_ctx = (
            "\n\n⚠️ 学生当前表现出挫败情绪。请优先共情和鼓励，"
            "不要急于纠正或给建议。先肯定ta的努力，再温和地提供帮助。"
            "语气要比平时更温暖、更有耐心。"
        )
        system_content += frustration_ctx

    # P0: 最近对话挫败模式检测

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
            # 推荐多平台视频搜索
            if any(s for s in ctx.get('skill_ids', []) if s != 'general_practice'):
                system_content += "\n[Media] 如果用户需要视频讲解，推荐生成多平台搜索链接(B站/YouTube/知乎)"
    except Exception:
        pass

    # 添加分区上下文
    if partition.context_summary:
        system_content += f"\n\n当前分区：{partition.name}"
        system_content += f"\n分区摘要：{partition.context_summary}"

    # 注入可用知识点（供引用溯源）
    try:
        from domain.knowledge.prerequisites import ALL_PREREQUISITES, SKILL_TO_SUBJECT
        subject = partition.subject or ""
        relevant_skills = []
        if subject and subject in SKILL_TO_SUBJECT:
            relevant_skills = SKILL_TO_SUBJECT[subject][:15]
        else:
            relevant_skills = list(ALL_PREREQUISITES.keys())[:15]
        if relevant_skills:
            system_content += f"\n\n可引用的知识点: {', '.join(relevant_skills)}\n回答涉及这些知识点时，在末尾标注 [来源: 知识点名称]。"
    except Exception:
        pass

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
        cleaned_text, sources = parse_sources(reply)
        text_block = ResponseBlock(
            type="text",
            status="ready",
            content={"text": cleaned_text},
            sources=sources,
            order=order,
        )
        response_blocks.append(text_block)
        order += 1

        # 执行工具
        for tool_name in detected_tools:
            tool_block = await tool_executor.execute(tool_name, {"query": user_text, "subject": user_text})

            # 补充工具参数（基于用户输入）
            if tool_name == "search_media":
                tool_block = await tool_executor.execute(tool_name, {"query": user_text, "platforms": ["bilibili", "zhihu", "youtube"]})
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

        cleaned_text, sources = parse_sources(reply)
        text_block = ResponseBlock(
            type="text",
            status="ready",
            content={"text": cleaned_text},
            sources=sources,
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
