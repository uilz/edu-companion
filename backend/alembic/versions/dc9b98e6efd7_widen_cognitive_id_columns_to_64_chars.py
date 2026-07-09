"""widen cognitive id columns to 64 chars

Revision ID: dc9b98e6efd7
Revises: 1bf173434c24
Create Date: 2026-07-09 18:52:05.334267

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'dc9b98e6efd7'
down_revision: Union[str, Sequence[str], None] = '1bf173434c24'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _alter_varchar(table: str, column: str, length: int = 64) -> None:
    op.alter_column(
        table,
        column,
        existing_type=sa.VARCHAR(length=32),
        type_=sa.VARCHAR(length=length),
        existing_nullable=True,
    )


def upgrade() -> None:
    """Widen all cognitive ID columns to support UUIDs and long slugs."""
    # Edge layer
    _alter_varchar("knowledge_edges", "id")
    _alter_varchar("knowledge_edges", "source_id")
    _alter_varchar("knowledge_edges", "target_id")

    # Event layer
    _alter_varchar("practice_events", "id")
    _alter_varchar("practice_events", "node_id")
    _alter_varchar("cognitive_events", "id")
    _alter_varchar("cognitive_events", "node_id")

    # Projection layer
    _alter_varchar("cognitive_node_projections", "node_id")

    # List sub-tables
    _alter_varchar("cognitive_node_error_clusters", "id")
    _alter_varchar("cognitive_node_error_clusters", "node_id")
    _alter_varchar("cognitive_node_deep_processing", "id")
    _alter_varchar("cognitive_node_deep_processing", "node_id")
    _alter_varchar("cognitive_node_composition_members", "id")
    _alter_varchar("cognitive_node_composition_members", "chunk_id")
    _alter_varchar("cognitive_node_composition_members", "node_id")


def downgrade() -> None:
    """Narrow columns back to 32 chars (not recommended if data > 32 chars exists)."""
    _alter_varchar("cognitive_node_composition_members", "node_id")
    _alter_varchar("cognitive_node_composition_members", "chunk_id")
    _alter_varchar("cognitive_node_composition_members", "id")
    _alter_varchar("cognitive_node_deep_processing", "node_id")
    _alter_varchar("cognitive_node_deep_processing", "id")
    _alter_varchar("cognitive_node_error_clusters", "node_id")
    _alter_varchar("cognitive_node_error_clusters", "id")
    _alter_varchar("cognitive_node_projections", "node_id")
    _alter_varchar("cognitive_events", "node_id")
    _alter_varchar("cognitive_events", "id")
    _alter_varchar("practice_events", "node_id")
    _alter_varchar("practice_events", "id")
    _alter_varchar("knowledge_edges", "target_id")
    _alter_varchar("knowledge_edges", "source_id")
    _alter_varchar("knowledge_edges", "id")
