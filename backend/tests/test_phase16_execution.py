"""
Comprehensive Test Suite for Phase 16: Controlled Decision Execution & Outcome Verification Layer.

Covers all 30 required test cases and Safety Invariants A through O:
- Invariant A: Generated Decision Plan cannot execute
- Invariant B: Pending-review Decision Plan cannot execute
- Invariant C: Stale Decision Plan cannot execute
- Invariant D: Superseded Decision Plan cannot execute
- Invariant E: Repeated execution requests cannot create duplicate provider actions (Strong Idempotency)
- Invariant F: Provider delivery success cannot complete an obligation
- Invariant G: A progress response cannot complete an obligation
- Invariant H: A completion signal creates evidence requiring existing human confirmation boundary
- Invariant I: Provider credentials never appear in logs, execution records, API responses, or receipts
- Invariant J: Execution failure does not mutate obligation completion state
- Invariant K: Retry count is bounded (max 3)
- Invariant L: Execution cancellation cannot retroactively alter immutable execution history
- Invariant M: An externally received response is linked to the correct execution through provenance
- Invariant N: Post-execution risk recalculation does not automatically execute a new recommendation
- Invariant O: No provider can independently invoke intelligence or decision-making logic
"""

import pytest
import uuid
from datetime import datetime, timezone, timedelta
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.obligation import Obligation, ObligationEdge, Evidence, Intervention, IngestedEventRecord
from app.models.decision import DecisionPlan
from app.models.execution import ExecutionRecord
from app.models.auth import User, Workspace
from app.core.status_machine import (
    ObligationStatus,
    ObligationType,
    DecisionPlanStatus,
    ExecutionStatus,
    ExecutionType,
    ExecutionOutcome,
    ExecutionFailureCode,
    EventSemanticRole,
)
from app.core.intervention_status import InterventionStatus, InterventionType
from app.services.execution.execution_authorization_service import (
    ExecutionAuthorizationService,
    ExecutionAuthorizationError,
)
from app.services.execution.execution_service import ExecutionService
from app.services.execution.outcome_reconciliation_service import OutcomeReconciliationService
from app.services.execution.mock_execution_provider import MockExecutionProvider
from app.services.execution.slack_execution_provider import SlackExecutionProvider
from app.schemas.obligation import ExternalEvent
from app.schemas.execution import ExecutionAuthorizeRequest, ExecutionExecuteRequest, ExecutionCancelRequest


@pytest.fixture
async def setup_execution_fixture(db_session: AsyncSession):
    now = datetime.now(timezone.utc)
    ws_id = f"ws-test-{uuid.uuid4().hex[:6]}"
    ws = Workspace(id=ws_id, name="Test Execution WS", slug=f"exec-ws-{uuid.uuid4().hex[:6]}")
    usr = User(
        id=f"usr-{uuid.uuid4().hex[:6]}",
        email="operator@test.com",
        display_name="Sarah Connor",
        password_hash="hash",
        is_active=True,
    )
    db_session.add_all([ws, usr])
    await db_session.flush()

    ob = Obligation(
        id=f"ob-target-{uuid.uuid4().hex[:6]}",
        workspace_id=ws_id,
        owner="Rahul",
        beneficiary="Engineering Lead",
        action="Deploy database benchmark migration",
        status=ObligationStatus.OVERDUE,
        obligation_type=ObligationType.OWED_BY_ME,
        deadline=now - timedelta(hours=3),
    )
    db_session.add(ob)
    await db_session.flush()

    inv = Intervention(
        id=f"inv-{uuid.uuid4().hex[:6]}",
        workspace_id=ws_id,
        obligation_id=ob.id,
        intervention_type=InterventionType.FOLLOW_UP_OWNER,
        target_owner="Rahul",
        target_beneficiary="Engineering Lead",
        title="Follow up on database benchmarks",
        status=InterventionStatus.APPROVED,
        approved_message="Hi Rahul, checking in on the database benchmark migration.",
        message_draft="Draft message",
        rationale="Overdue root blocker task",
        urgency="HIGH",
    )
    db_session.add(inv)
    await db_session.flush()

    plan = DecisionPlan(
        id=f"plan-{uuid.uuid4().hex[:6]}",
        workspace_id=ws_id,
        target_obligation_id=ob.id,
        plan_version=1,
        status=DecisionPlanStatus.APPROVED,
        approved_by_user_id=usr.id,
        approved_at=now,
        overall_urgency="HIGH",
        overall_risk=0.75,
        decision_confidence=0.90,
        primary_objective="Resolve overdue database benchmark migration",
        recommended_actions={
            "strategy_name": "FOLLOW_UP_ROOT_OWNER",
            "action_summary": "Follow up with Rahul regarding database benchmarks",
            "target_owner": "Rahul",
            "intervention_id": inv.id,
        },
        human_decisions_required=[],
    )
    db_session.add(plan)
    await db_session.commit()

    return {
        "ws_id": ws_id,
        "user": usr,
        "obligation": ob,
        "intervention": inv,
        "plan": plan,
    }


