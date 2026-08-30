from typing import Optional
from fastapi import APIRouter, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import DatabaseSession, ExtractionServiceDep
from app.core.status_machine import (
    ObligationStatus,
    ObligationType,
    InvalidStatusTransitionError,
)
from app.schemas.obligation import (
    ExtractionRequest,
    ExtractionResponse,
    ObligationCreate,
    ObligationUpdate,
    ObligationStatusUpdate,
    ObligationResponse,
    ObligationListResponse,
    ObligationEdgeCreate,
    ObligationEdgeResponse,
)
from app.services.obligation_service import ObligationService
from app.services.extraction_service import ExtractionService

router = APIRouter(prefix="/obligations", tags=["Obligations"])


@router.post("/extract", response_model=ExtractionResponse)
async def extract_obligation(
    request: ExtractionRequest,
    extractor: ExtractionService = ExtractionServiceDep,
):
    """
    Analyzes raw text and produces a candidate structured obligation with field-level confidence.
    Does NOT persist anything to the database (Human-in-the-loop requirement).
    """
    return await extractor.extract_candidate(request)


@router.post("", response_model=ObligationResponse, status_code=status.HTTP_201_CREATED)
async def create_obligation(
    data: ObligationCreate,
    db: AsyncSession = DatabaseSession,
):
    """
    Persists a confirmed obligation to the database after human review.
    """
    return await ObligationService.create(db, data)


@router.get("", response_model=ObligationListResponse)
async def list_obligations(
    obligation_type: Optional[ObligationType] = Query(None, description="Filter by direction: OWED_BY_ME or OWED_TO_ME"),
    status: Optional[ObligationStatus] = Query(None, description="Filter by status"),
    search: Optional[str] = Query(None, description="Keyword search in action, owner, beneficiary"),
    is_at_risk: Optional[bool] = Query(None, description="Filter by risk criteria"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: AsyncSession = DatabaseSession,
):
    """
    List obligations with comprehensive filtering and search.
    """
    return await ObligationService.list_all(
        session=db,
        obligation_type=obligation_type,
        status=status,
        search=search,
        is_at_risk=is_at_risk,
        limit=limit,
        offset=offset,
    )


@router.get("/{obligation_id}", response_model=ObligationResponse)
async def get_obligation(
    obligation_id: str,
    db: AsyncSession = DatabaseSession,
):
    """
    Retrieve single obligation by ID.
    """
    obligation = await ObligationService.get_by_id(db, obligation_id)
    if not obligation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Obligation with ID '{obligation_id}' not found",
        )
    return obligation


@router.patch("/{obligation_id}", response_model=ObligationResponse)
async def update_obligation(
    obligation_id: str,
    data: ObligationUpdate,
    db: AsyncSession = DatabaseSession,
):
    """
    Update editable fields of an obligation.
    """
    updated = await ObligationService.update(db, obligation_id, data)
    if not updated:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Obligation with ID '{obligation_id}' not found",
        )
    return updated


@router.patch("/{obligation_id}/status", response_model=ObligationResponse)
async def update_obligation_status(
    obligation_id: str,
    status_data: ObligationStatusUpdate,
    db: AsyncSession = DatabaseSession,
):
    """
    Execute a controlled status transition with domain-level validation.
    """
    try:
        updated = await ObligationService.update_status(db, obligation_id, status_data)
        if not updated:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Obligation with ID '{obligation_id}' not found",
            )
        return updated
    except InvalidStatusTransitionError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e),
        )


@router.delete("/{obligation_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_obligation(
    obligation_id: str,
    db: AsyncSession = DatabaseSession,
):
    """
    Delete an obligation.
    """
    deleted = await ObligationService.delete(db, obligation_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Obligation with ID '{obligation_id}' not found",
        )
    return None


@router.post("/edges", response_model=ObligationEdgeResponse, status_code=status.HTTP_201_CREATED)
async def create_obligation_edge(
    data: ObligationEdgeCreate,
    db: AsyncSession = DatabaseSession,
):
    """
    Create a bidirectional or dependency edge between two obligations.
    """
    # Verify both exist
    from_ob = await ObligationService.get_by_id(db, data.from_obligation_id)
    to_ob = await ObligationService.get_by_id(db, data.to_obligation_id)
    if not from_ob or not to_ob:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="One or both obligation IDs in edge not found",
        )
    return await ObligationService.create_edge(db, data)
