import uuid
from datetime import datetime, timezone
from typing import Optional, Any, List, Dict
from sqlalchemy import (
    String,
    Text,
    DateTime,
    Float,
    Integer,
    Boolean,
    Enum as SQLEnum,
    ForeignKey,
    JSON,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base
from app.core.status_machine import (
    ObligationStatus,
    ObligationType,
    EdgeType,
    EvidenceType,
    CorrelationStatus,
    EventSemanticRole,
    ReconciliationStatus,
)
from app.core.intervention_status import (
    InterventionType,
    InterventionStatus,
    InterventionOutcome,
)


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
    
    # Phase 14: Multi-tenant Workspace Scope
    workspace_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
        default="ws-default",
        index=True
    )
    
    # Core domain parties & duty
    owner: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    beneficiary: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    action: Mapped[str] = mapped_column(Text, nullable=False)
    
    # Temporal & conditions
    deadline: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    conditions: Mapped[Optional[Any]] = mapped_column(JSON, nullable=True)
    
    # Verification & state (JSON field kept for backwards compatibility with audit entries)
    evidence: Mapped[Optional[List[Dict[str, Any]]]] = mapped_column(JSON, nullable=True, default=list)
    status: Mapped[ObligationStatus] = mapped_column(
        SQLEnum(ObligationStatus, name="obligation_status_enum", native_enum=False),
        nullable=False,
        default=ObligationStatus.CONFIRMED,
        index=True
    )
    next_action: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Phase 3: Structured Block Reason (e.g. {blocked: true, blocked_by: [{obligation_id, owner, action, status, reason}]})
    block_reason: Mapped[Optional[Any]] = mapped_column(JSON, nullable=True)
    
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

    # Phase 3: Relationships to edges
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

    # Phase 4: Normalized first-class Evidence entities
    evidence_records: Mapped[List["Evidence"]] = relationship(
        "Evidence",
        back_populates="obligation",
        cascade="all, delete-orphan",
        order_by="desc(Evidence.observed_at)",
    )

    # Phase 6: Human-controlled Interventions
    interventions: Mapped[List["Intervention"]] = relationship(
        "Intervention",
        back_populates="obligation",
        cascade="all, delete-orphan",
        order_by="desc(Intervention.created_at)",
    )

    # Phase 11: Cross-Provider Reconciliation Records
    reconciliation_records: Mapped[List["ReconciliationRecord"]] = relationship(
        "ReconciliationRecord",
        back_populates="obligation",
        cascade="all, delete-orphan",
        order_by="desc(ReconciliationRecord.created_at)",
    )

    # Phase 12: Historical Outcome Snapshots & Predictions
    outcome_snapshots: Mapped[List["ObligationOutcomeSnapshot"]] = relationship(
        "ObligationOutcomeSnapshot",
        back_populates="obligation",
        cascade="all, delete-orphan",
        order_by="desc(ObligationOutcomeSnapshot.created_at)",
    )
    prediction_snapshots: Mapped[List["PredictionSnapshot"]] = relationship(
        "PredictionSnapshot",
        back_populates="obligation",
        cascade="all, delete-orphan",
        order_by="desc(PredictionSnapshot.created_at)",
    )
    prediction_feedbacks: Mapped[List["PredictionFeedback"]] = relationship(
        "PredictionFeedback",
        back_populates="obligation",
        cascade="all, delete-orphan",
        order_by="desc(PredictionFeedback.created_at)",
    )



class ObligationEdge(Base):
    __tablename__ = "obligation_edges"
    __table_args__ = (
        UniqueConstraint("from_obligation_id", "to_obligation_id", "edge_type", name="uq_obligation_edge"),
    )

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
        index=True
    )
    
    workspace_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
        default="ws-default",
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


class Evidence(Base):
    __tablename__ = "obligation_evidence"
    __table_args__ = (
        UniqueConstraint("source_type", "source_ref", "obligation_id", name="uq_evidence_source_ob"),
    )

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
        index=True
    )
    workspace_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
        default="ws-default",
        index=True
    )
    obligation_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("obligations.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    actor_user_id: Mapped[Optional[str]] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True
    )
    evidence_type: Mapped[EvidenceType] = mapped_column(
        SQLEnum(EvidenceType, name="evidence_type_enum", native_enum=False),
        nullable=False,
        default=EvidenceType.MESSAGE
    )
    source_type: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        default="message"
    )
    source_ref: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
        index=True
    )
    content: Mapped[str] = mapped_column(
        Text,
        nullable=False
    )
    correlation_status: Mapped[CorrelationStatus] = mapped_column(
        SQLEnum(CorrelationStatus, name="correlation_status_enum", native_enum=False),
        nullable=False,
        default=CorrelationStatus.SUGGESTED,
        index=True
    )
    correlation_confidence: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        default=1.0
    )
    semantic_role: Mapped[EventSemanticRole] = mapped_column(
        SQLEnum(EventSemanticRole, name="event_semantic_role_enum", native_enum=False),
        nullable=False,
        default=EventSemanticRole.COMPLETION_SIGNAL
    )
    reasoning: Mapped[Optional[Any]] = mapped_column(
        JSON,
        nullable=True
    )
    extra_metadata: Mapped[Optional[Any]] = mapped_column(
        JSON,
        nullable=True
    )
    actor: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True
    )
    observed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False
    )

    # ORM relationship
    obligation: Mapped["Obligation"] = relationship(
        "Obligation",
        back_populates="evidence_records"
    )


