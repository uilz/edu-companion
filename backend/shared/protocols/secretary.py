"""
Secretary Repository Protocol — 秘书系统数据持久化契约

定义 domain 层对持久化基础设施的抽象依赖。
基础设施层 (infra/) 实现这些接口。

Phase A3: 将 ProposalStore 从直接使用 get_db() 改为显式实现此 Protocol。
"""

from __future__ import annotations

from typing import Any, Protocol

# 仅用于类型标注
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.domain.secretary.models import Proposal


class SecretaryRepository(Protocol):
    """秘书系统数据持久化契约 — 提案 CRUD"""

    def save_proposal(
        self, proposal: "Proposal", user_id: str, session_id: str | None = None,
    ) -> str:
        """保存提案，返回提案 ID，相同用户+标题+来源的 pending 提案自动去重"""
        ...

    def update_status(
        self, proposal_id: str, status: str, user_id: str,
        extra_log: dict | None = None,
    ) -> bool:
        """更新提案状态（pending → accepted / dismissed / snoozed / expired / deleted）"""
        ...

    def get_pending_proposals(
        self, user_id: str, limit: int = 20,
        source_module: str | None = None,
        action_type: str | None = None,
        priority_min: int | None = None,
        priority_max: int | None = None,
        search: str | None = None,
    ) -> list["Proposal"]:
        """获取待处理提案列表（支持筛选参数）"""
        ...

    def get_history(
        self, user_id: str, days: int = 7, limit: int = 50,
        source_module: str | None = None,
        action_type: str | None = None,
        page: int = 1,
        page_size: int = 50,
    ) -> list[dict[str, Any]]:
        """获取提案历史（支持筛选与分页）"""
        ...

    def get_daily_usage(self, user_id: str) -> int:
        """获取用户今日已使用的提案推送数"""
        ...

    # ── 新操作 ──

    def snooze_proposal(
        self, proposal_id: str, user_id: str,
        until_timestamp: float | None = None,
    ) -> bool:
        """延后提案（status → snoozed，记录 snoozed_until）"""
        ...

    def delete_proposal(
        self, proposal_id: str, user_id: str,
    ) -> bool:
        """删除提案（status → deleted）"""
        ...

    def restore_proposal(
        self, proposal_id: str, user_id: str,
    ) -> bool:
        """恢复提案（snoozed/deleted → pending）"""
        ...

    def batch_update_status(
        self, proposal_ids: list[str], status: str, user_id: str,
    ) -> int:
        """批量更新提案状态，返回更新的记录数"""
        ...