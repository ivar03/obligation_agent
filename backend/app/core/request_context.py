"""
Request Correlation & Context Management.
Provides request_id correlation, client IP, and User-Agent tracking
across asynchronous coroutines and audit services.
"""

import uuid
import re
from typing import Optional, Callable
from contextvars import ContextVar
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

request_id_ctx: ContextVar[Optional[str]] = ContextVar("request_id", default=None)
client_ip_ctx: ContextVar[Optional[str]] = ContextVar("client_ip", default=None)
user_agent_ctx: ContextVar[Optional[str]] = ContextVar("user_agent", default=None)


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
    Returns the active request correlation ID, or generates a local one if outside request lifecycle.
    """
    req_id = request_id_ctx.get()
    if not req_id:
        return str(uuid.uuid4())
    return req_id


def get_current_client_ip() -> Optional[str]:
    return client_ip_ctx.get()


def get_current_user_agent() -> Optional[str]:
    return user_agent_ctx.get()


class RequestContextMiddleware(BaseHTTPMiddleware):
    """
    FastAPI / Starlette middleware extracting client IP, User-Agent, and propagating X-Request-Id.
    """
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Extract or generate request correlation ID
        incoming_req_id = (
            request.headers.get("X-Request-Id")
            or request.headers.get("X-Correlation-Id")
        )
        req_id = sanitize_request_id(incoming_req_id)
        token_req = request_id_ctx.set(req_id)

        # Extract client IP
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            client_ip = forwarded_for.split(",")[0].strip()
        elif request.client:
            client_ip = request.client.host
        else:
            client_ip = None
        token_ip = client_ip_ctx.set(client_ip)

        # Extract User-Agent
        ua = request.headers.get("User-Agent")
        token_ua = user_agent_ctx.set(ua)

        try:
            response = await call_next(request)
            response.headers["X-Request-Id"] = req_id
            return response
        finally:
            request_id_ctx.reset(token_req)
            client_ip_ctx.reset(token_ip)
            user_agent_ctx.reset(token_ua)
