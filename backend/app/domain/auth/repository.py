"""
用户仓储 — 用户表的 CRUD 操作

遵循分层原则：此文件是唯一操作 users 表的地方。
API 层和 Service 层通过此仓储访问用户数据。
"""
from __future__ import annotations

import logging
from typing import Optional
from datetime import datetime

logger = logging.getLogger(__name__)


class UserRepo:
    """用户数据仓储"""

    def __init__(self):
        from app.db.database import get_db
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
                last_login  TIMESTAMP,
                created_at  TIMESTAMP NOT NULL DEFAULT NOW(),
                updated_at  TIMESTAMP NOT NULL DEFAULT NOW()
            )
        """)
        self._db.execute("""
            CREATE INDEX IF NOT EXISTS idx_users_username ON users(username)
        """)

    def create(self, user_id: str, username: str, password_hash: str,
               email: str = "", display_name: str = "") -> dict:
        """创建用户"""
        now = datetime.now().isoformat()
        self._db.execute(
            """INSERT INTO users (id, username, email, password_hash, display_name, created_at, updated_at)
               VALUES (%s, %s, %s, %s, %s, %s, %s)""",
            (user_id, username, email, password_hash, display_name or username, now, now),
        )
        return self.find_by_id(user_id)

    def find_by_id(self, user_id: str) -> Optional[dict]:
        """按 ID 查找用户"""
        return self._db.fetchone(
            "SELECT id, username, email, display_name, role, is_active, last_login, created_at FROM users WHERE id = %s",
            (user_id,),
        )

    def find_by_username(self, username: str) -> Optional[dict]:
        """按用户名查找用户（含密码哈希，仅用于认证）"""
        return self._db.fetchone(
            "SELECT * FROM users WHERE username = %s",
            (username,),
        )

    def update_last_login(self, user_id: str) -> None:
        """更新最后登录时间"""
        now = datetime.now().isoformat()
        self._db.execute(
            "UPDATE users SET last_login = %s, updated_at = %s WHERE id = %s",
            (now, now, user_id),
        )

    def update_profile(self, user_id: str, display_name: str = None, email: str = None) -> None:
        """更新用户资料"""
        updates = []
        params = []
        if display_name is not None:
            updates.append("display_name = %s")
            params.append(display_name)
        if email is not None:
            updates.append("email = %s")
            params.append(email)
        if updates:
            updates.append("updated_at = %s")
            params.append(datetime.now().isoformat())
            params.append(user_id)
            self._db.execute(
                f"UPDATE users SET {', '.join(updates)} WHERE id = %s",
                tuple(params),
            )

    def list_users(self, limit: int = 50) -> list[dict]:
        """列出用户（管理用）"""
        return self._db.fetchall(
            "SELECT id, username, email, display_name, role, is_active, last_login, created_at FROM users ORDER BY created_at DESC LIMIT %s",
            (limit,),
        )


# 全局单例
_user_repo: Optional[UserRepo] = None


def get_user_repo() -> UserRepo:
    global _user_repo
    if _user_repo is None:
        _user_repo = UserRepo()
        _user_repo.ensure_table()
    return _user_repo
