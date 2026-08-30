import pytest
from datetime import datetime, timezone, timedelta
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import status

from app.core.status_machine import (
    ObligationStatus,
    ObligationType,
    EdgeType,
    EventSemanticRole,
    CorrelationStatus,
)
from app.core.intervention_status import InterventionStatus, InterventionType, InterventionOutcome
from app.models.obligation import Obligation, ObligationEdge, Evidence, Intervention, IngestedEventRecord
from app.schemas.obligation import ExternalEvent, IngestRawEventRequest, EventSimulateRequest
from app.services.providers.registry import provider_registry, ProviderRegistry
from app.services.providers.mock_provider import MockProvider
from app.services.providers.base_provider import BaseProvider
from app.services.event_ingestion_service import EventIngestionService
from app.services.graph_service import GraphService
from app.services.risk_engine import RiskEngine


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


@pytest.mark.asyncio
async def test_1_provider_registry_lookup():
    """1. Verify provider registry returns registered providers."""
    mock = provider_registry.get("mock")
    assert mock is not None
    assert mock.provider_name == "mock"
    assert mock.provider_version == "1.0.0"
    assert "simulation" in mock.capabilities

    providers = provider_registry.list_providers()
    assert any(p["name"] == "mock" for p in providers)


@pytest.mark.asyncio
async def test_2_unknown_provider_rejection():
    """2. Unknown provider raises ValueError / 400."""
    with pytest.raises(ValueError) as exc:
        provider_registry.get("non_existent_provider_xyz")
    assert "Unknown provider" in str(exc.value)


@pytest.mark.asyncio
async def test_3_mock_event_normalization():
    """3. MockProvider correctly normalizes raw payloads and canonical scenarios."""
    provider = MockProvider()
    
    # Test dictionary normalization
    raw = {
        "text": "Sent the database benchmark numbers.",
        "author": "Rahul",
        "to": ["Ravi"],
        "message_id": "msg_001",
        "attachments": [{"name": "benchmarks.csv"}],
    }
    event = provider.normalize_event(raw)
    assert event.content == "Sent the database benchmark numbers."
    assert event.sender == "Rahul"
    assert event.recipients == ["Ravi"]
    assert event.source_ref == "msg_001"
    assert "attachments" in event.metadata

    # Test canonical scenario generation
    scenario_b = provider.generate_canonical_event(MockProvider.SCENARIO_PROGRESS)
    assert "working on" in scenario_b.content.lower()
    assert scenario_b.sender == "Rahul"


@pytest.mark.asyncio
async def test_4_successful_ingestion(client: AsyncClient, db_session: AsyncSession):
    """4. Successful ingestion of a raw event creates audit record and returns PROCESSED."""
    ob = Obligation(
        owner="Rahul",
        beneficiary="Ravi",
        action="Send database benchmark numbers",
        status=ObligationStatus.CONFIRMED,
        obligation_type=ObligationType.OWED_TO_ME,
    )
    db_session.add(ob)
    await db_session.commit()

    payload = {
        "provider": "mock",
        "payload": {
            "content": "Sent the database benchmark numbers.",
            "sender": "Rahul",
            "recipients": ["Ravi"],
            "source_ref": "ref_succ_001",
        }
    }
    res = await client.post("/api/events/ingest", json=payload)
    assert res.status_code == status.HTTP_201_CREATED
    data = res.json()
    assert data["status"] == "PROCESSED"
    assert data["semantic_role"] == "COMPLETION_SIGNAL"
    assert len(data["evidence_records"]) == 1
    assert ob.id in data["affected_obligation_ids"]


@pytest.mark.asyncio
async def test_5_duplicate_event_detection(client: AsyncClient, db_session: AsyncSession):
    """5. Duplicate event detection returns DUPLICATE without creating double evidence."""
    ob = Obligation(
        owner="Rahul",
        beneficiary="Ravi",
        action="Send database benchmark numbers",
        status=ObligationStatus.CONFIRMED,
        obligation_type=ObligationType.OWED_TO_ME,
    )
    db_session.add(ob)
    await db_session.commit()

    payload = {
        "provider": "mock",
        "payload": {
            "content": "Sent the database benchmark numbers.",
            "sender": "Rahul",
            "recipients": ["Ravi"],
            "source_ref": "dup_test_ref_999",
        }
    }
    # First ingestion
    res1 = await client.post("/api/events/ingest", json=payload)
    assert res1.status_code == status.HTTP_201_CREATED
    assert res1.json()["status"] == "PROCESSED"

    # Second duplicate ingestion
    res2 = await client.post("/api/events/ingest", json=payload)
    assert res2.status_code == status.HTTP_201_CREATED
    data2 = res2.json()
    assert data2["status"] == "DUPLICATE"
    assert "Duplicate event detected" in data2["message"]


