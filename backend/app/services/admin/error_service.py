"""
AdminErrorService — 管理系统错误报告服务

使用内存存储（dict），不依赖数据库。
"""

from __future__ import annotations

import logging
import time
import traceback
import uuid
from typing import Any

from app.schemas.admin_error import AdminError

logger = logging.getLogger(__name__)


class AdminErrorService:
    """管理系统错误报告 — 线程安全的内存存储"""

    def __init__(self) -> None:
        self._errors: dict[str, AdminError] = {}

    def report_error(
        self,
        source: str,
        processor_name: str,
        user_id: str,
        exception: Exception,
        context: dict | None = None,
    ) -> str | None:
        """报告一个错误，返回错误记录 ID，失败时返回 None（永不抛出）"""
        try:
            error_id = uuid.uuid4().hex[:12]
            error = AdminError(
                id=error_id,
                source=source,
                processor_name=processor_name,
                user_id=user_id,
                error_type=type(exception).__name__,
                error_message=str(exception)[:500],
                traceback="".join(
                    traceback.format_exception(
                        type(exception), exception, exception.__traceback__
                    )
                ),
                context=context or {},
                occurred_at=time.time(),
                acknowledged=False,
            )
            self._errors[error_id] = error
            logger.warning(
                "AdminError [%s] source=%s processor=%s user=%s type=%s: %s",
                error_id, source, processor_name, user_id,
                error.error_type, error.error_message,
            )
            return error_id
        except Exception as e:
            logger.exception("AdminErrorService.report_error 自身失败: %s", e)
            return None

    def get_errors(
        self,
        source: str | None = None,
        limit: int = 50,
    ) -> list[AdminError]:
        """获取错误列表，按发生时间降序排列"""
        errors = list(self._errors.values())
        if source:
            errors = [e for e in errors if e.source == source]
        errors.sort(key=lambda e: e.occurred_at, reverse=True)
        return errors[:limit]

    def acknowledge_error(self, error_id: str) -> bool:
        """标记错误为已确认，返回是否成功"""
        error = self._errors.get(error_id)
        if error is None:
            return False
        error.acknowledged = True
        return True

    def get_unacknowledged_count(self) -> int:
        """获取未确认错误数量"""
        return sum(1 for e in self._errors.values() if not e.acknowledged)


# 模块级单例
admin_error_service = AdminErrorService()
