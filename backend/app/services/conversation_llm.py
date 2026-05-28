"""
对话系统 LLM 服务
基于树结构构建上下文，调用 LLM 生成回复
支持多模态响应块（ResponseBlock）集成
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any, AsyncGenerator

from app.schemas.conversation import (
    ContentBlock,
    TextBlock,
    TreeNode,
    ResponseBlock,
)
from app.services.llm_service import llm_service, _parse_tool_calls_response
from app.services.storage import storage
from app.services.tree_ops import tree_ops
from app.services.classifier import classifier
from app.services.tool_executor import tool_executor, predict_tools, SLOW_TOOLS

from app.services.emotion_analyzer import emotion_analyzer
from app.services.context_builder import _build_context_messages

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
# P0 钩子：消息后处理（元历史 / 分支重命名 / 图谱更新）
# ═══════════════════════════════════════════════

def _p0_post_message_hooks(user_id: str, partition_id: str, node: TreeNode) -> None:
    """消息存储后的 P0 钩子：异步写元历史 + 触发分支命名/摘要"""
    import asyncio
    try:
        loop = asyncio.get_running_loop()
        if loop.is_running():
            from app.services.meta_history import write_to_meta_history
            loop.create_task(write_to_meta_history(user_id, node))

            data = storage.load(user_id)
            conversation = data.conversations.get(node.conversation_id) if node.conversation_id else None
            if conversation:
                msg_count = len(conversation.path)
                from app.services.branch_summarizer import (
                    try_auto_rename_branch, generate_branch_summary, update_partition_context,
                )

                async def _do_rename():
                    new_name = await try_auto_rename_branch(user_id, node.conversation_id, msg_count)
                    if new_name:
                        _data = storage.load(user_id)
                        _conv = _data.conversations.get(node.conversation_id)
                        if _conv:
                            _conv.name = new_name
                            storage.save(user_id, _data)
                            # 分支命名后 → 异步更新知识图谱
                            _trigger_graph_update(user_id, node.conversation_id, new_name)

                loop.create_task(_do_rename())

                if msg_count >= 10 and msg_count % 10 == 0:
                    generate_branch_summary(user_id, node.conversation_id)
                if msg_count % 5 == 0:
                    update_partition_context(user_id, partition_id)
    except Exception:
        logger.debug("P0 hooks skipped")


def _trigger_graph_update(user_id: str, conversation_id: str, new_branch_name: str) -> None:
    """分支命名后异步触发知识图谱更新（fire and forget）"""
    async def _update():
        try:
            data = storage.load(user_id)
            conversation = data.conversations.get(conversation_id)
            if not conversation:
                return
            # v4: find partition via topic → domain
            topic = data.topics.get(conversation.topic_id) if hasattr(conversation, 'topic_id') else None
            domain = data.domains.get(topic.domain_id) if topic else None
            if not domain:
                return
            partition_id = domain.partition_id
            partition = data.partitions.get(partition_id)
            if not partition:
                return

            # 已存在的图谱 → 增量合并；不存在 → 新建
            data.knowledge_graphs.get(partition_id)

            from app.api.knowledge_graph import generate_graph_logic
            await generate_graph_logic(
                user_id=user_id,
                partition_id=partition_id,
                data=data,
                branch_name=new_branch_name,
            )
        except Exception as e:
            logger.debug(f"异步图谱更新跳过: {e}")

    try:
        import asyncio
        loop = asyncio.get_running_loop()
        if loop.is_running():
            loop.create_task(_update())
    except Exception:
        logger.debug("异步图谱更新事件循环获取失败", exc_info=True)


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
    from app.services.storage import storage
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
# 回复生成（非流式 / 带工具 / 流式）
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


# ═══════════════════════════════════════════════
# 工具调用辅助函数
# ═══════════════════════════════════════════════

def _build_tool_params(tool_name: str, user_text: str, partition) -> dict:
    """根据工具类型从用户输入构建参数"""
    subject = getattr(partition, "subject", "") or "通用"
    if tool_name == "search_media":
        return {"query": user_text, "platforms": ["bilibili", "zhihu", "youtube"]}
    elif tool_name == "generate_practice":
        return {
            "subject": subject,
            "knowledge_point": user_text[:80],
            "difficulty": "进阶",
            "count": 2,
        }
    elif tool_name == "generate_image":
        return {"prompt": user_text}
    elif tool_name == "generate_mindmap":
        return {"topic": user_text, "depth": 3}
    elif tool_name == "generate_document":
        return {"topic": user_text, "format": "markdown"}
    return {"query": user_text}


def _summarize_tool_result(tool_name: str, block: ResponseBlock) -> str:
    """提取工具结果中的关键信息，供 LLM 引用"""
    content = block.content or {}
    if tool_name == "search_media":
        platforms = content.get("platforms", [])
        links_count = sum(len(p.get("links", [])) for p in platforms)
        names = [p.get("name", "") for p in platforms[:3]]
        return f"搜索到{links_count}个视频链接（{', '.join(names)}）"
    elif tool_name == "generate_practice":
        questions = content.get("questions", [])
        return f"生成{len(questions)}道练习题"
    elif tool_name == "generate_image":
        return "已生成图片"
    elif tool_name == "generate_mindmap":
        return "已生成思维导图"
    elif tool_name == "generate_document":
        return "已生成文档"
    return f"工具{tool_name}执行完成"


# ── 工具结果上下文注入 ──

def _build_tool_context(tool_results: list[dict]) -> str:
    """构建注入 LLM 的工具结果上下文"""
    lines = ["[工具执行结果] 以下内容已展示给学生，请在回复中自然地引用："]
    for r in tool_results:
        if "error" in r:
            lines.append(f"- {r['tool']}: 执行失败 ({r['error']})")
        else:
            lines.append(f"- {r['tool']}: {r['summary']}")
    lines.append("\n请在回复中引导学生查看上面的卡片/结果。如果是练习题，鼓励学生作答。")
    return "\n".join(lines)


# ── 带工具调用的回复生成 ──

async def generate_reply_with_tools(
    user_id: str,
    partition_id: str,
    user_text: str,
) -> list[ResponseBlock]:
    """生成助手回复，集成工具调用（非流式）。

    策略: 意图预判 → 先执行工具 → LLM 统一回复。
    返回 ResponseBlock 列表：text block（首位） + tool result blocks。
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

    # 意图预判（含上下文感知：AI建议→用户同意）
    last_ai_text = ""
    for msg in reversed(recent_messages):
        if msg.role == "assistant":
            last_ai_text = msg.text_summary or ""
            break
    detected_tools = predict_tools(user_text, last_ai_text)
    logger.info("Detected tools: %s for text: %s", detected_tools, user_text[:50])

    # 构建上下文
    llm_messages = _build_context_messages(partition, conversation, recent_messages, user_text, user_id)

    response_blocks: list[ResponseBlock] = []
    order = 0

    if detected_tools:
        # 🔧 修复：先执行工具 → 注入结果 → LLM统一回复
        tool_results: list[dict] = []
        for tool_name in detected_tools:
            try:
                # 构建工具参数
                params = _build_tool_params(tool_name, user_text, partition)
                tool_block = await tool_executor.execute(tool_name, params)
                tool_block.order = order
                response_blocks.append(tool_block)
                order += 1
                
                # 提取有用信息注入LLM上下文
                tool_results.append({
                    "tool": tool_name,
                    "summary": _summarize_tool_result(tool_name, tool_block),
                })
                
                # 慢任务：提交后台作业
                if tool_name in SLOW_TOOLS:
                    from app.services.background_jobs import job_manager
                    job = await job_manager.submit(
                        user_id=user_id,
                        tool_name=tool_name,
                        params=params,
                        block_id=tool_block.id,
                        partition_id=partition_id,
                        conversation_id=conversation.id if conversation else "",
                    )
                    data.response_blocks[tool_block.id] = tool_block
                    storage.save(user_id, data)
            except Exception as e:
                logger.error(f"Tool {tool_name} failed: {e}")
                tool_results.append({"tool": tool_name, "error": str(e)})
        
        # 将工具结果注入 LLM 上下文
        if tool_results:
            tool_context = _build_tool_context(tool_results)
            llm_messages.append({"role": "system", "content": tool_context})
        
        # 调用 LLM 生成最终回复（含工具结果引用）
        try:
            reply = await llm_service.generate(
                messages=llm_messages,
                task_type="chat",
                temperature=0.7,
                max_tokens=2048,
            )
        except Exception as e:
            logger.error("LLM generation failed: %s", e)
            reply = "我帮你准备了一些学习资料，请看上面的卡片 👆"

        # 创建文本 ResponseBlock
        cleaned_text, sources = parse_sources(reply)
        text_block = ResponseBlock(
            type="text",
            status="ready",
            content={"text": cleaned_text},
            sources=sources,
            order=0,  # 文本放最前面
        )
        # 插入到开头
        response_blocks.insert(0, text_block)
        # 重新编号
        for i, b in enumerate(response_blocks):
            b.order = i
    else:
        # 无 regex 匹配 → LLM function-calling 路径
        tools = tool_executor.get_tools_for_llm()
        try:
            reply = await llm_service.generate(
                messages=llm_messages,
                task_type="chat",
                temperature=0.7,
                max_tokens=2048,
                tools=tools,
            )
        except Exception as e:
            logger.error("LLM generation failed: %s", e)
            reply = ""

        # 检查 LLM 是否请求 tool_calls
        tool_calls = _parse_tool_calls_response(reply)
        if tool_calls:
            # LLM 自主决定调用工具
            logger.info(
                "LLM requested tool_calls: %s",
                [tc["function"]["name"] for tc in tool_calls],
            )

            # 添加 assistant 消息（含 tool_calls）到上下文
            llm_messages.append({
                "role": "assistant",
                "content": None,
                "tool_calls": tool_calls,
            })

            tool_results: list[dict] = []
            for tc in tool_calls:
                tool_name = tc["function"]["name"]
                try:
                    args = json.loads(tc["function"]["arguments"])
                except (json.JSONDecodeError, KeyError):
                    args = {}

                try:
                    # 使用 LLM 提供的参数执行工具
                    tool_block = await tool_executor.execute(tool_name, args)
                    tool_block.order = order
                    response_blocks.append(tool_block)
                    order += 1

                    tool_results.append({
                        "tool": tool_name,
                        "summary": _summarize_tool_result(tool_name, tool_block),
                    })

                    # 慢任务：提交后台作业
                    if tool_name in SLOW_TOOLS:
                        from app.services.background_jobs import job_manager
                        await job_manager.submit(
                            user_id=user_id,
                            tool_name=tool_name,
                            params=args,
                            block_id=tool_block.id,
                            partition_id=partition_id,
                            conversation_id=conversation.id if conversation else "",
                        )
                        data.response_blocks[tool_block.id] = tool_block
                        storage.save(user_id, data)

                    # 将工具结果作为 tool message 添加到上下文
                    result_content = json.dumps(
                        tool_block.content or {}, ensure_ascii=False,
                    )
                    llm_messages.append({
                        "role": "tool",
                        "tool_call_id": tc["id"],
                        "content": result_content,
                    })
                except Exception as e:
                    logger.error("LLM tool %s failed: %s", tool_name, e)
                    tool_results.append({"tool": tool_name, "error": str(e)})
                    llm_messages.append({
                        "role": "tool",
                        "tool_call_id": tc["id"],
                        "content": json.dumps({"error": str(e)}),
                    })

            # 将工具结果摘要注入 LLM 上下文
            if tool_results:
                tool_context = _build_tool_context(tool_results)
                llm_messages.append({"role": "system", "content": tool_context})

            # 第二次调用 LLM：基于工具结果生成最终回复
            try:
                reply = await llm_service.generate(
                    messages=llm_messages,
                    task_type="chat",
                    temperature=0.7,
                    max_tokens=2048,
                )
            except Exception as e:
                logger.error("LLM second call failed: %s", e)
                reply = "我帮你准备了一些学习资料，请看上面的卡片 👆"

            cleaned_text, sources = parse_sources(reply)
            text_block = ResponseBlock(
                type="text",
                status="ready",
                content={"text": cleaned_text},
                sources=sources,
                order=0,
            )
            response_blocks.insert(0, text_block)
            # 重新编号
            for i, b in enumerate(response_blocks):
                b.order = i
        else:
            # LLM 没有请求工具 → 纯文本回复
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


