from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.api.deps import DatabaseSession
from app.models.auth import User, Workspace
from app.core.auth_deps import get_current_user, get_current_workspace
from app.schemas.obligation import DashboardSummaryResponse
from app.services.obligation_service import ObligationService

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])


@router.get("/summary", response_model=DashboardSummaryResponse)
async def get_dashboard_summary(
    db: AsyncSession = DatabaseSession,
    workspace: Workspace = Depends(get_current_workspace),
    user: User = Depends(get_current_user),
):
    """
    Retrieve aggregated metrics and obligations for You Owe, Others Owe You, and At Risk sections for active workspace.
    """
    return await ObligationService.get_dashboard_summary(db, workspace_id=workspace.id)
