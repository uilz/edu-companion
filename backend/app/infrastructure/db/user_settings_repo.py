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

    # ── Task #84: 统一偏好读写 (typed) ──

    # 顶层 key 命名空间 (SSOT)
    NS_LLM_CONFIG = "llm_config"
    NS_LLM_BEHAVIOR = "llm_behavior"     # temperature / max_tokens / system_prompt
    NS_UI = "ui"                          # theme / style
    NS_LEARNING = "learning"              # socratic_mode / socratic_follow_up / auto_scroll_on_load
    NS_NOTIFICATION = "notification"      # 通知偏好
    NS_VIEW = "view"                      # 项目详情页视图偏好 (Task #89): view.{project_id}

    # 项目视图白名单 (Task #89)
    PROJECT_VIEW_NAMES: tuple[str, ...] = (
        "document", "outline", "kanban", "knowledge", "activity",
    )

    def get_user_preferences(self, user_id: str) -> dict:
        """读取所有用户偏好 (D16 兼容) — 返回顶层 dict."""
        return self.get_all(user_id)

    def get_llm_behavior(self, user_id: str) -> dict:
        """读取 LLM 行为参数 (temperature / max_tokens / system_prompt)."""
        return self.get_key(user_id, self.NS_LLM_BEHAVIOR, default={
            "temperature": 0.7,
            "max_tokens": 2048,
            "system_prompt": "",
        })

    def set_llm_behavior(self, user_id: str, behavior: dict) -> dict:
        """写入 LLM 行为参数 (合并写, 缺省补全)."""
        current = self.get_llm_behavior(user_id)
        merged = {**current, **{k: v for k, v in behavior.items() if v is not None}}
        merged.setdefault("temperature", 0.7)
        merged.setdefault("max_tokens", 2048)
        merged.setdefault("system_prompt", "")
        # 范围校验
        try:
            t = float(merged["temperature"])
            merged["temperature"] = max(0.0, min(2.0, t))
        except (TypeError, ValueError):
            merged["temperature"] = 0.7
        try:
            m = int(merged["max_tokens"])
            merged["max_tokens"] = max(64, min(8192, m))
        except (TypeError, ValueError):
            merged["max_tokens"] = 2048
        if not isinstance(merged["system_prompt"], str):
            merged["system_prompt"] = str(merged["system_prompt"])[:4000]
        else:
            merged["system_prompt"] = merged["system_prompt"][:4000]
        self.set_key(user_id, self.NS_LLM_BEHAVIOR, merged)
        return merged

    def get_ui_prefs(self, user_id: str) -> dict:
        """读取 UI 偏好 (theme / style / serif_font)."""
        return self.get_key(user_id, self.NS_UI, default={
            "theme": "dark",
            "style": "professional",
            "serif_font": False,
        })

    def set_ui_prefs(self, user_id: str, prefs: dict) -> dict:
        """写入 UI 偏好 (合并写)."""
        current = self.get_ui_prefs(user_id)
        merged = {**current, **{k: v for k, v in prefs.items() if v is not None}}
        if merged.get("theme") not in ("dark", "light"):
            merged["theme"] = current.get("theme", "dark")
        if merged.get("style") not in ("professional", "playful", "knowledge", "soft-data", "gamified"):
            merged["style"] = current.get("style", "professional")
        self.set_key(user_id, self.NS_UI, merged)
        return merged

    def get_learning_prefs(self, user_id: str) -> dict:
        """读取学习偏好 (socratic / auto_scroll)."""
        return self.get_key(user_id, self.NS_LEARNING, default={
            "socratic_mode": False,
            "socratic_follow_up_mode": False,
            "auto_scroll_on_load": True,
        })

    def set_learning_prefs(self, user_id: str, prefs: dict) -> dict:
        """写入学习偏好 (合并写)."""
        current = self.get_learning_prefs(user_id)
        merged = {**current, **{k: v for k, v in prefs.items() if v is not None}}
        for k in ("socratic_mode", "socratic_follow_up_mode", "auto_scroll_on_load", "today_quote_enabled"):
            if k in merged and not isinstance(merged[k], bool):
                merged[k] = bool(merged[k])
        self.set_key(user_id, self.NS_LEARNING, merged)
        return merged

    # ── Task #89: 项目视图偏好 (per-user × per-project) ──

    def get_view_pref(self, user_id: str, project_id: str, default: str = "document") -> str:
        """读取项目详情页视图偏好。

        存储结构: settings["view"][project_id] = "document" | "outline" | "kanban" | "knowledge" | "activity"
        """
        all_views = self.get_key(user_id, self.NS_VIEW, default={})
        if not isinstance(all_views, dict):
            return default
        view = all_views.get(project_id)
        if view in self.PROJECT_VIEW_NAMES:
            return view
        return default

    def set_view_pref(self, user_id: str, project_id: str, view: str) -> str:
        """写入项目详情页视图偏好（合并写）。非法值会抛 ValueError。"""
        if view not in self.PROJECT_VIEW_NAMES:
            raise ValueError(
                f"view 必须是 {self.PROJECT_VIEW_NAMES} 之一, 当前: {view}"
            )
        all_views = self.get_key(user_id, self.NS_VIEW, default={})
        if not isinstance(all_views, dict):
            all_views = {}
        all_views[project_id] = view
        self.set_key(user_id, self.NS_VIEW, all_views)
        return view


# ── 全局单例 ──

_settings_repo: Optional[UserSettingsRepo] = None


def get_user_settings_repo() -> UserSettingsRepo:
    """获取 UserSettingsRepo 单例"""
    global _settings_repo
    if _settings_repo is None:
        _settings_repo = UserSettingsRepo()
    return _settings_repo