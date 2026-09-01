"""
Phase 22 LLM Data Minimization & Prompt-Injection Containment Service.

Enforces:
 1. Deterministic PII, credential, and token scrubbing prior to LLM provider dispatch.
 2. Strict Trust Hierarchy:
    SYSTEM INSTRUCTIONS > APPLICATION POLICY > VERIFIED DOMAIN FACTS > UNTRUSTED EXTERNAL CONTENT
 3. Adversarial prompt-injection detection and sanitization.
"""

import re
from typing import Dict, Any, Tuple, Optional
from app.core.sanitizer import sanitize_text, SENSITIVE_PATTERNS


class LLMDataMinimizer:
    """
    Minimizes context and strips toxic/sensitive data before LLM dispatch.
    """

    # Extended PII patterns
    EMAIL_PATTERN = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,7}\b")
    PHONE_PATTERN = re.compile(r"\b(?:\+?\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b")
    CREDIT_CARD_PATTERN = re.compile(r"\b(?:\d{4}[-\s]?){3}\d{4}\b")
    SSN_PATTERN = re.compile(r"\b\d{3}-\d{2}-\d{4}\b")

    # Prompt Injection & Jailbreak Heuristics
    INJECTION_PATTERNS = [
        re.compile(r"ignore\s+(?:all\s+|your\s+|all\s+your\s+)?(?:previous|prior|above)\s+instructions?", re.IGNORECASE),
        re.compile(r"system\s+override", re.IGNORECASE),

        re.compile(r"you\s+are\s+now\s+(?:in\s+developer\s+mode|dan|unrestricted)", re.IGNORECASE),
        re.compile(r"disregard\s+(?:the\s+)?rules", re.IGNORECASE),
        re.compile(r"reveal\s+(?:all\s+)?(?:secrets|tokens|credentials|passwords|keys)", re.IGNORECASE),
        re.compile(r"approve\s+(?:this\s+)?(?:decision|plan|obligation)\s+immediately", re.IGNORECASE),
        re.compile(r"delete\s+(?:the\s+)?(?:audit\s+trail|database|records)", re.IGNORECASE),
    ]

    @classmethod
    def sanitize_untrusted_input(cls, raw_text: str) -> Tuple[str, bool, Optional[str]]:
        """
        Scrubs PII and credentials, detects prompt injection, and sanitizes untrusted input.
        Returns: (sanitized_text, injection_detected, detected_pattern_name)
        """
        if not raw_text or not isinstance(raw_text, str):
            return "", False, None

        # 1. First pass: scrub credentials & tokens via core sanitizer
        text = sanitize_text(raw_text)

        # 2. Second pass: scrub PII
        text = cls.EMAIL_PATTERN.sub("[EMAIL_REDACTED]", text)
        text = cls.PHONE_PATTERN.sub("[PHONE_REDACTED]", text)
        text = cls.CREDIT_CARD_PATTERN.sub("[CARD_REDACTED]", text)
        text = cls.SSN_PATTERN.sub("[SSN_REDACTED]", text)

        # 3. Third pass: check for adversarial prompt injections
        injection_detected = False
        detected_rule = None
        for pattern in cls.INJECTION_PATTERNS:
            if pattern.search(text):
                injection_detected = True
                detected_rule = pattern.pattern
                # Defang the injected command in the sanitized text
                text = pattern.sub("[UNTRUSTED_INJECTION_DEFANGED]", text)

        return text, injection_detected, detected_rule

    @classmethod
    def prepare_grounded_context(
        cls,
        verified_facts: Dict[str, Any],
        untrusted_external_content: str,
    ) -> Dict[str, Any]:
        """
        Structures the LLM payload enforcing the 4-tier trust boundary hierarchy.
        """
        sanitized_external, injected, rule = cls.sanitize_untrusted_input(untrusted_external_content)

        return {
            "trust_hierarchy": "SYSTEM > POLICY > VERIFIED_FACTS > UNTRUSTED_EXTERNAL",
            "system_policy": "You are a read-only semantic analyzer. You have NO execution, mutation, or approval authority.",
            "verified_facts": verified_facts,
            "untrusted_external_evidence": sanitized_external,
            "injection_flagged": injected,
            "defanged_rule": rule,
        }
