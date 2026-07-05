"""Project 服务层 — 顶层入口

聚合 versioning + node_ref + 节点 CRUD 的主 service。
"""
from __future__ import annotations

import json
import logging
import os
from datetime import datetime
from typing import Any
from uuid import uuid4

from app.infrastructure.db.database import get_db

logger = logging.getLogger(__name__)


# ────────────────────────────────────────────────────────────────
# 建表（幂等）
# ────────────────────────────────────────────────────────────────


def ensure_tables() -> None:
    """确保 project_* 表存在（幂等）。

    使用 execute_batch 一次性执行所有 DDL，避免按 ; 拆分破坏多语句。
    """
    db = get_db()
    candidates = [
        "app/infrastructure/db/project_schema.sql",
        "backend/app/infrastructure/db/project_schema.sql",
        os.path.join(os.path.dirname(__file__), "../../infrastructure/db/project_schema.sql"),
    ]
    sql_path = None
    for p in candidates:
        if os.path.exists(p):
            sql_path = p
            break
    if not sql_path:
        logger.error("找不到 project_schema.sql")
        return
    with open(sql_path) as f:
        sql = f.read()
    try:
        db.execute(sql)
    except Exception as exc:  # noqa: BLE001
        logger.warning("建表失败 (单次执行失败, 尝试拆分): %s", exc)
        # 拆分重试（用于 PG 不支持多语句的情况）
        for stmt in sql.split(";"):
            s = stmt.strip()
            if not s:
                continue
            try:
                db.execute(s)
            except Exception as exc2:  # noqa: BLE001
                logger.debug("建表语句跳过: %s | %s", s[:80], exc2)


def _new_uuid() -> str:
    return str(uuid4())


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
# 项目 CRUD
# ────────────────────────────────────────────────────────────────


def _row_to_project(row: dict | None) -> dict | None:
    if not row:
        return None
    return {
        "id": row["id"],
        "user_id": row["user_id"],
        "name": row["name"],
        "description": row.get("description"),
        "template_id": row.get("template_id"),
        "template_version": row.get("template_version"),
        "status": row.get("status") or "active",
        "tags": _json_loads(row.get("tags"), []),
        "node_count": row.get("node_count") or 0,
        "completed_node_count": row.get("completed_node_count") or 0,
        "created_at": row["created_at"].isoformat() if row.get("created_at") else None,
        "updated_at": row["updated_at"].isoformat() if row.get("updated_at") else None,
    }


def list_projects(user_id: str, status: str | None = None) -> list[dict]:
    ensure_tables()
    db = get_db()
    if status:
        rows = db.fetchall(
            "SELECT * FROM projects WHERE user_id = %s AND status = %s ORDER BY updated_at DESC",
            (user_id, status),
        )
    else:
        rows = db.fetchall(
            "SELECT * FROM projects WHERE user_id = %s ORDER BY updated_at DESC",
            (user_id,),
        )
    return [p for p in (_row_to_project(r) for r in rows) if p]


def get_project(user_id: str, project_id: str) -> dict | None:
    ensure_tables()
    db = get_db()
    row = db.fetchone(
        "SELECT * FROM projects WHERE id = %s AND user_id = %s",
        (project_id, user_id),
    )
    return _row_to_project(row)


def create_project(
    user_id: str,
    name: str,
    description: str | None = None,
    template_id: str | None = None,
    template_version: int | None = None,
    tags: list[str] | None = None,
) -> dict:
    ensure_tables()
    db = get_db()
    project_id = _new_uuid()
    db.execute(
        """
        INSERT INTO projects (id, user_id, name, description, template_id,
                              template_version, tags, status, created_at, updated_at)
        VALUES (%s, %s, %s, %s, %s, %s, %s::jsonb, 'active', NOW(), NOW())
        """,
        (
            project_id, user_id, name, description, template_id, template_version,
            _json_dumps(tags or []),
        ),
    )
    return get_project(user_id, project_id)  # type: ignore[return-value]


