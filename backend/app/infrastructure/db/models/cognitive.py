"""
Cognitive 数据系统 ORM 模型（SQLAlchemy 2.0）

目标：将原来大 JSONB 单表的 CognitiveNode 拆分为：
- 瘦实体表 knowledge_nodes
- 统一边表 knowledge_edges
- 练习事件表 practice_events
- 认知领域事件表 cognitive_events
- 派生状态投影表 cognitive_node_projections
- 列表子表 error_clusters / deep_processing / composition_members
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


class Base(DeclarativeBase):
    """SQLAlchemy 声明式基类"""

    type_annotation_map = {
        dict[str, Any]: JSONB,
        list[str]: JSONB,
    }


# ═══════════════════════════════════════════════════════════════
# 1. 实体层
# ═══════════════════════════════════════════════════════════════


class KnowledgeNodeORM(Base):
    __tablename__ = "knowledge_nodes"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: _new_id("kn"))
    user_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    label: Mapped[str] = mapped_column(Text, nullable=False)
    level: Mapped[str] = mapped_column(String(16), nullable=False, default="topic")
    parent_id: Mapped[str | None] = mapped_column(
        String(64), ForeignKey("knowledge_nodes.id", ondelete="SET NULL"), nullable=True, index=True
    )
    path_id: Mapped[str] = mapped_column(Text, nullable=False, default="")

    node_type: Mapped[str] = mapped_column(String(32), nullable=False, default="explicit")
    is_visible: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    is_core: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    brief: Mapped[str] = mapped_column(Text, nullable=False, default="")
    emoji: Mapped[str] = mapped_column(String(8), nullable=False, default="")
    color: Mapped[str] = mapped_column(String(16), nullable=False, default="")
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    tags: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    created_by: Mapped[str] = mapped_column(String(32), nullable=False, default="user")

    embedding: Mapped[list[float] | None] = mapped_column(JSONB, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utc_now
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utc_now, onupdate=_utc_now
    )
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # relationships
    parent: Mapped[KnowledgeNodeORM | None] = relationship(
        "KnowledgeNodeORM", remote_side="KnowledgeNodeORM.id", back_populates="children"
    )
    children: Mapped[list[KnowledgeNodeORM]] = relationship(
        "KnowledgeNodeORM", back_populates="parent"
    )
    outgoing_edges: Mapped[list[KnowledgeEdgeORM]] = relationship(
        "KnowledgeEdgeORM", foreign_keys="KnowledgeEdgeORM.source_id", back_populates="source"
    )
    incoming_edges: Mapped[list[KnowledgeEdgeORM]] = relationship(
        "KnowledgeEdgeORM", foreign_keys="KnowledgeEdgeORM.target_id", back_populates="target"
    )
    projection: Mapped[CognitiveNodeProjectionORM | None] = relationship(
        "CognitiveNodeProjectionORM", back_populates="node", uselist=False
    )

    __table_args__ = (
        Index("ix_knowledge_nodes_user_label", "user_id", func.lower("label")),
        Index("ix_knowledge_nodes_user_level", "user_id", "level"),
    )


# ═══════════════════════════════════════════════════════════════
# 2. 边关系层
# ═══════════════════════════════════════════════════════════════


class KnowledgeEdgeORM(Base):
    __tablename__ = "knowledge_edges"

    id: Mapped[str] = mapped_column(
        String(64), primary_key=True, default=lambda: _new_id("ke")
    )
    user_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    source_id: Mapped[str] = mapped_column(
        ForeignKey("knowledge_nodes.id", ondelete="CASCADE"), nullable=False, index=True
    )
    target_id: Mapped[str] = mapped_column(
        ForeignKey("knowledge_nodes.id", ondelete="CASCADE"), nullable=False, index=True
    )
    edge_type: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    strength: Mapped[float] = mapped_column(Float, nullable=False, default=0.5)
    edge_weight: Mapped[float] = mapped_column(Float, nullable=False, default=0.5)
    edge_distance_decay: Mapped[float] = mapped_column(Float, nullable=False, default=0.5)
    max_propagation_hops: Mapped[int] = mapped_column(Integer, nullable=False, default=2)
    edge_metadata: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utc_now
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utc_now, onupdate=_utc_now
    )

    source: Mapped[KnowledgeNodeORM] = relationship(
        "KnowledgeNodeORM", foreign_keys=[source_id], back_populates="outgoing_edges"
    )
    target: Mapped[KnowledgeNodeORM] = relationship(
        "KnowledgeNodeORM", foreign_keys=[target_id], back_populates="incoming_edges"
    )

    __table_args__ = (
        UniqueConstraint("user_id", "source_id", "target_id", "edge_type", name="uq_knowledge_edges"),
        Index("ix_knowledge_edges_user_type", "user_id", "edge_type"),
    )


# ═══════════════════════════════════════════════════════════════
# 3. 事件层
# ═══════════════════════════════════════════════════════════════


class PracticeEventORM(Base):
    __tablename__ = "practice_events"

    id: Mapped[str] = mapped_column(
        String(64), primary_key=True, default=lambda: _new_id("pe")
    )
    user_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    node_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("knowledge_nodes.id", ondelete="CASCADE"), nullable=False, index=True
    )
    session_id: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    question_id: Mapped[str] = mapped_column(String(64), nullable=False, default="")

    actor_type: Mapped[str] = mapped_column(String(16), nullable=False, default="user")
    source_type: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    source_id: Mapped[str] = mapped_column(String(64), nullable=False, default="")

    timestamp: Mapped[float] = mapped_column(Float, nullable=False)
    success: Mapped[bool] = mapped_column(Boolean, nullable=False)
    latency_ms: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    weight: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)

    difficulty: Mapped[float | None] = mapped_column(Float, nullable=True)
    guess: Mapped[float | None] = mapped_column(Float, nullable=True)
    slip: Mapped[float | None] = mapped_column(Float, nullable=True)

    confidence_before: Mapped[float | None] = mapped_column(Float, nullable=True)
    confidence_after: Mapped[float | None] = mapped_column(Float, nullable=True)
    hints_used: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    time_spent: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)

    error_embedding: Mapped[list[float] | None] = mapped_column(JSONB, nullable=True)
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False, unique=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utc_now
    )

    __table_args__ = (
        Index("ix_practice_events_user_node_ts", "user_id", "node_id", "timestamp"),
        Index("ix_practice_events_session", "session_id"),
    )


class CognitiveEventORM(Base):
    """认知领域事件：node_created / edge_created / goal_changed / daily_tick 等"""

    __tablename__ = "cognitive_events"

    id: Mapped[str] = mapped_column(
        String(64), primary_key=True, default=lambda: _new_id("ce")
    )
    user_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    event_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    actor_type: Mapped[str] = mapped_column(String(16), nullable=False, default="user")
    source_type: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    source_id: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    node_id: Mapped[str | None] = mapped_column(
        String(64), ForeignKey("knowledge_nodes.id", ondelete="CASCADE"), nullable=True, index=True
    )
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="pending")
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utc_now
    )

    __table_args__ = (
        Index("ix_cognitive_events_user_status", "user_id", "status"),
        Index("ix_cognitive_events_user_type", "user_id", "event_type"),
    )


# ═══════════════════════════════════════════════════════════════
# 4. 派生状态层
# ═══════════════════════════════════════════════════════════════


class CognitiveNodeProjectionORM(Base):
    """CognitiveNode 各子系统的物化投影（可完全从事件重建）。

    核心信念采用 Beta(α, β) 概率分布，统一表达掌握度、不确定性和复习需求。
    """

    __tablename__ = "cognitive_node_projections"

    node_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("knowledge_nodes.id", ondelete="CASCADE"), primary_key=True
    )
    user_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)

    # Belief: Beta(α, β) 后验分布
    belief_alpha: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)
    belief_beta: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)
    belief_evidence_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    belief_last_updated: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)

    # 时间衰减与稳定性
    stability_factor: Mapped[float] = mapped_column(Float, nullable=False, default=0.5)
    forgetting_rate: Mapped[float] = mapped_column(Float, nullable=False, default=0.1)

    # 信息增益
    total_information_gain: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    last_information_gain: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)

    # 调度（由 Beta 不确定性 + 秘书修正统一决定）
    sched_urgency: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    sched_next_review: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    sched_interval_days: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)
    sched_interleaving_group: Mapped[str] = mapped_column(String(32), nullable=False, default="")
    sched_next_action_type: Mapped[str] = mapped_column(String(32), nullable=False, default="")

    # 图传播：独立证据权重，防止过度平滑
    independent_evidence_weight: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)

    # Activation
    act_base_level: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    act_retrieval_prob: Mapped[float] = mapped_column(Float, nullable=False, default=0.5)
    act_latency_ms: Mapped[float] = mapped_column(Float, nullable=False, default=5000.0)
    act_spread: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    act_last_updated: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)

    # Trend
    trend_velocity: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    trend_stability: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    trend_volatility: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    trend_direction: Mapped[str] = mapped_column(String(16), nullable=False, default="plateau")
    trend_stagnation_days: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)

    # Metacognition
    meta_self_assessment: Mapped[float] = mapped_column(Float, nullable=False, default=0.5)
    meta_calibration_error: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    meta_direction: Mapped[str] = mapped_column(String(16), nullable=False, default="accurate")

    # Engagement
    eng_xp: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    eng_streak_current: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    eng_streak_longest: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    eng_flow_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    eng_last_practice_date: Mapped[str] = mapped_column(String(16), nullable=False, default="")

    # GoalAlignment
    goal_toward: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    goal_distance: Mapped[int] = mapped_column(Integer, nullable=False, default=-1)
    goal_on_critical_path: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    # Composition
    comp_chunk_id: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    comp_chunking_status: Mapped[str] = mapped_column(String(16), nullable=False, default="none")

    # Prediction
    pred_top_down_mean: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    pred_prediction_error: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    pred_error_flag: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    # CognitiveLoad
    load_intrinsic: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)
    load_dynamic: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utc_now, onupdate=_utc_now
    )

    node: Mapped[KnowledgeNodeORM] = relationship(
        "KnowledgeNodeORM", back_populates="projection"
    )

    __table_args__ = (
        Index("ix_cognitive_projections_user_urgency", "user_id", "sched_urgency"),
        Index("ix_cognitive_projections_user_next_review", "user_id", "sched_next_review"),
    )


# ═══════════════════════════════════════════════════════════════
# 5. 列表子表
# ═══════════════════════════════════════════════════════════════


class CognitiveNodeErrorClusterORM(Base):
    __tablename__ = "cognitive_node_error_clusters"

    id: Mapped[str] = mapped_column(
        String(64), primary_key=True, default=lambda: _new_id("ec")
    )
    user_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    node_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("knowledge_nodes.id", ondelete="CASCADE"), nullable=False, index=True
    )
    error_type: Mapped[str] = mapped_column(String(64), nullable=False)
    frequency: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    last_occurred: Mapped[float] = mapped_column(Float, nullable=False)
    cluster_metadata: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utc_now
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utc_now, onupdate=_utc_now
    )


class CognitiveNodeDeepProcessingORM(Base):
    __tablename__ = "cognitive_node_deep_processing"

    id: Mapped[str] = mapped_column(
        String(64), primary_key=True, default=lambda: _new_id("dp")
    )
    user_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    node_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("knowledge_nodes.id", ondelete="CASCADE"), nullable=False, index=True
    )
    task_type: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="pending")
    prompt: Mapped[str] = mapped_column(Text, nullable=False, default="")
    result: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utc_now
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class CognitiveNodeCompositionMemberORM(Base):
    __tablename__ = "cognitive_node_composition_members"

    id: Mapped[str] = mapped_column(
        String(64), primary_key=True, default=lambda: _new_id("cm")
    )
    chunk_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    user_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    node_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("knowledge_nodes.id", ondelete="CASCADE"), nullable=False, index=True
    )
    co_occurrence_count: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utc_now
    )

    __table_args__ = (
        UniqueConstraint("chunk_id", "node_id", name="uq_composition_members"),
    )
