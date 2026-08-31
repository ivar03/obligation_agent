from datetime import datetime, timezone
from typing import List, Optional, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import logger
from app.core.status_machine import (
    ObligationStatus,
    ResolutionStrategyType,
    CausalFactorType,
)
from app.models.obligation import Obligation
from app.schemas.intelligence import ResolutionPlanResponse
from app.services.intelligence.root_cause_engine import RootCauseAnalysisEngine
from app.services.intelligence.impact_analysis_service import ImpactAnalysisService
from app.services.graph_service import GraphService


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class ResolutionPlanner:
    """
    Resolution Planning Engine.
    Determines the highest-leverage human action based on root-cause analysis and downstream impact.
    Strictly prefers resolving upstream root causes rather than repeatedly addressing downstream symptoms.
    """

    @classmethod
    async def plan_resolution(
        cls, session: AsyncSession, obligation_id: str, workspace_id: Optional[str] = None
    ) -> ResolutionPlanResponse:
        obligation = await session.get(Obligation, obligation_id)
        if not obligation or (workspace_id and obligation.workspace_id != workspace_id):
            raise ValueError(f"Obligation with ID '{obligation_id}' not found.")

        # 1. Perform Root Cause Analysis
        rc_analysis = await RootCauseAnalysisEngine.analyze(session, obligation_id, workspace_id=workspace_id)
        # 2. Perform Impact Analysis
        impact_analysis = await ImpactAnalysisService.analyze_impact(session, obligation_id, workspace_id=workspace_id)

        strategy: ResolutionStrategyType = ResolutionStrategyType.NO_ACTION
        target_id: str = obligation.id
        target_owner: str = obligation.owner or "Unassigned"
        target_action: str = obligation.action
        rationale: str = ""
        expected_impact: str = ""
        confidence: float = 0.85
        supporting_causes: List[str] = []
        suggested_intervention: Optional[str] = None
        alternatives: List[Dict[str, Any]] = []

        # Completed or Cancelled obligations
        if obligation.status in (ObligationStatus.COMPLETED, ObligationStatus.CANCELLED):
            return ResolutionPlanResponse(
                obligation_id=obligation.id,
                action=obligation.action,
                owner=obligation.owner,
                strategy=ResolutionStrategyType.NO_ACTION,
                target_obligation_id=obligation.id,
                target_owner=obligation.owner or "Unassigned",
                target_action=obligation.action,
                rationale="Obligation is already completed or cancelled; no operational action required.",
                expected_impact="Maintains current closed state.",
                confidence=1.0,
                supporting_causes=["Obligation is in terminal state."],
                suggested_intervention_type=None,
                alternative_strategies=[],
                evaluated_at=utc_now(),
            )

        # Strategy 1: Upstream Root Blocker exists -> Target the root prerequisite (Upstream-First Principle)
        if rc_analysis.upstream_causes:
            top_upstream = rc_analysis.upstream_causes[0]
            if top_upstream.target_obligation_id and top_upstream.target_obligation_id != obligation.id:
                strategy = ResolutionStrategyType.FOLLOW_UP_ROOT_OWNER
                target_id = top_upstream.target_obligation_id
                target_owner = top_upstream.target_owner or "Prerequisite Owner"
                target_action = top_upstream.target_action or "Upstream Prerequisite"
                confidence = top_upstream.confidence
                supporting_causes.append(top_upstream.description)

                rationale = (
                    f"Prioritize resolving root prerequisite '{target_action}' owned by {target_owner}. "
                    f"Acting upstream cures the root bottleneck instead of symptomatically chasing downstream blocks."
                )

                unblock_count = 1 + impact_analysis.total_downstream_dependents_count
                expected_impact = (
                    f"Unblocks '{obligation.action}' and {impact_analysis.total_downstream_dependents_count} "
                    f"downstream dependent obligation(s) across {len(impact_analysis.affected_owners)} owner(s)."
                )
                suggested_intervention = "FOLLOW_UP"

                # Add alternative: direct blocker review
                alternatives.append({
                    "strategy": ResolutionStrategyType.REVIEW_DEPENDENCY.value,
                    "target_obligation_id": obligation.id,
                    "target_owner": obligation.owner,
                    "description": "Examine if the dependency link can be decoupled or re-routed.",
                })

        # Strategy 2: Direct Blocker on Target
        elif rc_analysis.direct_causes and any("Prerequisite" in dc.description for dc in rc_analysis.direct_causes):
            direct_blocker_cause = next(dc for dc in rc_analysis.direct_causes if "Prerequisite" in dc.description)
            strategy = ResolutionStrategyType.RESOLVE_ROOT_BLOCKER
            target_id = direct_blocker_cause.target_obligation_id or obligation.id
            target_owner = direct_blocker_cause.target_owner or obligation.owner or "Blocker Owner"
            target_action = direct_blocker_cause.target_action or "Direct Blocker"
            confidence = direct_blocker_cause.confidence
            supporting_causes.append(direct_blocker_cause.description)

            rationale = f"Direct prerequisite '{target_action}' by {target_owner} is currently blocking execution."
            expected_impact = f"Satisfies blocker and transitions '{obligation.action}' to CONFIRMED / IN_PROGRESS."
            suggested_intervention = "FOLLOW_UP"

        # Strategy 3: Unassigned Owner
        elif not obligation.owner or obligation.owner.lower() in ("unassigned", "unknown", "tbd", ""):
            strategy = ResolutionStrategyType.ASSIGN_OWNER
            target_id = obligation.id
            target_owner = "Unassigned"
            target_action = obligation.action
            confidence = 0.95
            supporting_causes.append("Obligation lacks an assigned duty bearer.")

            rationale = "No individual is accountable for delivering this commitment."
            expected_impact = "Establishes clear ownership and accountability, reducing ambiguity risk."
            suggested_intervention = "ASSIGNMENT_REQUEST"

        # Strategy 4: Overdue Target Deadline
        elif obligation.status == ObligationStatus.OVERDUE:
            strategy = ResolutionStrategyType.CLARIFY_DEADLINE
            target_id = obligation.id
            target_owner = obligation.owner or "Owner"
            target_action = obligation.action
            confidence = 0.90
            supporting_causes.append(f"Target deadline {obligation.deadline} has passed.")

            rationale = f"Commitment is past due. Follow up with {target_owner} to renegotiate or confirm delivery status."
            expected_impact = "Restores schedule fidelity and updates downstream stakeholders."
            suggested_intervention = "DEADLINE_EXTENSION_REQUEST"

        # Strategy 5: Missing Evidence
        elif rc_analysis.contributing_factors and any("evidence" in cf.description.lower() for cf in rc_analysis.contributing_factors):
            strategy = ResolutionStrategyType.REQUEST_MISSING_EVIDENCE
            target_id = obligation.id
            target_owner = obligation.owner or "Owner"
            target_action = obligation.action
            confidence = 0.80
            supporting_causes.append("No progress or completion evidence detected.")

            rationale = f"Work may be completed or in progress but unrecorded in the system."
            expected_impact = "Confirms actual physical state and enables automated or human completion."
            suggested_intervention = "EVIDENCE_REQUEST"

        # Strategy 6: Conditional triggers pending
        elif obligation.conditions:
            strategy = ResolutionStrategyType.WAIT_FOR_CONDITION
            target_id = obligation.id
            target_owner = obligation.owner or "Owner"
            target_action = obligation.action
            confidence = 0.75
            supporting_causes.append(f"Subject to condition: {obligation.conditions}")

            rationale = f"Awaiting external operational condition: '{obligation.conditions}'."
            expected_impact = "Monitors condition triggers without premature harassment of owner."
            suggested_intervention = None

        else:
            strategy = ResolutionStrategyType.NO_ACTION
            target_id = obligation.id
            target_owner = obligation.owner or "Owner"
            target_action = obligation.action
            confidence = 0.70
            rationale = "Obligation is operating within normal parameters."
            expected_impact = "Continues normal tracking."
            suggested_intervention = None

        return ResolutionPlanResponse(
            obligation_id=obligation.id,
            action=obligation.action,
            owner=obligation.owner,
            strategy=strategy,
            target_obligation_id=target_id,
            target_owner=target_owner,
            target_action=target_action,
            rationale=rationale,
            expected_impact=expected_impact,
            confidence=round(confidence, 2),
            supporting_causes=supporting_causes or [rc_analysis.primary_root_cause],
            suggested_intervention_type=suggested_intervention,
            alternative_strategies=alternatives,
            evaluated_at=utc_now(),
        )
