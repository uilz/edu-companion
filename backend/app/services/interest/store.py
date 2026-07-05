"""
InterestExplorer 数据访问层

提供 8 张表的标准 CRUD 封装:
- interest_tags
- interest_push_prefs
- interest_sources
- interest_source_subscriptions (用户对信息源的订阅/启用)
- interest_fetched_items (抓取缓存 — 跨用户共享)
- interest_push_records (链接级别去重的用户推送)
- interest_feedback
- interest_weight_adjustments (本地权重)

所有 SQL 显式处理 JSONB 序列化/反序列化，UUID 由调用方生成。
"""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from app.infrastructure.db.database import get_db

logger = logging.getLogger(__name__)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _new_id() -> str:
    return str(uuid.uuid4())


# ═══════════════════════════════════════════
# 1. interest_tags
# ═══════════════════════════════════════════


def create_tag(
    user_id: str,
    name: str,
    level: int = 0,
    parent_id: Optional[str] = None,
    weight: int = 1,
    source: str = "manual",
    source_ref_id: Optional[str] = None,
    color: Optional[str] = None,
) -> Optional[dict]:
    """创建兴趣标签

    source: manual / from_knowledge / from_reading
    weight: 1=主要, 2=次要
    """
    db = get_db()
    tag_id = _new_id()
    try:
        db.execute(
            """
            INSERT INTO interest_tags
            (id, user_id, name, level, parent_id, weight, source, source_ref_id, color, created_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                tag_id,
                user_id,
                name,
                level,
                parent_id,
                weight,
                source,
                source_ref_id,
                color,
                _now(),
            ),
        )
        return get_tag(user_id, tag_id)
    except Exception as e:
        logger.warning("create_tag 失败: %s", e)
        return None


def get_tag(user_id: str, tag_id: str) -> Optional[dict]:
    db = get_db()
    row = db.fetchone(
        "SELECT * FROM interest_tags WHERE id = %s AND user_id = %s",
        (tag_id, user_id),
    )
    return _row_to_dict(row)


def list_tags(user_id: str) -> list[dict]:
    db = get_db()
    rows = db.fetchall(
        "SELECT * FROM interest_tags WHERE user_id = %s ORDER BY level, name",
        (user_id,),
    )
    return [_row_to_dict(r) for r in rows]


def update_tag(
    user_id: str,
    tag_id: str,
    name: Optional[str] = None,
    weight: Optional[int] = None,
    color: Optional[str] = None,
    parent_id: Optional[str] = None,
) -> Optional[dict]:
    db = get_db()
    sets: list[str] = []
    params: list[Any] = []
    if name is not None:
        sets.append("name = %s")
        params.append(name)
    if weight is not None:
        sets.append("weight = %s")
        params.append(weight)
    if color is not None:
        sets.append("color = %s")
        params.append(color)
    if parent_id is not None:
        sets.append("parent_id = %s")
        params.append(parent_id)
    if not sets:
        return get_tag(user_id, tag_id)
    params.extend([tag_id, user_id])
    db.execute(
        f"UPDATE interest_tags SET {', '.join(sets)} "
        "WHERE id = %s AND user_id = %s",
        tuple(params),
    )
    return get_tag(user_id, tag_id)


def delete_tag(user_id: str, tag_id: str) -> bool:
    db = get_db()
    try:
        # 必须按 user_id 过滤并核对受影响行数，避免跨用户误删 / 误报成功
        rowcount = db.execute_with_rowcount(
            "DELETE FROM interest_tags WHERE id = %s AND user_id = %s",
            (tag_id, user_id),
        )
        return rowcount > 0
    except Exception as e:
        logger.warning("delete_tag 失败: %s", e)
        return False


# ═══════════════════════════════════════════
# 2. interest_push_prefs
# ═══════════════════════════════════════════


def get_prefs(user_id: str) -> dict:
    db = get_db()
    row = db.fetchone(
        "SELECT * FROM interest_push_prefs WHERE user_id = %s",
        (user_id,),
    )
    if not row:
        return default_prefs()
    return _prefs_row_to_dict(row)


def default_prefs() -> dict:
    return {
        "user_id": "",
        "frequency": "daily",
        "push_time": "08:00:00",
        "timezone": "Asia/Shanghai",
        "daily_limit": 6,
        "research_object_pct": 50,
        "research_method_pct": 30,
        "hot_news_pct": 20,
        "cross_disciplinary": False,
        "retention_days": 90,
        "is_enabled": True,
        "created_at": None,
        "updated_at": None,
    }


def upsert_prefs(user_id: str, updates: dict) -> dict:
    """插入或更新推送偏好

    校验:
      - 三个比例之和必须 = 100
      - frequency 必须是 daily/weekly/manual
    """
    db = get_db()
    current = get_prefs(user_id)
    merged = {**current, **updates, "user_id": user_id}

    # 校验比例之和
    s = (
        int(merged.get("research_object_pct", 50))
        + int(merged.get("research_method_pct", 30))
        + int(merged.get("hot_news_pct", 20))
    )
    if s != 100:
        raise ValueError(f"推送比例之和必须 = 100，当前: {s}")

    if merged.get("frequency") not in ("daily", "weekly", "manual"):
        raise ValueError("frequency 必须是 daily/weekly/manual")

    row = db.fetchone(
        "SELECT user_id FROM interest_push_prefs WHERE user_id = %s",
        (user_id,),
    )
    now = _now()
    if row:
        sets: list[str] = []
        params: list[Any] = []
        for k in [
            "frequency", "push_time", "timezone", "daily_limit",
            "research_object_pct", "research_method_pct", "hot_news_pct",
            "cross_disciplinary", "retention_days", "is_enabled",
        ]:
            if k in merged:
                sets.append(f"{k} = %s")
                params.append(merged[k])
        params.append(user_id)
        db.execute(
            f"UPDATE interest_push_prefs SET {', '.join(sets)} "
            "WHERE user_id = %s",
            tuple(params),
        )
    else:
        db.execute(
            """
            INSERT INTO interest_push_prefs
            (user_id, frequency, push_time, timezone, daily_limit,
             research_object_pct, research_method_pct, hot_news_pct,
             cross_disciplinary, retention_days, is_enabled,
             created_at, updated_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                user_id,
                merged.get("frequency", "daily"),
                merged.get("push_time", "08:00:00"),
                merged.get("timezone", "Asia/Shanghai"),
                int(merged.get("daily_limit", 6)),
                int(merged.get("research_object_pct", 50)),
                int(merged.get("research_method_pct", 30)),
                int(merged.get("hot_news_pct", 20)),
                bool(merged.get("cross_disciplinary", False)),
                int(merged.get("retention_days", 90)),
                bool(merged.get("is_enabled", True)),
                now,
                now,
            ),
        )
    return get_prefs(user_id)


