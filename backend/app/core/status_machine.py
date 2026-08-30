from enum import Enum
from typing import Set, Dict


class ObligationStatus(str, Enum):
    DETECTED = "DETECTED"
    CONFIRMED = "CONFIRMED"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    OVERDUE = "OVERDUE"
    CANCELLED = "CANCELLED"
    BLOCKED = "BLOCKED"


class ObligationType(str, Enum):
    OWED_BY_ME = "OWED_BY_ME"
    OWED_TO_ME = "OWED_TO_ME"


class EdgeType(str, Enum):
    DEPENDS_ON = "DEPENDS_ON"
    LINKED = "LINKED"


VALID_TRANSITIONS: Dict[ObligationStatus, Set[ObligationStatus]] = {
    ObligationStatus.DETECTED: {
        ObligationStatus.CONFIRMED,
        ObligationStatus.CANCELLED,
    },
    ObligationStatus.CONFIRMED: {
        ObligationStatus.IN_PROGRESS,
        ObligationStatus.COMPLETED,
        ObligationStatus.BLOCKED,
        ObligationStatus.OVERDUE,
        ObligationStatus.CANCELLED,
    },
    ObligationStatus.IN_PROGRESS: {
        ObligationStatus.COMPLETED,
        ObligationStatus.BLOCKED,
        ObligationStatus.OVERDUE,
        ObligationStatus.CANCELLED,
        ObligationStatus.CONFIRMED,
    },
    ObligationStatus.BLOCKED: {
        ObligationStatus.IN_PROGRESS,
        ObligationStatus.CONFIRMED,
        ObligationStatus.CANCELLED,
        ObligationStatus.OVERDUE,
    },
    ObligationStatus.OVERDUE: {
        ObligationStatus.IN_PROGRESS,
        ObligationStatus.COMPLETED,
        ObligationStatus.CANCELLED,
        ObligationStatus.BLOCKED,
    },
    ObligationStatus.COMPLETED: {
        ObligationStatus.IN_PROGRESS,
    },
    ObligationStatus.CANCELLED: {
        ObligationStatus.CONFIRMED,
    },
}


class InvalidStatusTransitionError(Exception):
    def __init__(self, current_status: ObligationStatus, new_status: ObligationStatus):
        super().__init__(
            f"Invalid status transition from '{current_status}' to '{new_status}'."
        )
        self.current_status = current_status
        self.new_status = new_status


def validate_status_transition(current: ObligationStatus, target: ObligationStatus) -> None:
    if current == target:
        return
    allowed = VALID_TRANSITIONS.get(current, set())
    if target not in allowed:
        raise InvalidStatusTransitionError(current, target)
