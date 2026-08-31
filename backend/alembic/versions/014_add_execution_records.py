"""Add execution records table and indexes for Phase 16

Revision ID: 014_add_execution_records
Revises: 013_add_organizational_memories
Create Date: 2026-08-31 15:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '014_add_execution_records'
down_revision: Union[str, None] = '013_add_organizational_memories'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'execution_records',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('workspace_id', sa.String(length=36), nullable=False, server_default='ws-default'),
        sa.Column('decision_plan_id', sa.String(length=36), nullable=False),
        sa.Column('intervention_id', sa.String(length=36), nullable=True),
        sa.Column('obligation_id', sa.String(length=36), nullable=False),
        sa.Column('execution_type', sa.String(length=64), nullable=False, server_default='INTERVENTION_MESSAGE'),
        sa.Column('provider', sa.String(length=64), nullable=False, server_default='mock'),
        sa.Column('provider_version', sa.String(length=32), nullable=False, server_default='1.0.0'),
        sa.Column('status', sa.String(length=64), nullable=False, server_default='PENDING_AUTHORIZATION'),
        sa.Column('authorized_by', sa.String(length=128), nullable=True),
        sa.Column('authorized_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('executed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('provider_execution_ref', sa.String(length=128), nullable=True),
        sa.Column('idempotency_key', sa.String(length=128), nullable=False),
        sa.Column('request_payload_hash', sa.String(length=64), nullable=False),
        sa.Column('safe_request_metadata', sa.JSON(), nullable=False),
        sa.Column('delivery_status', sa.String(length=64), nullable=True),
        sa.Column('failure_code', sa.String(length=64), nullable=True),
        sa.Column('failure_reason', sa.Text(), nullable=True),
        sa.Column('retry_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('max_retries', sa.Integer(), nullable=False, server_default='3'),
        sa.Column('next_retry_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('response_received_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('response_event_id', sa.String(length=36), nullable=True),
        sa.Column('outcome', sa.String(length=64), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['workspace_id'], ['workspaces.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['decision_plan_id'], ['decision_plans.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['intervention_id'], ['interventions.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['obligation_id'], ['obligations.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['response_event_id'], ['ingested_events.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id')
    )

    op.create_index('ix_execution_records_ws_status', 'execution_records', ['workspace_id', 'status'], unique=False)
    op.create_index('ix_execution_records_ws_idempotency', 'execution_records', ['workspace_id', 'idempotency_key'], unique=False)
    op.create_index('ix_execution_records_plan_id', 'execution_records', ['decision_plan_id'], unique=False)
    op.create_index('ix_execution_records_obligation_id', 'execution_records', ['obligation_id'], unique=False)
    op.create_index('ix_execution_records_executed_at', 'execution_records', ['executed_at'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_execution_records_executed_at', table_name='execution_records')
    op.drop_index('ix_execution_records_obligation_id', table_name='execution_records')
    op.drop_index('ix_execution_records_plan_id', table_name='execution_records')
    op.drop_index('ix_execution_records_ws_idempotency', table_name='execution_records')
    op.drop_index('ix_execution_records_ws_status', table_name='execution_records')
    op.drop_table('execution_records')
