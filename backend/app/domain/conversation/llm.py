"""
对话系统 LLM 服务（Facade）

基于树结构构建上下文，调用 LLM 生成回复。
支持多模态响应块（ResponseBlock）集成。

本模块是薄封装层，实际实现分布在：
- llm_core:      基础工具函数 + LLM 调用（非流式 / 流式）
- tool_dispatch:  工具参数构建 / 结果摘要 / 带工具调用的回复生成
- cognitive_sync: 对话后处理 — 知识证据分析 & CognitiveNode 联动
"""

from __future__ import annotations

import json
import logging
import re
from typing import AsyncGenerator

from app.schemas.conversation import (
    ContentBlock,
    TextBlock,
    TreeNode,
    ResponseBlock,
)
from app.services.common.storage import storage
from app.services.knowledge.tree_ops import tree_ops
from app.services.common.classifier import classifier
from app.services.llm.tool_executor import tool_executor, predict_tools, SLOW_TOOLS
from app.services.analytics.emotion_analyzer import emotion_analyzer

# (re-exports removed — import directly from sub-modules)

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════
# 公开 API：send_and_reply（非流式完整流程）
# ═══════════════════════════════════════════════

async def send_and_reply(
    user_id: str,
    partition_id: str,
    user_text: str,
    content_blocks: list[ContentBlock] | None = None,
    conversation_id: str = "",
    pending_quote: dict | None = None,
) -> dict:
    """
    完整流程：存用户消息 → 生成回复（含工具） → 存助手消息。
    返回两条消息和 response_blocks。
    """
    # 1. 存用户消息
    blocks = content_blocks or [TextBlock(text=user_text)]
    if pending_quote:
        from app.schemas.conversation import QuoteBlock
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

    # 2. 生成回复（含工具调用）- 如果有引用，把引用内容加入上下文
    enriched_text = user_text
    if pending_quote:
        qt = pending_quote.get("quoted_text", "")
        if qt:
            enriched_text = f"（引用上文：「{qt}」）\n{user_text}"
    response_blocks = await generate_reply_with_tools(user_id, partition_id, enriched_text)

    # 提取文本内容用于存储助手消息
    text_parts = []
    for block in response_blocks:
        if block.type == "text":
            text_parts.append(block.content.get("text", ""))
    reply_text = "\n\n".join(text_parts) if text_parts else ""

    # ── 追问问题解析：从回复中提取并清理 ──
    cleaned_reply, follow_up_questions = _parse_follow_up_questions(reply_text)
    if follow_up_questions:
        reply_text = cleaned_reply
        # 更新 response_blocks 中的文本内容
        for block in response_blocks:
            if block.type == "text":
                block.content["text"] = cleaned_reply

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
                from app.services.analytics.learning_events import record_event
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

    # ── 将追问问题写入 assistant node 的 metadata ──
    if follow_up_questions:
        data = storage.load(user_id)
        if assistant_node.id in data.nodes:
            data.nodes[assistant_node.id].metadata = data.nodes[assistant_node.id].metadata or {}
            data.nodes[assistant_node.id].metadata["follow_up_questions"] = follow_up_questions
            storage.save(user_id, data)

    return {
        "user_message": user_node,
        "assistant_message": assistant_node,
        "partition_id": partition_id,
        "response_blocks": [b.model_dump() for b in response_blocks],
    }


# ═══════════════════════════════════════════════
# 公开 API：send_and_reply_stream（流式完整流程）
# ═══════════════════════════════════════════════

# ── 追问问题解析 ──

FOLLOW_UP_RE = re.compile(
    r'<!--FOLLOW_UP-->\s*\n?(.*?)\n?<!--/FOLLOW_UP-->',
    re.DOTALL,
)

