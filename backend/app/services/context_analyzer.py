import re
from datetime import datetime, timezone
from typing import Optional, List
from app.schemas.obligation import MessageContext, ExtractionRequest
from app.core.logging import logger


class ContextAnalyzer:
    """
    Analyzes raw text and optional conversation metadata to construct
    a normalized, timezone-aware MessageContext for downstream reasoning agents.
    """

    def analyze(self, request: ExtractionRequest) -> MessageContext:
        raw_text = request.text.strip()
        provided_ctx = request.context or MessageContext()

        # 1. Resolve Timezone-Aware Reference Timestamp
        ref_time = request.reference_datetime or provided_ctx.reference_time
        if ref_time is None:
            ref_time = datetime.now(timezone.utc)
        elif ref_time.tzinfo is None:
            # Ensure naive datetimes are interpreted as UTC
            ref_time = ref_time.replace(tzinfo=timezone.utc)

        # 2. Extract potential participant names from text if not supplied
        participants = list(provided_ctx.participants or [])
        sender = provided_ctx.sender
        recipients = list(provided_ctx.recipients or [])

        # Detect addressed names like "Rahul, please..." or "Hey Sarah,"
        addressed_match = re.search(r"^(?:hey|hi|hello)?\s*([A-Z][a-z]+)[,:]\s*(?:please|can you|could you|would you)?", raw_text, re.IGNORECASE)
        if addressed_match:
            addressed_name = addressed_match.group(1).capitalize()
            if addressed_name not in recipients:
                recipients.append(addressed_name)
            if addressed_name not in participants:
                participants.append(addressed_name)

        # Detect third-party mentions
        mentioned_names = re.findall(r"\b([A-Z][a-z]+)\b", raw_text)
        for name in mentioned_names:
            if name.lower() not in ["i", "we", "you", "the", "send", "friday", "monday", "tuesday", "wednesday", "thursday", "saturday", "sunday", "today", "tomorrow"]:
                if name not in participants:
                    participants.append(name)

        # If sender provided and not in participants
        if sender and sender not in participants:
            participants.append(sender)

        normalized_context = MessageContext(
            message=raw_text,
            sender=sender,
            recipients=recipients,
            participants=participants,
            previous_messages=provided_ctx.previous_messages or [],
            reference_time=ref_time,
            current_user=provided_ctx.current_user or "You"
        )

        logger.debug(
            f"Context analyzed: sender={normalized_context.sender}, "
            f"recipients={normalized_context.recipients}, "
            f"participants={normalized_context.participants}, "
            f"ref_time={normalized_context.reference_time.isoformat()}"
        )

        return normalized_context
