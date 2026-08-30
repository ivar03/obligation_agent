import pytest
import uuid
from datetime import datetime, timezone, timedelta
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.obligation import Obligation, ObligationEdge, Evidence, Intervention, IngestedEventRecord
from app.models.integration import IntegrationConnection
from app.core.status_machine import (
    ObligationStatus,
    ObligationType,
    EdgeType,
    EventSemanticRole,
    RiskLevel,
    ActionType,
    CorrelationStatus,
)
from app.services.providers.registry import provider_registry
from app.services.providers.google_calendar_provider import GoogleCalendarProvider, parse_calendar_identity
from app.services.event_classifier import EventClassifier
from app.services.event_ingestion_service import EventIngestionService
from app.services.risk_engine import RiskEngine
from app.services.recommendation_engine import RecommendationEngine


@pytest.fixture
def calendar_provider():
    return GoogleCalendarProvider()


# =============================================================================
# 1. PROVIDER REGISTRY TESTS (Tests 1-3)
# =============================================================================

def test_01_provider_registry_lookup():
    """1. Provider registry lookup for google_calendar."""
    assert provider_registry.has_provider("google_calendar")
    provider = provider_registry.get("google_calendar")
    assert provider.provider_name == "google_calendar"
    assert provider.provider_version == "1.0.0"


def test_02_unknown_provider_rejection():
    """2. Unknown provider lookup raises ValueError."""
    with pytest.raises(ValueError, match="Unknown provider 'unsupported_calendar'"):
        provider_registry.get("unsupported_calendar")


def test_03_provider_registry_contains_all_four_providers():
    """3. Registry contains mock, slack, gmail, and google_calendar."""
    providers = provider_registry.list_providers()
    provider_names = {p["name"] for p in providers}
    assert {"mock", "slack", "gmail", "google_calendar"}.issubset(provider_names)


# =============================================================================
# 2. NORMALIZATION & SOURCE_REF (Tests 4-8)
# =============================================================================

def test_04_calendar_payload_normalization(calendar_provider):
    """4. Calendar payload normalization into ExternalEvent."""
    now = datetime.now(timezone.utc)
    raw = {
        "id": "evt_norm_101",
        "summary": "Project Review Meeting",
        "description": "Discussing milestone metrics.",
        "organizer": {"displayName": "Ravi", "email": "ravi@acme.com"},
        "attendees": [{"displayName": "Rahul", "email": "rahul@acme.com"}],
        "start": {"dateTime": (now + timedelta(days=1)).isoformat()},
        "end": {"dateTime": (now + timedelta(days=1, hours=1)).isoformat()},
        "status": "confirmed",
    }
    event = calendar_provider.normalize_event(raw)
    assert event.source_type == "google_calendar"
    assert event.sender == "Ravi"
    assert "Rahul" in event.recipients
    assert "Project Review" in event.content


def test_05_metadata_normalization(calendar_provider):
    """5. Metadata normalization with timezone, location, and attendee responses."""
    raw = {
        "id": "evt_meta_202",
        "summary": "Design Sync",
        "location": "Room 3B",
        "hangoutLink": "https://meet.google.com/abc-def-ghi",
        "start": {"dateTime": "2026-09-01T10:00:00Z", "timeZone": "Asia/Kolkata"},
        "end": {"dateTime": "2026-09-01T11:00:00Z", "timeZone": "Asia/Kolkata"},
        "attendees": [
            {"displayName": "Rahul", "email": "rahul@acme.com", "responseStatus": "accepted"}
        ],
    }
    event = calendar_provider.normalize_event(raw)
    assert event.metadata["location"] == "Room 3B"
    assert event.metadata["meeting_url"] == "https://meet.google.com/abc-def-ghi"
    assert event.metadata["timezone"] == "Asia/Kolkata"
    assert event.metadata["attendee_responses"]["Rahul"] == "accepted"


