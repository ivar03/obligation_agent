"""Add integration_connections table

Revision ID: 006_add_integrations
Revises: 005_add_event_ingestion
Create Date: 2026-08-31 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '006_add_integrations'
down_revision: Union[str, None] = '005_add_event_ingestion'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'integration_connections',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('provider', sa.String(length=64), nullable=False),
        sa.Column('external_account_id', sa.String(length=255), nullable=True),
        sa.Column('external_account_name', sa.String(length=255), nullable=True),
        sa.Column('status', sa.String(length=32), nullable=False, server_default='CONNECTED'),
        sa.Column('encrypted_credentials', sa.Text(), nullable=True),
        sa.Column('scopes', sa.JSON(), nullable=True),
        sa.Column('connection_metadata', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('provider', 'external_account_id', name='uq_provider_account')
    )
    op.create_index(op.f('ix_integration_connections_id'), 'integration_connections', ['id'], unique=False)
    op.create_index(op.f('ix_integration_connections_provider'), 'integration_connections', ['provider'], unique=False)
    op.create_index(op.f('ix_integration_connections_external_account_id'), 'integration_connections', ['external_account_id'], unique=False)
    op.create_index(op.f('ix_integration_connections_status'), 'integration_connections', ['status'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_integration_connections_status'), table_name='integration_connections')
    op.drop_index(op.f('ix_integration_connections_external_account_id'), table_name='integration_connections')
    op.drop_index(op.f('ix_integration_connections_provider'), table_name='integration_connections')
    op.drop_index(op.f('ix_integration_connections_id'), table_name='integration_connections')
    op.drop_table('integration_connections')