@pytest.mark.asyncio
async def test_6_event_classification(client: AsyncClient):
    """6. Stateless event analysis classifies various semantic roles correctly."""
    res_comp = await client.post("/api/events/analyze", json={
        "content": "Sent the finalized report to the stakeholders.",
        "sender": "Rahul",
    })
    assert res_comp.json()["semantic_role"] == "COMPLETION_SIGNAL"

    res_prog = await client.post("/api/events/analyze", json={
        "content": "Working on the performance benchmarks now.",
        "sender": "Rahul",
    })
    assert res_prog.json()["semantic_role"] == "PROGRESS_UPDATE"

    res_block = await client.post("/api/events/analyze", json={
        "content": "I couldn't send the export because the cluster is down.",
        "sender": "Rahul",
    })
    assert res_block.json()["semantic_role"] == "NON_COMPLETION_SIGNAL"


@pytest.mark.asyncio
async def test_7_completion_candidate_correlation(client: AsyncClient, db_session: AsyncSession):
    """7. Completion event produces high confidence match candidate."""
    ob = Obligation(
        owner="Rahul",
        beneficiary="Ravi",
        action="Deploy authentication service to staging",
        status=ObligationStatus.IN_PROGRESS,
        obligation_type=ObligationType.OWED_TO_ME,
    )
    db_session.add(ob)
    await db_session.commit()

    res = await client.post("/api/events/ingest", json={
        "provider": "mock",
        "payload": {
            "content": "Deployed authentication service to staging environment.",
            "sender": "Rahul",
            "recipients": ["Ravi"],
            "source_ref": "deploy_ref_01",
        }
    })
    assert res.status_code == status.HTTP_201_CREATED
    data = res.json()
    assert data["semantic_role"] == "COMPLETION_SIGNAL"
    assert len(data["matches"]) >= 1
    best = data["matches"][0]
    assert best["is_completion_candidate"] is True
    assert best["correlation_confidence"] >= 0.80


@pytest.mark.asyncio
async def test_8_progress_event_handling(client: AsyncClient, db_session: AsyncSession):
    """8. Progress update is correlated and marked with PROGRESS_UPDATE role."""
    ob = Obligation(
        owner="Rahul",
        beneficiary="Ravi",
        action="Compile quarterly financial audit report",
        status=ObligationStatus.CONFIRMED,
        obligation_type=ObligationType.OWED_TO_ME,
    )
    db_session.add(ob)
    await db_session.commit()

    res = await client.post("/api/events/ingest", json={
        "provider": "mock",
        "payload": {
            "content": "Currently drafting the quarterly financial audit report.",
            "sender": "Rahul",
            "recipients": ["Ravi"],
            "source_ref": "audit_prog_01",
        }
    })
    assert res.status_code == status.HTTP_201_CREATED
    data = res.json()
    assert data["semantic_role"] == "PROGRESS_UPDATE"
    assert len(data["evidence_records"]) == 1


@pytest.mark.asyncio
async def test_9_negative_blocker_handling(client: AsyncClient, db_session: AsyncSession):
    """9. Negative blocker creates non-completion evidence and flags blocker."""
    ob = Obligation(
        owner="Rahul",
        beneficiary="Ravi",
        action="Export production database telemetry",
        status=ObligationStatus.CONFIRMED,
        obligation_type=ObligationType.OWED_TO_ME,
    )
    db_session.add(ob)
    await db_session.commit()

    res = await client.post("/api/events/ingest", json={
        "provider": "mock",
        "payload": {
            "content": "Failed to export production database telemetry due to disk errors.",
            "sender": "Rahul",
            "recipients": ["Ravi"],
            "source_ref": "export_fail_01",
        }
    })
    assert res.status_code == status.HTTP_201_CREATED
    data = res.json()
    assert data["semantic_role"] == "NON_COMPLETION_SIGNAL"


