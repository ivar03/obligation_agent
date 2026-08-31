"""
Phase 19 Async Event Dispatcher.

Orchestrates asynchronous event processing with:
  - Stream partition isolation & strict FIFO ordering per stream_key
  - Concurrency across distinct streams
  - Isolated execution boundaries (poison events do not crash worker)
  - Exponential backoff retries for transient failures
  - Dead-letter queue (DLQ) transitions for permanent errors & exhausted retries
  - Lease-based crash recovery
  - Integration with existing EventIngestionService without duplicating intelligence logic
"""

import time
import asyncio
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any, List, Tuple
from sqlalchemy import select, update, and_, or_, func, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.logging import get_logger
from app.core.database import AsyncSessionLocal
from app.core.metrics import metrics
from app.models.event_inbox import EventInboxRecord, EventInboxStatus
from app.services.event_ingestion_service import EventIngestionService

logger = get_logger("obligation_agent.event_dispatcher")


# Non-retryable error signatures
PERMANENT_ERROR_TYPES = (
    ValueError,
    KeyError,
    TypeError,
)


class AsyncEventDispatcher:
    """
    Dispatcher engine responsible for claiming, stream-ordering, and processing buffered events.
    """

    def __init__(
        self,
        worker_id: str = "dispatcher-1",
        lease_timeout_seconds: int = None,
    ):
        self.worker_id = worker_id
        self.lease_timeout = lease_timeout_seconds or settings.WORKER_LEASE_TIMEOUT_SECONDS
        self._running = False
        self._loop_task: Optional[asyncio.Task] = None

    async def claim_next_event(
        self,
        worker_label: Optional[str] = None,
        workspace_id: Optional[str] = None,
        session: Optional[AsyncSession] = None,
    ) -> Optional[EventInboxRecord]:
        """
        Atomically claims the next eligible event while enforcing stream ordering:
        If an event with the same stream_key is currently in PROCESSING state, subsequent
        events in that stream wait, while other streams continue processing in parallel.
        """
        worker = worker_label or self.worker_id
        now = datetime.now(timezone.utc)
        lease_until = now + timedelta(seconds=self.lease_timeout)

        async def _do_claim(sess: AsyncSession) -> Optional[EventInboxRecord]:
            # 1. Identify all stream_keys currently being processed
            active_streams_stmt = select(EventInboxRecord.stream_key).where(
                EventInboxRecord.status == EventInboxStatus.PROCESSING
            )
            active_streams_res = await sess.execute(active_streams_stmt)
            busy_streams = set(active_streams_res.scalars().all())

            # 2. Query next available event not in a busy stream
            conditions = [
                EventInboxRecord.status.in_([
                    EventInboxStatus.QUEUED,
                    EventInboxStatus.RETRY_SCHEDULED,
                ]),
                EventInboxRecord.available_at <= now,
            ]
            if workspace_id:
                conditions.append(EventInboxRecord.workspace_id == workspace_id)

            candidates_stmt = (
                select(EventInboxRecord)
                .where(and_(*conditions))
                .order_by(EventInboxRecord.received_at.asc())
                .limit(20)
            )
            res = await sess.execute(candidates_stmt)
            candidates = res.scalars().all()


            candidate_to_claim = None
            for cand in candidates:
                if cand.stream_key not in busy_streams:
                    candidate_to_claim = cand
                    break

            if not candidate_to_claim:
                return None

            # 3. Atomically lock candidate
            claim_update = (
                update(EventInboxRecord)
                .where(
                    and_(
                        EventInboxRecord.id == candidate_to_claim.id,
                        EventInboxRecord.status.in_([
                            EventInboxStatus.QUEUED,
                            EventInboxStatus.RETRY_SCHEDULED,
                        ]),
                    )
                )
                .values(
                    status=EventInboxStatus.PROCESSING,
                    locked_at=now,
                    locked_by=worker,
                    lease_expires_at=lease_until,
                    updated_at=now,
                )
            )
            update_res = await sess.execute(claim_update)
            if update_res.rowcount == 0:
                await sess.rollback()
                return None

            await sess.commit()
            return await sess.get(EventInboxRecord, candidate_to_claim.id)

        if session:
            return await _do_claim(session)
        else:
            async with AsyncSessionLocal() as sess:
                return await _do_claim(sess)

    async def process_event(
        self,
        record: EventInboxRecord,
        worker_label: Optional[str] = None,
        session: Optional[AsyncSession] = None,
    ) -> Dict[str, Any]:
        """
        Executes an event through the existing EventIngestionService pipeline.
        Records metrics, latency, retries on transient errors, or shifts to DLQ on exhaustion.
        """
        worker = worker_label or self.worker_id
        start_time = time.time()
        now = datetime.now(timezone.utc)

        async def _do_process(sess: AsyncSession) -> Dict[str, Any]:
            nonlocal record
            try:
                # Dispatch to existing intelligence ingestion pipeline
                result = await EventIngestionService.ingest_from_provider(
                    session=sess,
                    provider_name=record.provider,
                    raw_payload=record.raw_payload or {},
                    workspace_id=record.workspace_id,
                )

                duration_ms = round((time.time() - start_time) * 1000, 2)

                # Mark PROCESSED
                await sess.execute(
                    update(EventInboxRecord)
                    .where(EventInboxRecord.id == record.id)
                    .values(
                        status=EventInboxStatus.PROCESSED,
                        processed_at=datetime.now(timezone.utc),
                        processing_duration_ms=duration_ms,
                        locked_at=None,
                        locked_by=None,
                        lease_expires_at=None,
                        updated_at=datetime.now(timezone.utc),
                    )
                )
                await sess.commit()

                # Telemetry
                metrics.increment("events.processed_total", labels={"provider": record.provider})
                metrics.record_duration("events.processing_latency_ms", duration_ms, labels={"provider": record.provider})

                logger.info(
                    f"Successfully processed event [{record.id}] in {duration_ms}ms on stream [{record.stream_key}].",
                    extra={"event_id": record.id, "provider": record.provider, "duration_ms": duration_ms}
                )
                return {
                    "success": True,
                    "event_id": record.id,
                    "duration_ms": duration_ms,
                    "result": result.model_dump() if hasattr(result, "model_dump") else result,
                }

            except Exception as exc:
                duration_ms = round((time.time() - start_time) * 1000, 2)
                is_permanent = isinstance(exc, PERMANENT_ERROR_TYPES) or "invalid" in str(exc).lower()
                next_attempt = record.attempt_count + 1

                if not is_permanent and next_attempt < record.max_attempts:
                    # Transient error: Exponential backoff
                    delay_seconds = 2 ** next_attempt
                    next_available = datetime.now(timezone.utc) + timedelta(seconds=delay_seconds)

                    await sess.execute(
                        update(EventInboxRecord)
                        .where(EventInboxRecord.id == record.id)
                        .values(
                            status=EventInboxStatus.RETRY_SCHEDULED,
                            attempt_count=next_attempt,
                            available_at=next_available,
                            last_error=str(exc)[:2000],
                            locked_at=None,
                            locked_by=None,
                            lease_expires_at=None,
                            updated_at=datetime.now(timezone.utc),
                        )
                    )
                    await sess.commit()

                    metrics.increment("events.retry_total", labels={"provider": record.provider})
                    logger.warning(
                        f"Transient failure for event [{record.id}] (attempt {next_attempt}/{record.max_attempts}). Retrying in {delay_seconds}s: {exc}",
                        extra={"event_id": record.id, "attempt": next_attempt, "retry_in": delay_seconds}
                    )
                    return {
                        "success": False,
                        "status": "RETRY_SCHEDULED",
                        "event_id": record.id,
                        "attempt": next_attempt,
                        "error": str(exc),
                    }
                else:
                    # Permanent failure or retry exhaustion -> DEAD_LETTER
                    await sess.execute(
                        update(EventInboxRecord)
                        .where(EventInboxRecord.id == record.id)
                        .values(
                            status=EventInboxStatus.DEAD_LETTER,
                            attempt_count=next_attempt,
                            last_error=str(exc)[:2000],
                            locked_at=None,
                            locked_by=None,
                            lease_expires_at=None,
                            updated_at=datetime.now(timezone.utc),
                        )
                    )
                    await sess.commit()

                    metrics.increment("events.dead_letter_total", labels={"provider": record.provider})
                    metrics.increment("events.failed_total", labels={"provider": record.provider})

                    logger.error(
                        f"Event [{record.id}] transitioned to DEAD_LETTER after {next_attempt} attempt(s): {exc}",
                        extra={"event_id": record.id, "error": str(exc), "permanent": is_permanent}
                    )
                    return {
                        "success": False,
                        "status": "DEAD_LETTER",
                        "event_id": record.id,
                        "error": str(exc),
                    }

        if session:
            return await _do_process(session)
        else:
            async with AsyncSessionLocal() as sess:
                return await _do_process(sess)

    async def recover_stale_leases(self, session: Optional[AsyncSession] = None) -> int:
        """
        Reclaims events whose processing leases have expired due to worker crashes.
        """
        cutoff = datetime.now(timezone.utc)

        async def _do_recover(sess: AsyncSession) -> int:
            stale_stmt = (
                update(EventInboxRecord)
                .where(
                    and_(
                        EventInboxRecord.status == EventInboxStatus.PROCESSING,
                        EventInboxRecord.lease_expires_at < cutoff,
                    )
                )
                .values(
                    status=EventInboxStatus.QUEUED,
                    locked_at=None,
                    locked_by=None,
                    lease_expires_at=None,
                    updated_at=datetime.now(timezone.utc),
                )
                .returning(EventInboxRecord.id)
            )
            res = await sess.execute(stale_stmt)
            recovered_ids = res.scalars().all()
            await sess.commit()

            if recovered_ids:
                logger.info(f"Reclaimed {len(recovered_ids)} crashed/stale event inbox leases.")
            return len(recovered_ids)

        if session:
            return await _do_recover(session)
        else:
            async with AsyncSessionLocal() as sess:
                return await _do_recover(sess)

    async def get_inbox_queue_stats(
        self,
        workspace_id: Optional[str] = None,
        session: Optional[AsyncSession] = None,
    ) -> Dict[str, Any]:
        """
        Calculates operational queue depths, oldest event age, and dead-letter counts.
        """
        async def _do_stats(sess: AsyncSession) -> Dict[str, Any]:
            def _filter(stmt):
                if workspace_id:
                    return stmt.where(EventInboxRecord.workspace_id == workspace_id)
                return stmt

            queued = (await sess.execute(_filter(select(func.count(EventInboxRecord.id)).where(EventInboxRecord.status == EventInboxStatus.QUEUED)))).scalar() or 0
            processing = (await sess.execute(_filter(select(func.count(EventInboxRecord.id)).where(EventInboxRecord.status == EventInboxStatus.PROCESSING)))).scalar() or 0
            retrying = (await sess.execute(_filter(select(func.count(EventInboxRecord.id)).where(EventInboxRecord.status == EventInboxStatus.RETRY_SCHEDULED)))).scalar() or 0
            dead_letter = (await sess.execute(_filter(select(func.count(EventInboxRecord.id)).where(EventInboxRecord.status == EventInboxStatus.DEAD_LETTER)))).scalar() or 0
            processed = (await sess.execute(_filter(select(func.count(EventInboxRecord.id)).where(EventInboxRecord.status == EventInboxStatus.PROCESSED)))).scalar() or 0

            # Oldest queued event age
            oldest_res = await sess.execute(
                _filter(
                    select(EventInboxRecord.received_at)
                    .where(EventInboxRecord.status.in_([EventInboxStatus.QUEUED, EventInboxStatus.RETRY_SCHEDULED]))
                    .order_by(EventInboxRecord.received_at.asc())
                    .limit(1)
                )
            )
            oldest_ts = oldest_res.scalar_one_or_none()
            oldest_age_sec = 0.0
            if oldest_ts:
                now = datetime.now(timezone.utc)
                if oldest_ts.tzinfo is None:
                    oldest_ts = oldest_ts.replace(tzinfo=timezone.utc)
                oldest_age_sec = max(0.0, (now - oldest_ts).total_seconds())

            return {
                "queued": queued,
                "processing": processing,
                "retrying": retrying,
                "dead_letter": dead_letter,
                "processed": processed,
                "total_backlog": queued + processing + retrying,
                "oldest_queued_age_seconds": round(oldest_age_sec, 2),
            }

        if session:
            return await _do_stats(session)
        else:
            async with AsyncSessionLocal() as sess:
                return await _do_stats(sess)


# Global singleton dispatcher instance
event_dispatcher = AsyncEventDispatcher()
