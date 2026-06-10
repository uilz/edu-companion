"""
登录事件仓储 — login_events 表的 CRUD

记录每次登录的设备、IP、区域等信息，用于安全审计和用户管理。
"""
from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime
from typing import Optional

logger = logging.getLogger(__name__)


class LoginEventRepo:
    """登录事件数据仓储"""

    def __init__(self):
        from app.db.database import get_db
        self._db = get_db()

    def ensure_table(self) -> None:
        """确保 login_events 表存在"""
        self._db.execute("""
            CREATE TABLE IF NOT EXISTS login_events (
                event_id     TEXT PRIMARY KEY,
                user_id      TEXT NOT NULL,
                ip_address   TEXT DEFAULT '',
                country      TEXT DEFAULT '',
                region       TEXT DEFAULT '',
                city         TEXT DEFAULT '',
                user_agent   TEXT DEFAULT '',
                device_type  TEXT DEFAULT '',
                browser      TEXT DEFAULT '',
                os           TEXT DEFAULT '',
                is_current   BOOLEAN DEFAULT FALSE,
                created_at   TIMESTAMP NOT NULL DEFAULT NOW()
            )
        """)
        self._db.execute("""
            CREATE INDEX IF NOT EXISTS idx_login_events_user ON login_events(user_id)
        """)
        self._db.execute("""
            CREATE INDEX IF NOT EXISTS idx_login_events_created ON login_events(created_at DESC)
        """)
        self._db.execute("""
            CREATE INDEX IF NOT EXISTS idx_login_events_ip ON login_events(ip_address)
        """)

    def record_login(
        self,
        user_id: str,
        ip_address: str = "",
        user_agent: str = "",
        country: str = "",
        region: str = "",
        city: str = "",
        device_type: str = "",
        browser: str = "",
        os: str = "",
    ) -> dict:
        """记录一次登录事件，同设备1小时内不重复创建"""
        now = datetime.now().isoformat()

        # 检查是否已有同设备近1小时的登录记录（去重）
        existing = self._db.fetchone(
            """SELECT event_id FROM login_events
               WHERE user_id = %s
                 AND ip_address = %s
                 AND device_type = %s
                 AND browser = %s
                 AND os = %s
                 AND created_at > NOW() - INTERVAL '1 hour'
               ORDER BY created_at DESC
               LIMIT 1""",
            (user_id, ip_address, device_type, browser, os),
        )
        if existing:
            event_id = existing["event_id"]
            # 更新已有记录时间并标记为当前
            self._db.execute(
                "UPDATE login_events SET created_at = %s WHERE event_id = %s",
                (now, event_id),
            )
            self._db.execute(
                "UPDATE login_events SET is_current = FALSE WHERE user_id = %s AND is_current = TRUE",
                (user_id,),
            )
            self._db.execute(
                "UPDATE login_events SET is_current = TRUE WHERE event_id = %s",
                (event_id,),
            )
            return {"event_id": event_id, "user_id": user_id}

        event_id = f"le_{uuid.uuid4().hex[:12]}"

        # 将之前的 is_current 标记清除
        self._db.execute(
            "UPDATE login_events SET is_current = FALSE WHERE user_id = %s AND is_current = TRUE",
            (user_id,),
        )

        self._db.execute(
            """INSERT INTO login_events
               (event_id, user_id, ip_address, country, region, city,
                user_agent, device_type, browser, os, is_current, created_at)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, TRUE, %s)""",
            (event_id, user_id, ip_address, country, region, city,
             user_agent, device_type, browser, os, now),
        )
        return {"event_id": event_id, "user_id": user_id}

    def get_user_login_history(
        self, user_id: str, limit: int = 20, offset: int = 0
    ) -> list[dict]:
        """获取用户登录历史"""
        rows = self._db.fetchall(
            """SELECT event_id, user_id, ip_address, country, region, city,
                      user_agent, device_type, browser, os, is_current, created_at
               FROM login_events
               WHERE user_id = %s
               ORDER BY created_at DESC
               LIMIT %s OFFSET %s""",
            (user_id, limit, offset),
        )
        return rows or []

    def get_user_active_sessions(self, user_id: str) -> list[dict]:
        """获取用户当前活跃会话（最近24小时内的登录），按 device_type+browser+os+ip_address 去重"""
        rows = self._db.fetchall(
            """SELECT DISTINCT ON (device_type, browser, os, ip_address)
                      event_id, user_id, ip_address, country, region, city,
                      user_agent, device_type, browser, os, is_current, 
                      MAX(created_at) AS created_at
               FROM login_events
               WHERE user_id = %s
                 AND created_at > NOW() - INTERVAL '24 hours'
               GROUP BY event_id, user_id, ip_address, country, region, city,
                        user_agent, device_type, browser, os, is_current
               ORDER BY device_type, browser, os, ip_address, created_at DESC""",
            (user_id,),
        )
        return rows or []

    def get_user_online_status(self, user_id: str) -> dict:
        """获取用户在线状态（基于 users.last_active_at）"""
        row = self._db.fetchone(
            "SELECT last_active_at, last_login FROM users WHERE id = %s",
            (user_id,),
        )
        if not row:
            return {"online": False, "last_seen": None}

        # 优先用 last_active_at，其次用 last_login
        last_active = str(row.get("last_active_at") or row.get("last_login") or "")
        if not last_active:
            return {"online": False, "last_seen": None}

        # 30分钟内有活动视为在线
        from datetime import timedelta
        try:
            last_dt = datetime.fromisoformat(last_active)
            online = (datetime.now() - last_dt) < timedelta(minutes=30)
        except (ValueError, TypeError):
            online = False

        return {"online": online, "last_seen": last_active}

    def get_ip_analysis(self, user_id: str) -> list[dict]:
        """获取用户 IP 及区域分析"""
        rows = self._db.fetchall(
            """SELECT ip_address, country, region, city,
                      COUNT(*) AS login_count,
                      MAX(created_at) AS last_seen
               FROM login_events
               WHERE user_id = %s AND ip_address != ''
               GROUP BY ip_address, country, region, city
               ORDER BY login_count DESC
               LIMIT 20""",
            (user_id,),
        )
        return rows or []

    def get_all_online_count(self) -> int:
        """获取当前在线用户总数（基于 last_active_at）"""
        row = self._db.fetchone(
            """SELECT COUNT(*) AS cnt FROM users
               WHERE last_active_at > NOW() - INTERVAL '30 minutes'
                 AND is_active = TRUE"""
        )
        return int(row["cnt"]) if row else 0

    def get_online_users(self, limit: int = 50) -> list[dict]:
        """获取在线用户列表（基于 last_active_at）"""
        rows = self._db.fetchall(
            """SELECT u.id AS user_id, u.username, u.display_name, u.role,
                      u.last_active_at AS last_seen,
                      le.ip_address, le.device_type, le.browser, le.os,
                      le.country, le.region, le.city
               FROM users u
               LEFT JOIN LATERAL (
                   SELECT ip_address, device_type, browser, os, country, region, city
                   FROM login_events
                   WHERE user_id = u.id
                   ORDER BY created_at DESC LIMIT 1
               ) le ON TRUE
               WHERE u.last_active_at > NOW() - INTERVAL '30 minutes'
                 AND u.is_active = TRUE
               ORDER BY u.last_active_at DESC
               LIMIT %s""",
            (limit,),
        )
        return rows or []


# 全局单例
_login_event_repo: Optional[LoginEventRepo] = None


def get_login_event_repo() -> LoginEventRepo:
    global _login_event_repo
    if _login_event_repo is None:
        _login_event_repo = LoginEventRepo()
        _login_event_repo.ensure_table()
    return _login_event_repo