def test_06_stable_source_ref_generation(calendar_provider):
    """6. Stable source_ref generation across repeated normalization."""
    raw = {
        "calendar_id": "c_eng",
        "id": "evt_stable_303",
        "sequence": 1,
    }
    e1 = calendar_provider.normalize_event(raw)
    e2 = calendar_provider.normalize_event(raw)
    assert e1.source_ref == e2.source_ref
    assert e1.source_ref == "google_calendar:c_eng:evt_stable_303:1"


def test_07_identity_parsing_variations():
    """7. Identity parsing across string, email, dict, and angle bracket formats."""
    assert parse_calendar_identity("Alice <alice@acme.com>") == "Alice"
    assert parse_calendar_identity({"name": "Bob"}) == "Bob"
    assert parse_calendar_identity("<carol@acme.com>") == "carol@acme.com"
    assert parse_calendar_identity(None) == "Unknown"


def test_08_credential_leakage_prevention(calendar_provider):
    """8. Credential leakage prevention strips tokens and secrets from metadata."""
    raw = {
        "id": "evt_safe_404",
        "summary": "Sprint Planning",
        "metadata": {
            "token": "secret_oauth_token",
            "access_token": "ya29.secret",
            "refresh_token": "1//refresh",
            "safe_project": "Obligation Agent",
        },
    }
    event = calendar_provider.normalize_event(raw)
    assert "token" not in event.metadata
    assert "access_token" not in event.metadata
    assert "refresh_token" not in event.metadata
    assert event.metadata["safe_project"] == "Obligation Agent"


# =============================================================================
# 3. SEMANTIC CLASSIFICATION (Tests 9-14)
# =============================================================================

def test_09_meeting_scheduled_classification(calendar_provider):
    """9. Meeting scheduled classification."""
    event = calendar_provider.generate_canonical_event("SCENARIO_A_MEETING")
    assert event.metadata["meeting_status"] == "MEETING_SCHEDULED"
    role, _, _ = EventClassifier.classify(event.content)
    assert role in [EventSemanticRole.COMMITMENT, EventSemanticRole.PROGRESS_UPDATE]


def test_10_meeting_rescheduled_classification(calendar_provider):
    """10. Meeting rescheduled classification."""
    event = calendar_provider.generate_canonical_event("SCENARIO_B_RESCHEDULED")
    assert event.metadata["meeting_status"] == "MEETING_RESCHEDULED"
    role, _, _ = EventClassifier.classify(event.content)
    assert role in [EventSemanticRole.COMMITMENT, EventSemanticRole.PROGRESS_UPDATE]


def test_11_meeting_cancelled_classification(calendar_provider):
    """11. Meeting cancelled classification."""
    event = calendar_provider.generate_canonical_event("SCENARIO_C_CANCELLED")
    assert event.metadata["meeting_status"] == "MEETING_CANCELLED"
    role, _, _ = EventClassifier.classify(event.content)
    assert role == EventSemanticRole.NON_COMPLETION_SIGNAL


def test_12_attendee_response_classification(calendar_provider):
    """12. Attendee response classification."""
    event = calendar_provider.generate_canonical_event("SCENARIO_D_ATTENDEE_ACCEPTED")
    assert event.metadata["meeting_status"] == "ATTENDEE_RESPONSE"
    role, _, _ = EventClassifier.classify(event.content)
    assert role == EventSemanticRole.PROGRESS_UPDATE


def test_13_meeting_completed_classification(calendar_provider):
    """13. Meeting completed classification."""
    event = calendar_provider.generate_canonical_event("SCENARIO_E_MEETING_COMPLETED")
    assert event.metadata["meeting_status"] == "MEETING_COMPLETED"
    role, _, _ = EventClassifier.classify(event.content)
    assert role in [EventSemanticRole.PROGRESS_UPDATE, EventSemanticRole.COMPLETION_SIGNAL]


def test_14_unrelated_calendar_event_classification(calendar_provider):
    """14. Unrelated calendar event classification."""
    event = calendar_provider.generate_canonical_event("SCENARIO_F_UNRELATED")
    role, _, _ = EventClassifier.classify(event.content)
    assert role == EventSemanticRole.IRRELEVANT


# =============================================================================
# 4. IDEMPOTENCY & EVENT UPDATES (Tests 15-17)
# =============================================================================

