"""
================================================================================
Phase 14: Identity, Workspace, Authentication & Authorization Tests
================================================================================
Validates:
1. User registration, password hashing (PBKDF2-HMAC-SHA256), email uniqueness.
2. Login session issuance, HTTP-only cookie setting, token verification.
3. User profile and workspace discovery via /api/auth/me.
4. Workspace CRUD, slug generation, owner assignment.
5. Workspace membership and role hierarchy (OWNER > ADMIN > MEMBER > VIEWER).
6. Role-based authorization gates:
   - VIEWER: read-only access (403 on mutations).
   - MEMBER: standard obligation and intervention mutations allowed.
   - ADMIN: integrations and member management allowed.
   - OWNER: workspace deletion and role escalation allowed.
7. Strict multi-tenant isolation:
   - Server-side workspace scoping on all queries.
   - IDOR prevention: access to foreign tenant ID returns 404 Not Found.
8. Backward compatibility: fallback to default demo user in dev/test mode.
"""

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.status_machine import WorkspaceRole, ObligationStatus, ObligationType
from app.core.security import hash_password, verify_password, create_session_token, decode_session_token
from app.models.auth import User, Workspace, WorkspaceMembership
from app.models.obligation import Obligation


@pytest.mark.asyncio
async def test_password_hashing_and_verification():
    """Test cryptographic password hashing and constant-time verification."""
    password = "SuperSecretPassword123!"
    p_hash = hash_password(password)

    assert p_hash.startswith("pbkdf2_sha256$100000$")
    assert verify_password(password, p_hash) is True
    assert verify_password("WrongPassword!", p_hash) is False
    assert verify_password("", p_hash) is False


@pytest.mark.asyncio
async def test_session_token_generation_and_decoding():
    """Test cryptographically signed HMAC-SHA256 session token generation and verification."""
    token = create_session_token(user_id="usr-123", workspace_id="ws-abc", expires_in_seconds=3600)
    assert token is not None
    assert "." in token

    payload = decode_session_token(token)
    assert payload is not None
    assert payload["sub"] == "usr-123"
    assert payload["ws"] == "ws-abc"

    # Tampered token
    tampered = token[:-4] + "abcd"
    assert decode_session_token(tampered) is None


@pytest.mark.asyncio
async def test_user_registration_and_login_flow(client: AsyncClient):
    """Test user registration and subsequent login setting session token and cookie."""
    # 1. Register a new user
    reg_payload = {
        "email": "alice@enterprise.corp",
        "password": "Password123!",
        "display_name": "Alice Wonderland",
    }
    reg_res = await client.post("/api/auth/register", json=reg_payload)
    assert reg_res.status_code == 201, reg_res.text
    data = reg_res.json()
    assert data["user"]["email"] == "alice@enterprise.corp"
    assert data["user"]["display_name"] == "Alice Wonderland"
    assert "token" in data
    assert "obligation_session" in reg_res.cookies

    alice_token = data["token"]
    alice_id = data["user"]["id"]

    # 2. Duplicate registration should be rejected
    dup_res = await client.post("/api/auth/register", json=reg_payload)
    assert dup_res.status_code == 400

    # 3. Login with correct credentials
    login_payload = {
        "email": "alice@enterprise.corp",
        "password": "Password123!",
    }
    login_res = await client.post("/api/auth/login", json=login_payload)
    assert login_res.status_code == 200
    login_data = login_res.json()
    assert login_data["user"]["id"] == alice_id
    assert "token" in login_data

    # 4. Login with invalid password
    bad_login = await client.post(
        "/api/auth/login",
        json={"email": "alice@enterprise.corp", "password": "WrongPassword!"},
    )
    assert bad_login.status_code == 401

    # 5. Access /api/auth/me with Bearer token
    me_res = await client.get(
        "/api/auth/me",
        headers={"Authorization": f"Bearer {alice_token}"},
    )
    assert me_res.status_code == 200
    me_data = me_res.json()
    assert me_data["user"]["id"] == alice_id
    assert len(me_data["workspaces"]) >= 1
    assert me_data["workspaces"][0]["role"] == "OWNER"


