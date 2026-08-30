import pytest
from datetime import datetime, timedelta, timezone
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import status

from app.main import app
from app.models.obligation import Obligation, ObligationEdge, Evidence, Intervention
from app.core.status_machine import (
    ObligationStatus,
    ObligationType,
    EdgeType,
    EvidenceType,
    CorrelationStatus,
    EventSemanticRole,
    RiskLevel,
)
from app.core.intervention_status import (
    InterventionType,
    InterventionStatus,
    InterventionOutcome,
)
from app.services.intervention_planner import InterventionPlanner
from app.services.intervention_service import InterventionService
from app.services.message_generator import MessageGenerator
from app.services.risk_engine import RiskEngine
from app.schemas.obligation import RiskAssessmentResponse


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


@pytest.fixture
async def async_client(db_session: AsyncSession):
    from app.api.deps import get_db

    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_1_healthy_obligation_no_intervention(db_session: AsyncSession):
    now = utc_now()
    ob = Obligation(
        owner="Alice",
        beneficiary="Bob",
        action="Complete Q4 report",
        deadline=now + timedelta(days=14),
        status=ObligationStatus.CONFIRMED,
        obligation_type=ObligationType.OWED_BY_ME,
    )
    db_session.add(ob)
    await db_session.commit()

    # Healthy obligation -> InterventionPlanner returns None
    plan = await InterventionPlanner.plan_intervention(db_session, ob.id)
    assert plan is None


@pytest.mark.asyncio
async def test_2_high_risk_overdue_dependency_resolve_dependency(db_session: AsyncSession):
    now = utc_now()
    # Rahul owes Ravi benchmark numbers (overdue)
    ob_prereq = Obligation(
        owner="Rahul",
        beneficiary="Ravi",
        action="Send database benchmark numbers",
        deadline=now - timedelta(hours=5),
        status=ObligationStatus.OVERDUE,
        obligation_type=ObligationType.OWED_TO_ME,
    )
    db_session.add(ob_prereq)
    await db_session.flush()

    # Ravi's report is blocked by Rahul
    ob_blocked = Obligation(
        owner="Ravi",
        beneficiary="Team",
        action="Finish benchmark analysis report",
        deadline=now + timedelta(hours=10),
        status=ObligationStatus.BLOCKED,
        obligation_type=ObligationType.OWED_BY_ME,
        block_reason={"blocked": True, "blocked_by": [{"obligation_id": ob_prereq.id, "owner": "Rahul", "action": ob_prereq.action, "status": "OVERDUE", "reason": "Overdue prerequisite"}]},
    )
    db_session.add(ob_blocked)
    await db_session.flush()

    edge = ObligationEdge(
        from_obligation_id=ob_blocked.id,
        to_obligation_id=ob_prereq.id,
        edge_type=EdgeType.DEPENDS_ON,
    )
    db_session.add(edge)
    await db_session.commit()

    plan = await InterventionPlanner.plan_intervention(db_session, ob_blocked.id)
    assert plan is not None
    assert plan.intervention_type == InterventionType.RESOLVE_DEPENDENCY
    assert plan.target_owner == "Rahul"
    assert "Rahul" in plan.message_draft
    assert "Send database benchmark numbers" in plan.message_draft or "benchmark numbers" in plan.message_draft.lower()


@pytest.mark.asyncio
async def test_3_high_risk_owner_obligation_follow_up_owner(db_session: AsyncSession):
    now = utc_now()
    ob = Obligation(
        owner="Rahul",
        beneficiary="Ravi",
        action="Submit tax filing documents",
        deadline=now - timedelta(hours=2),
        status=ObligationStatus.OVERDUE,
        obligation_type=ObligationType.OWED_TO_ME,
    )
    db_session.add(ob)
    await db_session.commit()

    plan = await InterventionPlanner.plan_intervention(db_session, ob.id)
    assert plan is not None
    assert plan.intervention_type == InterventionType.FOLLOW_UP_OWNER
    assert plan.target_owner == "Rahul"
    assert "Submit tax filing documents" in plan.message_draft