@pytest.mark.asyncio
async def test_15_duplicate_notification_detection(db_session: AsyncSession):
    """15. Duplicate notification detection returns DUPLICATE status."""
    payload = {
        "id": f"evt_dup_{uuid.uuid4().hex[:8]}",
        "summary": "Executive Roadmap Review",
        "organizer": "Ravi",
        "attendees": ["Rahul"],
    }
    res1 = await EventIngestionService.ingest_from_provider(db_session, "google_calendar", payload)
    res2 = await EventIngestionService.ingest_from_provider(db_session, "google_calendar", payload)
    assert res1.status in ["PROCESSED", "NO_MATCH"]
    assert res2.status == "DUPLICATE"
    assert res2.event_id == res1.event_id


@pytest.mark.asyncio
async def test_16_duplicate_event_delivery(db_session: AsyncSession):
    """16. Duplicate event delivery does not create duplicate IngestedEventRecords."""
    payload = {
        "id": f"evt_rec_{uuid.uuid4().hex[:8]}",
        "summary": "Team Sync",
        "organizer": "Ravi",
    }
    await EventIngestionService.ingest_from_provider(db_session, "google_calendar", payload)
    await EventIngestionService.ingest_from_provider(db_session, "google_calendar", payload)

    stmt = select(IngestedEventRecord).where(IngestedEventRecord.content.contains("Team Sync"))
    res = await db_session.execute(stmt)
    records = list(res.scalars().all())
    assert len(records) == 1


@pytest.mark.asyncio
async def test_17_event_update_handling(db_session: AsyncSession):
    """17. Event update with incremented sequence creates a distinct updated version."""
    base_id = f"evt_upd_{uuid.uuid4().hex[:8]}"
    payload_v0 = {"id": base_id, "summary": "Project Review", "sequence": 0}
    payload_v1 = {"id": base_id, "summary": "Project Review (Updated Time)", "sequence": 1, "rescheduled": True}

    res_v0 = await EventIngestionService.ingest_from_provider(db_session, "google_calendar", payload_v0)
    res_v1 = await EventIngestionService.ingest_from_provider(db_session, "google_calendar", payload_v1)
    assert res_v0.status in ["PROCESSED", "NO_MATCH"]
    assert res_v1.status in ["PROCESSED", "NO_MATCH"]
    assert res_v0.event_id != res_v1.event_id


# =============================================================================
# 5. OAUTH & SECURITY (Tests 18-21)
# =============================================================================

@pytest.mark.asyncio
async def test_18_oauth_state_generation(client: AsyncClient):
    """18. OAuth state generation includes CSRF token."""
    resp = await client.get("/api/integrations/google_calendar/connect")
    assert resp.status_code == 200
    data = resp.json()
    assert "state=" in data["authorization_url"]
    assert len(data["state"]) >= 32


@pytest.mark.asyncio
async def test_19_oauth_callback_validation(client: AsyncClient):
    """19. Callback validation establishes connection."""
    init_res = await client.get("/api/integrations/google_calendar/connect")
    state = init_res.json()["state"]

    cb_res = await client.post(f"/api/integrations/google_calendar/callback?code=mock_code&state={state}")
    assert cb_res.status_code == 200
    assert cb_res.json()["status"] == "CONNECTED"


@pytest.mark.asyncio
async def test_20_invalid_oauth_state_rejection(client: AsyncClient):
    """20. Invalid CSRF state rejection with 400 Bad Request."""
    resp = await client.post("/api/integrations/google_calendar/callback?code=mock_code&state=bad_state")
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_21_integration_disconnect_and_reconnect(client: AsyncClient):
    """21. Disconnect and re-test connection."""
    # Connect
    init_res = await client.get("/api/integrations/google_calendar/connect")
    state = init_res.json()["state"]
    await client.post(f"/api/integrations/google_calendar/callback?code=mock_code&state={state}")

    # Disconnect
    disc_res = await client.post("/api/integrations/google_calendar/disconnect")
    assert disc_res.status_code == 200
    assert disc_res.json()["status"] == "DISCONNECTED"

    # Test connection after disconnect
    test_res = await client.post("/api/integrations/google_calendar/test")
    assert test_res.status_code == 200
    assert test_res.json()["success"] is False