# ═══════════════════════════════════════════
# 3. interest_sources
# ═══════════════════════════════════════════


def create_source(
    user_id: Optional[str],
    name: str,
    type_: str,
    config: dict,
    category: Optional[str] = None,
    is_system: bool = False,
    enabled: bool = True,
) -> Optional[dict]:
    db = get_db()
    source_id = _new_id()
    try:
        db.execute(
            """
            INSERT INTO interest_sources
            (id, user_id, name, type, category, config,
             enabled, is_system, last_fetched_at, last_fetch_status,
             last_fetch_error, created_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, NULL, NULL, NULL, %s)
            """,
            (
                source_id,
                user_id,
                name,
                type_,
                category,
                json.dumps(config, ensure_ascii=False),
                enabled,
                is_system,
                _now(),
            ),
        )
        return get_source(source_id)
    except Exception as e:
        logger.warning("create_source 失败: %s", e)
        return None


def get_source(source_id: str) -> Optional[dict]:
    db = get_db()
    row = db.fetchone(
        "SELECT * FROM interest_sources WHERE id = %s",
        (source_id,),
    )
    return _source_row_to_dict(row)


def list_sources(user_id: Optional[str] = None, enabled_only: bool = False) -> list[dict]:
    db = get_db()
    if user_id is None:
        sql = "SELECT * FROM interest_sources"
        params: tuple = ()
        if enabled_only:
            sql += " WHERE enabled = TRUE"
    else:
        sql = (
            "SELECT * FROM interest_sources "
            "WHERE (user_id = %s OR user_id IS NULL)"
        )
        params = (user_id,)
        if enabled_only:
            sql += " AND enabled = TRUE"
        sql += " ORDER BY is_system DESC, name"
    rows = db.fetchall(sql, params)
    return [_source_row_to_dict(r) for r in rows]


