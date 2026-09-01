"""
Phase 21 Deterministic Alerting Engine.

Evaluates operational health conditions against threshold rules and manages
the full alert lifecycle (OPEN, ACKNOWLEDGED, RESOLVED, SUPPRESSED).
Alerts notify operators; they never mutate domain business state.
"""

import hashlib
from typing import Optional, List, Dict, Any
from datetime import datetime, timezone, timedelta
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.logging import logger
from app.core.metrics import metrics
from app.models.event_inbox import EventInboxRecord, EventInboxStatus
from app.models.operational_alert import OperationalAlert
from app.schemas.observability import AlertStatus, OperationalAlertSchema


class AlertEngine:
    """
    Deterministic operational rule evaluation and alert lifecycle manager.
    """

    @classmethod
    def generate_fingerprint(cls, alert_name: str, workspace_id: str, resource_key: str) -> str:
        return hashlib.sha256(f"{alert_name}:{workspace_id}:{resource_key}".encode()).hexdigest()[:32]

    @classmethod
    async def evaluate_rules(
        cls,
        workspace_id: str,
        session: AsyncSession,
    ) -> List[OperationalAlert]:
        """
        Runs deterministic alert rule checks and generates/updates operational alerts.
        """
        generated_alerts: List[OperationalAlert] = []
        now = datetime.now(timezone.utc)

        # Rule 1: Dead Letter Queue Depth > 0
        dlq_stmt = (
            select(EventInboxRecord)
            .where(
                EventInboxRecord.workspace_id == workspace_id,
                EventInboxRecord.status == EventInboxStatus.DEAD_LETTER,
            )
        )
        dlq_res = await session.execute(dlq_stmt)
        dlq_items = dlq_res.scalars().all()
        dlq_count = len(dlq_items)

        if dlq_count > 0:
            fp = cls.generate_fingerprint("DLQ_BACKLOG_DETECTED", workspace_id, "inbox_dlq")
            alert = await cls._upsert_alert(
                session=session,
                workspace_id=workspace_id,
                alert_name="DLQ_BACKLOG_DETECTED",
                alert_type="QUEUE_HEALTH",
                severity="ERROR" if dlq_count > 5 else "WARNING",
                summary=f"Event Dead Letter Queue contains {dlq_count} failed events requiring operator review.",
                details={"dlq_count": dlq_count, "sample_ids": [i.id for i in dlq_items[:5]]},
                fingerprint=fp,
            )
            generated_alerts.append(alert)

        # Rule 2: Unclaimed Queue Latency / Age > 300s
        stale_time = now - timedelta(seconds=300)
        age_stmt = (
            select(EventInboxRecord)
            .where(
                EventInboxRecord.workspace_id == workspace_id,
                EventInboxRecord.status == EventInboxStatus.QUEUED,
                EventInboxRecord.received_at < stale_time,
            )
        )
        age_res = await session.execute(age_stmt)
        stale_items = age_res.scalars().all()
        if stale_items:
            fp = cls.generate_fingerprint("QUEUE_AGE_EXCEEDED", workspace_id, "queue_latency")
            alert = await cls._upsert_alert(
                session=session,
                workspace_id=workspace_id,
                alert_name="QUEUE_AGE_EXCEEDED",
                alert_type="LATENCY",
                severity="WARNING",
                summary=f"{len(stale_items)} queued events have exceeded the 300s processing latency threshold.",
                details={"stale_count": len(stale_items)},
                fingerprint=fp,
            )
            generated_alerts.append(alert)

        # Rule 3: Circuit Breaker Open Alert
        try:
            from app.core.circuit_breaker import circuit_breaker
            open_breakers = [p for p, cb in circuit_breaker._breakers.items() if cb.is_open()]
            for p in open_breakers:
                fp = cls.generate_fingerprint("CIRCUIT_BREAKER_OPEN", workspace_id, p)
                alert = await cls._upsert_alert(
                    session=session,
                    workspace_id=workspace_id,
                    alert_name="CIRCUIT_BREAKER_OPEN",
                    alert_type="PROVIDER_FAILURE",
                    severity="CRITICAL",
                    summary=f"Circuit breaker for provider '{p}' has tripped to OPEN due to consecutive failures.",
                    details={"provider": p, "state": "OPEN"},
                    fingerprint=fp,
                )
                generated_alerts.append(alert)
        except Exception:
            pass

        # Rule 4: Security Alerts from Operational Audit Records
        try:
            from app.models.operational_audit import OperationalAuditRecord
            sec_stmt = (
                select(OperationalAuditRecord)
                .where(
                    OperationalAuditRecord.workspace_id == workspace_id,
                    OperationalAuditRecord.timestamp >= now - timedelta(minutes=15),
                    OperationalAuditRecord.result.in_(["DENIED", "FLAGGED", "FAILED"]),
                )
            )
            sec_res = await session.execute(sec_stmt)
            sec_records = sec_res.scalars().all()

            # Check prompt injections
            injections = [r for r in sec_records if r.error_code == "PROMPT_INJECTION_DETECTED" or "injection" in (r.action or "").lower()]
            if injections:
                fp = cls.generate_fingerprint("PROMPT_INJECTION_DETECTED", workspace_id, "llm_security")
                alert = await cls._upsert_alert(
                    session=session,
                    workspace_id=workspace_id,
                    alert_name="PROMPT_INJECTION_DETECTED",
                    alert_type="SECURITY",
                    severity="WARNING",
                    summary=f"{len(injections)} prompt injection attempts intercepted and defanged in the last 15m.",
                    details={"attempt_count": len(injections), "sample_trace_ids": [r.trace_id for r in injections[:3]]},
                    fingerprint=fp,
                    trace_id=injections[0].trace_id,
                )
                generated_alerts.append(alert)

            # Check cross tenant access attempts
            cross_tenant = [r for r in sec_records if r.error_code == "CROSS_TENANT_ACCESS_ATTEMPT" or "cross_tenant" in (r.action or "").lower()]
            if cross_tenant:
                fp = cls.generate_fingerprint("CROSS_TENANT_ACCESS_ATTEMPT", workspace_id, "auth_isolation")
                alert = await cls._upsert_alert(
                    session=session,
                    workspace_id=workspace_id,
                    alert_name="CROSS_TENANT_ACCESS_ATTEMPT",
                    alert_type="SECURITY",
                    severity="ERROR",
                    summary=f"{len(cross_tenant)} unauthorized cross-workspace resource access attempts detected.",
                    details={"attempt_count": len(cross_tenant), "sample_actor_ids": [r.actor_id for r in cross_tenant[:3]]},
                    fingerprint=fp,
                    trace_id=cross_tenant[0].trace_id,
                )
                generated_alerts.append(alert)
        except Exception:
            pass

        return generated_alerts


    @classmethod
    async def _upsert_alert(
        cls,
        session: AsyncSession,
        workspace_id: str,
        alert_name: str,
        alert_type: str,
        severity: str,
        summary: str,
        details: Dict[str, Any],
        fingerprint: str,
        trace_id: Optional[str] = None,
    ) -> OperationalAlert:
        """Finds open alert by fingerprint or creates a new one."""
        stmt = (
            select(OperationalAlert)
            .where(
                OperationalAlert.workspace_id == workspace_id,
                OperationalAlert.fingerprint == fingerprint,
                OperationalAlert.status.in_(["OPEN", "ACKNOWLEDGED"]),
            )
            .limit(1)
        )
        res = await session.execute(stmt)
        existing = res.scalar()

        if existing:
            existing.summary = summary
            existing.details = details
            existing.severity = severity
            await session.commit()
            return existing

        new_alert = OperationalAlert(
            workspace_id=workspace_id,
            alert_name=alert_name,
            alert_type=alert_type,
            severity=severity,
            status="OPEN",
            summary=summary,
            details=details,
            fingerprint=fingerprint,
            trace_id=trace_id,
        )
        session.add(new_alert)
        await session.commit()
        return new_alert

    @classmethod
    async def transition_status(
        cls,
        alert_id: str,
        action: str,  # "acknowledge", "resolve", "suppress"
        actor_id: str,
        session: AsyncSession,
    ) -> Optional[OperationalAlert]:
        """Transitions alert status according to operator command."""
        alert = await session.get(OperationalAlert, alert_id)
        if not alert:
            return None

        now = datetime.now(timezone.utc)
        action_lower = action.lower()

        if "ack" in action_lower:
            alert.status = "ACKNOWLEDGED"
            alert.acknowledged_by = actor_id
            alert.acknowledged_at = now
        elif "resolve" in action_lower:
            alert.status = "RESOLVED"
            alert.resolved_at = now
        elif "suppress" in action_lower:
            alert.status = "SUPPRESSED"

        await session.commit()
        return alert
