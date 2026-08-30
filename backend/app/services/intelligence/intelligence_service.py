import uuid
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.obligation import Obligation, Evidence, Intervention, ReconciliationRecord
from app.models.intelligence import ObligationOutcomeSnapshot, PredictionSnapshot, PredictionFeedback
from app.core.status_machine import ObligationStatus, ObligationOutcomeType
from app.services.intelligence.outcome_classifier import OutcomeClassifier
from app.services.intelligence.similarity_engine import SimilarityEngine
from app.services.intelligence.historical_pattern_engine import HistoricalPatternEngine
from app.services.intelligence.predictive_obligation_engine import PredictiveObligationEngine
from app.services.intelligence.prediction_evaluation_service import PredictionEvaluationService
from app.services.intelligence.adaptive_prediction_provider import AdaptivePredictionProvider
from app.services.intelligence.calibration_engine import CalibrationEngine
from app.services.intelligence.weight_learning_engine import WeightLearningEngine
from app.services.intelligence.feedback_service import FeedbackService
from app.services.intelligence.intervention_effectiveness_service import InterventionEffectivenessService
from app.schemas.intelligence import (
    ObligationPredictionResponse,
    SimilarObligationsResponse,
    HistoricalPatternsResponse,
    OwnerPatternMetric,
    PredictionEvaluationMetrics,
    IntelligenceOverviewResponse,
    OutcomeSnapshotResponse,
    AdaptiveOverviewResponse,
    AdaptiveCalibrationResponse,
    AdaptiveFeaturePatternsResponse,
    ModelComparisonResponse,
    PredictionHistoryResponse,
    PredictionHistoryItem,
    InterventionEffectivenessMetric,
)


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class IntelligenceService:
    """
    Unified intelligence orchestrator coordinating outcome snapshot recording,
    deterministic pattern learning, predictive forecasting, adaptive weight learning,
    and calibration evaluation.
    """

    @classmethod
    async def record_outcome_snapshot(
        cls,
        session: AsyncSession,
        obligation_id: str,
        completed_at: Optional[datetime] = None,
    ) -> Optional[ObligationOutcomeSnapshot]:
        """
        Extracts and records a historical outcome snapshot for an obligation,
        then triggers feedback evaluation for prior forecasts.
        """
        ob = await session.get(Obligation, obligation_id)
        if not ob:
            return None

        # Fetch associated evidence
        ev_stmt = select(Evidence).where(Evidence.obligation_id == obligation_id)
        ev_res = await session.execute(ev_stmt)
        evidence_list = list(ev_res.scalars().all())

        # Fetch interventions
        inv_stmt = select(Intervention).where(Intervention.obligation_id == obligation_id)
        inv_res = await session.execute(inv_stmt)
        interventions_list = list(inv_res.scalars().all())

        # Fetch reconciliations
        rec_stmt = select(ReconciliationRecord).where(ReconciliationRecord.obligation_id == obligation_id)
        rec_res = await session.execute(rec_stmt)
        reconciliations_list = list(rec_res.scalars().all())

        # Classify outcome
        outcome_type, delay_hours = OutcomeClassifier.classify(
            obligation=ob,
            completed_at=completed_at or utc_now(),
            evidence_list=evidence_list,
            interventions_list=interventions_list,
            reconciliation_records=reconciliations_list,
        )

        # Count dependencies & blockers
        from app.services.graph_service import GraphService
        deps = await GraphService.get_dependencies(session, obligation_id)
        blockers = await GraphService.get_blockers(session, obligation_id)

        inv_req = len(interventions_list) > 0
        inv_succ = any(i.status in ["EXECUTED", "RESOLVED"] for i in interventions_list)
        rec_conflict = any(r.contradiction_score >= 0.50 or r.status == "RESOLVED_CONFLICTING" for r in reconciliations_list)

        snapshot = ObligationOutcomeSnapshot(
            workspace_id=ob.workspace_id,
            obligation_id=obligation_id,
            snapshot_time=utc_now(),
            status=ob.status.value if hasattr(ob.status, "value") else str(ob.status),
            outcome_type=outcome_type.value if hasattr(outcome_type, "value") else str(outcome_type),
            owner=ob.owner,
            beneficiary=ob.beneficiary,
            obligation_type=ob.obligation_type.value if hasattr(ob.obligation_type, "value") else str(ob.obligation_type),
            action=ob.action,
            deadline=ob.deadline,
            completed_at=completed_at or (utc_now() if ob.status == ObligationStatus.COMPLETED else None),
            delay_hours=round(delay_hours, 1),
            risk_score=0.0,  # Snapshot risk
            risk_level="LOW",
            dependency_count=len(deps),
            blocker_count=len(blockers),
            evidence_count=len(evidence_list),
            intervention_count=len(interventions_list),
            intervention_required=inv_req,
            intervention_successful=inv_succ,
            reconciliation_conflict_occurred=rec_conflict,
            relevant_event_signals=[e.semantic_role.value if hasattr(e.semantic_role, "value") else str(e.semantic_role) for e in evidence_list[:5]],
            extra_metadata={},
        )
        session.add(snapshot)
        await session.commit()
        await session.refresh(snapshot)

        # Record PredictionFeedback records
        await FeedbackService.record_feedback(session, obligation_id, snapshot)

        return snapshot

    @classmethod
    async def predict_and_snapshot(
        cls,
        session: AsyncSession,
        obligation_id: str,
        context: Optional[Dict[str, Any]] = None,
        provider: str = "predictive-v1",
    ) -> ObligationPredictionResponse:
        """
        Generates predictive forecast and records a persistent PredictionSnapshot.
        """
        ob = await session.get(Obligation, obligation_id)
        if provider == "adaptive-v1":
            prediction = await AdaptivePredictionProvider.predict(session, obligation_id)
        else:
            prediction = await PredictiveObligationEngine.predict_obligation(session, obligation_id, context)

        snap = PredictionSnapshot(
            workspace_id=ob.workspace_id if ob else "ws-default",
            obligation_id=obligation_id,
            model_version=prediction.model_version,
            prediction_type="FAILURE_PROBABILITY",
            failure_probability=prediction.failure_probability,
            completion_probability=prediction.completion_probability,
            expected_delay_hours=prediction.expected_delay_hours,
            intervention_likelihood=prediction.intervention_likelihood,
            blockage_likelihood=prediction.blockage_likelihood,
            confidence=prediction.confidence,
            prediction_reasons=[r.model_dump() for r in prediction.reasons],
            preventative_recommendation=prediction.preventative_recommendation,
            recommended_action_type=prediction.recommended_action_type.value if prediction.recommended_action_type else None,
            created_at=utc_now(),
        )
        session.add(snap)
        await session.commit()

        return prediction

    @classmethod
    async def compare_models(
        cls,
        session: AsyncSession,
        obligation_id: str,
    ) -> ModelComparisonResponse:
        """
        Runs both predictive-v1 and adaptive-v1 providers for the same obligation
        and returns a structured comparison breakdown.
        """
        ob = await session.get(Obligation, obligation_id)
        if not ob:
            raise ValueError(f"Obligation with ID '{obligation_id}' not found.")

        pred_v1 = await PredictiveObligationEngine.predict_obligation(session, obligation_id)
        adapt_v1 = await AdaptivePredictionProvider.predict(session, obligation_id, ob)

        prob_variance = round(adapt_v1.failure_probability - pred_v1.failure_probability, 4)
        delay_variance = round(adapt_v1.expected_delay_hours - pred_v1.expected_delay_hours, 1)

        reasons: List[str] = []
        if abs(prob_variance) >= 0.03:
            dir_str = "elevated" if prob_variance > 0 else "reduced"
            reasons.append(
                f"Adaptive feature weights {dir_str} failure probability by {abs(round(prob_variance * 100, 1))}% based on historical feedback calibration."
            )
        if abs(delay_variance) >= 1.0:
            dir_str = "increased" if delay_variance > 0 else "decreased"
            reasons.append(
                f"Historical owner delivery pattern {dir_str} expected delay projection by {abs(delay_variance)}h."
            )
        if not reasons:
            reasons.append("Both models show strong concordance on this commitment's delivery trajectory.")

        return ModelComparisonResponse(
            obligation_id=obligation_id,
            action=ob.action,
            owner=ob.owner,
            predictive_v1=pred_v1,
            adaptive_v1=adapt_v1,
            probability_variance=prob_variance,
            delay_variance_hours=delay_variance,
            adjustment_reasons=reasons,
            recommended_provider="adaptive-v1",
        )

    @classmethod
    async def get_prediction_history(
        cls,
        session: AsyncSession,
        obligation_id: str,
    ) -> PredictionHistoryResponse:
        """
        Retrieves complete prediction history and outcome evaluation for an obligation.
        """
        ob = await session.get(Obligation, obligation_id)
        snap_stmt = select(PredictionSnapshot).where(
            PredictionSnapshot.obligation_id == obligation_id
        ).order_by(PredictionSnapshot.created_at.desc())
        snap_res = await session.execute(snap_stmt)
        snapshots = snap_res.scalars().all()

        history_items: List[PredictionHistoryItem] = []
        for s in snapshots:
            top_sigs = [r.get("signal", "") for r in (s.prediction_reasons or [])[:3]]
            history_items.append(
                PredictionHistoryItem(
                    prediction_id=s.id,
                    model_version=s.model_version,
                    predicted_at=s.created_at,
                    failure_probability=s.failure_probability,
                    expected_delay_hours=s.expected_delay_hours,
                    confidence=s.confidence,
                    top_signals=[sig for sig in top_sigs if sig],
                    observed_outcome=s.actual_outcome,
                    observed_delay_hours=s.actual_delay_hours,
                    prediction_error=s.prediction_error,
                )
            )

        return PredictionHistoryResponse(
            obligation_id=obligation_id,
            action=ob.action if ob else None,
            history=history_items,
        )

    @classmethod
    async def get_adaptive_overview(
        cls,
        session: AsyncSession,
    ) -> AdaptiveOverviewResponse:
        """
        Aggregates full adaptive intelligence overview.
        """
        cal = await CalibrationEngine.compute_calibration(session)
        patterns = await WeightLearningEngine.get_feature_patterns(session)
        efficacy = await InterventionEffectivenessService.get_metrics(session)

        # Count total evaluated feedbacks
        fb_stmt = select(PredictionFeedback)
        fb_res = await session.execute(fb_stmt)
        feedbacks = fb_res.scalars().all()

        return AdaptiveOverviewResponse(
            active_evaluations=len(feedbacks),
            calibration_status=cal.status,
            model_comparison_summary={
                "baseline_model": "predictive-v1",
                "adaptive_model": "adaptive-v1",
                "learned_weights_count": len(patterns.learned_weights),
                "total_feedbacks_evaluated": len(feedbacks),
            },
            top_effective_features=patterns.features[:6],
            intervention_efficacy=efficacy,
            calibration_metrics=cal,
        )

    @classmethod
    async def get_overview(cls, session: AsyncSession) -> IntelligenceOverviewResponse:
        """
        Generates holistic intelligence overview across all active obligations.
        """
        stmt = select(Obligation).where(
            Obligation.status.notin_([ObligationStatus.COMPLETED, ObligationStatus.CANCELLED])
        ).order_by(Obligation.created_at.desc())
        res = await session.execute(stmt)
        active_obs = res.scalars().all()

        predictions: List[ObligationPredictionResponse] = []
        for ob in active_obs:
            try:
                pred = await PredictiveObligationEngine.predict_obligation(session, ob.id)
                predictions.append(pred)
            except Exception:
                continue

        # Sort predictions by failure probability descending
        predictions.sort(key=lambda p: p.failure_probability, reverse=True)

        high_failure = sum(1 for p in predictions if p.failure_probability >= 0.50)
        miss_deadline = sum(1 for p in predictions if p.expected_delay_hours > 0 and p.failure_probability >= 0.40)
        req_intervention = sum(1 for p in predictions if p.intervention_likelihood >= 0.50)
        high_blockage = sum(1 for p in predictions if p.blockage_likelihood >= 0.40)

        eval_summary = await PredictionEvaluationService.evaluate_predictions(session)

        return IntelligenceOverviewResponse(
            active_obligations_evaluated=len(predictions),
            high_predicted_failure_count=high_failure,
            likely_to_miss_deadline_count=miss_deadline,
            likely_to_require_intervention_count=req_intervention,
            high_blockage_risk_count=high_blockage,
            predictions=predictions,
            evaluation_summary=eval_summary,
            model_version="predictive-v1",
        )

    @classmethod
    async def get_obligation_dossier(cls, session: AsyncSession, obligation_id: str) -> Dict[str, Any]:
        """
        Builds full predictive intelligence dossier for an obligation detail view.
        """
        ob = await session.get(Obligation, obligation_id)
        if not ob:
            raise ValueError(f"Obligation '{obligation_id}' not found.")

        prediction = await PredictiveObligationEngine.predict_obligation(session, obligation_id)
        similar = await SimilarityEngine.find_similar_obligations(session, obligation_id, limit=4)
        owner_metrics = await HistoricalPatternEngine.get_owner_metrics(session)
        owner_metric = next((m for m in owner_metrics if m.owner.strip().lower() == ob.owner.strip().lower()), None)

        return {
            "prediction": prediction.model_dump(),
            "similar_obligations": similar.model_dump(),
            "owner_context": owner_metric.model_dump() if owner_metric else None,
            "derived_provenance": prediction.derived_from.model_dump(),
        }

    @classmethod
    async def get_history(cls, session: AsyncSession, obligation_id: str) -> List[OutcomeSnapshotResponse]:
        """
        Returns history of outcome snapshots for an obligation.
        """
        stmt = select(ObligationOutcomeSnapshot).where(
            ObligationOutcomeSnapshot.obligation_id == obligation_id
        ).order_by(ObligationOutcomeSnapshot.created_at.desc())
        res = await session.execute(stmt)
        snapshots = res.scalars().all()
        return [OutcomeSnapshotResponse.model_validate(s) for s in snapshots]

