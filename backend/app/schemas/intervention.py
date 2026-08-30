from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, ConfigDict
from app.core.intervention_status import (
    InterventionType,
    InterventionStatus,
    InterventionOutcome,
)


class InterventionAuditEntry(BaseModel):
    event: str
    actor: str = "USER"
    timestamp: datetime
    details: Optional[Dict[str, Any]] = None


class InterventionCreate(BaseModel):
    obligation_id: str
    intervention_type: InterventionType
    target_owner: str
    target_beneficiary: str
    title: str
    rationale: str
    message_draft: str
    approved_message: Optional[str] = None
    context_data: Optional[Dict[str, Any]] = Field(default_factory=dict)
    urgency: str = "MEDIUM"
    status: InterventionStatus = InterventionStatus.PENDING_REVIEW
    requires_approval: bool = True
    scheduled_for: Optional[datetime] = None
    chain_depth: int = 1


class InterventionUpdate(BaseModel):
    target_owner: Optional[str] = None
    target_beneficiary: Optional[str] = None
    title: Optional[str] = None
    approved_message: Optional[str] = None
    scheduled_for: Optional[datetime] = None
    urgency: Optional[str] = None
    context_data: Optional[Dict[str, Any]] = None


class InterventionPlanRequest(BaseModel):
    obligation_id: str
    force: bool = Field(default=False, description="Bypass cooldown/duplicate check if force is True")


class InterventionApproveRequest(BaseModel):
    approved_by: Optional[str] = "USER"
    approved_message: Optional[str] = None


class InterventionScheduleRequest(BaseModel):
    scheduled_for: datetime
    approved_message: Optional[str] = None
    approved_by: Optional[str] = "USER"


class InterventionOutcomeRequest(BaseModel):
    outcome: InterventionOutcome
    notes: Optional[str] = None


class InterventionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    obligation_id: str
    intervention_type: InterventionType
    target_owner: str
    target_beneficiary: str
    title: str
    rationale: str
    message_draft: str
    approved_message: Optional[str] = None
    context_data: Optional[Dict[str, Any]] = None
    urgency: str
    status: InterventionStatus
    outcome: Optional[InterventionOutcome] = None
    requires_approval: bool = True
    approved_at: Optional[datetime] = None
    approved_by: Optional[str] = None
    scheduled_for: Optional[datetime] = None
    executed_at: Optional[datetime] = None
    execution_reference: Optional[str] = None
    execution_mode: str = "MOCK_DEMO"
    follow_up_at: Optional[datetime] = None
    cooldown_until: Optional[datetime] = None
    chain_depth: int = 1
    audit_trail: Optional[List[Dict[str, Any]]] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime


class InterventionListResponse(BaseModel):
    items: List[InterventionResponse]
    total: int


class InterventionQueueResponse(BaseModel):
    pending_review_count: int
    ready_to_execute_count: int
    scheduled_count: int
    total_action_required: int
    items: List[InterventionResponse] = Field(default_factory=list)
