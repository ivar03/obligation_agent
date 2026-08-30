"""Add identity, workspaces, and multi-tenant authorization tables

Revision ID: 010_add_identity_and_workspaces
Revises: 009_add_prediction_feedback
Create Date: 2026-08-31 04:00:00.000000

"""
from typing import Sequence, Union
from datetime import datetime, timezone
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '010_add_identity_and_workspaces'
down_revision: Union[str, None] = '009_add_prediction_feedback'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Create users table
    op.create_table(
        'users',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('email', sa.String(length=255), nullable=False),
        sa.Column('password_hash', sa.String(length=255), nullable=False),
        sa.Column('display_name', sa.String(length=255), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.text('1')),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_users_id'), 'users', ['id'], unique=False)
    op.create_index(op.f('ix_users_email'), 'users', ['email'], unique=True)

    # 2. Create workspaces table
    op.create_table(
        'workspaces',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('slug', sa.String(length=255), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_workspaces_id'), 'workspaces', ['id'], unique=False)
    op.create_index(op.f('ix_workspaces_slug'), 'workspaces', ['slug'], unique=True)

    # 3. Create workspace_memberships table
    op.create_table(
        'workspace_memberships',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('workspace_id', sa.String(length=36), nullable=False),
        sa.Column('user_id', sa.String(length=36), nullable=False),
        sa.Column('role', sa.String(length=32), nullable=False, server_default='MEMBER'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['workspace_id'], ['workspaces.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('workspace_id', 'user_id', name='uq_workspace_user_membership')
    )
    op.create_index(op.f('ix_workspace_memberships_id'), 'workspace_memberships', ['id'], unique=False)
    op.create_index(op.f('ix_workspace_memberships_workspace_id'), 'workspace_memberships', ['workspace_id'], unique=False)
    op.create_index(op.f('ix_workspace_memberships_user_id'), 'workspace_memberships', ['user_id'], unique=False)
    op.create_index(op.f('ix_workspace_memberships_role'), 'workspace_memberships', ['role'], unique=False)

    # 4. Insert Default Workspace & User for Seamless Migration
    now_iso = datetime.now(timezone.utc).isoformat()
    # Default password hash for 'demo1234'
    default_hash = "pbkdf2_sha256$100000$666978656473616c7431323334$3d2899d255160914a84f3c051a80d738fca1660f64beae465da3bbd8c83a542b"
    op.execute(
        f"INSERT INTO users (id, email, password_hash, display_name, is_active, created_at, updated_at) "
        f"VALUES ('usr-default', 'demo@obligation.local', '{default_hash}', 'Demo User', 1, '{now_iso}', '{now_iso}')"
    )
    op.execute(
        f"INSERT INTO workspaces (id, name, slug, created_at, updated_at) "
        f"VALUES ('ws-default', 'Default Workspace', 'default-workspace', '{now_iso}', '{now_iso}')"
    )
    op.execute(
        f"INSERT INTO workspace_memberships (id, workspace_id, user_id, role, created_at, updated_at) "
        f"VALUES ('mem-default', 'ws-default', 'usr-default', 'OWNER', '{now_iso}', '{now_iso}')"
    )

    # 5. Add workspace_id column to existing business entities
    scoped_tables = [
        'obligations',
        'obligation_edges',
        'obligation_evidence',
        'interventions',
        'ingested_events',
        'reconciliation_records',
        'integration_connections',
        'obligation_outcome_snapshots',
        'prediction_snapshots',
        'prediction_feedbacks',
    ]

    for tbl in scoped_tables:
        with op.batch_alter_table(tbl, schema=None) as batch_op:
            batch_op.add_column(sa.Column('workspace_id', sa.String(length=36), nullable=False, server_default='ws-default'))
            batch_op.create_foreign_key(f'fk_{tbl}_workspace_id', 'workspaces', ['workspace_id'], ['id'], ondelete='CASCADE')
            batch_op.create_index(f'ix_{tbl}_workspace_id', ['workspace_id'], unique=False)

    # 6. Add actor_user_id to human action tables
    actor_tables = [
        'obligation_evidence',
        'interventions',
        'reconciliation_records',
    ]
    for tbl in actor_tables:
        with op.batch_alter_table(tbl, schema=None) as batch_op:
            batch_op.add_column(sa.Column('actor_user_id', sa.String(length=36), nullable=True))
            batch_op.create_foreign_key(f'fk_{tbl}_actor_user_id', 'users', ['actor_user_id'], ['id'], ondelete='SET NULL')
            batch_op.create_index(f'ix_{tbl}_actor_user_id', ['actor_user_id'], unique=False)


def downgrade() -> None:
    scoped_tables = [
        'obligations',
        'obligation_edges',
        'obligation_evidence',
        'interventions',
        'ingested_events',
        'reconciliation_records',
        'integration_connections',
        'obligation_outcome_snapshots',
        'prediction_snapshots',
        'prediction_feedbacks',
    ]
    for tbl in scoped_tables:
        with op.batch_alter_table(tbl, schema=None) as batch_op:
            batch_op.drop_index(f'ix_{tbl}_workspace_id')
            batch_op.drop_constraint(f'fk_{tbl}_workspace_id', type_='foreignkey')
            batch_op.drop_column('workspace_id')

    actor_tables = [
        'obligation_evidence',
        'interventions',
        'reconciliation_records',
    ]
    for tbl in actor_tables:
        with op.batch_alter_table(tbl, schema=None) as batch_op:
            batch_op.drop_index(f'ix_{tbl}_actor_user_id')
            batch_op.drop_constraint(f'fk_{tbl}_actor_user_id', type_='foreignkey')
            batch_op.drop_column('actor_user_id')

    op.drop_table('workspace_memberships')
    op.drop_table('workspaces')
    op.drop_table('users')
