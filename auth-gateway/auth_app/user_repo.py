"""
认证网关独立用户仓库
不依赖后端任何模块
"""
from __future__ import annotations

import hashlib
import os
import time
from typing import Optional

from auth_app.database import get_db_instance, DB


def hash_password(password: str) -> str:
    """使用 bcrypt 风格的密码哈希（简化版，生产环境应使用 bcrypt）"""
    import bcrypt
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    import bcrypt
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
    except Exception:
        return False


class UserRepo:
    """用户数据访问层"""

    def __init__(self):
        self.db = get_db_instance()
        self._ensure_table()

    def _ensure_table(self):
        """确保 users 表存在"""
        self.db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id VARCHAR(32) PRIMARY KEY,
                username VARCHAR(32) UNIQUE NOT NULL,
                email VARCHAR(128) DEFAULT '',
                password_hash VARCHAR(128) NOT NULL,
                display_name VARCHAR(64) DEFAULT '',
                avatar_url VARCHAR(512) DEFAULT '',
                role VARCHAR(16) DEFAULT 'user',
                is_active BOOLEAN DEFAULT true,
                last_login TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        # 兼容旧表：无 avatar_url 列时添加
        try:
            self.db.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS avatar_url VARCHAR(512) DEFAULT ''")
        except Exception:
            pass

    def find_by_id(self, user_id: str) -> Optional[dict]:
        return self.db.fetchone("SELECT * FROM users WHERE id = %s", (user_id,))

    def find_by_username(self, username: str) -> Optional[dict]:
        return self.db.fetchone("SELECT * FROM users WHERE username = %s", (username,))

    def find_by_email(self, email: str) -> Optional[dict]:
        return self.db.fetchone("SELECT * FROM users WHERE email = %s AND email != ''", (email,))

    def create(self, username: str, password_hash: str, email: str = "", display_name: str = "", role: str = "user") -> dict:
        user_id = f"u_{hashlib.md5(f'{username}{time.time()}'.encode()).hexdigest()[:12]}"
        self.db.execute(
            """INSERT INTO users (id, username, email, password_hash, display_name, role, created_at, updated_at)
               VALUES (%s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)""",
            (user_id, username, email, password_hash, display_name or username, role),
        )
        return self.find_by_id(user_id)

    def update_last_login(self, user_id: str):
        self.db.execute(
            "UPDATE users SET last_login = CURRENT_TIMESTAMP, updated_at = CURRENT_TIMESTAMP WHERE id = %s",
            (user_id,),
        )

    def update_password(self, user_id: str, new_password_hash: str):
        self.db.execute(
            "UPDATE users SET password_hash = %s, updated_at = CURRENT_TIMESTAMP WHERE id = %s",
            (new_password_hash, user_id),
        )

    def update_avatar(self, user_id: str, avatar_url: str):
        self.db.execute(
            "UPDATE users SET avatar_url = %s, updated_at = CURRENT_TIMESTAMP WHERE id = %s",
            (avatar_url, user_id),
        )

    def update_profile(self, user_id: str, display_name: str = None, email: str = None):
        updates = []
        params = []
        if display_name is not None:
            updates.append("display_name = %s")
            params.append(display_name)
        if email is not None:
            updates.append("email = %s")
            params.append(email)
        if updates:
            updates.append("updated_at = CURRENT_TIMESTAMP")
            params.append(user_id)
            self.db.execute(f"UPDATE users SET {', '.join(updates)} WHERE id = %s", tuple(params))


_user_repo: Optional[UserRepo] = None


def get_user_repo() -> UserRepo:
    global _user_repo
    if _user_repo is None:
        _user_repo = UserRepo()
    return _user_repo