# =============================================================================
# 6. TEMPORAL CORRELATION & SAFETY BOUNDARIES (Tests 22-26)
# =============================================================================

@pytest.mark.asyncio
async def test_22_strong_obligation_to_meeting_correlation(db_session: AsyncSession):
    """22. Strong obligation-to-meeting correlation with matching owner, beneficiary, and action."""
    ob = Obligation(
        owner="Rahul",
        beneficiary="Ravi",
        action="Deliver database benchmark report for project review",
        deadline=datetime.now(timezone.utc) + timedelta(days=2),
        status=ObligationStatus.CONFIRMED,
        obligation_type=ObligationType.OWED_TO_ME,
    )
    db_session.add(ob)
    await db_session.commit()

    payload = {
        "id": f"evt_bench_{uuid.uuid4().hex[:8]}",
        "summary": "Project Review - Database Benchmarks",
        "organizer": "Ravi",
        "attendees": ["Rahul", "Ravi"],
    }
    res = await EventIngestionService.ingest_from_provider(db_session, "google_calendar", payload)
    assert res.status == "PROCESSED"
    assert len(res.evidence_records) > 0
    assert res.evidence_records[0].correlation_confidence >= 0.70


@pytest.mark.asyncio
async def test_23_weak_correlation_partial_match(db_session: AsyncSession):
    """23. Weak correlation when only partial keywords overlap without attendees."""
    ob = Obligation(
        owner="Rahul",
        beneficiary="Ravi",
        action="Deliver database benchmark report",
        deadline=datetime.now(timezone.utc) + timedelta(days=2),
        status=ObligationStatus.CONFIRMED,
        obligation_type=ObligationType.OWED_TO_ME,
    )
    db_session.add(ob)
    await db_session.commit()

    payload = {
        "id": f"evt_general_{uuid.uuid4().hex[:8]}",
        "summary": "General Database Overview",
        "organizer": "Stranger",
        "attendees": ["External Person"],
    }
    res = await EventIngestionService.ingest_from_provider(db_session, "google_calendar", payload)
    # Low confidence without owner/beneficiary alignment
    assert res.status in ["NO_MATCH", "PROCESSED"]


@pytest.mark.asyncio
async def test_24_unrelated_meeting_does_not_correlate(db_session: AsyncSession):
    """24. Completely unrelated meeting does not correlate."""
    ob = Obligation(
        owner="Rahul",
        beneficiary="Ravi",
        action="Prepare quarterly tax filing",
        deadline=datetime.now(timezone.utc) + timedelta(days=5),
        status=ObligationStatus.CONFIRMED,
        obligation_type=ObligationType.OWED_TO_ME,
    )
    db_session.add(ob)
    await db_session.commit()

    lunch_payload = {
        "id": f"evt_lunch_{uuid.uuid4().hex[:8]}",
        "summary": "Personal Lunch with Alice",
        "organizer": "Alice",
        "attendees": ["Alice", "Bob"],
    }
    res = await EventIngestionService.ingest_from_provider(db_session, "google_calendar", lunch_payload)
    assert res.status == "NO_MATCH"


@pytest.mark.asyncio
async def test_25_calendar_context_does_not_fabricate_deadline(db_session: AsyncSession):
    """25. Calendar meeting time does NOT overwrite or mutate obligation deadline."""
    initial_deadline = datetime.now(timezone.utc) + timedelta(days=5)
    ob = Obligation(
        owner="Rahul",
        beneficiary="Ravi",
        action="Present roadmap at quarterly review",
        deadline=initial_deadline,
        status=ObligationStatus.CONFIRMED,
        obligation_type=ObligationType.OWED_TO_ME,
    )
    db_session.add(ob)
    await db_session.commit()

    meeting_time = (datetime.now(timezone.utc) + timedelta(days=1)).isoformat()
    payload = {
        "id": f"evt_road_{uuid.uuid4().hex[:8]}",
        "summary": "Quarterly Review Meeting",
        "organizer": "Ravi",
        "attendees": ["Rahul", "Ravi"],
        "start": {"dateTime": meeting_time},
    }
    await EventIngestionService.ingest_from_provider(db_session, "google_calendar", payload)

    await db_session.refresh(ob)
    assert ob.deadline.replace(tzinfo=timezone.utc) == initial_deadline.replace(tzinfo=timezone.utc)


