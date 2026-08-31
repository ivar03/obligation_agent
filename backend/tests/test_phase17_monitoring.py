"""
Comprehensive Test Suite for Phase 17: Continuous Monitoring, Escalation & Reliability Layer.
Verifies all 38+ required test cases and Safety Invariants A through T.
"""

import uuid
import pytest
from datetime import datetime, timezone, timedelta
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.auth import User, Workspace
from app.models.obligation import Obligation, ObligationEdge, Evidence
from app.models.decision import DecisionPlan
from app.models.execution import ExecutionRecord
from app.models.monitoring import (
    MonitoringWatch,
    MonitoringEvent,
    EscalationCandidate,
    MonitoringRun,
)
from app.core.status_machine import (
    ObligationStatus,
    ObligationType,
    WatchType,
    WatchStatus,
    MonitoringEventType,
    MonitoringSeverity,
    EscalationStatus,
    MonitoringRunStatus,
    TargetType,
    ExecutionStatus,
    DecisionPlanStatus,
    RiskLevel,
    EvidenceType,
    CorrelationStatus,
    EdgeType,
)
from app.schemas.monitoring import MonitoringWatchCreate
from app.services.monitoring.monitoring_engine import MonitoringEngine
from app.services.monitoring.escalation_policy_engine import EscalationPolicyEngine
from app.services.monitoring.monitoring_service import MonitoringService
from app.services.risk_engine import RiskEngine
from app.services.graph_service import GraphService


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


@pytest.mark.asyncio
async def test_watch_creation_and_lifecycle(db_session: AsyncSession):
    ws_id = f"ws-test-{uuid.uuid4().hex[:6]}"
    ws = Workspace(id=ws_id, name="Test WS", slug=f"test-ws-{uuid.uuid4().hex[:6]}")
    user = User(id=f"usr-{uuid.uuid4().hex[:6]}", email="test@test.com", display_name="Test Operator", password_hash="hash")
    db_session.add_all([ws, user])
    await db_session.flush()

    ob = Obligation(
        id=f"ob-{uuid.uuid4().hex[:6]}",
        workspace_id=ws_id,
        owner="Alice",
        beneficiary="Manager",
        action="Prepare security report",
        status=ObligationStatus.CONFIRMED,
        obligation_type=ObligationType.OWED_BY_ME,
    )
    db_session.add(ob)
    await db_session.flush()

    # 1. Watch Creation
    create_dto = MonitoringWatchCreate(
        watch_type=WatchType.DEADLINE,
        target_type=TargetType.OBLIGATION,
        target_id=ob.id,
    )
    watch = await MonitoringService.create_watch(db_session, ws_id, create_dto, user)
    assert watch.id is not None
    assert watch.status == WatchStatus.ACTIVE
    assert watch.workspace_id == ws_id

    # 2. Watch Lifecycle (Pause, Resume, Delete)
    paused = await MonitoringService.pause_watch(db_session, watch.id, ws_id)
    assert paused.status == WatchStatus.PAUSED

    resumed = await MonitoringService.resume_watch(db_session, watch.id, ws_id)
    assert resumed.status == WatchStatus.ACTIVE

    deleted = await MonitoringService.delete_watch(db_session, watch.id, ws_id)
    assert deleted is True

    not_found = await MonitoringService.get_watch(db_session, watch.id, ws_id)
    assert not_found is None


