"""Reading 节点引用解析 (@概念名) — 简化版

依据 docs/modules/reading/overview.md §4
- 复用 Project 的 node_ref 解析思想
- 阅读场景：用户笔记中写 "@概念名" 解析为 linked_node_ids 列表
- 不做循环检测 / 跨项目引用（阅读场景不必要）

实现要点：
  1. @@node:<uuid> → 直接通过 ID 查询 CognitiveNode
  2. @概念名 → 在知识图谱中搜索匹配 label
  3. 无法解析的 token → 静默忽略（仅记录 raw string 作为标签）
"""
from __future__ import annotations

import re
from typing import Any

# 引用语法
_REF_NODE_ID = re.compile(r"@@node:(?P<node_id>[0-9a-fA-F-]{8,})")
_REF_TITLE = re.compile(r"@(?P<name>[^\s@,;，；：:]+)")


def parse_references(text: str) -> list[dict[str, str]]:
    """从文本中提取所有 @引用 token 列表。

    返回 [{"type": "id" | "title", "value": "..."}, ...]
    """
    if not text:
        return []
    out: list[dict[str, str]] = []
    seen: set[str] = set()

    # 1) 显式 ID 引用
    for m in _REF_NODE_ID.finditer(text):
        tok = f"@@node:{m.group('node_id')}"
        if tok not in seen:
            seen.add(tok)
            out.append({"type": "id", "value": tok})

    # 2) 标题引用
    consumed = [(m.start(), m.end()) for m in _REF_NODE_ID.finditer(text)]

    def _consumed(pos: int) -> bool:
        return any(s <= pos < e for s, e in consumed)

    for m in _REF_TITLE.finditer(text):
        if _consumed(m.start()):
            continue
        tok = m.group("name").strip()
        if tok and tok not in seen:
            seen.add(tok)
            out.append({"type": "title", "value": tok})

    return out


def resolve_references(user_id: str, text: str) -> list[str]:
    """解析 @引用 为 node_id 列表。

    解析规则（按优先级）：
      1. @@node:<uuid> → 直接通过 ID 查询 knowledge_nodes
      2. @概念名 → 在 knowledge_nodes 中按 label 匹配
      3. 无法解析的 → 忽略
    """
    from app.infrastructure.db.database import get_db
    db = get_db()
    refs = parse_references(text)
    resolved: list[str] = []
    seen: set[str] = set()
    for ref in refs:
        node_id = _resolve_one(db, user_id, ref)
        if node_id and node_id not in seen:
            seen.add(node_id)
            resolved.append(node_id)
    return resolved


def _resolve_one(db: Any, user_id: str, ref: dict[str, str]) -> str | None:
    """解析单个 @引用 token。"""
    if ref["type"] == "id":
        node_id = ref["value"][len("@@node:"):]
        try:
            row = db.fetchone(
                "SELECT id FROM knowledge_nodes WHERE id = %s AND user_id = %s AND deleted_at IS NULL",
                (node_id, user_id),
            )
            return row["id"] if row else None
        except Exception:
            return None
    # title 匹配
    title = ref["value"]
    try:
        row = db.fetchone(
            """
            SELECT id FROM knowledge_nodes
            WHERE user_id = %s AND deleted_at IS NULL
              AND label = %s
            ORDER BY level ASC NULLS LAST
            LIMIT 1
            """,
            (user_id, title),
        )
        if row:
            return row["id"]
    except Exception:
        pass
    return None
