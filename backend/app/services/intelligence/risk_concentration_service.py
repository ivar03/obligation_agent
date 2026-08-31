from datetime import datetime, timezone
from typing import List, Optional, Dict, Any, Set
from collections import defaultdict
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import logger
from app.core.status_machine import (
    ObligationStatus,
    ConcentrationType,
)
from app.models.obligation import Obligation, ObligationEdge
from app.schemas.intelligence import (
    BottleneckAnalysisResponse,
    BottleneckItem,
    RiskConcentrationResponse,
    RiskConcentrationItem,
)
from app.services.graph_service import GraphService
from app.services.risk_engine import RiskEngine


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class RiskConcentrationService:
    """
    Identifies systemic organizational bottlenecks and risk concentrations across the obligation graph.
    Uses strictly neutral, non-judgmental structural language.
    """

    @classmethod
    async def get_bottlenecks(
        cls, session: AsyncSession, workspace_id: Optional[str] = None
    ) -> BottleneckAnalysisResponse:
        # Fetch active obligations
        stmt = select(Obligation)
        if workspace_id:
            stmt = stmt.where(Obligation.workspace_id == workspace_id)
        res = await session.execute(stmt)
        all_obs = list(res.scalars().all())

        bottlenecks: List[BottleneckItem] = []

        for ob in all_obs:
            if ob.status in (ObligationStatus.COMPLETED, ObligationStatus.CANCELLED):
                continue

            summary = await GraphService.get_impact_summary(session, ob.id)
            total_downstream = summary["total_downstream_dependents_count"]
            affected_owners = summary["affected_owners"]

            if total_downstream > 0:
                # Calculate bottleneck score
                # Factors: downstream count, distinct owners, own blocked/overdue status
                status_mult = 1.5 if ob.status in (ObligationStatus.OVERDUE, ObligationStatus.BLOCKED) else 1.0
                score = round(min(1.0, (total_downstream * 0.15 + len(affected_owners) * 0.10) * status_mult), 3)

                summary_text = (
                    f"This obligation currently has significant downstream structural influence, "
                    f"connecting to {total_downstream} dependent obligation(s) across {len(affected_owners)} owner(s)."
                )

                bottlenecks.append(
                    BottleneckItem(
                        obligation_id=ob.id,
                        owner=ob.owner or "Unassigned",
                        action=ob.action,
                        status=ob.status.value if hasattr(ob.status, "value") else str(ob.status),
                        downstream_dependents_count=total_downstream,
                        affected_owners_count=len(affected_owners),
                        critical_path_involvement_count=summary["maximum_dependency_depth"],
                        bottleneck_score=score,
                        neutral_summary=summary_text,
                    )
                )

        # Sort bottlenecks by score descending
        bottlenecks.sort(key=lambda b: b.bottleneck_score, reverse=True)

        return BottleneckAnalysisResponse(
            workspace_id=workspace_id or "ws-default",
            total_bottlenecks=len(bottlenecks),
            bottlenecks=bottlenecks,
            evaluated_at=utc_now(),
        )

    @classmethod
    async def get_risk_concentrations(
        cls, session: AsyncSession, workspace_id: Optional[str] = None
    ) -> RiskConcentrationResponse:
        stmt = select(Obligation)
        if workspace_id:
            stmt = stmt.where(Obligation.workspace_id == workspace_id)
        res = await session.execute(stmt)
        all_obs = list(res.scalars().all())

        items: List[RiskConcentrationItem] = []

        # 1. Check Owner-level downstream concentrations
        owner_downstream_counts: Dict[str, Set[str]] = defaultdict(set)
        owner_obs: Dict[str, List[Obligation]] = defaultdict(list)

        for ob in all_obs:
            if ob.status not in (ObligationStatus.COMPLETED, ObligationStatus.CANCELLED) and ob.owner:
                owner_obs[ob.owner].append(ob)
                summary = await GraphService.get_impact_summary(session, ob.id)
                for d in summary["affected_owners"]:
                    if d != ob.owner:
                        owner_downstream_counts[ob.owner].add(d)

        for owner, affected_peeps in owner_downstream_counts.items():
            if len(affected_peeps) >= 2:
                items.append(
                    RiskConcentrationItem(
                        concentration_type=ConcentrationType.HIGH_IMPACT_OWNER,
                        target_id=owner,
                        target_name=owner,
                        severity="HIGH" if len(affected_peeps) >= 4 else "MEDIUM",
                        score=round(min(1.0, len(affected_peeps) * 0.20), 2),
                        description=f"Commitments by {owner} represent key inputs for {len(affected_peeps)} other team members.",
                        affected_count=len(affected_peeps),
                    )
                )

        # 2. Check Critical Prerequisites
        for ob in all_obs:
            if ob.status != ObligationStatus.COMPLETED:
                summary = await GraphService.get_impact_summary(session, ob.id)
                if summary["affected_high_risk_obligations"] >= 2:
                    items.append(
                        RiskConcentrationItem(
                            concentration_type=ConcentrationType.CRITICAL_PREREQUISITE,
                            target_id=ob.id,
                            target_name=ob.action,
                            severity="CRITICAL" if ob.status == ObligationStatus.OVERDUE else "HIGH",
                            score=round(min(1.0, summary["affected_high_risk_obligations"] * 0.30), 2),
                            description=f"Prerequisite '{ob.action}' currently blocks {summary['affected_high_risk_obligations']} high-risk downstream commitments.",
                            affected_count=summary["affected_high_risk_obligations"],
                        )
                    )

        # Sort concentrations by score descending
        items.sort(key=lambda x: x.score, reverse=True)

        return RiskConcentrationResponse(
            workspace_id=workspace_id or "ws-default",
            total_concentrations=len(items),
            items=items,
            evaluated_at=utc_now(),
        )