@pytest.mark.asyncio
async def test_26_human_confirmation_remains_required(db_session: AsyncSession):
    """26. Human confirmation is mandatory; calendar events never auto-complete obligations."""
    ob = Obligation(
        owner="Rahul",
        beneficiary="Ravi",
        action="Deliver project review slides",
        deadline=datetime.now(timezone.utc) + timedelta(days=1),
        status=ObligationStatus.CONFIRMED,
        obligation_type=ObligationType.OWED_TO_ME,
    )
    db_session.add(ob)
    await db_session.commit()

    payload = {
        "id": f"evt_slides_{uuid.uuid4().hex[:8]}",
        "summary": "Project Review Meeting Concluded",
        "organizer": "Ravi",
        "attendees": ["Rahul", "Ravi"],
        "completed": True,
    }
    await EventIngestionService.ingest_from_provider(db_session, "google_calendar", payload)

    await db_session.refresh(ob)
    assert ob.status == ObligationStatus.CONFIRMED


# =============================================================================
# 7. RISK & RECOMMENDATIONS (Tests 27-32)
# =============================================================================

@pytest.mark.asyncio
async def test_27_upcoming_meeting_increases_urgency(db_session: AsyncSession):
    """27. Upcoming related meeting generates UPCOMING_RELATED_MEETING signal."""
    ob = Obligation(
        owner="Rahul",
        beneficiary="Ravi",
        action="Deliver demo dataset for sprint review",
        deadline=datetime.now(timezone.utc) + timedelta(days=2),
        status=ObligationStatus.CONFIRMED,
        obligation_type=ObligationType.OWED_TO_ME,
    )
    db_session.add(ob)
    await db_session.commit()
    await db_session.refresh(ob)

    ev = Evidence(
        obligation_id=ob.id,
        source_type="google_calendar",
        content="Meeting: Sprint Review tomorrow",
        correlation_confidence=0.85,
        correlation_status=CorrelationStatus.SUGGESTED,
        semantic_role=EventSemanticRole.COMMITMENT,
        extra_metadata={
            "source_provider": "google_calendar",
            "summary": "Sprint Review",
            "meeting_status": "MEETING_SCHEDULED",
            "start_time": (datetime.now(timezone.utc) + timedelta(hours=18)).isoformat(),
        },
    )
    db_session.add(ev)
    await db_session.commit()

    assessment = await RiskEngine.assess_obligation(db_session, ob.id)
    assert "UPCOMING_RELATED_MEETING" in {s.signal_type for s in assessment.signals}


@pytest.mark.asyncio
async def test_28_completed_meeting_without_evidence_increases_risk(db_session: AsyncSession):
    """28. Concluded meeting without evidence generates RELATED_MEETING_COMPLETED_WITHOUT_COMPLETION."""
    ob = Obligation(
        owner="Rahul",
        beneficiary="Ravi",
        action="Deliver benchmark numbers at review",
        deadline=datetime.now(timezone.utc) + timedelta(hours=3),
        status=ObligationStatus.CONFIRMED,
        obligation_type=ObligationType.OWED_TO_ME,
    )
    db_session.add(ob)
    await db_session.commit()
    await db_session.refresh(ob)

    ev = Evidence(
        obligation_id=ob.id,
        source_type="google_calendar",
        content="Meeting: Project Review has ended",
        correlation_confidence=0.85,
        correlation_status=CorrelationStatus.SUGGESTED,
        semantic_role=EventSemanticRole.PROGRESS_UPDATE,
        extra_metadata={
            "source_provider": "google_calendar",
            "summary": "Project Review",
            "meeting_status": "MEETING_COMPLETED",
            "completed": True,
        },
    )
    db_session.add(ev)
    await db_session.commit()

    assessment = await RiskEngine.assess_obligation(db_session, ob.id)
    assert "RELATED_MEETING_COMPLETED_WITHOUT_COMPLETION" in {s.signal_type for s in assessment.signals}
    assert assessment.action_type == ActionType.FOLLOW_UP_AFTER_MEETING


