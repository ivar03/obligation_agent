from datetime import datetime
from enum import Enum
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, ConfigDict
from app.core.status_machine import (
    ObligationStatus,
    ObligationType,
    EdgeType,
    EvidenceType,
    CorrelationStatus,
    EventSemanticRole,
    RiskLevel,
    ActionType,
    ReconciliationStatus,
    ReconciliationResolutionAction,
)
from app.core.confidence import AmbiguityDetail


class DeadlineType(str, Enum):
    EXPLICIT = "EXPLICIT"
    RELATIVE = "RELATIVE"
    CONDITIONAL = "CONDITIONAL"
    UNKNOWN = "UNKNOWN"


class MessageContext(BaseModel):
    message: Optional[str] = None
    sender: Optional[str] = None
    recipients: Optional[List[str]] = Field(default_factory=list)
    participants: Optional[List[str]] = Field(default_factory=list)
    previous_messages: Optional[List[Dict[str, Any]]] = Field(default_factory=list)
    reference_time: Optional[datetime] = None
    current_user: Optional[str] = "You"


class OwnershipResolution(BaseModel):
    owner: str
    beneficiary: str
    confidence: float = Field(..., ge=0.0, le=1.0)
    reasoning: str
    ambiguous: bool = False
    obligation_type: ObligationType
    suggested_assignees: List[str] = Field(default_factory=list)


class DeadlineResolution(BaseModel):
    deadline_type: DeadlineType
    resolved_deadline: Optional[datetime] = None
    condition_trigger: Optional[str] = None
    confidence: float = Field(..., ge=0.0, le=1.0)
    reasoning: str
    ambiguous: bool = False
    raw_expression: Optional[str] = None


class ResolutionResult(BaseModel):
    ownership: OwnershipResolution
    deadline: DeadlineResolution
    review_required: bool = False
    ambiguities: List[AmbiguityDetail] = Field(default_factory=list)
    confidence_summary: Dict[str, float] = Field(default_factory=dict)


class FieldConfidence(BaseModel):
    overall: float = Field(default=1.0, ge=0.0, le=1.0)
    owner: float = Field(default=1.0, ge=0.0, le=1.0)
    beneficiary: float = Field(default=1.0, ge=0.0, le=1.0)
    action: float = Field(default=1.0, ge=0.0, le=1.0)
    deadline: float = Field(default=1.0, ge=0.0, le=1.0)
    conditions: float = Field(default=1.0, ge=0.0, le=1.0)
    obligation_type: float = Field(default=1.0, ge=0.0, le=1.0)


class ObligationCandidate(BaseModel):
    owner: str
    beneficiary: str
    action: str
    deadline: Optional[datetime] = None
    conditions: Optional[Any] = None
    obligation_type: ObligationType
    next_action: Optional[str] = None
    source_ref: Optional[str] = None
    confidence: FieldConfidence = Field(default_factory=FieldConfidence)
    deadline_type: Optional[DeadlineType] = None
    resolution: Optional[ResolutionResult] = None


class ExtractionRequest(BaseModel):
    text: str = Field(..., min_length=1, description="Raw message or text to extract obligation from")
    context: Optional[MessageContext] = None
    reference_datetime: Optional[datetime] = None


class ExtractionResponse(BaseModel):
    detected: bool
    obligation: Optional[ObligationCandidate] = None
    reason: Optional[str] = None
    raw_text: Optional[str] = None


class BlockerDetail(BaseModel):
    obligation_id: str
    owner: str
    beneficiary: str
    action: str
    status: ObligationStatus
    reason: str


class BlockReason(BaseModel):
    blocked: bool = True
    blocked_by: List[BlockerDetail] = Field(default_factory=list)
    updated_at: Optional[datetime] = None


