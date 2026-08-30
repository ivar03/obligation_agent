import pytest
import hmac
import hashlib
import time
import uuid
from datetime import datetime, timezone, timedelta
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.status_machine import (
    ObligationStatus,
    ObligationType,
    EdgeType,
    EvidenceType,
    CorrelationStatus,
    EventSemanticRole,
    RiskLevel,
)
from app.core.intervention_status import InterventionStatus, InterventionOutcome, InterventionType
from app.models.obligation import Obligation, ObligationEdge, Evidence, Intervention, IngestedEventRecord
from app.models.integration import IntegrationConnection
from app.schemas.obligation import ExternalEvent
from app.services.providers.registry import provider_registry
from app.services.providers.slack_provider import SlackProvider
from app.services.integration_service import IntegrationService
from app.services.event_ingestion_service import EventIngestionService
from app.services.risk_engine import RiskEngine
from app.services.intervention_service import InterventionService as IntervService
from app.services.graph_service import GraphService


def generate_slack_signature(body: bytes, timestamp: str, secret: str) -> str:
    """Generates valid Slack HMAC-SHA256 signature for test requests."""
    sig_basestring = f"v0:{timestamp}:".encode("utf-8") + body
    computed_hash = hmac.new(secret.encode("utf-8"), sig_basestring, hashlib.sha256).hexdigest()
    return f"v0={computed_hash}"


# ==========================================
# 1. PROVIDER REGISTRATION & METADATA TESTS (1-5)
# ==========================================

def test_01_slack_provider_registered():
    """1. Verify Slack provider is registered in ProviderRegistry."""
    assert provider_registry.has_provider("slack")
    provider = provider_registry.get("slack")
    assert isinstance(provider, SlackProvider)
    assert provider.provider_name == "slack"
    assert provider.provider_version == "1.0.0"


def test_02_provider_metadata_and_capabilities():
    """2. Verify provider capabilities and listing contains both mock and slack without secrets."""
    providers = provider_registry.list_providers()
    provider_names = [p["name"] for p in providers]
    assert "mock" in provider_names
    assert "slack" in provider_names

    slack_p = next(p for p in providers if p["name"] == "slack")
    assert "events" in slack_p["capabilities"]
    assert "messages" in slack_p["capabilities"]
    assert "webhook" in slack_p["capabilities"]
    assert "attachments" in slack_p["capabilities"]

    for p in providers:
        assert "secret" not in p
        assert "token" not in p
        assert "bot_token" not in p


def test_03_slack_normalization_standard_message():
    """3. Verify Slack message payload normalizes into ExternalEvent correctly."""
    provider = SlackProvider()
    payload = {
        "type": "event_callback",
        "team_id": "T01234567",
        "api_app_id": "A09876543",
        "event": {
            "type": "message",
            "user": "U12345678",
            "user_name": "Rahul",
            "text": "Sent the database benchmark numbers to <@U87654321|Ravi>.",
            "ts": "1609459200.000200",
            "channel": "C0123GENERAL",
            "channel_name": "general",
        }
    }

    event = provider.normalize_event(payload)
    assert isinstance(event, ExternalEvent)
    assert event.source_type == "slack"
    assert event.sender == "Rahul"
    assert "Ravi" in event.recipients
    assert "benchmark numbers" in event.content
    assert event.metadata["team_id"] == "T01234567"
    assert event.metadata["channel_id"] == "C0123GENERAL"
    assert event.metadata["slack_user_id"] == "U12345678"
    assert event.source_ref.startswith("slack_T01234567_")


def test_04_malformed_payload_rejection():
    """4. Verify malformed payload rejection raises ValueError."""
    provider = SlackProvider()
    with pytest.raises(ValueError, match="Malformed Slack payload"):
        provider.normalize_event({})

    with pytest.raises(ValueError, match="Malformed Slack payload"):
        provider.normalize_event({"invalid_structure": 123})


def test_05_unsupported_event_handling():
    """5. Verify unsupported non-content Slack event subtypes are handled cleanly."""
    provider = SlackProvider()
    payload = {
        "type": "event_callback",
        "team_id": "T01",
        "event": {
            "type": "message",
            "subtype": "channel_join",
            "user": "U99",
            "text": "<@U99> has joined the channel",
            "ts": "1609459200.000300",
            "channel": "C01",
        }
    }
    event = provider.normalize_event(payload)
    assert event.metadata["subtype"] == "channel_join"
    assert event.source_type == "slack"


