"""
Phase 20 Persistent LLM Analysis Record Model.

Provides an immutable, tamper-evident audit record of all natural-language
interpretations, validation outcomes, grounding checks, and prompt versions.
"""

import uuid
from datetime import datetime, timezone
from sqlalchemy import (
    Column,
    String,
    DateTime,
    Float,
    Integer,
    Boolean,
    Text,
    JSON,
    ForeignKey,
    Index,
)
from app.core.database import Base


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def generate_uuid() -> str:
    return f"llm-{uuid.uuid4().hex}"


class LLMAnalysisRecord(Base):
    """
    Immutable historical record of an LLM analysis, including input hashes,
    structured outputs, validation status, and grounding evaluation.
    """
    __tablename__ = "llm_analysis_records"

    id = Column(String(64), primary_key=True, default=generate_uuid, index=True)
    workspace_id = Column(
        String(36),
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
        default="ws-default",
        index=True,
    )
    source_ref = Column(String(255), nullable=True, index=True)
    analysis_type = Column(String(64), nullable=False, index=True)
    provider = Column(String(64), nullable=False, default="mock")
    model = Column(String(128), nullable=False, default="mock-intelligence-v1")
    prompt_version = Column(String(32), nullable=False, default="v1")
    schema_version = Column(String(64), nullable=False, default="obligation-proposal-v1")
    input_hash = Column(String(64), nullable=False, index=True)
    raw_prompt_redacted = Column(Text, nullable=True)
    structured_output = Column(JSON, nullable=True)
    confidence = Column(Float, nullable=False, default=0.0)
    validation_status = Column(String(64), nullable=False, default="VALID", index=True)
    validation_errors = Column(JSON, nullable=True)
    grounding_status = Column(String(64), nullable=False, default="GROUNDED", index=True)
    grounding_errors = Column(JSON, nullable=True)
    fallback_used = Column(Boolean, nullable=False, default=False)
    human_review_required = Column(Boolean, nullable=False, default=False, index=True)
    human_review_status = Column(String(32), nullable=True)  # "ACCEPTED", "REJECTED", "EDITED"
    reviewer_notes = Column(Text, nullable=True)
    latency_ms = Column(Float, nullable=False, default=0.0)
    tokens_in = Column(Integer, nullable=False, default=0)
    tokens_out = Column(Integer, nullable=False, default=0)
    cost_estimate_usd = Column(Float, nullable=False, default=0.0)
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False, index=True)

    __table_args__ = (
        Index("ix_llm_analysis_ws_type_created", "workspace_id", "analysis_type", "created_at"),
        Index("ix_llm_analysis_input_hash", "workspace_id", "input_hash"),
    )
