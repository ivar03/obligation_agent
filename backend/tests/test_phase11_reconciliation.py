import pytest
import uuid
from datetime import datetime, timezone, timedelta
from httpx import AsyncClient, ASGITransport
from sqlalchemy import select

from app.main import app
from app.models.obligation import (
    Obligation,
    ObligationEdge,
    Evidence,
    ReconciliationRecord,
)
from app.core.status_machine import (
    ObligationStatus,
    ObligationType,
    EdgeType,
    EventSemanticRole,
    CorrelationStatus,
    ReconciliationStatus,
    ReconciliationResolutionAction,
    ActionType,
    RiskLevel,
)
from app.schemas.obligation import (
    ReconciliationResolutionRequest,
    ReconciliationDismissRequest,
)
from app.services.reconciliation_service import ReconciliationService
from app.services.event_ingestion_service import EventIngestionService
from app.services.risk_engine import RiskEngine
from app.services.recommendation_engine import RecommendationEngine
from app.services.graph_service import GraphService


@pytest.mark.asyncio
async def test_single_completion_reconciliation(db_session):
    """Test 1: Single completion signal produces a consistent reconciliation record with review recommendation."""
    now = datetime.now(timezone.utc)
    ob = Obligation(
        owner="Rahul",
        beneficiary="Ravi",
        action="Submit quarterly tax analysis report",
        deadline=now + timedelta(days=2),
        status=ObligationStatus.CONFIRMED,
        obligation_type=ObligationType.OWED_TO_ME,
    )
    db_session.add(ob)
    await db_session.commit()
    await db_session.refresh(ob)

    ev = Evidence(
        obligation_id=ob.id,
        evidence_type="MESSAGE",
        source_type="gmail",
        source_ref="gmail:msg:1001",
        content="Here is the quarterly tax analysis report attached.",
        correlation_status=CorrelationStatus.SUGGESTED,
        correlation_confidence=0.92,
        semantic_role=EventSemanticRole.COMPLETION_SIGNAL,
        actor="rahul@acme.com",
        observed_at=now,
    )
    db_session.add(ev)
    await db_session.commit()

    rec = await ReconciliationService.reconcile_obligation(db_session, ob.id)
    assert rec is not None
    assert rec.status == ReconciliationStatus.CONSISTENT
    assert rec.consistency_score >= 0.75
    assert rec.contradiction_score <= 0.10
    assert ev.id in rec.supporting_evidence_ids
    assert len(rec.conflicting_evidence_ids) == 0

    # Core Safety: Obligation must NOT be auto-completed
    await db_session.refresh(ob)
    assert ob.status == ObligationStatus.CONFIRMED


@pytest.mark.asyncio
async def test_multi_provider_reinforcing_consistency(db_session):
    """Test 2: Multi-provider completion signals (Slack + Gmail) reinforce confidence without false contradictions."""
    now = datetime.now(timezone.utc)
    ob = Obligation(
        owner="Rahul",
        beneficiary="Ravi",
        action="Deploy authentication microservice to staging",
        deadline=now + timedelta(days=3),
        status=ObligationStatus.CONFIRMED,
        obligation_type=ObligationType.OWED_TO_ME,
    )
    db_session.add(ob)
    await db_session.commit()
    await db_session.refresh(ob)

    ev1 = Evidence(
        obligation_id=ob.id,
        evidence_type="MESSAGE",
        source_type="slack",
        source_ref="slack:msg:2001",
        content="Deployed auth microservice v2.1 to staging successfully.",
        correlation_status=CorrelationStatus.SUGGESTED,
        correlation_confidence=0.95,
        semantic_role=EventSemanticRole.COMPLETION_SIGNAL,
        actor="rahul_dev",
        observed_at=now - timedelta(minutes=10),
    )
    ev2 = Evidence(
        obligation_id=ob.id,
        evidence_type="MESSAGE",
        source_type="gmail",
        source_ref="gmail:msg:2002",
        content="Hi Ravi, staging deploy of auth service is verified and live.",
        correlation_status=CorrelationStatus.SUGGESTED,
        correlation_confidence=0.96,
        semantic_role=EventSemanticRole.COMPLETION_SIGNAL,
        actor="rahul@acme.com",
        observed_at=now,
    )
    db_session.add_all([ev1, ev2])
    await db_session.commit()

    rec = await ReconciliationService.reconcile_obligation(db_session, ob.id)
    assert rec.status == ReconciliationStatus.CONSISTENT
    assert rec.consistency_score >= 0.90
    assert rec.contradiction_score == 0.0
    assert rec.confidence >= 0.90
    assert rec.recommended_action == ActionType.CONFIRM_COMPLETION_EVIDENCE.value
    assert ev1.id in rec.supporting_evidence_ids
    assert ev2.id in rec.supporting_evidence_ids


