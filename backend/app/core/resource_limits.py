"""
Phase 19 Resource Protection Hard Limits.

Enforces configurable upper bounds on all expensive operations to prevent
pathological workspaces or malicious payloads from exhausting the service.

Usage:
    from app.core.resource_limits import ResourceLimits
    ResourceLimits.check_csv_size(file_bytes)        # raises PayloadTooLargeError
    ResourceLimits.check_graph_depth(depth)          # raises ObligationAgentError
    ResourceLimits.check_graph_nodes(node_count)
    ResourceLimits.check_search_result_count(n)
"""

from app.core.config import settings
from app.core.errors import (
    ObligationAgentError,
    PayloadTooLargeError,
    ValidationError,
    ErrorCode,
)


class ResourceLimits:
    """Static enforcement methods for all configurable resource limits."""

    # ------------------------------------------------------------------
    # Payload / upload size limits
    # ------------------------------------------------------------------

    @staticmethod
    def check_request_body(byte_count: int) -> None:
        limit = settings.MAX_REQUEST_BODY_BYTES
        if byte_count > limit:
            raise PayloadTooLargeError(limit_bytes=limit)

    @staticmethod
    def check_webhook_payload(byte_count: int) -> None:
        limit = settings.MAX_WEBHOOK_PAYLOAD_BYTES
        if byte_count > limit:
            raise PayloadTooLargeError(limit_bytes=limit, code=ErrorCode.WEBHOOK_PAYLOAD_TOO_LARGE)

    @staticmethod
    def check_csv_size(byte_count: int) -> None:
        limit = settings.MAX_CSV_FILE_BYTES
        if byte_count > limit:
            raise PayloadTooLargeError(limit_bytes=limit, code=ErrorCode.CSV_TOO_LARGE)

    @staticmethod
    def check_csv_row_count(row_count: int) -> None:
        limit = settings.MAX_CSV_ROWS
        if row_count > limit:
            raise ObligationAgentError(
                code=ErrorCode.CSV_ROW_LIMIT_EXCEEDED,
                message=f"CSV exceeds the maximum row limit of {limit:,} rows.",
            )

    # ------------------------------------------------------------------
    # Search
    # ------------------------------------------------------------------

    @staticmethod
    def check_search_result_count(requested: int) -> int:
        """Clamp search result count to the configured maximum."""
        return min(requested, settings.MAX_SEARCH_RESULTS)

    # ------------------------------------------------------------------
    # Graph / dependency traversal
    # ------------------------------------------------------------------

    @staticmethod
    def check_graph_depth(depth: int) -> None:
        limit = settings.MAX_GRAPH_DEPTH
        if depth > limit:
            raise ObligationAgentError(
                code=ErrorCode.GRAPH_DEPTH_EXCEEDED,
                message=f"Graph traversal depth {depth} exceeds the limit of {limit}.",
            )

    @staticmethod
    def check_graph_nodes(node_count: int) -> None:
        limit = settings.MAX_GRAPH_NODES
        if node_count > limit:
            raise ObligationAgentError(
                code=ErrorCode.GRAPH_SIZE_EXCEEDED,
                message=f"Graph size {node_count:,} nodes exceeds the limit of {limit:,}.",
            )

    # ------------------------------------------------------------------
    # Intelligence / Simulation
    # ------------------------------------------------------------------

    @staticmethod
    def check_simulation_scenarios(count: int) -> None:
        limit = settings.MAX_SIMULATION_SCENARIOS
        if count > limit:
            raise ObligationAgentError(
                code=ErrorCode.RESOURCE_LIMIT_EXCEEDED,
                message=f"Simulation scenario count {count} exceeds the limit of {limit}.",
            )

    # ------------------------------------------------------------------
    # Event batching
    # ------------------------------------------------------------------

    @staticmethod
    def check_event_batch_size(count: int) -> None:
        limit = settings.MAX_EVENT_BATCH_SIZE
        if count > limit:
            raise ObligationAgentError(
                code=ErrorCode.RESOURCE_LIMIT_EXCEEDED,
                message=f"Event batch size {count} exceeds the limit of {limit}.",
            )
