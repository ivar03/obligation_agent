import pytest
import json
import base64
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
from app.services.providers.gmail_provider import GmailProvider, parse_email_identity
from app.services.integration_service import IntegrationService
from app.services.event_ingestion_service import EventIngestionService
from app.services.risk_engine import RiskEngine
from app.services.graph_service import GraphService


# ==========================================
# 1. PROVIDER REGISTRATION & METADATA TESTS (1-5)
# ==========================================

def test_01_gmail_provider_registered():
    """1. Verify Gmail provider is registered in ProviderRegistry."""
    assert provider_registry.has_provider("gmail")
    provider = provider_registry.get("gmail")
    assert isinstance(provider, GmailProvider)
    assert provider.provider_name == "gmail"
    assert provider.provider_version == "1.0.0"


def test_02_provider_metadata_and_capabilities():
    """2. Verify provider capabilities listing contains mock, slack, and gmail without secrets."""
    providers = provider_registry.list_providers()
    provider_names = [p["name"] for p in providers]
    assert "mock" in provider_names
    assert "slack" in provider_names
    assert "gmail" in provider_names

    gmail_p = next(p for p in providers if p["name"] == "gmail")
    assert "events" in gmail_p["capabilities"]
    assert "messages" in gmail_p["capabilities"]
    assert "threads" in gmail_p["capabilities"]
    assert "attachments" in gmail_p["capabilities"]
    assert "email_ingestion" in gmail_p["capabilities"]

    for p in providers:
        assert "secret" not in p
        assert "token" not in p
        assert "client_secret" not in p


def test_03_gmail_normalization_standard_email():
    """3. Verify standard email payload normalizes into ExternalEvent correctly."""
    provider = GmailProvider()
    payload = {
        "from": "Rahul Sharma <rahul@acme.com>",
        "to": ["Ravi Kumar <ravi@acme.com>"],
        "subject": "Database benchmark numbers",
        "body": "Working on the database benchmark numbers. I'll send them shortly.",
        "message_id": "<msg_101@acme.com>",
        "thread_id": "thread_benchmarks_101",
    }
    event = provider.normalize_event(payload)
    assert isinstance(event, ExternalEvent)
    assert event.source_type == "gmail"
    assert event.sender == "Rahul Sharma"
    assert event.recipients == ["Ravi Kumar"]
    assert "Working on the database benchmark numbers" in event.content
    assert event.metadata["subject"] == "Database benchmark numbers"
    assert event.metadata["thread_id"] == "thread_benchmarks_101"
    assert event.source_ref == "gmail_msg_101@acme.com"


def test_04_malformed_payload_rejection():
    """4. Verify malformed Gmail payload rejection raises ValueError."""
    provider = GmailProvider()
    with pytest.raises(ValueError, match="Malformed Gmail payload"):
        provider.normalize_event({})

    with pytest.raises(ValueError, match="Malformed Gmail payload"):
        provider.normalize_event({"invalid_field_only": 123})


def test_05_gmail_identity_parsing():
    """5. Verify email identity parser extracts display name or clean email."""
    assert parse_email_identity("Rahul Sharma <rahul@acme.com>") == "Rahul Sharma"
    assert parse_email_identity("<rahul@acme.com>") == "rahul@acme.com"
    assert parse_email_identity("Rahul") == "Rahul"
    assert parse_email_identity("") == "Unknown"
    assert parse_email_identity(None) == "Unknown"


# ==========================================
# 2. EMAIL STRUCTURE & METADATA TESTS (6-11)
# ==========================================

def test_06_gmail_thread_reply_normalization():
    """6. Verify thread replies preserve in_reply_to, references, and thread_id."""
    provider = GmailProvider()
    payload = {
        "from": "Rahul <rahul@acme.com>",
        "to": "ravi@acme.com",
        "subject": "Re: Database benchmarks",
        "body": "Follow up reply.",
        "message_id": "<reply_202@acme.com>",
        "thread_id": "thread_benchmarks_101",
        "in_reply_to": "<msg_101@acme.com>",
        "references": ["<msg_101@acme.com>"],
    }
    event = provider.normalize_event(payload)
    assert event.metadata["in_reply_to"] == "<msg_101@acme.com>"
    assert event.metadata["references"] == ["<msg_101@acme.com>"]
    assert event.metadata["thread_id"] == "thread_benchmarks_101"


