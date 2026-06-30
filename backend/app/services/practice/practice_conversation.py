"""
Practice Conversation 管理 — DirectoryNode(type="conv", kind="practice") 全生命周期

练习会话使用 DirectoryNode(node_type="conv", kind="practice") 来存储，
与对话系统采用统一的数据模型。
"""

from __future__ import annotations

import logging
import time
from uuid import uuid4

from app.schemas.conversation import (
    TextBlock, TreeNode, UserData,
)
from app.schemas.directory_node import DirectoryNode
from app.services.common import get_data_repo

logger = logging.getLogger(__name__)

PRACTICE_PARTITION_NAME = "📝 练习"


def ensure_practice_partition(user_id: str, data: UserData | None = None) -> tuple[str, UserData]:
    """确保存在练习专用目录，返回 (dir_id, data)。"""
    if data is None:
        data = get_data_repo().load(user_id)

    # 在 directory_nodes 中查找练习目录
    for nid, n in data.directory_nodes.items():
        if n.node_type == "dir" and n.name == PRACTICE_PARTITION_NAME:
            return nid, data

    # 创建练习目录
    from app.services.knowledge.tree_service import tree_ops
    try:
        partition = tree_ops.create_dir(
            user_id=user_id,
            parent_id=next(iter(data.directory_nodes)).id if data.directory_nodes else "",
            name=PRACTICE_PARTITION_NAME,
            emoji="📝",
            kind="practice",
        )
        # reload to get updated data
        data = get_data_repo().load(user_id)
    except Exception:
        # fallback: 直接创建 DirectoryNode
        dir_id = f"dir_{uuid4().hex[:12]}"
        partition = DirectoryNode(
            id=dir_id,
            node_type="dir",
            kind="practice",
            name=PRACTICE_PARTITION_NAME,
        )
        data.directory_nodes[dir_id] = partition
        get_data_repo().save(user_id, data)

    logger.info("练习目录已创建/找到: %s", partition.id)
    return partition.id, data


def create_practice_conversation(
    user_id: str,
    session_id: str,
    bank_id: str,
    bank_name: str = "",
    question_count: int = 0,
    mode: str = "adaptive",
) -> str:
    """创建一条练习会话。

    返回 directory_node id (即 conv_id)。
    """
    data = get_data_repo().load(user_id)
    dir_id, data = ensure_practice_partition(user_id, data)

    conv = DirectoryNode(
        node_type="conv",
        kind="practice",
        parent_id=dir_id,
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
            "dir_id": dir_id,
        },
    )
    # 创建根节点
    root_id = str(uuid4())
    root_node = TreeNode(
        id=root_id, parent_id=root_id,
        directory_id=conv.id,
        role="assistant", content_blocks=[], text_summary="[practice_virtual_root]",
    )
    data.nodes[root_id] = root_node
    conv.conv_message_ids = [root_id]

    data.directory_nodes[conv.id] = conv
    get_data_repo().save(user_id, data)

    logger.info("练习会话创建: conv=%s, session=%s", conv.id, session_id)
    return conv.id


def get_conversation_by_session(
    user_id: str,
    session_id: str,
    data: UserData | None = None,
) -> DirectoryNode | None:
    """根据 session_id 查找对应的练习会话。"""
    if data is None:
        data = get_data_repo().load(user_id)
    for n in data.directory_nodes.values():
        if n.node_type == "conv" and n.kind == "practice":
            meta = n.metadata or {}
            if meta.get("session_id") == session_id:
                return n
    return None


def add_practice_answer_message(
    user_id: str,
    conv_id: str,
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
    """在练习会话中添加一条答题消息。"""
    data = get_data_repo().load(user_id)
    conv = data.directory_nodes.get(conv_id)
    if not conv:
        logger.warning("练习会话 %s 不存在", conv_id)
        return

    msg_ids = conv.conv_message_ids or []
    parent_id = msg_ids[-1] if msg_ids else conv.id

    # 创建答题消息节点
    node = TreeNode(
        parent_id=parent_id,
        directory_id=conv_id,
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
    conv.conv_message_ids = msg_ids + [node.id]
    conv.updated_at = time.time()

    # 更新 metadata 统计
    meta = conv.metadata or {}
    meta["last_question_id"] = question_id
    meta["answered_count"] = meta.get("answered_count", 0) + 1
    if is_correct:
        meta["correct_count"] = meta.get("correct_count", 0) + 1
    else:
        meta["wrong_count"] = meta.get("wrong_count", 0) + 1
    conv.metadata = meta

    data.directory_nodes[conv_id] = conv
    get_data_repo().save(user_id, data)


def update_conversation_on_complete(
    user_id: str,
    session_id: str,
    correct_count: int,
    wrong_count: int,
    score: float,
    duration_seconds: int | None,
) -> None:
    """完成练习后更新目录节点元数据。"""
    data = get_data_repo().load(user_id)
    conv = get_conversation_by_session(user_id, session_id, data)
    if not conv:
        logger.warning("练习会话 %s 无对应节点", session_id)
        return

    meta = conv.metadata or {}
    meta["status"] = "completed"
    meta["correct_count"] = correct_count
    meta["wrong_count"] = wrong_count
    meta["score"] = score
    meta["duration_seconds"] = duration_seconds
    conv.metadata = meta

    total = correct_count + wrong_count
    meta["summary"] = f"{correct_count}/{total} 正确 ({score}%), {duration_seconds or 0}s"

    data.directory_nodes[conv.id] = conv
    get_data_repo().save(user_id, data)
    logger.info("练习会话已更新: session=%s, score=%.1f%%", session_id, score)


def complete_practice_conversation(
    session_id: str,
    user_id: str,
    stats: dict,
) -> None:
    """练习完成后的更新入口（适配 practice_session.py 调用）。"""
    update_conversation_on_complete(
        user_id=user_id,
        session_id=session_id,
        correct_count=stats.get("correct", 0),
        wrong_count=stats.get("wrong", 0),
        score=stats.get("score", 0),
        duration_seconds=stats.get("duration_seconds"),
    )
