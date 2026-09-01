"""
Phase 21 Operational Audit Service.

Manages append-only operational audit logging with SHA-256 hash chaining,
cryptographic verification, tenant isolation, and sensitive metadata redaction.
"""

import json
import time
import uuid
import hashlib
from typing import Optional, Dict, Any, List, Tuple
from datetime import datetime, timezone

from sqlalchemy import select, desc, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import logger
from app.core.request_context import (
    get_current_request_id,
    get_current_trace_id,
    get_current_span_id,
)
from app.core.sanitizer import sanitize_metadata
from app.models.operational_audit import OperationalAuditRecord
from app.schemas.observability import (
    OperationalAuditRecordSchema,
    AuditIntegrityResult,
    AuditStatsResponse,
    OperationalEventType,
    OperationalSeverity,
)

GENESIS_HASH = "0000000000000000000000000000000000000000000000000000000000000000"
_monotonic_counter = 0


def get_next_sequence_id() -> int:
    global _monotonic_counter
    _monotonic_counter += 1
    return _monotonic_counter


def canonical_timestamp_iso(ts: Any) -> str:

    """Produces canonical ISO timestamp format across all SQL dialects and drivers."""
    if isinstance(ts, str):
        # Convert "2026-09-01 12:00:00.123456" to canonical ISO format
        cleaned = ts.strip().replace(" ", "T")
        if "+" in cleaned:
            cleaned = cleaned.split("+")[0]
        if "Z" in cleaned:
            cleaned = cleaned[:-1]
        return cleaned
    if hasattr(ts, "strftime"):
        return ts.strftime("%Y-%m-%dT%H:%M:%S.%f")
    return str(ts)


