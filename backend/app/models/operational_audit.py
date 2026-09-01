"""
Phase 21 Operational Audit Record Model.

Provides append-only, tamper-evident audit logging for all infrastructure,
security, worker, provider, LLM, and operational events with SHA-256 hash chaining.
"""

import uuid
from datetime import datetime, timezone
from sqlalchemy import (
    Column,
    String,
    DateTime,
    Text,
    JSON,
    ForeignKey,
    Index,
)
from app.core.database import Base


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def generate_op_audit_id() -> str:
    return f"opaud-{uuid.uuid4().hex}"


class OperationalAuditRecord(Base):
    """
    Immutable, append-only operational audit log with SHA-256 hash chaining.
    """
    __tablename__ = "operational_audit_records"

    id = Column(String(64), primary_key=True, default=generate_op_audit_id, index=True)
    workspace_id = Column(
        String(36),
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
        default="ws-default",
        index=True,
    )
    timestamp = Column(DateTime(timezone=True), default=utc_now, nullable=False, index=True)
    event_type = Column(String(64), nullable=False, index=True)
    severity = Column(String(32), nullable=False, default="INFO", index=True)
    actor_type = Column(String(32), nullable=False, default="SYSTEM")
    actor_id = Column(String(128), nullable=True, index=True)
    request_id = Column(String(64), nullable=True, index=True)
    trace_id = Column(String(64), nullable=True, index=True)
    span_id = Column(String(32), nullable=True)
    resource_type = Column(String(64), nullable=True, index=True)
    resource_id = Column(String(128), nullable=True, index=True)
    provider = Column(String(64), nullable=True, index=True)
    action = Column(String(128), nullable=False)
    result = Column(String(32), nullable=False, default="SUCCESS", index=True)
    error_code = Column(String(64), nullable=True, index=True)
    metadata_json = Column(JSON, nullable=True)
    previous_hash = Column(String(64), nullable=True)
    record_hash = Column(String(64), nullable=False, index=True)

    __table_args__ = (
        Index("ix_op_audit_ws_time", "workspace_id", "timestamp"),
        Index("ix_op_audit_ws_event", "workspace_id", "event_type"),
        Index("ix_op_audit_ws_trace", "workspace_id", "trace_id"),
        Index("ix_op_audit_ws_req", "workspace_id", "request_id"),
        Index("ix_op_audit_ws_resource", "workspace_id", "resource_type", "resource_id"),
    )
