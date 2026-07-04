"""
Auth 数据持久化 — 用户、LLM 配置、登录事件的 CRUD

合并自 domain/auth/repository.py、user_llm_repo.py、login_event_repo.py。
领域层通过 get_*_repo() 函数访问（见 domain/auth/*.py 中的 re-export）。
"""
from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime
from typing import Any, Optional

from app.infrastructure.crypto import encrypt, decrypt

logger = logging.getLogger(__name__)


class UserRepo:
    """用户数据仓储"""

    def __init__(self):
        from app.infrastructure.db.database import get_db
        self._db = get_db()

    def ensure_table(self) -> None:
        """确保 users 表存在"""
        self._db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id          TEXT PRIMARY KEY,
                username    TEXT NOT NULL UNIQUE,
                email       TEXT DEFAULT '',
                password_hash TEXT NOT NULL,
                display_name TEXT DEFAULT '',
                role        TEXT DEFAULT 'user',
                is_active   BOOLEAN DEFAULT TRUE,
                token_version INTEGER DEFAULT 0,
                last_login  TIMESTAMP,
                last_active_at TIMESTAMP,
                created_at  TIMESTAMP NOT NULL DEFAULT NOW(),
                updated_at  TIMESTAMP NOT NULL DEFAULT NOW()
            )
        """)
        self._db.execute("""
            CREATE INDEX IF NOT EXISTS idx_users_username ON users(username)
        """)
        # 兼容旧表：添加 last_active_at 列
        try:
            self._db.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS last_active_at TIMESTAMP")
        except Exception:
            pass
        # 兼容旧表：添加 token_version 列
        try:
            self._db.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS token_version INTEGER DEFAULT 0")
        except Exception:
            pass

    def find_by_username(self, username: str) -> Optional[dict]:
        """按用户名查找用户"""
        return self._db.fetchone(
            "SELECT * FROM users WHERE username = %s", (username,),
        )

    def find_by_id(self, user_id: str) -> Optional[dict]:
        """按 ID 查找用户"""
        return self._db.fetchone(
            "SELECT * FROM users WHERE id = %s", (user_id,),
        )

    def create_user(self, user_id: str, username: str, password_hash: str, display_name: str = "", email: str = "", role: str = "user") -> bool:
        """创建新用户"""
        try:
            self._db.execute(
                """INSERT INTO users (id, username, email, password_hash, display_name, role)
                   VALUES (%s, %s, %s, %s, %s, %s)""",
                (user_id, username, email, password_hash, display_name, role),
            )
            return True
        except Exception as e:
            logger.warning("创建用户失败: %s", e)
            return False

    def update_password(self, user_id: str, password_hash: str) -> bool:
        """更新密码"""
        try:
            self._db.execute(
                "UPDATE users SET password_hash = %s, updated_at = NOW() WHERE id = %s",
                (password_hash, user_id),
            )
            return True
        except Exception as e:
            logger.warning("更新密码失败: %s", e)
            return False

    def update_last_login(self, user_id: str) -> None:
        """更新最后登录时间"""
        self._db.execute(
            "UPDATE users SET last_login = NOW(), last_active_at = NOW() WHERE id = %s",
            (user_id,),
        )

    def touch_last_active(self, user_id: str, throttle_sec: int = 300) -> None:
        """节流式刷新 last_active_at（默认 5 分钟节流）

        判定逻辑放在 DB 内（NOW() 比较），避免每请求都产生一次 UPDATE。
        用于在认证中间件里 fire-and-forget 触发，不会阻塞请求。
        """
        self._db.execute(
            "UPDATE users SET last_active_at = NOW() "
            "WHERE id = %s AND (last_active_at IS NULL "
            "  OR last_active_at < NOW() - make_interval(secs => %s))",
            (user_id, throttle_sec),
        )

    def get_online_users(self, limit: int = 50, online_window_min: int = 30) -> list[dict]:
        """获取当前在线用户列表（last_active_at 在 N 分钟内）"""
        return self._db.fetchall(
            """SELECT id, username, display_name, role, email,
                      last_active_at, last_login
               FROM users
               WHERE last_active_at IS NOT NULL
                 AND last_active_at > NOW() - make_interval(mins => %s)
               ORDER BY last_active_at DESC
               LIMIT %s""",
            (online_window_min, limit),
        ) or []

    def get_online_count(self, online_window_min: int = 30) -> int:
        """获取在线用户数"""
        row = self._db.fetchone(
            """SELECT COUNT(*) AS c FROM users
               WHERE last_active_at IS NOT NULL
                 AND last_active_at > NOW() - make_interval(mins => %s)""",
            (online_window_min,),
        )
        return int(row["c"]) if row else 0

    def update_display_name(self, user_id: str, display_name: str) -> None:
        """更新显示名称"""
        self._db.execute(
            "UPDATE users SET display_name = %s, updated_at = NOW() WHERE id = %s",
            (display_name, user_id),
        )

    def update_profile(
        self,
        user_id: str,
        display_name: str | None = None,
        email: str | None = None,
    ) -> bool:
        """更新用户资料 (display_name / email, Task #84)

        只更新非 None 字段, 保留其他字段原值。
        """
        try:
            fields: list[str] = []
            params: list[Any] = []
            if display_name is not None:
                fields.append("display_name = %s")
                params.append(display_name)
            if email is not None:
                fields.append("email = %s")
                params.append(email)
            if not fields:
                return False
            fields.append("updated_at = NOW()")
            params.append(user_id)
            self._db.execute(
                f"UPDATE users SET {', '.join(fields)} WHERE id = %s",
                tuple(params),
            )
            return True
        except Exception as e:
            logger.warning("更新资料失败: %s", e)
            return False

    def deactivate_user(self, user_id: str) -> None:
        """停用用户"""
        self._db.execute(
            "UPDATE users SET is_active = FALSE, updated_at = NOW() WHERE id = %s",
            (user_id,),
        )

    def deactivate_account(self, user_id: str, username: str) -> None:
        """注销账号（软删除）"""
        from datetime import datetime
        now = datetime.now().isoformat()
        self._db.execute(
            "UPDATE users SET deleted_at = %s, username = %s, status = 'deactivated' WHERE id = %s",
            (now, f"{username}_deleted_{user_id[:8]}", user_id),
        )

    def increment_token_version(self, user_id: str) -> None:
        """递增 token_version 使旧 token 失效"""
        from datetime import datetime
        self._db.execute(
            "UPDATE users SET token_version = COALESCE(token_version, 0) + 1, updated_at = %s WHERE id = %s",
            (datetime.now().isoformat(), user_id),
        )

    def clear_login_sessions(self, user_id: str) -> None:
        """清除用户所有登录会话的 is_current 标记"""
        self._db.execute(
            "UPDATE login_events SET is_current = FALSE WHERE user_id = %s",
            (user_id,),
        )

    def list_users(self, page: int = 1, page_size: int = 20) -> dict:
        """获取用户列表（分页），返回 {users, total, page, page_size}"""
        offset = (page - 1) * page_size
        rows = self._db.fetchall(
            "SELECT id, username, email, display_name, role, is_active, "
            "last_login, last_active_at, created_at, updated_at "
            "FROM users ORDER BY created_at DESC LIMIT %s OFFSET %s",
            (page_size, offset),
        )
        total = self._db.fetchone("SELECT COUNT(*) as cnt FROM users")
        return {
            "users": rows,
            "total": total["cnt"] if total else 0,
            "page": page,
            "page_size": page_size,
        }


class LoginEventRepo:
    """登录事件数据仓储"""

    def __init__(self):
        from app.infrastructure.db.database import get_db
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

    def log_event(
        self,
        user_id: str,
        ip_address: str = "",
        user_agent: str = "",
    ) -> str:
        """记录登录事件，返回 event_id"""
        event_id = f"le_{uuid.uuid4().hex[:12]}"

        # UA 解析
        parsed = {}
        try:
            from app.domain.auth.ua_parser import parse_user_agent
            parsed = parse_user_agent(user_agent)
        except Exception:
            pass

        self._db.execute(
            """INSERT INTO login_events
               (event_id, user_id, ip_address, user_agent,
                device_type, browser, os, is_current, created_at)
               VALUES (%s, %s, %s, %s, %s, %s, %s, TRUE, NOW())""",
            (
                event_id, user_id, ip_address, user_agent,
                parsed.get("device_type", ""),
                parsed.get("browser", ""),
                parsed.get("os", ""),
            ),
        )
        # 将其他设备的 is_current 置为 FALSE
        self._db.execute(
            "UPDATE login_events SET is_current = FALSE "
            "WHERE user_id = %s AND event_id != %s",
            (user_id, event_id),
        )
        return event_id

    def get_latest(self, user_id: str) -> Optional[dict]:
        """获取用户最新登录事件"""
        return self._db.fetchone(
            "SELECT * FROM login_events WHERE user_id = %s ORDER BY created_at DESC LIMIT 1",
            (user_id,),
        )

    def get_history(self, user_id: str, limit: int = 20) -> list[dict]:
        """获取用户登录历史"""
        return self._db.fetchall(
            "SELECT * FROM login_events WHERE user_id = %s "
            "ORDER BY created_at DESC LIMIT %s",
            (user_id, limit),
        )

    def get_all_users_latest_login(self) -> list[dict]:
        """获取所有用户的最新登录事件（用于管理后台）"""
        return self._db.fetchall(
            """SELECT DISTINCT ON (le.user_id)
                   le.event_id, le.user_id, le.ip_address,
                   le.device_type, le.browser, le.os,
                   le.country, le.region, le.city,
                   le.created_at, u.display_name, u.username
               FROM login_events le
               JOIN users u ON u.id = le.user_id
               ORDER BY le.user_id, le.created_at DESC"""
        )

    def count_by_range(self, start: str, end: str) -> int:
        """统计某时间范围内的登录次数"""
        row = self._db.fetchone(
            "SELECT COUNT(*) as cnt FROM login_events "
            "WHERE created_at >= %s AND created_at < %s",
            (start, end),
        )
        return row["cnt"] if row else 0

    def get_stats(self, days: int = 7) -> dict:
        """获取登录统计"""
        rows = self._db.fetchall(
            """SELECT DATE(created_at) as date, COUNT(*) as cnt
               FROM login_events
               WHERE created_at >= NOW() - INTERVAL '%s days'
               GROUP BY DATE(created_at)
               ORDER BY date""",
            (days,),
        )
        total = self._db.fetchone("SELECT COUNT(*) as cnt FROM login_events")
        return {
            "daily": rows,
            "total": total["cnt"] if total else 0,
        }

    def get_user_login_history(self, user_id: str, limit: int = 20) -> list[dict]:
        """获取用户登录历史（别名）"""
        return self.get_history(user_id, limit)

    def get_user_online_status(self, user_id: str) -> dict:
        """获取用户在线状态（基于 users.last_active_at，30 分钟内视为在线）

        DB 列是 `timestamp without time zone`，NOW() 返回 CST 墙钟。
        Python 进程也在 CST，故用 `datetime.now()` 而非 `datetime.utcnow()`。
        """
        row = self._db.fetchone(
            "SELECT last_active_at FROM users WHERE id = %s",
            (user_id,),
        )
        last_seen = row["last_active_at"] if row else None
        online = False
        if last_seen:
            from datetime import datetime, timedelta
            online = (datetime.now() - last_seen) < timedelta(minutes=30)
        return {
            "online": online,
            "last_seen": last_seen.isoformat() if last_seen else None,
        }

    def get_user_active_sessions(self, user_id: str) -> list[dict]:
        """获取用户活跃会话"""
        limit = 10
        rows = self._db.fetchall(
            "SELECT event_id, user_id, ip_address, device_type, browser, os, "
            "       country, region, city, created_at, is_current "
            "FROM login_events WHERE user_id = %s AND is_current = TRUE "
            "ORDER BY created_at DESC LIMIT %s",
            (user_id, limit),
        )
        return rows or []

    def get_ip_analysis(self, user_id: str) -> list[dict]:
        """获取用户 IP 分析（按 IP 聚合统计）"""
        rows = self._db.fetchall(
            """SELECT ip_address, country, region, city,
                      COUNT(*) AS count,
                      MAX(created_at) AS last_seen
               FROM login_events
               WHERE user_id = %s
               GROUP BY ip_address, country, region, city
               ORDER BY count DESC""",
            (user_id,),
        )
        return rows or []

    def mark_current_session(self, user_id: str, ip_address: str, user_agent: str) -> None:
        """将匹配 IP + UA 的最新登录事件标记为当前会话"""
        self._db.execute(
            """UPDATE login_events SET is_current = TRUE
               WHERE user_id = %s AND ip_address = %s AND user_agent = %s
               AND created_at = (
                   SELECT MAX(created_at) FROM login_events
                   WHERE user_id = %s AND ip_address = %s AND user_agent = %s
               )""",
            (user_id, ip_address, user_agent, user_id, ip_address, user_agent),
        )


class UserLlmConfigRepo:
    """用户 LLM 配置数据仓储 — D16: 迁移至 user_settings 统一表"""

    def __init__(self):
        from app.infrastructure.db.database import get_db
        from app.infrastructure.db.user_settings_repo import get_user_settings_repo
        self._db = get_db()
        self._settings = get_user_settings_repo()

    def get(self, user_id: str) -> Optional[dict]:
        """获取用户 LLM 配置（解密 api_key）"""
        config = self._settings.get_key(user_id, "llm_config")
        if not config or not config.get("model_name"):
            return None
        config = dict(config)
        config["api_key"] = decrypt(config.get("api_key_encrypted", ""))
        config.pop("api_key_encrypted", None)
        config.setdefault("api_base", "")
        config.setdefault("is_active", True)
        return config

    def set(self, user_id: str, api_base: str = "", api_key: str = "", model_name: str = "") -> None:
        """设置用户 LLM 配置（加密 api_key）"""
        encrypted = encrypt(api_key) if api_key else ""
        self._settings.set_key(user_id, "llm_config", {
            "api_base": api_base,
            "api_key_encrypted": encrypted,
            "model_name": model_name,
            "is_active": True,
        })

    def save(self, user_id: str = "", api_base: str = "", api_key: str = "", model_name: str = "") -> None:
        """保存用户 LLM 配置（settings_api.py 兼容别名）"""
        self.set(user_id, api_base, api_key, model_name)

    def delete(self, user_id: str) -> None:
        """删除用户 LLM 配置"""
        self._settings.delete_key(user_id, "llm_config")