class ObligationCreate(BaseModel):
    owner: str = Field(..., min_length=1)
    beneficiary: str = Field(..., min_length=1)
    action: str = Field(..., min_length=1)
    deadline: Optional[datetime] = None
    conditions: Optional[Any] = None
    evidence: Optional[List[Dict[str, Any]]] = Field(default_factory=list)
    status: ObligationStatus = Field(default=ObligationStatus.CONFIRMED)
    next_action: Optional[str] = None
    source_ref: Optional[str] = None
    obligation_type: ObligationType
    confidence: Optional[Dict[str, Any]] = None


class ObligationUpdate(BaseModel):
    owner: Optional[str] = None
    beneficiary: Optional[str] = None
    action: Optional[str] = None
    deadline: Optional[datetime] = None
    conditions: Optional[Any] = None
    evidence: Optional[List[Dict[str, Any]]] = None
    next_action: Optional[str] = None
    source_ref: Optional[str] = None
    obligation_type: Optional[ObligationType] = None
    confidence: Optional[Dict[str, Any]] = None


class ObligationStatusUpdate(BaseModel):
    status: ObligationStatus
    reason: Optional[str] = None
    evidence: Optional[Dict[str, Any]] = None


class ObligationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    owner: str
    beneficiary: str
    action: str
    deadline: Optional[datetime] = None
    conditions: Optional[Any] = None
    evidence: Optional[List[Dict[str, Any]]] = None
    status: ObligationStatus
    next_action: Optional[str] = None
    block_reason: Optional[Any] = None
    source_ref: Optional[str] = None
    obligation_type: ObligationType
    confidence: Optional[Dict[str, Any]] = None
    created_at: datetime
    updated_at: datetime
    is_at_risk: bool = False
    risk_level: Optional[RiskLevel] = None
    risk_score: Optional[float] = None


class ObligationListResponse(BaseModel):
    items: List[ObligationResponse]
    total: int


class DashboardSummaryResponse(BaseModel):
    you_owe_count: int
    others_owe_count: int
    at_risk_count: int
    completed_count: int
    blocked_count: int = 0
    pending_evidence_count: int = 0
    you_owe_obligations: List[ObligationResponse]
    others_owe_obligations: List[ObligationResponse]
    at_risk_obligations: List[ObligationResponse]


class ObligationEdgeCreate(BaseModel):
    from_obligation_id: str
    to_obligation_id: str
    edge_type: EdgeType = Field(default=EdgeType.LINKED)


class ObligationEdgeResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    from_obligation_id: str
    to_obligation_id: str
    edge_type: EdgeType
    created_at: datetime


class ObligationGraphResponse(BaseModel):
    obligation: ObligationResponse
    dependencies: List[ObligationResponse] = Field(default_factory=list)
    dependents: List[ObligationResponse] = Field(default_factory=list)
    linked: List[ObligationResponse] = Field(default_factory=list)
    blockers: List[BlockerDetail] = Field(default_factory=list)
    is_blocked: bool = False
    unblocks_on_completion: List[ObligationResponse] = Field(default_factory=list)


# ==========================================
# PHASE 4: EVIDENCE & EVENT CORRELATION SCHEMAS
# ==========================================

class ExternalEvent(BaseModel):
    source_type: str = Field(default="message", description="Type of source: message, email, file, audit_log, system")
    source_ref: Optional[str] = Field(default=None, description="Unique reference ID from source system for deduplication")
    sender: Optional[str] = Field(default=None, description="Actor/sender name or ID")
    recipients: List[str] = Field(default_factory=list, description="Target recipient names or IDs")
    timestamp: Optional[datetime] = Field(default=None, description="Observed event timestamp")
    content: str = Field(..., min_length=1, description="Message text or observation snippet")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Arbitrary attachments or external context")


class CorrelationMatch(BaseModel):
    obligation_id: str
    owner: str
    beneficiary: str
    action: str
    status: ObligationStatus
    correlation_confidence: float = Field(..., ge=0.0, le=1.0)
    confidence_level: str  # HIGH, MEDIUM, LOW
    semantic_role: EventSemanticRole
    is_completion_candidate: bool
    matched_signals: List[str] = Field(default_factory=list)
    unmatched_signals: List[str] = Field(default_factory=list)
    reasoning: List[str] = Field(default_factory=list)
    review_required: bool = False


