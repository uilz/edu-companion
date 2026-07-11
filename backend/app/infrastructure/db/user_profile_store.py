"""用户编排画像持久化 — 基于 PostgreSQL

职责:
  - 读取/写入 UserOrchestrationProfile
  - 维护信任分、疲劳分、每日配额、关系记忆
  - 每日重置 proactive_quota_today
"""

from __future__ import annotations

import json
import logging
from typing import Any

from app.domain.secretary.models import (
    RelationMemoryEntry,
    UserOrchestrationProfile,
)

logger = logging.getLogger(__name__)


class UserOrchestrationProfileStore:
    """用户编排画像持久化"""

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

    def get_profile(self, user_id: str) -> UserOrchestrationProfile:
        """获取用户编排画像（不存在则返回默认值）"""
        db = self._get_db()
        try:
            row = db.fetchone(
                "SELECT * FROM secretary_user_profiles WHERE user_id = %s",
                (user_id,),
            )
        except Exception as e:
            logger.debug("读取用户编排画像失败: %s", e)
            return UserOrchestrationProfile(user_id=user_id)

        if not row:
            return UserOrchestrationProfile(user_id=user_id)

        return self._row_to_profile(row)

    def save_profile(self, profile: UserOrchestrationProfile) -> bool:
        """保存用户编排画像"""
        db = self._get_db()
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc)

        relation_memory_json = {
            key: entry.model_dump()
            for key, entry in (profile.relation_memory or {}).items()
        }

        try:
            db.execute(
                """INSERT INTO secretary_user_profiles
                   (user_id, trust_score, fatigue_score, proactive_quota_today,
                    last_proactive_at, enabled_modules, quiet_hours_start, quiet_hours_end,
                    relation_memory, version, created_at, updated_at)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                   ON CONFLICT (user_id) DO UPDATE SET
                    trust_score = EXCLUDED.trust_score,
                    fatigue_score = EXCLUDED.fatigue_score,
                    proactive_quota_today = EXCLUDED.proactive_quota_today,
                    last_proactive_at = EXCLUDED.last_proactive_at,
                    enabled_modules = EXCLUDED.enabled_modules,
                    quiet_hours_start = EXCLUDED.quiet_hours_start,
                    quiet_hours_end = EXCLUDED.quiet_hours_end,
                    relation_memory = EXCLUDED.relation_memory,
                    version = secretary_user_profiles.version + 1,
                    updated_at = EXCLUDED.updated_at""",
                (
                    profile.user_id,
                    profile.trust_score,
                    profile.fatigue_score,
                    profile.proactive_quota_today,
                    datetime.fromtimestamp(profile.last_proactive_at, tz=timezone.utc) if profile.last_proactive_at else None,
                    json.dumps(profile.enabled_modules, ensure_ascii=False),
                    profile.quiet_hours_start,
                    profile.quiet_hours_end,
                    json.dumps(relation_memory_json, ensure_ascii=False),
                    profile.version,
                    now,
                    now,
                ),
            )
            return True
        except Exception as e:
            logger.warning("保存用户编排画像失败: %s", e)
            return False

    def update_relation_memory(
        self,
        user_id: str,
        action_type: str,
        target_id: str,
        action: str,
    ) -> RelationMemoryEntry:
        """更新关系记忆并返回更新后的条目"""
        profile = self.get_profile(user_id)
        key = f"{action_type}:{target_id}" if target_id else action_type
        entry = profile.relation_memory.get(key)
        if not entry:
            entry = RelationMemoryEntry(action_type=action_type, target_id=target_id or "")

        now = __import__("time").time()
        if action == "accept":
            entry.accept_count += 1
            entry.ignore_count = 0
            entry.effective_priority_bias = max(0, entry.effective_priority_bias - 1)
        elif action == "dismiss":
            entry.ignore_count += 1
            entry.last_interaction_at = now
            if entry.ignore_count >= 3:
                entry.effective_priority_bias = min(2, entry.effective_priority_bias + 1)

        profile.relation_memory[key] = entry
        self.save_profile(profile)
        return entry

    def reset_daily_quota_if_needed(self, user_id: str, default_quota: int = 5) -> UserOrchestrationProfile:
        """如果需要，重置每日配额（跨天）"""
        import time
        from datetime import datetime, timezone

        profile = self.get_profile(user_id)
        now = time.time()
        today = datetime.fromtimestamp(now, tz=timezone.utc).strftime("%Y-%m-%d")
        last_date = None
        if profile.last_proactive_at:
            last_date = datetime.fromtimestamp(profile.last_proactive_at, tz=timezone.utc).strftime("%Y-%m-%d")

        if last_date != today:
            profile.proactive_quota_today = default_quota
            profile.last_proactive_at = now
            self.save_profile(profile)
        return profile

    def _row_to_profile(self, row: dict[str, Any]) -> UserOrchestrationProfile:
        relation_memory: dict[str, RelationMemoryEntry] = {}
        raw_mem = row.get("relation_memory") or {}
        if isinstance(raw_mem, str):
            try:
                raw_mem = json.loads(raw_mem)
            except Exception:
                raw_mem = {}
        for key, val in raw_mem.items():
            try:
                if isinstance(val, dict):
                    relation_memory[key] = RelationMemoryEntry(**val)
            except Exception:
                continue

        last_proactive_at = row.get("last_proactive_at")
        return UserOrchestrationProfile(
            user_id=row["user_id"],
            trust_score=row.get("trust_score", 0.5) or 0.5,
            fatigue_score=row.get("fatigue_score", 0.0) or 0.0,
            proactive_quota_today=row.get("proactive_quota_today", 5) or 5,
            last_proactive_at=last_proactive_at.timestamp() if hasattr(last_proactive_at, "timestamp") else (float(last_proactive_at) if last_proactive_at else None),
            enabled_modules=row.get("enabled_modules", []) or [],
            quiet_hours_start=row.get("quiet_hours_start", "22:00") or "22:00",
            quiet_hours_end=row.get("quiet_hours_end", "08:00") or "08:00",
            relation_memory=relation_memory,
            version=row.get("version", 0) or 0,
        )


# ── 全局实例 ──
user_profile_store = UserOrchestrationProfileStore()
