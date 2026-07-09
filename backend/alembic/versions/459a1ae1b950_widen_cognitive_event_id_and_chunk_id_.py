"""widen cognitive event id and chunk id to 64

Revision ID: 459a1ae1b950
Revises: dc9b98e6efd7
Create Date: 2026-07-09 19:52:42.008568

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '459a1ae1b950'
down_revision: Union[str, Sequence[str], None] = 'dc9b98e6efd7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Widen remaining cognitive ID columns to 64 chars."""
    op.alter_column(
        "cognitive_events",
        "id",
        existing_type=sa.VARCHAR(length=32),
        type_=sa.VARCHAR(length=64),
        existing_nullable=False,
    )
    op.alter_column(
        "cognitive_node_projections",
        "comp_chunk_id",
        existing_type=sa.VARCHAR(length=32),
        type_=sa.VARCHAR(length=64),
        existing_nullable=False,
    )


def downgrade() -> None:
    """Narrow columns back to 32 chars."""
    op.alter_column(
        "cognitive_node_projections",
        "comp_chunk_id",
        existing_type=sa.VARCHAR(length=64),
        type_=sa.VARCHAR(length=32),
        existing_nullable=False,
    )
    op.alter_column(
        "cognitive_events",
        "id",
        existing_type=sa.VARCHAR(length=64),
        type_=sa.VARCHAR(length=32),
        existing_nullable=False,
    )
