"""Add durable event inbox table for Phase 19

Revision ID: 017_add_event_inbox
Revises: 016_add_durable_job_queue
Create Date: 2026-09-01 01:00:00.000000

Creates:
  - event_inbox: durable buffer for incoming provider events with deterministic
    composite unique constraints for exactly-once processing, partition stream keys,
    lease mechanisms, and DLQ lifecycle.
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers
revision: str = '017_add_event_inbox'
down_revision: Union[str, None] = '016_add_durable_job_queue'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'event_inbox',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('workspace_id', sa.String(36), sa.ForeignKey('workspaces.id', ondelete='CASCADE'), nullable=False),
        sa.Column('provider', sa.String(64), nullable=False),
        sa.Column('source_ref', sa.String(255), nullable=True),
        sa.Column('event_type', sa.String(64), nullable=False, server_default='message'),
        sa.Column('payload_hash', sa.String(64), nullable=False),
        sa.Column('stream_key', sa.String(255), nullable=False, server_default='default'),
        sa.Column('payload_metadata', sa.JSON(), nullable=True),
        sa.Column('raw_payload', sa.JSON(), nullable=True),
        sa.Column(
            'status',
            sa.Enum(
                'RECEIVED', 'QUEUED', 'PROCESSING', 'PROCESSED',
                'RETRY_SCHEDULED', 'FAILED', 'DEAD_LETTER',
                name='eventinboxstatus'
            ),
            nullable=False,
            default='QUEUED',
        ),
        sa.Column('attempt_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('max_attempts', sa.Integer(), nullable=False, server_default='3'),
        sa.Column('last_error', sa.Text(), nullable=True),
        sa.Column('locked_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('locked_by', sa.String(100), nullable=True),
        sa.Column('lease_expires_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('received_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('available_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('processed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('processing_duration_ms', sa.Float(), nullable=True),
        sa.Column('correlation_id', sa.String(64), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    )

    # Unique constraint for deterministic idempotency
    op.create_unique_constraint(
        'uq_event_inbox_idempotency',
        'event_inbox',
        ['workspace_id', 'provider', 'source_ref', 'payload_hash'],
    )

    # Indices for efficient polling, stream ordering, and tenant isolation
    op.create_index('ix_event_inbox_status_available', 'event_inbox', ['status', 'available_at'])
    op.create_index('ix_event_inbox_stream_status', 'event_inbox', ['stream_key', 'status'])
    op.create_index('ix_event_inbox_ws_status', 'event_inbox', ['workspace_id', 'status'])
    op.create_index('ix_event_inbox_provider_rcvd', 'event_inbox', ['provider', 'received_at'])
    op.create_index('ix_event_inbox_correlation_id', 'event_inbox', ['correlation_id'])


def downgrade() -> None:
    op.drop_index('ix_event_inbox_correlation_id', table_name='event_inbox')
    op.drop_index('ix_event_inbox_provider_rcvd', table_name='event_inbox')
    op.drop_index('ix_event_inbox_ws_status', table_name='event_inbox')
    op.drop_index('ix_event_inbox_stream_status', table_name='event_inbox')
    op.drop_index('ix_event_inbox_status_available', table_name='event_inbox')
    op.drop_constraint('uq_event_inbox_idempotency', 'event_inbox', type_='unique')
    op.drop_table('event_inbox')

    try:
        op.execute("DROP TYPE IF EXISTS eventinboxstatus")
    except Exception:
        pass
