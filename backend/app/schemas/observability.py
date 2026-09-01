"""
Phase 21 Operational Observability & Audit Schemas.

Defines the Operational Event Taxonomy, Trace Graph Schemas,
Audit Integrity Schemas, Alert Lifecycle Schemas, and SLO/Error-Budget Models.
"""

from enum import Enum
from typing import Optional, List, Dict, Any
from datetime import datetime, timezone
from pydantic import BaseModel, Field


class OperationalSeverity(str, Enum):
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class AlertStatus(str, Enum):
    OPEN = "OPEN"
    ACKNOWLEDGED = "ACKNOWLEDGED"
    RESOLVED = "RESOLVED"
    SUPPRESSED = "SUPPRESSED"


class SLOStatus(str, Enum):
    HEALTHY = "HEALTHY"
    WARNING = "WARNING"
    BREACHED = "BREACHED"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"


class OperationalEventType(str, Enum):
    # Security / Auth
    AUTHENTICATION_FAILURE = "AUTHENTICATION_FAILURE"
    AUTHORIZATION_DENIED = "AUTHORIZATION_DENIED"
    RATE_LIMIT_TRIGGERED = "RATE_LIMIT_TRIGGERED"
    USER_LOGIN = "USER_LOGIN"

    # Webhook / Ingestion
    WEBHOOK_ACCEPTED = "WEBHOOK_ACCEPTED"
    WEBHOOK_REJECTED = "WEBHOOK_REJECTED"
    WEBHOOK_SIGNATURE_FAILURE = "WEBHOOK_SIGNATURE_FAILURE"

    # Queue / Workers
    EVENT_QUEUED = "EVENT_QUEUED"
    EVENT_PROCESSING = "EVENT_PROCESSING"
    EVENT_PROCESSED = "EVENT_PROCESSED"
    EVENT_RETRY = "EVENT_RETRY"
    EVENT_DEAD_LETTER = "EVENT_DEAD_LETTER"
    WORKER_STARTED = "WORKER_STARTED"
    WORKER_STOPPED = "WORKER_STOPPED"
    WORKER_CRASH_RECOVERY = "WORKER_CRASH_RECOVERY"

    # Providers & Circuit Breakers
    PROVIDER_CONNECTED = "PROVIDER_CONNECTED"
    PROVIDER_DEGRADED = "PROVIDER_DEGRADED"
    PROVIDER_RATE_LIMITED = "PROVIDER_RATE_LIMITED"
    PROVIDER_AUTH_FAILED = "PROVIDER_AUTH_FAILED"
    PROVIDER_UNAVAILABLE = "PROVIDER_UNAVAILABLE"
    CIRCUIT_OPENED = "CIRCUIT_OPENED"
    CIRCUIT_HALF_OPEN = "CIRCUIT_HALF_OPEN"
    CIRCUIT_CLOSED = "CIRCUIT_CLOSED"

    # LLM Intelligence
    LLM_REQUEST = "LLM_REQUEST"
    LLM_FAILURE = "LLM_FAILURE"
    LLM_TIMEOUT = "LLM_TIMEOUT"
    LLM_VALIDATION_FAILURE = "LLM_VALIDATION_FAILURE"
    LLM_GROUNDING_FAILURE = "LLM_GROUNDING_FAILURE"
    LLM_FALLBACK = "LLM_FALLBACK"

    # Decision & Interventions
    DECISION_GENERATED = "DECISION_GENERATED"
    DECISION_APPROVED = "DECISION_APPROVED"
    DECISION_REJECTED = "DECISION_REJECTED"
    DECISION_SUPERSEDED = "DECISION_SUPERSEDED"

    # Execution Engine
    EXECUTION_AUTHORIZED = "EXECUTION_AUTHORIZED"
    EXECUTION_STARTED = "EXECUTION_STARTED"
    EXECUTION_DELIVERED = "EXECUTION_DELIVERED"
    EXECUTION_FAILED = "EXECUTION_FAILED"
    EXECUTION_RETRIED = "EXECUTION_RETRIED"

    # Backups & Admin
    BACKUP_CREATED = "BACKUP_CREATED"
    BACKUP_FAILED = "BACKUP_FAILED"
    RESTORE_EXECUTED = "RESTORE_EXECUTED"
    CONFIGURATION_CHANGED = "CONFIGURATION_CHANGED"
    ADMIN_ACTION = "ADMIN_ACTION"


