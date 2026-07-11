"""add learning_activities table

Revision ID: 7dbbae02fd26
Revises: 47b28cb8e774
Create Date: 2026-07-11 20:16:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '7dbbae02fd26'
down_revision: Union[str, Sequence[str], None] = '47b28cb8e774'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'learning_activities',
        sa.Column('id', sa.String(length=32), nullable=False),
        sa.Column('user_id', sa.String(length=64), nullable=False),
        sa.Column('activity_type', sa.String(length=32), nullable=False),
        sa.Column('module', sa.String(length=32), nullable=False),
        sa.Column('source_event_id', sa.String(length=64), nullable=True),
        sa.Column('source_event_type', sa.String(length=32), nullable=True),
        sa.Column('idempotency_key', sa.String(length=128), nullable=True),
        sa.Column('title', sa.String(length=255), nullable=False),
        sa.Column('description', sa.Text(), nullable=False),
        sa.Column('status', sa.String(length=32), nullable=False),
        sa.Column('timestamp', sa.DateTime(timezone=True), nullable=False),
        sa.Column('deep_link', sa.String(length=512), nullable=False),
        sa.Column('meta', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_learning_activities_activity_type'), 'learning_activities', ['activity_type'], unique=False)
    op.create_index(op.f('ix_learning_activities_idempotency_key'), 'learning_activities', ['idempotency_key'], unique=False)
    op.create_index(op.f('ix_learning_activities_module'), 'learning_activities', ['module'], unique=False)
    op.create_index(op.f('ix_learning_activities_timestamp'), 'learning_activities', ['timestamp'], unique=False)
    op.create_index(op.f('ix_learning_activities_user_id'), 'learning_activities', ['user_id'], unique=False)
    op.create_index('ix_learning_activities_user_module', 'learning_activities', ['user_id', 'module', 'timestamp'], unique=False)
    op.create_index('ix_learning_activities_user_time', 'learning_activities', ['user_id', 'timestamp'], unique=False)
    op.create_index('ix_learning_activities_user_type', 'learning_activities', ['user_id', 'activity_type', 'timestamp'], unique=False)
    op.create_index('ix_learning_activities_user_idempotency', 'learning_activities', ['user_id', 'idempotency_key'], unique=True)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index('ix_learning_activities_user_idempotency', table_name='learning_activities')
    op.drop_index('ix_learning_activities_user_type', table_name='learning_activities')
    op.drop_index('ix_learning_activities_user_time', table_name='learning_activities')
    op.drop_index('ix_learning_activities_user_module', table_name='learning_activities')
    op.drop_index(op.f('ix_learning_activities_user_id'), table_name='learning_activities')
    op.drop_index(op.f('ix_learning_activities_timestamp'), table_name='learning_activities')
    op.drop_index(op.f('ix_learning_activities_module'), table_name='learning_activities')
    op.drop_index(op.f('ix_learning_activities_idempotency_key'), table_name='learning_activities')
    op.drop_index(op.f('ix_learning_activities_activity_type'), table_name='learning_activities')
    op.drop_table('learning_activities')
