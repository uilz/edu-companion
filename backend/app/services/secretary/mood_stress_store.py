"""
MoodStress 模块数据访问层 (Task #87)

负责 5 张表的数据访问：
  - mood_stress_prefs        — 用户偏好 (19 项)
  - emotion_records          — 情绪/压力/能量记录 (manual + auto)
  - mood_stress_intervention_logs — 干预工具日志
  - mood_stress_rules        — 用户自定义规则
  - behavior_signals         — 行为信号 (7 种类型)

设计：
1. **单一职责**：本文件只做数据 CRUD，业务逻辑在 modules/mood_stress.py
2. **跨用户隔离**：所有方法都必须接受 user_id 并在 SQL 中过滤
3. **不抛业务异常**：404 / 验证错误由 API 层处理，store 仅返回 bool / row
4. **JSON 字段**：emotion_tags / related_event_ids / signal_data 等用 psycopg2 JSONB
5. **UUID**：所有主键为 str(uuid4())，删除/查找时用 UUID 格式校验
"""
from __future__ import annotations

import json
import logging
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Any, Optional

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────
# 19 项偏好默认值
# ──────────────────────────────────────────────

DEFAULT_PREFS: dict[str, Any] = {
    "reminder_enabled": False,
    "reminder_frequency": None,
    "reminder_time": None,
    "data_retention_days": 90,
    "auto_collect_task_switch": True,
    "auto_collect_stay_duration": True,
    "auto_collect_error_rate": True,
    "auto_collect_undo": True,
    "auto_collect_session_anomaly": True,
    "auto_collect_flashcard_failure": True,
    "auto_collect_voice_features": False,
    "output_to_planning": True,
    "output_to_conversation": True,
    "output_to_language_room": True,
    "knowledge_breathing_excluded_node_ids": [],
    "environment_theme": "default",
    "environment_sound": "none",
    "planning_rules": {},
}

# 19 项偏好字段（用于 SQL 动态构建）
PREFS_COLUMNS: list[str] = [
    "reminder_enabled",
    "reminder_frequency",
    "reminder_time",
    "data_retention_days",
    "auto_collect_task_switch",
    "auto_collect_stay_duration",
    "auto_collect_error_rate",
    "auto_collect_undo",
    "auto_collect_session_anomaly",
    "auto_collect_flashcard_failure",
    "auto_collect_voice_features",
    "output_to_planning",
    "output_to_conversation",
    "output_to_language_room",
    "knowledge_breathing_excluded_node_ids",
    "environment_theme",
    "environment_sound",
    "planning_rules",
]


# ──────────────────────────────────────────────
# 数据类
# ──────────────────────────────────────────────

@dataclass
class EmotionRecord:
    """emotion_records 表的一行"""
    id: str
    user_id: str
    source: str  # manual / auto
    emotion_tags: list[str] = field(default_factory=list)
    pressure_score: Optional[int] = None
    energy_score: Optional[int] = None
    text_note: Optional[str] = None
    related_event_ids: list[str] = field(default_factory=list)
    created_at: Optional[str] = None

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class InterventionLog:
    """mood_stress_intervention_logs 表的一行"""
    id: str
    user_id: str
    intervention_type: str
    duration_seconds: Optional[int] = None
    trigger_event: Optional[str] = None
    notes: Optional[str] = None
    created_at: Optional[str] = None

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class BehaviorSignal:
    """behavior_signals 表的一行"""
    id: str
    user_id: str
    signal_type: str
    signal_data: dict = field(default_factory=dict)
    severity: int = 1
    is_read: bool = False
    created_at: Optional[str] = None

    def to_dict(self) -> dict:
        return asdict(self)


# ──────────────────────────────────────────────
# 工具
# ──────────────────────────────────────────────

def _new_id() -> str:
    """生成完整 UUID 字符串（36 字符含连字符）

    数据库 emotion_records.id / mood_stress_intervention_logs.id /
    mood_stress_rules.id / behavior_signals.id 都是 uuid 类型。
    """
    return str(uuid.uuid4())


