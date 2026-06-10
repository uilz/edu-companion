"""
认证服务 — 注册、登录、令牌管理

职责：
- 用户注册（密码哈希 + 创建记录）
- 用户登录（密码校验 + JWT 签发）
- JWT 令牌签发 / 验证 / 刷新
- 当前用户解析
"""
from __future__ import annotations

import logging
import os
import uuid
from datetime import datetime, timedelta
from typing import Optional

import bcrypt
import jwt

from app.config import settings
from app.domain.auth.repository import get_user_repo

logger = logging.getLogger(__name__)

# JWT 配置
JWT_SECRET = os.getenv("JWT_SECRET")
if not JWT_SECRET:
    raise RuntimeError("JWT_SECRET environment variable is not set")
JWT_ALGORITHM = "HS256"
JWT_EXPIRE_HOURS = int(os.getenv("JWT_EXPIRE_HOURS", "24"))
JWT_REFRESH_EXPIRE_DAYS = int(os.getenv("JWT_REFRESH_EXPIRE_DAYS", "7"))


class AuthService:
    """认证服务"""

    def __init__(self):
        self.repo = get_user_repo()

    # ── 密码工具 ──

    @staticmethod
    def hash_password(password: str) -> str:
        """密码哈希"""
        return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")

    @staticmethod
    def verify_password(password: str, password_hash: str) -> bool:
        """校验密码"""
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))

    # ── JWT 工具 ──

    @staticmethod
    def create_access_token(user_id: str, username: str, role: str = "user") -> str:
        """签发 access token"""
        expire = datetime.utcnow() + timedelta(hours=JWT_EXPIRE_HOURS)
        payload = {
            "sub": user_id,
            "username": username,
            "role": role,
            "exp": expire,
            "iat": datetime.utcnow(),
            "type": "access",
        }
        return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)

    @staticmethod
    def create_refresh_token(user_id: str) -> str:
        """签发 refresh token"""
        expire = datetime.utcnow() + timedelta(days=JWT_REFRESH_EXPIRE_DAYS)
        payload = {
            "sub": user_id,
            "exp": expire,
            "iat": datetime.utcnow(),
            "type": "refresh",
        }
        return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)

    @staticmethod
    def decode_token(token: str) -> Optional[dict]:
        """解码并验证 JWT"""
        try:
            payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
            return payload
        except jwt.ExpiredSignatureError:
            return None
        except jwt.InvalidTokenError:
            return None

    # ── 业务方法 ──

    def register(self, username: str, password: str,
                 email: str = "", display_name: str = "") -> dict:
        """
        用户注册

        Returns: {user, access_token, refresh_token}
        Raises: ValueError — 用户名已存在
        """
        # 检查用户名是否已存在
        existing = self.repo.find_by_username(username)
        if existing:
            raise ValueError("用户名已存在")

        # 创建用户
        user_id = f"u_{uuid.uuid4().hex[:12]}"
        password_hash = self.hash_password(password)
        user = self.repo.create(
            user_id=user_id,
            username=username,
            password_hash=password_hash,
            email=email,
            display_name=display_name or username,
        )

        # 签发令牌
        access_token = self.create_access_token(user_id, username)
        refresh_token = self.create_refresh_token(user_id)

        logger.info("用户注册: %s (%s)", username, user_id)
        return {
            "user": user,
            "access_token": access_token,
            "refresh_token": refresh_token,
        }

    def login(self, username: str, password: str) -> dict:
        """
        用户登录

        Returns: {user, access_token, refresh_token}
        Raises: ValueError — 用户名或密码错误
        """
        user = self.repo.find_by_username(username)
        if not user:
            raise ValueError("用户名或密码错误")

        if not self.verify_password(password, user["password_hash"]):
            raise ValueError("用户名或密码错误")

        if not user.get("is_active", True):
            raise ValueError("账户已被禁用")

        # 更新最后登录时间
        self.repo.update_last_login(user["id"])

        # 签发令牌
        access_token = self.create_access_token(user["id"], user["username"], user.get("role", "user"))
        refresh_token = self.create_refresh_token(user["id"])

        # 返回不含密码的用户信息
        safe_user = {k: v for k, v in user.items() if k != "password_hash"}
        logger.info("用户登录: %s (%s)", username, user["id"])
        return {
            "user": safe_user,
            "access_token": access_token,
            "refresh_token": refresh_token,
        }

    def refresh(self, refresh_token: str) -> dict:
        """
        刷新令牌

        Returns: {access_token, refresh_token}
        Raises: ValueError — 无效的 refresh token
        """
        payload = self.decode_token(refresh_token)
        if not payload or payload.get("type") != "refresh":
            raise ValueError("无效的刷新令牌")

        user_id = payload["sub"]
        user = self.repo.find_by_id(user_id)
        if not user or not user.get("is_active", True):
            raise ValueError("用户不存在或已禁用")

        access_token = self.create_access_token(user["id"], user["username"], user.get("role", "user"))
        new_refresh = self.create_refresh_token(user_id)

        return {
            "access_token": access_token,
            "refresh_token": new_refresh,
        }

    def get_current_user(self, token: str) -> Optional[dict]:
        """从 JWT 解析当前用户"""
        payload = self.decode_token(token)
        if not payload or payload.get("type") != "access":
            return None

        user_id = payload.get("sub")
        if not user_id:
            return None

        return self.repo.find_by_id(user_id)


# 全局单例
_auth_service: Optional[AuthService] = None


def get_auth_service() -> AuthService:
    global _auth_service
    if _auth_service is None:
        _auth_service = AuthService()
    return _auth_service