class EventAnalysisResponse(BaseModel):
    semantic_role: EventSemanticRole
    matches: List[CorrelationMatch] = Field(default_factory=list)
    best_match: Optional[CorrelationMatch] = None
    summary: str


class EvidenceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    obligation_id: str
    evidence_type: EvidenceType
    source_type: str
    source_ref: Optional[str] = None
    content: str
    correlation_status: CorrelationStatus
    correlation_confidence: float
    semantic_role: EventSemanticRole
    reasoning: Optional[Any] = None
    extra_metadata: Optional[Any] = None
    actor: Optional[str] = None
    observed_at: datetime
    created_at: datetime


class EvidenceListResponse(BaseModel):
    items: List[EvidenceResponse] = Field(default_factory=list)
    total: int


class EvidenceConfirmRequest(BaseModel):
    notes: Optional[str] = None


class EventIngestionResponse(BaseModel):
    ingested: bool
    semantic_role: EventSemanticRole
    evidence_records: List[EvidenceResponse] = Field(default_factory=list)
    matches: List[CorrelationMatch] = Field(default_factory=list)
    message: str


# ==========================================
# PHASE 7: CONTINUOUS EVENT INGESTION & PROVIDER SCHEMAS
# ==========================================

class ProviderInfo(BaseModel):
    name: str
    version: str
    capabilities: List[str] = Field(default_factory=list)
    is_connected: bool = True


class IngestRawEventRequest(BaseModel):
    provider: str = Field(default="mock", description="Registered provider name: mock, slack, webhook, etc.")
    payload: Dict[str, Any] = Field(..., description="Provider-specific raw event dictionary")


class EventSimulateRequest(BaseModel):
    scenario: str = Field(default="SCENARIO_A_COMPLETION", description="Scenario key: SCENARIO_A_COMPLETION, SCENARIO_B_PROGRESS, SCENARIO_C_BLOCKER, SCENARIO_D_REQUEST, SCENARIO_E_CHATTER")
    sender: Optional[str] = None
    recipients: Optional[List[str]] = None
    content: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


class IngestedEventResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    provider: str
    source_type: str
    source_ref: Optional[str] = None
    sender: Optional[str] = None
    recipients: Optional[List[str]] = Field(default_factory=list)
    content: str
    semantic_role: EventSemanticRole
    processing_status: str
    candidate_obligation_ids: Optional[List[str]] = Field(default_factory=list)
    correlated_obligation_id: Optional[str] = None
    evidence_id: Optional[str] = None
    correlation_confidence: Optional[float] = None
    match_explanation: Optional[str] = None
    action_taken: Optional[str] = None
    resolved_intervention_id: Optional[str] = None
    raw_payload: Optional[Dict[str, Any]] = None
    received_at: datetime
    created_at: datetime


class IngestedEventListResponse(BaseModel):
    items: List[IngestedEventResponse] = Field(default_factory=list)
    total: int


class IngestionResultResponse(BaseModel):
    status: str  # PROCESSED, DUPLICATE, REJECTED, NO_MATCH
    event_id: str
    provider: str
    semantic_role: EventSemanticRole
    matches: List[CorrelationMatch] = Field(default_factory=list)
    evidence_records: List[EvidenceResponse] = Field(default_factory=list)
    affected_obligation_ids: List[str] = Field(default_factory=list)
    updated_intervention_ids: List[str] = Field(default_factory=list)
    message: str


# ==========================================
# PHASE 5: PROACTIVE RISK & RECOMMENDATION SCHEMAS
# ==========================================

class RiskSignal(BaseModel):
    signal_type: str
    severity: str  # LOW, MEDIUM, HIGH, CRITICAL
    contribution: float = Field(..., ge=-1.0, le=1.0)
    explanation: str


