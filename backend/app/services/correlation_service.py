import re
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone

from app.core.logging import logger
from app.core.status_machine import (
    ObligationStatus,
    EventSemanticRole,
)
from app.core.confidence import (
    CONFIDENCE_THRESHOLD_HIGH,
    CONFIDENCE_THRESHOLD_MEDIUM,
)
from app.models.obligation import Obligation
from app.schemas.obligation import (
    ExternalEvent,
    CorrelationMatch,
    EventAnalysisResponse,
)
from app.services.event_classifier import EventClassifier


def normalize_name(name: Optional[str]) -> str:
    if not name:
        return ""
    n = name.strip().lower()
    if n in ["you", "me", "myself"]:
        return "you"
    return n


def tokenize_action(action: str) -> List[str]:
    # Extract substantive nouns and verbs (excluding common stop words)
    stop_words = {"the", "a", "an", "to", "for", "in", "on", "at", "by", "from", "and", "or", "is", "be", "with"}
    words = re.findall(r"\b[a-zA-Z]{3,}\b", action.lower())
    return [w for w in words if w not in stop_words]


class EvidenceCorrelationService:
    """
    Correlates normalized external events against active obligations.
    Produces explainable match confidence, signal breakdowns, and identifies completion candidates.
    """

    @classmethod
    def evaluate_match(
        cls,
        event: ExternalEvent,
        obligation: Obligation,
        semantic_role: EventSemanticRole,
        classifier_reason: str,
    ) -> CorrelationMatch:
        matched_signals: List[str] = []
        unmatched_signals: List[str] = []
        reasoning: List[str] = []

        base_score = 0.10

        # 1. Semantic Role Check
        if semantic_role == EventSemanticRole.COMPLETION_SIGNAL:
            base_score += 0.25
            matched_signals.append("Completion language detected")
            reasoning.append(f"Event contains past-tense completion phrasing ({classifier_reason})")
        elif semantic_role == EventSemanticRole.COMMITMENT:
            base_score += 0.05
            unmatched_signals.append("Event is future commitment (Not completion)")
            reasoning.append("Event describes future commitment; not proof of current completion.")
        elif semantic_role == EventSemanticRole.REQUEST:
            base_score += 0.05
            unmatched_signals.append("Event is request/directive (Not completion)")
            reasoning.append("Event is a request to another person; not proof of completion.")
        elif semantic_role == EventSemanticRole.NON_COMPLETION_SIGNAL:
            base_score += 0.05
            unmatched_signals.append("Event indicates delay/blocker/non-completion")
            reasoning.append("Event indicates a blocker, delay, or failure to fulfill.")
        elif semantic_role == EventSemanticRole.PROGRESS_UPDATE:
            base_score += 0.15
            matched_signals.append("Progress update detected")
            reasoning.append("Event indicates active progress on task.")

        # 2. Participant Alignment (Sender / Organizer & Recipients / Attendees)
        norm_sender = normalize_name(event.sender)
        norm_owner = normalize_name(obligation.owner)
        norm_recipients = [normalize_name(r) for r in event.recipients]
        norm_beneficiary = normalize_name(obligation.beneficiary)

        is_calendar = event.source_type == "google_calendar" or (
            isinstance(event.metadata, dict) and event.metadata.get("source_provider") == "google_calendar"
        )

        if is_calendar:
            # Calendar event attendee/organizer matching
            all_participants = [norm_sender] + norm_recipients
            owner_in_meeting = norm_owner in all_participants or (
                norm_owner in ["ravi", "you"] and any(p in ["ravi", "you"] for p in all_participants)
            )
            beneficiary_in_meeting = norm_beneficiary in all_participants or (
                norm_beneficiary in ["ravi", "you"] and any(p in ["ravi", "you"] for p in all_participants)
            ) or (norm_beneficiary in ["team", "executive team"] and len(all_participants) >= 2)

            if owner_in_meeting and beneficiary_in_meeting:
                base_score += 0.40
                matched_signals.append(f"Meeting participants include owner ({obligation.owner}) and beneficiary ({obligation.beneficiary})")
                reasoning.append(f"Calendar meeting participants include obligation owner '{obligation.owner}' and beneficiary '{obligation.beneficiary}'")
            elif owner_in_meeting:
                base_score += 0.25
                matched_signals.append(f"Meeting attendee includes obligation owner ({obligation.owner})")
                reasoning.append(f"Obligation owner '{obligation.owner}' is an attendee of this calendar meeting.")
            elif beneficiary_in_meeting:
                base_score += 0.15
                matched_signals.append(f"Meeting organizer/attendee includes beneficiary ({obligation.beneficiary})")
                reasoning.append(f"Obligation beneficiary '{obligation.beneficiary}' is a participant in this calendar meeting.")
            else:
                base_score -= 0.20
                unmatched_signals.append("Neither owner nor beneficiary is listed on calendar event")
                reasoning.append("Calendar event participants do not match obligation parties.")
        else:
            # Standard message sender vs owner alignment
            if norm_sender and norm_owner:
                if norm_sender == norm_owner or (norm_sender == "you" and norm_owner in ["ravi", "you"]) or (norm_owner == "you" and norm_sender in ["ravi", "you"]):
                    base_score += 0.35
                    matched_signals.append(f"Owner matches sender ({obligation.owner})")
                    reasoning.append(f"Event sender '{event.sender}' matches obligation owner '{obligation.owner}'")
                else:
                    base_score -= 0.25
                    unmatched_signals.append(f"Sender '{event.sender}' does not match owner '{obligation.owner}'")
                    reasoning.append(f"Sender '{event.sender}' differs from expected owner '{obligation.owner}'")
            else:
                reasoning.append("Sender metadata not provided for strict owner alignment.")

            # Standard message recipient vs beneficiary alignment
            if norm_beneficiary and norm_recipients:
                if norm_beneficiary in norm_recipients or (norm_beneficiary == "you" and any(r in ["ravi", "you"] for r in norm_recipients)) or (norm_beneficiary in ["ravi", "team"] and "you" in norm_recipients):
                    base_score += 0.20
                    matched_signals.append(f"Beneficiary matches recipient ({obligation.beneficiary})")
                    reasoning.append(f"Event recipient list includes obligation beneficiary '{obligation.beneficiary}'")
                else:
                    unmatched_signals.append("Recipient does not explicitly match beneficiary")
        
        # 4. Action Text / Entity Similarity
        action_tokens = tokenize_action(obligation.action)
        event_lower = event.content.lower()
        matched_tokens = [tok for tok in action_tokens if tok in event_lower]

        if action_tokens:
            overlap_ratio = len(matched_tokens) / len(action_tokens)
            if overlap_ratio >= 0.5:
                base_score += 0.25
                matched_signals.append(f"High action overlap: {', '.join(matched_tokens)}")
                reasoning.append(f"Substantial keyword/entity overlap with obligation action: {matched_tokens}")
            elif overlap_ratio > 0.2 or len(matched_tokens) >= 1:
                base_score += 0.15
                matched_signals.append(f"Partial action overlap: {', '.join(matched_tokens)}")
                reasoning.append(f"Partial action entity match: {matched_tokens}")
            else:
                base_score = min(base_score, 0.20)
                unmatched_signals.append("No text overlap with action description")
                reasoning.append("Event content has no keyword overlap with obligation action.")

        # 5. Attachment Signal Boost
        attachments = event.metadata.get("attachments", []) if isinstance(event.metadata, dict) else []
        if attachments and any(tok in ["report", "csv", "numbers", "doc", "specs", "file", "deck"] for tok in action_tokens):
            base_score += 0.10
            matched_signals.append(f"Attached deliverable artifact ({len(attachments)} file(s))")
            reasoning.append("Event includes attached file deliverable matching document obligation.")

        # Cap confidence score between 0.05 and 0.98
        score = max(0.05, min(0.98, base_score))

        # Commitments, requests, negative signals, and calendar scheduled events cannot be completion candidates
        if is_calendar:
            # Calendar events are temporal context / evidence, never auto-completion
            is_candidate = False
        elif semantic_role in [EventSemanticRole.COMMITMENT, EventSemanticRole.REQUEST, EventSemanticRole.NON_COMPLETION_SIGNAL, EventSemanticRole.IRRELEVANT]:
            score = min(0.40, score)
            is_candidate = False
        else:
            is_candidate = score >= CONFIDENCE_THRESHOLD_MEDIUM and semantic_role == EventSemanticRole.COMPLETION_SIGNAL

        # Confidence Level
        if score >= CONFIDENCE_THRESHOLD_HIGH:
            level = "HIGH"
            review_required = False
        elif score >= CONFIDENCE_THRESHOLD_MEDIUM:
            level = "MEDIUM"
            review_required = True
        else:
            level = "LOW"
            review_required = True

        return CorrelationMatch(
            obligation_id=obligation.id,
            owner=obligation.owner,
            beneficiary=obligation.beneficiary,
            action=obligation.action,
            status=obligation.status,
            correlation_confidence=round(score, 2),
            confidence_level=level,
            semantic_role=semantic_role,
            is_completion_candidate=is_candidate,
            matched_signals=matched_signals,
            unmatched_signals=unmatched_signals,
            reasoning=reasoning,
            review_required=review_required,
        )

    @classmethod
    def correlate(
        cls, event: ExternalEvent, candidate_obligations: List[Obligation]
    ) -> EventAnalysisResponse:
        has_attachments = bool(event.metadata.get("attachments")) if isinstance(event.metadata, dict) else False
        semantic_role, _, classifier_reason = EventClassifier.classify(
            event.content, has_attachments=has_attachments
        )

        if semantic_role == EventSemanticRole.IRRELEVANT and not candidate_obligations:
            return EventAnalysisResponse(
                semantic_role=semantic_role,
                matches=[],
                best_match=None,
                summary="No actionable commitment or completion signals found in event.",
            )

        matches: List[CorrelationMatch] = []
        for ob in candidate_obligations:
            match = cls.evaluate_match(event, ob, semantic_role, classifier_reason)
            matches.append(match)

        # Sort matches by score descending
        matches.sort(key=lambda m: m.correlation_confidence, reverse=True)

        best_match = matches[0] if matches else None
        summary = (
            f"Event classified as {semantic_role.value}. "
            f"Identified {len(matches)} potential obligation match(es)."
        )
        if best_match and best_match.is_completion_candidate:
            summary += f" Strong completion candidate for [{best_match.owner} -> {best_match.beneficiary}]: '{best_match.action}' ({int(best_match.correlation_confidence * 100)}% match)."

        return EventAnalysisResponse(
            semantic_role=semantic_role,
            matches=matches,
            best_match=best_match,
            summary=summary,
        )
