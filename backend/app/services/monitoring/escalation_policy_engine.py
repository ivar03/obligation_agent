import hashlib
import uuid
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any, List, Tuple
from sqlalchemy import select, and_, or_, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import logger
from app.models.obligation import Obligation, ObligationEdge
from app.models.decision import DecisionPlan
from app.models.monitoring import MonitoringEvent, EscalationCandidate
from app.core.status_machine import (
    MonitoringSeverity,
    EscalationStatus,
    MonitoringEventType,
    TargetType,
    ObligationStatus,
)


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class EscalationPolicyEngine:
    """
    Escalation Policy Engine for Phase 17.
    Evaluates MonitoringEvents to determine if an EscalationCandidate should be surfaced to a human.
    Strictly advisory: NEVER executes autonomous operational actions.
    """

    COOLDOWN_MAP = {
        MonitoringSeverity.CRITICAL: timedelta(hours=6),
        MonitoringSeverity.HIGH: timedelta(hours=12),
        MonitoringSeverity.WARNING: timedelta(hours=24),
        MonitoringSeverity.NOTICE: timedelta(hours=48),
        MonitoringSeverity.INFO: timedelta(hours=48),
    }

    @classmethod
    def compute_escalation_dedup_key(
        cls,
        workspace_id: str,
        target_type: str,
        target_id: str,
        event_type: str,
        severity: str,
        condition_signature: str,
    ) -> str:
        raw = f"{workspace_id}:{target_type}:{target_id}:{event_type}:{severity}:{condition_signature}"
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:32]

    @classmethod
    async def evaluate_event(
        cls,
        session: AsyncSession,
        event: MonitoringEvent,
        workspace_id: str,
    ) -> Optional[EscalationCandidate]:
        """
        Determines whether the given MonitoringEvent warrants an EscalationCandidate.
        Applies deduplication and cooldown rules.
        """
        # 1. Check if severity warrants escalation
        if event.severity in (MonitoringSeverity.INFO, MonitoringSeverity.NOTICE):
            return None

        # 2. Extract context & downstream impact
        target_id = event.target_id
        target_type = event.target_type

        affected_obligations: List[str] = []
        affected_owners: List[str] = []
        blast_radius: Dict[str, Any] = {"direct_dependents": 0, "total_cascade_depth": 0}
        decision_plan_id: Optional[str] = None

        if target_type == TargetType.OBLIGATION:
            ob = await session.get(Obligation, target_id)
            if ob:
                # Query downstream blocked commitments
                downstream_stmt = (
                    select(ObligationEdge)
                    .where(
                        and_(
                            ObligationEdge.to_obligation_id == ob.id,
                            ObligationEdge.workspace_id == workspace_id,
                        )
                    )
                )
                edges = (await session.execute(downstream_stmt)).scalars().all()
                for edge in edges:
                    dep_ob = await session.get(Obligation, edge.from_obligation_id)
                    if dep_ob and dep_ob.status not in (ObligationStatus.COMPLETED, ObligationStatus.CANCELLED):
                        affected_obligations.append(dep_ob.id)
                        if dep_ob.owner and dep_ob.owner not in affected_owners:
                            affected_owners.append(dep_ob.owner)

                blast_radius = {
                    "direct_dependents": len(affected_obligations),
                    "affected_owners_count": len(affected_owners),
                }

                # Find latest decision plan
                plan_stmt = (
                    select(DecisionPlan)
                    .where(DecisionPlan.target_obligation_id == ob.id)
                    .order_by(desc(DecisionPlan.plan_version))
                    .limit(1)
                )
                plan = (await session.execute(plan_stmt)).scalars().first()
                if plan:
                    decision_plan_id = plan.id

        elif target_type == TargetType.DECISION_PLAN:
            decision_plan_id = target_id

        # 3. Determine Advisory Recommended Next Step
        recommended_next_step = cls._formulate_recommended_next_step(event, decision_plan_id, len(affected_obligations))

        # 4. Compute Deduplication Key
        condition_sig = f"sev_{event.severity.value}:{event.event_type.value}"
        dedup_key = cls.compute_escalation_dedup_key(
            workspace_id=workspace_id,
            target_type=target_type.value,
            target_id=target_id,
            event_type=event.event_type.value,
            severity=event.severity.value,
            condition_signature=condition_sig,
        )

        # 5. Check for Existing Active Escalations (Deduplication & Cooldown)
        now = utc_now()
        existing_stmt = (
            select(EscalationCandidate)
            .where(
                and_(
                    EscalationCandidate.workspace_id == workspace_id,
                    EscalationCandidate.deduplication_key == dedup_key,
                )
            )
            .order_by(desc(EscalationCandidate.created_at))
            .limit(1)
        )
        existing = (await session.execute(existing_stmt)).scalars().first()

        cooldown_window = cls.COOLDOWN_MAP.get(event.severity, timedelta(hours=12))

        if existing:
            # If open or acknowledged, suppress duplicate
            if existing.status in (EscalationStatus.OPEN, EscalationStatus.ACKNOWLEDGED):
                logger.debug(f"Suppressing duplicate open escalation for {target_id} (ID: {existing.id})")
                return None
            # If dismissed or resolved within cooldown window, suppress
            if (now - existing.created_at) < cooldown_window:
                logger.debug(f"Suppressing escalation within cooldown window ({cooldown_window}) for {target_id}")
                return None

        # 6. Create New Escalation Candidate
        escalation = EscalationCandidate(
            id=str(uuid.uuid4()),
            workspace_id=workspace_id,
            monitoring_event_id=event.id,
            target_type=target_type,
            target_id=target_id,
            severity=event.severity,
            reason=event.explanation,
            recommended_next_step=recommended_next_step,
            affected_obligations=affected_obligations,
            affected_owners=affected_owners,
            blast_radius=blast_radius,
            decision_plan_id=decision_plan_id,
            status=EscalationStatus.OPEN,
            deduplication_key=dedup_key,
            created_at=now,
        )
        session.add(escalation)
        await session.flush()
        return escalation

    @classmethod
    def _formulate_recommended_next_step(
        cls,
        event: MonitoringEvent,
        decision_plan_id: Optional[str],
        affected_count: int,
    ) -> str:
        """
        Formulates clear, neutral advisory recommendations for the human operator.
        """
        if event.event_type == MonitoringEventType.DEADLINE_BREACHED:
            if decision_plan_id:
                return "Review and execute authorized Decision Plan to rescue breached commitment."
            return "Contact commitment owner to negotiate revised deadline or unblock critical path."

        if event.event_type == MonitoringEventType.RISK_ESCALATED:
            if affected_count > 0:
                return f"Review blast radius affecting {affected_count} downstream commitments and synthesize rescue plan."
            return "Inspect root cause risk signals and consider follow-up intervention."

        if event.event_type == MonitoringEventType.EXECUTION_FAILED:
            return "Review provider delivery receipt, verify recipient routing, and consider operator retry."

        if event.event_type == MonitoringEventType.EXECUTION_RESPONSE_TIMEOUT:
            return "Follow-up response timed out (>24h). Operator manual check-in recommended."

        if event.event_type == MonitoringEventType.DECISION_PLAN_STALE:
            return "Refresh Decision Plan to calculate new strategy matching updated graph state."

        if event.event_type == MonitoringEventType.SYSTEMIC_BOTTLENECK_DETECTED:
            return f"High-priority blocker affecting {affected_count} dependent obligations. Prioritize root resolution."

        return "Operator review recommended."
