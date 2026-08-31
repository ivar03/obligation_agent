from datetime import datetime, timezone
from typing import List, Optional, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import logger
from app.core.status_machine import ObligationStatus
from app.models.obligation import Obligation
from app.schemas.intelligence import ImpactAnalysisResponse
from app.services.graph_service import GraphService
from app.services.risk_engine import RiskEngine


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class ImpactAnalysisService:
    """
    Computes the blast radius and downstream organizational impact of an obligation.
    Calculates deterministic, explainable impact scores bounded to [0.0, 1.0].
    """

    @classmethod
    async def analyze_impact(
        cls, session: AsyncSession, obligation_id: str, workspace_id: Optional[str] = None
    ) -> ImpactAnalysisResponse:
        obligation = await session.get(Obligation, obligation_id)
        if not obligation or (workspace_id and obligation.workspace_id != workspace_id):
            raise ValueError(f"Obligation with ID '{obligation_id}' not found.")

        # 1. Traversal metrics
        summary = await GraphService.get_impact_summary(session, obligation_id)
        downstream = await GraphService.get_downstream_impact(session, obligation_id)

        direct_count = summary["direct_dependents_count"]
        total_downstream_count = summary["total_downstream_dependents_count"]
        max_depth = summary["maximum_dependency_depth"]
        affected_owners = summary["affected_owners"]
        affected_deadlines = summary["affected_deadlines"]
        affected_high_risk = summary["affected_high_risk_obligations"]

        # Critical path calculation from this node downstream
        critical_path_len = max_depth

        # 2. Deterministic, bounded impact score calculation:
        # - Downstream count normalized (cap at 10 for full 1.0): weight 0.35
        downstream_norm = min(1.0, total_downstream_count / 10.0)
        # - Dependency depth normalized (cap at 5 for full 1.0): weight 0.25
        depth_norm = min(1.0, max_depth / 5.0)
        # - High risk downstream ratio: weight 0.20
        high_risk_norm = min(1.0, affected_high_risk / max(1, total_downstream_count)) if total_downstream_count > 0 else 0.0
        # - Affected owners fan-out (cap at 5 owners for full 1.0): weight 0.10
        fan_out_norm = min(1.0, len(affected_owners) / 5.0)
        # - Target obligation's own risk or deadline urgency: weight 0.10
        target_risk = 0.0
        if obligation.status in (ObligationStatus.OVERDUE, ObligationStatus.BLOCKED):
            target_risk = 1.0
        elif obligation.status == ObligationStatus.IN_PROGRESS:
            target_risk = 0.5

        raw_score = (
            (0.35 * downstream_norm)
            + (0.25 * depth_norm)
            + (0.20 * high_risk_norm)
            + (0.10 * fan_out_norm)
            + (0.10 * target_risk)
        )

        impact_score = max(0.0, min(1.0, round(raw_score, 3)))

        # Impact level classification
        if impact_score >= 0.75:
            impact_level = "CRITICAL"
        elif impact_score >= 0.50:
            impact_level = "HIGH"
        elif impact_score >= 0.25:
            impact_level = "MEDIUM"
        else:
            impact_level = "LOW"

        score_breakdown = {
            "downstream_count_component": round(0.35 * downstream_norm, 3),
            "depth_component": round(0.25 * depth_norm, 3),
            "high_risk_dependents_component": round(0.20 * high_risk_norm, 3),
            "owner_fan_out_component": round(0.10 * fan_out_norm, 3),
            "target_state_component": round(0.10 * target_risk, 3),
            "raw_total": round(raw_score, 3),
        }

        return ImpactAnalysisResponse(
            obligation_id=obligation.id,
            action=obligation.action,
            owner=obligation.owner,
            status=obligation.status.value if hasattr(obligation.status, "value") else str(obligation.status),
            direct_dependents_count=direct_count,
            total_downstream_dependents_count=total_downstream_count,
            maximum_dependency_depth=max_depth,
            critical_path_length=critical_path_len,
            affected_owners=affected_owners,
            affected_deadlines=affected_deadlines,
            affected_high_risk_obligations=affected_high_risk,
            impact_score=impact_score,
            impact_level=impact_level,
            score_breakdown=score_breakdown,
            downstream_items=summary["downstream_items"],
            evaluated_at=utc_now(),
        )
