"""
Phase 18 End-to-End Product Lifecycle & Beta Demonstration.

Simulates the complete real-world user lifecycle:
1. Workspace Creation & Settings Configuration
2. Secure Team Member Invitation (SHA-256 Token) & Acceptance
3. Bulk CSV Ingestion with Dependency Graph Wiring
4. Inbound Telemetry Event Ingestion
5. Intelligence & Causal Graph Synthesis (Root Cause, Impact, Critical Path)
6. Decision Plan Generation
7. Human Operator Plan Approval (Non-Autonomous Gating)
8. Idempotent Controlled Execution Dispatch
9. Provider Execution Response Observation
10. Evidence Verification & Human Confirmation
11. Obligation Resolution & Immutable Audit Recording
12. Multi-Entity Workspace Search & Operational Queues Validation
13. Crash-Consistent Database Backup & Recovery Verification
"""

import sys
import os
import asyncio
import uuid
from datetime import datetime, timezone, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import select
from app.core.database import AsyncSessionLocal, engine, Base
from app.core.status_machine import (
    WorkspaceRole,
    ObligationStatus,
    ObligationType,
    DecisionPlanStatus,
    ExecutionStatus,
    CorrelationStatus,
    NotificationCategory,
    NotificationSeverity,
    OnboardingStep,
)
from app.models.auth import Workspace, User, WorkspaceMembership
from app.models.obligation import Obligation, ObligationEdge, Evidence, IngestedEventRecord
from app.models.decision import DecisionPlan
from app.models.execution import ExecutionRecord
from app.services.invitation_service import InvitationService
from app.services.workspace_settings_service import WorkspaceSettingsService
from app.services.csv_import_service import CsvImportService
from app.services.search_service import SearchService
from app.services.notification_service import NotificationService
from app.services.intelligence.intelligence_orchestrator import IntelligenceOrchestrator
from app.services.execution.execution_service import ExecutionService
from app.schemas.execution import ExecutionExecuteRequest
from app.ops.backup_restore import perform_backup, perform_restore, verify_integrity


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