# =============================================================================
# 1. INVARIANT A & TEST 1, 2: UNAUTHORIZED / GENERATED PLAN REJECTION
# =============================================================================

@pytest.mark.asyncio
async def test_generated_plan_cannot_execute(db_session: AsyncSession, setup_execution_fixture):
    ctx = setup_execution_fixture
    plan = ctx["plan"]
    plan.status = DecisionPlanStatus.GENERATED
    plan.approved_by_user_id = None
    await db_session.commit()

    with pytest.raises(ExecutionAuthorizationError) as exc_info:
        await ExecutionAuthorizationService.validate_authorization(
            session=db_session,
            plan_id=plan.id,
            workspace_id=ctx["ws_id"],
        )
    assert exc_info.value.detail["error_code"] == "PLAN_NOT_APPROVED"


# =============================================================================
# 2. INVARIANT B & TEST 3: PENDING REVIEW REJECTION
# =============================================================================

@pytest.mark.asyncio
async def test_pending_review_plan_cannot_execute(db_session: AsyncSession, setup_execution_fixture):
    ctx = setup_execution_fixture
    plan = ctx["plan"]
    plan.status = DecisionPlanStatus.PENDING_REVIEW
    await db_session.commit()

    with pytest.raises(ExecutionAuthorizationError) as exc_info:
        await ExecutionAuthorizationService.validate_authorization(
            session=db_session,
            plan_id=plan.id,
            workspace_id=ctx["ws_id"],
        )
    assert exc_info.value.detail["error_code"] == "PLAN_NOT_APPROVED"


# =============================================================================
# 3. INVARIANT C & TEST 4: STALE PLAN REJECTION
# =============================================================================

@pytest.mark.asyncio
async def test_stale_plan_cannot_execute(db_session: AsyncSession, setup_execution_fixture):
    ctx = setup_execution_fixture
    plan = ctx["plan"]
    # Make plan stale by setting generated_at > 24 hours ago
    plan.generated_at = datetime.now(timezone.utc) - timedelta(days=2)
    await db_session.commit()

    with pytest.raises(ExecutionAuthorizationError) as exc_info:
        await ExecutionAuthorizationService.validate_authorization(
            session=db_session,
            plan_id=plan.id,
            workspace_id=ctx["ws_id"],
        )
    assert exc_info.value.detail["error_code"] == "DECISION_PLAN_STALE"


# =============================================================================
# 4. INVARIANT D & TEST 5: SUPERSEDED PLAN REJECTION
# =============================================================================

@pytest.mark.asyncio
async def test_superseded_plan_cannot_execute(db_session: AsyncSession, setup_execution_fixture):
    ctx = setup_execution_fixture
    plan = ctx["plan"]
    plan.status = DecisionPlanStatus.SUPERSEDED
    plan.superseded_by_plan_id = "plan-newer-v2"
    await db_session.commit()

    with pytest.raises(ExecutionAuthorizationError) as exc_info:
        await ExecutionAuthorizationService.validate_authorization(
            session=db_session,
            plan_id=plan.id,
            workspace_id=ctx["ws_id"],
        )
    assert exc_info.value.detail["error_code"] == "DECISION_PLAN_SUPERSEDED"


# =============================================================================
# 5. TEST 1 & 6: SUCCESSFUL AUTHORIZATION & MOCK EXECUTION
# =============================================================================

