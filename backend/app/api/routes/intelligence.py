from typing import List, Dict, Any, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.auth import User, Workspace
from app.core.auth_deps import get_current_user, get_current_workspace
from app.services.intelligence.intelligence_service import IntelligenceService
from app.services.intelligence.similarity_engine import SimilarityEngine
from app.services.intelligence.historical_pattern_engine import HistoricalPatternEngine
from app.services.intelligence.prediction_evaluation_service import PredictionEvaluationService
from app.schemas.intelligence import (
    IntelligenceOverviewResponse,
    ObligationPredictionResponse,
    SimilarObligationsResponse,
    HistoricalPatternsResponse,
    OwnerPatternMetric,
    PredictionEvaluationMetrics,
    OutcomeSnapshotResponse,
    AdaptiveOverviewResponse,
    AdaptiveFeaturePatternsResponse,
    AdaptiveCalibrationResponse,
    ModelComparisonResponse,
    PredictionHistoryResponse,
    InterventionEffectivenessMetric,
    RootCauseAnalysisResponse,
    ImpactAnalysisResponse,
    CriticalPathResponse,
    ResolutionPlanResponse,
    ResolutionSimulationRequest,
    ResolutionSimulationResponse,
    BottleneckAnalysisResponse,
    RiskConcentrationResponse,
)
from app.services.intelligence.calibration_engine import CalibrationEngine
from app.services.intelligence.weight_learning_engine import WeightLearningEngine
from app.services.intelligence.intervention_effectiveness_service import InterventionEffectivenessService
from app.services.intelligence.root_cause_engine import RootCauseAnalysisEngine
from app.services.intelligence.impact_analysis_service import ImpactAnalysisService
from app.services.intelligence.critical_path_engine import CriticalPathEngine
from app.services.intelligence.resolution_planner import ResolutionPlanner
from app.services.intelligence.resolution_simulation_service import ResolutionSimulationService
from app.services.intelligence.risk_concentration_service import RiskConcentrationService

router = APIRouter(prefix="/intelligence", tags=["Intelligence & Predictions"])


@router.get("/overview", response_model=IntelligenceOverviewResponse)
async def get_intelligence_overview(
    session: AsyncSession = Depends(get_db),
    workspace: Workspace = Depends(get_current_workspace),
    user: User = Depends(get_current_user),
):
    """
    Returns high-level predictive intelligence overview across all active obligations in workspace.
    """
    return await IntelligenceService.get_overview(session)


