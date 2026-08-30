import re
from abc import ABC, abstractmethod
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any
from app.core.config import settings
from app.core.logging import logger
from app.core.status_machine import ObligationType
from app.schemas.obligation import (
    ExtractionRequest,
    ExtractionResponse,
    ObligationCandidate,
    FieldConfidence,
)


class BaseExtractionProvider(ABC):
    """Abstract interface for obligation extraction providers (LLMs or Heuristics)."""

    @abstractmethod
    async def extract(self, text: str) -> ExtractionResponse:
        pass


class DevMockExtractionProvider(BaseExtractionProvider):
    """
    Intelligent heuristic and rule-based extraction provider for local/dev use.
    Provides robust parsing for dates, entities, conditions, and ownership ambiguity.
    """

    async def extract(self, text: str) -> ExtractionResponse:
        cleaned = text.strip()
        if not cleaned:
            return ExtractionResponse(
                detected=False,
                reason="Empty text provided.",
                raw_text=text
            )

        lower = cleaned.lower()

        # Action and commitment indicators
        commitment_keywords = [
            "send", "review", "deliver", "submit", "prepare", "finish", "complete",
            "pay", "owe", "owes", "draft", "write", "fix", "deploy", "update", "call",
            "meet", "schedule", "provide", "share", "transfer", "buy", "push", "test",
            "email", "ping", "reach out", "will do", "promise", "guarantee"
        ]
        has_commitment_action = any(re.search(rf"\b{kw}\b", lower) for kw in commitment_keywords)

        # Conversational / pleasantry phrases without actionable commitment
        conversational_patterns = [
            r"^hello\b", r"^hi\b", r"^hey\b", r"^good (morning|afternoon|evening|day)\b",
            r"^hope you\b", r"^how are you\b", r"^the weather\b", r"^just saying thanks\b",
            r"^thank you\b", r"^thanks\b", r"^ok noted\b", r"^cool\b", r"^sounds good\b",
            r"^great job\b", r"^nice work\b"
        ]
        is_conversational = any(re.search(pat, lower) for pat in conversational_patterns)

        if is_conversational and not has_commitment_action:
            return ExtractionResponse(
                detected=False,
                reason="The message is conversational or courteous and contains no identifiable commitment or obligation.",
                raw_text=cleaned
            )

        if not has_commitment_action and not ("by " in lower or "before " in lower or "tomorrow" in lower):
            return ExtractionResponse(
                detected=False,
                reason="No actionable commitment or obligation pattern was detected in the text.",
                raw_text=cleaned
            )

        # Ambiguity detection check
        is_ambiguous = bool(
            re.search(r"\b(we should probably|someone should|maybe we|somebody needs to|it would be nice if we)\b", lower)
        )

        # 1. Parse Owner & Beneficiary & Type
        owner = "You"
        beneficiary = "Team"
        obligation_type = ObligationType.OWED_BY_ME
        owner_conf = 0.95
        beneficiary_conf = 0.90
        overall_conf = 0.92

        if is_ambiguous:
            owner = "Unassigned / Team (Ambiguous)"
            beneficiary = "Client / Project"
            owner_conf = 0.35
            beneficiary_conf = 0.50
            overall_conf = 0.45

        # Check explicit "X owes Y:" pattern
        owes_match = re.search(r"^([A-Za-z0-9_\s]+)\s+owes\s+([A-Za-z0-9_\s]+)[:\s-]+(.*)$", cleaned, re.IGNORECASE)
        if owes_match:
            raw_owner = owes_match.group(1).strip()
            raw_beneficiary = owes_match.group(2).strip()
            rest_action = owes_match.group(3).strip()

            owner = raw_owner
            beneficiary = raw_beneficiary
            if raw_owner.lower() in ["ravi", "i", "me", "you", "user"]:
                owner = "You"
                obligation_type = ObligationType.OWED_BY_ME
            elif raw_beneficiary.lower() in ["ravi", "i", "me", "you", "user"]:
                beneficiary = "You"
                obligation_type = ObligationType.OWED_TO_ME
            else:
                obligation_type = ObligationType.OWED_TO_ME

            cleaned = rest_action or cleaned
            lower = cleaned.lower()
        else:
            # Check pattern: "Rahul owes Ravi..." or "Professor owes..."
            third_party_match = re.search(r"\b([A-Z][a-z]+)\s+will\s+([a-z].*)", cleaned)
            if third_party_match and not lower.startswith("i will"):
                raw_owner = third_party_match.group(1).strip()
                if raw_owner.lower() not in ["i", "we", "you"]:
                    owner = raw_owner
                    beneficiary = "You"
                    obligation_type = ObligationType.OWED_TO_ME

            if re.search(r"\b(can you|please|could you)\b", lower):
                owner = "You"
                beneficiary = "Requester"
                obligation_type = ObligationType.OWED_BY_ME

            if re.search(r"\b(i will|i'll|i promise to|i shall|i need to)\b", lower):
                owner = "You"
                obligation_type = ObligationType.OWED_BY_ME
                to_match = re.search(r"\bto\s+([A-Z][a-z]+|the\s+[a-z]+)\b", cleaned)
                if to_match:
                    beneficiary = to_match.group(1).strip()

        # 2. Parse Conditions
        conditions = None
        cond_conf = 1.0
        cond_match = re.search(
            r"\b(after|once|if|provided that|conditional on|before\s+[a-zA-Z]+\s+can)\s+([^.,;\n]+)",
            cleaned,
            re.IGNORECASE
        )
        if cond_match:
            conditions = cond_match.group(0).strip().capitalize()
            cond_conf = 0.88

        # 3. Parse Deadline
        deadline = None
        deadline_conf = 0.85
        now = datetime.now(timezone.utc)

        if "tomorrow" in lower:
            deadline = (now + timedelta(days=1)).replace(hour=17, minute=0, second=0, microsecond=0)
            deadline_conf = 0.95
        elif "today" in lower or "tonight" in lower or "eod" in lower:
            deadline = now.replace(hour=18, minute=0, second=0, microsecond=0)
            deadline_conf = 0.95
        elif "friday" in lower:
            days_ahead = (4 - now.weekday() + 7) % 7
            if days_ahead == 0:
                days_ahead = 7
            deadline = (now + timedelta(days=days_ahead)).replace(hour=17, minute=0, second=0, microsecond=0)
            deadline_conf = 0.90
        elif "monday" in lower:
            days_ahead = (0 - now.weekday() + 7) % 7
            if days_ahead == 0:
                days_ahead = 7
            deadline = (now + timedelta(days=days_ahead)).replace(hour=17, minute=0, second=0, microsecond=0)
            deadline_conf = 0.90
        elif "wednesday" in lower:
            days_ahead = (2 - now.weekday() + 7) % 7
            if days_ahead == 0:
                days_ahead = 7
            deadline = (now + timedelta(days=days_ahead)).replace(hour=17, minute=0, second=0, microsecond=0)
            deadline_conf = 0.90
        elif "next week" in lower:
            deadline = (now + timedelta(days=7)).replace(hour=17, minute=0, second=0, microsecond=0)
            deadline_conf = 0.80

        # 4. Action refinement
        action = cleaned
        # Strip outer quotes if any
        action = action.strip(' "“\'”')
        # Clean leading filler
        action = re.sub(r"^(i will|i'll|please|we should probably|could you|can you)\s+", "", action, flags=re.IGNORECASE)
        action = action.rstrip(".!")
        action = action[:1].upper() + action[1:] if action else "Perform obligation"

        # 5. Suggested Next Action
        next_action = f"Follow up on '{action}'"
        if obligation_type == ObligationType.OWED_BY_ME:
            next_action = f"Draft and complete: {action}"
        else:
            next_action = f"Check in with {owner} regarding: {action}"

        confidence = FieldConfidence(
            overall=round(overall_conf, 2),
            owner=round(owner_conf, 2),
            beneficiary=round(beneficiary_conf, 2),
            action=0.95 if not is_ambiguous else 0.70,
            deadline=round(deadline_conf, 2) if deadline else 0.50,
            conditions=round(cond_conf, 2) if conditions else 0.90,
            obligation_type=0.95 if not is_ambiguous else 0.60,
        )

        candidate = ObligationCandidate(
            owner=owner,
            beneficiary=beneficiary,
            action=action,
            deadline=deadline,
            conditions=conditions,
            obligation_type=obligation_type,
            next_action=next_action,
            source_ref="Manual Text Input",
            confidence=confidence,
        )

        return ExtractionResponse(
            detected=True,
            obligation=candidate,
            raw_text=text
        )


class ExtractionService:
    """Orchestrator for the extraction pipeline, delegating to the configured provider."""

    def __init__(self, provider: Optional[BaseExtractionProvider] = None):
        if provider is not None:
            self.provider = provider
        else:
            self.provider = self._resolve_provider()

    def _resolve_provider(self) -> BaseExtractionProvider:
        provider_type = settings.LLM_PROVIDER.upper()
        logger.info(f"Initializing extraction provider: {provider_type}")
        if provider_type == "DEV_MOCK":
            return DevMockExtractionProvider()
        # Additional providers (OpenAI, Gemini) can be registered here seamlessly
        logger.warning(f"Provider '{provider_type}' not directly configured. Falling back to DevMockExtractionProvider.")
        return DevMockExtractionProvider()

    async def extract_candidate(self, request: ExtractionRequest) -> ExtractionResponse:
        logger.info(f"Executing extraction pipeline on message (len={len(request.text)})")
        return await self.provider.extract(request.text)