def _is_uuid_like(s: str) -> bool:
    """判断字符串是否像 UUID（包含连字符的 36 字符或纯 12+ 字符 hex）"""
    if not s or not isinstance(s, str):
        return False
    s = s.strip()
    # 完整 UUID 36 字符
    if len(s) == 36 and s.count("-") == 4:
        try:
            uuid.UUID(s)
            return True
        except ValueError:
            return False
    # 短 UUID 12 字符 hex
    if len(s) >= 12 and all(c in "0123456789abcdefABCDEF" for c in s):
        return True
    return False


def _to_jsonb(value: Any) -> str:
    """list/dict → JSON 字符串（psycopg2 不能直接传 list 给 JSONB 参数）"""
    if value is None:
        return "[]"
    if isinstance(value, str):
        return value
    return json.dumps(value, ensure_ascii=False)


def _from_jsonb(value: Any, default: Any = None) -> Any:
    """JSONB → list/dict（psycopg2 取出的 JSONB 字段是 str/None）"""
    if value is None:
        return default
    if isinstance(value, (list, dict)):
        return value
    if isinstance(value, str):
        try:
            return json.loads(value)
        except (json.JSONDecodeError, TypeError):
            return default
    return default


# ──────────────────────────────────────────────
# 偏好 (mood_stress_prefs)
# ──────────────────────────────────────────────

def get_prefs(user_id: str) -> dict:
    """读取用户偏好 — 缺失时返回默认 19 项"""
    from app.infrastructure.db.database import get_db
    db = get_db()

    row = db.fetchone(
        "SELECT * FROM mood_stress_prefs WHERE user_id = %s",
        (user_id,),
    )

    if not row:
        return dict(DEFAULT_PREFS)

    # 解析 JSONB 字段
    out = dict(DEFAULT_PREFS)
    out["user_id"] = user_id
    for col in PREFS_COLUMNS:
        if col in row:
            val = row[col]
            if col in ("knowledge_breathing_excluded_node_ids", "planning_rules"):
                out[col] = _from_jsonb(val, default=DEFAULT_PREFS.get(col))
            else:
                out[col] = val
    out["created_at"] = row.get("created_at").isoformat() if row.get("created_at") else None
    out["updated_at"] = row.get("updated_at").isoformat() if row.get("updated_at") else None
    return out


def upsert_prefs(user_id: str, delta: dict) -> dict:
    """
    增量更新偏好 — 只覆盖 delta 中显式提供的字段。

    设计：保留不在 delta 中的字段不变 (真正增量)。
    """
    from app.infrastructure.db.database import get_db
    db = get_db()

    # 过滤掉不在 PREFS_COLUMNS 的字段
    safe_delta = {k: v for k, v in delta.items() if k in PREFS_COLUMNS}
    if not safe_delta:
        return get_prefs(user_id)

    # JSONB 字段序列化
    payload: dict[str, Any] = {}
    for k, v in safe_delta.items():
        if k in ("knowledge_breathing_excluded_node_ids", "planning_rules"):
            payload[k] = _to_jsonb(v)
        else:
            payload[k] = v

    columns = list(payload.keys())
    placeholders = ", ".join(f"%({k})s" for k in columns)
    update_clause = ", ".join(f"{k} = EXCLUDED.{k}" for k in columns)
    update_clause += ", updated_at = NOW()"

    sql = (
        f"INSERT INTO mood_stress_prefs (user_id, {', '.join(columns)}, created_at, updated_at) "
        f"VALUES (%(user_id)s, {placeholders}, NOW(), NOW()) "
        f"ON CONFLICT (user_id) DO UPDATE SET {update_clause}"
    )
    params = {**payload, "user_id": user_id}
    db.execute(sql, params)

    return get_prefs(user_id)


# ──────────────────────────────────────────────
# 情绪记录 (emotion_records)
# ──────────────────────────────────────────────