# ── 流式回复生成 ──

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


# ═══════════════════════════════════════════════
# 对话后处理：知识证据分析 & CognitiveNode 联动
# ═══════════════════════════════════════════════

# ── 对话知识证据分析（异步，不阻塞回复） ──

async def _analyze_conversation_evidence(
    user_id: str,
    partition_id: str,
    user_text: str,
    assistant_reply: str,
    conversation_id: str = "",
):
    """分析一轮对话，提取知识证据写入 SharedKnowledgeState"""
    try:
        from app.services.knowledge_bridge import knowledge_bridge
        from app.services.storage import storage as _st

        # 从 partition 推断涉及的技能（通过 CognitiveNode 查找实际 node_id）
        from app.cognitive.storage import find_node_by_label
        data = _st.load(user_id)
        conversation = data.conversations.get(conversation_id) if conversation_id else _find_active_conversation(data, partition_id)
        partition = data.partitions.get(partition_id)
        skill_ids = []
        if partition:
            label_to_lookup = partition.name or partition.subject
            if label_to_lookup:
                node = find_node_by_label(label_to_lookup, user_id)
                if node:
                    skill_ids = [node.id]
                elif partition.subject and partition.subject != label_to_lookup:
                    node = find_node_by_label(partition.subject, user_id)
                    if node:
                        skill_ids = [node.id]

        if skill_ids:
            await knowledge_bridge.deep_evidence_analysis(
                user_text=user_text,
                assistant_reply=assistant_reply,
                skill_ids=skill_ids,
                conversation_id=conversation.id if conversation else "", # type: ignore
            )
    except Exception as e:
        logger.debug(f"知识证据分析跳过: {e}")


