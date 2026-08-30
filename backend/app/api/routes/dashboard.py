from fastapi import APIRouter
from sqlalchemy.ext.asyncio import AsyncSession
from app.api.deps import DatabaseSession
from app.schemas.obligation import DashboardSummaryResponse
from app.services.obligation_service import ObligationService

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])


@router.get("/summary", response_model=DashboardSummaryResponse)
async def get_dashboard_summary(
    db: AsyncSession = DatabaseSession,
):
    """
    Retrieve aggregated metrics and obligations for You Owe, Others Owe You, and At Risk sections.
    """
    return await ObligationService.get_dashboard_summary(db)