class Intervention(Base):
    __tablename__ = "interventions"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
        index=True
    )
    workspace_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
        default="ws-default",
        index=True
    )
    obligation_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("obligations.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    actor_user_id: Mapped[Optional[str]] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True
    )
    intervention_type: Mapped[InterventionType] = mapped_column(
        SQLEnum(InterventionType, name="intervention_type_enum", native_enum=False),
        nullable=False,
        index=True
    )
    target_owner: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    target_beneficiary: Mapped[str] = mapped_column(String(255), nullable=False)
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    rationale: Mapped[str] = mapped_column(Text, nullable=False)
    message_draft: Mapped[str] = mapped_column(Text, nullable=False)
    approved_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    context_data: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)
    urgency: Mapped[str] = mapped_column(String(32), nullable=False, default="MEDIUM", index=True)
    status: Mapped[InterventionStatus] = mapped_column(
        SQLEnum(InterventionStatus, name="intervention_status_enum", native_enum=False),
        nullable=False,
        default=InterventionStatus.PENDING_REVIEW,
        index=True
    )
    outcome: Mapped[Optional[InterventionOutcome]] = mapped_column(
        SQLEnum(InterventionOutcome, name="intervention_outcome_enum", native_enum=False),
        nullable=True,
        index=True
    )
    requires_approval: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    approved_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    approved_by: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    scheduled_for: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    executed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    execution_reference: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    execution_mode: Mapped[str] = mapped_column(String(64), default="MOCK_DEMO", nullable=False)
    follow_up_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    cooldown_until: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    chain_depth: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    audit_trail: Mapped[Optional[List[Dict[str, Any]]]] = mapped_column(JSON, nullable=True, default=list)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
        index=True
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        onupdate=utc_now,
        nullable=False
    )

    # ORM relationship
    obligation: Mapped["Obligation"] = relationship(
        "Obligation",
        back_populates="interventions"
    )


class IngestedEventRecord(Base):
    __tablename__ = "ingested_events"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
        index=True
    )
    workspace_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
        default="ws-default",
        index=True
    )
    provider: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    source_type: Mapped[str] = mapped_column(String(64), nullable=False, default="message")
    source_ref: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, index=True)
    sender: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    recipients: Mapped[Optional[List[str]]] = mapped_column(JSON, nullable=True, default=list)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    semantic_role: Mapped[EventSemanticRole] = mapped_column(
        SQLEnum(EventSemanticRole, name="event_semantic_role_enum", native_enum=False),
        nullable=False,
        default=EventSemanticRole.IRRELEVANT,
        index=True
    )
    processing_status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="PROCESSED",
        index=True
    )
    candidate_obligation_ids: Mapped[Optional[List[str]]] = mapped_column(JSON, nullable=True, default=list)
    correlated_obligation_id: Mapped[Optional[str]] = mapped_column(
        String(36),
        ForeignKey("obligations.id", ondelete="SET NULL"),
        nullable=True,
        index=True
    )
    evidence_id: Mapped[Optional[str]] = mapped_column(
        String(36),
        ForeignKey("obligation_evidence.id", ondelete="SET NULL"),
        nullable=True,
        index=True
    )
    correlation_confidence: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    match_explanation: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    action_taken: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    resolved_intervention_id: Mapped[Optional[str]] = mapped_column(
        String(36),
        ForeignKey("interventions.id", ondelete="SET NULL"),
        nullable=True
    )
    raw_payload: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)
    received_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
        index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False
    )


class ReconciliationRecord(Base):
    __tablename__ = "reconciliation_records"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
        index=True
    )
    workspace_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
        default="ws-default",
        index=True
    )
    obligation_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("obligations.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    actor_user_id: Mapped[Optional[str]] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True
    )
    status: Mapped[ReconciliationStatus] = mapped_column(
        SQLEnum(ReconciliationStatus, name="reconciliation_status_enum", native_enum=False),
        nullable=False,
        default=ReconciliationStatus.AMBIGUOUS,
        index=True
    )
    confidence: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    consistency_score: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    contradiction_score: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)

    supporting_evidence_ids: Mapped[Optional[List[str]]] = mapped_column(JSON, nullable=True, default=list)
    conflicting_evidence_ids: Mapped[Optional[List[str]]] = mapped_column(JSON, nullable=True, default=list)
    supporting_event_ids: Mapped[Optional[List[str]]] = mapped_column(JSON, nullable=True, default=list)
    conflicting_event_ids: Mapped[Optional[List[str]]] = mapped_column(JSON, nullable=True, default=list)

    explanation: Mapped[Optional[List[str]]] = mapped_column(JSON, nullable=True, default=list)
    recommended_action: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)

    resolution: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)
    resolved_by: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    resolved_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
        index=True
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        onupdate=utc_now,
        nullable=False
    )

    # ORM relationship
    obligation: Mapped["Obligation"] = relationship(
        "Obligation",
        back_populates="reconciliation_records"
    )