@pytest.mark.asyncio
async def test_4_ambiguous_ownership_assign_owner(db_session: AsyncSession):
    now = utc_now()
    ob = Obligation(
        owner="We",
        beneficiary="Client",
        action="Prepare security compliance answers",
        deadline=now + timedelta(hours=10),
        status=ObligationStatus.CONFIRMED,
        obligation_type=ObligationType.OWED_BY_ME,
        confidence={"owner": 0.4},
    )
    db_session.add(ob)
    await db_session.commit()

    plan = await InterventionPlanner.plan_intervention(db_session, ob.id)
    assert plan is not None
    assert plan.intervention_type == InterventionType.ASSIGN_OWNER
    assert "assign" in plan.message_draft.lower() or "owner" in plan.message_draft.lower()


@pytest.mark.asyncio
async def test_5_unknown_deadline_clarify_deadline(db_session: AsyncSession):
    ob = Obligation(
        owner="Alex",
        beneficiary="Sam",
        action="Migrate legacy user records",
        deadline=None,
        status=ObligationStatus.CONFIRMED,
        obligation_type=ObligationType.OWED_TO_ME,
    )
    db_session.add(ob)
    await db_session.commit()

    plan = await InterventionPlanner.plan_intervention(db_session, ob.id, force=True)
    assert plan is not None
    assert plan.intervention_type == InterventionType.CLARIFY_DEADLINE
    assert "Migrate legacy user records" in plan.message_draft


@pytest.mark.asyncio
async def test_6_conditional_trigger_monitor_condition(db_session: AsyncSession):
    ob = Obligation(
        owner="Sara",
        beneficiary="Lead",
        action="Deploy staging v2 build",
        deadline=None,
        conditions="Once QA signs off on integration test results",
        status=ObligationStatus.CONFIRMED,
        obligation_type=ObligationType.OWED_BY_ME,
    )
    db_session.add(ob)
    await db_session.commit()

    plan = await InterventionPlanner.plan_intervention(db_session, ob.id, force=True)
    assert plan is not None
    assert plan.intervention_type == InterventionType.MONITOR_CONDITION
    assert "Once QA signs off" in plan.message_draft or "Deploy staging v2 build" in plan.message_draft


@pytest.mark.asyncio
async def test_7_conflicting_evidence_review_evidence(db_session: AsyncSession):
    now = utc_now()
    ob = Obligation(
        owner="Vikram",
        beneficiary="Elena",
        action="Deliver system architecture diagram",
        deadline=now + timedelta(hours=6),
        status=ObligationStatus.CONFIRMED,
        obligation_type=ObligationType.OWED_TO_ME,
    )
    db_session.add(ob)
    await db_session.flush()

    ev1 = Evidence(
        obligation_id=ob.id,
        evidence_type=EvidenceType.MESSAGE,
        source_type="slack",
        content="I uploaded the architecture diagram to Drive.",
        semantic_role=EventSemanticRole.COMPLETION_SIGNAL,
        correlation_status=CorrelationStatus.SUGGESTED,
        correlation_confidence=0.85,
    )
    ev2 = Evidence(
        obligation_id=ob.id,
        evidence_type=EvidenceType.MESSAGE,
        source_type="slack",
        content="Still blocked on network topology, cannot finish diagram today.",
        semantic_role=EventSemanticRole.NON_COMPLETION_SIGNAL,
        correlation_status=CorrelationStatus.SUGGESTED,
        correlation_confidence=0.80,
    )
    db_session.add_all([ev1, ev2])
    await db_session.commit()

    plan = await InterventionPlanner.plan_intervention(db_session, ob.id)
    assert plan is not None
    assert plan.intervention_type == InterventionType.REVIEW_EVIDENCE
    assert "Review required" in plan.message_draft or "evidence" in plan.message_draft.lower()


@pytest.mark.asyncio
async def test_8_message_draft_generation_uses_only_known_facts():
    now = utc_now()
    ob = Obligation(
        id="test-id",
        owner="Kavita",
        beneficiary="Arun",
        action="Provide API access keys",
        deadline=now + timedelta(hours=5),
        status=ObligationStatus.CONFIRMED,
        obligation_type=ObligationType.OWED_TO_ME,
    )

    draft = MessageGenerator.generate_draft(
        obligation=ob,
        intervention_type=InterventionType.FOLLOW_UP_OWNER,
        target_owner="Kavita",
        target_beneficiary="Arun",
    )

    assert "Kavita" in draft
    assert "Provide API access keys" in draft
    assert "due within 5 hours" in draft or "is due" in draft


