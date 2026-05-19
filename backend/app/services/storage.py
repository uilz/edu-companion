"""
对话数据存储引擎

支持两种后端:
- JSON 文件 (默认)
- PostgreSQL (设置 USE_PG_STORAGE=true)

通过统一接口 (load/save) 对外暴露。
"""

from __future__ import annotations

import hashlib
import os
from pathlib import Path
from threading import Lock

from app.schemas.conversation import UserData


class JsonStorageEngine:
    """JSON 文件存储引擎，线程安全的用户数据持久化"""

    def __init__(self, base_dir: str = "~/.companion/data") -> None:
        self.base_dir = Path(os.path.expanduser(base_dir))
        self._locks: dict[str, Lock] = {}
        self._cache: dict[str, UserData] = {}
        self._versions: dict[str, int] = {}  # ETag version counters
        self._etags: dict[str, str] = {}      # computed ETag hashes

    def _get_lock(self, user_id: str) -> Lock:
        if user_id not in self._locks:
            self._locks[user_id] = Lock()
        return self._locks[user_id]

    def _get_path(self, user_id: str) -> Path:
        return self.base_dir / user_id / "userData.json"

    def load(self, user_id: str) -> UserData:
        lock = self._get_lock(user_id)
        with lock:
            if user_id in self._cache:
                return self._cache[user_id]
            path = self._get_path(user_id)
            if path.exists():
                with open(path, "r", encoding="utf-8") as f:
                    data = UserData.model_validate_json(f.read())
            else:
                data = UserData(user_id=user_id)
            self._cache[user_id] = data
            return data

    def save(self, user_id: str, data: UserData) -> None:
        lock = self._get_lock(user_id)
        with lock:
            path = self._get_path(user_id)
            path.parent.mkdir(parents=True, exist_ok=True)
            json_str = data.model_dump_json(indent=2, exclude_none=True)
            tmp_path = path.with_suffix(".tmp")
            with open(tmp_path, "w", encoding="utf-8") as f:
                f.write(json_str)
            tmp_path.replace(path)
            self._cache[user_id] = data
            # Bump version → invalidates ETag
            self._versions[user_id] = self._versions.get(user_id, 0) + 1
            self._etags.pop(user_id, None)

    def get_etag(self, user_id: str) -> str:
        """Return a stable ETag for the current user data state."""
        lock = self._get_lock(user_id)
        with lock:
            version = self._versions.get(user_id, 0)
            return f'W/"{user_id}:{version}"'


def _get_storage():
    """根据环境变量选择存储后端"""
    use_pg = os.environ.get("USE_PG_STORAGE", "").lower() in ("1", "true", "yes")
    if use_pg:
        from app.services.pg_storage import pg_storage
        return pg_storage
    return JsonStorageEngine()


# 全局单例 (所有 import 方透明使用)
storage = _get_storage()
