"""Add durable job queue table for Phase 19

Revision ID: 016_add_durable_job_queue
Revises: 015_add_monitoring_layer
Create Date: 2026-09-01 00:00:00.000000

Creates:
  - background_jobs: durable job queue with idempotency key, lease mechanism,
    attempt tracking, and status lifecycle for crash-safe background processing.
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers
revision: str = '016_add_durable_job_queue'
down_revision: Union[str, None] = '015_add_monitoring_layer'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'background_jobs',
        sa.Column('id', sa.String(), primary_key=True),
        sa.Column('job_type', sa.String(100), nullable=False),
        sa.Column('workspace_id', sa.String(), nullable=False),
        sa.Column('payload', sa.Text(), nullable=True),
        sa.Column(
            'status',
            sa.Enum(
                'QUEUED', 'CLAIMED', 'PROCESSING',
                'COMPLETED', 'FAILED', 'DEAD_LETTER',
                name='jobstatus'
            ),
            nullable=False,
            default='QUEUED',
        ),
        sa.Column('attempt_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('max_attempts', sa.Integer(), nullable=False, server_default='3'),
        sa.Column('idempotency_key', sa.String(255), nullable=True),
        sa.Column('scheduled_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('claimed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('lease_expires_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('claimed_by', sa.String(100), nullable=True),
        sa.Column('error', sa.Text(), nullable=True),
    )

    # Unique constraint on idempotency_key (when present) for exactly-once semantics
    op.create_unique_constraint(
        'uq_background_jobs_idempotency_key',
        'background_jobs',
        ['idempotency_key'],
    )

    # Composite index for efficient QUEUED job polling (status + scheduled_at)
    op.create_index(
        'ix_background_jobs_status_scheduled',
        'background_jobs',
        ['status', 'scheduled_at'],
    )

    op.create_index(
        'ix_background_jobs_workspace',
        'background_jobs',
        ['workspace_id'],
    )

    op.create_index(
        'ix_background_jobs_type',
        'background_jobs',
        ['job_type'],
    )


def downgrade() -> None:
    op.drop_index('ix_background_jobs_type', table_name='background_jobs')
    op.drop_index('ix_background_jobs_workspace', table_name='background_jobs')
    op.drop_index('ix_background_jobs_status_scheduled', table_name='background_jobs')
    op.drop_constraint('uq_background_jobs_idempotency_key', 'background_jobs', type_='unique')
    op.drop_table('background_jobs')

    # Drop the enum type for PostgreSQL (SQLite ignores this)
    try:
        op.execute("DROP TYPE IF EXISTS jobstatus")
    except Exception:
        pass
