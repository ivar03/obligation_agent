"""
Phase 18 Operational Queues API Endpoints.
"""

from typing import Optional, List, Dict, Any
from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, and_, or_, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.auth import WorkspaceMembership
from app.core.auth_deps import get_current_membership
from app.models.obligation import Obligation, Evidence, IngestedEventRecord
from app.models.decision import DecisionPlan
from app.models.execution import ExecutionRecord
from app.core.status_machine import (
    ObligationStatus,
    DecisionPlanStatus,
    ExecutionStatus,
    CorrelationStatus,
)

router = APIRouter(prefix="/queues", tags=["Operational Queues"])


@router.get("/action")
async def get_action_queue(
    owner: Optional[str] = None,
    limit: int = Query(50, ge=1, le=100),
    membership: WorkspaceMembership = Depends(get_current_membership),
    session: AsyncSession = Depends(get_db),
):
    """
    Action Queue: Returns obligations that are OVERDUE, BLOCKED, or flagged requiring immediate attention.
    """
    stmt = (
        select(Obligation)
        .where(
            and_(
                Obligation.workspace_id == membership.workspace_id,
                Obligation.status.in_([ObligationStatus.OVERDUE, ObligationStatus.BLOCKED, ObligationStatus.CONFIRMED]),
            )
        )
    )
    if owner:
        stmt = stmt.where(Obligation.owner.ilike(f"%{owner}%"))

    stmt = stmt.order_by(Obligation.deadline.asc().nulls_last()).limit(limit)
    obs = (await session.execute(stmt)).scalars().all()

    return {
        "queue_name": "Action Queue",
        "total_count": len(obs),
        "items": [
            {
                "id": o.id,
                "action": o.action,
                "owner": o.owner,
                "beneficiary": o.beneficiary,
                "status": o.status.value,
                "priority": getattr(o, "priority", "MEDIUM"),
                "deadline": o.deadline.isoformat() if o.deadline else None,
                "is_overdue": o.status == ObligationStatus.OVERDUE,
                "is_blocked": o.status == ObligationStatus.BLOCKED,
                "url": f"/obligations/{o.id}",
            }
            for o in obs
        ],
    }


@router.get("/evidence")
async def get_evidence_review_queue(
    limit: int = Query(50, ge=1, le=100),
    membership: WorkspaceMembership = Depends(get_current_membership),
    session: AsyncSession = Depends(get_db),
):
    """
    Evidence Review Queue: Returns evidence candidates awaiting human operator confirmation.
    """
    stmt = (
        select(Evidence)
        .where(
            and_(
                Evidence.workspace_id == membership.workspace_id,
                Evidence.correlation_status == CorrelationStatus.SUGGESTED,
            )
        )
        .order_by(Evidence.created_at.desc())
        .limit(limit)
    )
    items = (await session.execute(stmt)).scalars().all()

    return {
        "queue_name": "Evidence Review Queue",
        "total_count": len(items),
        "items": [
            {
                "id": e.id,
                "obligation_id": e.obligation_id,
                "evidence_type": e.evidence_type.value if hasattr(e.evidence_type, "value") else str(e.evidence_type),
                "source_type": e.source_type,
                "content": e.content,
                "actor": getattr(e, "actor", None),
                "confidence_score": getattr(e, "correlation_confidence", 1.0),
                "created_at": e.created_at.isoformat(),
                "url": f"/obligations/{e.obligation_id}",
            }

            for e in items
        ],
    }


@router.get("/decisions")
async def get_decision_queue(
    limit: int = Query(50, ge=1, le=100),
    membership: WorkspaceMembership = Depends(get_current_membership),
    session: AsyncSession = Depends(get_db),
):
    """
    Decision Queue: Returns Decision Plans awaiting operator approval or simulation.
    """
    stmt = (
        select(DecisionPlan)
        .where(
            and_(
                DecisionPlan.workspace_id == membership.workspace_id,
                DecisionPlan.status.in_([DecisionPlanStatus.GENERATED, DecisionPlanStatus.APPROVED]),
            )
        )
        .order_by(DecisionPlan.overall_risk.desc(), DecisionPlan.generated_at.desc())
        .limit(limit)
    )
    items = (await session.execute(stmt)).scalars().all()

    return {
        "queue_name": "Decision Queue",
        "total_count": len(items),
        "items": [
            {
                "id": d.id,
                "target_obligation_id": d.target_obligation_id,
                "status": d.status.value,
                "primary_objective": d.primary_objective,
                "overall_urgency": d.overall_urgency,
                "overall_risk": d.overall_risk,
                "decision_confidence": d.decision_confidence,
                "created_at": d.generated_at.isoformat() if d.generated_at else None,
                "url": f"/intelligence/decisions/{d.id}",
            }
            for d in items
        ],
    }


