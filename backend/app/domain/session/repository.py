"""Session Repository — 轻量内存存储。

V1 中 Session 是短生命周期对象（20-90min），使用内存存储。
Growth / Reflection / Memory 通过 EventBus 异步持久化。
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.domain.session.models import Session


class SessionRepository:
    """Session 内存仓库。"""

    def __init__(self):
        self._store: dict[str, Session] = {}

    def get(self, session_id: str) -> Session | None:
        """按 ID 获取 Session。"""
        return self._store.get(session_id)

    def list_by_learner(self, learner_id: str, limit: int = 20) -> list[Session]:
        """获取 Learner 最近的 Session 列表。"""
        sessions = [
            s for s in self._store.values()
            if s.learner_id == learner_id
        ]
        sessions.sort(key=lambda s: s.started_at, reverse=True)
        return sessions[:limit]

    def list_active_by_learner(self, learner_id: str) -> list[Session]:
        """获取 Learner 当前活跃的 Session。"""
        return [
            s for s in self._store.values()
            if s.learner_id == learner_id and s.status == "active"
        ]

    def save(self, session: Session) -> None:
        """保存 Session（新增或覆盖）。"""
        self._store[session.id] = session

    def delete(self, session_id: str) -> None:
        """删除 Session。"""
        self._store.pop(session_id, None)


# 模块级单例
_session_repo: SessionRepository | None = None


def get_session_repo() -> SessionRepository:
    global _session_repo
    if _session_repo is None:
        _session_repo = SessionRepository()
    return _session_repo
