"""
对话摘要存储 — conversation_summaries 表适配

现有表结构：
  id, conversation_id, user_id, round_number,
  summary, involved_node_ids, token_count, created_at

每 N 轮对话生成一次结构化摘要，用于长上下文裁剪。
"""
from __future__ import annotations

import json
import logging
import time
from typing import Any
from uuid import uuid4

from app.db.database import get_db

logger = logging.getLogger(__name__)

_SUMMARY_INTERVAL = 10  # 每 10 轮对话生成一次摘要


def save_summary(
    conversation_id: str,
    summary: str,
    user_id: str = "",
    round_number: int = 0,
    involved_node_ids: list[str] | None = None,
    token_count: int = 0,
) -> str:
    """保存一条对话摘要"""
    db = get_db()
    sid = str(uuid4())[:12]
    db.execute(
        """INSERT INTO conversation_summaries
           (id, conversation_id, user_id, round_number, summary, involved_node_ids, token_count)
           VALUES (%s, %s, %s, %s, %s, %s, %s)""",
        (
            sid, conversation_id, user_id, round_number, summary,
            involved_node_ids or [],
            token_count,
        ),
    )
    return sid


def get_recent_summaries(
    conversation_id: str, limit: int = 5,
) -> list[dict[str, Any]]:
    """获取最近的摘要（旧 → 新）"""
    db = get_db()
    rows = db.fetchall(
        """SELECT id, summary, involved_node_ids, round_number, token_count
           FROM conversation_summaries
           WHERE conversation_id = %s
           ORDER BY round_number DESC LIMIT %s""",
        (conversation_id, limit),
    )
    result = []
    for r in reversed(rows):
        ids = r.get("involved_node_ids")
        if isinstance(ids, str):
            ids = json.loads(ids)
        result.append({
            "id": r["id"],
            "summary": r["summary"],
            "involved_node_ids": ids or [],
            "round_number": r["round_number"],
        })
    return result


def build_condensed_context(
    conversation_id: str,
    recent_turns: list[dict[str, str]],
    max_recent: int = 5,
) -> str:
    """
    构建裁剪后的 LLM 上下文：
      最近 max_recent 轮完整消息 + 之前摘要
    """
    summaries = get_recent_summaries(conversation_id, limit=5)
    parts = []

    if summaries:
        parts.append("【对话历史摘要】")
        for s in summaries:
            parts.append(f"  - 第{s['round_number']}轮: {s['summary']}")

    if recent_turns:
        parts.append("")
        parts.append("【最近对话】")
        for turn in recent_turns[-max_recent:]:
            parts.append(f"  用户: {turn.get('user', '')}")
            parts.append(f"  助手: {turn.get('assistant', '')}")

    return "\n".join(parts)


def should_generate_summary(
    conversation_id: str, current_round: int,
) -> bool:
    """检查当前轮数是否需要进行摘要生成"""
    if current_round < _SUMMARY_INTERVAL:
        return False
    if current_round % _SUMMARY_INTERVAL == 0:
        db = get_db()
        row = db.fetchone(
            "SELECT id FROM conversation_summaries "
            "WHERE conversation_id = %s AND round_number = %s",
            (conversation_id, current_round),
        )
        return row is None
    return False
