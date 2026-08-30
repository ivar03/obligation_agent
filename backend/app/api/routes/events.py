from typing import Optional, List, Dict, Any
from fastapi import APIRouter, status, Query, HTTPException, Request, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import DatabaseSession, get_db
from app.core.status_machine import EventSemanticRole
from app.schemas.obligation import (
    ExternalEvent,
    EventAnalysisResponse,
    EventIngestionResponse,
    IngestRawEventRequest,
    EventSimulateRequest,
    IngestedEventResponse,
    IngestedEventListResponse,
    IngestionResultResponse,
    ProviderInfo,
)
from app.services.event_ingestion_service import EventIngestionService
from app.services.providers.registry import provider_registry

router = APIRouter(prefix="/events", tags=["Events & Evidence"])


@router.post("/analyze", response_model=EventAnalysisResponse)
async def analyze_event(
    event: ExternalEvent,
    db: AsyncSession = DatabaseSession,
):
    """
    Stateless event analysis.
    Classifies event semantic role and calculates correlation against active obligations without saving.
    """
    return await EventIngestionService.analyze_event(db, event)


@router.post("/ingest", response_model=IngestionResultResponse, status_code=status.HTTP_201_CREATED)
async def ingest_provider_event(
    request: IngestRawEventRequest,
    db: AsyncSession = DatabaseSession,
):
    """
    Stateful ingestion of provider-specific raw payload.
    Resolves provider adapter, normalizes payload, deduplicates, correlates, and audits event.
    """
    try:
        return await EventIngestionService.ingest_from_provider(
            session=db,
            provider_name=request.provider,
            raw_payload=request.payload,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.post("/simulate", response_model=IngestionResultResponse, status_code=status.HTTP_201_CREATED)
async def simulate_event(
    payload: EventSimulateRequest,
    db: AsyncSession = DatabaseSession,
):
    """
    Development simulation of canonical test scenarios using MockProvider.
    """
    return await EventIngestionService.simulate_scenario(db, payload)


@router.get("/providers", response_model=List[ProviderInfo])
async def list_providers():
    """
    Lists all registered provider adapters and their supported capabilities.
    """
    return provider_registry.list_providers()


@router.get("", response_model=IngestedEventListResponse)
async def list_ingested_events(
    provider: Optional[str] = Query(None, description="Filter by provider: mock, slack, etc."),
    semantic_role: Optional[EventSemanticRole] = Query(None, description="Filter by semantic role"),
    processing_status: Optional[str] = Query(None, description="Filter by status: PROCESSED, DUPLICATE, etc."),
    source_ref: Optional[str] = Query(None, description="Filter by external source reference"),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: AsyncSession = DatabaseSession,
):
    """
    Lists historical ingested event audit records.
    """
    return await EventIngestionService.list_events(
        session=db,
        provider=provider,
        semantic_role=semantic_role,
        processing_status=processing_status,
        source_ref=source_ref,
        limit=limit,
        offset=offset,
    )


@router.get("/{id}", response_model=IngestedEventResponse)
async def get_ingested_event(
    id: str,
    db: AsyncSession = DatabaseSession,
):
    """
    Retrieves full audit inspection details for a single ingested event.
    """
    return await EventIngestionService.get_event_by_id(db, id)


@router.post("", response_model=EventIngestionResponse, status_code=status.HTTP_201_CREATED)
async def ingest_event_legacy(
    event: ExternalEvent,
    db: AsyncSession = DatabaseSession,
):
    """
    Backwards-compatible normalized event ingestion.
    """
    return await EventIngestionService.ingest_event(db, event)