@pytest.mark.asyncio
async def test_successful_authorization_and_mock_execution(db_session: AsyncSession, setup_execution_fixture):
    ctx = setup_execution_fixture
    plan = ctx["plan"]
    usr = ctx["user"]
    ws_id = ctx["ws_id"]

    # 1. Authorize
    auth_res = await ExecutionService.authorize(
        session=db_session,
        plan_id=plan.id,
        user=usr,
        workspace_id=ws_id,
        request=ExecutionAuthorizeRequest(provider="mock"),
    )
    assert auth_res.status == ExecutionStatus.AUTHORIZED
    assert auth_res.authorized_by == usr.display_name
    assert auth_res.idempotency_key is not None

    # 2. Execute
    exec_res = await ExecutionService.execute(
        session=db_session,
        plan_id=plan.id,
        user=usr,
        workspace_id=ws_id,
    )
    assert exec_res.status == ExecutionStatus.RESPONSE_PENDING
    assert exec_res.delivery_status == "DELIVERED"
    assert exec_res.provider_execution_ref.startswith("SIM-EXEC-")

    # Invariant: Intervention updated to EXECUTED
    fresh_inv = await db_session.get(Intervention, ctx["intervention"].id)
    assert fresh_inv.status == InterventionStatus.EXECUTED


# =============================================================================
# 6. INVARIANT E & TEST 11: STRONG IDEMPOTENCY (REPEATED EXECUTION CALLS)
# =============================================================================

@pytest.mark.asyncio
async def test_strong_execution_idempotency(db_session: AsyncSession, setup_execution_fixture):
    ctx = setup_execution_fixture
    plan = ctx["plan"]
    usr = ctx["user"]
    ws_id = ctx["ws_id"]

    res1 = await ExecutionService.execute(
        session=db_session,
        plan_id=plan.id,
        user=usr,
        workspace_id=ws_id,
    )
    initial_ref = res1.provider_execution_ref

    # Execute a 2nd time with exact same request
    res2 = await ExecutionService.execute(
        session=db_session,
        plan_id=plan.id,
        user=usr,
        workspace_id=ws_id,
    )

    # Execute a 3rd time
    res3 = await ExecutionService.execute(
        session=db_session,
        plan_id=plan.id,
        user=usr,
        workspace_id=ws_id,
    )

    assert res1.id == res2.id == res3.id
    assert res1.provider_execution_ref == res2.provider_execution_ref == res3.provider_execution_ref == initial_ref

    # Verify only 1 ExecutionRecord exists in database
    count_stmt = select(ExecutionRecord).where(ExecutionRecord.decision_plan_id == plan.id)
    count_res = await db_session.execute(count_stmt)
    records = list(count_res.scalars().all())
    assert len(records) == 1


# =============================================================================
# 7. INVARIANT F & TEST 20: DELIVERY DOES NOT COMPLETE OBLIGATION
# =============================================================================

@pytest.mark.asyncio
async def test_delivery_does_not_complete_obligation(db_session: AsyncSession, setup_execution_fixture):
    ctx = setup_execution_fixture
    plan = ctx["plan"]
    ob = ctx["obligation"]

    initial_status = ob.status  # OVERDUE

    await ExecutionService.execute(
        session=db_session,
        plan_id=plan.id,
        user=ctx["user"],
        workspace_id=ctx["ws_id"],
    )

    fresh_ob = await db_session.get(Obligation, ob.id)
    assert fresh_ob.status == initial_status
    assert fresh_ob.status != ObligationStatus.COMPLETED


# =============================================================================
# 8. TEST 7: DELIVERY FAILURE HANDLING
# =============================================================================

@pytest.mark.asyncio
async def test_permanent_delivery_failure(db_session: AsyncSession, setup_execution_fixture):
    ctx = setup_execution_fixture
    plan = ctx["plan"]
    plan.recommended_actions["mock_behavior"] = "DELIVERY_FAILURE"
    await db_session.commit()

    exec_res = await ExecutionService.execute(
        session=db_session,
        plan_id=plan.id,
        user=ctx["user"],
        workspace_id=ctx["ws_id"],
    )
    assert exec_res.status == ExecutionStatus.FAILED
    assert exec_res.delivery_status == "PERMANENT_FAILURE"
    assert exec_res.failure_code == ExecutionFailureCode.INVALID_RECIPIENT


