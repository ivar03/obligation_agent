"""Initial schema for obligations and obligation edges

Revision ID: 001_initial_schema
Revises: 
Create Date: 2026-08-30 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '001_initial_schema'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'obligations',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('owner', sa.String(length=255), nullable=False),
        sa.Column('beneficiary', sa.String(length=255), nullable=False),
        sa.Column('action', sa.Text(), nullable=False),
        sa.Column('deadline', sa.DateTime(timezone=True), nullable=True),
        sa.Column('conditions', sa.JSON(), nullable=True),
        sa.Column('evidence', sa.JSON(), nullable=True),
        sa.Column('status', sa.Enum('DETECTED', 'CONFIRMED', 'IN_PROGRESS', 'COMPLETED', 'OVERDUE', 'CANCELLED', 'BLOCKED', name='obligation_status_enum', native_enum=False), nullable=False),
        sa.Column('next_action', sa.Text(), nullable=True),
        sa.Column('source_ref', sa.String(length=512), nullable=True),
        sa.Column('obligation_type', sa.Enum('OWED_BY_ME', 'OWED_TO_ME', name='obligation_type_enum', native_enum=False), nullable=False),
        sa.Column('confidence', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_obligations_id'), 'obligations', ['id'], unique=False)
    op.create_index(op.f('ix_obligations_owner'), 'obligations', ['owner'], unique=False)
    op.create_index(op.f('ix_obligations_beneficiary'), 'obligations', ['beneficiary'], unique=False)
    op.create_index(op.f('ix_obligations_deadline'), 'obligations', ['deadline'], unique=False)
    op.create_index(op.f('ix_obligations_status'), 'obligations', ['status'], unique=False)
    op.create_index(op.f('ix_obligations_obligation_type'), 'obligations', ['obligation_type'], unique=False)

    op.create_table(
        'obligation_edges',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('from_obligation_id', sa.String(length=36), nullable=False),
        sa.Column('to_obligation_id', sa.String(length=36), nullable=False),
        sa.Column('edge_type', sa.Enum('DEPENDS_ON', 'LINKED', name='edge_type_enum', native_enum=False), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['from_obligation_id'], ['obligations.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['to_obligation_id'], ['obligations.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_obligation_edges_id'), 'obligation_edges', ['id'], unique=False)
    op.create_index(op.f('ix_obligation_edges_from_obligation_id'), 'obligation_edges', ['from_obligation_id'], unique=False)
    op.create_index(op.f('ix_obligation_edges_to_obligation_id'), 'obligation_edges', ['to_obligation_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_obligation_edges_to_obligation_id'), table_name='obligation_edges')
    op.drop_index(op.f('ix_obligation_edges_from_obligation_id'), table_name='obligation_edges')
    op.drop_index(op.f('ix_obligation_edges_id'), table_name='obligation_edges')
    op.drop_table('obligation_edges')
    
    op.drop_index(op.f('ix_obligations_obligation_type'), table_name='obligations')
    op.drop_index(op.f('ix_obligations_status'), table_name='obligations')
    op.drop_index(op.f('ix_obligations_deadline'), table_name='obligations')
    op.drop_index(op.f('ix_obligations_beneficiary'), table_name='obligations')
    op.drop_index(op.f('ix_obligations_owner'), table_name='obligations')
    op.drop_index(op.f('ix_obligations_id'), table_name='obligations')
    op.drop_table('obligations')
