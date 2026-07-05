"""
Project 服务层 — 节点版本控制（横切能力）

设计要点（ADR 0001 §2.1 + data-model.md §3）:
  - 字段级粒度: title/description/content/tags/... 各自独立维护版本
  - 一次修改只对**被修改的字段**入栈新版本
  - 未修改字段的版本号不变
  - 回滚本身产生新版本，保留回滚点（事件审计可追溯）
  - 支持任意两个历史版本 diff
"""
from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Any, Iterable
from uuid import uuid4

from app.infrastructure.db.database import get_db

logger = logging.getLogger(__name__)


# 节点可版本化字段（被纳入版本控制的内容字段）
VERSIONABLE_FIELDS: tuple[str, ...] = (
    "title",
    "description",
    "content",
    "rows",
    "columns",
    "code",
    "explanation",
    "language",
    "tags",
    "material_id",
    "chunk_id_range",
    "fragments",
    "linked_node_ids",
    "linked_material_ids",
    "linked_card_ids",
    "cross_project_refs",
)


# ────────────────────────────────────────────────────────────────
# 内部辅助
# ────────────────────────────────────────────────────────────────


def _new_uuid() -> str:
    return str(uuid4())


def _iso_now() -> str:
    return datetime.utcnow().isoformat()


def _load_node(node_id: str) -> dict | None:
    db = get_db()
    return db.fetchone("SELECT * FROM project_nodes WHERE id = %s", (node_id,))


def _json_dumps(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, default=str)


def _json_loads(value: Any, default: Any = None) -> Any:
    if value is None:
        return default
    if isinstance(value, (dict, list)):
        return value
    try:
        return json.loads(value)
    except (json.JSONDecodeError, TypeError):
        return default


# ────────────────────────────────────────────────────────────────
# 字段级 diff
# ────────────────────────────────────────────────────────────────


def diff_field_versions(
    node_id: str,
    version_a: int,
    version_b: int,
) -> dict[str, dict[str, Any]]:
    """比较两个历史版本之间的字段级差异。

    返回 {field_name: {"old": ..., "new": ..., "changed": bool}}

    特殊处理: v1 表示"初始状态"，无 node_versions 记录。
    这时取 v2..v_version 的累积状态作为 v1 的"new"值。
    """
    db = get_db()
    a_row = db.fetchone(
        "SELECT field_changes, changed_fields FROM node_versions "
        "WHERE node_id = %s AND version_number = %s",
        (node_id, version_a),
    )
    b_row = db.fetchone(
        "SELECT field_changes, changed_fields FROM node_versions "
        "WHERE node_id = %s AND version_number = %s",
        (node_id, version_b),
    )

    # 累积每条 version 之后的字段值
    def _state_at(target: int) -> dict[str, Any] | None:
        """返回截至 target 版本的"new"值映射。"""
        if target <= 1:
            # v1 是初始状态 — 拿 v2..v_target 的累积
            return None
        rows = db.fetchall(
            "SELECT field_changes FROM node_versions "
            "WHERE node_id = %s AND version_number BETWEEN 2 AND %s "
            "ORDER BY version_number ASC",
            (node_id, target),
        )
        if not rows:
            return None
        state: dict[str, Any] = {}
        for r in rows:
            changes = _json_loads(r["field_changes"], {})
            for f, c in changes.items():
                state[f] = c.get("new")
        return state

    a_state = _state_at(version_a)
    b_state = _state_at(version_b)

    if a_state is None and b_state is None:
        return {}

    # 累加初始基线：从 v2 到 max(a,b) 中间所有版本
    # 简化：若 a==1 则 a_state = {}，否则 a_state = 截至 a 的字段值
    if a_state is None:
        a_state = {}
    if b_state is None:
        b_state = {}

    all_fields = set(a_state.keys()) | set(b_state.keys())
    diff: dict[str, dict[str, Any]] = {}
    for field in all_fields:
        old_val = a_state.get(field)
        new_val = b_state.get(field)
        if old_val != new_val:
            diff[field] = {"old": old_val, "new": new_val, "changed": True}
    return diff


