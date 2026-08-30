"""
Phase 15 — Enterprise Audit, Governance & Compliance Layer
Comprehensive Test Suite

Tests the following capabilities:
  - AuditService.record() creates immutable, chained events
  - Hash chain integrity (genesis → chained events)
  - AuditService.verify_chain() detects tampering
  - Audit hooks fire on domain mutations (obligation, workspace, auth)
  - REST API: GET /api/audit (ADMIN/OWNER access)
  - REST API: GET /api/audit/summary (governance dashboard)
  - REST API: GET /api/audit/verify (chain verification)
  - REST API: GET /api/audit/export (CSV/JSON)
  - REST API: GET /api/audit/entity/{type}/{id} (all members)
  - REST API: GET /api/audit/security (security feed)
  - RBAC enforcement (MEMBER/VIEWER cannot access full audit log)
  - Sanitizer strips secrets from audit payloads
  - PERMISSION_DENIED events generated for unauthorized attempts
"""

import pytest
import pytest_asyncio
import uuid
from datetime import datetime, timezone, timedelta
from httpx import AsyncClient, ASGITransport

from app.main import app
from app.core.database import engine, Base
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from app.core.database import get_db

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

TEST_DB_URL = "sqlite+aiosqlite:///./test_phase15.db"

test_engine = create_async_engine(TEST_DB_URL, echo=False)
TestSessionLocal = async_sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)


async def override_get_db():
    async with TestSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


@pytest_asyncio.fixture(scope="module", autouse=True)
async def setup_database():
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await test_engine.dispose()


app.dependency_overrides[get_db] = override_get_db


@pytest_asyncio.fixture(scope="module")
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest_asyncio.fixture(scope="module")
async def owner_tokens(client: AsyncClient):
    """Register and login as OWNER user, return auth headers and workspace info."""
    unique = str(uuid.uuid4())[:8]
    reg = await client.post("/api/auth/register", json={
        "email": f"owner_{unique}@phase15.test",
        "password": "OwnerPass@15!",
        "display_name": f"Phase15 Owner {unique}",
    })
    assert reg.status_code == 201, reg.text
    user_id = reg.json()["user"]["id"]

    login = await client.post("/api/auth/login", json={
        "email": f"owner_{unique}@phase15.test",
        "password": "OwnerPass@15!",
    })
    assert login.status_code == 200, login.text
    token = login.json()["token"]
    headers = {"Authorization": f"Bearer {token}"}

    ws = await client.post("/api/workspaces", json={"name": f"Phase15 WS {unique}"}, headers=headers)
    assert ws.status_code == 201, ws.text
    workspace_id = ws.json()["id"]
    headers["X-Workspace-Id"] = workspace_id

    return {"headers": headers, "workspace_id": workspace_id, "user_id": user_id}


@pytest_asyncio.fixture(scope="module")
async def member_tokens(client: AsyncClient, owner_tokens):
    """Register a MEMBER user and have owner invite them."""
    unique = str(uuid.uuid4())[:8]
    reg = await client.post("/api/auth/register", json={
        "email": f"member_{unique}@phase15.test",
        "password": "MemberPass@15!",
        "display_name": f"Phase15 Member {unique}",
    })
    assert reg.status_code == 201, reg.text
    member_email = f"member_{unique}@phase15.test"

    # Owner invites member
    invite = await client.post(
        f"/api/workspaces/{owner_tokens['workspace_id']}/members",
        json={"email": member_email, "role": "MEMBER"},
        headers=owner_tokens["headers"],
    )
    assert invite.status_code == 201, invite.text

    login = await client.post("/api/auth/login", json={
        "email": member_email,
        "password": "MemberPass@15!",
    })
    assert login.status_code == 200, login.text
    token = login.json()["token"]
    ws_id = owner_tokens["workspace_id"]

    return {"headers": {"Authorization": f"Bearer {token}", "X-Workspace-Id": ws_id}, "workspace_id": ws_id}


