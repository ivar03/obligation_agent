"""
SQLAlchemy ORM Model for Organizational Memory in Phase 16.
"""

import uuid
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
from sqlalchemy import (
    Column,
    String,
    Float,
    Boolean,
    DateTime,
    JSON,
    Text,
    ForeignKey,
    Enum as SQLEnum,
    Index,
)
from sqlalchemy.orm import relationship
from app.core.database import Base
from app.core.status_machine import MemoryType


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class OrganizationalMemory(Base):
    __tablename__ = "organizational_memories"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    workspace_id = Column(
        String(36),
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
        default="ws-default",
        index=True,
    )
    memory_type = Column(
        SQLEnum(MemoryType, name="memory_type_enum", native_enum=False),
        nullable=False,
        index=True,
    )
    source_type = Column(String(64), nullable=False, default="obligation")
    source_ref = Column(String(255), nullable=True)

    obligation_id = Column(
        String(36),
        ForeignKey("obligations.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    event_id = Column(String(36), nullable=True, index=True)
    owner_id = Column(String(128), nullable=True, index=True)

    content = Column(Text, nullable=False)
    semantic_summary = Column(Text, nullable=False)
    semantic_labels = Column(JSON, nullable=False, default=list)
    entities = Column(JSON, nullable=False, default=list)
    topics = Column(JSON, nullable=False, default=list)

    outcome = Column(String(64), nullable=True)
    observed_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
        index=True,
    )
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
    )

    metadata_json = Column(JSON, nullable=False, default=dict)
    importance_score = Column(Float, nullable=False, default=0.5)
    confidence = Column(Float, nullable=False, default=1.0)
    is_active = Column(Boolean, nullable=False, default=True)

    __table_args__ = (
        Index("ix_org_memories_ws_type", "workspace_id", "memory_type"),
        Index("ix_org_memories_ws_owner", "workspace_id", "owner_id"),
        Index("ix_org_memories_ws_observed", "workspace_id", "observed_at"),
        Index("ix_org_memories_obligation", "obligation_id"),
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "workspace_id": self.workspace_id,
            "memory_type": self.memory_type.value if hasattr(self.memory_type, "value") else str(self.memory_type),
            "source_type": self.source_type,
            "source_ref": self.source_ref,
            "obligation_id": self.obligation_id,
            "event_id": self.event_id,
            "owner_id": self.owner_id,
            "content": self.content,
            "semantic_summary": self.semantic_summary,
            "semantic_labels": self.semantic_labels or [],
            "entities": self.entities or [],
            "topics": self.topics or [],
            "outcome": self.outcome,
            "observed_at": self.observed_at.isoformat() if self.observed_at else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "metadata": self.metadata_json or {},
            "importance_score": self.importance_score,
            "confidence": self.confidence,
            "is_active": self.is_active,
        }