def update_project(
    user_id: str,
    project_id: str,
    name: str | None = None,
    description: str | None = None,
    status: str | None = None,
    tags: list[str] | None = None,
) -> dict | None:
    db = get_db()
    sets: list[str] = []
    params: list[Any] = []
    if name is not None:
        sets.append("name = %s")
        params.append(name)
    if description is not None:
        sets.append("description = %s")
        params.append(description)
    if status is not None:
        sets.append("status = %s")
        params.append(status)
    if tags is not None:
        sets.append("tags = %s::jsonb")
        params.append(_json_dumps(tags))
    if not sets:
        return get_project(user_id, project_id)
    sets.append("updated_at = NOW()")
    params.extend([project_id, user_id])
    db.execute(
        f"UPDATE projects SET {', '.join(sets)} WHERE id = %s AND user_id = %s",
        tuple(params),
    )
    return get_project(user_id, project_id)


def delete_project(user_id: str, project_id: str) -> bool:
    db = get_db()
    db.execute("DELETE FROM projects WHERE id = %s AND user_id = %s", (project_id, user_id))
    return True


# ────────────────────────────────────────────────────────────────
# 节点 CRUD
# ────────────────────────────────────────────────────────────────


def _row_to_node(row: dict | None) -> dict | None:
    if not row:
        return None
    return {
        "id": row["id"],
        "user_id": row["user_id"],
        "project_id": row["project_id"],
        "parent_id": row.get("parent_id"),
        "type": row.get("type"),
        "title": row.get("title"),
        "description": row.get("description"),
        "order_in_parent": row.get("order_in_parent") or 0,
        "tags": _json_loads(row.get("tags"), []),
        "content": _json_loads(row.get("content")),
        "rows": _json_loads(row.get("rows")),
        "columns": _json_loads(row.get("columns")),
        "language": row.get("language"),
        "code": row.get("code"),
        "explanation": row.get("explanation"),
        "material_id": row.get("material_id"),
        "chunk_id_range": _json_loads(row.get("chunk_id_range")),
        "fragments": _json_loads(row.get("fragments")),
        "linked_node_ids": _json_loads(row.get("linked_node_ids"), []),
        "linked_material_ids": _json_loads(row.get("linked_material_ids"), []),
        "linked_card_ids": _json_loads(row.get("linked_card_ids"), []),
        "cross_project_refs": _json_loads(row.get("cross_project_refs"), []),
        "version": row.get("version") or 1,
        "is_archived": row.get("is_archived") or False,
        "status": row.get("status", "active"),
        "completed_at": row["completed_at"].isoformat() if row.get("completed_at") else None,
        "created_at": row["created_at"].isoformat() if row.get("created_at") else None,
        "updated_at": row["updated_at"].isoformat() if row.get("updated_at") else None,
    }


def list_nodes(
    user_id: str,
    project_id: str,
    include_archived: bool = False,
    parent_id: str | None = None,
) -> list[dict]:
    ensure_tables()
    db = get_db()
    sql = "SELECT * FROM project_nodes WHERE project_id = %s AND user_id = %s"
    params: list[Any] = [project_id, user_id]
    if not include_archived:
        sql += " AND is_archived = FALSE"
    if parent_id is not None:
        sql += " AND parent_id = %s"
        params.append(parent_id)
    sql += " ORDER BY order_in_parent ASC, created_at ASC"
    rows = db.fetchall(sql, tuple(params))
    return [n for n in (_row_to_node(r) for r in rows) if n]


def get_node(user_id: str, project_id: str, node_id: str) -> dict | None:
    ensure_tables()
    db = get_db()
    row = db.fetchone(
        "SELECT * FROM project_nodes WHERE id = %s AND project_id = %s AND user_id = %s",
        (node_id, project_id, user_id),
    )
    return _row_to_node(row)


