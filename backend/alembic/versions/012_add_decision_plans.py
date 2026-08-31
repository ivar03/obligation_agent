"""Add decision plans table and indexes for Phase 15

Revision ID: 012_add_decision_plans
Revises: 011_add_audit_events
Create Date: 2026-08-31 12:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '012_add_decision_plans'
down_revision: Union[str, None] = '011_add_audit_events'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create decision_plans table
    op.create_table(
        'decision_plans',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('workspace_id', sa.String(length=36), nullable=False, server_default='ws-default'),
        sa.Column('target_obligation_id', sa.String(length=36), nullable=False),
        sa.Column('generated_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('plan_version', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('status', sa.String(length=50), nullable=False, server_default='GENERATED'),
        sa.Column('overall_urgency', sa.String(length=32), nullable=False, server_default='MEDIUM'),
        sa.Column('overall_risk', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('decision_confidence', sa.Float(), nullable=False, server_default='1.0'),
        sa.Column('primary_objective', sa.Text(), nullable=False),
        sa.Column('root_cause_obligation_id', sa.String(length=36), nullable=True),
        sa.Column('critical_path', sa.JSON(), nullable=False),
        sa.Column('impact_summary', sa.JSON(), nullable=False),
        sa.Column('key_risks', sa.JSON(), nullable=False),
        sa.Column('supporting_evidence', sa.JSON(), nullable=False),
        sa.Column('recommended_actions', sa.JSON(), nullable=False),
        sa.Column('alternative_actions', sa.JSON(), nullable=False),
        sa.Column('human_decisions_required', sa.JSON(), nullable=False),
        sa.Column('assumptions', sa.JSON(), nullable=False),
        sa.Column('uncertainties', sa.JSON(), nullable=False),
        sa.Column('simulation_summary', sa.JSON(), nullable=False),
        sa.Column('created_from_snapshot_ids', sa.JSON(), nullable=False),
        sa.Column('created_from_event_ids', sa.JSON(), nullable=False),
        sa.Column('approved_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('approved_by_user_id', sa.String(length=36), nullable=True),
        sa.Column('rejected_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('rejected_by_user_id', sa.String(length=36), nullable=True),
        sa.Column('superseded_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('superseded_by_plan_id', sa.String(length=36), nullable=True),
        sa.Column('resolution_notes', sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(['workspace_id'], ['workspaces.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['target_obligation_id'], ['obligations.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['root_cause_obligation_id'], ['obligations.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['approved_by_user_id'], ['users.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['rejected_by_user_id'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_decision_plans_id'), 'decision_plans', ['id'], unique=False)
    op.create_index(op.f('ix_decision_plans_workspace_id'), 'decision_plans', ['workspace_id'], unique=False)
    op.create_index(op.f('ix_decision_plans_target_obligation_id'), 'decision_plans', ['target_obligation_id'], unique=False)
    op.create_index(op.f('ix_decision_plans_generated_at'), 'decision_plans', ['generated_at'], unique=False)
    op.create_index(op.f('ix_decision_plans_plan_version'), 'decision_plans', ['plan_version'], unique=False)
    op.create_index(op.f('ix_decision_plans_status'), 'decision_plans', ['status'], unique=False)
    op.create_index(op.f('ix_decision_plans_root_cause_obligation_id'), 'decision_plans', ['root_cause_obligation_id'], unique=False)
    op.create_index('ix_decision_plans_ws_target', 'decision_plans', ['workspace_id', 'target_obligation_id'], unique=False)
    op.create_index('ix_decision_plans_status_gen', 'decision_plans', ['status', 'generated_at'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_decision_plans_status_gen', table_name='decision_plans')
    op.drop_index('ix_decision_plans_ws_target', table_name='decision_plans')
    op.drop_index(op.f('ix_decision_plans_root_cause_obligation_id'), table_name='decision_plans')
    op.drop_index(op.f('ix_decision_plans_status'), table_name='decision_plans')
    op.drop_index(op.f('ix_decision_plans_plan_version'), table_name='decision_plans')
    op.drop_index(op.f('ix_decision_plans_generated_at'), table_name='decision_plans')
    op.drop_index(op.f('ix_decision_plans_target_obligation_id'), table_name='decision_plans')
    op.drop_index(op.f('ix_decision_plans_workspace_id'), table_name='decision_plans')
    op.drop_index(op.f('ix_decision_plans_id'), table_name='decision_plans')
    op.drop_table('decision_plans')
