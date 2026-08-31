"""
Phase 19 Test Suite: Unified Error Model.
Tests structured error responses, stable error codes, and HTTP exception conversions.
"""

import pytest
from app.core.errors import (
    ErrorCode,
    ObligationAgentError,
    NotFoundError,
    AuthorizationError,
    RateLimitError,
    make_error_response,
)


def test_obligation_agent_error_response():
    err = ObligationAgentError(
        code=ErrorCode.DECISION_PLAN_STALE,
        message="Decision plan is no longer valid.",
        http_status=400,
    )
    resp = err.to_response()
    assert resp.status_code == 400
    
    import json
    body = json.loads(resp.body.decode("utf-8"))
    assert "error" in body
    assert body["error"]["code"] == ErrorCode.DECISION_PLAN_STALE
    assert body["error"]["message"] == "Decision plan is no longer valid."
    assert "request_id" in body["error"]


def test_typed_error_classes():
    nf = NotFoundError("Workspace")
    assert nf.http_status == 404
    assert nf.code == ErrorCode.NOT_FOUND

    auth_err = AuthorizationError("Admin access required.")
    assert auth_err.http_status == 403
    assert auth_err.code == ErrorCode.FORBIDDEN

    rl_err = RateLimitError(retry_after=45)
    assert rl_err.http_status == 429
    assert rl_err.code == ErrorCode.RATE_LIMIT_EXCEEDED
    assert rl_err.retry_after == 45