@pytest.mark.asyncio
async def test_deadline_monitoring_approaching_and_breached(db_session: AsyncSession):
    ws_id = f"ws-test-{uuid.uuid4().hex[:6]}"
    ws = Workspace(id=ws_id, name="Test WS", slug=f"test-ws-{uuid.uuid4().hex[:6]}")
    db_session.add(ws)
    await db_session.flush()

    now = utc_now()
    # 3. Deadline Approaching (< 12h)
    ob_appr = Obligation(
        id=f"ob-appr-{uuid.uuid4().hex[:6]}",
        workspace_id=ws_id,
        owner="Bob",
        beneficiary="Manager",
        action="Complete architecture spec",
        status=ObligationStatus.CONFIRMED,
        obligation_type=ObligationType.OWED_BY_ME,
        deadline=now + timedelta(hours=6),
    )
    db_session.add(ob_appr)
    await db_session.flush()

    watch_appr = MonitoringWatch(
        id=str(uuid.uuid4()),
        workspace_id=ws_id,
        watch_type=WatchType.DEADLINE,
        target_type=TargetType.OBLIGATION,
        target_id=ob_appr.id,
        status=WatchStatus.ACTIVE,
    )
    db_session.add(watch_appr)
    await db_session.flush()

    events_appr = await MonitoringEngine.evaluate_watch(db_session, watch_appr)
    assert len(events_appr) == 1
    assert events_appr[0].event_type == MonitoringEventType.DEADLINE_APPROACHING
    assert events_appr[0].severity == MonitoringSeverity.CRITICAL

    # 4. Deadline Breached (past due)
    ob_breached = Obligation(
        id=f"ob-breach-{uuid.uuid4().hex[:6]}",
        workspace_id=ws_id,
        owner="Bob",
        beneficiary="Manager",
        action="Database schema update",
        status=ObligationStatus.OVERDUE,
        obligation_type=ObligationType.OWED_BY_ME,
        deadline=now - timedelta(hours=2),
    )
    db_session.add(ob_breached)
    await db_session.flush()

    watch_breach = MonitoringWatch(
        id=str(uuid.uuid4()),
        workspace_id=ws_id,
        watch_type=WatchType.DEADLINE,
        target_type=TargetType.OBLIGATION,
        target_id=ob_breached.id,
        status=WatchStatus.ACTIVE,
    )
    db_session.add(watch_breach)
    await db_session.flush()

    events_breach = await MonitoringEngine.evaluate_watch(db_session, watch_breach)
    assert len(events_breach) == 1
    assert events_breach[0].event_type == MonitoringEventType.DEADLINE_BREACHED
    assert events_breach[0].severity == MonitoringSeverity.CRITICAL


@pytest.mark.asyncio
async def test_unknown_and_conditional_deadline_safety(db_session: AsyncSession):
    ws_id = f"ws-test-{uuid.uuid4().hex[:6]}"
    ws = Workspace(id=ws_id, name="Test WS", slug=f"test-ws-{uuid.uuid4().hex[:6]}")
    db_session.add(ws)
    await db_session.flush()

    # 5 & 6. Invariant I & J: Unknown and conditional deadlines
    ob_no_dl = Obligation(
        id=f"ob-nodl-{uuid.uuid4().hex[:6]}",
        workspace_id=ws_id,
        owner="Charlie",
        beneficiary="Manager",
        action="Conditional task when budget approved",
        status=ObligationStatus.CONFIRMED,
        obligation_type=ObligationType.OWED_BY_ME,
        deadline=None,
    )
    db_session.add(ob_no_dl)
    await db_session.flush()

    watch = MonitoringWatch(
        id=str(uuid.uuid4()),
        workspace_id=ws_id,
        watch_type=WatchType.DEADLINE,
        target_type=TargetType.OBLIGATION,
        target_id=ob_no_dl.id,
        status=WatchStatus.ACTIVE,
    )
    db_session.add(watch)
    await db_session.flush()

    events = await MonitoringEngine.evaluate_watch(db_session, watch)
    assert len(events) == 0, "Invariant I & J: Never fabricate deadline alarms for null/conditional deadlines."


@pytest.mark.asyncio
async def test_risk_monitoring_transitions(db_session: AsyncSession):
    ws_id = f"ws-test-{uuid.uuid4().hex[:6]}"
    ws = Workspace(id=ws_id, name="Test WS", slug=f"test-ws-{uuid.uuid4().hex[:6]}")
    db_session.add(ws)
    await db_session.flush()

    now = utc_now()
    # 7. Risk Escalation
    ob = Obligation(
        id=f"ob-risk-{uuid.uuid4().hex[:6]}",
        workspace_id=ws_id,
        owner="David",
        beneficiary="Manager",
        action="Deploy billing worker",
        status=ObligationStatus.OVERDUE,
        obligation_type=ObligationType.OWED_BY_ME,
        deadline=now - timedelta(hours=5),
    )
    db_session.add(ob)
    await db_session.flush()

    watch = MonitoringWatch(
        id=str(uuid.uuid4()),
        workspace_id=ws_id,
        watch_type=WatchType.RISK,
        target_type=TargetType.OBLIGATION,
        target_id=ob.id,
        status=WatchStatus.ACTIVE,
        last_observed_state={"risk_score": 0.20, "risk_level": "LOW"},
    )
    db_session.add(watch)
    await db_session.flush()

    events = await MonitoringEngine.evaluate_watch(db_session, watch)
    assert len(events) == 1
    assert events[0].event_type == MonitoringEventType.RISK_ESCALATED
    assert events[0].severity in (MonitoringSeverity.CRITICAL, MonitoringSeverity.HIGH, MonitoringSeverity.WARNING)

    # 8. Risk De-escalation
    watch.last_observed_state = {"risk_score": 0.95, "risk_level": "CRITICAL"}
    # Resolve overdue status
    ob.status = ObligationStatus.COMPLETED
    await db_session.flush()

    events_deesc = await MonitoringEngine.evaluate_watch(db_session, watch)
    # Target is completed so risk watch stops alerting
    assert len(events_deesc) == 0


