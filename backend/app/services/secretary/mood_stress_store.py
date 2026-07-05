"""
MoodStress 模块 — 数据访问层

封装以下表的 CRUD：
  - emotion_records (扩展自 ADR 0005 前的 emotion 缓存)
  - mood_stress_prefs
  - mood_stress_intervention_logs
  - mood_stress_rules
  - behavior_signals

设计原则：
  - 手动记录 (source='manual') 优先于自动检测 (source='auto')
  - 行为信号只读消费, 不写回学习数据
  - 干预工具不进入知识图谱, 仅本地记录
"""
from __future__ import annotations

import json
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Iterable

from app.infrastructure.db.database import get_db

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────
# 偏好默认值
# ──────────────────────────────────────────────

MOOD_STRESS_DEFAULT_PREFS: dict[str, Any] = {
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
    "auto_collect_voice_features": False,   # 语音特征默认关闭
    "output_to_planning": True,
    "output_to_conversation": True,
    "output_to_language_room": True,
    "knowledge_breathing_excluded_node_ids": [],
    "environment_theme": "default",
    "environment_sound": "none",
    "planning_rules": {},
}


@dataclass
class EmotionRecordRow:
    """emotion_records 行的 Python 表示"""
    id: str
    user_id: str
    source: str  # manual / auto
    emotion_tags: list[str]
    pressure_score: int | None
    energy_score: int | None
    text_note: str | None
    related_event_ids: list[str]
    created_at: datetime

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "user_id": self.user_id,
            "source": self.source,
            "emotion_tags": self.emotion_tags,
            "pressure_score": self.pressure_score,
            "energy_score": self.energy_score,
            "text_note": self.text_note,
            "related_event_ids": self.related_event_ids,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


@dataclass
class InterventionLogRow:
    id: str
    user_id: str
    intervention_type: str
    duration_seconds: int | None
    trigger_event: str | None
    notes: str | None
    created_at: datetime

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "user_id": self.user_id,
            "intervention_type": self.intervention_type,
            "duration_seconds": self.duration_seconds,
            "trigger_event": self.trigger_event,
            "notes": self.notes,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


@dataclass
class BehaviorSignalRow:
    id: str
    user_id: str
    signal_type: str
    signal_data: dict
    severity: int
    is_read: bool
    created_at: datetime

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "user_id": self.user_id,
            "signal_type": self.signal_type,
            "signal_data": self.signal_data,
            "severity": self.severity,
            "is_read": self.is_read,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


# ──────────────────────────────────────────────
# 仓库
# ──────────────────────────────────────────────