@pytest.mark.asyncio
async def test_10_no_obligation_conversational_event(client: AsyncClient):
    """10. Conversational chatter produces NO_MATCH status without spurious evidence."""
    res = await client.post("/api/events/ingest", json={
        "provider": "mock",
        "payload": {
            "content": "Good morning team, have a great day!",
            "sender": "Rahul",
            "source_ref": "chat_001",
        }
    })
    assert res.status_code == status.HTTP_201_CREATED
    data = res.json()
    assert data["semantic_role"] == "IRRELEVANT"
    assert data["status"] == "NO_MATCH"
    assert len(data["evidence_records"]) == 0


@pytest.mark.asyncio
async def test_11_human_confirmation_requirement_preserved(client: AsyncClient, db_session: AsyncSession):
    """11. Ingesting completion signal leaves obligation in active status until human confirmation."""
    ob = Obligation(
        owner="Rahul",
        beneficiary="Ravi",
        action="Submit security questionnaire",
        status=ObligationStatus.IN_PROGRESS,
        obligation_type=ObligationType.OWED_TO_ME,
    )
    db_session.add(ob)
    await db_session.commit()

    res = await client.post("/api/events/ingest", json={
        "provider": "mock",
        "payload": {
            "content": "Submitted the security questionnaire.",
            "sender": "Rahul",
            "recipients": ["Ravi"],
            "source_ref": "sec_01",
        }
    })
    assert res.status_code == status.HTTP_201_CREATED

    # Obligation must NOT be automatically completed
    await db_session.refresh(ob)
    assert ob.status == ObligationStatus.IN_PROGRESS


@pytest.mark.asyncio
async def test_12_risk_recalculation_after_relevant_event(client: AsyncClient, db_session: AsyncSession):
    """12. Progress event produces PROGRESS_DETECTED decay signal in RiskEngine."""
    ob = Obligation(
        owner="Rahul",
        beneficiary="Ravi",
        action="Prepare API migration document",
        status=ObligationStatus.CONFIRMED,
        obligation_type=ObligationType.OWED_TO_ME,
        deadline=utc_now() + timedelta(days=2),
    )
    db_session.add(ob)
    await db_session.commit()

    # Ingest progress event
    await client.post("/api/events/ingest", json={
        "provider": "mock",
        "payload": {
            "content": "Making progress on API migration document.",
            "sender": "Rahul",
            "recipients": ["Ravi"],
            "source_ref": "api_mig_01",
        }
    })

    # RiskEngine evaluation
    risk = await RiskEngine.assess_obligation(session=db_session, obligation_id=ob.id)
    assert risk is not None
    signal_types = [s.signal_type for s in risk.signals]
    assert "PROGRESS_DETECTED" in signal_types


@pytest.mark.asyncio
async def test_13_intervention_acknowledgement_correlation(client: AsyncClient, db_session: AsyncSession):
    """13. Incoming progress event updates active intervention to ACKNOWLEDGED with PROGRESS_REPORTED outcome."""
    ob = Obligation(
        owner="Rahul",
        beneficiary="Ravi",
        action="Deliver design wireframes",
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
        title="Follow-up: Rahul",
        rationale="Approaching deadline.",
        message_draft="Please send design wireframes.",
        urgency="HIGH",
        status=InterventionStatus.EXECUTED,
        execution_mode="MOCK_DEMO",
    )
    db_session.add(inv)
    await db_session.commit()

    # Ingest progress event
    res = await client.post("/api/events/ingest", json={
        "provider": "mock",
        "payload": {
            "content": "Working on the design wireframes now, will share today.",
            "sender": "Rahul",
            "recipients": ["Ravi"],
            "source_ref": "des_prog_01",
        }
    })
    assert res.status_code == status.HTTP_201_CREATED
    assert inv.id in res.json()["updated_intervention_ids"]

    await db_session.refresh(inv)
    assert inv.status == InterventionStatus.ACKNOWLEDGED
    assert inv.outcome == InterventionOutcome.PROGRESS_REPORTED


