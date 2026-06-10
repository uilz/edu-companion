"""
认证网关独立 JWT 服务
不依赖后端任何模块
"""
from __future__ import annotations

import os
import time
import jwt
from typing import Optional


class JWTService:
    """独立 JWT 令牌管理"""

    def __init__(self):
        self.secret = os.getenv("JWT_SECRET")
        if not self.secret:
            raise RuntimeError("JWT_SECRET environment variable is not set")
        self.algorithm = os.getenv("JWT_ALGORITHM", "HS256")
        self.access_expire = int(os.getenv("JWT_ACCESS_EXPIRE_HOURS", "24")) * 3600
        self.refresh_expire = int(os.getenv("JWT_REFRESH_EXPIRE_DAYS", "7")) * 86400

    def create_access_token(self, user_id: str, username: str, role: str = "user", token_version: int = 0) -> str:
        now = int(time.time())
        payload = {
            "sub": user_id,
            "username": username,
            "role": role,
            "token_version": token_version,
            "exp": now + self.access_expire,
            "iat": now,
            "type": "access",
        }
        return jwt.encode(payload, self.secret, algorithm=self.algorithm)

    def create_refresh_token(self, user_id: str) -> str:
        now = int(time.time())
        payload = {
            "sub": user_id,
            "exp": now + self.refresh_expire,
            "iat": now,
            "type": "refresh",
        }
        return jwt.encode(payload, self.secret, algorithm=self.algorithm)

    def verify_token(self, token: str) -> Optional[dict]:
        try:
            payload = jwt.decode(token, self.secret, algorithms=[self.algorithm])
            if payload.get("type") != "access":
                return None
            
            user_id = payload["sub"]
            token_version = payload.get("token_version", 0)
            
            # 验证 token_version 是否匹配当前 DB 记录
            from auth_app.user_repo import get_user_repo
            current_version = get_user_repo().get_token_version(user_id)
            if token_version != current_version:
                return None  # token 已过期（被强制下线）
            
            return {
                "user_id": user_id,
                "username": payload.get("username", ""),
                "role": payload.get("role", "user"),
            }
        except jwt.ExpiredSignatureError:
            return None
        except jwt.InvalidTokenError:
            return None
        return None

    def verify_refresh_token(self, token: str) -> Optional[str]:
        try:
            payload = jwt.decode(token, self.secret, algorithms=[self.algorithm])
            if payload.get("type") == "refresh":
                return payload["sub"]
        except jwt.ExpiredSignatureError:
            return None
        except jwt.InvalidTokenError:
            return None
        return None


_jwt_service: Optional[JWTService] = None


def get_jwt_service() -> JWTService:
    global _jwt_service
    if _jwt_service is None:
        _jwt_service = JWTService()
    return _jwt_service
