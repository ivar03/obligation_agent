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
    OPERATOR = "OPERATOR"
    MEMBER = "MEMBER"
    VIEWER = "VIEWER"


ROLE_HIERARCHY: Dict[WorkspaceRole, int] = {
    WorkspaceRole.VIEWER: 10,
    WorkspaceRole.MEMBER: 20,
    WorkspaceRole.OPERATOR: 25,
    WorkspaceRole.ADMIN: 30,
    WorkspaceRole.OWNER: 40,
}


ROLE_PERMISSIONS: Dict[str, Set[WorkspaceRole]] = {
    "VIEW_OBLIGATIONS": {WorkspaceRole.VIEWER, WorkspaceRole.MEMBER, WorkspaceRole.OPERATOR, WorkspaceRole.ADMIN, WorkspaceRole.OWNER},
    "CREATE_OBLIGATION": {WorkspaceRole.MEMBER, WorkspaceRole.OPERATOR, WorkspaceRole.ADMIN, WorkspaceRole.OWNER},
    "MUTATE_OBLIGATIONS": {WorkspaceRole.MEMBER, WorkspaceRole.OPERATOR, WorkspaceRole.ADMIN, WorkspaceRole.OWNER},
    "DELETE_OBLIGATIONS": {WorkspaceRole.ADMIN, WorkspaceRole.OWNER},
    "CONFIRM_EVIDENCE": {WorkspaceRole.OPERATOR, WorkspaceRole.ADMIN, WorkspaceRole.OWNER},
    "REJECT_EVIDENCE": {WorkspaceRole.OPERATOR, WorkspaceRole.ADMIN, WorkspaceRole.OWNER},
    "PLAN_INTERVENTIONS": {WorkspaceRole.OPERATOR, WorkspaceRole.ADMIN, WorkspaceRole.OWNER},
    "APPROVE_INTERVENTIONS": {WorkspaceRole.OPERATOR, WorkspaceRole.ADMIN, WorkspaceRole.OWNER},
    "EXECUTE_INTERVENTIONS": {WorkspaceRole.OPERATOR, WorkspaceRole.ADMIN, WorkspaceRole.OWNER},
    "GENERATE_DECISION_PLAN": {WorkspaceRole.MEMBER, WorkspaceRole.OPERATOR, WorkspaceRole.ADMIN, WorkspaceRole.OWNER},
    "APPROVE_DECISION_PLAN": {WorkspaceRole.OPERATOR, WorkspaceRole.ADMIN, WorkspaceRole.OWNER},
    "REJECT_DECISION_PLAN": {WorkspaceRole.OPERATOR, WorkspaceRole.ADMIN, WorkspaceRole.OWNER},
    "AUTHORIZE_EXECUTION": {WorkspaceRole.OPERATOR, WorkspaceRole.ADMIN, WorkspaceRole.OWNER},
    "EXECUTE_DECISION": {WorkspaceRole.OPERATOR, WorkspaceRole.ADMIN, WorkspaceRole.OWNER},
    "RETRY_EXECUTION": {WorkspaceRole.OPERATOR, WorkspaceRole.ADMIN, WorkspaceRole.OWNER},
    "CANCEL_EXECUTION": {WorkspaceRole.OPERATOR, WorkspaceRole.ADMIN, WorkspaceRole.OWNER},
    "MANAGE_INTEGRATIONS": {WorkspaceRole.ADMIN, WorkspaceRole.OWNER},
    "MANAGE_MEMBERS": {WorkspaceRole.ADMIN, WorkspaceRole.OWNER},
    "INVITE_MEMBERS": {WorkspaceRole.ADMIN, WorkspaceRole.OWNER},
    "CHANGE_ROLES": {WorkspaceRole.ADMIN, WorkspaceRole.OWNER},
    "DELETE_WORKSPACE": {WorkspaceRole.OWNER},
    "MANAGE_WORKSPACE_SETTINGS": {WorkspaceRole.ADMIN, WorkspaceRole.OWNER},
    "IMPORT_OBLIGATIONS": {WorkspaceRole.MEMBER, WorkspaceRole.OPERATOR, WorkspaceRole.ADMIN, WorkspaceRole.OWNER},
    "VIEW_AUDIT_LOG": {WorkspaceRole.OPERATOR, WorkspaceRole.ADMIN, WorkspaceRole.OWNER},
    "VIEW_ENTITY_AUDIT": {WorkspaceRole.VIEWER, WorkspaceRole.MEMBER, WorkspaceRole.OPERATOR, WorkspaceRole.ADMIN, WorkspaceRole.OWNER},
    "MANAGE_GOVERNANCE": {WorkspaceRole.ADMIN, WorkspaceRole.OWNER},
    "VERIFY_AUDIT_CHAIN": {WorkspaceRole.ADMIN, WorkspaceRole.OWNER},
    "EXPORT_AUDIT_LOG": {WorkspaceRole.ADMIN, WorkspaceRole.OWNER},
    "TRIGGER_MONITORING": {WorkspaceRole.OPERATOR, WorkspaceRole.ADMIN, WorkspaceRole.OWNER},
    "MANAGE_WATCHES": {WorkspaceRole.OPERATOR, WorkspaceRole.ADMIN, WorkspaceRole.OWNER},
    "MANAGE_ESCALATIONS": {WorkspaceRole.OPERATOR, WorkspaceRole.ADMIN, WorkspaceRole.OWNER},
}