class OperationalAuditService:
    """
    Append-only, tamper-evident operational audit service.
    """

    @classmethod
    def calculate_record_hash(
        cls,
        record_id: str,
        workspace_id: str,
        timestamp_iso: str,
        event_type: str,
        action: str,
        result: str,
        actor_id: Optional[str],
        trace_id: Optional[str],
        resource_id: Optional[str],
        metadata_json: Optional[Dict[str, Any]],
        previous_hash: str,
    ) -> str:
        """Calculates canonical SHA-256 hash chaining current payload to previous hash."""
        canonical_dict = {
            "id": record_id,
            "workspace_id": workspace_id,
            "timestamp": canonical_timestamp_iso(timestamp_iso),
            "event_type": event_type,
            "action": action,
            "result": result,
            "actor_id": actor_id or "",
            "trace_id": trace_id or "",
            "resource_id": resource_id or "",
            "metadata": metadata_json or {},
            "previous_hash": previous_hash,
        }
        canonical_str = json.dumps(canonical_dict, sort_keys=True)
        return hashlib.sha256(canonical_str.encode("utf-8")).hexdigest()

    @classmethod
    async def log_event(
        cls,
        session: AsyncSession,
        workspace_id: str,
        event_type: str,
        action: str,
        severity: str = "INFO",
        actor_type: str = "SYSTEM",
        actor_id: Optional[str] = None,
        resource_type: Optional[str] = None,
        resource_id: Optional[str] = None,
        provider: Optional[str] = None,
        result: str = "SUCCESS",
        error_code: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        trace_id: Optional[str] = None,
        span_id: Optional[str] = None,
        request_id: Optional[str] = None,
    ) -> OperationalAuditRecord:
        """
        Creates and persists a new append-only operational audit record linked to the previous hash.
        """
        # Redact any credentials from metadata
        clean_metadata = sanitize_metadata(metadata or {})
        now = datetime.now(timezone.utc)
        now_iso = canonical_timestamp_iso(now)

        req_id = request_id or get_current_request_id()
        tr_id = trace_id or get_current_trace_id()
        sp_id = span_id or get_current_span_id()


        # 1. Fetch latest record hash for hash chaining
        stmt = (
            select(OperationalAuditRecord.record_hash)
            .where(OperationalAuditRecord.workspace_id == workspace_id)
            .order_by(desc(OperationalAuditRecord.id))
            .limit(1)
        )
        res = await session.execute(stmt)
        latest_hash = res.scalar()
        prev_hash = latest_hash if latest_hash else GENESIS_HASH

        # Generate monotonically sortable ID
        rec_id = f"opaud-{time.time_ns():020d}-{get_next_sequence_id():010d}"


        # Calculate tamper-evident hash
        rec_hash = cls.calculate_record_hash(
            record_id=rec_id,
            workspace_id=workspace_id,
            timestamp_iso=now_iso,
            event_type=event_type,
            action=action,
            result=result,
            actor_id=actor_id,
            trace_id=tr_id,
            resource_id=resource_id,
            metadata_json=clean_metadata,
            previous_hash=prev_hash,
        )


        record = OperationalAuditRecord(
            id=rec_id,
            workspace_id=workspace_id,
            timestamp=now,
            event_type=event_type,
            severity=severity,
            actor_type=actor_type,
            actor_id=actor_id,
            request_id=req_id,
            trace_id=tr_id,
            span_id=sp_id,
            resource_type=resource_type,
            resource_id=resource_id,
            provider=provider,
            action=action,
            result=result,
            error_code=error_code,
            metadata_json=clean_metadata,
            previous_hash=prev_hash,
            record_hash=rec_hash,
        )

        session.add(record)
        await session.flush()
        return record


    @classmethod
    async def verify_chain(
        cls,
        workspace_id: str,
        session: AsyncSession,
    ) -> AuditIntegrityResult:
        """
        Cryptographically verifies the SHA-256 hash chain for a workspace.
        Detects any modified payload, deleted record, or broken link.
        """
        start = time.perf_counter()
        stmt = (
            select(OperationalAuditRecord)
            .where(OperationalAuditRecord.workspace_id == workspace_id)
        )
        res = await session.execute(stmt)
        records = res.scalars().all()

        total = len(records)
        if total == 0:
            return AuditIntegrityResult(
                workspace_id=workspace_id,
                verified=True,
                total_records=0,
                intact_records=0,
                corrupted_records=0,
                tampered_record_ids=[],
                verification_duration_ms=0.0,
                verified_at=datetime.now(timezone.utc).isoformat(),
            )

        # Index records by previous_hash for exact hash-pointer traversal
        by_prev_hash: Dict[str, OperationalAuditRecord] = {}
        for r in records:
            if r.previous_hash in by_prev_hash:
                # Fork detected! Multiple records claim same previous hash
                by_prev_hash[r.previous_hash] = r
            else:
                by_prev_hash[r.previous_hash] = r

        intact = 0
        corrupted = 0
        tampered_ids: List[str] = []
        visited_ids = set()

        curr_prev = GENESIS_HASH

        while curr_prev in by_prev_hash:
            r = by_prev_hash[curr_prev]
            if r.id in visited_ids:
                # Cycle detected
                tampered_ids.append(r.id)
                corrupted += 1
                break
            visited_ids.add(r.id)

            now_iso = r.timestamp.isoformat() if hasattr(r.timestamp, "isoformat") else str(r.timestamp)
            expected_hash = cls.calculate_record_hash(
                record_id=r.id,
                workspace_id=r.workspace_id,
                timestamp_iso=now_iso,
                event_type=r.event_type,
                action=r.action,
                result=r.result,
                actor_id=r.actor_id,
                trace_id=r.trace_id,
                resource_id=r.resource_id,
                metadata_json=r.metadata_json,
                previous_hash=curr_prev,
            )

            if r.record_hash != expected_hash:
                corrupted += 1
                tampered_ids.append(r.id)
                # Broken link
                break
            else:
                intact += 1
                curr_prev = r.record_hash

        # Any unvisited records in the workspace are orphaned or disconnected links
        unvisited = [r.id for r in records if r.id not in visited_ids]
        if unvisited:
            corrupted += len(unvisited)
            for uid in unvisited:
                if uid not in tampered_ids:
                    tampered_ids.append(uid)

        dur_ms = round((time.perf_counter() - start) * 1000, 2)
        verified = corrupted == 0 and intact == total

        return AuditIntegrityResult(
            workspace_id=workspace_id,
            verified=verified,
            total_records=total,
            intact_records=intact,
            corrupted_records=corrupted,
            tampered_record_ids=tampered_ids,
            verification_duration_ms=dur_ms,
            verified_at=datetime.now(timezone.utc).isoformat(),
        )


    @classmethod
    async def get_stats(
        cls,
        workspace_id: str,
        session: AsyncSession,
    ) -> AuditStatsResponse:
        """Calculates statistical distribution of operational events."""
        stmt = select(OperationalAuditRecord).where(OperationalAuditRecord.workspace_id == workspace_id)
        res = await session.execute(stmt)
        records = res.scalars().all()

        by_severity: Dict[str, int] = {}
        by_event_type: Dict[str, int] = {}
        by_result: Dict[str, int] = {}
        last_time = None

        for r in records:
            by_severity[r.severity] = by_severity.get(r.severity, 0) + 1
            by_event_type[r.event_type] = by_event_type.get(r.event_type, 0) + 1
            by_result[r.result] = by_result.get(r.result, 0) + 1
            last_time = r.timestamp.isoformat()

        return AuditStatsResponse(
            workspace_id=workspace_id,
            total_audit_records=len(records),
            by_severity=by_severity,
            by_event_type=by_event_type,
            by_result=by_result,
            last_event_time=last_time,
        )
