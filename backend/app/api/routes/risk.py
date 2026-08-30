from typing import Optional
from fastapi import APIRouter, Query, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import DatabaseSession
from app.core.status_machine import (
    ObligationStatus,
    ObligationType,
    RiskLevel,
)
from app.models.auth import User, Workspace
from app.core.auth_deps import get_current_user, get_current_workspace
from app.schemas.obligation import BulkRiskResponse
from app.services.obligation_service import ObligationService

router = APIRouter(prefix="/risk", tags=["Risk & Proactive Rescue"])


@router.get("", response_model=BulkRiskResponse)
async def get_bulk_risks(
    risk_level: Optional[RiskLevel] = Query(None, description="Filter by risk level: CRITICAL, HIGH, MEDIUM, LOW"),
    owner: Optional[str] = Query(None, description="Filter by owner name"),
    obligation_type: Optional[ObligationType] = Query(None, description="Filter by direction"),
    status: Optional[ObligationStatus] = Query(None, description="Filter by obligation status"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: AsyncSession = DatabaseSession,
    workspace: Workspace = Depends(get_current_workspace),
    user: User = Depends(get_current_user),
):
    """
    Retrieve active obligations assessed by the Proactive Risk Engine for active workspace,
    prioritized by failure probability, deadline urgency, and graph fan-out impact.
    """
    return await ObligationService.get_bulk_risks(
        session=db,
        risk_level=risk_level,
        owner=owner,
        obligation_type=obligation_type,
        status=status,
        limit=limit,
        offset=offset,
        workspace_id=workspace.id,
    )