@pytest.mark.asyncio
async def test_14_intervention_completion_correlation(client: AsyncClient, db_session: AsyncSession):
    """14. Incoming completion event logs COMPLETION_SIGNAL_RECEIVED in intervention audit trail."""
    ob = Obligation(
        owner="Rahul",
        beneficiary="Ravi",
        action="Send client contract agreement",
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
        title="Follow-up: Contract",
        rationale="Overdue deliverable.",
        message_draft="Please send contract.",
        urgency="CRITICAL",
        status=InterventionStatus.EXECUTED,
    )
    db_session.add(inv)
    await db_session.commit()

    res = await client.post("/api/events/ingest", json={
        "provider": "mock",
        "payload": {
            "content": "Sent client contract agreement to the client.",
            "sender": "Rahul",
            "recipients": ["Ravi"],
            "source_ref": "contract_sent_01",
        }
    })
    assert res.status_code == status.HTTP_201_CREATED

    await db_session.refresh(inv)
    audit_events = [e["event"] for e in inv.audit_trail]
    assert "COMPLETION_SIGNAL_RECEIVED" in audit_events


@pytest.mark.asyncio
async def test_15_event_api_retrieval(client: AsyncClient, db_session: AsyncSession):
    """15. GET /api/events returns paginated list of ingested events with filtering."""
    # Ingest event
    await client.post("/api/events/ingest", json={
        "provider": "mock",
        "payload": {
            "content": "Testing event listing endpoint.",
            "sender": "Rahul",
            "source_ref": "list_test_ref_01",
        }
    })

    res = await client.get("/api/events?provider=mock&limit=10")
    assert res.status_code == status.HTTP_200_OK
    data = res.json()
    assert "items" in data
    assert "total" in data
    assert data["total"] >= 1
    assert any(i["source_ref"] == "list_test_ref_01" for i in data["items"])


@pytest.mark.asyncio
async def test_16_event_detail_retrieval(client: AsyncClient, db_session: AsyncSession):
    """16. GET /api/events/{id} returns complete audit record."""
    ingest_res = await client.post("/api/events/ingest", json={
        "provider": "mock",
        "payload": {
            "content": "Specific detail inspection event.",
            "sender": "Rahul",
            "source_ref": "detail_test_ref_01",
        }
    })
    event_id = ingest_res.json()["event_id"]

    res = await client.get(f"/api/events/{event_id}")
    assert res.status_code == status.HTTP_200_OK
    data = res.json()
    assert data["id"] == event_id
    assert data["content"] == "Specific detail inspection event."
    assert data["source_ref"] == "detail_test_ref_01"


@pytest.mark.asyncio
async def test_17_simulation_endpoint(client: AsyncClient, db_session: AsyncSession):
    """17. POST /api/events/simulate runs canonical mock scenarios."""
    ob = Obligation(
        owner="Rahul",
        beneficiary="Ravi",
        action="Send database benchmark numbers",
        status=ObligationStatus.CONFIRMED,
        obligation_type=ObligationType.OWED_TO_ME,
    )
    db_session.add(ob)
    await db_session.commit()

    res = await client.post("/api/events/simulate", json={
        "scenario": "SCENARIO_A_COMPLETION",
    })
    assert res.status_code == status.HTTP_201_CREATED
    data = res.json()
    assert data["semantic_role"] == "COMPLETION_SIGNAL"
    assert data["provider"] == "mock"


@pytest.mark.asyncio
async def test_18_webhook_provider_routing(client: AsyncClient, db_session: AsyncSession):
    """18. POST /api/webhooks/{provider} correctly routes to registered provider adapter."""
    res = await client.post("/api/webhooks/mock", json={
        "content": "Webhook payload received.",
        "sender": "Rahul",
        "source_ref": "webhook_001",
    })
    assert res.status_code == status.HTTP_201_CREATED
    data = res.json()
    assert data["provider"] == "mock"


@pytest.mark.asyncio
async def test_19_invalid_provider_payload_handling(client: AsyncClient):
    """19. Unknown provider or invalid payload returns HTTP 400."""
    res = await client.post("/api/events/ingest", json={
        "provider": "non_existent_provider_abc",
        "payload": {"content": "Hello"},
    })
    assert res.status_code == status.HTTP_400_BAD_REQUEST
    assert "Unknown provider" in res.json()["detail"]


