"""
元消息历史服务（Meta Message History）
异步写入每月JSONL分片，≤100MB/片。只存放不处理。
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
from datetime import datetime
from pathlib import Path

from app.schemas.conversation import TreeNode

logger = logging.getLogger(__name__)

BASE_DIR = Path(os.path.expanduser("~/.companion/history"))
MAX_SHARD_SIZE = 100 * 1024 * 1024  # 100MB


def _get_shard_path(user_id: str) -> Path:
    """获取当前月份的最新分片路径"""
    now = datetime.now()
    month_dir = BASE_DIR / user_id / now.strftime("%Y-%m")
    month_dir.mkdir(parents=True, exist_ok=True)

    # 找现有分片（≤100MB）
    shards = sorted(month_dir.glob("messages_*.jsonl"))
    if shards:
        latest = shards[-1]
        if latest.stat().st_size < MAX_SHARD_SIZE:
            return latest

    # 新建分片
    next_idx = len(shards) + 1
    return month_dir / f"messages_{next_idx:03d}.jsonl"


async def write_to_meta_history(user_id: str, node: TreeNode) -> None:
    """
    异步写入元消息历史
    
    在后台执行，不阻塞消息发送。
    写入格式：JSONL，每行一条消息的完整快照。
    """
    try:
        path = _get_shard_path(user_id)
        record = _node_to_record(node)

        # 异步写入（不阻塞）
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, _append_line, path, record)

        logger.debug("元历史已写入: %s (%s)", node.id, path.name)
    except Exception:
        logger.error("元历史写入失败: %s", node.id, exc_info=True)


def _node_to_record(node: TreeNode) -> dict:
    """将TreeNode转为元历史记录"""
    return {
        "id": node.id,
        "partition_id": node.partition_id,
        "branch_id": node.branch_id,
        "role": node.role,
        "content_blocks": [b.model_dump() for b in node.content_blocks],
        "text_summary": node.text_summary,
        "timestamp": node.timestamp,
        "token_count": node.token_count,
        "tree_metadata": {
            "parent_id": node.parent_id,
            "children_ids": node.children_ids,
            "is_deleted": node.is_deleted,
            "has_modified_version": node.has_modified_version,
        },
        "written_at": datetime.now().isoformat(),
    }


def _append_line(path: Path, record: dict) -> None:
    """追加一行JSONL"""
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")
