from datetime import datetime, timezone
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field, ConfigDict

from app.core.status_machine import (
    ObligationStatus,
    ObligationType,
    ActionType,
    ObligationOutcomeType,
    PredictiveActionType,
    RiskLevel,
)


class PredictionReasonItem(BaseModel):
    signal: str
    impact: float
    explanation: str


class DerivedProvenanceInfo(BaseModel):
    current_risk_evaluated: bool = True
    historical_outcomes_count: int = 0
    similar_obligations_count: int = 0
    dependency_history_count: int = 0
    intervention_history_count: int = 0


class ObligationPredictionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True, protected_namespaces=())

    obligation_id: str
    action: Optional[str] = None
    owner: Optional[str] = None
    beneficiary: Optional[str] = None
    status: Optional[ObligationStatus] = None
    deadline: Optional[datetime] = None
    model_version: str = "predictive-v1"
    failure_probability: float
    completion_probability: float
    expected_delay_hours: float
    intervention_likelihood: float
    blockage_likelihood: float
    confidence: float
    reasons: List[PredictionReasonItem] = Field(default_factory=list)
    preventative_recommendation: Optional[str] = None
    recommended_action_type: Optional[ActionType] = None
    derived_from: DerivedProvenanceInfo = Field(default_factory=DerivedProvenanceInfo)
    current_risk_score: Optional[float] = None
    current_risk_level: Optional[RiskLevel] = None
    predicted_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class SimilarObligationItem(BaseModel):
    obligation_id: str
    action: str
    owner: str
    beneficiary: str
    status: str
    outcome_type: str
    delay_hours: float
    similarity_score: float
    shared_features: List[str] = Field(default_factory=list)
    completed_at: Optional[datetime] = None


class SimilarObligationsResponse(BaseModel):
    obligation_id: str
    items: List[SimilarObligationItem] = Field(default_factory=list)
    total_similar_count: int = 0
    historical_summary: str = ""


class OwnerPatternMetric(BaseModel):
    owner: str
    total_obligations: int
    completed_count: int
    on_time_count: int
    late_count: int
    overdue_count: int
    blocked_count: int
    on_time_rate: float
    late_rate: float
    avg_delay_hours: float
    median_delay_hours: float
    intervention_response_rate: float
    blocker_frequency: float
    insights: List[str] = Field(default_factory=list)


class HistoricalPatternsResponse(BaseModel):
    total_historical_snapshots: int
    completion_rate: float
    on_time_completion_rate: float
    avg_delay_hours: float
    median_delay_hours: float
    dependency_bottleneck_rate: float
    intervention_success_rate: float
    frequent_blockers: List[Dict[str, Any]] = Field(default_factory=list)
    delay_distribution: Dict[str, int] = Field(default_factory=dict)
    owner_metrics: List[OwnerPatternMetric] = Field(default_factory=list)


class PredictionEvaluationMetrics(BaseModel):
    total_predictions_evaluated: int = 0
    status: str = "INSUFFICIENT_HISTORY"  # "EVALUATED" | "INSUFFICIENT_HISTORY"
    mean_absolute_error_hours: Optional[float] = None
    brier_score: Optional[float] = None
    calibration_error: Optional[float] = None
    high_risk_precision: Optional[float] = None
    overdue_recall: Optional[float] = None
    accuracy: Optional[float] = None
    evaluated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    message: str = "Not enough historical outcomes to evaluate prediction quality."


class IntelligenceOverviewResponse(BaseModel):
    model_config = ConfigDict(protected_namespaces=())

    active_obligations_evaluated: int
    high_predicted_failure_count: int
    likely_to_miss_deadline_count: int
    likely_to_require_intervention_count: int
    high_blockage_risk_count: int
    predictions: List[ObligationPredictionResponse] = Field(default_factory=list)
    evaluation_summary: PredictionEvaluationMetrics = Field(default_factory=PredictionEvaluationMetrics)
    model_version: str = "predictive-v1"


class OutcomeSnapshotResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True, protected_namespaces=())

    id: str
    obligation_id: str
    snapshot_time: datetime
    status: str
    outcome_type: str
    owner: str
    beneficiary: str
    action: str
    deadline: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    delay_hours: float
    risk_score: float
    risk_level: str
    dependency_count: int
    blocker_count: int
    evidence_count: int
    intervention_count: int
    intervention_required: bool
    intervention_successful: bool
    reconciliation_conflict_occurred: bool
    relevant_event_signals: Optional[List[Any]] = None
    created_at: datetime


