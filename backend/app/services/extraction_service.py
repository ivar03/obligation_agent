import re
from abc import ABC, abstractmethod
from typing import Optional, Dict, Any, List
from app.core.config import settings
from app.core.logging import logger
from app.core.status_machine import ObligationType
from app.core.confidence import (
    ConfidenceEvaluator,
    AmbiguityDetail,
    CONFIDENCE_THRESHOLD_HIGH,
)
from app.schemas.obligation import (
    ExtractionRequest,
    ExtractionResponse,
    ObligationCandidate,
    FieldConfidence,
    MessageContext,
    ResolutionResult,
    DeadlineType,
)
from app.services.context_analyzer import ContextAnalyzer
from app.services.ownership_agent import BaseOwnershipAgent, DevMockOwnershipAgent
from app.services.deadline_agent import BaseDeadlineAgent, DevMockDeadlineAgent


class TupleDetection:
    def __init__(self, detected: bool, action: Optional[str] = None, reason: Optional[str] = None):
        self.detected = detected
        self.action = action
        self.reason = reason


class BaseExtractionProvider(ABC):
    """Abstract interface for obligation extraction providers (LLMs or Heuristics)."""

    @abstractmethod
    async def extract_initial(self, text: str, context: MessageContext) -> TupleDetection:
        pass


class DevMockExtractionProvider(BaseExtractionProvider):
    """
    Intelligent heuristic parser for commitment detection and action extraction.
    """

    async def extract_initial(self, text: str, context: MessageContext) -> TupleDetection:
        cleaned = text.strip()
        if not cleaned:
            return TupleDetection(detected=False, reason="Empty text provided.")

        lower = cleaned.lower()

        # Action and commitment indicators
        commitment_keywords = [
            "send", "review", "deliver", "submit", "prepare", "finish", "complete",
            "pay", "owe", "owes", "draft", "write", "fix", "deploy", "update", "call",
            "meet", "schedule", "provide", "share", "transfer", "buy", "push", "test",
            "email", "ping", "reach out", "will do", "promise", "guarantee", "get this done"
        ]
        has_commitment_action = any(re.search(rf"\b{kw}\b", lower) for kw in commitment_keywords)

        # Conversational phrases without actionable commitment
        conversational_patterns = [
            r"^hello\b", r"^hi\b", r"^hey\b", r"^good (morning|afternoon|evening|day)\b",
            r"^hope you\b", r"^how are you\b", r"^the weather\b", r"^just saying thanks\b",
            r"^thank you\b", r"^thanks\b", r"^ok noted\b", r"^cool\b", r"^sounds good\b",
            r"^great job\b", r"^nice work\b"
        ]
        is_conversational = any(re.search(pat, lower) for pat in conversational_patterns)

        if is_conversational and not has_commitment_action:
            return TupleDetection(
                detected=False,
                reason="The message is conversational or courteous and contains no identifiable commitment or obligation."
            )

        if not has_commitment_action and not ("by " in lower or "before " in lower or "tomorrow" in lower or "owes" in lower):
            return TupleDetection(
                detected=False,
                reason="No actionable commitment or obligation pattern was detected in the text."
            )

        # Clean action text
        action = cleaned
        # Strip "X owes Y:" prefix if present for clean action title
        owes_prefix = re.search(r"^[A-Za-z0-9_\s]+\s+owes\s+[A-Za-z0-9_\s]+[:\s-]+(.*)$", action, re.IGNORECASE)
        if owes_prefix and owes_prefix.group(1).strip():
            action = owes_prefix.group(1).strip()

        action = action.strip(' "“\'”')
        action = re.sub(r"^(i will|i'll|please|we should probably|could you|can you)\s+", "", action, flags=re.IGNORECASE)
        action = action.rstrip(".!")
        action = action[:1].upper() + action[1:] if action else "Perform commitment"

        return TupleDetection(detected=True, action=action)


