"""
JSON 文件存储引擎
线程安全的用户数据持久化，使用文件锁 + 内存缓存
"""

from __future__ import annotations

import os
from pathlib import Path
from threading import Lock

from app.schemas.conversation import UserData


class StorageEngine:
    """JSON 文件存储引擎，支持线程安全的读写操作"""

    def __init__(self, base_dir: str = "~/.companion/data") -> None:
        self.base_dir = Path(os.path.expanduser(base_dir))
        self._locks: dict[str, Lock] = {}
        self._cache: dict[str, UserData] = {}

    def _get_lock(self, user_id: str) -> Lock:
        if user_id not in self._locks:
            self._locks[user_id] = Lock()
        return self._locks[user_id]

    def _get_path(self, user_id: str) -> Path:
        return self.base_dir / user_id / "userData.json"

    def load(self, user_id: str) -> UserData:
        """从磁盘加载用户数据，优先返回缓存"""
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
        """保存用户数据到磁盘并更新缓存"""
        lock = self._get_lock(user_id)
        with lock:
            path = self._get_path(user_id)
            path.parent.mkdir(parents=True, exist_ok=True)
            with open(path, "w", encoding="utf-8") as f:
                f.write(data.model_dump_json(indent=2))
            self._cache[user_id] = data

    def get_or_create(self, user_id: str) -> UserData:
        """加载或创建新的用户数据"""
        return self.load(user_id)

    def invalidate(self, user_id: str) -> None:
        """使缓存失效"""
        self._cache.pop(user_id, None)


# 全局单例
storage = StorageEngine()