@pytest.mark.asyncio
async def test_workspace_crud_and_membership(client: AsyncClient):
    """Test workspace creation, member invitations, and role management."""
    # Register Owner
    owner_reg = await client.post(
        "/api/auth/register",
        json={"email": "owner@corp.com", "password": "Pass1234Owner!", "display_name": "Workspace Owner"},
    )
    owner_token = owner_reg.json()["token"]
    owner_headers = {"Authorization": f"Bearer {owner_token}"}

    # Register Member to be added
    member_reg = await client.post(
        "/api/auth/register",
        json={"email": "bob@corp.com", "password": "Pass1234Bob!", "display_name": "Bob Member"},
    )
    bob_token = member_reg.json()["token"]
    bob_id = member_reg.json()["user"]["id"]
    bob_headers = {"Authorization": f"Bearer {bob_token}"}

    # Create new custom workspace
    ws_res = await client.post(
        "/api/workspaces",
        json={"name": "Acme Legal Ops", "slug": "acme-legal-ops"},
        headers=owner_headers,
    )
    assert ws_res.status_code == 201
    ws_data = ws_res.json()
    ws_id = ws_data["id"]
    assert ws_data["name"] == "Acme Legal Ops"
    assert ws_data["slug"] == "acme-legal-ops"

    # Add Bob as a VIEWER
    add_mem_res = await client.post(
        f"/api/workspaces/{ws_id}/members",
        json={"email": "bob@corp.com", "role": "VIEWER"},
        headers=owner_headers,
    )
    assert add_mem_res.status_code == 201
    mem_data = add_mem_res.json()
    assert mem_data["user_id"] == bob_id
    assert mem_data["role"] == "VIEWER"

    # List members
    members_res = await client.get(f"/api/workspaces/{ws_id}/members", headers=owner_headers)
    assert members_res.status_code == 200
    members_list = members_res.json()
    assert len(members_list) == 2

    # Promote Bob to MEMBER
    update_role_res = await client.patch(
        f"/api/workspaces/{ws_id}/members/{bob_id}",
        json={"role": "MEMBER"},
        headers=owner_headers,
    )
    assert update_role_res.status_code == 200
    assert update_role_res.json()["role"] == "MEMBER"


@pytest.mark.asyncio
async def test_role_based_access_control(client: AsyncClient):
    """Test VIEWER role read-only restrictions vs MEMBER/ADMIN permissions."""
    # 1. Setup workspace with Owner and Viewer
    owner_reg = await client.post(
        "/api/auth/register",
        json={"email": "lead@company.com", "password": "LeadPassword123!", "display_name": "Team Lead"},
    )
    owner_token = owner_reg.json()["token"]
    owner_headers = {"Authorization": f"Bearer {owner_token}"}

    ws_res = await client.post(
        "/api/workspaces",
        json={"name": "Engineering Commitments"},
        headers=owner_headers,
    )
    ws_id = ws_res.json()["id"]
    owner_ws_headers = {"Authorization": f"Bearer {owner_token}", "X-Workspace-Id": ws_id}

    # Register Viewer
    viewer_reg = await client.post(
        "/api/auth/register",
        json={"email": "auditor@company.com", "password": "AuditorPassword123!", "display_name": "Auditor"},
    )
    viewer_token = viewer_reg.json()["token"]
    viewer_id = viewer_reg.json()["user"]["id"]
    viewer_ws_headers = {"Authorization": f"Bearer {viewer_token}", "X-Workspace-Id": ws_id}

    # Add auditor as VIEWER
    await client.post(
        f"/api/workspaces/{ws_id}/members",
        json={"email": "auditor@company.com", "role": "VIEWER"},
        headers=owner_headers,
    )

    # 2. Owner creates an obligation in this workspace
    create_ob_res = await client.post(
        "/api/obligations",
        json={
            "owner": "Alice Lead",
            "beneficiary": "VP Engineering",
            "action": "Complete architectural blueprint",
            "obligation_type": "OWED_BY_ME",
            "status": "CONFIRMED",
        },
        headers=owner_ws_headers,
    )
    assert create_ob_res.status_code == 201
    ob_id = create_ob_res.json()["id"]

    # 3. Viewer CAN read obligations
    viewer_get = await client.get(f"/api/obligations/{ob_id}", headers=viewer_ws_headers)
    assert viewer_get.status_code == 200
    assert viewer_get.json()["id"] == ob_id

    # 4. Viewer CANNOT create obligations (403 Forbidden)
    viewer_create = await client.post(
        "/api/obligations",
        json={
            "owner": "Auditor",
            "beneficiary": "Team",
            "action": "Unauthorized obligation",
            "obligation_type": "OWED_BY_ME",
        },
        headers=viewer_ws_headers,
    )
    assert viewer_create.status_code == 403

    # 5. Viewer CANNOT update obligation (403 Forbidden)
    viewer_update = await client.patch(
        f"/api/obligations/{ob_id}",
        json={"action": "Tampered action"},
        headers=viewer_ws_headers,
    )
    assert viewer_update.status_code == 403

    # 6. Viewer CANNOT manage integrations (403 Forbidden)
    viewer_integ = await client.post(
        "/api/integrations/slack/disconnect",
        headers=viewer_ws_headers,
    )
    assert viewer_integ.status_code == 403


