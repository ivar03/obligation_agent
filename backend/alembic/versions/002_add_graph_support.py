"""Add block_reason to obligations and unique constraint to obligation_edges

Revision ID: 002_add_graph_support
Revises: 001_initial_schema
Create Date: 2026-08-30 14:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '002_add_graph_support'
down_revision: Union[str, None] = '001_initial_schema'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Add block_reason column to obligations table
    op.add_column('obligations', sa.Column('block_reason', sa.JSON(), nullable=True))

    # 2. Add unique constraint to obligation_edges (from_obligation_id, to_obligation_id, edge_type)
    # Using batch_alter_table for SQLite compatibility
    with op.batch_alter_table('obligation_edges', schema=None) as batch_op:
        batch_op.create_unique_constraint(
            'uq_obligation_edge',
            ['from_obligation_id', 'to_obligation_id', 'edge_type']
        )


def downgrade() -> None:
    with op.batch_alter_table('obligation_edges', schema=None) as batch_op:
        batch_op.drop_constraint('uq_obligation_edge', type_='unique')

    op.drop_column('obligations', 'block_reason')
