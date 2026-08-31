"""
Phase 20 LLM & Natural-Language Intelligence Layer Schemas.

Defines strict Pydantic structured output contracts, validation models,
grounding context packets, reconciliation models, and API schemas.
"""

from enum import Enum
from typing import Optional, List, Dict, Any, Union
from datetime import datetime, timezone
from pydantic import BaseModel, Field, field_validator


class LLMAnalysisType(str, Enum):
    OBLIGATION_EXTRACTION = "OBLIGATION_EXTRACTION"
    EVENT_SEMANTICS = "EVENT_SEMANTICS"
    EVIDENCE_INTERPRETATION = "EVIDENCE_INTERPRETATION"
    GROUNDED_EXPLANATION = "GROUNDED_EXPLANATION"
    DECISION_EXPLANATION = "DECISION_EXPLANATION"
    HYBRID_RECONCILIATION = "HYBRID_RECONCILIATION"


class LLMValidationStatus(str, Enum):
    VALID = "VALID"
    INVALID_SCHEMA = "INVALID_SCHEMA"
    CONFIDENCE_OUT_OF_BOUNDS = "CONFIDENCE_OUT_OF_BOUNDS"
    UNKNOWN_ENTITY = "UNKNOWN_ENTITY"
    FABRICATED_DEPENDENCY = "FABRICATED_DEPENDENCY"
    GROUNDING_FAILED = "GROUNDING_FAILED"
    SECURITY_REJECTED = "SECURITY_REJECTED"
    FALLBACK_APPLIED = "FALLBACK_APPLIED"


class GroundingCheckStatus(str, Enum):
    GROUNDED = "GROUNDED"
    UNGROUNDED_CLAIM = "UNGROUNDED_CLAIM"
    FABRICATED_ENTITY = "FABRICATED_ENTITY"
    FABRICATED_DATE = "FABRICATED_DATE"
    SECRET_DETECTED = "SECRET_DETECTED"
    GROUNDING_FAILED = "GROUNDING_FAILED"


class LLMProviderInfo(BaseModel):
    provider_name: str
    provider_version: str
    model: str
    capabilities: List[str] = Field(default_factory=list)
    healthy: bool = True


# -----------------------------------------------------------------------------
# Structured Proposals
# -----------------------------------------------------------------------------

class ObligationProposal(BaseModel):
    """Structured proposal for an extracted obligation."""
    schema_version: str = "obligation-proposal-v1"
    action: str = Field(..., description="Actionable statement of the obligation or commitment")
    owner: Optional[str] = Field(None, description="Inferred duty bearer (None if ambiguous)")
    beneficiary: Optional[str] = Field(None, description="Party to whom obligation is owed")
    deadline: Optional[str] = Field(None, description="ISO-8601 or natural language deadline expression")
    obligation_type: str = Field("OWED_TO_ME", description="OWED_TO_ME, OWED_BY_ME, or MUTUAL")
    conditions: Optional[str] = Field(None, description="Prerequisite conditions or triggers")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Overall confidence score bounded between 0.0 and 1.0")
    uncertainties: List[str] = Field(default_factory=list, description="Explicit ambiguities or missing information")
    reasoning: str = Field("", description="Concise explanation of the LLM's interpretation")
    source_reference: Optional[str] = Field(None, description="Message ID or source reference")
    provider: str = Field("mock", description="LLM provider name")
    provider_version: str = Field("1.0", description="LLM provider/model version")
    prompt_version: str = Field("v1", description="Prompt template version used")

    @field_validator("confidence")
    @classmethod
    def validate_confidence(cls, v: float) -> float:
        if not (0.0 <= v <= 1.0):
            raise ValueError("Confidence must be strictly bounded between 0.0 and 1.0")
        return round(v, 4)


class EventSemanticProposal(BaseModel):
    """Structured proposal for an external event's semantic role."""
    schema_version: str = "event-semantic-proposal-v1"
    semantic_role: str = Field(
        ...,
        description="COMPLETION_SIGNAL, COMMITMENT, REQUEST, PROGRESS_UPDATE, NEGATIVE_BLOCKER, or IRRELEVANT"
    )
    confidence: float = Field(..., ge=0.0, le=1.0)
    summary: str = Field(..., description="Short semantic summary")
    actor: Optional[str] = Field(None, description="Actor initiating the action")
    recipient: Optional[str] = Field(None, description="Target recipient of deliverable")
    deliverable: Optional[str] = Field(None, description="Deliverable or artifact referenced")
    evidence_strength: float = Field(0.5, ge=0.0, le=1.0, description="Strength as potential evidence")
    contradictions: List[str] = Field(default_factory=list, description="Any detected contradictions or caveats")
    reasoning: str = Field("")
    provider: str = "mock"
    prompt_version: str = "v1"