@pytest.mark.asyncio
async def test_9_message_draft_must_not_fabricate_claims():
    ob = Obligation(
        id="test-id",
        owner="Rohan",
        beneficiary="Priya",
        action="Audit SSL certificates",
        deadline=None,
        status=ObligationStatus.CONFIRMED,
        obligation_type=ObligationType.OWED_BY_ME,
    )

    draft = MessageGenerator.generate_draft(
        obligation=ob,
        intervention_type=InterventionType.FOLLOW_UP_OWNER,
        target_owner="Rohan",
        target_beneficiary="Priya",
    )

    # Must not contain fabricated promises or non-existent client mentions
    assert "yesterday" not in draft.lower()
    assert "client is waiting" not in draft.lower()
    assert "you promised" not in draft.lower()


@pytest.mark.asyncio
async def test_10_intervention_creation_via_api(async_client: AsyncClient, db_session: AsyncSession):
    now = utc_now()
    ob = Obligation(
        owner="Rahul",
        beneficiary="Ravi",
        action="Send financial audit ledger",
        deadline=now - timedelta(hours=3),
        status=ObligationStatus.OVERDUE,
        obligation_type=ObligationType.OWED_TO_ME,
    )
    db_session.add(ob)
    await db_session.commit()

    res = await async_client.post("/api/interventions/plan", json={"obligation_id": ob.id})
    assert res.status_code == status.HTTP_201_CREATED
    data = res.json()
    assert data["obligation_id"] == ob.id
    assert data["status"] == "PENDING_REVIEW"
    assert data["requires_approval"] is True
    assert data["target_owner"] == "Rahul"


@pytest.mark.asyncio
async def test_11_duplicate_intervention_prevention(db_session: AsyncSession):
    now = utc_now()
    ob = Obligation(
        owner="Rahul",
        beneficiary="Ravi",
        action="Send database benchmark numbers",
        deadline=now - timedelta(hours=2),
        status=ObligationStatus.OVERDUE,
        obligation_type=ObligationType.OWED_TO_ME,
    )
    db_session.add(ob)
    await db_session.commit()

    plan1 = await InterventionPlanner.plan_intervention(db_session, ob.id)
    assert plan1 is not None

    # Second call returns existing active intervention instead of creating a duplicate
    plan2 = await InterventionPlanner.plan_intervention(db_session, ob.id)
    assert plan2 is not None
    assert plan2.id == plan1.id


@pytest.mark.asyncio
async def test_12_cooldown_enforcement(db_session: AsyncSession):
    now = utc_now()
    ob = Obligation(
        owner="Rahul",
        beneficiary="Ravi",
        action="Deploy benchmark metrics",
        deadline=now - timedelta(hours=1),
        status=ObligationStatus.OVERDUE,
        obligation_type=ObligationType.OWED_TO_ME,
    )
    db_session.add(ob)
    await db_session.commit()

    plan = await InterventionPlanner.plan_intervention(db_session, ob.id)
    assert plan is not None

    # Simulate approved and executed
    await InterventionService.approve(db_session, plan.id)
    await InterventionService.execute(db_session, plan.id)

    # Next attempt during cooldown returns the in-cooldown intervention
    subsequent_plan = await InterventionPlanner.plan_intervention(db_session, ob.id)
    assert subsequent_plan is not None
    assert subsequent_plan.id == plan.id


