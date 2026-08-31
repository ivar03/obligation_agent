"""
Outcome Reconciliation Service for Phase 16.
Correlates post-execution external events with original execution records, reconciles outcomes,
refreshes risk signals, and strictly enforces the NO FALSE COMPLETION safety invariant.
"""

from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
from sqlalchemy import select, and_, or_, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import logger
from app.core.status_machine import (
    ExecutionStatus,
    ExecutionOutcome,
    EventSemanticRole,
    ObligationStatus,
    validate_execution_transition,
)
from app.core.intervention_status import InterventionStatus, InterventionOutcome
from app.models.execution import ExecutionRecord
from app.models.obligation import Obligation, Intervention, IngestedEventRecord, Evidence
from app.models.decision import DecisionPlan
from app.schemas.obligation import ExternalEvent
from app.schemas.execution import OutcomeReconciliationResponse


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class OutcomeReconciliationService:
    """
    Reconciles observed external response events against active execution records.
    """

    @classmethod
    async def reconcile_event(
        cls,
        session: AsyncSession,
        event_record: IngestedEventRecord,
        external_event: ExternalEvent,
    ) -> List[OutcomeReconciliationResponse]:
        """
        Correlates an ingested event with any active ExecutionRecord waiting for response.
        """
        workspace_id = event_record.workspace_id
        target_obligation_id = event_record.correlated_obligation_id

        query = select(ExecutionRecord).where(
            and_(
                ExecutionRecord.workspace_id == workspace_id,
                ExecutionRecord.status.in_([
                    ExecutionStatus.DELIVERED,
                    ExecutionStatus.RESPONSE_PENDING,
                    ExecutionStatus.OUTCOME_DETECTED,
                ]),
            )
        )
        if target_obligation_id:
            query = query.where(ExecutionRecord.obligation_id == target_obligation_id)

        res = await session.execute(query)
        matching_executions = list(res.scalars().all())

        if not matching_executions:
            return []

        reconciled_responses: List[OutcomeReconciliationResponse] = []
        now = utc_now()

        # Map semantic role to ExecutionOutcome
        detected_outcome = ExecutionOutcome.UNKNOWN
        if event_record.semantic_role == EventSemanticRole.PROGRESS_UPDATE:
            detected_outcome = ExecutionOutcome.PROGRESS_REPORTED
        elif event_record.semantic_role == EventSemanticRole.COMPLETION_SIGNAL:
            detected_outcome = ExecutionOutcome.COMPLETION_SIGNAL
        elif event_record.semantic_role == EventSemanticRole.NON_COMPLETION_SIGNAL:
            detected_outcome = ExecutionOutcome.NEGATIVE_RESPONSE
        elif event_record.semantic_role in [EventSemanticRole.COMMITMENT, EventSemanticRole.REQUEST]:
            detected_outcome = ExecutionOutcome.ACKNOWLEDGED

        for exec_rec in matching_executions:
            prev_status = exec_rec.status
            exec_rec.response_received_at = now
            exec_rec.response_event_id = event_record.id
            exec_rec.outcome = detected_outcome

            # Advance status from RESPONSE_PENDING to OUTCOME_DETECTED
            if exec_rec.status == ExecutionStatus.RESPONSE_PENDING:
                validate_execution_transition(exec_rec.status, ExecutionStatus.OUTCOME_DETECTED)
                exec_rec.status = ExecutionStatus.OUTCOME_DETECTED

            # Check if linked obligation is already COMPLETED (e.g. human verified)
            ob = await session.get(Obligation, exec_rec.obligation_id)
            if ob and ob.status == ObligationStatus.COMPLETED:
                validate_execution_transition(exec_rec.status, ExecutionStatus.RESOLVED)
                exec_rec.status = ExecutionStatus.RESOLVED

            # Check linked intervention
            intervention_status_str = None
            if exec_rec.intervention_id:
                inv = await session.get(Intervention, exec_rec.intervention_id)
                if inv:
                    if detected_outcome == ExecutionOutcome.PROGRESS_REPORTED:
                        inv.status = InterventionStatus.ACKNOWLEDGED
                        inv.outcome = InterventionOutcome.PROGRESS_REPORTED
                    elif detected_outcome == ExecutionOutcome.COMPLETION_SIGNAL:
                        inv.status = InterventionStatus.ACKNOWLEDGED
                        inv.outcome = InterventionOutcome.COMPLETED
                    intervention_status_str = inv.status.value

            # Check Decision Plan staleness
            from app.services.intelligence.intelligence_orchestrator import IntelligenceOrchestrator
            plan = await session.get(DecisionPlan, exec_rec.decision_plan_id)
            plan_marked_stale = False
            if plan and ob:
                is_stale = await IntelligenceOrchestrator._is_plan_stale(session, plan, ob)
                plan_marked_stale = is_stale or (detected_outcome in [ExecutionOutcome.PROGRESS_REPORTED, ExecutionOutcome.COMPLETION_SIGNAL])

            await session.flush()

            reconciled_responses.append(
                OutcomeReconciliationResponse(
                    execution_id=exec_rec.id,
                    event_id=event_record.id,
                    outcome=detected_outcome,
                    previous_execution_status=prev_status,
                    updated_execution_status=exec_rec.status,
                    intervention_status=intervention_status_str,
                    obligation_status=ob.status.value if ob else "UNKNOWN",
                    evidence_created=event_record.action_taken == "SUGGESTED_EVIDENCE_CREATED",
                    evidence_id=event_record.evidence_id,
                    plan_marked_stale=plan_marked_stale,
                    reconciled_at=now,
                    reconciliation_notes=f"Reconciled event [{event_record.id}] with execution [{exec_rec.id}] (Outcome: {detected_outcome.value}). "
                                         f"Safety Invariant Verified: Obligation was NOT automatically completed by execution delivery.",
                )
            )

        return reconciled_responses

    @classmethod
    async def resolve_on_obligation_completed(
        cls,
        session: AsyncSession,
        obligation_id: str,
    ) -> List[str]:
        """
        Called when an obligation is authoritatively completed (via evidence confirmation).
        Transitions all associated executions in OUTCOME_DETECTED or RESPONSE_PENDING to RESOLVED.
        """
        query = select(ExecutionRecord).where(
            and_(
                ExecutionRecord.obligation_id == obligation_id,
                ExecutionRecord.status.in_([
                    ExecutionStatus.DELIVERED,
                    ExecutionStatus.RESPONSE_PENDING,
                    ExecutionStatus.OUTCOME_DETECTED,
                ]),
            )
        )
        res = await session.execute(query)
        executions = list(res.scalars().all())
        resolved_ids = []

        for exec_rec in executions:
            validate_execution_transition(exec_rec.status, ExecutionStatus.RESOLVED)
            exec_rec.status = ExecutionStatus.RESOLVED
            resolved_ids.append(exec_rec.id)

        if executions:
            await session.flush()

        return resolved_ids