def create_node(
    user_id: str,
    project_id: str,
    type: int,
    title: str,
    parent_id: str | None = None,
    description: str | None = None,
    tags: list[str] | None = None,
    content: dict | None = None,
    rows: list | None = None,
    columns: list | None = None,
    language: str | None = None,
    code: str | None = None,
    explanation: str | None = None,
    material_id: str | None = None,
    chunk_id_range: dict | None = None,
    fragments: list | None = None,
    linked_node_ids: list | None = None,
    linked_material_ids: list | None = None,
    linked_card_ids: list | None = None,
    cross_project_refs: list | None = None,
    order_in_parent: int | None = None,
    node_id: str | None = None,
    increment_project_count: bool = True,
) -> dict | None:
    """创建项目节点（领域服务公共方法）。

    所有跨项目复制 / 模板实例化 / 跨模块导入都应走本方法，避免在外部
    直接 `INSERT INTO project_nodes` 造成字段漂移、计数错乱、版本不一致。

    Args:
        order_in_parent:       显式指定顺序（不传则自动追加到末尾）
        node_id:               显式指定 UUID（用于跨项目复制时保持映射）
        increment_project_count: 批量场景下可置 False，最后由调用方合并 +1
    """
    ensure_tables()
    db = get_db()
    proj = db.fetchone("SELECT id FROM projects WHERE id = %s AND user_id = %s", (project_id, user_id))
    if not proj:
        return None

    if not node_id:
        node_id = _new_uuid()

    if order_in_parent is None:
        order_row = db.fetchone(
            "SELECT COALESCE(MAX(order_in_parent), -1) AS m FROM project_nodes "
            "WHERE project_id = %s AND (parent_id = %s OR (parent_id IS NULL AND %s IS NULL))",
            (project_id, parent_id, parent_id),
        )
        order_in_parent = (order_row["m"] + 1) if order_row else 0

    db.execute(
        """
        INSERT INTO project_nodes (
            id, user_id, project_id, parent_id, type, title, description,
            order_in_parent, tags,
            content, rows, columns, language, code, explanation,
            material_id, chunk_id_range, fragments,
            linked_node_ids, linked_material_ids, linked_card_ids, cross_project_refs,
            version, created_at, updated_at
        ) VALUES (
            %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb,
            %s::jsonb, %s::jsonb, %s::jsonb, %s, %s, %s, %s, %s::jsonb, %s::jsonb,
            %s::jsonb, %s::jsonb, %s::jsonb, %s::jsonb,
            1, NOW(), NOW()
        )
        """,
        (
            node_id, user_id, project_id, parent_id, type, title, description,
            order_in_parent, _json_dumps(tags or []),
            _json_dumps(content), _json_dumps(rows), _json_dumps(columns),
            language, code, explanation, material_id,
            _json_dumps(chunk_id_range), _json_dumps(fragments),
            _json_dumps(linked_node_ids or []),
            _json_dumps(linked_material_ids or []),
            _json_dumps(linked_card_ids or []),
            _json_dumps(cross_project_refs or []),
        ),
    )

    if increment_project_count:
        db.execute(
            "UPDATE projects SET node_count = node_count + 1, updated_at = NOW() "
            "WHERE id = %s",
            (project_id,),
        )

    return get_node(user_id, project_id, node_id)


def create_node_batch(
    user_id: str,
    project_id: str,
    nodes: list[dict],
) -> list[dict | None]:
    """批量创建项目节点（领域服务公共方法）。

    内部委托给 :func:`create_node`；为避免 N 次 node_count 更新，
    最后一次性累加。所有 dict payload 接受与 create_node 相同的字段。

    Args:
        user_id:    所属用户
        project_id: 目标项目
        nodes:      节点 payload 列表，每个 payload 至少需含 `type` + `title`

    Returns:
        与入参等长的创建结果列表（None 表示该节点未成功创建）
    """
    if not nodes:
        return []
    created: list[dict | None] = []
    for payload in nodes:
        node = create_node(
            user_id=user_id,
            project_id=project_id,
            increment_project_count=False,  # 批量累加，最后统一更新
            **payload,
        )
        created.append(node)
    # 一次性累加 node_count（仅统计成功创建）
    success_count = sum(1 for n in created if n is not None)
    if success_count:
        ensure_tables()
        db = get_db()
        db.execute(
            "UPDATE projects SET node_count = node_count + %s, updated_at = NOW() "
            "WHERE id = %s",
            (success_count, project_id),
        )
    return created


def update_node(
    user_id: str,
    project_id: str,
    node_id: str,
    payload: dict,
) -> dict | None:
    """更新节点（带字段级版本入栈）。"""
    ensure_tables()
    from app.services.project.versioning import push_version
    db = get_db()

    node = db.fetchone(
        "SELECT * FROM project_nodes WHERE id = %s AND project_id = %s AND user_id = %s",
        (node_id, project_id, user_id),
    )
    if not node:
        return None

    # 解析 payload（自动 JSON 化）
    normalized: dict[str, Any] = {}
    for k, v in payload.items():
        if v is None:
            continue
        if isinstance(v, (dict, list)):
            normalized[k] = v
        else:
            normalized[k] = v

    # 入栈版本（仅记录变更字段）
    push_version(node_id, normalized, change_source="user_edit")

    # 解析 @节点 引用
    description = normalized.get("description") or node.get("description")
    if description:
        try:
            from app.services.project.node_ref import sync_node_references
            sync_node_references(user_id, project_id, node_id, description)
        except Exception as exc:  # noqa: BLE001
            logger.warning("sync_node_references 失败: %s", exc)

    return get_node(user_id, project_id, node_id)