@pytest.mark.asyncio
async def test_completion_vs_negative_blocker_contradiction(db_session):
    """Test 3: Completion signal contradicted by a negative blocker signal generates CONFLICTING reconciliation."""
    now = datetime.now(timezone.utc)
    ob = Obligation(
        owner="Rahul",
        beneficiary="Ravi",
        action="Generate data export archive",
        deadline=now + timedelta(days=1),
        status=ObligationStatus.CONFIRMED,
        obligation_type=ObligationType.OWED_TO_ME,
    )
    db_session.add(ob)
    await db_session.commit()
    await db_session.refresh(ob)

    ev_comp = Evidence(
        obligation_id=ob.id,
        evidence_type="MESSAGE",
        source_type="gmail",
        source_ref="gmail:msg:3001",
        content="Data export archive generated and sent.",
        correlation_status=CorrelationStatus.SUGGESTED,
        correlation_confidence=0.90,
        semantic_role=EventSemanticRole.COMPLETION_SIGNAL,
        actor="rahul@acme.com",
        observed_at=now - timedelta(hours=2),
    )
    ev_block = Evidence(
        obligation_id=ob.id,
        evidence_type="MESSAGE",
        source_type="slack",
        source_ref="slack:msg:3002",
        content="Data export failed due to disk space exhaustion. Archive was not created.",
        correlation_status=CorrelationStatus.SUGGESTED,
        correlation_confidence=0.92,
        semantic_role=EventSemanticRole.NON_COMPLETION_SIGNAL,
        actor="rahul_dev",
        observed_at=now,
    )
    db_session.add_all([ev_comp, ev_block])
    await db_session.commit()

    rec = await ReconciliationService.reconcile_obligation(db_session, ob.id)
    assert rec.status == ReconciliationStatus.CONFLICTING
    assert rec.contradiction_score >= 0.70
    assert ev_comp.id in rec.supporting_evidence_ids
    assert ev_block.id in rec.conflicting_evidence_ids
    assert rec.recommended_action == ActionType.REVIEW_CONFLICTING_EVIDENCE.value

    # Evaluate Risk Engine with this contradiction
    assessment = await RiskEngine.assess_obligation(db_session, ob.id)
    assert assessment.risk_level in [RiskLevel.MEDIUM, RiskLevel.HIGH, RiskLevel.CRITICAL]
    signal_types = [s.signal_type for s in assessment.signals]
    assert assessment.action_type in [ActionType.REVIEW_EVIDENCE, ActionType.REVIEW_CONFLICTING_EVIDENCE]


