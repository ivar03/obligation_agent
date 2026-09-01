"""
Phase 21 Automated Test Suite: Observability, Operational Audit & System-Wide Traceability.

Tests:
1. Unified correlation and trace context propagation.
2. Operational audit logging with SHA-256 hash chaining.
3. Cryptographic hash-chain integrity and tamper detection.
4. Multi-tenant workspace isolation for audit logs.
5. Sensitive metadata and token redaction.
6. System-wide trace graph reconstruction.
7. Deterministic alert rule evaluation and lifecycle management.
8. SLO compliance and error-budget calculation (including INSUFFICIENT_DATA).
9. Preservation of safety invariants (zero state mutation by observability).
"""

import pytest
import asyncio
from datetime import datetime, timezone
from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

from app.core.database import Base
from app.core.request_context import (
    request_id_ctx,
    trace_id_ctx,
    span_id_ctx,
    get_current_request_id,
    get_current_trace_id,
    get_current_span_id,
    set_trace_context,
)
from app.core.trace_context import traced_span
from app.models.auth import Workspace, User
from app.models.event_inbox import EventInboxRecord, EventInboxStatus
from app.models.operational_audit import OperationalAuditRecord
from app.models.operational_alert import OperationalAlert
from app.services.operational_audit_service import OperationalAuditService, GENESIS_HASH
from app.services.trace_service import TraceService
from app.services.alert_engine import AlertEngine
from app.services.slo_engine import SLOEngine
from app.schemas.observability import SLOStatus


@pytest.fixture(scope="function")
async def test_db():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with async_session() as session:
        # Create workspaces
        ws_a = Workspace(id="ws-alpha", name="Workspace Alpha", slug="ws-alpha")
        ws_b = Workspace(id="ws-beta", name="Workspace Beta", slug="ws-beta")
        session.add_all([ws_a, ws_b])
        await session.commit()
        yield session


    await engine.dispose()


@pytest.mark.asyncio
async def test_trace_context_propagation():
    """Verify trace_id, span_id, and request_id propagation across sync/async contexts."""
    set_trace_context(trace_id="trace-12345", span_id="span-abc", request_id="req-999")

    assert get_current_trace_id() == "trace-12345"
    assert get_current_span_id() == "span-abc"
    assert get_current_request_id() == "req-999"

    @traced_span(span_name="test_operation", component="TEST")
    async def sub_operation():
        assert get_current_trace_id() == "trace-12345"
        nested_span = get_current_span_id()
        assert nested_span is not None
        assert nested_span != "span-abc"
        return True

    res = await sub_operation()
    assert res is True
    # Context reverts after span
    assert get_current_span_id() == "span-abc"


@pytest.mark.asyncio
async def test_operational_audit_hash_chaining(test_db: AsyncSession):
    """Verify append-only operational audit logging with SHA-256 hash chaining."""
    rec1 = await OperationalAuditService.log_event(
        session=test_db,
        workspace_id="ws-alpha",
        event_type="WEBHOOK_ACCEPTED",
        action="Slack webhook received",
        trace_id="tr-100",
    )
    assert rec1.previous_hash == GENESIS_HASH
    assert len(rec1.record_hash) == 64

    rec2 = await OperationalAuditService.log_event(
        session=test_db,
        workspace_id="ws-alpha",
        event_type="EVENT_QUEUED",
        action="Dispatched to inbox queue",
        trace_id="tr-100",
    )
    assert rec2.previous_hash == rec1.record_hash
    assert len(rec2.record_hash) == 64

    rec3 = await OperationalAuditService.log_event(
        session=test_db,
        workspace_id="ws-alpha",
        event_type="EVENT_PROCESSED",
        action="Event processed by worker",
        trace_id="tr-100",
    )
    assert rec3.previous_hash == rec2.record_hash

    # Verify cryptographic integrity
    integrity = await OperationalAuditService.verify_chain("ws-alpha", test_db)
    assert integrity.verified is True
    assert integrity.total_records == 3
    assert integrity.intact_records == 3
    assert integrity.corrupted_records == 0


@pytest.mark.asyncio
async def test_audit_tamper_detection(test_db: AsyncSession):
    """Verify that tampering with an audit record fails cryptographic verification."""
    rec1 = await OperationalAuditService.log_event(
        session=test_db,
        workspace_id="ws-alpha",
        event_type="AUTHENTICATION_FAILURE",
        action="Failed password attempt",
    )
    rec2 = await OperationalAuditService.log_event(
        session=test_db,
        workspace_id="ws-alpha",
        event_type="AUTHORIZATION_DENIED",
        action="Denied access to admin settings",
    )

    # Integrity should pass before tampering
    res_before = await OperationalAuditService.verify_chain("ws-alpha", test_db)
    assert res_before.verified is True

    # Tamper with rec1 action
    rec1.action = "Tampered action unauthorized"
    await test_db.commit()

    # Integrity should FAIL and flag rec1
    res_after = await OperationalAuditService.verify_chain("ws-alpha", test_db)
    assert res_after.verified is False
    assert res_after.corrupted_records >= 1
    assert rec1.id in res_after.tampered_record_ids


