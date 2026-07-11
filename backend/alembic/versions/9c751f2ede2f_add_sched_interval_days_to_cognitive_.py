"""add sched_interval_days to cognitive_node_projections

Revision ID: 9c751f2ede2f
Revises: 3228233e13ee
Create Date: 2026-07-11 12:50:45.574803

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '9c751f2ede2f'
down_revision: Union[str, Sequence[str], None] = '3228233e13ee'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """为 cognitive_node_projections 补充 sched_interval_days 列。"""
    op.add_column(
        'cognitive_node_projections',
        sa.Column('sched_interval_days', sa.Float(), nullable=False, server_default='1.0'),
    )
    op.alter_column('cognitive_node_projections', 'sched_interval_days', server_default=None)


def downgrade() -> None:
    """移除 sched_interval_days 列。"""
    op.drop_column('cognitive_node_projections', 'sched_interval_days')