# ==========================================
# 2. SECURITY & SIGNATURE TESTS (6-10)
# ==========================================

def test_06_valid_slack_signature():
    """6. Verify valid HMAC-SHA256 Slack signature passes verification."""
    secret = "test_signing_secret_12345"
    body = b'{"type":"event_callback","event":{"type":"message","text":"hello"}}'
    ts = str(int(time.time()))
    sig = generate_slack_signature(body, ts, secret)

    is_valid = SlackProvider.verify_slack_signature(
        request_body=body,
        timestamp=ts,
        signature=sig,
        signing_secret=secret,
    )
    assert is_valid is True


def test_07_invalid_slack_signature():
    """7. Verify tampered body or invalid signature is rejected."""
    secret = "test_signing_secret_12345"
    body = b'{"type":"event_callback","event":{"type":"message","text":"hello"}}'
    tampered_body = b'{"type":"event_callback","event":{"type":"message","text":"tampered"}}'
    ts = str(int(time.time()))
    sig = generate_slack_signature(body, ts, secret)

    is_valid = SlackProvider.verify_slack_signature(
        request_body=tampered_body,
        timestamp=ts,
        signature=sig,
        signing_secret=secret,
    )
    assert is_valid is False


def test_08_expired_replayed_request_rejection():
    """8. Verify expired/replayed Slack requests (>300s old) are rejected."""
    secret = "test_signing_secret_12345"
    body = b'{"type":"event_callback"}'
    expired_ts = str(int(time.time()) - 600)  # 10 mins ago
    sig = generate_slack_signature(body, expired_ts, secret)

    is_valid = SlackProvider.verify_slack_signature(
        request_body=body,
        timestamp=expired_ts,
        signature=sig,
        signing_secret=secret,
        tolerance_seconds=300,
    )
    assert is_valid is False


@pytest.mark.asyncio
async def test_09_slack_url_verification(client: AsyncClient):
    """9. Verify Slack URL verification challenge returns challenge parameter."""
    challenge_payload = {
        "type": "url_verification",
        "token": "Jhj54668f44f9f43f87b8f04e4a7a8a2d",
        "challenge": "3eZbrw1aBm2rZgRNFDxV2595E9CY3gmdALWMmHkvFXO7tYXAYM8P",
    }
    res = await client.post("/api/webhooks/slack", json=challenge_payload)
    assert res.status_code == 200
    assert res.json() == {"challenge": "3eZbrw1aBm2rZgRNFDxV2595E9CY3gmdALWMmHkvFXO7tYXAYM8P"}


@pytest.mark.asyncio
async def test_10_invalid_oauth_state_rejection(client: AsyncClient):
    """10. Verify invalid or forged OAuth state is rejected with 400."""
    res = await client.post(
        "/api/integrations/slack/callback?code=fake_code&state=invalid_forged_state"
    )
    assert res.status_code == 400
    assert "invalid" in res.json()["detail"].lower()


# ==========================================
# 3. INGESTION & IDEMPOTENCY TESTS (11-15)
# ==========================================

@pytest.mark.asyncio
async def test_11_slack_message_ingestion(client: AsyncClient, db_session: AsyncSession):
    """11. Verify Slack message ingestion via webhook endpoint."""
    ob = Obligation(
        owner="Rahul",
        beneficiary="Ravi",
        action="Send database benchmark numbers",
        deadline=datetime.now(timezone.utc) + timedelta(days=2),
        status=ObligationStatus.CONFIRMED,
        obligation_type=ObligationType.OWED_TO_ME,
    )
    db_session.add(ob)
    await db_session.commit()

    webhook_payload = {
        "type": "event_callback",
        "team_id": "T_TEST_WORKSPACE",
        "event": {
            "type": "message",
            "user": "U_RAHUL",
            "user_name": "Rahul",
            "text": "Working on the database benchmark numbers. Will send them shortly.",
            "ts": "1609459500.000100",
            "channel": "C_DEV",
        }
    }

    res = await client.post("/api/webhooks/slack", json=webhook_payload)
    assert res.status_code in [200, 201]
    data = res.json()
    assert data["provider"] == "slack"
    assert data["semantic_role"] == "PROGRESS_UPDATE"
    assert ob.id in data["affected_obligation_ids"]