@pytest.mark.asyncio
async def test_completion_vs_later_progress_reversal(db_session):
    """Test 4: Early completion followed by later 'still working' message is flagged as CONFLICTING."""
    now = datetime.now(timezone.utc)
    ob = Obligation(
        owner="Rahul",
        beneficiary="Ravi",
        action="Complete security audit checklist",
        deadline=now + timedelta(days=2),
        status=ObligationStatus.CONFIRMED,
        obligation_type=ObligationType.OWED_TO_ME,
    )
    db_session.add(ob)
    await db_session.commit()
    await db_session.refresh(ob)

    ev_early_comp = Evidence(
        obligation_id=ob.id,
        evidence_type="MESSAGE",
        source_type="gmail",
        source_ref="gmail:msg:4001",
        content="Security audit checklist completed.",
        correlation_status=CorrelationStatus.SUGGESTED,
        correlation_confidence=0.90,
        semantic_role=EventSemanticRole.COMPLETION_SIGNAL,
        observed_at=now - timedelta(hours=4),
    )
    ev_later_prog = Evidence(
        obligation_id=ob.id,
        evidence_type="MESSAGE",
        source_type="slack",
        source_ref="slack:msg:4002",
        content="Still working on the security audit checklist items today.",
        correlation_status=CorrelationStatus.SUGGESTED,
        correlation_confidence=0.88,
        semantic_role=EventSemanticRole.PROGRESS_UPDATE,
        observed_at=now,
    )
    db_session.add_all([ev_early_comp, ev_later_prog])
    await db_session.commit()

    rec = await ReconciliationService.reconcile_obligation(db_session, ob.id)
    assert rec.status == ReconciliationStatus.CONFLICTING
    assert rec.contradiction_score >= 0.70
    assert rec.recommended_action == ActionType.REVIEW_STALE_SIGNAL.value


@pytest.mark.asyncio
async def test_progress_followed_by_later_completion_is_consistent(db_session):
    """Test 5: Earlier progress update followed by later completion is coherent and CONSISTENT."""
    now = datetime.now(timezone.utc)
    ob = Obligation(
        owner="Rahul",
        beneficiary="Ravi",
        action="Draft API integration guide",
        deadline=now + timedelta(days=3),
        status=ObligationStatus.CONFIRMED,
        obligation_type=ObligationType.OWED_TO_ME,
    )
    db_session.add(ob)
    await db_session.commit()
    await db_session.refresh(ob)

    ev_prog = Evidence(
        obligation_id=ob.id,
        evidence_type="MESSAGE",
        source_type="slack",
        source_ref="slack:msg:5001",
        content="Started drafting the API integration guide today.",
        correlation_status=CorrelationStatus.SUGGESTED,
        correlation_confidence=0.85,
        semantic_role=EventSemanticRole.PROGRESS_UPDATE,
        observed_at=now - timedelta(hours=3),
    )
    ev_comp = Evidence(
        obligation_id=ob.id,
        evidence_type="MESSAGE",
        source_type="gmail",
        source_ref="gmail:msg:5002",
        content="Finished and attached the finalized API integration guide.",
        correlation_status=CorrelationStatus.SUGGESTED,
        correlation_confidence=0.95,
        semantic_role=EventSemanticRole.COMPLETION_SIGNAL,
        observed_at=now,
    )
    db_session.add_all([ev_prog, ev_comp])
    await db_session.commit()

    rec = await ReconciliationService.reconcile_obligation(db_session, ob.id)
    assert rec.status == ReconciliationStatus.CONSISTENT
    assert rec.consistency_score >= 0.85
    assert rec.contradiction_score <= 0.10


@pytest.mark.asyncio
async def test_conditional_prerequisite_conflict(db_session):
    """Test 6: Completion signal received on a BLOCKED obligation generates AMBIGUOUS reconciliation."""
    now = datetime.now(timezone.utc)
    ob = Obligation(
        owner="Rahul",
        beneficiary="Ravi",
        action="Present executive review",
        deadline=now + timedelta(days=4),
        status=ObligationStatus.BLOCKED,
        obligation_type=ObligationType.OWED_BY_ME,
        block_reason={"blocked": True, "reason": "Awaiting benchmark report"},
    )
    db_session.add(ob)
    await db_session.commit()
    await db_session.refresh(ob)

    ev = Evidence(
        obligation_id=ob.id,
        evidence_type="MESSAGE",
        source_type="slack",
        source_ref="slack:msg:6001",
        content="Presented the executive review slides.",
        correlation_status=CorrelationStatus.SUGGESTED,
        correlation_confidence=0.90,
        semantic_role=EventSemanticRole.COMPLETION_SIGNAL,
        observed_at=now,
    )
    db_session.add(ev)
    await db_session.commit()

    rec = await ReconciliationService.reconcile_obligation(db_session, ob.id)
    assert rec.status == ReconciliationStatus.AMBIGUOUS
    assert "active prerequisite dependencies" in rec.explanation[0]


