from datetime import datetime, timezone
from typing import Protocol, Dict, Any, Optional, List
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.status_machine import (
    ObligationStatus,
    ActionType,
    RiskLevel,
)
from app.models.obligation import Obligation
from app.schemas.intelligence import (
    ObligationPredictionResponse,
    PredictionReasonItem,
    DerivedProvenanceInfo,
)
from app.services.risk_engine import RiskEngine
from app.services.graph_service import GraphService
from app.services.reconciliation_service import ReconciliationService
from app.services.intelligence.similarity_engine import SimilarityEngine
from app.services.intelligence.historical_pattern_engine import HistoricalPatternEngine


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class PredictionProvider(Protocol):
    """Protocol for pluggable predictive models (deterministic rule-based or future statistical/ML)."""

    async def predict(
        self,
        session: AsyncSession,
        obligation: Obligation,
        context: Optional[Dict[str, Any]] = None,
    ) -> ObligationPredictionResponse:
        ...


class DeterministicPredictionProvider:
    """
    Phase 12 Reference Predictor ('predictive-v1').
    Transparent, bounded weighted model synthesizing current risk, temporal urgency,
    historical owner latency, dependency health, and cross-source evidence consistency.
    """

    MODEL_VERSION = "predictive-v1"

    async def predict(
        self,
        session: AsyncSession,
        obligation: Obligation,
        context: Optional[Dict[str, Any]] = None,
    ) -> ObligationPredictionResponse:
        now = utc_now()
        reasons: List[PredictionReasonItem] = []
        base_failure_score = 0.15  # Default baseline failure probability

        # 1. Current Risk Assessment
        risk_assess = await RiskEngine.assess_obligation(session, obligation.id)
        current_risk_score = risk_assess.risk_score
        current_risk_level = risk_assess.risk_level

        # Risk contribution
        risk_contrib = current_risk_score * 0.35
        base_failure_score += risk_contrib
        if current_risk_score >= 0.50:
            reasons.append(
                PredictionReasonItem(
                    signal="CURRENT_RISK_ELEVATED",
                    impact=round(risk_contrib, 2),
                    explanation=f"Current risk evaluation is elevated ({risk_assess.risk_level.value}, score: {current_risk_score:.2f}).",
                )
            )

        # 2. Deadline Urgency & Hours Remaining
        expected_delay_hours = 0.0
        hours_remaining = None
        if obligation.deadline:
            deadline_tz = obligation.deadline
            if deadline_tz.tzinfo is None:
                deadline_tz = deadline_tz.replace(tzinfo=timezone.utc)
            hours_remaining = (deadline_tz - now).total_seconds() / 3600.0

            if hours_remaining <= 0:
                past_hrs = abs(hours_remaining)
                base_failure_score += 0.35
                expected_delay_hours += past_hrs
                reasons.append(
                    PredictionReasonItem(
                        signal="DEADLINE_PASSED",
                        impact=0.35,
                        explanation=f"Deadline has already lapsed by {past_hrs:.1f} hours without verified completion.",
                    )
                )
            elif hours_remaining <= 24.0:
                base_failure_score += 0.22
                expected_delay_hours += 8.0
                reasons.append(
                    PredictionReasonItem(
                        signal="DEADLINE_PRESSURE",
                        impact=0.22,
                        explanation=f"Imminent deadline pressure: Only {hours_remaining:.1f} hours remain.",
                    )
                )
            elif hours_remaining <= 72.0:
                base_failure_score += 0.08
                reasons.append(
                    PredictionReasonItem(
                        signal="MODERATE_TIMEFRAME",
                        impact=0.08,
                        explanation=f"Deadline is in {hours_remaining / 24.0:.1f} days.",
                    )
                )
            else:
                base_failure_score -= 0.05
                reasons.append(
                    PredictionReasonItem(
                        signal="AMPLE_LEAD_TIME",
                        impact=-0.05,
                        explanation=f"Ample buffer available ({hours_remaining / 24.0:.1f} days remaining).",
                    )
                )

        # 3. Owner Historical Latency
        owner_metrics = await HistoricalPatternEngine.get_owner_metrics(session)
        owner_metric = next((m for m in owner_metrics if m.owner.strip().lower() == obligation.owner.strip().lower()), None)

        if owner_metric and owner_metric.total_obligations >= 2:
            if owner_metric.late_rate >= 0.40 or owner_metric.avg_delay_hours >= 12.0:
                owner_impact = 0.16
                base_failure_score += owner_impact
                expected_delay_hours = max(expected_delay_hours, owner_metric.avg_delay_hours)
                reasons.append(
                    PredictionReasonItem(
                        signal="HISTORICAL_DELAY_PATTERN",
                        impact=owner_impact,
                        explanation=f"Owner historically delivers with latency (average delay: ~{owner_metric.avg_delay_hours:.1f}h).",
                    )
                )
            elif owner_metric.on_time_rate >= 0.80:
                owner_impact = -0.14
                base_failure_score += owner_impact
                reasons.append(
                    PredictionReasonItem(
                        signal="HISTORICAL_RELIABILITY",
                        impact=owner_impact,
                        explanation=f"Owner has high historical on-time fulfillment ({owner_metric.on_time_rate * 100:.0f}%).",
                    )
                )

        # 4. Dependency Health & Graph Cascade Bottlenecks
        blockers = await GraphService.get_blockers(session, obligation.id)
        blockage_likelihood = 0.0
        if blockers:
            base_failure_score += 0.25
            blockage_likelihood = 0.85
            expected_delay_hours += 14.0
            reasons.append(
                PredictionReasonItem(
                    signal="DEPENDENCY_BLOCKED",
                    impact=0.25,
                    explanation=f"Task is actively blocked by {len(blockers)} unresolved upstream prerequisite(s).",
                )
            )
        else:
            deps = await GraphService.get_dependencies(session, obligation.id)
            if deps:
                blockage_likelihood = 0.25
                base_failure_score += 0.06
                reasons.append(
                    PredictionReasonItem(
                        signal="PREREQUISITE_DEPENDENCIES_PRESENT",
                        impact=0.06,
                        explanation=f"Task depends on {len(deps)} upstream obligation(s).",
                    )
                )

        # 5. Similar Obligation Historical Outcomes
        similar_res = await SimilarityEngine.find_similar_obligations(session, obligation.id, limit=5)
        if similar_res.items:
            similar_late = sum(1 for s in similar_res.items if s.outcome_type in ["COMPLETED_LATE", "OVERDUE"])
            similar_ontime = sum(1 for s in similar_res.items if s.outcome_type in ["COMPLETED_ON_TIME", "COMPLETED_AFTER_INTERVENTION"])
            if similar_late > similar_ontime:
                sim_impact = 0.12
                base_failure_score += sim_impact
                reasons.append(
                    PredictionReasonItem(
                        signal="SIMILAR_TASK_FAILURE_RATE",
                        impact=sim_impact,
                        explanation=f"Structurally similar tasks historically missed deadlines ({similar_late} of {len(similar_res.items)} late/overdue).",
                    )
                )
            elif similar_ontime > similar_late:
                sim_impact = -0.10
                base_failure_score += sim_impact
                reasons.append(
                    PredictionReasonItem(
                        signal="SIMILAR_TASK_SUCCESS_RATE",
                        impact=sim_impact,
                        explanation=f"Structurally similar tasks historically completed on time ({similar_ontime} of {len(similar_res.items)} on time).",
                    )
                )

        # 6. Cross-Provider Reconciliation State
        rec = await ReconciliationService.get_by_obligation(session, obligation.id)
        if rec:
            if rec.status == "CONFLICTING":
                base_failure_score += 0.15
                reasons.append(
                    PredictionReasonItem(
                        signal="RECONCILIATION_CONTRADICTION",
                        impact=0.15,
                        explanation="Contradictory evidence signals detected across independent communication channels.",
                    )
                )
            elif rec.status == "CONSISTENT":
                base_failure_score -= 0.12
                reasons.append(
                    PredictionReasonItem(
                        signal="CONSISTENT_SUPPORTING_EVIDENCE",
                        impact=-0.12,
                        explanation="Multi-source supporting evidence indicates deliverable fulfillment.",
                    )
                )

        # 7. Bound probabilities and compute confidence
        failure_prob = max(0.05, min(0.95, round(base_failure_score, 2)))
        completion_prob = round(1.0 - failure_prob, 2)
        expected_delay = round(expected_delay_hours, 1)

        # Intervention likelihood
        intervention_likelihood = 0.10
        if failure_prob >= 0.50:
            intervention_likelihood += 0.40
        if blockers:
            intervention_likelihood += 0.30
        if owner_metric and owner_metric.intervention_response_rate >= 0.5:
            intervention_likelihood += 0.15
        intervention_likelihood = max(0.05, min(0.95, round(intervention_likelihood, 2)))

        # Confidence calculation based on evidence density
        data_points = 1  # Base risk
        if hours_remaining is not None:
            data_points += 1
        if owner_metric and owner_metric.total_obligations > 0:
            data_points += min(3, owner_metric.total_obligations)
        if similar_res.items:
            data_points += len(similar_res.items)
        if rec:
            data_points += 1

        confidence = max(0.25, min(0.95, round(0.30 + (data_points * 0.07), 2)))

        # Preventative Action Recommendation Formulation
        preventative_recommendation = "No preventative action required at this time."
        recommended_action_type = ActionType.NO_ACTION

        if blockers:
            preventative_recommendation = "Resolve upstream prerequisite blockers to prevent downstream delivery delay."
            recommended_action_type = ActionType.RESOLVE_DEPENDENCY
        elif rec and rec.status == "CONFLICTING":
            preventative_recommendation = "Review conflicting evidence statements across providers to adjudicate true fulfillment state."
            recommended_action_type = ActionType.REVIEW_CONFLICTING_EVIDENCE
        elif failure_prob >= 0.65 or (hours_remaining is not None and hours_remaining <= 24.0 and failure_prob >= 0.45):
            preventative_recommendation = "Initiate early proactive follow-up with task owner to mitigate anticipated delivery latency."
            recommended_action_type = ActionType.FOLLOW_UP_OWNER
        elif failure_prob >= 0.40:
            preventative_recommendation = "Monitor progress signals and verify deliverable attachments as deadline approaches."
            recommended_action_type = ActionType.START_WORK

        # Provenance summary
        provenance = DerivedProvenanceInfo(
            current_risk_evaluated=True,
            historical_outcomes_count=owner_metric.total_obligations if owner_metric else 0,
            similar_obligations_count=len(similar_res.items),
            dependency_history_count=len(blockers),
            intervention_history_count=owner_metric.completed_count if owner_metric else 0,
        )

        return ObligationPredictionResponse(
            obligation_id=obligation.id,
            action=obligation.action,
            owner=obligation.owner,
            beneficiary=obligation.beneficiary,
            status=obligation.status,
            deadline=obligation.deadline,
            model_version=self.MODEL_VERSION,
            failure_probability=failure_prob,
            completion_probability=completion_prob,
            expected_delay_hours=expected_delay,
            intervention_likelihood=intervention_likelihood,
            blockage_likelihood=round(blockage_likelihood, 2),
            confidence=confidence,
            reasons=reasons,
            preventative_recommendation=preventative_recommendation,
            recommended_action_type=recommended_action_type,
            derived_from=provenance,
            current_risk_score=current_risk_score,
            current_risk_level=current_risk_level,
            predicted_at=now,
        )


class PredictiveObligationEngine:
    """
    Predictive engine facade managing active prediction providers.
    """
    _provider: PredictionProvider = DeterministicPredictionProvider()

    @classmethod
    def set_provider(cls, provider: PredictionProvider) -> None:
        cls._provider = provider

    @classmethod
    async def predict_obligation(
        cls,
        session: AsyncSession,
        obligation_id: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> ObligationPredictionResponse:
        obligation = await session.get(Obligation, obligation_id)
        if not obligation:
            raise ValueError(f"Obligation with ID '{obligation_id}' not found.")
        return await cls._provider.predict(session, obligation, context)
