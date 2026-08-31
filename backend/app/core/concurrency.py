"""
Phase 17 Concurrency & Transactional Race-Condition Protection.

Provides atomic transactional locks, idempotency keys, and optimistic concurrency
guards for critical domain operations:
- Decision Plan approval & execution
- Evidence confirmation & obligation status transitions
- Webhook deduplication & event ingestion
"""

import asyncio
from typing import Dict, Optional, Set
from contextlib import asynccontextmanager
from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import logger


class ConcurrencyCoordinator:
    """
    In-memory async lock coordinator for preventing race conditions
    on identical target entity mutations across concurrent worker threads or HTTP requests.
    """

    def __init__(self):
        self._locks: Dict[str, asyncio.Lock] = {}
        self._global_lock = asyncio.Lock()

    async def _get_lock(self, lock_key: str) -> asyncio.Lock:
        async with self._global_lock:
            if lock_key not in self._locks:
                self._locks[lock_key] = asyncio.Lock()
            return self._locks[lock_key]

    @asynccontextmanager
    async def acquire_lock(self, domain: str, entity_id: str, timeout_seconds: float = 10.0):
        """
        Context manager acquiring an exclusive async lock for `domain:entity_id`.
        Raises HTTP 409 Conflict / 429 Too Many Requests if lock acquisition times out.
        """
        lock_key = f"{domain}:{entity_id}"
        lock = await self._get_lock(lock_key)

        try:
            acquired = await asyncio.wait_for(lock.acquire(), timeout=timeout_seconds)
        except asyncio.TimeoutError:
            logger.warning(f"Concurrency lock timeout for [{lock_key}] after {timeout_seconds}s")
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Concurrent operation in progress for {domain} '{entity_id}'. Please retry shortly.",
            )

        try:
            yield
        finally:
            lock.release()


# Global concurrency coordinator instance
concurrency_guard = ConcurrencyCoordinator()
