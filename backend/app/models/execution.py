"""
SQLAlchemy ORM Model for Controlled Execution in Phase 16.
"""

import uuid
from datetime import datetime, timezone
from typing import Optional, Dict, Any
from sqlalchemy import (
     Column,
     String,
     Integer,
     DateTime,
     JSON,
     Text,
     ForeignKey,
     Enum as SQLEnum,
     Index,
)
from sqlalchemy.orm import relationship
from app.core.database import Base
from app.core.status_machine import (
     ExecutionStatus,
     ExecutionType,
     ExecutionOutcome,
     ExecutionFailureCode,
)


def utc_now() -> datetime:
     return datetime.now(timezone.utc)


class ExecutionRecord(Base):
     __tablename__ = "execution_records"

     id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
     workspace_id = Column(
         String(36),
         ForeignKey("workspaces.id", ondelete="CASCADE"),
         nullable=False,
         default="ws-default",
         index=True,
     )
     decision_plan_id = Column(
         String(36),
         ForeignKey("decision_plans.id", ondelete="CASCADE"),
         nullable=False,
         index=True,
     )
     intervention_id = Column(
         String(36),
         ForeignKey("interventions.id", ondelete="SET NULL"),
         nullable=True,
         index=True,
     )
     obligation_id = Column(
         String(36),
         ForeignKey("obligations.id", ondelete="CASCADE"),
         nullable=False,
         index=True,
     )
     execution_type = Column(
         SQLEnum(ExecutionType, name="execution_type_enum", native_enum=False),
         nullable=False,
         default=ExecutionType.INTERVENTION_MESSAGE,
         index=True,
     )
     provider = Column(String(64), nullable=False, default="mock", index=True)
     provider_version = Column(String(32), nullable=False, default="1.0.0")
     status = Column(
         SQLEnum(ExecutionStatus, name="execution_status_enum", native_enum=False),
         nullable=False,
         default=ExecutionStatus.PENDING_AUTHORIZATION,
         index=True,
     )
     authorized_by = Column(String(128), nullable=True)
     authorized_at = Column(DateTime(timezone=True), nullable=True)
     executed_at = Column(DateTime(timezone=True), nullable=True, index=True)
     provider_execution_ref = Column(String(128), nullable=True, index=True)
     idempotency_key = Column(String(128), nullable=False, index=True)
     request_payload_hash = Column(String(64), nullable=False)
     safe_request_metadata = Column(JSON, nullable=False, default=dict)
     delivery_status = Column(String(64), nullable=True)
     failure_code = Column(
         SQLEnum(ExecutionFailureCode, name="execution_failure_code_enum", native_enum=False),
         nullable=True,
     )
     failure_reason = Column(Text, nullable=True)
     retry_count = Column(Integer, nullable=False, default=0)
     max_retries = Column(Integer, nullable=False, default=3)
     next_retry_at = Column(DateTime(timezone=True), nullable=True)
     response_received_at = Column(DateTime(timezone=True), nullable=True)
     response_event_id = Column(
         String(36),
         ForeignKey("ingested_events.id", ondelete="SET NULL"),
         nullable=True,
         index=True,
     )
     outcome = Column(
         SQLEnum(ExecutionOutcome, name="execution_outcome_enum", native_enum=False),
         nullable=True,
     )
     created_at = Column(DateTime(timezone=True), nullable=False, default=utc_now, index=True)
     updated_at = Column(
         DateTime(timezone=True),
         nullable=False,
         default=utc_now,
         onupdate=utc_now,
     )

     # Relationships
     decision_plan = relationship("DecisionPlan", foreign_keys=[decision_plan_id], lazy="joined")
     intervention = relationship("Intervention", foreign_keys=[intervention_id], lazy="joined")
     obligation = relationship("Obligation", foreign_keys=[obligation_id], lazy="joined")

     __table_args__ = (
         Index("ix_execution_records_ws_status", "workspace_id", "status"),
         Index("ix_execution_records_ws_idempotency", "workspace_id", "idempotency_key"),
     )
