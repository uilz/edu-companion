"""CognitiveNode 存储层 — PostgreSQL 读写

提供 CognitiveNode + CognitiveEvent 的完整 CRUD。
同步实现，复用现有 psycopg2 连接池。
"""

from __future__ import annotations

import json
import logging
import time
from typing import Optional

from app.shared.constants import DEFAULT_USER_ID
from app.cognitive.models import (
    Activation, Belief, CognitiveEvent, CognitiveLoad, CognitiveNode,
    Composition, DeepLink, DeepProcessing, Diagnostic, DialogueContext,
    Engagement, ErrorCluster, GoalAlignment, Metacognition, PracticeEvent,
    PracticeSummary, Prediction, Prerequisite, Scheduling, Trend,
    Unlock, Associate, UserCognitiveState,
)
from app.db.database import Database, get_db

logger = logging.getLogger(__name__)

# ── JSON 序列化 ──


def _to_json(obj) -> str:
    """Pydantic → JSON 字符串，支持嵌套 Pydantic list"""
    if obj is None:
        return json.dumps(None)
    if isinstance(obj, list):
        return "[" + ",".join(
            _to_json(item).strip() for item in obj
        ) + "]"
    if hasattr(obj, "model_dump_json"):
        return obj.model_dump_json()
    return json.dumps(obj, ensure_ascii=False, default=str)


def _from_json(cls, raw: str | dict | None):
    """JSON → Pydantic，接受字符串或已解析的 dict"""
    if raw is None:
        return None
    if isinstance(raw, str):
        if not raw or raw == "{}" or raw == "[]":
            return cls()
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            return cls()
    else:
        parsed = raw
    try:
        return cls.model_validate(parsed)
    except Exception as e:
        logger.warning(f"_from_json({cls.__name__}) failed: {e}, raw={str(raw)[:100]}")
        return cls()


# ── CognitiveNode CRUD ──


def upsert_node(node: CognitiveNode, user_id: str = DEFAULT_USER_ID) -> None:
    """插入或更新一个 CognitiveNode（完整覆盖）"""
    db = get_db()
    from datetime import datetime, timezone
    now_iso = datetime.now(timezone.utc).isoformat()

    # 手动构建 SQL 和参数——确保 JSONB 值作为合法 JSON 字符串传递
    columns = [
        "id", "user_id", "label", "level", "parent", "children", "is_core",
        "activation", "belief", "prediction", "cognitive_load", "trend", "scheduling",
        "dialogue_contexts", "practice_events", "practice_summary", "error_clusters",
        "metacognition", "engagement", "composition", "deep_links", "deep_processing",
        "goal_alignment", "diagnostic", "prerequisites", "unlocks", "associates",
        "param_refs", "meta", "updated_at",
        # Phase 8
        "path_id", "node_type", "is_visible", "subsystems", "embedding", "is_active",
    ]
    # 确保所有 JSONB 值为合法 JSON 字符串
    vals = {c: _to_json(getattr(node, c, None)) for c in columns}
    vals.update({
        "id": node.id,
        "user_id": user_id,
        "label": node.label,
        "level": node.level,
        "parent": node.parent,
        "is_core": node.is_core,
        "children": _to_json(node.children),
        "updated_at": now_iso,
        # Phase 8 — 明文存储，不 JSON 双序列化
        "path_id": node.path_id or "",
        "node_type": node.node_type or "explicit",
        "is_visible": node.is_visible,
        "is_active": node.is_active,
    })

    placeholders = ", ".join(f"%({k})s" for k in vals)
    update_cols = [k for k in vals if k != "id"]
    update_clause = ", ".join(f"{k} = %({k})s" for k in update_cols)
    sql = (
        f"INSERT INTO cognitive_nodes ({', '.join(vals.keys())}) "
        f"VALUES ({placeholders}) "
        f"ON CONFLICT (id) DO UPDATE SET {update_clause}"
    )

    conn = db.get_conn()
    try:
        cur = conn.cursor()
        cur.execute(sql, vals)
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        cur.close()
        db.put_conn(conn)


def get_node(node_id: str, user_id: str = DEFAULT_USER_ID) -> Optional[CognitiveNode]:
    """通过 ID 获取 CognitiveNode"""
    db = get_db()
    row = db.fetchone(
        "SELECT * FROM cognitive_nodes WHERE id = %s AND user_id = %s",
        (node_id, user_id),
    )
    if not row:
        return None
    return _row_to_node(row)