def compute_field_diff(
    old_payload: dict[str, Any],
    new_payload: dict[str, Any],
) -> tuple[list[str], dict[str, dict[str, Any]]]:
    """根据 old/new 字段字典计算字段级差异。

    返回 (changed_fields, field_changes)：
      - changed_fields: 发生变化的字段名列表
      - field_changes: {field: {"old": ..., "new": ...}}
    """
    changed: list[str] = []
    field_changes: dict[str, dict[str, Any]] = {}
    for field in VERSIONABLE_FIELDS:
        if field not in new_payload:
            continue
        old_val = old_payload.get(field)
        new_val = new_payload[field]
        if old_val != new_val:
            changed.append(field)
            field_changes[field] = {"old": old_val, "new": new_val}
    return changed, field_changes


# ────────────────────────────────────────────────────────────────
# 入栈新版本
# ────────────────────────────────────────────────────────────────


def _summarize_diff(field_changes: dict[str, dict[str, Any]]) -> str:
    """生成人类可读的变更摘要。"""
    if not field_changes:
        return "无变更"
    parts = []
    for field, change in field_changes.items():
        old = change.get("old")
        new = change.get("new")
        if old is None and new is not None:
            parts.append(f"+ {field}")
        elif old is not None and new is None:
            parts.append(f"- {field}")
        else:
            parts.append(f"~ {field}")
    return "修改字段: " + ", ".join(parts)


def push_version(
    node_id: str,
    new_payload: dict[str, Any],
    change_source: str = "user_edit",
    is_rollback: bool = False,
    rolled_back_from_version: int | None = None,
) -> dict | None:
    """入栈一个新的字段级版本。

    new_payload 中的字段若与当前值不同则记录到 node_versions，
    并相应更新 project_nodes.version。
    """
    node = _load_node(node_id)
    if not node:
        logger.warning("push_version: 节点不存在 %s", node_id)
        return None

    old_payload = {f: node.get(f) for f in VERSIONABLE_FIELDS}
    changed_fields, field_changes = compute_field_diff(old_payload, new_payload)

    if not changed_fields:
        logger.debug("push_version: 节点 %s 无字段变更", node_id)
        return None

    db = get_db()
    new_version_number = (node.get("version") or 1) + 1
    version_id = _new_uuid()
    summary = _summarize_diff(field_changes)

    db.execute(
        """
        INSERT INTO node_versions (
            id, node_id, version_number, field_changes, changed_fields,
            diff_summary, is_rollback, rolled_back_from_version, change_source
        ) VALUES (%s, %s, %s, %s::jsonb, %s::jsonb, %s, %s, %s, %s)
        """,
        (
            version_id,
            node_id,
            new_version_number,
            _json_dumps(field_changes),
            _json_dumps(changed_fields),
            summary,
            is_rollback,
            rolled_back_from_version,
            change_source,
        ),
    )

    # 更新节点本身
    set_clauses: list[str] = []
    set_params: list[Any] = []
    jsonb_fields = {
        "content", "rows", "columns", "chunk_id_range", "fragments",
        "linked_node_ids", "linked_material_ids", "linked_card_ids",
        "cross_project_refs", "tags",
    }
    for field, change in field_changes.items():
        new_val = change.get("new")
        if field in jsonb_fields:
            set_clauses.append(f"{field} = %s::jsonb")
            set_params.append(_json_dumps(new_val))
        else:
            set_clauses.append(f"{field} = %s")
            set_params.append(new_val)
    set_clauses.append("version = %s")
    set_params.append(new_version_number)
    set_clauses.append("updated_at = NOW()")
    set_params.append(node_id)

    if set_clauses:
        db.execute(
            f"UPDATE project_nodes SET {', '.join(set_clauses)} WHERE id = %s",
            tuple(set_params),
        )

    logger.info(
        "节点 %s 版本入栈 v%s (fields=%s, rollback=%s)",
        node_id, new_version_number, changed_fields, is_rollback,
    )
    return {
        "version_id": version_id,
        "version_number": new_version_number,
        "changed_fields": changed_fields,
        "diff_summary": summary,
        "is_rollback": is_rollback,
    }


# ────────────────────────────────────────────────────────────────
# 版本查询
# ────────────────────────────────────────────────────────────────