@pytest.mark.asyncio
async def test_12_duplicate_slack_event_detection(client: AsyncClient, db_session: AsyncSession):
    """12. Verify delivering the same Slack event twice returns DUPLICATE status."""
    ob = Obligation(
        owner="Rahul",
        beneficiary="Ravi",
        action="Provide Q3 performance audit",
        status=ObligationStatus.CONFIRMED,
        obligation_type=ObligationType.OWED_TO_ME,
    )
    db_session.add(ob)
    await db_session.commit()

    webhook_payload = {
        "type": "event_callback",
        "team_id": "T_DEDUP_TEST",
        "event_id": "EvDEDUP12345",
        "event": {
            "type": "message",
            "user": "U_RAHUL",
            "user_name": "Rahul",
            "text": "Sent the Q3 performance audit document.",
            "ts": "1609459900.000100",
            "channel": "C_TEST",
        }
    }

    res1 = await client.post("/api/webhooks/slack", json=webhook_payload)
    assert res1.status_code in [200, 201]
    assert res1.json()["status"] == "PROCESSED"
    first_id = res1.json()["event_id"]

    res2 = await client.post("/api/webhooks/slack", json=webhook_payload)
    assert res2.status_code in [200, 201]
    assert res2.json()["status"] == "DUPLICATE"
    assert res2.json()["event_id"] == first_id


@pytest.mark.asyncio
async def test_13_event_audit_creation(client: AsyncClient, db_session: AsyncSession):
    """13. Verify immutable IngestedEventRecord audit entry is created."""
    webhook_payload = {
        "type": "event_callback",
        "team_id": "T_AUDIT",
        "event": {
            "type": "message",
            "user": "U_ALICE",
            "user_name": "Alice",
            "text": "Hey everyone, just checking in!",
            "ts": "1609460100.000100",
            "channel": "C_GENERAL",
        }
    }
    res = await client.post("/api/webhooks/slack", json=webhook_payload)
    assert res.status_code in [200, 201]
    event_id = res.json()["event_id"]

    audit_stmt = select(IngestedEventRecord).where(IngestedEventRecord.id == event_id)
    audit_res = await db_session.execute(audit_stmt)
    record = audit_res.scalar_one_or_none()
    assert record is not None
    assert record.provider == "slack"
    assert record.sender == "Alice"
    assert record.semantic_role == EventSemanticRole.IRRELEVANT


def test_14_normalized_external_event_correctness():
    """14. Verify ExternalEvent fields adhere strictly to provider-agnostic contract."""
    provider = SlackProvider()
    raw = {
        "type": "event_callback",
        "team_id": "T1",
        "event": {
            "type": "message",
            "user": "U1",
            "user_name": "DevUser",
            "text": "Task finished",
            "ts": "1609459200.000100",
            "channel": "C1",
        }
    }
    evt = provider.normalize_event(raw)
    assert isinstance(evt, ExternalEvent)
    assert evt.source_type == "slack"
    assert evt.content == "Task finished"
    assert evt.sender == "DevUser"
    assert isinstance(evt.timestamp, datetime)


def test_15_slack_metadata_preservation():
    """15. Verify workspace, channel, thread_ts, and attachments metadata are preserved."""
    provider = SlackProvider()
    raw = {
        "type": "event_callback",
        "team_id": "T_METADATA",
        "event": {
            "type": "message",
            "user": "U_BOB",
            "user_name": "Bob",
            "text": "Uploaded the security report",
            "ts": "1609460200.000100",
            "thread_ts": "1609460100.000100",
            "channel": "C_SECURITY",
            "channel_name": "security-team",
            "files": [
                {
                    "name": "security_audit.pdf",
                    "filetype": "pdf",
                    "mimetype": "application/pdf",
                    "size": 524288,
                    "url_private": "https://slack.com/files/sec.pdf"
                }
            ]
        }
    }
    evt = provider.normalize_event(raw)
    assert evt.metadata["team_id"] == "T_METADATA"
    assert evt.metadata["channel_id"] == "C_SECURITY"
    assert evt.metadata["channel_name"] == "security-team"
    assert evt.metadata["thread_ts"] == "1609460100.000100"
    assert len(evt.metadata["attachments"]) == 1
    assert evt.metadata["attachments"][0]["name"] == "security_audit.pdf"