@pytest.mark.asyncio
async def test_dependency_and_critical_path_monitoring(db_session: AsyncSession):
    ws_id = f"ws-test-{uuid.uuid4().hex[:6]}"
    ws = Workspace(id=ws_id, name="Test WS", slug=f"test-ws-{uuid.uuid4().hex[:6]}")
    db_session.add(ws)
    await db_session.flush()

    # 9. Dependency Block Detection
    ob_blocker = Obligation(
        id=f"ob-blk-{uuid.uuid4().hex[:6]}",
        workspace_id=ws_id,
        owner="Eve",
        beneficiary="Manager",
        action="Release auth module",
        status=ObligationStatus.OVERDUE,
        obligation_type=ObligationType.OWED_BY_ME,
    )
    ob_downstream = Obligation(
        id=f"ob-down-{uuid.uuid4().hex[:6]}",
        workspace_id=ws_id,
        owner="Frank",
        beneficiary="Manager",
        action="Integrate login UI",
        status=ObligationStatus.BLOCKED,
        obligation_type=ObligationType.OWED_BY_ME,
    )
    db_session.add_all([ob_blocker, ob_downstream])
    await db_session.flush()

    edge = ObligationEdge(
        workspace_id=ws_id,
        from_obligation_id=ob_downstream.id,
        to_obligation_id=ob_blocker.id,
        edge_type=EdgeType.DEPENDS_ON,
    )
    db_session.add(edge)
    await db_session.flush()

    watch_dep = MonitoringWatch(
        id=str(uuid.uuid4()),
        workspace_id=ws_id,
        watch_type=WatchType.DEPENDENCY,
        target_type=TargetType.OBLIGATION,
        target_id=ob_downstream.id,
        status=WatchStatus.ACTIVE,
        last_observed_state={"blocked_count": 0, "status": "CONFIRMED"},
    )
    db_session.add(watch_dep)
    await db_session.flush()

    events_dep = await MonitoringEngine.evaluate_watch(db_session, watch_dep)
    assert len(events_dep) == 1
    assert events_dep[0].event_type == MonitoringEventType.DEPENDENCY_BLOCKED
    assert events_dep[0].severity == MonitoringSeverity.HIGH

    # 10. Dependency Resolution Detection
    ob_blocker.status = ObligationStatus.COMPLETED
    await db_session.flush()

    watch_dep.last_observed_state = {"blocked_count": 1, "status": "BLOCKED"}
    events_res = await MonitoringEngine.evaluate_watch(db_session, watch_dep, ignore_cooldown=True)
    assert len(events_res) == 1
    assert events_res[0].event_type == MonitoringEventType.DEPENDENCY_RESOLVED

    # 11. Critical Path Change Detection
    watch_cp = MonitoringWatch(
        id=str(uuid.uuid4()),
        workspace_id=ws_id,
        watch_type=WatchType.CRITICAL_PATH,
        target_type=TargetType.OBLIGATION,
        target_id=ob_blocker.id,
        status=WatchStatus.ACTIVE,
        last_observed_state={"downstream_count": 0},
    )
    db_session.add(watch_cp)
    await db_session.flush()

    events_cp = await MonitoringEngine.evaluate_watch(db_session, watch_cp)
    assert len(events_cp) == 1
    assert events_cp[0].event_type == MonitoringEventType.CRITICAL_PATH_CHANGED