def has_permission(role: WorkspaceRole, capability: str) -> bool:
    allowed_roles = ROLE_PERMISSIONS.get(capability, set())
    return role in allowed_roles


# ==============================================================================
# PHASE 18: PRODUCTIZATION & BETA READINESS ENUMS
# ==============================================================================

class InvitationStatus(str, Enum):
    PENDING = "PENDING"
    ACCEPTED = "ACCEPTED"
    EXPIRED = "EXPIRED"
    CANCELLED = "CANCELLED"


class NotificationCategory(str, Enum):
    ACTION_REQUIRED = "ACTION_REQUIRED"
    INFORMATION = "INFORMATION"
    WARNING = "WARNING"
    ERROR = "ERROR"
    SECURITY = "SECURITY"
    INTEGRATION = "INTEGRATION"


class NotificationSeverity(str, Enum):
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class OnboardingStep(str, Enum):
    WELCOME = "WELCOME"
    CREATE_WORKSPACE = "CREATE_WORKSPACE"
    INVITE_TEAM = "INVITE_TEAM"
    CONNECT_SLACK = "CONNECT_SLACK"
    MONITORING_PREFS = "MONITORING_PREFS"
    IMPORT_OBLIGATIONS = "IMPORT_OBLIGATIONS"
    COMPLETED = "COMPLETED"


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


# ==============================================================================
# PHASE 14: ROOT-CAUSE ANALYSIS, RESOLUTION PLANNING & SIMULATION ENUMS
# ==============================================================================

class CausalFactorType(str, Enum):
    DIRECT_CAUSE = "DIRECT_CAUSE"
    UPSTREAM_CAUSE = "UPSTREAM_CAUSE"
    CONTRIBUTING_FACTOR = "CONTRIBUTING_FACTOR"
    UNCERTAINTY = "UNCERTAINTY"


class ResolutionStrategyType(str, Enum):
    RESOLVE_ROOT_BLOCKER = "RESOLVE_ROOT_BLOCKER"
    FOLLOW_UP_ROOT_OWNER = "FOLLOW_UP_ROOT_OWNER"
    REQUEST_MISSING_EVIDENCE = "REQUEST_MISSING_EVIDENCE"
    ASSIGN_OWNER = "ASSIGN_OWNER"
    CLARIFY_DEADLINE = "CLARIFY_DEADLINE"
    REVIEW_CONFLICTING_EVIDENCE = "REVIEW_CONFLICTING_EVIDENCE"
    WAIT_FOR_CONDITION = "WAIT_FOR_CONDITION"
    REVIEW_DEPENDENCY = "REVIEW_DEPENDENCY"
    NO_ACTION = "NO_ACTION"


class SimulationActionType(str, Enum):
    COMPLETE_OBLIGATION = "COMPLETE_OBLIGATION"
    RESOLVE_BLOCKER = "RESOLVE_BLOCKER"
    ASSIGN_OWNER = "ASSIGN_OWNER"
    REMOVE_DEPENDENCY = "REMOVE_DEPENDENCY"
    CONFIRM_EVIDENCE = "CONFIRM_EVIDENCE"


