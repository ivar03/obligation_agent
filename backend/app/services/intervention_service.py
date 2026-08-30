from datetime import datetime, timedelta, timezone
from typing import Optional, List, Dict, Any
from sqlalchemy import select, and_, or_, desc, func
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException, status

from app.core.logging import logger
from app.core.status_machine import ObligationStatus
from app.core.intervention_status import (
    InterventionType,
    InterventionStatus,
    InterventionOutcome,
    validate_intervention_transition,
    InvalidInterventionStatusTransitionError,
)
from app.models.obligation import Obligation, Intervention
from app.schemas.intervention import (
    InterventionCreate,
    InterventionUpdate,
    InterventionResponse,
    InterventionListResponse,
    InterventionQueueResponse,
    InterventionApproveRequest,
    InterventionScheduleRequest,
    InterventionOutcomeRequest,
)
from app.services.intervention_planner import InterventionPlanner
from app.services.intervention_executor import DevMockInterventionExecutor, BaseInterventionExecutor


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def to_intervention_dto(intervention: Intervention) -> InterventionResponse:
    return InterventionResponse.model_validate(intervention)


class InterventionService:

    @staticmethod
    async def plan(
        session: AsyncSession, obligation_id: str, force: bool = False
    ) -> Optional[InterventionResponse]:
        intervention = await InterventionPlanner.plan_intervention(
            session=session, obligation_id=obligation_id, force=force
        )
        if not intervention:
            return None
        return to_intervention_dto(intervention)

    @staticmethod
    async def get_by_id(
        session: AsyncSession, intervention_id: str
    ) -> Optional[InterventionResponse]:
        query = select(Intervention).where(Intervention.id == intervention_id)
        result = await session.execute(query)
        intervention = result.scalar_one_or_none()
        if not intervention:
            return None
        return to_intervention_dto(intervention)

    @staticmethod
    async def list_all(
        session: AsyncSession,
        status: Optional[InterventionStatus] = None,
        intervention_type: Optional[InterventionType] = None,
        obligation_id: Optional[str] = None,
        urgency: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> InterventionListResponse:
        query = select(Intervention)

        if status:
            query = query.where(Intervention.status == status)
        if intervention_type:
            query = query.where(Intervention.intervention_type == intervention_type)
        if obligation_id:
            query = query.where(Intervention.obligation_id == obligation_id)
        if urgency:
            query = query.where(Intervention.urgency == urgency)

        query = query.order_by(desc(Intervention.created_at))
        result = await session.execute(query)
        items = list(result.scalars().all())

        dtos = [to_intervention_dto(it) for it in items]
        total = len(dtos)
        paginated = dtos[offset: offset + limit]

        return InterventionListResponse(items=paginated, total=total)

    @staticmethod
    async def get_queue(session: AsyncSession, limit: int = 50) -> InterventionQueueResponse:
        # Prioritize active interventions needing review or execution
        now = utc_now()
        query = (
            select(Intervention)
            .where(
                Intervention.status.in_([
                    InterventionStatus.PENDING_REVIEW,
                    InterventionStatus.APPROVED,
                    InterventionStatus.READY_TO_EXECUTE,
                    InterventionStatus.SCHEDULED,
                ])
            )
            .order_by(desc(Intervention.created_at))
        )
        result = await session.execute(query)
        items = list(result.scalars().all())

        # Sort priority:
        # 1. READY_TO_EXECUTE / APPROVED
        # 2. PENDING_REVIEW
        # 3. SCHEDULED
        # secondary sort: urgency CRITICAL -> HIGH -> MEDIUM -> LOW
        urgency_weights = {"CRITICAL": 4, "HIGH": 3, "MEDIUM": 2, "LOW": 1}
        status_weights = {
            InterventionStatus.READY_TO_EXECUTE: 4,
            InterventionStatus.APPROVED: 3,
            InterventionStatus.PENDING_REVIEW: 2,
            InterventionStatus.SCHEDULED: 1,
        }

        items.sort(
            key=lambda it: (
                status_weights.get(it.status, 0),
                urgency_weights.get(it.urgency, 1),
                it.created_at,
            ),
            reverse=True,
        )

        dtos = [to_intervention_dto(it) for it in items]
        pending_review_count = sum(1 for it in items if it.status == InterventionStatus.PENDING_REVIEW)
        ready_to_execute_count = sum(
            1 for it in items if it.status in [InterventionStatus.APPROVED, InterventionStatus.READY_TO_EXECUTE]
        )
        scheduled_count = sum(1 for it in items if it.status == InterventionStatus.SCHEDULED)

        return InterventionQueueResponse(
            pending_review_count=pending_review_count,
            ready_to_execute_count=ready_to_execute_count,
            scheduled_count=scheduled_count,
            total_action_required=len(dtos),
            items=dtos[:limit],
        )

    @staticmethod
    async def update_draft(
        session: AsyncSession, intervention_id: str, data: InterventionUpdate
    ) -> Optional[InterventionResponse]:
        intervention = await session.get(Intervention, intervention_id)
        if not intervention:
            return None

        update_dict = data.model_dump(exclude_unset=True)
        now = utc_now()

        # Audit entry for edits
        current_audit = list(intervention.audit_trail or [])
        current_audit.append({
            "event": "EDITED",
            "actor": "USER",
            "timestamp": now.isoformat(),
            "details": {k: v for k, v in update_dict.items() if k != "context_data"},
        })
        intervention.audit_trail = current_audit

        for k, v in update_dict.items():
            setattr(intervention, k, v)

        await session.flush()
        await session.refresh(intervention)
        return to_intervention_dto(intervention)

    @staticmethod
    async def approve(
        session: AsyncSession, intervention_id: str, req: Optional[InterventionApproveRequest] = None
    ) -> InterventionResponse:
        intervention = await session.get(Intervention, intervention_id)
        if not intervention:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Intervention not found.",
            )

        validate_intervention_transition(intervention.status, InterventionStatus.APPROVED)

        now = utc_now()
        actor = req.approved_by if req and req.approved_by else "USER"
        if req and req.approved_message:
            intervention.approved_message = req.approved_message

        intervention.status = InterventionStatus.APPROVED
        intervention.approved_at = now
        intervention.approved_by = actor

        current_audit = list(intervention.audit_trail or [])
        current_audit.append({
            "event": "APPROVED",
            "actor": actor,
            "timestamp": now.isoformat(),
            "details": {
                "approved_message": intervention.approved_message,
            },
        })
        intervention.audit_trail = current_audit

        await session.flush()
        await session.refresh(intervention)
        logger.info(f"InterventionApproved: Intervention [{intervention_id}] approved by [{actor}].")
        return to_intervention_dto(intervention)

    @staticmethod
    async def schedule(
        session: AsyncSession, intervention_id: str, req: InterventionScheduleRequest
    ) -> InterventionResponse:
        intervention = await session.get(Intervention, intervention_id)
        if not intervention:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Intervention not found.",
            )

        validate_intervention_transition(intervention.status, InterventionStatus.SCHEDULED)

        now = utc_now()
        actor = req.approved_by if req.approved_by else "USER"
        if req.approved_message:
            intervention.approved_message = req.approved_message

        intervention.status = InterventionStatus.SCHEDULED
        intervention.scheduled_for = req.scheduled_for
        intervention.approved_at = now
        intervention.approved_by = actor

        current_audit = list(intervention.audit_trail or [])
        current_audit.append({
            "event": "SCHEDULED",
            "actor": actor,
            "timestamp": now.isoformat(),
            "details": {
                "scheduled_for": req.scheduled_for.isoformat(),
            },
        })
        intervention.audit_trail = current_audit

        await session.flush()
        await session.refresh(intervention)
        logger.info(f"InterventionScheduled: Intervention [{intervention_id}] scheduled for [{req.scheduled_for}].")
        return to_intervention_dto(intervention)

    @staticmethod
    async def execute(
        session: AsyncSession,
        intervention_id: str,
        executor: Optional[BaseInterventionExecutor] = None,
    ) -> InterventionResponse:
        intervention = await session.get(Intervention, intervention_id)
        if not intervention:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Intervention not found.",
            )

        # Explicit Human Control Enforcement (Step 14 & 39)
        # Execution is only permitted if intervention is APPROVED, READY_TO_EXECUTE, or SCHEDULED
        if intervention.status not in [
            InterventionStatus.APPROVED,
            InterventionStatus.READY_TO_EXECUTE,
            InterventionStatus.SCHEDULED,
        ]:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=f"Execution rejected: Intervention status is '{intervention.status.value}'. Explicit human approval is required before execution.",
            )

        validate_intervention_transition(intervention.status, InterventionStatus.EXECUTED)

        exec_adapter = executor or DevMockInterventionExecutor()
        exec_res = await exec_adapter.execute(session, intervention)

        now = utc_now()
        intervention.status = InterventionStatus.EXECUTED
        intervention.executed_at = now
        intervention.execution_reference = exec_res.get("execution_reference")
        intervention.execution_mode = exec_res.get("mode", "MOCK_DEMO")
        intervention.cooldown_until = now + timedelta(hours=24)
        intervention.follow_up_at = now + timedelta(hours=48)

        current_audit = list(intervention.audit_trail or [])
        current_audit.append({
            "event": "EXECUTED",
            "actor": "USER",
            "timestamp": now.isoformat(),
            "details": exec_res,
        })
        intervention.audit_trail = current_audit

        await session.flush()
        await session.refresh(intervention)
        logger.info(
            f"InterventionExecuted: Intervention [{intervention_id}] executed via [{intervention.execution_mode}] (Ref: {intervention.execution_reference})."
        )
        return to_intervention_dto(intervention)

    @staticmethod
    async def record_outcome(
        session: AsyncSession, intervention_id: str, req: InterventionOutcomeRequest
    ) -> InterventionResponse:
        intervention = await session.get(Intervention, intervention_id)
        if not intervention:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Intervention not found.",
            )

        now = utc_now()
        intervention.outcome = req.outcome

        # If outcome is COMPLETED or NOT_NEEDED, transition status to RESOLVED
        if req.outcome in [InterventionOutcome.COMPLETED, InterventionOutcome.NOT_NEEDED]:
            if intervention.status != InterventionStatus.RESOLVED:
                intervention.status = InterventionStatus.RESOLVED
        elif req.outcome == InterventionOutcome.ACKNOWLEDGED:
            if intervention.status == InterventionStatus.EXECUTED:
                intervention.status = InterventionStatus.ACKNOWLEDGED

        current_audit = list(intervention.audit_trail or [])
        current_audit.append({
            "event": "OUTCOME_RECORDED",
            "actor": "USER",
            "timestamp": now.isoformat(),
            "details": {
                "outcome": req.outcome.value,
                "notes": req.notes,
            },
        })
        intervention.audit_trail = current_audit

        await session.flush()
        await session.refresh(intervention)
        logger.info(
            f"InterventionOutcomeRecorded: Intervention [{intervention_id}] recorded outcome [{req.outcome.value}]."
        )
        return to_intervention_dto(intervention)

    @staticmethod
    async def cancel(
        session: AsyncSession, intervention_id: str, reason: Optional[str] = None
    ) -> InterventionResponse:
        intervention = await session.get(Intervention, intervention_id)
        if not intervention:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Intervention not found.",
            )

        validate_intervention_transition(intervention.status, InterventionStatus.CANCELLED)

        now = utc_now()
        intervention.status = InterventionStatus.CANCELLED

        current_audit = list(intervention.audit_trail or [])
        current_audit.append({
            "event": "CANCELLED",
            "actor": "USER",
            "timestamp": now.isoformat(),
            "details": {"reason": reason or "User cancelled intervention."},
        })
        intervention.audit_trail = current_audit

        await session.flush()
        await session.refresh(intervention)
        logger.info(f"InterventionCancelled: Intervention [{intervention_id}] marked CANCELLED.")
        return to_intervention_dto(intervention)

    @staticmethod
    async def resolve(
        session: AsyncSession, intervention_id: str, reason: Optional[str] = None
    ) -> InterventionResponse:
        intervention = await session.get(Intervention, intervention_id)
        if not intervention:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Intervention not found.",
            )

        now = utc_now()
        intervention.status = InterventionStatus.RESOLVED
        intervention.outcome = InterventionOutcome.COMPLETED

        current_audit = list(intervention.audit_trail or [])
        current_audit.append({
            "event": "RESOLVED",
            "actor": "USER",
            "timestamp": now.isoformat(),
            "details": {"reason": reason or "Intervention resolved."},
        })
        intervention.audit_trail = current_audit

        await session.flush()
        await session.refresh(intervention)
        logger.info(f"InterventionResolved: Intervention [{intervention_id}] marked RESOLVED.")
        return to_intervention_dto(intervention)

    @staticmethod
    async def auto_resolve_for_obligation(
        session: AsyncSession, obligation_id: str, reason: str = "Obligation completed via evidence confirmation."
    ) -> None:
        """
        Closed-loop auto-resolution: when an obligation completes, resolve active interventions.
        """
        now = utc_now()
        stmt = select(Intervention).where(
            and_(
                Intervention.obligation_id == obligation_id,
                Intervention.status.in_([
                    InterventionStatus.PENDING_REVIEW,
                    InterventionStatus.APPROVED,
                    InterventionStatus.SCHEDULED,
                    InterventionStatus.READY_TO_EXECUTE,
                    InterventionStatus.EXECUTED,
                    InterventionStatus.ACKNOWLEDGED,
                ]),
            )
        )
        res = await session.execute(stmt)
        active_interventions = list(res.scalars().all())

        for it in active_interventions:
            it.status = InterventionStatus.RESOLVED
            it.outcome = InterventionOutcome.COMPLETED
            current_audit = list(it.audit_trail or [])
            current_audit.append({
                "event": "RESOLVED",
                "actor": "SYSTEM",
                "timestamp": now.isoformat(),
                "details": {"reason": reason},
            })
            it.audit_trail = current_audit

        await session.flush()
        logger.info(
            f"InterventionsAutoResolved: Resolved {len(active_interventions)} active interventions for obligation [{obligation_id}]."
        )
