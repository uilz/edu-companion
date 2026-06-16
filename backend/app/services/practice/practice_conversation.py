"""
Practice Conversation 管理 — Conversation(type="practice") 全生命周期

练习会话统一使用 Conversation(type="practice") 存储在 UserData 中，
与知识树探索对话 (tree_exploration)、秘书对话 (secretary) 采用相同机制。

分区: 所有练习会话挂在专用 "📝 练习" 分区下。
"""

from __future__ import annotations

import logging
import time
from uuid import uuid4

from app.schemas.conversation import (
    Conversation, Partition, TextBlock, TreeNode, UserData,
)
from app.services.common import get_data_repo

logger = logging.getLogger(__name__)

PRACTICE_PARTITION_NAME = "📝 练习"


def ensure_practice_partition(user_id: str, data: UserData | None = None) -> tuple[str, UserData]:
    """确保存在练习专用分区，返回 (partition_id, data)。"""
    if data is None:
        data = get_data_repo().load(user_id)

    for pid, p in data.partitions.items():
        if p.name == PRACTICE_PARTITION_NAME:
            return pid, data

    # 创建练习分区
    partition = Partition(
        name=PRACTICE_PARTITION_NAME,
        subject="练习",
        direction="subject",
        emoji="📝",
        color="#FF6B35",
        root_id=str(uuid4()),
    )
    data.partitions[partition.id] = partition

    # 根节点
    root_node = TreeNode(
        id=partition.root_id, parent_id=partition.root_id,
        partition_id=partition.id, conversation_id="",
        role="assistant", content_blocks=[], text_summary="[practice_root]",
    )
    data.nodes[partition.root_id] = root_node

    get_data_repo().save(user_id, data)
    logger.info("练习分区已创建: %s", partition.id)
    return partition.id, data


def create_practice_conversation(
    user_id: str,
    session_id: str,
    bank_id: str,
    bank_name: str = "",
    question_count: int = 0,
    mode: str = "adaptive",
) -> str:
    """创建一条练习会话的 Conversation 记录。

    返回 conversation_id。
    """
    data = get_data_repo().load(user_id)
    partition_id, data = ensure_practice_partition(user_id, data)

    conv = Conversation(
        parent_id=partition_id,
        parent_type="partition",
        type="practice",
        name=bank_name or f"练习-{session_id[:8]}",
        metadata={
            "session_id": session_id,
            "bank_id": bank_id,
            "question_count": question_count,
            "mode": mode,
            "correct_count": 0,
            "wrong_count": 0,
            "score": None,
            "status": "created",
        },
    )
    conv.partition_id = partition_id

    # 创建根节点
    root_id = str(uuid4())
    root_node = TreeNode(
        id=root_id, parent_id=root_id,
        partition_id=partition_id, conversation_id=conv.id,
        role="assistant", content_blocks=[], text_summary="[practice_virtual_root]",
    )
    data.nodes[root_id] = root_node
    conv.path.append(root_id)

    data.conversations[conv.id] = conv
    get_data_repo().save(user_id, data)

    logger.info("练习会话 Conversation 已创建: conv=%s, session=%s", conv.id, session_id)
    return conv.id


def get_conversation_by_session(
    user_id: str,
    session_id: str,
    data: UserData | None = None,
) -> Conversation | None:
    """根据 session_id 查找对应的 Conversation。"""
    if data is None:
        data = get_data_repo().load(user_id)
    for conv in data.conversations.values():
        if conv.type == "practice" and conv.metadata.get("session_id") == session_id:
            return conv
    return None


def add_practice_answer_message(
    user_id: str,
    conversation_id: str,
    session_id: str,
    question_id: str,
    stem: str,
    user_answer: list,
    is_correct: bool,
    correct_answer: list,
    time_spent: int,
    hints_used: int,
    analysis: str = "",
) -> None:
    """在练习 Conversation 中添加一条答题消息。"""
    data = get_data_repo().load(user_id)
    conv = data.conversations.get(conversation_id)
    if not conv:
        logger.warning("Conversation %s not found, skipping practice message", conversation_id)
        return

    # 创建答题消息节点
    node = TreeNode(
        parent_id=conv.path[-1] if conv.path else conv.id,
        partition_id=conv.partition_id,
        conversation_id=conversation_id,
        role="assistant",
        content_blocks=[
            TextBlock(text=f"[练习] {stem[:80]}"),
        ],
        text_summary=f"答题: {'✓' if is_correct else '✗'} {stem[:60]}",
        metadata={
            "type": "practice_answer",
            "question_id": question_id,
            "session_id": session_id,
            "user_answer": user_answer,
            "is_correct": is_correct,
            "correct_answer": correct_answer,
            "time_spent_seconds": time_spent,
            "hints_used": hints_used,
            "explanation": analysis[:200] if analysis else "",
        },
    )
    data.nodes[node.id] = node
    conv.path.append(node.id)
    conv.last_message_at = time.time()

    # 更新 metadata 统计
    meta = conv.metadata
    meta["last_question_id"] = question_id
    meta["answered_count"] = meta.get("answered_count", 0) + 1
    if is_correct:
        meta["correct_count"] = meta.get("correct_count", 0) + 1
    else:
        meta["wrong_count"] = meta.get("wrong_count", 0) + 1
    conv.metadata = meta

    data.conversations[conversation_id] = conv
    get_data_repo().save(user_id, data)


def update_conversation_on_complete(
    user_id: str,
    session_id: str,
    correct_count: int,
    wrong_count: int,
    score: float,
    duration_seconds: int | None,
) -> None:
    """完成练习后更新 Conversation 元数据。"""
    data = get_data_repo().load(user_id)
    conv = get_conversation_by_session(user_id, session_id, data)
    if not conv:
        logger.warning("练习会话 %s 无对应 Conversation", session_id)
        return

    meta = conv.metadata
    meta["status"] = "completed"
    meta["correct_count"] = correct_count
    meta["wrong_count"] = wrong_count
    meta["score"] = score
    meta["duration_seconds"] = duration_seconds
    conv.metadata = meta

    # summary
    total = correct_count + wrong_count
    conv.practice_summary = f"{correct_count}/{total} 正确 ({score}%), {duration_seconds or 0}s"
    conv.summary_dirty = True

    data.conversations[conv.id] = conv
    get_data_repo().save(user_id, data)
    logger.info("练习会话 Conversation 已更新: session=%s, score=%.1f%%", session_id, score)


def complete_practice_conversation(
    session_id: str,
    user_id: str,
    stats: dict,
) -> None:
    """练习完成后的 Conversation 更新入口（适配 practice_session.py 调用）。

    stats 格式: {"score": ..., "total": ..., "correct": ..., "wrong": ...}
    """
    update_conversation_on_complete(
        user_id=user_id,
        session_id=session_id,
        correct_count=stats.get("correct", 0),
        wrong_count=stats.get("wrong", 0),
        score=stats.get("score", 0),
        duration_seconds=stats.get("duration_seconds"),
    )
