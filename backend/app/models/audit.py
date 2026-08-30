"""
SQLAlchemy ORM Model for Immutable Audit & Governance Events.
"""

import uuid
from datetime import datetime, timezone
from sqlalchemy import (
    Column,
    String,
    DateTime,
    JSON,
    Text,
    ForeignKey,
    Index,
)
from sqlalchemy.orm import relationship
from app.core.database import Base


class AuditEvent(Base):
    __tablename__ = "audit_events"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    workspace_id = Column(
        String(36),
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    actor_user_id = Column(
        String(36),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    actor_role = Column(String(50), nullable=True)
    action = Column(String(100), nullable=False, index=True)
    entity_type = Column(String(50), nullable=True, index=True)
    entity_id = Column(String(100), nullable=True, index=True)
    timestamp = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        index=True,
    )
    request_id = Column(String(64), nullable=True, index=True)
    source = Column(String(50), nullable=False, default="API")
    ip_address = Column(String(100), nullable=True)
    user_agent = Column(String(500), nullable=True)
    before_state = Column(JSON, nullable=True)
    after_state = Column(JSON, nullable=True)
    audit_metadata = Column(JSON, nullable=True)
    reason = Column(Text, nullable=True)
    severity = Column(String(20), nullable=False, default="INFO")
    result = Column(String(20), nullable=False, default="SUCCESS")
    previous_event_hash = Column(String(64), nullable=True)
    event_hash = Column(String(64), nullable=False, index=True)

    # Relationships
    workspace = relationship("Workspace", backref="audit_events", lazy="selectin")
    actor = relationship("User", backref="audit_events", lazy="selectin")

    __table_args__ = (
        Index("ix_audit_events_ws_timestamp", "workspace_id", "timestamp"),
        Index("ix_audit_events_ws_action", "workspace_id", "action"),
        Index("ix_audit_events_ws_entity", "workspace_id", "entity_type", "entity_id"),
    )
