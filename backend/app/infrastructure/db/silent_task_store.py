"""静默后台任务持久化 — 基于 PostgreSQL

设计:
  - secretary_silent_tasks 表存储所有静默任务
  - 幂等创建：同用户 + 同 task_type + 同指纹的 pending/running 任务不重复插入
  - 结果引用 (result_ref) 用于让消费者定位预计算产物
"""

from __future__ import annotations

import json
import logging
from typing import Any

from app.domain.secretary.models import SilentTask

logger = logging.getLogger(__name__)


class SilentTaskStore:
    """静默任务持久化存储"""

    def __init__(self) -> None:
        self._db = None

    def _get_db(self):
        if self._db is None:
            from app.infrastructure.db.database import get_db
            self._db = get_db()
        return self._db

    @staticmethod
    def _ensure_table() -> None:
        from app.infrastructure.db.secretary_schema import _ensure_tables
        _ensure_tables()

    def _fingerprint(self, task_type: str, payload: dict) -> str:
        """生成任务指纹，用于去重"""
        stable = {"task_type": task_type}
        # 选取参与去重的关键字段
        for key in ("node_id", "kp_id", "scope", "date", "material_id"):
            if key in payload:
                stable[key] = payload[key]
        return json.dumps(stable, sort_keys=True, ensure_ascii=False)

    def save_task(self, task: SilentTask) -> str:
        """保存任务（自动去重），返回任务 ID"""
        db = self._get_db()
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc)

        fingerprint = self._fingerprint(task.task_type, task.payload or {})

        # 幂等去重：同用户+同类型+同指纹 的 pending/running 任务不重复创建
        try:
            existing = db.fetchone(
                "SELECT id FROM secretary_silent_tasks "
                "WHERE user_id = %s AND task_type = %s AND status IN ('pending', 'running') "
                "AND metadata->>'fingerprint' = %s "
                "LIMIT 1",
                (task.user_id, task.task_type, fingerprint),
            )
            if existing:
                logger.debug("静默任务去重: %s %s", task.task_type, fingerprint)
                return existing["id"]
        except Exception:
            pass

        metadata = {"fingerprint": fingerprint}
        ready_at = None
        if task.ready_at:
            ready_at = datetime.fromtimestamp(task.ready_at, tz=timezone.utc)

        try:
            db.execute(
                """INSERT INTO secretary_silent_tasks
                   (id, user_id, task_type, payload, status, result_ref, priority,
                    created_at, ready_at, updated_at, metadata)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                (
                    task.id,
                    task.user_id,
                    task.task_type,
                    json.dumps(task.payload or {}, ensure_ascii=False),
                    task.status or "pending",
                    task.result_ref or "",
                    task.priority or 3,
                    now,
                    ready_at,
                    now,
                    json.dumps(metadata, ensure_ascii=False),
                ),
            )
        except Exception as e:
            logger.warning("静默任务写入失败: %s", e)
            raise
        return task.id

    def update_status(
        self,
        task_id: str,
        status: str,
        result_ref: str | None = None,
        result_payload: dict | None = None,
    ) -> bool:
        """更新任务状态，返回是否真实更新"""
        db = self._get_db()
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc)

        extra_log = {
            "status_change": {"to": status, "at": now.isoformat()},
        }
        if result_payload:
            extra_log["result"] = result_payload

        ready_at = now if status == "ready" else None
        consumed_at = now if status == "consumed" else None

        fields = ["status = %s", "updated_at = %s", "metadata = COALESCE(metadata, '{}'::jsonb) || %s::jsonb"]
        params: list[Any] = [status, now, json.dumps(extra_log, ensure_ascii=False)]

        if result_ref is not None:
            fields.append("result_ref = %s")
            params.append(result_ref)
        if ready_at is not None:
            fields.append("ready_at = %s")
            params.append(ready_at)
        if consumed_at is not None:
            fields.append("consumed_at = %s")
            params.append(consumed_at)

        params.append(task_id)
        sql = f"UPDATE secretary_silent_tasks SET {', '.join(fields)} WHERE id = %s"

        cur = db.get_conn().cursor()
        try:
            cur.execute(sql, tuple(params))
            updated = cur.rowcount > 0
        finally:
            cur.connection.commit()
            cur.close()
            db.put_conn(cur.connection)
        return updated

    def get_task(self, task_id: str, user_id: str | None = None) -> SilentTask | None:
        """获取单个任务"""
        db = self._get_db()
        sql = "SELECT * FROM secretary_silent_tasks WHERE id = %s"
        params: list[Any] = [task_id]
        if user_id:
            sql += " AND user_id = %s"
            params.append(user_id)
        row = db.fetchone(sql, tuple(params))
        return self._row_to_task(row) if row else None

    def list_tasks(
        self,
        user_id: str,
        status: str | None = None,
        task_type: str | None = None,
        limit: int = 50,
    ) -> list[SilentTask]:
        """获取任务列表"""
        db = self._get_db()
        conditions = ["user_id = %s"]
        params: list[Any] = [user_id]
        if status:
            conditions.append("status = %s")
            params.append(status)
        if task_type:
            conditions.append("task_type = %s")
            params.append(task_type)

        where_clause = " AND ".join(conditions)
        sql = (
            f"SELECT * FROM secretary_silent_tasks WHERE {where_clause} "
            f"ORDER BY priority ASC, created_at ASC LIMIT %s"
        )
        params.append(limit)
        rows = db.fetchall(sql, tuple(params))
        return [t for t in (self._row_to_task(r) for r in rows) if t is not None]

    def claim_next_pending(
        self,
        user_id: str,
        task_type: str | None = None,
    ) -> SilentTask | None:
        """原子地认领下一个待处理任务"""
        db = self._get_db()
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc)

        conditions = ["user_id = %s", "status = 'pending'"]
        params: list[Any] = [user_id]
        if task_type:
            conditions.append("task_type = %s")
            params.append(task_type)

        where_clause = " AND ".join(conditions)
        sql = (
            f"UPDATE secretary_silent_tasks SET status = 'running', updated_at = %s "
            f"WHERE id = ("
            f"  SELECT id FROM secretary_silent_tasks "
            f"  WHERE {where_clause} "
            f"  ORDER BY priority ASC, created_at ASC LIMIT 1 "
            f"  FOR UPDATE SKIP LOCKED"
            f") RETURNING *"
        )
        params.insert(0, now)

        row = db.fetchone(sql, tuple(params))
        return self._row_to_task(row) if row else None

    def _row_to_task(self, row: dict[str, Any] | None) -> SilentTask | None:
        if not row:
            return None
        try:
            payload = row.get("payload") or {}
            if isinstance(payload, str):
                payload = json.loads(payload)
            ready_at = row.get("ready_at")
            consumed_at = row.get("consumed_at")
            created_at = row.get("created_at")
            return SilentTask(
                id=row["id"],
                user_id=row["user_id"],
                task_type=row["task_type"],
                payload=payload,
                status=row.get("status", "pending"),
                result_ref=row.get("result_ref", "") or "",
                priority=row.get("priority", 3) or 3,
                created_at=created_at.timestamp() if hasattr(created_at, "timestamp") else float(created_at or 0),
                ready_at=ready_at.timestamp() if hasattr(ready_at, "timestamp") else (float(ready_at) if ready_at else None),
                consumed_at=consumed_at.timestamp() if hasattr(consumed_at, "timestamp") else (float(consumed_at) if consumed_at else None),
            )
        except Exception as e:
            logger.debug("解析静默任务行失败: %s", e)
            return None
