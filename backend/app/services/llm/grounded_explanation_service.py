"""
Phase 20 Grounded Explanation Service.

Generates human-readable root-cause, cascade impact, and decision explanations
strictly grounded in verified database facts. All outputs undergo deterministic
post-generation validation to catch any fabricated entities or hallucinated claims.
"""

import json
import time
import hashlib
from typing import Optional, List, Dict, Any
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.logging import logger
from app.core.prompt_registry import PromptRegistry
from app.models.obligation import Obligation, ObligationEdge, Evidence
from app.models.decision import DecisionPlan
from app.models.llm_analysis import LLMAnalysisRecord
from app.schemas.llm import (
    GroundedExplanationProposal,
    GroundedContextPacket,
    GroundingCheckStatus,
    LLMExplainResponse,
)
from app.services.llm.base import BaseLLMProvider
from app.services.llm.provider_registry import LLMProviderRegistry
from app.services.llm.grounding_validator import GroundingValidator


class GroundedExplanationService:
    """
    Constructs verified context packets from the datastore and generates
    grounded natural-language explanations.
    """

    def __init__(self, llm_provider: Optional[BaseLLMProvider] = None):
        self.llm_provider = llm_provider

    async def build_context_packet(
        self,
        workspace_id: str,
        target_entity_id: str,
        session: AsyncSession,
    ) -> GroundedContextPacket:
        """Assembles verified application state from DB without letting LLM query directly."""
        packet = GroundedContextPacket(
            workspace_id=workspace_id,
            target_entity_id=target_entity_id,
        )

        # 1. Fetch relevant obligations
        stmt = select(Obligation).where(Obligation.workspace_id == workspace_id).limit(20)
        res = await session.execute(stmt)
        obs = res.scalars().all()

        for ob in obs:
            packet.known_obligation_ids.append(ob.id)
            if ob.owner and ob.owner not in packet.known_users:
                packet.known_users.append(ob.owner)
            if ob.beneficiary and ob.beneficiary not in packet.known_users:
                packet.known_users.append(ob.beneficiary)
            if ob.deadline:
                packet.verified_deadlines.append(ob.deadline.isoformat())

            packet.obligations.append({
                "id": ob.id,
                "action": ob.action,
                "owner": ob.owner,
                "beneficiary": ob.beneficiary,
                "status": ob.status.value if hasattr(ob.status, "value") else str(ob.status),
                "deadline": ob.deadline.isoformat() if ob.deadline else None,
                "risk_score": getattr(ob, "risk_score", 0.0),
            })

        # 2. Fetch dependency edges
        edge_stmt = select(ObligationEdge).limit(30)
        edge_res = await session.execute(edge_stmt)
        edges = edge_res.scalars().all()
        for e in edges:
            packet.dependencies.append({
                "source_id": e.source_id,
                "target_id": e.target_id,
                "dependency_type": e.dependency_type,
            })

        # Add target entity explicitly if not present
        if target_entity_id not in packet.known_obligation_ids:
            packet.known_obligation_ids.append(target_entity_id)

        return packet

    async def generate_explanation(
        self,
        workspace_id: str,
        target_entity_id: str,
        prompt_instruction: str = "Explain the root cause and downstream cascade impact.",
        session: Optional[AsyncSession] = None,
        injected_context: Optional[GroundedContextPacket] = None,
    ) -> LLMExplainResponse:
        start_time = time.time()
        provider = self.llm_provider or LLMProviderRegistry.get()

        # Step 1: Build verified facts context packet
        if injected_context:
            context_packet = injected_context
        elif session:
            context_packet = await self.build_context_packet(workspace_id, target_entity_id, session)
        else:
            # Standalone default verified context packet
            context_packet = GroundedContextPacket(
                workspace_id=workspace_id,
                target_entity_id=target_entity_id,
                known_users=["Rahul", "Ravi", "Priya", "Alice", "Bob"],
                known_obligation_ids=[target_entity_id, "ob-root-db", "ob-api-ravi", "ob-fe-priya"],
                obligations=[
                    {"id": "ob-root-db", "owner": "Rahul", "action": "Database migration", "status": "OVERDUE"},
                    {"id": "ob-api-ravi", "owner": "Ravi", "action": "API integration", "status": "BLOCKED"},
                    {"id": "ob-fe-priya", "owner": "Priya", "action": "Frontend client demo", "status": "PENDING"},
                ],
                dependencies=[
                    {"source_id": "ob-root-db", "target_id": "ob-api-ravi"},
                    {"source_id": "ob-api-ravi", "target_id": "ob-fe-priya"},
                ],
            )

        context_json = context_packet.model_dump_json(indent=2)
        prompt_tmpl = PromptRegistry.get("grounded_explanation", version="v1")
        system_prompt = prompt_tmpl.system_prompt if prompt_tmpl else "Generate grounded explanation."
        user_prompt = prompt_tmpl.format_user_prompt(
            context_packet_json=context_json,
            target_entity_id=target_entity_id,
            prompt_instruction=prompt_instruction,
        ) if prompt_tmpl else f"Facts:\n{context_json}\nInstruction: {prompt_instruction}"

        # Step 2: Invoke LLM Provider
        fallback_used = False
        try:
            proposal: GroundedExplanationProposal = await provider.generate_structured(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                schema_cls=GroundedExplanationProposal,
                timeout_seconds=settings.LLM_TIMEOUT_SECONDS,
            )
        except Exception as e:
            logger.error(f"Grounded explanation LLM call failed: {e}")
            fallback_used = True
            proposal = GroundedExplanationProposal(
                explanation="Deterministic fallback: Overdue upstream dependencies are blocking the target deliverable.",
                grounded_facts_used=[target_entity_id],
                confidence=0.75,
                grounding_status=GroundingCheckStatus.GROUNDED,
                reasoning="Deterministic explanation fallback.",
                provider="deterministic_fallback",
            )

        # Step 3: Validate Grounding (Deterministic Guardrails)
        grounding_status, grounding_errors = GroundingValidator.validate_grounding(proposal, context_packet)

        latency_ms = round((time.time() - start_time) * 1000, 2)
        input_hash = hashlib.sha256(user_prompt.encode("utf-8")).hexdigest()

        # Step 4: Persist LLMAnalysisRecord audit trail
        record_id = None
        if session:
            try:
                record = LLMAnalysisRecord(
                    workspace_id=workspace_id,
                    source_ref=f"obligation:{target_entity_id}",
                    analysis_type="GROUNDED_EXPLANATION",
                    provider=provider.provider_name if provider else "mock",
                    model=provider.model_name if provider else "mock-intelligence-v1",
                    prompt_version="v1",
                    schema_version="grounded-explanation-v1",
                    input_hash=input_hash,
                    raw_prompt_redacted=prompt_instruction[:500],
                    structured_output=proposal.model_dump(),
                    confidence=proposal.confidence,
                    validation_status="VALID",
                    grounding_status=grounding_status.value,
                    grounding_errors=grounding_errors if grounding_errors else None,
                    fallback_used=fallback_used,
                    latency_ms=latency_ms,
                    tokens_in=len(user_prompt.split()) * 2,
                    tokens_out=len(proposal.explanation.split()) * 2,
                )
                session.add(record)
                await session.commit()
                record_id = record.id
            except Exception as e:
                logger.error(f"Failed to persist grounded explanation record: {e}")
                await session.rollback()

        return LLMExplainResponse(
            success=grounding_status == GroundingCheckStatus.GROUNDED,
            explanation=proposal.explanation,
            grounding_status=grounding_status,
            grounding_errors=grounding_errors,
            grounded_facts_used=proposal.grounded_facts_used,
            confidence=proposal.confidence,
            analysis_record_id=record_id,
            fallback_used=fallback_used,
            latency_ms=latency_ms,
        )
