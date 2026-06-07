"""
Data Repository Protocols — 数据持久化契约

双端口设计：
- DataRepository: 正常业务使用的 load/save 接口
- AdminRepository: 管理/迁移工具使用的原始 SQL 接口

设计原则：调用方只 import Protocol，不 import 具体实现。
实现方在 app/services/common/ 中。
"""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

# 仅用于类型标注，避免 runtime 依赖
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.schemas.conversation import UserData


@runtime_checkable
class DataRepository(Protocol):
    """
    对话数据持久化契约

    正常业务代码（conversation_routes, tree_ops, classifier, llm_core 等）
    应该只通过此接口访问用户数据。两套存储引擎（JSON + PG）都实现此契约。
    """

    def load(self, user_id: str) -> "UserData":
        """
        加载用户完整数据。

        返回 UserData 对象。用户不存在时返回新构造的空 UserData。
        """
        ...

    def save(self, user_id: str, data: "UserData") -> None:
        """
        保存用户完整数据（全量覆盖）。

        当前两引擎都是全量写入。调用方确保 data 包含完整状态。
        """
        ...

    def get_etag(self, user_id: str) -> str:
        """
        返回当前用户数据的 ETag。

        用于 HTTP 条件请求（If-None-Match / If-Match）。
        格式: W/"<user_id>:<timestamp|version>"
        """
        ...


@runtime_checkable
class AdminRepository(Protocol):
    """
    原始 SQL 访问契约

    仅限管理 API、数据迁移脚本、后台维护使用。
    不暴露给正常业务代码。

    实现说明：
    - PgStorageEngine 同时实现此接口
    - JsonStorageEngine 的 query/execute 返回空列表（JSON 模式不支持 SQL）
    """

    def query(self, sql: str, params: list | None = None) -> list[dict[str, Any]]:
        """
        执行 SELECT 查询并返回结果列表。

        sql: 原始 SQL（参数用 %s 占位）
        params: 参数列表
        """
        ...

    def execute(self, sql: str, params: list | None = None) -> None:
        """
        执行 INSERT/UPDATE/DELETE 等写操作。

        sql: 原始 SQL（参数用 %s 占位）
        params: 参数列表
        """
        ...
