"""
Phase 20 Semantic Event & Evidence Interpreter.

Interprets inbound asynchronous events and candidate evidence artifacts
using versioned LLM prompts, strict schema validation, and zero autonomous
state mutation invariants.
"""

import time
import hashlib
from typing import Optional, Dict, Any, Tuple
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.logging import logger
from app.core.prompt_registry import PromptRegistry
from app.services.event_classifier import EventClassifier
from app.core.status_machine import EventSemanticRole
from app.schemas.llm import (
    EventSemanticProposal,
    EvidenceInterpretationProposal,
    LLMValidationStatus,
)
from app.models.llm_analysis import LLMAnalysisRecord
from app.services.llm.base import BaseLLMProvider
from app.services.llm.provider_registry import LLMProviderRegistry
from app.services.llm.validation_service import LLMValidationService


class SemanticEventInterpreter:
    """
    Interprets external asynchronous events for nuanced human semantics.
    """

    def __init__(self, llm_provider: Optional[BaseLLMProvider] = None):
        self.llm_provider = llm_provider

    async def interpret_event(
        self,
        content: str,
        provider_name: str = "slack",
        stream_key: str = "default",
        workspace_id: str = "ws-default",
        session: Optional[AsyncSession] = None,
    ) -> Tuple[EventSemanticProposal, LLMValidationStatus]:
        start_time = time.time()
        input_hash = hashlib.sha256(content.strip().encode("utf-8")).hexdigest()

        # Step 1: Run deterministic heuristic classifier baseline
        det_role, det_conf, det_reason = EventClassifier.classify(content)

        # Step 2: Invoke LLM Semantic Interpreter
        provider = self.llm_provider or LLMProviderRegistry.get()
        prompt_tmpl = PromptRegistry.get("event_semantics", version="v1")
        system_prompt = prompt_tmpl.system_prompt if prompt_tmpl else "Classify event semantics."
        user_prompt = prompt_tmpl.format_user_prompt(
            provider=provider_name,
            stream_key=stream_key,
            content=content,
        ) if prompt_tmpl else content

        proposal: Optional[EventSemanticProposal] = None
        validation_status = LLMValidationStatus.VALID
        fallback_used = False

        if settings.LLM_ENABLED:
            try:
                proposal = await provider.generate_structured(
                    system_prompt=system_prompt,
                    user_prompt=user_prompt,
                    schema_cls=EventSemanticProposal,
                    timeout_seconds=settings.LLM_TIMEOUT_SECONDS,
                )
                validation_status, errors = LLMValidationService.validate_event_semantics(proposal)
                if validation_status != LLMValidationStatus.VALID:
                    logger.warning(f"Event semantic proposal validation failed: {errors}")
            except Exception as e:
                logger.error(f"Semantic event interpretation failed: {e}. Falling back to deterministic classifier.")
                fallback_used = True
                validation_status = LLMValidationStatus.FALLBACK_APPLIED

        if not proposal or validation_status != LLMValidationStatus.VALID:
            # Deterministic fallback
            proposal = EventSemanticProposal(
                semantic_role=det_role.value if hasattr(det_role, "value") else str(det_role),
                confidence=det_conf,
                summary=det_reason,
                evidence_strength=0.85 if det_role == EventSemanticRole.COMPLETION_SIGNAL else 0.40,
                reasoning=det_reason,
                provider="deterministic_fallback",
            )

        latency_ms = round((time.time() - start_time) * 1000, 2)

        # Step 3: Persist LLMAnalysisRecord audit trail
        if session:
            try:
                record = LLMAnalysisRecord(
                    workspace_id=workspace_id,
                    source_ref=f"{provider_name}:{stream_key}",
                    analysis_type="EVENT_SEMANTICS",
                    provider=provider.provider_name if provider else "mock",
                    model=provider.model_name if provider else "mock-intelligence-v1",
                    prompt_version="v1",
                    schema_version="event-semantic-proposal-v1",
                    input_hash=input_hash,
                    raw_prompt_redacted=content[:500],
                    structured_output=proposal.model_dump(),
                    confidence=proposal.confidence,
                    validation_status=validation_status.value,
                    grounding_status="GROUNDED",
                    fallback_used=fallback_used,
                    latency_ms=latency_ms,
                    tokens_in=len(content.split()) * 2,
                    tokens_out=45,
                )
                session.add(record)
                await session.commit()
            except Exception as e:
                logger.error(f"Failed to persist event semantic analysis record: {e}")
                await session.rollback()

        return proposal, validation_status

    async def interpret_evidence(
        self,
        obligation_id: str,
        action: str,
        owner: str,
        deadline: Optional[str],
        evidence_content: str,
        workspace_id: str = "ws-default",
        session: Optional[AsyncSession] = None,
    ) -> Tuple[EvidenceInterpretationProposal, LLMValidationStatus]:
        start_time = time.time()
        provider = self.llm_provider or LLMProviderRegistry.get()
        prompt_tmpl = PromptRegistry.get("evidence_interpretation", version="v1")
        system_prompt = prompt_tmpl.system_prompt if prompt_tmpl else "Interpret candidate evidence."
        user_prompt = prompt_tmpl.format_user_prompt(
            obligation_id=obligation_id,
            action=action,
            owner=owner,
            deadline=deadline or "None",
            evidence_content=evidence_content,
        ) if prompt_tmpl else evidence_content

        try:
            proposal = await provider.generate_structured(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                schema_cls=EvidenceInterpretationProposal,
                timeout_seconds=settings.LLM_TIMEOUT_SECONDS,
            )
            validation_status, _ = LLMValidationService.validate_evidence_interpretation(proposal)
        except Exception as e:
            logger.error(f"Evidence interpretation LLM call failed: {e}")
            proposal = EvidenceInterpretationProposal(
                evidence_category="AMBIGUOUS",
                confidence=0.50,
                extracted_action=action,
                evidence_strength=0.30,
                reasoning="Fallback evidence interpretation.",
                provider="deterministic_fallback",
            )
            validation_status = LLMValidationStatus.FALLBACK_APPLIED

        return proposal, validation_status