# ==========================================
# 4. INTELLIGENCE INTEGRATION TESTS (16-20)
# ==========================================

@pytest.mark.asyncio
async def test_16_slack_completion_event_creates_evidence_candidate(client: AsyncClient, db_session: AsyncSession):
    """16. Verify Slack completion message creates SUGGESTED evidence."""
    ob = Obligation(
        owner="Rahul",
        beneficiary="Ravi",
        action="Deliver benchmark numbers",
        status=ObligationStatus.CONFIRMED,
        obligation_type=ObligationType.OWED_TO_ME,
    )
    db_session.add(ob)
    await db_session.commit()

    webhook_payload = {
        "type": "event_callback",
        "team_id": "T_COMPLETION",
        "event": {
            "type": "message",
            "user": "U_RAHUL",
            "user_name": "Rahul",
            "text": "Sent the database benchmark numbers to Ravi.",
            "ts": str(time.time()),
            "channel": "C_DEV",
            "files": [{"name": "benchmark_results.csv", "size": 8192}]
        }
    }
    res = await client.post("/api/webhooks/slack", json=webhook_payload)
    assert res.status_code in [200, 201]
    data = res.json()
    assert len(data["evidence_records"]) > 0
    assert data["evidence_records"][0]["correlation_status"] == "SUGGESTED"
    assert data["evidence_records"][0]["semantic_role"] == "COMPLETION_SIGNAL"


@pytest.mark.asyncio
async def test_17_slack_progress_event_acknowledges_intervention(client: AsyncClient, db_session: AsyncSession):
    """17. Verify Slack progress update updates active intervention outcome to PROGRESS_REPORTED."""
    ob = Obligation(
        owner="Rahul",
        beneficiary="Ravi",
        action="Prepare system architecture review",
        status=ObligationStatus.CONFIRMED,
        obligation_type=ObligationType.OWED_TO_ME,
    )
    db_session.add(ob)
    await db_session.commit()

    inv = Intervention(
        obligation_id=ob.id,
        intervention_type=InterventionType.REQUEST_STATUS_UPDATE,
        target_owner="Rahul",
        target_beneficiary="Ravi",
        title="Reminder for Architecture Review",
        rationale="Deadline approaching",
        message_draft="Hi Rahul, checking in on the architecture review.",
        status=InterventionStatus.APPROVED,
        urgency="MEDIUM",
    )
    db_session.add(inv)
    await db_session.commit()

    # Progress webhook from Rahul
    webhook_payload = {
        "type": "event_callback",
        "team_id": "T_PROG",
        "event": {
            "type": "message",
            "user": "U_RAHUL",
            "user_name": "Rahul",
            "text": "Working on the system architecture review. Will finish draft today.",
            "ts": str(time.time()),
            "channel": "C_ARCH",
        }
    }
    res = await client.post("/api/webhooks/slack", json=webhook_payload)
    assert res.status_code in [200, 201]

    await db_session.refresh(inv)
    assert inv.outcome == InterventionOutcome.PROGRESS_REPORTED


@pytest.mark.asyncio
async def test_18_slack_blocker_event_recalculates_risk(client: AsyncClient, db_session: AsyncSession):
    """18. Verify Slack blocker event increases risk on correlated obligation."""
    ob = Obligation(
        owner="Rahul",
        beneficiary="Ravi",
        action="Deploy API gateway",
        deadline=datetime.now(timezone.utc) + timedelta(hours=6),
        status=ObligationStatus.CONFIRMED,
        obligation_type=ObligationType.OWED_TO_ME,
    )
    db_session.add(ob)
    await db_session.commit()

    # Ingest Blocker Event
    blocker_payload = {
        "type": "event_callback",
        "team_id": "T_BLOCK",
        "event": {
            "type": "message",
            "user": "U_RAHUL",
            "user_name": "Rahul",
            "text": "I couldn't deploy the API gateway because the SSL certificates failed.",
            "ts": str(time.time()),
            "channel": "C_OPS",
        }
    }
    res = await client.post("/api/webhooks/slack", json=blocker_payload)
    assert res.status_code in [200, 201]
    assert res.json()["semantic_role"] == "NON_COMPLETION_SIGNAL"

    # Assess Risk
    risk_assessment = await RiskEngine.assess_obligation(db_session, ob.id)
    assert risk_assessment is not None
    assert risk_assessment.risk_score >= 0.40