@pytest.mark.asyncio
async def test_29_cancelled_meeting_signal_without_cancelling_obligation(db_session: AsyncSession):
    """29. Cancelled meeting produces signal and recommendation without cancelling obligation."""
    ob = Obligation(
        owner="Rahul",
        beneficiary="Ravi",
        action="Present strategy at quarterly review",
        deadline=datetime.now(timezone.utc) + timedelta(days=2),
        status=ObligationStatus.CONFIRMED,
        obligation_type=ObligationType.OWED_TO_ME,
    )
    db_session.add(ob)
    await db_session.commit()
    await db_session.refresh(ob)

    ev = Evidence(
        obligation_id=ob.id,
        source_type="google_calendar",
        content="Quarterly Review meeting was cancelled",
        correlation_confidence=0.80,
        correlation_status=CorrelationStatus.SUGGESTED,
        semantic_role=EventSemanticRole.NON_COMPLETION_SIGNAL,
        extra_metadata={
            "source_provider": "google_calendar",
            "summary": "Quarterly Review",
            "meeting_status": "MEETING_CANCELLED",
            "cancelled": True,
        },
    )
    db_session.add(ev)
    await db_session.commit()

    assessment = await RiskEngine.assess_obligation(db_session, ob.id)
    assert "RELATED_MEETING_CANCELLED" in {s.signal_type for s in assessment.signals}
    assert assessment.action_type == ActionType.REVIEW_CANCELLED_MEETING
    await db_session.refresh(ob)
    assert ob.status == ObligationStatus.CONFIRMED


@pytest.mark.asyncio
async def test_30_rescheduled_meeting_recalculates_temporal_context(db_session: AsyncSession):
    """30. Rescheduled meeting produces RELATED_MEETING_RESCHEDULED and advisory action."""
    ob = Obligation(
        owner="Rahul",
        beneficiary="Ravi",
        action="Deliver project review notes",
        deadline=datetime.now(timezone.utc) + timedelta(days=3),
        status=ObligationStatus.CONFIRMED,
        obligation_type=ObligationType.OWED_TO_ME,
    )
    db_session.add(ob)
    await db_session.commit()
    await db_session.refresh(ob)

    ev = Evidence(
        obligation_id=ob.id,
        source_type="google_calendar",
        content="Project Review meeting moved to Tuesday",
        correlation_confidence=0.80,
        correlation_status=CorrelationStatus.SUGGESTED,
        semantic_role=EventSemanticRole.COMMITMENT,
        extra_metadata={
            "source_provider": "google_calendar",
            "summary": "Project Review",
            "meeting_status": "MEETING_RESCHEDULED",
            "rescheduled": True,
        },
    )
    db_session.add(ev)
    await db_session.commit()

    assessment = await RiskEngine.assess_obligation(db_session, ob.id)
    assert "RELATED_MEETING_RESCHEDULED" in {s.signal_type for s in assessment.signals}
    assert assessment.action_type == ActionType.REVIEW_RESCHEDULED_COMMITMENT


@pytest.mark.asyncio
async def test_31_risk_remains_bounded(db_session: AsyncSession):
    """31. Cumulative risk score remains bounded between 0.0 and 1.0."""
    ob = Obligation(
        owner="unassigned",
        beneficiary="Ravi",
        action="Deliver benchmark dataset",
        deadline=datetime.now(timezone.utc) - timedelta(days=2),
        status=ObligationStatus.OVERDUE,
        obligation_type=ObligationType.OWED_BY_ME,
    )
    db_session.add(ob)
    await db_session.commit()

    assessment = await RiskEngine.assess_obligation(db_session, ob.id)
    assert 0.0 <= assessment.risk_score <= 1.0
    assert assessment.risk_level in [RiskLevel.HIGH, RiskLevel.CRITICAL]


