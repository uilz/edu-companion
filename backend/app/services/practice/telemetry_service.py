"""答题遥测服务 — Phase 3

职责：
- 接收前端聚合后的遥测数据，存入 answer_telemetry 表
- 发布 PracticeAnswerBehaviorRecorded 事件（轻量派生指标）

原始事件序列（hover/select/input 等）体积大，直接落库；
事件总线只携带 telemetry_id 与派生指标，供认知中心/秘书消费。
"""
from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from app.infrastructure.db.database import get_db
from app.infrastructure.event_bus_utils import publish_event_safe
from shared.events import PracticeAnswerBehaviorRecorded

logger = logging.getLogger(__name__)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _uid(prefix: str = "tel") -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


def _json(v: Any) -> str:
    return json.dumps(v, ensure_ascii=False, default=str)


def _parse_json(raw: Any, default: Any = None) -> Any:
    if raw is None or raw == "" or raw == {} or raw == []:
        return default if default is not None else {}
    if isinstance(raw, (dict, list)):
        return raw
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return default if default is not None else {}


def save_telemetry(
    user_id: str,
    telemetry_id: str,
    session_id: str,
    question_id: str,
    attempt_id: str,
    raw_events: list[dict],
    derived: dict[str, Any],
) -> dict:
    """保存遥测数据并发布 PracticeAnswerBehaviorRecorded 事件。

    Args:
        telemetry_id: 前端生成的唯一遥测 ID（幂等键）
        derived: 派生指标，如 time_on_question_ms / hesitation_ms / answer_change_count 等
    """
    if not telemetry_id or not question_id or not attempt_id:
        raise ValueError("telemetry_id / question_id / attempt_id 不能为空")

    db = get_db()
    now = _now()
    record_id = _uid("at")

    # 幂等：若 telemetry_id 已存在，更新原始事件与派生指标
    existing = db.fetchone(
        "SELECT id FROM answer_telemetry WHERE telemetry_id = %s",
        (telemetry_id,),
    )
    if existing:
        db.execute(
            """UPDATE answer_telemetry
               SET raw_events = %s, derived = %s, session_id = %s, question_id = %s, attempt_id = %s
               WHERE telemetry_id = %s""",
            (_json(raw_events), _json(derived), session_id, question_id, attempt_id, telemetry_id),
        )
        record_id = existing["id"]
    else:
        db.execute(
            """INSERT INTO answer_telemetry
               (id, user_id, telemetry_id, session_id, question_id, attempt_id, raw_events, derived, created_at)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)""",
            (record_id, user_id, telemetry_id, session_id, question_id, attempt_id,
             _json(raw_events), _json(derived), now),
        )

    publish_event_safe(PracticeAnswerBehaviorRecorded(
        user_id=user_id,
        telemetry_id=telemetry_id,
        session_id=session_id,
        question_id=question_id,
        attempt_id=attempt_id,
        time_on_question_ms=int(derived.get("time_on_question_ms", 0)),
        hesitation_ms=int(derived.get("hesitation_ms", 0)),
        answer_change_count=int(derived.get("answer_change_count", 0)),
        total_hover_ms=int(derived.get("total_hover_ms", 0)),
        avg_text_pause_ms=float(derived.get("avg_text_pause_ms", 0.0)),
        hint_count=int(derived.get("hint_count", 0)),
        recorded_at=now,
    ))

    return {
        "id": record_id,
        "telemetry_id": telemetry_id,
        "attempt_id": attempt_id,
        "question_id": question_id,
        "derived": derived,
    }


def get_telemetry_by_attempt(attempt_id: str) -> dict | None:
    db = get_db()
    row = db.fetchone(
        "SELECT * FROM answer_telemetry WHERE attempt_id = %s",
        (attempt_id,),
    )
    if not row:
        return None
    out = dict(row)
    out["raw_events"] = _parse_json(out.get("raw_events"), [])
    out["derived"] = _parse_json(out.get("derived"), {})
    return out
