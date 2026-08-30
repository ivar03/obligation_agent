import re
from abc import ABC, abstractmethod
from typing import List, Optional
from app.core.logging import logger
from app.core.status_machine import ObligationType
from app.schemas.obligation import MessageContext, OwnershipResolution


class BaseOwnershipAgent(ABC):
    """Abstract interface for ownership reasoning agent."""

    @abstractmethod
    async def resolve(self, text: str, context: MessageContext) -> OwnershipResolution:
        pass


class DevMockOwnershipAgent(BaseOwnershipAgent):
    """
    Rule-based and heuristic ownership reasoning agent.
    Accurately identifies first-person, second-person, third-person, reciprocal,
    and ambiguous group patterns without hallucinating arbitrary owners.
    """

    async def resolve(self, text: str, context: MessageContext) -> OwnershipResolution:
        cleaned = text.strip()
        lower = cleaned.lower()
        current_user = context.current_user or "You"
        sender = context.sender
        recipients = context.recipients or []
        participants = context.participants or []

        # 1. Ambiguous Group / Passive Phrasing
        ambiguous_pattern = r"\b(we should probably|someone should|maybe we|somebody needs to|it would be nice if we|we need to|can someone|team should)\b"
        if re.search(ambiguous_pattern, lower):
            logger.info("OwnershipAgent detected ambiguous group/unassigned phrasing.")
            suggested = [p for p in participants if p not in ["You", "Unassigned / Team (Ambiguous)"]]
            if not suggested:
                suggested = [current_user]
            return OwnershipResolution(
                owner="Unassigned / Team (Ambiguous)",
                beneficiary="Client / Team",
                confidence=0.35,
                reasoning="The message uses collective or unassigned phrasing ('we/someone') without identifying a specific responsible duty bearer.",
                ambiguous=True,
                obligation_type=ObligationType.OWED_BY_ME,
                suggested_assignees=suggested
            )

        # 2. Reciprocal "X owes Y:" pattern
        owes_match = re.search(r"^([A-Za-z0-9_\s]+)\s+owes\s+([A-Za-z0-9_\s]+)[:\s-]+(.*)$", cleaned, re.IGNORECASE)
        if owes_match:
            raw_owner = owes_match.group(1).strip()
            raw_beneficiary = owes_match.group(2).strip()

            is_owner_me = raw_owner.lower() in ["ravi", "i", "me", "you", "user", current_user.lower()]
            is_bene_me = raw_beneficiary.lower() in ["ravi", "i", "me", "you", "user", current_user.lower()]

            if is_owner_me:
                owner = current_user
                beneficiary = raw_beneficiary if not is_bene_me else "Recipient"
                ob_type = ObligationType.OWED_BY_ME
            elif is_bene_me:
                owner = raw_owner
                beneficiary = current_user
                ob_type = ObligationType.OWED_TO_ME
            else:
                owner = raw_owner
                beneficiary = raw_beneficiary
                ob_type = ObligationType.OWED_TO_ME

            logger.info(f"OwnershipAgent resolved explicit reciprocal relationship: {owner} -> {beneficiary}")
            return OwnershipResolution(
                owner=owner,
                beneficiary=beneficiary,
                confidence=0.96,
                reasoning=f"Explicit reciprocal obligation detected between '{owner}' (duty bearer) and '{beneficiary}' (beneficiary).",
                ambiguous=False,
                obligation_type=ob_type,
                suggested_assignees=[owner]
            )

        # 3. Explicit Second-Person Request: "Rahul, please..." or "Hey Rahul, send me..."
        addressed_match = re.search(r"^(?:hey|hi|hello)?\s*([A-Z][a-z]+)[,:]\s*(?:please|can you|could you|would you)?\s*(.*)", cleaned, re.IGNORECASE)
        if addressed_match:
            addressed_name = addressed_match.group(1).capitalize()
            rest = addressed_match.group(2).lower()
            if addressed_name.lower() not in ["i", "we", "you"]:
                beneficiary = current_user
                if sender:
                    beneficiary = sender
                logger.info(f"OwnershipAgent resolved second-person directive to {addressed_name}")
                return OwnershipResolution(
                    owner=addressed_name,
                    beneficiary=beneficiary,
                    confidence=0.94,
                    reasoning=f"The message is a direct request addressed to '{addressed_name}'.",
                    ambiguous=False,
                    obligation_type=ObligationType.OWED_TO_ME,
                    suggested_assignees=[addressed_name]
                )

        # 4. Explicit Third-Person: "Rahul will send..." or "Professor will review..."
        third_person_match = re.search(r"\b([A-Z][a-z]+)\s+(?:will|shall|promises to|is going to)\s+([a-z].*)", cleaned)
        if third_person_match:
            third_party = third_person_match.group(1).capitalize()
            if third_party.lower() not in ["i", "we", "you", "the"]:
                beneficiary = current_user
                if sender and sender != third_party:
                    beneficiary = sender
                logger.info(f"OwnershipAgent resolved third-person commitment from {third_party}")
                return OwnershipResolution(
                    owner=third_party,
                    beneficiary=beneficiary,
                    confidence=0.92,
                    reasoning=f"Third-person commitment statement identifies '{third_party}' as the duty bearer.",
                    ambiguous=False,
                    obligation_type=ObligationType.OWED_TO_ME,
                    suggested_assignees=[third_party]
                )

        # 5. First-Person: "I will...", "I'll...", "I need to..."
        if re.search(r"\b(i will|i'll|i promise to|i shall|i need to|i am going to)\b", lower):
            owner = current_user
            if sender and sender.lower() not in ["you", "me", "i"]:
                owner = sender
            
            # Extract beneficiary if "to [Name]" is present
            beneficiary = "Recipient"
            to_match = re.search(r"\bto\s+([A-Z][a-z]+|the\s+[a-z]+)\b", cleaned)
            if to_match:
                beneficiary = to_match.group(1).strip()
            elif recipients:
                beneficiary = recipients[0]

            logger.info(f"OwnershipAgent resolved first-person commitment by {owner} to {beneficiary}")
            return OwnershipResolution(
                owner=owner,
                beneficiary=beneficiary,
                confidence=0.95,
                reasoning="The speaker explicitly states their personal commitment using first-person language ('I will...').",
                ambiguous=False,
                obligation_type=ObligationType.OWED_BY_ME,
                suggested_assignees=[owner]
            )

        # 6. Generic "Can you..." / "Please..." without explicit addressed name
        if re.search(r"\b(can you|could you|please)\b", lower):
            owner = recipients[0] if recipients else current_user
            beneficiary = sender if sender else "Requester"
            logger.info(f"OwnershipAgent resolved generic directive to {owner}")
            return OwnershipResolution(
                owner=owner,
                beneficiary=beneficiary,
                confidence=0.88 if recipients else 0.78,
                reasoning=f"Direct action request assigns responsibility to '{owner}'.",
                ambiguous=False if recipients else True,
                obligation_type=ObligationType.OWED_BY_ME if owner == current_user else ObligationType.OWED_TO_ME,
                suggested_assignees=participants or [current_user]
            )

        # Default fallback
        logger.info("OwnershipAgent applying fallback owner determination.")
        return OwnershipResolution(
            owner=current_user,
            beneficiary="Team",
            confidence=0.70,
            reasoning="Defaulted responsibility to current user due to implicit duty context.",
            ambiguous=True,
            obligation_type=ObligationType.OWED_BY_ME,
            suggested_assignees=participants or [current_user]
        )