def test_07_gmail_attachments_metadata_normalization():
    """7. Verify email attachments are normalized safely without downloading files."""
    provider = GmailProvider()
    payload = {
        "from": "Rahul <rahul@acme.com>",
        "to": "ravi@acme.com",
        "subject": "Results",
        "body": "Attached benchmark csv.",
        "message_id": "<msg_att_303@acme.com>",
        "attachments": [
            {
                "name": "benchmark_results.csv",
                "filetype": "csv",
                "mimetype": "text/csv",
                "size": 24576,
                "attachment_id": "att_9988",
            }
        ],
    }
    event = provider.normalize_event(payload)
    assert len(event.metadata["attachments"]) == 1
    att = event.metadata["attachments"][0]
    assert att["name"] == "benchmark_results.csv"
    assert att["size"] == 24576
    assert att["mimetype"] == "text/csv"


def test_08_gmail_pubsub_push_normalization():
    """8. Verify Google Cloud Pub/Sub base64 payload normalization."""
    provider = GmailProvider()
    email_data = {
        "from": "Rahul <rahul@acme.com>",
        "to": ["Ravi <ravi@acme.com>"],
        "subject": "PubSub Email",
        "body": "Message delivered via Google Pub/Sub push notification.",
        "message_id": "<msg_pubsub_404@acme.com>",
    }
    encoded = base64.b64encode(json.dumps(email_data).encode("utf-8")).decode("utf-8")
    pubsub_payload = {
        "message": {
            "data": encoded,
            "messageId": "pubsub_msg_id_7777",
            "publishTime": "2026-08-31T01:00:00.000Z",
        }
    }
    event = provider.normalize_event(pubsub_payload)
    assert event.sender == "Rahul"
    assert event.recipients == ["Ravi"]
    assert "Google Pub/Sub" in event.content
    assert event.source_ref == "gmail_msg_pubsub_404@acme.com"


def test_09_canonical_scenarios_progress_and_completion():
    """9. Verify canonical scenarios A (progress) and B (completion)."""
    provider = GmailProvider()
    progress_evt = provider.normalize_event({"scenario": "GMAIL_SCENARIO_A_PROGRESS"})
    assert progress_evt.sender == "Rahul"
    assert "Working on the database benchmark numbers" in progress_evt.content

    completion_evt = provider.normalize_event({"scenario": "GMAIL_SCENARIO_B_COMPLETION"})
    assert "Sent the database benchmark numbers" in completion_evt.content
    assert len(completion_evt.metadata["attachments"]) > 0


def test_10_canonical_scenarios_blocker_and_request():
    """10. Verify canonical scenarios C (blocker) and D (request)."""
    provider = GmailProvider()
    blocker_evt = provider.normalize_event({"scenario": "GMAIL_SCENARIO_C_BLOCKER"})
    assert "database is unavailable" in blocker_evt.content

    request_evt = provider.normalize_event({"scenario": "GMAIL_SCENARIO_D_REQUEST"})
    assert "could you send the updated benchmark numbers" in request_evt.content


def test_11_canonical_scenarios_chatter_and_thread():
    """11. Verify canonical scenarios E (chatter) and F (thread reply)."""
    provider = GmailProvider()
    chatter_evt = provider.normalize_event({"scenario": "GMAIL_SCENARIO_E_CHATTER"})
    assert "Good morning everyone" in chatter_evt.content

    reply_evt = provider.normalize_event({"scenario": "GMAIL_SCENARIO_F_THREAD_REPLY"})
    assert reply_evt.metadata.get("in_reply_to") is not None


# ==========================================
# 3. OAUTH & CONNECTION MANAGEMENT TESTS (12-16)
# ==========================================

@pytest.mark.asyncio
async def test_12_gmail_oauth_url_generation(client: AsyncClient):
    """12. Verify OAuth connect URL generation with CSRF state protection."""
    res = await client.get("/api/integrations/gmail/connect")
    assert res.status_code == 200
    data = res.json()
    assert data["provider"] == "gmail"
    assert "accounts.google.com/o/oauth2/v2/auth" in data["authorization_url"]
    assert "gmail.readonly" in data["authorization_url"]
    assert "state=" in data["authorization_url"]
    assert len(data["state"]) > 20


@pytest.mark.asyncio
async def test_13_gmail_oauth_invalid_state_rejection(client: AsyncClient):
    """13. Verify invalid or forged OAuth state is rejected with 400."""
    res = await client.post(
        "/api/integrations/gmail/callback?code=test_code&state=invalid_forged_state"
    )
    assert res.status_code == 400
    assert "invalid" in res.json()["detail"].lower()


