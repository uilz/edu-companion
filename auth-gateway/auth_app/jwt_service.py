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
        self.secret = os.getenv("JWT_SECRET", "auth-gateway-secret-key-2026")
        self.algorithm = os.getenv("JWT_ALGORITHM", "HS256")
        self.access_expire = int(os.getenv("JWT_ACCESS_EXPIRE_HOURS", "24")) * 3600
        self.refresh_expire = int(os.getenv("JWT_REFRESH_EXPIRE_DAYS", "7")) * 86400

    def create_access_token(self, user_id: str, username: str, role: str = "user") -> str:
        now = int(time.time())
        payload = {
            "sub": user_id,
            "username": username,
            "role": role,
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
            if payload.get("type") == "access":
                return {
                    "user_id": payload["sub"],
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
