"""Add enterprise audit events table and indexes

Revision ID: 011_add_audit_events
Revises: 010_add_identity_and_workspaces
Create Date: 2026-08-31 06:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '011_add_audit_events'
down_revision: Union[str, None] = '010_add_identity_and_workspaces'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create audit_events table
    op.create_table(
        'audit_events',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('workspace_id', sa.String(length=36), nullable=False),
        sa.Column('actor_user_id', sa.String(length=36), nullable=True),
        sa.Column('actor_role', sa.String(length=50), nullable=True),
        sa.Column('action', sa.String(length=100), nullable=False),
        sa.Column('entity_type', sa.String(length=50), nullable=True),
        sa.Column('entity_id', sa.String(length=100), nullable=True),
        sa.Column('timestamp', sa.DateTime(timezone=True), nullable=False),
        sa.Column('request_id', sa.String(length=64), nullable=True),
        sa.Column('source', sa.String(length=50), nullable=False, server_default='API'),
        sa.Column('ip_address', sa.String(length=100), nullable=True),
        sa.Column('user_agent', sa.String(length=500), nullable=True),
        sa.Column('before_state', sa.JSON(), nullable=True),
        sa.Column('after_state', sa.JSON(), nullable=True),
        sa.Column('audit_metadata', sa.JSON(), nullable=True),
        sa.Column('reason', sa.Text(), nullable=True),
        sa.Column('severity', sa.String(length=20), nullable=False, server_default='INFO'),
        sa.Column('result', sa.String(length=20), nullable=False, server_default='SUCCESS'),
        sa.Column('previous_event_hash', sa.String(length=64), nullable=True),
        sa.Column('event_hash', sa.String(length=64), nullable=False),
        sa.ForeignKeyConstraint(['actor_user_id'], ['users.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['workspace_id'], ['workspaces.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_audit_events_id'), 'audit_events', ['id'], unique=False)
    op.create_index(op.f('ix_audit_events_workspace_id'), 'audit_events', ['workspace_id'], unique=False)
    op.create_index(op.f('ix_audit_events_actor_user_id'), 'audit_events', ['actor_user_id'], unique=False)
    op.create_index(op.f('ix_audit_events_action'), 'audit_events', ['action'], unique=False)
    op.create_index(op.f('ix_audit_events_entity_type'), 'audit_events', ['entity_type'], unique=False)
    op.create_index(op.f('ix_audit_events_entity_id'), 'audit_events', ['entity_id'], unique=False)
    op.create_index(op.f('ix_audit_events_timestamp'), 'audit_events', ['timestamp'], unique=False)
    op.create_index(op.f('ix_audit_events_request_id'), 'audit_events', ['request_id'], unique=False)
    op.create_index(op.f('ix_audit_events_event_hash'), 'audit_events', ['event_hash'], unique=False)
    op.create_index('ix_audit_events_ws_timestamp', 'audit_events', ['workspace_id', 'timestamp'], unique=False)
    op.create_index('ix_audit_events_ws_action', 'audit_events', ['workspace_id', 'action'], unique=False)
    op.create_index('ix_audit_events_ws_entity', 'audit_events', ['workspace_id', 'entity_type', 'entity_id'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_audit_events_ws_entity', table_name='audit_events')
    op.drop_index('ix_audit_events_ws_action', table_name='audit_events')
    op.drop_index('ix_audit_events_ws_timestamp', table_name='audit_events')
    op.drop_index(op.f('ix_audit_events_event_hash'), table_name='audit_events')
    op.drop_index(op.f('ix_audit_events_request_id'), table_name='audit_events')
    op.drop_index(op.f('ix_audit_events_timestamp'), table_name='audit_events')
    op.drop_index(op.f('ix_audit_events_entity_id'), table_name='audit_events')
    op.drop_index(op.f('ix_audit_events_entity_type'), table_name='audit_events')
    op.drop_index(op.f('ix_audit_events_action'), table_name='audit_events')
    op.drop_index(op.f('ix_audit_events_actor_user_id'), table_name='audit_events')
    op.drop_index(op.f('ix_audit_events_workspace_id'), table_name='audit_events')
    op.drop_index(op.f('ix_audit_events_id'), table_name='audit_events')
    op.drop_table('audit_events')
