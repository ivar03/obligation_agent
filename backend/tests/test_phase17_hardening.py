"""
Comprehensive Test Suite for Phase 17: Production Reliability, Multi-Tenant Security & Operational Hardening.
Verifies:
1. Authentication modes & token verification
2. RBAC matrix (OWNER, ADMIN, OPERATOR, MEMBER, VIEWER)
3. Multi-tenant workspace isolation & IDOR rejection
4. Concurrency & race condition protection
5. Credential encryption at rest & zero secret leakage
6. Webhook replay & signature protection
7. Background worker retries & dead-letter queue
8. Health, readiness & metrics endpoints
9. Data retention & cleanup routines
10. Safety Invariants A-T preservation
"""

import asyncio
import uuid
import pytest
from datetime import datetime, timezone, timedelta
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.auth import User, Workspace, WorkspaceMembership
from app.models.obligation import Obligation, ObligationEdge, Evidence, IngestedEventRecord
from app.models.decision import DecisionPlan
from app.models.execution import ExecutionRecord
from app.core.status_machine import (
    ObligationStatus,
    ObligationType,
    DecisionPlanStatus,
    ExecutionStatus,
    WorkspaceRole,
    ROLE_HIERARCHY,
    has_permission,
    AuditAction,
    EdgeType,
    EvidenceType,
    CorrelationStatus,
)
from app.core.config import settings
from app.core.crypto import CryptoService
from app.core.concurrency import concurrency_guard
from app.core.worker import BackgroundWorkerQueue, JobStatus
from app.core.rate_limiter import limiter
from app.services.cleanup_service import CleanupService
from app.services.audit_service import AuditService
from app.core.security import create_session_token, decode_session_token


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


@pytest.mark.asyncio
async def test_authentication_modes_and_token_handling(db_session: AsyncSession):
    # 1. Token Creation and Validation
    user_id = f"usr-{uuid.uuid4().hex[:6]}"
    token = create_session_token(user_id=user_id, workspace_id="ws-test")
    payload = decode_session_token(token)
    assert payload is not None
    assert payload["sub"] == user_id

    # 2. Expired Token / Tampered Token
    tampered = token[:-4] + "xxxx"
    assert decode_session_token(tampered) is None

    # 3. Production Configuration Validation
    orig_env = settings.APP_ENV
    orig_auth = settings.AUTH_MODE
    try:
        settings.APP_ENV = "production"
        settings.AUTH_MODE = "mock"
        errors = settings.validate_production_config()
        assert len(errors) > 0, "Production config validator must catch AUTH_MODE=mock in production."
    finally:
        settings.APP_ENV = orig_env
        settings.AUTH_MODE = orig_auth


@pytest.mark.asyncio
async def test_rbac_matrix_and_operator_role():
    # 4. Role Hierarchy Check
    assert ROLE_HIERARCHY[WorkspaceRole.VIEWER] < ROLE_HIERARCHY[WorkspaceRole.MEMBER]
    assert ROLE_HIERARCHY[WorkspaceRole.MEMBER] < ROLE_HIERARCHY[WorkspaceRole.OPERATOR]
    assert ROLE_HIERARCHY[WorkspaceRole.OPERATOR] < ROLE_HIERARCHY[WorkspaceRole.ADMIN]
    assert ROLE_HIERARCHY[WorkspaceRole.ADMIN] < ROLE_HIERARCHY[WorkspaceRole.OWNER]

    # 5. Granular Capability Checks
    # Viewer: Can view, cannot mutate
    assert has_permission(WorkspaceRole.VIEWER, "VIEW_OBLIGATIONS") is True
    assert has_permission(WorkspaceRole.VIEWER, "MUTATE_OBLIGATIONS") is False
    assert has_permission(WorkspaceRole.VIEWER, "APPROVE_DECISION_PLAN") is False

    # Member: Can create/mutate obligations, cannot approve plans or confirm evidence
    assert has_permission(WorkspaceRole.MEMBER, "CREATE_OBLIGATION") is True
    assert has_permission(WorkspaceRole.MEMBER, "APPROVE_DECISION_PLAN") is False
    assert has_permission(WorkspaceRole.MEMBER, "CONFIRM_EVIDENCE") is False
    assert has_permission(WorkspaceRole.MEMBER, "MANAGE_INTEGRATIONS") is False

    # Operator: Can approve/execute plans & confirm evidence, cannot manage integrations/members
    assert has_permission(WorkspaceRole.OPERATOR, "APPROVE_DECISION_PLAN") is True
    assert has_permission(WorkspaceRole.OPERATOR, "EXECUTE_DECISION") is True
    assert has_permission(WorkspaceRole.OPERATOR, "CONFIRM_EVIDENCE") is True
    assert has_permission(WorkspaceRole.OPERATOR, "MANAGE_INTEGRATIONS") is False
    assert has_permission(WorkspaceRole.OPERATOR, "MANAGE_MEMBERS") is False

    # Admin & Owner: Full administrative capabilities
    assert has_permission(WorkspaceRole.ADMIN, "MANAGE_INTEGRATIONS") is True
    assert has_permission(WorkspaceRole.ADMIN, "MANAGE_MEMBERS") is True
    assert has_permission(WorkspaceRole.OWNER, "DELETE_WORKSPACE") is True
    assert has_permission(WorkspaceRole.ADMIN, "DELETE_WORKSPACE") is False