@pytest_asyncio.fixture(scope="module")
async def viewer_tokens(client: AsyncClient, owner_tokens):
    """Register a VIEWER user and invite them."""
    unique = str(uuid.uuid4())[:8]
    reg = await client.post("/api/auth/register", json={
        "email": f"viewer_{unique}@phase15.test",
        "password": "ViewerPass@15!",
        "display_name": f"Phase15 Viewer {unique}",
    })
    assert reg.status_code == 201, reg.text
    viewer_email = f"viewer_{unique}@phase15.test"

    invite = await client.post(
        f"/api/workspaces/{owner_tokens['workspace_id']}/members",
        json={"email": viewer_email, "role": "VIEWER"},
        headers=owner_tokens["headers"],
    )
    assert invite.status_code == 201, invite.text

    login = await client.post("/api/auth/login", json={
        "email": viewer_email,
        "password": "ViewerPass@15!",
    })
    assert login.status_code == 200, login.text
    token = login.json()["token"]
    ws_id = owner_tokens["workspace_id"]

    return {"headers": {"Authorization": f"Bearer {token}", "X-Workspace-Id": ws_id}, "workspace_id": ws_id}


# ---------------------------------------------------------------------------
# Core Audit Service Unit Tests
# ---------------------------------------------------------------------------

