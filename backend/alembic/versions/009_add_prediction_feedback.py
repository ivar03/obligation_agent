"""Add prediction feedback table

Revision ID: 009_add_prediction_feedback
Revises: 008_add_intelligence_and_predictions
Create Date: 2026-08-31 03:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '009_add_prediction_feedback'
down_revision: Union[str, None] = '008_add_intelligence_and_predictions'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'prediction_feedbacks',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('prediction_snapshot_id', sa.String(length=36), nullable=False),
        sa.Column('obligation_id', sa.String(length=36), nullable=False),
        sa.Column('prediction_provider', sa.String(length=64), nullable=False, server_default='deterministic-v1'),
        sa.Column('model_version', sa.String(length=64), nullable=False, server_default='predictive-v1'),
        sa.Column('predicted_failure_probability', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('predicted_completion_probability', sa.Float(), nullable=False, server_default='1.0'),
        sa.Column('predicted_expected_delay_hours', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('predicted_intervention_likelihood', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('predicted_confidence', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('feature_attributions', sa.JSON(), nullable=True),
        sa.Column('observed_outcome', sa.String(length=64), nullable=False),
        sa.Column('observed_delay_hours', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('absolute_delay_error', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('probability_error', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('was_high_risk_prediction_correct', sa.Boolean(), nullable=True),
        sa.Column('intervention_recommended', sa.Boolean(), nullable=False, server_default=sa.text('0')),
        sa.Column('intervention_taken', sa.Boolean(), nullable=False, server_default=sa.text('0')),
        sa.Column('intervention_effective', sa.Boolean(), nullable=True),
        sa.Column('extra_metadata', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['prediction_snapshot_id'], ['prediction_snapshots.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['obligation_id'], ['obligations.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_prediction_feedbacks_id'), 'prediction_feedbacks', ['id'], unique=False)
    op.create_index(op.f('ix_prediction_feedbacks_prediction_snapshot_id'), 'prediction_feedbacks', ['prediction_snapshot_id'], unique=False)
    op.create_index(op.f('ix_prediction_feedbacks_obligation_id'), 'prediction_feedbacks', ['obligation_id'], unique=False)
    op.create_index(op.f('ix_prediction_feedbacks_prediction_provider'), 'prediction_feedbacks', ['prediction_provider'], unique=False)
    op.create_index(op.f('ix_prediction_feedbacks_model_version'), 'prediction_feedbacks', ['model_version'], unique=False)
    op.create_index(op.f('ix_prediction_feedbacks_observed_outcome'), 'prediction_feedbacks', ['observed_outcome'], unique=False)
    op.create_index(op.f('ix_prediction_feedbacks_created_at'), 'prediction_feedbacks', ['created_at'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_prediction_feedbacks_created_at'), table_name='prediction_feedbacks')
    op.drop_index(op.f('ix_prediction_feedbacks_observed_outcome'), table_name='prediction_feedbacks')
    op.drop_index(op.f('ix_prediction_feedbacks_model_version'), table_name='prediction_feedbacks')
    op.drop_index(op.f('ix_prediction_feedbacks_prediction_provider'), table_name='prediction_feedbacks')
    op.drop_index(op.f('ix_prediction_feedbacks_obligation_id'), table_name='prediction_feedbacks')
    op.drop_index(op.f('ix_prediction_feedbacks_prediction_snapshot_id'), table_name='prediction_feedbacks')
    op.drop_index(op.f('ix_prediction_feedbacks_id'), table_name='prediction_feedbacks')
    op.drop_table('prediction_feedbacks')