@pytest.mark.asyncio
async def test_14_gmail_oauth_callback_success(client: AsyncClient):
    """14. Verify OAuth callback exchanges code and persists connection record."""
    init_res = await client.get("/api/integrations/gmail/connect")
    state = init_res.json()["state"]

    cb_res = await client.post(f"/api/integrations/gmail/callback?code=mock_google_code_123&state={state}")
    assert cb_res.status_code == 200
    conn = cb_res.json()
    assert conn["provider"] == "gmail"
    assert conn["status"] == "CONNECTED"
    assert "email_ingestion" in conn["capabilities"]
    assert "access_token" not in conn  # Zero credential leakage


@pytest.mark.asyncio
async def test_15_gmail_connection_test_endpoint(client: AsyncClient):
    """15. Verify Gmail connection test endpoint returns active health status."""
    # Establish connection first
    init_res = await client.get("/api/integrations/gmail/connect")
    state = init_res.json()["state"]
    await client.post(f"/api/integrations/gmail/callback?code=mock_code&state={state}")

    test_res = await client.post("/api/integrations/gmail/test")
    assert test_res.status_code == 200
    data = test_res.json()
    assert data["provider"] == "gmail"
    assert data["status"] == "CONNECTED"


@pytest.mark.asyncio
async def test_16_gmail_disconnect_and_reconnect(client: AsyncClient):
    """16. Verify disconnecting and reconnecting Gmail connection."""
    # Establish connection
    init_res = await client.get("/api/integrations/gmail/connect")
    state = init_res.json()["state"]
    await client.post(f"/api/integrations/gmail/callback?code=mock_code&state={state}")

    # Disconnect
    disc_res = await client.post("/api/integrations/gmail/disconnect")
    assert disc_res.status_code == 200
    assert disc_res.json()["status"] == "DISCONNECTED"

    # Reconnect
    init_res2 = await client.get("/api/integrations/gmail/connect")
    state2 = init_res2.json()["state"]
    cb_res = await client.post(f"/api/integrations/gmail/callback?code=code_recon&state={state2}")
    assert cb_res.status_code == 200
    assert cb_res.json()["status"] == "CONNECTED"


# ==========================================
# 4. INGESTION & IDEMPOTENCY TESTS (17-19)
# ==========================================

@pytest.mark.asyncio
async def test_17_gmail_message_ingestion_webhook(client: AsyncClient, db_session: AsyncSession):
    """17. Verify Gmail message ingestion via dedicated webhook endpoint."""
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
        "from": "Rahul <rahul@acme.com>",
        "to": ["Ravi <ravi@acme.com>"],
        "subject": "Database benchmark numbers update",
        "body": "Working on the database benchmark numbers. Will send them shortly.",
        "message_id": f"<msg_ingest_{int(time.time()*1000)}@acme.com>",
    }

    res = await client.post("/api/webhooks/gmail", json=webhook_payload)
    assert res.status_code in [200, 201]
    data = res.json()
    assert data["provider"] == "gmail"
    assert data["semantic_role"] == "PROGRESS_UPDATE"
    assert ob.id in data["affected_obligation_ids"]


@pytest.mark.asyncio
async def test_18_duplicate_gmail_message_idempotency(client: AsyncClient, db_session: AsyncSession):
    """18. Verify delivering the exact same Gmail message twice returns DUPLICATE."""
    fixed_msg_id = f"<msg_idem_{uuid.uuid4().hex[:8]}@acme.com>"
    payload = {
        "from": "Rahul <rahul@acme.com>",
        "to": "Ravi <ravi@acme.com>",
        "subject": "Idempotency test email",
        "body": "Working on the database benchmark numbers.",
        "message_id": fixed_msg_id,
    }

    res1 = await client.post("/api/webhooks/gmail", json=payload)
    assert res1.status_code in [200, 201]
    assert res1.json()["status"] in ["PROCESSED", "NO_MATCH"]
    first_id = res1.json()["event_id"]

    res2 = await client.post("/api/webhooks/gmail", json=payload)
    assert res2.status_code in [200, 201]
    assert res2.json()["status"] == "DUPLICATE"
    assert res2.json()["event_id"] == first_id


