"""
Phase 19 Event Processing & Dead-Letter Queue (DLQ) Operational APIs.

Endpoints:
  GET  /api/events/queue              — List active event queue items (QUEUED, PROCESSING, RETRY_SCHEDULED)
  GET  /api/events/queue/{id}         — Inspect individual event record & safe metadata
  GET  /api/events/dead-letter        — List dead-letter queue items
  POST /api/events/dead-letter/{id}/retry   — Idempotently retry an event from DLQ
  POST /api/events/dead-letter/{id}/discard — Discard a DLQ event with immutable audit trail
"""

from typing import Optional, List, Dict, Any
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import select, update, and_, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.auth import WorkspaceMembership
from app.core.auth_deps import get_current_membership, require_role
from app.core.status_machine import WorkspaceRole, AuditAction, AuditSource
from app.models.event_inbox import EventInboxRecord, EventInboxStatus
from app.services.audit_service import AuditService
from app.services.async_event_dispatcher import event_dispatcher

router = APIRouter(prefix="/events", tags=["Async Event Queue & DLQ"])


class DiscardEventRequest(BaseModel):
    reason: Optional[str] = "Discarded by operator"


@router.get("/queue")
async def list_event_queue(
    status_filter: Optional[str] = Query(None, alias="status"),
    provider: Optional[str] = None,
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    membership: WorkspaceMembership = Depends(get_current_membership),
    session: AsyncSession = Depends(get_db),
):
    """
    Returns paginated active items in the Event Inbox Queue.
    """
    stmt = select(EventInboxRecord).where(
        EventInboxRecord.workspace_id == membership.workspace_id
    )

    if status_filter:
        try:
            status_enum = EventInboxStatus(status_filter.upper())
            stmt = stmt.where(EventInboxRecord.status == status_enum)
        except ValueError:
            pass
    else:
        stmt = stmt.where(
            EventInboxRecord.status.in_([
                EventInboxStatus.QUEUED,
                EventInboxStatus.PROCESSING,
                EventInboxStatus.RETRY_SCHEDULED,
            ])
        )

    if provider:
        stmt = stmt.where(EventInboxRecord.provider == provider)

    stmt = stmt.order_by(EventInboxRecord.received_at.desc()).offset(offset).limit(limit)
    res = await session.execute(stmt)
    records = res.scalars().all()

    stats = await event_dispatcher.get_inbox_queue_stats(
        workspace_id=membership.workspace_id,
        session=session,
    )

    return {
        "stats": stats,
        "total_returned": len(records),
        "items": [
            {
                "id": r.id,
                "workspace_id": r.workspace_id,
                "provider": r.provider,
                "source_ref": r.source_ref,
                "event_type": r.event_type,
                "stream_key": r.stream_key,
                "status": r.status.value if hasattr(r.status, "value") else str(r.status),
                "attempt_count": r.attempt_count,
                "max_attempts": r.max_attempts,
                "last_error": r.last_error,
                "received_at": r.received_at.isoformat() if r.received_at else None,
                "available_at": r.available_at.isoformat() if r.available_at else None,
                "processing_duration_ms": r.processing_duration_ms,
                "payload_metadata": r.payload_metadata,
            }
            for r in records
        ],
    }


@router.get("/queue/{event_id}")
async def get_event_details(
    event_id: str,
    membership: WorkspaceMembership = Depends(get_current_membership),
    session: AsyncSession = Depends(get_db),
):
    """
    Inspects an individual Event Inbox record with safe sanitized metadata.
    """
    stmt = select(EventInboxRecord).where(
        and_(
            EventInboxRecord.id == event_id,
            EventInboxRecord.workspace_id == membership.workspace_id,
        )
    )
    res = await session.execute(stmt)
    record = res.scalar_one_or_none()
    if not record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Event inbox record '{event_id}' not found.",
        )

    return {
        "id": record.id,
        "workspace_id": record.workspace_id,
        "provider": record.provider,
        "source_ref": record.source_ref,
        "event_type": record.event_type,
        "payload_hash": record.payload_hash,
        "stream_key": record.stream_key,
        "status": record.status.value if hasattr(record.status, "value") else str(record.status),
        "attempt_count": record.attempt_count,
        "max_attempts": record.max_attempts,
        "last_error": record.last_error,
        "locked_at": record.locked_at.isoformat() if record.locked_at else None,
        "locked_by": record.locked_by,
        "received_at": record.received_at.isoformat() if record.received_at else None,
        "available_at": record.available_at.isoformat() if record.available_at else None,
        "processed_at": record.processed_at.isoformat() if record.processed_at else None,
        "processing_duration_ms": record.processing_duration_ms,
        "payload_metadata": record.payload_metadata,
        "created_at": record.created_at.isoformat() if record.created_at else None,
        "updated_at": record.updated_at.isoformat() if record.updated_at else None,
    }