@pytest.mark.asyncio
async def test_13_approval_transition(async_client: AsyncClient, db_session: AsyncSession):
    now = utc_now()
    ob = Obligation(
        owner="Rahul",
        beneficiary="Ravi",
        action="Compile customer feedback matrix",
        deadline=now - timedelta(hours=1),
        status=ObligationStatus.OVERDUE,
        obligation_type=ObligationType.OWED_TO_ME,
    )
    db_session.add(ob)
    await db_session.commit()

    plan = await InterventionPlanner.plan_intervention(db_session, ob.id)
    assert plan.status == InterventionStatus.PENDING_REVIEW

    res = await async_client.post(
        f"/api/interventions/{plan.id}/approve",
        json={"approved_by": "Ravi", "approved_message": "Hi Rahul, customized approval message."},
    )
    assert res.status_code == status.HTTP_200_OK
    data = res.json()
    assert data["status"] == "APPROVED"
    assert data["approved_by"] == "Ravi"
    assert data["approved_message"] == "Hi Rahul, customized approval message."
    assert data["approved_at"] is not None


@pytest.mark.asyncio
async def test_14_approval_required_before_execution(async_client: AsyncClient, db_session: AsyncSession):
    now = utc_now()
    ob = Obligation(
        owner="Rahul",
        beneficiary="Ravi",
        action="Send performance profile",
        deadline=now - timedelta(hours=2),
        status=ObligationStatus.OVERDUE,
        obligation_type=ObligationType.OWED_TO_ME,
    )
    db_session.add(ob)
    await db_session.commit()

    plan = await InterventionPlanner.plan_intervention(db_session, ob.id)
    assert plan.status == InterventionStatus.PENDING_REVIEW

    # Direct execution without approval must be rejected with 422
    res = await async_client.post(f"/api/interventions/{plan.id}/execute")
    assert res.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
    assert "approval is required" in res.json()["detail"].lower()


@pytest.mark.asyncio
async def test_15_execution_approved_to_executed(async_client: AsyncClient, db_session: AsyncSession):
    now = utc_now()
    ob = Obligation(
        owner="Rahul",
        beneficiary="Ravi",
        action="Send server latency reports",
        deadline=now - timedelta(hours=2),
        status=ObligationStatus.OVERDUE,
        obligation_type=ObligationType.OWED_TO_ME,
    )
    db_session.add(ob)
    await db_session.commit()

    plan = await InterventionPlanner.plan_intervention(db_session, ob.id)
    await InterventionService.approve(db_session, plan.id)

    res = await async_client.post(f"/api/interventions/{plan.id}/execute")
    assert res.status_code == status.HTTP_200_OK
    data = res.json()
    assert data["status"] == "EXECUTED"
    assert data["executed_at"] is not None
    assert data["execution_reference"].startswith("SIM-DEMO-")
    assert data["execution_mode"] == "MOCK_DEMO"


@pytest.mark.asyncio
async def test_16_cancellation(async_client: AsyncClient, db_session: AsyncSession):
    now = utc_now()
    ob = Obligation(
        owner="Rahul",
        beneficiary="Ravi",
        action="Audit error log dump",
        deadline=now - timedelta(hours=1),
        status=ObligationStatus.OVERDUE,
        obligation_type=ObligationType.OWED_TO_ME,
    )
    db_session.add(ob)
    await db_session.commit()

    plan = await InterventionPlanner.plan_intervention(db_session, ob.id)

    res = await async_client.post(f"/api/interventions/{plan.id}/cancel?reason=No+longer+required")
    assert res.status_code == status.HTTP_200_OK
    assert res.json()["status"] == "CANCELLED"


@pytest.mark.asyncio
async def test_17_scheduling(async_client: AsyncClient, db_session: AsyncSession):
    now = utc_now()
    ob = Obligation(
        owner="Rahul",
        beneficiary="Ravi",
        action="Review Kubernetes Helm charts",
        deadline=now + timedelta(days=2),
        status=ObligationStatus.CONFIRMED,
        obligation_type=ObligationType.OWED_TO_ME,
    )
    db_session.add(ob)
    await db_session.commit()

    plan = await InterventionPlanner.plan_intervention(db_session, ob.id, force=True)
    future_time = now + timedelta(hours=24)

    res = await async_client.post(
        f"/api/interventions/{plan.id}/schedule",
        json={"scheduled_for": future_time.isoformat(), "approved_by": "Ravi"},
    )
    assert res.status_code == status.HTTP_200_OK
    data = res.json()
    assert data["status"] == "SCHEDULED"
    assert data["scheduled_for"] is not None