# ── 知识树探索意图关键词 ──
TREE_INTENT_PATTERNS = [
    r"(知识(结构|体系|图谱|树)|概念(图|关系)|思维导图|知识点(关系|链接))",
    r"(关系|依赖|前置|前后置|先修|拓展|延伸)",
    r"(能(不能|否|不能)?.*(列|画|展示|看看|梳理|整理|归类))",
    r"(整个|全部|所有).*(知识|概念|节点|内容|体系|框架)",
    r"(知识.*(掌握|学习|覆盖|关联|连通|组织|分类))",
    r"(结构|体系|框架|大纲|全景|概览|总览).*(知识|学习|内容|课程|学科)",
    r"(怎么|如何|怎样).*(安排|组织|构建|规划|设计|搭建).*(知识|学习|体系|框架)",
]


def _detect_tree_interest(user_text: str, reply_text: str, partition_id: str) -> dict | None:
    """检测用户是否对知识树探索感兴趣，返回推荐信息或 None"""
    import re
    combined = (user_text + " " + reply_text).lower()
    for pat in TREE_INTENT_PATTERNS:
        if re.search(pat, combined):
            # 检查该分区是否有知识树
            from app.services.common.storage import storage
            data = storage.load()
            graph = data.knowledge_graphs.get(partition_id)
            if graph and graph.nodes:
                pname = data.partitions[partition_id].name if partition_id in data.partitions else ""
                return {
                    "partition_id": partition_id,
                    "message": f"💡 这些知识点已整理成知识树，要不要去探索一下？",
                    "node_count": len(graph.nodes),
                    "edge_count": len(graph.edges),
                    "partition_name": pname,
                }
            elif not graph or not graph.nodes:
                return {
                    "partition_id": partition_id,
                    "message": "💡 需要为这个分区生成知识树吗？可以去知识树页面一键生成。",
                    "needs_generate": True,
                }
    return None


# ── 学习意图关键词（临时会话 → 推荐切换） ──
LEARN_INTENT_PATTERNS = [
    r"(学习|了解|掌握|理解|弄懂|搞懂|学会|学懂).*(什么|这个|哪个|知识|概念|内容|这门|这门课|这个学科)",
    r"(想|想要|希望|打算|计划|准备).*(学|了解|掌握|看|读).*(知识|概念|内容|课|课程|学科|书)",
    r"(这个|那|某|一个).*(知识点|概念|术语|公式|定理|定律|原理|方法|技巧)",
    r"(怎么|如何|怎样).*(学|学习|掌握|理解|入门|开始)",
    r"(推荐|建议|介绍).*(教材|书籍|资料|课程|课|资源|文章|视频)",
    r"(什么|哪些|有哪些).*(基础|前置|先修|预备|前提|准备).*(知识|课程|内容)",
    r"(教我|告诉我|讲讲|说说|解释|解释一下).*(什么|这个|那个|这些)",
]

# ── 行动模式 ──
ACTION_NEED_PATTERNS = [
    r"(帮我|请|麻烦).*(总结|归纳|整理|生成|创建|建|画)",
    r"(列|写|做个|制定|安排|规划).*(计划|方案|大纲|框架|路线图|学习计划)",
]


def _detect_temp_conv_intent(user_text: str, reply_text: str, partition_id: str) -> dict | None:
    """检测临时会话中用户是否有学习/探索特定主题的意图

    如果检测到：
    1. 学习某主题 → 推荐去对话系统创建相应学习会话
    2. 知识树探索 → 推荐去知识树页面
    3. 需要结构化整理 → 推荐知识树
    如果都未命中 → None
    """
    from app.services.common.storage import storage
    combined = (user_text + " " + reply_text).lower()
    data = storage.load()

    # 检查是否有知识树
    graph = data.knowledge_graphs.get(partition_id) if partition_id else None
    has_graph = bool(graph and graph.nodes)

    # 检测知识树探索意图
    for pat in TREE_INTENT_PATTERNS:
        if re.search(pat, combined):
            if has_graph:
                pname = data.partitions[partition_id].name if partition_id in data.partitions else ""
                return {
                    "type": "switch_to_tree",
                    "message": "💡 这些知识点在知识树中有组织结构，要不要去看看？",
                    "partition_id": partition_id,
                    "partition_name": pname,
                }
            else:
                return {
                    "type": "switch_to_tree",
                    "message": "💡 需要生成知识树来梳理这些知识吗？",
                    "needs_generate": True,
                }

    # 检测学习意图
    for pat in LEARN_INTENT_PATTERNS:
        if re.search(pat, combined):
            return {
                "type": "switch_to_learn",
                "message": "💡 看起来你对某个主题有兴趣，要不要创建一个学习会话？",
                "partition_id": partition_id,
                "create_conversation": True,
            }

    # 检测行动意图（整理/生成）
    for pat in ACTION_NEED_PATTERNS:
        if re.search(pat, combined):
            if has_graph:
                return {
                    "type": "switch_to_tree",
                    "message": "💡 要不要去知识树中整理这些内容？",
                    "partition_id": partition_id,
                }
            break

    return None


