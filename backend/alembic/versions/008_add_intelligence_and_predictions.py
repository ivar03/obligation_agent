"""Add intelligence and prediction snapshots tables

Revision ID: 008_add_intelligence_and_predictions
Revises: 007_add_reconciliation
Create Date: 2026-08-31 03:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '008_add_intelligence_and_predictions'
down_revision: Union[str, None] = '007_add_reconciliation'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Create obligation_outcome_snapshots
    op.create_table(
        'obligation_outcome_snapshots',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('obligation_id', sa.String(length=36), nullable=False),
        sa.Column('snapshot_time', sa.DateTime(timezone=True), nullable=False),
        sa.Column('status', sa.String(length=32), nullable=False),
        sa.Column('outcome_type', sa.String(length=64), nullable=False),
        sa.Column('owner', sa.String(length=255), nullable=False),
        sa.Column('beneficiary', sa.String(length=255), nullable=False),
        sa.Column('obligation_type', sa.String(length=32), nullable=False),
        sa.Column('action', sa.Text(), nullable=False),
        sa.Column('deadline', sa.DateTime(timezone=True), nullable=True),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('delay_hours', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('risk_score', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('risk_level', sa.String(length=32), nullable=False, server_default='LOW'),
        sa.Column('dependency_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('blocker_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('evidence_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('intervention_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('intervention_required', sa.Boolean(), nullable=False, server_default=sa.text('0')),
        sa.Column('intervention_successful', sa.Boolean(), nullable=False, server_default=sa.text('0')),
        sa.Column('reconciliation_conflict_occurred', sa.Boolean(), nullable=False, server_default=sa.text('0')),
        sa.Column('relevant_event_signals', sa.JSON(), nullable=True),
        sa.Column('extra_metadata', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['obligation_id'], ['obligations.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_obligation_outcome_snapshots_id'), 'obligation_outcome_snapshots', ['id'], unique=False)
    op.create_index(op.f('ix_obligation_outcome_snapshots_obligation_id'), 'obligation_outcome_snapshots', ['obligation_id'], unique=False)
    op.create_index(op.f('ix_obligation_outcome_snapshots_outcome_type'), 'obligation_outcome_snapshots', ['outcome_type'], unique=False)
    op.create_index(op.f('ix_obligation_outcome_snapshots_owner'), 'obligation_outcome_snapshots', ['owner'], unique=False)
    op.create_index(op.f('ix_obligation_outcome_snapshots_created_at'), 'obligation_outcome_snapshots', ['created_at'], unique=False)

    # 2. Create prediction_snapshots
    op.create_table(
        'prediction_snapshots',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('obligation_id', sa.String(length=36), nullable=False),
        sa.Column('model_version', sa.String(length=64), nullable=False, server_default='predictive-v1'),
        sa.Column('prediction_type', sa.String(length=64), nullable=False, server_default='FAILURE_PROBABILITY'),
        sa.Column('failure_probability', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('completion_probability', sa.Float(), nullable=False, server_default='1.0'),
        sa.Column('expected_delay_hours', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('intervention_likelihood', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('blockage_likelihood', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('confidence', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('prediction_reasons', sa.JSON(), nullable=True),
        sa.Column('preventative_recommendation', sa.Text(), nullable=True),
        sa.Column('recommended_action_type', sa.String(length=64), nullable=True),
        sa.Column('actual_outcome', sa.String(length=64), nullable=True),
        sa.Column('actual_delay_hours', sa.Float(), nullable=True),
        sa.Column('evaluated_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('prediction_error', sa.Float(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['obligation_id'], ['obligations.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_prediction_snapshots_id'), 'prediction_snapshots', ['id'], unique=False)
    op.create_index(op.f('ix_prediction_snapshots_obligation_id'), 'prediction_snapshots', ['obligation_id'], unique=False)
    op.create_index(op.f('ix_prediction_snapshots_model_version'), 'prediction_snapshots', ['model_version'], unique=False)
    op.create_index(op.f('ix_prediction_snapshots_created_at'), 'prediction_snapshots', ['created_at'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_prediction_snapshots_created_at'), table_name='prediction_snapshots')
    op.drop_index(op.f('ix_prediction_snapshots_model_version'), table_name='prediction_snapshots')
    op.drop_index(op.f('ix_prediction_snapshots_obligation_id'), table_name='prediction_snapshots')
    op.drop_index(op.f('ix_prediction_snapshots_id'), table_name='prediction_snapshots')
    op.drop_table('prediction_snapshots')

    op.drop_index(op.f('ix_obligation_outcome_snapshots_created_at'), table_name='obligation_outcome_snapshots')
    op.drop_index(op.f('ix_obligation_outcome_snapshots_owner'), table_name='obligation_outcome_snapshots')
    op.drop_index(op.f('ix_obligation_outcome_snapshots_outcome_type'), table_name='obligation_outcome_snapshots')
    op.drop_index(op.f('ix_obligation_outcome_snapshots_obligation_id'), table_name='obligation_outcome_snapshots')
    op.drop_index(op.f('ix_obligation_outcome_snapshots_id'), table_name='obligation_outcome_snapshots')
    op.drop_table('obligation_outcome_snapshots')