@router.get("/obligations/{obligation_id}", response_model=Dict[str, Any])
async def get_obligation_intelligence_dossier(
    obligation_id: str,
    session: AsyncSession = Depends(get_db),
    workspace: Workspace = Depends(get_current_workspace),
    user: User = Depends(get_current_user),
):
    """
    Returns full predictive intelligence dossier for an obligation.
    """
    try:
        return await IntelligenceService.get_obligation_dossier(session, obligation_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.get("/obligations/{obligation_id}/prediction", response_model=ObligationPredictionResponse)
async def get_obligation_prediction(
    obligation_id: str,
    session: AsyncSession = Depends(get_db),
    workspace: Workspace = Depends(get_current_workspace),
    user: User = Depends(get_current_user),
):
    """
    Computes and records a prediction snapshot for an active obligation.
    """
    try:
        return await IntelligenceService.predict_and_snapshot(session, obligation_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.get("/obligations/{obligation_id}/similar", response_model=SimilarObligationsResponse)
async def get_similar_obligations(
    obligation_id: str,
    limit: int = 6,
    session: AsyncSession = Depends(get_db),
    workspace: Workspace = Depends(get_current_workspace),
    user: User = Depends(get_current_user),
):
    """
    Retrieves historically similar obligations and their recorded outcomes.
    """
    return await SimilarityEngine.find_similar_obligations(session, obligation_id, limit=limit)


@router.get("/patterns", response_model=HistoricalPatternsResponse)
async def get_historical_patterns(
    session: AsyncSession = Depends(get_db),
    workspace: Workspace = Depends(get_current_workspace),
    user: User = Depends(get_current_user),
):
    """
    Returns aggregated global historical patterns.
    """
    return await HistoricalPatternEngine.get_historical_patterns(session)


@router.get("/owners", response_model=List[OwnerPatternMetric])
async def get_owner_analytics(
    session: AsyncSession = Depends(get_db),
    workspace: Workspace = Depends(get_current_workspace),
    user: User = Depends(get_current_user),
):
    """
    Returns neutral operational owner metrics.
    """
    return await HistoricalPatternEngine.get_owner_metrics(session)


@router.get("/evaluation", response_model=PredictionEvaluationMetrics)
async def get_prediction_evaluation(
    model_version: Optional[str] = "predictive-v1",
    session: AsyncSession = Depends(get_db),
    workspace: Workspace = Depends(get_current_workspace),
    user: User = Depends(get_current_user),
):
    """
    Evaluates historical predictions against actual outcomes (MAE, calibration, Brier score).
    """
    return await PredictionEvaluationService.evaluate_predictions(session, model_version=model_version)


@router.get("/history/{obligation_id}", response_model=List[OutcomeSnapshotResponse])
async def get_obligation_history(
    obligation_id: str,
    session: AsyncSession = Depends(get_db),
    workspace: Workspace = Depends(get_current_workspace),
    user: User = Depends(get_current_user),
):
    """
    Returns the timeline of recorded outcome snapshots for a specific obligation.
    """
    return await IntelligenceService.get_history(session, obligation_id)


# ==============================================================================
# PHASE 13: ADAPTIVE PREDICTION, CALIBRATION & INTELLIGENCE FEEDBACK
# ==============================================================================

@router.get("/adaptive/overview", response_model=AdaptiveOverviewResponse)
async def get_adaptive_overview(
    session: AsyncSession = Depends(get_db),
    workspace: Workspace = Depends(get_current_workspace),
    user: User = Depends(get_current_user),
):
    """
    Returns complete adaptive intelligence dashboard overview including calibration,
    learned feature weights, and intervention efficacy.
    """
    return await IntelligenceService.get_adaptive_overview(session)


@router.get("/adaptive/features", response_model=AdaptiveFeaturePatternsResponse)
async def get_adaptive_features(
    session: AsyncSession = Depends(get_db),
    workspace: Workspace = Depends(get_current_workspace),
    user: User = Depends(get_current_user),
):
    """
    Returns empirically learned feature effectiveness and statistical weights
    from historical PredictionFeedback records.
    """
    return await WeightLearningEngine.get_feature_patterns(session)


@router.get("/adaptive/calibration", response_model=AdaptiveCalibrationResponse)
async def get_adaptive_calibration(
    model_version: Optional[str] = None,
    session: AsyncSession = Depends(get_db),
    workspace: Workspace = Depends(get_current_workspace),
    user: User = Depends(get_current_user),
):
    """
    Returns statistical calibration analysis (Brier score, calibration error, precision, recall)
    with strict data sufficiency boundaries.
    """
    return await CalibrationEngine.compute_calibration(session, model_version=model_version)


@router.get("/compare/{obligation_id}", response_model=ModelComparisonResponse)
async def compare_prediction_models(
    obligation_id: str,
    session: AsyncSession = Depends(get_db),
    workspace: Workspace = Depends(get_current_workspace),
    user: User = Depends(get_current_user),
):
    """
    Generates and compares predictions between predictive-v1 (baseline) and
    adaptive-v1 (calibrated) for the same obligation.
    """
    try:
        return await IntelligenceService.compare_models(session, obligation_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.get("/obligations/{obligation_id}/prediction-history", response_model=PredictionHistoryResponse)
async def get_obligation_prediction_history(
    obligation_id: str,
    session: AsyncSession = Depends(get_db),
    workspace: Workspace = Depends(get_current_workspace),
    user: User = Depends(get_current_user),
):
    """
    Retrieves full prediction history, probabilities, and outcome evaluation for an obligation.
    """
    try:
        return await IntelligenceService.get_prediction_history(session, obligation_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.get("/intervention-effectiveness", response_model=InterventionEffectivenessMetric)
async def get_intervention_effectiveness(
    session: AsyncSession = Depends(get_db),
    workspace: Workspace = Depends(get_current_workspace),
    user: User = Depends(get_current_user),
):
    """
    Returns objective operational analysis of observed completion rates for
    commitments with vs without human-authorized interventions.
    """
    return await InterventionEffectivenessService.get_metrics(session)


# ==============================================================================
# PHASE 14: ROOT-CAUSE ANALYSIS, IMPACT & RESOLUTION PLANNING ROUTES
# ==============================================================================

@router.get("/obligations/{obligation_id}/root-cause", response_model=RootCauseAnalysisResponse)
async def get_obligation_root_cause(
    obligation_id: str,
    session: AsyncSession = Depends(get_db),
    workspace: Workspace = Depends(get_current_workspace),
    user: User = Depends(get_current_user),
):
    """
    Performs multi-signal causal deduction classifying direct causes, upstream causes,
    contributing factors, and uncertainties with calibrated confidence.
    """
    try:
        return await RootCauseAnalysisEngine.analyze(
            session, obligation_id, workspace_id=workspace.id if workspace else None
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.get("/obligations/{obligation_id}/impact", response_model=ImpactAnalysisResponse)
async def get_obligation_impact(
    obligation_id: str,
    session: AsyncSession = Depends(get_db),
    workspace: Workspace = Depends(get_current_workspace),
    user: User = Depends(get_current_user),
):
    """
    Calculates downstream blast radius and bounded impact score (0.0 to 1.0)
    with detailed score breakdown.
    """
    try:
        return await ImpactAnalysisService.analyze_impact(
            session, obligation_id, workspace_id=workspace.id if workspace else None
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.get("/obligations/{obligation_id}/critical-path", response_model=CriticalPathResponse)
async def get_obligation_critical_path(
    obligation_id: str,
    session: AsyncSession = Depends(get_db),
    workspace: Workspace = Depends(get_current_workspace),
    user: User = Depends(get_current_user),
):
    """
    Computes deterministic critical dependency path over DAGs, identifying
    highest-risk prerequisite chain and root blocker.
    """
    try:
        return await CriticalPathEngine.compute_critical_path(
            session, obligation_id, workspace_id=workspace.id if workspace else None
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.get("/obligations/{obligation_id}/resolution-plan", response_model=ResolutionPlanResponse)
async def get_obligation_resolution_plan(
    obligation_id: str,
    session: AsyncSession = Depends(get_db),
    workspace: Workspace = Depends(get_current_workspace),
    user: User = Depends(get_current_user),
):
    """
    Generates highest-leverage actionable human intervention plan, prioritizing
    upstream root causes over downstream symptoms.
    """
    try:
        return await ResolutionPlanner.plan_resolution(
            session, obligation_id, workspace_id=workspace.id if workspace else None
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.post("/obligations/{obligation_id}/simulate-resolution", response_model=ResolutionSimulationResponse)
async def simulate_obligation_resolution(
    obligation_id: str,
    request: ResolutionSimulationRequest,
    session: AsyncSession = Depends(get_db),
    workspace: Workspace = Depends(get_current_workspace),
    user: User = Depends(get_current_user),
):
    """
    100% side-effect-free in-memory counterfactual resolution simulator.
    Simulates completing prerequisites or resolving blockers without mutating the database.
    """
    if request.target_obligation_id != obligation_id:
        request.target_obligation_id = obligation_id

    try:
        return await ResolutionSimulationService.simulate(
            session, request, workspace_id=workspace.id if workspace else None
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.get("/bottlenecks", response_model=BottleneckAnalysisResponse)
async def get_systemic_bottlenecks(
    session: AsyncSession = Depends(get_db),
    workspace: Workspace = Depends(get_current_workspace),
    user: User = Depends(get_current_user),
):
    """
    Surfaces structural bottleneck commitments with high downstream dependency fan-out.
    """
    return await RiskConcentrationService.get_bottlenecks(
        session, workspace_id=workspace.id if workspace else None
    )


@router.get("/risk-concentration", response_model=RiskConcentrationResponse)
async def get_risk_concentration(
    session: AsyncSession = Depends(get_db),
    workspace: Workspace = Depends(get_current_workspace),
    user: User = Depends(get_current_user),
):
    """
    Identifies systemic organizational risk concentrations and multi-person choke points.
    """
    return await RiskConcentrationService.get_risk_concentrations(
        session, workspace_id=workspace.id if workspace else None
    )


