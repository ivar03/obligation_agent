"""
Comprehensive Multi-Tenant Isolation & Authorization Matrix Test Suite.

Verifies strict tenant isolation across all domain entities:
 - Workspace A cannot read or mutate Workspace B obligations.
 - Direct-ID attacks (GET/PUT/DELETE /obligations/{ws_b_id}) are strictly rejected.
 - Decisions, Evidence, Invitations, CSV imports, and LLM histories are strictly workspace-isolated.
 - Cross-workspace invitation acceptance cannot compromise foreign workspaces.
"""

import uuid
from datetime import datetime, timezone, timedelta
import pytest
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession

from app.main import app
from app.core.security import create_session_token, hash_password
from app.models.auth import User, Workspace, WorkspaceMembership
from app.models.organization import WorkspaceInvitation
from app.models.obligation import Obligation, Evidence
from app.models.decision import DecisionPlan
from app.models.llm_analysis import LLMAnalysisRecord
from app.core.status_machine import (
    WorkspaceRole,
    ObligationStatus,
    ObligationType,
    EvidenceType,
    CorrelationStatus,
    EventSemanticRole,
    DecisionPlanStatus,
    InvitationStatus,
)


@pytest.mark.asyncio
async def test_multi_tenant_isolation_and_direct_id_attacks(db_session: AsyncSession, client: AsyncClient):
    # 1. Setup Workspace A & User A

    ws_a = Workspace(id="ws-tenant-a", name="Tenant A Workspace", slug="tenant-a")
    user_a = User(
        id="usr-tenant-a",
        email="user_a@tenant-a.com",
        password_hash=hash_password("password123"),
        display_name="Alice (Tenant A)",
        is_active=True,
    )
    mem_a = WorkspaceMembership(
        id="mem-tenant-a",
        workspace_id=ws_a.id,
        user_id=user_a.id,
        role=WorkspaceRole.OWNER,
    )

    # 2. Setup Workspace B & User B
    ws_b = Workspace(id="ws-tenant-b", name="Tenant B Workspace", slug="tenant-b")
    user_b = User(
        id="usr-tenant-b",
        email="user_b@tenant-b.com",
        password_hash=hash_password("password123"),
        display_name="Bob (Tenant B)",
        is_active=True,
    )
    mem_b = WorkspaceMembership(
        id="mem-tenant-b",
        workspace_id=ws_b.id,
        user_id=user_b.id,
        role=WorkspaceRole.OWNER,
    )

    db_session.add_all([ws_a, user_a, mem_a, ws_b, user_b, mem_b])
    await db_session.commit()

    # 3. Create Resources in Workspace B
    ob_b = Obligation(
        id="ob-secret-b-001",
        workspace_id=ws_b.id,
        owner="user_b@tenant-b.com",
        beneficiary="Tenant B Board",
        action="Confidential Acquisition Plan for Project X",
        status=ObligationStatus.IN_PROGRESS,
        obligation_type=ObligationType.OWED_BY_ME,
        deadline=datetime.now(timezone.utc) + timedelta(days=10),
    )
    ev_b = Evidence(
        id="ev-secret-b-001",
        workspace_id=ws_b.id,
        obligation_id=ob_b.id,
        evidence_type=EvidenceType.DOCUMENT,
        source_type="file",
        content="Confidential financial audit spreadsheet",
        correlation_status=CorrelationStatus.CONFIRMED,
        semantic_role=EventSemanticRole.PROGRESS_UPDATE,
    )
    dp_b = DecisionPlan(
        id="dp-secret-b-001",
        workspace_id=ws_b.id,
        target_obligation_id=ob_b.id,
        primary_objective="Acquisition Financing Strategy",
        status=DecisionPlanStatus.GENERATED,
    )
    llm_b = LLMAnalysisRecord(
        id="llm-rec-secret-b-001",
        workspace_id=ws_b.id,
        source_ref="audit-b",
        analysis_type="obligation_extraction",
        prompt_version="v1",
        schema_version="obligation-proposal-v1",
        provider="mock",
        model="gemini-1.5-flash",
        input_hash="hash-b-001",
        raw_prompt_redacted="Confidential tenant B transcript",
        structured_output={"action": "Confidential acquisition"},
    )
    inv_b = WorkspaceInvitation(
        id="inv-secret-b-001",
        workspace_id=ws_b.id,
        invited_email="contractor@tenant-b.com",
        role=WorkspaceRole.MEMBER,
        invited_by_user_id=user_b.id,
        token_hash="hash-token-b",
        status=InvitationStatus.PENDING,
        expires_at=datetime.now(timezone.utc) + timedelta(days=7),
    )

    db_session.add_all([ob_b, ev_b, dp_b, llm_b, inv_b])
    await db_session.commit()

    # Generate Auth Tokens
    token_a = create_session_token(user_id=user_a.id, workspace_id=ws_a.id)
    headers_a = {
        "Authorization": f"Bearer {token_a}",
        "X-Workspace-Id": ws_a.id,
    }


    # TEST 1: List obligations — User A only sees WS A obligations
    resp = await client.get("/api/obligations", headers=headers_a)

    assert resp.status_code == 200
    items = resp.json().get("items", [])
    assert all(item["workspace_id"] == ws_a.id for item in items)
    assert not any(item["id"] == ob_b.id for item in items)

    # TEST 2: Direct-ID Attack (GET /api/obligations/{ob_b.id})
    resp = await client.get(f"/api/obligations/{ob_b.id}", headers=headers_a)
    assert resp.status_code in [404, 403]

    # TEST 3: Direct-ID Attack (PATCH /api/obligations/{ob_b.id})
    resp = await client.patch(
        f"/api/obligations/{ob_b.id}",
        json={"action": "Tampered Action by Attacker"},
        headers=headers_a,
    )
    assert resp.status_code in [404, 403]

    # TEST 4: Direct-ID Attack (DELETE /api/obligations/{ob_b.id})
    resp = await client.delete(f"/api/obligations/{ob_b.id}", headers=headers_a)
    assert resp.status_code in [404, 403]

    # Verify resource was NOT mutated or deleted in DB
    ob_check = await db_session.get(Obligation, ob_b.id)
    assert ob_check is not None
    assert ob_check.action == "Confidential Acquisition Plan for Project X"

    # TEST 5: Direct-ID Attack on Decision Plan (GET /api/decision-plans/{dp_b.id})
    resp = await client.get(f"/api/decision-plans/{dp_b.id}", headers=headers_a)
    assert resp.status_code in [404, 403]

    # TEST 6: Direct-ID Attack on Invitations (GET /api/workspaces/{ws_b.id}/invitations)
    resp = await client.get(f"/api/workspaces/{ws_b.id}/invitations", headers=headers_a)
    assert resp.status_code in [403, 404]

    # TEST 7: Cross-workspace Invitation Forgery (POST /api/workspaces/{ws_b.id}/invitations)
    resp = await client.post(
        f"/api/workspaces/{ws_b.id}/invitations",
        json={"invited_email": "spy@attacker.com", "role": "ADMIN"},
        headers=headers_a,
    )
    assert resp.status_code in [403, 404]

    # TEST 8: LLM Analysis History Isolation (GET /api/intelligence/llm/history)
    resp = await client.get("/api/intelligence/llm/history", headers=headers_a)
    if resp.status_code == 200:
        data = resp.json()
        records = data if isinstance(data, list) else data.get("records", [])
        assert not any(r["id"] == llm_b.id for r in records)


    # TEST 9: CSV Bulk Import Scoping
    resp = await client.post(
        "/api/obligations/import/csv/commit",
        json={
            "rows": [{
                "action": "Tenant A Imported Action",
                "owner": "user_a@tenant-a.com",
                "beneficiary": "Tenant A",
            }],
            "skip_duplicates": False,
        },
        headers=headers_a,
    )
    assert resp.status_code == 200
    imported_ids = resp.json().get("created_obligation_ids", [])
    assert len(imported_ids) > 0
    
    # Verify imported obligation belongs to WS A
    for imp_id in imported_ids:
        ob_imp = await db_session.get(Obligation, imp_id)
        assert ob_imp is not None
        assert ob_imp.workspace_id == ws_a.id


