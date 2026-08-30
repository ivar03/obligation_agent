from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.core.status_machine import ReconciliationStatus, WorkspaceRole
from app.models.auth import User, Workspace, WorkspaceMembership
from app.core.auth_deps import (
    get_current_user,
    get_current_membership,
    get_current_workspace,
    require_role,
)
from app.schemas.obligation import (
    ReconciliationRecordResponse,
    ReconciliationListResponse,
    ReconciliationResolutionRequest,
    ReconciliationDismissRequest,
)
from app.services.reconciliation_service import ReconciliationService

router = APIRouter(tags=["reconciliation"])


@router.get("/reconciliation", response_model=ReconciliationListResponse)
async def list_reconciliations(
    status: Optional[ReconciliationStatus] = Query(None, description="Filter by reconciliation status: CONFLICTING, CONSISTENT, AMBIGUOUS, RESOLVED_SUPPORTING, etc."),
    obligation_id: Optional[str] = Query(None, description="Filter by obligation ID"),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    workspace: Workspace = Depends(get_current_workspace),
    user: User = Depends(get_current_user),
):
    """
    List cross-provider reconciliation records with optional status and obligation filtering in active workspace.
    """
    return await ReconciliationService.list_reconciliations(
        session=db,
        status_filter=status,
        obligation_id=obligation_id,
        limit=limit,
        offset=offset,
        workspace_id=workspace.id,
    )


@router.get("/reconciliation/{reconciliation_id}", response_model=ReconciliationRecordResponse)
async def get_reconciliation(
    reconciliation_id: str,
    db: AsyncSession = Depends(get_db),
    workspace: Workspace = Depends(get_current_workspace),
    user: User = Depends(get_current_user),
):
    """
    Get detailed reconciliation record by ID with chronological multi-provider evidence provenance timeline.
    """
    return await ReconciliationService.get_reconciliation(
        session=db, reconciliation_id=reconciliation_id, workspace_id=workspace.id
    )


@router.get("/obligations/{obligation_id}/reconciliation", response_model=Optional[ReconciliationRecordResponse])
async def get_obligation_reconciliation(
    obligation_id: str,
    db: AsyncSession = Depends(get_db),
    workspace: Workspace = Depends(get_current_workspace),
    user: User = Depends(get_current_user),
):
    """
    Get active cross-provider reconciliation record for a specific obligation.
    """
    rec = await ReconciliationService.get_by_obligation(
        session=db, obligation_id=obligation_id, workspace_id=workspace.id
    )
    if not rec:
        # Also try reconciling on-the-fly if evidence exists
        rec_created = await ReconciliationService.reconcile_obligation(
            session=db, obligation_id=obligation_id, workspace_id=workspace.id
        )
        if rec_created:
            return await ReconciliationService.get_reconciliation(
                session=db, reconciliation_id=rec_created.id, workspace_id=workspace.id
            )
        return None
    return rec


@router.post("/reconciliation/{reconciliation_id}/resolve", response_model=ReconciliationRecordResponse)
async def resolve_reconciliation(
    reconciliation_id: str,
    payload: ReconciliationResolutionRequest,
    db: AsyncSession = Depends(get_db),
    workspace: Workspace = Depends(get_current_workspace),
    membership: WorkspaceMembership = Depends(require_role(WorkspaceRole.MEMBER)),
    user: User = Depends(get_current_user),
):
    """
    Authoritatively resolve a cross-provider contradiction or confirm completion.
    Validates lifecycle state machine transitions and unblocks downstream graph dependents on completion.
    """
    return await ReconciliationService.resolve_reconciliation(
        session=db,
        reconciliation_id=reconciliation_id,
        request=payload,
        workspace_id=workspace.id,
        actor_user_id=user.id,
    )


@router.post("/reconciliation/{reconciliation_id}/dismiss", response_model=ReconciliationRecordResponse)
async def dismiss_reconciliation(
    reconciliation_id: str,
    payload: ReconciliationDismissRequest = ReconciliationDismissRequest(),
    db: AsyncSession = Depends(get_db),
    workspace: Workspace = Depends(get_current_workspace),
    membership: WorkspaceMembership = Depends(require_role(WorkspaceRole.MEMBER)),
    user: User = Depends(get_current_user),
):
    """
    Dismiss an active contradiction record.
    """
    return await ReconciliationService.dismiss_reconciliation(
        session=db,
        reconciliation_id=reconciliation_id,
        request=payload,
        workspace_id=workspace.id,
        actor_user_id=user.id,
    )
