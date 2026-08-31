"""
Pydantic Schemas for Controlled Execution Layer in Phase 16.
"""

from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, ConfigDict
from app.core.status_machine import (
    ExecutionStatus,
    ExecutionType,
    ExecutionOutcome,
    ExecutionFailureCode,
)


class ExecutionAuthorizeRequest(BaseModel):
    strategy_name: Optional[str] = None
    provider: Optional[str] = "mock"
    authorized_action: Optional[Dict[str, Any]] = None
    notes: Optional[str] = None


class ExecutionExecuteRequest(BaseModel):
    provider: Optional[str] = None
    idempotency_key: Optional[str] = None
    notes: Optional[str] = None


class ExecutionCancelRequest(BaseModel):
    reason: str


class ExecutionRetryRequest(BaseModel):
    reason: Optional[str] = None


class ExecutionRecordResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    workspace_id: str
    decision_plan_id: str
    intervention_id: Optional[str] = None
    obligation_id: str
    execution_type: ExecutionType
    provider: str
    provider_version: str
    status: ExecutionStatus
    authorized_by: Optional[str] = None
    authorized_at: Optional[datetime] = None
    executed_at: Optional[datetime] = None
    provider_execution_ref: Optional[str] = None
    idempotency_key: str
    request_payload_hash: str
    safe_request_metadata: Dict[str, Any] = Field(default_factory=dict)
    delivery_status: Optional[str] = None
    failure_code: Optional[ExecutionFailureCode] = None
    failure_reason: Optional[str] = None
    retry_count: int
    max_retries: int
    next_retry_at: Optional[datetime] = None
    response_received_at: Optional[datetime] = None
    response_event_id: Optional[str] = None
    outcome: Optional[ExecutionOutcome] = None
    created_at: datetime
    updated_at: datetime


class ExecutionReceiptResponse(BaseModel):
    execution_id: str
    workspace_id: str
    decision_plan_id: str
    plan_version: int
    intervention_id: Optional[str] = None
    obligation_id: str
    obligation_action: str
    target_owner: Optional[str] = None
    provider: str
    provider_execution_ref: Optional[str] = None
    delivery_status: str
    status: ExecutionStatus
    authorized_by: Optional[str] = None
    authorized_at: Optional[datetime] = None
    executed_at: Optional[datetime] = None
    retry_count: int
    failure_code: Optional[str] = None
    failure_reason: Optional[str] = None
    safe_metadata: Dict[str, Any] = Field(default_factory=dict)
    receipt_generated_at: datetime


class ExecutionHistoryResponse(BaseModel):
    items: List[ExecutionRecordResponse]
    total: int


class ExecutionQueueItem(BaseModel):
    execution: ExecutionRecordResponse
    obligation_action: str
    obligation_owner: Optional[str] = None
    plan_urgency: str
    plan_risk: float


class ExecutionQueueResponse(BaseModel):
    pending_authorization_count: int
    executing_count: int
    delivered_count: int
    awaiting_response_count: int
    resolved_count: int
    failed_count: int
    items: List[ExecutionQueueItem]


class OutcomeReconciliationResponse(BaseModel):
    execution_id: str
    event_id: str
    outcome: ExecutionOutcome
    previous_execution_status: ExecutionStatus
    updated_execution_status: ExecutionStatus
    intervention_status: Optional[str] = None
    obligation_status: str
    evidence_created: bool
    evidence_id: Optional[str] = None
    plan_marked_stale: bool
    reconciled_at: datetime
    reconciliation_notes: str
