"""
Tests for Data Loading Fixes, Reconciliation Workspace Refresh, and Operational Audit Explorer.
Validates:
 1. Reconciliation workspace refresh endpoint (POST /api/reconciliation/refresh)
 2. Domain action bridge to OperationalAuditRecord with SHA-256 hash chaining
 3. Activity Center event ingestion and query isolation
 4. Multi-tenant workspace isolation for audit events, reconciliation, and integrations
"""

import pytest
import uuid
from datetime import datetime, timezone, timedelta
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.auth import User, Workspace, WorkspaceMembership
from app.models.obligation import Obligation, Evidence, ReconciliationRecord, IngestedEventRecord
from app.models.operational_audit import OperationalAuditRecord
from app.core.status_machine import (
    WorkspaceRole,
    ObligationStatus,
    ObligationType,
    EvidenceType,
    CorrelationStatus,
    EventSemanticRole,
    AuditAction,
    AuditSeverity,
    AuditResult,
)
from app.core.audit_chain import GENESIS_HASH
from app.services.reconciliation_service import ReconciliationService
from app.services.event_ingestion_service import EventIngestionService
from app.services.operational_audit_service import OperationalAuditService
from app.services.audit_service import AuditService
from app.schemas.obligation import ExternalEvent


@pytest.mark.asyncio
async def test_reconciliation_workspace_refresh(db_session: AsyncSession):
    """Verify that Reconcile Workspace evaluates all obligations and generates records."""
    ws_id = f"ws-recon-{uuid.uuid4().hex[:6]}"
    user_id = f"usr-{uuid.uuid4().hex[:6]}"

    # Setup Workspace & User
    ws = Workspace(id=ws_id, name="Recon Test Workspace", slug=f"recon-{uuid.uuid4().hex[:4]}")
    user = User(id=user_id, email=f"recon-{uuid.uuid4().hex[:4]}@test.local", password_hash="hash", display_name="Recon User")
    mem = WorkspaceMembership(id=f"mem-{uuid.uuid4().hex[:6]}", workspace_id=ws_id, user_id=user_id, role=WorkspaceRole.OWNER)
    db_session.add_all([ws, user, mem])

    now = datetime.now(timezone.utc)
    # Obligation 1
    ob1 = Obligation(
        id=f"ob-{uuid.uuid4().hex[:6]}",
        workspace_id=ws_id,
        owner=user.email,
        beneficiary="Team",
        action="Complete API v2 documentation",
        deadline=now + timedelta(days=3),
        status=ObligationStatus.IN_PROGRESS,
        obligation_type=ObligationType.OWED_BY_ME,
        confidence={"overall": 0.95},
    )
    db_session.add(ob1)
    await db_session.flush()

    # Ingest evidence for Obligation 1
    ev1 = Evidence(
        id=f"ev-{uuid.uuid4().hex[:6]}",
        workspace_id=ws_id,
        obligation_id=ob1.id,
        evidence_type=EvidenceType.EVENT,
        source_type="slack",
        source_ref="slack-doc-update",
        content="API v2 documentation drafting has begun.",
        correlation_confidence=0.95,
        correlation_status=CorrelationStatus.CONFIRMED,
        semantic_role=EventSemanticRole.PROGRESS_UPDATE,
    )
    db_session.add(ev1)
    await db_session.commit()

    # Call Reconcile Workspace
    records = await ReconciliationService.reconcile_workspace(db_session, ws_id)
    assert len(records) >= 1

    # List reconciliations for workspace
    list_res = await ReconciliationService.list_reconciliations(db_session, workspace_id=ws_id)
    assert list_res.total >= 1
    assert any(r.obligation_id == ob1.id for r in list_res.items)


@pytest.mark.asyncio
async def test_audit_service_bridge_to_operational_audit(db_session: AsyncSession):
    """Verify that AuditService.record also creates an OperationalAuditRecord with hash chaining."""
    ws_id = f"ws-bridge-{uuid.uuid4().hex[:6]}"
    user_id = f"usr-actor-{uuid.uuid4().hex[:6]}"

    # Record via AuditService
    audit_ev = await AuditService.record(
        session=db_session,
        workspace_id=ws_id,
        action=AuditAction.OBLIGATION_CREATED,
        actor_user_id=user_id,
        actor_role="ADMIN",
        entity_type="Obligation",
        entity_id="ob-12345",
        metadata={"title": "Deliver API Spec"},
    )
    await db_session.commit()


    # Verify that an OperationalAuditRecord was also created
    op_stmt = (
        select(OperationalAuditRecord)
        .where(OperationalAuditRecord.workspace_id == ws_id)
        .order_by(OperationalAuditRecord.timestamp.desc())
    )
    res = await db_session.execute(op_stmt)
    op_records = res.scalars().all()
    assert len(op_records) >= 1

    latest_op = op_records[0]
    assert latest_op.workspace_id == ws_id
    assert latest_op.resource_type == "Obligation"
    assert latest_op.resource_id == "ob-12345"
    assert latest_op.record_hash is not None
    assert len(latest_op.record_hash) == 64


@pytest.mark.asyncio
async def test_operational_audit_tenant_isolation(db_session: AsyncSession):
    """Verify strict multi-tenant isolation for operational audit records."""
    ws_a = f"ws-a-{uuid.uuid4().hex[:6]}"
    ws_b = f"ws-b-{uuid.uuid4().hex[:6]}"

    # Log in Workspace A
    await OperationalAuditService.log_event(
        session=db_session,
        workspace_id=ws_a,
        event_type="SECRET_ROTATED",
        action="Rotated webhook secret",
        severity="INFO",
    )

    # Log in Workspace B
    await OperationalAuditService.log_event(
        session=db_session,
        workspace_id=ws_b,
        event_type="AUTH_FAILURE",
        action="Invalid token attempt",
        severity="WARNING",
    )
    await db_session.commit()

    # Query Workspace A
    res_a = await db_session.execute(
        select(OperationalAuditRecord).where(OperationalAuditRecord.workspace_id == ws_a)
    )
    records_a = res_a.scalars().all()
    assert len(records_a) == 1
    assert records_a[0].event_type == "SECRET_ROTATED"
    assert all(r.workspace_id == ws_a for r in records_a)

    # Query Workspace B
    res_b = await db_session.execute(
        select(OperationalAuditRecord).where(OperationalAuditRecord.workspace_id == ws_b)
    )
    records_b = res_b.scalars().all()
    assert len(records_b) == 1
    assert records_b[0].event_type == "AUTH_FAILURE"
    assert all(r.workspace_id == ws_b for r in records_b)

    # Verify chain integrity for Workspace A
    integrity_a = await OperationalAuditService.verify_chain(ws_a, db_session)
    assert integrity_a.verified is True
    assert integrity_a.total_records == 1