def delete_node(user_id: str, project_id: str, node_id: str) -> bool:
    ensure_tables()
    db = get_db()
    # 标记被引用关系为 broken
    try:
        from app.services.project.node_ref import mark_broken_references
        mark_broken_references(node_id, "target_node_deleted")
    except Exception:
        pass
    db.execute(
        "DELETE FROM project_nodes WHERE id = %s AND project_id = %s AND user_id = %s",
        (node_id, project_id, user_id),
    )
    db.execute(
        "UPDATE projects SET node_count = GREATEST(node_count - 1, 0), updated_at = NOW() "
        "WHERE id = %s",
        (project_id,),
    )
    return True


def archive_node(user_id: str, project_id: str, node_id: str, archived: bool = True) -> dict | None:
    db = get_db()
    db.execute(
        "UPDATE project_nodes SET is_archived = %s, updated_at = NOW() "
        "WHERE id = %s AND project_id = %s AND user_id = %s",
        (archived, node_id, project_id, user_id),
    )
    return get_node(user_id, project_id, node_id)


def complete_node(user_id: str, project_id: str, node_id: str, completed: bool = True) -> dict | None:
    db = get_db()
    db.execute(
        "UPDATE project_nodes SET completed_at = %s, updated_at = NOW() "
        "WHERE id = %s AND project_id = %s AND user_id = %s",
        (datetime.utcnow() if completed else None, node_id, project_id, user_id),
    )
    if completed:
        db.execute(
            "UPDATE projects SET completed_node_count = completed_node_count + 1, updated_at = NOW() "
            "WHERE id = %s",
            (project_id,),
        )
    return get_node(user_id, project_id, node_id)


# Task #89: 节点 status 字段（看板列）
NODE_STATUS_VALUES: tuple[str, ...] = ("pending", "active", "completed", "archived")


def update_node_status(
    user_id: str,
    project_id: str,
    node_id: str,
    status: str,
) -> dict | None:
    """更新节点 status 字段（看板拖拽用）。

    status 是非版本化字段，直接 UPDATE project_nodes。
    与 completed_at 保持一致：status='completed' 时若 completed_at 为空则自动补上。
    """
    if status not in NODE_STATUS_VALUES:
        raise ValueError(f"status 必须是 {NODE_STATUS_VALUES} 之一, 当前: {status}")
    ensure_tables()
    db = get_db()
    # 同步 completed_at：进 completed 时打时间戳
    if status == "completed":
        db.execute(
            "UPDATE project_nodes SET status = %s, completed_at = COALESCE(completed_at, NOW()), updated_at = NOW() "
            "WHERE id = %s AND project_id = %s AND user_id = %s",
            (status, node_id, project_id, user_id),
        )
    else:
        db.execute(
            "UPDATE project_nodes SET status = %s, updated_at = NOW() "
            "WHERE id = %s AND project_id = %s AND user_id = %s",
            (status, node_id, project_id, user_id),
        )
    # 维护 projects.completed_node_count
    if status == "completed":
        db.execute(
            "UPDATE projects SET completed_node_count = "
            "(SELECT COUNT(*) FROM project_nodes "
            " WHERE project_id = %s AND user_id = %s AND status = 'completed'), "
            "updated_at = NOW() "
            "WHERE id = %s",
            (project_id, user_id, project_id),
        )
    return get_node(user_id, project_id, node_id)


# Task #89: 节点 reorder（拖拽重排用）
def reorder_nodes(
    user_id: str,
    project_id: str,
    node_ids_in_order: list[str],
) -> bool:
    """按给定顺序重排同父级的节点（更新 order_in_parent）。"""
    ensure_tables()
    db = get_db()
    for idx, nid in enumerate(node_ids_in_order):
        db.execute(
            "UPDATE project_nodes SET order_in_parent = %s, updated_at = NOW() "
            "WHERE id = %s AND project_id = %s AND user_id = %s",
            (idx, nid, project_id, user_id),
        )
    return True


# ────────────────────────────────────────────────────────────────
# 里程碑
# ────────────────────────────────────────────────────────────────


