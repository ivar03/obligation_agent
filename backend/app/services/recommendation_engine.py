from typing import Tuple, List, Optional
from app.core.status_machine import (
    ObligationStatus,
    ObligationType,
    ActionType,
    RiskLevel,
)
from app.models.obligation import Obligation
from app.schemas.obligation import RiskSignal, BlockerDetail


class RecommendationEngine:
    """
    Produces actionable, structured, and non-presumptive recommendations
    based on dominant risk causes, duty direction, and blocker context.
    """

    @classmethod
    def generate_recommendation(
        cls,
        obligation: Obligation,
        risk_level: RiskLevel,
        signals: List[RiskSignal],
        blockers: List[BlockerDetail],
    ) -> Tuple[ActionType, str]:
        # Completed or Cancelled obligations need no action
        if obligation.status in [ObligationStatus.COMPLETED, ObligationStatus.CANCELLED]:
            return ActionType.NO_ACTION, "Obligation is resolved. No action required."

        signal_types = {s.signal_type for s in signals}

        # 1. Dependency / Blocker resolution
        if obligation.status == ObligationStatus.BLOCKED or "DEPENDENCY_OVERDUE" in signal_types or "DEPENDENCY_BLOCKED" in signal_types:
            if blockers:
                b = blockers[0]
                return (
                    ActionType.RESOLVE_DEPENDENCY,
                    f"Follow up with {b.owner} regarding blocking prerequisite: '{b.action}'.",
                )
            return (
                ActionType.RESOLVE_DEPENDENCY,
                "Resolve unresolved prerequisite dependency before proceeding.",
            )

        # 2. Conflicting evidence resolution
        if "CONFLICTING_EVIDENCE" in signal_types:
            return (
                ActionType.REVIEW_EVIDENCE,
                "Review conflicting evidence statements to verify fulfillment status.",
            )

        # 3. Completion candidate evidence pending confirmation
        if "COMPLETION_CANDIDATE_DETECTED" in signal_types:
            return (
                ActionType.REVIEW_EVIDENCE,
                "Review and confirm detected completion evidence to mark obligation complete.",
            )

        # 4. Ownership ambiguity
        if "OWNERSHIP_UNCERTAINTY" in signal_types:
            return (
                ActionType.ASSIGN_OWNER,
                "Assign a single accountable owner to eliminate responsibility uncertainty.",
            )

        # 5. Conditional waiting
        if "CONDITIONAL_TRIGGER_WAITING" in signal_types:
            return (
                ActionType.MONITOR_CONDITION,
                "Monitor prerequisite condition trigger before beginning execution.",
            )

        # 6. Overdue lifecycle state
        if obligation.status == ObligationStatus.OVERDUE or "DEADLINE_PASSED" in signal_types:
            if obligation.obligation_type == ObligationType.OWED_BY_ME:
                return (
                    ActionType.START_WORK,
                    "Complete overdue deliverable immediately or negotiate a revised deadline with the beneficiary.",
                )
            return (
                ActionType.FOLLOW_UP_OWNER,
                f"Follow up with {obligation.owner} regarding this overdue commitment.",
            )

        # 7. Approaching deadline pressure
        if "DEADLINE_PROXIMITY" in signal_types:
            if obligation.obligation_type == ObligationType.OWED_BY_ME:
                return (
                    ActionType.START_WORK,
                    "Begin work immediately to ensure on-time completion before the deadline.",
                )
            return (
                ActionType.FOLLOW_UP_OWNER,
                f"Send a proactive check-in to {obligation.owner} regarding upcoming delivery.",
            )

        # 8. Ambiguous or unknown deadline
        if "DEADLINE_AMBIGUOUS" in signal_types:
            return (
                ActionType.REVIEW_DEADLINE,
                "Clarify the timeline and set an explicit deadline.",
            )

        # 9. Low risk / Default
        if risk_level == RiskLevel.LOW:
            return ActionType.NO_ACTION, "Commitment is healthy and on schedule. No intervention needed."

        return ActionType.START_WORK, "Review current progress and ensure task remains on schedule."