@pytest.mark.asyncio
async def test_18_scheduled_intervention_queue_prioritization(async_client: AsyncClient, db_session: AsyncSession):
    now = utc_now()
    ob = Obligation(
        owner="Rahul",
        beneficiary="Ravi",
        action="Send Redis cache configs",
        deadline=now - timedelta(hours=2),
        status=ObligationStatus.OVERDUE,
        obligation_type=ObligationType.OWED_TO_ME,
    )
    db_session.add(ob)
    await db_session.commit()

    plan = await InterventionPlanner.plan_intervention(db_session, ob.id)
    await InterventionService.approve(db_session, plan.id)

    res = await async_client.get("/api/interventions/queue")
    assert res.status_code == status.HTTP_200_OK
    data = res.json()
    assert data["total_action_required"] >= 1
    assert any(it["id"] == plan.id for it in data["items"])


@pytest.mark.asyncio
async def test_19_outcome_recording(async_client: AsyncClient, db_session: AsyncSession):
    now = utc_now()
    ob = Obligation(
        owner="Rahul",
        beneficiary="Ravi",
        action="Verify SSL pinning",
        deadline=now - timedelta(hours=1),
        status=ObligationStatus.OVERDUE,
        obligation_type=ObligationType.OWED_TO_ME,
    )
    db_session.add(ob)
    await db_session.commit()

    plan = await InterventionPlanner.plan_intervention(db_session, ob.id)
    await InterventionService.approve(db_session, plan.id)
    await InterventionService.execute(db_session, plan.id)

    res = await async_client.post(
        f"/api/interventions/{plan.id}/outcome",
        json={"outcome": "ACKNOWLEDGED", "notes": "Rahul replied via chat that he is working on it."},
    )
    assert res.status_code == status.HTTP_200_OK
    data = res.json()
    assert data["outcome"] == "ACKNOWLEDGED"
    assert data["status"] == "ACKNOWLEDGED"


@pytest.mark.asyncio
async def test_20_acknowledgement_outcome_updates_state(db_session: AsyncSession):
    now = utc_now()
    ob = Obligation(
        owner="Rahul",
        beneficiary="Ravi",
        action="Send DB metrics",
        deadline=now - timedelta(hours=1),
        status=ObligationStatus.OVERDUE,
        obligation_type=ObligationType.OWED_TO_ME,
    )
    db_session.add(ob)
    await db_session.commit()

    plan = await InterventionPlanner.plan_intervention(db_session, ob.id)
    await InterventionService.approve(db_session, plan.id)
    await InterventionService.execute(db_session, plan.id)

    from app.schemas.intervention import InterventionOutcomeRequest
    updated = await InterventionService.record_outcome(
        db_session, plan.id, InterventionOutcomeRequest(outcome=InterventionOutcome.ACKNOWLEDGED)
    )
    assert updated.outcome == InterventionOutcome.ACKNOWLEDGED
    assert updated.status == InterventionStatus.ACKNOWLEDGED


@pytest.mark.asyncio
async def test_21_no_response_outcome(db_session: AsyncSession):
    now = utc_now()
    ob = Obligation(
        owner="Rahul",
        beneficiary="Ravi",
        action="Send DB metrics",
        deadline=now - timedelta(hours=1),
        status=ObligationStatus.OVERDUE,
        obligation_type=ObligationType.OWED_TO_ME,
    )
    db_session.add(ob)
    await db_session.commit()

    plan = await InterventionPlanner.plan_intervention(db_session, ob.id)
    await InterventionService.approve(db_session, plan.id)
    await InterventionService.execute(db_session, plan.id)

    from app.schemas.intervention import InterventionOutcomeRequest
    updated = await InterventionService.record_outcome(
        db_session, plan.id, InterventionOutcomeRequest(outcome=InterventionOutcome.NO_RESPONSE)
    )
    assert updated.outcome == InterventionOutcome.NO_RESPONSE


