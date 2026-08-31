"""
SQLAlchemy ORM Model for Decision Plans in Phase 15.
"""

import uuid
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
from sqlalchemy import (
    Column,
    String,
    Integer,
    Float,
    DateTime,
    JSON,
    Text,
    ForeignKey,
    Enum as SQLEnum,
    Index,
)
from sqlalchemy.orm import relationship
from app.core.database import Base
from app.core.status_machine import DecisionPlanStatus


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class DecisionPlan(Base):
    __tablename__ = "decision_plans"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    workspace_id = Column(
        String(36),
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
        default="ws-default",
        index=True,
    )
    target_obligation_id = Column(
        String(36),
        ForeignKey("obligations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    generated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
        index=True,
    )
    plan_version = Column(Integer, nullable=False, default=1, index=True)
    status = Column(
        SQLEnum(DecisionPlanStatus, name="decision_plan_status_enum", native_enum=False),
        nullable=False,
        default=DecisionPlanStatus.GENERATED,
        index=True,
    )
    overall_urgency = Column(String(32), nullable=False, default="MEDIUM")
    overall_risk = Column(Float, nullable=False, default=0.0)
    decision_confidence = Column(Float, nullable=False, default=1.0)
    primary_objective = Column(Text, nullable=False)
    root_cause_obligation_id = Column(
        String(36),
        ForeignKey("obligations.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    critical_path = Column(JSON, nullable=False, default=list)
    impact_summary = Column(JSON, nullable=False, default=dict)
    key_risks = Column(JSON, nullable=False, default=list)
    supporting_evidence = Column(JSON, nullable=False, default=list)
    recommended_actions = Column(JSON, nullable=False, default=dict)
    alternative_actions = Column(JSON, nullable=False, default=list)
    human_decisions_required = Column(JSON, nullable=False, default=list)
    assumptions = Column(JSON, nullable=False, default=list)
    uncertainties = Column(JSON, nullable=False, default=list)
    simulation_summary = Column(JSON, nullable=False, default=dict)
    created_from_snapshot_ids = Column(JSON, nullable=False, default=list)
    created_from_event_ids = Column(JSON, nullable=False, default=list)

    # Authorization & Lifecycle
    approved_at = Column(DateTime(timezone=True), nullable=True)
    approved_by_user_id = Column(
        String(36),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    rejected_at = Column(DateTime(timezone=True), nullable=True)
    rejected_by_user_id = Column(
        String(36),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    superseded_at = Column(DateTime(timezone=True), nullable=True)
    superseded_by_plan_id = Column(String(36), nullable=True)
    resolution_notes = Column(Text, nullable=True)

    # Indexes
    __table_args__ = (
        Index("ix_decision_plans_ws_target", "workspace_id", "target_obligation_id"),
        Index("ix_decision_plans_status_gen", "status", "generated_at"),
    )
