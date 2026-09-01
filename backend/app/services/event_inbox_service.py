"""
Phase 19 Event Inbox Service.

Provides durable buffering, deterministic hashing, stream partitioning,
and database-level duplicate suppression for incoming provider events.
"""

import hashlib
import json
import uuid
from datetime import datetime, timezone
from typing import Dict, Any, Optional, Tuple
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError

from app.core.logging import get_logger
from app.core.sanitizer import sanitize_for_audit
from app.models.event_inbox import EventInboxRecord, EventInboxStatus

logger = get_logger("obligation_agent.event_inbox")


class EventInboxService:
    """
    Manages the durable intake buffer for all external events.
    Guarantees that identical deliveries (1, 10, or 100 times) resolve to a single logical inbox record.
    """

    @staticmethod
    def compute_payload_hash(provider: str, source_ref: Optional[str], payload: Dict[str, Any]) -> str:
        """
        Computes a deterministic SHA-256 hash of the sanitized payload.
        Ensures consistent hashing regardless of dictionary key ordering.
        """
        clean_payload = sanitize_for_audit(payload)
        serialized = json.dumps(clean_payload, sort_keys=True, default=str)
        content_for_hash = f"{provider}:{source_ref or ''}:{serialized}".encode("utf-8")
        return hashlib.sha256(content_for_hash).hexdigest()

    @staticmethod
    def compute_stream_key(workspace_id: str, provider: str, payload: Dict[str, Any]) -> str:
        """
        Determines the logical stream key for FIFO partition ordering.
        Events with the same stream_key are processed sequentially.
        Different stream_keys execute concurrently in parallel.
        """
        prov = provider.lower()
        if prov == "slack":
            channel = payload.get("channel") or payload.get("event", {}).get("channel") or "general"
            thread_ts = payload.get("thread_ts") or payload.get("event", {}).get("thread_ts")
            if thread_ts:
                return f"{workspace_id}:slack:{channel}:{thread_ts}"
            return f"{workspace_id}:slack:{channel}"
        elif prov == "gmail":
            thread_id = (
                payload.get("threadId")
                or payload.get("thread_id")
                or payload.get("message", {}).get("threadId")
                or "inbox"
            )
            return f"{workspace_id}:gmail:{thread_id}"
        elif prov in ("google_calendar", "google-calendar"):
            calendar_id = payload.get("calendarId") or payload.get("channelId") or "primary"
            return f"{workspace_id}:google_calendar:{calendar_id}"
        elif prov == "jira":
            issue_key = (
                payload.get("key")
                or payload.get("issue", {}).get("key")
                or payload.get("issue_key")
                or payload.get("project_key")
                or "default"
            )
            return f"{workspace_id}:jira:{issue_key}"
        
        # Default partition per workspace + provider
        return f"{workspace_id}:{provider}:default"

    @staticmethod
    def extract_source_ref(provider: str, payload: Dict[str, Any]) -> Optional[str]:
        """
        Extracts stable provider-specific external message / event identifier.
        """
        prov = provider.lower()
        if prov == "slack":
            event_obj = payload.get("event", {}) if isinstance(payload.get("event"), dict) else {}
            return (
                payload.get("event_id")
                or event_obj.get("client_msg_id")
                or event_obj.get("ts")
                or payload.get("ts")
            )
        elif prov == "gmail":
            return (
                payload.get("id")
                or payload.get("message_id")
                or payload.get("message", {}).get("message_id") if isinstance(payload.get("message"), dict) else None
            )
        elif prov in ("google_calendar", "google-calendar"):
            return payload.get("id") or payload.get("resourceId") or payload.get("channelId")
        elif prov == "jira":
            key = payload.get("key") or payload.get("issue", {}).get("key")
            comment_id = payload.get("comment", {}).get("id") if isinstance(payload.get("comment"), dict) else None
            if key and comment_id:
                return f"jira:{key}:comment:{comment_id}"
            if key:
                return f"jira:{key}"
            return payload.get("id") or payload.get("event_id")
        
        return payload.get("id") or payload.get("event_id")


    @staticmethod
    def extract_safe_metadata(provider: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extracts safe, non-sensitive metadata for operational inspection and auditing.
        Never stores secrets, tokens, or raw authorization headers.
        """
        safe_meta: Dict[str, Any] = {
            "provider": provider,
            "received_at": datetime.now(timezone.utc).isoformat(),
        }

        if provider == "slack":
            event = payload.get("event", {}) if isinstance(payload.get("event"), dict) else payload
            safe_meta.update({
                "channel": event.get("channel") or payload.get("channel"),
                "user": event.get("user") or payload.get("user"),
                "type": event.get("type") or payload.get("type"),
                "subtype": event.get("subtype"),
                "thread_ts": event.get("thread_ts"),
                "text_length": len(str(event.get("text", ""))),
            })
        elif provider == "gmail":
            safe_meta.update({
                "sender": payload.get("from") or payload.get("sender"),
                "subject": payload.get("subject"),
                "message_id": payload.get("id") or payload.get("message_id"),
                "thread_id": payload.get("threadId") or payload.get("thread_id"),
                "snippet": str(payload.get("snippet", ""))[:120],
            })
        elif provider in ("google_calendar", "google-calendar"):
            safe_meta.update({
                "summary": payload.get("summary"),
                "status": payload.get("status"),
                "start": payload.get("start"),
                "end": payload.get("end"),
                "event_id": payload.get("id"),
            })
        else:
            safe_meta.update({
                "type": payload.get("type", "event"),
                "keys_present": list(payload.keys())[:15],
            })

        return safe_meta

    @classmethod
    async def ingest_to_inbox(
        cls,
        session: AsyncSession,
        workspace_id: str,
        provider: str,
        raw_payload: Dict[str, Any],
        event_type: str = "message",
        correlation_id: Optional[str] = None,
    ) -> Tuple[EventInboxRecord, bool]:
        """
        Atomically buffers an incoming event into the EventInbox.
        Returns: (inbox_record, is_duplicate)
        """
        source_ref = cls.extract_source_ref(provider, raw_payload)
        payload_hash = cls.compute_payload_hash(provider, source_ref, raw_payload)
        stream_key = cls.compute_stream_key(workspace_id, provider, raw_payload)
        safe_metadata = cls.extract_safe_metadata(provider, raw_payload)
        sanitized_body = sanitize_for_audit(raw_payload)

        # 1. Fast existence check
        existing_stmt = select(EventInboxRecord).where(
            and_(
                EventInboxRecord.workspace_id == workspace_id,
                EventInboxRecord.provider == provider,
                EventInboxRecord.source_ref == source_ref,
                EventInboxRecord.payload_hash == payload_hash,
            )
        )
        existing_res = await session.execute(existing_stmt)
        existing = existing_res.scalar_one_or_none()
        if existing:
            logger.info(
                f"Duplicate event detected in inbox [{existing.id}] for stream [{stream_key}]. Returning existing record.",
                extra={"event_id": existing.id, "provider": provider, "stream_key": stream_key}
            )
            return existing, True

        # 2. Insert new record
        record_id = f"inbox-{uuid.uuid4().hex}"
        now = datetime.now(timezone.utc)
        record = EventInboxRecord(
            id=record_id,
            workspace_id=workspace_id,
            provider=provider,
            source_ref=source_ref,
            event_type=event_type,
            payload_hash=payload_hash,
            stream_key=stream_key,
            payload_metadata=safe_metadata,
            raw_payload=sanitized_body,
            status=EventInboxStatus.QUEUED,
            attempt_count=0,
            max_attempts=3,
            received_at=now,
            available_at=now,
            correlation_id=correlation_id,
            created_at=now,
            updated_at=now,
        )

        try:
            session.add(record)
            await session.commit()
            logger.info(
                f"Persisted event into durable inbox [{record.id}] on stream [{stream_key}].",
                extra={"event_id": record.id, "provider": provider, "stream_key": stream_key}
            )
            return record, False
        except IntegrityError:
            # Concurrent race caught by database-level unique constraint
            await session.rollback()
            res = await session.execute(existing_stmt)
            concurrent_existing = res.scalar_one()
            return concurrent_existing, True