@pytest.mark.asyncio
async def test_audit_metadata_credential_redaction(test_db: AsyncSession):
    """Verify sensitive tokens and keys are sanitized from audit metadata."""
    dirty_metadata = {
        "user_email": "operator@example.com",
        "slack_token": "xoxb-12345-67890-abcdef",
        "api_key": "sk-proj-secret-12345",
        "password": "SuperSecretPassword123!",
    }

    rec = await OperationalAuditService.log_event(
        session=test_db,
        workspace_id="ws-alpha",
        event_type="PROVIDER_CONNECTED",
        action="Connected Slack Integration",
        metadata=dirty_metadata,
    )

    clean_meta = rec.metadata_json
    assert clean_meta["user_email"] == "operator@example.com"
    assert clean_meta["slack_token"] == "[REDACTED]"
    assert clean_meta["api_key"] == "[REDACTED]"
    assert clean_meta["password"] == "[REDACTED]"


@pytest.mark.asyncio
async def test_multi_tenant_audit_isolation(test_db: AsyncSession):
    """Verify tenant isolation between workspace audit chains."""
    await OperationalAuditService.log_event(
        session=test_db,
        workspace_id="ws-alpha",
        event_type="ADMIN_ACTION",
        action="Alpha admin action",
    )
    await OperationalAuditService.log_event(
        session=test_db,
        workspace_id="ws-beta",
        event_type="ADMIN_ACTION",
        action="Beta admin action",
    )

    res_alpha = await OperationalAuditService.verify_chain("ws-alpha", test_db)
    res_beta = await OperationalAuditService.verify_chain("ws-beta", test_db)

    assert res_alpha.total_records == 1
    assert res_beta.total_records == 1


@pytest.mark.asyncio
async def test_trace_graph_reconstruction(test_db: AsyncSession):
    """Verify system-wide trace graph reconstruction across inbox and audits."""
    tr_id = "trace-flow-xyz"

    # Add inbox event
    ev = EventInboxRecord(
        workspace_id="ws-alpha",
        correlation_id=tr_id,
        source_ref=tr_id,
        provider="slack",
        event_type="message",
        payload_hash="hash-12345",
        stream_key="slack:channel",
        status=EventInboxStatus.PROCESSED,
        processing_duration_ms=45.5,
    )
    test_db.add(ev)


    # Add audit log
    await OperationalAuditService.log_event(
        session=test_db,
        workspace_id="ws-alpha",
        event_type="WEBHOOK_ACCEPTED",
        action="Slack Webhook Intake",
        trace_id=tr_id,
    )
    await test_db.commit()

    graph = await TraceService.reconstruct_trace(tr_id, "ws-alpha", test_db)
    assert graph.trace_id == tr_id
    assert graph.node_count >= 2
    assert graph.is_complete is True


@pytest.mark.asyncio
async def test_deterministic_alerting_rules(test_db: AsyncSession):
    """Verify deterministic alert generation when DLQ has failed items."""
    # 1. Add DLQ event
    dlq_ev = EventInboxRecord(
        workspace_id="ws-alpha",
        correlation_id="tr-dlq",
        source_ref="tr-dlq",
        provider="slack",
        event_type="message",
        payload_hash="hash-dlq-123",
        stream_key="slack:channel",
        status=EventInboxStatus.DEAD_LETTER,
        last_error="Max retry limit reached",
        attempt_count=5,
    )
    test_db.add(dlq_ev)
    await test_db.commit()


    # 2. Evaluate alert rules
    alerts = await AlertEngine.evaluate_rules("ws-alpha", test_db)
    assert len(alerts) >= 1
    assert alerts[0].alert_name == "DLQ_BACKLOG_DETECTED"
    assert alerts[0].status == "OPEN"

    # 3. Transition alert lifecycle
    ack_alert = await AlertEngine.transition_status(
        alert_id=alerts[0].id,
        action="acknowledge",
        actor_id="test-operator",
        session=test_db,
    )
    assert ack_alert.status == "ACKNOWLEDGED"

    res_alert = await AlertEngine.transition_status(
        alert_id=alerts[0].id,
        action="resolve",
        actor_id="test-operator",
        session=test_db,
    )
    assert res_alert.status == "RESOLVED"


