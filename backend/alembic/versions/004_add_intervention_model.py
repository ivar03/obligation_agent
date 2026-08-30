"""Add interventions table

Revision ID: 004_add_intervention_model
Revises: 003_add_evidence_model
Create Date: 2026-08-30 19:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '004_add_intervention_model'
down_revision: Union[str, None] = '003_add_evidence_model'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'interventions',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('obligation_id', sa.String(length=36), nullable=False),
        sa.Column('intervention_type', sa.Enum(
            'FOLLOW_UP_OWNER',
            'REQUEST_STATUS_UPDATE',
            'REQUEST_MISSING_DELIVERABLE',
            'RESOLVE_DEPENDENCY',
            'REVIEW_EVIDENCE',
            'ASSIGN_OWNER',
            'CLARIFY_DEADLINE',
            'MONITOR_CONDITION',
            'NO_INTERVENTION',
            name='intervention_type_enum',
            native_enum=False
        ), nullable=False),
        sa.Column('target_owner', sa.String(length=255), nullable=False),
        sa.Column('target_beneficiary', sa.String(length=255), nullable=False),
        sa.Column('title', sa.String(length=512), nullable=False),
        sa.Column('rationale', sa.Text(), nullable=False),
        sa.Column('message_draft', sa.Text(), nullable=False),
        sa.Column('approved_message', sa.Text(), nullable=True),
        sa.Column('context_data', sa.JSON(), nullable=True),
        sa.Column('urgency', sa.String(length=32), nullable=False, default='MEDIUM'),
        sa.Column('status', sa.Enum(
            'DRAFT',
            'PENDING_REVIEW',
            'APPROVED',
            'SCHEDULED',
            'READY_TO_EXECUTE',
            'EXECUTED',
            'ACKNOWLEDGED',
            'RESOLVED',
            'CANCELLED',
            'EXPIRED',
            name='intervention_status_enum',
            native_enum=False
        ), nullable=False),
        sa.Column('outcome', sa.Enum(
            'ACKNOWLEDGED',
            'PROGRESS_REPORTED',
            'COMPLETED',
            'NO_RESPONSE',
            'NEGATIVE_RESPONSE',
            'REJECTED',
            'NOT_NEEDED',
            'UNKNOWN',
            name='intervention_outcome_enum',
            native_enum=False
        ), nullable=True),
        sa.Column('requires_approval', sa.Boolean(), nullable=False, default=True),
        sa.Column('approved_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('approved_by', sa.String(length=255), nullable=True),
        sa.Column('scheduled_for', sa.DateTime(timezone=True), nullable=True),
        sa.Column('executed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('execution_reference', sa.String(length=255), nullable=True),
        sa.Column('execution_mode', sa.String(length=64), nullable=False, default='MOCK_DEMO'),
        sa.Column('follow_up_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('cooldown_until', sa.DateTime(timezone=True), nullable=True),
        sa.Column('chain_depth', sa.Integer(), nullable=False, default=1),
        sa.Column('audit_trail', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['obligation_id'], ['obligations.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_interventions_id'), 'interventions', ['id'], unique=False)
    op.create_index(op.f('ix_interventions_obligation_id'), 'interventions', ['obligation_id'], unique=False)
    op.create_index(op.f('ix_interventions_intervention_type'), 'interventions', ['intervention_type'], unique=False)
    op.create_index(op.f('ix_interventions_target_owner'), 'interventions', ['target_owner'], unique=False)
    op.create_index(op.f('ix_interventions_urgency'), 'interventions', ['urgency'], unique=False)
    op.create_index(op.f('ix_interventions_status'), 'interventions', ['status'], unique=False)
    op.create_index(op.f('ix_interventions_scheduled_for'), 'interventions', ['scheduled_for'], unique=False)
    op.create_index(op.f('ix_interventions_created_at'), 'interventions', ['created_at'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_interventions_created_at'), table_name='interventions')
    op.drop_index(op.f('ix_interventions_scheduled_for'), table_name='interventions')
    op.drop_index(op.f('ix_interventions_status'), table_name='interventions')
    op.drop_index(op.f('ix_interventions_urgency'), table_name='interventions')
    op.drop_index(op.f('ix_interventions_target_owner'), table_name='interventions')
    op.drop_index(op.f('ix_interventions_intervention_type'), table_name='interventions')
    op.drop_index(op.f('ix_interventions_obligation_id'), table_name='interventions')
    op.drop_index(op.f('ix_interventions_id'), table_name='interventions')
    op.drop_table('interventions')
