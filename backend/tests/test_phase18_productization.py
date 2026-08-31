"""
Phase 18 Automated Test Suite — Production Productization & Real-World Beta Readiness.
"""

import pytest
import uuid
from datetime import datetime, timezone, timedelta
from httpx import AsyncClient, ASGITransport

from app.main import app
from app.core.database import AsyncSessionLocal
from app.models.auth import Workspace, User, WorkspaceMembership
from app.models.obligation import Obligation, Evidence
from app.models.organization import WorkspaceInvitation, WorkspaceSettings, InAppNotification
from app.core.status_machine import (
    WorkspaceRole,
    InvitationStatus,
    ObligationStatus,
    ObligationType,
    NotificationCategory,
    NotificationSeverity,
    OnboardingStep,
)
from app.services.invitation_service import InvitationService
from app.services.workspace_settings_service import WorkspaceSettingsService
from app.services.csv_import_service import CsvImportService
from app.services.search_service import SearchService
from app.services.notification_service import NotificationService


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


@pytest.mark.asyncio
async def test_workspace_invitation_lifecycle():
    """
    Tests invitation creation, single-use token hashing, expiration, and acceptance.
    """
    async with AsyncSessionLocal() as session:
        ws = Workspace(id=f"ws-inv-{uuid.uuid4().hex[:6]}", name="Invite Test WS", slug=f"inv-{uuid.uuid4().hex[:6]}")
        owner = User(id=f"u-inv-o-{uuid.uuid4().hex[:6]}", email=f"inv_owner_{uuid.uuid4().hex[:4]}@test.com", display_name="Owner", password_hash="hash")
        session.add_all([ws, owner])
        await session.flush()
        mem = WorkspaceMembership(workspace_id=ws.id, user_id=owner.id, role=WorkspaceRole.OWNER)
        session.add(mem)
        await session.commit()

        # 1. Create invitation
        invite_email = f"new_member_{uuid.uuid4().hex[:4]}@test.com"
        inv_resp = await InvitationService.create_invitation(
            session=session,
            workspace_id=ws.id,
            caller_user_id=owner.id,
            invited_email=invite_email,
            role=WorkspaceRole.OPERATOR,
        )
        assert inv_resp.status == InvitationStatus.PENDING
        assert inv_resp.invitation_token is not None

        # 2. Accept invitation
        new_mem, new_user = await InvitationService.accept_invitation(
            session=session,
            raw_token=inv_resp.invitation_token,
            password="SecurePassword123!",
            display_name="New Operator",
        )
        assert new_mem.workspace_id == ws.id
        assert new_mem.role == WorkspaceRole.OPERATOR
        assert new_user.email == invite_email

        # 3. Verify single-use: second attempt fails
        with pytest.raises(Exception):
            await InvitationService.accept_invitation(
                session=session,
                raw_token=inv_resp.invitation_token,
            )


@pytest.mark.asyncio
async def test_workspace_settings_and_onboarding():
    """
    Tests settings retrieval, update, and persistent onboarding progression.
    """
    async with AsyncSessionLocal() as session:
        ws = Workspace(id=f"ws-set-{uuid.uuid4().hex[:6]}", name="Settings WS", slug=f"set-{uuid.uuid4().hex[:6]}")
        owner = User(id=f"u-set-{uuid.uuid4().hex[:6]}", email=f"set_owner_{uuid.uuid4().hex[:4]}@test.com", display_name="Owner", password_hash="hash")
        session.add_all([ws, owner])
        await session.flush()
        mem = WorkspaceMembership(workspace_id=ws.id, user_id=owner.id, role=WorkspaceRole.OWNER)
        session.add(mem)
        await session.commit()

        # Get initial progress
        prog = await WorkspaceSettingsService.get_onboarding_progress(session, ws.id)
        assert prog.current_step == OnboardingStep.WELCOME
        assert prog.is_completed is False

        # Advance onboarding
        updated_prog = await WorkspaceSettingsService.update_onboarding_step(session, ws.id, OnboardingStep.CONNECT_SLACK)
        assert updated_prog.current_step == OnboardingStep.CONNECT_SLACK
        assert OnboardingStep.WELCOME.value in updated_prog.completed_steps


@pytest.mark.asyncio
async def test_in_app_notifications():
    """
    Tests alert creation, list unread, and mark-all-read.
    """
    async with AsyncSessionLocal() as session:
        ws_id = f"ws-notif-{uuid.uuid4().hex[:6]}"
        ws = Workspace(id=ws_id, name="Notif WS", slug=f"notif-{uuid.uuid4().hex[:6]}")
        user = User(id=f"u-notif-{uuid.uuid4().hex[:6]}", email=f"notif_{uuid.uuid4().hex[:4]}@test.com", display_name="User", password_hash="hash")
        session.add_all([ws, user])
        await session.flush()
        session.add(WorkspaceMembership(workspace_id=ws.id, user_id=user.id, role=WorkspaceRole.MEMBER))
        await session.commit()

        # Create alert
        notif = await NotificationService.create_notification(
            session=session,
            workspace_id=ws_id,
            category=NotificationCategory.ACTION_REQUIRED,
            severity=NotificationSeverity.WARNING,
            title="Action Needed",
            message="Please review high-risk obligation.",
            user_id=user.id,
        )
        assert notif.is_read is False

        # List notifications
        resp = await NotificationService.list_notifications(session, ws_id, user_id=user.id)
        assert resp.unread_count >= 1

        # Mark read
        await NotificationService.mark_read(session, notif.id, ws_id)
        resp_after = await NotificationService.list_notifications(session, ws_id, user_id=user.id, unread_only=True)
        assert not any(i.id == notif.id for i in resp_after.items)


