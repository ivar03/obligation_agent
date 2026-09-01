"""
Phase 21 Distributed Trace Context & Span Management.

Provides trace context utilities, span decorators, and correlation propagators
across synchronous and asynchronous execution units.
"""

import time
import functools
import inspect
from typing import Optional, Dict, Any, Callable, TypeVar, Coroutine
from app.core.request_context import (
    get_current_trace_id,
    get_current_span_id,
    generate_span_id,
    set_trace_context,
    span_id_ctx,
)

F = TypeVar("F", bound=Callable[..., Any])


class TraceSpan:
    """Represents an active in-memory trace span context manager."""

    def __init__(self, span_name: str, component: str = "app", attributes: Optional[Dict[str, Any]] = None):
        self.span_name = span_name
        self.component = component
        self.attributes = attributes or {}
        self.span_id = generate_span_id()
        self.parent_span_id: Optional[str] = None
        self.trace_id = get_current_trace_id()
        self.start_time: float = 0.0
        self.duration_ms: float = 0.0
        self._token = None

    def __enter__(self):
        self.parent_span_id = get_current_span_id()
        self._token = span_id_ctx.set(self.span_id)
        self.start_time = time.perf_counter()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.duration_ms = round((time.perf_counter() - self.start_time) * 1000, 2)
        if self._token:
            span_id_ctx.reset(self._token)
        return False

    async def __aenter__(self):
        return self.__enter__()

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        return self.__exit__(exc_type, exc_val, exc_tb)


def traced_span(span_name: str, component: str = "app", attributes: Optional[Dict[str, Any]] = None):
    """
    Decorator for tracing sync and async functions as named trace spans.
    """
    def decorator(func: F) -> F:
        if inspect.iscoroutinefunction(func):
            @functools.wraps(func)
            async def async_wrapper(*args, **kwargs):
                async with TraceSpan(span_name=span_name, component=component, attributes=attributes):
                    return await func(*args, **kwargs)
            return async_wrapper  # type: ignore
        else:
            @functools.wraps(func)
            def sync_wrapper(*args, **kwargs):
                with TraceSpan(span_name=span_name, component=component, attributes=attributes):
                    return func(*args, **kwargs)
            return sync_wrapper  # type: ignore
    return decorator