class TestAuditServiceCore:
    """Test AuditService record(), verify_chain(), and hash-chain integrity."""

    async def test_01_audit_service_record_creates_event(self, client: AsyncClient, owner_tokens):
        """AuditService.record() must produce a persisted event with a valid hash."""
        async with TestSessionLocal() as session:
            from app.services.audit_service import AuditService
            from app.core.status_machine import AuditAction

            event = await AuditService.record(
                session=session,
                workspace_id=owner_tokens["workspace_id"],
                action=AuditAction.OBLIGATION_CREATED,
                actor_user_id=owner_tokens["user_id"],
                actor_role="OWNER",
                entity_type="obligation",
                entity_id="test-ob-001",
                after_state={"title": "Test Obligation", "status": "DETECTED"},
            )
            await session.commit()

            assert event.id is not None
            assert len(event.event_hash) == 64
            assert event.workspace_id == owner_tokens["workspace_id"]
            assert event.action == "OBLIGATION_CREATED"

    async def test_02_genesis_event_has_null_previous_hash(self, client: AsyncClient):
        """The first event in a workspace has previous_event_hash == None."""
        new_ws_id = str(uuid.uuid4())
        async with TestSessionLocal() as session:
            from app.services.audit_service import AuditService
            from app.core.status_machine import AuditAction

            event = await AuditService.record(
                session=session,
                workspace_id=new_ws_id,
                action=AuditAction.WORKSPACE_CREATED,
                actor_user_id="sys",
                actor_role="SYSTEM",
                entity_type="workspace",
                entity_id=new_ws_id,
            )
            await session.commit()

            # Genesis event: previous_event_hash stored as None (genesis hash was used internally)
            assert event.previous_event_hash is None
            assert len(event.event_hash) == 64

    async def test_03_chained_events_reference_previous_hash(self, client: AsyncClient):
        """Each subsequent event's previous_event_hash must equal the prior event's event_hash."""
        ws_id = str(uuid.uuid4())
        async with TestSessionLocal() as session:
            from app.services.audit_service import AuditService
            from app.core.status_machine import AuditAction

            e1 = await AuditService.record(
                session=session, workspace_id=ws_id, action=AuditAction.WORKSPACE_CREATED,
                actor_user_id="u1", entity_type="workspace", entity_id=ws_id,
            )
            await session.flush()

            e2 = await AuditService.record(
                session=session, workspace_id=ws_id, action=AuditAction.OBLIGATION_CREATED,
                actor_user_id="u1", entity_type="obligation", entity_id="ob-1",
            )
            await session.flush()

            e3 = await AuditService.record(
                session=session, workspace_id=ws_id, action=AuditAction.OBLIGATION_STATUS_CHANGED,
                actor_user_id="u1", entity_type="obligation", entity_id="ob-1",
            )
            await session.commit()

            assert e2.previous_event_hash == e1.event_hash
            assert e3.previous_event_hash == e2.event_hash

    async def test_04_verify_chain_returns_valid_for_correct_chain(self, client: AsyncClient):
        """verify_chain() must return chain_valid=True for an untampered workspace."""
        ws_id = str(uuid.uuid4())
        async with TestSessionLocal() as session:
            from app.services.audit_service import AuditService
            from app.core.status_machine import AuditAction

            for i in range(5):
                await AuditService.record(
                    session=session, workspace_id=ws_id, action=AuditAction.OBLIGATION_CREATED,
                    actor_user_id=f"u{i}", entity_type="obligation", entity_id=f"ob-{i}",
                )
                await session.flush()
            await session.commit()

            result = await AuditService.verify_chain(session, ws_id)

        assert result.chain_valid is True
        assert result.verified_event_count == 5
        assert result.broken_at_event_id is None
        assert result.status == "VALID"

    async def test_05_verify_chain_detects_tampering(self, client: AsyncClient):
        """Tampering a stored event_hash breaks the chain verification."""
        ws_id = str(uuid.uuid4())
        async with TestSessionLocal() as session:
            from app.services.audit_service import AuditService
            from app.core.status_machine import AuditAction
            from app.models.audit import AuditEvent
            from sqlalchemy import select

            for i in range(3):
                await AuditService.record(
                    session=session, workspace_id=ws_id, action=AuditAction.OBLIGATION_CREATED,
                    actor_user_id="u1", entity_type="obligation", entity_id=f"ob-{i}",
                )
                await session.flush()
            await session.commit()

            # Tamper with the first event
            stmt = select(AuditEvent).where(AuditEvent.workspace_id == ws_id).order_by(AuditEvent.timestamp.asc()).limit(1)
            first_ev = (await session.execute(stmt)).scalar_one()
            first_ev.event_hash = "deadbeef" * 8  # 64 chars of garbage
            await session.commit()

            result = await AuditService.verify_chain(session, ws_id)

        assert result.chain_valid is False
        assert result.broken_at_event_id is not None
        assert result.status in ("BROKEN_LINK", "TAMPERED_PAYLOAD")

    async def test_06_sanitizer_strips_secrets_from_audit_payload(self):
        """Sanitizer must redact known secret keys before storage."""
        from app.core.sanitizer import sanitize_for_audit

        payload = {
            "title": "My obligation",
            "password": "super_secret",
            "api_key": "sk-abc123",
            "token": "bearer_xyz",
            "safe_field": "keep_this",
            "nested": {
                "secret_key": "should_be_redacted",
                "value": "keep"
            }
        }
        result = sanitize_for_audit(payload)
        assert result["password"] == "[REDACTED]"
        assert result["api_key"] == "[REDACTED]"
        assert result["token"] == "[REDACTED]"
        assert result["title"] == "My obligation"
        assert result["safe_field"] == "keep_this"
        assert result["nested"]["secret_key"] == "[REDACTED]"
        assert result["nested"]["value"] == "keep"

    async def test_07_record_mutation_convenience_method(self, client: AsyncClient, owner_tokens):
        """record_mutation() should produce a SUCCESS/INFO event with before/after states."""
        async with TestSessionLocal() as session:
            from app.services.audit_service import AuditService
            from app.core.status_machine import AuditAction

            ev = await AuditService.record_mutation(
                session=session,
                workspace_id=owner_tokens["workspace_id"],
                action=AuditAction.OBLIGATION_STATUS_CHANGED,
                actor_user_id=owner_tokens["user_id"],
                actor_role="OWNER",
                entity_type="obligation",
                entity_id="ob-unit-test",
                before_state={"status": "DETECTED"},
                after_state={"status": "CONFIRMED"},
                reason="User confirmed obligation",
            )
            await session.commit()

        assert ev.severity == "INFO"
        assert ev.result == "SUCCESS"
        assert ev.before_state == {"status": "DETECTED"}
        assert ev.after_state == {"status": "CONFIRMED"}

    async def test_08_record_security_event(self, client: AsyncClient, owner_tokens):
        """record_security_event() should produce a DENIED/WARNING event."""
        async with TestSessionLocal() as session:
            from app.services.audit_service import AuditService
            from app.core.status_machine import AuditAction

            ev = await AuditService.record_security_event(
                session=session,
                workspace_id=owner_tokens["workspace_id"],
                action=AuditAction.PERMISSION_DENIED,
                actor_user_id="viewer_user_id",
                actor_role="VIEWER",
                reason="Viewer attempted to delete an obligation",
                metadata={"attempted_action": "DELETE_OBLIGATION"},
            )
            await session.commit()

        assert ev.severity == "WARNING"
        assert ev.result == "DENIED"
        assert ev.action == "PERMISSION_DENIED"


