"""
FastAPI Routes for Phase 17 Continuous Monitoring, Escalation & Reliability Layer.
Mounted at /api/intelligence/monitoring/
"""

from typing import Optional, List
from fastapi import APIRouter, Depends, Query, status, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.auth import User, Workspace
from app.core.auth_deps import get_current_user, get_current_workspace
from app.core.status_machine import (
    WatchStatus,
    WatchType,
    MonitoringSeverity,
    MonitoringEventType,
    EscalationStatus,
)
from app.schemas.monitoring import (
    MonitoringWatchCreate,
    MonitoringWatchUpdate,
    MonitoringWatchResponse,
    MonitoringWatchListResponse,
    MonitoringEventResponse,
    MonitoringEventListResponse,
    EscalationCandidateResponse,
    EscalationCandidateListResponse,
    EscalationAcknowledgeRequest,
    EscalationResolveRequest,
    EscalationDismissRequest,
    MonitoringRunRequest,
    MonitoringRunResponse,
    MonitoringRunListResponse,
    MonitoringSummaryResponse,
)
from app.services.monitoring.monitoring_service import MonitoringService

router = APIRouter(prefix="/intelligence/monitoring", tags=["Continuous Monitoring & Escalation"])


# =============================================================================
# 1. Monitoring Runs & Cycles
# =============================================================================

@router.post("/run", response_model=MonitoringRunResponse, status_code=status.HTTP_200_OK)
async def trigger_monitoring_cycle(
    payload: Optional[MonitoringRunRequest] = None,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    workspace: Workspace = Depends(get_current_workspace),
):
    """
    Triggers a controlled continuous monitoring evaluation pass across active watches.
    Does NOT perform any consequential autonomous actions.
    """
    watch_ids = payload.watch_ids if payload else None
    force_all = payload.force_all if payload else False

    run = await MonitoringService.run_monitoring_cycle(
        session=session,
        workspace_id=workspace.id,
        watch_ids=watch_ids,
        force_all=force_all,
    )
    await session.commit()
    return run


@router.get("/runs", response_model=MonitoringRunListResponse, status_code=status.HTTP_200_OK)
async def list_monitoring_runs(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    workspace: Workspace = Depends(get_current_workspace),
):
    """
    Lists historical monitoring runs.
    """
    items, total = await MonitoringService.list_runs(
        session=session,
        workspace_id=workspace.id,
        limit=limit,
        offset=offset,
    )
    return MonitoringRunListResponse(
        items=[MonitoringRunResponse.model_validate(r) for r in items],
        total=total,
    )


@router.get("/runs/{run_id}", response_model=MonitoringRunResponse, status_code=status.HTTP_200_OK)
async def get_monitoring_run_by_id(
    run_id: str,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    workspace: Workspace = Depends(get_current_workspace),
):
    """
    Retrieves a specific monitoring run by ID.
    """
    run = await MonitoringService.get_run(session, run_id, workspace.id)
    if not run:
        raise HTTPException(status_code=404, detail="Monitoring run not found.")
    return run


# =============================================================================
# 2. Watch Management Endpoints
# =============================================================================

@router.post("/watches", response_model=MonitoringWatchResponse, status_code=status.HTTP_201_CREATED)
async def create_monitoring_watch(
    payload: MonitoringWatchCreate,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    workspace: Workspace = Depends(get_current_workspace),
):
    """
    Creates a new monitoring watch for an obligation, execution, dependency, or decision plan.
    """
    watch = await MonitoringService.create_watch(
        session=session,
        workspace_id=workspace.id,
        data=payload,
        user=current_user,
    )
    await session.commit()
    return watch


@router.get("/watches", response_model=MonitoringWatchListResponse, status_code=status.HTTP_200_OK)
async def list_monitoring_watches(
    status: Optional[WatchStatus] = None,
    watch_type: Optional[WatchType] = None,
    target_id: Optional[str] = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    workspace: Workspace = Depends(get_current_workspace),
):
    """
    Lists monitoring watches in the workspace.
    """
    items, total = await MonitoringService.list_watches(
        session=session,
        workspace_id=workspace.id,
        status=status,
        watch_type=watch_type,
        target_id=target_id,
        limit=limit,
        offset=offset,
    )
    return MonitoringWatchListResponse(
        items=[MonitoringWatchResponse.model_validate(w) for w in items],
        total=total,
    )


@router.get("/watches/{watch_id}", response_model=MonitoringWatchResponse, status_code=status.HTTP_200_OK)
async def get_monitoring_watch_by_id(
    watch_id: str,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    workspace: Workspace = Depends(get_current_workspace),
):
    """
    Retrieves a monitoring watch by ID.
    """
    watch = await MonitoringService.get_watch(session, watch_id, workspace.id)
    if not watch:
        raise HTTPException(status_code=404, detail="Monitoring watch not found.")
    return watch