@pytest.mark.asyncio
async def test_human_resolution_confirm_completion_and_graph_cascade(db_session):
    """Test 7: Human resolution with CONFIRM_COMPLETION completes obligation and unblocks graph dependents."""
    now = datetime.now(timezone.utc)
    ob_a = Obligation(
        owner="Rahul",
        beneficiary="Ravi",
        action="Finalize legal contract terms",
        deadline=now + timedelta(days=2),
        status=ObligationStatus.CONFIRMED,
        obligation_type=ObligationType.OWED_TO_ME,
    )
    ob_b = Obligation(
        owner="Ravi",
        beneficiary="Partner",
        action="Countersign and execute partnership agreement",
        deadline=now + timedelta(days=3),
        status=ObligationStatus.BLOCKED,
        obligation_type=ObligationType.OWED_BY_ME,
        block_reason={"blocked": True, "blocked_by": [{"obligation_id": "placeholder"}]},
    )
    db_session.add_all([ob_a, ob_b])
    await db_session.commit()
    await db_session.refresh(ob_a)
    await db_session.refresh(ob_b)

    # Edge: B depends on A
    edge = ObligationEdge(
        from_obligation_id=ob_b.id,
        to_obligation_id=ob_a.id,
        edge_type=EdgeType.DEPENDS_ON,
    )
    db_session.add(edge)
    await db_session.commit()

    # Ingest completion evidence
    ev = Evidence(
        obligation_id=ob_a.id,
        evidence_type="MESSAGE",
        source_type="gmail",
        source_ref="gmail:msg:7001",
        content="Attached finalized contract terms agreed with partner.",
        correlation_status=CorrelationStatus.SUGGESTED,
        correlation_confidence=0.95,
        semantic_role=EventSemanticRole.COMPLETION_SIGNAL,
        observed_at=now,
    )
    db_session.add(ev)
    await db_session.commit()

    rec = await ReconciliationService.reconcile_obligation(db_session, ob_a.id)

    # Human operator resolves reconciliation by confirming completion
    req = ReconciliationResolutionRequest(
        action=ReconciliationResolutionAction.CONFIRM_COMPLETION,
        notes="Reviewed PDF and confirmed terms match requirements.",
        operator="Ravi",
        selected_evidence_id=ev.id,
    )
    res = await ReconciliationService.resolve_reconciliation(db_session, rec.id, req)
    assert res.status == ReconciliationStatus.RESOLVED_SUPPORTING
    assert res.resolved_by == "Ravi"
    assert res.resolution["action"] == "CONFIRM_COMPLETION"

    # Obligation A must be COMPLETED
    await db_session.refresh(ob_a)
    assert ob_a.status == ObligationStatus.COMPLETED

    # Downstream Obligation B must be unblocked to CONFIRMED
    await db_session.refresh(ob_b)
    assert ob_b.status == ObligationStatus.CONFIRMED