def _parse_follow_up_questions(reply_text: str) -> tuple[str, list[str]]:
    """从回复文本中解析追问问题，返回 (清理后的文本, 问题列表)。"""
    match = FOLLOW_UP_RE.search(reply_text)
    if not match:
        return reply_text, []
    raw = match.group(1).strip()
    # 清理后的回复（去掉 FOLLOW_UP 块）
    cleaned = FOLLOW_UP_RE.sub('', reply_text).strip()
    # 按换行分割，过滤空行，去掉编号前缀
    questions = [
        q.strip().lstrip('0123456789.、）) ')
        for q in raw.split('\n')
        if q.strip()
    ]
    # 最多取 3 个
    return cleaned, questions[:3]


async def send_and_reply_stream(
    user_id: str,
    partition_id: str,
    user_text: str,
    content_blocks: list[ContentBlock] | None = None,
    conversation_id: str = "",
    pending_quote: dict | None = None,
) -> AsyncGenerator[dict, None]:
    """
    完整流程（流式）：自动路由 → 存用户消息 → 预执行工具 → 流式生成回复 → 存助手消息。
    产出事件：context_switch / tool_block / token / done

    v4: 集成 auto_resolve 自动定位分区/领域/专题/对话，检测到切换时发出 context_switch。
    v5: 支持 pending_quote 引用块。
    """
    import asyncio

    # 0. 自动路由：分类 + 创建缺失层级 + 检测切换（线程池执行，不阻塞事件循环）
    route = await asyncio.to_thread(
        classifier.auto_resolve,
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
    # 如果有引用数据，添加 QuoteBlock 到 content_blocks
    if pending_quote:
        from app.schemas.conversation import QuoteBlock
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
    # 如果有引用，把引用内容加入上下文
    enriched_text = user_text
    if pending_quote:
        qt = pending_quote.get("quoted_text", "")
        if qt:
            enriched_text = f"（引用上文：「{qt}」）\n{user_text}"
    
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

    detected_tools = predict_tools(enriched_text, last_ai_text)
    logger.info("Streaming detected tools: %s for text: %s", detected_tools, enriched_text[:50])

    response_blocks: list[ResponseBlock] = []
    extra_tool_context = ""
    order = 0

    if detected_tools:
        tool_results: list[dict] = []
        for tool_name in detected_tools:
            try:
                params = _build_tool_params(tool_name, enriched_text, partition)
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
                    from app.services.common.background_jobs import job_manager
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

    # 2b. LLM function-calling 流式探测（regex 未命中时）
    # 流式调用：无工具时直接输出，有工具时执行后二次调用
    from app.services.llm.llm_service import llm_service, _parse_tool_calls_response
    from app.services.conversation.context_builder import _build_context_messages
    llm_probe_reply = ""
    probe_had_tools = False
    if not detected_tools and not extra_tool_context:
        probe_recent = []
        if conversation:
            for nid in conversation.path[-8:]:
                node = data.nodes.get(nid)
                if node and not node.is_deleted:
                    probe_recent.append(node)
        probe_messages = _build_context_messages(
            partition, conversation, probe_recent, enriched_text, user_id,
        )
        tools = tool_executor.get_tools_for_llm()
        try:
            # 流式探测：同时支持 tool_calls 和文本输出
            probe_accumulated = ""
            probe_tool_calls_raw: dict[int, dict] = {}  # index -> {id, name, arguments}
            async for chunk in llm_service.generate_stream(
                messages=probe_messages,
                task_type="chat",
                temperature=0.7,
                max_tokens=2048,
                tools=tools,
            ):
                probe_accumulated += chunk
                # 如果有文本内容且未检测到工具调用，直接 yield
                if not probe_had_tools:
                    yield {"type": "token", "content": chunk}
        except Exception as e:
            logger.error("LLM function-calling probe failed: %s", e)
            probe_accumulated = ""

        # 检查探测结果中是否有 tool_calls
        probe_tool_calls = _parse_tool_calls_response(probe_accumulated)
        if probe_tool_calls:
            probe_had_tools = True
            llm_probe_reply = ""  # 清空，工具执行后会二次调用
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
                        from app.services.common.background_jobs import job_manager
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

            for block in response_blocks:
                yield {"type": "tool_block", "block": block.model_dump(mode="json")}
        else:
            # 无工具调用 → 流式文本已直接 yield，无需二次调用
            llm_probe_reply = probe_accumulated

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
            # 流式探测已直接 yield 文本 → 直接使用结果，无需二次调用
            full_reply = llm_probe_reply
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

    # ── 追问问题解析：从回复中提取并清理 ──
    cleaned_reply, follow_up_questions = _parse_follow_up_questions(full_reply)
    if follow_up_questions:
        # 覆写清理后的文本（去掉 FOLLOW_UP 块）
        tree_ops.update_message_content(user_id, asst_node_id, cleaned_reply)
        full_reply = cleaned_reply
        logger.info("Follow-up questions extracted from reply: %d questions", len(follow_up_questions))
    else:
        follow_up_questions = None

    # 刷新 assistant_node 对象，用于后续 yield done
    data = storage.load(user_id)
    assistant_node = data.nodes.get(asst_node_id) or assistant_node

    # ── 将追问问题写入 assistant node 的 metadata ──
    if follow_up_questions:
        assistant_node.metadata = assistant_node.metadata or {}
        assistant_node.metadata["follow_up_questions"] = follow_up_questions
        data.nodes[assistant_node.id] = assistant_node
        storage.save(user_id, data)

    # P0: async meta history for assistant
    _p0_post_message_hooks(user_id, partition_id, assistant_node)

    # 5. 存储响应块（回填 message_id）
    data = storage.load(user_id)
    for block in response_blocks:
        block.message_id = assistant_node.id
        data.response_blocks[block.id] = block
    storage.save(user_id, data)

    yield {
        "type": "done",
        "assistant_message": assistant_node.model_dump(mode="json"),
        "response_blocks": [b.model_dump(mode="json") for b in response_blocks],
    }

    # ── P1: 对话 → 知识树 双向推荐 ──
    tree_rec = _detect_tree_interest(user_text, full_reply, partition_id)
    if tree_rec:
        yield {"type": "tree_recommendation", **tree_rec}

    # ── P2: 临时会话 → 学习推荐 ──
    if resolved_conversation_id:
        _data_temp = storage.load(user_id)
        _conv_temp = _data_temp.conversations.get(resolved_conversation_id)
        if _conv_temp and _conv_temp.is_temporary:
            temp_rec = _detect_temp_conv_intent(user_text, full_reply, resolved_partition_id)
            if temp_rec:
                yield {"type": "temp_recommendation", **temp_rec}

    # Phase 6: 流式路径 — 对话 → CognitiveNode 联动
    try:
        import asyncio as _cognitive_asyncio2
        loop = _cognitive_asyncio2.get_running_loop()
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
        logger.debug("认知对话上下文联动跳过（send_and_reply_stream）", exc_info=True)
