"""Add operational observability and alerts tables for Phase 21

Revision ID: 019_add_operational_observability
Revises: 018_add_llm_analysis_records
Create Date: 2026-09-01 03:00:00.000000

Creates:
  - operational_audit_records: append-only operational audit log with SHA-256 hash chaining
  - operational_alerts: deterministic operational alerts lifecycle table
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers
revision: str = '019_add_operational_observability'
down_revision: Union[str, None] = '018_add_llm_analysis_records'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. operational_audit_records table
    op.create_table(
        'operational_audit_records',
        sa.Column('id', sa.String(64), primary_key=True),
        sa.Column('workspace_id', sa.String(36), sa.ForeignKey('workspaces.id', ondelete='CASCADE'), nullable=False),
        sa.Column('timestamp', sa.DateTime(timezone=True), nullable=False),
        sa.Column('event_type', sa.String(64), nullable=False),
        sa.Column('severity', sa.String(32), nullable=False, server_default='INFO'),
        sa.Column('actor_type', sa.String(32), nullable=False, server_default='SYSTEM'),
        sa.Column('actor_id', sa.String(128), nullable=True),
        sa.Column('request_id', sa.String(64), nullable=True),
        sa.Column('trace_id', sa.String(64), nullable=True),
        sa.Column('span_id', sa.String(32), nullable=True),
        sa.Column('resource_type', sa.String(64), nullable=True),
        sa.Column('resource_id', sa.String(128), nullable=True),
        sa.Column('provider', sa.String(64), nullable=True),
        sa.Column('action', sa.String(128), nullable=False),
        sa.Column('result', sa.String(32), nullable=False, server_default='SUCCESS'),
        sa.Column('error_code', sa.String(64), nullable=True),
        sa.Column('metadata_json', sa.JSON(), nullable=True),
        sa.Column('previous_hash', sa.String(64), nullable=True),
        sa.Column('record_hash', sa.String(64), nullable=False),
    )

    op.create_index('ix_op_audit_ws_time', 'operational_audit_records', ['workspace_id', 'timestamp'])
    op.create_index('ix_op_audit_ws_event', 'operational_audit_records', ['workspace_id', 'event_type'])
    op.create_index('ix_op_audit_ws_trace', 'operational_audit_records', ['workspace_id', 'trace_id'])
    op.create_index('ix_op_audit_ws_req', 'operational_audit_records', ['workspace_id', 'request_id'])
    op.create_index('ix_op_audit_ws_resource', 'operational_audit_records', ['workspace_id', 'resource_type', 'resource_id'])
    op.create_index('ix_op_audit_record_hash', 'operational_audit_records', ['record_hash'])

    # 2. operational_alerts table
    op.create_table(
        'operational_alerts',
        sa.Column('id', sa.String(64), primary_key=True),
        sa.Column('workspace_id', sa.String(36), sa.ForeignKey('workspaces.id', ondelete='CASCADE'), nullable=False),
        sa.Column('alert_name', sa.String(128), nullable=False),
        sa.Column('alert_type', sa.String(64), nullable=False),
        sa.Column('severity', sa.String(32), nullable=False, server_default='WARNING'),
        sa.Column('status', sa.String(32), nullable=False, server_default='OPEN'),
        sa.Column('summary', sa.Text(), nullable=False),
        sa.Column('details', sa.JSON(), nullable=True),
        sa.Column('fingerprint', sa.String(128), nullable=False),
        sa.Column('trace_id', sa.String(64), nullable=True),
        sa.Column('acknowledged_by', sa.String(128), nullable=True),
        sa.Column('acknowledged_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('resolved_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    )

    op.create_index('ix_op_alerts_ws_status', 'operational_alerts', ['workspace_id', 'status'])
    op.create_index('ix_op_alerts_ws_fingerprint', 'operational_alerts', ['workspace_id', 'fingerprint'])


def downgrade() -> None:
    op.drop_index('ix_op_alerts_ws_fingerprint', table_name='operational_alerts')
    op.drop_index('ix_op_alerts_ws_status', table_name='operational_alerts')
    op.drop_table('operational_alerts')

    op.drop_index('ix_op_audit_record_hash', table_name='operational_audit_records')
    op.drop_index('ix_op_audit_ws_resource', table_name='operational_audit_records')
    op.drop_index('ix_op_audit_ws_req', table_name='operational_audit_records')
    op.drop_index('ix_op_audit_ws_trace', table_name='operational_audit_records')
    op.drop_index('ix_op_audit_ws_event', table_name='operational_audit_records')
    op.drop_index('ix_op_audit_ws_time', table_name='operational_audit_records')
    op.drop_table('operational_audit_records')