def list_versions(node_id: str, limit: int = 50) -> list[dict]:
    """列出节点的所有历史版本（最新在前）。"""
    db = get_db()
    rows = db.fetchall(
        """
        SELECT id, version_number, changed_fields, diff_summary,
               is_rollback, rolled_back_from_version, change_source, created_at
          FROM node_versions
         WHERE node_id = %s
         ORDER BY version_number DESC
         LIMIT %s
        """,
        (node_id, limit),
    )
    return [
        {
            "version_id": r["id"],
            "version_number": r["version_number"],
            "changed_fields": _json_loads(r["changed_fields"], []),
            "diff_summary": r["diff_summary"],
            "is_rollback": r["is_rollback"],
            "rolled_back_from_version": r["rolled_back_from_version"],
            "change_source": r["change_source"],
            "created_at": r["created_at"].isoformat() if r.get("created_at") else None,
        }
        for r in rows
    ]


def get_version(node_id: str, version_number: int) -> dict | None:
    """获取某个历史版本的内容快照。"""
    db = get_db()
    row = db.fetchone(
        """
        SELECT id, version_number, field_changes, changed_fields,
               diff_summary, is_rollback, rolled_back_from_version, change_source, created_at
          FROM node_versions
         WHERE node_id = %s AND version_number = %s
        """,
        (node_id, version_number),
    )
    if not row:
        return None
    return {
        "version_id": row["id"],
        "version_number": row["version_number"],
        "field_changes": _json_loads(row["field_changes"], {}),
        "changed_fields": _json_loads(row["changed_fields"], []),
        "diff_summary": row["diff_summary"],
        "is_rollback": row["is_rollback"],
        "rolled_back_from_version": row["rolled_back_from_version"],
        "change_source": row["change_source"],
        "created_at": row["created_at"].isoformat() if row.get("created_at") else None,
    }


# ────────────────────────────────────────────────────────────────
# 单字段 / 多字段回滚
# ────────────────────────────────────────────────────────────────


def rollback_to_version(
    node_id: str,
    target_version: int,
    fields: Iterable[str] | None = None,
) -> dict | None:
    """回滚节点到指定版本（可仅回滚部分字段）。

    回滚本身会产生新版本（version_number +1, is_rollback=True）。

    特殊处理: target_version=1 是初始状态，node_versions 表无对应记录。
    此时通过 v2 的 field_changes.old 字段重建 v1 状态。
    """
    target_values: dict[str, Any] = {}

    if target_version == 1:
        # 初始状态：取 v2.field_changes 的 old 值
        db = get_db()
        v2_row = db.fetchone(
            "SELECT field_changes FROM node_versions "
            "WHERE node_id = %s AND version_number = 2",
            (node_id,),
        )
        if v2_row:
            v2_changes = _json_loads(v2_row["field_changes"], {})
            for f, c in v2_changes.items():
                old_val = c.get("old")
                if old_val is not None:
                    target_values[f] = old_val
    else:
        target = get_version(node_id, target_version)
        if not target:
            return None
        # 从 target.field_changes 中取 "new" 字段值（目标版本写入的内容）
        target_values = {
            f: change["new"]
            for f, change in target.get("field_changes", {}).items()
        }

    if fields is not None:
        target_values = {f: target_values[f] for f in fields if f in target_values}

    if not target_values:
        logger.warning("rollback_to_version: 没有可回滚字段 (node=%s, target=%s)", node_id, target_version)
        return None

    return push_version(
        node_id=node_id,
        new_payload=target_values,
        change_source="rollback",
        is_rollback=True,
        rolled_back_from_version=target_version,
    )


# ────────────────────────────────────────────────────────────────
# Diff API
# ────────────────────────────────────────────────────────────────


def diff_versions(node_id: str, version_a: int, version_b: int) -> dict:
    """比较两个版本之间的字段级 diff。"""
    field_diff = diff_field_versions(node_id, version_a, version_b)
    return {
        "node_id": node_id,
        "version_a": version_a,
        "version_b": version_b,
        "field_diffs": field_diff,
        "changed_fields": list(field_diff.keys()),
    }
