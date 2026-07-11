"""
Knowledge Tree schemas — 用户主观知识结构
"""

from __future__ import annotations

import time
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field


class KnowledgeTree(BaseModel):
    """知识树容器。"""

    id: str = Field(default_factory=lambda: f"kt_{uuid4().hex[:12]}")
    user_id: str = ""
    title: str = "我的知识树"
    description: str = ""
    tree_type: str = "project"  # project | domain | map
    root_node_id: str | None = None
    default_view_mode: str = "tree"  # tree | graph | split
    default_layout: str = "layered"  # layered | force | radial | manual
    tags: list[str] = Field(default_factory=list)
    meta: dict[str, Any] = Field(default_factory=dict)
    status: str = "active"
    created_at: float = Field(default_factory=time.time)
    updated_at: float = Field(default_factory=time.time)
    version: int = 0


class TreeNode(BaseModel):
    """知识树节点 — 用户创作单位。"""

    id: str = Field(default_factory=lambda: f"tn_{uuid4().hex[:12]}")
    tree_id: str = ""
    user_id: str = ""
    label: str = "新节点"
    node_type: str = "concept"  # topic | concept | skill | material | question | card | note | milestone
    parent_id: str | None = None
    children_order: list[str] = Field(default_factory=list)
    order_index: int = 0
    color: str = ""
    emoji: str = ""
    icon_url: str = ""
    position: dict[str, Any] = Field(default_factory=dict)
    source_refs: list[dict[str, Any]] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    brief: str = ""
    meta: dict[str, Any] = Field(default_factory=dict)
    status: str = "active"
    created_at: float = Field(default_factory=time.time)
    updated_at: float = Field(default_factory=time.time)
    version: int = 0

    # 运行时派生（非数据库字段）
    linked_cognitive_node_ids: list[str] = Field(default_factory=list)
    cognitive_view: dict[str, Any] | None = None


class TreeEdge(BaseModel):
    """知识树边 — 用户定义的结构关系。"""

    id: str = Field(default_factory=lambda: f"te_{uuid4().hex[:12]}")
    tree_id: str = ""
    user_id: str = ""
    source_node_id: str = ""
    target_node_id: str = ""
    edge_type: str = "parent_child"  # parent_child | prerequisite | related | sequence | reference
    strength: float = 1.0
    is_user_confirmed: bool = True
    is_inferred: bool = False
    meta: dict[str, Any] = Field(default_factory=dict)
    created_at: float = Field(default_factory=time.time)


class TreeNodeCognitiveLink(BaseModel):
    """树节点与认知节点关联。"""

    id: str = Field(default_factory=lambda: f"tcl_{uuid4().hex[:12]}")
    tree_id: str = ""
    tree_node_id: str = ""
    cognitive_node_id: str = ""
    user_id: str = ""
    link_role: str = "primary"  # primary | reference | derived
    created_at: float = Field(default_factory=time.time)


class ViewportState(BaseModel):
    """知识树视图状态。"""

    user_id: str = ""
    tree_id: str = ""
    view_mode: str = "tree"
    layout: str = "layered"
    zoom: float = 1.0
    pan_x: float = 0.0
    pan_y: float = 0.0
    filters: dict[str, Any] = Field(default_factory=dict)
    collapsed_node_ids: list[str] = Field(default_factory=list)
    focused_node_id: str = ""
    updated_at: float = Field(default_factory=time.time)