@pytest.mark.asyncio
async def test_22_completion_outcome_resolves_intervention(db_session: AsyncSession):
    now = utc_now()
    ob = Obligation(
        owner="Rahul",
        beneficiary="Ravi",
        action="Send DB metrics",
        deadline=now - timedelta(hours=1),
        status=ObligationStatus.OVERDUE,
        obligation_type=ObligationType.OWED_TO_ME,
    )
    db_session.add(ob)
    await db_session.commit()

    plan = await InterventionPlanner.plan_intervention(db_session, ob.id)
    await InterventionService.approve(db_session, plan.id)
    await InterventionService.execute(db_session, plan.id)

    from app.schemas.intervention import InterventionOutcomeRequest
    updated = await InterventionService.record_outcome(
        db_session, plan.id, InterventionOutcomeRequest(outcome=InterventionOutcome.COMPLETED)
    )
    assert updated.outcome == InterventionOutcome.COMPLETED
    assert updated.status == InterventionStatus.RESOLVED


@pytest.mark.asyncio
async def test_23_evidence_confirmation_resolves_intervention(db_session: AsyncSession):
    now = utc_now()
    ob = Obligation(
        owner="Rahul",
        beneficiary="Ravi",
        action="Send benchmark spreadsheet",
        deadline=now - timedelta(hours=1),
        status=ObligationStatus.OVERDUE,
        obligation_type=ObligationType.OWED_TO_ME,
    )
    db_session.add(ob)
    await db_session.flush()

    plan = await InterventionPlanner.plan_intervention(db_session, ob.id)
    await InterventionService.approve(db_session, plan.id)
    await InterventionService.execute(db_session, plan.id)

    ev = Evidence(
        obligation_id=ob.id,
        evidence_type=EvidenceType.FILE,
        source_type="upload",
        content="Uploaded spreadsheet benchmark.xlsx",
        semantic_role=EventSemanticRole.COMPLETION_SIGNAL,
        correlation_status=CorrelationStatus.SUGGESTED,
        correlation_confidence=0.92,
    )
    db_session.add(ev)
    await db_session.commit()

    # Confirm evidence via ObligationService
    from app.services.obligation_service import ObligationService
    await ObligationService.confirm_evidence(db_session, ob.id, ev.id)

    # Active intervention must now be auto-resolved
    inv = await db_session.get(Intervention, plan.id)
    assert inv.status == InterventionStatus.RESOLVED
    assert inv.outcome == InterventionOutcome.COMPLETED


@pytest.mark.asyncio
async def test_24_no_response_increases_risk_appropriately(db_session: AsyncSession):
    now = utc_now()
    ob = Obligation(
        owner="Rahul",
        beneficiary="Ravi",
        action="Audit cloud firewall logs",
        deadline=now + timedelta(days=2),
        status=ObligationStatus.CONFIRMED,
        obligation_type=ObligationType.OWED_TO_ME,
    )
    db_session.add(ob)
    await db_session.commit()

    inv = Intervention(
        obligation_id=ob.id,
        intervention_type=InterventionType.FOLLOW_UP_OWNER,
        target_owner="Rahul",
        target_beneficiary="Ravi",
        title="Follow up",
        rationale="Follow up",
        message_draft="Follow up",
        urgency="HIGH",
        status=InterventionStatus.EXECUTED,
        outcome=InterventionOutcome.NO_RESPONSE,
        executed_at=now - timedelta(hours=26),
    )
    db_session.add(inv)
    await db_session.commit()

    risk = await RiskEngine.assess_obligation(db_session, ob.id)
    assert any(s.signal_type == "NO_RESPONSE_AFTER_INTERVENTION" for s in risk.signals)


@pytest.mark.asyncio
async def test_25_acknowledgement_reduces_risk_appropriately(db_session: AsyncSession):
    now = utc_now()
    ob = Obligation(
        owner="Rahul",
        beneficiary="Ravi",
        action="Review security whitepaper",
        deadline=now + timedelta(hours=18),
        status=ObligationStatus.CONFIRMED,
        obligation_type=ObligationType.OWED_TO_ME,
    )
    db_session.add(ob)
    await db_session.commit()

    inv = Intervention(
        obligation_id=ob.id,
        intervention_type=InterventionType.FOLLOW_UP_OWNER,
        target_owner="Rahul",
        target_beneficiary="Ravi",
        title="Follow up",
        rationale="Follow up",
        message_draft="Follow up",
        urgency="HIGH",
        status=InterventionStatus.ACKNOWLEDGED,
        outcome=InterventionOutcome.ACKNOWLEDGED,
        executed_at=now - timedelta(hours=2),
    )
    db_session.add(inv)
    await db_session.commit()

    risk = await RiskEngine.assess_obligation(db_session, ob.id)
    assert any(s.signal_type == "ACKNOWLEDGED_INTERVENTION" for s in risk.signals)


