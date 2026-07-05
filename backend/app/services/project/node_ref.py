"""
Project 服务层 — @节点 引用解析与跨项目节点复制

实现要点 (overview.md §5, ADR 0001 §2.2-2.3):
  - 解析节点内容中 `@节点名` 语法，绑定到实际 project_node_id
  - 跨项目引用:
      * link_copy: 源节点更新同步 (默认)
      * deep_copy: 完全独立
  - 循环检测: A→B→A 时标记 creates_cycle=True 并警告
  - 被引用节点删除/移动时: 设置 is_broken=True + 记录 broken_reason
  - 通过 CognitiveNodeLinked 事件通知知识图谱
"""
from __future__ import annotations

import json
import logging
import re
from typing import Any
from uuid import uuid4

from app.infrastructure.db.database import get_db
from app.infrastructure.event_bus_utils import publish_event_safe
from shared.events import CognitiveNodeLinked, CrossModuleTarget

logger = logging.getLogger(__name__)


# 引用语法：
#   @@node:<uuid>        (直接通过 ID 引用, 优先匹配)
#   @项目A/第一章/1.2    (跨项目路径式引用，title path)
#   @节点名              (同项目标题匹配)
# 实际场景里，多数实现是从富文本/描述的字符串中扫描。
# 这里提供一个简化的标题/路径解析器，存的是 target_node_id + target_project_id。
# 优先匹配 @@node: 前缀；其余以 @ 开头的 token 视为标题/路径引用。
_REF_NODE_ID = re.compile(r"@@node:(?P<node_id>[0-9a-fA-F-]{8,})")
_REF_TITLE = re.compile(r"@(?P<path>(?:[^\s@,;，；]+))")


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


def _publish_cognitive_link(
    user_id: str,
    project_node_id: str,
    target_ref_id: str,
    target_ref_type: str,
    action: str,
    link_type: str = "project_node_ref",
) -> None:
    """发布 CognitiveNodeLinked 事件，让知识图谱侧感知 project_node 链接变化。

    委托给 publish_event_safe — 自动适配 sync/async 上下文，不再使用
    deprecated 的 `asyncio.get_event_loop()`。
    """
    event = CognitiveNodeLinked(
        user_id=user_id,
        node_id=project_node_id,
        link_type=link_type,
        target_ref_type=target_ref_type,
        target_ref_id=target_ref_id,
        action=action,  # type: ignore[arg-type]
    )
    publish_event_safe(event)


# ────────────────────────────────────────────────────────────────
# 引用解析
# ────────────────────────────────────────────────────────────────


def parse_references(text: str) -> list[str]:
    """从文本中提取所有 @引用 token 列表。

    优先匹配 @@node:<uuid> 显式 ID 引用；其余以 @ 开头的 token 视为标题/路径。
    """
    if not text:
        return []
    tokens: list[str] = []
    seen: set[str] = set()

    # 1) 显式 ID 引用 (完整 token，含 @@node: 前缀)
    for m in _REF_NODE_ID.finditer(text):
        tok = f"@@node:{m.group('node_id')}"
        if tok not in seen:
            seen.add(tok)
            tokens.append(tok)

    # 2) 标题 / 路径引用 (去掉 @@node: 已覆盖的位置)
    consumed_spans: list[tuple[int, int]] = [
        (m.start(), m.end()) for m in _REF_NODE_ID.finditer(text)
    ]

    def _in_consumed(pos: int) -> bool:
        for s, e in consumed_spans:
            if s <= pos < e:
                return True
        return False

    for m in _REF_TITLE.finditer(text):
        if _in_consumed(m.start()):
            continue
        tok = m.group("path")
        if tok not in seen:
            seen.add(tok)
            tokens.append(tok)

    return tokens


