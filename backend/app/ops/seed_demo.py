"""
Obligation Agent — Real-World Demo Environment Seed.

Populates a rich, realistic, domain-grounded demo environment:
 - Demo User & Team Member Accounts
 - Demo Workspace & Isolated Scopes
 - Healthy, At-Risk, Blocked, and Chained Obligations
 - Dependency Graph Edges
 - Correlated Evidence & Ingested Events
 - Decision Center Proposals & Simulated Plans
 - Semantic LLM Analysis Records (deterministic mock analysis)

Safe for development/staging; guards against accidental production invocation.
"""

import os
import sys
import uuid
import asyncio
from datetime import datetime, timedelta, timezone
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import AsyncSessionLocal, engine, Base
from app.core.security import hash_password
from app.core.status_machine import (
    WorkspaceRole,
    ObligationStatus,
    ObligationType,
    EdgeType,
    EvidenceType,
    CorrelationStatus,
    EventSemanticRole,
    DecisionPlanStatus,
)
from app.core.intervention_status import (
    InterventionStatus,
    InterventionType,
)

from app.models.auth import User, Workspace, WorkspaceMembership
from app.models.obligation import (
    Obligation,
    ObligationEdge,
    Evidence,
    Intervention,
    IngestedEventRecord,
    ReconciliationRecord,
)
from app.models.decision import DecisionPlan
from app.models.llm_analysis import LLMAnalysisRecord
from app.models.integration import IntegrationConnection
from app.models.operational_audit import OperationalAuditRecord
from app.models.audit import AuditEvent
from app.schemas.obligation import ExternalEvent
from app.services.event_ingestion_service import EventIngestionService
from app.services.reconciliation_service import ReconciliationService
from app.services.operational_audit_service import OperationalAuditService
from app.services.audit_service import AuditService
from app.core.logging import logger, setup_logging


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


