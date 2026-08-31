"""
Pydantic Schemas for Phase 15 Decision Layer.
"""

from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
from app.core.status_machine import DecisionPlanStatus, HumanDecisionType, ProvenanceSourceType


class ProvenanceReferenceItem(BaseModel):
    source_type: ProvenanceSourceType | str
    reference_id: str
    description: str
    confidence: float = 1.0


class HumanDecisionRequirement(BaseModel):
    decision_type: HumanDecisionType | str
    reason: str
    affected_obligation_id: str
    affected_obligation_action: Optional[str] = None
    consequence_of_decision: str
    supporting_evidence: List[str] = Field(default_factory=list)
    confidence: float = 1.0
    proposed_default: Optional[str] = None
    requires_admin: bool = False


class CandidateStrategyItem(BaseModel):
    strategy_id: str
    strategy_name: str
    strategy_type: str
    target_obligation_id: str
    target_owner: str
    target_action: str
    rationale: str
    decision_score: float = Field(ge=0.0, le=1.0)
    expected_impact: str
    risk_reduction: float = 0.0
    projected_unblocks_count: int = 0
    simulated_evaluation: Dict[str, Any] = Field(default_factory=dict)
    human_decisions: List[HumanDecisionRequirement] = Field(default_factory=list)
    is_primary_recommendation: bool = False
    score_breakdown: Dict[str, float] = Field(default_factory=dict)


class DecisionPlanResponse(BaseModel):
    id: str
    workspace_id: str
    target_obligation_id: str
    target_obligation_action: Optional[str] = None
    target_obligation_owner: Optional[str] = None
    target_obligation_status: Optional[str] = None
    generated_at: datetime
    plan_version: int = 1
    status: DecisionPlanStatus | str
    overall_urgency: str = "MEDIUM"
    overall_risk: float = 0.0
    decision_confidence: float = 1.0
    primary_objective: str
    root_cause_obligation_id: Optional[str] = None
    root_cause_summary: Optional[str] = None
    critical_path: List[Dict[str, Any]] = Field(default_factory=list)
    impact_summary: Dict[str, Any] = Field(default_factory=dict)
    key_risks: List[str] = Field(default_factory=list)
    supporting_evidence: List[Dict[str, Any]] = Field(default_factory=list)
    recommended_actions: Dict[str, Any] = Field(default_factory=dict)
    alternative_actions: List[Dict[str, Any]] = Field(default_factory=list)
    human_decisions_required: List[HumanDecisionRequirement] = Field(default_factory=list)
    assumptions: List[str] = Field(default_factory=list)
    uncertainties: List[str] = Field(default_factory=list)
    simulation_summary: Dict[str, Any] = Field(default_factory=dict)
    created_from_snapshot_ids: List[str] = Field(default_factory=list)
    created_from_event_ids: List[str] = Field(default_factory=list)
    explainability_narrative: str = ""
    approved_at: Optional[datetime] = None
    approved_by_user_id: Optional[str] = None
    rejected_at: Optional[datetime] = None
    rejected_by_user_id: Optional[str] = None
    superseded_at: Optional[datetime] = None
    superseded_by_plan_id: Optional[str] = None
    resolution_notes: Optional[str] = None
    is_stale: bool = False


class DecisionPlanSummaryResponse(BaseModel):
    id: str
    workspace_id: str
    target_obligation_id: str
    target_obligation_action: str
    target_obligation_owner: str
    target_obligation_status: str
    plan_version: int
    status: DecisionPlanStatus | str
    overall_urgency: str
    overall_risk: float
    decision_confidence: float
    primary_objective: str
    recommended_strategy_name: str
    target_owner: str
    human_decisions_count: int
    is_stale: bool
    generated_at: datetime


class DecisionPlanListResponse(BaseModel):
    items: List[DecisionPlanSummaryResponse]
    total: int


class DecisionPlanApproveRequest(BaseModel):
    selected_strategy_id: Optional[str] = None
    notes: Optional[str] = None


class DecisionPlanRejectRequest(BaseModel):
    reason: str


class DecisionPlanSimulateRequest(BaseModel):
    strategy_id: Optional[str] = None
    custom_action: Optional[str] = None
    custom_parameters: Optional[Dict[str, Any]] = None