@pytest.mark.asyncio
async def test_26_completion_removes_active_risk(db_session: AsyncSession):
    now = utc_now()
    ob = Obligation(
        owner="Rahul",
        beneficiary="Ravi",
        action="Sign off on penetration test",
        deadline=now - timedelta(hours=10),
        status=ObligationStatus.COMPLETED,
        obligation_type=ObligationType.OWED_TO_ME,
    )
    db_session.add(ob)
    await db_session.commit()

    risk = await RiskEngine.assess_obligation(db_session, ob.id)
    assert risk.risk_score == 0.0
    assert risk.risk_level == RiskLevel.LOW
    assert risk.is_at_risk is False


@pytest.mark.asyncio
async def test_27_intervention_chain_depth_limit(db_session: AsyncSession):
    now = utc_now()
    ob = Obligation(
        owner="Rahul",
        beneficiary="Ravi",
        action="Submit vendor assessment",
        deadline=now - timedelta(hours=2),
        status=ObligationStatus.OVERDUE,
        obligation_type=ObligationType.OWED_TO_ME,
    )
    db_session.add(ob)
    await db_session.flush()

    # Create 3 past interventions
    for i in range(3):
        db_session.add(
            Intervention(
                obligation_id=ob.id,
                intervention_type=InterventionType.FOLLOW_UP_OWNER,
                target_owner="Rahul",
                target_beneficiary="Ravi",
                title=f"Follow up {i+1}",
                rationale="Past follow up",
                message_draft="Past draft",
                status=InterventionStatus.CANCELLED,
            )
        )
    await db_session.commit()

    plan = await InterventionPlanner.plan_intervention(db_session, ob.id, force=True)
    assert plan.chain_depth == 3


@pytest.mark.asyncio
async def test_28_escalation_recommendation_on_repeated_chain(db_session: AsyncSession):
    now = utc_now()
    ob = Obligation(
        owner="Rahul",
        beneficiary="Ravi",
        action="Submit vendor assessment",
        deadline=now - timedelta(hours=2),
        status=ObligationStatus.OVERDUE,
        obligation_type=ObligationType.OWED_TO_ME,
    )
    db_session.add(ob)
    await db_session.flush()

    for i in range(2):
        db_session.add(
            Intervention(
                obligation_id=ob.id,
                intervention_type=InterventionType.FOLLOW_UP_OWNER,
                target_owner="Rahul",
                target_beneficiary="Ravi",
                title=f"Follow up {i+1}",
                rationale="Past follow up",
                message_draft="Past draft",
                status=InterventionStatus.CANCELLED,
            )
        )
    await db_session.commit()

    plan = await InterventionPlanner.plan_intervention(db_session, ob.id, force=True)
    assert "escalat" in plan.rationale.lower()


@pytest.mark.asyncio
async def test_29_audit_trail_logging(async_client: AsyncClient, db_session: AsyncSession):
    now = utc_now()
    ob = Obligation(
        owner="Rahul",
        beneficiary="Ravi",
        action="Audit cloud DNS records",
        deadline=now - timedelta(hours=1),
        status=ObligationStatus.OVERDUE,
        obligation_type=ObligationType.OWED_TO_ME,
    )
    db_session.add(ob)
    await db_session.commit()

    plan = await InterventionPlanner.plan_intervention(db_session, ob.id)
    await async_client.patch(f"/api/interventions/{plan.id}", json={"approved_message": "Edited message draft"})
    await async_client.post(f"/api/interventions/{plan.id}/approve", json={"approved_by": "Ravi"})
    await async_client.post(f"/api/interventions/{plan.id}/execute")

    res = await async_client.get(f"/api/interventions/{plan.id}")
    data = res.json()
    audit_events = [entry["event"] for entry in data["audit_trail"]]
    assert "DRAFT_GENERATED" in audit_events
    assert "EDITED" in audit_events
    assert "APPROVED" in audit_events
    assert "EXECUTED" in audit_events


