"""Practice 模块工作单元（Unit of Work）。

封装一次练习命令所需的 DB Session、聚合根仓储与传统数据访问。
职责：
1. 管理 SQLAlchemy Session 生命周期与事务边界；
2. 提供聚合根仓储；
3. 提供底层 raw SQL db 访问（兼容现有 session_repository）。
"""

from __future__ import annotations

from typing import Any

from app.infrastructure.db.database import get_db
from app.domain.practice.repository import PracticeAggregateRepository


class PracticeUnitOfWork:
    """练习命令工作单元。

    使用示例：
        with PracticeUnitOfWork() as uow:
            aggregate = uow.aggregates.get(session_id)
            ...
            uow.commit()
    """

    def __init__(self, db_session=None, sql_db=None):
        """参数均为可选；不传时从全局获取。

        db_session: SQLAlchemy ORM Session，用于聚合根快照/命令记录。
        sql_db: 兼容现有 session_repository 的 raw SQL db 对象。
        """
        self._db_session = db_session
        self._sql_db = sql_db
        self._owns_session = db_session is None
        self._owns_sql_db = sql_db is None
        self._aggregates: PracticeAggregateRepository | None = None

    @property
    def session(self):
        if self._db_session is None:
            from app.infrastructure.db.database import get_db_session
            self._db_session = next(get_db_session())
        return self._db_session

    @property
    def sql_db(self):
        if self._sql_db is None:
            self._sql_db = get_db()
        return self._sql_db

    @property
    def aggregates(self) -> PracticeAggregateRepository:
        if self._aggregates is None:
            self._aggregates = PracticeAggregateRepository(self.session)
        return self._aggregates

    def commit(self) -> None:
        if self._db_session is not None:
            self._db_session.commit()

    def rollback(self) -> None:
        if self._db_session is not None:
            self._db_session.rollback()

    def __enter__(self) -> "PracticeUnitOfWork":
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        if exc_type is not None:
            self.rollback()
        if self._owns_session and self._db_session is not None:
            self._db_session.close()
        # sql_db 是全局/外部对象，不关闭