def insert_emotion_record(
    user_id: str,
    source: str,
    emotion_tags: list[str],
    pressure_score: Optional[int],
    energy_score: Optional[int],
    text_note: Optional[str],
    related_event_ids: Optional[list[str]] = None,
    record_id: Optional[str] = None,
) -> EmotionRecord:
    """插入一条情绪记录"""
    from app.infrastructure.db.database import get_db
    db = get_db()

    rid = record_id or _new_id()
    sql = (
        "INSERT INTO emotion_records "
        "(id, user_id, source, emotion_tags, pressure_score, energy_score, text_note, related_event_ids, created_at) "
        "VALUES (%(id)s, %(user_id)s, %(source)s, %(emotion_tags)s, %(pressure_score)s, "
        "%(energy_score)s, %(text_note)s, %(related_event_ids)s, NOW())"
    )
    db.execute(sql, {
        "id": rid,
        "user_id": user_id,
        "source": source,
        "emotion_tags": _to_jsonb(emotion_tags or []),
        "pressure_score": pressure_score,
        "energy_score": energy_score,
        "text_note": text_note,
        "related_event_ids": _to_jsonb(related_event_ids or []),
    })
    return get_emotion_record(user_id=user_id, record_id=rid) or EmotionRecord(
        id=rid, user_id=user_id, source=source,
        emotion_tags=emotion_tags, pressure_score=pressure_score,
        energy_score=energy_score, text_note=text_note,
        related_event_ids=related_event_ids or [],
    )


def get_emotion_record(user_id: str, record_id: str) -> Optional[EmotionRecord]:
    """读取单条情绪记录"""
    from app.infrastructure.db.database import get_db
    db = get_db()

    row = db.fetchone(
        "SELECT * FROM emotion_records WHERE user_id = %s AND id = %s",
        (user_id, record_id),
    )
    if not row:
        return None
    return _row_to_emotion_record(row)


def _row_to_emotion_record(row: dict) -> EmotionRecord:
    return EmotionRecord(
        id=row["id"],
        user_id=row["user_id"],
        source=row["source"],
        emotion_tags=_from_jsonb(row.get("emotion_tags"), default=[]),
        pressure_score=row.get("pressure_score"),
        energy_score=row.get("energy_score"),
        text_note=row.get("text_note"),
        related_event_ids=_from_jsonb(row.get("related_event_ids"), default=[]),
        created_at=row.get("created_at").isoformat() if row.get("created_at") else None,
    )


def list_emotion_records(
    user_id: str,
    source: Optional[str] = None,
    days: int = 30,
    limit: int = 50,
) -> list[EmotionRecord]:
    """列出用户情绪记录（按时间倒序）"""
    from app.infrastructure.db.database import get_db
    db = get_db()

    conditions = ["user_id = %s", "created_at >= NOW() - (%s || ' days')::INTERVAL"]
    params: list[Any] = [user_id, str(days)]
    if source:
        conditions.append("source = %s")
        params.append(source)

    params.append(limit)
    sql = (
        f"SELECT * FROM emotion_records "
        f"WHERE {' AND '.join(conditions)} "
        f"ORDER BY created_at DESC LIMIT %s"
    )
    rows = db.fetchall(sql, tuple(params))
    return [_row_to_emotion_record(r) for r in rows]


def delete_emotion_record(user_id: str, record_id: str) -> bool:
    """删除单条情绪记录（遗忘权）"""
    if not _is_uuid_like(record_id):
        return False
    from app.infrastructure.db.database import get_db
    db = get_db()
    try:
        conn = db.get_conn()
        cur = conn.cursor()
        cur.execute(
            "DELETE FROM emotion_records WHERE user_id = %s AND id = %s",
            (user_id, record_id),
        )
        rowcount = cur.rowcount
        conn.commit()
        cur.close()
        db.put_conn(conn)
        return rowcount > 0
    except Exception as exc:  # noqa: BLE001
        logger.debug("delete_emotion_record 失败: %s", exc)
        return False


# ──────────────────────────────────────────────
# 干预日志 (mood_stress_intervention_logs)
# ──────────────────────────────────────────────