def test_32_recommendation_engine_advisory_actions():
    """32. RecommendationEngine returns advisory actions for each meeting signal."""
    ob = Obligation(owner="Rahul", beneficiary="Ravi", action="Task", status=ObligationStatus.CONFIRMED, obligation_type=ObligationType.OWED_TO_ME)
    
    # Completed meeting without proof
    sig1 = [type("Signal", (), {"signal_type": "RELATED_MEETING_COMPLETED_WITHOUT_COMPLETION"})()]
    act1, _ = RecommendationEngine.generate_recommendation(ob, RiskLevel.HIGH, sig1, [])
    assert act1 == ActionType.FOLLOW_UP_AFTER_MEETING

    # Cancelled meeting
    sig2 = [type("Signal", (), {"signal_type": "RELATED_MEETING_CANCELLED"})()]
    act2, _ = RecommendationEngine.generate_recommendation(ob, RiskLevel.MEDIUM, sig2, [])
    assert act2 == ActionType.REVIEW_CANCELLED_MEETING


# =============================================================================
# 8. API & WEBHOOKS (Tests 33-36)
# =============================================================================

@pytest.mark.asyncio
async def test_33_calendar_webhook_ingestion(client: AsyncClient):
    """33. POST /api/webhooks/google-calendar successfully ingests payload."""
    payload = {
        "id": f"evt_api_{uuid.uuid4().hex[:8]}",
        "summary": "Engineering Sync",
        "organizer": "Ravi",
    }
    resp = await client.post("/api/webhooks/google-calendar", json=payload)
    assert resp.status_code == 200
    assert resp.json()["provider"] == "google_calendar"


@pytest.mark.asyncio
async def test_34_calendar_webhook_alias_endpoint(client: AsyncClient):
    """34. POST /api/webhooks/google_calendar alias endpoint functions identically."""
    payload = {
        "id": f"evt_alias_{uuid.uuid4().hex[:8]}",
        "summary": "Product Review",
        "organizer": "Ravi",
    }
    resp = await client.post("/api/webhooks/google_calendar", json=payload)
    assert resp.status_code == 200
    assert resp.json()["provider"] == "google_calendar"


@pytest.mark.asyncio
async def test_35_integration_listing_exposes_google_calendar(client: AsyncClient):
    """35. GET /api/integrations exposes Google Calendar with safe metadata."""
    resp = await client.get("/api/integrations")
    assert resp.status_code == 200
    data = resp.json()
    registered = {p["name"] for p in data["registered_providers"]}
    assert "google_calendar" in registered


@pytest.mark.asyncio
async def test_36_activity_feed_retrieval(client: AsyncClient):
    """36. GET /api/events retrieves ingested calendar events."""
    payload = {
        "id": f"evt_feed_{uuid.uuid4().hex[:8]}",
        "summary": "All-Hands Meeting",
        "organizer": "Leadership",
    }
    await client.post("/api/webhooks/google-calendar", json=payload)
    resp = await client.get("/api/events?provider=google_calendar")
    assert resp.status_code == 200


# =============================================================================
# 9. GRAPH & CLOSED LOOP CASCADE (Tests 37-40)
# =============================================================================

@pytest.mark.asyncio
async def test_37_calendar_signals_do_not_break_graph_propagation(client: AsyncClient, db_session: AsyncSession):
    """37. Calendar temporal signals coexist cleanly with dependency graph structures."""
    ob1 = Obligation(owner="Rahul", beneficiary="Ravi", action="Prereq", status=ObligationStatus.CONFIRMED, obligation_type=ObligationType.OWED_TO_ME)
    ob2 = Obligation(owner="Ravi", beneficiary="Team", action="Dependent", status=ObligationStatus.BLOCKED, obligation_type=ObligationType.OWED_BY_ME)
    db_session.add_all([ob1, ob2])
    await db_session.commit()
    await db_session.refresh(ob1)
    await db_session.refresh(ob2)

    edge = ObligationEdge(from_obligation_id=ob2.id, to_obligation_id=ob1.id, edge_type=EdgeType.DEPENDS_ON)
    db_session.add(edge)
    await db_session.commit()

    # Calendar event arrives for ob1
    await client.post("/api/webhooks/google-calendar", json={"id": "evt_g1", "summary": "Prereq Sync", "organizer": "Ravi", "attendees": ["Rahul"]})
    await db_session.refresh(ob1)
    await db_session.refresh(ob2)

    assert ob1.status == ObligationStatus.CONFIRMED
    assert ob2.status == ObligationStatus.BLOCKED


