from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.intelligence import PredictionSnapshot, ObligationOutcomeSnapshot
from app.models.obligation import Obligation
from app.schemas.intelligence import PredictionEvaluationMetrics


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class PredictionEvaluationService:
    """
    Service for comparing persisted PredictionSnapshot forecasts against actual
    observed outcomes to calculate calibration, accuracy, Brier score, and MAE.
    """

    MIN_SAMPLES_FOR_EVALUATION = 3

    @classmethod
    async def evaluate_predictions(
        cls,
        session: AsyncSession,
        model_version: Optional[str] = "predictive-v1",
    ) -> PredictionEvaluationMetrics:
        now = utc_now()

        stmt = select(PredictionSnapshot).order_by(PredictionSnapshot.created_at.desc())
        if model_version:
            stmt = stmt.where(PredictionSnapshot.model_version == model_version)

        res = await session.execute(stmt)
        snapshots = list(res.scalars().all())

        if not snapshots:
            return PredictionEvaluationMetrics(
                total_predictions_evaluated=0,
                status="INSUFFICIENT_HISTORY",
                message="No prediction snapshots recorded yet.",
                evaluated_at=now,
            )

        # Update actual outcomes for snapshots where obligation has resolved
        evaluated_records: List[PredictionSnapshot] = []
        for snap in snapshots:
            if not snap.actual_outcome:
                # Check outcome snapshot
                snap_stmt = select(ObligationOutcomeSnapshot).where(
                    ObligationOutcomeSnapshot.obligation_id == snap.obligation_id
                ).order_by(ObligationOutcomeSnapshot.created_at.desc())
                snap_res = await session.execute(snap_stmt)
                outcome = snap_res.scalars().first()

                if outcome:
                    snap.actual_outcome = outcome.outcome_type
                    snap.actual_delay_hours = outcome.delay_hours
                    snap.evaluated_at = now

                    # Ground truth failure: 1.0 if late, overdue, or conflicted, 0.0 if completed on time
                    actual_fail = 1.0 if outcome.outcome_type in [
                        "OVERDUE", "COMPLETED_LATE", "BLOCKED", "CONFLICTED_COMPLETION"
                    ] else 0.0

                    snap.prediction_error = abs(snap.failure_probability - actual_fail)
                    session.add(snap)
                    evaluated_records.append(snap)
            else:
                evaluated_records.append(snap)

        if evaluated_records:
            await session.commit()

        # Check sample sufficiency
        valid_evals = [s for s in evaluated_records if s.actual_outcome is not None]
        total_eval = len(valid_evals)

        if total_eval < cls.MIN_SAMPLES_FOR_EVALUATION:
            return PredictionEvaluationMetrics(
                total_predictions_evaluated=total_eval,
                status="INSUFFICIENT_HISTORY",
                message=(
                    f"Insufficient historical evaluations ({total_eval} observed, minimum "
                    f"{cls.MIN_SAMPLES_FOR_EVALUATION} required for calibration analysis)."
                ),
                evaluated_at=now,
            )

        # 1. Brier Score & Accuracy
        brier_sum = 0.0
        correct_predictions = 0
        mae_delay_sum = 0.0
        predicted_probs: List[float] = []
        actual_labels: List[float] = []

        tp = 0
        fp = 0
        fn = 0
        tn = 0

        for s in valid_evals:
            actual_fail = 1.0 if s.actual_outcome in [
                "OVERDUE", "COMPLETED_LATE", "BLOCKED", "CONFLICTED_COMPLETION"
            ] else 0.0

            predicted_probs.append(s.failure_probability)
            actual_labels.append(actual_fail)

            # Brier score component: (prob - y)^2
            brier_sum += (s.failure_probability - actual_fail) ** 2

            # Delay MAE
            act_delay = s.actual_delay_hours if s.actual_delay_hours is not None else 0.0
            mae_delay_sum += abs(s.expected_delay_hours - act_delay)

            # Classification at 0.50 threshold
            pred_fail_binary = 1.0 if s.failure_probability >= 0.50 else 0.0
            if pred_fail_binary == actual_fail:
                correct_predictions += 1

            if pred_fail_binary == 1.0 and actual_fail == 1.0:
                tp += 1
            elif pred_fail_binary == 1.0 and actual_fail == 0.0:
                fp += 1
            elif pred_fail_binary == 0.0 and actual_fail == 1.0:
                fn += 1
            else:
                tn += 1

        brier_score = round(brier_sum / total_eval, 3)
        mae_hours = round(mae_delay_sum / total_eval, 1)
        accuracy = round(correct_predictions / total_eval, 2)

        # Calibration Error
        avg_pred_prob = sum(predicted_probs) / total_eval
        empirical_fail_rate = sum(actual_labels) / total_eval
        calibration_error = round(abs(avg_pred_prob - empirical_fail_rate), 3)

        # Precision & Recall
        precision = round(tp / (tp + fp), 2) if (tp + fp) > 0 else 1.0
        recall = round(tp / (tp + fn), 2) if (tp + fn) > 0 else 1.0

        return PredictionEvaluationMetrics(
            total_predictions_evaluated=total_eval,
            status="EVALUATED",
            mean_absolute_error_hours=mae_hours,
            brier_score=brier_score,
            calibration_error=calibration_error,
            high_risk_precision=precision,
            overdue_recall=recall,
            accuracy=accuracy,
            evaluated_at=now,
            message=f"Model calibration verified on {total_eval} historical outcomes.",
        )