def get_nodes_by_level(
    level: str, user_id: str = DEFAULT_USER_ID,
) -> list[CognitiveNode]:
    """获取某一层级的所有节点"""
    db = get_db()
    rows = db.fetchall(
        "SELECT * FROM cognitive_nodes WHERE level = %s AND user_id = %s ORDER BY id",
        (level, user_id),
    )
    return [_row_to_node(r) for r in rows]


def get_children(parent_id: str, user_id: str = DEFAULT_USER_ID) -> list[CognitiveNode]:
    """获取某节点的直接子节点"""
    db = get_db()
    rows = db.fetchall(
        "SELECT * FROM cognitive_nodes WHERE parent = %s AND user_id = %s ORDER BY id",
        (parent_id, user_id),
    )
    return [_row_to_node(r) for r in rows]


def get_subtree(root_id: str, user_id: str = DEFAULT_USER_ID) -> dict[str, CognitiveNode]:
    """获取以 root_id 为根的整个子树（广度优先）"""
    db = get_db()
    # 用递归 CTE 或简单的一层一层查
    rows = db.fetchall(
        """
        WITH RECURSIVE subtree AS (
            SELECT * FROM cognitive_nodes
            WHERE id = %s AND user_id = %s
            UNION ALL
            SELECT cn.* FROM cognitive_nodes cn
            JOIN subtree ON cn.parent = subtree.id
            WHERE cn.user_id = %s
        )
        SELECT * FROM subtree
        """,
        (root_id, user_id, user_id),
    )
    return {r["id"]: _row_to_node(r) for r in rows}


def delete_node(node_id: str, user_id: str = DEFAULT_USER_ID) -> None:
    """删除节点（含子节点级联）"""
    db = get_db()
    db.execute(
        "DELETE FROM cognitive_nodes WHERE id = %s AND user_id = %s",
        (node_id, user_id),
    )
    # 清理子节点的 parent 引用和父节点的 children 引用
    db.execute(
        "UPDATE cognitive_nodes SET parent = NULL, "
        "children = (children::jsonb - %s)::jsonb "
        "WHERE children::jsonb ? %s AND user_id = %s",
        (node_id, node_id, user_id),
    )


def search_nodes(
    query: str, user_id: str = DEFAULT_USER_ID, limit: int = 20,
) -> list[CognitiveNode]:
    """按 label 或 id 搜索节点"""
    db = get_db()
    pattern = f"%{query}%"
    rows = db.fetchall(
        "SELECT * FROM cognitive_nodes WHERE user_id = %s "
        "AND (label ILIKE %s OR id ILIKE %s) "
        "ORDER BY length(id) LIMIT %s",
        (user_id, pattern, pattern, limit),
    )
    return [_row_to_node(r) for r in rows]


def list_all_nodes(user_id: str = DEFAULT_USER_ID) -> list[CognitiveNode]:
    """获取用户所有节点"""
    db = get_db()
    rows = db.fetchall(
        "SELECT * FROM cognitive_nodes WHERE user_id = %s ORDER BY id",
        (user_id,),
    )
    return [_row_to_node(r) for r in rows]


def get_urgent_nodes(
    limit: int = 10, user_id: str = DEFAULT_USER_ID,
) -> list[CognitiveNode]:
    """获取紧迫度最高的节点（用于调度）"""
    db = get_db()
    rows = db.fetchall(
        "SELECT * FROM cognitive_nodes WHERE user_id = %s "
        "AND scheduling->>'urgency' IS NOT NULL "
        "ORDER BY (scheduling->>'urgency')::float DESC LIMIT %s",
        (user_id, limit),
    )
    return [_row_to_node(r) for r in rows]


# ── 事件读写 ──


def append_event(event: CognitiveEvent) -> None:
    """追加一条认知事件"""
    db = get_db()
    data = {
        "event_id": event.event_id,
        "event_type": event.event_type,
        "user_id": event.user_id,
        "node_id": event.node_id,
        "timestamp": _ts_to_pg(event.timestamp),
        "payload": _to_json(event.payload),
    }
    db.execute(
        "INSERT INTO cognitive_events (event_id, event_type, user_id, node_id, timestamp, payload) "
        "VALUES (%(event_id)s, %(event_type)s, %(user_id)s, %(node_id)s, %(timestamp)s, %(payload)s) "
        "ON CONFLICT (event_id) DO NOTHING",
        data,
    )


