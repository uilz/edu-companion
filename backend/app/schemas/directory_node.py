"""
DirectoryNode — 统一目录结构节点

取代旧 Partition/Domain/Topic/Conversation 四个独立模型。
所有节点统一存储, 通过 node_type/kind 区分行为和界面表现。
"""

from __future__ import annotations

import time
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field, ConfigDict


class DirectoryNode(BaseModel):
    """统一目录节点

    node_type: "dir" | "conv"           — 结构
    kind:      "general" | "temp" | "practice" | "secretary"  — 行为
    """
    id: str = Field(default_factory=lambda: f"dir_{uuid4().hex[:12]}")
    user_id: str = ""
    parent_id: str | None = None
    node_type: str = "dir"    # "dir" | "conv"
    kind: str = "general"     # "general" | "temp" | "practice" | "secretary"

    name: str = "新节点"

    # 结构
    path: list[str] = Field(default_factory=list)       # ["root_id", "l1_id", "this_id"]
    children_order: list[str] = Field(default_factory=list)  # 有序子级 ID 列表 (dir 类型)
    conv_message_ids: list[str] = Field(default_factory=list)  # conv 类下的消息 ID

    # 命名系统
    user_name: str | None = None   # 用户手动命名, None 则回退 ai_name
    ai_name: str = ""              # AI 从 summary_short 生成

    # 组织工具
    summary_short: str = ""
    summary_dirty: bool = False

    # conv 类特有数据 (原 Conversation 独有字段)
    payload: dict[str, Any] = Field(default_factory=dict)

    # 元信息
    created_at: float = Field(default_factory=time.time)
    updated_at: float = Field(default_factory=time.time)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @property
    def display_name(self) -> str:
        """显示用名: user_name or ai_name or name"""
        return self.user_name or self.ai_name or self.name or "新节点"

    @property
    def is_temp(self) -> bool:
        return self.kind == "temp"

    @property
    def is_dir(self) -> bool:
        return self.node_type == "dir"

    @property
    def is_conv(self) -> bool:
        return self.node_type == "conv"

    def add_child(self, child_id: str) -> None:
        if child_id not in self.children_order:
            self.children_order.append(child_id)

    def remove_child(self, child_id: str) -> None:
        self.children_order = [c for c in self.children_order if c != child_id]


class MessageNode(BaseModel):
    """消息节点 — 取代原 TreeNode

    TreeNode 改名 MessageNode, 不再耦合 partition_id/conversation_id,
    统一用 directory_id 指向所属 conv 节点。
    discussed_skill_ids 已删除 (改为事件化)。

    可容纳旧 TreeNode 序列化数据（向前兼容），
    分区字段映射: partition_id+conversation_id → directory_id。
    """
    id: str = Field(default_factory=lambda: f"msg_{uuid4().hex[:12]}")
    directory_id: str = ""                    # 所属 conv 节点 ID

    # ── 向后兼容 (旧 TreeNode 字段, 已废弃) ──
    partition_id: str = ""
    conversation_id: str = ""
    parent_id: str | None = None
    children_ids: list[str] = Field(default_factory=list)

    # ── 内容 ──
    role: str = "user"                        # "user" | "assistant"
    content: str = ""
    content_blocks: list[dict] = Field(default_factory=list)  # ContentBlock dicts
    text_summary: str = ""
    summary: str | None = None
    cross_partition: dict | None = None       # CrossPartitionMark

    # ── 元信息 ──
    timestamp: float = Field(default_factory=time.time)
    token_count: int = 0
    version: int = 1                          # 取代 has_modified_version
    is_deleted: bool = False
    is_archived: bool = False

    # ── 链接 ──
    links_to: list[str] = Field(default_factory=list)
    linked_from: list[str] = Field(default_factory=list)

    # ── 多 Agent 体系 ──
    agent_label: str = ""

    # ── 子支 ──
    has_sub_branches: bool = False
    sub_branch_ids: list[str] = Field(default_factory=list)
    sub_branch_summaries: list[dict] = Field(default_factory=list)

    # 存档
    metadata: dict[str, Any] = Field(default_factory=dict)
