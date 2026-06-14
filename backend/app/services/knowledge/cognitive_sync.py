"""
认知同步模块：对话后处理 — 知识证据分析 & CognitiveNode 联动

包含:
- _p0_post_message_hooks: 消息后处理（元历史 / 分支重命名 / 图谱更新）
- _trigger_graph_update: 分支命名后触发知识图谱更新
- _analyze_conversation_evidence: 对话知识证据分析
- _cognify_dialogue_context: 对话上下文联动 → CognitiveNode
"""

from __future__ import annotations

import logging
from typing import Any

from app.schemas.directory_node import MessageNode
from app.services.common import get_data_repo

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════
# P0 钩子：消息后处理（元历史 / 分支重命名 / 图谱更新）
# ═══════════════════════════════════════════════

def _p0_post_message_hooks(user_id: str, partition_id: str, node: MessageNode) -> None:
    """消息存储后的 P0 钩子：异步写元历史 + 触发分支命名/摘要"""
    import asyncio
    try:
        loop = asyncio.get_running_loop()
        if loop.is_running():
            from app.services.analytics.meta_history import write_to_meta_history
            loop.create_task(write_to_meta_history(user_id, node))

            data = get_data_repo().load(user_id)
            conv_id = node.directory_id or node.conversation_id
            conv = data.directory_nodes.get(conv_id) if conv_id else None
            if conv and conv.node_type == "conv":
                msg_count = len(conv.conv_message_ids)
                from app.services.conversation.branch_summarizer import (
                    try_auto_rename_branch, generate_branch_summary, update_partition_context,
                )

                async def _do_rename():
                    new_name = await try_auto_rename_branch(user_id, conv_id, msg_count)
                    if new_name:
                        _data = get_data_repo().load(user_id)
                        _conv = _data.directory_nodes.get(conv_id)
                        if _conv:
                            _conv.name = new_name
                            get_data_repo().save(user_id, _data)
                            # 分支命名后 → 异步更新知识图谱
                            _trigger_graph_update(user_id, conv_id, new_name)

                loop.create_task(_do_rename())

                if msg_count >= 10 and msg_count % 10 == 0:
                    generate_branch_summary(user_id, conv_id)
                if msg_count % 5 == 0:
                    update_partition_context(user_id, partition_id)
    except Exception:
        logger.debug("P0 hooks skipped")


def _trigger_graph_update(user_id: str, conversation_id: str, new_branch_name: str) -> None:
    """分支命名后异步触发知识图谱更新（fire and forget）"""
    async def _update():
        try:
            data = get_data_repo().load(user_id)
            conv = data.directory_nodes.get(conversation_id)
            if not conv or conv.node_type != "conv":
                return

            # 沿 parent 链向上找到根 dir 节点（旧模型中即 partition）
            root_dir_id = None
            current_id = conv.parent_id
            while current_id:
                parent = data.directory_nodes.get(current_id)
                if not parent:
                    break
                if parent.node_type == "dir" and parent.parent_id is None:
                    root_dir_id = parent.id
                    break
                current_id = parent.parent_id

            if not root_dir_id:
                return

            # 已存在的图谱 → 增量合并；不存在 → 新建
            data.knowledge_graphs.get(root_dir_id)

            from app.api.knowledge.knowledge_routes import generate_graph_logic
            await generate_graph_logic(
                user_id=user_id,
                partition_id=root_dir_id,
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
    """分析一轮对话，提取知识证据（通过 CognitiveNode 事件系统）"""
    try:
        from app.services.knowledge.cognitive_queries import analyze_dialogue_evidence
        from app.services.common import get_data_repo as _st

        # 从 partition 推断涉及的技能（通过 CognitiveNode 查找实际 node_id）
        from app.domain.cognitive import get_repo
        data = _st.load(user_id)
        from app.infrastructure.llm.llm_core import _find_active_conversation
        conversation = data.conversations.get(conversation_id) if conversation_id else _find_active_conversation(data, partition_id)
        partition = data.partitions.get(partition_id)
        skill_ids = []
        if partition:
            label_to_lookup = partition.name or getattr(partition, 'subject', None)
            if label_to_lookup:
                node = get_repo().find_node_by_label(label_to_lookup, user_id)
                if node:
                    skill_ids = [node.id]
                elif getattr(partition, 'subject', None) and partition.subject != label_to_lookup:
                    node = get_repo().find_node_by_label(partition.subject, user_id)
                    if node:
                        skill_ids = [node.id]

        if skill_ids:
            evidence = await analyze_dialogue_evidence(
                user_text=user_text,
                assistant_reply=assistant_reply,
                skill_ids=skill_ids,
            )
            if evidence:
                logger.debug(f"对话证据检测: {evidence}")
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
        from app.domain.cognitive.events import submit_dialogue_context
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
    except ImportError as e:
        logger.warning("Cognitive context module not available, skipping: %s", e)
    except Exception as e:
        logger.debug(f"认知对话上下文联动跳过: {e}")