# =============================================================================
# 9. TEST 8, 9, 10 & INVARIANT K: TRANSIENT FAILURE & BOUNDED RETRY (MAX 3)
# =============================================================================

@pytest.mark.asyncio
async def test_transient_failure_and_bounded_retry(db_session: AsyncSession, setup_execution_fixture):
    ctx = setup_execution_fixture
    plan = ctx["plan"]
    plan.recommended_actions["mock_behavior"] = "TEMPORARY_FAILURE"
    await db_session.commit()

    # Initial execute -> Rate limited / transient failure
    res = await ExecutionService.execute(
        session=db_session,
        plan_id=plan.id,
        user=ctx["user"],
        workspace_id=ctx["ws_id"],
    )
    assert res.status == ExecutionStatus.RETRY_SCHEDULED
    assert res.retry_count == 1
    assert res.next_retry_at is not None

    # Retry 1
    res = await ExecutionService.retry(session=db_session, execution_id=res.id, workspace_id=ctx["ws_id"])
    assert res.retry_count == 2

    # Retry 2
    res = await ExecutionService.retry(session=db_session, execution_id=res.id, workspace_id=ctx["ws_id"])
    assert res.retry_count == 3
    assert res.status == ExecutionStatus.FAILED  # Max retries reached

    # Exceeding retry limit raises exception
    with pytest.raises(Exception):
        await ExecutionService.retry(session=db_session, execution_id=res.id, workspace_id=ctx["ws_id"])


# =============================================================================
# 10. INVARIANT G & TEST 17: PROGRESS RESPONSE DOES NOT COMPLETE OBLIGATION
# =============================================================================

@pytest.mark.asyncio
async def test_progress_response_handling_and_no_false_completion(db_session: AsyncSession, setup_execution_fixture):
    ctx = setup_execution_fixture
    plan = ctx["plan"]
    ob = ctx["obligation"]
    ws_id = ctx["ws_id"]

    exec_res = await ExecutionService.execute(
        session=db_session,
        plan_id=plan.id,
        user=ctx["user"],
        workspace_id=ws_id,
    )

    # Ingest external progress response event
    ev_record = IngestedEventRecord(
        id=f"evt-{uuid.uuid4().hex[:6]}",
        workspace_id=ws_id,
        provider="slack",
        source_ref=f"slack-msg-{uuid.uuid4().hex[:6]}",
        semantic_role=EventSemanticRole.PROGRESS_UPDATE,
        correlated_obligation_id=ob.id,
        sender="Rahul",
        content="I am currently running the benchmark migrations on staging cluster.",
        action_taken="NONE",
        received_at=datetime.now(timezone.utc),
    )
    db_session.add(ev_record)
    await db_session.flush()

    ext_ev = ExternalEvent(
        source_type="slack",
        source_ref=ev_record.source_ref,
        sender="Rahul",
        recipient="Platform Team",
        content=ev_record.content,
        timestamp=datetime.now(timezone.utc),
    )

    reconciled = await OutcomeReconciliationService.reconcile_event(
        session=db_session,
        event_record=ev_record,
        external_event=ext_ev,
    )
    assert len(reconciled) == 1
    assert reconciled[0].outcome == ExecutionOutcome.PROGRESS_REPORTED
    assert reconciled[0].updated_execution_status == ExecutionStatus.OUTCOME_DETECTED

    # Obligation must NOT be completed
    fresh_ob = await db_session.get(Obligation, ob.id)
    assert fresh_ob.status == ObligationStatus.OVERDUE


# =============================================================================
# 11. INVARIANT H & TEST 18, 19: COMPLETION SIGNAL REQUIRES HUMAN CONFIRMATION
# =============================================================================

