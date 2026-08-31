"""
Phase 20 LLM & Natural-Language Intelligence REST API.

Provides provider-neutral endpoints for natural-language interpretation,
hybrid extraction, semantic event understanding, grounded explanations,
and human review triage.
"""

from typing import Optional, List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.logging import logger
from app.core.metrics import metrics
from app.schemas.obligation import ExtractionRequest
from app.schemas.llm import (
    LLMAnalyzeRequest,
    LLMAnalyzeResponse,
    LLMExplainRequest,
    LLMExplainResponse,
    LLMReviewActionRequest,
    LLMProviderInfo,
    LLMValidationStatus,
    GroundingCheckStatus,
    ExtractionReconciliation,
    EventSemanticProposal,
)
from app.models.llm_analysis import LLMAnalysisRecord
from app.services.llm.provider_registry import LLMProviderRegistry
from app.services.llm.hybrid_extraction_service import HybridExtractionService
from app.services.llm.semantic_event_interpreter import SemanticEventInterpreter
from app.services.llm.grounded_explanation_service import GroundedExplanationService
from app.services.llm.rate_limiter import LLMRateLimiter

router = APIRouter(prefix="/api/intelligence/llm", tags=["LLM Intelligence"])


@router.get("/providers", response_model=Dict[str, Any])
async def list_providers():
    """Returns registered LLM providers and active provider."""
    return {
        "active_provider": LLMProviderRegistry.get_active_provider_name(),
        "registered_providers": LLMProviderRegistry.list_providers(),
    }


@router.get("/health", response_model=List[LLMProviderInfo])
async def check_llm_health():
    """Runs health checks on all registered LLM providers."""
    return await LLMProviderRegistry.get_all_health()


