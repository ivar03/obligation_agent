"""
Phase 20 LLM Rate Limiter & Cost Control.

Enforces workspace-level rate limits (requests per minute and per day)
to prevent event storm overconsumption and quota exhaustion.
"""

import time
from collections import deque
from typing import Dict
from app.core.config import settings


class LLMRateLimiter:
    """In-memory sliding window rate limiter for LLM invocations."""

    _minute_windows: Dict[str, deque] = {}
    _daily_counts: Dict[str, int] = {}
    _daily_reset_time: Dict[str, float] = {}

    @classmethod
    def check_and_record(cls, workspace_id: str = "ws-default") -> bool:
        """
        Returns True if request is allowed within rate limits; False otherwise.
        """
        now = time.time()
        max_per_min = settings.LLM_MAX_REQUESTS_PER_MINUTE
        max_per_day = settings.LLM_MAX_DAILY_REQUESTS

        # 1. Check minute window
        if workspace_id not in cls._minute_windows:
            cls._minute_windows[workspace_id] = deque()

        window = cls._minute_windows[workspace_id]
        while window and window[0] < now - 60.0:
            window.popleft()

        if len(window) >= max_per_min:
            return False

        # 2. Check daily limit
        reset_time = cls._daily_reset_time.get(workspace_id, 0.0)
        if now > reset_time:
            cls._daily_counts[workspace_id] = 0
            cls._daily_reset_time[workspace_id] = now + 86400.0

        if cls._daily_counts.get(workspace_id, 0) >= max_per_day:
            return False

        # Record usage
        window.append(now)
        cls._daily_counts[workspace_id] = cls._daily_counts.get(workspace_id, 0) + 1
        return True

    @classmethod
    def reset(cls):
        """Clears rate limit windows for test isolation."""
        cls._minute_windows.clear()
        cls._daily_counts.clear()
        cls._daily_reset_time.clear()