def insert_intervention(
    user_id: str,
    intervention_type: str,
    duration_seconds: Optional[int] = None,
    trigger_event: Optional[str] = None,
    notes: Optional[str] = None,
    intervention_id: Optional[str] = None,
) -> InterventionLog:
    """记录一次干预工具使用"""
    from app.infrastructure.db.database import get_db
    db = get_db()

    iid = intervention_id or _new_id()
    sql = (
        "INSERT INTO mood_stress_intervention_logs "
        "(id, user_id, intervention_type, duration_seconds, trigger_event, notes, created_at) "
        "VALUES (%(id)s, %(user_id)s, %(type)s, %(duration)s, %(trigger)s, %(notes)s, NOW())"
    )
    db.execute(sql, {
        "id": iid,
        "user_id": user_id,
        "type": intervention_type,
        "duration": duration_seconds,
        "trigger": trigger_event,
        "notes": notes,
    })
    return InterventionLog(
        id=iid, user_id=user_id, intervention_type=intervention_type,
        duration_seconds=duration_seconds, trigger_event=trigger_event,
        notes=notes, created_at=datetime.now(timezone.utc).isoformat(),
    )


def list_interventions(
    user_id: str,
    days: int = 30,
    limit: int = 50,
) -> list[InterventionLog]:
    """列出干预日志"""
    from app.infrastructure.db.database import get_db
    db = get_db()

    rows = db.fetchall(
        "SELECT * FROM mood_stress_intervention_logs "
        "WHERE user_id = %s AND created_at >= NOW() - (%s || ' days')::INTERVAL "
        "ORDER BY created_at DESC LIMIT %s",
        (user_id, str(days), limit),
    )
    return [
        InterventionLog(
            id=r["id"],
            user_id=r["user_id"],
            intervention_type=r["intervention_type"],
            duration_seconds=r.get("duration_seconds"),
            trigger_event=r.get("trigger_event"),
            notes=r.get("notes"),
            created_at=r["created_at"].isoformat() if r.get("created_at") else None,
        )
        for r in rows
    ]


# ──────────────────────────────────────────────
# 行为信号 (behavior_signals)
# ──────────────────────────────────────────────

def insert_behavior_signal(
    user_id: str,
    signal_type: str,
    signal_data: dict,
    severity: int = 1,
    signal_id: Optional[str] = None,
) -> BehaviorSignal:
    """记录一条行为信号"""
    from app.infrastructure.db.database import get_db
    db = get_db()

    sid = signal_id or _new_id()
    sql = (
        "INSERT INTO behavior_signals "
        "(id, user_id, signal_type, signal_data, severity, is_read, created_at) "
        "VALUES (%(id)s, %(user_id)s, %(type)s, %(data)s, %(severity)s, FALSE, NOW())"
    )
    db.execute(sql, {
        "id": sid,
        "user_id": user_id,
        "type": signal_type,
        "data": _to_jsonb(signal_data or {}),
        "severity": severity,
    })
    return BehaviorSignal(
        id=sid, user_id=user_id, signal_type=signal_type,
        signal_data=signal_data or {}, severity=severity, is_read=False,
        created_at=datetime.now(timezone.utc).isoformat(),
    )


def list_unread_signals(user_id: str, limit: int = 50) -> list[BehaviorSignal]:
    """列出未读行为信号（按时间倒序）"""
    from app.infrastructure.db.database import get_db
    db = get_db()

    rows = db.fetchall(
        "SELECT * FROM behavior_signals "
        "WHERE user_id = %s AND is_read = FALSE "
        "ORDER BY created_at DESC LIMIT %s",
        (user_id, limit),
    )
    return [_row_to_behavior_signal(r) for r in rows]


def _row_to_behavior_signal(row: dict) -> BehaviorSignal:
    return BehaviorSignal(
        id=row["id"],
        user_id=row["user_id"],
        signal_type=row["signal_type"],
        signal_data=_from_jsonb(row.get("signal_data"), default={}),
        severity=row.get("severity", 1),
        is_read=row.get("is_read", False),
        created_at=row["created_at"].isoformat() if row.get("created_at") else None,
    )


