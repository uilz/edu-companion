"""migrate cognitive projections to beta belief model

Revision ID: 45cad95ec888
Revises: 459a1ae1b950
Create Date: 2026-07-09 21:36:00.238109

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '45cad95ec888'
down_revision: Union[str, Sequence[str], None] = '459a1ae1b950'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """将 cognitive 子系统迁移到 Beta 概率信念模型。"""

    # ── 1. 练习事件：记录行为主体与来源 ──
    op.add_column(
        'practice_events',
        sa.Column('actor_type', sa.String(length=16), nullable=False, server_default='user'),
    )
    op.add_column(
        'practice_events',
        sa.Column('source_type', sa.String(length=64), nullable=False, server_default=''),
    )
    op.add_column(
        'practice_events',
        sa.Column('source_id', sa.String(length=64), nullable=False, server_default=''),
    )
    # 移除 server_default，后续由应用层默认值控制
    op.alter_column('practice_events', 'actor_type', server_default=None)
    op.alter_column('practice_events', 'source_type', server_default=None)
    op.alter_column('practice_events', 'source_id', server_default=None)

    # ── 2. 认知领域事件：记录行为主体 ──
    op.add_column(
        'cognitive_events',
        sa.Column('actor_type', sa.String(length=16), nullable=False, server_default='user'),
    )
    op.alter_column('cognitive_events', 'actor_type', server_default=None)

    # ── 3. 知识边：新增传播控制参数 ──
    op.add_column(
        'knowledge_edges',
        sa.Column('edge_weight', sa.Float(), nullable=False, server_default='0.5'),
    )
    op.add_column(
        'knowledge_edges',
        sa.Column('edge_distance_decay', sa.Float(), nullable=False, server_default='0.5'),
    )
    op.add_column(
        'knowledge_edges',
        sa.Column('max_propagation_hops', sa.Integer(), nullable=False, server_default='2'),
    )
    op.alter_column('knowledge_edges', 'edge_weight', server_default=None)
    op.alter_column('knowledge_edges', 'edge_distance_decay', server_default=None)
    op.alter_column('knowledge_edges', 'max_propagation_hops', server_default=None)

    # ── 4. 派生状态投影：Beta 信念与相关参数 ──
    _add_beta_projection_columns()

    # ── 5. 移除旧 BKT-lite 字段 ──
    _drop_bkt_columns()


def _add_beta_projection_columns() -> None:
    """新增 Beta 信念、衰减、信息增益与图传播字段。"""
    columns = [
        ('belief_alpha', sa.Float(), '1.0'),
        ('belief_beta', sa.Float(), '1.0'),
        ('belief_evidence_count', sa.Integer(), '0'),
        ('belief_last_updated', sa.Float(), '0.0'),
        ('stability_factor', sa.Float(), '0.5'),
        ('forgetting_rate', sa.Float(), '0.1'),
        ('total_information_gain', sa.Float(), '0.0'),
        ('last_information_gain', sa.Float(), '0.0'),
        ('independent_evidence_weight', sa.Float(), '1.0'),
    ]
    for name, col_type, default in columns:
        op.add_column(
            'cognitive_node_projections',
            sa.Column(name, col_type, nullable=False, server_default=default),
        )
        op.alter_column('cognitive_node_projections', name, server_default=None)


def _drop_bkt_columns() -> None:
    """清理已废弃的 BKT-lite 列。"""
    bkt_columns = [
        'bkt_proficiency',
        'bkt_peak',
        'bkt_last_updated',
        'bkt_slip',
        'bkt_known',
        'bkt_guess',
        'bkt_learn',
        'bkt_forget',
    ]
    for col in bkt_columns:
        op.drop_column('cognitive_node_projections', col)


def downgrade() -> None:
    """回滚到 BKT-lite 模型。"""

    # 恢复 BKT 列
    op.add_column(
        'cognitive_node_projections',
        sa.Column('bkt_learn', sa.DOUBLE_PRECISION(precision=53), autoincrement=False, nullable=False, server_default='0.3'),
    )
    op.add_column(
        'cognitive_node_projections',
        sa.Column('bkt_guess', sa.DOUBLE_PRECISION(precision=53), autoincrement=False, nullable=False, server_default='0.2'),
    )
    op.add_column(
        'cognitive_node_projections',
        sa.Column('bkt_known', sa.DOUBLE_PRECISION(precision=53), autoincrement=False, nullable=False, server_default='0.3'),
    )
    op.add_column(
        'cognitive_node_projections',
        sa.Column('bkt_slip', sa.DOUBLE_PRECISION(precision=53), autoincrement=False, nullable=False, server_default='0.1'),
    )
    op.add_column(
        'cognitive_node_projections',
        sa.Column('bkt_peak', sa.DOUBLE_PRECISION(precision=53), autoincrement=False, nullable=False, server_default='0.3'),
    )
    op.add_column(
        'cognitive_node_projections',
        sa.Column('bkt_forget', sa.DOUBLE_PRECISION(precision=53), autoincrement=False, nullable=False, server_default='0.05'),
    )
    op.add_column(
        'cognitive_node_projections',
        sa.Column('bkt_last_updated', sa.DOUBLE_PRECISION(precision=53), autoincrement=False, nullable=False, server_default='0.0'),
    )
    op.add_column(
        'cognitive_node_projections',
        sa.Column('bkt_proficiency', sa.DOUBLE_PRECISION(precision=53), autoincrement=False, nullable=False, server_default='0.3'),
    )

    # 移除 Beta 相关列
    beta_columns = [
        'independent_evidence_weight',
        'last_information_gain',
        'total_information_gain',
        'forgetting_rate',
        'stability_factor',
        'belief_last_updated',
        'belief_evidence_count',
        'belief_beta',
        'belief_alpha',
    ]
    for col in beta_columns:
        op.drop_column('cognitive_node_projections', col)

    # 移除边传播参数
    op.drop_column('knowledge_edges', 'max_propagation_hops')
    op.drop_column('knowledge_edges', 'edge_distance_decay')
    op.drop_column('knowledge_edges', 'edge_weight')

    # 移除事件主体/来源字段
    op.drop_column('cognitive_events', 'actor_type')
    op.drop_column('practice_events', 'source_id')
    op.drop_column('practice_events', 'source_type')
    op.drop_column('practice_events', 'actor_type')
