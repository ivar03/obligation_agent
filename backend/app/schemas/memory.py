"""
Pydantic Schemas for Organizational Memory and Historical Reasoning in Phase 16.
"""

from typing import List, Dict, Any, Optional
from datetime import datetime
from pydantic import BaseModel, Field
from app.core.status_machine import (
    MemoryType,
    PatternType,
    PatternMaturity,
    RecurrenceInterval,
)


class SemanticRepresentationResponse(BaseModel):
    action: Optional[str] = None
    deliverable: Optional[str] = None
    entities: List[str] = Field(default_factory=list)
    topics: List[str] = Field(default_factory=list)
    obligation_type: Optional[str] = None
    deadline_characteristic: Optional[str] = None
    blocker_terms: List[str] = Field(default_factory=list)
    dependency_terms: List[str] = Field(default_factory=list)


class OrganizationalMemoryCreate(BaseModel):
    memory_type: MemoryType
    source_type: str = "obligation"
    source_ref: Optional[str] = None
    obligation_id: Optional[str] = None
    event_id: Optional[str] = None
    owner_id: Optional[str] = None
    content: str
    semantic_summary: str
    semantic_labels: List[str] = Field(default_factory=list)
    entities: List[str] = Field(default_factory=list)
    topics: List[str] = Field(default_factory=list)
    outcome: Optional[str] = None
    observed_at: Optional[datetime] = None
    metadata_json: Dict[str, Any] = Field(default_factory=dict)
    importance_score: float = 0.5
    confidence: float = 1.0


class OrganizationalMemoryResponse(BaseModel):
    id: str
    workspace_id: str
    memory_type: MemoryType
    source_type: str
    source_ref: Optional[str] = None
    obligation_id: Optional[str] = None
    event_id: Optional[str] = None
    owner_id: Optional[str] = None
    content: str
    semantic_summary: str
    semantic_labels: List[str] = Field(default_factory=list)
    entities: List[str] = Field(default_factory=list)
    topics: List[str] = Field(default_factory=list)
    outcome: Optional[str] = None
    observed_at: datetime
    created_at: datetime
    metadata_json: Dict[str, Any] = Field(default_factory=dict)
    importance_score: float = 0.5
    confidence: float = 1.0
    is_active: bool = True

    class Config:
        from_attributes = True


class MemoryRetrievalItem(BaseModel):
    memory: OrganizationalMemoryResponse
    relevance_score: float
    match_reasons: List[str]
    similarity_breakdown: Dict[str, float] = Field(default_factory=dict)


class HistoricalPatternItem(BaseModel):
    pattern_type: PatternType
    maturity: PatternMaturity
    observation_count: int
    confidence: float
    supporting_memory_ids: List[str] = Field(default_factory=list)
    first_observed_at: Optional[datetime] = None
    last_observed_at: Optional[datetime] = None
    description: str
    neutral_metrics: Dict[str, Any] = Field(default_factory=dict)


class HistoricalOwnerAnalyticsResponse(BaseModel):
    owner_id: str
    total_commitments_observed: int
    has_sufficient_history: bool
    completion_rate: float
    on_time_completion_rate: float
    median_delay_hours: float
    late_completion_frequency: float
    evidence_confirmation_rate: float
    intervention_response_rate: float
    recurring_blockers_count: int
    neutral_summary: str
    evaluated_at: datetime


class RecurringObligationItem(BaseModel):
    recurrence_type: RecurrenceInterval
    estimated_interval_days: float
    observation_count: int
    confidence: float
    last_occurrence: Optional[datetime] = None
    next_expected_window: Optional[str] = None
    description: str


class MemoryContextResponse(BaseModel):
    obligation_id: str
    context_status: str
    semantic_representation: SemanticRepresentationResponse
    similar_obligations: List[MemoryRetrievalItem] = Field(default_factory=list)
    historical_patterns: List[HistoricalPatternItem] = Field(default_factory=list)
    recurring_blockers: List[HistoricalPatternItem] = Field(default_factory=list)
    intervention_history: List[MemoryRetrievalItem] = Field(default_factory=list)
    owner_analytics: Optional[HistoricalOwnerAnalyticsResponse] = None
    recurring_commitment: Optional[RecurringObligationItem] = None
    confidence: float
    explanation: str
    evaluated_at: datetime


class MemoryListResponse(BaseModel):
    items: List[OrganizationalMemoryResponse]
    total: int


class MemorySearchRequest(BaseModel):
    query: Optional[str] = None
    memory_type: Optional[MemoryType] = None
    owner_id: Optional[str] = None
    obligation_id: Optional[str] = None
    min_relevance: float = 0.3
    limit: int = 50
    offset: int = 0
