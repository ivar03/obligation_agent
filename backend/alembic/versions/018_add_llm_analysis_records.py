"""Add LLM analysis records table for Phase 20

Revision ID: 018_add_llm_analysis_records
Revises: 017_add_event_inbox
Create Date: 2026-09-01 02:00:00.000000

Creates:
  - llm_analysis_records: persistent audit trail of natural language proposals,
    validation evaluations, grounding checks, and prompt versions.
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers
revision: str = '018_add_llm_analysis_records'
down_revision: Union[str, None] = '017_add_event_inbox'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'llm_analysis_records',
        sa.Column('id', sa.String(64), primary_key=True),
        sa.Column('workspace_id', sa.String(36), sa.ForeignKey('workspaces.id', ondelete='CASCADE'), nullable=False),
        sa.Column('source_ref', sa.String(255), nullable=True),
        sa.Column('analysis_type', sa.String(64), nullable=False),
        sa.Column('provider', sa.String(64), nullable=False, server_default='mock'),
        sa.Column('model', sa.String(128), nullable=False, server_default='mock-intelligence-v1'),
        sa.Column('prompt_version', sa.String(32), nullable=False, server_default='v1'),
        sa.Column('schema_version', sa.String(64), nullable=False, server_default='obligation-proposal-v1'),
        sa.Column('input_hash', sa.String(64), nullable=False),
        sa.Column('raw_prompt_redacted', sa.Text(), nullable=True),
        sa.Column('structured_output', sa.JSON(), nullable=True),
        sa.Column('confidence', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('validation_status', sa.String(64), nullable=False, server_default='VALID'),
        sa.Column('validation_errors', sa.JSON(), nullable=True),
        sa.Column('grounding_status', sa.String(64), nullable=False, server_default='GROUNDED'),
        sa.Column('grounding_errors', sa.JSON(), nullable=True),
        sa.Column('fallback_used', sa.Boolean(), nullable=False, server_default='0'),
        sa.Column('human_review_required', sa.Boolean(), nullable=False, server_default='0'),
        sa.Column('human_review_status', sa.String(32), nullable=True),
        sa.Column('reviewer_notes', sa.Text(), nullable=True),
        sa.Column('latency_ms', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('tokens_in', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('tokens_out', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('cost_estimate_usd', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    )

    op.create_index('ix_llm_analysis_ws_type_created', 'llm_analysis_records', ['workspace_id', 'analysis_type', 'created_at'])
    op.create_index('ix_llm_analysis_input_hash', 'llm_analysis_records', ['workspace_id', 'input_hash'])
    op.create_index('ix_llm_analysis_validation_status', 'llm_analysis_records', ['validation_status'])
    op.create_index('ix_llm_analysis_grounding_status', 'llm_analysis_records', ['grounding_status'])
    op.create_index('ix_llm_analysis_human_review', 'llm_analysis_records', ['human_review_required'])


def downgrade() -> None:
    op.drop_index('ix_llm_analysis_human_review', table_name='llm_analysis_records')
    op.drop_index('ix_llm_analysis_grounding_status', table_name='llm_analysis_records')
    op.drop_index('ix_llm_analysis_validation_status', table_name='llm_analysis_records')
    op.drop_index('ix_llm_analysis_input_hash', table_name='llm_analysis_records')
    op.drop_index('ix_llm_analysis_ws_type_created', table_name='llm_analysis_records')
    op.drop_table('llm_analysis_records')
