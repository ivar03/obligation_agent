"""
Centralized Enterprise Audit & Governance Service.
Provides authoritative, immutable, tamper-resistant, workspace-scoped audit recording,
querying, hash-chain verification, and compliance exports.
"""

import uuid
import csv
import io
import json
from datetime import datetime, timezone, timedelta
from typing import Optional, List, Dict, Any, Tuple, Union
from sqlalchemy import select, func, desc, asc, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit import AuditEvent
from app.models.auth import User
from app.core.status_machine import AuditAction, AuditSeverity, AuditResult, AuditSource, WorkspaceRole
from app.core.sanitizer import sanitize_for_audit
from app.core.audit_chain import compute_event_hash, verify_event_chain, GENESIS_HASH
from app.core.request_context import (
    get_current_request_id,
    get_current_client_ip,
    get_current_user_agent,
)
from app.schemas.audit import (
    AuditEventResponse,
    AuditListResponse,
    AuditVerificationResponse,
    GovernanceSummaryResponse,
    TopActorMetric,
    EntityTypeMetric,
)


class AuditService:
    """
    Centralized service for logging, querying, and verifying enterprise audit trails.
    """

    @classmethod
    async def get_latest_workspace_event_hash(
        cls,
        session: AsyncSession,
        workspace_id: str,
    ) -> str:
        """
        Retrieves the hash of the most recent audit event in the specified workspace.
        """
        stmt = (
            select(AuditEvent.event_hash)
            .where(AuditEvent.workspace_id == workspace_id)
            .order_by(AuditEvent.timestamp.desc(), AuditEvent.id.desc())
            .limit(1)
        )
        res = await session.execute(stmt)
        latest_hash = res.scalar_one_or_none()
        return latest_hash or GENESIS_HASH

    @classmethod
    async def record(
        cls,
        session: AsyncSession,
        workspace_id: str,
        action: Union[str, AuditAction],
        actor_user_id: Optional[str] = None,
        actor_role: Optional[str] = None,
        entity_type: Optional[str] = None,
        entity_id: Optional[str] = None,
        source: Union[str, AuditSource] = AuditSource.API,
        before_state: Optional[Dict[str, Any]] = None,
        after_state: Optional[Dict[str, Any]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        reason: Optional[str] = None,
        severity: Union[str, AuditSeverity] = AuditSeverity.INFO,
        result: Union[str, AuditResult] = AuditResult.SUCCESS,
        request_id: Optional[str] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        timestamp: Optional[datetime] = None,
    ) -> AuditEvent:
        """
        Primary entry point for appending an immutable, chained audit event.
        """
        event_id = str(uuid.uuid4())
        ts = timestamp or datetime.now(timezone.utc)
        req_id = request_id or get_current_request_id()
        ip = ip_address or get_current_client_ip()
        ua = user_agent or get_current_user_agent()

        action_str = action.value if hasattr(action, "value") else str(action)
        source_str = source.value if hasattr(source, "value") else str(source)
        severity_str = severity.value if hasattr(severity, "value") else str(severity)
        result_str = result.value if hasattr(result, "value") else str(result)

        # 1. Sanitize payload elements to scrub secrets
        safe_before = sanitize_for_audit(before_state) if before_state else None
        safe_after = sanitize_for_audit(after_state) if after_state else None
        safe_meta = sanitize_for_audit(metadata) if metadata else None

        # 2. Get previous event hash in workspace
        previous_hash = await cls.get_latest_workspace_event_hash(session, workspace_id)

        # 3. Compute deterministic event hash
        ev_hash = compute_event_hash(
            previous_hash=previous_hash,
            event_id=event_id,
            workspace_id=workspace_id,
            actor_user_id=actor_user_id,
            actor_role=actor_role,
            action=action_str,
            entity_type=entity_type,
            entity_id=entity_id,
            timestamp=ts,
            request_id=req_id,
            source=source_str,
            before_state=safe_before,
            after_state=safe_after,
            audit_metadata=safe_meta,
            reason=reason,
            severity=severity_str,
            result=result_str,
        )

        # 4. Construct AuditEvent model
        event = AuditEvent(
            id=event_id,
            workspace_id=workspace_id,
            actor_user_id=actor_user_id,
            actor_role=actor_role,
            action=action_str,
            entity_type=entity_type,
            entity_id=entity_id,
            timestamp=ts,
            request_id=req_id,
            source=source_str,
            ip_address=ip,
            user_agent=ua,
            before_state=safe_before,
            after_state=safe_after,
            audit_metadata=safe_meta,
            reason=reason,
            severity=severity_str,
            result=result_str,
            previous_event_hash=previous_hash if previous_hash != GENESIS_HASH else None,
            event_hash=ev_hash,
        )

        session.add(event)
        await session.flush()
        return event

    @classmethod
    async def record_mutation(
        cls,
        session: AsyncSession,
        workspace_id: str,
        action: Union[str, AuditAction],
        actor_user_id: Optional[str],
        actor_role: Optional[str],
        entity_type: str,
        entity_id: str,
        before_state: Optional[Dict[str, Any]] = None,
        after_state: Optional[Dict[str, Any]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        reason: Optional[str] = None,
        source: Union[str, AuditSource] = AuditSource.API,
    ) -> AuditEvent:
        """
        Records a domain state mutation with before/after state diff.
        """
        return await cls.record(
            session=session,
            workspace_id=workspace_id,
            action=action,
            actor_user_id=actor_user_id,
            actor_role=actor_role,
            entity_type=entity_type,
            entity_id=entity_id,
            source=source,
            before_state=before_state,
            after_state=after_state,
            metadata=metadata,
            reason=reason,
            severity=AuditSeverity.INFO,
            result=AuditResult.SUCCESS,
        )

    @classmethod
    async def record_security_event(
        cls,
        session: AsyncSession,
        workspace_id: str,
        action: Union[str, AuditAction],
        actor_user_id: Optional[str] = None,
        actor_role: Optional[str] = None,
        entity_type: Optional[str] = None,
        entity_id: Optional[str] = None,
        reason: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        severity: Union[str, AuditSeverity] = AuditSeverity.WARNING,
        result: Union[str, AuditResult] = AuditResult.DENIED,
    ) -> AuditEvent:
        """
        Records an authorization denial or cross-tenant security anomaly.
        """
        return await cls.record(
            session=session,
            workspace_id=workspace_id,
            action=action,
            actor_user_id=actor_user_id,
            actor_role=actor_role,
            entity_type=entity_type,
            entity_id=entity_id,
            source=AuditSource.API,
            reason=reason,
            metadata=metadata,
            severity=severity,
            result=result,
        )

    @classmethod
    async def record_auth_event(
        cls,
        session: AsyncSession,
        workspace_id: str,
        action: Union[str, AuditAction],
        actor_user_id: Optional[str] = None,
        email: Optional[str] = None,
        result: Union[str, AuditResult] = AuditResult.SUCCESS,
        reason: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> AuditEvent:
        """
        Records an authentication lifecycle event (login, failed login, logout).
        """
        severity = AuditSeverity.INFO if result == AuditResult.SUCCESS else AuditSeverity.WARNING
        meta = metadata or {}
        if email:
            meta["email"] = email

        return await cls.record(
            session=session,
            workspace_id=workspace_id,
            action=action,
            actor_user_id=actor_user_id,
            actor_role="USER",
            entity_type="user",
            entity_id=actor_user_id,
            source=AuditSource.API,
            metadata=meta,
            reason=reason,
            severity=severity,
            result=result,
        )

    @classmethod
    async def get_workspace_events(
        cls,
        session: AsyncSession,
        workspace_id: str,
        action: Optional[str] = None,
        actor_user_id: Optional[str] = None,
        entity_type: Optional[str] = None,
        entity_id: Optional[str] = None,
        severity: Optional[str] = None,
        result: Optional[str] = None,
        request_id: Optional[str] = None,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> Tuple[List[AuditEventResponse], int]:
        """
        Queries paginated workspace audit events with filtering.
        """
        filters = [AuditEvent.workspace_id == workspace_id]

        if action:
            filters.append(AuditEvent.action == action)
        if actor_user_id:
            filters.append(AuditEvent.actor_user_id == actor_user_id)
        if entity_type:
            filters.append(AuditEvent.entity_type == entity_type)
        if entity_id:
            filters.append(AuditEvent.entity_id == entity_id)
        if severity:
            filters.append(AuditEvent.severity == severity)
        if result:
            filters.append(AuditEvent.result == result)
        if request_id:
            filters.append(AuditEvent.request_id == request_id)
        if date_from:
            filters.append(AuditEvent.timestamp >= date_from)
        if date_to:
            filters.append(AuditEvent.timestamp <= date_to)

        # Count query
        count_stmt = select(func.count(AuditEvent.id)).where(and_(*filters))
        total_res = await session.execute(count_stmt)
        total = total_res.scalar_one() or 0

        # Items query
        stmt = (
            select(AuditEvent)
            .where(and_(*filters))
            .order_by(AuditEvent.timestamp.desc(), AuditEvent.id.desc())
            .limit(limit)
            .offset(offset)
        )
        res = await session.execute(stmt)
        events = res.scalars().all()

        # Map to response models with actor details
        items = []
        for ev in events:
            actor_name = ev.actor.display_name if ev.actor else ("System" if ev.source == "SYSTEM_WORKER" else None)
            actor_email = ev.actor.email if ev.actor else None
            items.append(
                AuditEventResponse(
                    id=ev.id,
                    workspace_id=ev.workspace_id,
                    actor_user_id=ev.actor_user_id,
                    actor_name=actor_name,
                    actor_email=actor_email,
                    actor_role=ev.actor_role,
                    action=ev.action,
                    entity_type=ev.entity_type,
                    entity_id=ev.entity_id,
                    timestamp=ev.timestamp,
                    request_id=ev.request_id,
                    source=ev.source,
                    ip_address=ev.ip_address,
                    user_agent=ev.user_agent,
                    before_state=ev.before_state,
                    after_state=ev.after_state,
                    audit_metadata=ev.audit_metadata,
                    reason=ev.reason,
                    severity=ev.severity,
                    result=ev.result,
                    previous_event_hash=ev.previous_event_hash,
                    event_hash=ev.event_hash,
                )
            )

        return items, total

    @classmethod
    async def get_entity_history(
        cls,
        session: AsyncSession,
        workspace_id: str,
        entity_type: str,
        entity_id: str,
    ) -> List[AuditEventResponse]:
        """
        Retrieves the chronological audit history for a specific domain entity.
        """
        stmt = (
            select(AuditEvent)
            .where(
                AuditEvent.workspace_id == workspace_id,
                AuditEvent.entity_type == entity_type,
                AuditEvent.entity_id == entity_id,
            )
            .order_by(AuditEvent.timestamp.asc(), AuditEvent.id.asc())
        )
        res = await session.execute(stmt)
        events = res.scalars().all()

        items = []
        for ev in events:
            actor_name = ev.actor.display_name if ev.actor else ("System" if ev.source == "SYSTEM_WORKER" else None)
            actor_email = ev.actor.email if ev.actor else None
            items.append(
                AuditEventResponse(
                    id=ev.id,
                    workspace_id=ev.workspace_id,
                    actor_user_id=ev.actor_user_id,
                    actor_name=actor_name,
                    actor_email=actor_email,
                    actor_role=ev.actor_role,
                    action=ev.action,
                    entity_type=ev.entity_type,
                    entity_id=ev.entity_id,
                    timestamp=ev.timestamp,
                    request_id=ev.request_id,
                    source=ev.source,
                    ip_address=ev.ip_address,
                    user_agent=ev.user_agent,
                    before_state=ev.before_state,
                    after_state=ev.after_state,
                    audit_metadata=ev.audit_metadata,
                    reason=ev.reason,
                    severity=ev.severity,
                    result=ev.result,
                    previous_event_hash=ev.previous_event_hash,
                    event_hash=ev.event_hash,
                )
            )
        return items

    @classmethod
    async def verify_chain(
        cls,
        session: AsyncSession,
        workspace_id: str,
    ) -> AuditVerificationResponse:
        """
        Verifies the complete cryptographic hash chain for the given workspace.
        """
        stmt = (
            select(AuditEvent)
            .where(AuditEvent.workspace_id == workspace_id)
            .order_by(AuditEvent.timestamp.asc(), AuditEvent.id.asc())
        )
        res = await session.execute(stmt)
        events = res.scalars().all()

        verification = verify_event_chain(events)
        return AuditVerificationResponse(
            workspace_id=workspace_id,
            chain_valid=verification["chain_valid"],
            status=verification["status"],
            verified_event_count=verification["verified_event_count"],
            broken_at_event_id=verification["broken_at_event_id"],
            expected_hash=verification["expected_hash"],
            actual_hash=verification["actual_hash"],
            message=verification["message"],
        )

    @classmethod
    async def get_governance_summary(
        cls,
        session: AsyncSession,
        workspace_id: str,
    ) -> GovernanceSummaryResponse:
        """
        Computes aggregated operational governance metrics for the workspace.
        """
        now = datetime.now(timezone.utc)
        start_of_today = datetime(now.year, now.month, now.day, tzinfo=timezone.utc)

        # 1. Total events count
        total_stmt = select(func.count(AuditEvent.id)).where(AuditEvent.workspace_id == workspace_id)
        total_events = (await session.execute(total_stmt)).scalar_one() or 0

        # 2. Events today
        today_stmt = select(func.count(AuditEvent.id)).where(
            AuditEvent.workspace_id == workspace_id,
            AuditEvent.timestamp >= start_of_today,
        )
        events_today = (await session.execute(today_stmt)).scalar_one() or 0

        # 3. Security events count
        sec_stmt = select(func.count(AuditEvent.id)).where(
            AuditEvent.workspace_id == workspace_id,
            AuditEvent.action.in_([
                AuditAction.PERMISSION_DENIED.value,
                AuditAction.SECURITY_VIOLATION.value,
                AuditAction.AUTH_LOGIN_FAILED.value,
            ]),
        )
        security_events_count = (await session.execute(sec_stmt)).scalar_one() or 0

        # 4. Specific counts
        denial_stmt = select(func.count(AuditEvent.id)).where(
            AuditEvent.workspace_id == workspace_id,
            AuditEvent.action == AuditAction.PERMISSION_DENIED.value,
        )
        permission_denials_count = (await session.execute(denial_stmt)).scalar_one() or 0

        failed_login_stmt = select(func.count(AuditEvent.id)).where(
            AuditEvent.workspace_id == workspace_id,
            AuditEvent.action == AuditAction.AUTH_LOGIN_FAILED.value,
        )
        failed_logins_count = (await session.execute(failed_login_stmt)).scalar_one() or 0

        human_stmt = select(func.count(AuditEvent.id)).where(
            AuditEvent.workspace_id == workspace_id,
            AuditEvent.actor_user_id.isnot(None),
            AuditEvent.source != "SYSTEM_WORKER",
        )
        human_actions_count = (await session.execute(human_stmt)).scalar_one() or 0

        system_stmt = select(func.count(AuditEvent.id)).where(
            AuditEvent.workspace_id == workspace_id,
            AuditEvent.source == "SYSTEM_WORKER",
        )
        system_events_count = (await session.execute(system_stmt)).scalar_one() or 0

        # Interventions approved / executed
        appr_stmt = select(func.count(AuditEvent.id)).where(
            AuditEvent.workspace_id == workspace_id,
            AuditEvent.action == AuditAction.INTERVENTION_APPROVED.value,
        )
        interventions_approved_count = (await session.execute(appr_stmt)).scalar_one() or 0

        exec_stmt = select(func.count(AuditEvent.id)).where(
            AuditEvent.workspace_id == workspace_id,
            AuditEvent.action == AuditAction.INTERVENTION_EXECUTED.value,
        )
        interventions_executed_count = (await session.execute(exec_stmt)).scalar_one() or 0

        # Evidence confirmations
        conf_stmt = select(func.count(AuditEvent.id)).where(
            AuditEvent.workspace_id == workspace_id,
            AuditEvent.action == AuditAction.EVIDENCE_CONFIRMED.value,
        )
        evidence_confirmations_count = (await session.execute(conf_stmt)).scalar_one() or 0

        # Reconciliation decisions
        rec_stmt = select(func.count(AuditEvent.id)).where(
            AuditEvent.workspace_id == workspace_id,
            AuditEvent.action == AuditAction.RECONCILIATION_RESOLVED.value,
        )
        reconciliation_decisions_count = (await session.execute(rec_stmt)).scalar_one() or 0

        # Mutations today
        mut_today_stmt = select(func.count(AuditEvent.id)).where(
            AuditEvent.workspace_id == workspace_id,
            AuditEvent.timestamp >= start_of_today,
            AuditEvent.action.like("%_CREATED")
            | AuditEvent.action.like("%_UPDATED")
            | AuditEvent.action.like("%_DELETED")
            | AuditEvent.action.like("%_RESOLVED")
            | AuditEvent.action.like("%_APPROVED")
            | AuditEvent.action.like("%_EXECUTED")
            | AuditEvent.action.like("%_CONFIRMED"),
        )
        mutations_today = (await session.execute(mut_today_stmt)).scalar_one() or 0

        # Top actors by mutation count
        actor_stmt = (
            select(
                AuditEvent.actor_user_id,
                func.count(AuditEvent.id).label("mut_count"),
            )
            .where(
                AuditEvent.workspace_id == workspace_id,
                AuditEvent.actor_user_id.isnot(None),
            )
            .group_by(AuditEvent.actor_user_id)
            .order_by(desc("mut_count"))
            .limit(5)
        )
        actor_rows = (await session.execute(actor_stmt)).all()
        top_actors = []
        for uid, count in actor_rows:
            user_obj = await session.get(User, uid) if uid else None
            top_actors.append(
                TopActorMetric(
                    actor_user_id=uid,
                    actor_name=user_obj.display_name if user_obj else "Unknown User",
                    actor_email=user_obj.email if user_obj else None,
                    mutation_count=count,
                )
            )

        # Most modified entity types
        entity_stmt = (
            select(
                AuditEvent.entity_type,
                func.count(AuditEvent.id).label("ent_count"),
            )
            .where(
                AuditEvent.workspace_id == workspace_id,
                AuditEvent.entity_type.isnot(None),
            )
            .group_by(AuditEvent.entity_type)
            .order_by(desc("ent_count"))
            .limit(5)
        )
        ent_rows = (await session.execute(entity_stmt)).all()
        most_modified = [
            EntityTypeMetric(entity_type=etype, mutation_count=count)
            for etype, count in ent_rows if etype
        ]

        # Recent security events (last 5)
        recent_sec_stmt = (
            select(AuditEvent)
            .where(
                AuditEvent.workspace_id == workspace_id,
                AuditEvent.action.in_([
                    AuditAction.PERMISSION_DENIED.value,
                    AuditAction.SECURITY_VIOLATION.value,
                    AuditAction.AUTH_LOGIN_FAILED.value,
                ]),
            )
            .order_by(AuditEvent.timestamp.desc(), AuditEvent.id.desc())
            .limit(5)
        )
        recent_sec_events = (await session.execute(recent_sec_stmt)).scalars().all()
        sec_items = []
        for ev in recent_sec_events:
            sec_items.append(
                AuditEventResponse(
                    id=ev.id,
                    workspace_id=ev.workspace_id,
                    actor_user_id=ev.actor_user_id,
                    actor_name=ev.actor.display_name if ev.actor else None,
                    actor_email=ev.actor.email if ev.actor else None,
                    actor_role=ev.actor_role,
                    action=ev.action,
                    entity_type=ev.entity_type,
                    entity_id=ev.entity_id,
                    timestamp=ev.timestamp,
                    request_id=ev.request_id,
                    source=ev.source,
                    ip_address=ev.ip_address,
                    user_agent=ev.user_agent,
                    before_state=ev.before_state,
                    after_state=ev.after_state,
                    audit_metadata=ev.audit_metadata,
                    reason=ev.reason,
                    severity=ev.severity,
                    result=ev.result,
                    previous_event_hash=ev.previous_event_hash,
                    event_hash=ev.event_hash,
                )
            )

        # Fast chain integrity verification
        ver_res = await cls.verify_chain(session, workspace_id)

        return GovernanceSummaryResponse(
            workspace_id=workspace_id,
            total_audit_events=total_events,
            events_today=events_today,
            mutations_today=mutations_today,
            security_events_count=security_events_count,
            permission_denials_count=permission_denials_count,
            failed_logins_count=failed_logins_count,
            human_actions_count=human_actions_count,
            system_events_count=system_events_count,
            interventions_approved_count=interventions_approved_count,
            interventions_executed_count=interventions_executed_count,
            evidence_confirmations_count=evidence_confirmations_count,
            reconciliation_decisions_count=reconciliation_decisions_count,
            top_actors=top_actors,
            most_modified_entities=most_modified,
            recent_security_events=sec_items,
            chain_integrity_status=ver_res.status,
        )

    @classmethod
    async def export_audit_log(
        cls,
        session: AsyncSession,
        workspace_id: str,
        export_format: str = "json",
        action: Optional[str] = None,
        entity_type: Optional[str] = None,
        severity: Optional[str] = None,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None,
    ) -> Tuple[str, str]:
        """
        Exports sanitized workspace audit records as a CSV string or JSON string.
        Returns: (content_str, mime_type)
        """
        events, _ = await cls.get_workspace_events(
            session=session,
            workspace_id=workspace_id,
            action=action,
            entity_type=entity_type,
            severity=severity,
            date_from=date_from,
            date_to=date_to,
            limit=5000,
            offset=0,
        )

        if export_format.lower() == "csv":
            output = io.StringIO()
            fieldnames = [
                "id",
                "workspace_id",
                "timestamp",
                "action",
                "actor_user_id",
                "actor_name",
                "actor_role",
                "entity_type",
                "entity_id",
                "source",
                "severity",
                "result",
                "reason",
                "request_id",
                "previous_event_hash",
                "event_hash",
            ]
            writer = csv.DictWriter(output, fieldnames=fieldnames, extrasaction="ignore")
            writer.writeheader()
            for ev in events:
                row = ev.model_dump()
                row["timestamp"] = ev.timestamp.isoformat()
                writer.writerow(row)
            return output.getvalue(), "text/csv"

        # JSON format
        json_records = [ev.model_dump(mode="json") for ev in events]
        return json.dumps(
            {
                "workspace_id": workspace_id,
                "exported_at": datetime.now(timezone.utc).isoformat(),
                "total_records": len(json_records),
                "records": json_records,
            },
            indent=2,
        ), "application/json"