@pytest.mark.asyncio
async def test_19_gmail_audit_record_creation(client: AsyncClient, db_session: AsyncSession):
    """19. Verify immutable IngestedEventRecord audit entry is created for Gmail events."""
    webhook_payload = {
        "from": "Alice <alice@acme.com>",
        "to": ["Team <team@acme.com>"],
        "subject": "Weekly sync check-in",
        "body": "Hey everyone, just checking in for the weekly sync!",
        "message_id": f"<msg_audit_{uuid.uuid4().hex[:8]}@acme.com>",
    }
    res = await client.post("/api/webhooks/gmail", json=webhook_payload)
    assert res.status_code in [200, 201]
    event_id = res.json()["event_id"]

    audit_stmt = select(IngestedEventRecord).where(IngestedEventRecord.id == event_id)
    audit_res = await db_session.execute(audit_stmt)
    record = audit_res.scalar_one_or_none()
    assert record is not None
    assert record.provider == "gmail"
    assert record.sender == "Alice"
    assert record.semantic_role == EventSemanticRole.IRRELEVANT


# ==========================================
# 5. INTELLIGENCE CORRELATION & RISK (20-25)
# ==========================================

@pytest.mark.asyncio
async def test_20_gmail_progress_event_acknowledges_intervention(client: AsyncClient, db_session: AsyncSession):
    """20. Verify Gmail progress update updates active intervention outcome to PROGRESS_REPORTED."""
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

    payload = {
        "from": "Rahul <rahul@acme.com>",
        "to": "Ravi <ravi@acme.com>",
        "subject": "Re: Architecture Review",
        "body": "Working on the system architecture review. Will finish draft today.",
        "message_id": f"<msg_arch_{uuid.uuid4().hex[:8]}@acme.com>",
    }
    res = await client.post("/api/webhooks/gmail", json=payload)
    assert res.status_code in [200, 201]

    await db_session.refresh(inv)
    assert inv.outcome == InterventionOutcome.PROGRESS_REPORTED


@pytest.mark.asyncio
async def test_21_gmail_blocker_event_recalculates_risk(client: AsyncClient, db_session: AsyncSession):
    """21. Verify Gmail blocker event increases risk on correlated obligation."""
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

    payload = {
        "from": "Rahul <rahul@acme.com>",
        "to": "Ravi <ravi@acme.com>",
        "subject": "API gateway blocked",
        "body": "I couldn't deploy the API gateway because the SSL certificates failed.",
        "message_id": f"<msg_block_{uuid.uuid4().hex[:8]}@acme.com>",
    }
    res = await client.post("/api/webhooks/gmail", json=payload)
    assert res.status_code in [200, 201]
    assert res.json()["semantic_role"] == "NON_COMPLETION_SIGNAL"

    risk_assessment = await RiskEngine.assess_obligation(db_session, ob.id)
    assert risk_assessment is not None
    assert risk_assessment.risk_score >= 0.40


@pytest.mark.asyncio
async def test_22_gmail_completion_evidence_remains_human_gated(client: AsyncClient, db_session: AsyncSession):
    """22. Verify completion evidence does NOT automatically mark obligation COMPLETED."""
    ob = Obligation(
        owner="Rahul",
        beneficiary="Ravi",
        action="Submit financial projections",
        deadline=datetime.now(timezone.utc) + timedelta(days=2),
        status=ObligationStatus.CONFIRMED,
        obligation_type=ObligationType.OWED_TO_ME,
    )
    db_session.add(ob)
    await db_session.commit()

    payload = {
        "from": "Rahul <rahul@acme.com>",
        "to": "Ravi <ravi@acme.com>",
        "subject": "Financial projections attached",
        "body": "Sent the financial projections for Q4.",
        "message_id": f"<msg_fin_{uuid.uuid4().hex[:8]}@acme.com>",
        "attachments": [{"name": "q4_projections.xlsx", "size": 12000}],
    }
    res = await client.post("/api/webhooks/gmail", json=payload)
    assert res.status_code in [200, 201]

    await db_session.refresh(ob)
    assert ob.status == ObligationStatus.CONFIRMED  # Human gate intact


