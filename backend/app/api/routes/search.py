"""
Phase 18 Global Search Endpoint.
"""

from typing import Optional, List
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.auth import WorkspaceMembership
from app.core.auth_deps import get_current_membership
from app.services.search_service import SearchService

router = APIRouter(prefix="/search", tags=["Global Search"])


@router.get("")
async def search_workspace(
    q: str = Query("", description="Search term"),
    type: Optional[List[str]] = Query(None, description="Filter entity types"),
    status: Optional[str] = Query(None, description="Status filter"),
    owner: Optional[str] = Query(None, description="Owner filter"),
    limit: int = Query(30, ge=1, le=100),
    membership: WorkspaceMembership = Depends(get_current_membership),
    session: AsyncSession = Depends(get_db),
):
    """
    Performs unified workspace-scoped search across obligations, people, events,
    decision plans, interventions, executions, and evidence.
    """
    return await SearchService.global_search(
        session=session,
        workspace_id=membership.workspace_id,
        query=q,
        entity_types=type,
        status_filter=status,
        owner_filter=owner,
        limit=limit,
    )