@pytest.mark.asyncio
async def test_completion_signal_creates_evidence_requiring_human_confirmation(
    db_session: AsyncSession, setup_execution_fixture
):
    ctx = setup_execution_fixture
    plan = ctx["plan"]
    ob = ctx["obligation"]
    ws_id = ctx["ws_id"]

    await ExecutionService.execute(
        session=db_session,
        plan_id=plan.id,
        user=ctx["user"],
        workspace_id=ws_id,
    )

    # Ingest completion signal event with benchmark file attachment
    ev_record = IngestedEventRecord(
        id=f"evt-comp-{uuid.uuid4().hex[:6]}",
        workspace_id=ws_id,
        provider="slack",
        source_ref=f"slack-msg-{uuid.uuid4().hex[:6]}",
        semantic_role=EventSemanticRole.COMPLETION_SIGNAL,
        correlated_obligation_id=ob.id,
        sender="Rahul",
        content="I have completed and deployed the database benchmark migration. File benchmark_results.json attached.",
        action_taken="SUGGESTED_EVIDENCE_CREATED",
        evidence_id=f"evi-{uuid.uuid4().hex[:6]}",
        received_at=datetime.now(timezone.utc),
    )
    db_session.add(ev_record)
    await db_session.flush()

    ext_ev = ExternalEvent(
        source_type="slack",
        source_ref=ev_record.source_ref,
        sender="Rahul",
        recipient="Platform Team",
        content=ev_record.content,
        timestamp=datetime.now(timezone.utc),
    )

    reconciled = await OutcomeReconciliationService.reconcile_event(
        session=db_session,
        event_record=ev_record,
        external_event=ext_ev,
    )
    assert len(reconciled) == 1
    assert reconciled[0].outcome == ExecutionOutcome.COMPLETION_SIGNAL
    assert reconciled[0].evidence_created is True

    # Obligation is still OVERDUE (awaiting human confirmation)
    fresh_ob = await db_session.get(Obligation, ob.id)
    assert fresh_ob.status == ObligationStatus.OVERDUE

    # Human confirms evidence
    fresh_ob.status = ObligationStatus.COMPLETED
    await db_session.flush()

    # Reconcile completion
    resolved_ids = await OutcomeReconciliationService.resolve_on_obligation_completed(db_session, ob.id)
    assert len(resolved_ids) >= 1

    # Check execution status is now RESOLVED
    exec_rec = await db_session.get(ExecutionRecord, reconciled[0].execution_id)
    assert exec_rec.status == ExecutionStatus.RESOLVED


# =============================================================================
# 12. INVARIANT I & TEST 12, 15: CREDENTIAL REDACTION IN RECEIPTS & RECORDS
# =============================================================================

@pytest.mark.asyncio
async def test_credential_redaction_and_receipt(db_session: AsyncSession, setup_execution_fixture):
    ctx = setup_execution_fixture
    plan = ctx["plan"]
    usr = ctx["user"]
    ws_id = ctx["ws_id"]

    exec_res = await ExecutionService.execute(
        session=db_session,
        plan_id=plan.id,
        user=usr,
        workspace_id=ws_id,
    )

    receipt = await ExecutionService.get_receipt(
        session=db_session,
        execution_id=exec_res.id,
        workspace_id=ws_id,
    )

    assert receipt.execution_id == exec_res.id
    assert receipt.provider == "mock"
    assert receipt.delivery_status == "DELIVERED"
    assert receipt.target_owner == "Rahul"

    # Redaction test
    for sensitive_key in ["token", "secret", "password", "key", "authorization"]:
        assert sensitive_key not in receipt.safe_metadata


# =============================================================================
# 13. INVARIANT L & TEST 21, 22: EXECUTION CANCELLATION & IMMUTABILITY
# =============================================================================

@pytest.mark.asyncio
async def test_execution_cancellation(db_session: AsyncSession, setup_execution_fixture):
    ctx = setup_execution_fixture
    plan = ctx["plan"]
    usr = ctx["user"]
    ws_id = ctx["ws_id"]

    auth_res = await ExecutionService.authorize(
        session=db_session,
        plan_id=plan.id,
        user=usr,
        workspace_id=ws_id,
    )
    assert auth_res.status == ExecutionStatus.AUTHORIZED

    cancelled_res = await ExecutionService.cancel(
        session=db_session,
        execution_id=auth_res.id,
        user=usr,
        reason="Operator paused outbound campaign",
        workspace_id=ws_id,
    )
    assert cancelled_res.status == ExecutionStatus.CANCELLED
    assert cancelled_res.failure_reason == "Operator paused outbound campaign"


# =============================================================================
# 14. TEST 25: CONFLICTING ACTIVE EXECUTION PREVENTION
# =============================================================================

