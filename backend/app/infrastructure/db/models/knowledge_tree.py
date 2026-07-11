"""
Knowledge Tree ORM 模型（SQLAlchemy 2.0）

目标：将用户主观创作的知识树结构与认知数据系统完全解耦：
- knowledge_trees: 知识树容器
- tree_nodes: 用户创作的树节点
- tree_edges: 用户定义的树边
- tree_node_cognitive_links: 树节点与认知节点的关联
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.infrastructure.db.models.cognitive import Base


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


class KnowledgeTreeORM(Base):
    """知识树容器 — 用户主观知识结构的根。"""

    __tablename__ = "knowledge_trees"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=lambda: _new_id("kt"))
    user_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)

    title: Mapped[str] = mapped_column(String(255), nullable=False, default="我的知识树")
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    tree_type: Mapped[str] = mapped_column(String(32), nullable=False, default="project")
    root_node_id: Mapped[str | None] = mapped_column(String(32), nullable=True)

    default_view_mode: Mapped[str] = mapped_column(String(32), nullable=False, default="tree")
    default_layout: Mapped[str] = mapped_column(String(32), nullable=False, default="layered")

    tags: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    meta: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)

    status: Mapped[str] = mapped_column(String(32), nullable=False, default="active")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utc_now
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utc_now, onupdate=_utc_now
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    nodes: Mapped[list["TreeNodeORM"]] = relationship(
        "TreeNodeORM", back_populates="tree", cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("ix_knowledge_trees_user_status", "user_id", "status"),
    )


class TreeNodeORM(Base):
    """知识树节点 — 用户主观创作单位。"""

    __tablename__ = "tree_nodes"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=lambda: _new_id("tn"))
    tree_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("knowledge_trees.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)

    label: Mapped[str] = mapped_column(String(255), nullable=False)
    node_type: Mapped[str] = mapped_column(String(32), nullable=False, default="concept")
    parent_id: Mapped[str | None] = mapped_column(
        String(32), ForeignKey("tree_nodes.id", ondelete="CASCADE"), nullable=True, index=True
    )
    children_order: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    order_index: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    color: Mapped[str] = mapped_column(String(16), nullable=False, default="")
    emoji: Mapped[str] = mapped_column(String(8), nullable=False, default="")
    icon_url: Mapped[str] = mapped_column(String(512), nullable=False, default="")
    position: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)

    source_refs: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False, default=list)
    tags: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    brief: Mapped[str] = mapped_column(Text, nullable=False, default="")
    meta: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)

    status: Mapped[str] = mapped_column(String(32), nullable=False, default="active")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utc_now
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utc_now, onupdate=_utc_now
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    tree: Mapped["KnowledgeTreeORM"] = relationship("KnowledgeTreeORM", back_populates="nodes")

    __table_args__ = (
        Index("ix_tree_nodes_tree_status", "tree_id", "status"),
    )


class TreeEdgeORM(Base):
    """知识树边 — 用户定义的结构关系。"""

    __tablename__ = "tree_edges"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=lambda: _new_id("te"))
    tree_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("knowledge_trees.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)

    source_node_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("tree_nodes.id", ondelete="CASCADE"), nullable=False, index=True
    )
    target_node_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("tree_nodes.id", ondelete="CASCADE"), nullable=False, index=True
    )
    edge_type: Mapped[str] = mapped_column(String(32), nullable=False, default="parent_child")
    strength: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)
    is_user_confirmed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    is_inferred: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    meta: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utc_now
    )

    __table_args__ = (
        UniqueConstraint("tree_id", "source_node_id", "target_node_id", "edge_type"),
    )


class TreeNodeCognitiveLinkORM(Base):
    """树节点与认知节点的关联 — 支持多对多。"""

    __tablename__ = "tree_node_cognitive_links"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=lambda: _new_id("tcl"))
    tree_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("knowledge_trees.id", ondelete="CASCADE"), nullable=False, index=True
    )
    tree_node_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("tree_nodes.id", ondelete="CASCADE"), nullable=False, index=True
    )
    cognitive_node_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    user_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    link_role: Mapped[str] = mapped_column(String(32), nullable=False, default="primary")

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utc_now
    )

    __table_args__ = (
        UniqueConstraint("tree_id", "tree_node_id", "cognitive_node_id"),
        Index("ix_tree_cognitive_links_tree_node", "tree_node_id"),
        Index("ix_tree_cognitive_links_cognitive", "cognitive_node_id"),
    )
