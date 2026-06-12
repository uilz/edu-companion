"""
安全增强模块 — Turnstile 验证 / 系统配置 / IP 管控 / 攻击冷却

所有功能独立于业务后端，仅依赖 auth-gateway 自身数据库。
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import time
from dataclasses import dataclass
from typing import Optional

import httpx

from auth_app.database import get_db_instance, DB

logger = logging.getLogger(__name__)

# ═══════════════════════════════════════════════════════════
# 一、Cloudflare Turnstile 验证
# ═══════════════════════════════════════════════════════════

TURNSTILE_SECRET_KEY = os.getenv("TURNSTILE_SECRET_KEY", "")
TURNSTILE_VERIFY_URL = "https://challenges.cloudflare.com/turnstile/v0/siteverify"


async def verify_turnstile_token(token: str, ip: str = "") -> bool:
    """验证 Turnstile 令牌

    当 TURNSTILE_SECRET_KEY 未配置时跳过验证（开发模式）。
    """
    if not TURNSTILE_SECRET_KEY:
        logger.debug("Turnstile 密钥未配置，跳过验证")
        return True

    if not token:
        logger.warning("Turnstile 验证失败: token 为空")
        return False

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(
                TURNSTILE_VERIFY_URL,
                data={
                    "secret": TURNSTILE_SECRET_KEY,
                    "response": token,
                    "remoteip": ip,
                },
            )
            result = resp.json()
            if result.get("success"):
                return True

            error_codes = result.get("error-codes", [])
            logger.warning("Turnstile 验证失败: %s", error_codes)
            return False
    except Exception as e:
        logger.error("Turnstile 验证请求异常: %s", e)
        return False


# ═══════════════════════════════════════════════════════════
# 二、系统配置（注册/登录开关）
# ═══════════════════════════════════════════════════════════


class SystemConfig:
    """系统配置管理 — 存储于 system_config 表 (key-value)

    配置项:
      registration_enabled  — 是否允许新用户注册 (true/false)
      login_enabled         — 是否允许登录 (true/false)
    """

    _table_checked = False

    def __init__(self):
        self._db: DB = get_db_instance()
        self._ensure_table()

    def _ensure_table(self):
        if SystemConfig._table_checked:
            return
        self._db.execute("""
            CREATE TABLE IF NOT EXISTS system_config (
                key         VARCHAR(64) PRIMARY KEY,
                value       TEXT NOT NULL DEFAULT '',
                updated_at  TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
        """)
        # 插入默认值（如不存在）
        defaults = {
            "registration_enabled": "true",
            "login_enabled": "true",
        }
        for k, v in defaults.items():
            row = self._db.fetchone(
                "SELECT key FROM system_config WHERE key = %s", (k,)
            )
            if not row:
                self._db.execute(
                    "INSERT INTO system_config (key, value) VALUES (%s, %s)",
                    (k, v),
                )
        SystemConfig._table_checked = True

    def get(self, key: str, default: str = "") -> str:
        row = self._db.fetchone(
            "SELECT value FROM system_config WHERE key = %s", (key,)
        )
        return row["value"] if row else default

    def set(self, key: str, value: str) -> None:
        self._db.execute(
            """INSERT INTO system_config (key, value, updated_at)
               VALUES (%s, %s, CURRENT_TIMESTAMP)
               ON CONFLICT (key)
               DO UPDATE SET value = %s, updated_at = CURRENT_TIMESTAMP""",
            (key, value, value),
        )

    def get_all(self) -> dict:
        rows = self._db.fetchall("SELECT key, value FROM system_config")
        return {r["key"]: r["value"] for r in rows}

    def is_registration_enabled(self) -> bool:
        return self.get("registration_enabled", "true") == "true"

    def is_login_enabled(self) -> bool:
        return self.get("login_enabled", "true") == "true"


_system_config: Optional[SystemConfig] = None


def get_system_config() -> SystemConfig:
    global _system_config
    if _system_config is None:
        _system_config = SystemConfig()
    return _system_config


# ═══════════════════════════════════════════════════════════
# 三、IP 管控（黑白名单）
# ═══════════════════════════════════════════════════════════


class IPControlManager:
    """IP 黑白名单管理 — 存储于 ip_controls 表"""

    _table_checked = False

    def __init__(self):
        self._db: DB = get_db_instance()
        self._ensure_table()

    def _ensure_table(self):
        if IPControlManager._table_checked:
            return
        self._db.execute("""
            CREATE TABLE IF NOT EXISTS ip_controls (
                id          SERIAL PRIMARY KEY,
                ip          VARCHAR(45) NOT NULL,
                list_type   VARCHAR(10) NOT NULL CHECK (list_type IN ('blacklist', 'whitelist')),
                reason      VARCHAR(256) DEFAULT '',
                is_temp     BOOLEAN DEFAULT FALSE,
                expires_at  TIMESTAMP,
                created_by  VARCHAR(32) DEFAULT '',
                created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(ip, list_type)
            )
        """)
        IPControlManager._table_checked = True

    def is_blacklisted(self, ip: str) -> bool:
        """检查 IP 是否在黑名单中（含临时封禁）"""
        row = self._db.fetchone(
            """SELECT 1 FROM ip_controls
               WHERE ip = %s AND list_type = 'blacklist'
                 AND (expires_at IS NULL OR expires_at > CURRENT_TIMESTAMP)""",
            (ip,),
        )
        return row is not None

    def is_whitelisted(self, ip: str) -> bool:
        """检查 IP 是否在白名单中"""
        row = self._db.fetchone(
            """SELECT 1 FROM ip_controls
               WHERE ip = %s AND list_type = 'whitelist'
                 AND (expires_at IS NULL OR expires_at > CURRENT_TIMESTAMP)""",
            (ip,),
        )
        return row is not None

    def add_blacklist(self, ip: str, reason: str = "", expires_minutes: int = 0, created_by: str = "") -> None:
        """添加 IP 到黑名单

        Args:
            ip: IP 地址
            reason: 原因
            expires_minutes: 过期分钟数（0 = 永久）
            created_by: 创建者
        """
        if expires_minutes > 0:
            self._db.execute(
                """INSERT INTO ip_controls (ip, list_type, reason, is_temp, expires_at, created_by)
                   VALUES (%s, 'blacklist', %s, TRUE, CURRENT_TIMESTAMP + INTERVAL '%s minutes', %s)
                   ON CONFLICT (ip, list_type)
                   DO UPDATE SET reason = %s, is_temp = TRUE,
                       expires_at = CURRENT_TIMESTAMP + INTERVAL '%s minutes',
                       created_by = %s""",
                (ip, reason, str(expires_minutes), created_by,
                 reason, str(expires_minutes), created_by),
            )
        else:
            self._db.execute(
                """INSERT INTO ip_controls (ip, list_type, reason, created_by)
                   VALUES (%s, 'blacklist', %s, %s)
                   ON CONFLICT (ip, list_type)
                   DO UPDATE SET reason = %s, is_temp = FALSE,
                       expires_at = NULL, created_by = %s""",
                (ip, reason, created_by, reason, created_by),
            )

    def add_whitelist(self, ip: str, reason: str = "", created_by: str = "") -> None:
        """添加 IP 到白名单"""
        self._db.execute(
            """INSERT INTO ip_controls (ip, list_type, reason, created_by)
               VALUES (%s, 'whitelist', %s, %s)
               ON CONFLICT (ip, list_type)
               DO UPDATE SET reason = %s, created_by = %s""",
            (ip, reason, created_by, reason, created_by),
        )

    def remove(self, ip: str, list_type: str) -> None:
        """从指定列表中移除 IP"""
        self._db.execute(
            "DELETE FROM ip_controls WHERE ip = %s AND list_type = %s",
            (ip, list_type),
        )

    def list_blacklist(self) -> list[dict]:
        """列出所有有效黑名单"""
        rows = self._db.fetchall(
            """SELECT id, ip, reason, is_temp, expires_at, created_by, created_at
               FROM ip_controls
               WHERE list_type = 'blacklist'
                 AND (expires_at IS NULL OR expires_at > CURRENT_TIMESTAMP)
               ORDER BY created_at DESC"""
        )
        return rows or []

    def list_whitelist(self) -> list[dict]:
        """列出所有白名单"""
        rows = self._db.fetchall(
            """SELECT id, ip, reason, created_by, created_at
               FROM ip_controls
               WHERE list_type = 'whitelist'
               ORDER BY created_at DESC"""
        )
        return rows or []

    def delete_by_id(self, record_id: int) -> bool:
        """通过 ID 删除管控记录"""
        cur = self._db.execute(
            "DELETE FROM ip_controls WHERE id = %s", (record_id,)
        )
        return cur.rowcount > 0

    def cleanup_expired(self) -> int:
        """清理过期记录，返回清理条数"""
        cur = self._db.execute(
            "DELETE FROM ip_controls WHERE expires_at IS NOT NULL AND expires_at <= CURRENT_TIMESTAMP"
        )
        return cur.rowcount if cur else 0


_ip_control_manager: Optional[IPControlManager] = None


def get_ip_control_manager() -> IPControlManager:
    global _ip_control_manager
    if _ip_control_manager is None:
        _ip_control_manager = IPControlManager()
    return _ip_control_manager


# ═══════════════════════════════════════════════════════════
# 四、攻击冷却系统
# ═══════════════════════════════════════════════════════════

@dataclass
class CoolingRecord:
    """单条冷却记录"""
    level: int           # 1=预警(Turnstile强制), 2=封禁
    expires_at: float    # 冷却到期时间戳
    failed_attempts: int  # 冷却期间累计失败次数


class CoolingManager:
    """攻击冷却管理器 — 内存态，按 IP 追踪

    冷却等级:
      Level 0 (正常): 无限制
      Level 1 (预警): 强制 Turnstile 验证
        - 触发: 登录失败 ≥5次/分钟 或 注册 ≥3次/分钟
        - 降级: 攻���停止（窗口内无新增失败）自动回到 Level 0
      Level 2 (封禁): IP 临时封禁 30 分钟
        - 触发: Level 1 期间继续攻击 ≥3次 或 登录失败 ≥15次/分钟
        - 解除: 30 分钟后自动回到 Level 0

    设计:
      - 纯内存，不持久化（重启后冷却重置，合理）
      - 定时过期清理（检查时惰性清理）
    """

    # ── 阈值配置 ──
    # Level 1 触发
    LOGIN_FAIL_THRESHOLD_L1 = 5     # 5 次登录失败/分钟 → L1
    REGISTER_FAIL_THRESHOLD_L1 = 3  # 3 次注册失败/分钟 → L1
    # Level 2 触发
    L1_CONTINUED_ATTACKS = 3        # L1 期间继续攻击 ≥3 次 → L2
    LOGIN_FAIL_THRESHOLD_L2 = 15    # 15 次登录失败/分钟 → L2（绕过 L1 直升）
    # 时间窗口
    WINDOW_SECONDS = 60             # 统计窗口（秒）
    L2_DURATION_MINUTES = 30        # L2 封禁时长（分钟）

    def __init__(self):
        # key: ip, value: (failed_attempts, first_fail_time, cooling)
        self._login_fails: dict[str, tuple[int, float]] = {}
        self._register_fails: dict[str, tuple[int, float]] = {}
        self._l1_fails: dict[str, tuple[int, float]] = {}  # L1 期间累计
        # active cooling states: key: ip, value: CoolingRecord
        self._active_cooling: dict[str, CoolingRecord] = {}

    # ── 登录失败追踪 ──

    def record_login_failure(self, ip: str) -> int:
        """记录一次登录失败，返回当前窗口内失败次数"""
        now = time.time()
        attempts, first_time = self._login_fails.get(ip, (0, now))

        if now - first_time > self.WINDOW_SECONDS:
            self._login_fails[ip] = (1, now)
            return 1

        self._login_fails[ip] = (attempts + 1, first_time)
        return attempts + 1

    def record_register_failure(self, ip: str) -> int:
        """记录一次注册失败，返回当前窗口内失败次数"""
        now = time.time()
        attempts, first_time = self._register_fails.get(ip, (0, now))

        if now - first_time > self.WINDOW_SECONDS:
            self._register_fails[ip] = (1, now)
            return 1

        self._register_fails[ip] = (attempts + 1, first_time)
        return attempts + 1

    def clear_login_fails(self, ip: str) -> None:
        """登录成功，清除失败记录"""
        self._login_fails.pop(ip, None)
        self._l1_fails.pop(ip, None)

    def clear_register_fails(self, ip: str) -> None:
        """注册成功，清除失败记录"""
        self._register_fails.pop(ip, None)

    # ── 冷却状态检查 ──

    def get_cooling_level(self, ip: str) -> int:
        """获取当前冷却等级 (0/1/2)"""
        record = self._active_cooling.get(ip)
        if not record:
            return 0

        if time.time() >= record.expires_at:
            # 冷却到期，自动清除
            self._active_cooling.pop(ip, None)
            self._login_fails.pop(ip, None)
            self._register_fails.pop(ip, None)
            self._l1_fails.pop(ip, None)
            return 0

        return record.level

    def _set_cooling(self, ip: str, level: int, duration_minutes: int) -> None:
        """设置冷却状态"""
        now = time.time()
        self._active_cooling[ip] = CoolingRecord(
            level=level,
            expires_at=now + duration_minutes * 60,
            failed_attempts=0,
        )

    def check_and_apply(self, ip: str) -> int:
        """检查并自动应用冷却策略，返回当前冷却等级 (0/1/2)

        每次请求敏感端点时调用此方法。
        """
        # 先检查是否有活跃冷却
        current_level = self.get_cooling_level(ip)
        if current_level > 0:
            return current_level

        # 检查登录失败次数 → Level 1
        now = time.time()
        login_attempts, login_first = self._login_fails.get(ip, (0, now))
        if now - login_first <= self.WINDOW_SECONDS:
            if login_attempts >= self.LOGIN_FAIL_THRESHOLD_L2:
                # 直升 Level 2
                logger.warning("冷却升级 L2: ip=%s 登录失败 %d 次", ip, login_attempts)
                self._set_cooling(ip, 2, self.L2_DURATION_MINUTES)
                # 同步加入 IP 黑名单
                try:
                    mgr = get_ip_control_manager()
                    mgr.add_blacklist(ip, reason=f"冷却 L2: 短时内登录失败 {login_attempts} 次", expires_minutes=self.L2_DURATION_MINUTES)
                except Exception as e:
                    logger.error("IP 黑名单写入失败: %s", e)
                return 2
            elif login_attempts >= self.LOGIN_FAIL_THRESHOLD_L1:
                # 检查 Level 1 期间继续攻击次数
                l1_attempts, l1_first = self._l1_fails.get(ip, (0, now))
                if now - l1_first > self.WINDOW_SECONDS:
                    self._l1_fails[ip] = (1, now)
                else:
                    self._l1_fails[ip] = (l1_attempts + 1, l1_first)

                if l1_attempts + 1 >= self.L1_CONTINUED_ATTACKS:
                    # 升级 Level 2
                    logger.warning("冷却升级 L2: ip=%s L1 期间继续攻击 %d 次", ip, l1_attempts + 1)
                    self._set_cooling(ip, 2, self.L2_DURATION_MINUTES)
                    try:
                        mgr = get_ip_control_manager()
                        mgr.add_blacklist(ip, reason=f"冷却 L2: L1 期间持续攻击", expires_minutes=self.L2_DURATION_MINUTES)
                    except Exception as e:
                        logger.error("IP 黑名单写入失败: %s", e)
                    return 2

                logger.info("冷却触发 L1: ip=%s 登录失败 %d 次", ip, login_attempts)
                self._set_cooling(ip, 1, 1)  # 1 分钟窗口
                return 1

        # 检查注册失败次数 → Level 1
        reg_attempts, reg_first = self._register_fails.get(ip, (0, now))
        if now - reg_first <= self.WINDOW_SECONDS:
            if reg_attempts >= self.REGISTER_FAIL_THRESHOLD_L1:
                logger.info("冷却触发 L1: ip=%s 注册失败 %d 次", ip, reg_attempts)
                self._set_cooling(ip, 1, 1)
                return 1

        return 0

    def remove_cooling(self, ip: str) -> None:
        """手动解除冷却"""
        self._active_cooling.pop(ip, None)
        self._login_fails.pop(ip, None)
        self._register_fails.pop(ip, None)
        self._l1_fails.pop(ip, None)

    def get_status(self) -> dict:
        """获取当前冷却状态（管理员监控用）"""
        now = time.time()
        active = {}
        for ip, record in self._active_cooling.items():
            remaining = max(0, int(record.expires_at - now))
            if remaining > 0:
                active[ip] = {
                    "level": record.level,
                    "remaining_seconds": remaining,
                    "failed_attempts": record.failed_attempts,
                }
        # 当前正在受监控但尚未触发冷却的 IP
        monitored = {}
        for ip, (attempts, first_time) in self._login_fails.items():
            if now - first_time <= self.WINDOW_SECONDS and attempts >= 2:
                monitored[ip] = {
                    "type": "login",
                    "attempts": attempts,
                    "window_remaining": max(0, int(self.WINDOW_SECONDS - (now - first_time))),
                }
        for ip, (attempts, first_time) in self._register_fails.items():
            if now - first_time <= self.WINDOW_SECONDS and attempts >= 2:
                monitored[ip] = {
                    "type": "register",
                    "attempts": attempts,
                    "window_remaining": max(0, int(self.WINDOW_SECONDS - (now - first_time))),
                }
        return {
            "active_cooling": active,
            "monitored_ips": monitored,
            "config": {
                "login_fail_L1": self.LOGIN_FAIL_THRESHOLD_L1,
                "register_fail_L1": self.REGISTER_FAIL_THRESHOLD_L1,
                "login_fail_L2": self.LOGIN_FAIL_THRESHOLD_L2,
                "l1_continued_to_l2": self.L1_CONTINUED_ATTACKS,
                "l2_duration_minutes": self.L2_DURATION_MINUTES,
                "window_seconds": self.WINDOW_SECONDS,
            },
        }


_cooling_manager: Optional[CoolingManager] = None


def get_cooling_manager() -> CoolingManager:
    global _cooling_manager
    if _cooling_manager is None:
        _cooling_manager = CoolingManager()
    return _cooling_manager
