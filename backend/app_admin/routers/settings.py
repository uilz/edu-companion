"""系统设置 — super_admin 权限

GET    /config                  获取系统配置（环境变量快照）
GET    /db-status               数据库连接状态
GET    /services                各服务运行状态
GET    /security/config         获取安全配置（注册/登录开关）
PUT    /security/config         更新安全配置
GET    /security/ip-controls    列出 IP 管控
POST   /security/ip-controls    添加 IP 管控
DELETE /security/ip-controls/{id}  删除 IP 管控
GET    /security/cooling        获取攻击冷却状态
DELETE /security/cooling/{ip}   解除 IP 冷却
"""
from __future__ import annotations

import logging
import os

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request

from app_admin.deps import require_role

logger = logging.getLogger(__name__)

router = APIRouter()

AUTH_GATEWAY_URL = os.getenv("AUTH_GATEWAY_URL", "http://127.0.0.1:18001")


def _repo():
    from app.services.common import get_admin_repo
    return get_admin_repo()


async def _proxy_to_auth_gateway(path: str, method: str = "GET", body: dict | None = None, token: str = "") -> dict:
    """代理请求到 auth-gateway 的管理 API"""
    url = f"{AUTH_GATEWAY_URL}{path}"
    headers = {"Authorization": f"Bearer {token}"}
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            if method == "GET":
                resp = await client.get(url, headers=headers)
            elif method == "PUT":
                resp = await client.put(url, headers=headers, json=body or {})
            elif method == "POST":
                resp = await client.post(url, headers=headers, json=body or {})
            elif method == "DELETE":
                resp = await client.delete(url, headers=headers)
            else:
                raise HTTPException(status_code=500, detail=f"不支持的 HTTP 方法: {method}")
            if resp.status_code >= 400:
                detail = resp.json().get("detail", str(resp.status_code)) if resp.text else str(resp.status_code)
                raise HTTPException(status_code=resp.status_code, detail=detail)
            return resp.json()
    except httpx.RequestError as e:
        logger.error("auth-gateway 代理请求失败: %s", e)
        raise HTTPException(status_code=503, detail=f"认证网关不可达: {e}")


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


# ═══════════════════════════════════════════════════════════
# 安全管理 — 代理到 auth-gateway 的管理 API
# ═══════════════════════════════════════════════════════════


@router.get("/security/config")
async def get_security_config(request: Request, _: dict = Depends(require_role("super_admin"))):
    """获取安全配置（注册/登录开关）"""
    token = request.headers.get("Authorization", "").replace("Bearer ", "")
    return await _proxy_to_auth_gateway("/api/auth/admin/config", token=token)


@router.put("/security/config")
async def update_security_config(request: Request, _: dict = Depends(require_role("super_admin"))):
    """更新安全配置（注册/登录开关）"""
    token = request.headers.get("Authorization", "").replace("Bearer ", "")
    body = await request.json()
    return await _proxy_to_auth_gateway("/api/auth/admin/config", method="PUT", body=body, token=token)


@router.get("/security/ip-controls")
async def list_ip_controls(request: Request, _: dict = Depends(require_role("super_admin"))):
    """列出 IP 黑白名单"""
    token = request.headers.get("Authorization", "").replace("Bearer ", "")
    return await _proxy_to_auth_gateway("/api/auth/admin/ip-controls", token=token)


@router.post("/security/ip-controls")
async def add_ip_control(request: Request, _: dict = Depends(require_role("super_admin"))):
    """添加 IP 管控"""
    token = request.headers.get("Authorization", "").replace("Bearer ", "")
    body = await request.json()
    return await _proxy_to_auth_gateway("/api/auth/admin/ip-controls", method="POST", body=body, token=token)


@router.delete("/security/ip-controls/{record_id}")
async def delete_ip_control(record_id: int, request: Request, _: dict = Depends(require_role("super_admin"))):
    """删除 IP 管控记录"""
    token = request.headers.get("Authorization", "").replace("Bearer ", "")
    return await _proxy_to_auth_gateway(f"/api/auth/admin/ip-controls/{record_id}", method="DELETE", token=token)


@router.get("/security/cooling")
async def get_cooling_status(request: Request, _: dict = Depends(require_role("super_admin"))):
    """获取攻击冷却状态"""
    token = request.headers.get("Authorization", "").replace("Bearer ", "")
    return await _proxy_to_auth_gateway("/api/auth/admin/cooling", token=token)


@router.delete("/security/cooling/{ip}")
async def remove_cooling(ip: str, request: Request, _: dict = Depends(require_role("super_admin"))):
    """解除某 IP 的冷却状态"""
    token = request.headers.get("Authorization", "").replace("Bearer ", "")
    return await _proxy_to_auth_gateway(f"/api/auth/admin/cooling/{ip}", method="DELETE", token=token)
