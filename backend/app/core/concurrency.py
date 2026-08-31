"""
Phase 19 Distributed Concurrency Safety.

Upgrades the in-process asyncio lock coordinator to use database-level
row locking for safety across multiple API instances.

Strategy:
  - PostgreSQL: pg_try_advisory_xact_lock(hashtext(key)) — zero-wait advisory lock
  - SQLite (dev/test): falls back to in-process asyncio lock (single process only)

All critical state transitions use database-level uniqueness constraints as
the ultimate idempotency guarantee, with this coordinator as an additional
early-exit optimisation.

Usage:
    async with concurrency_guard.acquire_lock("decision_plan", plan_id, session):
        # DB-level exclusive lock held; safe to mutate
        ...
"""

import asyncio
import hashlib
from typing import Dict, Optional
from contextlib import asynccontextmanager
from fastapi import HTTPException, status
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger("obligation_agent.concurrency")


class ConcurrencyCoordinator:
    """
    Hybrid concurrency coordinator:
      - PostgreSQL: uses pg_try_advisory_xact_lock for distributed safety
      - SQLite: in-process asyncio.Lock (acceptable for single-instance dev)
    """

    def __init__(self):
        # Fallback in-process locks (SQLite / single-process)
        self._locks: Dict[str, asyncio.Lock] = {}
        self._global_lock = asyncio.Lock()

    async def _get_async_lock(self, lock_key: str) -> asyncio.Lock:
        async with self._global_lock:
            if lock_key not in self._locks:
                self._locks[lock_key] = asyncio.Lock()
            return self._locks[lock_key]

    @staticmethod
    def _pg_lock_key(domain: str, entity_id: str) -> int:
        """Convert a string key to a 64-bit integer for pg_try_advisory_xact_lock."""
        digest = hashlib.sha256(f"{domain}:{entity_id}".encode()).digest()
        # Use first 8 bytes as a signed 64-bit integer
        raw = int.from_bytes(digest[:8], byteorder="big", signed=True)
        return raw

    @asynccontextmanager
    async def acquire_lock(
        self,
        domain: str,
        entity_id: str,
        session: Optional[AsyncSession] = None,
        timeout_seconds: float = 10.0,
    ):
        """
        Acquire an exclusive lock for domain:entity_id.

        If a database session is provided and the backend is PostgreSQL,
        uses pg_try_advisory_xact_lock (released automatically at transaction end).
        Otherwise falls back to an in-process asyncio.Lock with timeout.

        Raises HTTP 409 Conflict if the lock cannot be acquired.
        """
        lock_key = f"{domain}:{entity_id}"

        if session is not None and settings.is_postgres():
            await self._acquire_pg_lock(lock_key, domain, entity_id, session)
            try:
                yield
            finally:
                pass  # PG advisory locks release automatically at transaction end
        else:
            await self._acquire_async_lock(lock_key, domain, entity_id, timeout_seconds)
            lock = await self._get_async_lock(lock_key)
            try:
                yield
            finally:
                try:
                    lock.release()
                except RuntimeError:
                    pass

    async def _acquire_pg_lock(
        self, lock_key: str, domain: str, entity_id: str, session: AsyncSession
    ):
        pg_key = self._pg_lock_key(domain, entity_id)
        result = await session.execute(
            text("SELECT pg_try_advisory_xact_lock(:key)"),
            {"key": pg_key},
        )
        acquired = result.scalar()
        if not acquired:
            logger.warning(
                f"PostgreSQL advisory lock contention",
                extra={"lock_key": lock_key, "pg_key": pg_key},
            )
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={
                    "error": {
                        "code": "CONFLICT",
                        "message": f"Concurrent operation in progress for {domain} '{entity_id}'. Please retry.",
                    }
                },
            )

    async def _acquire_async_lock(
        self, lock_key: str, domain: str, entity_id: str, timeout_seconds: float
    ):
        lock = await self._get_async_lock(lock_key)
        try:
            await asyncio.wait_for(lock.acquire(), timeout=timeout_seconds)
        except asyncio.TimeoutError:
            logger.warning(
                f"Asyncio lock timeout",
                extra={"lock_key": lock_key, "timeout": timeout_seconds},
            )
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={
                    "error": {
                        "code": "CONFLICT",
                        "message": f"Concurrent operation in progress for {domain} '{entity_id}'. Please retry.",
                    }
                },
            )


# Global coordinator instance
concurrency_guard = ConcurrencyCoordinator()