class ConcentrationType(str, Enum):
    BOTTLENECK = "BOTTLENECK"
    HIGH_IMPACT_OWNER = "HIGH_IMPACT_OWNER"
    CRITICAL_PREREQUISITE = "CRITICAL_PREREQUISITE"
    RISK_CONCENTRATION = "RISK_CONCENTRATION"


# ==============================================================================
# PHASE 15: INTELLIGENCE ORCHESTRATOR & DECISION LAYER ENUMS
# ==============================================================================

class DecisionPlanStatus(str, Enum):
    GENERATED = "GENERATED"
    PENDING_REVIEW = "PENDING_REVIEW"
    APPROVED = "APPROVED"
    PARTIALLY_EXECUTED = "PARTIALLY_EXECUTED"
    RESOLVED = "RESOLVED"
    REJECTED = "REJECTED"
    SUPERSEDED = "SUPERSEDED"
    EXPIRED = "EXPIRED"
    CANCELLED = "CANCELLED"


class ProvenanceSourceType(str, Enum):
    ROOT_CAUSE = "ROOT_CAUSE"
    RISK_ENGINE = "RISK_ENGINE"
    PREDICTION = "PREDICTION"
    EVIDENCE = "EVIDENCE"
    GRAPH = "GRAPH"
    EVENT = "EVENT"
    INTERVENTION = "INTERVENTION"


class HumanDecisionType(str, Enum):
    ASSIGN_OWNER = "ASSIGN_OWNER"
    APPROVE_INTERVENTION = "APPROVE_INTERVENTION"
    CONFIRM_EVIDENCE = "CONFIRM_EVIDENCE"
    CHANGE_DEADLINE = "CHANGE_DEADLINE"
    REMOVE_DEPENDENCY = "REMOVE_DEPENDENCY"
    APPROVE_ALTERNATIVE_STRATEGY = "APPROVE_ALTERNATIVE_STRATEGY"


# ==============================================================================
# PHASE 16: ORGANIZATIONAL MEMORY & HISTORICAL REASONING ENUMS
# ==============================================================================

class MemoryType(str, Enum):
    OBLIGATION_OUTCOME = "OBLIGATION_OUTCOME"
    EVIDENCE_PATTERN = "EVIDENCE_PATTERN"
    INTERVENTION_OUTCOME = "INTERVENTION_OUTCOME"
    DEPENDENCY_PATTERN = "DEPENDENCY_PATTERN"
    OWNER_HISTORY = "OWNER_HISTORY"
    BLOCKER_PATTERN = "BLOCKER_PATTERN"
    RESOLUTION_PATTERN = "RESOLUTION_PATTERN"
    EVENT_CONTEXT = "EVENT_CONTEXT"
    RECURRING_COMMITMENT = "RECURRING_COMMITMENT"


class PatternType(str, Enum):
    RECURRING_DELAY_PATTERN = "RECURRING_DELAY_PATTERN"
    RECURRING_BLOCKER_PATTERN = "RECURRING_BLOCKER_PATTERN"
    RECURRING_DEPENDENCY_PATTERN = "RECURRING_DEPENDENCY_PATTERN"
    RECURRING_INTERVENTION_RESPONSE = "RECURRING_INTERVENTION_RESPONSE"
    RECURRING_OBLIGATION_TYPE = "RECURRING_OBLIGATION_TYPE"


class PatternMaturity(str, Enum):
    INSUFFICIENT_HISTORY = "INSUFFICIENT_HISTORY"  # < 3 observations
    EMERGING_PATTERN = "EMERGING_PATTERN"          # 3-9 observations
    ESTABLISHED_PATTERN = "ESTABLISHED_PATTERN"    # 10+ observations


class RecurrenceInterval(str, Enum):
    DAILY = "DAILY"
    WEEKLY = "WEEKLY"
    BIWEEKLY = "BIWEEKLY"
    MONTHLY = "MONTHLY"
    QUARTERLY = "QUARTERLY"
    AD_HOC = "AD_HOC"