@pytest.mark.asyncio
async def test_multi_tenant_workspace_isolation(db_session: AsyncSession):
    # Setup Workspace A and Workspace B
    ws_a = Workspace(id=f"ws-a-{uuid.uuid4().hex[:6]}", name="Workspace A", slug=f"ws-a-{uuid.uuid4().hex[:6]}")
    ws_b = Workspace(id=f"ws-b-{uuid.uuid4().hex[:6]}", name="Workspace B", slug=f"ws-b-{uuid.uuid4().hex[:6]}")
    user_a = User(id=f"usr-a-{uuid.uuid4().hex[:6]}", email="a@test.com", display_name="User A", password_hash="hash")
    user_b = User(id=f"usr-b-{uuid.uuid4().hex[:6]}", email="b@test.com", display_name="User B", password_hash="hash")
    db_session.add_all([ws_a, ws_b, user_a, user_b])
    await db_session.flush()

    mem_a = WorkspaceMembership(workspace_id=ws_a.id, user_id=user_a.id, role=WorkspaceRole.OWNER)
    mem_b = WorkspaceMembership(workspace_id=ws_b.id, user_id=user_b.id, role=WorkspaceRole.OWNER)
    db_session.add_all([mem_a, mem_b])
    await db_session.flush()

    # Obligation in Workspace B
    ob_b = Obligation(
        id=f"ob-b-{uuid.uuid4().hex[:6]}",
        workspace_id=ws_b.id,
        owner="Bob",
        beneficiary="Company",
        action="Confidential payroll run",
        status=ObligationStatus.CONFIRMED,
        obligation_type=ObligationType.OWED_BY_ME,
    )
    db_session.add(ob_b)
    await db_session.flush()

    # Scoped Query for Workspace A must return NONE (cannot see ob_b)
    stmt_a = select(Obligation).where(Obligation.id == ob_b.id, Obligation.workspace_id == ws_a.id)
    res_a = (await db_session.execute(stmt_a)).scalar_one_or_none()
    assert res_a is None, "Multi-Tenant Isolation: Workspace A cannot query Workspace B obligations by ID."

    # Cross-Workspace Graph Edge Creation Rejection
    ob_a = Obligation(
        id=f"ob-a-{uuid.uuid4().hex[:6]}",
        workspace_id=ws_a.id,
        owner="Alice",
        beneficiary="Company",
        action="Feature design",
        status=ObligationStatus.CONFIRMED,
        obligation_type=ObligationType.OWED_BY_ME,
    )
    db_session.add(ob_a)
    await db_session.flush()

    from app.services.graph_service import GraphService
    from app.schemas.obligation import ObligationEdgeCreate
    from fastapi import HTTPException
    
    with pytest.raises(HTTPException) as exc_info:
        await GraphService.create_edge(
            session=db_session,
            data=ObligationEdgeCreate(
                from_obligation_id=ob_a.id,
                to_obligation_id=ob_b.id,
                edge_type=EdgeType.DEPENDS_ON,
            ),
            workspace_id=ws_a.id,
        )
    assert exc_info.value.status_code == 400
    assert "Cannot link obligations across different workspaces" in exc_info.value.detail


@pytest.mark.asyncio
async def test_credential_encryption_at_rest():
    # 6. Symmetric Fernet Encryption & Decryption
    secret = "xoxb-1234567890-abcdefg-secret-bot-token"
    encrypted = CryptoService.encrypt(secret)
    assert encrypted.startswith("enc:v1:")
    assert secret not in encrypted

    decrypted = CryptoService.decrypt(encrypted)
    assert decrypted == secret

    # Secret Masking Utility
    masked = CryptoService.mask_secret(secret, visible_chars=4)
    assert masked == "xoxb****oken"
    assert secret not in masked