@router.get("/dead-letter")
async def list_dead_letter_events(
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    membership: WorkspaceMembership = Depends(get_current_membership),
    session: AsyncSession = Depends(get_db),
):
    """
    Lists all events currently in DEAD_LETTER status.
    """
    stmt = (
        select(EventInboxRecord)
        .where(
            and_(
                EventInboxRecord.workspace_id == membership.workspace_id,
                EventInboxRecord.status == EventInboxStatus.DEAD_LETTER,
            )
        )
        .order_by(EventInboxRecord.updated_at.desc())
        .offset(offset)
        .limit(limit)
    )
    res = await session.execute(stmt)
    records = res.scalars().all()

    return {
        "queue_name": "Dead Letter Queue",
        "total_count": len(records),
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
            for r in records
        ],
    }


@router.post("/dead-letter/{event_id}/retry")
async def retry_dead_letter_event(
    event_id: str,
    membership: WorkspaceMembership = Depends(require_role(WorkspaceRole.OPERATOR)),
    session: AsyncSession = Depends(get_db),
):
    """
    Idempotently re-queues an event from the Dead-Letter Queue.
    Resets attempt counter and clears error state.
    """
    stmt = select(EventInboxRecord).where(
        and_(
            EventInboxRecord.id == event_id,
            EventInboxRecord.workspace_id == membership.workspace_id,
        )
    )
    res = await session.execute(stmt)
    record = res.scalar_one_or_none()
    if not record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Event '{event_id}' not found.",
        )

    now = datetime.now(timezone.utc)
    record.status = EventInboxStatus.QUEUED
    record.attempt_count = 0
    record.available_at = now
    record.last_error = None
    record.locked_at = None
    record.locked_by = None
    record.lease_expires_at = None
    record.updated_at = now

    await session.commit()

    # Audit log
    await AuditService.record(
        session=session,
        workspace_id=membership.workspace_id,
        action=AuditAction.INTERVENTION_APPROVED,
        actor_user_id=membership.user_id,
        actor_role=membership.role.value if hasattr(membership.role, "value") else str(membership.role),
        entity_type="event_inbox",
        entity_id=record.id,
        source=AuditSource.API,
        reason=f"Operator manually re-queued dead-letter event [{record.id}]",
    )
    await session.commit()

    return {
        "status": "requeued",
        "event_id": record.id,
        "stream_key": record.stream_key,
        "message": f"Event [{record.id}] successfully returned to QUEUED state.",
    }


@router.post("/dead-letter/{event_id}/discard")
async def discard_dead_letter_event(
    event_id: str,
    request: DiscardEventRequest,
    membership: WorkspaceMembership = Depends(require_role(WorkspaceRole.OPERATOR)),
    session: AsyncSession = Depends(get_db),
):
    """
    Marks a dead-letter event as permanently FAILED and records an immutable audit record.
    """
    stmt = select(EventInboxRecord).where(
        and_(
            EventInboxRecord.id == event_id,
            EventInboxRecord.workspace_id == membership.workspace_id,
        )
    )
    res = await session.execute(stmt)
    record = res.scalar_one_or_none()
    if not record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Event '{event_id}' not found.",
        )

    now = datetime.now(timezone.utc)
    record.status = EventInboxStatus.FAILED
    record.last_error = f"Permanently discarded by operator: {request.reason}"
    record.updated_at = now

    await session.commit()

    # Immutable audit trail
    await AuditService.record(
        session=session,
        workspace_id=membership.workspace_id,
        action=AuditAction.INTERVENTION_CANCELLED,
        actor_user_id=membership.user_id,
        actor_role=membership.role.value if hasattr(membership.role, "value") else str(membership.role),
        entity_type="event_inbox",
        entity_id=record.id,
        source=AuditSource.API,
        reason=f"Operator discarded dead-letter event: {request.reason}",
    )
    await session.commit()

    return {
        "status": "discarded",
        "event_id": record.id,
        "message": f"Event [{record.id}] marked as permanently FAILED.",
    }
