"""秘书提案持久化 — 基于 PostgreSQL 的 CRUD

设计:
  - secretary_proposals 表存储所有提案
  - 每条提案含完整决策链日志
  - 支持 status 切换: pending → accepted / dismissed / snoozed / expired
"""

from __future__ import annotations

import json
import logging
import time
from datetime import datetime, timezone
from typing import Any

from ..models import Proposal, SecretaryPrefs

logger = logging.getLogger(__name__)


class ProposalStore:
    """提案持久化存储"""

    def __init__(self):
        self._db = None

    def _get_db(self):
        if self._db is None:
            from app.db.database import get_db
            self._db = get_db()
        return self._db

    def save_proposal(self, proposal: Proposal, user_id: str, session_id: str | None = None) -> str:
        """保存提案到数据库"""
        db = self._get_db()
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc)

        # 生成决策链日志
        decision_log = {
            "generated_by": proposal.generated_by,
            "insight_source": proposal.insight_source,
            "analysis_type": proposal.action_type,
            "generated_at": now.isoformat(),
        }

        db.execute(
            """INSERT INTO secretary_proposals
               (user_id, proposal, status, decision_log, session_id, expires_at, created_at)
               VALUES (%s, %s, 'pending', %s, %s, %s, %s)""",
            (
                user_id,
                json.dumps(proposal.model_dump(), ensure_ascii=False),
                json.dumps(decision_log, ensure_ascii=False),
                session_id,
                datetime.fromtimestamp(proposal.expires_at, tz=timezone.utc) if proposal.expires_at else None,
                now,
            ),
        )
        return proposal.id

    def update_status(
        self,
        proposal_id: str,
        status: str,
        user_id: str,
        extra_log: dict | None = None,
    ) -> bool:
        """更新提案状态"""
        db = self._get_db()
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc)

        # 构建时间戳字段
        ts_field = {
            "accepted": "accepted_at",
            "dismissed": "dismissed_at",
        }.get(status)

        if ts_field:
            db.execute(
                f"UPDATE secretary_proposals SET status = %s, {ts_field} = %s, decision_log = decision_log || %s::jsonb WHERE id = %s AND user_id = %s",
                (status, now, json.dumps(extra_log or {}), proposal_id, user_id),
            )
        else:
            db.execute(
                "UPDATE secretary_proposals SET status = %s WHERE id = %s AND user_id = %s",
                (status, proposal_id, user_id),
            )
        return db.conn.status == 0  # 粗略判断

    def get_pending_proposals(self, user_id: str, limit: int = 20) -> list[Proposal]:
        """获取待处理的提案"""
        db = self._get_db()
        rows = db.fetchall(
            """SELECT proposal, id, status, created_at
               FROM secretary_proposals
               WHERE user_id = %s AND status = 'pending'
               ORDER BY proposal->>'priority' DESC, created_at DESC
               LIMIT %s""",
            (user_id, limit),
        )
        return [Proposal(**r["proposal"]) for r in rows]

    def get_history(
        self, user_id: str, days: int = 7, limit: int = 50,
    ) -> list[dict[str, Any]]:
        """获取提案历史"""
        db = self._get_db()
        from datetime import datetime, timezone, timedelta
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)

        rows = db.fetchall(
            """SELECT id, proposal, status, decision_log, created_at, accepted_at, dismissed_at
               FROM secretary_proposals
               WHERE user_id = %s AND created_at >= %s
               ORDER BY created_at DESC
               LIMIT %s""",
            (user_id, cutoff, limit),
        )
        return [
            {
                "id": r["id"],
                "proposal": r["proposal"],
                "status": r["status"],
                "created_at": r["created_at"].isoformat() if hasattr(r["created_at"], 'isoformat') else str(r["created_at"]),
                "accepted_at": r.get("accepted_at"),
                "dismissed_at": r.get("dismissed_at"),
                "decision_log": r.get("decision_log"),
            }
            for r in rows
        ]

    def expire_old_proposals(self, user_id: str) -> int:
        """将过期提案标记为 expired"""
        db = self._get_db()
        db.execute(
            """UPDATE secretary_proposals
               SET status = 'expired'
               WHERE user_id = %s AND status = 'pending'
               AND expires_at IS NOT NULL AND expires_at < NOW()""",
            (user_id,),
        )
        return db.conn.status

    def get_stats(self, user_id: str) -> dict[str, int]:
        """获取提案统计"""
        db = self._get_db()
        row = db.fetchone(
            """SELECT
                COUNT(*) FILTER (WHERE status = 'pending') as pending,
                COUNT(*) FILTER (WHERE status = 'accepted') as accepted,
                COUNT(*) FILTER (WHERE status = 'dismissed') as dismissed
               FROM secretary_proposals WHERE user_id = %s""",
            (user_id,),
        )
        return {
            "pending": row["pending"] if row else 0,
            "accepted": row["accepted"] if row else 0,
            "dismissed": row["dismissed"] if row else 0,
        }
