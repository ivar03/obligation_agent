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


class EvidenceType(str, Enum):
    MESSAGE = "MESSAGE"
    DOCUMENT = "DOCUMENT"
    FILE = "FILE"
    EVENT = "EVENT"
    MANUAL = "MANUAL"
    SYSTEM = "SYSTEM"


class CorrelationStatus(str, Enum):
    DETECTED = "DETECTED"
    SUGGESTED = "SUGGESTED"
    CONFIRMED = "CONFIRMED"
    REJECTED = "REJECTED"


class EventSemanticRole(str, Enum):
    COMPLETION_SIGNAL = "COMPLETION_SIGNAL"
    COMMITMENT = "COMMITMENT"
    REQUEST = "REQUEST"
    PROGRESS_UPDATE = "PROGRESS_UPDATE"
    NON_COMPLETION_SIGNAL = "NON_COMPLETION_SIGNAL"
    IRRELEVANT = "IRRELEVANT"


class RiskLevel(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class ActionType(str, Enum):
    START_WORK = "START_WORK"
    FOLLOW_UP_OWNER = "FOLLOW_UP_OWNER"
    RESOLVE_DEPENDENCY = "RESOLVE_DEPENDENCY"
    REVIEW_EVIDENCE = "REVIEW_EVIDENCE"
    ASSIGN_OWNER = "ASSIGN_OWNER"
    MONITOR_CONDITION = "MONITOR_CONDITION"
    REVIEW_DEADLINE = "REVIEW_DEADLINE"
    PREPARE_FOR_MEETING = "PREPARE_FOR_MEETING"
    FOLLOW_UP_AFTER_MEETING = "FOLLOW_UP_AFTER_MEETING"
    REVIEW_RESCHEDULED_COMMITMENT = "REVIEW_RESCHEDULED_COMMITMENT"
    REVIEW_CANCELLED_MEETING = "REVIEW_CANCELLED_MEETING"
    REVIEW_CONFLICTING_EVIDENCE = "REVIEW_CONFLICTING_EVIDENCE"
    CONFIRM_COMPLETION_EVIDENCE = "CONFIRM_COMPLETION_EVIDENCE"
    REVIEW_STALE_SIGNAL = "REVIEW_STALE_SIGNAL"
    KEEP_ACTIVE = "KEEP_ACTIVE"
    EARLY_FOLLOW_UP = "EARLY_FOLLOW_UP"
    PREPARE_EVIDENCE_REVIEW = "PREPARE_EVIDENCE_REVIEW"
    CLARIFY_OWNER = "CLARIFY_OWNER"
    CLARIFY_DEADLINE = "CLARIFY_DEADLINE"
    MONITOR_PROGRESS = "MONITOR_PROGRESS"
    NO_PREVENTATIVE_ACTION = "NO_PREVENTATIVE_ACTION"
    NO_ACTION = "NO_ACTION"


class ReconciliationStatus(str, Enum):
    CONSISTENT = "CONSISTENT"
    CONFLICTING = "CONFLICTING"
    AMBIGUOUS = "AMBIGUOUS"
    RESOLVED_SUPPORTING = "RESOLVED_SUPPORTING"
    RESOLVED_CONFLICTING = "RESOLVED_CONFLICTING"
    DISMISSED = "DISMISSED"


class ReconciliationResolutionAction(str, Enum):
    CONFIRM_COMPLETION = "CONFIRM_COMPLETION"
    CONFIRM_NOT_COMPLETED = "CONFIRM_NOT_COMPLETED"
    DISMISS_CONTRADICTION = "DISMISS_CONTRADICTION"
    MARK_AS_STALE = "MARK_AS_STALE"
    KEEP_OBLIGATION_ACTIVE = "KEEP_OBLIGATION_ACTIVE"
    REOPEN_OBLIGATION = "REOPEN_OBLIGATION"


class ObligationOutcomeType(str, Enum):
    COMPLETED_ON_TIME = "COMPLETED_ON_TIME"
    COMPLETED_LATE = "COMPLETED_LATE"
    OVERDUE = "OVERDUE"
    BLOCKED = "BLOCKED"
    CANCELLED = "CANCELLED"
    ABANDONED = "ABANDONED"
    COMPLETED_AFTER_INTERVENTION = "COMPLETED_AFTER_INTERVENTION"
    COMPLETED_AFTER_FOLLOW_UP = "COMPLETED_AFTER_FOLLOW_UP"
    COMPLETED_AFTER_DEPENDENCY_RESOLUTION = "COMPLETED_AFTER_DEPENDENCY_RESOLUTION"
    CONFLICTED_COMPLETION = "CONFLICTED_COMPLETION"
    UNKNOWN = "UNKNOWN"


class PredictiveActionType(str, Enum):
    EARLY_FOLLOW_UP = "EARLY_FOLLOW_UP"
    PREPARE_EVIDENCE_REVIEW = "PREPARE_EVIDENCE_REVIEW"
    RESOLVE_DEPENDENCY = "RESOLVE_DEPENDENCY"
    CLARIFY_OWNER = "CLARIFY_OWNER"
    CLARIFY_DEADLINE = "CLARIFY_DEADLINE"
    MONITOR_PROGRESS = "MONITOR_PROGRESS"
    NO_PREVENTATIVE_ACTION = "NO_PREVENTATIVE_ACTION"


class CalibrationStatus(str, Enum):
    INSUFFICIENT_HISTORY = "INSUFFICIENT_HISTORY"
    LOW_SAMPLE = "LOW_SAMPLE"
    CALIBRATION_AVAILABLE = "CALIBRATION_AVAILABLE"


class FeatureDirection(str, Enum):
    INCREASES_RISK = "INCREASES_RISK"
    DECREASES_RISK = "DECREASES_RISK"
    NEUTRAL = "NEUTRAL"


class PredictionProviderType(str, Enum):
    DETERMINISTIC_V1 = "deterministic-v1"
    ADAPTIVE_V1 = "adaptive-v1"




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


# ==============================================================================
# PHASE 14: IDENTITY, WORKSPACE & ROLE AUTHORIZATION
# ==============================================================================

class WorkspaceRole(str, Enum):
    OWNER = "OWNER"
    ADMIN = "ADMIN"
    MEMBER = "MEMBER"
    VIEWER = "VIEWER"


ROLE_HIERARCHY: Dict[WorkspaceRole, int] = {
    WorkspaceRole.VIEWER: 10,
    WorkspaceRole.MEMBER: 20,
    WorkspaceRole.ADMIN: 30,
    WorkspaceRole.OWNER: 40,
}


ROLE_PERMISSIONS: Dict[str, Set[WorkspaceRole]] = {
    "VIEW_OBLIGATIONS": {WorkspaceRole.VIEWER, WorkspaceRole.MEMBER, WorkspaceRole.ADMIN, WorkspaceRole.OWNER},
    "MUTATE_OBLIGATIONS": {WorkspaceRole.MEMBER, WorkspaceRole.ADMIN, WorkspaceRole.OWNER},
    "DELETE_OBLIGATIONS": {WorkspaceRole.MEMBER, WorkspaceRole.ADMIN, WorkspaceRole.OWNER},
    "CONFIRM_EVIDENCE": {WorkspaceRole.MEMBER, WorkspaceRole.ADMIN, WorkspaceRole.OWNER},
    "PLAN_INTERVENTIONS": {WorkspaceRole.MEMBER, WorkspaceRole.ADMIN, WorkspaceRole.OWNER},
    "APPROVE_INTERVENTIONS": {WorkspaceRole.MEMBER, WorkspaceRole.ADMIN, WorkspaceRole.OWNER},
    "EXECUTE_INTERVENTIONS": {WorkspaceRole.MEMBER, WorkspaceRole.ADMIN, WorkspaceRole.OWNER},
    "MANAGE_INTEGRATIONS": {WorkspaceRole.ADMIN, WorkspaceRole.OWNER},
    "MANAGE_MEMBERS": {WorkspaceRole.ADMIN, WorkspaceRole.OWNER},
    "CHANGE_ROLES": {WorkspaceRole.ADMIN, WorkspaceRole.OWNER},
    "DELETE_WORKSPACE": {WorkspaceRole.OWNER},
    "VIEW_AUDIT_LOG": {WorkspaceRole.ADMIN, WorkspaceRole.OWNER},
    "VIEW_ENTITY_AUDIT": {WorkspaceRole.VIEWER, WorkspaceRole.MEMBER, WorkspaceRole.ADMIN, WorkspaceRole.OWNER},
    "MANAGE_GOVERNANCE": {WorkspaceRole.ADMIN, WorkspaceRole.OWNER},
    "VERIFY_AUDIT_CHAIN": {WorkspaceRole.ADMIN, WorkspaceRole.OWNER},
    "EXPORT_AUDIT_LOG": {WorkspaceRole.ADMIN, WorkspaceRole.OWNER},
}


def has_permission(role: WorkspaceRole, capability: str) -> bool:
    allowed_roles = ROLE_PERMISSIONS.get(capability, set())
    return role in allowed_roles


# ==============================================================================
# PHASE 15: ENTERPRISE AUDIT & GOVERNANCE ENUMS
# ==============================================================================

class AuditAction(str, Enum):
    # Authentication & Session
    AUTH_LOGIN = "AUTH_LOGIN"
    AUTH_LOGOUT = "AUTH_LOGOUT"
    AUTH_LOGIN_FAILED = "AUTH_LOGIN_FAILED"
    AUTH_SESSION_CREATED = "AUTH_SESSION_CREATED"
    AUTH_SESSION_REVOKED = "AUTH_SESSION_REVOKED"

    # Workspace & Membership
    WORKSPACE_CREATED = "WORKSPACE_CREATED"
    WORKSPACE_RENAMED = "WORKSPACE_RENAMED"
    WORKSPACE_MEMBER_INVITED = "WORKSPACE_MEMBER_INVITED"
    WORKSPACE_MEMBER_ROLE_CHANGED = "WORKSPACE_MEMBER_ROLE_CHANGED"
    WORKSPACE_MEMBER_REMOVED = "WORKSPACE_MEMBER_REMOVED"
    WORKSPACE_OWNERSHIP_TRANSFERRED = "WORKSPACE_OWNERSHIP_TRANSFERRED"

    # Obligations
    OBLIGATION_CREATED = "OBLIGATION_CREATED"
    OBLIGATION_UPDATED = "OBLIGATION_UPDATED"
    OBLIGATION_DELETED = "OBLIGATION_DELETED"
    OBLIGATION_STATUS_CHANGED = "OBLIGATION_STATUS_CHANGED"

    # Graph Edges
    EDGE_CREATED = "EDGE_CREATED"
    EDGE_DELETED = "EDGE_DELETED"

    # Evidence
    EVIDENCE_CREATED = "EVIDENCE_CREATED"
    EVIDENCE_CONFIRMED = "EVIDENCE_CONFIRMED"
    EVIDENCE_REJECTED = "EVIDENCE_REJECTED"

    # Reconciliation
    RECONCILIATION_RESOLVED = "RECONCILIATION_RESOLVED"
    RECONCILIATION_DISMISSED = "RECONCILIATION_DISMISSED"

    # Interventions
    INTERVENTION_CREATED = "INTERVENTION_CREATED"
    INTERVENTION_EDITED = "INTERVENTION_EDITED"
    INTERVENTION_APPROVED = "INTERVENTION_APPROVED"
    INTERVENTION_SCHEDULED = "INTERVENTION_SCHEDULED"
    INTERVENTION_EXECUTED = "INTERVENTION_EXECUTED"
    INTERVENTION_CANCELLED = "INTERVENTION_CANCELLED"
    INTERVENTION_RESOLVED = "INTERVENTION_RESOLVED"

    # Event Ingestion
    EVENT_INGESTED = "EVENT_INGESTED"
    EVENT_DUPLICATE_DETECTED = "EVENT_DUPLICATE_DETECTED"

    # Integrations
    INTEGRATION_CONNECTED = "INTEGRATION_CONNECTED"
    INTEGRATION_DISCONNECTED = "INTEGRATION_DISCONNECTED"
    INTEGRATION_CONFIGURED = "INTEGRATION_CONFIGURED"
    INTEGRATION_DISABLED = "INTEGRATION_DISABLED"
    INTEGRATION_TESTED = "INTEGRATION_TESTED"

    # Intelligence & Feedback
    PREDICTION_GENERATED = "PREDICTION_GENERATED"
    PREDICTION_FEEDBACK_RECORDED = "PREDICTION_FEEDBACK_RECORDED"

    # Security & Access Control
    PERMISSION_DENIED = "PERMISSION_DENIED"
    SECURITY_VIOLATION = "SECURITY_VIOLATION"


class AuditSeverity(str, Enum):
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class AuditResult(str, Enum):
    SUCCESS = "SUCCESS"
    DENIED = "DENIED"
    FAILED = "FAILED"
    VIOLATION = "VIOLATION"


class AuditSource(str, Enum):
    API = "API"
    WEBHOOK = "WEBHOOK"
    SYSTEM_WORKER = "SYSTEM_WORKER"
    INTEGRATION_SYNC = "INTEGRATION_SYNC"