def resolve_reference(
    user_id: str,
    ref_token: str,
    project_id: str,
    source_node_id: str | None = None,
) -> dict | None:
    """将 @引用 token 解析为节点记录。

    解析规则（按优先级）:
      1. @@node:<uuid> → 直接通过 ID 查询
      2. @项目名/章节路径 → 跨项目精确路径
      3. @节点名 → 同项目内 title 匹配（首个, 跳过自身）
      4. @节点名 → 跨项目 title 匹配（兜底）

    返回 {node_id, project_id, title} 或 None
    """
    db = get_db()

    # 1. 直接通过 ID
    if ref_token.startswith("@@node:"):
        node_id = ref_token[len("@@node:"):]
        row = db.fetchone(
            "SELECT id, project_id, title FROM project_nodes WHERE id = %s AND user_id = %s",
            (node_id, user_id),
        )
        if row and (source_node_id is None or row["id"] != source_node_id):
            return {"node_id": row["id"], "project_id": row["project_id"], "title": row["title"]}

    # 2. 跨项目路径
    if "/" in ref_token:
        parts = [p.strip() for p in ref_token.split("/") if p.strip()]
        if parts:
            project_name = parts[0]
            proj = db.fetchone(
                "SELECT id FROM projects WHERE user_id = %s AND name = %s LIMIT 1",
                (user_id, project_name),
            )
            if proj:
                rest_path = " / ".join(parts[1:]) if len(parts) > 1 else ""
                node = db.fetchone(
                    """
                    SELECT id, project_id, title FROM project_nodes
                     WHERE project_id = %s AND user_id = %s
                       AND title = %s
                     LIMIT 1
                    """,
                    (proj["id"], user_id, rest_path or parts[0]),
                )
                if node and (source_node_id is None or node["id"] != source_node_id):
                    return {"node_id": node["id"], "project_id": node["project_id"], "title": node["title"]}

    # 3. 同项目内 title 匹配（跳过自身）
    row = db.fetchone(
        """
        SELECT id, project_id, title FROM project_nodes
         WHERE project_id = %s AND user_id = %s
           AND title = %s
         LIMIT 1
        """,
        (project_id, user_id, ref_token),
    )
    if row and (source_node_id is None or row["id"] != source_node_id):
        return {"node_id": row["id"], "project_id": row["project_id"], "title": row["title"]}

    # 4. 跨项目 title 匹配（兜底）
    row = db.fetchone(
        """
        SELECT id, project_id, title FROM project_nodes
         WHERE user_id = %s
           AND project_id != %s
           AND title = %s
         LIMIT 1
        """,
        (user_id, project_id, ref_token),
    )
    if row and (source_node_id is None or row["id"] != source_node_id):
        return {"node_id": row["id"], "project_id": row["project_id"], "title": row["title"]}

    return None


# ────────────────────────────────────────────────────────────────
# 引用管理
# ────────────────────────────────────────────────────────────────


def sync_node_references(
    user_id: str,
    project_id: str,
    source_node_id: str,
    text: str,
) -> int:
    """根据节点内容中的 @引用 同步 node_references 表。

    - 删除 source 已不存在的旧引用
    - 新增新引用
    - 检测循环引用（A→B→A）
    - 同步发布 CognitiveNodeLinked 事件
    """
    db = get_db()
    tokens = parse_references(text)
    resolved: list[dict] = []
    for tok in tokens:
        target = resolve_reference(user_id, tok, project_id, source_node_id=source_node_id)
        if target and target["node_id"] != source_node_id:
            resolved.append(target)

    # 删除已不存在的引用
    db.execute("DELETE FROM node_references WHERE source_node_id = %s", (source_node_id,))

    created = 0
    for ref in resolved:
        target_node_id = ref["node_id"]
        target_project_id = ref["project_id"]
        cross_project = target_project_id != project_id

        # 循环检测：A→B→A
        creates_cycle = _detect_cycle(db, source_node_id, target_node_id)

        db.execute(
            """
            INSERT INTO node_references (
                id, source_node_id, target_node_id, target_project_id,
                reference_type, is_broken, creates_cycle
            ) VALUES (%s, %s, %s, %s, %s, FALSE, %s)
            """,
            (
                _new_uuid(),
                source_node_id,
                target_node_id,
                target_project_id,
                "embed" if cross_project else "inline",
                creates_cycle,
            ),
        )
        created += 1

        if creates_cycle:
            logger.warning(
                "跨项目引用形成循环: %s -> %s", source_node_id, target_node_id,
            )

        # 同步发布知识图谱侧事件（仅同项目类型；跨项目使用专用 ref_type）
        _publish_cognitive_link(
            user_id=user_id,
            project_node_id=source_node_id,
            target_ref_id=target_node_id,
            target_ref_type="project_node" if cross_project else "project_node_inline",
            action="created",
            link_type="cross_project_ref" if cross_project else "inline_ref",
        )

    return created


def _detect_cycle(db, source_node_id: str, target_node_id: str) -> bool:
    """检测 source→target 是否会形成循环（target 反向已引用 source）。

    采用 BFS：自 target 起查找其所有引用，若能追溯到 source_node_id 则成环。
    """
    if source_node_id == target_node_id:
        return True

    visited: set[str] = set()
    stack = [target_node_id]
    while stack:
        cur = stack.pop()
        if cur in visited:
            continue
        visited.add(cur)
        if cur == source_node_id:
            return True
        # 取出 cur 的所有 target
        rows = db.fetchall(
            "SELECT target_node_id FROM node_references WHERE source_node_id = %s",
            (cur,),
        )
        for r in rows:
            if r["target_node_id"] not in visited:
                stack.append(r["target_node_id"])
    return False


