"""Add organizational memories table and indexes for Phase 16

Revision ID: 013_add_organizational_memories
Revises: 012_add_decision_plans
Create Date: 2026-08-31 14:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '013_add_organizational_memories'
down_revision: Union[str, None] = '012_add_decision_plans'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create organizational_memories table
    op.create_table(
        'organizational_memories',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('workspace_id', sa.String(length=36), nullable=False, server_default='ws-default'),
        sa.Column('memory_type', sa.String(length=64), nullable=False),
        sa.Column('source_type', sa.String(length=64), nullable=False, server_default='obligation'),
        sa.Column('source_ref', sa.String(length=255), nullable=True),
        sa.Column('obligation_id', sa.String(length=36), nullable=True),
        sa.Column('event_id', sa.String(length=36), nullable=True),
        sa.Column('owner_id', sa.String(length=128), nullable=True),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('semantic_summary', sa.Text(), nullable=False),
        sa.Column('semantic_labels', sa.JSON(), nullable=False),
        sa.Column('entities', sa.JSON(), nullable=False),
        sa.Column('topics', sa.JSON(), nullable=False),
        sa.Column('outcome', sa.String(length=64), nullable=True),
        sa.Column('observed_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('metadata_json', sa.JSON(), nullable=False),
        sa.Column('importance_score', sa.Float(), nullable=False, server_default='0.5'),
        sa.Column('confidence', sa.Float(), nullable=False, server_default='1.0'),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='1'),
        sa.ForeignKeyConstraint(['workspace_id'], ['workspaces.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['obligation_id'], ['obligations.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id')
    )

    op.create_index('ix_org_memories_ws_type', 'organizational_memories', ['workspace_id', 'memory_type'], unique=False)
    op.create_index('ix_org_memories_ws_owner', 'organizational_memories', ['workspace_id', 'owner_id'], unique=False)
    op.create_index('ix_org_memories_ws_observed', 'organizational_memories', ['workspace_id', 'observed_at'], unique=False)
    op.create_index('ix_org_memories_obligation', 'organizational_memories', ['obligation_id'], unique=False)
    op.create_index('ix_org_memories_event', 'organizational_memories', ['event_id'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_org_memories_event', table_name='organizational_memories')
    op.drop_index('ix_org_memories_obligation', table_name='organizational_memories')
    op.drop_index('ix_org_memories_ws_observed', table_name='organizational_memories')
    op.drop_index('ix_org_memories_ws_owner', table_name='organizational_memories')
    op.drop_index('ix_org_memories_ws_type', table_name='organizational_memories')
    op.drop_table('organizational_memories')
