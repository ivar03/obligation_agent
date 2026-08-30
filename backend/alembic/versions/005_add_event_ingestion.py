"""Add ingested_events table

Revision ID: 005_add_event_ingestion
Revises: 004_add_intervention_model
Create Date: 2026-08-30 20:05:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '005_add_event_ingestion'
down_revision: Union[str, None] = '004_add_intervention_model'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'ingested_events',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('provider', sa.String(length=64), nullable=False),
        sa.Column('source_type', sa.String(length=64), nullable=False),
        sa.Column('source_ref', sa.String(length=255), nullable=True),
        sa.Column('sender', sa.String(length=255), nullable=True),
        sa.Column('recipients', sa.JSON(), nullable=True),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('semantic_role', sa.Enum(
            'COMPLETION_SIGNAL',
            'COMMITMENT',
            'REQUEST',
            'PROGRESS_UPDATE',
            'NON_COMPLETION_SIGNAL',
            'IRRELEVANT',
            name='event_semantic_role_enum',
            native_enum=False
        ), nullable=False),
        sa.Column('processing_status', sa.String(length=32), nullable=False),
        sa.Column('candidate_obligation_ids', sa.JSON(), nullable=True),
        sa.Column('correlated_obligation_id', sa.String(length=36), nullable=True),
        sa.Column('evidence_id', sa.String(length=36), nullable=True),
        sa.Column('correlation_confidence', sa.Float(), nullable=True),
        sa.Column('match_explanation', sa.Text(), nullable=True),
        sa.Column('action_taken', sa.String(length=64), nullable=True),
        sa.Column('resolved_intervention_id', sa.String(length=36), nullable=True),
        sa.Column('raw_payload', sa.JSON(), nullable=True),
        sa.Column('received_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['correlated_obligation_id'], ['obligations.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['evidence_id'], ['obligation_evidence.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['resolved_intervention_id'], ['interventions.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_ingested_events_id'), 'ingested_events', ['id'], unique=False)
    op.create_index(op.f('ix_ingested_events_provider'), 'ingested_events', ['provider'], unique=False)
    op.create_index(op.f('ix_ingested_events_source_ref'), 'ingested_events', ['source_ref'], unique=False)
    op.create_index(op.f('ix_ingested_events_semantic_role'), 'ingested_events', ['semantic_role'], unique=False)
    op.create_index(op.f('ix_ingested_events_processing_status'), 'ingested_events', ['processing_status'], unique=False)
    op.create_index(op.f('ix_ingested_events_correlated_obligation_id'), 'ingested_events', ['correlated_obligation_id'], unique=False)
    op.create_index(op.f('ix_ingested_events_evidence_id'), 'ingested_events', ['evidence_id'], unique=False)
    op.create_index(op.f('ix_ingested_events_received_at'), 'ingested_events', ['received_at'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_ingested_events_received_at'), table_name='ingested_events')
    op.drop_index(op.f('ix_ingested_events_evidence_id'), table_name='ingested_events')
    op.drop_index(op.f('ix_ingested_events_correlated_obligation_id'), table_name='ingested_events')
    op.drop_index(op.f('ix_ingested_events_processing_status'), table_name='ingested_events')
    op.drop_index(op.f('ix_ingested_events_semantic_role'), table_name='ingested_events')
    op.drop_index(op.f('ix_ingested_events_source_ref'), table_name='ingested_events')
    op.drop_index(op.f('ix_ingested_events_provider'), table_name='ingested_events')
    op.drop_index(op.f('ix_ingested_events_id'), table_name='ingested_events')
    op.drop_table('ingested_events')
