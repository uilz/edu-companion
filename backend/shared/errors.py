"""
AppError 异常体系 — 统一错误分类与结构化响应

设计原则:
- 所有应用异常继承 AppError，确保全局异常处理器能统一捕获
- status_code 区分 4xx（客户端错误）和 5xx（服务端错误）
- detail 为人类可读描述，context 为调试用额外数据
"""

from __future__ import annotations

from typing import Any


class AppError(Exception):
    """应用异常基类"""

    status_code: int = 500
    code: str = "internal_error"
    detail: str = "Internal server error"
    context: dict[str, Any] | None = None

    def __init__(
        self,
        detail: str | None = None,
        context: dict[str, Any] | None = None,
    ):
        if detail:
            self.detail = detail
        if context:
            self.context = context
        super().__init__(self.detail)

    def to_dict(self) -> dict[str, Any]:
        """序列化为 JSON 响应"""
        result: dict[str, Any] = {
            "error": self.code,
            "detail": self.detail,
        }
        if self.context:
            result["context"] = self.context
        return result


# ── 4xx 客户端错误 ──


class NotFoundError(AppError):
    status_code = 404
    code = "not_found"


class ValidationError(AppError):
    status_code = 400
    code = "validation_error"


class ConflictError(AppError):
    status_code = 409
    code = "conflict"


class UnauthorizedError(AppError):
    status_code = 401
    code = "unauthorized"


# ── 5xx 服务端错误 ──


class DatabaseError(AppError):
    status_code = 500
    code = "database_error"


class ExternalServiceError(AppError):
    """外部服务调用失败（LLM、Embedding 等）"""
    status_code = 502
    code = "external_service_error"


class EmbeddingError(ExternalServiceError):
    code = "embedding_error"


class LLMError(ExternalServiceError):
    code = "llm_error"


class ConfigurationError(AppError):
    status_code = 500
    code = "configuration_error"