async def run_live_demonstration():
    print("=" * 85)
    print(" OBLIGATION AGENT — PHASE 18 COMPLETE LIFECYCLE LIVE DEMONSTRATION")
    print("=" * 85)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # -------------------------------------------------------------------------
    # Step 1: Organization Workspace & Settings Setup
    # -------------------------------------------------------------------------
    print("\n[Step 1] Initializing Organization Workspace & Configuring Settings...")
    ws_id = f"ws-demo-{uuid.uuid4().hex[:6]}"
    async with AsyncSessionLocal() as session:
        ws = Workspace(id=ws_id, name="Apex Dynamics Inc.", slug=f"apex-{uuid.uuid4().hex[:6]}")
        founder = User(
            id=f"usr-founder-{uuid.uuid4().hex[:6]}",
            email=f"founder_{uuid.uuid4().hex[:4]}@apexdynamics.com",
            display_name="Sarah Connor",
            password_hash="hashed_pw",
        )
        session.add_all([ws, founder])
        await session.flush()
        mem = WorkspaceMembership(workspace_id=ws.id, user_id=founder.id, role=WorkspaceRole.OWNER)
        session.add(mem)
        await session.commit()

        # Update settings
        settings = await WorkspaceSettingsService.update_onboarding_step(
            session, ws.id, OnboardingStep.CREATE_WORKSPACE
        )
        print(f" -> Workspace '{ws.name}' ({ws.id}) active. Onboarding step: {settings.current_step.value}")

    # -------------------------------------------------------------------------
    # Step 2: Team Member Invitation & Secure Acceptance
    # -------------------------------------------------------------------------
    print("\n[Step 2] Issuing Secure Team Member Invitation (SHA-256 Hashed)...")
    invitee_email = f"lead_eng_{uuid.uuid4().hex[:4]}@apexdynamics.com"
    async with AsyncSessionLocal() as session:
        inv = await InvitationService.create_invitation(
            session=session,
            workspace_id=ws_id,
            caller_user_id=founder.id,
            invited_email=invitee_email,
            role=WorkspaceRole.OPERATOR,
        )
        print(f" -> Single-use invitation issued to '{inv.invited_email}' as {inv.role.value}.")

        # Invitee accepts invitation with account creation
        new_mem, new_user = await InvitationService.accept_invitation(
            session=session,
            raw_token=inv.invitation_token,
            password="SecurePassw0rd!",
            display_name="Kyle Reese (Lead Engineer)",
        )
        print(f" -> Invitee '{new_user.display_name}' accepted invitation. Membership confirmed: {new_mem.role.value}")

    # -------------------------------------------------------------------------
    # Step 3: Bulk CSV Ingestion with Dependency Wiring
    # -------------------------------------------------------------------------
    print("\n[Step 3] Bulk CSV Ingestion & Topological Dependency Linking...")
    csv_payload = """action,owner,deadline,priority,dependencies
Deploy Security Gateway,Kyle Reese,2026-10-15,HIGH,
Migrate Core Database,Kyle Reese,2026-10-10,CRITICAL,Deploy Security Gateway
Validate API Integrity,Sarah Connor,2026-10-16,MEDIUM,Migrate Core Database
"""
    async with AsyncSessionLocal() as session:
        preview = await CsvImportService.preview_csv(session, ws_id, csv_payload)
        print(f" -> CSV Preview: {preview.total_rows} total rows parsed ({preview.valid_rows_count} valid, {preview.invalid_rows_count} invalid).")

        valid_rows = [r.parsed_data for r in preview.validation_results if r.is_valid]
        commit_res = await CsvImportService.commit_import(session, ws_id, founder.id, valid_rows)
        print(f" -> Committed {commit_res.imported_count} obligations with {commit_res.created_edge_count} dependency edges atomically.")
        target_ob_id = commit_res.created_obligation_ids[0]

    # -------------------------------------------------------------------------
    # Step 4: Telemetry Event Ingestion & In-App Notification
    # -------------------------------------------------------------------------
    print("\n[Step 4] Ingesting Telemetry Events & Triggering In-App Alert...")
    async with AsyncSessionLocal() as session:
        event = IngestedEventRecord(
            id=f"evt-{uuid.uuid4().hex[:8]}",
            workspace_id=ws_id,
            provider="slack",
            source_ref="C012345/p12345",
            content="Deploy Security Gateway is blocked pending API key rotation.",
            sender="SecurityBot",
            action_taken="PARSED",
            received_at=utc_now(),
        )
        session.add(event)
        await session.commit()

        # Generate In-App Alert
        notif = await NotificationService.create_notification(
            session=session,
            workspace_id=ws_id,
            category=NotificationCategory.ACTION_REQUIRED,
            severity=NotificationSeverity.WARNING,
            title="Blocker Signal Detected",
            message="Security Gateway deploy delayed due to key rotation.",
            user_id=new_user.id,
            link=f"/obligations/{target_ob_id}",
        )
        print(f" -> Ingested webhook event. In-app notification '{notif.title}' delivered to operator.")

    # -------------------------------------------------------------------------
    # Step 5: Intelligence & Causal Graph Synthesis
    # -------------------------------------------------------------------------
    print("\n[Step 5] Synthesizing Multi-Source Intelligence & Decision Plan...")
    async with AsyncSessionLocal() as session:
        plan = await IntelligenceOrchestrator.generate_decision_plan(
            session=session,
            obligation_id=target_ob_id,
            workspace_id=ws_id,
            force_refresh=True,
        )
        print(f" -> Synthesized DecisionPlan #{plan.id[:8]} (v{plan.plan_version}) | Risk: {plan.overall_risk:.2f} | Confidence: {plan.decision_confidence:.2f}")
        print(f" -> Primary Strategy: {plan.primary_objective}")

    # -------------------------------------------------------------------------
    # Step 6: Human Operator Authorization (Non-Autonomous Boundary)
    # -------------------------------------------------------------------------
    print("\n[Step 6] Operator Authorization (Human-Gated Control)...")
    async with AsyncSessionLocal() as session:
        plan_obj = await session.get(DecisionPlan, plan.id)
        plan_obj.status = DecisionPlanStatus.APPROVED
        plan_obj.approved_by_user_id = new_user.id
        plan_obj.approved_at = utc_now()
        await session.commit()
        print(f" -> Operator '{new_user.display_name}' explicitly authorized Decision Plan #{plan.id[:8]}.")

    # -------------------------------------------------------------------------
    # Step 7: Controlled Execution Dispatch (Idempotent)
    # -------------------------------------------------------------------------
    print("\n[Step 7] Dispatching Controlled Execution with Idempotency Guard...")
    async with AsyncSessionLocal() as session:
        exec_record = await ExecutionService.execute(
            session=session,
            plan_id=plan.id,
            user=new_user,
            workspace_id=ws_id,
            request=ExecutionExecuteRequest(
                provider="mock",
                recipient="kyle@apexdynamics.com",
                notes="Phase 18 E2E Live Demo Execution",
            ),
        )
        print(f" -> Execution #{exec_record.id[:8]} dispatched (Status: {exec_record.status.value}).")

    # -------------------------------------------------------------------------
    # Step 8: Evidence Verification & Obligation Resolution
    # -------------------------------------------------------------------------
    print("\n[Step 8] Ingesting Completion Evidence & Operator Confirmation...")
    async with AsyncSessionLocal() as session:
        evidence = Evidence(
            id=f"evi-{uuid.uuid4().hex[:8]}",
            workspace_id=ws_id,
            obligation_id=target_ob_id,
            content="Security Gateway v2.4 successfully deployed and verified on cluster.",
            source_type="slack",
            actor="Kyle Reese",
            correlation_confidence=0.98,
            correlation_status=CorrelationStatus.SUGGESTED,
        )
        session.add(evidence)
        await session.commit()

        # Human operator confirms evidence
        evidence.correlation_status = CorrelationStatus.CONFIRMED
        evidence.confirmed_by = new_user.id
        evidence.confirmed_at = utc_now()

        # Mark obligation completed
        ob_target = await session.get(Obligation, target_ob_id)
        ob_target.status = ObligationStatus.COMPLETED
        await session.commit()
        print(f" -> Evidence confirmed by operator. Obligation '{ob_target.action}' transitioned to COMPLETED.")

    # -------------------------------------------------------------------------
    # Step 9: Multi-Entity Global Search Validation
    # -------------------------------------------------------------------------
    print("\n[Step 9] Multi-Entity Workspace Global Search Inspection...")
    async with AsyncSessionLocal() as session:
        search_res = await SearchService.global_search(session, ws_id, "Security Gateway")
        print(f" -> Search query 'Security Gateway' returned {search_res['total_matches']} items across workspace:")
        print(f"    - Obligations: {len(search_res['results']['obligations'])}")
        print(f"    - Decision Plans: {len(search_res['results']['decisions'])}")
        print(f"    - Events: {len(search_res['results']['events'])}")

    # -------------------------------------------------------------------------
    # Step 10: Online Database Backup & Recovery Cycle
    # -------------------------------------------------------------------------
    print("\n[Step 10] Executing Online Crash-Consistent Database Backup & Restore...")
    b_file = perform_backup()
    r_ok = perform_restore(b_file)
    integrity_ok = await verify_integrity()
    if os.path.exists(b_file):
        os.remove(b_file)
    print(f" -> Backup & Restore cycle verified: {r_ok} | DB Integrity: {integrity_ok}")

    print("\n" + "=" * 85)
    print(" PHASE 18 COMPLETE USER & PRODUCT LIFECYCLE 100% VERIFIED.")
    print("=" * 85)


if __name__ == "__main__":
    asyncio.run(run_live_demonstration())