class ExtractionService:
    """
    Orchestrator for the Phase 2 extraction and reasoning pipeline:
    Context Analyzer -> Initial Extraction -> Ownership Agent -> Deadline Agent -> Confidence Gating.
    """

    def __init__(
        self,
        provider: Optional[BaseExtractionProvider] = None,
        ownership_agent: Optional[BaseOwnershipAgent] = None,
        deadline_agent: Optional[BaseDeadlineAgent] = None,
        context_analyzer: Optional[ContextAnalyzer] = None,
    ):
        self.provider = provider or DevMockExtractionProvider()
        self.ownership_agent = ownership_agent or DevMockOwnershipAgent()
        self.deadline_agent = deadline_agent or DevMockDeadlineAgent()
        self.context_analyzer = context_analyzer or ContextAnalyzer()

    async def extract_candidate(self, request: ExtractionRequest) -> ExtractionResponse:
        logger.info(f"Initiating Phase 2 Extraction Pipeline for input (len={len(request.text)})")

        # Step 1: Analyze and construct context
        context = self.context_analyzer.analyze(request)

        # Step 2: Initial commitment detection
        detection = await self.provider.extract_initial(request.text, context)
        if not detection.detected:
            logger.info(f"No obligation detected. Reason: {detection.reason}")
            return ExtractionResponse(
                detected=False,
                reason=detection.reason,
                raw_text=request.text
            )

        # Step 3: Ownership reasoning
        ownership = await self.ownership_agent.resolve(request.text, context)

        # Step 4: Deadline & Temporal reasoning
        deadline = await self.deadline_agent.resolve(request.text, context)

        # Step 5: Ambiguity evaluation & confidence gating
        ambiguities: List[AmbiguityDetail] = []

        if ownership.ambiguous or ownership.confidence < CONFIDENCE_THRESHOLD_HIGH:
            ambiguities.append(
                AmbiguityDetail(
                    field="owner",
                    reason=ownership.reasoning,
                    confidence=ownership.confidence,
                    suggested_action="Confirm or select the responsible duty bearer"
                )
            )

        if deadline.ambiguous or deadline.confidence < CONFIDENCE_THRESHOLD_HIGH:
            ambiguities.append(
                AmbiguityDetail(
                    field="deadline",
                    reason=deadline.reasoning,
                    confidence=deadline.confidence,
                    suggested_action="Specify concrete deadline or confirm trigger"
                )
            )

        confidence_map = {
            "owner": ownership.confidence,
            "beneficiary": 0.95 if not ownership.ambiguous else 0.60,
            "action": 0.95 if not ownership.ambiguous else 0.75,
            "deadline": deadline.confidence,
            "conditions": 0.94 if deadline.condition_trigger else 0.90,
            "obligation_type": 0.95 if not ownership.ambiguous else 0.60,
        }
        overall_conf = round(sum(confidence_map.values()) / len(confidence_map), 2)
        confidence_map["overall"] = overall_conf

        review_required = ConfidenceEvaluator.is_review_required(confidence_map, ambiguities)

        resolution_result = ResolutionResult(
            ownership=ownership,
            deadline=deadline,
            review_required=review_required,
            ambiguities=ambiguities,
            confidence_summary=confidence_map
        )

        # Step 6: Assemble final candidate
        action = detection.action or request.text.strip()
        next_action = f"Draft and complete: {action}" if ownership.obligation_type == ObligationType.OWED_BY_ME else f"Check in with {ownership.owner} regarding: {action}"

        candidate = ObligationCandidate(
            owner=ownership.owner,
            beneficiary=ownership.beneficiary,
            action=action,
            deadline=deadline.resolved_deadline,
            conditions=deadline.condition_trigger,
            obligation_type=ownership.obligation_type,
            next_action=next_action,
            source_ref="Manual Text Input",
            confidence=FieldConfidence(
                overall=overall_conf,
                owner=round(ownership.confidence, 2),
                beneficiary=round(confidence_map["beneficiary"], 2),
                action=round(confidence_map["action"], 2),
                deadline=round(deadline.confidence, 2),
                conditions=round(confidence_map["conditions"], 2),
                obligation_type=round(confidence_map["obligation_type"], 2),
            ),
            deadline_type=deadline.deadline_type,
            resolution=resolution_result,
        )

        logger.info(
            f"Extraction complete: owner='{candidate.owner}', "
            f"deadline_type={candidate.deadline_type}, "
            f"review_required={review_required}, "
            f"ambiguities_count={len(ambiguities)}"
        )

        return ExtractionResponse(
            detected=True,
            obligation=candidate,
            raw_text=request.text
        )
