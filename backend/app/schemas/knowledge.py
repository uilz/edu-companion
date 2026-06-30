"""
Knowledge System v5 — 四实体解耦架构

KnowledgeNode: 唯一知识点实体 (合并 KGNode + CognitiveNode)
Conversation: 独立会话实体 (连接导航树和知识树的桥)
Message: 独立消息实体
NavigationNode: 纯导航节点 (替代 DirectoryNode)
"""

from __future__ import annotations
import time
from typing import Any
from uuid import uuid4
from pydantic import BaseModel, Field

# ═══════════════════════════════════════════
# KnowledgeNode — 唯一知识点实体
# ═══════════════════════════════════════════

class KnowledgeNode(BaseModel):
    """唯一的知识点实体。合并原 KGNode + CognitiveNode"""
    id: str = Field(default_factory=lambda: f"kn_{uuid4().hex[:12]}")
    user_id: str = ""
    parent_id: str | None = None

    # 身份
    label: str = ""
    level: str = "topic"  # domain | topic | concept | atom
    brief: str = ""
    tags: list[str] = Field(default_factory=list)
    created_by: str = "user"  # user | ai | auto_generated

    # 树结构
    children_order: list[str] = Field(default_factory=list)

    # 关系 (前置/后置/相关)
    prerequisites: list[dict] = Field(default_factory=list)  # [{id, type: strict|suggested}]
    unlocks: list[dict] = Field(default_factory=list)
    associates: list[dict] = Field(default_factory=list)  # [{id, strength, type, label}]

    # 可视化
    emoji: str = ""
    color: str = ""
    sort_order: int = 0
    is_visible: bool = True
    node_type: str = "explicit"  # explicit | auto_generated | user_created | suggested

    # 认知状态 (摘要字段, 完整模型在 cognitive 模块)
    mastery: float = 0.0  # 计算字段: belief.proficiency_mean
    mastery_level: str = "未接触"

    # 元信息
    path_id: str = ""
    created_at: float = Field(default_factory=time.time)
    updated_at: float = Field(default_factory=time.time)
    is_active: bool = True
    metadata: dict[str, Any] = Field(default_factory=dict)


# ═══════════════════════════════════════════
# Conversation — 独立会话实体
# ═══════════════════════════════════════════

class Conversation(BaseModel):
    """独立的会话实体，连接导航树和知识树"""
    id: str = Field(default_factory=lambda: f"conv_{uuid4().hex[:12]}")
    user_id: str = ""

    # 消息
    message_ids: list[str] = Field(default_factory=list)

    # 知识点关联 (核心桥字段)
    knowledge_node_ids: list[str] = Field(default_factory=list)

    # 摘要
    summary_short: str = ""
    summary_dirty: bool = False

    # 子支
    parent_conv_id: str = ""
    sub_branch_ids: list[str] = Field(default_factory=list)
    depth: int = 0

    # 元信息
    created_at: float = Field(default_factory=time.time)
    updated_at: float = Field(default_factory=time.time)
    metadata: dict[str, Any] = Field(default_factory=dict)


# ═══════════════════════════════════════════
# Message — 独立消息实体
# ═══════════════════════════════════════════

class Message(BaseModel):
    """消息节点"""
    id: str = Field(default_factory=lambda: f"msg_{uuid4().hex[:12]}")
    conv_id: str = ""

    # 内容
    role: str = "user"  # user | assistant
    content: str = ""
    content_blocks: list[dict] = Field(default_factory=list)
    text_summary: str = ""

    # 知识点关联 (可选精确标记)
    knowledge_node_ids: list[str] = Field(default_factory=list)

    # 树结构 (消息链)
    parent_id: str | None = None
    children_ids: list[str] = Field(default_factory=list)

    # 子支
    has_sub_branches: bool = False
    sub_branch_ids: list[str] = Field(default_factory=list)
    sub_branch_summaries: list[dict] = Field(default_factory=list)

    # 版本
    version: int = 1
    is_deleted: bool = False

    # 元信息
    timestamp: float = Field(default_factory=time.time)
    token_count: int = 0
    agent_label: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)


# ═══════════════════════════════════════════
# NavigationNode — 纯导航节点
# ═══════════════════════════════════════════

class NavigationNode(BaseModel):
    """纯导航节点，用户自由组织的文件夹结构"""
    id: str = Field(default_factory=lambda: f"nav_{uuid4().hex[:12]}")
    user_id: str = ""
    parent_id: str | None = None

    node_type: str = "dir"  # "dir" | "conv"
    kind: str = "general"  # general | temp | practice | secretary

    name: str = "新节点"
    user_name: str | None = None
    ai_name: str = ""

    children_order: list[str] = Field(default_factory=list)

    # conv 类型: 指向 Conversation
    conv_id: str | None = None

    # dir 类型可选: 指向知识区域
    knowledge_area_id: str | None = None

    # 元信息
    path: list[str] = Field(default_factory=list)
    created_at: float = Field(default_factory=time.time)
    updated_at: float = Field(default_factory=time.time)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @property
    def display_name(self) -> str:
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