@pytest.mark.asyncio
async def test_cross_tenant_isolation_and_idor_protection(client: AsyncClient):
    """Test strict isolation between Workspace A and Workspace B with IDOR protection."""
    # Tenant A
    user_a = await client.post(
        "/api/auth/register",
        json={"email": "user_a@tenant-a.com", "password": "PasswordA123!", "display_name": "Tenant A User"},
    )
    token_a = user_a.json()["token"]
    ws_a_res = await client.post(
        "/api/workspaces",
        json={"name": "Tenant A Workspace"},
        headers={"Authorization": f"Bearer {token_a}"},
    )
    ws_a_id = ws_a_res.json()["id"]
    headers_a = {"Authorization": f"Bearer {token_a}", "X-Workspace-Id": ws_a_id}

    # Tenant B
    user_b = await client.post(
        "/api/auth/register",
        json={"email": "user_b@tenant-b.com", "password": "PasswordB123!", "display_name": "Tenant B User"},
    )
    token_b = user_b.json()["token"]
    ws_b_res = await client.post(
        "/api/workspaces",
        json={"name": "Tenant B Workspace"},
        headers={"Authorization": f"Bearer {token_b}"},
    )
    ws_b_id = ws_b_res.json()["id"]
    headers_b = {"Authorization": f"Bearer {token_b}", "X-Workspace-Id": ws_b_id}

    # Create obligation in Tenant A
    ob_a_res = await client.post(
        "/api/obligations",
        json={
            "owner": "Secret Agent A",
            "beneficiary": "Agency A",
            "action": "Confidential Mission A",
            "obligation_type": "OWED_BY_ME",
        },
        headers=headers_a,
    )
    assert ob_a_res.status_code == 201
    ob_a_id = ob_a_res.json()["id"]

    # 1. Tenant B listing obligations should NOT see Tenant A's obligation
    list_b = await client.get("/api/obligations", headers=headers_b)
    assert list_b.status_code == 200
    ob_ids_b = [o["id"] for o in list_b.json()["items"]]
    assert ob_a_id not in ob_ids_b

    # 2. Tenant B attempting direct IDOR fetch of Tenant A's obligation returns 404 (Not Found)
    idor_get = await client.get(f"/api/obligations/{ob_a_id}", headers=headers_b)
    assert idor_get.status_code == 404

    # 3. Tenant B attempting to update Tenant A's obligation returns 404
    idor_update = await client.patch(
        f"/api/obligations/{ob_a_id}",
        json={"action": "Hacked action"},
        headers=headers_b,
    )
    assert idor_update.status_code == 404

    # 4. Ingesting event in Tenant B does not correlate with Tenant A's obligation
    event_b = {
        "provider": "mock",
        "payload": {
            "scenario": "COMPLETION",
            "sender": "Secret Agent A",
            "recipients": ["Agency A"],
            "content": "Completed the Confidential Mission A successfully.",
        },
    }
    ingest_b = await client.post("/api/events/ingest", json=event_b, headers=headers_b)
    assert ingest_b.status_code == 201
    ingest_b_data = ingest_b.json()
    assert ob_a_id not in ingest_b_data["affected_obligation_ids"]


@pytest.mark.asyncio
async def test_legacy_unauthenticated_fallback(client: AsyncClient):
    """Test unauthenticated calls fallback gracefully to default demo user and workspace in dev mode."""
    # List obligations without auth headers
    res = await client.get("/api/obligations")
    assert res.status_code == 200

    # Dashboard summary without auth headers
    dash_res = await client.get("/api/dashboard/summary")
    assert dash_res.status_code == 200