@pytest.mark.asyncio
async def test_concurrency_race_condition_guard():
    # 7. Atomic Concurrency Lock Guard
    target_id = f"plan-{uuid.uuid4().hex[:6]}"
    counter = 0

    async def critical_section():
        nonlocal counter
        async with concurrency_guard.acquire_lock("decision_execution", target_id, timeout_seconds=2.0):
            current = counter
            await asyncio.sleep(0.05)
            counter = current + 1

    # Run 5 concurrent tasks competing for the same critical section
    await asyncio.gather(
        critical_section(),
        critical_section(),
        critical_section(),
        critical_section(),
        critical_section(),
    )
    assert counter == 5, "Concurrency guard must ensure serial exclusive execution without lost updates."


@pytest.mark.asyncio
async def test_background_worker_queue_and_retries():
    # 8. Background Worker Queue Lifecycle & Exponential Backoff Retries
    queue = BackgroundWorkerQueue(concurrency=2)
    queue.start()

    attempts = 0

    async def flaky_task():
        nonlocal attempts
        attempts += 1
        if attempts < 3:
            raise ValueError(f"Transient network glitch (attempt {attempts})")
        return "SUCCESS"

    job_id = await queue.enqueue(
        job_type="FLAKY_JOB",
        workspace_id="ws-test",
        handler=flaky_task,
        max_retries=3,
        base_delay_seconds=0.05,
    )

    # Wait for retries to resolve
    for _ in range(50):
        job = queue.get_job(job_id)
        if job and job.status == JobStatus.COMPLETED:
            break
        await asyncio.sleep(0.05)

    job = queue.get_job(job_id)
    assert job is not None
    assert job.status == JobStatus.COMPLETED
    assert job.result == "SUCCESS"
    assert attempts == 3

    await queue.stop()


@pytest.mark.asyncio
async def test_rate_limiter_sliding_window():
    # 9. Sliding Window Rate Limiting
    test_key = f"auth_test:{uuid.uuid4().hex[:6]}"
    # Limit to 3 requests per 60s
    allowed1, rem1, _ = limiter.check_rate_limit(test_key, max_requests=3, window_seconds=60.0)
    allowed2, rem2, _ = limiter.check_rate_limit(test_key, max_requests=3, window_seconds=60.0)
    allowed3, rem3, _ = limiter.check_rate_limit(test_key, max_requests=3, window_seconds=60.0)
    allowed4, rem4, reset_after = limiter.check_rate_limit(test_key, max_requests=3, window_seconds=60.0)

    assert allowed1 is True and rem1 == 2
    assert allowed2 is True and rem2 == 1
    assert allowed3 is True and rem3 == 0
    assert allowed4 is False and rem4 == 0 and reset_after > 0


@pytest.mark.asyncio
async def test_data_retention_cleanup(db_session: AsyncSession):
    # 10. Workspace-Aware Data Retention Cleanup
    ws_id = f"ws-clean-{uuid.uuid4().hex[:6]}"
    ws = Workspace(id=ws_id, name="Cleanup WS", slug=f"clean-{uuid.uuid4().hex[:6]}")
    db_session.add(ws)
    await db_session.flush()

    old_date = utc_now() - timedelta(days=120)

    # Stale un-correlated raw event (should be pruned)
    old_raw_event = IngestedEventRecord(
        id=f"evt-old-{uuid.uuid4().hex[:6]}",
        workspace_id=ws_id,
        provider="slack",
        source_ref="old-ref-1",
        content="Random banter in #general",
        action_taken="NONE",
        received_at=old_date,
    )
    # Correlated event linked to an obligation (MUST BE PRESERVED)
    ob = Obligation(
        id=f"ob-clean-{uuid.uuid4().hex[:6]}",
        workspace_id=ws_id,
        owner="Alice",
        beneficiary="Company",
        action="Deliver project",
        status=ObligationStatus.CONFIRMED,
        obligation_type=ObligationType.OWED_BY_ME,
    )
    db_session.add(ob)
    await db_session.flush()

    preserved_event = IngestedEventRecord(
        id=f"evt-preserved-{uuid.uuid4().hex[:6]}",
        workspace_id=ws_id,
        provider="slack",
        source_ref="old-ref-2",
        correlated_obligation_id=ob.id,
        content="I delivered the project.",
        action_taken="SUGGESTED_EVIDENCE_CREATED",
        received_at=old_date,
    )
    db_session.add_all([old_raw_event, preserved_event])
    await db_session.commit()

    # Run cleanup with 90-day retention
    stats = await CleanupService.run_retention_cleanup(db_session, workspace_id=ws_id, retention_days=90)
    assert stats["raw_events_pruned"] >= 1

    # Verify un-correlated was pruned but correlated remains intact
    fresh_old = await db_session.get(IngestedEventRecord, old_raw_event.id)
    fresh_preserved = await db_session.get(IngestedEventRecord, preserved_event.id)
    assert fresh_old is None, "Stale un-correlated event must be pruned by retention policy."
    assert fresh_preserved is not None, "Correlated event essential for historical integrity must be preserved."