@pytest.mark.asyncio
async def test_30_human_approval_enforcement(db_session: AsyncSession):
    now = utc_now()
    ob = Obligation(
        owner="Rahul",
        beneficiary="Ravi",
        action="Publish changelog",
        deadline=now - timedelta(hours=1),
        status=ObligationStatus.OVERDUE,
        obligation_type=ObligationType.OWED_TO_ME,
    )
    db_session.add(ob)
    await db_session.commit()

    plan = await InterventionPlanner.plan_intervention(db_session, ob.id)
    assert plan.requires_approval is True
    assert plan.status == InterventionStatus.PENDING_REVIEW


@pytest.mark.asyncio
async def test_31_no_automatic_external_communication(db_session: AsyncSession):
    from app.services.intervention_executor import DevMockInterventionExecutor
    executor = DevMockInterventionExecutor()

    inv = Intervention(
        id="test-inv-id",
        obligation_id="dummy",
        intervention_type=InterventionType.FOLLOW_UP_OWNER,
        target_owner="Rahul",
        target_beneficiary="Ravi",
        title="Test Follow Up",
        rationale="Testing",
        message_draft="Hello Rahul",
        status=InterventionStatus.APPROVED,
    )

    result = await executor.execute(db_session, inv)
    assert result["mode"] == "MOCK_DEMO"
    assert "No external messages were transmitted" in result["note"]


@pytest.mark.asyncio
async def test_32_post_intervention_event_correlation(async_client: AsyncClient, db_session: AsyncSession):
    now = utc_now()
    ob = Obligation(
        owner="Rahul",
        beneficiary="Ravi",
        action="Send benchmark numbers",
        deadline=now - timedelta(hours=1),
        status=ObligationStatus.OVERDUE,
        obligation_type=ObligationType.OWED_TO_ME,
    )
    db_session.add(ob)
    await db_session.commit()

    plan = await InterventionPlanner.plan_intervention(db_session, ob.id)
    await InterventionService.approve(db_session, plan.id)
    await InterventionService.execute(db_session, plan.id)

    # External progress event arrives
    event_payload = {
        "source_type": "slack",
        "source_ref": "msg-12345",
        "sender": "Rahul",
        "recipients": ["Ravi"],
        "content": "Working on benchmark numbers, almost done.",
        "occurred_at": now.isoformat(),
    }
    res = await async_client.post("/api/events", json=event_payload)
    assert res.status_code == status.HTTP_201_CREATED
    data = res.json()
    assert data["ingested"] is True
    assert len(data["matches"]) > 0


@pytest.mark.asyncio
async def test_33_risk_recalculation_after_intervention_outcome(db_session: AsyncSession):
    now = utc_now()
    ob = Obligation(
        owner="Rahul",
        beneficiary="Ravi",
        action="Deliver penetration test certificate",
        deadline=now + timedelta(hours=12),
        status=ObligationStatus.CONFIRMED,
        obligation_type=ObligationType.OWED_TO_ME,
    )
    db_session.add(ob)
    await db_session.commit()

    plan = await InterventionPlanner.plan_intervention(db_session, ob.id)
    await InterventionService.approve(db_session, plan.id)
    await InterventionService.execute(db_session, plan.id)

    # Initial risk assessment
    risk_before = await RiskEngine.assess_obligation(db_session, ob.id)

    # Record acknowledgement
    from app.schemas.intervention import InterventionOutcomeRequest
    await InterventionService.record_outcome(
        db_session, plan.id, InterventionOutcomeRequest(outcome=InterventionOutcome.ACKNOWLEDGED)
    )

    risk_after = await RiskEngine.assess_obligation(db_session, ob.id)
    assert risk_after.risk_score <= risk_before.risk_score
