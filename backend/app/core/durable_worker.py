"""
Phase 19 Durable Background Job Queue.

Replaces the in-memory BackgroundWorkerQueue with a database-backed durable
job system that survives process restarts, container restarts, and worker crashes.

Key properties:
  - All job state is persisted to the database immediately on enqueue.
  - Workers claim jobs using SELECT ... FOR UPDATE SKIP LOCKED (PostgreSQL) or
    an UPDATE-based atomic claim (SQLite fallback).
  - A lease timeout ensures crashed workers cannot strand jobs permanently.
  - Exponential backoff via scheduled_at column.
  - Idempotency: duplicate enqueue with same idempotency_key is a no-op.
  - On startup: recover CLAIMED/PROCESSING jobs whose leases have expired.

Job lifecycle:
    QUEUED → CLAIMED → PROCESSING → COMPLETED
    PROCESSING → QUEUED (retry scheduled)
    PROCESSING → DEAD_LETTER (after max_attempts)
"""

import asyncio
import uuid
import time
import json
from datetime import datetime, timezone, timedelta
from typing import Any, Callable, Coroutine, Dict, List, Optional
from sqlalchemy import select, update, func, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.logging import get_logger
from app.core.database import AsyncSessionLocal
from app.models.job import BackgroundJobRecord, JobStatus

logger = get_logger("obligation_agent.durable_worker")

# ---------------------------------------------------------------------------
# Job handler registry
# ---------------------------------------------------------------------------
_JOB_HANDLERS: Dict[str, Callable[..., Coroutine]] = {}


def register_job_handler(job_type: str):
    """Decorator to register an async function as a job handler."""
    def decorator(fn: Callable[..., Coroutine]):
        _JOB_HANDLERS[job_type] = fn
        return fn
    return decorator


def get_job_handler(job_type: str) -> Optional[Callable]:
    return _JOB_HANDLERS.get(job_type)


# ---------------------------------------------------------------------------
# Durable Queue
# ---------------------------------------------------------------------------