@pytest.mark.asyncio
async def test_human_resolution_keep_active_and_dismiss(db_session):
    """Test 8: Human resolution KEEP_OBLIGATION_ACTIVE and DISMISS_CONTRADICTION preserves active status."""
    now = datetime.now(timezone.utc)
    ob = Obligation(
        owner="Rahul",
        beneficiary="Ravi",
        action="Submit security penetration test report",
        deadline=now + timedelta(days=2),
        status=ObligationStatus.CONFIRMED,
        obligation_type=ObligationType.OWED_TO_ME,
    )
    db_session.add(ob)
    await db_session.commit()
    await db_session.refresh(ob)

    ev_block = Evidence(
        obligation_id=ob.id,
        evidence_type="MESSAGE",
        source_type="slack",
        source_ref="slack:msg:8001",
        content="Penetration testing paused due to staging maintenance.",
        correlation_status=CorrelationStatus.SUGGESTED,
        correlation_confidence=0.88,
        semantic_role=EventSemanticRole.NON_COMPLETION_SIGNAL,
        observed_at=now,
    )
    db_session.add(ev_block)
    await db_session.commit()

    rec = await ReconciliationService.reconcile_obligation(db_session, ob.id)
    assert rec.status == ReconciliationStatus.CONFLICTING

    # Keep Active resolution
    req = ReconciliationResolutionRequest(
        action=ReconciliationResolutionAction.KEEP_OBLIGATION_ACTIVE,
        notes="Acknowledged delay, keeping task active.",
        operator="Security Lead",
    )
    res = await ReconciliationService.resolve_reconciliation(db_session, rec.id, req)
    assert res.status == ReconciliationStatus.RESOLVED_CONFLICTING
    await db_session.refresh(ob)
    assert ob.status == ObligationStatus.CONFIRMED

    # Dismiss test
    rec2 = await ReconciliationService.reconcile_obligation(db_session, ob.id)
    dismiss_req = ReconciliationDismissRequest(reason="Known noise", operator="Lead")
    dismiss_res = await ReconciliationService.dismiss_reconciliation(db_session, rec2.id, dismiss_req)
    assert dismiss_res.status == ReconciliationStatus.DISMISSED


@pytest.mark.asyncio
async def test_reconciliation_api_endpoints(client, db_session):
    """Test 9: REST API endpoints for listing, fetching, and resolving reconciliations."""
    now = datetime.now(timezone.utc)
    ob = Obligation(
        owner="Rahul",
        beneficiary="Ravi",
        action="API Integration Deliverable Verification",
        deadline=now + timedelta(days=2),
        status=ObligationStatus.CONFIRMED,
        obligation_type=ObligationType.OWED_TO_ME,
    )
    db_session.add(ob)
    await db_session.commit()
    await db_session.refresh(ob)

    ev = Evidence(
        obligation_id=ob.id,
        evidence_type="MESSAGE",
        source_type="gmail",
        source_ref="gmail:msg:api:9001",
        content="API integration deliverable completed.",
        correlation_status=CorrelationStatus.SUGGESTED,
        correlation_confidence=0.90,
        semantic_role=EventSemanticRole.COMPLETION_SIGNAL,
        observed_at=now,
    )
    db_session.add(ev)
    await db_session.commit()

    rec = await ReconciliationService.reconcile_obligation(db_session, ob.id)

    # GET /api/reconciliation
    res_list = await client.get("/api/reconciliation")
    assert res_list.status_code == 200
    data_list = res_list.json()
    assert data_list["total"] >= 1

    # GET /api/reconciliation/{id}
    res_get = await client.get(f"/api/reconciliation/{rec.id}")
    assert res_get.status_code == 200
    data_get = res_get.json()
    assert data_get["id"] == rec.id
    assert len(data_get["evidence_timeline"]) >= 1

    # GET /api/obligations/{id}/reconciliation
    res_ob = await client.get(f"/api/obligations/{ob.id}/reconciliation")
    assert res_ob.status_code == 200
    assert res_ob.json()["id"] == rec.id

    # POST /api/reconciliation/{id}/resolve
    res_resolve = await client.post(
        f"/api/reconciliation/{rec.id}/resolve",
        json={
            "action": "CONFIRM_COMPLETION",
            "notes": "Verified via REST API endpoint.",
            "operator": "API Operator",
        },
    )
    assert res_resolve.status_code == 200
    assert res_resolve.json()["status"] == "RESOLVED_SUPPORTING"