def mark_signals_read(user_id: str, ids: list[str]) -> int:
    """批量标记信号已读 — 返回成功标记数

    静默忽略非法 ID（防止 422），但返回 0 表示无任何变更。
    """
    if not ids:
        return 0
    valid_ids = [i for i in ids if _is_uuid_like(i)]
    if not valid_ids:
        return 0

    from app.infrastructure.db.database import get_db
    db = get_db()

    placeholders = ", ".join(["%s"] * len(valid_ids))
    sql = (
        f"UPDATE behavior_signals SET is_read = TRUE "
        f"WHERE user_id = %s AND id IN ({placeholders}) AND is_read = FALSE"
    )
    # psycopg2.execute 的第二个参数是 tuple，多个 %s 需要展开
    conn = db.get_conn()
    try:
        cur = conn.cursor()
        cur.execute(sql, (user_id, *valid_ids))
        rowcount = cur.rowcount
        conn.commit()
        cur.close()
        db.put_conn(conn)
        return rowcount
    except Exception as exc:  # noqa: BLE001
        try:
            conn.rollback()
        except Exception:
            pass
        db.put_conn(conn)
        logger.debug("mark_signals_read 失败: %s", exc)
        return 0


# ──────────────────────────────────────────────
# 规则 (mood_stress_rules)
# ──────────────────────────────────────────────

def add_rule(
    user_id: str,
    rule_name: str,
    trigger_metric: str,
    trigger_operator: str,
    trigger_value: Any,
    action: str,
) -> str:
    """新增规则 — 返回新规则 ID"""
    from app.infrastructure.db.database import get_db
    db = get_db()

    rid = _new_id()
    sql = (
        "INSERT INTO mood_stress_rules "
        "(id, user_id, rule_name, trigger_metric, trigger_operator, trigger_value, action, is_enabled, created_at) "
        "VALUES (%(id)s, %(user_id)s, %(name)s, %(metric)s, %(op)s, %(value)s, %(action)s, TRUE, NOW())"
    )
    db.execute(sql, {
        "id": rid,
        "user_id": user_id,
        "name": rule_name,
        "metric": trigger_metric,
        "op": trigger_operator,
        "value": _to_jsonb(trigger_value),
        "action": action,
    })
    return rid


def list_rules(user_id: str) -> list[dict]:
    """列出用户所有规则"""
    from app.infrastructure.db.database import get_db
    db = get_db()

    rows = db.fetchall(
        "SELECT * FROM mood_stress_rules WHERE user_id = %s ORDER BY created_at DESC",
        (user_id,),
    )
    return [
        {
            "id": r["id"],
            "user_id": r["user_id"],
            "rule_name": r["rule_name"],
            "trigger_metric": r["trigger_metric"],
            "trigger_operator": r["trigger_operator"],
            "trigger_value": _from_jsonb(r.get("trigger_value"), default=None),
            "action": r["action"],
            "is_enabled": r.get("is_enabled", True),
            "created_at": r["created_at"].isoformat() if r.get("created_at") else None,
        }
        for r in rows
    ]


def delete_rule(user_id: str, rule_id: str) -> bool:
    """删除规则 — UUID 格式校验后物理删除"""
    if not _is_uuid_like(rule_id):
        return False
    from app.infrastructure.db.database import get_db
    db = get_db()
    try:
        conn = db.get_conn()
        cur = conn.cursor()
        cur.execute(
            "DELETE FROM mood_stress_rules WHERE user_id = %s AND id = %s",
            (user_id, rule_id),
        )
        rowcount = cur.rowcount
        conn.commit()
        cur.close()
        db.put_conn(conn)
        return rowcount > 0
    except Exception as exc:  # noqa: BLE001
        logger.debug("delete_rule 失败: %s", exc)
        return False


# ──────────────────────────────────────────────
# 清理（可选 — 由 scheduler 调用）
# ──────────────────────────────────────────────

def purge_old_records(user_id: str, retention_days: int) -> int:
    """按 prefs.data_retention_days 清理旧记录 — 返回清理数"""
    from app.infrastructure.db.database import get_db
    db = get_db()
    try:
        conn = db.get_conn()
        cur = conn.cursor()
        cur.execute(
            "DELETE FROM emotion_records "
            "WHERE user_id = %s AND created_at < NOW() - (%s || ' days')::INTERVAL",
            (user_id, str(retention_days)),
        )
        rowcount = cur.rowcount
        conn.commit()
        cur.close()
        db.put_conn(conn)
        return rowcount
    except Exception as exc:  # noqa: BLE001
        logger.debug("purge_old_records 失败: %s", exc)
        return 0