@router.post("/analyze", response_model=LLMAnalyzeResponse)
async def analyze_obligation_text(
    req: LLMAnalyzeRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Analyzes natural-language text for obligation commitments using the
    hybrid extraction pipeline (Deterministic Heuristics + LLM Proposal + Reconciliation).
    """
    workspace_id = req.workspace_id or "ws-default"

    # Rate limit check
    if not LLMRateLimiter.check_and_record(workspace_id):
        metrics.increment("llm.rate_limited_total", labels={"workspace": workspace_id})
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"LLM request rate limit exceeded for workspace '{workspace_id}'.",
        )

    metrics.increment("llm.requests_total", labels={"type": "analyze", "workspace": workspace_id})

    ext_req = ExtractionRequest(
        text=req.text,
        source_type=req.source_ref or "api_input",
        user_id=req.sender or "user",
    )

    provider = LLMProviderRegistry.get(req.provider) if req.provider else None
    service = HybridExtractionService(llm_provider=provider)

    try:
        resp = await service.analyze_and_extract(
            request=ext_req,
            workspace_id=workspace_id,
            session=db,
        )
        if resp.success:
            metrics.increment("llm.success_total", labels={"type": "analyze"})
            metrics.record_duration("llm.latency_ms", resp.latency_ms)
        else:
            metrics.increment("llm.failure_total", labels={"type": "analyze"})
        return resp
    except Exception as e:
        metrics.increment("llm.failure_total", labels={"type": "analyze"})
        logger.error(f"Error in /api/intelligence/llm/analyze: {e}")
        raise HTTPException(status_code=500, detail=f"LLM analysis failed: {str(e)}")


@router.post("/semantic-event", response_model=Dict[str, Any])
async def interpret_semantic_event(
    payload: Dict[str, Any],
    db: AsyncSession = Depends(get_db),
):
    """
    Classifies external asynchronous event semantics, actors, and deliverables.
    """
    content = payload.get("content") or payload.get("text") or ""
    provider_name = payload.get("provider", "slack")
    stream_key = payload.get("stream_key", "default")
    workspace_id = payload.get("workspace_id", "ws-default")

    if not content:
        raise HTTPException(status_code=400, detail="Missing required 'content' or 'text' field.")

    interpreter = SemanticEventInterpreter()
    proposal, val_status = await interpreter.interpret_event(
        content=content,
        provider_name=provider_name,
        stream_key=stream_key,
        workspace_id=workspace_id,
        session=db,
    )

    return {
        "success": True,
        "proposal": proposal.model_dump(),
        "validation_status": val_status.value,
    }


@router.post("/explain", response_model=LLMExplainResponse)
async def generate_grounded_explanation(
    req: LLMExplainRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Generates a natural-language explanation of root-cause or cascade impact,
    strictly validated against database-verified ground facts.
    """
    workspace_id = req.workspace_id or "ws-default"
    provider = LLMProviderRegistry.get(req.provider) if req.provider else None
    service = GroundedExplanationService(llm_provider=provider)

    resp = await service.generate_explanation(
        workspace_id=workspace_id,
        target_entity_id=req.target_entity_id,
        prompt_instruction=req.prompt_instruction or "Explain root-cause and downstream impacts.",
        session=db,
    )
    return resp


@router.get("/history", response_model=List[Dict[str, Any]])
async def list_analysis_history(
    workspace_id: str = Query("ws-default"),
    analysis_type: Optional[str] = None,
    limit: int = Query(50, le=200),
    db: AsyncSession = Depends(get_db),
):
    """Lists persistent LLM analysis audit records for the workspace."""
    stmt = select(LLMAnalysisRecord).where(LLMAnalysisRecord.workspace_id == workspace_id)
    if analysis_type:
        stmt = stmt.where(LLMAnalysisRecord.analysis_type == analysis_type)
    stmt = stmt.order_by(desc(LLMAnalysisRecord.created_at)).limit(limit)

    res = await db.execute(stmt)
    records = res.scalars().all()

    return [
        {
            "id": r.id,
            "workspace_id": r.workspace_id,
            "source_ref": r.source_ref,
            "analysis_type": r.analysis_type,
            "provider": r.provider,
            "model": r.model,
            "prompt_version": r.prompt_version,
            "confidence": r.confidence,
            "validation_status": r.validation_status,
            "grounding_status": r.grounding_status,
            "fallback_used": r.fallback_used,
            "human_review_required": r.human_review_required,
            "human_review_status": r.human_review_status,
            "latency_ms": r.latency_ms,
            "created_at": r.created_at.isoformat(),
        }
        for r in records
    ]


@router.get("/history/{record_id}", response_model=Dict[str, Any])
async def get_analysis_record(
    record_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Retrieves full details of a specific LLM analysis record."""
    record = await db.get(LLMAnalysisRecord, record_id)
    if not record:
        raise HTTPException(status_code=404, detail=f"LLMAnalysisRecord '{record_id}' not found.")

    return {
        "id": record.id,
        "workspace_id": record.workspace_id,
        "source_ref": record.source_ref,
        "analysis_type": record.analysis_type,
        "provider": record.provider,
        "model": record.model,
        "prompt_version": record.prompt_version,
        "schema_version": record.schema_version,
        "input_hash": record.input_hash,
        "raw_prompt_redacted": record.raw_prompt_redacted,
        "structured_output": record.structured_output,
        "confidence": record.confidence,
        "validation_status": record.validation_status,
        "validation_errors": record.validation_errors,
        "grounding_status": record.grounding_status,
        "grounding_errors": record.grounding_errors,
        "fallback_used": record.fallback_used,
        "human_review_required": record.human_review_required,
        "human_review_status": record.human_review_status,
        "reviewer_notes": record.reviewer_notes,
        "latency_ms": record.latency_ms,
        "tokens_in": record.tokens_in,
        "tokens_out": record.tokens_out,
        "created_at": record.created_at.isoformat(),
    }


@router.post("/review/{record_id}", response_model=Dict[str, Any])
async def review_analysis_record(
    record_id: str,
    req: LLMReviewActionRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Human-in-the-loop triage action on an ambiguous or gated proposal.
    Action can be 'accept', 'reject', or 'edit'.
    """
    record = await db.get(LLMAnalysisRecord, record_id)
    if not record:
        raise HTTPException(status_code=404, detail=f"LLMAnalysisRecord '{record_id}' not found.")

    action_norm = req.action.upper()
    if action_norm not in ["ACCEPTED", "REJECTED", "EDITED", "ACCEPT", "REJECT", "EDIT"]:
        raise HTTPException(status_code=400, detail="Action must be 'accept', 'reject', or 'edit'.")

    status_str = "ACCEPTED" if "ACCEPT" in action_norm else ("REJECTED" if "REJECT" in action_norm else "EDITED")
    record.human_review_status = status_str
    record.human_review_required = False
    record.reviewer_notes = req.reviewer_notes

    if req.edited_proposal:
        record.structured_output = req.edited_proposal.model_dump()

    await db.commit()

    return {
        "success": True,
        "record_id": record.id,
        "human_review_status": record.human_review_status,
        "reviewer_notes": record.reviewer_notes,
    }