@pytest.mark.asyncio
async def test_slo_engine_evaluations(test_db: AsyncSession):
    """Verify SLO evaluation returns INSUFFICIENT_DATA when sample counts are low."""
    slis, budgets = await SLOEngine.evaluate_slos("ws-alpha", test_db)
    assert len(slis) >= 3
    assert len(budgets) >= 3

    # With zero samples, status must be INSUFFICIENT_DATA (never fabricated)
    for s in slis:
        assert s.status == SLOStatus.INSUFFICIENT_DATA
        assert s.actual_percentage is None


@pytest.mark.asyncio
async def test_alert_deduplication_via_fingerprint(test_db: AsyncSession):
    """Verify that multiple rule evaluations do not duplicate open alerts with identical fingerprints."""
    dlq_ev = EventInboxRecord(
        workspace_id="ws-alpha",
        correlation_id="tr-dlq-dup",
        source_ref="tr-dlq-dup",
        provider="slack",
        event_type="message",
        payload_hash="hash-dup-123",
        stream_key="slack:channel",
        status=EventInboxStatus.DEAD_LETTER,
        last_error="Timeout",
        attempt_count=5,
    )
    test_db.add(dlq_ev)
    await test_db.commit()

    # First evaluation creates alert
    alerts1 = await AlertEngine.evaluate_rules("ws-alpha", test_db)
    assert len(alerts1) == 1
    alert_id1 = alerts1[0].id

    # Second evaluation reuses existing alert
    alerts2 = await AlertEngine.evaluate_rules("ws-alpha", test_db)
    assert len(alerts2) == 1
    assert alerts2[0].id == alert_id1


@pytest.mark.asyncio
async def test_alert_suppression(test_db: AsyncSession):
    """Verify alert status transition to SUPPRESSED."""
    dlq_ev = EventInboxRecord(
        workspace_id="ws-alpha",
        correlation_id="tr-dlq-sup",
        source_ref="tr-dlq-sup",
        provider="slack",
        event_type="message",
        payload_hash="hash-sup-123",
        stream_key="slack:channel",
        status=EventInboxStatus.DEAD_LETTER,
        last_error="Timeout",
        attempt_count=5,
    )
    test_db.add(dlq_ev)
    await test_db.commit()

    alerts = await AlertEngine.evaluate_rules("ws-alpha", test_db)
    suppressed = await AlertEngine.transition_status(
        alert_id=alerts[0].id,
        action="suppress",
        actor_id="operator-1",
        session=test_db,
    )
    assert suppressed.status == "SUPPRESSED"


@pytest.mark.asyncio
async def test_slo_evaluation_with_samples(test_db: AsyncSession):
    """Verify real SLO calculations and error-budget consumption with sufficient samples."""
    # Add 10 processed events and 0 DLQ events -> 100% success rate
    for i in range(10):
        ev = EventInboxRecord(
            workspace_id="ws-alpha",
            correlation_id=f"tr-sample-{i}",
            source_ref=f"ref-{i}",
            provider="slack",
            event_type="message",
            payload_hash=f"hash-sample-{i}",
            stream_key="slack:channel",
            status=EventInboxStatus.PROCESSED,
        )
        test_db.add(ev)
    await test_db.commit()

    slis, budgets = await SLOEngine.evaluate_slos("ws-alpha", test_db)
    ev_sli = next(s for s in slis if s.category == "EVENT_PROCESSING")
    assert ev_sli.status == SLOStatus.HEALTHY
    assert ev_sli.actual_percentage == 100.0
    assert ev_sli.sample_count == 10

    ev_budget = next(b for b in budgets if b.slo_name == "Event Processing Success Rate")
    assert ev_budget.status == SLOStatus.HEALTHY
    assert ev_budget.consumed_percentage == 0.0
    assert ev_budget.remaining_percentage == 100.0


@pytest.mark.asyncio
async def test_cross_tenant_trace_isolation(test_db: AsyncSession):
    """Verify that TraceService enforces tenant isolation across workspaces."""
    tr_id = "trace-secret-alpha"

    await OperationalAuditService.log_event(
        session=test_db,
        workspace_id="ws-alpha",
        event_type="WEBHOOK_ACCEPTED",
        action="Alpha Webhook",
        trace_id=tr_id,
    )

    # Reconstructing in ws-alpha should find nodes
    graph_alpha = await TraceService.reconstruct_trace(tr_id, "ws-alpha", test_db)
    assert graph_alpha.node_count >= 1
    assert graph_alpha.workspace_id == "ws-alpha"

    # Reconstructing same trace_id in ws-beta should NOT see ws-alpha nodes
    graph_beta = await TraceService.reconstruct_trace(tr_id, "ws-beta", test_db)
    assert len([n for n in graph_beta.nodes if n.component == "AUDIT"]) == 0

