from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.core.intervention_status import InterventionStatus, InterventionType
from app.schemas.intervention import (
    InterventionPlanRequest,
    InterventionApproveRequest,
    InterventionScheduleRequest,
    InterventionOutcomeRequest,
    InterventionUpdate,
    InterventionResponse,
    InterventionListResponse,
    InterventionQueueResponse,
)
from app.services.intervention_service import InterventionService

router = APIRouter(prefix="/interventions", tags=["interventions"])


@router.post("/plan", response_model=InterventionResponse, status_code=status.HTTP_201_CREATED)
async def plan_intervention(
    payload: InterventionPlanRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Generate or retrieve a structured intervention plan for an obligation.
    """
    res = await InterventionService.plan(
        session=db, obligation_id=payload.obligation_id, force=payload.force
    )
    if not res:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Could not plan intervention: obligation not found or healthy with no action required.",
        )
    return res


@router.get("", response_model=InterventionListResponse)
async def list_interventions(
    status: Optional[InterventionStatus] = Query(None, description="Filter by intervention status"),
    intervention_type: Optional[InterventionType] = Query(None, description="Filter by intervention type"),
    obligation_id: Optional[str] = Query(None, description="Filter by obligation ID"),
    urgency: Optional[str] = Query(None, description="Filter by urgency"),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    """
    List all interventions with multi-dimensional filtering.
    """
    return await InterventionService.list_all(
        session=db,
        status=status,
        intervention_type=intervention_type,
        obligation_id=obligation_id,
        urgency=urgency,
        limit=limit,
        offset=offset,
    )


@router.get("/queue", response_model=InterventionQueueResponse)
async def get_intervention_queue(
    limit: int = Query(50, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    """
    Get the prioritized intervention action queue requiring human attention.
    """
    return await InterventionService.get_queue(session=db, limit=limit)


@router.get("/{id}", response_model=InterventionResponse)
async def get_intervention_by_id(
    id: str,
    db: AsyncSession = Depends(get_db),
):
    """
    Get detailed intervention record with audit trail and context packet.
    """
    res = await InterventionService.get_by_id(session=db, intervention_id=id)
    if not res:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Intervention with ID '{id}' not found.",
        )
    return res


@router.patch("/{id}", response_model=InterventionResponse)
async def update_intervention_draft(
    id: str,
    payload: InterventionUpdate,
    db: AsyncSession = Depends(get_db),
):
    """
    Edit draft message, target, scheduled time, or urgency before approval.
    """
    res = await InterventionService.update_draft(
        session=db, intervention_id=id, data=payload
    )
    if not res:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Intervention with ID '{id}' not found.",
        )
    return res


@router.post("/{id}/approve", response_model=InterventionResponse)
async def approve_intervention(
    id: str,
    payload: Optional[InterventionApproveRequest] = None,
    db: AsyncSession = Depends(get_db),
):
    """
    Explicit human approval of an intervention plan.
    """
    return await InterventionService.approve(
        session=db, intervention_id=id, req=payload
    )


@router.post("/{id}/schedule", response_model=InterventionResponse)
async def schedule_intervention(
    id: str,
    payload: InterventionScheduleRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Schedule an approved intervention for future execution.
    """
    return await InterventionService.schedule(
        session=db, intervention_id=id, req=payload
    )


@router.post("/{id}/execute", response_model=InterventionResponse)
async def execute_intervention(
    id: str,
    db: AsyncSession = Depends(get_db),
):
    """
    Explicitly trigger simulated execution of an approved intervention.
    """
    return await InterventionService.execute(session=db, intervention_id=id)


@router.post("/{id}/outcome", response_model=InterventionResponse)
async def record_intervention_outcome(
    id: str,
    payload: InterventionOutcomeRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Record observed or human-entered outcome for an intervention.
    """
    return await InterventionService.record_outcome(
        session=db, intervention_id=id, req=payload
    )


@router.post("/{id}/cancel", response_model=InterventionResponse)
async def cancel_intervention(
    id: str,
    reason: Optional[str] = Query(None, description="Reason for cancellation"),
    db: AsyncSession = Depends(get_db),
):
    """
    Cancel an active intervention.
    """
    return await InterventionService.cancel(
        session=db, intervention_id=id, reason=reason
    )


@router.post("/{id}/resolve", response_model=InterventionResponse)
async def resolve_intervention(
    id: str,
    reason: Optional[str] = Query(None, description="Reason for resolution"),
    db: AsyncSession = Depends(get_db),
):
    """
    Mark an intervention resolved.
    """
    return await InterventionService.resolve(
        session=db, intervention_id=id, reason=reason
    )
