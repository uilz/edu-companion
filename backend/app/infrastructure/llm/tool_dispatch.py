"""
工具调度模块：工具参数构建、结果摘要、工具调用回复生成

包含:
- _build_tool_params: 根据工具类型构建参数
- _summarize_tool_result: 提取工具结果关键信息
- _build_tool_context: 构建注入 LLM 的工具结果上下文
- generate_reply_with_tools: 带工具调用的回复生成（非流式）
"""

from __future__ import annotations

import json
import logging
from typing import Any

from app.schemas.conversation import (
    ResponseBlock,
)
from app.infrastructure.llm.llm_service import llm_service, _parse_tool_calls_response
from app.services.common import get_data_repo
from app.infrastructure.llm.tool_executor import tool_executor, SLOW_TOOLS
from app.infrastructure.llm.tool_repository import get_tool_repository

from app.infrastructure.llm.llm_core import _find_active_conversation, parse_sources
from app.services.conversation.context_pipeline import build_llm_messages

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════
# 工具调用辅助函数
# ═══════════════════════════════════════════════

def _build_tool_params(tool_name: str, user_text: str, partition, conversation=None) -> dict:
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
            "conversation_id": conversation.id if conversation else "",
            "bank_name": "",  # LLM 可指定
        }
    elif tool_name == "query_question_banks":
        return {
            "action": "list_banks",
            "keyword": user_text[:50],
            "limit": 10,
        }
    elif tool_name == "create_question_bank":
        return {
            "name": user_text[:80],
            "description": user_text[:200],
            "subject": subject,
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
        count = content.get("count", len(questions))
        bank_id = content.get("bank_id", "")
        return f"生成{count}道练习题（题库ID: {bank_id}），题目已保存到练习系统"
    elif tool_name == "query_question_banks":
        return content.get("summary", "查询题库完成")
    elif tool_name == "create_question_bank":
        if content.get("created"):
            bank = content.get("bank", {})
            return f"已创建题库「{bank.get('name')}」（ID: {bank.get('id')}）"
        return f"创建题库失败: {content.get('error', '未知错误')}"
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
    data = get_data_repo().load(user_id)
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
    detected_tools = [intent.action for intent in get_tool_repository().detect_intent(user_text, last_ai_text) if intent.action]
    logger.info("Detected tools: %s for text: %s", detected_tools, user_text[:50])

    # 构建上下文
    llm_messages = await build_llm_messages(partition, conversation, recent_messages, user_text, user_id)

    response_blocks: list[ResponseBlock] = []
    order = 0

    if detected_tools:
        # 🔧 修复：先执行工具 → 注入结果 → LLM统一回复
        tool_results: list[dict] = []
        for tool_name in detected_tools:
            try:
                # 构建工具参数
                params = _build_tool_params(tool_name, user_text, partition, conversation)
                tool_block = await tool_executor.execute(tool_name, params, user_id=user_id)
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
                    get_data_repo().save(user_id, data)
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
                user_id=user_id,
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
        tools = get_tool_repository().to_llm_schema()
        try:
            reply = await llm_service.generate(
                messages=llm_messages,
                task_type="chat",
                temperature=0.7,
                max_tokens=2048,
                tools=tools,
                user_id=user_id,
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
                    tool_block = await tool_executor.execute(tool_name, args, user_id=user_id)
                    tool_block.order = order
                    response_blocks.append(tool_block)
                    order += 1

                    tool_results.append({
                        "tool": tool_name,
                        "summary": _summarize_tool_result(tool_name, tool_block),
                    })

                    # 慢任务：提交后台作业
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
                        get_data_repo().save(user_id, data)

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
                    user_id=user_id,
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
    data = get_data_repo().load(user_id)
    for block in response_blocks:
        data.response_blocks[block.id] = block
    get_data_repo().save(user_id, data)

    return response_blocks
