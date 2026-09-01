import re
from typing import Tuple
from app.core.status_machine import EventSemanticRole


class EventClassifier:
    """
    Classifies external messages/events into semantic roles:
    - COMPLETION_SIGNAL: Proves or asserts fulfillment of an obligation.
    - COMMITMENT: Promise of future action (NOT completion).
    - REQUEST: Directive to another party (NOT completion).
    - PROGRESS_UPDATE: Work ongoing.
    - NON_COMPLETION_SIGNAL: Negative signal, blocker, or failure.
    - IRRELEVANT: Casual chatter or unrelated pleasantry.
    """

    NON_COMPLETION_PATTERNS = [
        r"\b(?:couldn'?t|could\s+not|can'?t|cannot|failed\s+to|unable\s+to)\s+(?:send|submit|finish|complete|review|deliver|export|provide|share|deploy|generate)\b",
        r"\b(?:haven'?t|have\s+not)\s+(?:sent|submitted|finished|completed|received|reviewed|exported|provided)\b",
        r"\b(?:still\s+haven'?t|still\s+waiting\s+for|not\s+yet\s+sent|delayed|rejected|blocked\s+by|blocked\s+on|is\s+blocked|export\s+failed|failed\s+because)\b",
        r"\b(?:client\s+rejected|proposal\s+rejected|did\s+not\s+send|meeting\s+cancelled|meeting_cancelled|cancelled\s+meeting|found\s+discrepancies|discrepancies\s+in|not\s+ready)\b",
        r"\b(?:status:\s*blocked|status\s+transition:\s*.*\bblocked|\bblocked\b)\b",
    ]

    COMMITMENT_PATTERNS = [
        r"\b(?:i\s+will|i'll|will|i'm\s+going\s+to|going\s+to|plan\s+to|promise\s+to)\s+(?:send|submit|finish|complete|review|share|upload|provide|write|export)\b",
        r"\b(?:tomorrow|next\s+week|later\s+today|by\s+friday|by\s+monday|soon)\b",
        r"\b(?:calendar\s+meeting|meeting_scheduled|meeting_rescheduled|rescheduled\s+project|moved\s+to)\b",
    ]

    REQUEST_PATTERNS = [
        r"\b(?:can\s+you|could\s+you|would\s+you|please|kindly|did\s+you)\s+(?:send|submit|review|share|finish|provide|export)\b",
        r"\b(?:reminder\s+to|where\s+is\s+the|status\s+of|any\s+update\s+on)\b",
    ]

    PROGRESS_PATTERNS = [
        r"\b(?:working\s+on|currently\s+drafting|in\s+progress|drafting|almost\s+done|making\s+progress|accepted\s+the\s+project|attendee_response|meeting\s+concluded|meeting_completed)\b",
        r"\b(?:status:\s*in\s*progress|status:\s*to\s*do|status\s+transition:\s*.*\bin\s*progress)\b",
    ]

    COMPLETION_PATTERNS = [
        r"\b(?:sent|submitted|finished|completed|reviewed|uploaded|delivered|signed|deployed|published|provided|exported)\b",
        r"\b(?:attached|attaching|here\s+is|here\s+are|all\s+done|task\s+complete|done\s+with|discrepancies\s+resolved|all\s+resolved)\b",
        r"\b(?:csv\s+sent|docs\s+sent|report\s+sent|numbers\s+sent|email\s+sent)\b",
        r"\b(?:status:\s*done|status:\s*resolved|status:\s*closed|status\s+transition:\s*.*\b(?:done|resolved|closed))\b",
    ]


    IRRELEVANT_PATTERNS = [
        r"^(?:hi|hello|hey|good\s+morning|good\s+afternoon|good\s+evening|thanks|thank\s+you|cool|ok|okay|sounds\s+good|got\s+it)[.!]?$",
        r"\b(?:personal\s+lunch|lunch\s+with\s+friend)\b",
    ]

    @classmethod
    def classify(cls, content: str, has_attachments: bool = False) -> Tuple[EventSemanticRole, float, str]:
        text = content.strip().lower()

        # 1. Check Irrelevant
        for pattern in cls.IRRELEVANT_PATTERNS:
            if re.search(pattern, text, re.IGNORECASE):
                return EventSemanticRole.IRRELEVANT, 0.95, "Conversational pleasantry with no actionable duty."

        # 2. Check Negative / Non-Completion
        for pattern in cls.NON_COMPLETION_PATTERNS:
            if re.search(pattern, text, re.IGNORECASE):
                return EventSemanticRole.NON_COMPLETION_SIGNAL, 0.90, "Expressed inability, blocker, rejection, or delay."

        # 3. Check Progress (active ongoing work takes precedence over future ETA)
        for pattern in cls.PROGRESS_PATTERNS:
            if re.search(pattern, text, re.IGNORECASE):
                return EventSemanticRole.PROGRESS_UPDATE, 0.88, "Progress update indicating ongoing work."

        # 4. Check Future Commitment
        for pattern in cls.COMMITMENT_PATTERNS:
            if re.search(pattern, text, re.IGNORECASE):
                # Ensure it is not a past statement like "I will have sent"
                return EventSemanticRole.COMMITMENT, 0.92, "Statement of future commitment or intent; not completion evidence."

        # 5. Check Request
        for pattern in cls.REQUEST_PATTERNS:
            if re.search(pattern, text, re.IGNORECASE):
                return EventSemanticRole.REQUEST, 0.90, "Directive or inquiry to another party; not completion evidence."

        # 6. Check Completion Signal
        for pattern in cls.COMPLETION_PATTERNS:
            if re.search(pattern, text, re.IGNORECASE):
                return EventSemanticRole.COMPLETION_SIGNAL, 0.92, "Detected past-tense fulfillment or delivery language."

        # 7. Attachment fallback
        if has_attachments:
            return EventSemanticRole.COMPLETION_SIGNAL, 0.80, "Event contains file attachments indicating deliverable handoff."

        return EventSemanticRole.IRRELEVANT, 0.50, "Unclassified event text."
