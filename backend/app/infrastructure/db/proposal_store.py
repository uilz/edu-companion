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

from app.domain.secretary.models import Proposal
from shared.protocols.secretary import SecretaryRepository

logger = logging.getLogger(__name__)


class ProposalStore(SecretaryRepository):
    """提案持久化存储（实现 SecretaryRepository 协议）"""

    def __init__(self):
        self._db = None

    def _get_db(self):
        if self._db is None:
            from app.infrastructure.db.database import get_db
            self._db = get_db()
        return self._db

    @staticmethod
    def _ensure_table() -> None:
        """确保 secretary_proposals 表存在（幂等）

        Task #83 B-1/B-2: 委派给 secretary_schema._ensure_tables()
        统一在 secretary_schema.sql 中定义, 避免重复字段定义
        """
        from app.infrastructure.db.secretary_schema import _ensure_tables
        _ensure_tables()

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
        fingerprint = None
        if proposal.payload and "_fingerprint" in proposal.payload:
            fingerprint = proposal.payload.pop("_fingerprint")
            decision_log["fingerprint"] = fingerprint
            # 指纹去重检查
            try:
                existing = db.fetchone(
                    "SELECT id FROM secretary_proposals "
                    "WHERE user_id = %s AND status = 'pending' "
                    "AND metadata->>'fingerprint' = %s "
                    "LIMIT 1",
                    (user_id, fingerprint),
                )
                if existing:
                    logger.debug("指纹去重: [%s] %s", proposal.generated_by, proposal.title)
                    return existing["id"]
            except Exception:
                pass

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
        """更新提案状态（将日志追加到 metadata），返回是否真实更新"""
        db = self._get_db()
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc)

        extra = extra_log or {}
        extra["updated_at"] = now.isoformat()

        # 在 metadata 中记录状态变更
        cur = db.get_conn().cursor()
        try:
            cur.execute(
                "UPDATE secretary_proposals SET status = %s, "
                "metadata = COALESCE(metadata, '{}'::jsonb) || %s::jsonb, "
                "updated_at = %s "
                "WHERE id = %s AND user_id = %s",
                (status, json.dumps({"status_change": {"to": status, "at": now.isoformat(), **extra}}),
                 now, proposal_id, user_id),
            )
            return cur.rowcount > 0
        finally:
            cur.connection.commit()
            cur.close()
            db.put_conn(cur.connection)

    def get_pending_proposals(
        self, user_id: str, limit: int = 20,
        source_module: str | None = None,
        action_type: str | None = None,
        priority_min: int | None = None,
        priority_max: int | None = None,
        search: str | None = None,
    ) -> list[Proposal]:
        """获取待处理的提案（支持筛选参数）"""
        db = self._get_db()

        conditions = ["user_id = %s", "status = 'pending'"]
        params: list[Any] = [user_id]

        if source_module:
            conditions.append("generated_by = %s")
            params.append(source_module)
        if action_type:
            conditions.append("action_type = %s")
            params.append(action_type)
        if priority_min is not None:
            conditions.append("priority >= %s")
            params.append(priority_min)
        if priority_max is not None:
            conditions.append("priority <= %s")
            params.append(priority_max)

        where_clause = " AND ".join(conditions)
        sql = (
            f"SELECT id, emoji, title, description, action_type, payload, "
            f"priority, generated_by, overrideable, status, metadata, created_at "
            f"FROM secretary_proposals WHERE {where_clause} "
            f"ORDER BY priority DESC, created_at DESC LIMIT %s"
        )
        params.append(limit)

        rows = db.fetchall(sql, tuple(params))

        result = []
        for r in rows:
            try:
                payload = r.get("payload") or {}
                if isinstance(payload, str):
                    payload = json.loads(payload)

                # 搜索过滤（在应用层做，因为需要中文全文搜索）
                if search:
                    q = search.lower()
                    title = (r.get("title") or "").lower()
                    desc = (r.get("description") or "").lower()
                    if q not in title and q not in desc:
                        continue

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
        source_module: str | None = None,
        action_type: str | None = None,
        page: int = 1,
        page_size: int = 50,
    ) -> list[dict[str, Any]]:
        """获取提案历史（支持筛选与分页）"""
        db = self._get_db()
        from datetime import datetime, timezone, timedelta
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)

        conditions = ["user_id = %s", "created_at >= %s"]
        params: list[Any] = [user_id, cutoff]

        if source_module:
            conditions.append("generated_by = %s")
            params.append(source_module)
        if action_type:
            conditions.append("action_type = %s")
            params.append(action_type)

        where_clause = " AND ".join(conditions)
        offset = (page - 1) * page_size
        sql = (
            f"SELECT id, emoji, title, description, action_type, payload, "
            f"priority, generated_by, overrideable, status, metadata, created_at "
            f"FROM secretary_proposals WHERE {where_clause} "
            f"ORDER BY created_at DESC LIMIT %s OFFSET %s"
        )
        params.append(page_size)
        params.append(offset)

        rows = db.fetchall(sql, tuple(params))
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
        """将过期提案标记为 expired，返回真实更新数"""
        db = self._get_db()
        cur = db.get_conn().cursor()
        try:
            cur.execute(
                """UPDATE secretary_proposals
                   SET status = 'expired'
                   WHERE user_id = %s AND status = 'pending'
                   AND expires_at IS NOT NULL AND expires_at < NOW()""",
                (user_id,),
            )
            return cur.rowcount
        finally:
            cur.connection.commit()
            cur.close()
            db.put_conn(cur.connection)

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

    def get_daily_usage(self, user_id: str) -> int:
        """获取用户今日已使用的提案推送数"""
        try:
            from datetime import datetime, timezone
            db = self._get_db()
            today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
            row = db.fetchone(
                """SELECT COUNT(*) as cnt FROM secretary_proposals
                   WHERE user_id = %s AND DATE(created_at) = %s
                   AND status IN ('pending', 'accepted')""",
                (user_id, today),
            )
            return row["cnt"] if row else 0
        except Exception as e:
            logger.debug("获取每日用量失败: %s", e)
            return 0

    # ═══════════════════════════════════════════════
    # Phase 2: 新操作 — 延后 / 删除 / 恢复 / 批量
    # ═══════════════════════════════════════════════

    def snooze_proposal(
        self, proposal_id: str, user_id: str,
        until_timestamp: float | None = None,
    ) -> bool:
        """延后提案 — status → snoozed + 记录 snoozed_until，返回是否真实更新"""
        db = self._get_db()
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc)

        meta_update: dict[str, Any] = {"snoozed_at": now.isoformat()}
        if until_timestamp:
            meta_update["snoozed_until"] = until_timestamp

        cur = db.get_conn().cursor()
        try:
            cur.execute(
                "UPDATE secretary_proposals SET status = 'snoozed', "
                "metadata = COALESCE(metadata, '{}'::jsonb) || %s::jsonb, "
                "updated_at = %s "
                "WHERE id = %s AND user_id = %s",
                (json.dumps({"snooze": meta_update}),
                 now, proposal_id, user_id),
            )
            return cur.rowcount > 0
        finally:
            cur.connection.commit()
            cur.close()
            db.put_conn(cur.connection)

    def delete_proposal(self, proposal_id: str, user_id: str) -> bool:
        """删除提案 — status → deleted，返回是否真实更新"""
        db = self._get_db()
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc)
        cur = db.get_conn().cursor()
        try:
            cur.execute(
                "UPDATE secretary_proposals SET status = 'deleted', updated_at = %s "
                "WHERE id = %s AND user_id = %s",
                (now, proposal_id, user_id),
            )
            return cur.rowcount > 0
        finally:
            cur.connection.commit()
            cur.close()
            db.put_conn(cur.connection)

    def restore_proposal(self, proposal_id: str, user_id: str) -> bool:
        """恢复提案 — snoozed/deleted → pending，返回是否真实更新"""
        db = self._get_db()
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc)
        cur = db.get_conn().cursor()
        try:
            cur.execute(
                "UPDATE secretary_proposals SET status = 'pending', "
                "metadata = COALESCE(metadata, '{}'::jsonb) || %s::jsonb, "
                "updated_at = %s "
                "WHERE id = %s AND user_id = %s "
                "AND status IN ('snoozed', 'deleted')",
                (json.dumps({"restored_at": now.isoformat()}),
                 now, proposal_id, user_id),
            )
            return cur.rowcount > 0
        finally:
            cur.connection.commit()
            cur.close()
            db.put_conn(cur.connection)

    def batch_update_status(
        self,
        proposal_ids: list[str],
        status: str,
        user_id: str,
    ) -> int:
        """批量更新提案状态，返回真实更新的记录数"""
        if not proposal_ids:
            return 0
        db = self._get_db()
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc)

        cur = db.get_conn().cursor()
        try:
            placeholders = ", ".join("%s" for _ in proposal_ids)
            sql = (
                f"UPDATE secretary_proposals SET status = %s, updated_at = %s "
                f"WHERE id IN ({placeholders}) AND user_id = %s"
            )
            params = [status, now] + list(proposal_ids) + [user_id]
            cur.execute(sql, tuple(params))
            return cur.rowcount
        finally:
            cur.connection.commit()
            cur.close()
            db.put_conn(cur.connection)