# ── Phase 6: 对话上下文联动 → CognitiveNode ──

async def _cognify_dialogue_context(
    user_id: str,
    conversation: Any,
    skill_ids: list[str],
    context_type: str = "lower",
):
    """异步向 CognitiveNode 写入对话上下文。"""
    try:
        from app.cognitive.events import submit_dialogue_context
        import asyncio

        conversation_id = conversation.id if conversation else ""
        for sid in skill_ids:
            await asyncio.to_thread(
                submit_dialogue_context,
                user_id=user_id,
                node_id=sid,
                session_id=conversation_id,
                context_type=context_type,
                branch_id=conversation_id,
                relevance_score=0.5,
                summary_text=f"conversation {conversation_id[:8]}",
            )
    except ImportError:
        pass
    except Exception as e:
        logger.debug(f"认知对话上下文联动跳过: {e}")


# ═══════════════════════════════════════════════
# 公开 API：send_and_reply（非流式完整流程）
# ═══════════════════════════════════════════════

async def send_and_reply(
    user_id: str,
    partition_id: str,
    user_text: str,
    content_blocks: list[ContentBlock] | None = None,
    conversation_id: str = "",
) -> dict:
    """
    完整流程：存用户消息 → 生成回复（含工具） → 存助手消息。
    返回两条消息和 response_blocks。
    """
    # 1. 存用户消息
    blocks = content_blocks or [TextBlock(text=user_text)]
    user_node = tree_ops.add_message(
        user_id, partition_id, "user", blocks, user_text, conversation_id=conversation_id,
    )

    # P0: 异步写入元历史 + 触发分支自动命名
    _p0_post_message_hooks(user_id, partition_id, user_node)

    # P0: 异步情绪追踪（LLM 分类 + 缓存）
    import asyncio
    try:
        loop = asyncio.get_running_loop()
        if loop.is_running():
            loop.create_task(emotion_analyzer.classify(user_text, user_id))
    except Exception:
        logger.debug("异步图谱更新事件循环获取失败", exc_info=True)

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
        user_id, partition_id, "assistant", reply_blocks, reply_text, conversation_id=conversation_id,
    )

    # 回填 message_id 到 ResponseBlock（之前存储时 message_id 尚未知）
    data = storage.load(user_id)
    
    for block in response_blocks:
        if block.id in data.response_blocks:
            data.response_blocks[block.id].message_id = assistant_node.id
    storage.save(user_id, data)

    # v3.0: 从回复中提取 [来源: xxx] 标注 → 映射为 skill_id → 写入节点
    if reply_text:
        _, source_labels = parse_sources(reply_text)
        if source_labels:
            skill_ids = _resolve_skill_ids(source_labels, partition_id, user_id)
            if skill_ids:
                data = storage.load(user_id)
                # 获取对话对象（优先使用传入的 conversation_id，否则查找活跃对话）
                conversation = data.conversations.get(conversation_id) if conversation_id else _find_active_conversation(data, partition_id)
                if assistant_node.id in data.nodes:
                    data.nodes[assistant_node.id].discussed_skill_ids = skill_ids
                    storage.save(user_id, data)
                logger.info(f"消息 {assistant_node.id[:8]} 标注知识点: {skill_ids}")
                # v3.0: 记录事件
                from app.services.learning_events import record_event
                from app.schemas.learning_event import EventType
                for sid in skill_ids:
                    record_event(
                        EventType.SKILL_DISCUSSED,
                        user_id=user_id,
                        partition_id=partition_id,
                        conversation_id=conversation.id if conversation else None, # type: ignore
                        skill_ids=[sid],
                    )
                # Phase 6: 对话 → CognitiveNode 对话上下文联动
                import asyncio as _cognitive_asyncio
                try:
                    loop = _cognitive_asyncio.get_running_loop()
                    if loop.is_running():
                        loop.create_task(_cognify_dialogue_context(
                            user_id, conversation, skill_ids,
                            context_type="lower",
                        ))
                except Exception:
                    logger.debug("认知对话上下文联动跳过（send_and_reply）", exc_info=True)

    # P0: 异步写入助手消息的元历史
    _p0_post_message_hooks(user_id, partition_id, assistant_node)

    # P0: 异步知识证据分析（对话 → SharedKnowledgeState）
    import asyncio as _asyncio
    try:
        loop = _asyncio.get_running_loop()
        if loop.is_running():
            loop.create_task(_analyze_conversation_evidence(
                user_id, partition_id, user_text, reply_text,
                conversation_id=conversation_id    # ← 已修复：传递 conversation_id
            ))
    except Exception:
        logger.debug("异步图谱更新事件循环获取失败", exc_info=True)

    return {
        "user_message": user_node,
        "assistant_message": assistant_node,
        "partition_id": partition_id,
        "response_blocks": [b.model_dump() for b in response_blocks],
    }