def list_enabled_sources() -> list[dict]:
    return list_sources(user_id=None, enabled_only=True)


def set_source_enabled(source_id: str, enabled: bool) -> bool:
    db = get_db()
    try:
        db.execute(
            "UPDATE interest_sources SET enabled = %s WHERE id = %s",
            (enabled, source_id),
        )
        return True
    except Exception as e:
        logger.warning("set_source_enabled 失败: %s", e)
        return False


def update_source_fetch_status(
    source_id: str,
    status: str,
    error: Optional[str] = None,
) -> None:
    db = get_db()
    try:
        db.execute(
            """
            UPDATE interest_sources
            SET last_fetched_at = %s,
                last_fetch_status = %s,
                last_fetch_error = %s
            WHERE id = %s
            """,
            (_now(), status, error, source_id),
        )
    except Exception as e:
        logger.warning("update_source_fetch_status 失败: %s", e)


def delete_source(source_id: str, user_id: Optional[str] = None) -> bool:
    """删除信息源

    关键安全约束 (避免跨用户误删):
      - user_id 提供时: 仅删除属于该用户的私有源 (user_id = x)
      - user_id=None:    仅删除系统源 (user_id IS NULL)
      - 跨用户请求会返回 False (受影响行数=0)
    """
    db = get_db()
    try:
        if user_id is None:
            sql = "DELETE FROM interest_sources WHERE id = %s AND user_id IS NULL"
            params: tuple = (source_id,)
        else:
            sql = "DELETE FROM interest_sources WHERE id = %s AND user_id = %s"
            params = (source_id, user_id)
        rowcount = db.execute_with_rowcount(sql, params)
        return rowcount > 0
    except Exception as e:
        logger.warning("delete_source 失败: %s", e)
        return False


def bulk_create_sources(sources: list[dict]) -> int:
    """批量创建信息源（OPML 导入使用）"""
    db = get_db()
    success = 0
    for s in sources:
        if create_source(**s):
            success += 1
    return success


# ═══════════════════════════════════════════
# 4. interest_push_records (链接级别去重)
# ═══════════════════════════════════════════


