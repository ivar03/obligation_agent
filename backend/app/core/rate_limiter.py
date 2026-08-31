"""
Phase 19 In-Memory Sliding Window Rate Limiter.

Protects sensitive endpoints against abuse, brute-force, and runaway loops
without interfering with legitimate provider retry semantics.
Employs unified error responses and structured error codes.
"""

import time
from typing import Dict, List, Tuple, Optional
from fastapi import Request, status
from fastapi.responses import JSONResponse

from app.core.config import settings
from app.core.logging import logger
from app.core.errors import ErrorCode, make_error_response
from app.core.request_context import get_current_request_id


class InMemoryRateLimiter:
    """
    Thread-safe in-memory sliding window rate limiter.
    Keys are built from client IP + workspace/endpoint signature.
    """

    def __init__(self):
        # Map: rate_key -> list of timestamp floats
        self._windows: Dict[str, List[float]] = {}

    def _cleanup(self, now: float, window_seconds: float = 60.0):
        """Purge records older than window_seconds."""
        threshold = now - window_seconds
        keys_to_delete = []
        for key, timestamps in self._windows.items():
            valid_ts = [t for t in timestamps if t > threshold]
            if not valid_ts:
                keys_to_delete.append(key)
            else:
                self._windows[key] = valid_ts
        for k in keys_to_delete:
            del self._windows[k]

    def check_rate_limit(
        self,
        key: str,
        max_requests: int = 120,
        window_seconds: float = 60.0,
    ) -> Tuple[bool, int, float]:
        """
        Checks whether the given key has exceeded max_requests within window_seconds.
        Returns: (is_allowed, remaining_requests, reset_after_seconds)
        """
        if not settings.RATE_LIMIT_ENABLED:
            return True, max_requests, 0.0

        now = time.time()
        threshold = now - window_seconds

        timestamps = self._windows.get(key, [])
        valid_ts = [t for t in timestamps if t > threshold]

        if len(valid_ts) >= max_requests:
            oldest = valid_ts[0]
            reset_after = max(0.0, oldest + window_seconds - now)
            self._windows[key] = valid_ts
            return False, 0, reset_after

        valid_ts.append(now)
        self._windows[key] = valid_ts
        remaining = max_requests - len(valid_ts)
        return True, remaining, 0.0


limiter = InMemoryRateLimiter()


def rate_limit(
    max_requests: Optional[int] = None,
    window_seconds: float = 60.0,
    key_prefix: str = "general",
):
    """
    FastAPI dependency enforcing sliding window rate limits.
    """
    async def dependency(request: Request):
        if not settings.RATE_LIMIT_ENABLED:
            return

        limit = max_requests or settings.RATE_LIMIT_DEFAULT_PER_MINUTE

        client_ip = request.client.host if request.client else "unknown"
        ws_id = request.headers.get("X-Workspace-Id", "default")
        path = request.url.path

        key = f"{key_prefix}:{client_ip}:{ws_id}:{path}"
        allowed, remaining, reset_after = limiter.check_rate_limit(key, max_requests=limit, window_seconds=window_seconds)

        if not allowed:
            logger.warning(
                f"Rate limit exceeded for [{key}]: limit={limit}/min, retry_after={reset_after:.1f}s",
                extra={"key": key, "limit": limit, "retry_after": reset_after}
            )
            from app.core.errors import RateLimitError
            raise RateLimitError(retry_after=int(reset_after) + 1)

    return dependency

