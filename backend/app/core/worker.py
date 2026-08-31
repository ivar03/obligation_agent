"""
Phase 19 Background Worker.

Provides DurableJobQueue (database-backed durable queue) as the default worker_queue,
while preserving BackgroundWorkerQueue and JobStatus classes for backwards compatibility.
"""

import asyncio
import uuid
import time
from enum import Enum
from typing import Callable, Coroutine, Dict, Any, Optional, List
from datetime import datetime, timezone

from app.core.config import settings
from app.core.logging import get_logger
from app.core.durable_worker import DurableJobQueue, durable_queue
from app.models.job import JobStatus

logger = get_logger("obligation_agent.worker")


class BackgroundJob:
    def __init__(self, job_id, job_type, workspace_id, handler, args=(), kwargs=None,
                 max_retries=3, base_delay_seconds=1.0):
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
    def __init__(self, concurrency: int = 4):
        self.concurrency = concurrency
        self._queue: asyncio.Queue = asyncio.Queue()
        self._jobs: Dict[str, BackgroundJob] = {}
        self._workers: List[asyncio.Task] = []
        self._running = False

    def start(self):
        if self._running:
            return
        self._running = True
        for i in range(self.concurrency):
            task = asyncio.create_task(self._worker_loop(i), name=f"bg-worker-{i}")
            self._workers.append(task)
        logger.info(f"BackgroundWorkerQueue started (in-memory) with {self.concurrency} workers.")

    async def stop(self):
        if not self._running:
            return
        self._running = False
        for task in self._workers:
            task.cancel()
        await asyncio.gather(*self._workers, return_exceptions=True)
        self._workers.clear()
        logger.info("BackgroundWorkerQueue stopped gracefully.")

    async def enqueue(self, job_type, workspace_id, handler, *args,
                      job_id=None, max_retries=3, base_delay_seconds=1.0, **kwargs) -> str:
        j_id = job_id or f"job-{uuid.uuid4().hex[:10]}"
        if j_id in self._jobs:
            existing = self._jobs[j_id]
            if existing.status in (JobStatus.QUEUED, JobStatus.PROCESSING, JobStatus.COMPLETED):
                return j_id
        job = BackgroundJob(j_id, job_type, workspace_id, handler, args, kwargs, max_retries, base_delay_seconds)
        self._jobs[j_id] = job
        await self._queue.put(job)
        return j_id

    def get_job(self, job_id: str):
        return self._jobs.get(job_id)

    def list_jobs(self, workspace_id=None, limit=50):
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
                    delay = job.base_delay_seconds * (2 ** (job.retry_count - 1))
                    job.next_retry_at = time.time() + delay
                    job.status = JobStatus.QUEUED
                    await self._queue.put(job)
                else:
                    job.status = JobStatus.DEAD_LETTER
                    job.completed_at = datetime.now(timezone.utc)
                    logger.error(f"Job [{job.job_id}] moved to DEAD_LETTER.")
            finally:
                self._queue.task_done()


if settings.WORKER_DURABLE_QUEUE:
    worker_queue = durable_queue
else:
    worker_queue = BackgroundWorkerQueue(concurrency=settings.WORKER_CONCURRENCY)

__all__ = ["worker_queue", "BackgroundWorkerQueue", "JobStatus", "BackgroundJob"]
