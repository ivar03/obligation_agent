"""
Phase 19 Request Correlation & Context Management.

Provides request_id correlation, client IP, User-Agent, and request timing
across asynchronous coroutines and audit services.

The middleware emits a structured access log for every HTTP request,
including duration_ms, status_code, and route — all credential-free.
"""

import uuid
import re
import time
from typing import Optional, Callable
from contextvars import ContextVar
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

# Context variables propagated through the async call chain
request_id_ctx: ContextVar[Optional[str]] = ContextVar("request_id", default=None)
client_ip_ctx: ContextVar[Optional[str]] = ContextVar("client_ip", default=None)
user_agent_ctx: ContextVar[Optional[str]] = ContextVar("user_agent", default=None)
request_start_ctx: ContextVar[Optional[float]] = ContextVar("request_start", default=None)


def sanitize_request_id(raw_id: Optional[str]) -> str:
    """
    Validates and sanitizes a client-provided correlation ID.
    If invalid or empty, generates a secure UUID.
    """
    if raw_id:
        cleaned = re.sub(r"[^a-zA-Z0-9\-_]", "", raw_id.strip())
        if 4 <= len(cleaned) <= 64:
            return cleaned
    return str(uuid.uuid4())


def get_current_request_id() -> str:
    """
    Returns the active request correlation ID.
    Generates a one-shot UUID if called outside the request lifecycle.
    """
    req_id = request_id_ctx.get()
    if not req_id:
        return str(uuid.uuid4())
    return req_id


def get_current_client_ip() -> Optional[str]:
    return client_ip_ctx.get()


def get_current_user_agent() -> Optional[str]:
    return user_agent_ctx.get()


def get_request_duration_ms() -> Optional[float]:
    """Returns elapsed time in ms since the request started, or None if unavailable."""
    start = request_start_ctx.get()
    if start is not None:
        return round((time.perf_counter() - start) * 1000, 2)
    return None


class RequestContextMiddleware(BaseHTTPMiddleware):
    """
    FastAPI / Starlette middleware that:
      1. Extracts or generates a request correlation ID (X-Request-Id)
      2. Extracts client IP (respects X-Forwarded-For from reverse proxy)
      3. Records request start time for duration measurement
      4. Emits structured access log on response
      5. Propagates X-Request-Id response header

    Does NOT log Authorization headers, tokens, or sensitive body content.
    """

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        start = time.perf_counter()

        # Extract or generate request correlation ID
        incoming_req_id = (
            request.headers.get("X-Request-Id")
            or request.headers.get("X-Correlation-Id")
        )
        req_id = sanitize_request_id(incoming_req_id)
        token_req = request_id_ctx.set(req_id)
        token_start = request_start_ctx.set(start)

        # Extract client IP
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            client_ip = forwarded_for.split(",")[0].strip()
        elif request.client:
            client_ip = request.client.host
        else:
            client_ip = None
        token_ip = client_ip_ctx.set(client_ip)

        # Extract User-Agent (safe to log — no secrets)
        ua = request.headers.get("User-Agent")
        token_ua = user_agent_ctx.set(ua)

        try:
            response = await call_next(request)
            duration_ms = round((time.perf_counter() - start) * 1000, 2)
            response.headers["X-Request-Id"] = req_id

            # Emit structured access log (credential-free)
            _emit_access_log(request, response.status_code, duration_ms, req_id)

            # Update metrics
            try:
                from app.core.metrics import metrics
                route = request.url.path
                labels = {"route": _normalize_route(route)}
                metrics.increment("api.requests", labels=labels)
                metrics.record_duration("api.latency_ms", duration_ms, labels=labels)
                if response.status_code >= 400:
                    metrics.increment("api.errors", labels=labels)
            except Exception:
                pass

            return response
        except Exception as exc:
            duration_ms = round((time.perf_counter() - start) * 1000, 2)
            _emit_access_log(request, 500, duration_ms, req_id)
            raise
        finally:
            request_id_ctx.reset(token_req)
            request_start_ctx.reset(token_start)
            client_ip_ctx.reset(token_ip)
            user_agent_ctx.reset(token_ua)


def _emit_access_log(request: Request, status_code: int, duration_ms: float, req_id: str):
    """Emit a structured access log entry (never includes credentials)."""
    try:
        import logging
        log = logging.getLogger("obligation_agent.access")
        level = logging.WARNING if status_code >= 500 else (
            logging.INFO if status_code < 400 else logging.WARNING
        )
        log.log(
            level,
            f"{request.method} {request.url.path} → {status_code}",
            extra={
                "request_id": req_id,
                "method": request.method,
                "route": request.url.path,
                "status": status_code,
                "duration_ms": duration_ms,
            },
        )
    except Exception:
        pass


def _normalize_route(path: str) -> str:
    """Normalize route path by replacing UUIDs/IDs with placeholders for metric grouping."""
    import re
    # Replace UUID-like segments
    path = re.sub(r"/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", "/{id}", path)
    # Replace numeric IDs
    path = re.sub(r"/\d+", "/{id}", path)
    return path