def get_unprocessed_events(
    user_id: str = DEFAULT_USER_ID,
    limit: int = 50,
) -> list[CognitiveEvent]:
    """获取未处理事件"""
    db = get_db()
    rows = db.fetchall(
        "SELECT * FROM cognitive_events WHERE user_id = %s "
        "AND processed = FALSE ORDER BY timestamp LIMIT %s",
        (user_id, limit),
    )
    return [_row_to_event(r) for r in rows]


def mark_event_processed(event_id: str) -> None:
    """标记事件已处理"""
    db = get_db()
    db.execute(
        "UPDATE cognitive_events SET processed = TRUE WHERE event_id = %s",
        (event_id,),
    )


def query_events(
    event_type: str | None = None,
    node_id: str | None = None,
    user_id: str = DEFAULT_USER_ID,
    limit: int = 50,
) -> list[CognitiveEvent]:
    """查询事件（按类型和/或节点过滤）"""
    db = get_db()
    conditions = ["user_id = %s"]
    params: list = [user_id]
    if event_type:
        conditions.append("event_type = %s")
        params.append(event_type)
    if node_id:
        conditions.append("node_id = %s")
        params.append(node_id)
    sql = f"SELECT * FROM cognitive_events WHERE {' AND '.join(conditions)} ORDER BY timestamp DESC LIMIT %s"
    params.append(limit)
    rows = db.fetchall(sql, tuple(params))
    return [_row_to_event(r) for r in rows]


# ── 辅助 ──


def _ts_to_pg(ts: float) -> str:
    """Unix 时间戳 → PostgreSQL TIMESTAMPTZ 字符串"""
    from datetime import datetime, timezone
    return datetime.fromtimestamp(ts, tz=timezone.utc).isoformat()


def _parse_embedding(raw) -> list[float] | None:
    """Parse embedding from JSONB column into list[float]"""
    if raw is None:
        return None
    if isinstance(raw, list):
        try:
            return [float(v) for v in raw]
        except (TypeError, ValueError):
            return None
    if isinstance(raw, str):
        try:
            return json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            return None
    return None


def _row_to_node(row: dict) -> CognitiveNode:
    """数据库行 → CognitiveNode"""
    raw = row

    def _parse_list(col, elem_type):
        """Parse JSONB list column into typed Pydantic models"""
        items = _parse_json_list(raw.get(col))
        result = []
        for item in items:
            if elem_type is str:
                result.append(str(item))
            elif elem_type is float:
                result.append(float(item))
            else:
                result.append(_from_json(elem_type, item))
        return result

    return CognitiveNode(
        id=raw["id"],
        label=raw.get("label", ""),
        level=raw.get("level", "atom"),
        parent=raw.get("parent"),
        children=_parse_list("children", str),
        is_core=raw.get("is_core", False),
        activation=_from_json(Activation, raw.get("activation")),
        belief=_from_json(Belief, raw.get("belief")),
        prediction=_from_json(Prediction, raw.get("prediction")),
        cognitive_load=_from_json(CognitiveLoad, raw.get("cognitive_load")),
        trend=_from_json(Trend, raw.get("trend")),
        scheduling=_from_json(Scheduling, raw.get("scheduling")),
        dialogue_contexts=_parse_list("dialogue_contexts", DialogueContext),
        practice_events=_parse_list("practice_events", PracticeEvent),
        practice_summary=_from_json(PracticeSummary, raw.get("practice_summary")),
        error_clusters=_parse_list("error_clusters", ErrorCluster),
        metacognition=_from_json(Metacognition, raw.get("metacognition")),
        engagement=_from_json(Engagement, raw.get("engagement")),
        composition=_from_json(Composition, raw.get("composition")),
        deep_links=_parse_list("deep_links", DeepLink),
        deep_processing=_from_json(DeepProcessing, raw.get("deep_processing")),
        goal_alignment=_from_json(GoalAlignment, raw.get("goal_alignment")),
        diagnostic=_from_json(Diagnostic, raw.get("diagnostic")),
        prerequisites=_parse_list("prerequisites", Prerequisite),
        unlocks=_parse_list("unlocks", Unlock),
        associates=_parse_list("associates", Associate),
        param_refs=_parse_json_dict(raw.get("param_refs")),
        meta=_from_json(MetaInfo, raw.get("meta")),
        # Phase 8 字段
        path_id=raw.get("path_id") or "",
        node_type=raw.get("node_type") or "explicit",
        is_visible=raw.get("is_visible", False),
        subsystems=_parse_json_dict(raw.get("subsystems")),
        embedding=_parse_embedding(raw.get("embedding")),
        is_active=raw.get("is_active", True),
    )