@pytest.mark.asyncio
async def test_19_completion_evidence_remains_human_gated(client: AsyncClient, db_session: AsyncSession):
    """19. Verify completion evidence does NOT automatically mark obligation COMPLETED."""
    ob = Obligation(
        owner="Rahul",
        beneficiary="Ravi",
        action="Submit tax filing documents",
        status=ObligationStatus.CONFIRMED,
        obligation_type=ObligationType.OWED_TO_ME,
    )
    db_session.add(ob)
    await db_session.commit()

    payload = {
        "type": "event_callback",
        "team_id": "T_TAX",
        "event": {
            "type": "message",
            "user": "U_RAHUL",
            "user_name": "Rahul",
            "text": "Sent the tax filing documents.",
            "ts": str(time.time()),
            "channel": "C_TAX",
        }
    }
    res = await client.post("/api/webhooks/slack", json=payload)
    assert res.status_code in [200, 201]

    # Verify obligation remains CONFIRMED
    await db_session.refresh(ob)
    assert ob.status == ObligationStatus.CONFIRMED


@pytest.mark.asyncio
async def test_20_confirmed_evidence_graph_propagation(client: AsyncClient, db_session: AsyncSession):
    """20. Verify confirming evidence triggers graph propagation and unblocks dependents."""
    ob1 = Obligation(
        owner="Rahul",
        beneficiary="Ravi",
        action="Complete auth module",
        status=ObligationStatus.CONFIRMED,
        obligation_type=ObligationType.OWED_TO_ME,
    )
    ob2 = Obligation(
        owner="Ravi",
        beneficiary="Team",
        action="Integrate auth into frontend",
        status=ObligationStatus.BLOCKED,
        obligation_type=ObligationType.OWED_BY_ME,
        block_reason={"blocked": True, "blocked_by": [{"obligation_id": "temp"}]}
    )
    db_session.add_all([ob1, ob2])
    await db_session.commit()

    edge = ObligationEdge(
        from_obligation_id=ob2.id,
        to_obligation_id=ob1.id,
        edge_type=EdgeType.DEPENDS_ON,
    )
    db_session.add(edge)
    await db_session.commit()

    # Ingest completion event
    payload = {
        "type": "event_callback",
        "team_id": "T_GRAPH",
        "event": {
            "type": "message",
            "user": "U_RAHUL",
            "user_name": "Rahul",
            "text": "Completed the auth module.",
            "ts": str(time.time()),
            "channel": "C_DEV",
        }
    }
    ingest_res = await client.post("/api/webhooks/slack", json=payload)
    ev_id = ingest_res.json()["evidence_records"][0]["id"]

    # Human confirms evidence
    confirm_res = await client.post(
        f"/api/obligations/{ob1.id}/evidence/{ev_id}/confirm",
        json={"notes": "Confirmed by Ravi"},
    )
    assert confirm_res.status_code == 200

    await db_session.refresh(ob1)
    await db_session.refresh(ob2)
    assert ob1.status == ObligationStatus.COMPLETED
    assert ob2.status == ObligationStatus.CONFIRMED  # Unblocked!


# ==========================================
# 5. CONNECTION MANAGEMENT TESTS (21-25)
# ==========================================

@pytest.mark.asyncio
async def test_21_connection_creation(db_session: AsyncSession):
    """21. Verify creating and persisting IntegrationConnection."""
    conn = await IntegrationService.create_or_update_connection(
        session=db_session,
        provider="slack",
        external_account_id="T_ACME_CORP",
        external_account_name="Acme Corp",
        status="CONNECTED",
        scopes=["channels:history", "chat:write"],
    )
    await db_session.commit()
    assert conn.provider == "slack"
    assert conn.external_account_id == "T_ACME_CORP"
    assert conn.status == "CONNECTED"