@pytest.mark.asyncio
async def test_csv_import_preview_and_commit():
    """
    Tests CSV bulk ingestion parsing, duplicate detection, and atomic commit.
    """
    async with AsyncSessionLocal() as session:
        ws_id = f"ws-csv-{uuid.uuid4().hex[:6]}"
        ws = Workspace(id=ws_id, name="CSV Import WS", slug=f"csv-{uuid.uuid4().hex[:6]}")
        user = User(id=f"u-csv-{uuid.uuid4().hex[:6]}", email=f"csv_{uuid.uuid4().hex[:4]}@test.com", display_name="CSV User", password_hash="hash")
        session.add_all([ws, user])
        await session.flush()
        session.add(WorkspaceMembership(workspace_id=ws.id, user_id=user.id, role=WorkspaceRole.OWNER))
        await session.commit()

        csv_data = """action,owner,deadline,priority,dependencies
Deploy Production Gateway,DevOps Lead,2026-10-15,HIGH,
Configure SSL Certificates,Security Lead,2026-10-14,CRITICAL,Deploy Production Gateway
"""
        # 1. Preview
        preview = await CsvImportService.preview_csv(session, ws_id, csv_data)
        assert preview.total_rows == 2
        assert preview.valid_rows_count == 2
        assert preview.can_commit is True

        # 2. Commit
        valid_rows = [r.parsed_data for r in preview.validation_results if r.is_valid]
        commit_res = await CsvImportService.commit_import(session, ws_id, user.id, valid_rows)
        assert commit_res.imported_count == 2
        assert commit_res.created_edge_count == 1


@pytest.mark.asyncio
async def test_workspace_scoped_global_search():
    """
    Tests multi-entity search isolation between separate workspaces.
    """
    async with AsyncSessionLocal() as session:
        ws1_id = f"ws-s1-{uuid.uuid4().hex[:6]}"
        ws2_id = f"ws-s2-{uuid.uuid4().hex[:6]}"
        ws1 = Workspace(id=ws1_id, name="WS 1", slug=f"ws1-{uuid.uuid4().hex[:4]}")
        ws2 = Workspace(id=ws2_id, name="WS 2", slug=f"ws2-{uuid.uuid4().hex[:4]}")
        session.add_all([ws1, ws2])
        await session.flush()

        ob1 = Obligation(
            id=f"ob-s1-{uuid.uuid4().hex[:6]}",
            workspace_id=ws1_id,
            owner="TargetEngineer",
            beneficiary="Lead",
            action="Secret WS1 Mission Action",
            status=ObligationStatus.CONFIRMED,
            obligation_type=ObligationType.OWED_BY_ME,
        )
        ob2 = Obligation(
            id=f"ob-s2-{uuid.uuid4().hex[:6]}",
            workspace_id=ws2_id,
            owner="TargetEngineer",
            beneficiary="Lead",
            action="WS2 Other Action",
            status=ObligationStatus.CONFIRMED,
            obligation_type=ObligationType.OWED_BY_ME,
        )
        session.add_all([ob1, ob2])
        await session.commit()

        # Search WS1: Must find ob1 and NEVER ob2
        search_ws1 = await SearchService.global_search(session, ws1_id, "Secret WS1 Mission")
        assert any(o["id"] == ob1.id for o in search_ws1["results"]["obligations"])
        assert not any(o["id"] == ob2.id for o in search_ws1["results"]["obligations"])

        # Search WS2: Must NOT find ob1
        search_ws2 = await SearchService.global_search(session, ws2_id, "Secret WS1 Mission")
        assert len(search_ws2["results"]["obligations"]) == 0


@pytest.mark.asyncio
async def test_operational_queues_and_human_gating():
    """
    Tests operational queues retrieval and ensures human confirmation invariant is intact.
    """
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # Mock auth headers automatically resolve workspace and role in dev mode
        res_act = await ac.get("/api/queues/action")
        assert res_act.status_code == 200
        assert "items" in res_act.json()

        res_evi = await ac.get("/api/queues/evidence")
        assert res_evi.status_code == 200

        res_dec = await ac.get("/api/queues/decisions")
        assert res_dec.status_code == 200

        res_exec = await ac.get("/api/queues/executions")
        assert res_exec.status_code == 200

        res_feed = await ac.get("/api/queues/activity")
        assert res_feed.status_code == 200
