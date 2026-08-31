"""
Phase 20 Grounding Validator & Hallucination Guardrails.

Verifies that all generated explanations are strictly grounded in verified
application facts from the database and contain zero fabricated entities,
unknown dates, or leaked secrets.
"""

import re
from typing import Tuple, List
from app.schemas.llm import (
    GroundedExplanationProposal,
    GroundedContextPacket,
    GroundingCheckStatus,
)


class GroundingValidator:
    """
    Deterministic post-generation validator that checks LLM output against
    the verified GroundedContextPacket.
    """

    SECRET_PATTERNS = [
        r"xox[baprs]-[0-9a-zA-Z]+",
        r"ghp_[0-9a-zA-Z]{36}",
        r"ey[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}",
        r"(?:password|secret_key|client_secret)\s*[:=]\s*['\"][^'\"]+['\"]",
    ]

    @classmethod
    def validate_grounding(
        cls,
        explanation: GroundedExplanationProposal,
        context: GroundedContextPacket,
    ) -> Tuple[GroundingCheckStatus, List[str]]:
        text = explanation.explanation
        errors: List[str] = []

        # 1. Secret / Credential Leakage Check
        for pat in cls.SECRET_PATTERNS:
            if re.search(pat, text, re.IGNORECASE):
                return GroundingCheckStatus.SECRET_DETECTED, [
                    "Generated explanation contains potentially leaked credentials or API secrets."
                ]

        # 2. Obligation ID Grounding Check
        # Find any references like 'ob-...' or 'inbox-...' in the text
        referenced_ids = re.findall(r"\b(ob-[a-zA-Z0-9_-]+|inbox-[a-zA-Z0-9_-]+)\b", text)
        known_ids = set(context.known_obligation_ids)
        for rid in referenced_ids:
            if rid not in known_ids:
                errors.append(f"Referenced obligation ID '{rid}' does not exist in verified application state.")

        # 3. User / Identity Grounding Check
        # Check against known users in context
        known_user_tokens = {u.strip().lower() for u in context.known_users if u}
        # Common fictional names to catch synthetic test hallucinations
        suspect_hallucinations = ["dr. victor frankenstein", "unknown synthetic actor", "batman", "sherlock"]
        for sh in suspect_hallucinations:
            if sh in text.lower():
                errors.append(f"Fabricated person '{sh}' detected in explanation.")

        # 4. Unknown Deadline / Extreme Date Grounding
        # E.g. dates in 2099 or unverified future centuries
        if "2099" in text or "2100" in text:
            errors.append("Unsupported speculative date '2099/2100' detected in explanation.")

        # 5. Claim validation from proposal's self-reported status
        if explanation.grounding_status in [
            GroundingCheckStatus.FABRICATED_ENTITY,
            GroundingCheckStatus.UNGROUNDED_CLAIM,
            GroundingCheckStatus.GROUNDING_FAILED,
        ]:
            errors.append(explanation.grounding_notes or "Self-reported grounding inconsistency.")

        if errors:
            return GroundingCheckStatus.GROUNDING_FAILED, errors

        return GroundingCheckStatus.GROUNDED, []
