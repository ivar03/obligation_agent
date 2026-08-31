"""
Phase 19 Background Job Model.

Represents a durable job record persisted to the database.
The idempotency_key unique constraint prevents duplicate job creation.
"""

import enum
from datetime import datetime
from sqlalchemy import (
    Column, String, Integer, Text, DateTime, Enum as SAEnum,
    Index, UniqueConstraint,
)
from app.core.database import Base


class JobStatus(str, enum.Enum):
    QUEUED = "QUEUED"
    CLAIMED = "CLAIMED"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    DEAD_LETTER = "DEAD_LETTER"


class BackgroundJobRecord(Base):
    """
    Durable database-backed background job record.

    Status lifecycle:
        QUEUED → CLAIMED → PROCESSING → COMPLETED
        PROCESSING → QUEUED (retry, via scheduled_at)
        PROCESSING → DEAD_LETTER (exhausted)
    """
    __tablename__ = "background_jobs"
    __table_args__ = (
        UniqueConstraint("idempotency_key", name="uq_background_jobs_idempotency_key"),
        Index("ix_background_jobs_status_scheduled", "status", "scheduled_at"),
        Index("ix_background_jobs_workspace", "workspace_id"),
        Index("ix_background_jobs_type", "job_type"),
    )

    id = Column(String, primary_key=True)
    job_type = Column(String(100), nullable=False)
    workspace_id = Column(String, nullable=False)
    payload = Column(Text, nullable=True)           # JSON-encoded payload
    status = Column(SAEnum(JobStatus), nullable=False, default=JobStatus.QUEUED)
    attempt_count = Column(Integer, default=0, nullable=False)
    max_attempts = Column(Integer, default=3, nullable=False)
    idempotency_key = Column(String(255), nullable=True)

    # Timing fields
    scheduled_at = Column(DateTime(timezone=True), nullable=True)  # when to run
    created_at = Column(DateTime(timezone=True), nullable=True)
    claimed_at = Column(DateTime(timezone=True), nullable=True)
    lease_expires_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)

    # Worker ownership
    claimed_by = Column(String(100), nullable=True)   # worker instance ID

    # Error state
    error = Column(Text, nullable=True)               # last error message (truncated)
