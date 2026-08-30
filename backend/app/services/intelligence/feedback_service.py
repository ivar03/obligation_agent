"""
================================================================================
Feedback Service
Obligation Agent — Phase 13: Adaptive Prediction & Intelligence Feedback
================================================================================

Matches historical PredictionSnapshots with observed ObligationOutcomeSnapshots
to create immutable PredictionFeedback records for calibration and weight learning.
"""

from typing import List, Optional
from datetime import datetime, timezone
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.intelligence import (
    PredictionSnapshot,
    ObligationOutcomeSnapshot,
    PredictionFeedback,
)


class FeedbackService:
    """
    Orchestrates the evaluation of forecasts against ground-truth outcomes.
    """

    @classmethod
    async def record_feedback(
        cls,
        session: AsyncSession,
        obligation_id: str,
        snapshot: ObligationOutcomeSnapshot,
    ) -> List[PredictionFeedback]:
        """
        Creates PredictionFeedback records for all un-evaluated prediction snapshots
        associated with this obligation.
        """
        # Find prediction snapshots for this obligation
        pred_stmt = select(PredictionSnapshot).where(
            PredictionSnapshot.obligation_id == obligation_id
        ).order_by(PredictionSnapshot.created_at.desc())
        pred_res = await session.execute(pred_stmt)
        snapshots = pred_res.scalars().all()

        if not snapshots:
            return []

        created_feedbacks: List[PredictionFeedback] = []
        now = datetime.now(timezone.utc)

        # Determine ground truth failure
        is_failure = 1.0 if (
            snapshot.outcome_type in ("COMPLETED_LATE", "OVERDUE", "BLOCKED", "CONFLICTED_COMPLETION")
            or snapshot.delay_hours > 0.5
        ) else 0.0

        for snap in snapshots:
            # Calculate errors
            abs_delay_error = round(abs(snap.expected_delay_hours - snapshot.delay_hours), 2)
            prob_error = round(abs(snap.failure_probability - is_failure), 4)

            # High risk prediction correctness
            if snap.failure_probability >= 0.50:
                was_high_risk_correct = (is_failure == 1.0)
            else:
                was_high_risk_correct = (is_failure == 0.0)

            # Update prediction snapshot evaluated fields
            snap.actual_outcome = snapshot.outcome_type
            snap.actual_delay_hours = snapshot.delay_hours
            snap.evaluated_at = now
            snap.prediction_error = prob_error

            # Convert prediction reasons to feature attributions if available
            reasons = snap.prediction_reasons or []
            feature_attributions = []
            for r in reasons:
                feature_attributions.append({
                    "feature": r.get("signal", "UNKNOWN"),
                    "contribution": r.get("impact", 0.0),
                    "normalized_value": 0.8 if r.get("impact", 0.0) > 0 else 0.2,
                    "direction": "INCREASES_RISK" if r.get("impact", 0.0) > 0 else "DECREASES_RISK",
                    "explanation": r.get("explanation", ""),
                })

            provider_name = "adaptive-v1" if snap.model_version == "adaptive-v1" else "deterministic-v1"

            fb = PredictionFeedback(
                workspace_id=snapshot.workspace_id,
                prediction_snapshot_id=snap.id,
                obligation_id=obligation_id,
                prediction_provider=provider_name,
                model_version=snap.model_version,
                predicted_failure_probability=snap.failure_probability,
                predicted_completion_probability=snap.completion_probability,
                predicted_expected_delay_hours=snap.expected_delay_hours,
                predicted_intervention_likelihood=snap.intervention_likelihood,
                predicted_confidence=snap.confidence,
                feature_attributions=feature_attributions,
                observed_outcome=snapshot.outcome_type,
                observed_delay_hours=snapshot.delay_hours,
                absolute_delay_error=abs_delay_error,
                probability_error=prob_error,
                was_high_risk_prediction_correct=was_high_risk_correct,
                intervention_recommended=snapshot.intervention_required,
                intervention_taken=snapshot.intervention_count > 0,
                intervention_effective=snapshot.intervention_successful if snapshot.intervention_count > 0 else None,
                created_at=now,
            )
            session.add(fb)
            created_feedbacks.append(fb)

        await session.commit()
        return created_feedbacks