def _row_to_event(row: dict) -> CognitiveEvent:
    """数据库行 → CognitiveEvent"""
    ts = row.get("timestamp")
    timestamp = ts.timestamp() if hasattr(ts, "timestamp") else float(ts)
    return CognitiveEvent(
        event_id=row["event_id"],
        event_type=row["event_type"],
        user_id=row["user_id"],
        node_id=row.get("node_id"),
        timestamp=timestamp,
        payload=_parse_json_dict(row.get("payload")),
    )


def _parse_json_list(raw) -> list:
    if raw is None:
        return []
    if isinstance(raw, list):
        return raw
    if isinstance(raw, str):
        try:
            return json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            return []
    return []


def _parse_json_dict(raw) -> dict:
    if raw is None:
        return {}
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str):
        try:
            return json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            return {}
    return {}


# ── Phase 8 新方法 ──


def find_node_by_path(path_id: str, user_id: str = DEFAULT_USER_ID) -> Optional[CognitiveNode]:
    """通过 path_id 查找节点"""
    db = get_db()
    row = db.fetchone(
        "SELECT * FROM cognitive_nodes WHERE path_id = %s AND user_id = %s AND deleted_at IS NULL",
        (path_id, user_id),
    )
    if not row:
        return None
    return _row_to_node(row)


def vector_search(
    query_embedding: list[float],
    user_id: str = DEFAULT_USER_ID,
    level: str | None = None,
    limit: int = 10,
    min_similarity: float = 0.1,
) -> list[dict]:
    """向量检索：按余弦相似度在 Python 端计算

    JSONB 存储 embedding，不支持 pgvector 时用 Python 计算。
    返回：
    [{"id": str, "label": str, "path_id": str, "level": str,
      "similarity": float, "is_visible": bool}, ...]
    """
    query_norm = _cosine_normalize(query_embedding)

    db = get_db()
    level_filter = "AND level = %s" if level else ""
    level_param = (level,) if level else ()
    params = (user_id,) + level_param

    rows = db.fetchall(
        f"""
        SELECT id, label, path_id, level, is_visible, embedding
        FROM cognitive_nodes
        WHERE user_id = %s
          AND embedding IS NOT NULL
          AND deleted_at IS NULL
          {level_filter}
        """,
        params,
    )

    results = []
    for r in rows:
        embed = _parse_embedding(r.get("embedding"))
        if not embed:
            continue
        sim = _cosine_similarity(query_norm, embed)
        if sim < min_similarity:
            continue
        results.append({
            "id": r["id"],
            "label": r["label"],
            "path_id": r.get("path_id") or "",
            "level": r["level"],
            "is_visible": r.get("is_visible", False),
            "similarity": round(sim, 6),
        })

    results.sort(key=lambda x: -x["similarity"])
    return results[:limit]


def _cosine_normalize(vec: list[float]) -> tuple[list[float], float]:
    """归一化向量，同时返回原始范数"""
    norm = sum(v * v for v in vec) ** 0.5
    if norm == 0:
        return vec, 0.0
    return [v / norm for v in vec], norm


def _cosine_similarity(norm_a: tuple[list[float], float] | list[float],
                       norm_b: tuple[list[float], float] | list[float]) -> float:
    """计算两个归一化向量的余弦相似度

    接受 (vec, norm) tuple 或裸 list（自动归一化）
    """
    if isinstance(norm_a, tuple):
        a = norm_a[0]
    else:
        a, _ = _cosine_normalize(norm_a)
    if isinstance(norm_b, tuple):
        b = norm_b[0]
    else:
        b, _ = _cosine_normalize(norm_b)

    dot = sum(av * bv for av, bv in zip(a, b))
    return max(-1.0, min(1.0, dot))