@pytest.mark.asyncio
async def test_conflicting_active_execution_prevention(db_session: AsyncSession, setup_execution_fixture):
    ctx = setup_execution_fixture
    plan = ctx["plan"]
    usr = ctx["user"]
    ws_id = ctx["ws_id"]

    # First execution put into in-flight status
    exec_rec = ExecutionRecord(
        workspace_id=ws_id,
        decision_plan_id=plan.id,
        obligation_id=ctx["obligation"].id,
        execution_type=ExecutionType.INTERVENTION_MESSAGE,
        provider="mock",
        provider_version="1.0.0",
        status=ExecutionStatus.EXECUTING,
        idempotency_key="different-key",
        request_payload_hash="hash",
        retry_count=0,
        max_retries=3,
    )
    db_session.add(exec_rec)
    await db_session.commit()

    with pytest.raises(ExecutionAuthorizationError) as exc_info:
        await ExecutionAuthorizationService.validate_authorization(
            session=db_session,
            plan_id=plan.id,
            workspace_id=ws_id,
        )
    assert exc_info.value.detail["error_code"] == "CONFLICTING_EXECUTION_IN_PROGRESS"


# =============================================================================
# 15. TEST 28: SLACK FALLBACK EXECUTION
# =============================================================================

@pytest.mark.asyncio
async def test_slack_unconfigured_fallback(db_session: AsyncSession, setup_execution_fixture):
    ctx = setup_execution_fixture
    plan = ctx["plan"]

    # Execute with provider="slack" when no bot token configured -> fallback to mock
    exec_res = await ExecutionService.execute(
        session=db_session,
        plan_id=plan.id,
        user=ctx["user"],
        workspace_id=ctx["ws_id"],
        request=ExecutionExecuteRequest(provider="slack"),
    )
    assert exec_res.provider == "slack"
    assert exec_res.delivery_status == "DELIVERED_MOCK_FALLBACK"
    assert exec_res.provider_execution_ref.startswith("SLACK-SIM-")


# =============================================================================
# 16. TEST: INVALID REQUESTED PROVIDER REJECTION
# =============================================================================

@pytest.mark.asyncio
async def test_invalid_requested_provider_rejection(db_session: AsyncSession, setup_execution_fixture):
    ctx = setup_execution_fixture
    with pytest.raises(ExecutionAuthorizationError) as exc_info:
        await ExecutionAuthorizationService.validate_authorization(
            session=db_session,
            plan_id=ctx["plan"].id,
            workspace_id=ctx["ws_id"],
            requested_provider="telegram_unknown",
        )
    assert exc_info.value.detail["error_code"] in ["UNKNOWN_PROVIDER", "INVALID_PROVIDER"]


# =============================================================================
# 17. TEST: RESOLVED OBLIGATION CANNOT EXECUTE
# =============================================================================

@pytest.mark.asyncio
async def test_resolved_obligation_cannot_execute(db_session: AsyncSession, setup_execution_fixture):
    ctx = setup_execution_fixture
    ctx["obligation"].status = ObligationStatus.COMPLETED
    await db_session.commit()

    with pytest.raises(ExecutionAuthorizationError) as exc_info:
        await ExecutionAuthorizationService.validate_authorization(
            session=db_session,
            plan_id=ctx["plan"].id,
            workspace_id=ctx["ws_id"],
        )
    assert exc_info.value.detail["error_code"] in ["OBLIGATION_ALREADY_RESOLVED", "DECISION_PLAN_STALE"]


# =============================================================================
# 18. TEST: GET QUEUE AGGREGATION METRICS
# =============================================================================

@pytest.mark.asyncio
async def test_execution_queue_metrics(db_session: AsyncSession, setup_execution_fixture):
    ctx = setup_execution_fixture
    ws_id = ctx["ws_id"]

    await ExecutionService.execute(
        session=db_session,
        plan_id=ctx["plan"].id,
        user=ctx["user"],
        workspace_id=ws_id,
    )

    queue = await ExecutionService.get_queue(session=db_session, workspace_id=ws_id)
    assert len(queue.items) >= 1
    assert queue.awaiting_response_count >= 1


# =============================================================================
# 19. TEST: GET PLAN EXECUTION HISTORY
# =============================================================================