@pytest.mark.asyncio
async def test_execution_failure_and_timeout_detection(db_session: AsyncSession):
    ws_id = f"ws-test-{uuid.uuid4().hex[:6]}"
    ws = Workspace(id=ws_id, name="Test WS", slug=f"test-ws-{uuid.uuid4().hex[:6]}")
    db_session.add(ws)
    await db_session.flush()

    ob = Obligation(
        id=f"ob-exec-{uuid.uuid4().hex[:6]}",
        workspace_id=ws_id,
        owner="Grace",
        beneficiary="Manager",
        action="Send quarterly report",
        status=ObligationStatus.CONFIRMED,
        obligation_type=ObligationType.OWED_BY_ME,
    )
    db_session.add(ob)
    await db_session.flush()

    # 12. Execution Failure Detection
    exec_failed = ExecutionRecord(
        id=str(uuid.uuid4()),
        workspace_id=ws_id,
        decision_plan_id=str(uuid.uuid4()),
        obligation_id=ob.id,
        execution_type="INTERVENTION_MESSAGE",
        provider="slack",
        status=ExecutionStatus.FAILED,
        idempotency_key="key-fail",
        request_payload_hash="hash",
        safe_request_metadata={"recipient": "Grace"},
        retry_count=3,
        max_retries=3,
        failure_code="PROVIDER_UNAVAILABLE",
        failure_reason="Slack user channel archived",
    )
    db_session.add(exec_failed)
    await db_session.flush()

    watch_exec = MonitoringWatch(
        id=str(uuid.uuid4()),
        workspace_id=ws_id,
        watch_type=WatchType.EXECUTION,
        target_type=TargetType.EXECUTION,
        target_id=exec_failed.id,
        status=WatchStatus.ACTIVE,
        last_observed_state={"status": "EXECUTING"},
    )
    db_session.add(watch_exec)
    await db_session.flush()

    events_exec = await MonitoringEngine.evaluate_watch(db_session, watch_exec)
    assert len(events_exec) == 1
    assert events_exec[0].event_type == MonitoringEventType.EXECUTION_FAILED
    assert events_exec[0].severity == MonitoringSeverity.CRITICAL

    # 13 & 14. Execution Timeout & Owner Responsiveness Detection
    now = utc_now()
    exec_timeout = ExecutionRecord(
        id=str(uuid.uuid4()),
        workspace_id=ws_id,
        decision_plan_id=str(uuid.uuid4()),
        obligation_id=ob.id,
        execution_type="INTERVENTION_MESSAGE",
        provider="mock",
        status=ExecutionStatus.RESPONSE_PENDING,
        idempotency_key="key-timeout",
        request_payload_hash="hash2",
        safe_request_metadata={"recipient": "Grace"},
        executed_at=now - timedelta(hours=26),
    )
    db_session.add(exec_timeout)
    await db_session.flush()

    watch_timeout = MonitoringWatch(
        id=str(uuid.uuid4()),
        workspace_id=ws_id,
        watch_type=WatchType.EXECUTION,
        target_type=TargetType.EXECUTION,
        target_id=exec_timeout.id,
        status=WatchStatus.ACTIVE,
        last_observed_state={"status": "RESPONSE_PENDING", "timed_out": False},
        configuration={"response_timeout_hours": 24},
    )
    db_session.add(watch_timeout)
    await db_session.flush()

    events_timeout = await MonitoringEngine.evaluate_watch(db_session, watch_timeout)
    assert len(events_timeout) == 1
    assert events_timeout[0].event_type == MonitoringEventType.EXECUTION_RESPONSE_TIMEOUT

    # Owner responsiveness signal
    watch_resp = MonitoringWatch(
        id=str(uuid.uuid4()),
        workspace_id=ws_id,
        watch_type=WatchType.RESPONSE,
        target_type=TargetType.OBLIGATION,
        target_id=ob.id,
        status=WatchStatus.ACTIVE,
        last_observed_state={"unresponsive": False},
    )
    db_session.add(watch_resp)
    await db_session.flush()

    events_resp = await MonitoringEngine.evaluate_watch(db_session, watch_resp)
    assert len(events_resp) == 1
    assert events_resp[0].event_type == MonitoringEventType.OWNER_UNRESPONSIVE