@pytest.mark.asyncio
async def test_20_idempotent_repeated_ingestion(client: AsyncClient, db_session: AsyncSession):
    """20. Repeating ingestion 3 times creates only 1 evidence record."""
    ob = Obligation(
        owner="Rahul",
        beneficiary="Ravi",
        action="Send weekly status report",
        status=ObligationStatus.CONFIRMED,
        obligation_type=ObligationType.OWED_TO_ME,
    )
    db_session.add(ob)
    await db_session.commit()

    payload = {
        "provider": "mock",
        "payload": {
            "content": "Sent the weekly status report.",
            "sender": "Rahul",
            "recipients": ["Ravi"],
            "source_ref": "idempotent_ref_777",
        }
    }

    # Call 3 times
    r1 = await client.post("/api/events/ingest", json=payload)
    r2 = await client.post("/api/events/ingest", json=payload)
    r3 = await client.post("/api/events/ingest", json=payload)

    assert r1.json()["status"] == "PROCESSED"
    assert r2.json()["status"] == "DUPLICATE"
    assert r3.json()["status"] == "DUPLICATE"

    # Verify only 1 evidence in DB
    ev_stmt = select(Evidence).where(Evidence.obligation_id == ob.id)
    ev_res = await db_session.execute(ev_stmt)
    records = list(ev_res.scalars().all())
    assert len(records) == 1


@pytest.mark.asyncio
async def test_21_graph_propagation_after_confirmed_completion(client: AsyncClient, db_session: AsyncSession):
    """21. Confirming evidence from ingested event triggers graph unblocking for dependents."""
    prereq = Obligation(
        owner="Rahul",
        beneficiary="Ravi",
        action="Provide API schemas",
        status=ObligationStatus.CONFIRMED,
        obligation_type=ObligationType.OWED_TO_ME,
    )
    db_session.add(prereq)
    await db_session.flush()

    dep = Obligation(
        owner="Ravi",
        beneficiary="Team",
        action="Implement frontend API integration",
        status=ObligationStatus.BLOCKED,
        obligation_type=ObligationType.OWED_BY_ME,
    )
    db_session.add(dep)
    await db_session.flush()

    edge = ObligationEdge(
        from_obligation_id=dep.id,
        to_obligation_id=prereq.id,
        edge_type=EdgeType.DEPENDS_ON,
    )
    db_session.add(edge)
    await db_session.commit()

    # Ingest completion event
    res = await client.post("/api/events/ingest", json={
        "provider": "mock",
        "payload": {
            "content": "Provided API schemas in the repo.",
            "sender": "Rahul",
            "recipients": ["Ravi"],
            "source_ref": "schema_ref_01",
        }
    })
    evidence_id = res.json()["evidence_records"][0]["id"]

    # Confirm evidence
    conf_res = await client.post(f"/api/obligations/{prereq.id}/evidence/{evidence_id}/confirm")
    assert conf_res.status_code == status.HTTP_200_OK

    # Prereq completed and dependent unblocked
    await db_session.refresh(prereq)
    await db_session.refresh(dep)
    assert prereq.status == ObligationStatus.COMPLETED
    assert dep.status == ObligationStatus.CONFIRMED


@pytest.mark.asyncio
async def test_22_audit_record_creation(client: AsyncClient, db_session: AsyncSession):
    """22. Complete audit trail metadata is stored in IngestedEventRecord."""
    res = await client.post("/api/events/ingest", json={
        "provider": "mock",
        "payload": {
            "content": "Audit trail verification message.",
            "sender": "Rahul",
            "recipients": ["Ravi"],
            "source_ref": "audit_record_ref_888",
            "metadata": {"channel": "engineering"},
        }
    })
    event_id = res.json()["event_id"]

    stmt = select(IngestedEventRecord).where(IngestedEventRecord.id == event_id)
    audit_res = await db_session.execute(stmt)
    record = audit_res.scalar_one_or_none()

    assert record is not None
    assert record.provider == "mock"
    assert record.source_ref == "audit_record_ref_888"
    assert record.sender == "Rahul"
    assert record.recipients == ["Ravi"]
    assert record.raw_payload is not None
    assert record.received_at is not None