class DurableJobQueue:
    """
    Database-backed durable job queue with lease-based crash recovery.
    """

    def __init__(self):
        self._worker_id = f"worker-{uuid.uuid4().hex[:8]}"
        self._workers: List[asyncio.Task] = []
        self._running = False
        self._concurrency = settings.WORKER_CONCURRENCY
        self._poll_interval = settings.WORKER_POLL_INTERVAL_SECONDS
        self._lease_timeout = settings.WORKER_LEASE_TIMEOUT_SECONDS

    def start(self):
        if self._running:
            return
        self._running = True
        for i in range(self._concurrency):
            task = asyncio.create_task(
                self._worker_loop(i),
                name=f"durable-worker-{i}",
            )
            self._workers.append(task)
        logger.info(
            "DurableJobQueue started",
            extra={"worker_id": self._worker_id, "concurrency": self._concurrency},
        )

    async def stop(self):
        if not self._running:
            return
        self._running = False
        for task in self._workers:
            task.cancel()
        await asyncio.gather(*self._workers, return_exceptions=True)
        self._workers.clear()
        logger.info("DurableJobQueue stopped gracefully.", extra={"worker_id": self._worker_id})

    async def enqueue(
        self,
        job_type: str,
        workspace_id: str,
        payload: Dict[str, Any],
        idempotency_key: Optional[str] = None,
        max_attempts: int = 3,
        scheduled_at: Optional[datetime] = None,
        session: Optional[AsyncSession] = None,
    ) -> str:
        job_id = f"job-{uuid.uuid4().hex}"
        idem_key = idempotency_key or job_id
        now = datetime.now(timezone.utc)
        run_at = scheduled_at or now

        async def _do_enqueue(sess: AsyncSession) -> str:
            if idempotency_key:
                existing = await sess.execute(
                    select(BackgroundJobRecord).where(
                        BackgroundJobRecord.idempotency_key == idempotency_key
                    )
                )
                existing_job = existing.scalar_one_or_none()
                if existing_job and existing_job.status not in (
                    JobStatus.FAILED, JobStatus.DEAD_LETTER
                ):
                    return existing_job.id

            job = BackgroundJobRecord(
                id=job_id,
                job_type=job_type,
                workspace_id=workspace_id,
                payload=json.dumps(payload),
                status=JobStatus.QUEUED,
                attempt_count=0,
                max_attempts=max_attempts,
                idempotency_key=idem_key,
                scheduled_at=run_at,
                created_at=now,
            )
            sess.add(job)
            await sess.commit()
            return job_id

        if session:
            return await _do_enqueue(session)
        else:
            async with AsyncSessionLocal() as sess:
                return await _do_enqueue(sess)

    async def get_job(self, job_id: str, session: Optional[AsyncSession] = None) -> Optional[Dict[str, Any]]:
        async def _do_get(sess: AsyncSession):
            result = await sess.get(BackgroundJobRecord, job_id)
            if result:
                return {
                    "id": result.id,
                    "job_type": result.job_type,
                    "workspace_id": result.workspace_id,
                    "status": result.status,
                    "attempt_count": result.attempt_count,
                    "max_attempts": result.max_attempts,
                    "error": result.error,
                    "created_at": result.created_at.isoformat() if result.created_at else None,
                    "completed_at": result.completed_at.isoformat() if result.completed_at else None,
                }
            return None

        if session:
            return await _do_get(session)
        else:
            async with AsyncSessionLocal() as sess:
                return await _do_get(sess)

    async def recover_stale_jobs(self, session: Optional[AsyncSession] = None) -> int:
        cutoff = datetime.now(timezone.utc) - timedelta(seconds=self._lease_timeout)

        async def _do_recover(sess: AsyncSession):
            result = await sess.execute(
                update(BackgroundJobRecord)
                .where(
                    BackgroundJobRecord.status == JobStatus.CLAIMED,
                    BackgroundJobRecord.claimed_at < cutoff,
                )
                .values(
                    status=JobStatus.QUEUED,
                    claimed_at=None,
                    claimed_by=None,
                    lease_expires_at=None,
                )
                .returning(BackgroundJobRecord.id)
            )
            recovered_ids = result.scalars().all()
            await sess.commit()

            # Also recover stale event inbox records
            try:
                from app.services.async_event_dispatcher import event_dispatcher
                await event_dispatcher.recover_stale_leases(session=sess)
            except Exception:
                pass

            return len(recovered_ids)

        if session:
            return await _do_recover(session)
        else:
            async with AsyncSessionLocal() as sess:
                return await _do_recover(sess)

    async def get_queue_stats(self, session: Optional[AsyncSession] = None) -> Dict[str, int]:
        async def _do_stats(sess: AsyncSession):
            def count_by_status(s):
                return select(func.count(BackgroundJobRecord.id)).where(
                    BackgroundJobRecord.status == s
                )
            queued = (await sess.execute(count_by_status(JobStatus.QUEUED))).scalar() or 0
            claimed = (await sess.execute(count_by_status(JobStatus.CLAIMED))).scalar() or 0
            processing = (await sess.execute(count_by_status(JobStatus.PROCESSING))).scalar() or 0
            completed = (await sess.execute(count_by_status(JobStatus.COMPLETED))).scalar() or 0
            failed = (await sess.execute(count_by_status(JobStatus.FAILED))).scalar() or 0
            dead_letter = (await sess.execute(count_by_status(JobStatus.DEAD_LETTER))).scalar() or 0
            return {
                "queued": queued,
                "claimed": claimed,
                "processing": processing,
                "completed": completed,
                "failed": failed,
                "dead_letter": dead_letter,
                "total_active": queued + claimed + processing,
            }

        if session:
            return await _do_stats(session)
        else:
            async with AsyncSessionLocal() as sess:
                return await _do_stats(sess)

    async def _worker_loop(self, worker_idx: int):
        worker_label = f"{self._worker_id}-{worker_idx}"
        while self._running:
            try:
                # 1. Check background jobs
                claimed_job = await self._claim_next_job(worker_label)
                if claimed_job is not None:
                    await self._process_job(claimed_job, worker_label)
                    continue

                # 2. Check event inbox stream
                try:
                    from app.services.async_event_dispatcher import event_dispatcher
                    claimed_event = await event_dispatcher.claim_next_event(worker_label)
                    if claimed_event is not None:
                        await event_dispatcher.process_event(claimed_event, worker_label)
                        continue
                except Exception as ex:
                    logger.debug(f"Event claim check: {ex}")

                # If no jobs or events available, sleep
                await asyncio.sleep(self._poll_interval)
            except asyncio.CancelledError:
                break
            except Exception as exc:
                logger.error(
                    f"Worker loop error: {exc}",
                    extra={"worker": worker_label},
                    exc_info=True,
                )
                await asyncio.sleep(2.0)

    async def _claim_next_job(self, worker_label: str, session: Optional[AsyncSession] = None) -> Optional[BackgroundJobRecord]:
        now = datetime.now(timezone.utc)
        lease_until = now + timedelta(seconds=self._lease_timeout)

        async def _do_claim(sess: AsyncSession):
            try:
                if settings.is_postgres():
                    result = await sess.execute(
                        text("""
                            UPDATE background_jobs
                            SET status = 'CLAIMED',
                                claimed_at = :now,
                                claimed_by = :worker,
                                lease_expires_at = :lease_until
                            WHERE id = (
                                SELECT id FROM background_jobs
                                WHERE status = 'QUEUED'
                                  AND scheduled_at <= :now
                                ORDER BY scheduled_at ASC
                                LIMIT 1
                                FOR UPDATE SKIP LOCKED
                            )
                            RETURNING id
                        """),
                        {"now": now, "worker": worker_label, "lease_until": lease_until}
                    )
                    claimed_id = result.scalar_one_or_none()
                else:
                    find_result = await sess.execute(
                        select(BackgroundJobRecord)
                        .where(
                            BackgroundJobRecord.status == JobStatus.QUEUED,
                            BackgroundJobRecord.scheduled_at <= now,
                        )
                        .order_by(BackgroundJobRecord.scheduled_at.asc())
                        .limit(1)
                    )
                    job = find_result.scalar_one_or_none()
                    if not job:
                        return None
                    claimed_id = job.id

                    await sess.execute(
                        update(BackgroundJobRecord)
                        .where(BackgroundJobRecord.id == claimed_id)
                        .values(
                            status=JobStatus.CLAIMED,
                            claimed_at=now,
                            claimed_by=worker_label,
                            lease_expires_at=lease_until,
                        )
                    )

                await sess.commit()
                if not claimed_id:
                    return None

                return await sess.get(BackgroundJobRecord, claimed_id)
            except Exception as exc:
                await sess.rollback()
                logger.debug(f"Claim error: {exc}")
                return None

        if session:
            return await _do_claim(session)
        else:
            async with AsyncSessionLocal() as sess:
                return await _do_claim(sess)

    async def _process_job(self, job: BackgroundJobRecord, worker_label: str, session: Optional[AsyncSession] = None):
        async def _do_process(sess: AsyncSession):
            await sess.execute(
                update(BackgroundJobRecord)
                .where(BackgroundJobRecord.id == job.id)
                .values(status=JobStatus.PROCESSING)
            )
            await sess.commit()

            try:
                handler = get_job_handler(job.job_type)
                if handler is None:
                    raise ValueError(f"No handler registered for job_type '{job.job_type}'")

                payload = json.loads(job.payload or "{}")
                await handler(**payload)

                await sess.execute(
                    update(BackgroundJobRecord)
                    .where(BackgroundJobRecord.id == job.id)
                    .values(status=JobStatus.COMPLETED, completed_at=datetime.now(timezone.utc))
                )
                await sess.commit()
            except Exception as exc:
                attempt = job.attempt_count + 1
                if attempt < job.max_attempts:
                    delay_seconds = 2 ** attempt
                    retry_at = datetime.now(timezone.utc) + timedelta(seconds=delay_seconds)
                    await sess.execute(
                        update(BackgroundJobRecord)
                        .where(BackgroundJobRecord.id == job.id)
                        .values(
                            status=JobStatus.QUEUED,
                            attempt_count=attempt,
                            error=str(exc)[:2000],
                            scheduled_at=retry_at,
                            claimed_at=None,
                            claimed_by=None,
                            lease_expires_at=None,
                        )
                    )
                    await sess.commit()
                else:
                    await sess.execute(
                        update(BackgroundJobRecord)
                        .where(BackgroundJobRecord.id == job.id)
                        .values(
                            status=JobStatus.DEAD_LETTER,
                            attempt_count=attempt,
                            error=str(exc)[:2000],
                            completed_at=datetime.now(timezone.utc),
                        )
                    )
                    await sess.commit()

        if session:
            await _do_process(session)
        else:
            async with AsyncSessionLocal() as sess:
                await _do_process(sess)


# Global instance
durable_queue = DurableJobQueue()