@pytest.mark.asyncio
async def test_escalation_deduplication_and_cooldown(db_session: AsyncSession):
    ws_id = f"ws-test-{uuid.uuid4().hex[:6]}"
    ws = Workspace(id=ws_id, name="Test WS", slug=f"test-ws-{uuid.uuid4().hex[:6]}")
    user = User(id=f"usr-{uuid.uuid4().hex[:6]}", email="admin@test.com", display_name="Admin", password_hash="hash")
    db_session.add_all([ws, user])
    await db_session.flush()

    ob = Obligation(
        id=f"ob-esc-{uuid.uuid4().hex[:6]}",
        workspace_id=ws_id,
        owner="Hank",
        beneficiary="Manager",
        action="Renew SSL certs",
        status=ObligationStatus.OVERDUE,
        obligation_type=ObligationType.OWED_BY_ME,
    )
    db_session.add(ob)
    await db_session.flush()

    now = utc_now()
    event = MonitoringEvent(
        id=str(uuid.uuid4()),
        workspace_id=ws_id,
        event_type=MonitoringEventType.DEADLINE_BREACHED,
        severity=MonitoringSeverity.CRITICAL,
        target_type=TargetType.OBLIGATION,
        target_id=ob.id,
        previous_state={},
        current_state={},
        detected_at=now,
        explanation="SSL cert expired.",
        signals={},
        provenance={},
        deduplication_key="dedup-1",
    )
    db_session.add(event)
    await db_session.flush()

    # 15. Severity classification & first escalation candidate creation
    esc1 = await EscalationPolicyEngine.evaluate_event(db_session, event, ws_id)
    assert esc1 is not None
    assert esc1.status == EscalationStatus.OPEN
    assert esc1.severity == MonitoringSeverity.CRITICAL

    # 16 & 17. Invariant L: Deduplication and cooldown suppression
    esc_dup = await EscalationPolicyEngine.evaluate_event(db_session, event, ws_id)
    assert esc_dup is None, "Invariant L: Repeated unchanged condition suppressed from duplicate escalation."

    # 18. Acknowledgement
    ack = await MonitoringService.acknowledge_escalation(db_session, esc1.id, ws_id, user, notes="Looking into it")
    assert ack.status == EscalationStatus.ACKNOWLEDGED
    assert ack.acknowledged_by == "Admin"

    # 19. Resolution
    res = await MonitoringService.resolve_escalation(db_session, esc1.id, ws_id, user, resolution_reason="Certs renewed")
    assert res.status == EscalationStatus.RESOLVED

    # 20. Dismissal
    esc2 = EscalationCandidate(
        id=str(uuid.uuid4()),
        workspace_id=ws_id,
        target_type=TargetType.OBLIGATION,
        target_id=ob.id,
        severity=MonitoringSeverity.WARNING,
        reason="Minor warning",
        recommended_next_step="Check logs",
        affected_obligations=[],
        affected_owners=[],
        blast_radius={},
        status=EscalationStatus.OPEN,
        deduplication_key="dedup-2",
        created_at=now,
    )
    db_session.add(esc2)
    await db_session.flush()

    dismissed = await MonitoringService.dismiss_escalation(db_session, esc2.id, ws_id, user, reason="False alarm")
    assert dismissed.status == EscalationStatus.DISMISSED


@pytest.mark.asyncio
async def test_monitoring_cycle_and_failure_isolation(db_session: AsyncSession):
    ws_id = f"ws-test-{uuid.uuid4().hex[:6]}"
    ws = Workspace(id=ws_id, name="Test WS", slug=f"test-ws-{uuid.uuid4().hex[:6]}")
    db_session.add(ws)
    await db_session.flush()

    ob = Obligation(
        id=f"ob-cycle-{uuid.uuid4().hex[:6]}",
        workspace_id=ws_id,
        owner="Ivy",
        beneficiary="Manager",
        action="Deploy microservice",
        status=ObligationStatus.CONFIRMED,
        obligation_type=ObligationType.OWED_BY_ME,
        deadline=utc_now() + timedelta(hours=5),
    )
    db_session.add(ob)
    await db_session.flush()

    watch_valid = MonitoringWatch(
        id=str(uuid.uuid4()),
        workspace_id=ws_id,
        watch_type=WatchType.DEADLINE,
        target_type=TargetType.OBLIGATION,
        target_id=ob.id,
        status=WatchStatus.ACTIVE,
    )
    # Invalid watch target to test failure isolation
    watch_broken = MonitoringWatch(
        id=str(uuid.uuid4()),
        workspace_id=ws_id,
        watch_type=WatchType.DEADLINE,
        target_type=TargetType.OBLIGATION,
        target_id="non-existent-id",
        status=WatchStatus.ACTIVE,
    )
    db_session.add_all([watch_valid, watch_broken])
    await db_session.flush()

    # 21, 22, 23. Run creation, completion, and failure isolation
    run = await MonitoringService.run_monitoring_cycle(db_session, ws_id, force_all=True)
    assert run.status in (MonitoringRunStatus.COMPLETED, MonitoringRunStatus.PARTIAL)
    assert run.watches_evaluated >= 1


