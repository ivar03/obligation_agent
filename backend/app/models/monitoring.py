import uuid
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List
from sqlalchemy import (
    String,
    Text,
    DateTime,
    Integer,
    ForeignKey,
    JSON,
    Enum as SQLEnum,
    Index,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.core.status_machine import (
    WatchType,
    WatchStatus,
    MonitoringEventType,
    MonitoringSeverity,
    EscalationStatus,
    MonitoringRunStatus,
    TargetType,
)


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class MonitoringWatch(Base):
    __tablename__ = "monitoring_watches"
    __table_args__ = (
        Index("ix_monitoring_watches_ws_status", "workspace_id", "status"),
        Index("ix_monitoring_watches_ws_target", "workspace_id", "target_type", "target_id"),
        Index("ix_monitoring_watches_next_eval", "workspace_id", "status", "next_evaluation_at"),
    )

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )
    workspace_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
        default="ws-default",
    )
    watch_type: Mapped[WatchType] = mapped_column(
        SQLEnum(WatchType, name="watch_type_enum", native_enum=False),
        nullable=False,
        default=WatchType.DEADLINE,
    )
    target_type: Mapped[TargetType] = mapped_column(
        SQLEnum(TargetType, name="target_type_enum", native_enum=False),
        nullable=False,
        default=TargetType.OBLIGATION,
    )
    target_id: Mapped[str] = mapped_column(
        String(128),
        nullable=False,
    )
    status: Mapped[WatchStatus] = mapped_column(
        SQLEnum(WatchStatus, name="watch_status_enum", native_enum=False),
        nullable=False,
        default=WatchStatus.ACTIVE,
    )
    configuration: Mapped[Dict[str, Any]] = mapped_column(
        JSON,
        nullable=False,
        default=dict,
    )
    last_evaluated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    next_evaluation_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    last_observed_state: Mapped[Dict[str, Any]] = mapped_column(
        JSON,
        nullable=False,
        default=dict,
    )
    last_triggered_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    trigger_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )
    cooldown_until: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    created_by: Mapped[Optional[str]] = mapped_column(
        String(128),
        nullable=True,
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

    # Relationships
    events: Mapped[List["MonitoringEvent"]] = relationship(
        "MonitoringEvent",
        back_populates="watch",
        cascade="all, delete-orphan",
    )


class MonitoringEvent(Base):
    __tablename__ = "monitoring_events"
    __table_args__ = (
        Index("ix_monitoring_events_ws_severity", "workspace_id", "severity"),
        Index("ix_monitoring_events_ws_target", "workspace_id", "target_type", "target_id"),
        Index("ix_monitoring_events_ws_dedup", "workspace_id", "deduplication_key"),
        Index("ix_monitoring_events_detected_at", "workspace_id", "detected_at"),
    )

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )
    workspace_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
        default="ws-default",
    )
    watch_id: Mapped[Optional[str]] = mapped_column(
        String(36),
        ForeignKey("monitoring_watches.id", ondelete="SET NULL"),
        nullable=True,
    )
    event_type: Mapped[MonitoringEventType] = mapped_column(
        SQLEnum(MonitoringEventType, name="monitoring_event_type_enum", native_enum=False),
        nullable=False,
    )
    severity: Mapped[MonitoringSeverity] = mapped_column(
        SQLEnum(MonitoringSeverity, name="monitoring_severity_enum", native_enum=False),
        nullable=False,
        default=MonitoringSeverity.INFO,
    )
    target_type: Mapped[TargetType] = mapped_column(
        SQLEnum(TargetType, name="target_type_enum", native_enum=False),
        nullable=False,
        default=TargetType.OBLIGATION,
    )
    target_id: Mapped[str] = mapped_column(
        String(128),
        nullable=False,
    )
    previous_state: Mapped[Dict[str, Any]] = mapped_column(
        JSON,
        nullable=False,
        default=dict,
    )
    current_state: Mapped[Dict[str, Any]] = mapped_column(
        JSON,
        nullable=False,
        default=dict,
    )
    detected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
    )
    explanation: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    signals: Mapped[Dict[str, Any]] = mapped_column(
        JSON,
        nullable=False,
        default=dict,
    )
    provenance: Mapped[Dict[str, Any]] = mapped_column(
        JSON,
        nullable=False,
        default=dict,
    )
    deduplication_key: Mapped[str] = mapped_column(
        String(128),
        nullable=False,
    )
    acknowledged_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    acknowledged_by: Mapped[Optional[str]] = mapped_column(
        String(128),
        nullable=True,
    )
    resolved_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    resolution_reason: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )

    # Relationships
    watch: Mapped[Optional["MonitoringWatch"]] = relationship(
        "MonitoringWatch",
        back_populates="events",
    )
    escalation_candidates: Mapped[List["EscalationCandidate"]] = relationship(
        "EscalationCandidate",
        back_populates="monitoring_event",
        cascade="all, delete-orphan",
    )


