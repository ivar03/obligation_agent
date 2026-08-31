"""Add monitoring layer tables and indexes for Phase 17

Revision ID: 015_add_monitoring_layer
Revises: 014_add_execution_records
Create Date: 2026-08-31 18:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '015_add_monitoring_layer'
down_revision: Union[str, None] = '014_add_execution_records'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. monitoring_watches
    op.create_table(
        'monitoring_watches',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('workspace_id', sa.String(length=36), nullable=False, server_default='ws-default'),
        sa.Column('watch_type', sa.String(length=64), nullable=False, server_default='DEADLINE'),
        sa.Column('target_type', sa.String(length=64), nullable=False, server_default='OBLIGATION'),
        sa.Column('target_id', sa.String(length=128), nullable=False),
        sa.Column('status', sa.String(length=64), nullable=False, server_default='ACTIVE'),
        sa.Column('configuration', sa.JSON(), nullable=False),
        sa.Column('last_evaluated_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('next_evaluation_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('last_observed_state', sa.JSON(), nullable=False),
        sa.Column('last_triggered_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('trigger_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('cooldown_until', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_by', sa.String(length=128), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['workspace_id'], ['workspaces.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_monitoring_watches_ws_status', 'monitoring_watches', ['workspace_id', 'status'], unique=False)
    op.create_index('ix_monitoring_watches_ws_target', 'monitoring_watches', ['workspace_id', 'target_type', 'target_id'], unique=False)
    op.create_index('ix_monitoring_watches_next_eval', 'monitoring_watches', ['workspace_id', 'status', 'next_evaluation_at'], unique=False)

    # 2. monitoring_events
    op.create_table(
        'monitoring_events',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('workspace_id', sa.String(length=36), nullable=False, server_default='ws-default'),
        sa.Column('watch_id', sa.String(length=36), nullable=True),
        sa.Column('event_type', sa.String(length=64), nullable=False),
        sa.Column('severity', sa.String(length=32), nullable=False, server_default='INFO'),
        sa.Column('target_type', sa.String(length=64), nullable=False, server_default='OBLIGATION'),
        sa.Column('target_id', sa.String(length=128), nullable=False),
        sa.Column('previous_state', sa.JSON(), nullable=False),
        sa.Column('current_state', sa.JSON(), nullable=False),
        sa.Column('detected_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('explanation', sa.Text(), nullable=False),
        sa.Column('signals', sa.JSON(), nullable=False),
        sa.Column('provenance', sa.JSON(), nullable=False),
        sa.Column('deduplication_key', sa.String(length=128), nullable=False),
        sa.Column('acknowledged_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('acknowledged_by', sa.String(length=128), nullable=True),
        sa.Column('resolved_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('resolution_reason', sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(['workspace_id'], ['workspaces.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['watch_id'], ['monitoring_watches.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_monitoring_events_ws_severity', 'monitoring_events', ['workspace_id', 'severity'], unique=False)
    op.create_index('ix_monitoring_events_ws_target', 'monitoring_events', ['workspace_id', 'target_type', 'target_id'], unique=False)
    op.create_index('ix_monitoring_events_ws_dedup', 'monitoring_events', ['workspace_id', 'deduplication_key'], unique=False)
    op.create_index('ix_monitoring_events_detected_at', 'monitoring_events', ['workspace_id', 'detected_at'], unique=False)

    # 3. escalation_candidates
    op.create_table(
        'escalation_candidates',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('workspace_id', sa.String(length=36), nullable=False, server_default='ws-default'),
        sa.Column('monitoring_event_id', sa.String(length=36), nullable=True),
        sa.Column('target_type', sa.String(length=64), nullable=False, server_default='OBLIGATION'),
        sa.Column('target_id', sa.String(length=128), nullable=False),
        sa.Column('severity', sa.String(length=32), nullable=False, server_default='WARNING'),
        sa.Column('reason', sa.Text(), nullable=False),
        sa.Column('recommended_next_step', sa.Text(), nullable=False),
        sa.Column('affected_obligations', sa.JSON(), nullable=False),
        sa.Column('affected_owners', sa.JSON(), nullable=False),
        sa.Column('blast_radius', sa.JSON(), nullable=False),
        sa.Column('decision_plan_id', sa.String(length=36), nullable=True),
        sa.Column('status', sa.String(length=32), nullable=False, server_default='OPEN'),
        sa.Column('deduplication_key', sa.String(length=128), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('acknowledged_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('acknowledged_by', sa.String(length=128), nullable=True),
        sa.Column('resolved_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['workspace_id'], ['workspaces.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['monitoring_event_id'], ['monitoring_events.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_escalation_candidates_ws_status', 'escalation_candidates', ['workspace_id', 'status'], unique=False)
    op.create_index('ix_escalation_candidates_ws_severity', 'escalation_candidates', ['workspace_id', 'severity'], unique=False)
    op.create_index('ix_escalation_candidates_ws_target', 'escalation_candidates', ['workspace_id', 'target_type', 'target_id'], unique=False)
    op.create_index('ix_escalation_candidates_ws_dedup', 'escalation_candidates', ['workspace_id', 'deduplication_key'], unique=False)

    # 4. monitoring_runs
    op.create_table(
        'monitoring_runs',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('workspace_id', sa.String(length=36), nullable=False, server_default='ws-default'),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('watches_evaluated', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('events_created', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('escalations_created', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('errors', sa.JSON(), nullable=False),
        sa.Column('status', sa.String(length=32), nullable=False, server_default='RUNNING'),
        sa.ForeignKeyConstraint(['workspace_id'], ['workspaces.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_monitoring_runs_ws_status', 'monitoring_runs', ['workspace_id', 'status'], unique=False)
    op.create_index('ix_monitoring_runs_ws_started', 'monitoring_runs', ['workspace_id', 'started_at'], unique=False)


def downgrade() -> None:
    op.drop_table('monitoring_runs')
    op.drop_table('escalation_candidates')
    op.drop_table('monitoring_events')
    op.drop_table('monitoring_watches')