@pytest.mark.asyncio
async def test_23_human_confirmation_triggers_obligation_completed(client: AsyncClient, db_session: AsyncSession):
    """23. Verify human confirming suggested evidence marks obligation COMPLETED."""
    ob = Obligation(
        owner="Rahul",
        beneficiary="Ravi",
        action="Deliver benchmark dataset",
        deadline=datetime.now(timezone.utc) + timedelta(days=1),
        status=ObligationStatus.CONFIRMED,
        obligation_type=ObligationType.OWED_TO_ME,
    )
    db_session.add(ob)
    await db_session.commit()

    payload = {
        "from": "Rahul <rahul@acme.com>",
        "to": "Ravi <ravi@acme.com>",
        "subject": "Benchmark dataset",
        "body": "Sent the benchmark dataset.",
        "message_id": f"<msg_bench_{uuid.uuid4().hex[:8]}@acme.com>",
        "attachments": [{"name": "dataset.csv", "size": 8192}],
    }
    res = await client.post("/api/webhooks/gmail", json=payload)
    data = res.json()
    matching_evs = [e for e in data["evidence_records"] if e["obligation_id"] == ob.id]
    assert len(matching_evs) > 0
    ev_id = matching_evs[0]["id"]

    confirm_res = await client.post(
        f"/api/obligations/{ob.id}/evidence/{ev_id}/confirm",
        json={"notes": "Verified dataset content."},
    )
    assert confirm_res.status_code == 200

    await db_session.refresh(ob)
    assert ob.status == ObligationStatus.COMPLETED


@pytest.mark.asyncio
async def test_24_completion_unblocks_graph_dependency(client: AsyncClient, db_session: AsyncSession):
    """24. Verify completing prerequisite obligation unblocks dependent obligation."""
    ob_prereq = Obligation(
        owner="Rahul",
        beneficiary="Ravi",
        action="Deliver benchmark dataset for migration",
        deadline=datetime.now(timezone.utc) + timedelta(days=1),
        status=ObligationStatus.CONFIRMED,
        obligation_type=ObligationType.OWED_TO_ME,
    )
    ob_dep = Obligation(
        owner="Ravi",
        beneficiary="Management",
        action="Execute migration dependent on benchmarks",
        deadline=datetime.now(timezone.utc) + timedelta(days=2),
        status=ObligationStatus.BLOCKED,
        obligation_type=ObligationType.OWED_BY_ME,
        block_reason={"blocked": True, "blocked_by": [{"obligation_id": "placeholder"}]},
    )
    db_session.add_all([ob_prereq, ob_dep])
    await db_session.commit()

    edge = ObligationEdge(
        from_obligation_id=ob_dep.id,
        to_obligation_id=ob_prereq.id,
        edge_type=EdgeType.DEPENDS_ON,
    )
    db_session.add(edge)
    await db_session.commit()

    # Ingest completion
    payload = {
        "from": "Rahul <rahul@acme.com>",
        "to": "Ravi <ravi@acme.com>",
        "subject": "Benchmark dataset delivered",
        "body": "Sent the benchmark dataset for migration.",
        "message_id": f"<msg_dep_unblock_{uuid.uuid4().hex[:8]}@acme.com>",
        "attachments": [{"name": "migration_benchmarks.csv", "size": 16000}],
    }
    res = await client.post("/api/webhooks/gmail", json=payload)
    data = res.json()
    matching_evs = [e for e in data["evidence_records"] if e["obligation_id"] == ob_prereq.id]
    assert len(matching_evs) > 0
    ev_id = matching_evs[0]["id"]

    # Confirm
    confirm_res = await client.post(
        f"/api/obligations/{ob_prereq.id}/evidence/{ev_id}/confirm",
        json={"notes": "Approved."},
    )
    assert confirm_res.status_code == 200

    await db_session.refresh(ob_prereq)
    await db_session.refresh(ob_dep)
    assert ob_prereq.status == ObligationStatus.COMPLETED
    assert ob_dep.status == ObligationStatus.CONFIRMED  # UNBLOCKED!


@pytest.mark.asyncio
async def test_25_risk_engine_decreases_on_completed_obligation(client: AsyncClient, db_session: AsyncSession):
    """25. Verify risk score drops to 0 on completed obligation."""
    ob = Obligation(
        owner="Rahul",
        beneficiary="Ravi",
        action="Complete risk benchmark verification",
        status=ObligationStatus.COMPLETED,
        obligation_type=ObligationType.OWED_TO_ME,
    )
    db_session.add(ob)
    await db_session.commit()

    risk = await RiskEngine.assess_obligation(db_session, ob.id)
    assert risk.risk_score == 0.0
    assert risk.risk_level == RiskLevel.LOW


# ==========================================
# 6. SECURITY, CLASSIFICATION & MULTI-PROVIDER (26-32)
# ==========================================

