"""
用户设置统一仓储 (D16)

统一 user_llm_configs + secretary_prefs + policy_memory + UI 偏好
到 user_settings(user_id, settings_jsonb) 表。
"""

from __future__ import annotations

import json
import logging
from typing import Any, Optional

logger = logging.getLogger(__name__)


class UserSettingsRepo:
    """用户设置统一数据仓储"""

    def __init__(self):
        from app.infrastructure.db.database import get_db
        self._db = get_db()

    def ensure_table(self) -> None:
        """确保 user_settings 表存在"""
        self._db.execute("""
            CREATE TABLE IF NOT EXISTS user_settings (
                user_id         TEXT NOT NULL PRIMARY KEY,
                settings_jsonb  JSONB NOT NULL DEFAULT '{}',
                updated_at      TIMESTAMPTZ DEFAULT NOW()
            )
        """)

    # ── 全量读写 ──

    def get_all(self, user_id: str) -> dict:
        """获取用户全部设置"""
        self.ensure_table()
        row = self._db.fetchone(
            "SELECT settings_jsonb FROM user_settings WHERE user_id = %s",
            (user_id,),
        )
        if not row or not row.get("settings_jsonb"):
            return {}
        raw = row["settings_jsonb"]
        if isinstance(raw, dict):
            return raw
        try:
            return json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            return {}

    def set_all(self, user_id: str, settings: dict) -> None:
        """全量写入用户设置"""
        self.ensure_table()
        self._db.execute(
            """INSERT INTO user_settings (user_id, settings_jsonb, updated_at)
               VALUES (%s, %s, NOW())
               ON CONFLICT (user_id) DO UPDATE SET
                   settings_jsonb = EXCLUDED.settings_jsonb,
                   updated_at = NOW()""",
            (user_id, json.dumps(settings, ensure_ascii=False)),
        )

    # ── 按 key 读写 ──

    def get_key(self, user_id: str, key: str, default: Any = None) -> Any:
        """读取某个设置项"""
        settings = self.get_all(user_id)
        return settings.get(key, default)

    def set_key(self, user_id: str, key: str, value: Any) -> None:
        """写入某个设置项（merge 写入）"""
        settings = self.get_all(user_id)
        settings[key] = value
        self.set_all(user_id, settings)

    def set_multiple(self, user_id: str, updates: dict) -> None:
        """批量写入多个设置项（merge 写入）"""
        settings = self.get_all(user_id)
        settings.update(updates)
        self.set_all(user_id, settings)

    # ── 删除 ──

    def delete_key(self, user_id: str, key: str) -> None:
        """删除某个设置项"""
        settings = self.get_all(user_id)
        settings.pop(key, None)
        self.set_all(user_id, settings)

    def delete(self, user_id: str) -> None:
        """删除用户全部设置"""
        self._db.execute(
            "DELETE FROM user_settings WHERE user_id = %s",
            (user_id,),
        )


# ── 全局单例 ──

_settings_repo: Optional[UserSettingsRepo] = None


def get_user_settings_repo() -> UserSettingsRepo:
    """获取 UserSettingsRepo 单例"""
    global _settings_repo
    if _settings_repo is None:
        _settings_repo = UserSettingsRepo()
    return _settings_repo