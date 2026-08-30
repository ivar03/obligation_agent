from datetime import datetime, timedelta, timezone
from typing import Optional, List, Dict, Any
from sqlalchemy import select, and_, or_, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import logger
from app.core.status_machine import ObligationStatus, ObligationType, RiskLevel
from app.core.intervention_status import (
    InterventionType,
    InterventionStatus,
    InterventionOutcome,
)
from app.models.obligation import Obligation, Intervention, Evidence
from app.schemas.obligation import RiskAssessmentResponse, BlockerDetail
from app.services.message_generator import MessageGenerator


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class InterventionPlanner:
    """
    Plans, prepares, and deduplicates human-controlled interventions
    grounded in risk assessment, graph dependencies, and evidence state.
    """

    COOLDOWN_HOURS = 24
    MAX_INTERVENTION_CHAIN_DEPTH = 3

    @classmethod
    async def plan_intervention(
        cls,
        session: AsyncSession,
        obligation_id: str,
        force: bool = False,
    ) -> Optional[Intervention]:
        from app.services.graph_service import GraphService
        from app.services.risk_engine import RiskEngine

        now = utc_now()

        # 1. Fetch Obligation
        obligation = await session.get(Obligation, obligation_id)
        if not obligation:
            return None

        # 2. Resolved obligations need no intervention
        if obligation.status in [ObligationStatus.COMPLETED, ObligationStatus.CANCELLED]:
            return None

        # 3. Fetch Risk Assessment, Graph Context, and Evidence
        risk_assessment = await RiskEngine.assess_obligation(session, obligation_id)
        blockers = await GraphService.get_blockers(session, obligation_id)
        dependents = await GraphService.get_dependents(session, obligation_id)

        ev_stmt = (
            select(Evidence)
            .where(Evidence.obligation_id == obligation_id)
            .order_by(desc(Evidence.observed_at))
            .limit(5)
        )
        ev_res = await session.execute(ev_stmt)
        recent_evidence = list(ev_res.scalars().all())

        # 4. If obligation is LOW risk and healthy, and not forced and not blocked: check if specific actionable signals exist
        active_signals = {s.signal_type for s in (risk_assessment.signals if risk_assessment else [])}
        actionable_signals = {
            "CONFLICTING_EVIDENCE",
            "COMPLETION_CANDIDATE_DETECTED",
            "OWNERSHIP_UNCERTAINTY",
            "DEADLINE_PASSED",
            "NEGATIVE_EVIDENCE",
        }
        if (
            not force
            and risk_assessment
            and risk_assessment.risk_level == RiskLevel.LOW
            and obligation.status not in [ObligationStatus.OVERDUE, ObligationStatus.BLOCKED]
            and not blockers
            and not (active_signals & actionable_signals)
        ):
            return None

        # 5. Check active duplicate and cooldown (Steps 20 & 21)
        if not force:
            active_stmt = (
                select(Intervention)
                .where(
                    and_(
                        Intervention.obligation_id == obligation_id,
                        Intervention.status.in_([
                            InterventionStatus.PENDING_REVIEW,
                            InterventionStatus.APPROVED,
                            InterventionStatus.SCHEDULED,
                            InterventionStatus.READY_TO_EXECUTE,
                        ]),
                    )
                )
                .order_by(desc(Intervention.created_at))
            )
            active_res = await session.execute(active_stmt)
            existing_active = active_res.scalar_one_or_none()
            if existing_active:
                logger.info(
                    f"InterventionPlanner: Returning existing active intervention [{existing_active.id}] for obligation [{obligation_id}]."
                )
                return existing_active

            # Cooldown check for recently executed intervention
            cooldown_stmt = (
                select(Intervention)
                .where(
                    and_(
                        Intervention.obligation_id == obligation_id,
                        Intervention.cooldown_until > now,
                        Intervention.status.notin_([InterventionStatus.CANCELLED, InterventionStatus.RESOLVED]),
                    )
                )
                .order_by(desc(Intervention.created_at))
            )
            cooldown_res = await session.execute(cooldown_stmt)
            in_cooldown = cooldown_res.scalar_one_or_none()
            if in_cooldown:
                logger.info(
                    f"InterventionPlanner: Obligation [{obligation_id}] is in cooldown until [{in_cooldown.cooldown_until}]."
                )
                return in_cooldown

        # 6. Determine Intervention Type & Targets (Step 6)
        signals = {s.signal_type for s in (risk_assessment.signals if risk_assessment else [])}
        
        target_owner = obligation.owner
        target_beneficiary = obligation.beneficiary
        urgency = risk_assessment.risk_level.value if risk_assessment else "MEDIUM"
        rationale = ""
        intervention_type = InterventionType.FOLLOW_UP_OWNER

        if obligation.status == ObligationStatus.BLOCKED or blockers:
            intervention_type = InterventionType.RESOLVE_DEPENDENCY
            if blockers:
                b = blockers[0]
                target_owner = b.owner
                target_beneficiary = obligation.owner
                rationale = f"Obligation is blocked by {b.owner}'s prerequisite '{b.action}'."
            else:
                rationale = "Obligation is marked BLOCKED and requires dependency resolution."
        elif "OWNERSHIP_UNCERTAINTY" in signals:
            intervention_type = InterventionType.ASSIGN_OWNER
            target_owner = "Unassigned Team Lead"
            rationale = f"Ownership for '{obligation.action}' is ambiguous ('{obligation.owner}'); requires single accountable owner."
        elif "CONFLICTING_EVIDENCE" in signals:
            intervention_type = InterventionType.REVIEW_EVIDENCE
            target_owner = obligation.beneficiary
            rationale = "Conflicting evidence observations recorded requiring human review."
        elif "COMPLETION_CANDIDATE_DETECTED" in signals:
            intervention_type = InterventionType.REVIEW_EVIDENCE
            target_owner = obligation.beneficiary
            rationale = "Suggested completion evidence detected awaiting human confirmation."
        elif "CONDITIONAL_TRIGGER_WAITING" in signals:
            intervention_type = InterventionType.MONITOR_CONDITION
            target_owner = obligation.owner
            rationale = f"Obligation is waiting on prerequisite condition: '{obligation.conditions}'."
        elif "DEADLINE_AMBIGUOUS" in signals:
            intervention_type = InterventionType.CLARIFY_DEADLINE
            target_owner = obligation.owner
            rationale = "No explicit deadline set; timeline requires clarification."
        elif "DEADLINE_PASSED" in signals or obligation.status == ObligationStatus.OVERDUE:
            intervention_type = InterventionType.FOLLOW_UP_OWNER
            target_owner = obligation.owner
            rationale = "Deadline has passed without fulfillment."
        elif "NO_PROGRESS" in signals and "DEADLINE_PROXIMITY" in signals:
            intervention_type = InterventionType.REQUEST_STATUS_UPDATE
            target_owner = obligation.owner
            rationale = "Deadline is approaching with no recorded progress evidence."
        else:
            intervention_type = InterventionType.FOLLOW_UP_OWNER
            target_owner = obligation.owner
            rationale = "Proactive check-in recommended to ensure commitment remains on track."

        # Compute Title
        title = f"{intervention_type.replace('_', ' ').title()}: {target_owner} ({obligation.action[:40]}...)"

        # 7. Generate Deterministic Draft (Steps 7 & 8)
        message_draft = MessageGenerator.generate_draft(
            obligation=obligation,
            intervention_type=intervention_type,
            target_owner=target_owner,
            target_beneficiary=target_beneficiary,
            blockers=blockers,
            dependents=dependents,
            risk_assessment=risk_assessment,
        )

        # 8. Compute Chain Depth & Escalation (Step 22 & 38)
        past_stmt = (
            select(Intervention)
            .where(Intervention.obligation_id == obligation_id)
            .order_by(desc(Intervention.created_at))
        )
        past_res = await session.execute(past_stmt)
        past_interventions = list(past_res.scalars().all())
        chain_depth = min(cls.MAX_INTERVENTION_CHAIN_DEPTH, len(past_interventions) + 1)

        if chain_depth >= 3:
            rationale += " (Repeated follow-up chain; consider escalating to leadership if no response)."

        # 9. Assemble Context Packet (Step 9)
        context_packet = {
            "obligation": {
                "id": obligation.id,
                "owner": obligation.owner,
                "beneficiary": obligation.beneficiary,
                "action": obligation.action,
                "status": obligation.status.value,
                "deadline": obligation.deadline.isoformat() if obligation.deadline else None,
                "conditions": obligation.conditions,
            },
            "risk": {
                "score": risk_assessment.risk_score if risk_assessment else 0.5,
                "level": risk_assessment.risk_level.value if risk_assessment else "MEDIUM",
                "priority_score": risk_assessment.priority_score if risk_assessment else 0.5,
                "breakdown": risk_assessment.breakdown.model_dump() if risk_assessment else {},
                "reasons": risk_assessment.reasons if risk_assessment else [],
            },
            "blockers": [b.model_dump() for b in blockers],
            "dependents_count": len(dependents),
            "recent_evidence_count": len(recent_evidence),
            "chain_depth": chain_depth,
        }

        # 10. Create Intervention Record
        cooldown_until = now + timedelta(hours=cls.COOLDOWN_HOURS)

        intervention = Intervention(
            workspace_id=obligation.workspace_id,
            obligation_id=obligation.id,
            intervention_type=intervention_type,
            target_owner=target_owner,
            target_beneficiary=target_beneficiary,
            title=title,
            rationale=rationale,
            message_draft=message_draft,
            approved_message=message_draft, # default approved text to draft
            context_data=context_packet,
            urgency=urgency,
            status=InterventionStatus.PENDING_REVIEW,
            outcome=None,
            requires_approval=True,
            approved_at=None,
            approved_by=None,
            scheduled_for=None,
            executed_at=None,
            execution_reference=None,
            execution_mode="MOCK_DEMO",
            follow_up_at=now + timedelta(hours=48),
            cooldown_until=cooldown_until,
            chain_depth=chain_depth,
            audit_trail=[{
                "event": "DRAFT_GENERATED",
                "actor": "SYSTEM",
                "timestamp": now.isoformat(),
                "details": {
                    "intervention_type": intervention_type.value,
                    "urgency": urgency,
                    "risk_score": risk_assessment.risk_score if risk_assessment else 0.5,
                }
            }],
        )

        session.add(intervention)
        await session.flush()
        await session.refresh(intervention)

        logger.info(
            f"InterventionPlanned: Created intervention [{intervention.id}] ({intervention_type.value}) for obligation [{obligation_id}]."
        )
        return intervention
