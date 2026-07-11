"""add conversation notes and answer telemetry tables

Revision ID: 3228233e13ee
Revises: 0825f5cc175f
Create Date: 2026-07-11 12:11:47.022994

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '3228233e13ee'
down_revision: Union[str, Sequence[str], None] = '0825f5cc175f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add tables for Phase 3 conversation-flashcard integration."""
    # conversation_notes: 对话笔记，与闪卡双向同步
    op.create_table(
        'conversation_notes',
        sa.Column('id', sa.String(length=32), nullable=False),
        sa.Column('user_id', sa.String(length=32), nullable=False),
        sa.Column('conv_id', sa.String(length=32), nullable=False),
        sa.Column('source_message_id', sa.String(length=32), nullable=False),
        sa.Column('front_text', sa.Text(), nullable=False),
        sa.Column('back_text', sa.Text(), nullable=True),
        sa.Column('back_context', sa.Text(), nullable=True),
        sa.Column('language', sa.String(length=10), nullable=True),
        sa.Column('tags', postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default='[]'),
        sa.Column('linked_node_ids', postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default='[]'),
        sa.Column('source_ref', postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default='{}'),
        sa.Column('flashcard_id', sa.String(length=32), nullable=True),
        sa.Column('status', sa.String(length=16), nullable=False, server_default='draft'),
        sa.Column('field_versions', postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default='{}'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.ForeignKeyConstraint(['flashcard_id'], ['flashcards.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_conversation_notes_conv', 'conversation_notes', ['conv_id'], unique=False)
    op.create_index('ix_conversation_notes_flashcard', 'conversation_notes', ['flashcard_id'], unique=False)
    op.create_index('ix_conversation_notes_user', 'conversation_notes', ['user_id'], unique=False)

    # answer_telemetry: 答题行为遥测原始数据
    op.create_table(
        'answer_telemetry',
        sa.Column('id', sa.String(length=32), nullable=False),
        sa.Column('user_id', sa.String(length=32), nullable=False),
        sa.Column('telemetry_id', sa.String(length=64), nullable=False),
        sa.Column('session_id', sa.String(length=32), nullable=True),
        sa.Column('question_id', sa.String(length=32), nullable=False),
        sa.Column('attempt_id', sa.String(length=32), nullable=False),
        sa.Column('raw_events', postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default='[]'),
        sa.Column('derived', postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default='{}'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('telemetry_id')
    )
    op.create_index('ix_answer_telemetry_attempt', 'answer_telemetry', ['attempt_id'], unique=False)
    op.create_index('ix_answer_telemetry_user', 'answer_telemetry', ['user_id'], unique=False)

    # diagnostic_signals: 由遥测派生的诊断信号
    op.create_table(
        'diagnostic_signals',
        sa.Column('id', sa.String(length=32), nullable=False),
        sa.Column('user_id', sa.String(length=32), nullable=False),
        sa.Column('attempt_id', sa.String(length=32), nullable=False),
        sa.Column('question_id', sa.String(length=32), nullable=False),
        sa.Column('signals', postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default='{}'),
        sa.Column('interpretation', sa.Text(), nullable=True),
        sa.Column('suggested_action', sa.String(length=32), nullable=True),
        sa.Column('confidence', sa.Float(), nullable=False, server_default='0'),
        sa.Column('generated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_diagnostic_signals_attempt', 'diagnostic_signals', ['attempt_id'], unique=False)


def downgrade() -> None:
    """Drop Phase 3 tables."""
    op.drop_index('ix_diagnostic_signals_attempt', table_name='diagnostic_signals')
    op.drop_table('diagnostic_signals')

    op.drop_index('ix_answer_telemetry_user', table_name='answer_telemetry')
    op.drop_index('ix_answer_telemetry_attempt', table_name='answer_telemetry')
    op.drop_table('answer_telemetry')

    op.drop_index('ix_conversation_notes_user', table_name='conversation_notes')
    op.drop_index('ix_conversation_notes_flashcard', table_name='conversation_notes')
    op.drop_index('ix_conversation_notes_conv', table_name='conversation_notes')
    op.drop_table('conversation_notes')
