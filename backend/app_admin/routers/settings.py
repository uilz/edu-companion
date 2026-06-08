"""系统设置 — super_admin 权限

GET    /config        获取系统配置（环境变量快照）
GET    /env           获取关键环境变量（脱敏）
GET    /db-status     数据库连接状态
GET    /services      各服务运行状态
"""
from __future__ import annotations

import logging
import os

from fastapi import APIRouter, Depends

from app_admin.deps import require_role

logger = logging.getLogger(__name__)

router = APIRouter()


def _repo():
    from app.services.common import get_admin_repo
    return get_admin_repo()


@router.get("/config")
async def get_config(_: dict = Depends(require_role("super_admin"))):
    """获取系统配置快照"""
    return {
        "service": "app_admin",
        "version": "1.0.0",
        "python_version": __import__("sys").version,
        "pid": os.getpid(),
        "cwd": os.getcwd(),
    }


@router.get("/env")
async def get_env(_: dict = Depends(require_role("super_admin"))):
    """获取关键环境变量（脱敏显示）"""
    keys = [
        "JWT_SECRET", "JWT_ALGORITHM",
        "DB_HOST", "DB_PORT", "DB_NAME", "DB_USER",
        "AUTH_GATEWAY_URL",
    ]
    result = {}
    for k in keys:
        val = os.getenv(k, "")
        # 脱敏
        if k == "JWT_SECRET" and val:
            val = val[:8] + "***" + val[-4:] if len(val) > 14 else "***"
        if "PASSWORD" in k.upper() and val:
            val = val[:4] + "***" if len(val) > 8 else "***"
        result[k] = val or "(未设置)"

    # 检查配置文件
    env_files = {}
    for path in [
        "/home/deploy/edu-companion/backend/.env",
        "/home/deploy/edu-companion/auth-gateway/config/.env",
    ]:
        env_files[path] = os.path.exists(path)
    result["_env_files"] = env_files

    return {"env": result}


@router.get("/db-status")
async def db_status(_: dict = Depends(require_role("super_admin"))):
    """数据库连接状态"""
    repo = _repo()
    if not repo:
        return {"connected": False, "error": "AdminRepository 不可用"}

    try:
        rows = repo.query("SELECT 1 AS ok")
        return {
            "connected": bool(rows),
            "version_rows": rows,
        }
    except Exception as e:
        return {"connected": False, "error": str(e)}


@router.get("/services")
async def services(_: dict = Depends(require_role("super_admin"))):
    """各服务运行状态"""
    import subprocess
    import socket

    services = {}

    # 1. admin 自身
    services["app_admin"] = {"port": 8001, "status": "running", "pid": os.getpid()}

    # 2. auth-gateway (18001)
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        s.settimeout(2)
        services["auth_gateway"] = {
            "port": 18001,
            "status": "running" if s.connect_ex(("127.0.0.1", 18001)) == 0 else "unreachable",
        }
    finally:
        s.close()

    # 3. main backend (8000)
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        s.settimeout(2)
        services["main_backend"] = {
            "port": 8000,
            "status": "running" if s.connect_ex(("127.0.0.1", 8000)) == 0 else "unreachable",
        }
    finally:
        s.close()

    # 4. PostgreSQL
    try:
        repo = _repo()
        if repo:
            rows = repo.query("SELECT 1 AS ping")
            services["postgres"] = {"status": "running" if rows else "error"}
    except Exception:
        services["postgres"] = {"status": "unreachable"}

    return {"services": services}
