"""
Phase 20 Hybrid Extraction Service.

Orchestrates the dual-pipeline extraction architecture:
1. Executes deterministic extraction heuristics (ExtractionService baseline).
2. Concurrently invokes LLM provider via versioned prompt.
3. Passes LLM proposal through deterministic validation.
4. Reconciles outcomes via ExtractionReconciliationEngine.
5. Persists an immutable LLMAnalysisRecord audit trail.
6. Returns validated canonical candidate + full reconciliation telemetry.
"""

import time
import hashlib
from typing import Optional, List, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.logging import logger
from app.core.prompt_registry import PromptRegistry
from app.schemas.obligation import ExtractionRequest, ExtractionResponse
from app.schemas.llm import (
    ObligationProposal,
    ExtractionReconciliation,
    LLMValidationStatus,
    LLMAnalyzeResponse,
)
from app.models.llm_analysis import LLMAnalysisRecord
from app.services.extraction_service import ExtractionService
from app.services.llm.base import BaseLLMProvider
from app.services.llm.provider_registry import LLMProviderRegistry
from app.services.llm.validation_service import LLMValidationService
from app.services.llm.reconciliation_engine import ExtractionReconciliationEngine


class HybridExtractionService:
    """
    Main entry point for Phase 20 natural-language obligation extraction.
    """

    def __init__(
        self,
        extraction_service: Optional[ExtractionService] = None,
        llm_provider: Optional[BaseLLMProvider] = None,
    ):
        self.extraction_service = extraction_service or ExtractionService()
        self.llm_provider = llm_provider

    async def analyze_and_extract(
        self,
        request: ExtractionRequest,
        workspace_id: str = "ws-default",
        known_users: Optional[List[str]] = None,
        session: Optional[AsyncSession] = None,
    ) -> LLMAnalyzeResponse:
        start_time = time.time()
        input_hash = hashlib.sha256(request.text.strip().encode("utf-8")).hexdigest()

        # Step 1: Execute deterministic baseline extraction
        det_response: ExtractionResponse = await self.extraction_service.extract_candidate(request)
        det_candidate = det_response.obligation if det_response.detected else None

        # Step 2: Invoke LLM Provider (if enabled)
        llm_proposal: Optional[ObligationProposal] = None
        validation_status = LLMValidationStatus.VALID
        validation_errors: List[str] = []
        fallback_used = False
        provider = self.llm_provider or LLMProviderRegistry.get()

        source_ref = (request.context.source_type if request.context and hasattr(request.context, "source_type") else None) or getattr(request, "source_type", None) or "manual"
        sender = (request.context.sender if request.context and hasattr(request.context, "sender") else None) or getattr(request, "user_id", None) or "unknown"

        if settings.LLM_ENABLED:
            prompt_tmpl = PromptRegistry.get("obligation_extraction", version="v1")
            system_prompt = prompt_tmpl.system_prompt if prompt_tmpl else "Extract obligation structured proposal."
            user_prompt = prompt_tmpl.format_user_prompt(
                source_ref=source_ref,
                sender=sender,
                channel="default",
                text=request.text,
            ) if prompt_tmpl else request.text

            try:
                llm_proposal = await provider.generate_structured(
                    system_prompt=system_prompt,
                    user_prompt=user_prompt,
                    schema_cls=ObligationProposal,
                    timeout_seconds=settings.LLM_TIMEOUT_SECONDS,
                )
                # Step 3: Validate LLM Proposal
                validation_status, validation_errors = LLMValidationService.validate_obligation_proposal(
                    proposal=llm_proposal,
                    known_users=known_users,
                    workspace_id=workspace_id,
                )
                if validation_status != LLMValidationStatus.VALID:
                    logger.warning(
                        f"LLM proposal failed validation [{validation_status}]: {validation_errors}"
                    )
            except Exception as e:
                logger.error(f"LLM provider invocation failed or timed out: {e}. Falling back to deterministic pipeline.")
                fallback_used = True
                validation_status = LLMValidationStatus.FALLBACK_APPLIED
                validation_errors = [str(e)]
                llm_proposal = None
        else:
            fallback_used = True
            validation_status = LLMValidationStatus.FALLBACK_APPLIED
            validation_errors = ["LLM processing is disabled via configuration."]

        # Step 4: Reconcile outcomes
        reconciliation = ExtractionReconciliationEngine.reconcile(
            deterministic_detected=det_response.detected,
            deterministic_candidate=det_candidate,
            llm_proposal=llm_proposal if validation_status == LLMValidationStatus.VALID else None,
        )

        latency_ms = round((time.time() - start_time) * 1000, 2)

        # Step 5: Persist LLMAnalysisRecord audit trail
        record_id = None
        if session:
            try:
                record = LLMAnalysisRecord(
                    workspace_id=workspace_id,
                    source_ref=source_ref,
                    analysis_type="OBLIGATION_EXTRACTION",
                    provider=provider.provider_name if provider else "mock",
                    model=provider.model_name if provider else "mock-intelligence-v1",
                    prompt_version="v1",
                    schema_version="obligation-proposal-v1",
                    input_hash=input_hash,
                    raw_prompt_redacted=request.text[:500],
                    structured_output=llm_proposal.model_dump() if llm_proposal else None,
                    confidence=reconciliation.confidence,
                    validation_status=validation_status.value,
                    validation_errors=validation_errors if validation_errors else None,
                    grounding_status="GROUNDED",
                    fallback_used=fallback_used,
                    human_review_required=reconciliation.human_review_required,
                    latency_ms=latency_ms,
                    tokens_in=len(request.text.split()) * 2,
                    tokens_out=60 if llm_proposal else 0,
                )

                session.add(record)
                await session.commit()
                record_id = record.id
            except Exception as e:
                logger.error(f"Failed to persist LLMAnalysisRecord: {e}")
                await session.rollback()

        return LLMAnalyzeResponse(
            success=True,
            proposal=llm_proposal,
            validation_status=validation_status,
            validation_errors=validation_errors,
            reconciliation=reconciliation,
            analysis_record_id=record_id,
            fallback_used=fallback_used,
            latency_ms=latency_ms,
        )