@pytest.mark.asyncio
async def test_reconciliation_triggered_by_event_ingestion(db_session):
    """Test 10: Event ingestion pipeline automatically triggers reconciliation for affected obligations."""
    now = datetime.now(timezone.utc)
    ob = Obligation(
        owner="Rahul",
        beneficiary="Ravi",
        action="Deliver project status report",
        deadline=now + timedelta(days=2),
        status=ObligationStatus.CONFIRMED,
        obligation_type=ObligationType.OWED_TO_ME,
    )
    db_session.add(ob)
    await db_session.commit()
    await db_session.refresh(ob)

    # Ingest Gmail event
    payload = {
        "from": "Rahul <rahul@acme.com>",
        "to": ["Ravi <ravi@acme.com>"],
        "subject": "Deliver project status report",
        "body": "Hi Ravi, please find attached the delivered project status report.",
        "attachments": [{"name": "status_report.pdf", "size": 15000}],
    }
    res = await EventIngestionService.ingest_from_provider(db_session, "gmail", payload)
    assert res.status == "PROCESSED"
    assert ob.id in res.affected_obligation_ids

    # Query reconciliation record created automatically
    rec_stmt = select(ReconciliationRecord).where(ReconciliationRecord.obligation_id == ob.id)
    rec_res = await db_session.execute(rec_stmt)
    rec = rec_res.scalars().first()
    assert rec is not None
    assert rec.status == ReconciliationStatus.CONSISTENT
    assert len(rec.supporting_evidence_ids) >= 1


@pytest.mark.asyncio
async def test_reconciliation_reopening_behavior(db_session):
    """Test 11: Reopening a completed obligation transitions status and re-evaluates dependencies."""
    now = datetime.now(timezone.utc)
    ob = Obligation(
        owner="Rahul",
        beneficiary="Ravi",
        action="Complete database migration script",
        deadline=now + timedelta(days=2),
        status=ObligationStatus.COMPLETED,
        obligation_type=ObligationType.OWED_TO_ME,
    )
    db_session.add(ob)
    await db_session.commit()
    await db_session.refresh(ob)

    rec = ReconciliationRecord(
        obligation_id=ob.id,
        status=ReconciliationStatus.RESOLVED_SUPPORTING,
        confidence=0.90,
        consistency_score=0.90,
    )
    db_session.add(rec)
    await db_session.commit()
    await db_session.refresh(rec)

    # Reopen request
    req = ReconciliationResolutionRequest(
        action=ReconciliationResolutionAction.REOPEN_OBLIGATION,
        notes="Customer reported migration bug; reopening task.",
        operator="Ravi",
    )
    res = await ReconciliationService.resolve_reconciliation(db_session, rec.id, req)
    assert res.status == ReconciliationStatus.RESOLVED_CONFLICTING
    await db_session.refresh(ob)
    assert ob.status == ObligationStatus.IN_PROGRESS


@pytest.mark.asyncio
async def test_reconciliation_mark_as_stale(db_session):
    """Test 12: MARK_AS_STALE marks conflicting evidence as rejected and updates reconciliation."""
    now = datetime.now(timezone.utc)
    ob = Obligation(
        owner="Rahul",
        beneficiary="Ravi",
        action="Deliver design assets",
        deadline=now + timedelta(days=2),
        status=ObligationStatus.CONFIRMED,
        obligation_type=ObligationType.OWED_TO_ME,
    )
    db_session.add(ob)
    await db_session.commit()
    await db_session.refresh(ob)

    ev_conf = Evidence(
        obligation_id=ob.id,
        evidence_type="MESSAGE",
        source_type="slack",
        source_ref="slack:stale:101",
        content="Design assets delayed.",
        correlation_status=CorrelationStatus.SUGGESTED,
        correlation_confidence=0.85,
        semantic_role=EventSemanticRole.NON_COMPLETION_SIGNAL,
        observed_at=now - timedelta(days=1),
    )
    db_session.add(ev_conf)
    await db_session.commit()

    rec = await ReconciliationService.reconcile_obligation(db_session, ob.id)
    assert rec.status == ReconciliationStatus.CONFLICTING

    req = ReconciliationResolutionRequest(
        action=ReconciliationResolutionAction.MARK_AS_STALE,
        notes="Older blocker was resolved in subsequent sprint.",
        operator="Design Lead",
    )
    res = await ReconciliationService.resolve_reconciliation(db_session, rec.id, req)
    assert res.status == ReconciliationStatus.RESOLVED_SUPPORTING
    await db_session.refresh(ev_conf)
    assert ev_conf.correlation_status == CorrelationStatus.REJECTED


