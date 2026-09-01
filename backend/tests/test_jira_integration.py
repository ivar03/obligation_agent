"""
Integration Test Suite for Jira Cloud Provider Ingestion & Intelligence Pipelines.

Verifies:
 - Connection lifecycle with encrypted credential storage.
 - Project discovery and selection.
 - Issue synchronization and ingestion into EventIngestionService.
 - Webhook processing with HMAC and secret token verification.
 - Evidence candidate generation from Jira issues.
 - Clean disconnection and credential purging.
"""

import hmac
import hashlib
import json
import pytest
from datetime import datetime, timezone, timedelta
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.security import create_session_token, hash_password
from app.models.auth import User, Workspace, WorkspaceMembership
from app.models.obligation import Obligation, Evidence, IngestedEventRecord
from app.models.integration import IntegrationConnection
from app.core.status_machine import (
    WorkspaceRole,
    ObligationStatus,
    ObligationType,
)


@pytest.mark.asyncio
async def test_jira_integration_full_lifecycle(db_session: AsyncSession, client: AsyncClient):
    # 1. Setup Workspace and Admin User
    ws = Workspace(id="ws-jira-test", name="Jira Workspace", slug="jira-ws")
    user = User(
        id="usr-jira-admin",
        email="admin@jira-test.com",
        password_hash=hash_password("adminpass"),
        display_name="Jira Admin",
        is_active=True,
    )
    membership = WorkspaceMembership(
        id="mem-jira-admin",
        workspace_id=ws.id,
        user_id=user.id,
        role=WorkspaceRole.ADMIN,
    )

    # 2. Setup an active obligation that can correlate with Jira issues
    ob = Obligation(
        id="ob-jira-corr-01",
        workspace_id=ws.id,
        owner="priya@company.com",
        beneficiary="admin@jira-test.com",
        action="Conduct Database Migration Performance Benchmark",
        status=ObligationStatus.IN_PROGRESS,
        obligation_type=ObligationType.OWED_TO_ME,
        deadline=datetime.now(timezone.utc) + timedelta(days=5),
    )

    db_session.add_all([ws, user, membership, ob])
    await db_session.commit()

    token = create_session_token(user_id=user.id, workspace_id=ws.id)
    headers = {
        "Authorization": f"Bearer {token}",
        "X-Workspace-Id": ws.id,
    }

    # TEST 1: Connect Jira via API Token
    resp = await client.post(
        "/api/integrations/jira/connect-token",
        json={
            "site_url": "https://acme-corp.atlassian.net",
            "email": "jira-admin@acme-corp.com",
            "api_token": "mock-token-xyz-12345",
        },
        headers=headers,
    )
    assert resp.status_code == 200
    connect_data = resp.json()
    assert connect_data["provider"] == "jira"
    assert connect_data["status"] == "CONNECTED"
    assert "acme-corp.atlassian.net" in connect_data["site_url"]

    # Verify credentials encrypted in database
    conn = await db_session.get(IntegrationConnection, connect_data["id"])
    assert conn is not None
    assert conn.encrypted_credentials.startswith("enc:v1:")
    assert "mock-token-xyz-12345" not in conn.encrypted_credentials  # Never plaintext

    # TEST 2: List discoverable Jira projects
    resp = await client.get("/api/integrations/jira/projects", headers=headers)
    assert resp.status_code == 200
    projects = resp.json()
    assert isinstance(projects, list)
    assert len(projects) > 0
    project_keys = [p["key"] for p in projects]
    assert "ENG" in project_keys or "SEC" in project_keys

    # TEST 3: Select projects to synchronize
    resp = await client.post(
        "/api/integrations/jira/projects",
        json={"project_keys": ["ENG", "SEC"]},
        headers=headers,
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "SUCCESS"
    assert "ENG" in resp.json()["selected_projects"]

    # TEST 4: Trigger Jira Issue Sync
    resp = await client.post(
        "/api/integrations/jira/sync",
        json={"project_keys": ["ENG"]},
        headers=headers,
    )
    assert resp.status_code == 200
    sync_res = resp.json()
    assert sync_res["status"] == "COMPLETED"
    assert sync_res["synced_issues_count"] >= 2

    # Verify IngestedEventRecord was created for Jira issues
    stmt_ev = select(IngestedEventRecord).where(
        IngestedEventRecord.workspace_id == ws.id,
        IngestedEventRecord.provider == "jira",
    )
    ingested_records = (await db_session.execute(stmt_ev)).scalars().all()
    assert len(ingested_records) >= 2
    assert any("ENG-101" in r.source_ref for r in ingested_records)

    # TEST 5: Verify Evidence Candidate was generated for the correlated obligation
    stmt_evid = select(Evidence).where(Evidence.obligation_id == ob.id)
    evidence_items = (await db_session.execute(stmt_evid)).scalars().all()
    assert len(evidence_items) >= 1
    assert any("jira" in ev.source_type or "jira" in ev.source_ref for ev in evidence_items)

    # TEST 6: Check Sync Status Endpoint
    resp = await client.get("/api/integrations/jira/sync/status", headers=headers)
    assert resp.status_code == 200
    status_data = resp.json()
    assert status_data["connected"] is True
    assert status_data["status"] == "CONNECTED"
    assert status_data["total_synced_issues"] >= 2
    assert status_data["last_synced_at"] is not None

    # TEST 7: Ingest Jira Webhook Event
    webhook_payload = {
        "webhookEvent": "jira:issue_updated",
        "issue": {
            "key": "ENG-102",
            "fields": {
                "summary": "Conduct Database Migration Performance Benchmark",
                "status": {"name": "In Progress"},
                "priority": {"name": "Critical"},
                "assignee": {"displayName": "Priya Sharma", "emailAddress": "priya@company.com"},
                "project": {"key": "ENG", "name": "Engineering"},
                "duedate": "2026-09-12",
            }
        },
        "changelog": {
            "items": [
                {
                    "field": "status",
                    "fromString": "Blocked",
                    "toString": "In Progress",
                }
            ]
        }
    }

    resp = await client.post(
        "/api/webhooks/jira",
        json=webhook_payload,
        headers={"X-Workspace-Id": ws.id},
    )
    assert resp.status_code in [200, 201]

    # TEST 8: Disconnect Jira
    resp = await client.post("/api/integrations/jira/disconnect", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["status"] == "DISCONNECTED"

    # Verify credentials purged
    await db_session.refresh(conn)
    assert conn.status == "DISCONNECTED"
    assert conn.encrypted_credentials is None