# -----------------------------------------------------------------------------
# Operational Audit Schemas
# -----------------------------------------------------------------------------

class OperationalAuditRecordSchema(BaseModel):
    id: str
    workspace_id: str
    timestamp: str
    event_type: str
    severity: str
    actor_type: str = "SYSTEM"  # "USER", "SYSTEM", "OPERATOR", "PROVIDER"
    actor_id: Optional[str] = None
    request_id: Optional[str] = None
    trace_id: Optional[str] = None
    span_id: Optional[str] = None
    resource_type: Optional[str] = None
    resource_id: Optional[str] = None
    provider: Optional[str] = None
    action: str
    result: str = "SUCCESS"  # "SUCCESS", "FAILURE", "ATTEMPT", "REJECTED"
    error_code: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
    previous_hash: Optional[str] = None
    record_hash: str


class AuditIntegrityResult(BaseModel):
    workspace_id: str
    verified: bool
    total_records: int
    intact_records: int
    corrupted_records: int
    tampered_record_ids: List[str] = Field(default_factory=list)
    verification_duration_ms: float
    verified_at: str


class AuditStatsResponse(BaseModel):
    workspace_id: str
    total_audit_records: int
    by_severity: Dict[str, int]
    by_event_type: Dict[str, int]
    by_result: Dict[str, int]
    last_event_time: Optional[str] = None


# -----------------------------------------------------------------------------
# Trace Reconstruction Schemas
# -----------------------------------------------------------------------------

class TraceNode(BaseModel):
    node_id: str
    span_id: Optional[str] = None
    parent_span_id: Optional[str] = None
    component: str  # "WEBHOOK", "INBOX", "WORKER", "LLM", "OBLIGATION", "DECISION", "EXECUTION", "AUDIT"
    step_name: str
    status: str  # "SUCCESS", "FAILURE", "QUEUED", "PROCESSING", "RETRY", "DEAD_LETTER"
    timestamp: str
    duration_ms: Optional[float] = None
    resource_id: Optional[str] = None
    error_message: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class TraceWorkflowGraph(BaseModel):
    trace_id: str
    workspace_id: str
    root_event_type: Optional[str] = None
    start_time: str
    end_time: Optional[str] = None
    total_duration_ms: Optional[float] = None
    node_count: int
    nodes: List[TraceNode]
    is_complete: bool
    has_errors: bool
    related_obligation_ids: List[str] = Field(default_factory=list)
    related_decision_ids: List[str] = Field(default_factory=list)


# -----------------------------------------------------------------------------
# Alerting Schemas
# -----------------------------------------------------------------------------

class OperationalAlertSchema(BaseModel):
    id: str
    workspace_id: str
    alert_name: str
    alert_type: str
    severity: str
    status: AlertStatus
    summary: str
    details: Dict[str, Any] = Field(default_factory=dict)
    fingerprint: str
    trace_id: Optional[str] = None
    acknowledged_by: Optional[str] = None
    acknowledged_at: Optional[str] = None
    resolved_at: Optional[str] = None
    created_at: str
    updated_at: str


class AlertActionRequest(BaseModel):
    action: str = Field(..., description="'acknowledge', 'resolve', 'suppress'")
    actor_id: str = "operator"
    notes: Optional[str] = None


# -----------------------------------------------------------------------------
# SLO & Error-Budget Schemas
# -----------------------------------------------------------------------------

class SLIReport(BaseModel):
    name: str
    category: str  # "API", "EVENT_PROCESSING", "EXECUTION", "LLM"
    target_percentage: float
    actual_percentage: Optional[float] = None
    status: SLOStatus
    sample_count: int
    details: Dict[str, Any] = Field(default_factory=dict)


class ErrorBudgetReport(BaseModel):
    slo_name: str
    total_budget_percentage: float
    consumed_percentage: Optional[float] = None
    remaining_percentage: Optional[float] = None
    status: SLOStatus
    status_reason: str


class OperationsDashboardMetrics(BaseModel):
    workspace_id: str
    timestamp: str
    api_health: str
    database_backend: str
    worker_status: str
    total_queued_events: int
    dead_letter_depth: int
    open_alerts_count: int
    active_circuit_breakers_open: int
    throughput_rpm: Dict[str, float]
    latency_percentiles: Dict[str, Dict[str, Optional[float]]]
    error_rates: Dict[str, float]
    slos: List[SLIReport]
    error_budgets: List[ErrorBudgetReport]
    provider_health_summary: Dict[str, str]
