"""
Pydantic Schemas for Enterprise Audit, Governance & Compliance.
"""

from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, ConfigDict, Field


class AuditEventResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    workspace_id: str
    actor_user_id: Optional[str] = None
    actor_name: Optional[str] = None
    actor_email: Optional[str] = None
    actor_role: Optional[str] = None
    action: str
    entity_type: Optional[str] = None
    entity_id: Optional[str] = None
    timestamp: datetime
    request_id: Optional[str] = None
    source: str = "API"
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    before_state: Optional[Dict[str, Any]] = None
    after_state: Optional[Dict[str, Any]] = None
    audit_metadata: Optional[Dict[str, Any]] = None
    reason: Optional[str] = None
    severity: str = "INFO"
    result: str = "SUCCESS"
    previous_event_hash: Optional[str] = None
    event_hash: str


class AuditListResponse(BaseModel):
    items: List[AuditEventResponse] = Field(default_factory=list)
    total: int
    limit: int
    offset: int


class AuditVerificationResponse(BaseModel):
    workspace_id: str
    chain_valid: bool
    status: str
    verified_event_count: int
    broken_at_event_id: Optional[str] = None
    expected_hash: Optional[str] = None
    actual_hash: Optional[str] = None
    verified_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    message: str


class TopActorMetric(BaseModel):
    actor_user_id: Optional[str] = None
    actor_name: str
    actor_email: Optional[str] = None
    mutation_count: int


class EntityTypeMetric(BaseModel):
    entity_type: str
    mutation_count: int


class GovernanceSummaryResponse(BaseModel):
    workspace_id: str
    total_audit_events: int
    events_today: int
    mutations_today: int
    security_events_count: int
    permission_denials_count: int
    failed_logins_count: int
    human_actions_count: int
    system_events_count: int
    interventions_approved_count: int
    interventions_executed_count: int
    evidence_confirmations_count: int
    reconciliation_decisions_count: int
    top_actors: List[TopActorMetric] = Field(default_factory=list)
    most_modified_entities: List[EntityTypeMetric] = Field(default_factory=list)
    recent_security_events: List[AuditEventResponse] = Field(default_factory=list)
    chain_integrity_status: str = "VALID"
    evaluated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class AuditExportResponse(BaseModel):
    workspace_id: str
    format: str
    total_records: int
    exported_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    records: List[Dict[str, Any]] = Field(default_factory=list)