def get_visible_children(parent_id: str, user_id: str = DEFAULT_USER_ID) -> list[CognitiveNode]:
    """获取某节点下可见的直接子节点"""
    db = get_db()
    rows = db.fetchall(
        "SELECT * FROM cognitive_nodes "
        "WHERE parent = %s AND user_id = %s AND is_visible = true AND deleted_at IS NULL "
        "ORDER BY label",
        (parent_id, user_id),
    )
    return [_row_to_node(r) for r in rows]


def find_node_by_label(
    label: str, user_id: str = DEFAULT_USER_ID,
) -> Optional[CognitiveNode]:
    """通过 label 查找节点（精确匹配优先，降级 ILIKE）"""
    db = get_db()
    # 精确匹配
    row = db.fetchone(
        "SELECT * FROM cognitive_nodes WHERE label = %s AND user_id = %s AND deleted_at IS NULL",
        (label, user_id),
    )
    if row:
        return _row_to_node(row)
    # 降级：模糊匹配取最相似的
    pattern = f"%{label}%"
    rows = db.fetchall(
        "SELECT * FROM cognitive_nodes WHERE user_id = %s AND deleted_at IS NULL "
        "AND label ILIKE %s "
        "ORDER BY length(label) DESC LIMIT 1",
        (user_id, pattern),
    )
    if rows:
        return _row_to_node(rows[0])
    return None


def sync_from_practice_event(
    user_id: str,
    skill_id: str,
    is_correct: bool,
    p_known_before: float = 0.5,
    p_known_after: float = 0.5,
    time_spent: float = 0.0,
    hints_used: int = 0,
) -> None:
    """练习事件 → 更新 cognitive_nodes 的 belief + practice_summary

    这是 Phase 9 的核心数据通路：将练习系统的 BKT 后验结果
    同步到 CognitiveNode 的 Beta 分布信念。
    """
    node = find_node_by_label(skill_id, user_id)
    if not node:
        logger.info(
            "sync_from_practice: no node found for skill=%s, creating atom node",
            skill_id,
        )
        # 自动创建原子节点
        node = CognitiveNode(
            id=skill_id,  # 复用 skill_id 作为 ID
            label=skill_id.split(".")[-1] if "." in skill_id else skill_id,
            level="atom",
            node_type="auto_generated",
            is_visible=False,
        )
        upsert_node(node, user_id)
        # 重新读取以获得全字段
        node = get_node(skill_id, user_id)
        if not node:
            logger.error("sync_from_practice: failed to create node for %s", skill_id)
            return

    # Beta 分布后验更新
    is_correct_int = 1 if is_correct else 0
    old_alpha = node.belief.alpha
    old_beta = node.belief.beta
    node.belief.alpha = old_alpha + is_correct_int
    node.belief.beta = old_beta + (1 - is_correct_int)
    total = node.belief.alpha + node.belief.beta
    node.belief.proficiency_mean = node.belief.alpha / total if total > 0 else 0.5
    node.belief.proficiency_precision = total
    node.belief.last_updated = time.time()
    node.belief.peak_proficiency = max(node.belief.peak_proficiency, node.belief.proficiency_mean)

    # 更新 practice_summary
    node.practice_summary.total_attempts += 1
    node.practice_summary.correct_attempts += is_correct_int
    node.practice_summary.total_time_spent += time_spent
    if node.practice_summary.total_attempts > 0:
        recent_rate = node.practice_summary.correct_attempts / node.practice_summary.total_attempts
    else:
        recent_rate = 0.0
    node.practice_summary.recent_success_rate_7d = recent_rate
    node.practice_summary.last_practiced = time.time()

    # 记录练习事件
    node.practice_events.append(PracticeEvent(
        timestamp=time.time(),
        success=is_correct,
        latency_ms=time_spent * 1000,
        weight=1.0 - (hints_used * 0.1),
    ))

    # ── Phase 11: CognitiveNode 预建字段填充 ──

    # 1. Trend: 记录近期掌握度变化
    window = node.trend.recent_proficiencies
    window.append(node.belief.proficiency_mean)
    if len(window) > 20:
        window.pop(0)
    node.trend.recent_proficiencies = window

    if len(window) >= 3:
        recent = window[-3:]
        slope = (recent[-1] - recent[0]) / 2.0
        prev_vel = node.trend.velocity_ewma or 0.0
        node.trend.velocity_ewma = 0.3 * slope + 0.7 * prev_vel
        if abs(node.trend.velocity_ewma) < 0.01:
            node.trend.direction = "stable"
        elif node.trend.velocity_ewma > 0.01:
            node.trend.direction = "ascending"
        else:
            node.trend.direction = "descending"

    # 停滞天数：没有显著进步的天数
    if node.trend.direction in ("stable", "descending"):
        if node.practice_summary.last_practiced:
            node.trend.stagnation_days = (
                time.time() - node.practice_summary.last_practiced
            ) / 86400.0

    # 2. CognitiveLoad: 根据错误率
    err_rate = 0.0
    if node.practice_summary.total_attempts > 0:
        err_rate = 1.0 - (node.practice_summary.correct_attempts / node.practice_summary.total_attempts)
    node.cognitive_load.intrinsic = min(err_rate * 1.5, 0.95)
    # 动态负荷：近期练习密度
    recent_count = sum(1 for e in node.practice_events if e.timestamp > time.time() - 3600)
    node.cognitive_load.dynamic = min(recent_count / 20.0, 1.0)

    # 3. ErrorClusters: 答错时追加错误记录
    if not is_correct:
        clusters = node.error_clusters
        cluster_id = f"err_{skill_id[:16]}"
        existing = next((c for c in clusters if c.cluster_id == cluster_id), None)
        if existing:
            existing.count += 1
            existing.last_seen = time.time()
        else:
            node.error_clusters.append(ErrorCluster(
                cluster_id=cluster_id,
                count=1,
                last_seen=time.time(),
            ))

    # 4. Engagement: XP + 连续练习
    xp_gain = 10 if is_correct else 2
    xp_gain += max(0, 10 - time_spent) * 0.5  # 快速作答奖励
    node.engagement.xp += xp_gain
    node.engagement.effort_estimate = max(0.0, 1.0 - err_rate * 1.2)
    # streak: 当天只要有一次练习就计一次连续
    now = time.time()
    today_start = now - (now % 86400)
    if node.practice_summary.last_practiced and node.practice_summary.last_practiced >= today_start:
        node.engagement.streak_current = max(node.engagement.streak_current, 1)
    else:
        node.engagement.streak_current = 1

    upsert_node(node, user_id)
    logger.info(
        "✅ Practice synced to CognitiveNode: skill=%s correct=%s "
        "belief=%.3f→%.3f (α=%d β=%d)",
        skill_id, is_correct,
        p_known_before, node.belief.proficiency_mean,
        node.belief.alpha, node.belief.beta,
    )