def create_push_record(
    user_id: str,
    push_type: str,
    title: str,
    source_id: Optional[str] = None,
    summary: Optional[str] = None,
    url: Optional[str] = None,
    author: Optional[str] = None,
    published_at: Optional[datetime] = None,
    matched_tags: Optional[list[str]] = None,
) -> Optional[dict]:
    """创建推送记录

    关键约束 (data-model.md §4):
      - url + user_id 唯一
      - url 为 NULL 时不去重（如纯文本推送）
    """
    db = get_db()
    push_id = _new_id()
    try:
        db.execute(
            """
            INSERT INTO interest_push_records
            (id, user_id, source_id, push_type, title, summary, url,
             author, published_at, matched_tags, generated_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                push_id,
                user_id,
                source_id,
                push_type,
                title,
                summary,
                url,
                author,
                published_at,
                json.dumps(matched_tags or [], ensure_ascii=False),
                _now(),
            ),
        )
        return get_push_record(user_id, push_id)
    except Exception as e:
        # 唯一约束冲突（链接级别去重）
        if "uq_push_records_user_url" in str(e) or "unique" in str(e).lower():
            logger.debug("推送链接已存在（链接级别去重）: %s", url)
            return None
        logger.warning("create_push_record 失败: %s", e)
        return None


def get_push_record(user_id: str, push_id: str) -> Optional[dict]:
    db = get_db()
    row = db.fetchone(
        "SELECT * FROM interest_push_records WHERE id = %s AND user_id = %s",
        (push_id, user_id),
    )
    return _push_row_to_dict(row)


def get_push_record_by_url(user_id: str, url: str) -> Optional[dict]:
    """按 URL 查询（链接级别去重的查询入口）"""
    if not url:
        return None
    db = get_db()
    row = db.fetchone(
        "SELECT * FROM interest_push_records "
        "WHERE user_id = %s AND url = %s LIMIT 1",
        (user_id, url),
    )
    return _push_row_to_dict(row)


def list_push_records(
    user_id: str,
    push_type: Optional[str] = None,
    since: Optional[datetime] = None,
    limit: int = 50,
    offset: int = 0,
) -> list[dict]:
    db = get_db()
    sql = "SELECT * FROM interest_push_records WHERE user_id = %s"
    params: list[Any] = [user_id]
    if push_type:
        sql += " AND push_type = %s"
        params.append(push_type)
    if since:
        sql += " AND generated_at >= %s"
        params.append(since)
    sql += " ORDER BY generated_at DESC LIMIT %s OFFSET %s"
    params.extend([limit, offset])
    rows = db.fetchall(sql, tuple(params))
    return [_push_row_to_dict(r) for r in rows]


def list_today_pushes(user_id: str) -> list[dict]:
    """查询今日推送（按本地时区 0 点起算）"""
    db = get_db()
    row = db.fetchone(
        "SELECT (NOW() AT TIME ZONE COALESCE("
        "(SELECT timezone FROM interest_push_prefs WHERE user_id = %s), "
        "'Asia/Shanghai'))::date AS today",
        (user_id,),
    )
    today = row["today"] if row else None
    if not today:
        return []
    sql = """
        SELECT * FROM interest_push_records
        WHERE user_id = %s
          AND (generated_at AT TIME ZONE COALESCE(
            (SELECT timezone FROM interest_push_prefs WHERE user_id = %s),
            'Asia/Shanghai'))::date = %s
        ORDER BY generated_at DESC
    """
    rows = db.fetchall(sql, (user_id, user_id, today))
    return [_push_row_to_dict(r) for r in rows]


# ═══════════════════════════════════════════
# 5. interest_feedback
# ═══════════════════════════════════════════


def record_feedback(
    push_id: str,
    user_id: str,
    feedback: str,
    target_module: Optional[str] = None,
    target_ref_id: Optional[str] = None,
) -> Optional[dict]:
    db = get_db()
    try:
        db.execute(
            """
            INSERT INTO interest_feedback
            (push_id, user_id, feedback, target_module, target_ref_id, feedback_at)
            VALUES (%s, %s, %s, %s, %s, %s)
            ON CONFLICT (push_id) DO UPDATE
            SET feedback = EXCLUDED.feedback,
                target_module = EXCLUDED.target_module,
                target_ref_id = EXCLUDED.target_ref_id,
                feedback_at = EXCLUDED.feedback_at
            """,
            (push_id, user_id, feedback, target_module, target_ref_id, _now()),
        )
        return get_feedback(push_id)
    except Exception as e:
        logger.warning("record_feedback 失败: %s", e)
        return None


def get_feedback(push_id: str) -> Optional[dict]:
    db = get_db()
    row = db.fetchone(
        "SELECT * FROM interest_feedback WHERE push_id = %s",
        (push_id,),
    )
    return _feedback_row_to_dict(row)


def list_feedback(user_id: str, limit: int = 50) -> list[dict]:
    """列出用户反馈（关联 push_records 取 url）"""
    db = get_db()
    rows = db.fetchall(
        """
        SELECT f.*, p.url AS push_url
        FROM interest_feedback f
        LEFT JOIN interest_push_records p ON p.id = f.push_id
        WHERE f.user_id = %s
        ORDER BY f.feedback_at DESC
        LIMIT %s
        """,
        (user_id, limit),
    )
    out: list[dict] = []
    for r in rows:
        d = dict(r)
        for k, v in list(d.items()):
            if hasattr(v, "isoformat"):
                d[k] = v.isoformat()
        out.append(d)
    return out


def get_feedback_for_push(push_id: str) -> Optional[dict]:
    return get_feedback(push_id)


# ═══════════════════════════════════════════
# 6. interest_weight_adjustments (本地权重)
# ═══════════════════════════════════════════


def get_weight_adjustment(user_id: str, tag_id: str) -> Optional[dict]:
    db = get_db()
    row = db.fetchone(
        """
        SELECT * FROM interest_weight_adjustments
        WHERE user_id = %s AND tag_id = %s
        """,
        (user_id, tag_id),
    )
    return _weight_row_to_dict(row)


def list_weight_adjustments(user_id: str) -> list[dict]:
    db = get_db()
    rows = db.fetchall(
        """
        SELECT wa.*, t.name AS tag_name, t.level AS tag_level
        FROM interest_weight_adjustments wa
        LEFT JOIN interest_tags t ON t.id = wa.tag_id
        WHERE wa.user_id = %s
        ORDER BY wa.dislike_score DESC
        """,
        (user_id,),
    )
    return [_weight_row_to_dict(r) for r in rows]


def increment_dislike(user_id: str, tag_id: str, delta: float = 0.1) -> dict:
    """累计不感兴趣分数

    关键约束 (ADR 0007 决策 10):
      - 不发送到服务端
      - 仅本地采样概率调整
      - 累计 0.0-1.0
    """
    db = get_db()
    current = get_weight_adjustment(user_id, tag_id)
    if current:
        new_score = min(1.0, current["dislike_score"] + delta)
        new_count = current["adjustment_count"] + 1
        db.execute(
            """
            UPDATE interest_weight_adjustments
            SET dislike_score = %s,
                adjustment_count = %s
            WHERE user_id = %s AND tag_id = %s
            """,
            (new_score, new_count, user_id, tag_id),
        )
    else:
        new_id = _new_id()
        new_score = min(1.0, delta)
        new_count = 1
        db.execute(
            """
            INSERT INTO interest_weight_adjustments
            (id, user_id, tag_id, dislike_score, adjustment_count, updated_at)
            VALUES (%s, %s, %s, %s, %s, %s)
            """,
            (new_id, user_id, tag_id, new_score, new_count, _now()),
        )
    return get_weight_adjustment(user_id, tag_id) or {}


def reset_weights(user_id: str) -> int:
    """清空本地权重"""
    db = get_db()
    try:
        db.execute(
            "DELETE FROM interest_weight_adjustments WHERE user_id = %s",
            (user_id,),
        )
        return 1
    except Exception as e:
        logger.warning("reset_weights 失败: %s", e)
        return 0


# ═══════════════════════════════════════════
# 7. 清理过期推送
# ═══════════════════════════════════════════


def cleanup_expired(retention_days: int) -> int:
    db = get_db()
    try:
        return int(db.fetchone(
            "SELECT interest_cleanup_expired(%s) AS deleted",
            (retention_days,),
        )["deleted"] or 0)
    except Exception as e:
        logger.warning("cleanup_expired 失败: %s", e)
        return 0


# ═══════════════════════════════════════════
# 辅助 - 行转 dict (JSONB 反序列化)
# ═══════════════════════════════════════════


def _row_to_dict(row: Optional[dict]) -> Optional[dict]:
    if not row:
        return None
    out = dict(row)
    for k, v in list(out.items()):
        if hasattr(v, "isoformat"):
            out[k] = v.isoformat()
    return out


def _source_row_to_dict(row: Optional[dict]) -> Optional[dict]:
    if not row:
        return None
    out = dict(row)
    if "config" in out and isinstance(out["config"], str):
        try:
            out["config"] = json.loads(out["config"])
        except Exception:
            out["config"] = {}
    for k, v in list(out.items()):
        if hasattr(v, "isoformat"):
            out[k] = v.isoformat()
    return out


def _push_row_to_dict(row: Optional[dict]) -> Optional[dict]:
    if not row:
        return None
    out = dict(row)
    if "matched_tags" in out and isinstance(out["matched_tags"], str):
        try:
            out["matched_tags"] = json.loads(out["matched_tags"])
        except Exception:
            out["matched_tags"] = []
    if isinstance(out.get("matched_tags"), list) is False:
        out["matched_tags"] = []
    for k, v in list(out.items()):
        if hasattr(v, "isoformat"):
            out[k] = v.isoformat()
    return out


def _prefs_row_to_dict(row: dict) -> dict:
    out = dict(row)
    if hasattr(out.get("push_time"), "isoformat"):
        out["push_time"] = out["push_time"].isoformat()
    elif out.get("push_time") is not None:
        out["push_time"] = str(out["push_time"])
    if hasattr(out.get("created_at"), "isoformat"):
        out["created_at"] = out["created_at"].isoformat()
    if hasattr(out.get("updated_at"), "isoformat"):
        out["updated_at"] = out["updated_at"].isoformat()
    return out


def _feedback_row_to_dict(row: Optional[dict]) -> Optional[dict]:
    if not row:
        return None
    out = dict(row)
    if hasattr(out.get("feedback_at"), "isoformat"):
        out["feedback_at"] = out["feedback_at"].isoformat()
    return out


def _weight_row_to_dict(row: Optional[dict]) -> Optional[dict]:
    if not row:
        return None
    out = dict(row)
    if hasattr(out.get("updated_at"), "isoformat"):
        out["updated_at"] = out["updated_at"].isoformat()
    return out


# ═══════════════════════════════════════════
# 7. interest_source_subscriptions
#    用户对 (系统/自定义) 源的订阅状态
#    - 系统源 (interest_sources.user_id IS NULL) 需要按用户启用
#    - 自定义源 (interest_sources.user_id = x) 自动订阅，可单独禁用
# ═══════════════════════════════════════════


def ensure_subscription(
    user_id: str,
    source_id: str,
    enabled: bool = True,
) -> Optional[dict]:
    """幂等创建订阅（已存在则更新 enabled）"""
    db = get_db()
    sub_id = _new_id()
    try:
        db.execute(
            """
            INSERT INTO interest_source_subscriptions
            (id, user_id, source_id, enabled, created_at, updated_at)
            VALUES (%s, %s, %s, %s, NOW(), NOW())
            ON CONFLICT (user_id, source_id) DO UPDATE
            SET enabled = EXCLUDED.enabled, updated_at = NOW()
            """,
            (sub_id, user_id, source_id, enabled),
        )
        return get_subscription(user_id, source_id)
    except Exception as e:
        logger.warning("ensure_subscription 失败: %s", e)
        return None


def get_subscription(user_id: str, source_id: str) -> Optional[dict]:
    db = get_db()
    row = db.fetchone(
        "SELECT * FROM interest_source_subscriptions "
        "WHERE user_id = %s AND source_id = %s",
        (user_id, source_id),
    )
    if not row:
        return None
    out = dict(row)
    for k, v in list(out.items()):
        if hasattr(v, "isoformat"):
            out[k] = v.isoformat()
    return out


def list_user_subscriptions(
    user_id: str, enabled_only: bool = False
) -> list[dict]:
    """列出用户的所有订阅"""
    db = get_db()
    sql = "SELECT * FROM interest_source_subscriptions WHERE user_id = %s"
    params: tuple = (user_id,)
    if enabled_only:
        sql += " AND enabled = TRUE"
    rows = db.fetchall(sql, params)
    out: list[dict] = []
    for row in rows:
        d = dict(row)
        for k, v in list(d.items()):
            if hasattr(v, "isoformat"):
                d[k] = v.isoformat()
        out.append(d)
    return out


def list_enabled_source_ids_for_user(user_id: str) -> list[str]:
    """返回用户启用的所有 source_id 列表 (系统源 + 私有源)

    判定逻辑:
      - 用户私有源 (interest_sources.user_id = user_id) → 视为启用
      - 系统源 (interest_sources.user_id IS NULL):
          - 有关闭订阅 (enabled=FALSE) → 不启用
          - 无订阅记录 → 默认不启用 (避免冷启动)
    """
    db = get_db()
    rows = db.fetchall(
        """
        SELECT s.id AS source_id,
               s.user_id AS owner_id,
               sub.enabled AS sub_enabled,
               sub.id AS sub_id
        FROM interest_sources s
        LEFT JOIN interest_source_subscriptions sub
          ON sub.source_id = s.id AND sub.user_id = %s
        WHERE s.enabled = TRUE
          AND (
            s.user_id = %s
            OR (s.user_id IS NULL AND sub.enabled = TRUE)
          )
        """,
        (user_id, user_id),
    )
    return [r["source_id"] for r in rows]


def set_subscription_enabled(
    user_id: str, source_id: str, enabled: bool
) -> bool:
    db = get_db()
    try:
        # upsert：先尝试更新，不存在则插入
        db.execute(
            """
            INSERT INTO interest_source_subscriptions
            (id, user_id, source_id, enabled, created_at, updated_at)
            SELECT %s, %s, %s, %s, NOW(), NOW()
            WHERE EXISTS (
                SELECT 1 FROM interest_sources WHERE id = %s
            )
            ON CONFLICT (user_id, source_id) DO UPDATE
            SET enabled = EXCLUDED.enabled, updated_at = NOW()
            """,
            (_new_id(), user_id, source_id, enabled, source_id),
        )
        # 上面 INSERT ... SELECT 可能在源不存在时跳过；显式检查行数
        row = db.fetchone(
            "SELECT id FROM interest_source_subscriptions "
            "WHERE user_id = %s AND source_id = %s",
            (user_id, source_id),
        )
        if not row:
            return False
        return True
    except Exception as e:
        logger.warning("set_subscription_enabled 失败: %s", e)
        return False


# ═══════════════════════════════════════════
# 8. interest_fetched_items
#    全局抓取缓存 — 每次抓取后写入
#    trigger_push 时按用户启用的 source 列表读取候选
# ═══════════════════════════════════════════


def upsert_fetched_items(
    source_id: str,
    items: list[dict],
) -> int:
    """把抓取到的条目写入缓存 (按 (source_id, url) 去重)

    items 中每个元素至少包含: title, url, summary, author, published_at
    返回新增数量
    """
    if not items:
        return 0
    db = get_db()
    added = 0
    for item in items:
        url = item.get("url")
        title = item.get("title") or ""
        if not title:
            continue
        try:
            db.execute(
                """
                INSERT INTO interest_fetched_items
                (id, source_id, title, url, summary, author, published_at, fetched_at)
                SELECT %s, %s, %s, %s, %s, %s, %s, NOW()
                WHERE NOT EXISTS (
                    SELECT 1 FROM interest_fetched_items
                    WHERE source_id = %s AND url IS NOT NULL
                      AND url = %s
                )
                """,
                (
                    _new_id(),
                    source_id,
                    title,
                    url,
                    item.get("summary"),
                    item.get("author"),
                    item.get("published_at"),
                    source_id,
                    url,
                ),
            )
            added += 1
        except Exception as e:
            logger.debug("upsert_fetched_item 失败 (源=%s): %s", source_id, e)
    return added


def list_fetched_items(
    source_ids: list[str],
    limit_per_source: int = 50,
    since: Optional[datetime] = None,
) -> list[dict]:
    """读取多个 source 最近的抓取条目

    返回: [{source_id, title, url, summary, author, published_at, fetched_at}, ...]
    """
    if not source_ids:
        return []
    db = get_db()
    # 使用 LATERAL 取每个 source 的 top N
    placeholders = ",".join(["%s"] * len(source_ids))
    sql = f"""
        SELECT DISTINCT ON (source_id, url) *
        FROM interest_fetched_items
        WHERE source_id IN ({placeholders})
    """
    params: list[Any] = list(source_ids)
    if since:
        sql += " AND fetched_at >= %s"
        params.append(since)
    sql += " ORDER BY source_id, url, fetched_at DESC"
    rows = db.fetchall(sql, tuple(params))
    out: list[dict] = []
    for r in rows:
        d = dict(r)
        for k, v in list(d.items()):
            if hasattr(v, "isoformat"):
                d[k] = v.isoformat()
        out.append(d)
    return out


def cleanup_fetched_items(older_than_days: int = 30) -> int:
    """清理过期的抓取缓存"""
    db = get_db()
    try:
        db.execute(
            "DELETE FROM interest_fetched_items "
            "WHERE fetched_at < NOW() - (%s || ' days')::INTERVAL",
            (older_than_days,),
        )
        return 0
    except Exception as e:
        logger.warning("cleanup_fetched_items 失败: %s", e)
        return 0
