"""
FastAPI Routes for Phase 16 Organizational Memory, Semantic Context & Historical Reasoning.
"""

from typing import Optional, List
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, desc

from app.core.database import get_db
from app.models.auth import User, Workspace
from app.models.obligation import Obligation
from app.models.memory import OrganizationalMemory
from app.core.auth_deps import get_current_user, get_current_workspace
from app.core.status_machine import (
    MemoryType,
    PatternType,
)
from app.schemas.memory import (
    MemoryContextResponse,
    MemoryRetrievalItem,
    HistoricalPatternItem,
    HistoricalOwnerAnalyticsResponse,
    RecurringObligationItem,
    OrganizationalMemoryCreate,
    OrganizationalMemoryResponse,
    MemoryListResponse,
)
from app.services.intelligence.memory.semantic_context_engine import SemanticContextEngine
from app.services.intelligence.memory.memory_formation_service import MemoryFormationService
from app.services.intelligence.memory.memory_retrieval_service import MemoryRetrievalService
from app.services.intelligence.memory.pattern_detection_service import PatternDetectionService
from app.services.intelligence.memory.historical_owner_analytics_service import HistoricalOwnerAnalyticsService


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


router = APIRouter(prefix="/intelligence/memory", tags=["Organizational Memory"])


@router.get("/{obligation_id}", response_model=MemoryContextResponse)
async def get_obligation_memory_context(
    obligation_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    workspace: Workspace = Depends(get_current_workspace),
):
    """
    Retrieves full organizational memory context for an obligation including semantic representation,
    comparable historical commitments, recurring patterns, owner analytics, and recurring cadences.
    """
    obligation = await db.get(Obligation, obligation_id)
    if not obligation or obligation.workspace_id != workspace.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Obligation '{obligation_id}' not found.",
        )

    # 1. Semantic extraction
    sem = SemanticContextEngine.extract_semantic_representation(
        text=obligation.action,
        owner=obligation.owner,
        deadline=obligation.deadline,
        obligation_type=obligation.obligation_type.value if hasattr(obligation.obligation_type, "value") else str(obligation.obligation_type),
    )

    # 2. Retrieve memories
    all_retrieved = await MemoryRetrievalService.retrieve_for_obligation(
        db, obligation, min_relevance=0.25, limit=20
    )

    similar_obs = [m for m in all_retrieved if m.memory.memory_type == MemoryType.OBLIGATION_OUTCOME]
    intervention_hist = [m for m in all_retrieved if m.memory.memory_type == MemoryType.INTERVENTION_OUTCOME]

    # 3. Detect patterns
    patterns = await PatternDetectionService.detect_patterns_for_obligation(
        db, obligation, all_retrieved
    )
    blockers = [p for p in patterns if p.pattern_type == PatternType.RECURRING_BLOCKER_PATTERN]

    # 4. Recurring commitment cadence
    recurring_cadence = await PatternDetectionService.detect_recurring_commitment(
        db, obligation, all_retrieved
    )

    # 5. Owner analytics
    owner_analytics: Optional[HistoricalOwnerAnalyticsResponse] = None
    if obligation.owner:
        owner_analytics = await HistoricalOwnerAnalyticsService.get_owner_analytics(
            db, obligation.owner, workspace_id=workspace.id
        )

    context_status = "AVAILABLE" if (similar_obs or patterns or owner_analytics) else "NO_COMPARABLE_HISTORY"

    # Explanation construction
    explanation_parts = []
    if similar_obs:
        explanation_parts.append(f"{len(similar_obs)} comparable historical commitment(s) observed")
    if patterns:
        explanation_parts.append(f"{len(patterns)} recurring pattern(s) identified")
    if owner_analytics and owner_analytics.has_sufficient_history:
        explanation_parts.append(f"Owner has {owner_analytics.total_commitments_observed} observed commitments")
    explanation = "; ".join(explanation_parts) if explanation_parts else "No significant comparable history observed in organizational memory."

    return MemoryContextResponse(
        obligation_id=obligation.id,
        context_status=context_status,
        semantic_representation=sem,
        similar_obligations=similar_obs[:10],
        historical_patterns=patterns,
        recurring_blockers=blockers,
        intervention_history=intervention_hist[:5],
        owner_analytics=owner_analytics,
        recurring_commitment=recurring_cadence,
        confidence=0.90 if similar_obs else 0.50,
        explanation=explanation,
        evaluated_at=utc_now(),
    )


@router.get("/search", response_model=List[MemoryRetrievalItem])
async def search_memories(
    query: Optional[str] = Query(None, description="Search text / deliverable"),
    memory_type: Optional[MemoryType] = Query(None, description="Filter by memory type"),
    owner_id: Optional[str] = Query(None, description="Filter by owner"),
    min_relevance: float = Query(0.2, ge=0.0, le=1.0),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    workspace: Workspace = Depends(get_current_workspace),
):
    """
    Searches organizational memories across the workspace.
    """
    return await MemoryRetrievalService.search_memories(
        session=db,
        workspace_id=workspace.id,
        query=query,
        memory_type=memory_type,
        owner_id=owner_id,
        min_relevance=min_relevance,
        limit=limit,
        offset=offset,
    )


@router.get("/patterns", response_model=List[HistoricalPatternItem])
async def get_workspace_patterns(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    workspace: Workspace = Depends(get_current_workspace),
):
    """
    Returns workspace-wide established organizational patterns.
    """
    memories = await MemoryRetrievalService.search_memories(
        session=db,
        workspace_id=workspace.id,
        min_relevance=0.0,
        limit=100,
    )

    if not memories:
        return []

    dummy_ob = Obligation(
        id="ws-summary",
        workspace_id=workspace.id,
        action="Workspace Wide Commitment Patterns",
    )
    return await PatternDetectionService.detect_patterns_for_obligation(
        db, dummy_ob, memories
    )


@router.get("/owners/{owner_id}", response_model=HistoricalOwnerAnalyticsResponse)
async def get_owner_analytics(
    owner_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    workspace: Workspace = Depends(get_current_workspace),
):
    """
    Returns strictly factual, neutral commitment history analytics for a specific owner.
    """
    return await HistoricalOwnerAnalyticsService.get_owner_analytics(
        session=db,
        owner_id=owner_id,
        workspace_id=workspace.id,
    )


@router.post("/form", response_model=OrganizationalMemoryResponse, status_code=status.HTTP_201_CREATED)
async def form_memory_manually(
    payload: OrganizationalMemoryCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    workspace: Workspace = Depends(get_current_workspace),
):
    """
    Creation of an organizational memory record.
    """
    mem = await MemoryFormationService.create_memory(
        session=db,
        payload=payload,
        workspace_id=workspace.id,
    )
    return OrganizationalMemoryResponse.model_validate(mem)