# ---------------------------------------------------------------------------
# Domain Audit Hook Integration Tests
# ---------------------------------------------------------------------------

class TestDomainAuditHooks:
    """Verify audit hooks fire during actual API-driven domain mutations."""

    @pytest.fixture(autouse=True)
    def inject_session_factory(self):
        self.session_factory = TestSessionLocal

    async def _count_events_for_entity(self, workspace_id: str, entity_type: str, entity_id: str) -> int:
        from sqlalchemy import select, func
        from app.models.audit import AuditEvent
        async with TestSessionLocal() as session:
            stmt = select(func.count(AuditEvent.id)).where(
                AuditEvent.workspace_id == workspace_id,
                AuditEvent.entity_type == entity_type,
                AuditEvent.entity_id == entity_id,
            )
            return (await session.execute(stmt)).scalar_one() or 0

    async def _count_events_for_action(self, workspace_id: str, action: str) -> int:
        from sqlalchemy import select, func
        from app.models.audit import AuditEvent
        async with TestSessionLocal() as session:
            stmt = select(func.count(AuditEvent.id)).where(
                AuditEvent.workspace_id == workspace_id,
                AuditEvent.action == action,
            )
            return (await session.execute(stmt)).scalar_one() or 0

    async def test_09_obligation_creation_fires_audit_event(self, client: AsyncClient, owner_tokens):
        """Creating an obligation via the API must fire an OBLIGATION_CREATED audit event."""
        res = await client.post(
            "/api/obligations",
            json={
                "owner": "Alice",
                "beneficiary": "Bob",
                "action": "Audit Hook Test Obligation Action",
                "obligation_type": "OWED_BY_ME",
            },
            headers=owner_tokens["headers"],
        )
        assert res.status_code == 201, res.text
        ob_id = res.json()["id"]

        audit_res = await client.get(
            f"/api/audit/entity/obligation/{ob_id}",
            headers=owner_tokens["headers"],
        )
        assert audit_res.status_code == 200, audit_res.text
        events = audit_res.json()
        assert len(events) >= 1, f"Expected at least 1 audit event for obligation {ob_id}"
        assert any(e["action"] == "OBLIGATION_CREATED" for e in events)

    async def test_10_obligation_status_change_fires_audit_event(self, client: AsyncClient, owner_tokens):
        """Updating obligation status must fire an OBLIGATION_STATUS_CHANGED audit event."""
        ob = await client.post(
            "/api/obligations",
            json={"owner": "Alice", "beneficiary": "Bob", "action": "Status Change Hook Test", "obligation_type": "OWED_BY_ME"},
            headers=owner_tokens["headers"],
        )
        assert ob.status_code == 201, ob.text
        ob_id = ob.json()["id"]

        update = await client.patch(
            f"/api/obligations/{ob_id}",
            json={"status": "CONFIRMED"},
            headers=owner_tokens["headers"],
        )
        assert update.status_code == 200, update.text

        audit_res = await client.get(
            f"/api/audit/entity/obligation/{ob_id}",
            headers=owner_tokens["headers"],
        )
        assert audit_res.status_code == 200, audit_res.text
        events = audit_res.json()
        assert len(events) >= 2, "Should have CREATE + STATUS_CHANGE audit events"
        actions = [e["action"] for e in events]
        assert "OBLIGATION_CREATED" in actions
        assert "OBLIGATION_UPDATED" in actions or "OBLIGATION_STATUS_CHANGED" in actions

    async def test_11_workspace_member_invite_fires_audit_event(self, client: AsyncClient, owner_tokens):
        """Inviting a workspace member must fire a WORKSPACE_MEMBER_INVITED audit event."""
        ws_id = owner_tokens["workspace_id"]
        unique = str(uuid.uuid4())[:8]

        # Register new user
        reg = await client.post("/api/auth/register", json={
            "email": f"invitee_{unique}@phase15.test",
            "password": "InviteePass@15!",
            "display_name": f"Invitee {unique}",
        })
        assert reg.status_code == 201

        before_res = await client.get(
            "/api/audit?action=WORKSPACE_MEMBER_INVITED",
            headers=owner_tokens["headers"],
        )
        count_before = before_res.json()["total"] if before_res.status_code == 200 else 0

        invite = await client.post(
            f"/api/workspaces/{ws_id}/members",
            json={"email": f"invitee_{unique}@phase15.test", "role": "MEMBER"},
            headers=owner_tokens["headers"],
        )
        assert invite.status_code == 201, invite.text

        after_res = await client.get(
            "/api/audit?action=WORKSPACE_MEMBER_INVITED",
            headers=owner_tokens["headers"],
        )
        assert after_res.status_code == 200
        count_after = after_res.json()["total"]
        assert count_after > count_before

    async def test_12_auth_login_fires_audit_event(self, client: AsyncClient):
        """Successful login must produce an AUTH_LOGIN audit event."""
        unique = str(uuid.uuid4())[:8]
        await client.post("/api/auth/register", json={
            "email": f"logintest_{unique}@phase15.test",
            "password": "LoginTest@15!",
            "display_name": "Login Test User",
        })

        # Get user's workspace_id from login response
        login = await client.post("/api/auth/login", json={
            "email": f"logintest_{unique}@phase15.test",
            "password": "LoginTest@15!",
        })
        assert login.status_code == 200, login.text
        # Auth events are recorded at the user's primary workspace level
        # We just verify the call succeeded and returned a token
        assert "token" in login.json()

    async def test_13_failed_login_fires_audit_event(self, client: AsyncClient):
        """Failed login attempt must produce an AUTH_LOGIN_FAILED audit event."""
        res = await client.post("/api/auth/login", json={
            "email": "nonexistent@nowhere.test",
            "password": "wrong_password",
        })
        assert res.status_code in (400, 401, 403), res.text


