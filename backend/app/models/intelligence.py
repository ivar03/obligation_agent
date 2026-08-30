import uuid
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any

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
)
from sqlalchemy.orm import relationship

from app.core.database import Base


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def generate_uuid() -> str:
    return str(uuid.uuid4())


class ObligationOutcomeSnapshot(Base):
    """
    Historical outcome snapshot capturing deterministic lifecycle outcomes,
    delays, intervention efficacy, and dependency patterns for learning.
    """
    __tablename__ = "obligation_outcome_snapshots"

    id = Column(String(36), primary_key=True, default=generate_uuid, index=True)
    workspace_id = Column(
        String(36),
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
        default="ws-default",
        index=True,
    )
    obligation_id = Column(
        String(36),
        ForeignKey("obligations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    snapshot_time = Column(DateTime(timezone=True), default=utc_now, nullable=False)
    status = Column(String(32), nullable=False)
    outcome_type = Column(String(64), nullable=False, index=True)
    owner = Column(String(255), nullable=False, index=True)
    beneficiary = Column(String(255), nullable=False)
    obligation_type = Column(String(32), nullable=False)
    action = Column(Text, nullable=False)
    deadline = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    delay_hours = Column(Float, nullable=False, default=0.0)
    risk_score = Column(Float, nullable=False, default=0.0)
    risk_level = Column(String(32), nullable=False, default="LOW")
    dependency_count = Column(Integer, nullable=False, default=0)
    blocker_count = Column(Integer, nullable=False, default=0)
    evidence_count = Column(Integer, nullable=False, default=0)
    intervention_count = Column(Integer, nullable=False, default=0)
    intervention_required = Column(Boolean, nullable=False, default=False)
    intervention_successful = Column(Boolean, nullable=False, default=False)
    reconciliation_conflict_occurred = Column(Boolean, nullable=False, default=False)
    relevant_event_signals = Column(JSON, nullable=True)
    extra_metadata = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False, index=True)
    updated_at = Column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)

    # Relationships
    obligation = relationship("Obligation", back_populates="outcome_snapshots")


class PredictionSnapshot(Base):
    """
    Historical prediction snapshot recording model forecast vs actual outcome
    for accuracy evaluation, calibration tracking, and continuous learning.
    """
    __tablename__ = "prediction_snapshots"

    id = Column(String(36), primary_key=True, default=generate_uuid, index=True)
    workspace_id = Column(
        String(36),
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
        default="ws-default",
        index=True,
    )
    obligation_id = Column(
        String(36),
        ForeignKey("obligations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    model_version = Column(String(64), nullable=False, default="predictive-v1", index=True)
    prediction_type = Column(String(64), nullable=False, default="FAILURE_PROBABILITY")
    failure_probability = Column(Float, nullable=False, default=0.0)
    completion_probability = Column(Float, nullable=False, default=1.0)
    expected_delay_hours = Column(Float, nullable=False, default=0.0)
    intervention_likelihood = Column(Float, nullable=False, default=0.0)
    blockage_likelihood = Column(Float, nullable=False, default=0.0)
    confidence = Column(Float, nullable=False, default=0.0)
    prediction_reasons = Column(JSON, nullable=True)
    preventative_recommendation = Column(Text, nullable=True)
    recommended_action_type = Column(String(64), nullable=True)
    actual_outcome = Column(String(64), nullable=True)
    actual_delay_hours = Column(Float, nullable=True)
    evaluated_at = Column(DateTime(timezone=True), nullable=True)
    prediction_error = Column(Float, nullable=True)
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False, index=True)

    # Relationships
    obligation = relationship("Obligation", back_populates="prediction_snapshots")
    feedbacks = relationship("PredictionFeedback", back_populates="prediction_snapshot", cascade="all, delete-orphan")


class PredictionFeedback(Base):
    """
    First-class prediction feedback record evaluating a forecast against
    actual observed ground-truth outcome, computing error metrics,
    preserving feature attribution, and driving adaptive weight learning.
    """
    __tablename__ = "prediction_feedbacks"

    id = Column(String(36), primary_key=True, default=generate_uuid, index=True)
    workspace_id = Column(
        String(36),
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
        default="ws-default",
        index=True,
    )
    prediction_snapshot_id = Column(
        String(36),
        ForeignKey("prediction_snapshots.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    obligation_id = Column(
        String(36),
        ForeignKey("obligations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    prediction_provider = Column(String(64), nullable=False, default="deterministic-v1", index=True)
    model_version = Column(String(64), nullable=False, default="predictive-v1", index=True)
    predicted_failure_probability = Column(Float, nullable=False, default=0.0)
    predicted_completion_probability = Column(Float, nullable=False, default=1.0)
    predicted_expected_delay_hours = Column(Float, nullable=False, default=0.0)
    predicted_intervention_likelihood = Column(Float, nullable=False, default=0.0)
    predicted_confidence = Column(Float, nullable=False, default=0.0)
    feature_attributions = Column(JSON, nullable=True)
    observed_outcome = Column(String(64), nullable=False, index=True)
    observed_delay_hours = Column(Float, nullable=False, default=0.0)
    absolute_delay_error = Column(Float, nullable=False, default=0.0)
    probability_error = Column(Float, nullable=False, default=0.0)
    was_high_risk_prediction_correct = Column(Boolean, nullable=True)
    intervention_recommended = Column(Boolean, nullable=False, default=False)
    intervention_taken = Column(Boolean, nullable=False, default=False)
    intervention_effective = Column(Boolean, nullable=True)
    extra_metadata = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False, index=True)

    # Relationships
    prediction_snapshot = relationship("PredictionSnapshot", back_populates="feedbacks")
    obligation = relationship("Obligation", back_populates="prediction_feedbacks")
