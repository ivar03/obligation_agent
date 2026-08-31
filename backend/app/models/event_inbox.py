"""
SQLAlchemy ORM Model for Durable Event Inbox and Asynchronous Event Processing.
Stores buffered external provider events with strong database-level idempotency,
stream-based partition keys, attempt counters, lease recovery, and DLQ tracking.
"""

import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Dict, Any, Optional
from sqlalchemy import (
    Column,
    String,
    DateTime,
    Integer,
    Float,
    Text,
    JSON,
    ForeignKey,
    UniqueConstraint,
    Index,
    Enum as SQLEnum,
)
from sqlalchemy.orm import Mapped, mapped_column
from app.core.database import Base


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class EventInboxStatus(str, Enum):
    RECEIVED = "RECEIVED"
    QUEUED = "QUEUED"
    PROCESSING = "PROCESSING"
    PROCESSED = "PROCESSED"
    RETRY_SCHEDULED = "RETRY_SCHEDULED"
    FAILED = "FAILED"
    DEAD_LETTER = "DEAD_LETTER"


class EventInboxRecord(Base):
    """
    Durable Event Inbox entity.
    Guarantees exactly-once logical processing via deterministic composite unique constraints,
    while enabling fast webhook acknowledgement and asynchronous pipeline execution.
    """
    __tablename__ = "event_inbox"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
        index=True,
    )
    workspace_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
        default="ws-default",
        index=True,
    )
    provider: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        index=True,
    )
    source_ref: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
        index=True,
    )
    event_type: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        default="message",
    )
    payload_hash: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        index=True,
    )
    stream_key: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        default="default",
        index=True,
    )
    payload_metadata: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSON,
        nullable=True,
    )
    raw_payload: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSON,
        nullable=True,
    )
    status: Mapped[EventInboxStatus] = mapped_column(
        SQLEnum(EventInboxStatus, name="event_inbox_status_enum", native_enum=False),
        nullable=False,
        default=EventInboxStatus.QUEUED,
        index=True,
    )
    attempt_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )
    max_attempts: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=3,
    )
    last_error: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    locked_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    locked_by: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
    )
    lease_expires_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    received_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
        index=True,
    )
    available_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
        index=True,
    )
    processed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    processing_duration_ms: Mapped[Optional[float]] = mapped_column(
        Float,
        nullable=True,
    )
    correlation_id: Mapped[Optional[str]] = mapped_column(
        String(64),
        nullable=True,
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        onupdate=utc_now,
        nullable=False,
    )

    __table_args__ = (
        UniqueConstraint(
            "workspace_id", "provider", "source_ref", "payload_hash",
            name="uq_event_inbox_idempotency"
        ),
        Index("ix_event_inbox_status_available", "status", "available_at"),
        Index("ix_event_inbox_stream_status", "stream_key", "status"),
        Index("ix_event_inbox_ws_status", "workspace_id", "status"),
    )