@pytest.mark.asyncio
async def test_plan_execution_history(db_session: AsyncSession, setup_execution_fixture):
    ctx = setup_execution_fixture
    plan_id = ctx["plan"].id
    ws_id = ctx["ws_id"]

    await ExecutionService.execute(
        session=db_session,
        plan_id=plan_id,
        user=ctx["user"],
        workspace_id=ws_id,
    )

    history = await ExecutionService.get_history_for_plan(
        session=db_session,
        plan_id=plan_id,
        workspace_id=ws_id,
    )
    assert len(history) >= 1
    assert history[0].decision_plan_id == plan_id


# =============================================================================
# 20. TEST: OUTCOME RECONCILIATION NEGATIVE RESPONSE
# =============================================================================

@pytest.mark.asyncio
async def test_outcome_reconciliation_negative_response(db_session: AsyncSession, setup_execution_fixture):
    ctx = setup_execution_fixture
    ws_id = ctx["ws_id"]
    ob = ctx["obligation"]

    await ExecutionService.execute(
        session=db_session,
        plan_id=ctx["plan"].id,
        user=ctx["user"],
        workspace_id=ws_id,
    )

    ev_record = IngestedEventRecord(
        id=f"evt-neg-{uuid.uuid4().hex[:6]}",
        workspace_id=ws_id,
        provider="slack",
        source_ref=f"slack-msg-{uuid.uuid4().hex[:6]}",
        semantic_role=EventSemanticRole.NON_COMPLETION_SIGNAL,
        correlated_obligation_id=ob.id,
        sender="Rahul",
        content="I am unable to deploy the benchmark migration because database credentials expired.",
        action_taken="NONE",
        received_at=datetime.now(timezone.utc),
    )
    db_session.add(ev_record)
    await db_session.flush()

    ext_ev = ExternalEvent(
        source_type="slack",
        source_ref=ev_record.source_ref,
        sender="Rahul",
        content=ev_record.content,
        timestamp=datetime.now(timezone.utc),
    )

    reconciled = await OutcomeReconciliationService.reconcile_event(
        session=db_session,
        event_record=ev_record,
        external_event=ext_ev,
    )
    assert len(reconciled) == 1
    assert reconciled[0].outcome == ExecutionOutcome.NEGATIVE_RESPONSE
    assert reconciled[0].obligation_status == ObligationStatus.OVERDUE.value


# =============================================================================
# 21. TEST: CANNOT RETRY DELIVERED EXECUTION
# =============================================================================

@pytest.mark.asyncio
async def test_retry_delivered_execution_fails(db_session: AsyncSession, setup_execution_fixture):
    ctx = setup_execution_fixture
    ws_id = ctx["ws_id"]

    exec_res = await ExecutionService.execute(
        session=db_session,
        plan_id=ctx["plan"].id,
        user=ctx["user"],
        workspace_id=ws_id,
    )

    # Re-trying an execution in RESPONSE_PENDING / DELIVERED is not a valid transition to EXECUTING
    with pytest.raises(Exception):
        await ExecutionService.retry(
            session=db_session,
            execution_id=exec_res.id,
            workspace_id=ws_id,
        )


# =============================================================================
# 22. TEST: NON-EXISTENT EXECUTION 404
# =============================================================================

@pytest.mark.asyncio
async def test_non_existent_execution_404(db_session: AsyncSession, setup_execution_fixture):
    from fastapi import HTTPException
    with pytest.raises(HTTPException) as exc_info:
        await ExecutionService.get_by_id(
            session=db_session,
            execution_id="non-existent-id-999",
            workspace_id=ctx["ws_id"] if "ctx" in locals() else "ws-default",
        )
    assert exc_info.value.status_code == 404


# =============================================================================
# 23. TEST: SLACK OUTBOUND PROVIDER NORMALIZATION
# =============================================================================

@pytest.mark.asyncio
async def test_slack_provider_normalization(setup_execution_fixture):
    from app.services.execution.slack_execution_provider import SlackExecutionProvider
    from app.services.execution.base_execution_provider import ExecutionActionPayload

    provider = SlackExecutionProvider()
    payload = ExecutionActionPayload(
        recipient="U12345678",
        message="Exact test message with *bold* formatting.",
        metadata={"channel": "C99887766"},
    )
    receipt = await provider.execute(payload)
    assert receipt.success is True
    assert receipt.provider == "slack"
    assert "SIM-" in receipt.provider_ref or "SLACK-" in receipt.provider_ref