class MoodStressStore:
    """情绪/压力/能量与干预工具的数据仓储"""

    def __init__(self) -> None:
        self._db = None

    def _get_db(self):
        if self._db is None:
            self._db = get_db()
        return self._db

    # ── 偏好 ──

    def get_prefs(self, user_id: str) -> dict:
        """获取偏好（缺失则返回默认）"""
        db = self._get_db()
        row = db.fetchone(
            "SELECT * FROM mood_stress_prefs WHERE user_id = %s",
            (user_id,),
        )
        if not row:
            return dict(MOOD_STRESS_DEFAULT_PREFS)

        merged = dict(MOOD_STRESS_DEFAULT_PREFS)
        for k, v in row.items():
            if k in ("created_at", "updated_at"):
                continue
            if k in ("knowledge_breathing_excluded_node_ids", "planning_rules") and v is not None:
                merged[k] = v if isinstance(v, (list, dict)) else json.loads(v)
            else:
                merged[k] = v
        return merged

    def upsert_prefs(self, user_id: str, prefs: dict) -> dict:
        """更新偏好（增量覆盖）"""
        db = self._get_db()
        current = self.get_prefs(user_id)
        current.update(prefs)
        now = datetime.now(timezone.utc)

        # 序列化 JSONB 字段
        excluded = current.get("knowledge_breathing_excluded_node_ids") or []
        planning_rules = current.get("planning_rules") or {}

        db.execute(
            """
            INSERT INTO mood_stress_prefs (
                user_id, reminder_enabled, reminder_frequency, reminder_time,
                data_retention_days,
                auto_collect_task_switch, auto_collect_stay_duration,
                auto_collect_error_rate, auto_collect_undo,
                auto_collect_session_anomaly, auto_collect_flashcard_failure,
                auto_collect_voice_features,
                output_to_planning, output_to_conversation, output_to_language_room,
                knowledge_breathing_excluded_node_ids,
                environment_theme, environment_sound, planning_rules,
                created_at, updated_at
            ) VALUES (
                %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s, %s, %s,
                %s, %s, %s,
                %s, %s, %s, %s,
                NOW(), NOW()
            )
            ON CONFLICT (user_id) DO UPDATE SET
                reminder_enabled = EXCLUDED.reminder_enabled,
                reminder_frequency = EXCLUDED.reminder_frequency,
                reminder_time = EXCLUDED.reminder_time,
                data_retention_days = EXCLUDED.data_retention_days,
                auto_collect_task_switch = EXCLUDED.auto_collect_task_switch,
                auto_collect_stay_duration = EXCLUDED.auto_collect_stay_duration,
                auto_collect_error_rate = EXCLUDED.auto_collect_error_rate,
                auto_collect_undo = EXCLUDED.auto_collect_undo,
                auto_collect_session_anomaly = EXCLUDED.auto_collect_session_anomaly,
                auto_collect_flashcard_failure = EXCLUDED.auto_collect_flashcard_failure,
                auto_collect_voice_features = EXCLUDED.auto_collect_voice_features,
                output_to_planning = EXCLUDED.output_to_planning,
                output_to_conversation = EXCLUDED.output_to_conversation,
                output_to_language_room = EXCLUDED.output_to_language_room,
                knowledge_breathing_excluded_node_ids = EXCLUDED.knowledge_breathing_excluded_node_ids,
                environment_theme = EXCLUDED.environment_theme,
                environment_sound = EXCLUDED.environment_sound,
                planning_rules = EXCLUDED.planning_rules,
                updated_at = NOW()
            """,
            (
                user_id,
                current.get("reminder_enabled", False),
                current.get("reminder_frequency"),
                current.get("reminder_time"),
                int(current.get("data_retention_days", 90)),
                current.get("auto_collect_task_switch", True),
                current.get("auto_collect_stay_duration", True),
                current.get("auto_collect_error_rate", True),
                current.get("auto_collect_undo", True),
                current.get("auto_collect_session_anomaly", True),
                current.get("auto_collect_flashcard_failure", True),
                current.get("auto_collect_voice_features", False),
                current.get("output_to_planning", True),
                current.get("output_to_conversation", True),
                current.get("output_to_language_room", True),
                json.dumps(excluded, ensure_ascii=False),
                current.get("environment_theme", "default"),
                current.get("environment_sound", "none"),
                json.dumps(planning_rules, ensure_ascii=False),
            ),
        )
        return self.get_prefs(user_id)

    # ── 情绪记录 ──

    def insert_emotion_record(
        self,
        user_id: str,
        source: str,
        emotion_tags: list[str],
        pressure_score: int | None = None,
        energy_score: int | None = None,
        text_note: str | None = None,
        related_event_ids: list[str] | None = None,
    ) -> EmotionRecordRow:
        """写入心情/压力/能量记录"""
        assert source in ("manual", "auto"), f"非法 source: {source}"
        if pressure_score is not None:
            assert 1 <= pressure_score <= 10, "pressure_score 必须在 1-10"
        if energy_score is not None:
            assert 1 <= energy_score <= 10, "energy_score 必须在 1-10"

        db = self._get_db()
        record_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc)

        db.execute(
            """
            INSERT INTO emotion_records
                (id, user_id, source, emotion_tags,
                 pressure_score, energy_score,
                 text_note, related_event_ids, created_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                record_id,
                user_id,
                source,
                json.dumps(emotion_tags or [], ensure_ascii=False),
                pressure_score,
                energy_score,
                text_note,
                json.dumps(related_event_ids or [], ensure_ascii=False),
                now,
            ),
        )
        return EmotionRecordRow(
            id=record_id,
            user_id=user_id,
            source=source,
            emotion_tags=emotion_tags or [],
            pressure_score=pressure_score,
            energy_score=energy_score,
            text_note=text_note,
            related_event_ids=related_event_ids or [],
            created_at=now,
        )

    def list_emotion_records(
        self,
        user_id: str,
        source: str | None = None,
        days: int = 30,
        limit: int = 200,
    ) -> list[EmotionRecordRow]:
        """获取情绪记录（默认按时间倒序，手动优先展示）"""
        db = self._get_db()
        params: list[Any] = [user_id]
        where = ["user_id = %s"]
        if source:
            where.append("source = %s")
            params.append(source)
        params.append(days)
        params.append(limit)

        rows = db.fetchall(
            f"""
            SELECT id, user_id, source, emotion_tags, pressure_score,
                   energy_score, text_note, related_event_ids, created_at
            FROM emotion_records
            WHERE {' AND '.join(where)}
              AND created_at > NOW() - INTERVAL '%s days'
            ORDER BY created_at DESC
            LIMIT %s
            """,
            tuple(params),
        )
        return [self._row_to_emotion(r) for r in (rows or [])]

    def latest_manual_record(self, user_id: str) -> EmotionRecordRow | None:
        """最近一次手动记录（仪表盘顶部展示）"""
        db = self._get_db()
        row = db.fetchone(
            """
            SELECT id, user_id, source, emotion_tags, pressure_score,
                   energy_score, text_note, related_event_ids, created_at
            FROM emotion_records
            WHERE user_id = %s AND source = 'manual'
            ORDER BY created_at DESC LIMIT 1
            """,
            (user_id,),
        )
        return self._row_to_emotion(row) if row else None

    def emotion_stats(
        self,
        user_id: str,
        days: int = 7,
    ) -> dict:
        """周期统计：压力均值、能量均值、心情分布"""
        db = self._get_db()
        rows = db.fetchall(
            """
            SELECT source, emotion_tags, pressure_score, energy_score
            FROM emotion_records
            WHERE user_id = %s
              AND created_at > NOW() - INTERVAL '%s days'
            """,
            (user_id, days),
        )
        if not rows:
            return {
                "days": days,
                "total": 0,
                "manual_total": 0,
                "auto_total": 0,
                "avg_pressure": None,
                "avg_energy": None,
                "tag_distribution": {},
            }

        manual_total = sum(1 for r in rows if r["source"] == "manual")
        auto_total = sum(1 for r in rows if r["source"] == "auto")
        pressures = [r["pressure_score"] for r in rows if r["pressure_score"] is not None]
        energies = [r["energy_score"] for r in rows if r["energy_score"] is not None]

        tag_dist: dict[str, int] = {}
        for r in rows:
            tags = r["emotion_tags"]
            if isinstance(tags, str):
                try:
                    tags = json.loads(tags)
                except Exception:
                    tags = []
            for t in (tags or []):
                tag_dist[t] = tag_dist.get(t, 0) + 1

        return {
            "days": days,
            "total": len(rows),
            "manual_total": manual_total,
            "auto_total": auto_total,
            "avg_pressure": round(sum(pressures) / len(pressures), 2) if pressures else None,
            "avg_energy": round(sum(energies) / len(energies), 2) if energies else None,
            "tag_distribution": tag_dist,
        }

    def delete_emotion_record(self, user_id: str, record_id: str) -> bool:
        # 校验 UUID 格式以避免 PG "invalid input syntax for type uuid" 错误
        import re
        if not isinstance(record_id, str) or not re.match(
            r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$",
            record_id,
        ):
            return False
        db = self._get_db()
        cur = db.get_conn().cursor()
        try:
            cur.execute(
                "DELETE FROM emotion_records WHERE id = %s AND user_id = %s",
                (record_id, user_id),
            )
            return cur.rowcount > 0
        finally:
            cur.connection.commit()
            cur.close()
            db.put_conn(cur.connection)

    def purge_old_records(self, user_id: str, retention_days: int) -> int:
        """按数据保留期清理过期记录"""
        db = self._get_db()
        cur = db.get_conn().cursor()
        try:
            cur.execute(
                """
                DELETE FROM emotion_records
                WHERE user_id = %s
                  AND created_at < NOW() - INTERVAL '%s days'
                """,
                (user_id, retention_days),
            )
            count = cur.rowcount
            return count
        finally:
            cur.connection.commit()
            cur.close()
            db.put_conn(cur.connection)

    # ── 干预工具 ──

    def log_intervention(
        self,
        user_id: str,
        intervention_type: str,
        duration_seconds: int | None = None,
        trigger_event: str | None = None,
        notes: str | None = None,
    ) -> InterventionLogRow:
        assert intervention_type in {
            "breathing", "knowledge_breathing",
            "cognitive_reappraisal", "environment",
        }
        db = self._get_db()
        log_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc)
        db.execute(
            """
            INSERT INTO mood_stress_intervention_logs
                (id, user_id, intervention_type,
                 duration_seconds, trigger_event, notes, created_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            """,
            (
                log_id, user_id, intervention_type,
                duration_seconds, trigger_event, notes, now,
            ),
        )
        return InterventionLogRow(
            id=log_id,
            user_id=user_id,
            intervention_type=intervention_type,
            duration_seconds=duration_seconds,
            trigger_event=trigger_event,
            notes=notes,
            created_at=now,
        )

    def list_interventions(
        self,
        user_id: str,
        days: int = 30,
        limit: int = 100,
    ) -> list[InterventionLogRow]:
        db = self._get_db()
        rows = db.fetchall(
            """
            SELECT id, user_id, intervention_type, duration_seconds,
                   trigger_event, notes, created_at
            FROM mood_stress_intervention_logs
            WHERE user_id = %s
              AND created_at > NOW() - INTERVAL '%s days'
            ORDER BY created_at DESC LIMIT %s
            """,
            (user_id, days, limit),
        )
        result: list[InterventionLogRow] = []
        for r in (rows or []):
            result.append(InterventionLogRow(
                id=r["id"],
                user_id=r["user_id"],
                intervention_type=r["intervention_type"],
                duration_seconds=r["duration_seconds"],
                trigger_event=r["trigger_event"],
                notes=r["notes"],
                created_at=r["created_at"],
            ))
        return result

    # ── 行为信号 ──

    def log_behavior_signal(
        self,
        user_id: str,
        signal_type: str,
        signal_data: dict,
        severity: int = 1,
    ) -> BehaviorSignalRow:
        """写入行为信号（仅提示用户，不修改学习数据）"""
        assert signal_type in {
            "task_switch", "stay_duration", "error_rate",
            "undo", "session_anomaly", "flashcard_failure", "voice_features",
        }
        assert 1 <= severity <= 3
        db = self._get_db()
        sig_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc)
        db.execute(
            """
            INSERT INTO behavior_signals
                (id, user_id, signal_type, signal_data, severity, is_read, created_at)
            VALUES (%s, %s, %s, %s, %s, FALSE, %s)
            """,
            (
                sig_id, user_id, signal_type,
                json.dumps(signal_data, ensure_ascii=False),
                severity, now,
            ),
        )
        return BehaviorSignalRow(
            id=sig_id, user_id=user_id, signal_type=signal_type,
            signal_data=signal_data, severity=severity, is_read=False, created_at=now,
        )

    def list_unread_signals(
        self,
        user_id: str,
        limit: int = 50,
    ) -> list[BehaviorSignalRow]:
        db = self._get_db()
        rows = db.fetchall(
            """
            SELECT id, user_id, signal_type, signal_data, severity, is_read, created_at
            FROM behavior_signals
            WHERE user_id = %s AND is_read = FALSE
            ORDER BY created_at DESC LIMIT %s
            """,
            (user_id, limit),
        )
        return [self._row_to_signal(r) for r in (rows or [])]

    def mark_signals_read(self, user_id: str, ids: Iterable[str]) -> int:
        ids = list(ids)
        if not ids:
            return 0
        # 仅保留合法 UUID 字符串, 避免 "invalid input syntax for type uuid" 错误
        import re
        uuid_re = re.compile(r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$")
        valid_ids = [i for i in ids if isinstance(i, str) and uuid_re.match(i)]
        if not valid_ids:
            return 0
        db = self._get_db()
        cur = db.get_conn().cursor()
        try:
            cur.execute(
                "UPDATE behavior_signals SET is_read = TRUE "
                "WHERE user_id = %s AND id = ANY(%s::uuid[])",
                (user_id, valid_ids),
            )
            return cur.rowcount
        finally:
            cur.connection.commit()
            cur.close()
            db.put_conn(cur.connection)

    # ── 规则 ──

    def add_rule(
        self,
        user_id: str,
        rule_name: str,
        trigger_metric: str,
        trigger_operator: str,
        trigger_value: Any,
        action: str,
    ) -> str:
        db = self._get_db()
        rule_id = str(uuid.uuid4())
        db.execute(
            """
            INSERT INTO mood_stress_rules
                (id, user_id, rule_name, trigger_metric, trigger_operator,
                 trigger_value, action, is_enabled)
            VALUES (%s, %s, %s, %s, %s, %s, %s, TRUE)
            """,
            (
                rule_id, user_id, rule_name, trigger_metric, trigger_operator,
                json.dumps(trigger_value, ensure_ascii=False), action,
            ),
        )
        return rule_id

    def list_rules(self, user_id: str, enabled_only: bool = False) -> list[dict]:
        db = self._get_db()
        sql = """
            SELECT id, user_id, rule_name, trigger_metric, trigger_operator,
                   trigger_value, action, is_enabled, created_at
            FROM mood_stress_rules
            WHERE user_id = %s
        """
        if enabled_only:
            sql += " AND is_enabled = TRUE"
        sql += " ORDER BY created_at DESC"
        rows = db.fetchall(sql, (user_id,)) or []
        result = []
        for r in rows:
            tv = r["trigger_value"]
            if isinstance(tv, str):
                try:
                    tv = json.loads(tv)
                except Exception:
                    tv = tv
            result.append({
                "id": r["id"],
                "rule_name": r["rule_name"],
                "trigger_metric": r["trigger_metric"],
                "trigger_operator": r["trigger_operator"],
                "trigger_value": tv,
                "action": r["action"],
                "is_enabled": r["is_enabled"],
                "created_at": r["created_at"].isoformat() if r["created_at"] else None,
            })
        return result

    def delete_rule(self, user_id: str, rule_id: str) -> bool:
        # 校验 UUID 格式以避免 PG "invalid input syntax for type uuid" 错误
        import re
        if not isinstance(rule_id, str) or not re.match(
            r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$",
            rule_id,
        ):
            return False
        db = self._get_db()
        cur = db.get_conn().cursor()
        try:
            cur.execute(
                "DELETE FROM mood_stress_rules WHERE id = %s AND user_id = %s",
                (rule_id, user_id),
            )
            return cur.rowcount > 0
        finally:
            cur.connection.commit()
            cur.close()
            db.put_conn(cur.connection)

    # ── 工具方法 ──

    @staticmethod
    def _row_to_emotion(row: dict) -> EmotionRecordRow:
        tags = row.get("emotion_tags")
        if isinstance(tags, str):
            try:
                tags = json.loads(tags)
            except Exception:
                tags = []
        related = row.get("related_event_ids")
        if isinstance(related, str):
            try:
                related = json.loads(related)
            except Exception:
                related = []
        return EmotionRecordRow(
            id=row["id"],
            user_id=row["user_id"],
            source=row["source"],
            emotion_tags=tags or [],
            pressure_score=row.get("pressure_score"),
            energy_score=row.get("energy_score"),
            text_note=row.get("text_note"),
            related_event_ids=related or [],
            created_at=row.get("created_at"),
        )

    @staticmethod
    def _row_to_signal(row: dict) -> BehaviorSignalRow:
        data = row.get("signal_data")
        if isinstance(data, str):
            try:
                data = json.loads(data)
            except Exception:
                data = {}
        return BehaviorSignalRow(
            id=row["id"],
            user_id=row["user_id"],
            signal_type=row["signal_type"],
            signal_data=data or {},
            severity=row.get("severity", 1),
            is_read=row.get("is_read", False),
            created_at=row.get("created_at"),
        )


# 全局实例
mood_stress_store = MoodStressStore()
