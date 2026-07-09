"""initial cognitive refactor schema

Revision ID: 1bf173434c24
Revises: 
Create Date: 2026-07-09 12:29:36.155835

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "1bf173434c24"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# 旧 CognitiveNode 中需要删除的 JSONB 子系统列
_OBSOLETE_KNOWLEDGE_NODE_COLUMNS = [
    "activation",
    "belief",
    "prediction",
    "cognitive_load",
    "trend",
    "scheduling",
    "dialogue_contexts",
    "practice_events",
    "practice_summary",
    "error_clusters",
    "metacognition",
    "engagement",
    "composition",
    "deep_links",
    "deep_processing",
    "goal_alignment",
    "diagnostic",
    "prerequisites",
    "unlocks",
    "associates",
    "param_refs",
    "meta",
    "subsystems",
    "children",
    "children_order",
    "description",
    "metadata",
]


def upgrade() -> None:
    """Upgrade schema."""
    # 开发阶段：先清理可能存在的旧结构/同名表，确保从干净状态开始
    op.execute("DROP TABLE IF EXISTS cognitive_node_composition_members CASCADE")
    op.execute("DROP TABLE IF EXISTS cognitive_node_deep_processing CASCADE")
    op.execute("DROP TABLE IF EXISTS cognitive_node_error_clusters CASCADE")
    op.execute("DROP TABLE IF EXISTS cognitive_node_projections CASCADE")
    op.execute("DROP TABLE IF EXISTS cognitive_events CASCADE")
    op.execute("DROP TABLE IF EXISTS practice_events CASCADE")
    op.execute("DROP TABLE IF EXISTS knowledge_edges CASCADE")

    # ── 1. 清理 knowledge_nodes 大 JSONB 表，瘦身为核心实体表 ──
    op.execute("ALTER TABLE IF EXISTS knowledge_nodes RENAME COLUMN parent TO parent_id")

    for col in _OBSOLETE_KNOWLEDGE_NODE_COLUMNS:
        op.drop_column("knowledge_nodes", col)

    # 调整已有列类型/约束
    op.alter_column("knowledge_nodes", "created_by", type_=sa.String(32))
    op.create_index("ix_knowledge_nodes_user_level", "knowledge_nodes", ["user_id", "level"])
    op.create_index(
        "ix_knowledge_nodes_user_label",
        "knowledge_nodes",
        [sa.text("LOWER(label)")],
    )

    # ── 2. 统一知识图谱边表 ──
    op.create_table(
        "knowledge_edges",
        sa.Column("id", sa.String(32), nullable=False),
        sa.Column("user_id", sa.String(64), nullable=False, index=True),
        sa.Column("source_id", sa.String(32), nullable=False, index=True),
        sa.Column("target_id", sa.String(32), nullable=False, index=True),
        sa.Column("edge_type", sa.String(32), nullable=False, index=True),
        sa.Column("strength", sa.Float(), nullable=False, default=0.5),
        sa.Column("edge_metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=False, default=dict),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now(), onupdate=sa.func.now()),
        sa.ForeignKeyConstraint(["source_id"], ["knowledge_nodes.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["target_id"], ["knowledge_nodes.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "source_id", "target_id", "edge_type", name="uq_knowledge_edges"),
    )
    op.create_index("ix_knowledge_edges_user_type", "knowledge_edges", ["user_id", "edge_type"])

    # ── 3. 练习事件独立表（append-only，真相源） ──
    op.create_table(
        "practice_events",
        sa.Column("id", sa.String(32), nullable=False),
        sa.Column("user_id", sa.String(64), nullable=False, index=True),
        sa.Column("node_id", sa.String(32), nullable=False, index=True),
        sa.Column("session_id", sa.String(64), nullable=False, default=""),
        sa.Column("question_id", sa.String(64), nullable=False, default=""),
        sa.Column("timestamp", sa.Float(), nullable=False),
        sa.Column("success", sa.Boolean(), nullable=False),
        sa.Column("latency_ms", sa.Float(), nullable=False, default=0.0),
        sa.Column("weight", sa.Float(), nullable=False, default=1.0),
        sa.Column("difficulty", sa.Float(), nullable=True),
        sa.Column("guess", sa.Float(), nullable=True),
        sa.Column("slip", sa.Float(), nullable=True),
        sa.Column("confidence_before", sa.Float(), nullable=True),
        sa.Column("confidence_after", sa.Float(), nullable=True),
        sa.Column("hints_used", sa.Integer(), nullable=False, default=0),
        sa.Column("time_spent", sa.Float(), nullable=False, default=0.0),
        sa.Column("error_embedding", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("idempotency_key", sa.String(128), nullable=False, unique=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["node_id"], ["knowledge_nodes.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_practice_events_user_node_ts", "practice_events", ["user_id", "node_id", "timestamp"])
    op.create_index("ix_practice_events_session", "practice_events", ["session_id"])

    # ── 4. 认知领域事件表 ──
    op.create_table(
        "cognitive_events",
        sa.Column("id", sa.String(32), nullable=False),
        sa.Column("user_id", sa.String(64), nullable=False, index=True),
        sa.Column("event_type", sa.String(64), nullable=False, index=True),
        sa.Column("source_type", sa.String(64), nullable=False, default=""),
        sa.Column("source_id", sa.String(64), nullable=False, default=""),
        sa.Column("node_id", sa.String(32), nullable=True, index=True),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False, default=dict),
        sa.Column("status", sa.String(16), nullable=False, default="pending"),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["node_id"], ["knowledge_nodes.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_cognitive_events_user_status", "cognitive_events", ["user_id", "status"])
    op.create_index("ix_cognitive_events_user_type", "cognitive_events", ["user_id", "event_type"])

    # ── 5. 派生状态投影表 ──
    op.create_table(
        "cognitive_node_projections",
        sa.Column("node_id", sa.String(32), nullable=False),
        sa.Column("user_id", sa.String(64), nullable=False, index=True),
        sa.Column("bkt_known", sa.Float(), nullable=False, default=0.3),
        sa.Column("bkt_learn", sa.Float(), nullable=False, default=0.3),
        sa.Column("bkt_forget", sa.Float(), nullable=False, default=0.05),
        sa.Column("bkt_guess", sa.Float(), nullable=False, default=0.2),
        sa.Column("bkt_slip", sa.Float(), nullable=False, default=0.1),
        sa.Column("bkt_proficiency", sa.Float(), nullable=False, default=0.3),
        sa.Column("bkt_peak", sa.Float(), nullable=False, default=0.3),
        sa.Column("bkt_last_updated", sa.Float(), nullable=False, default=0.0),
        sa.Column("act_base_level", sa.Float(), nullable=False, default=0.0),
        sa.Column("act_retrieval_prob", sa.Float(), nullable=False, default=0.5),
        sa.Column("act_latency_ms", sa.Float(), nullable=False, default=5000.0),
        sa.Column("act_spread", sa.Float(), nullable=False, default=0.0),
        sa.Column("act_last_updated", sa.Float(), nullable=False, default=0.0),
        sa.Column("trend_velocity", sa.Float(), nullable=False, default=0.0),
        sa.Column("trend_stability", sa.Float(), nullable=False, default=0.0),
        sa.Column("trend_volatility", sa.Float(), nullable=False, default=0.0),
        sa.Column("trend_direction", sa.String(16), nullable=False, default="plateau"),
        sa.Column("trend_stagnation_days", sa.Float(), nullable=False, default=0.0),
        sa.Column("sched_urgency", sa.Float(), nullable=False, default=0.0),
        sa.Column("sched_next_review", sa.Float(), nullable=False, default=0.0),
        sa.Column("sched_interleaving_group", sa.String(32), nullable=False, default=""),
        sa.Column("sched_next_action_type", sa.String(32), nullable=False, default=""),
        sa.Column("meta_self_assessment", sa.Float(), nullable=False, default=0.5),
        sa.Column("meta_calibration_error", sa.Float(), nullable=False, default=0.0),
        sa.Column("meta_direction", sa.String(16), nullable=False, default="accurate"),
        sa.Column("eng_xp", sa.Integer(), nullable=False, default=0),
        sa.Column("eng_streak_current", sa.Integer(), nullable=False, default=0),
        sa.Column("eng_streak_longest", sa.Integer(), nullable=False, default=0),
        sa.Column("eng_flow_score", sa.Float(), nullable=False, default=0.0),
        sa.Column("eng_last_practice_date", sa.String(16), nullable=False, default=""),
        sa.Column("goal_toward", sa.Float(), nullable=False, default=0.0),
        sa.Column("goal_distance", sa.Integer(), nullable=False, default=-1),
        sa.Column("goal_on_critical_path", sa.Boolean(), nullable=False, default=False),
        sa.Column("comp_chunk_id", sa.String(32), nullable=False, default=""),
        sa.Column("comp_chunking_status", sa.String(16), nullable=False, default="none"),
        sa.Column("pred_top_down_mean", sa.Float(), nullable=False, default=0.0),
        sa.Column("pred_prediction_error", sa.Float(), nullable=False, default=0.0),
        sa.Column("pred_error_flag", sa.Boolean(), nullable=False, default=False),
        sa.Column("load_intrinsic", sa.Float(), nullable=False, default=1.0),
        sa.Column("load_dynamic", sa.Float(), nullable=False, default=1.0),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now(), onupdate=sa.func.now()),
        sa.ForeignKeyConstraint(["node_id"], ["knowledge_nodes.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("node_id"),
    )
    op.create_index("ix_cognitive_projections_user_urgency", "cognitive_node_projections", ["user_id", "sched_urgency"])
    op.create_index("ix_cognitive_projections_user_next_review", "cognitive_node_projections", ["user_id", "sched_next_review"])

    # ── 6. 错误聚类子表 ──
    op.create_table(
        "cognitive_node_error_clusters",
        sa.Column("id", sa.String(32), nullable=False),
        sa.Column("user_id", sa.String(64), nullable=False, index=True),
        sa.Column("node_id", sa.String(32), nullable=False, index=True),
        sa.Column("error_type", sa.String(64), nullable=False),
        sa.Column("frequency", sa.Integer(), nullable=False, default=1),
        sa.Column("last_occurred", sa.Float(), nullable=False),
        sa.Column("cluster_metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=False, default=dict),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now(), onupdate=sa.func.now()),
        sa.ForeignKeyConstraint(["node_id"], ["knowledge_nodes.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )

    # ── 7. 深度加工子表 ──
    op.create_table(
        "cognitive_node_deep_processing",
        sa.Column("id", sa.String(32), nullable=False),
        sa.Column("user_id", sa.String(64), nullable=False, index=True),
        sa.Column("node_id", sa.String(32), nullable=False, index=True),
        sa.Column("task_type", sa.String(32), nullable=False),
        sa.Column("status", sa.String(16), nullable=False, default="pending"),
        sa.Column("prompt", sa.Text(), nullable=False, default=""),
        sa.Column("result", postgresql.JSONB(astext_type=sa.Text()), nullable=False, default=dict),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["node_id"], ["knowledge_nodes.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )

    # ── 8. 组块成员子表 ──
    op.create_table(
        "cognitive_node_composition_members",
        sa.Column("id", sa.String(32), nullable=False),
        sa.Column("chunk_id", sa.String(32), nullable=False, index=True),
        sa.Column("user_id", sa.String(64), nullable=False, index=True),
        sa.Column("node_id", sa.String(32), nullable=False, index=True),
        sa.Column("co_occurrence_count", sa.Integer(), nullable=False, default=1),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["node_id"], ["knowledge_nodes.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("chunk_id", "node_id", name="uq_composition_members"),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table("cognitive_node_composition_members")
    op.drop_table("cognitive_node_deep_processing")
    op.drop_table("cognitive_node_error_clusters")
    op.drop_table("cognitive_node_projections")
    op.drop_table("cognitive_events")
    op.drop_table("practice_events")
    op.drop_table("knowledge_edges")

    op.drop_index("ix_knowledge_nodes_user_label", table_name="knowledge_nodes")
    op.drop_index("ix_knowledge_nodes_user_level", table_name="knowledge_nodes")
    op.alter_column("knowledge_nodes", "created_by", type_=sa.Text())
    op.execute("ALTER TABLE IF EXISTS knowledge_nodes RENAME COLUMN parent_id TO parent")

    for col in _OBSOLETE_KNOWLEDGE_NODE_COLUMNS:
        op.add_column("knowledge_nodes", sa.Column(col, postgresql.JSONB, nullable=True))