async def seed_demo_environment(force_production: bool = False) -> dict:
    """
    Executes a clean, idempotent demo seed into the database.
    """
    setup_logging()

    if settings.is_production() and not force_production:
        logger.error("Refusing to seed demo environment in production without --force-production.")
        raise RuntimeError("Demo seed is forbidden in production environment without explicit override.")

    logger.info("Initializing database schema for demo environment...")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    demo_email = os.getenv("DEMO_USER_EMAIL", "demo@obligation.local").strip().lower()
    demo_password = os.getenv("DEMO_USER_PASSWORD", "demo1234")
    demo_workspace_name = os.getenv("DEMO_WORKSPACE_NAME", "Demo Workspace")
    demo_workspace_id = os.getenv("DEMO_WORKSPACE_ID", "ws-default")
    demo_user_id = os.getenv("DEMO_USER_ID", "usr-default")

    logger.info(f"Seeding demo workspace '{demo_workspace_name}' ({demo_workspace_id}) for '{demo_email}'...")

    async with AsyncSessionLocal() as session:
        now = utc_now()

        # 1. Clean existing records for this workspace
        await session.execute(delete(OperationalAuditRecord).where(OperationalAuditRecord.workspace_id == demo_workspace_id))
        await session.execute(delete(AuditEvent).where(AuditEvent.workspace_id == demo_workspace_id))
        await session.execute(delete(ReconciliationRecord).where(ReconciliationRecord.workspace_id == demo_workspace_id))
        await session.execute(delete(IngestedEventRecord).where(IngestedEventRecord.workspace_id == demo_workspace_id))
        await session.execute(delete(IntegrationConnection).where(IntegrationConnection.workspace_id == demo_workspace_id))
        await session.execute(delete(DecisionPlan).where(DecisionPlan.workspace_id == demo_workspace_id))
        await session.execute(delete(LLMAnalysisRecord).where(LLMAnalysisRecord.workspace_id == demo_workspace_id))
        await session.execute(delete(Intervention).where(Intervention.workspace_id == demo_workspace_id))
        await session.execute(delete(Evidence).where(Evidence.workspace_id == demo_workspace_id))
        await session.execute(delete(ObligationEdge).where(ObligationEdge.workspace_id == demo_workspace_id))
        await session.execute(delete(Obligation).where(Obligation.workspace_id == demo_workspace_id))
        await session.execute(delete(WorkspaceMembership).where(WorkspaceMembership.workspace_id == demo_workspace_id))
        await session.commit()

        # 2. Workspace & Users
        ws_stmt = select(Workspace).where(Workspace.id == demo_workspace_id)
        ws = (await session.execute(ws_stmt)).scalar_one_or_none()
        if not ws:
            ws = Workspace(
                id=demo_workspace_id,
                name=demo_workspace_name,
                slug="demo-workspace",
            )
            session.add(ws)

        # Primary Demo User (Owner)
        user_stmt = select(User).where(User.id == demo_user_id)
        demo_user = (await session.execute(user_stmt)).scalar_one_or_none()
        if not demo_user:
            demo_user = User(
                id=demo_user_id,
                email=demo_email,
                password_hash=hash_password(demo_password),
                display_name="Demo Operator",
                is_active=True,
            )
            session.add(demo_user)
        else:
            demo_user.email = demo_email
            demo_user.password_hash = hash_password(demo_password)

        # Secondary Team Member User
        priya_stmt = select(User).where(User.id == "usr-priya")
        priya_user = (await session.execute(priya_stmt)).scalar_one_or_none()
        if not priya_user:
            priya_user = User(
                id="usr-priya",
                email="priya@company.com",
                password_hash=hash_password("priya1234"),
                display_name="Priya Sharma (Tech Lead)",
                is_active=True,
            )
            session.add(priya_user)

        await session.flush()

        # Workspace Memberships
        mem_demo = WorkspaceMembership(
            id=f"mem-{uuid.uuid4().hex[:8]}",
            workspace_id=demo_workspace_id,
            user_id=demo_user.id,
            role=WorkspaceRole.OWNER,
        )
        mem_priya = WorkspaceMembership(
            id=f"mem-{uuid.uuid4().hex[:8]}",
            workspace_id=demo_workspace_id,
            user_id=priya_user.id,
            role=WorkspaceRole.MEMBER,
        )
        session.add_all([mem_demo, mem_priya])
        await session.flush()

        # 3. Obligations Dataset
        # Healthy Obligation
        ob_healthy = Obligation(
            id="ob-demo-healthy",
            workspace_id=demo_workspace_id,
            owner=demo_email,
            beneficiary="Engineering Team",
            action="Deliver v2 REST API Technical Specifications",
            deadline=now + timedelta(days=5),
            status=ObligationStatus.IN_PROGRESS,
            obligation_type=ObligationType.OWED_BY_ME,
            confidence={"overall": 0.98, "owner": 1.0, "action": 0.98, "deadline": 0.95},
            source_ref="Engineering RFC #104",
        )

        # At-Risk Obligation (Deadline approaching)
        ob_at_risk = Obligation(
            id="ob-demo-at-risk",
            workspace_id=demo_workspace_id,
            owner=demo_email,
            beneficiary="Security & Compliance Board",
            action="Submit SOC2 Type II Access Audit Package",
            deadline=now + timedelta(hours=14),
            status=ObligationStatus.IN_PROGRESS,
            obligation_type=ObligationType.OWED_BY_ME,
            confidence={"overall": 0.95, "owner": 0.98, "action": 0.95, "deadline": 0.92},
            source_ref="Security Compliance Jira Ticket",
        )

        # Upstream Prerequisite (Overdue -> Blocker)
        ob_upstream = Obligation(
            id="ob-demo-upstream",
            workspace_id=demo_workspace_id,
            owner="priya@company.com",
            beneficiary=demo_email,
            action="Provide Staging Database Benchmark Results",
            deadline=now - timedelta(days=1),
            status=ObligationStatus.OVERDUE,
            obligation_type=ObligationType.OWED_TO_ME,
            confidence={"overall": 0.96, "owner": 0.98, "action": 0.96, "deadline": 0.90},
            source_ref="Slack #dev-infra",
        )

        # Blocked Downstream Obligation
        ob_blocked = Obligation(
            id="ob-demo-blocked",
            workspace_id=demo_workspace_id,
            owner=demo_email,
            beneficiary="Executive Leadership",
            action="Finalize Infrastructure Migration Plan",
            deadline=now + timedelta(days=2),
            status=ObligationStatus.BLOCKED,
            block_reason={
                "blocked": True,
                "blocked_by": [{
                    "obligation_id": ob_upstream.id,
                    "owner": "priya@company.com",
                    "action": "Provide Staging Database Benchmark Results",
                    "status": "OVERDUE",
                    "reason": "Upstream benchmark metrics required to size migration targets.",
                }]
            },
            obligation_type=ObligationType.OWED_BY_ME,
            confidence={"overall": 0.94, "owner": 0.98, "action": 0.94, "deadline": 0.90},
            source_ref="Quarterly Planning Roadmap",
        )

        # Subsequent Production Release (Pending)
        ob_downstream = Obligation(
            id="ob-demo-downstream",
            workspace_id=demo_workspace_id,
            owner=demo_email,
            beneficiary="All Customers",
            action="Execute Zero-Downtime Production Cutover",
            deadline=now + timedelta(days=7),
            status=ObligationStatus.CONFIRMED,
            obligation_type=ObligationType.OWED_BY_ME,
            confidence={"overall": 0.90, "owner": 0.95, "action": 0.90, "deadline": 0.85},
            source_ref="Release Calendar",
        )

        session.add_all([ob_healthy, ob_at_risk, ob_upstream, ob_blocked, ob_downstream])
        await session.flush()

        # 4. Dependency Graph Edges
        edge_1 = ObligationEdge(
            id=f"edge-{uuid.uuid4().hex[:8]}",
            workspace_id=demo_workspace_id,
            from_obligation_id=ob_blocked.id,
            to_obligation_id=ob_upstream.id,
            edge_type=EdgeType.DEPENDS_ON,
        )
        edge_2 = ObligationEdge(
            id=f"edge-{uuid.uuid4().hex[:8]}",
            workspace_id=demo_workspace_id,
            from_obligation_id=ob_downstream.id,
            to_obligation_id=ob_blocked.id,
            edge_type=EdgeType.DEPENDS_ON,
        )
        session.add_all([edge_1, edge_2])
        await session.flush()

        # 5. Continuous Event Ingestion (Populates Activity Center & Correlated Evidence)
        event_slack = ExternalEvent(
            source_type="slack",
            source_ref="slack-msg-7721",
            sender="priya@company.com",
            recipients=[demo_email],
            content="Priya Sharma: 'Benchmark suite timed out on RDS read replicas. Staging database benchmark metrics will be delayed by 24h.'",
            timestamp=now - timedelta(hours=3),
        )
        await EventIngestionService.ingest_normalized_event(
            session=session,
            event=event_slack,
            provider_name="slack",
            raw_payload={"channel": "dev-infra", "user": "priya", "ts": "1725230400.001"},
            workspace_id=demo_workspace_id,
        )

        event_github = ExternalEvent(
            source_type="github",
            source_ref="gh-pr-4819",
            sender="tech-lead@company.com",
            recipients=["engineering-team@company.com"],
            content="PR #42 'Added OpenAPI schema specification for v2 endpoints and data contracts' merged to main.",
            timestamp=now - timedelta(hours=6),
        )
        await EventIngestionService.ingest_normalized_event(
            session=session,
            event=event_github,
            provider_name="direct",
            raw_payload={"repo": "api-gateway", "pr": 42, "merged": True},
            workspace_id=demo_workspace_id,
        )

        event_calendar = ExternalEvent(
            source_type="google_calendar",
            source_ref="cal-event-9910",
            sender="scheduler@company.com",
            recipients=[demo_email, "priya@company.com"],
            content="Calendar Event: 'Architecture Review & Infrastructure Migration Sync' scheduled with Executive Leadership.",
            timestamp=now - timedelta(hours=1),
        )
        await EventIngestionService.ingest_normalized_event(
            session=session,
            event=event_calendar,
            provider_name="google_calendar",
            raw_payload={"summary": "Architecture Sync", "status": "confirmed"},
            workspace_id=demo_workspace_id,
        )

        event_gmail = ExternalEvent(
            source_type="gmail",
            source_ref="gmail-msg-3312",
            sender="auditor@compliance.org",
            recipients=[demo_email],
            content="Compliance Audit Notice: 'Please confirm submission of SOC2 Type II Access Audit package by EOD.'",
            timestamp=now - timedelta(hours=2),
        )
        await EventIngestionService.ingest_normalized_event(
            session=session,
            event=event_gmail,
            provider_name="gmail",
            raw_payload={"subject": "SOC2 Submission Notice", "from": "auditor@compliance.org"},
            workspace_id=demo_workspace_id,
        )

        # 6. Cross-Provider Reconciliation Evaluation (Populates Reconciliation Tab)
        await ReconciliationService.reconcile_workspace(session, demo_workspace_id)

        # 7. Integration Connections Status
        conn_slack = IntegrationConnection(
            id=f"conn-{uuid.uuid4().hex[:8]}",
            workspace_id=demo_workspace_id,
            provider="slack",
            external_account_id="T01928374",
            external_account_name="Engineering Core Workspace",
            status="CONNECTED",
            scopes=["channels:history", "chat:write", "users:read"],
            connection_metadata={"webhook_url": "https://hooks.slack.com/services/DEMO/WEBHOOK/123", "bot_user_id": "U099182"},
        )
        conn_jira = IntegrationConnection(
            id=f"conn-{uuid.uuid4().hex[:8]}",
            workspace_id=demo_workspace_id,
            provider="jira",
            external_account_id="jira-cloud-instance",
            external_account_name="https://acme-demo.atlassian.net",
            status="CONNECTED",
            scopes=["read:jira-work", "write:jira-work"],
            connection_metadata={"site_url": "https://acme-demo.atlassian.net", "email": demo_email, "selected_projects": ["ENG", "INFRA"]},
        )
        session.add_all([conn_slack, conn_jira])
        await session.flush()

        # 8. Decision Center Plan
        dp_migration = DecisionPlan(
            id="dp-demo-migration-01",
            workspace_id=demo_workspace_id,
            target_obligation_id=ob_blocked.id,
            primary_objective="Resolve Migration Plan Dependency Blocker",
            overall_urgency="HIGH",
            overall_risk=0.88,
            decision_confidence=0.92,
            recommended_actions={
                "strategy_id": "strat-001",
                "strategy_name": "Grant temporary benchmark cluster access to lead engineer",
                "target_obligation_id": ob_upstream.id,
                "target_owner": "Priya Sharma",
                "strategy_type": "EXPEDITE_PREREQUISITE",
                "action_summary": "Follow up with Priya Sharma to expedite benchmark results.",
            },
            key_risks=["Migration delay will cascade to customer release calendar"],
            human_decisions_required=[
                {
                    "decision_type": "APPROVE_STRATEGY",
                    "reason": "Expedite staging benchmark prerequisite",
                    "affected_obligation_id": ob_upstream.id,
                    "consequence_of_decision": "Unblocks infrastructure migration roadmap",
                }
            ],
            status=DecisionPlanStatus.GENERATED,
        )
        session.add(dp_migration)

        # 9. Mock Semantic LLM Analysis Records (For /intelligence tab)
        llm_rec_1 = LLMAnalysisRecord(
            id=f"llm-rec-{uuid.uuid4().hex[:8]}",
            workspace_id=demo_workspace_id,
            source_ref="demo-init",
            analysis_type="obligation_extraction",
            prompt_version="obligation_extraction:v1",
            schema_version="obligation-proposal-v1",
            provider="mock",
            model="gemini-1.5-flash",
            input_hash="demo-input-hash-001",
            raw_prompt_redacted="I will send the final security audit report to the Compliance Board by tomorrow afternoon.",
            structured_output={
                "action": "Send final security audit report",
                "owner": demo_email,
                "beneficiary": "Compliance Board",
                "deadline": (now + timedelta(days=1)).isoformat(),
                "confidence": 0.95,
            },
            confidence=0.95,
            validation_status="VALID",
            grounding_status="GROUNDED",
            latency_ms=185.0,
        )
        session.add(llm_rec_1)

        # 10. Operational Audit Logging (Populates Operation Audit Explorer with SHA-256 Hash Chain)
        await OperationalAuditService.log_event(
            session=session,
            workspace_id=demo_workspace_id,
            event_type="WORKSPACE_PROVISIONED",
            action=f"Provisioned demo workspace '{demo_workspace_name}'",
            severity="INFO",
            actor_type="USER",
            actor_id=demo_user.id,
            resource_type="Workspace",
            resource_id=demo_workspace_id,
            result="SUCCESS",
            metadata={"slug": "demo-workspace", "owner_email": demo_email},
        )
        await OperationalAuditService.log_event(
            session=session,
            workspace_id=demo_workspace_id,
            event_type="OBLIGATIONS_INITIALIZED",
            action="Provisioned canonical demo obligations dataset",
            severity="INFO",
            actor_type="SYSTEM",
            actor_id="system-seed",
            resource_type="ObligationBatch",
            resource_id=f"batch-{uuid.uuid4().hex[:6]}",
            result="SUCCESS",
            metadata={"obligations_count": 5, "edges_count": 2},
        )
        await OperationalAuditService.log_event(
            session=session,
            workspace_id=demo_workspace_id,
            event_type="CROSS_PROVIDER_RECONCILIATION_EVALUATED",
            action="Evaluated multi-source evidence contradictions & consistency",
            severity="INFO",
            actor_type="SYSTEM",
            actor_id="engine-reconciliation",
            resource_type="ReconciliationRecord",
            resource_id="rec-auto-seed",
            result="SUCCESS",
            metadata={"workspace_id": demo_workspace_id, "evaluated_obligations": 5},
        )
        await OperationalAuditService.log_event(
            session=session,
            workspace_id=demo_workspace_id,
            event_type="INTEGRATIONS_CONFIGURED",
            action="Connected Slack and Jira provider adapters",
            severity="INFO",
            actor_type="USER",
            actor_id=demo_user.id,
            resource_type="IntegrationConnection",
            resource_id="conn-slack-jira",
            result="SUCCESS",
            metadata={"providers": ["slack", "jira"]},
        )

        await session.commit()

        logger.info("Demo environment seeded successfully.")
        return {
            "demo_user_email": demo_email,
            "demo_workspace_name": demo_workspace_name,
            "demo_workspace_id": demo_workspace_id,
            "obligations_count": 5,
            "dependencies_count": 2,
            "ingested_events_count": 4,
            "decision_plans_count": 1,
            "operational_audit_records_count": 4,
        }


if __name__ == "__main__":
    force = "--force-production" in sys.argv
    res = asyncio.run(seed_demo_environment(force_production=force))
    print("\n========================================================")
    print(" OBLIGATION AGENT — DEMO ENVIRONMENT SEED COMPLETE")
    print("========================================================")
    print(f" Workspace : {res['demo_workspace_name']} ({res['demo_workspace_id']})")
    print(f" User      : {res['demo_user_email']}")
    print(f" Password  : (configured via DEMO_USER_PASSWORD, default: demo1234)")
    print(f" Entities  : {res['obligations_count']} Obligations, {res['dependencies_count']} Edges, {res['ingested_events_count']} Ingested Events")
    print("========================================================\n")