# =============================================================================
# PHASE 16: CONTROLLED DECISION EXECUTION & OUTCOME VERIFICATION LAYER ENUMS
# =============================================================================

class ExecutionStatus(str, Enum):
    PENDING_AUTHORIZATION = "PENDING_AUTHORIZATION"
    AUTHORIZED = "AUTHORIZED"
    QUEUED = "QUEUED"
    EXECUTING = "EXECUTING"
    DELIVERED = "DELIVERED"
    DELIVERY_FAILED = "DELIVERY_FAILED"
    RETRY_SCHEDULED = "RETRY_SCHEDULED"
    RESPONSE_PENDING = "RESPONSE_PENDING"
    OUTCOME_DETECTED = "OUTCOME_DETECTED"
    RESOLVED = "RESOLVED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"
    EXPIRED = "EXPIRED"


class ExecutionType(str, Enum):
    INTERVENTION_MESSAGE = "INTERVENTION_MESSAGE"
    DIRECT_NOTIFICATION = "DIRECT_NOTIFICATION"
    STATUS_BROADCAST = "STATUS_BROADCAST"
    CUSTOM_ACTION = "CUSTOM_ACTION"


class ExecutionOutcome(str, Enum):
    ACKNOWLEDGED = "ACKNOWLEDGED"
    PROGRESS_REPORTED = "PROGRESS_REPORTED"
    COMPLETION_SIGNAL = "COMPLETION_SIGNAL"
    NEGATIVE_RESPONSE = "NEGATIVE_RESPONSE"
    NO_RESPONSE = "NO_RESPONSE"
    CONFLICTING_RESPONSE = "CONFLICTING_RESPONSE"
    UNKNOWN = "UNKNOWN"


class ExecutionFailureCode(str, Enum):
    INVALID_RECIPIENT = "INVALID_RECIPIENT"
    PROVIDER_UNAVAILABLE = "PROVIDER_UNAVAILABLE"
    RATE_LIMITED = "RATE_LIMITED"
    AUTHENTICATION_ERROR = "AUTHENTICATION_ERROR"
    PAYLOAD_ERROR = "PAYLOAD_ERROR"
    TIMEOUT = "TIMEOUT"
    UNKNOWN_ERROR = "UNKNOWN_ERROR"


VALID_EXECUTION_TRANSITIONS: Dict[ExecutionStatus, Set[ExecutionStatus]] = {
    ExecutionStatus.PENDING_AUTHORIZATION: {
        ExecutionStatus.AUTHORIZED,
        ExecutionStatus.CANCELLED,
        ExecutionStatus.EXPIRED,
    },
    ExecutionStatus.AUTHORIZED: {
        ExecutionStatus.QUEUED,
        ExecutionStatus.EXECUTING,
        ExecutionStatus.CANCELLED,
        ExecutionStatus.EXPIRED,
    },
    ExecutionStatus.QUEUED: {
        ExecutionStatus.EXECUTING,
        ExecutionStatus.CANCELLED,
        ExecutionStatus.FAILED,
    },
    ExecutionStatus.EXECUTING: {
        ExecutionStatus.DELIVERED,
        ExecutionStatus.DELIVERY_FAILED,
        ExecutionStatus.FAILED,
    },
    ExecutionStatus.DELIVERED: {
        ExecutionStatus.RESPONSE_PENDING,
        ExecutionStatus.OUTCOME_DETECTED,
        ExecutionStatus.RESOLVED,
    },
    ExecutionStatus.DELIVERY_FAILED: {
        ExecutionStatus.RETRY_SCHEDULED,
        ExecutionStatus.FAILED,
    },
    ExecutionStatus.RETRY_SCHEDULED: {
        ExecutionStatus.QUEUED,
        ExecutionStatus.EXECUTING,
        ExecutionStatus.CANCELLED,
        ExecutionStatus.FAILED,
    },
    ExecutionStatus.RESPONSE_PENDING: {
        ExecutionStatus.OUTCOME_DETECTED,
        ExecutionStatus.RESOLVED,
        ExecutionStatus.EXPIRED,
    },
    ExecutionStatus.OUTCOME_DETECTED: {
        ExecutionStatus.RESOLVED,
        ExecutionStatus.FAILED,
    },
    ExecutionStatus.RESOLVED: set(),
    ExecutionStatus.FAILED: {
        ExecutionStatus.RETRY_SCHEDULED,
        ExecutionStatus.EXECUTING,
        ExecutionStatus.QUEUED,
    },
    ExecutionStatus.CANCELLED: set(),
    ExecutionStatus.EXPIRED: set(),
}


