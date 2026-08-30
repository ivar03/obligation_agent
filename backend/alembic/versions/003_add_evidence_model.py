"""Add obligation_evidence table

Revision ID: 003_add_evidence_model
Revises: 002_add_graph_support
Create Date: 2026-08-30 15:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '003_add_evidence_model'
down_revision: Union[str, None] = '002_add_graph_support'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'obligation_evidence',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('obligation_id', sa.String(length=36), nullable=False),
        sa.Column('evidence_type', sa.Enum('MESSAGE', 'DOCUMENT', 'FILE', 'EVENT', 'MANUAL', 'SYSTEM', name='evidence_type_enum', native_enum=False), nullable=False),
        sa.Column('source_type', sa.String(length=64), nullable=False),
        sa.Column('source_ref', sa.String(length=255), nullable=True),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('correlation_status', sa.Enum('DETECTED', 'SUGGESTED', 'CONFIRMED', 'REJECTED', name='correlation_status_enum', native_enum=False), nullable=False),
        sa.Column('correlation_confidence', sa.Float(), nullable=False),
        sa.Column('semantic_role', sa.Enum('COMPLETION_SIGNAL', 'COMMITMENT', 'REQUEST', 'PROGRESS_UPDATE', 'NON_COMPLETION_SIGNAL', 'IRRELEVANT', name='event_semantic_role_enum', native_enum=False), nullable=False),
        sa.Column('reasoning', sa.JSON(), nullable=True),
        sa.Column('extra_metadata', sa.JSON(), nullable=True),
        sa.Column('actor', sa.String(length=255), nullable=True),
        sa.Column('observed_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['obligation_id'], ['obligations.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('source_type', 'source_ref', 'obligation_id', name='uq_evidence_source_ob')
    )
    op.create_index(op.f('ix_obligation_evidence_id'), 'obligation_evidence', ['id'], unique=False)
    op.create_index(op.f('ix_obligation_evidence_obligation_id'), 'obligation_evidence', ['obligation_id'], unique=False)
    op.create_index(op.f('ix_obligation_evidence_source_ref'), 'obligation_evidence', ['source_ref'], unique=False)
    op.create_index(op.f('ix_obligation_evidence_correlation_status'), 'obligation_evidence', ['correlation_status'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_obligation_evidence_correlation_status'), table_name='obligation_evidence')
    op.drop_index(op.f('ix_obligation_evidence_source_ref'), table_name='obligation_evidence')
    op.drop_index(op.f('ix_obligation_evidence_obligation_id'), table_name='obligation_evidence')
    op.drop_index(op.f('ix_obligation_evidence_id'), table_name='obligation_evidence')
    op.drop_table('obligation_evidence')
