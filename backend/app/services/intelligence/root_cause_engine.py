from datetime import datetime, timezone
from typing import List, Optional, Dict, Any, Tuple
from sqlalchemy import select, and_, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import logger
from app.core.status_machine import (
    ObligationStatus,
    ObligationType,
    RiskLevel,
    CausalFactorType,
    ResolutionStrategyType,
)
from app.models.obligation import Obligation, Evidence, Intervention, ReconciliationRecord
from app.schemas.intelligence import (
    RootCauseAnalysisResponse,
    CausalFactorItem,
)
from app.services.graph_service import GraphService, is_overdue_by_date
from app.services.risk_engine import RiskEngine


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class RootCauseAnalysisEngine:
    """
    Deterministic, explainable root-cause analysis engine.
    Analyzes an obligation to determine its true causal origin, distinguishing between:
    - DIRECT_CAUSE: Immediate blockers, direct deadline failure, ambiguous owner on target.
    - UPSTREAM_CAUSE: Multi-hop prerequisite failures causing domino effects.
    - CONTRIBUTING_FACTOR: Missing evidence, unreviewed conflicts, high complexity.
    - UNCERTAINTY: Ambiguous causality, lack of history, conditional triggers.
    """

    @classmethod
    async def analyze(
        cls, session: AsyncSession, obligation_id: str, workspace_id: Optional[str] = None
    ) -> RootCauseAnalysisResponse:
        obligation = await session.get(Obligation, obligation_id)
        if not obligation or (workspace_id and obligation.workspace_id != workspace_id):
            raise ValueError(f"Obligation with ID '{obligation_id}' not found.")

        # 1. Fetch risk assessment for direct signals
        risk_assessment = await RiskEngine.assess_obligation(session, obligation_id)
        current_risk_score = risk_assessment.risk_score if risk_assessment else 0.0

        # 2. Graph inspection
        direct_blockers = await GraphService.get_blockers(session, obligation_id)
        upstream_chain = await GraphService.get_upstream_chain(session, obligation_id)
        root_blockers = await GraphService.get_root_blockers(session, obligation_id)
        downstream_impact = await GraphService.get_downstream_impact(session, obligation_id)

        # 3. Evidence inspection
        ev_stmt = (
            select(Evidence)
            .where(Evidence.obligation_id == obligation_id)
            .order_by(desc(Evidence.observed_at))
        )
        ev_res = await session.execute(ev_stmt)
        evidence_list = list(ev_res.scalars().all())

        # 4. Interventions inspection
        inv_stmt = (
            select(Intervention)
            .where(Intervention.obligation_id == obligation_id)
            .order_by(desc(Intervention.created_at))
        )
        inv_res = await session.execute(inv_stmt)
        interventions = list(inv_res.scalars().all())

        # 5. Build causal factor buckets
        direct_causes: List[CausalFactorItem] = []
        upstream_causes: List[CausalFactorItem] = []
        contributing_factors: List[CausalFactorItem] = []
        uncertainties: List[CausalFactorItem] = []

        all_evidence_refs: List[str] = [e.id for e in evidence_list]
        all_event_refs: List[str] = []
        for e in evidence_list:
            if hasattr(e, "event_id") and e.event_id:
                all_event_refs.append(str(e.event_id))

        # Check direct state causes
        is_overdue = obligation.status == ObligationStatus.OVERDUE or is_overdue_by_date(obligation)
        is_blocked = obligation.status == ObligationStatus.BLOCKED or len(direct_blockers) > 0

        # Ownership check
        if not obligation.owner or obligation.owner.lower() in ("unassigned", "unknown", "tbd", ""):
            direct_causes.append(
                CausalFactorItem(
                    factor_type=CausalFactorType.DIRECT_CAUSE,
                    description=f"Obligation '{obligation.action}' lacks an assigned duty bearer (owner).",
                    target_obligation_id=obligation.id,
                    target_owner=obligation.owner or "Unassigned",
                    target_action=obligation.action,
                    confidence=0.95,
                    severity="HIGH",
                )
            )

        # Deadline pressure direct cause
        if is_overdue:
            direct_causes.append(
                CausalFactorItem(
                    factor_type=CausalFactorType.DIRECT_CAUSE,
                    description=f"Target obligation deadline has passed ({obligation.deadline.isoformat() if obligation.deadline else 'Past'}).",
                    target_obligation_id=obligation.id,
                    target_owner=obligation.owner,
                    target_action=obligation.action,
                    confidence=0.99,
                    severity="CRITICAL",
                )
            )

        # Direct blockers check
        for blk in direct_blockers:
            direct_causes.append(
                CausalFactorItem(
                    factor_type=CausalFactorType.DIRECT_CAUSE,
                    description=f"Direct prerequisite by {blk.owner} ('{blk.action}') is {blk.status.value if hasattr(blk.status, 'value') else blk.status}: {blk.reason}",
                    target_obligation_id=blk.obligation_id,
                    target_owner=blk.owner,
                    target_action=blk.action,
                    confidence=0.92,
                    severity="HIGH" if blk.status != ObligationStatus.OVERDUE else "CRITICAL",
                )
            )

        # Upstream Multi-Hop Root Causes
        # Check root blockers (the leaf origins of blockage)
        for rb in root_blockers:
            rb_obj: Obligation = rb["obligation"]
            rb_dist = rb["hop_distance"]
            if rb_dist > 1 or rb_obj.id not in [b.obligation_id for b in direct_blockers]:
                # Multi-hop upstream root cause
                upstream_causes.append(
                    CausalFactorItem(
                        factor_type=CausalFactorType.UPSTREAM_CAUSE,
                        description=(
                            f"Upstream root blocker ({rb_dist} hops away): {rb_obj.owner}'s obligation "
                            f"'{rb_obj.action}' is {rb_obj.status.value if hasattr(rb_obj.status, 'value') else rb_obj.status}."
                        ),
                        target_obligation_id=rb_obj.id,
                        target_owner=rb_obj.owner,
                        target_action=rb_obj.action,
                        confidence=0.88,
                        severity="CRITICAL" if rb_obj.status == ObligationStatus.OVERDUE else "HIGH",
                    )
                )

        # If no multi-hop root blockers but direct blockers exist, direct blockers are the roots
        if direct_blockers and not upstream_causes:
            for blk in direct_blockers:
                if blk.status == ObligationStatus.OVERDUE:
                    upstream_causes.append(
                        CausalFactorItem(
                            factor_type=CausalFactorType.UPSTREAM_CAUSE,
                            description=f"Prerequisite '{blk.action}' by {blk.owner} is overdue, creating direct blocker cascade.",
                            target_obligation_id=blk.obligation_id,
                            target_owner=blk.owner,
                            target_action=blk.action,
                            confidence=0.94,
                            severity="CRITICAL",
                        )
                    )

        # Contributing Factors
        # 1. Missing evidence when IN_PROGRESS / CONFIRMED
        if not evidence_list and obligation.status in (ObligationStatus.IN_PROGRESS, ObligationStatus.CONFIRMED):
            contributing_factors.append(
                CausalFactorItem(
                    factor_type=CausalFactorType.CONTRIBUTING_FACTOR,
                    description="No progress or completion evidence has been recorded for this obligation.",
                    target_obligation_id=obligation.id,
                    target_owner=obligation.owner,
                    target_action=obligation.action,
                    confidence=0.80,
                    severity="MEDIUM",
                )
            )

        # 2. Interventions pending or repeated
        if interventions:
            unresolved_inv = [i for i in interventions if i.status not in ("RESOLVED", "CANCELLED")]
            if unresolved_inv:
                contributing_factors.append(
                    CausalFactorItem(
                        factor_type=CausalFactorType.CONTRIBUTING_FACTOR,
                        description=f"There are {len(unresolved_inv)} active/unresolved human intervention(s) pending on this obligation.",
                        target_obligation_id=obligation.id,
                        target_owner=obligation.owner,
                        target_action=obligation.action,
                        confidence=0.85,
                        severity="MEDIUM",
                    )
                )

        # 3. Conditional triggers
        if obligation.conditions:
            contributing_factors.append(
                CausalFactorItem(
                    factor_type=CausalFactorType.CONTRIBUTING_FACTOR,
                    description=f"Obligation is subject to condition: {obligation.conditions}",
                    target_obligation_id=obligation.id,
                    target_owner=obligation.owner,
                    confidence=0.75,
                    severity="LOW",
                )
            )

        # Uncertainties
        if not direct_causes and not upstream_causes and obligation.status not in (ObligationStatus.COMPLETED, ObligationStatus.CANCELLED):
            uncertainties.append(
                CausalFactorItem(
                    factor_type=CausalFactorType.UNCERTAINTY,
                    description="No decisive blockers or deadline breaches found; risk may stem from external unmonitored workflows.",
                    target_obligation_id=obligation.id,
                    confidence=0.40,
                    severity="LOW",
                )
            )

        # Deduce primary root cause and overall explanation
        primary_root_cause: str = ""
        root_cause_type: CausalFactorType = CausalFactorType.UNCERTAINTY
        recommended_res: Optional[str] = None
        confidence: float = 0.85

        if upstream_causes:
            top_upstream = upstream_causes[0]
            primary_root_cause = f"Upstream prerequisite '{top_upstream.target_action}' by {top_upstream.target_owner} is unresolved."
            root_cause_type = CausalFactorType.UPSTREAM_CAUSE
            confidence = top_upstream.confidence
            recommended_res = f"Follow up with {top_upstream.target_owner} to resolve prerequisite '{top_upstream.target_action}'."
            overall_explanation = (
                f"Obligation '{obligation.action}' is impeded by an upstream root cause: "
                f"{top_upstream.description} Resolving this root dependency will clear the blocking cascade."
            )
        elif direct_causes:
            top_direct = direct_causes[0]
            primary_root_cause = top_direct.description
            root_cause_type = CausalFactorType.DIRECT_CAUSE
            confidence = top_direct.confidence
            if "lacks an assigned" in top_direct.description:
                recommended_res = "Assign an authoritative duty bearer (owner) to take responsibility for this obligation."
            elif is_overdue:
                recommended_res = f"Follow up with {obligation.owner} immediately regarding overdue deadline."
            else:
                recommended_res = f"Resolve direct blocker on obligation."
            overall_explanation = f"Obligation '{obligation.action}' is directly at risk: {top_direct.description}"
        elif contributing_factors:
            top_contrib = contributing_factors[0]
            primary_root_cause = top_contrib.description
            root_cause_type = CausalFactorType.CONTRIBUTING_FACTOR
            confidence = 0.70
            recommended_res = "Request progress evidence or review pending operational conditions."
            overall_explanation = f"Obligation '{obligation.action}' has contributing risk factors: {top_contrib.description}"
        else:
            primary_root_cause = "No critical risk or blocking failure identified."
            root_cause_type = CausalFactorType.UNCERTAINTY
            confidence = 0.60
            recommended_res = "No immediate resolution required; obligation is healthy or completed."
            overall_explanation = f"Obligation '{obligation.action}' is currently progressing normally with no blocking root causes."

        # Compute confidence level
        if confidence >= 0.80:
            confidence_level = "HIGH"
        elif confidence >= 0.50:
            confidence_level = "MEDIUM"
        else:
            confidence_level = "LOW"

        # Construct dependency path from root to current
        dependency_path: List[str] = []
        if root_blockers:
            first_root = root_blockers[0]
            if "path" in first_root:
                dependency_path = list(reversed(first_root["path"]))

        if not dependency_path and upstream_chain:
            dependency_path = [u["obligation"].id for u in upstream_chain] + [obligation.id]

        if not dependency_path:
            dependency_path = [obligation.id]

        affected_list = [
            {
                "obligation_id": d["obligation"].id,
                "action": d["obligation"].action,
                "owner": d["obligation"].owner,
                "status": d["obligation"].status.value if hasattr(d["obligation"].status, "value") else str(d["obligation"].status),
                "hop_distance": d["hop_distance"],
            }
            for d in downstream_impact
        ]

        return RootCauseAnalysisResponse(
            obligation_id=obligation.id,
            action=obligation.action,
            owner=obligation.owner,
            status=obligation.status.value if hasattr(obligation.status, "value") else str(obligation.status),
            overall_explanation=overall_explanation,
            primary_root_cause=primary_root_cause,
            root_cause_type=root_cause_type,
            confidence=round(confidence, 2),
            confidence_level=confidence_level,
            direct_causes=direct_causes,
            upstream_causes=upstream_causes,
            contributing_factors=contributing_factors,
            uncertainties=uncertainties,
            affected_obligations=affected_list,
            dependency_path=dependency_path,
            evidence_refs=all_evidence_refs,
            event_refs=all_event_refs,
            recommended_resolution=recommended_res,
            evaluated_at=utc_now(),
        )