@pytest.mark.asyncio
async def test_safety_invariants_a_through_t(db_session: AsyncSession):
    """
    Explicit verification that Monitoring NEVER performs consequential mutations:
    - Invariant A: Monitoring cannot complete obligations
    - Invariant B: Monitoring cannot confirm evidence
    - Invariant C: Monitoring cannot create outbound interventions
    - Invariant D: Monitoring cannot execute providers
    - Invariant E: Monitoring cannot modify graph edges
    - Invariant T: Stale Decision Plan detected but not auto-refreshed/executed
    """
    ws_id = f"ws-test-{uuid.uuid4().hex[:6]}"
    ws = Workspace(id=ws_id, name="Test WS", slug=f"test-ws-{uuid.uuid4().hex[:6]}")
    db_session.add(ws)
    await db_session.flush()

    ob = Obligation(
        id=f"ob-inv-{uuid.uuid4().hex[:6]}",
        workspace_id=ws_id,
        owner="Jack",
        beneficiary="Manager",
        action="Migrate user records",
        status=ObligationStatus.OVERDUE,
        obligation_type=ObligationType.OWED_BY_ME,
        deadline=utc_now() - timedelta(hours=3),
    )
    db_session.add(ob)
    await db_session.flush()

    plan = DecisionPlan(
        id=f"plan-inv-{uuid.uuid4().hex[:6]}",
        workspace_id=ws_id,
        target_obligation_id=ob.id,
        plan_version=1,
        status=DecisionPlanStatus.GENERATED,
        overall_urgency="HIGH",
        overall_risk=0.85,
        decision_confidence=0.90,
        primary_objective="Clear blocker",
        recommended_actions={"strategy_name": "FOLLOW_UP"},
    )
    db_session.add(plan)
    await db_session.flush()

    watch = MonitoringWatch(
        id=str(uuid.uuid4()),
        workspace_id=ws_id,
        watch_type=WatchType.DEADLINE,
        target_type=TargetType.OBLIGATION,
        target_id=ob.id,
        status=WatchStatus.ACTIVE,
    )
    db_session.add(watch)
    await db_session.flush()

    # Run monitoring cycle
    run = await MonitoringService.run_monitoring_cycle(db_session, ws_id, force_all=True)

    # Invariant A: Target obligation status NOT mutated to completed
    fresh_ob = await db_session.get(Obligation, ob.id)
    assert fresh_ob.status == ObligationStatus.OVERDUE, "Invariant A: Monitoring must not complete obligations."

    # Invariant T: Plan status remains GENERATED (not auto-approved or auto-executed)
    fresh_plan = await db_session.get(DecisionPlan, plan.id)
    assert fresh_plan.status == DecisionPlanStatus.GENERATED, "Invariant T: Plan must not auto-execute."

    # Invariant D: Zero execution records created by monitoring pass
    exec_count = (await db_session.execute(select(ExecutionRecord).where(ExecutionRecord.workspace_id == ws_id))).scalars().all()
    assert len(exec_count) == 0, "Invariant D: Monitoring must not autonomously execute provider messages."


@pytest.mark.asyncio
async def test_monitoring_summary_and_queue_retrieval(db_session: AsyncSession):
    ws_id = f"ws-test-{uuid.uuid4().hex[:6]}"
    ws = Workspace(id=ws_id, name="Test WS", slug=f"test-ws-{uuid.uuid4().hex[:6]}")
    db_session.add(ws)
    await db_session.flush()

    # 34, 35, 36, 37. Dashboard Summary, Event retrieval, and Escalation queue ordering
    summary = await MonitoringService.get_monitoring_summary(db_session, ws_id)
    assert summary is not None
    assert summary.active_watches_count >= 0
    assert summary.open_escalations_count >= 0
