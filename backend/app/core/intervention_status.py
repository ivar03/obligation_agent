from enum import Enum
from typing import Set, Dict


class InterventionType(str, Enum):
    FOLLOW_UP_OWNER = "FOLLOW_UP_OWNER"
    REQUEST_STATUS_UPDATE = "REQUEST_STATUS_UPDATE"
    REQUEST_MISSING_DELIVERABLE = "REQUEST_MISSING_DELIVERABLE"
    RESOLVE_DEPENDENCY = "RESOLVE_DEPENDENCY"
    REVIEW_EVIDENCE = "REVIEW_EVIDENCE"
    ASSIGN_OWNER = "ASSIGN_OWNER"
    CLARIFY_DEADLINE = "CLARIFY_DEADLINE"
    MONITOR_CONDITION = "MONITOR_CONDITION"
    NO_INTERVENTION = "NO_INTERVENTION"


class InterventionStatus(str, Enum):
    DRAFT = "DRAFT"
    PENDING_REVIEW = "PENDING_REVIEW"
    APPROVED = "APPROVED"
    SCHEDULED = "SCHEDULED"
    READY_TO_EXECUTE = "READY_TO_EXECUTE"
    EXECUTED = "EXECUTED"
    ACKNOWLEDGED = "ACKNOWLEDGED"
    RESOLVED = "RESOLVED"
    CANCELLED = "CANCELLED"
    EXPIRED = "EXPIRED"


class InterventionOutcome(str, Enum):
    ACKNOWLEDGED = "ACKNOWLEDGED"
    PROGRESS_REPORTED = "PROGRESS_REPORTED"
    COMPLETED = "COMPLETED"
    NO_RESPONSE = "NO_RESPONSE"
    NEGATIVE_RESPONSE = "NEGATIVE_RESPONSE"
    REJECTED = "REJECTED"
    NOT_NEEDED = "NOT_NEEDED"
    UNKNOWN = "UNKNOWN"


VALID_INTERVENTION_TRANSITIONS: Dict[InterventionStatus, Set[InterventionStatus]] = {
    InterventionStatus.DRAFT: {
        InterventionStatus.PENDING_REVIEW,
        InterventionStatus.CANCELLED,
    },
    InterventionStatus.PENDING_REVIEW: {
        InterventionStatus.APPROVED,
        InterventionStatus.SCHEDULED,
        InterventionStatus.CANCELLED,
        InterventionStatus.EXPIRED,
    },
    InterventionStatus.APPROVED: {
        InterventionStatus.SCHEDULED,
        InterventionStatus.READY_TO_EXECUTE,
        InterventionStatus.EXECUTED,
        InterventionStatus.CANCELLED,
    },
    InterventionStatus.SCHEDULED: {
        InterventionStatus.READY_TO_EXECUTE,
        InterventionStatus.EXECUTED,
        InterventionStatus.CANCELLED,
    },
    InterventionStatus.READY_TO_EXECUTE: {
        InterventionStatus.EXECUTED,
        InterventionStatus.CANCELLED,
    },
    InterventionStatus.EXECUTED: {
        InterventionStatus.ACKNOWLEDGED,
        InterventionStatus.RESOLVED,
        InterventionStatus.CANCELLED,
        InterventionStatus.EXPIRED,
    },
    InterventionStatus.ACKNOWLEDGED: {
        InterventionStatus.RESOLVED,
        InterventionStatus.CANCELLED,
    },
    InterventionStatus.RESOLVED: set(),
    InterventionStatus.CANCELLED: set(),
    InterventionStatus.EXPIRED: set(),
}


class InvalidInterventionStatusTransitionError(Exception):
    def __init__(self, current_status: InterventionStatus, new_status: InterventionStatus):
        super().__init__(
            f"Invalid intervention status transition from '{current_status}' to '{new_status}'."
        )
        self.current_status = current_status
        self.new_status = new_status


def validate_intervention_transition(
    current: InterventionStatus, target: InterventionStatus
) -> None:
    if current == target:
        return
    allowed = VALID_INTERVENTION_TRANSITIONS.get(current, set())
    if target not in allowed:
        raise InvalidInterventionStatusTransitionError(current, target)