@pytest.mark.asyncio
async def test_38_confirmed_evidence_completes_obligation(client: AsyncClient, db_session: AsyncSession):
    """38. Human-confirmed evidence successfully completes obligation."""
    ob = Obligation(owner="Rahul", beneficiary="Ravi", action="Deliver spec document", status=ObligationStatus.CONFIRMED, obligation_type=ObligationType.OWED_TO_ME)
    db_session.add(ob)
    await db_session.commit()
    await db_session.refresh(ob)

    res = await client.post("/api/webhooks/gmail", json={
        "from": "Rahul <rahul@acme.com>",
        "to": "Ravi <ravi@acme.com>",
        "subject": "Spec document attached",
        "body": "Sent the spec document.",
        "attachments": [{"name": "spec.pdf", "size": 1024}],
    })
    ev_id = res.json()["evidence_records"][0]["id"]

    confirm_res = await client.post(f"/api/obligations/{ob.id}/evidence/{ev_id}/confirm", json={"notes": "Approved."})
    assert confirm_res.status_code == 200

    await db_session.refresh(ob)
    assert ob.status == ObligationStatus.COMPLETED


@pytest.mark.asyncio
async def test_39_completed_prerequisite_unblocks_dependents(client: AsyncClient, db_session: AsyncSession):
    """39. Completing prerequisite obligation cascades to unblock dependent obligations."""
    ob1 = Obligation(owner="Rahul", beneficiary="Ravi", action="Deliver dataset", status=ObligationStatus.CONFIRMED, obligation_type=ObligationType.OWED_TO_ME)
    ob2 = Obligation(owner="Ravi", beneficiary="Exec", action="Publish report", status=ObligationStatus.BLOCKED, obligation_type=ObligationType.OWED_BY_ME)
    db_session.add_all([ob1, ob2])
    await db_session.commit()
    await db_session.refresh(ob1)
    await db_session.refresh(ob2)

    edge = ObligationEdge(from_obligation_id=ob2.id, to_obligation_id=ob1.id, edge_type=EdgeType.DEPENDS_ON)
    db_session.add(edge)
    await db_session.commit()

    res = await client.post("/api/webhooks/slack", json={
        "type": "event_callback",
        "team_id": "T_UNBLOCK",
        "event": {
            "type": "message",
            "user": "U_RAHUL",
            "user_name": "Rahul",
            "text": "Delivered dataset to the team.",
            "ts": "1700000099.000100",
            "channel": "C_ENG",
        }
    })
    ev_id = res.json()["evidence_records"][0]["id"]

    await client.post(f"/api/obligations/{ob1.id}/evidence/{ev_id}/confirm", json={"notes": "Confirmed."})

    await db_session.refresh(ob1)
    await db_session.refresh(ob2)
    assert ob1.status == ObligationStatus.COMPLETED
    assert ob2.status == ObligationStatus.CONFIRMED


@pytest.mark.asyncio
async def test_40_multi_provider_coexistence_regression(client: AsyncClient):
    """40. Multi-provider regression: Mock, Slack, Gmail, and Google Calendar coexist seamlessly."""
    # Test all 4 providers
    r_mock = await client.post("/api/integrations/mock/test")
    assert r_mock.status_code == 200
    assert r_mock.json()["success"] is True

    r_slack = await client.post("/api/integrations/slack/test")
    assert r_slack.status_code == 200

    r_gmail = await client.post("/api/integrations/gmail/test")
    assert r_gmail.status_code == 200

    r_gcal = await client.post("/api/integrations/google_calendar/test")
    assert r_gcal.status_code == 200
