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
)
from app.services.intelligence.calibration_engine import CalibrationEngine
from app.services.intelligence.weight_learning_engine import WeightLearningEngine
from app.services.intelligence.intervention_effectiveness_service import InterventionEffectivenessService

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

