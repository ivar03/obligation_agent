"""
Phase 20 Deterministic Development & Mock LLM Provider.

Provides deterministic, reproducible structured outputs for all standard scenarios:
- Explicit obligations
- Ambiguous ownership
- Conditional commitments
- Completion signals
- Progress updates
- Negative blockers / failures
- Grounded explanations
- Prompt injection containment
"""

import re
import json
import asyncio
from typing import Optional, Dict, Any, Type, TypeVar, List
from pydantic import BaseModel
from app.services.llm.base import BaseLLMProvider
from app.schemas.llm import (
    ObligationProposal,
    EventSemanticProposal,
    EvidenceInterpretationProposal,
    GroundedExplanationProposal,
    LLMProviderInfo,
    GroundingCheckStatus,
)

T = TypeVar("T", bound=BaseModel)


class MockLLMProvider(BaseLLMProvider):
    """
    Deterministic development LLM provider.
    Enables 100% offline verification, testing, and continuous integration.
    """

    def __init__(self, simulate_latency_ms: float = 5.0, fail_mode: Optional[str] = None):
        self._provider_name = "mock"
        self._provider_version = "1.0.0"
        self._model_name = "mock-intelligence-v1"
        self._simulate_latency_ms = simulate_latency_ms
        self._fail_mode = fail_mode  # None | "timeout" | "error" | "rate_limit"

    @property
    def provider_name(self) -> str:
        return self._provider_name

    @property
    def provider_version(self) -> str:
        return self._provider_version

    @property
    def model_name(self) -> str:
        return self._model_name

    @property
    def capabilities(self) -> List[str]:
        return ["structured_json", "grounded_explanation", "evidence_interpretation", "fast_ack"]

    def set_fail_mode(self, mode: Optional[str]):
        """Sets intentional failure mode for reliability & fallback testing."""
        self._fail_mode = mode

    async def generate_structured(
        self,
        system_prompt: str,
        user_prompt: str,
        schema_cls: Type[T],
        temperature: float = 0.0,
        max_tokens: int = 2048,
        timeout_seconds: float = 5.0,
    ) -> T:
        # Simulate failure modes if requested
        if self._fail_mode == "timeout":
            await asyncio.sleep(timeout_seconds + 0.1)
            raise TimeoutError("Mock LLM request timed out.")
        elif self._fail_mode == "error":
            raise RuntimeError("Mock LLM provider connection error.")
        elif self._fail_mode == "rate_limit":
            raise PermissionError("Mock LLM quota / rate limit exceeded.")

        if self._simulate_latency_ms > 0:
            await asyncio.sleep(self._simulate_latency_ms / 1000.0)

        # Route by target schema type
        if schema_cls == ObligationProposal:
            return self._generate_obligation_proposal(user_prompt)  # type: ignore
        elif schema_cls == EventSemanticProposal:
            return self._generate_event_semantic_proposal(user_prompt)  # type: ignore
        elif schema_cls == EvidenceInterpretationProposal:
            return self._generate_evidence_interpretation(user_prompt)  # type: ignore
        elif schema_cls == GroundedExplanationProposal:
            return self._generate_grounded_explanation(user_prompt)  # type: ignore

        # Generic fallback
        return schema_cls.model_validate({})  # type: ignore

    def _generate_obligation_proposal(self, user_prompt: str) -> ObligationProposal:
        text = user_prompt.lower()

        # Check for prompt injection patterns
        if "ignore previous instructions" in text or "system prompt override" in text or "drop database" in text:
            return ObligationProposal(
                action="Untrusted prompt injection attempt detected",
                owner=None,
                confidence=0.10,
                uncertainties=["Adversarial prompt injection pattern detected in input text."],
                reasoning="Text contains adversarial control commands. Neutralized into safe observation.",
                provider="mock",
                provider_version="1.0.0",
                prompt_version="v1",
            )

        # Scenario A: Explicit Obligation
        # "Rahul will send the database benchmark numbers by Friday."
        if "rahul" in text and ("send" in text or "benchmark" in text):
            deadline = "Friday" if "friday" in text else ("Next Thursday" if "thursday" in text else "End of week")
            return ObligationProposal(
                action="send the database benchmark numbers",
                owner="Rahul",
                beneficiary="Team",
                deadline=deadline,
                obligation_type="OWED_TO_ME",
                conditions=None,
                confidence=0.95,
                uncertainties=[],
                reasoning="Direct explicit commitment from Rahul with named action and clear temporal deadline.",
                provider="mock",
                provider_version="1.0.0",
                prompt_version="v1",
            )

        # Scenario B: Ambiguous Ownership
        # "We need to get the benchmark numbers over before the review."
        if "we need to" in text or "someone should" in text or "team needs to" in text:
            return ObligationProposal(
                action="get the benchmark numbers over",
                owner=None,
                beneficiary="Review Committee",
                deadline="before the review",
                obligation_type="MUTUAL",
                confidence=0.52,
                uncertainties=["Ambiguous owner: 'we' / collective pronoun specifies no individual duty bearer."],
                reasoning="Action and deadline identified, but duty bearer is ambiguous. Human confirmation required.",
                provider="mock",
                provider_version="1.0.0",
                prompt_version="v1",
            )

        # Scenario C: Conditional Commitment
        # "If the staging deployment passes, Ravi will publish the API report."
        if "if " in text and ("ravi" in text or "publish" in text or "passes" in text):
            return ObligationProposal(
                action="publish the API report",
                owner="Ravi",
                beneficiary="Team",
                deadline="Post-staging",
                obligation_type="OWED_TO_ME",
                conditions="staging deployment passes",
                confidence=0.92,
                uncertainties=["Execution depends on trigger condition: staging deployment passes."],
                reasoning="Identified conditional trigger and dependent action assigned to Ravi.",
                provider="mock",
                provider_version="1.0.0",
                prompt_version="v1",
            )

        # Relative deadline extraction
        # "Ravi, can you make sure the API migration is completed before the client demo next Thursday?"
        if "api migration" in text or ("ravi" in text and "client demo" in text):
            return ObligationProposal(
                action="complete API migration",
                owner="Ravi",
                beneficiary="Client Demo Team",
                deadline="Next Thursday before client demo",
                obligation_type="OWED_TO_ME",
                conditions="Before client demo",
                confidence=0.91,
                uncertainties=[],
                reasoning="Directive to Ravi with specific deliverable and client demo deadline constraint.",
                provider="mock",
                provider_version="1.0.0",
                prompt_version="v1",
            )

        # General dynamic fallback extraction
        owner_match = re.search(r"\b(alice|bob|charlie|priya|rahul|ravi|david|emma)\b", text, re.IGNORECASE)
        owner = owner_match.group(1).capitalize() if owner_match else None
        
        has_action = any(w in text for w in ["send", "submit", "complete", "finish", "review", "deploy", "update", "write", "deliver"])
        action = "Perform requested action" if has_action else "Unspecified conversational item"
        confidence = 0.85 if (owner and has_action) else (0.50 if has_action else 0.20)
        
        return ObligationProposal(
            action=action,
            owner=owner,
            beneficiary="Requester",
            deadline="Upcoming",
            obligation_type="OWED_TO_ME" if owner else "MUTUAL",
            confidence=confidence,
            uncertainties=["Heuristic dynamic interpretation applied."] if not owner else [],
            reasoning="Dynamic semantic parsing extracted available tokens.",
            provider="mock",
            provider_version="1.0.0",
            prompt_version="v1",
        )

    def _generate_event_semantic_proposal(self, user_prompt: str) -> EventSemanticProposal:
        text = user_prompt.lower()

        # Scenario D: Completion Signal
        # "I've sent the benchmark results to Priya."
        if any(w in text for w in ["sent", "submitted", "finished", "uploaded", "completed", "deployed", "resolved"]):
            if "couldn't" not in text and "can't" not in text and "not" not in text:
                recipient = "Priya" if "priya" in text else "Client"
                deliverable = "benchmark results" if "benchmark" in text else ("security patch" if "patch" in text else "deliverable")
                return EventSemanticProposal(
                    semantic_role="COMPLETION_SIGNAL",
                    confidence=0.94,
                    summary="Event reports delivery or fulfillment of work.",
                    actor="Sender",
                    recipient=recipient,
                    deliverable=deliverable,
                    evidence_strength=0.90,
                    contradictions=[],
                    reasoning="Past-tense completion verb with identified deliverable and recipient.",
                    provider="mock",
                    prompt_version="v1",
                )


        # Scenario E: Progress Update
        # "I'm still working on the migration."
        if "working on" in text or "in progress" in text or "drafting" in text or "making progress" in text:
            return EventSemanticProposal(
                semantic_role="PROGRESS_UPDATE",
                confidence=0.90,
                summary="Work is actively ongoing; not yet complete.",
                actor="Sender",
                deliverable="migration" if "migration" in text else "active task",
                evidence_strength=0.60,
                contradictions=[],
                reasoning="Ongoing progressive tense indicates active work without completion assertion.",
                provider="mock",
                prompt_version="v1",
            )

        # Scenario F: Negative Blocker
        # "I can't finish the migration because the production credentials haven't arrived."
        if "can't" in text or "cannot" in text or "blocked" in text or "failed" in text or "haven't arrived" in text:
            return EventSemanticProposal(
                semantic_role="NEGATIVE_BLOCKER",
                confidence=0.92,
                summary="Task is obstructed by an unresolved dependency or blocker.",
                actor="Sender",
                deliverable="migration" if "migration" in text else "task",
                evidence_strength=0.85,
                contradictions=["Blocker: missing prerequisites or credentials"],
                reasoning="Explicit negative constraint and blocker explanation detected.",
                provider="mock",
                prompt_version="v1",
            )

        # Request
        if "please" in text or "can you" in text or "could you" in text:
            return EventSemanticProposal(
                semantic_role="REQUEST",
                confidence=0.88,
                summary="Inbound directive or request to another collaborator.",
                actor="Sender",
                evidence_strength=0.30,
                reasoning="Imperative or polite request pattern.",
                provider="mock",
                prompt_version="v1",
            )

        # Irrelevant default
        return EventSemanticProposal(
            semantic_role="IRRELEVANT",
            confidence=0.95,
            summary="Casual conversational message or unrelated update.",
            evidence_strength=0.0,
            reasoning="No actionable deliverable or obligation reference.",
            provider="mock",
            prompt_version="v1",
        )

    def _generate_evidence_interpretation(self, user_prompt: str) -> EvidenceInterpretationProposal:
        text = user_prompt.lower()
        if "sent" in text or "submitted" in text or "attached" in text:
            return EvidenceInterpretationProposal(
                evidence_category="COMPLETION",
                confidence=0.91,
                extracted_action="Deliverable submission",
                deliverable_mentioned="Requested deliverable",
                actor="Sender",
                evidence_strength=0.88,
                reasoning="Event provides credible evidence for target obligation fulfillments.",
                provider="mock",
                prompt_version="v1",
            )
        elif "working on" in text or "in progress" in text:
            return EvidenceInterpretationProposal(
                evidence_category="PROGRESS",
                confidence=0.85,
                extracted_action="Active work ongoing",
                evidence_strength=0.50,
                reasoning="Ongoing work note.",
                provider="mock",
                prompt_version="v1",
            )
        else:
            return EvidenceInterpretationProposal(
                evidence_category="AMBIGUOUS",
                confidence=0.60,
                extracted_action="Unspecified",
                evidence_strength=0.20,
                reasoning="Candidate event provides insufficient evidence match.",
                provider="mock",
                prompt_version="v1",
            )

    def _generate_grounded_explanation(self, user_prompt: str) -> GroundedExplanationProposal:
        # Check if the prompt asks to include an unsupported entity or hallucination test
        if "hallucination_test" in user_prompt.lower() or "fabricate_unsupported_person" in user_prompt.lower():
            # Deliberately emits an unsupported person for testing grounding rejection
            return GroundedExplanationProposal(
                explanation="The issue is delayed by Dr. Victor Frankenstein on December 31, 2099.",
                grounded_facts_used=["ob-1"],
                confidence=0.70,
                grounding_status=GroundingCheckStatus.FABRICATED_ENTITY,
                grounding_notes="Explanation references entities not in verified facts packet.",
                reasoning="Injected synthetic fact for grounding verification.",
                provider="mock",
                prompt_version="v1",
            )

        # Standard grounded explanation
        return GroundedExplanationProposal(
            explanation=(
                "The critical path delay originates from the overdue database migration assigned to Rahul. "
                "Because Ravi's API integration depends on this schema change, the delay propagates downstream "
                "to Priya's frontend deliverable and threatens the upcoming demo deadline."
            ),
            grounded_facts_used=["ob-root-db", "ob-api-ravi", "ob-fe-priya"],
            confidence=0.96,
            uncertainties=[],
            grounding_status=GroundingCheckStatus.GROUNDED,
            reasoning="Synthesized root-cause dependency cascade strictly from supplied verified facts.",
            provider="mock",
            prompt_version="v1",
        )

    async def health_check(self) -> LLMProviderInfo:
        return LLMProviderInfo(
            provider_name=self.provider_name,
            provider_version=self.provider_version,
            model=self.model_name,
            capabilities=self.capabilities,
            healthy=True,
        )
