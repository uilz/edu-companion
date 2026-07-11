"""add practice aggregate and feedback projections

Revision ID: 0825f5cc175f
Revises: 45cad95ec888
Create Date: 2026-07-10 19:39:16.261049

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '0825f5cc175f'
down_revision: Union[str, Sequence[str], None] = '45cad95ec888'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add practice aggregate snapshots, command records and feedback projections."""
    # 练习聚合根快照
    op.create_table(
        'practice_aggregate_snapshots',
        sa.Column('session_id', sa.String(length=64), nullable=False),
        sa.Column('user_id', sa.String(length=64), nullable=False),
        sa.Column('version', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('status', sa.String(length=16), nullable=False, server_default='created'),
        sa.Column('payload', postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default='{}'),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.PrimaryKeyConstraint('session_id')
    )
    op.create_index('ix_practice_snapshots_user_status', 'practice_aggregate_snapshots', ['user_id', 'status'], unique=False)
    op.create_index(op.f('ix_practice_aggregate_snapshots_user_id'), 'practice_aggregate_snapshots', ['user_id'], unique=False)

    # 练习命令记录（事件溯源）
    op.create_table(
        'practice_command_records',
        sa.Column('command_id', sa.String(length=64), nullable=False),
        sa.Column('session_id', sa.String(length=64), nullable=False),
        sa.Column('user_id', sa.String(length=64), nullable=False),
        sa.Column('command_type', sa.String(length=64), nullable=False),
        sa.Column('version', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('payload', postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default='{}'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.PrimaryKeyConstraint('command_id')
    )
    op.create_index('ix_practice_commands_session_version', 'practice_command_records', ['session_id', 'version'], unique=False)
    op.create_index('ix_practice_commands_user_type', 'practice_command_records', ['user_id', 'command_type'], unique=False)
    op.create_index(op.f('ix_practice_command_records_session_id'), 'practice_command_records', ['session_id'], unique=False)
    op.create_index(op.f('ix_practice_command_records_user_id'), 'practice_command_records', ['user_id'], unique=False)
    op.create_index(op.f('ix_practice_command_records_command_type'), 'practice_command_records', ['command_type'], unique=False)

    # 练习反馈投影
    op.create_table(
        'practice_feedback_projections',
        sa.Column('attempt_id', sa.String(length=64), nullable=False),
        sa.Column('user_id', sa.String(length=64), nullable=False),
        sa.Column('session_id', sa.String(length=64), nullable=False),
        sa.Column('question_id', sa.String(length=64), nullable=False),
        sa.Column('node_id', sa.String(length=64), nullable=True),
        sa.Column('is_correct', sa.Boolean(), nullable=False),
        sa.Column('information_gain', sa.Float(), nullable=False, server_default='0'),
        sa.Column('uncertainty_reduction_percent', sa.Float(), nullable=False, server_default='0'),
        sa.Column('metacognition_feedback', sa.Text(), nullable=False, server_default=''),
        sa.Column('analysis', sa.Text(), nullable=False, server_default=''),
        sa.Column('learning_tips', postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default='[]'),
        sa.Column('next_action_type', sa.String(length=32), nullable=False, server_default=''),
        sa.Column('next_action_text', sa.Text(), nullable=False, server_default=''),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.ForeignKeyConstraint(['node_id'], ['knowledge_nodes.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('attempt_id')
    )
    op.create_index('ix_practice_feedback_session', 'practice_feedback_projections', ['session_id'], unique=False)
    op.create_index('ix_practice_feedback_user', 'practice_feedback_projections', ['user_id'], unique=False)
    op.create_index(op.f('ix_practice_feedback_projections_question_id'), 'practice_feedback_projections', ['question_id'], unique=False)


def downgrade() -> None:
    """Drop practice aggregate snapshots, command records and feedback projections."""
    op.drop_index(op.f('ix_practice_feedback_projections_question_id'), table_name='practice_feedback_projections')
    op.drop_index('ix_practice_feedback_user', table_name='practice_feedback_projections')
    op.drop_index('ix_practice_feedback_session', table_name='practice_feedback_projections')
    op.drop_table('practice_feedback_projections')

    op.drop_index(op.f('ix_practice_command_records_command_type'), table_name='practice_command_records')
    op.drop_index(op.f('ix_practice_command_records_user_id'), table_name='practice_command_records')
    op.drop_index(op.f('ix_practice_command_records_session_id'), table_name='practice_command_records')
    op.drop_index('ix_practice_commands_user_type', table_name='practice_command_records')
    op.drop_index('ix_practice_commands_session_version', table_name='practice_command_records')
    op.drop_table('practice_command_records')

    op.drop_index(op.f('ix_practice_aggregate_snapshots_user_id'), table_name='practice_aggregate_snapshots')
    op.drop_index('ix_practice_snapshots_user_status', table_name='practice_aggregate_snapshots')
    op.drop_table('practice_aggregate_snapshots')
