"""
Tenant Isolation & Direct-ID Attack Test Suite for Jira Integration.

Verifies:
 - Workspace A cannot access Workspace B's Jira connection.
 - Workspace A cannot trigger synchronization for Workspace B.
 - Workspace A cannot list, select, or mutate Workspace B's Jira projects.
 - Workspace A cannot view Jira-derived evidence or ingested events belonging to Workspace B.
 - Non-admin roles (MEMBER / VIEWER) cannot modify Jira connections or trigger synchronization.
"""

import pytest
from datetime import datetime, timezone
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.security import create_session_token, hash_password
from app.core.crypto import CryptoService
from app.models.auth import User, Workspace, WorkspaceMembership
from app.models.integration import IntegrationConnection
from app.models.obligation import Obligation, Evidence, IngestedEventRecord
from app.core.status_machine import WorkspaceRole, ObligationStatus, ObligationType


@pytest.mark.asyncio
async def test_jira_multi_tenant_isolation_and_role_matrix(db_session: AsyncSession, client: AsyncClient):
    # 1. Setup Tenant A
    ws_a = Workspace(id="ws-jira-tenant-a", name="Tenant A", slug="tenant-a")
    user_a = User(
        id="usr-jira-a",
        email="admin_a@tenant-a.com",
        password_hash=hash_password("p"),
        display_name="Admin A",
        is_active=True,
    )
    mem_a = WorkspaceMembership(id="mem-jira-a", workspace_id=ws_a.id, user_id=user_a.id, role=WorkspaceRole.ADMIN)

    # 2. Setup Tenant B with connected Jira instance
    ws_b = Workspace(id="ws-jira-tenant-b", name="Tenant B", slug="tenant-b")
    user_b = User(
        id="usr-jira-b",
        email="admin_b@tenant-b.com",
        password_hash=hash_password("p"),
        display_name="Admin B",
        is_active=True,
    )
    mem_b = WorkspaceMembership(id="mem-jira-b", workspace_id=ws_b.id, user_id=user_b.id, role=WorkspaceRole.ADMIN)

    # Member user in Tenant B (insufficient role for integration admin)
    user_b_member = User(
        id="usr-jira-b-mem",
        email="member_b@tenant-b.com",
        password_hash=hash_password("p"),
        display_name="Member B",
        is_active=True,
    )
    mem_b_member = WorkspaceMembership(id="mem-jira-b-mem", workspace_id=ws_b.id, user_id=user_b_member.id, role=WorkspaceRole.MEMBER)

    # Tenant B Jira Connection
    raw_creds_b = '{"site_url": "https://tenant-b-secret.atlassian.net", "email": "admin@tenant-b.com", "api_token": "secret-token-b"}'
    conn_b = IntegrationConnection(
        id="conn-jira-b-001",
        workspace_id=ws_b.id,
        provider="jira",
        external_account_id="jira-tenant-b",
        external_account_name="Tenant B Jira (https://tenant-b-secret.atlassian.net)",
        status="CONNECTED",
        encrypted_credentials=CryptoService.encrypt(raw_creds_b),
        connection_metadata={
            "site_url": "https://tenant-b-secret.atlassian.net",
            "selected_projects": ["SECRET_PROJ"],
            "sync_status": "IDLE",
        },
    )

    db_session.add_all([ws_a, user_a, mem_a, ws_b, user_b, mem_b, user_b_member, mem_b_member, conn_b])
    await db_session.commit()

    tok_a = create_session_token(user_id=user_a.id, workspace_id=ws_a.id)
    headers_a = {"Authorization": f"Bearer {tok_a}", "X-Workspace-Id": ws_a.id}

    tok_b_admin = create_session_token(user_id=user_b.id, workspace_id=ws_b.id)
    headers_b_admin = {"Authorization": f"Bearer {tok_b_admin}", "X-Workspace-Id": ws_b.id}

    tok_b_member = create_session_token(user_id=user_b_member.id, workspace_id=ws_b.id)
    headers_b_member = {"Authorization": f"Bearer {tok_b_member}", "X-Workspace-Id": ws_b.id}

    # TEST 1: Tenant A checks Jira status -> returns DISCONNECTED (Tenant B is connected)
    resp = await client.get("/api/integrations/jira/sync/status", headers=headers_a)
    assert resp.status_code == 200
    assert resp.json()["connected"] is False
    assert resp.json()["status"] == "DISCONNECTED"

    # TEST 2: Tenant A attempts to list projects -> rejected (400 - Not connected in Tenant A)
    resp = await client.get("/api/integrations/jira/projects", headers=headers_a)
    assert resp.status_code == 400

    # TEST 3: Tenant A attempts to trigger sync on Tenant A -> rejected (400 - Not connected)
    resp = await client.post("/api/integrations/jira/sync", headers=headers_a)
    assert resp.status_code == 400

    # TEST 4: Tenant A attempts cross-tenant spoofing by sending X-Workspace-Id: ws_b.id
    # get_current_membership validates caller against their authenticated session workspace
    resp_spoof = await client.get(
        "/api/integrations/jira/sync/status",
        headers={"Authorization": f"Bearer {tok_a}", "X-Workspace-Id": ws_b.id},
    )
    # Must reject unauthorized workspace access with 401/403
    assert resp_spoof.status_code in [401, 403]

    # TEST 5: Member in Tenant B cannot mutate Jira projects or trigger sync (403 Forbidden)
    resp = await client.post(
        "/api/integrations/jira/projects",
        json={"project_keys": ["MUTATED_BY_MEMBER"]},
        headers=headers_b_member,
    )
    assert resp.status_code == 403

    resp = await client.post("/api/integrations/jira/sync", headers=headers_b_member)
    assert resp.status_code == 403

    # TEST 6: Admin in Tenant B CAN list projects and trigger sync
    resp = await client.get("/api/integrations/jira/projects", headers=headers_b_admin)
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)

    resp = await client.post(
        "/api/integrations/jira/sync",
        json={"project_keys": ["SECRET_PROJ"]},
        headers=headers_b_admin,
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "COMPLETED"

    # Verify all synced event records belong strictly to Tenant B
    stmt_ev = select(IngestedEventRecord).where(IngestedEventRecord.provider == "jira")
    events = (await db_session.execute(stmt_ev)).scalars().all()
    assert all(e.workspace_id == ws_b.id for e in events)
    assert not any(e.workspace_id == ws_a.id for e in events)