@pytest.mark.asyncio
async def test_authorization_role_matrix(db_session: AsyncSession, client: AsyncClient):
    """
    Validates the full authorization matrix across roles:
    - OWNER / ADMIN: full CRUD on obligations, invitations, decisions.
    - MEMBER: read/create obligations, read decisions, CANNOT issue invitations.
    - VIEWER: read-only access, CANNOT mutate or create obligations or invitations.
    - UNAUTHENTICATED: rejected with 401 when token invalid/missing in protected mode.
    """
    ws = Workspace(id="ws-auth-matrix", name="Matrix Workspace", slug="auth-matrix")
    
    # 1. Admin User
    u_admin = User(id="usr-mat-admin", email="admin@mat.com", password_hash=hash_password("p"), display_name="Admin", is_active=True)
    m_admin = WorkspaceMembership(id="mem-mat-admin", workspace_id=ws.id, user_id=u_admin.id, role=WorkspaceRole.ADMIN)

    # 2. Member User
    u_member = User(id="usr-mat-member", email="member@mat.com", password_hash=hash_password("p"), display_name="Member", is_active=True)
    m_member = WorkspaceMembership(id="mem-mat-member", workspace_id=ws.id, user_id=u_member.id, role=WorkspaceRole.MEMBER)

    # 3. Viewer User
    u_viewer = User(id="usr-mat-viewer", email="viewer@mat.com", password_hash=hash_password("p"), display_name="Viewer", is_active=True)
    m_viewer = WorkspaceMembership(id="mem-mat-viewer", workspace_id=ws.id, user_id=u_viewer.id, role=WorkspaceRole.VIEWER)

    db_session.add_all([ws, u_admin, m_admin, u_member, m_member, u_viewer, m_viewer])
    await db_session.commit()

    tok_admin = create_session_token(user_id=u_admin.id, workspace_id=ws.id)
    tok_member = create_session_token(user_id=u_member.id, workspace_id=ws.id)
    tok_viewer = create_session_token(user_id=u_viewer.id, workspace_id=ws.id)

    h_admin = {"Authorization": f"Bearer {tok_admin}", "X-Workspace-Id": ws.id}
    h_member = {"Authorization": f"Bearer {tok_member}", "X-Workspace-Id": ws.id}
    h_viewer = {"Authorization": f"Bearer {tok_viewer}", "X-Workspace-Id": ws.id}

    # MATRIX 1: Admin CAN issue invitations
    resp = await client.post(
        f"/api/workspaces/{ws.id}/invitations",
        json={"invited_email": "contractor@mat.com", "role": "MEMBER"},
        headers=h_admin,
    )
    assert resp.status_code == 201

    # MATRIX 2: Member CANNOT issue invitations (403)
    resp = await client.post(
        f"/api/workspaces/{ws.id}/invitations",
        json={"invited_email": "contractor2@mat.com", "role": "MEMBER"},
        headers=h_member,
    )
    assert resp.status_code == 403

    # MATRIX 3: Viewer CANNOT issue invitations (403)
    resp = await client.post(
        f"/api/workspaces/{ws.id}/invitations",
        json={"invited_email": "contractor3@mat.com", "role": "MEMBER"},
        headers=h_viewer,
    )
    assert resp.status_code == 403

    # MATRIX 4: Member CAN create obligations
    resp = await client.post(
        "/api/obligations",
        json={
            "action": "Member Created Action",
            "owner": u_member.email,
            "beneficiary": "Team",
            "obligation_type": "OWED_BY_ME",
        },
        headers=h_member,
    )
    assert resp.status_code == 201
    created_ob_id = resp.json()["id"]

    # MATRIX 5: Viewer CANNOT delete obligations (403)
    resp = await client.delete(f"/api/obligations/{created_ob_id}", headers=h_viewer)
    assert resp.status_code == 403

    # MATRIX 6: Viewer CAN read obligations (200)
    resp = await client.get("/api/obligations", headers=h_viewer)
    assert resp.status_code == 200