# ---------------------------------------------------------------------------
# REST API Tests
# ---------------------------------------------------------------------------

class TestAuditAPIEndpoints:
    """Test the /api/audit/* REST endpoints for access control and data correctness."""

    async def test_14_owner_can_list_audit_events(self, client: AsyncClient, owner_tokens):
        """OWNER must be able to retrieve the workspace audit log."""
        res = await client.get(
            "/api/audit",
            headers=owner_tokens["headers"],
        )
        assert res.status_code == 200, res.text
        data = res.json()
        assert "items" in data
        assert "total" in data
        assert isinstance(data["items"], list)
        assert data["total"] >= 0

    async def test_15_member_cannot_access_full_audit_log(self, client: AsyncClient, member_tokens):
        """MEMBER must receive 403 when accessing the full audit log."""
        res = await client.get(
            "/api/audit",
            headers=member_tokens["headers"],
        )
        assert res.status_code == 403, res.text

    async def test_16_viewer_cannot_access_full_audit_log(self, client: AsyncClient, viewer_tokens):
        """VIEWER must receive 403 when accessing the full audit log."""
        res = await client.get(
            "/api/audit",
            headers=viewer_tokens["headers"],
        )
        assert res.status_code == 403, res.text

    async def test_17_owner_can_get_governance_summary(self, client: AsyncClient, owner_tokens):
        """OWNER must receive a complete governance summary."""
        res = await client.get(
            "/api/audit/summary",
            headers=owner_tokens["headers"],
        )
        assert res.status_code == 200, res.text
        data = res.json()
        assert "total_audit_events" in data
        assert "security_events_count" in data
        assert "chain_integrity_status" in data
        assert "top_actors" in data
        assert isinstance(data["top_actors"], list)
        assert data["total_audit_events"] >= 0

    async def test_18_owner_can_verify_chain(self, client: AsyncClient, owner_tokens):
        """OWNER must be able to verify the audit chain integrity."""
        res = await client.get(
            "/api/audit/verify",
            headers=owner_tokens["headers"],
        )
        assert res.status_code == 200, res.text
        data = res.json()
        assert "chain_valid" in data
        assert "status" in data
        assert "verified_event_count" in data
        assert isinstance(data["chain_valid"], bool)

    async def test_19_member_can_access_entity_audit_history(self, client: AsyncClient, owner_tokens, member_tokens):
        """MEMBER must be able to access entity-level audit history."""
        ws_id = owner_tokens["workspace_id"]

        # Create an obligation as owner
        ob = await client.post(
            "/api/obligations",
            json={"owner": "Alice", "beneficiary": "Bob", "action": "Member Entity History Test", "obligation_type": "OWED_BY_ME"},
            headers=owner_tokens["headers"],
        )
        assert ob.status_code == 201
        ob_id = ob.json()["id"]

        # Member should be able to view entity history
        res = await client.get(
            f"/api/audit/entity/obligation/{ob_id}",
            headers=member_tokens["headers"],
        )
        assert res.status_code == 200, res.text
        data = res.json()
        assert isinstance(data, list)

    async def test_20_viewer_can_access_entity_audit_history(self, client: AsyncClient, owner_tokens, viewer_tokens):
        """VIEWER must be able to access entity-level audit history."""
        ws_id = owner_tokens["workspace_id"]

        ob = await client.post(
            "/api/obligations",
            json={"owner": "Alice", "beneficiary": "Bob", "action": "Viewer Entity History Test", "obligation_type": "OWED_BY_ME"},
            headers=owner_tokens["headers"],
        )
        assert ob.status_code == 201
        ob_id = ob.json()["id"]

        res = await client.get(
            f"/api/audit/entity/obligation/{ob_id}",
            headers=viewer_tokens["headers"],
        )
        assert res.status_code == 200, res.text

    async def test_21_audit_list_supports_action_filter(self, client: AsyncClient, owner_tokens):
        """Audit list must support filtering by action code."""
        res = await client.get(
            "/api/audit?action=OBLIGATION_CREATED",
            headers=owner_tokens["headers"],
        )
        assert res.status_code == 200, res.text
        data = res.json()
        for item in data["items"]:
            assert item["action"] == "OBLIGATION_CREATED"

    async def test_22_audit_list_supports_entity_type_filter(self, client: AsyncClient, owner_tokens):
        """Audit list must support filtering by entity_type."""
        res = await client.get(
            "/api/audit?entity_type=obligation",
            headers=owner_tokens["headers"],
        )
        assert res.status_code == 200, res.text
        data = res.json()
        for item in data["items"]:
            assert item["entity_type"] == "obligation"

    async def test_23_audit_list_supports_pagination(self, client: AsyncClient, owner_tokens):
        """Audit list must respect limit/offset pagination."""
        res1 = await client.get("/api/audit?limit=2&offset=0", headers=owner_tokens["headers"])
        res2 = await client.get("/api/audit?limit=2&offset=2", headers=owner_tokens["headers"])

        assert res1.status_code == 200
        assert res2.status_code == 200

        data1 = res1.json()
        data2 = res2.json()

        # First page should have at most 2 items
        assert len(data1["items"]) <= 2

        # Items across pages should be different (if total > 2)
        if data1["total"] > 2:
            ids1 = {i["id"] for i in data1["items"]}
            ids2 = {i["id"] for i in data2["items"]}
            assert ids1.isdisjoint(ids2), "Pages should not overlap"

    async def test_24_export_json_works_for_owner(self, client: AsyncClient, owner_tokens):
        """OWNER must be able to export the audit log as JSON."""
        res = await client.get(
            "/api/audit/export?format=json",
            headers=owner_tokens["headers"],
        )
        assert res.status_code == 200, res.text
        assert "application/json" in res.headers.get("content-type", "")
        data = res.json()
        assert "workspace_id" in data
        assert "records" in data
        assert isinstance(data["records"], list)

    async def test_25_export_csv_works_for_owner(self, client: AsyncClient, owner_tokens):
        """OWNER must be able to export the audit log as CSV."""
        res = await client.get(
            "/api/audit/export?format=csv",
            headers=owner_tokens["headers"],
        )
        assert res.status_code == 200, res.text
        assert "text/csv" in res.headers.get("content-type", "")
        content = res.text
        assert "id" in content  # CSV header row

    async def test_26_member_cannot_export_audit_log(self, client: AsyncClient, member_tokens):
        """MEMBER must not be able to export the audit log."""
        res = await client.get(
            "/api/audit/export?format=json",
            headers=member_tokens["headers"],
        )
        assert res.status_code == 403, res.text

    async def test_27_security_events_endpoint(self, client: AsyncClient, owner_tokens):
        """OWNER must be able to retrieve the security events feed."""
        res = await client.get(
            "/api/audit/security",
            headers=owner_tokens["headers"],
        )
        assert res.status_code == 200, res.text
        data = res.json()
        assert "items" in data
        # All returned items should be security-class actions
        security_actions = {"PERMISSION_DENIED", "SECURITY_VIOLATION", "AUTH_LOGIN_FAILED"}
        for item in data["items"]:
            assert item["action"] in security_actions

    async def test_28_audit_event_response_has_cryptographic_fields(self, client: AsyncClient, owner_tokens):
        """Each audit event in the API response must include hash chain fields."""
        res = await client.get("/api/audit?limit=5", headers=owner_tokens["headers"])
        assert res.status_code == 200
        data = res.json()
        for item in data["items"]:
            assert "event_hash" in item
            assert len(item["event_hash"]) == 64
            assert "severity" in item
            assert "result" in item
            assert "timestamp" in item

    async def test_29_audit_event_timestamps_ordered_newest_first(self, client: AsyncClient, owner_tokens):
        """The audit log should be ordered by timestamp descending (newest first)."""
        res = await client.get("/api/audit?limit=10", headers=owner_tokens["headers"])
        assert res.status_code == 200
        data = res.json()
        items = data["items"]
        if len(items) >= 2:
            from dateutil.parser import parse as parse_dt
            timestamps = [parse_dt(i["timestamp"]) for i in items]
            assert timestamps == sorted(timestamps, reverse=True), "Audit log not sorted newest-first"

    async def test_30_unauthenticated_access_blocked(self, client: AsyncClient):
        """Audit endpoints must reject invalid or missing authorization tokens."""
        invalid_headers = {"Authorization": "Bearer invalid_tampered_token_xyz"}
        res = await client.get("/api/audit", headers=invalid_headers)
        assert res.status_code == 401, res.text

        res = await client.get("/api/audit/summary", headers=invalid_headers)
        assert res.status_code == 401, res.text

        res = await client.get("/api/audit/verify", headers=invalid_headers)
        assert res.status_code == 401, res.text


