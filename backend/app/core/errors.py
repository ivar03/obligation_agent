"""
Phase 19 Unified Error Model.

All API errors are returned as:
    {"error": {"code": "<STABLE_CODE>", "message": "<safe message>", "request_id": "..."}}

Stable machine-readable codes ensure clients can handle errors programmatically
without parsing human-readable messages.

Usage:
    raise ObligationAgentError("DECISION_PLAN_STALE", "The plan is no longer current.")
    raise NotFoundError("Workspace")
    raise AuthorizationError("Insufficient permissions.")
"""

from fastapi import status
from fastapi.responses import JSONResponse

from app.core.request_context import get_current_request_id


# ---------------------------------------------------------------------------
# Error Codes (stable, machine-readable)
# ---------------------------------------------------------------------------

class ErrorCode:
    # Authentication / Authorization
    UNAUTHORIZED = "UNAUTHORIZED"
    FORBIDDEN = "FORBIDDEN"
    TOKEN_EXPIRED = "TOKEN_EXPIRED"
    TOKEN_INVALID = "TOKEN_INVALID"
    SESSION_REVOKED = "SESSION_REVOKED"
    WORKSPACE_ACCESS_DENIED = "WORKSPACE_ACCESS_DENIED"

    # Resources
    NOT_FOUND = "NOT_FOUND"
    ALREADY_EXISTS = "ALREADY_EXISTS"
    CONFLICT = "CONFLICT"

    # Obligation lifecycle
    OBLIGATION_NOT_FOUND = "OBLIGATION_NOT_FOUND"
    OBLIGATION_INVALID_TRANSITION = "OBLIGATION_INVALID_TRANSITION"
    OBLIGATION_ALREADY_COMPLETE = "OBLIGATION_ALREADY_COMPLETE"
    OBLIGATION_BLOCKED = "OBLIGATION_BLOCKED"

    # Decision Plan
    DECISION_PLAN_NOT_FOUND = "DECISION_PLAN_NOT_FOUND"
    DECISION_PLAN_STALE = "DECISION_PLAN_STALE"
    DECISION_PLAN_ALREADY_APPROVED = "DECISION_PLAN_ALREADY_APPROVED"
    DECISION_PLAN_REJECTED = "DECISION_PLAN_REJECTED"
    DECISION_PLAN_INVALID_STATE = "DECISION_PLAN_INVALID_STATE"

    # Evidence
    EVIDENCE_NOT_FOUND = "EVIDENCE_NOT_FOUND"
    EVIDENCE_ALREADY_CONFIRMED = "EVIDENCE_ALREADY_CONFIRMED"
    EVIDENCE_CONFIRMATION_UNAUTHORIZED = "EVIDENCE_CONFIRMATION_UNAUTHORIZED"

    # Execution
    EXECUTION_NOT_FOUND = "EXECUTION_NOT_FOUND"
    EXECUTION_ALREADY_DISPATCHED = "EXECUTION_ALREADY_DISPATCHED"
    EXECUTION_AUTHORIZATION_REQUIRED = "EXECUTION_AUTHORIZATION_REQUIRED"
    EXECUTION_PROVIDER_FAILED = "EXECUTION_PROVIDER_FAILED"

    # Workers / Jobs
    JOB_NOT_FOUND = "JOB_NOT_FOUND"
    JOB_DEAD_LETTER = "JOB_DEAD_LETTER"
    QUEUE_FULL = "QUEUE_FULL"

    # Webhooks
    WEBHOOK_INVALID_SIGNATURE = "WEBHOOK_INVALID_SIGNATURE"
    WEBHOOK_STALE_TIMESTAMP = "WEBHOOK_STALE_TIMESTAMP"
    WEBHOOK_DUPLICATE_EVENT = "WEBHOOK_DUPLICATE_EVENT"
    WEBHOOK_PAYLOAD_TOO_LARGE = "WEBHOOK_PAYLOAD_TOO_LARGE"
    WEBHOOK_MALFORMED = "WEBHOOK_MALFORMED"

    # Provider
    PROVIDER_UNAVAILABLE = "PROVIDER_UNAVAILABLE"
    PROVIDER_RATE_LIMITED = "PROVIDER_RATE_LIMITED"
    PROVIDER_AUTH_FAILED = "PROVIDER_AUTH_FAILED"
    PROVIDER_TIMEOUT = "PROVIDER_TIMEOUT"
    CIRCUIT_OPEN = "CIRCUIT_OPEN"

    # Imports
    CSV_TOO_LARGE = "CSV_TOO_LARGE"
    CSV_ROW_LIMIT_EXCEEDED = "CSV_ROW_LIMIT_EXCEEDED"
    CSV_VALIDATION_FAILED = "CSV_VALIDATION_FAILED"

    # Validation / Input
    VALIDATION_ERROR = "VALIDATION_ERROR"
    PAYLOAD_TOO_LARGE = "PAYLOAD_TOO_LARGE"
    MALFORMED_JSON = "MALFORMED_JSON"
    RESOURCE_LIMIT_EXCEEDED = "RESOURCE_LIMIT_EXCEEDED"

    # Rate limiting
    RATE_LIMIT_EXCEEDED = "RATE_LIMIT_EXCEEDED"

    # Graph
    GRAPH_CYCLE_DETECTED = "GRAPH_CYCLE_DETECTED"
    GRAPH_DEPTH_EXCEEDED = "GRAPH_DEPTH_EXCEEDED"
    GRAPH_SIZE_EXCEEDED = "GRAPH_SIZE_EXCEEDED"

    # Internal
    INTERNAL_ERROR = "INTERNAL_ERROR"
    DATABASE_ERROR = "DATABASE_ERROR"
    CONFIGURATION_ERROR = "CONFIGURATION_ERROR"

    # Workspace
    WORKSPACE_NOT_FOUND = "WORKSPACE_NOT_FOUND"
    WORKSPACE_LIMIT_EXCEEDED = "WORKSPACE_LIMIT_EXCEEDED"
    INVITATION_NOT_FOUND = "INVITATION_NOT_FOUND"
    INVITATION_EXPIRED = "INVITATION_EXPIRED"
    INVITATION_ALREADY_USED = "INVITATION_ALREADY_USED"