class InvalidExecutionStatusTransitionError(Exception):
    def __init__(self, current: ExecutionStatus, target: ExecutionStatus):
        super().__init__(
            f"Invalid execution transition from {current.value} to {target.value}."
        )
        self.current = current
        self.target = target


def validate_execution_transition(current: ExecutionStatus, target: ExecutionStatus) -> bool:
    if current == target:
        return True
    allowed = VALID_EXECUTION_TRANSITIONS.get(current, set())
    if target not in allowed:
        raise InvalidExecutionStatusTransitionError(current, target)
    return True


# =============================================================================
# Phase 17: Continuous Monitoring & Escalation Enums
# =============================================================================

class WatchType(str, Enum):
    DEADLINE = "DEADLINE"
    RISK = "RISK"
    DEPENDENCY = "DEPENDENCY"
    EXECUTION = "EXECUTION"
    RESPONSE = "RESPONSE"
    EVIDENCE = "EVIDENCE"
    DECISION_PLAN = "DECISION_PLAN"
    CRITICAL_PATH = "CRITICAL_PATH"
    BOTTLENECK = "BOTTLENECK"


class WatchStatus(str, Enum):
    ACTIVE = "ACTIVE"
    PAUSED = "PAUSED"
    TRIGGERED = "TRIGGERED"
    RESOLVED = "RESOLVED"
    EXPIRED = "EXPIRED"
    CANCELLED = "CANCELLED"


class MonitoringEventType(str, Enum):
    DEADLINE_APPROACHING = "DEADLINE_APPROACHING"
    DEADLINE_BREACHED = "DEADLINE_BREACHED"
    RISK_ESCALATED = "RISK_ESCALATED"
    RISK_DEESCALATED = "RISK_DEESCALATED"
    DEPENDENCY_BLOCKED = "DEPENDENCY_BLOCKED"
    DEPENDENCY_RESOLVED = "DEPENDENCY_RESOLVED"
    NEW_COMPLETION_EVIDENCE = "NEW_COMPLETION_EVIDENCE"
    NEW_NEGATIVE_SIGNAL = "NEW_NEGATIVE_SIGNAL"
    OWNER_UNRESPONSIVE = "OWNER_UNRESPONSIVE"
    EXECUTION_FAILED = "EXECUTION_FAILED"
    EXECUTION_STALLED = "EXECUTION_STALLED"
    EXECUTION_RESPONSE_TIMEOUT = "EXECUTION_RESPONSE_TIMEOUT"
    DECISION_PLAN_STALE = "DECISION_PLAN_STALE"
    DECISION_PLAN_RESOLVED = "DECISION_PLAN_RESOLVED"
    CRITICAL_PATH_CHANGED = "CRITICAL_PATH_CHANGED"
    SYSTEMIC_BOTTLENECK_DETECTED = "SYSTEMIC_BOTTLENECK_DETECTED"


class MonitoringSeverity(str, Enum):
    INFO = "INFO"
    NOTICE = "NOTICE"
    WARNING = "WARNING"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class EscalationStatus(str, Enum):
    OPEN = "OPEN"
    ACKNOWLEDGED = "ACKNOWLEDGED"
    RESOLVED = "RESOLVED"
    DISMISSED = "DISMISSED"
    EXPIRED = "EXPIRED"


class MonitoringRunStatus(str, Enum):
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    PARTIAL = "PARTIAL"
    FAILED = "FAILED"


class TargetType(str, Enum):
    OBLIGATION = "OBLIGATION"
    EXECUTION = "EXECUTION"
    DECISION_PLAN = "DECISION_PLAN"
    INTERVENTION = "INTERVENTION"
    WORKSPACE = "WORKSPACE"
