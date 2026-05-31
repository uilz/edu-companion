"""秘书提案持久化 — 基于 PostgreSQL 的 CRUD

设计:
  - secretary_proposals 表存储所有提案
  - 每条提案含完整决策链日志
  - 支持 status 切换: pending → accepted / dismissed / snoozed / expired
"""

from __future__ import annotations

import json
import logging
from typing import Any

from .models import Proposal

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
        """保存提案到数据库（自动去重：同用户+同标题+同来源 的 pending 提案不重复插入）"""
        db = self._get_db()
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc)

        # 去重检查：已有同用户+同标题+同来源的 pending 提案 → 跳过
        try:
            existing = db.fetchone(
                "SELECT id FROM secretary_proposals "
                "WHERE user_id = %s AND title = %s "
                "AND generated_by = %s AND status = 'pending' "
                "LIMIT 1",
                (user_id, proposal.title, proposal.generated_by or ""),
            )
            if existing:
                logger.debug("跳过去重提案: [%s] %s", proposal.generated_by, proposal.title)
                return existing["id"]
        except Exception:
            pass  # 查重失败不回退，继续写入

        # 生成决策链日志（存入 metadata JSONB）
        decision_log = {
            "generated_by": proposal.generated_by or "",
            "insight_source": proposal.insight_source or "",
            "analysis_type": proposal.action_type,
            "generated_at": now.isoformat(),
        }
        # 如果有指纹标记，也存入 metadata
        if proposal.payload and "_fingerprint" in proposal.payload:
            decision_log["fingerprint"] = proposal.payload.pop("_fingerprint")

        try:
            db.execute(
                """INSERT INTO secretary_proposals
                   (id, user_id, session_id, emoji, title, description, action_type, payload,
                    priority, generated_by, overrideable, status, metadata, expires_at, created_at)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'pending', %s, %s, %s)""",
                (
                    proposal.id,
                    user_id,
                    session_id or "",
                    proposal.emoji or "",
                    proposal.title,
                    proposal.description or "",
                    proposal.action_type or "",
                    json.dumps(proposal.payload or {}, ensure_ascii=False),
                    proposal.priority or 3,
                    proposal.generated_by or "",
                    proposal.overrideable if hasattr(proposal, 'overrideable') else True,
                    json.dumps(decision_log, ensure_ascii=False),
                    datetime.fromtimestamp(proposal.expires_at, tz=timezone.utc) if proposal.expires_at else None,
                    now,
                ),
            )
        except Exception as e:
            # 回退：提案整体存入 metadata
            logger.warning("扁平写入失败，回退到 JSONB 模式: %s", e)
            fallback_meta = {
                **decision_log,
                "proposal": proposal.model_dump(),
            }
            db.execute(
                """INSERT INTO secretary_proposals
                   (id, user_id, session_id, emoji, title, description, action_type, payload,
                    priority, generated_by, overrideable, status, metadata, expires_at, created_at)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'pending', %s, %s, %s)""",
                (
                    proposal.id,
                    user_id,
                    session_id or "",
                    proposal.emoji or "",
                    proposal.title,
                    proposal.description or "",
                    proposal.action_type or "",
                    json.dumps(proposal.payload or {}, ensure_ascii=False),
                    proposal.priority or 3,
                    proposal.generated_by or "",
                    proposal.overrideable if hasattr(proposal, 'overrideable') else True,
                    json.dumps(fallback_meta, ensure_ascii=False),
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
        """更新提案状态（将日志追加到 metadata）"""
        db = self._get_db()
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc)

        extra = extra_log or {}
        extra["updated_at"] = now.isoformat()

        # 在 metadata 中记录状态变更
        db.execute(
            "UPDATE secretary_proposals SET status = %s, "
            "metadata = COALESCE(metadata, '{}'::jsonb) || %s::jsonb, "
            "updated_at = %s "
            "WHERE id = %s AND user_id = %s",
            (status, json.dumps({"status_change": {"to": status, "at": now.isoformat(), **extra}}),
             now, proposal_id, user_id),
        )
        return True

    def get_pending_proposals(self, user_id: str, limit: int = 20) -> list[Proposal]:
        """获取待处理的提案（适配扁平表结构）"""
        db = self._get_db()
        rows = db.fetchall(
            """SELECT id, emoji, title, description, action_type, payload,
                      priority, generated_by, overrideable, status, metadata, created_at
               FROM secretary_proposals
               WHERE user_id = %s AND status = 'pending'
               ORDER BY priority DESC, created_at DESC
               LIMIT %s""",
            (user_id, limit),
        )
        result = []
        for r in rows:
            try:
                payload = r.get("payload") or {}
                if isinstance(payload, str):
                    payload = json.loads(payload)
                result.append(Proposal(
                    id=r["id"],
                    emoji=r.get("emoji", "💡") or "💡",
                    title=r["title"],
                    description=r.get("description", "") or "",
                    action_type=r.get("action_type", "") or "",
                    payload=payload,
                    priority=r.get("priority", 3) or 3,
                    generated_by=r.get("generated_by", "") or "",
                    overrideable=True if r.get("overrideable") in (True, None) else False,
                ))
            except Exception as e:
                logger.debug("解析提案行失败: %s", e)
        return result

    def get_history(
        self, user_id: str, days: int = 7, limit: int = 50,
    ) -> list[dict[str, Any]]:
        """获取提案历史"""
        db = self._get_db()
        from datetime import datetime, timezone, timedelta
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)

        rows = db.fetchall(
            """SELECT id, emoji, title, description, action_type, payload,
                      priority, generated_by, overrideable, status, metadata,
                      created_at
               FROM secretary_proposals
               WHERE user_id = %s AND created_at >= %s
               ORDER BY created_at DESC
               LIMIT %s""",
            (user_id, cutoff, limit),
        )
        return [
            {
                "id": r["id"],
                "proposal": {
                    "emoji": r.get("emoji", "💡") or "💡",
                    "title": r["title"],
                    "description": r.get("description", "") or "",
                    "action_type": r.get("action_type", "") or "",
                    "payload": r.get("payload"),
                    "priority": r.get("priority", 3) or 3,
                    "generated_by": r.get("generated_by") or "",
                    "overrideable": True if r.get("overrideable") in (True, None) else False,
                },
                "status": r["status"],
                "created_at": r["created_at"].isoformat() if hasattr(r["created_at"], 'isoformat') else str(r["created_at"]),
                "metadata": r.get("metadata"),
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