def create_milestone(
    user_id: str,
    project_id: str,
    milestone_name: str,
    snapshot_data: dict | None = None,
    is_user_marked: bool = True,
) -> dict:
    ensure_tables()
    db = get_db()
    milestone_id = _new_uuid()
    if snapshot_data is None:
        snapshot_data = _compute_project_snapshot(db, project_id)
    db.execute(
        """
        INSERT INTO project_milestones (id, project_id, milestone_name,
                                        snapshot_data, is_user_marked, marked_at)
        VALUES (%s, %s, %s, %s::jsonb, %s, NOW())
        """,
        (
            milestone_id, project_id, milestone_name,
            _json_dumps(snapshot_data), is_user_marked,
        ),
    )
    row = db.fetchone("SELECT * FROM project_milestones WHERE id = %s", (milestone_id,))
    return {
        "id": row["id"],
        "project_id": row["project_id"],
        "milestone_name": row["milestone_name"],
        "snapshot_data": _json_loads(row["snapshot_data"], {}),
        "is_user_marked": row["is_user_marked"],
        "marked_at": row["marked_at"].isoformat(),
    }


def list_milestones(user_id: str, project_id: str) -> list[dict]:
    ensure_tables()
    db = get_db()
    rows = db.fetchall(
        "SELECT * FROM project_milestones WHERE project_id = %s ORDER BY marked_at DESC",
        (project_id,),
    )
    return [
        {
            "id": r["id"],
            "project_id": r["project_id"],
            "milestone_name": r["milestone_name"],
            "snapshot_data": _json_loads(r["snapshot_data"], {}),
            "is_user_marked": r["is_user_marked"],
            "marked_at": r["marked_at"].isoformat(),
        }
        for r in rows
    ]


def get_milestone(user_id: str, project_id: str, milestone_id: str) -> dict | None:
    """按 ID 查询单个里程碑，并校验它属于该项目 + 当前用户。"""
    ensure_tables()
    db = get_db()
    row = db.fetchone(
        """
        SELECT m.* FROM project_milestones m
         JOIN projects p ON p.id = m.project_id
         WHERE m.id = %s AND m.project_id = %s AND p.user_id = %s
        """,
        (milestone_id, project_id, user_id),
    )
    if not row:
        return None
    return {
        "id": row["id"],
        "project_id": row["project_id"],
        "milestone_name": row["milestone_name"],
        "snapshot_data": _json_loads(row["snapshot_data"], {}),
        "is_user_marked": row["is_user_marked"],
        "marked_at": row["marked_at"].isoformat(),
    }


def update_milestone(
    user_id: str,
    project_id: str,
    milestone_id: str,
    milestone_name: str | None = None,
    snapshot_data: dict | None = None,
    is_user_marked: bool | None = None,
    regenerate_snapshot: bool = False,
) -> dict | None:
    """更新里程碑。

    所有字段可选；仅更新传入的字段。
    snapshot_data 行为:
      - 显式传入 dict → 覆盖为该 dict
      - 显式传 None + regenerate_snapshot=True → 重新计算项目快照
      - 不传（None）→ 保持原值
    """
    db = get_db()
    # 先校验归属（不存则返回 None）
    existing = get_milestone(user_id, project_id, milestone_id)
    if not existing:
        return None

    sets: list[str] = []
    params: list[Any] = []
    if milestone_name is not None:
        sets.append("milestone_name = %s")
        params.append(milestone_name)
    if is_user_marked is not None:
        sets.append("is_user_marked = %s")
        params.append(is_user_marked)
    # snapshot_data 单独处理：
    #   - snapshot_data is not None → 用传入的 dict 覆盖
    #   - snapshot_data is None + regenerate_snapshot=True → 重新计算
    #   - 两者皆否 → 不修改（保持原值）
    if snapshot_data is not None or regenerate_snapshot:
        payload_snapshot = (
            _compute_project_snapshot(db, project_id)
            if regenerate_snapshot
            else snapshot_data
        )
        sets.append("snapshot_data = %s::jsonb")
        params.append(_json_dumps(payload_snapshot))

    if not sets:
        return existing
    params.extend([milestone_id, project_id])
    db.execute(
        f"UPDATE project_milestones SET {', '.join(sets)} "
        "WHERE id = %s AND project_id = %s",
        tuple(params),
    )
    return get_milestone(user_id, project_id, milestone_id)


