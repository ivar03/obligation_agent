import uuid
from datetime import datetime, timezone
from typing import Optional, Any, List, Dict
from sqlalchemy import (
    String,
    Text,
    DateTime,
    Enum as SQLEnum,
    ForeignKey,
    JSON,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base
from app.core.status_machine import ObligationStatus, ObligationType, EdgeType


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class Obligation(Base):
    __tablename__ = "obligations"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
        index=True
    )
    
    # Core domain parties & duty
    owner: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    beneficiary: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    action: Mapped[str] = mapped_column(Text, nullable=False)
    
    # Temporal & conditions
    deadline: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    conditions: Mapped[Optional[Any]] = mapped_column(JSON, nullable=True)
    
    # Verification & state
    evidence: Mapped[Optional[List[Dict[str, Any]]]] = mapped_column(JSON, nullable=True, default=list)
    status: Mapped[ObligationStatus] = mapped_column(
        SQLEnum(ObligationStatus, name="obligation_status_enum", native_enum=False),
        nullable=False,
        default=ObligationStatus.CONFIRMED,
        index=True
    )
    next_action: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    # Provenance & categorization
    source_ref: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    obligation_type: Mapped[ObligationType] = mapped_column(
        SQLEnum(ObligationType, name="obligation_type_enum", native_enum=False),
        nullable=False,
        index=True
    )
    
    # AI Extraction confidence (supports field-level breakdown)
    confidence: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        onupdate=utc_now,
        nullable=False
    )

    # Relationships to edges (future-compatible graph linking)
    outgoing_edges: Mapped[List["ObligationEdge"]] = relationship(
        "ObligationEdge",
        foreign_keys="ObligationEdge.from_obligation_id",
        back_populates="from_obligation",
        cascade="all, delete-orphan",
    )
    incoming_edges: Mapped[List["ObligationEdge"]] = relationship(
        "ObligationEdge",
        foreign_keys="ObligationEdge.to_obligation_id",
        back_populates="to_obligation",
        cascade="all, delete-orphan",
    )


class ObligationEdge(Base):
    __tablename__ = "obligation_edges"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
        index=True
    )
    
    from_obligation_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("obligations.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    to_obligation_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("obligations.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    edge_type: Mapped[EdgeType] = mapped_column(
        SQLEnum(EdgeType, name="edge_type_enum", native_enum=False),
        nullable=False,
        default=EdgeType.LINKED
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False
    )

    # ORM relationships
    from_obligation: Mapped["Obligation"] = relationship(
        "Obligation",
        foreign_keys=[from_obligation_id],
        back_populates="outgoing_edges"
    )
    to_obligation: Mapped["Obligation"] = relationship(
        "Obligation",
        foreign_keys=[to_obligation_id],
        back_populates="incoming_edges"
    )