def get_suggested_count(parent_id: str, user_id: str = DEFAULT_USER_ID) -> int:
    """获取某节点下的建议/隐藏子节点数量（用于预览计数）"""
    db = get_db()
    row = db.fetchone(
        "SELECT COUNT(*) as cnt FROM cognitive_nodes "
        "WHERE parent = %s AND user_id = %s AND is_visible = false AND deleted_at IS NULL "
        "AND node_type IN ('auto_generated', 'suggested')",
        (parent_id, user_id),
    )
    return row["cnt"] if row else 0


def set_node_visible(node_id: str, user_id: str = DEFAULT_USER_ID) -> None:
    """设置节点可见，并级联设置所有祖先节点可见"""
    node = get_node(node_id, user_id)
    if not node:
        return
    db = get_db()
    db.execute(
        "UPDATE cognitive_nodes SET is_visible = true, updated_at = now() WHERE id = %s AND user_id = %s",
        (node_id, user_id),
    )
    # 级联设置父节点可见
    parent_id = node.parent
    visited = {node_id}
    while parent_id and parent_id not in visited:
        visited.add(parent_id)
        db.execute(
            "UPDATE cognitive_nodes SET is_visible = true, updated_at = now() WHERE id = %s AND user_id = %s",
            (parent_id, user_id),
        )
        parent_row = db.fetchone(
            "SELECT parent FROM cognitive_nodes WHERE id = %s AND user_id = %s",
            (parent_id, user_id),
        )
        parent_id = parent_row["parent"] if parent_row else None