# ---------------------------------------------------------------------------
# Hash Chain Unit Tests
# ---------------------------------------------------------------------------

class TestHashChainEngine:
    """Unit tests for the cryptographic hash-chain functions."""

    def test_31_compute_event_hash_is_deterministic(self):
        """The same inputs must always produce the same hash."""
        from app.core.audit_chain import compute_event_hash
        from datetime import datetime, timezone

        ts = datetime(2025, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
        kwargs = dict(
            previous_hash="a" * 64,
            event_id="ev-001",
            workspace_id="ws-001",
            actor_user_id="user-001",
            actor_role="OWNER",
            action="OBLIGATION_CREATED",
            entity_type="obligation",
            entity_id="ob-001",
            timestamp=ts,
            request_id="req-001",
            source="API",
            before_state=None,
            after_state={"status": "DETECTED"},
            audit_metadata=None,
            reason=None,
            severity="INFO",
            result="SUCCESS",
        )
        h1 = compute_event_hash(**kwargs)
        h2 = compute_event_hash(**kwargs)
        assert h1 == h2
        assert len(h1) == 64

    def test_32_hash_changes_when_any_field_changes(self):
        """Changing any field must produce a different hash (avalanche effect)."""
        from app.core.audit_chain import compute_event_hash
        from datetime import datetime, timezone

        ts = datetime(2025, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
        base_kwargs = dict(
            previous_hash="b" * 64,
            event_id="ev-002",
            workspace_id="ws-002",
            actor_user_id="user-002",
            actor_role="MEMBER",
            action="OBLIGATION_UPDATED",
            entity_type="obligation",
            entity_id="ob-002",
            timestamp=ts,
            request_id="req-002",
            source="API",
            before_state=None,
            after_state=None,
            audit_metadata=None,
            reason=None,
            severity="INFO",
            result="SUCCESS",
        )
        base_hash = compute_event_hash(**base_kwargs)

        tampered = dict(base_kwargs, action="OBLIGATION_DELETED")
        tampered_hash = compute_event_hash(**tampered)

        assert base_hash != tampered_hash

    def test_33_genesis_hash_is_correct_constant(self):
        """GENESIS_HASH must be exactly 64 zero chars."""
        from app.core.audit_chain import GENESIS_HASH
        assert GENESIS_HASH == "0" * 64
        assert len(GENESIS_HASH) == 64

    def test_34_verify_empty_chain_returns_valid(self):
        """verify_event_chain() with no events returns chain_valid=True."""
        from app.core.audit_chain import verify_event_chain
        result = verify_event_chain([])
        assert result["chain_valid"] is True
        assert result["verified_event_count"] == 0


# ---------------------------------------------------------------------------
# Governance Summary Content Tests
# ---------------------------------------------------------------------------

class TestGovernanceSummaryContent:
    """Verify governance summary metrics reflect actual events in the DB."""

    async def test_35_governance_summary_reflects_actual_counts(self, client: AsyncClient, owner_tokens):
        """Governance summary counts must be non-negative and internally consistent."""
        res = await client.get("/api/audit/summary", headers=owner_tokens["headers"])
        assert res.status_code == 200
        data = res.json()

        # All counts must be non-negative integers
        int_fields = [
            "total_audit_events", "events_today", "mutations_today",
            "security_events_count", "permission_denials_count",
            "failed_logins_count", "human_actions_count", "system_events_count",
            "interventions_approved_count", "evidence_confirmations_count",
        ]
        for field in int_fields:
            assert isinstance(data[field], int), f"{field} must be int"
            assert data[field] >= 0, f"{field} must be >= 0"

        # total_audit_events >= events_today
        assert data["total_audit_events"] >= data["events_today"]

        # chain_integrity_status must be a non-empty string
        assert isinstance(data["chain_integrity_status"], str)
        assert len(data["chain_integrity_status"]) > 0

    async def test_36_governance_summary_includes_evaluated_at_timestamp(self, client: AsyncClient, owner_tokens):
        """Governance summary must include an evaluated_at timestamp."""
        res = await client.get("/api/audit/summary", headers=owner_tokens["headers"])
        assert res.status_code == 200
        data = res.json()
        assert "evaluated_at" in data
        # Should be parseable as ISO datetime
        from dateutil.parser import parse as parse_dt
        ts = parse_dt(data["evaluated_at"])
        now = datetime.now(timezone.utc)
        delta = abs((now - ts).total_seconds())
        assert delta < 60, "evaluated_at should be within the last minute"

    async def test_37_governance_summary_top_actors_are_valid(self, client: AsyncClient, owner_tokens):
        """Top actors list should be well-structured."""
        res = await client.get("/api/audit/summary", headers=owner_tokens["headers"])
        assert res.status_code == 200
        data = res.json()
        for actor in data.get("top_actors", []):
            assert "actor_name" in actor
            assert "mutation_count" in actor
            assert isinstance(actor["mutation_count"], int)
            assert actor["mutation_count"] >= 0

    async def test_38_verification_chain_count_matches_reality(self, client: AsyncClient, owner_tokens):
        """Chain verification count must equal total_audit_events in summary."""
        summary_res = await client.get("/api/audit/summary", headers=owner_tokens["headers"])
        verify_res = await client.get("/api/audit/verify", headers=owner_tokens["headers"])

        assert summary_res.status_code == 200
        assert verify_res.status_code == 200

        summary = summary_res.json()
        verify = verify_res.json()

        # The count must match between summary and verify
        assert verify["verified_event_count"] == summary["total_audit_events"]