# ---------------------------------------------------------------------------
# Exception Classes
# ---------------------------------------------------------------------------

class ObligationAgentError(Exception):
    """
    Base exception for all structured API errors.
    Carry a stable error code, a safe user-facing message, and an HTTP status.
    """

    def __init__(
        self,
        code: str,
        message: str,
        http_status: int = status.HTTP_400_BAD_REQUEST,
    ):
        self.code = code
        self.message = message
        self.http_status = http_status
        super().__init__(message)

    def to_response(self) -> JSONResponse:
        return JSONResponse(
            status_code=self.http_status,
            content={
                "error": {
                    "code": self.code,
                    "message": self.message,
                    "request_id": get_current_request_id(),
                }
            },
        )


class NotFoundError(ObligationAgentError):
    def __init__(self, resource: str, code: str = ErrorCode.NOT_FOUND):
        super().__init__(
            code=code,
            message=f"{resource} not found.",
            http_status=status.HTTP_404_NOT_FOUND,
        )


class AuthorizationError(ObligationAgentError):
    def __init__(self, message: str = "Insufficient permissions."):
        super().__init__(
            code=ErrorCode.FORBIDDEN,
            message=message,
            http_status=status.HTTP_403_FORBIDDEN,
        )


class AuthenticationError(ObligationAgentError):
    def __init__(self, message: str = "Authentication required.", code: str = ErrorCode.UNAUTHORIZED):
        super().__init__(
            code=code,
            message=message,
            http_status=status.HTTP_401_UNAUTHORIZED,
        )


class ValidationError(ObligationAgentError):
    def __init__(self, message: str, code: str = ErrorCode.VALIDATION_ERROR):
        super().__init__(
            code=code,
            message=message,
            http_status=status.HTTP_422_UNPROCESSABLE_ENTITY,
        )


class ConflictError(ObligationAgentError):
    def __init__(self, message: str, code: str = ErrorCode.CONFLICT):
        super().__init__(
            code=code,
            message=message,
            http_status=status.HTTP_409_CONFLICT,
        )


class RateLimitError(ObligationAgentError):
    def __init__(self, retry_after: int = 60):
        super().__init__(
            code=ErrorCode.RATE_LIMIT_EXCEEDED,
            message=f"Rate limit exceeded. Try again in {retry_after} seconds.",
            http_status=status.HTTP_429_TOO_MANY_REQUESTS,
        )
        self.retry_after = retry_after


class PayloadTooLargeError(ObligationAgentError):
    def __init__(self, limit_bytes: int, code: str = ErrorCode.PAYLOAD_TOO_LARGE):
        mb = limit_bytes // (1024 * 1024)
        super().__init__(
            code=code,
            message=f"Request payload exceeds the maximum allowed size ({mb} MB).",
            http_status=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
        )


class ProviderError(ObligationAgentError):
    def __init__(self, provider: str, message: str, code: str = ErrorCode.PROVIDER_UNAVAILABLE):
        super().__init__(
            code=code,
            message=f"Provider '{provider}' error: {message}",
            http_status=status.HTTP_502_BAD_GATEWAY,
        )


class CircuitOpenError(ObligationAgentError):
    def __init__(self, provider: str):
        super().__init__(
            code=ErrorCode.CIRCUIT_OPEN,
            message=f"Provider '{provider}' is temporarily unavailable. Circuit breaker is open.",
            http_status=status.HTTP_503_SERVICE_UNAVAILABLE,
        )


class InternalError(ObligationAgentError):
    def __init__(self, message: str = "An internal error occurred."):
        super().__init__(
            code=ErrorCode.INTERNAL_ERROR,
            message=message,
            http_status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


# ---------------------------------------------------------------------------
# Structured error response builder (for use in exception handlers)
# ---------------------------------------------------------------------------

def make_error_response(
    code: str,
    message: str,
    http_status: int,
    request_id: str = None,
) -> JSONResponse:
    """Build a structured error JSONResponse without raising an exception."""
    return JSONResponse(
        status_code=http_status,
        content={
            "error": {
                "code": code,
                "message": message,
                "request_id": request_id or get_current_request_id(),
            }
        },
    )
