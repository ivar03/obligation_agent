from typing import Dict, Any
from fastapi import APIRouter, status, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import DatabaseSession
from app.schemas.obligation import IngestionResultResponse
from app.services.event_ingestion_service import EventIngestionService

router = APIRouter(prefix="/webhooks", tags=["Webhooks"])


@router.post("/{provider}", response_model=IngestionResultResponse, status_code=status.HTTP_201_CREATED)
async def handle_provider_webhook(
    provider: str,
    payload: Dict[str, Any],
    db: AsyncSession = DatabaseSession,
):
    """
    Generic webhook receiver endpoint.
    Routes provider webhooks to the corresponding adapter for normalization and ingestion.
    """
    try:
        return await EventIngestionService.ingest_from_provider(
            session=db,
            provider_name=provider,
            raw_payload=payload,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