def delete_milestone(user_id: str, project_id: str, milestone_id: str) -> bool:
    """删除里程碑；先校验归属，无归属则返回 False。"""
    db = get_db()
    existing = get_milestone(user_id, project_id, milestone_id)
    if not existing:
        return False
    db.execute(
        "DELETE FROM project_milestones WHERE id = %s AND project_id = %s",
        (milestone_id, project_id),
    )
    return True


def _compute_project_snapshot(db, project_id: str) -> dict:
    """项目级整体快照（节点数/关联数/完成率）。"""
    node_stats = db.fetchone(
        """
        SELECT COUNT(*) AS total,
               COUNT(completed_at) AS completed
          FROM project_nodes
         WHERE project_id = %s
        """,
        (project_id,),
    )
    link_stats = db.fetchone(
        """
        SELECT COUNT(*) AS total_links FROM node_links nl
          JOIN project_nodes pn ON nl.source_node_id = pn.id
         WHERE pn.project_id = %s
        """,
        (project_id,),
    )
    total = node_stats["total"] or 0
    completed = node_stats["completed"] or 0
    return {
        "node_count": int(total),
        "completed_count": int(completed),
        "link_count": int(link_stats["total_links"] or 0),
        "completion_rate": (completed / total) if total else 0.0,
    }


# ────────────────────────────────────────────────────────────────
# 模板
# ────────────────────────────────────────────────────────────────


def list_templates(category: str | None = None, include_user: bool = True) -> list[dict]:
    ensure_tables()
    db = get_db()
    if category:
        rows = db.fetchall(
            "SELECT * FROM project_templates WHERE category = %s ORDER BY is_system DESC, name ASC",
            (category,),
        )
    else:
        rows = db.fetchall("SELECT * FROM project_templates ORDER BY is_system DESC, name ASC")
    return [t for t in (_row_to_template(r) for r in rows) if t]


def get_template(template_id: str) -> dict | None:
    ensure_tables()
    db = get_db()
    row = db.fetchone("SELECT * FROM project_templates WHERE id = %s", (template_id,))
    return _row_to_template(row)


def _row_to_template(row: dict | None) -> dict | None:
    if not row:
        return None
    return {
        "id": row["id"],
        "name": row["name"],
        "description": row.get("description"),
        "category": row.get("category"),
        "structure": _json_loads(row.get("structure"), {}),
        "placeholder_schema": _json_loads(row.get("placeholder_schema"), {}),
        "is_system": row.get("is_system") or False,
        "created_by_user_id": row.get("created_by_user_id"),
        "version": row.get("version") or 1,
        "parent_template_id": row.get("parent_template_id"),
        "created_at": row["created_at"].isoformat() if row.get("created_at") else None,
        "updated_at": row["updated_at"].isoformat() if row.get("updated_at") else None,
    }


def create_template(
    user_id: str | None,
    name: str,
    structure: dict,
    description: str | None = None,
    category: str | None = None,
    placeholder_schema: dict | None = None,
    is_system: bool = False,
) -> dict:
    ensure_tables()
    db = get_db()
    template_id = _new_uuid()
    db.execute(
        """
        INSERT INTO project_templates (
            id, name, description, category, structure, placeholder_schema,
            is_system, created_by_user_id, version, created_at, updated_at
        ) VALUES (%s, %s, %s, %s, %s::jsonb, %s::jsonb, %s, %s, 1, NOW(), NOW())
        """,
        (
            template_id, name, description, category,
            _json_dumps(structure), _json_dumps(placeholder_schema or {}),
            is_system, user_id,
        ),
    )
    return get_template(template_id)  # type: ignore[return-value]


def instantiate_from_template(
    user_id: str,
    template_id: str,
    name: str,
    placeholder_values: dict | None = None,
) -> dict:
    """从模板创建项目 + 节点树。"""
    ensure_tables()
    template = get_template(template_id)
    if not template:
        raise ValueError("模板不存在")

    project = create_project(
        user_id=user_id,
        name=name,
        description=template.get("description"),
        template_id=template_id,
        template_version=template.get("version"),
    )
    project_id = project["id"]  # type: ignore[index]

    # 渲染结构（支持占位符替换）
    rendered = _render_template_structure(
        template.get("structure", {}),
        placeholder_values or {},
    )
    _create_nodes_from_structure(user_id, project_id, rendered, parent_id=None)
    return get_project(user_id, project_id)  # type: ignore[return-value]