def mark_broken_references(node_id: str, reason: str) -> int:
    """当目标节点被删除/归档/移动时，把所有指向它的引用标记为 broken。"""
    db = get_db()
    rows = db.fetchall(
        "SELECT id FROM node_references WHERE target_node_id = %s",
        (node_id,),
    )
    if not rows:
        return 0
    ids = [r["id"] for r in rows]
    # 使用 IN 列表（占位符动态展开）保证跨 psycopg2 兼容
    placeholders = ",".join(["%s"] * len(ids))
    db.execute(
        f"UPDATE node_references SET is_broken = TRUE, broken_reason = %s WHERE id IN ({placeholders})",
        tuple([reason] + ids),
    )
    return len(ids)


# ────────────────────────────────────────────────────────────────
# 跨项目节点复制
# ────────────────────────────────────────────────────────────────


def copy_nodes_across_projects(
    user_id: str,
    source_project_id: str,
    target_project_id: str,
    node_ids: list[str],
    mode: str = "link_copy",  # "link_copy" | "deep_copy"
) -> list[dict]:
    """跨项目节点复制。

    - link_copy:  在目标项目插入新节点，title 相同，关联通过 ref 维持
                  source → target 的 link 关系，不复制版本历史
    - deep_copy:  完全独立复制（content/rows/columns/code 等全部复制）
                  仍然保留指向 source 的 ref（reference_type='link'）

    返回创建的 target 节点列表（含 source_node_id）。

    实现要点：节点创建走 :func:`app.services.project.create_node_batch`
    公共方法（避免直写 `INSERT INTO project_nodes` 造成字段漂移）。
    """
    if mode not in ("link_copy", "deep_copy"):
        raise ValueError(f"unknown copy mode: {mode}")

    db = get_db()
    target_proj = db.fetchone(
        "SELECT id FROM projects WHERE id = %s AND user_id = %s",
        (target_project_id, user_id),
    )
    if not target_proj:
        raise ValueError("目标项目不存在或无权限")

    # 1) 收集源节点（保持输入顺序）
    sources: list[dict] = []
    for sid in node_ids:
        src = db.fetchone(
            "SELECT * FROM project_nodes WHERE id = %s AND project_id = %s AND user_id = %s",
            (sid, source_project_id, user_id),
        )
        if src:
            sources.append(src)

    if not sources:
        return []

    # 2) 构造 batch payload（link_copy 跳过内容字段；deep_copy 全量复制）
    new_ids: list[str] = [_new_uuid() for _ in sources]
    payloads: list[dict] = []
    for src, new_id in zip(sources, new_ids):
        payload: dict = {
            "node_id": new_id,
            "type": int(src.get("type") or 1),
            "title": src.get("title"),
            "parent_id": src.get("parent_id"),
            "description": src.get("description"),
            "tags": src.get("tags") or [],
            "order_in_parent": src.get("order_in_parent") or 0,
        }
        if mode == "deep_copy":
            payload.update({
                "content": src.get("content"),
                "rows": src.get("rows"),
                "columns": src.get("columns"),
                "code": src.get("code"),
                "explanation": src.get("explanation"),
                "language": src.get("language"),
                "material_id": src.get("material_id"),
                "chunk_id_range": src.get("chunk_id_range"),
                "fragments": src.get("fragments"),
                "linked_node_ids": src.get("linked_node_ids") or [],
                "linked_material_ids": src.get("linked_material_ids") or [],
                "linked_card_ids": src.get("linked_card_ids") or [],
                "cross_project_refs": src.get("cross_project_refs") or [],
            })
        payloads.append(payload)

    # 3) 走 service 公共方法批量创建（自动累加 node_count + 维护 version/timestamps）
    from app.services.project import create_node_batch
    created_nodes = create_node_batch(
        user_id=user_id,
        project_id=target_project_id,
        nodes=payloads,
    )

    # 4) 写 ref + 发布认知事件（按成功创建顺序）
    ref_type = "link" if mode == "link_copy" else "embed"
    created: list[dict] = []
    for src, new_node in zip(sources, created_nodes):
        if not new_node:
            continue
        new_id = new_node["id"]
        # ref：source → new_id
        db.execute(
            """
            INSERT INTO node_references (
                id, source_node_id, target_node_id, target_project_id,
                reference_type
            ) VALUES (%s, %s, %s, %s, %s)
            """,
            (
                _new_uuid(),
                src["id"],
                new_id,
                target_project_id,
                ref_type,
            ),
        )

        # 发布认知事件
        _publish_cognitive_link(
            user_id=user_id,
            project_node_id=new_id,
            target_ref_id=src["id"],
            target_ref_type="project_node",
            action="created",
            link_type="cross_project_copy",
        )

        created.append({
            "source_node_id": src["id"],
            "new_node_id": new_id,
            "mode": mode,
        })
    return created