class EvidenceInterpretationProposal(BaseModel):
    """Structured proposal evaluating evidence match against an obligation."""
    schema_version: str = "evidence-interpretation-v1"
    evidence_category: str = Field(..., description="COMPLETION, PROGRESS, REQUEST, COMMITMENT, NEGATIVE_BLOCKER, AMBIGUOUS")
    confidence: float = Field(..., ge=0.0, le=1.0)
    extracted_action: str = Field("")
    deliverable_mentioned: Optional[str] = None
    actor: Optional[str] = None
    recipient: Optional[str] = None
    temporal_clues: Optional[str] = None
    evidence_strength: float = Field(0.5, ge=0.0, le=1.0)
    contradictions: List[str] = Field(default_factory=list)
    reasoning: str = Field("")
    provider: str = "mock"
    prompt_version: str = "v1"


class GroundedExplanationProposal(BaseModel):
    """Structured natural-language explanation strictly grounded in supplied facts."""
    schema_version: str = "grounded-explanation-v1"
    explanation: str = Field(..., description="Human-readable explanation")
    grounded_facts_used: List[str] = Field(default_factory=list, description="List of fact identifiers referenced")
    confidence: float = Field(0.9, ge=0.0, le=1.0)
    uncertainties: List[str] = Field(default_factory=list)
    reasoning: str = Field("")
    grounding_status: GroundingCheckStatus = GroundingCheckStatus.GROUNDED
    grounding_notes: Optional[str] = None
    provider: str = "mock"
    prompt_version: str = "v1"


# -----------------------------------------------------------------------------
# Reconciliation Model (Hybrid Deterministic + LLM)
# -----------------------------------------------------------------------------

class ExtractionReconciliation(BaseModel):
    """Reconciled output combining deterministic heuristics and LLM proposal."""
    deterministic_detected: bool
    deterministic_candidate: Optional[Dict[str, Any]] = None
    llm_proposal: Optional[ObligationProposal] = None
    agreement_fields: List[str] = Field(default_factory=list)
    disagreement_fields: List[str] = Field(default_factory=list)
    final_action: str
    final_owner: Optional[str] = None
    final_beneficiary: Optional[str] = None
    final_deadline: Optional[str] = None
    final_obligation_type: str = "OWED_TO_ME"
    final_conditions: Optional[str] = None
    confidence: float = Field(..., ge=0.0, le=1.0)
    human_review_required: bool = False
    reconciliation_strategy: str = Field(..., description="AGREEMENT_BOOST, DISAGREEMENT_GATED, LLM_SUPPLEMENTED, DETERMINISTIC_FALLBACK")
    reconciliation_reason: str = ""


# -----------------------------------------------------------------------------
# Grounded Context Packet
# -----------------------------------------------------------------------------

class GroundedContextPacket(BaseModel):
    """Strict verified facts packet passed to LLM for grounded generation."""
    workspace_id: str
    target_entity_id: str
    generated_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    known_users: List[str] = Field(default_factory=list)
    known_obligation_ids: List[str] = Field(default_factory=list)
    obligations: List[Dict[str, Any]] = Field(default_factory=list)
    dependencies: List[Dict[str, Any]] = Field(default_factory=list)
    evidence_records: List[Dict[str, Any]] = Field(default_factory=list)
    risk_signals: List[Dict[str, Any]] = Field(default_factory=list)
    decision_plans: List[Dict[str, Any]] = Field(default_factory=list)
    verified_deadlines: List[str] = Field(default_factory=list)


# -----------------------------------------------------------------------------
# API Request / Response Models
# -----------------------------------------------------------------------------

class LLMAnalyzeRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=10000)
    source_ref: Optional[str] = None
    sender: Optional[str] = None
    channel: Optional[str] = None
    workspace_id: str = "ws-default"
    provider: Optional[str] = None  # None for default active provider


class LLMAnalyzeResponse(BaseModel):
    success: bool
    proposal: Optional[ObligationProposal] = None
    validation_status: LLMValidationStatus
    validation_errors: List[str] = Field(default_factory=list)
    reconciliation: Optional[ExtractionReconciliation] = None
    analysis_record_id: Optional[str] = None
    fallback_used: bool = False
    latency_ms: float = 0.0


class LLMExplainRequest(BaseModel):
    target_entity_id: str
    prompt_instruction: Optional[str] = "Explain the root-cause and critical-path impact"
    workspace_id: str = "ws-default"
    provider: Optional[str] = None


class LLMExplainResponse(BaseModel):
    success: bool
    explanation: str
    grounding_status: GroundingCheckStatus
    grounding_errors: List[str] = Field(default_factory=list)
    grounded_facts_used: List[str] = Field(default_factory=list)
    confidence: float
    analysis_record_id: Optional[str] = None
    fallback_used: bool = False
    latency_ms: float = 0.0


class LLMReviewActionRequest(BaseModel):
    action: str = Field(..., description="'accept', 'reject', 'edit'")
    edited_proposal: Optional[ObligationProposal] = None
    reviewer_notes: Optional[str] = None