@pytest.mark.asyncio
async def test_26_pubsub_token_verification(client: AsyncClient, monkeypatch):
    """26. Verify Google Cloud Pub/Sub verification token validation."""
    monkeypatch.setattr(settings, "GMAIL_PUBSUB_VERIFICATION_TOKEN", "pubsub_token_sec_999")

    # Bad Token -> 401
    res_bad = await client.post(
        "/api/webhooks/gmail?token=bad_token",
        json={"scenario": "GMAIL_SCENARIO_A_PROGRESS"},
    )
    assert res_bad.status_code == 401
    assert "invalid token" in res_bad.json()["detail"]

    # Valid Token -> 200
    res_ok = await client.post(
        "/api/webhooks/gmail?token=pubsub_token_sec_999",
        json={"scenario": "GMAIL_SCENARIO_A_PROGRESS"},
    )
    assert res_ok.status_code == 200


def test_27_no_secrets_in_external_event_metadata():
    """27. Verify sensitive tokens and secrets are redacted from ExternalEvent metadata."""
    provider = GmailProvider()
    payload = {
        "from": "Rahul <rahul@acme.com>",
        "to": "ravi@acme.com",
        "subject": "Secret check",
        "body": "Normal body",
        "metadata": {
            "token": "secret_oauth_token_xyz",
            "access_token": "bearer_12345",
            "secret": "signing_sec_999",
            "client_secret": "my_client_secret",
            "safe_tag": "engineering_qa",
        },
    }
    event = provider.normalize_event(payload)
    assert "safe_tag" in event.metadata
    assert "token" not in event.metadata
    assert "access_token" not in event.metadata
    assert "secret" not in event.metadata
    assert "client_secret" not in event.metadata


@pytest.mark.asyncio
async def test_28_no_secrets_in_integrations_list_api(client: AsyncClient):
    """28. Verify GET /api/integrations exposes only safe metadata."""
    res = await client.get("/api/integrations")
    assert res.status_code == 200
    data = res.json()
    for conn in data["connections"]:
        assert "encrypted_credentials" not in conn
        assert "access_token" not in conn
        assert "refresh_token" not in conn


@pytest.mark.asyncio
async def test_29_gmail_request_email_classification(client: AsyncClient):
    """29. Verify request email is classified as REQUEST."""
    payload = {
        "from": "Ravi <ravi@acme.com>",
        "to": "Rahul <rahul@acme.com>",
        "subject": "Request for updated numbers",
        "body": "Rahul, could you send the updated benchmark numbers?",
        "message_id": f"<msg_req_{uuid.uuid4().hex[:8]}@acme.com>",
    }
    res = await client.post("/api/webhooks/gmail", json=payload)
    assert res.status_code in [200, 201]
    assert res.json()["semantic_role"] == "REQUEST"


@pytest.mark.asyncio
async def test_30_gmail_chatter_filtering(client: AsyncClient):
    """30. Verify chatter email is classified as IRRELEVANT."""
    payload = {
        "from": "Ravi <ravi@acme.com>",
        "to": "Team <team@acme.com>",
        "subject": "Morning Greeting",
        "body": "Good morning everyone! Hope you all have a productive week.",
        "message_id": f"<msg_chatter_{uuid.uuid4().hex[:8]}@acme.com>",
    }
    res = await client.post("/api/webhooks/gmail", json=payload)
    assert res.status_code in [200, 201]
    assert res.json()["semantic_role"] == "IRRELEVANT"


def test_31_unknown_provider_rejection():
    """31. Verify unknown provider resolution raises ValueError."""
    with pytest.raises(ValueError, match="Unknown provider 'unsupported_email_provider'"):
        provider_registry.get("unsupported_email_provider")


def test_32_multi_provider_coexistence():
    """32. Verify mock, slack, and gmail coexist and normalize independently."""
    p_mock = provider_registry.get("mock")
    p_slack = provider_registry.get("slack")
    p_gmail = provider_registry.get("gmail")

    assert p_mock.provider_name == "mock"
    assert p_slack.provider_name == "slack"
    assert p_gmail.provider_name == "gmail"

    evt_mock = p_mock.normalize_event({"scenario": "SCENARIO_A_COMPLETION"})
    evt_slack = p_slack.normalize_event({
        "type": "event_callback",
        "team_id": "T1",
        "event": {"type": "message", "text": "Slack message", "ts": "1609459200.000100", "user": "U1"}
    })
    evt_gmail = p_gmail.normalize_event({"scenario": "GMAIL_SCENARIO_A_PROGRESS"})

    assert evt_mock.source_type == "slack" or evt_mock.source_type == "mock"
    assert evt_slack.source_type == "slack"
    assert evt_gmail.source_type == "gmail"