def _render_template_structure(structure: dict, values: dict) -> dict:
    """递归替换结构中的 {{placeholder}} 占位符。"""
    if isinstance(structure, dict):
        return {k: _render_template_structure(v, values) for k, v in structure.items()}
    if isinstance(structure, list):
        return [_render_template_structure(v, values) for v in structure]
    if isinstance(structure, str) and structure.startswith("{{") and structure.endswith("}}"):
        key = structure[2:-2].strip()
        return values.get(key, structure)
    return structure


def _create_nodes_from_structure(
    user_id: str,
    project_id: str,
    structure: dict,
    parent_id: str | None,
) -> None:
    """根据模板结构递归创建节点。"""
    nodes = structure.get("nodes", [])
    for idx, n in enumerate(nodes):
        node = create_node(
            user_id=user_id,
            project_id=project_id,
            type=int(n.get("type", 1)),
            title=n.get("title", "未命名节点"),
            parent_id=parent_id,
            description=n.get("description"),
            tags=n.get("tags"),
            content=n.get("content"),
            rows=n.get("rows"),
            columns=n.get("columns"),
            language=n.get("language"),
            code=n.get("code"),
            explanation=n.get("explanation"),
            material_id=n.get("material_id"),
            chunk_id_range=n.get("chunk_id_range"),
            fragments=n.get("fragments"),
        )
        if node and n.get("nodes"):
            _create_nodes_from_structure(user_id, project_id, n, parent_id=node["id"])  # type: ignore[arg-type]


def seed_default_templates() -> int:
    """插入系统预置模板（幂等）。"""
    ensure_tables()
    db = get_db()
    existing = db.fetchone("SELECT COUNT(*) AS c FROM project_templates WHERE is_system = TRUE")
    if existing and existing["c"] > 0:
        return 0

    defaults = [
        {
            "name": "主题研究模板",
            "description": "适合人物/历史/专题的深度研究（大纲+文本+对比+附件）",
            "category": "research",
            "structure": {
                "nodes": [
                    {"type": 1, "title": "背景", "nodes": [
                        {"type": 2, "title": "核心概念"},
                    ]},
                    {"type": 1, "title": "多视角分析", "nodes": [
                        {"type": 4, "title": "观点对比"},
                    ]},
                    {"type": 1, "title": "参考资料", "nodes": [
                        {"type": 6, "title": "附件"},
                    ]},
                ]
            },
        },
        {
            "name": "解题分析模板",
            "description": "适合一题多解/题型归纳（大纲+对比+文本+数据表）",
            "category": "math",
            "structure": {
                "nodes": [
                    {"type": 1, "title": "原题", "nodes": [
                        {"type": 2, "title": "题目描述"},
                    ]},
                    {"type": 1, "title": "解法", "nodes": [
                        {"type": 4, "title": "解法对比"},
                        {"type": 3, "title": "效率对比表"},
                    ]},
                    {"type": 1, "title": "心得", "nodes": [
                        {"type": 2, "title": "个人总结"},
                    ]},
                ]
            },
        },
        {
            "name": "项目实践模板",
            "description": "适合技术搭建/手工项目（大纲+文本+代码+附件）",
            "category": "engineering",
            "structure": {
                "nodes": [
                    {"type": 1, "title": "目标"},
                    {"type": 1, "title": "实现", "nodes": [
                        {"type": 5, "title": "关键代码段", "language": "python"},
                        {"type": 2, "title": "踩坑日志"},
                    ]},
                    {"type": 1, "title": "成果", "nodes": [
                        {"type": 6, "title": "截图"},
                        {"type": 7, "title": "成果板"},
                    ]},
                ]
            },
        },
        {
            "name": "长篇阅读模板",
            "description": "适合书籍精读（大纲+文本+对比+聚合）",
            "category": "reading",
            "structure": {
                "nodes": [
                    {"type": 1, "title": "章节笔记", "nodes": [
                        {"type": 2, "title": "要点摘录"},
                    ]},
                    {"type": 1, "title": "横向对比", "nodes": [
                        {"type": 4, "title": "作者视角对比"},
                    ]},
                    {"type": 1, "title": "汇总", "nodes": [
                        {"type": 7, "title": "我的解读"},
                    ]},
                ]
            },
        },
    ]
    for tpl in defaults:
        create_template(
            user_id=None,
            name=tpl["name"],
            description=tpl.get("description"),
            category=tpl.get("category"),
            structure=tpl["structure"],
            is_system=True,
        )
    return len(defaults)
