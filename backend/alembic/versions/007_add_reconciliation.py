"""Add reconciliation_records table

Revision ID: 007_add_reconciliation
Revises: 006_add_integrations
Create Date: 2026-08-31 02:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '007_add_reconciliation'
down_revision: Union[str, None] = '006_add_integrations'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'reconciliation_records',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('obligation_id', sa.String(length=36), nullable=False),
        sa.Column('status', sa.String(length=32), nullable=False, server_default='AMBIGUOUS'),
        sa.Column('confidence', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('consistency_score', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('contradiction_score', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('supporting_evidence_ids', sa.JSON(), nullable=True),
        sa.Column('conflicting_evidence_ids', sa.JSON(), nullable=True),
        sa.Column('supporting_event_ids', sa.JSON(), nullable=True),
        sa.Column('conflicting_event_ids', sa.JSON(), nullable=True),
        sa.Column('explanation', sa.JSON(), nullable=True),
        sa.Column('recommended_action', sa.String(length=64), nullable=True),
        sa.Column('resolution', sa.JSON(), nullable=True),
        sa.Column('resolved_by', sa.String(length=255), nullable=True),
        sa.Column('resolved_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['obligation_id'], ['obligations.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_reconciliation_records_id'), 'reconciliation_records', ['id'], unique=False)
    op.create_index(op.f('ix_reconciliation_records_obligation_id'), 'reconciliation_records', ['obligation_id'], unique=False)
    op.create_index(op.f('ix_reconciliation_records_status'), 'reconciliation_records', ['status'], unique=False)
    op.create_index(op.f('ix_reconciliation_records_created_at'), 'reconciliation_records', ['created_at'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_reconciliation_records_created_at'), table_name='reconciliation_records')
    op.drop_index(op.f('ix_reconciliation_records_status'), table_name='reconciliation_records')
    op.drop_index(op.f('ix_reconciliation_records_obligation_id'), table_name='reconciliation_records')
    op.drop_index(op.f('ix_reconciliation_records_id'), table_name='reconciliation_records')
    op.drop_table('reconciliation_records')