@router.post("/watches/{watch_id}/pause", response_model=MonitoringWatchResponse, status_code=status.HTTP_200_OK)
async def pause_monitoring_watch(
    watch_id: str,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    workspace: Workspace = Depends(get_current_workspace),
):
    """
    Pauses an active monitoring watch.
    """
    try:
        watch = await MonitoringService.pause_watch(session, watch_id, workspace.id)
        await session.commit()
        return watch
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/watches/{watch_id}/resume", response_model=MonitoringWatchResponse, status_code=status.HTTP_200_OK)
async def resume_monitoring_watch(
    watch_id: str,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    workspace: Workspace = Depends(get_current_workspace),
):
    """
    Resumes a paused monitoring watch.
    """
    try:
        watch = await MonitoringService.resume_watch(session, watch_id, workspace.id)
        await session.commit()
        return watch
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.delete("/watches/{watch_id}", status_code=status.HTTP_200_OK)
async def delete_monitoring_watch(
    watch_id: str,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    workspace: Workspace = Depends(get_current_workspace),
):
    """
    Deletes a monitoring watch.
    """
    deleted = await MonitoringService.delete_watch(session, watch_id, workspace.id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Monitoring watch not found.")
    await session.commit()
    return {"message": "Watch deleted successfully.", "watch_id": watch_id}


# =============================================================================
# 3. Events Endpoints
# =============================================================================

@router.get("/events", response_model=MonitoringEventListResponse, status_code=status.HTTP_200_OK)
async def list_monitoring_events(
    severity: Optional[MonitoringSeverity] = None,
    target_id: Optional[str] = None,
    event_type: Optional[MonitoringEventType] = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    workspace: Workspace = Depends(get_current_workspace),
):
    """
    Lists immutable monitoring events generated by the monitoring engine.
    """
    items, total = await MonitoringService.list_events(
        session=session,
        workspace_id=workspace.id,
        severity=severity,
        target_id=target_id,
        event_type=event_type,
        limit=limit,
        offset=offset,
    )
    return MonitoringEventListResponse(
        items=[MonitoringEventResponse.model_validate(e) for e in items],
        total=total,
    )


@router.get("/events/{event_id}", response_model=MonitoringEventResponse, status_code=status.HTTP_200_OK)
async def get_monitoring_event_by_id(
    event_id: str,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    workspace: Workspace = Depends(get_current_workspace),
):
    """
    Retrieves a specific monitoring event by ID.
    """
    ev = await MonitoringService.get_event(session, event_id, workspace.id)
    if not ev:
        raise HTTPException(status_code=404, detail="Monitoring event not found.")
    return ev


# =============================================================================
# 4. Escalation Candidates Endpoints
# =============================================================================

@router.get("/escalations", response_model=EscalationCandidateListResponse, status_code=status.HTTP_200_OK)
async def list_escalation_candidates(
    status: Optional[EscalationStatus] = None,
    severity: Optional[MonitoringSeverity] = None,
    target_id: Optional[str] = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    workspace: Workspace = Depends(get_current_workspace),
):
    """
    Lists prioritized escalation candidates awaiting human review.
    """
    items, total = await MonitoringService.list_escalations(
        session=session,
        workspace_id=workspace.id,
        status=status,
        severity=severity,
        target_id=target_id,
        limit=limit,
        offset=offset,
    )
    return EscalationCandidateListResponse(
        items=[EscalationCandidateResponse.model_validate(e) for e in items],
        total=total,
    )


@router.get("/escalations/{escalation_id}", response_model=EscalationCandidateResponse, status_code=status.HTTP_200_OK)
async def get_escalation_candidate_by_id(
    escalation_id: str,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    workspace: Workspace = Depends(get_current_workspace),
):
    """
    Retrieves a specific escalation candidate.
    """
    esc = await MonitoringService.get_escalation(session, escalation_id, workspace.id)
    if not esc:
        raise HTTPException(status_code=404, detail="Escalation candidate not found.")
    return esc


@router.post("/escalations/{escalation_id}/acknowledge", response_model=EscalationCandidateResponse, status_code=status.HTTP_200_OK)
async def acknowledge_escalation_candidate(
    escalation_id: str,
    payload: Optional[EscalationAcknowledgeRequest] = None,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    workspace: Workspace = Depends(get_current_workspace),
):
    """
    Human operator acknowledges an escalation candidate.
    """
    try:
        esc = await MonitoringService.acknowledge_escalation(
            session=session,
            escalation_id=escalation_id,
            workspace_id=workspace.id,
            user=current_user,
            notes=payload.notes if payload else None,
        )
        await session.commit()
        return esc
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/escalations/{escalation_id}/resolve", response_model=EscalationCandidateResponse, status_code=status.HTTP_200_OK)
async def resolve_escalation_candidate(
    escalation_id: str,
    payload: Optional[EscalationResolveRequest] = None,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    workspace: Workspace = Depends(get_current_workspace),
):
    """
    Human operator marks an escalation candidate RESOLVED.
    """
    try:
        esc = await MonitoringService.resolve_escalation(
            session=session,
            escalation_id=escalation_id,
            workspace_id=workspace.id,
            user=current_user,
            resolution_reason=payload.resolution_reason if payload else None,
        )
        await session.commit()
        return esc
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/escalations/{escalation_id}/dismiss", response_model=EscalationCandidateResponse, status_code=status.HTTP_200_OK)
async def dismiss_escalation_candidate(
    escalation_id: str,
    payload: Optional[EscalationDismissRequest] = None,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    workspace: Workspace = Depends(get_current_workspace),
):
    """
    Human operator dismisses an escalation candidate.
    """
    try:
        esc = await MonitoringService.dismiss_escalation(
            session=session,
            escalation_id=escalation_id,
            workspace_id=workspace.id,
            user=current_user,
            reason=payload.reason if payload else None,
        )
        await session.commit()
        return esc
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


# =============================================================================
# 5. Monitoring Summary Endpoint
# =============================================================================

@router.get("/summary", response_model=MonitoringSummaryResponse, status_code=status.HTTP_200_OK)
async def get_monitoring_summary(
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    workspace: Workspace = Depends(get_current_workspace),
):
    """
    Returns aggregated continuous monitoring health metrics, recent condition alerts, and open escalations.
    """
    return await MonitoringService.get_monitoring_summary(session, workspace.id)