# ═══════════════════════════════════════════════
# 公开 API：send_and_reply_stream（流式完整流程）
# ═══════════════════════════════════════════════

async def send_and_reply_stream(
    user_id: str,
    partition_id: str,
    user_text: str,
    content_blocks: list[ContentBlock] | None = None,
    conversation_id: str = "",
) -> AsyncGenerator[dict, None]:
    """
    完整流程（流式）：自动路由 → 存用户消息 → 预执行工具 → 流式生成回复 → 存助手消息。
    产出事件：context_switch / tool_block / token / done

    v4: 集成 auto_resolve 自动定位分区/领域/专题/对话，检测到切换时发出 context_switch。
    """
    import asyncio

    # 0. 自动路由：分类 + 创建缺失层级 + 检测切换
    route = classifier.auto_resolve(
        user_id, user_text,
        current_partition_id=partition_id,
        current_conversation_id=conversation_id,
    )
    resolved_partition_id = route["partition_id"]
    resolved_conversation_id = route["conversation_id"]

    # 检测到切换 → 发出推荐事件（前端展示切换提示）
    if route["should_recommend_switch"]:
        full_path = route.get("full_path", "")
        yield {
            "type": "context_switch",
            "switch_detail": route["switch_detail"],
            "partition_id": resolved_partition_id,
            "conversation_id": resolved_conversation_id,
            "domain_name": route.get("domain_name", ""),
            "topic_name": route.get("topic_name", ""),
            "full_path": full_path,
        }

    # 更新为解析后的 partition_id
    partition_id = resolved_partition_id

    # 1. 存用户消息
    blocks = content_blocks or [TextBlock(text=user_text)]
    user_node = tree_ops.add_message(
        user_id, partition_id, "user", blocks, user_text,
        conversation_id=resolved_conversation_id,
    )

    # P0: async meta history
    _p0_post_message_hooks(user_id, partition_id, user_node)

    # P0: 异步情绪追踪
    try:
        loop = asyncio.get_running_loop()
        if loop.is_running():
            loop.create_task(emotion_analyzer.classify(user_text, user_id))
    except Exception:
        logger.debug("异步图谱更新事件循环获取失败", exc_info=True)

    yield {"type": "user_message", "message": user_node.model_dump(mode="json")}

    # 2. 预检测工具 → 先执行工具 → 注入上下文 → 再让 LLM 流式回复
    data = storage.load(user_id)
    partition = data.partitions.get(partition_id)
    # v4: find active conversation via topic
    conversation = None
    if partition:
        for topic in data.topics.values():
            domain = data.domains.get(topic.domain_id)
            if domain and domain.partition_id == partition_id:
                cid = topic.active_conversation_id
                if cid and cid in data.conversations:
                    conversation = data.conversations[cid]
                    break

    # 获取上一轮 AI 回复文本（上下文感知）
    last_ai_text = ""
    if conversation:
        for nid in reversed(conversation.path):
            node = data.nodes.get(nid)
            if node and node.role == "assistant" and not node.is_deleted:
                last_ai_text = node.text_summary or ""
                break

    detected_tools = predict_tools(user_text, last_ai_text)
    logger.info("Streaming detected tools: %s for text: %s", detected_tools, user_text[:50])

    response_blocks: list[ResponseBlock] = []
    extra_tool_context = ""
    order = 0

    if detected_tools:
        tool_results: list[dict] = []
        for tool_name in detected_tools:
            try:
                params = _build_tool_params(tool_name, user_text, partition)
                tool_block = await tool_executor.execute(tool_name, params)
                tool_block.order = order
                response_blocks.append(tool_block)
                order += 1

                # 提取有用信息注入 LLM 上下文
                tool_results.append({
                    "tool": tool_name,
                    "summary": _summarize_tool_result(tool_name, tool_block),
                })

                # 慢任务：提交后台作业
                if tool_name in SLOW_TOOLS:
                    from app.services.background_jobs import job_manager
                    job = await job_manager.submit(
                        user_id=user_id,
                        tool_name=tool_name,
                        params=params,
                        block_id=tool_block.id,
                        partition_id=partition_id,
                        conversation_id=conversation.id if conversation else "",
                    )
                    data.response_blocks[tool_block.id] = tool_block
            except Exception as e:
                logger.error(f"Pre-stream tool {tool_name} failed: {e}")
                tool_results.append({"tool": tool_name, "error": str(e)})

        # 构建注入 LLM 的工具上下文
        if tool_results:
            extra_tool_context = _build_tool_context(tool_results)

        # 先 yield 工具块（前端立即渲染卡片）
        for block in response_blocks:
            yield {"type": "tool_block", "block": block.model_dump(mode="json")}

    # 2b. LLM function-calling fallback（regex 未命中时）
    llm_probe_reply = ""  # 若 LLM probe 直接返回文本（无 tool_calls），存于此处
    if not detected_tools and not extra_tool_context:
        # 构建上下文用于 LLM 探测
        probe_recent = []
        if conversation:
            for nid in conversation.path[-8:]:
                node = data.nodes.get(nid)
                if node and not node.is_deleted:
                    probe_recent.append(node)
        probe_messages = _build_context_messages(
            partition, conversation, probe_recent, user_text, user_id,
        )
        tools = tool_executor.get_tools_for_llm()
        try:
            probe_result = await llm_service.generate(
                messages=probe_messages,
                task_type="chat",
                temperature=0.7,
                max_tokens=2048,
                tools=tools,
            )
        except Exception as e:
            logger.error("LLM function-calling probe failed: %s", e)
            probe_result = ""

        probe_tool_calls = _parse_tool_calls_response(probe_result)
        if probe_tool_calls:
            # LLM 自主决定调用工具
            logger.info(
                "Streaming LLM requested tool_calls: %s",
                [tc["function"]["name"] for tc in probe_tool_calls],
            )
            tool_results: list[dict] = []
            for tc in probe_tool_calls:
                tool_name = tc["function"]["name"]
                try:
                    args = json.loads(tc["function"]["arguments"])
                except (json.JSONDecodeError, KeyError):
                    args = {}
                try:
                    tool_block = await tool_executor.execute(tool_name, args)
                    tool_block.order = order
                    response_blocks.append(tool_block)
                    order += 1
                    tool_results.append({
                        "tool": tool_name,
                        "summary": _summarize_tool_result(tool_name, tool_block),
                    })
                    if tool_name in SLOW_TOOLS:
                        from app.services.background_jobs import job_manager
                        await job_manager.submit(
                            user_id=user_id,
                            tool_name=tool_name,
                            params=args,
                            block_id=tool_block.id,
                            partition_id=partition_id,
                            conversation_id=conversation.id if conversation else "",
                        )
                        data.response_blocks[tool_block.id] = tool_block
                except Exception as e:
                    logger.error("Streaming LLM tool %s failed: %s", tool_name, e)
                    tool_results.append({"tool": tool_name, "error": str(e)})

            if tool_results:
                extra_tool_context = _build_tool_context(tool_results)

            # yield 工具块
            for block in response_blocks:
                yield {"type": "tool_block", "block": block.model_dump(mode="json")}
        else:
            # LLM 直接返回文本（无需工具）→ 保存以跳过第二次 LLM 调用
            llm_probe_reply = probe_result

    # 3. 流式生成回复（LLM 现在能看到工具执行结果）
    # 先创建空助手节点（后续增量覆写，刷新不丢）
    reply_blocks_placeholder = [TextBlock(text="")]
    assistant_node = tree_ops.add_message(
        user_id, partition_id, "assistant", reply_blocks_placeholder, "",
        conversation_id=resolved_conversation_id,
    )
    asst_node_id = assistant_node.id
    full_reply = ""
    token_since_save = 0
    # Socratic questioning tracking: count consecutive questions
    socratic_count = 0
    _data_sq = storage.load(user_id)
    _conv_sq = _data_sq.conversations.get(resolved_conversation_id)
    if _conv_sq:
        _meta_sq = getattr(_conv_sq, 'metadata', None) or {}
        socratic_count = _meta_sq.get('socratic_question_count', 0)
    try:
        if llm_probe_reply:
            # LLM probe 已返回文本（无 tool_calls）→ 模拟流式输出
            chunk_size = 4
            for i in range(0, len(llm_probe_reply), chunk_size):
                chunk = llm_probe_reply[i:i + chunk_size]
                full_reply += chunk
                token_since_save += 1
                yield {"type": "token", "content": chunk}
                if token_since_save >= 20:
                    tree_ops.update_message_content(user_id, asst_node_id, full_reply)
                    token_since_save = 0
        else:
            async for chunk in generate_reply_stream(
                user_id, partition_id, user_text,
                extra_tool_context=extra_tool_context,
            ):
                full_reply += chunk
                token_since_save += 1
                yield {"type": "token", "content": chunk}
                # 每 20 token 覆写一次 DB，刷新后 loadMessages 能拿到最新文本
                if token_since_save >= 20:
                    tree_ops.update_message_content(user_id, asst_node_id, full_reply)
                    token_since_save = 0
    except Exception as e:
        logger.error("generate_reply_stream 失败: %s", str(e))
        fallback = f"抱歉，生成回复时遇到了问题 😣\n\n错误信息：{str(e)[:200]}\n\n请稍后重试或检查系统配置。"
        full_reply = fallback
        yield {"type": "token", "content": fallback}

    # 如果 LLM 没有返回任何内容，给用户一个可见提示
    if not full_reply.strip():
        full_reply = "抱歉，我暂时无法回复 😣\n\n请检查：\n1. API Key 是否正确配置\n2. 模型是否可用\n3. 稍后重试"

    # 4. 覆写最终版本到 DB（此时已完成）
    tree_ops.update_message_content(user_id, asst_node_id, full_reply)

    # Socratic: detect question in reply and update counter
    _stripped = full_reply.strip()
    if _stripped and (_stripped.endswith('?') or _stripped.endswith('？')):
        socratic_count += 1
    else:
        socratic_count = 0
    _data_sq2 = storage.load(user_id)
    _conv_sq2 = _data_sq2.conversations.get(resolved_conversation_id)
    if _conv_sq2:
        _conv_sq2.metadata = getattr(_conv_sq2, 'metadata', None) or {}
        _conv_sq2.metadata['socratic_question_count'] = socratic_count
        storage.save(user_id, _data_sq2)
        if socratic_count >= 3:
            logger.info("Socratic limit: %d consecutive questions in conv %s", socratic_count, resolved_conversation_id[:8])
    # 刷新 assistant_node 对象，用于后续 yield done
    data = storage.load(user_id)
    assistant_node = data.nodes.get(asst_node_id) or assistant_node

    # P0: async meta history for assistant
    _p0_post_message_hooks(user_id, partition_id, assistant_node)

    # 5. 存储响应块
    data = storage.load(user_id)
    for block in response_blocks:
        data.response_blocks[block.id] = block
    storage.save(user_id, data)

    yield {
        "type": "done",
        "assistant_message": assistant_node.model_dump(mode="json"),
        "response_blocks": [b.model_dump(mode="json") for b in response_blocks],
    }

    # Phase 6: 流式路径 — 对话 → CognitiveNode 联动
    try:
        import asyncio as _cognitive_asyncio2
_cognitive_asyncio.get_running_loop()
        if loop.is_running():
            # 从上下文中找 skill_ids
            skill_ids = set()
            for block in response_blocks:
                for sid in getattr(assistant_node, 'discussed_skill_ids', []):
                    skill_ids.add(sid)
            if skill_ids:
                loop.create_task(_cognify_dialogue_context(
                    user_id, conversation, list(skill_ids),
                    context_type="lower",
                ))
    except Exception:
        logger.debug("CognitiveNode 流式路径联动跳过", exc_info=True)