class EscalationCandidate(Base):
    __tablename__ = "escalation_candidates"
    __table_args__ = (
        Index("ix_escalation_candidates_ws_status", "workspace_id", "status"),
        Index("ix_escalation_candidates_ws_severity", "workspace_id", "severity"),
        Index("ix_escalation_candidates_ws_target", "workspace_id", "target_type", "target_id"),
        Index("ix_escalation_candidates_ws_dedup", "workspace_id", "deduplication_key"),
    )

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )
    workspace_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
        default="ws-default",
    )
    monitoring_event_id: Mapped[Optional[str]] = mapped_column(
        String(36),
        ForeignKey("monitoring_events.id", ondelete="SET NULL"),
        nullable=True,
    )
    target_type: Mapped[TargetType] = mapped_column(
        SQLEnum(TargetType, name="target_type_enum", native_enum=False),
        nullable=False,
        default=TargetType.OBLIGATION,
    )
    target_id: Mapped[str] = mapped_column(
        String(128),
        nullable=False,
    )
    severity: Mapped[MonitoringSeverity] = mapped_column(
        SQLEnum(MonitoringSeverity, name="monitoring_severity_enum", native_enum=False),
        nullable=False,
        default=MonitoringSeverity.WARNING,
    )
    reason: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    recommended_next_step: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    affected_obligations: Mapped[List[str]] = mapped_column(
        JSON,
        nullable=False,
        default=list,
    )
    affected_owners: Mapped[List[str]] = mapped_column(
        JSON,
        nullable=False,
        default=list,
    )
    blast_radius: Mapped[Dict[str, Any]] = mapped_column(
        JSON,
        nullable=False,
        default=dict,
    )
    decision_plan_id: Mapped[Optional[str]] = mapped_column(
        String(36),
        nullable=True,
    )
    status: Mapped[EscalationStatus] = mapped_column(
        SQLEnum(EscalationStatus, name="escalation_status_enum", native_enum=False),
        nullable=False,
        default=EscalationStatus.OPEN,
    )
    deduplication_key: Mapped[str] = mapped_column(
        String(128),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
    )
    acknowledged_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    acknowledged_by: Mapped[Optional[str]] = mapped_column(
        String(128),
        nullable=True,
    )
    resolved_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # Relationships
    monitoring_event: Mapped[Optional["MonitoringEvent"]] = relationship(
        "MonitoringEvent",
        back_populates="escalation_candidates",
    )


class MonitoringRun(Base):
    __tablename__ = "monitoring_runs"
    __table_args__ = (
        Index("ix_monitoring_runs_ws_status", "workspace_id", "status"),
        Index("ix_monitoring_runs_ws_started", "workspace_id", "started_at"),
    )

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )
    workspace_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
        default="ws-default",
    )
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    watches_evaluated: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )
    events_created: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )
    escalations_created: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )
    errors: Mapped[List[Dict[str, Any]]] = mapped_column(
        JSON,
        nullable=False,
        default=list,
    )
    status: Mapped[MonitoringRunStatus] = mapped_column(
        SQLEnum(MonitoringRunStatus, name="monitoring_run_status_enum", native_enum=False),
        nullable=False,
        default=MonitoringRunStatus.RUNNING,
    )
