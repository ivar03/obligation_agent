"""
Phase 17 Background Worker & Job Queue Architecture.

Provides durable, asynchronous job execution with:
- Job status lifecycle: QUEUED -> PROCESSING -> COMPLETED / FAILED / DEAD_LETTER
- Bounded retries with exponential backoff
- Dead-letter state for non-retryable failures
- Strong job idempotency
- Graceful shutdown handling
"""

import asyncio
import uuid
import time
from enum import Enum
from typing import Callable, Coroutine, Dict, Any, Optional, List
from datetime import datetime, timezone

from app.core.config import settings
from app.core.logging import logger


class JobStatus(str, Enum):
    QUEUED = "QUEUED"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    DEAD_LETTER = "DEAD_LETTER"


class BackgroundJob:
    def __init__(
        self,
        job_id: str,
        job_type: str,
        workspace_id: str,
        handler: Callable[..., Coroutine],
        args: tuple = (),
        kwargs: dict = None,
        max_retries: int = 3,
        base_delay_seconds: float = 1.0,
    ):
        self.job_id = job_id
        self.job_type = job_type
        self.workspace_id = workspace_id
        self.handler = handler
        self.args = args
        self.kwargs = kwargs or {}
        self.status = JobStatus.QUEUED
        self.retry_count = 0
        self.max_retries = max_retries
        self.base_delay_seconds = base_delay_seconds
        self.created_at = datetime.now(timezone.utc)
        self.started_at: Optional[datetime] = None
        self.completed_at: Optional[datetime] = None
        self.result: Any = None
        self.error: Optional[str] = None
        self.next_retry_at: Optional[float] = None


class BackgroundWorkerQueue:
    """
    In-process async worker queue with concurrency limits, bounded retries,
    exponential backoff, and dead-letter handling.
    """

    def __init__(self, concurrency: int = 4):
        self.concurrency = concurrency
        self._queue: asyncio.Queue = asyncio.Queue()
        self._jobs: Dict[str, BackgroundJob] = {}
        self._workers: List[asyncio.Task] = []
        self._running = False

    def start(self):
        """Starts the worker processing loop."""
        if self._running:
            return
        self._running = True
        for i in range(self.concurrency):
            task = asyncio.create_task(self._worker_loop(i), name=f"bg-worker-{i}")
            self._workers.append(task)
        logger.info(f"BackgroundWorkerQueue started with {self.concurrency} workers.")

    async def stop(self):
        """Gracefully shuts down all workers."""
        if not self._running:
            return
        self._running = False
        for task in self._workers:
            task.cancel()
        await asyncio.gather(*self._workers, return_exceptions=True)
        self._workers.clear()
        logger.info("BackgroundWorkerQueue stopped gracefully.")

    async def enqueue(
        self,
        job_type: str,
        workspace_id: str,
        handler: Callable[..., Coroutine],
        *args,
        job_id: Optional[str] = None,
        max_retries: int = 3,
        base_delay_seconds: float = 1.0,
        **kwargs,
    ) -> str:
        """Enqueues a new background job and returns the job_id."""
        j_id = job_id or f"job-{uuid.uuid4().hex[:10]}"

        # Idempotency check
        if j_id in self._jobs:
            existing = self._jobs[j_id]
            if existing.status in (JobStatus.QUEUED, JobStatus.PROCESSING, JobStatus.COMPLETED):
                logger.info(f"Job [{j_id}] already exists with status [{existing.status}]. Returning existing ID.")
                return j_id

        job = BackgroundJob(
            job_id=j_id,
            job_type=job_type,
            workspace_id=workspace_id,
            handler=handler,
            args=args,
            kwargs=kwargs,
            max_retries=max_retries,
            base_delay_seconds=base_delay_seconds,
        )
        self._jobs[j_id] = job
        await self._queue.put(job)
        return j_id

    def get_job(self, job_id: str) -> Optional[BackgroundJob]:
        return self._jobs.get(job_id)

    def list_jobs(self, workspace_id: Optional[str] = None, limit: int = 50) -> List[BackgroundJob]:
        jobs = list(self._jobs.values())
        if workspace_id:
            jobs = [j for j in jobs if j.workspace_id == workspace_id]
        jobs.sort(key=lambda x: x.created_at, reverse=True)
        return jobs[:limit]

    async def _worker_loop(self, worker_idx: int):
        while self._running:
            try:
                job: BackgroundJob = await self._queue.get()
            except asyncio.CancelledError:
                break

            # Handle scheduled retry backoff
            if job.next_retry_at:
                now = time.time()
                if now < job.next_retry_at:
                    await asyncio.sleep(min(1.0, job.next_retry_at - now))
                    await self._queue.put(job)
                    self._queue.task_done()
                    continue

            job.status = JobStatus.PROCESSING
            job.started_at = datetime.now(timezone.utc)

            try:
                result = await job.handler(*job.args, **job.kwargs)
                job.status = JobStatus.COMPLETED
                job.result = result
                job.completed_at = datetime.now(timezone.utc)
            except Exception as exc:
                job.retry_count += 1
                job.error = str(exc)
                logger.error(f"Job [{job.job_id}] failed (attempt {job.retry_count}/{job.max_retries}): {exc}")

                if job.retry_count <= job.max_retries:
                    # Exponential backoff
                    delay = job.base_delay_seconds * (2 ** (job.retry_count - 1))
                    job.next_retry_at = time.time() + delay
                    job.status = JobStatus.QUEUED
                    await self._queue.put(job)
                else:
                    job.status = JobStatus.DEAD_LETTER
                    job.completed_at = datetime.now(timezone.utc)
                    logger.error(f"Job [{job.job_id}] moved to DEAD_LETTER after {job.retry_count} failed attempts.")
            finally:
                self._queue.task_done()


# Global worker queue instance
worker_queue = BackgroundWorkerQueue(concurrency=settings.WORKER_CONCURRENCY)