class RiskBreakdown(BaseModel):
    deadline_pressure: float = 0.0
    dependency_risk: float = 0.0
    progress_risk: float = 0.0
    ownership_risk: float = 0.0
    evidence_risk: float = 0.0


class RiskAssessmentResponse(BaseModel):
    obligation_id: str
    owner: str
    beneficiary: str
    action: str
    status: ObligationStatus
    obligation_type: ObligationType
    deadline: Optional[datetime] = None
    risk_score: float = Field(..., ge=0.0, le=1.0)
    risk_level: RiskLevel
    is_at_risk: bool
    priority_score: float
    dependent_count: int = 0
    reasons: List[str] = Field(default_factory=list)
    signals: List[RiskSignal] = Field(default_factory=list)
    breakdown: RiskBreakdown = Field(default_factory=RiskBreakdown)
    recommended_action: str
    action_type: ActionType
    assessed_at: datetime


class BulkRiskResponse(BaseModel):
    total_at_risk: int
    critical_count: int
    high_count: int
    medium_count: int
    low_count: int
    items: List[RiskAssessmentResponse] = Field(default_factory=list)


# ==========================================
# PHASE 11: CROSS-PROVIDER RECONCILIATION SCHEMAS
# ==========================================

class EvidenceProvenanceDetail(BaseModel):
    evidence_id: str
    source_type: str
    source_ref: Optional[str] = None
    provider: str
    actor: Optional[str] = None
    recipients: Optional[List[str]] = Field(default_factory=list)
    semantic_role: EventSemanticRole
    correlation_confidence: float
    content: str
    observed_at: datetime
    is_supporting: bool = True
    is_conflicting: bool = False
    reasoning: Optional[Any] = None


class ReconciliationRecordResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    obligation_id: str
    status: ReconciliationStatus
    confidence: float
    consistency_score: float
    contradiction_score: float
    supporting_evidence_ids: List[str] = Field(default_factory=list)
    conflicting_evidence_ids: List[str] = Field(default_factory=list)
    supporting_event_ids: List[str] = Field(default_factory=list)
    conflicting_event_ids: List[str] = Field(default_factory=list)
    explanation: List[str] = Field(default_factory=list)
    recommended_action: Optional[str] = None
    resolution: Optional[Dict[str, Any]] = None
    resolved_by: Optional[str] = None
    resolved_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    # Optional enriched context for detailed view
    evidence_timeline: Optional[List[EvidenceProvenanceDetail]] = Field(default_factory=list)
    obligation_action: Optional[str] = None
    obligation_owner: Optional[str] = None
    obligation_beneficiary: Optional[str] = None
    obligation_status: Optional[ObligationStatus] = None


class ReconciliationListResponse(BaseModel):
    items: List[ReconciliationRecordResponse] = Field(default_factory=list)
    total: int
    conflicting_count: int = 0
    consistent_count: int = 0
    ambiguous_count: int = 0
    resolved_count: int = 0


class ReconciliationResolutionRequest(BaseModel):
    action: ReconciliationResolutionAction = Field(..., description="Operator decision: CONFIRM_COMPLETION, CONFIRM_NOT_COMPLETED, DISMISS_CONTRADICTION, MARK_AS_STALE, KEEP_OBLIGATION_ACTIVE, REOPEN_OBLIGATION")
    notes: Optional[str] = Field(None, description="Human operator justification notes")
    operator: Optional[str] = Field("Operator", description="Identity of the operator making the decision")
    selected_evidence_id: Optional[str] = Field(None, description="Specific evidence ID used to confirm completion if applicable")


class ReconciliationDismissRequest(BaseModel):
    reason: Optional[str] = Field("Dismissed by operator", description="Reason for dismissing the contradiction")
    operator: Optional[str] = Field("Operator", description="Identity of the operator")