@pytest.mark.asyncio
async def test_reconciliation_idempotency_duplicate_events(db_session):
    """Test 13: Reprocessing the same event does not duplicate reconciliation records."""
    now = datetime.now(timezone.utc)
    ob = Obligation(
        owner="Rahul",
        beneficiary="Ravi",
        action="Send weekly budget update",
        deadline=now + timedelta(days=2),
        status=ObligationStatus.CONFIRMED,
        obligation_type=ObligationType.OWED_TO_ME,
    )
    db_session.add(ob)
    await db_session.commit()
    await db_session.refresh(ob)

    payload = {
        "from": "Rahul <rahul@acme.com>",
        "to": ["Ravi <ravi@acme.com>"],
        "subject": "Send weekly budget update",
        "body": "Hi Ravi, attached is the weekly budget update.",
    }
    # Ingest once
    res1 = await EventIngestionService.ingest_from_provider(db_session, "gmail", payload)
    # Ingest second time (idempotency check)
    res2 = await EventIngestionService.ingest_from_provider(db_session, "gmail", payload)

    # Count reconciliation records for this obligation
    rec_stmt = select(ReconciliationRecord).where(ReconciliationRecord.obligation_id == ob.id)
    rec_res = await db_session.execute(rec_stmt)
    recs = list(rec_res.scalars().all())
    assert len(recs) == 1


@pytest.mark.asyncio
async def test_cross_provider_coexistence_calendar_slack_gmail(db_session):
    """Test 14: Comprehensive scenario with Slack progress, Google Calendar meeting, and Gmail deliverable."""
    now = datetime.now(timezone.utc)
    ob = Obligation(
        owner="Rahul",
        beneficiary="Ravi",
        action="Deliver architecture specification doc",
        deadline=now + timedelta(days=3),
        status=ObligationStatus.CONFIRMED,
        obligation_type=ObligationType.OWED_TO_ME,
    )
    db_session.add(ob)
    await db_session.commit()
    await db_session.refresh(ob)

    # 1. Slack progress update
    ev_slack = Evidence(
        obligation_id=ob.id,
        evidence_type="MESSAGE",
        source_type="slack",
        source_ref="slack:arch:1",
        content="Working on the architecture specification doc.",
        correlation_status=CorrelationStatus.SUGGESTED,
        correlation_confidence=0.85,
        semantic_role=EventSemanticRole.PROGRESS_UPDATE,
        observed_at=now - timedelta(hours=5),
    )
    # 2. Google Calendar meeting completed
    ev_cal = Evidence(
        obligation_id=ob.id,
        evidence_type="EVENT",
        source_type="google_calendar",
        source_ref="google_calendar:arch:2",
        content="Architecture specification review meeting.",
        correlation_status=CorrelationStatus.SUGGESTED,
        correlation_confidence=0.80,
        semantic_role=EventSemanticRole.PROGRESS_UPDATE,
        extra_metadata={"source_provider": "google_calendar", "meeting_status": "MEETING_COMPLETED"},
        observed_at=now - timedelta(hours=2),
    )
    # 3. Gmail deliverable sent
    ev_gmail = Evidence(
        obligation_id=ob.id,
        evidence_type="MESSAGE",
        source_type="gmail",
        source_ref="gmail:arch:3",
        content="Final architecture specification doc attached for approval.",
        correlation_status=CorrelationStatus.SUGGESTED,
        correlation_confidence=0.95,
        semantic_role=EventSemanticRole.COMPLETION_SIGNAL,
        observed_at=now,
    )
    db_session.add_all([ev_slack, ev_cal, ev_gmail])
    await db_session.commit()

    rec = await ReconciliationService.reconcile_obligation(db_session, ob.id)
    assert rec.status == ReconciliationStatus.CONSISTENT
    assert rec.consistency_score >= 0.85
    assert rec.contradiction_score <= 0.10
    assert rec.recommended_action == ActionType.CONFIRM_COMPLETION_EVIDENCE.value

    # Verify Risk Engine evaluates strong supporting evidence
    assessment = await RiskEngine.assess_obligation(db_session, ob.id)
    assert assessment.action_type == ActionType.CONFIRM_COMPLETION_EVIDENCE