@router.get("/executions")
async def get_execution_queue(
    limit: int = Query(50, ge=1, le=100),
    membership: WorkspaceMembership = Depends(get_current_membership),
    session: AsyncSession = Depends(get_db),
):
    """
    Execution Queue: Returns active in-flight or failed controlled executions.
    """
    stmt = (
        select(ExecutionRecord)
        .where(
            and_(
                ExecutionRecord.workspace_id == membership.workspace_id,
                ExecutionRecord.status.in_([
                    ExecutionStatus.AUTHORIZED,
                    ExecutionStatus.EXECUTING,
                    ExecutionStatus.DELIVERED,
                    ExecutionStatus.RESPONSE_PENDING,
                    ExecutionStatus.RETRY_SCHEDULED,
                    ExecutionStatus.DELIVERY_FAILED,
                    ExecutionStatus.FAILED,
                ]),
            )
        )
        .order_by(ExecutionRecord.updated_at.desc())
        .limit(limit)
    )
    items = (await session.execute(stmt)).scalars().all()

    return {
        "queue_name": "Execution Queue",
        "total_count": len(items),
        "items": [
            {
                "id": ex.id,
                "decision_plan_id": ex.decision_plan_id,
                "obligation_id": ex.obligation_id,
                "provider": ex.provider,
                "status": ex.status.value,
                "provider_ref": ex.provider_execution_ref,
                "retry_count": ex.retry_count,
                "max_retries": ex.max_retries,
                "updated_at": ex.updated_at.isoformat(),
                "url": f"/intelligence/execution/{ex.id}",
            }
            for ex in items
        ],
    }


@router.get("/activity")
async def get_activity_feed(
    limit: int = Query(50, ge=1, le=100),
    membership: WorkspaceMembership = Depends(get_current_membership),
    session: AsyncSession = Depends(get_db),
):
    """
    Activity Feed: Real-time event log for the active workspace.
    """
    stmt = (
        select(IngestedEventRecord)
        .where(IngestedEventRecord.workspace_id == membership.workspace_id)
        .order_by(IngestedEventRecord.received_at.desc())
        .limit(limit)
    )
    items = (await session.execute(stmt)).scalars().all()

    return {
        "queue_name": "Activity Feed",
        "total_count": len(items),
        "items": [
            {
                "id": ev.id,
                "provider": ev.provider,
                "sender": ev.sender,
                "content": ev.content,
                "action_taken": ev.action_taken,
                "correlated_obligation_id": ev.correlated_obligation_id,
                "received_at": ev.received_at.isoformat(),
            }
            for ev in items
        ],
    }


@router.get("/inbox")
async def get_event_inbox_queue(
    limit: int = Query(50, ge=1, le=100),
    membership: WorkspaceMembership = Depends(get_current_membership),
    session: AsyncSession = Depends(get_db),
):
    """
    Event Inbox Queue: Returns actively queued, processing, and retrying buffered events.
    """
    from app.models.event_inbox import EventInboxRecord, EventInboxStatus
    stmt = (
        select(EventInboxRecord)
        .where(
            and_(
                EventInboxRecord.workspace_id == membership.workspace_id,
                EventInboxRecord.status.in_([
                    EventInboxStatus.QUEUED,
                    EventInboxStatus.PROCESSING,
                    EventInboxStatus.RETRY_SCHEDULED,
                ]),
            )
        )
        .order_by(EventInboxRecord.received_at.desc())
        .limit(limit)
    )
    items = (await session.execute(stmt)).scalars().all()

    return {
        "queue_name": "Event Processing Queue",
        "total_count": len(items),
        "items": [
            {
                "id": r.id,
                "provider": r.provider,
                "source_ref": r.source_ref,
                "event_type": r.event_type,
                "stream_key": r.stream_key,
                "status": r.status.value if hasattr(r.status, "value") else str(r.status),
                "attempt_count": r.attempt_count,
                "max_attempts": r.max_attempts,
                "last_error": r.last_error,
                "received_at": r.received_at.isoformat() if r.received_at else None,
                "payload_metadata": r.payload_metadata,
            }
            for r in items
        ],
    }


@router.get("/dead-letter")
async def get_dead_letter_queue(
    limit: int = Query(50, ge=1, le=100),
    membership: WorkspaceMembership = Depends(get_current_membership),
    session: AsyncSession = Depends(get_db),
):
    """
    Dead-Letter Queue: Returns exhausted or poisoned events awaiting operator triage.
    """
    from app.models.event_inbox import EventInboxRecord, EventInboxStatus
    stmt = (
        select(EventInboxRecord)
        .where(
            and_(
                EventInboxRecord.workspace_id == membership.workspace_id,
                EventInboxRecord.status == EventInboxStatus.DEAD_LETTER,
            )
        )
        .order_by(EventInboxRecord.updated_at.desc())
        .limit(limit)
    )
    items = (await session.execute(stmt)).scalars().all()

    return {
        "queue_name": "Dead Letter Queue",
        "total_count": len(items),
        "items": [
            {
                "id": r.id,
                "provider": r.provider,
                "source_ref": r.source_ref,
                "event_type": r.event_type,
                "stream_key": r.stream_key,
                "status": "DEAD_LETTER",
                "attempt_count": r.attempt_count,
                "max_attempts": r.max_attempts,
                "last_error": r.last_error,
                "received_at": r.received_at.isoformat() if r.received_at else None,
                "updated_at": r.updated_at.isoformat() if r.updated_at else None,
                "payload_metadata": r.payload_metadata,
            }
            for r in items
        ],
    }

