"""
认证网关独立认证服务
不依赖后端任何模块
"""
from __future__ import annotations

from auth_app.jwt_service import get_jwt_service, JWTService
from auth_app.user_repo import get_user_repo, UserRepo, hash_password, verify_password


class AuthService:
    """独立认证业务逻辑"""

    def __init__(self):
        self.jwt: JWTService = get_jwt_service()
        self.repo: UserRepo = get_user_repo()

    def register(self, username: str, password: str, email: str = "", display_name: str = "") -> dict:
        # 用户名统一转小写，避免大小写重复
        username = username.strip().lower()
        if not username:
            raise ValueError("用户名不能为空")

        existing = self.repo.find_by_username(username)
        if existing:
            raise ValueError(f"用户名 {username} 已存在")

        password_hash = hash_password(password)
        user = self.repo.create(
            username=username,
            password_hash=password_hash,
            email=email,
            display_name=display_name or username,
        )

        access_token = self.jwt.create_access_token(user["id"], user["username"], user.get("role", "user"))
        refresh_token = self.jwt.create_refresh_token(user["id"])

        safe_user = {k: v for k, v in user.items() if k != "password_hash"}
        return {
            "user": safe_user,
            "access_token": access_token,
            "refresh_token": refresh_token,
        }

    def login(self, username: str, password: str) -> dict:
        # 登录时同样转小写匹配
        username = username.strip().lower()
        user = self.repo.find_by_username(username)
        if not user:
            raise ValueError("用户名或密码错误")

        if not verify_password(password, user["password_hash"]):
            raise ValueError("用户名或密码错误")

        self.repo.update_last_login(user["id"])

        access_token = self.jwt.create_access_token(user["id"], user["username"], user.get("role", "user"))
        refresh_token = self.jwt.create_refresh_token(user["id"])

        safe_user = {k: v for k, v in user.items() if k != "password_hash"}
        return {
            "user": safe_user,
            "access_token": access_token,
            "refresh_token": refresh_token,
        }

    def login_by_email(self, email: str, password: str) -> dict:
        email = email.strip().lower()
        user = self.repo.find_by_email(email)
        if not user:
            raise ValueError("邮箱或密码错误")

        if not verify_password(password, user["password_hash"]):
            raise ValueError("邮箱或密码错误")

        self.repo.update_last_login(user["id"])

        access_token = self.jwt.create_access_token(user["id"], user["username"], user.get("role", "user"))
        refresh_token = self.jwt.create_refresh_token(user["id"])

        safe_user = {k: v for k, v in user.items() if k != "password_hash"}
        return {
            "user": safe_user,
            "access_token": access_token,
            "refresh_token": refresh_token,
        }

    def refresh(self, refresh_token: str) -> dict:
        user_id = self.jwt.verify_refresh_token(refresh_token)
        if not user_id:
            raise ValueError("无效的刷新令牌")

        user = self.repo.find_by_id(user_id)
        if not user:
            raise ValueError("用户不存在")

        access_token = self.jwt.create_access_token(user["id"], user["username"], user.get("role", "user"))
        new_refresh_token = self.jwt.create_refresh_token(user["id"])

        return {
            "access_token": access_token,
            "refresh_token": new_refresh_token,
        }

    def get_current_user(self, token: str) -> dict | None:
        return self.jwt.verify_token(token)


_auth_service: AuthService | None = None


def get_auth_service() -> AuthService:
    global _auth_service
    if _auth_service is None:
        _auth_service = AuthService()
    return _auth_service
