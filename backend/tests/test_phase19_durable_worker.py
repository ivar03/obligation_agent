"""
Phase 19 Test Suite: Durable Background Worker & Queue.
Tests persistent job enqueue, idempotency, claiming, lease timeout recovery, retry logic, and dead-letter handling.
"""

import pytest
import asyncio
from datetime import datetime, timezone, timedelta
from sqlalchemy import select

from app.core.durable_worker import DurableJobQueue, register_job_handler
from app.models.job import BackgroundJobRecord, JobStatus


@pytest.mark.asyncio
async def test_durable_queue_enqueue_and_idempotency(db_session):
    queue = DurableJobQueue()
    
    # 1. Enqueue job
    job_id = await queue.enqueue(
        job_type="test_job",
        workspace_id="ws-test",
        payload={"key": "value1"},
        idempotency_key="idem-key-123",
        session=db_session,
    )
    assert job_id.startswith("job-")

    # 2. Duplicate enqueue with same idempotency key returns existing job_id
    duplicate_job_id = await queue.enqueue(
        job_type="test_job",
        workspace_id="ws-test",
        payload={"key": "value2"},
        idempotency_key="idem-key-123",
        session=db_session,
    )
    assert duplicate_job_id == job_id

    # 3. Verify job in database
    job_info = await queue.get_job(job_id, session=db_session)
    assert job_info is not None
    assert job_info["job_type"] == "test_job"
    assert job_info["status"] == JobStatus.QUEUED


@pytest.mark.asyncio
async def test_durable_queue_execution_lifecycle(db_session):
    executed_events = []

    @register_job_handler("lifecycle_test_job")
    async def sample_handler(message: str, count: int):
        executed_events.append((message, count))

    queue = DurableJobQueue()
    job_id = await queue.enqueue(
        job_type="lifecycle_test_job",
        workspace_id="ws-test",
        payload={"message": "hello", "count": 42},
        session=db_session,
    )

    # Claim job
    job_record = await queue._claim_next_job("worker-test-1", session=db_session)
    assert job_record is not None
    assert job_record.id == job_id
    assert job_record.status == JobStatus.CLAIMED
    assert job_record.claimed_by == "worker-test-1"

    # Process job
    await queue._process_job(job_record, "worker-test-1", session=db_session)
    assert len(executed_events) == 1
    assert executed_events[0] == ("hello", 42)

    # Verify status is COMPLETED
    job_info = await queue.get_job(job_id, session=db_session)
    assert job_info["status"] == JobStatus.COMPLETED
    assert job_info["completed_at"] is not None


@pytest.mark.asyncio
async def test_durable_queue_crash_recovery(db_session):
    queue = DurableJobQueue()
    queue._lease_timeout = 1  # 1 second for test

    # Insert a stale CLAIMED job
    job = BackgroundJobRecord(
        id="job-crashed-1",
        job_type="test_crash",
        workspace_id="ws-test",
        status=JobStatus.CLAIMED,
        claimed_at=datetime.now(timezone.utc) - timedelta(seconds=10),
        claimed_by="dead-worker",
    )
    db_session.add(job)
    await db_session.commit()

    # Recover stale jobs
    recovered_count = await queue.recover_stale_jobs(session=db_session)
    assert recovered_count >= 1

    # Verify job is back to QUEUED
    refreshed = await db_session.get(BackgroundJobRecord, "job-crashed-1")
    assert refreshed.status == JobStatus.QUEUED
    assert refreshed.claimed_by is None


@pytest.mark.asyncio
async def test_durable_queue_dead_letter_exhaustion(db_session):
    @register_job_handler("failing_job")
    async def always_fails():
        raise RuntimeError("Simulated external provider crash")

    queue = DurableJobQueue()
    job_id = await queue.enqueue(
        job_type="failing_job",
        workspace_id="ws-test",
        payload={},
        max_attempts=1,  # Exhaust after 1 failure
        session=db_session,
    )

    job_rec = await queue._claim_next_job("worker-test-fail", session=db_session)
    await queue._process_job(job_rec, "worker-test-fail", session=db_session)

    job_info = await queue.get_job(job_id, session=db_session)
    assert job_info["status"] == JobStatus.DEAD_LETTER
    assert "Simulated external provider crash" in job_info["error"]
