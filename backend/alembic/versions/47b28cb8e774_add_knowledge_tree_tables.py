"""add_knowledge_tree_tables

Revision ID: 47b28cb8e774
Revises: 9c751f2ede2f
Create Date: 2026-07-11 17:04:10.176336

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '47b28cb8e774'
down_revision: Union[str, Sequence[str], None] = '9c751f2ede2f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'knowledge_trees',
        sa.Column('id', sa.String(length=32), nullable=False),
        sa.Column('user_id', sa.String(length=64), nullable=False),
        sa.Column('title', sa.String(length=255), nullable=False),
        sa.Column('description', sa.Text(), nullable=False),
        sa.Column('tree_type', sa.String(length=32), nullable=False),
        sa.Column('root_node_id', sa.String(length=32), nullable=True),
        sa.Column('default_view_mode', sa.String(length=32), nullable=False),
        sa.Column('default_layout', sa.String(length=32), nullable=False),
        sa.Column('tags', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('meta', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('status', sa.String(length=32), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('version', sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_knowledge_trees_user', 'knowledge_trees', ['user_id'], unique=False)
    op.create_index('ix_knowledge_trees_user_status', 'knowledge_trees', ['user_id', 'status'], unique=False)

    op.create_table(
        'tree_nodes',
        sa.Column('id', sa.String(length=32), nullable=False),
        sa.Column('tree_id', sa.String(length=32), nullable=False),
        sa.Column('user_id', sa.String(length=64), nullable=False),
        sa.Column('label', sa.String(length=255), nullable=False),
        sa.Column('node_type', sa.String(length=32), nullable=False),
        sa.Column('parent_id', sa.String(length=32), nullable=True),
        sa.Column('children_order', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('order_index', sa.Integer(), nullable=False),
        sa.Column('color', sa.String(length=16), nullable=False),
        sa.Column('emoji', sa.String(length=8), nullable=False),
        sa.Column('icon_url', sa.String(length=512), nullable=False),
        sa.Column('position', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('source_refs', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('tags', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('brief', sa.Text(), nullable=False),
        sa.Column('meta', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('status', sa.String(length=32), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('version', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['parent_id'], ['tree_nodes.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['tree_id'], ['knowledge_trees.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_tree_nodes_tree', 'tree_nodes', ['tree_id'], unique=False)
    op.create_index('ix_tree_nodes_user', 'tree_nodes', ['user_id'], unique=False)
    op.create_index('ix_tree_nodes_parent', 'tree_nodes', ['parent_id'], unique=False)
    op.create_index('ix_tree_nodes_tree_status', 'tree_nodes', ['tree_id', 'status'], unique=False)

    op.create_table(
        'tree_edges',
        sa.Column('id', sa.String(length=32), nullable=False),
        sa.Column('tree_id', sa.String(length=32), nullable=False),
        sa.Column('user_id', sa.String(length=64), nullable=False),
        sa.Column('source_node_id', sa.String(length=32), nullable=False),
        sa.Column('target_node_id', sa.String(length=32), nullable=False),
        sa.Column('edge_type', sa.String(length=32), nullable=False),
        sa.Column('strength', sa.Float(), nullable=False),
        sa.Column('is_user_confirmed', sa.Boolean(), nullable=False),
        sa.Column('is_inferred', sa.Boolean(), nullable=False),
        sa.Column('meta', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['source_node_id'], ['tree_nodes.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['target_node_id'], ['tree_nodes.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['tree_id'], ['knowledge_trees.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('tree_id', 'source_node_id', 'target_node_id', 'edge_type')
    )
    op.create_index('ix_tree_edges_tree', 'tree_edges', ['tree_id'], unique=False)
    op.create_index('ix_tree_edges_source', 'tree_edges', ['source_node_id'], unique=False)
    op.create_index('ix_tree_edges_target', 'tree_edges', ['target_node_id'], unique=False)

    op.create_table(
        'tree_node_cognitive_links',
        sa.Column('id', sa.String(length=32), nullable=False),
        sa.Column('tree_id', sa.String(length=32), nullable=False),
        sa.Column('tree_node_id', sa.String(length=32), nullable=False),
        sa.Column('cognitive_node_id', sa.String(length=64), nullable=False),
        sa.Column('user_id', sa.String(length=64), nullable=False),
        sa.Column('link_role', sa.String(length=32), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['tree_id'], ['knowledge_trees.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['tree_node_id'], ['tree_nodes.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('tree_id', 'tree_node_id', 'cognitive_node_id')
    )
    op.create_index('ix_tree_cognitive_links_tree', 'tree_node_cognitive_links', ['tree_id'], unique=False)
    op.create_index('ix_tree_cognitive_links_tree_node', 'tree_node_cognitive_links', ['tree_node_id'], unique=False)
    op.create_index('ix_tree_cognitive_links_cognitive', 'tree_node_cognitive_links', ['cognitive_node_id'], unique=False)
    op.create_index('ix_tree_cognitive_links_user', 'tree_node_cognitive_links', ['user_id'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table('tree_node_cognitive_links')
    op.drop_table('tree_edges')
    op.drop_table('tree_nodes')
    op.drop_table('knowledge_trees')
