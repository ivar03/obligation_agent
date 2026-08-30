"""
================================================================================
Adaptive Prediction Provider
Obligation Agent — Phase 13: Adaptive Prediction & Intelligence Feedback
================================================================================

Implements the PredictionProvider Protocol with model_version = 'adaptive-v1'.
Combines base risk signals, historical patterns, and empirically learned
calibrated feature weights into bounded, explainable forecasts.
"""

from typing import Optional, List, Dict, Any
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.obligation import Obligation, ObligationEdge
from app.models.intelligence import ObligationOutcomeSnapshot
from app.core.status_machine import (
    ObligationStatus,
    ActionType,
    PredictiveActionType,
)
from app.schemas.intelligence import (
    ObligationPredictionResponse,
    PredictionReasonItem,
    DerivedProvenanceInfo,
)
from app.services.risk_engine import RiskEngine
from app.services.graph_service import GraphService
from app.services.intelligence.historical_pattern_engine import HistoricalPatternEngine
from app.services.intelligence.similarity_engine import SimilarityEngine
from app.services.intelligence.weight_learning_engine import WeightLearningEngine
from app.services.intelligence.feature_attribution_engine import FeatureAttributionEngine


class AdaptivePredictionProvider:
    """
    Adaptive prediction provider utilizing learned statistical feature weights
    and calibrated feedback loops.
    """

    model_version: str = "adaptive-v1"

    MIN_PROBABILITY: float = 0.05
    MAX_PROBABILITY: float = 0.95

    @classmethod
    async def predict(
        cls,
        session: AsyncSession,
        obligation_id: str,
        obligation: Optional[Obligation] = None,
    ) -> ObligationPredictionResponse:
        """
        Generates an adaptive forecast for the given obligation.
        """
        if obligation is None:
            stmt = select(Obligation).where(Obligation.id == obligation_id)
            res = await session.execute(stmt)
            obligation = res.scalar_one_or_none()
            if not obligation:
                raise ValueError(f"Obligation with ID '{obligation_id}' not found.")

        # 1. Existing Risk Engine Assessment
        risk = await RiskEngine.assess_obligation(session, obligation.id)
        current_risk_score = risk.risk_score
        current_risk_level = risk.risk_level

        # 2. Historical Owner Patterns
        owner_metrics = await HistoricalPatternEngine.get_owner_metrics(session)
        owner_data = next((m for m in owner_metrics if m.owner.lower() == obligation.owner.lower()), None)
        owner_avg_delay = owner_data.avg_delay_hours if owner_data else 0.0
        owner_on_time_rate = owner_data.on_time_rate if owner_data else 0.5

        # 3. Graph Dependency Blockers
        blockers = await GraphService.get_blockers(session, obligation.id)
        blocker_count = len(blockers)
        deps = await GraphService.get_dependencies(session, obligation.id)

        # 4. Similar Historical Commitments
        similar = await SimilarityEngine.find_similar_obligations(session, obligation.id, limit=5)
        similar_count = similar.total_similar_count
        if similar_count > 0:
            on_time_sim = sum(1 for s in similar.items if "ON_TIME" in s.outcome_type)
            similar_on_time_rate = on_time_sim / float(similar_count)
        else:
            similar_on_time_rate = 0.5

        # 5. Temporal Pressure
        now = datetime.now(timezone.utc)
        hours_remaining: Optional[float] = None
        if obligation.deadline:
            dl = obligation.deadline
            if dl.tzinfo is None:
                dl = dl.replace(tzinfo=timezone.utc)
            hours_remaining = (dl - now).total_seconds() / 3600.0

        # 6. Cross-Provider Contradiction Score
        contradiction_score = 0.0
        from app.models.obligation import ReconciliationRecord, Intervention
        rec_stmt = select(ReconciliationRecord).where(
            ReconciliationRecord.obligation_id == obligation.id
        ).order_by(ReconciliationRecord.created_at.desc())
        rec_res = await session.execute(rec_stmt)
        recs = rec_res.scalars().all()
        if recs:
            latest_rec = recs[0]
            if latest_rec.status == "CONFLICTING":
                contradiction_score = latest_rec.contradiction_score or 0.75

        # Interventions count
        inv_stmt = select(Intervention).where(Intervention.obligation_id == obligation.id)
        inv_res = await session.execute(inv_stmt)
        inv_count = len(inv_res.scalars().all())

        # 7. Obtain Learned Feature Weights
        learned_weights = await WeightLearningEngine.get_calibrated_weights(session)

        # 8. Extract Structured Feature Attributions
        attributions = FeatureAttributionEngine.extract_attributions(
            current_risk_score=current_risk_score,
            hours_remaining=hours_remaining,
            owner_avg_delay=owner_avg_delay,
            owner_on_time_rate=owner_on_time_rate,
            blocker_count=blocker_count,
            similar_tasks_count=similar_count,
            similar_on_time_rate=similar_on_time_rate,
            contradiction_score=contradiction_score,
            learned_weights=learned_weights,
        )

        # 9. Compute Calibrated Probabilities
        # Base prior from risk score
        base_failure_prob = current_risk_score * 0.40 + 0.10

        # Sum contributions
        total_adjustment = sum(attr.contribution for attr in attributions)
        raw_failure_prob = base_failure_prob + total_adjustment

        # Strictly bound within [0.05, 0.95]
        bounded_failure_prob = round(
            min(cls.MAX_PROBABILITY, max(cls.MIN_PROBABILITY, raw_failure_prob)),
            4
        )
        bounded_completion_prob = round(1.0 - bounded_failure_prob, 4)

        # Expected delay estimation
        base_delay = owner_avg_delay if owner_avg_delay > 0 else (12.0 * bounded_failure_prob)
        if blocker_count > 0:
            base_delay += blocker_count * 8.0
        if hours_remaining is not None and hours_remaining < 0:
            base_delay += abs(hours_remaining)
        expected_delay_hours = round(max(0.0, base_delay * bounded_failure_prob), 1)

        # Intervention likelihood
        raw_inv = bounded_failure_prob * 0.70 + (0.25 if blocker_count > 0 else 0.0) + (0.20 if contradiction_score > 0.3 else 0.0)
        intervention_likelihood = round(min(cls.MAX_PROBABILITY, max(cls.MIN_PROBABILITY, raw_inv)), 4)

        # Blockage likelihood
        raw_blk = (0.75 if blocker_count > 0 else 0.05) + (0.15 if contradiction_score > 0.3 else 0.0)
        blockage_likelihood = round(min(cls.MAX_PROBABILITY, max(cls.MIN_PROBABILITY, raw_blk)), 4)

        # Confidence: bounded by historical sample availability
        total_hist_stmt = select(ObligationOutcomeSnapshot)
        total_hist_res = await session.execute(total_hist_stmt)
        hist_count = len(total_hist_res.scalars().all())
        raw_conf = 0.55 + min(0.40, hist_count * 0.06 + similar_count * 0.04)
        confidence = round(min(cls.MAX_PROBABILITY, max(cls.MIN_PROBABILITY, raw_conf)), 4)

        # 10. Format Explainable Reasons
        reasons: List[PredictionReasonItem] = [
            PredictionReasonItem(
                signal=attr.feature,
                impact=attr.contribution,
                explanation=attr.explanation,
            )
            for attr in attributions
        ]
        # Sort reasons by absolute impact descending
        reasons.sort(key=lambda r: abs(r.impact), reverse=True)

        # 11. Formulate Preventative Advisory Recommendation
        if blocker_count > 0:
            rec_action_type = ActionType.RESOLVE_DEPENDENCY
            recommendation = f"Resolve {blocker_count} upstream prerequisite blocker(s) before approaching delivery window."
        elif contradiction_score > 0.3:
            rec_action_type = ActionType.REVIEW_CONFLICTING_EVIDENCE
            recommendation = "Review multi-source evidence contradictions across Slack/Email channels."
        elif bounded_failure_prob >= 0.55:
            rec_action_type = ActionType.FOLLOW_UP_OWNER
            recommendation = "Initiate early proactive follow-up with task owner to mitigate anticipated delivery latency."
        elif hours_remaining is not None and hours_remaining <= 24:
            rec_action_type = ActionType.START_WORK
            recommendation = "Prepare deliverable review ahead of upcoming deadline window."
        else:
            rec_action_type = ActionType.NO_ACTION
            recommendation = "Maintain regular monitoring schedule. Forecast indicates stable on-time delivery."

        return ObligationPredictionResponse(
            obligation_id=obligation.id,
            action=obligation.action,
            owner=obligation.owner,
            beneficiary=obligation.beneficiary,
            status=obligation.status,
            deadline=obligation.deadline,
            model_version=cls.model_version,
            failure_probability=bounded_failure_prob,
            completion_probability=bounded_completion_prob,
            expected_delay_hours=expected_delay_hours,
            intervention_likelihood=intervention_likelihood,
            blockage_likelihood=blockage_likelihood,
            confidence=confidence,
            reasons=reasons,
            preventative_recommendation=recommendation,
            recommended_action_type=rec_action_type,
            derived_from=DerivedProvenanceInfo(
                current_risk_evaluated=True,
                historical_outcomes_count=hist_count,
                similar_obligations_count=similar_count,
                dependency_history_count=len(deps),
                intervention_history_count=inv_count,
            ),
            current_risk_score=current_risk_score,
            current_risk_level=current_risk_level,
            predicted_at=now,
        )
