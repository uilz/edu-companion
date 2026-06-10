"""
用户自定义 LLM 配置仓储 — user_llm_configs 表的 CRUD

存储用户自定义的 API 端点、Key（加密）、模型名称。
"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Optional

from app.infrastructure.crypto import encrypt, decrypt

logger = logging.getLogger(__name__)


class UserLlmConfigRepo:
    """用户 LLM 配置数据仓储"""

    def __init__(self):
        from app.db.database import get_db
        self._db = get_db()

    def ensure_table(self) -> None:
        """确保 user_llm_configs 表存在"""
        self._db.execute("""
            CREATE TABLE IF NOT EXISTS user_llm_configs (
                user_id          TEXT PRIMARY KEY,
                api_base         TEXT DEFAULT '',
                api_key_encrypted TEXT DEFAULT '',
                model_name       TEXT DEFAULT '',
                is_active        BOOLEAN DEFAULT TRUE,
                updated_at       TIMESTAMP NOT NULL DEFAULT NOW()
            )
        """)

    def get(self, user_id: str) -> Optional[dict]:
        """获取用户 LLM 配置（解密 api_key）"""
        row = self._db.fetchone(
            "SELECT user_id, api_base, api_key_encrypted, model_name, is_active, updated_at "
            "FROM user_llm_configs WHERE user_id = %s",
            (user_id,),
        )
        if not row:
            return None
        # 解密 api_key
        row["api_key"] = decrypt(row.get("api_key_encrypted", ""))
        row.pop("api_key_encrypted", None)
        return row

    def save(self, user_id: str, api_base: str, api_key: str, model_name: str) -> None:
        """保存用户 LLM 配置（加密 api_key）"""
        encrypted = encrypt(api_key) if api_key else ""
        now = datetime.now().isoformat()
        self._db.execute(
            """INSERT INTO user_llm_configs (user_id, api_base, api_key_encrypted, model_name, updated_at)
               VALUES (%s, %s, %s, %s, %s)
               ON CONFLICT (user_id) DO UPDATE SET
                   api_base = EXCLUDED.api_base,
                   api_key_encrypted = EXCLUDED.api_key_encrypted,
                   model_name = EXCLUDED.model_name,
                   is_active = TRUE,
                   updated_at = EXCLUDED.updated_at""",
            (user_id, api_base, encrypted, model_name, now),
        )

    def delete(self, user_id: str) -> None:
        """删除用户 LLM 配置（重置为默认）"""
        self._db.execute(
            "DELETE FROM user_llm_configs WHERE user_id = %s",
            (user_id,),
        )

    def is_configured(self, user_id: str) -> bool:
        """检查用户是否已配置自定义 LLM"""
        row = self._db.fetchone(
            "SELECT 1 FROM user_llm_configs WHERE user_id = %s AND is_active = TRUE AND model_name != ''",
            (user_id,),
        )
        return row is not None


# 全局实例
_config_repo: Optional[UserLlmConfigRepo] = None


def get_user_llm_config_repo() -> UserLlmConfigRepo:
    global _config_repo
    if _config_repo is None:
        _config_repo = UserLlmConfigRepo()
        _config_repo.ensure_table()
    return _config_repo