@pytest.mark.asyncio
async def test_22_connection_listing(client: AsyncClient, db_session: AsyncSession):
    """22. Verify GET /api/integrations lists connections."""
    await IntegrationService.create_or_update_connection(
        session=db_session,
        provider="slack",
        external_account_id="T_LIST_TEST",
        external_account_name="Listing Test",
        status="CONNECTED",
    )
    await db_session.commit()

    res = await client.get("/api/integrations")
    assert res.status_code == 200
    data = res.json()
    assert len(data["connections"]) >= 1


@pytest.mark.asyncio
async def test_23_safe_connection_response(client: AsyncClient, db_session: AsyncSession):
    """23. Verify connection response contains safe fields only."""
    await IntegrationService.create_or_update_connection(
        session=db_session,
        provider="slack",
        external_account_id="T_SAFE",
        external_account_name="Safe Workspace",
        encrypted_credentials="SECRET_TOKEN_VALUE",
    )
    await db_session.commit()

    res = await client.get("/api/integrations/slack")
    assert res.status_code == 200
    data = res.json()
    assert "encrypted_credentials" not in data
    assert "token" not in data
    assert data["provider"] == "slack"
    assert data["status"] == "CONNECTED"


@pytest.mark.asyncio
async def test_24_connection_test(client: AsyncClient, db_session: AsyncSession):
    """24. Verify POST /api/integrations/{provider}/test endpoint."""
    await IntegrationService.create_or_update_connection(
        session=db_session,
        provider="slack",
        external_account_id="T_TEST_WS",
        external_account_name="Test WS",
        status="CONNECTED",
    )
    await db_session.commit()

    res = await client.post("/api/integrations/slack/test")
    assert res.status_code == 200
    assert res.json()["success"] is True
    assert res.json()["provider"] == "slack"


@pytest.mark.asyncio
async def test_25_disconnect_flow(client: AsyncClient, db_session: AsyncSession):
    """25. Verify POST /api/integrations/{provider}/disconnect sets status to DISCONNECTED."""
    await IntegrationService.create_or_update_connection(
        session=db_session,
        provider="slack",
        external_account_id="T_DISC",
        external_account_name="Disc WS",
        status="CONNECTED",
    )
    await db_session.commit()

    res = await client.post("/api/integrations/slack/disconnect")
    assert res.status_code == 200
    assert res.json()["status"] == "DISCONNECTED"


# ==========================================
# 6. SECURITY & SECRET REDACTION TESTS (26-28)
# ==========================================

@pytest.mark.asyncio
async def test_26_secrets_never_in_api_response(client: AsyncClient):
    """26. Verify secrets never appear in /api/integrations response."""
    res = await client.get("/api/integrations")
    text = res.text.lower()
    assert "signing_secret" not in text
    assert "client_secret" not in text
    assert "bot_token" not in text


def test_27_secrets_never_in_serialized_event_metadata():
    """27. Verify normalized ExternalEvent filters out credential keys from metadata."""
    provider = SlackProvider()
    raw = {
        "type": "event_callback",
        "team_id": "T1",
        "event": {"type": "message", "text": "test", "user": "U1", "ts": "1609459200.000100"},
        "metadata": {
            "bot_token": "xoxb-secret-token",
            "signing_secret": "my-secret",
            "token": "sensitive-token",
            "safe_key": "safe_value",
        }
    }
    evt = provider.normalize_event(raw)
    assert "bot_token" not in evt.metadata
    assert "signing_secret" not in evt.metadata
    assert "token" not in evt.metadata
    assert evt.metadata.get("safe_key") == "safe_value"


@pytest.mark.asyncio
async def test_28_invalid_credentials_handled_safely(client: AsyncClient):
    """28. Verify testing connection on an unknown provider returns 404 cleanly."""
    res = await client.post("/api/integrations/unknown_provider_xyz/test")
    assert res.status_code == 404
    assert "not registered" in res.json()["detail"].lower()
