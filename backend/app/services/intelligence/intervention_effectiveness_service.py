"""
================================================================================
Intervention Effectiveness Service
Obligation Agent — Phase 13: Adaptive Prediction & Intelligence Feedback
================================================================================

Analyzes historical intervention efficacy using neutral operational language.
Measures observed completion rates for intervened vs non-intervened commitments.
"""

from typing import List
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.intelligence import ObligationOutcomeSnapshot
from app.models.obligation import Intervention
from app.schemas.intelligence import InterventionEffectivenessMetric


class InterventionEffectivenessService:
    """
    Computes objective metrics on intervention follow-up outcomes.
    """

    @classmethod
    async def get_metrics(
        cls,
        session: AsyncSession,
    ) -> InterventionEffectivenessMetric:
        """
        Evaluates completion rates for commitments with and without human-authorized interventions.
        """
        # Fetch outcome snapshots
        snap_stmt = select(ObligationOutcomeSnapshot)
        snap_res = await session.execute(snap_stmt)
        snapshots = snap_res.scalars().all()

        # Fetch all interventions
        inv_stmt = select(Intervention)
        inv_res = await session.execute(inv_stmt)
        interventions = inv_res.scalars().all()

        total_snaps = len(snapshots)
        total_invs = len(interventions)
        executed_invs = sum(1 for inv in interventions if inv.status == "EXECUTED")

        if total_snaps < 3:
            return InterventionEffectivenessMetric(
                total_interventions_recommended=total_invs,
                interventions_executed=executed_invs,
                completed_after_intervention=0,
                completed_without_intervention=0,
                observed_completion_rate_with_intervention=0.0,
                observed_completion_rate_without_intervention=0.0,
                sample_size_status="INSUFFICIENT_HISTORY",
                insights=["Insufficient historical outcome data to measure intervention effectiveness."],
            )

        # Categorize snapshots
        intervened_snaps = [s for s in snapshots if s.intervention_count > 0 or s.intervention_required]
        non_intervened_snaps = [s for s in snapshots if s.intervention_count == 0 and not s.intervention_required]

        intervened_completed = sum(1 for s in intervened_snaps if "COMPLETED" in s.outcome_type)
        non_intervened_completed = sum(1 for s in non_intervened_snaps if "COMPLETED" in s.outcome_type)

        rate_with_inv = (
            round(intervened_completed / float(len(intervened_snaps)), 3)
            if intervened_snaps else 0.0
        )
        rate_without_inv = (
            round(non_intervened_completed / float(len(non_intervened_snaps)), 3)
            if non_intervened_snaps else 0.0
        )

        sample_status = "LOW_SAMPLE" if total_snaps < 10 else "CALIBRATION_AVAILABLE"

        insights = [
            f"Observed completion rate after intervention: {round(rate_with_inv * 100, 1)}% ({intervened_completed} of {len(intervened_snaps)} obligations).",
            f"Observed completion rate without intervention: {round(rate_without_inv * 100, 1)}% ({non_intervened_completed} of {len(non_intervened_snaps)} obligations).",
            f"Total human-authorized interventions executed: {executed_invs}.",
        ]

        return InterventionEffectivenessMetric(
            total_interventions_recommended=total_invs,
            interventions_executed=executed_invs,
            completed_after_intervention=intervened_completed,
            completed_without_intervention=non_intervened_completed,
            observed_completion_rate_with_intervention=rate_with_inv,
            observed_completion_rate_without_intervention=rate_without_inv,
            sample_size_status=sample_status,
            insights=insights,
        )
