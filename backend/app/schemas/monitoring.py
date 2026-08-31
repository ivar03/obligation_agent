from datetime import datetime
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field, ConfigDict

from app.core.status_machine import (
    WatchType,
    WatchStatus,
    MonitoringEventType,
    MonitoringSeverity,
    EscalationStatus,
    MonitoringRunStatus,
    TargetType,
)


# --- Monitoring Watch Schemas ---

class MonitoringWatchCreate(BaseModel):
    watch_type: WatchType = Field(default=WatchType.DEADLINE)
    target_type: TargetType = Field(default=TargetType.OBLIGATION)
    target_id: str
    configuration: Optional[Dict[str, Any]] = Field(default_factory=dict)
    next_evaluation_at: Optional[datetime] = None


class MonitoringWatchUpdate(BaseModel):
    status: Optional[WatchStatus] = None
    configuration: Optional[Dict[str, Any]] = None
    next_evaluation_at: Optional[datetime] = None


class MonitoringWatchResponse(BaseModel):
    id: str
    workspace_id: str
    watch_type: WatchType
    target_type: TargetType
    target_id: str
    status: WatchStatus
    configuration: Dict[str, Any]
    last_evaluated_at: Optional[datetime] = None
    next_evaluation_at: Optional[datetime] = None
    last_observed_state: Dict[str, Any]
    last_triggered_at: Optional[datetime] = None
    trigger_count: int
    cooldown_until: Optional[datetime] = None
    created_by: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class MonitoringWatchListResponse(BaseModel):
    items: List[MonitoringWatchResponse]
    total: int


# --- Monitoring Event Schemas ---

class MonitoringEventResponse(BaseModel):
    id: str
    workspace_id: str
    watch_id: Optional[str] = None
    event_type: MonitoringEventType
    severity: MonitoringSeverity
    target_type: TargetType
    target_id: str
    previous_state: Dict[str, Any]
    current_state: Dict[str, Any]
    detected_at: datetime
    explanation: str
    signals: Dict[str, Any]
    provenance: Dict[str, Any]
    deduplication_key: str
    acknowledged_at: Optional[datetime] = None
    acknowledged_by: Optional[str] = None
    resolved_at: Optional[datetime] = None
    resolution_reason: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class MonitoringEventListResponse(BaseModel):
    items: List[MonitoringEventResponse]
    total: int


# --- Escalation Candidate Schemas ---

class EscalationCandidateResponse(BaseModel):
    id: str
    workspace_id: str
    monitoring_event_id: Optional[str] = None
    target_type: TargetType
    target_id: str
    severity: MonitoringSeverity
    reason: str
    recommended_next_step: str
    affected_obligations: List[str]
    affected_owners: List[str]
    blast_radius: Dict[str, Any]
    decision_plan_id: Optional[str] = None
    status: EscalationStatus
    deduplication_key: str
    created_at: datetime
    acknowledged_at: Optional[datetime] = None
    acknowledged_by: Optional[str] = None
    resolved_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class EscalationCandidateListResponse(BaseModel):
    items: List[EscalationCandidateResponse]
    total: int


class EscalationAcknowledgeRequest(BaseModel):
    notes: Optional[str] = None


class EscalationResolveRequest(BaseModel):
    resolution_reason: Optional[str] = None


class EscalationDismissRequest(BaseModel):
    reason: Optional[str] = None


# --- Monitoring Run Schemas ---

class MonitoringRunRequest(BaseModel):
    watch_ids: Optional[List[str]] = None
    force_all: bool = False


class MonitoringRunResponse(BaseModel):
    id: str
    workspace_id: str
    started_at: datetime
    completed_at: Optional[datetime] = None
    watches_evaluated: int
    events_created: int
    escalations_created: int
    errors: List[Dict[str, Any]]
    status: MonitoringRunStatus

    model_config = ConfigDict(from_attributes=True)


class MonitoringRunListResponse(BaseModel):
    items: List[MonitoringRunResponse]
    total: int


# --- Monitoring Summary Schema ---

class MonitoringSummaryResponse(BaseModel):
    active_watches_count: int
    critical_events_count: int
    high_events_count: int
    open_escalations_count: int
    deadline_breaches_count: int
    risk_escalations_count: int
    execution_failures_count: int
    response_timeouts_count: int
    dependency_blocks_count: int
    stale_decision_plans_count: int
    recent_events: List[MonitoringEventResponse] = Field(default_factory=list)
    open_escalations: List[EscalationCandidateResponse] = Field(default_factory=list)
