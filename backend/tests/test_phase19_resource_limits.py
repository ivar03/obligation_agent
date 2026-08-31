"""
Phase 19 Test Suite: Resource Protection Hard Limits.
Tests payload size bounds, CSV limits, graph depth bounds, and batch size enforcement.
"""

import pytest
from app.core.resource_limits import ResourceLimits
from app.core.errors import PayloadTooLargeError, ObligationAgentError


def test_resource_limits_payload_checks():
    # Below limit passes
    ResourceLimits.check_request_body(1024)
    ResourceLimits.check_webhook_payload(500)

    # Exceeding payload limit raises PayloadTooLargeError
    with pytest.raises(PayloadTooLargeError):
        ResourceLimits.check_request_body(50 * 1024 * 1024)  # 50 MB > 10 MB limit


def test_resource_limits_csv_checks():
    ResourceLimits.check_csv_size(1024)
    ResourceLimits.check_csv_row_count(500)

    with pytest.raises(PayloadTooLargeError):
        ResourceLimits.check_csv_size(20 * 1024 * 1024)  # 20 MB > 5 MB limit

    with pytest.raises(ObligationAgentError):
        ResourceLimits.check_csv_row_count(25_000)  # > 10,000 limit


def test_resource_limits_graph_and_search():
    # Clamps search results
    clamped = ResourceLimits.check_search_result_count(500)
    assert clamped <= 200

    # Depth checks
    ResourceLimits.check_graph_depth(10)
    with pytest.raises(ObligationAgentError):
        ResourceLimits.check_graph_depth(100)  # > 50 limit