class FeatureAttributionItem(BaseModel):
    feature: str
    raw_value: float
    normalized_value: float
    contribution: float
    direction: str  # "INCREASES_RISK" | "DECREASES_RISK" | "NEUTRAL"
    explanation: str


class PredictionFeedbackResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True, protected_namespaces=())

    id: str
    prediction_snapshot_id: str
    obligation_id: str
    prediction_provider: str
    model_version: str
    predicted_failure_probability: float
    predicted_completion_probability: float
    predicted_expected_delay_hours: float
    predicted_intervention_likelihood: float
    predicted_confidence: float
    feature_attributions: Optional[List[Dict[str, Any]]] = None
    observed_outcome: str
    observed_delay_hours: float
    absolute_delay_error: float
    probability_error: float
    was_high_risk_prediction_correct: Optional[bool] = None
    intervention_recommended: bool
    intervention_taken: bool
    intervention_effective: Optional[bool] = None
    created_at: datetime


class FeatureEffectivenessItem(BaseModel):
    feature: str
    observation_count: int
    average_contribution: float
    predictive_direction: str
    outcome_association: float
    reliability_score: float
    historical_usefulness: str
    confidence: float


class AdaptiveFeaturePatternsResponse(BaseModel):
    total_feedback_evaluated: int
    learned_weights: Dict[str, float] = Field(default_factory=dict)
    features: List[FeatureEffectivenessItem] = Field(default_factory=list)


class AdaptiveCalibrationResponse(BaseModel):
    status: str  # "INSUFFICIENT_HISTORY" | "LOW_SAMPLE" | "CALIBRATION_AVAILABLE"
    total_evaluations: int
    minimum_required: int = 3
    brier_score: Optional[float] = None
    calibration_error: Optional[float] = None
    mean_absolute_delay_error: Optional[float] = None
    high_risk_precision: Optional[float] = None
    high_risk_recall: Optional[float] = None
    false_positive_rate: Optional[float] = None
    false_negative_rate: Optional[float] = None
    evaluated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    message: str = "Evaluating adaptive model calibration."


class ModelComparisonResponse(BaseModel):
    obligation_id: str
    action: Optional[str] = None
    owner: Optional[str] = None
    predictive_v1: ObligationPredictionResponse
    adaptive_v1: ObligationPredictionResponse
    probability_variance: float
    delay_variance_hours: float
    adjustment_reasons: List[str] = Field(default_factory=list)
    recommended_provider: str = "adaptive-v1"


class PredictionHistoryItem(BaseModel):
    model_config = ConfigDict(protected_namespaces=())

    prediction_id: str
    model_version: str
    predicted_at: datetime
    failure_probability: float
    expected_delay_hours: float
    confidence: float
    top_signals: List[str] = Field(default_factory=list)
    observed_outcome: Optional[str] = None
    observed_delay_hours: Optional[float] = None
    prediction_error: Optional[float] = None


class PredictionHistoryResponse(BaseModel):
    obligation_id: str
    action: Optional[str] = None
    history: List[PredictionHistoryItem] = Field(default_factory=list)


class InterventionEffectivenessMetric(BaseModel):
    total_interventions_recommended: int = 0
    interventions_executed: int = 0
    completed_after_intervention: int = 0
    completed_without_intervention: int = 0
    observed_completion_rate_with_intervention: float = 0.0
    observed_completion_rate_without_intervention: float = 0.0
    sample_size_status: str = "INSUFFICIENT_HISTORY"
    insights: List[str] = Field(default_factory=list)


class AdaptiveOverviewResponse(BaseModel):
    model_config = ConfigDict(protected_namespaces=())

    active_evaluations: int
    calibration_status: str
    model_comparison_summary: Dict[str, Any] = Field(default_factory=dict)
    top_effective_features: List[FeatureEffectivenessItem] = Field(default_factory=list)
    intervention_efficacy: InterventionEffectivenessMetric = Field(default_factory=InterventionEffectivenessMetric)
    calibration_metrics: AdaptiveCalibrationResponse

