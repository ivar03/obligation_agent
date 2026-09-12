"""
Obligation Agent — Real-World Demo Environment Seed.

Populates a rich, realistic, domain-grounded demo environment:
 - Demo User & Team Member Accounts across Functions (Product, Engineering, Finance, Ops, Sales, CS)
 - Demo Workspace & Isolated Scopes
 - 14 Balanced Obligations: Healthy, In Progress, At Risk, Blocked, Due Soon, Overdue, Completed
 - 3 Multi-Step Dependency Graph Chains
 - Correlated Evidence & Ingested Events with Conflicting Observations
 - 3 Decision Center Proposals with Human-in-the-Loop Governance
 - Semantic LLM Analysis Records (deterministic mock analysis)
 - Operational Audit Records with Cryptographic Hash Chain

Safe for development/staging; guards against accidental production invocation.
Idempotent and deterministic: cleans up workspace records before re-seeding.
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
    ReconciliationStatus,
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

        # 1. Clean existing records for this workspace (Guarantees Idempotency)
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

        # 2. Workspace & Cross-Functional Team Identities
        ws_stmt = select(Workspace).where(Workspace.id == demo_workspace_id)
        ws = (await session.execute(ws_stmt)).scalar_one_or_none()
        if not ws:
            ws = Workspace(
                id=demo_workspace_id,
                name=demo_workspace_name,
                slug="demo-workspace",
            )
            session.add(ws)

        team_identities = [
            (demo_user_id, demo_email, "demo1234", "Demo Operator", WorkspaceRole.OWNER),
            ("usr-priya", "priya@company.com", "priya1234", "Priya Sharma (Tech Lead - Engineering)", WorkspaceRole.MEMBER),
            ("usr-marcus", "marcus@company.com", "marcus1234", "Marcus Vance (Finance Director - Finance)", WorkspaceRole.MEMBER),
            ("usr-sarah", "sarah@company.com", "sarah1234", "Sarah Jenkins (VP Commercial Sales - Sales)", WorkspaceRole.MEMBER),
            ("usr-david", "david@company.com", "david1234", "David Kim (Head of Operations - Operations)", WorkspaceRole.MEMBER),
            ("usr-elena", "elena@company.com", "elena1234", "Elena Rostova (Principal PM - Product)", WorkspaceRole.MEMBER),
            ("usr-alex", "alex@company.com", "alex1234", "Alex Rivera (Lead CSM - Customer Success)", WorkspaceRole.MEMBER),
        ]

        for uid, uemail, upass, uname, urole in team_identities:
            user_stmt = select(User).where(User.id == uid)
            user_obj = (await session.execute(user_stmt)).scalar_one_or_none()
            if not user_obj:
                user_obj = User(
                    id=uid,
                    email=uemail,
                    password_hash=hash_password(upass),
                    display_name=uname,
                    is_active=True,
                )
                session.add(user_obj)
            else:
                user_obj.email = uemail
                user_obj.password_hash = hash_password(upass)
                user_obj.display_name = uname

            membership = WorkspaceMembership(
                id=f"mem-{uuid.uuid4().hex[:8]}",
                workspace_id=demo_workspace_id,
                user_id=uid,
                role=urole,
            )
            session.add(membership)

        await session.flush()

        # 3. Obligations Dataset (14 obligations with exact balanced distribution)
        # ----------------------------------------------------------------------
        # PIPELINE 1: Commercial Sales & Finance Governance
        # 1. Due soon: Finance Director authorization
        ob_fin_approval = Obligation(
            id="ob-demo-fin-approval",
            workspace_id=demo_workspace_id,
            owner="marcus@company.com",
            beneficiary="sarah@company.com",
            action="Authorize Tier-1 Enterprise Discount Structure for Acme Corp",
            deadline=now + timedelta(hours=18),
            status=ObligationStatus.IN_PROGRESS,
            obligation_type=ObligationType.OWED_TO_ME,
            confidence={"overall": 0.96, "owner": 1.0, "action": 0.95, "deadline": 0.92},
            source_ref="Finance Request #FIN-809",
        )

        # 2. Blocked: Pricing finalization (Blocked by Marcus)
        ob_pricing = Obligation(
            id="ob-demo-pricing",
            workspace_id=demo_workspace_id,
            owner="sarah@company.com",
            beneficiary="alex@company.com",
            action="Finalize Multi-Year Enterprise Pricing Schedule",
            deadline=now + timedelta(days=2),
            status=ObligationStatus.BLOCKED,
            block_reason={
                "blocked": True,
                "blocked_by": [{
                    "obligation_id": ob_fin_approval.id,
                    "owner": "marcus@company.com",
                    "action": "Authorize Tier-1 Enterprise Discount Structure for Acme Corp",
                    "status": "IN_PROGRESS",
                    "reason": "Executive finance authorization required before publishing customer discount table.",
                }]
            },
            obligation_type=ObligationType.OWED_BY_ME,
            confidence={"overall": 0.94, "owner": 0.98, "action": 0.94, "deadline": 0.90},
            source_ref="Salesforce Opp #SF-1049",
        )

        # 3. In Progress: Customer Proposal Delivery
        ob_proposal = Obligation(
            id="ob-demo-proposal",
            workspace_id=demo_workspace_id,
            owner="sarah@company.com",
            beneficiary="Acme Corp Procurement",
            action="Deliver Fully Executed Master Services Agreement & Proposal",
            deadline=now + timedelta(days=4),
            status=ObligationStatus.IN_PROGRESS,
            obligation_type=ObligationType.OWED_BY_ME,
            confidence={"overall": 0.92, "owner": 0.95, "action": 0.92, "deadline": 0.88},
            source_ref="Commercial Agreement Draft #MSA-992",
        )

        # 4. Confirmed: Customer Review Sync
        ob_customer_review = Obligation(
            id="ob-demo-customer-review",
            workspace_id=demo_workspace_id,
            owner="alex@company.com",
            beneficiary="sarah@company.com",
            action="Complete Commercial Stakeholder Review with Customer Executive Sponsor",
            deadline=now + timedelta(days=6),
            status=ObligationStatus.CONFIRMED,
            obligation_type=ObligationType.OWED_BY_ME,
            confidence={"overall": 0.90, "owner": 0.94, "action": 0.90, "deadline": 0.85},
            source_ref="Calendar Invite: Acme Corp Exec Review",
        )

        # PIPELINE 2: Infrastructure Migration & Engineering Delivery
        # 5. Overdue: Upstream Prerequisite Staging Benchmarks
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

        # 6. Blocked: Finalize Infrastructure Migration Plan
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

        # 7. In Progress: Execute Production Cutover
        ob_downstream = Obligation(
            id="ob-demo-downstream",
            workspace_id=demo_workspace_id,
            owner=demo_email,
            beneficiary="All Customers",
            action="Execute Zero-Downtime Production Cutover",
            deadline=now + timedelta(days=7),
            status=ObligationStatus.IN_PROGRESS,
            obligation_type=ObligationType.OWED_BY_ME,
            confidence={"overall": 0.90, "owner": 0.95, "action": 0.90, "deadline": 0.85},
            source_ref="Release Calendar",
        )

        # PIPELINE 3: Security & Compliance Audit
        # 8. Completed: Kubernetes RBAC Access Audit
        ob_sec_review = Obligation(
            id="ob-demo-sec-review",
            workspace_id=demo_workspace_id,
            owner="david@company.com",
            beneficiary=demo_email,
            action="Conduct Automated Kubernetes RBAC Access Audit",
            deadline=now - timedelta(days=2),
            status=ObligationStatus.COMPLETED,
            obligation_type=ObligationType.OWED_TO_ME,
            confidence={"overall": 0.99, "owner": 1.0, "action": 0.99, "deadline": 0.98},
            source_ref="Security Ticket SEC-104",
        )

        # 9. At Risk (Due Soon): Submit SOC2 Type II Audit Package
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
            source_ref="Compliance Audit Jira Ticket",
        )

        # 10. In Progress: Annual DPA Sign-offs
        ob_msa_exec = Obligation(
            id="ob-demo-msa-exec",
            workspace_id=demo_workspace_id,
            owner="sarah@company.com",
            beneficiary="Enterprise Risk Council",
            action="Archive Annual Data Processing Addendum (DPA) Sign-offs",
            deadline=now + timedelta(days=5),
            status=ObligationStatus.IN_PROGRESS,
            obligation_type=ObligationType.OWED_BY_ME,
            confidence={"overall": 0.91, "owner": 0.95, "action": 0.91, "deadline": 0.86},
            source_ref="Legal Vault Repository",
        )

        # STANDALONE CROSS-FUNCTIONAL COMMITMENTS:
        # 11. Healthy: Deliver v2 REST API Technical Specifications
        ob_healthy = Obligation(
            id="ob-demo-healthy",
            workspace_id=demo_workspace_id,
            owner=demo_email,
            beneficiary="Engineering Team",
            action="Deliver v2 REST API Technical Specifications",
            deadline=now + timedelta(days=5),
            status=ObligationStatus.CONFIRMED,
            obligation_type=ObligationType.OWED_BY_ME,
            confidence={"overall": 0.98, "owner": 1.0, "action": 0.98, "deadline": 0.95},
            source_ref="Engineering RFC #104",
        )

        # 12. Healthy: Publish Q4 Unified Product Roadmap
        ob_roadmap = Obligation(
            id="ob-demo-roadmap",
            workspace_id=demo_workspace_id,
            owner="elena@company.com",
            beneficiary="Executive Leadership",
            action="Publish Q4 Unified Obligation Intelligence Product Roadmap",
            deadline=now + timedelta(days=12),
            status=ObligationStatus.CONFIRMED,
            obligation_type=ObligationType.OWED_TO_ME,
            confidence={"overall": 0.97, "owner": 0.99, "action": 0.97, "deadline": 0.94},
            source_ref="Product Spec #PRD-2026-Q4",
        )

        # 13. Healthy: Implement Prometheus SLO Error Budget Burn Rate Alerts
        ob_monitoring = Obligation(
            id="ob-demo-monitoring",
            workspace_id=demo_workspace_id,
            owner="david@company.com",
            beneficiary="Site Reliability Engineering",
            action="Implement Prometheus SLO Error Budget Burn Rate Alerts",
            deadline=now + timedelta(days=8),
            status=ObligationStatus.CONFIRMED,
            obligation_type=ObligationType.OWED_BY_ME,
            confidence={"overall": 0.95, "owner": 0.97, "action": 0.95, "deadline": 0.90},
            source_ref="SRE Playbook #71",
        )

        # 14. At Risk: Deliver Custom SSO SAML Integration Onboarding Workshop
        ob_cs_onboarding = Obligation(
            id="ob-demo-cs-onboarding",
            workspace_id=demo_workspace_id,
            owner="alex@company.com",
            beneficiary="Global Logistics Ltd",
            action="Deliver Custom SSO SAML Integration Onboarding Workshop",
            deadline=now + timedelta(hours=20),
            status=ObligationStatus.IN_PROGRESS,
            obligation_type=ObligationType.OWED_BY_ME,
            confidence={"overall": 0.88, "owner": 0.92, "action": 0.88, "deadline": 0.82},
            source_ref="Zendesk Ticket #ZD-44210",
        )

        session.add_all([
            ob_fin_approval, ob_pricing, ob_proposal, ob_customer_review,
            ob_upstream, ob_blocked, ob_downstream,
            ob_sec_review, ob_at_risk, ob_msa_exec,
            ob_healthy, ob_roadmap, ob_monitoring, ob_cs_onboarding,
        ])
        await session.flush()

        # 4. Dependency Graph Edges (7 total across 3 distinct chains)
        # Chain 1 Edges: Finance -> Pricing -> Proposal -> Customer Review
        e1_1 = ObligationEdge(
            id=f"edge-{uuid.uuid4().hex[:8]}",
            workspace_id=demo_workspace_id,
            from_obligation_id=ob_pricing.id,
            to_obligation_id=ob_fin_approval.id,
            edge_type=EdgeType.DEPENDS_ON,
        )
        e1_2 = ObligationEdge(
            id=f"edge-{uuid.uuid4().hex[:8]}",
            workspace_id=demo_workspace_id,
            from_obligation_id=ob_proposal.id,
            to_obligation_id=ob_pricing.id,
            edge_type=EdgeType.DEPENDS_ON,
        )
        e1_3 = ObligationEdge(
            id=f"edge-{uuid.uuid4().hex[:8]}",
            workspace_id=demo_workspace_id,
            from_obligation_id=ob_customer_review.id,
            to_obligation_id=ob_proposal.id,
            edge_type=EdgeType.DEPENDS_ON,
        )

        # Chain 2 Edges: Benchmarks -> Migration -> Cutover
        e2_1 = ObligationEdge(
            id=f"edge-{uuid.uuid4().hex[:8]}",
            workspace_id=demo_workspace_id,
            from_obligation_id=ob_blocked.id,
            to_obligation_id=ob_upstream.id,
            edge_type=EdgeType.DEPENDS_ON,
        )
        e2_2 = ObligationEdge(
            id=f"edge-{uuid.uuid4().hex[:8]}",
            workspace_id=demo_workspace_id,
            from_obligation_id=ob_downstream.id,
            to_obligation_id=ob_blocked.id,
            edge_type=EdgeType.DEPENDS_ON,
        )

        # Chain 3 Edges: RBAC Audit -> SOC2 Package -> DPA Execution
        e3_1 = ObligationEdge(
            id=f"edge-{uuid.uuid4().hex[:8]}",
            workspace_id=demo_workspace_id,
            from_obligation_id=ob_at_risk.id,
            to_obligation_id=ob_sec_review.id,
            edge_type=EdgeType.DEPENDS_ON,
        )
        e3_2 = ObligationEdge(
            id=f"edge-{uuid.uuid4().hex[:8]}",
            workspace_id=demo_workspace_id,
            from_obligation_id=ob_msa_exec.id,
            to_obligation_id=ob_at_risk.id,
            edge_type=EdgeType.DEPENDS_ON,
        )

        session.add_all([e1_1, e1_2, e1_3, e2_1, e2_2, e3_1, e3_2])
        await session.flush()

        # 5. Supporting & Completed Evidence Records
        ev_sec = Evidence(
            id=f"ev-sec-{uuid.uuid4().hex[:8]}",
            obligation_id=ob_sec_review.id,
            evidence_type=EvidenceType.SYSTEM,
            source_type="kubernetes_audit",
            source_ref="k8s-audit-log-2026-09",
            content="Automated RBAC role assessment passed with zero privilege escalation risks across all namespaces.",
            correlation_status=CorrelationStatus.CONFIRMED,
            correlation_confidence=0.99,
            semantic_role=EventSemanticRole.COMPLETION_SIGNAL,
            actor="david@company.com",
            observed_at=now - timedelta(days=2),
        )
        ev_healthy = Evidence(
            id=f"ev-healthy-{uuid.uuid4().hex[:8]}",
            obligation_id=ob_healthy.id,
            evidence_type=EvidenceType.DOCUMENT,
            source_type="github",
            source_ref="gh-pr-4819",
            content="OpenAPI schema specification for v2 endpoints merged to main branch.",
            correlation_status=CorrelationStatus.SUGGESTED,
            correlation_confidence=0.95,
            semantic_role=EventSemanticRole.PROGRESS_UPDATE,
            actor="tech-lead@company.com",
            observed_at=now - timedelta(hours=6),
        )
        ev_proposal_slack = Evidence(
            id=f"ev-prop-slack-{uuid.uuid4().hex[:8]}",
            obligation_id=ob_proposal.id,
            evidence_type=EvidenceType.MESSAGE,
            source_type="slack",
            source_ref="slack-sales-981",
            content="Sarah Jenkins in #sales-enterprise: 'Customer confirmed verbally they are ready to sign, proposal sent.'",
            correlation_status=CorrelationStatus.SUGGESTED,
            correlation_confidence=0.88,
            semantic_role=EventSemanticRole.COMPLETION_SIGNAL,
            actor="sarah@company.com",
            observed_at=now - timedelta(hours=4),
        )
        ev_proposal_jira = Evidence(
            id=f"ev-prop-jira-{uuid.uuid4().hex[:8]}",
            obligation_id=ob_proposal.id,
            evidence_type=EvidenceType.SYSTEM,
            source_type="jira",
            source_ref="PRIC-401",
            content="Jira issue PRIC-401 remains in state 'IN_PROGRESS' with open commercial review subtasks.",
            correlation_status=CorrelationStatus.SUGGESTED,
            correlation_confidence=0.92,
            semantic_role=EventSemanticRole.NON_COMPLETION_SIGNAL,
            actor="system-jira",
            observed_at=now - timedelta(hours=3),
        )
        session.add_all([ev_sec, ev_healthy, ev_proposal_slack, ev_proposal_jira])
        await session.flush()

        # 6. Continuous Event Ingestion (Populates Activity Center & Feed)
        event_slack = ExternalEvent(
            source_type="slack",
            source_ref="slack-msg-7721",
            sender="priya@company.com",
            recipients=[demo_email],
            content="Priya Sharma: 'Benchmark suite timed out on RDS read replicas. Staging database benchmark metrics will be delayed by 24h.'",
            timestamp=now - timedelta(hours=5),
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

        event_jira_fin = ExternalEvent(
            source_type="jira",
            source_ref="jira-issue-fin-809",
            sender="marcus@company.com",
            recipients=["sarah@company.com"],
            content="Jira Issue FIN-809: 'Tier-1 Enterprise Discount Authorization' transitioned to In Review.",
            timestamp=now - timedelta(hours=8),
        )
        await EventIngestionService.ingest_normalized_event(
            session=session,
            event=event_jira_fin,
            provider_name="jira",
            raw_payload={"key": "FIN-809", "status": "IN_REVIEW"},
            workspace_id=demo_workspace_id,
        )

        event_cs_slack = ExternalEvent(
            source_type="slack",
            source_ref="slack-msg-9102",
            sender="alex@company.com",
            recipients=["sarah@company.com"],
            content="Alex Rivera: 'Acme Corp customer stakeholders requested preliminary SSO workshop before signing MSA.'",
            timestamp=now - timedelta(hours=3),
        )
        await EventIngestionService.ingest_normalized_event(
            session=session,
            event=event_cs_slack,
            provider_name="slack",
            raw_payload={"channel": "customer-success", "user": "alex"},
            workspace_id=demo_workspace_id,
        )

        # 7. Cross-Provider Reconciliation Records (Meaningful contradictions for review)
        # Discrepancy 1: Proposal delivery contradiction between Slack and Jira
        rec_proposal = ReconciliationRecord(
            id="rec-demo-proposal-contradiction",
            workspace_id=demo_workspace_id,
            obligation_id=ob_proposal.id,
            status=ReconciliationStatus.CONFLICTING,
            confidence=0.88,
            consistency_score=0.25,
            contradiction_score=0.85,
            supporting_evidence_ids=[ev_proposal_slack.id],
            conflicting_evidence_ids=[ev_proposal_jira.id],
            explanation=[
                "Slack channel #sales-enterprise indicates: 'Customer confirmed verbally they are ready to sign, proposal sent.'",
                "Jira issue PRIC-401 remains in state 'IN_PROGRESS' with open commercial review subtasks.",
                "Finance discount authorization (ob-demo-fin-approval) remains pending Director sign-off.",
            ],
            recommended_action="FLAG_CONTRADICTION_FOR_HUMAN_ADJUDICATION",
        )

        # Discrepancy 2: Benchmark delay contradiction with scheduled migration sync
        rec_infra = ReconciliationRecord(
            id="rec-demo-infra-contradiction",
            workspace_id=demo_workspace_id,
            obligation_id=ob_upstream.id,
            status=ReconciliationStatus.CONFLICTING,
            confidence=0.92,
            consistency_score=0.15,
            contradiction_score=0.90,
            supporting_evidence_ids=[],
            conflicting_evidence_ids=[],
            explanation=[
                "Direct Slack signal: 'Benchmark suite timed out on RDS read replicas. Staging database benchmark metrics delayed 24h.'",
                "Google Calendar has 'Architecture Review & Infrastructure Migration Sync' scheduled with Executive Leadership without benchmark results.",
            ],
            recommended_action="RESCHEDULE_OR_ESCALATE_PREREQUISITE",
        )

        # Ambiguous record: SOC2 Audit Package Submission Verification
        rec_sec = ReconciliationRecord(
            id="rec-demo-sec-ambiguous",
            workspace_id=demo_workspace_id,
            obligation_id=ob_at_risk.id,
            status=ReconciliationStatus.AMBIGUOUS,
            confidence=0.74,
            consistency_score=0.55,
            contradiction_score=0.45,
            supporting_evidence_ids=[ev_sec.id],
            conflicting_evidence_ids=[],
            explanation=[
                "Kubernetes RBAC Audit evidence confirmed completed by David Kim.",
                "Compliance auditor email requests submission confirmation before end of business today.",
                "Final audit artifact submission receipt has not yet been uploaded to evidence vault.",
            ],
            recommended_action="AWAIT_MANUAL_SUBMISSION_RECEIPT",
        )
        session.add_all([rec_proposal, rec_infra, rec_sec])
        await session.flush()

        # 8. Integration Connections
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
            connection_metadata={"site_url": "https://acme-demo.atlassian.net", "email": demo_email, "selected_projects": ["ENG", "INFRA", "FIN", "SALES"]},
        )
        session.add_all([conn_slack, conn_jira])
        await session.flush()

        # 9. Governed Decision Center Plans (3 actionable human-in-the-loop plans)
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

        dp_finance = DecisionPlan(
            id="dp-demo-finance-02",
            workspace_id=demo_workspace_id,
            target_obligation_id=ob_pricing.id,
            primary_objective="Resolve Commercial Pricing Dependency on Finance Director",
            overall_urgency="HIGH",
            overall_risk=0.78,
            decision_confidence=0.89,
            recommended_actions={
                "strategy_id": "strat-002",
                "strategy_name": "Request urgent executive review from Marcus Vance",
                "target_obligation_id": ob_fin_approval.id,
                "target_owner": "Marcus Vance",
                "strategy_type": "ESCALATE_PREREQUISITE",
                "action_summary": "Request accelerated finance review for Acme Corp tier-1 enterprise proposal.",
            },
            key_risks=["Sales quarter-end commitment closure depends on Acme Corp contract execution"],
            human_decisions_required=[
                {
                    "decision_type": "APPROVE_STRATEGY",
                    "reason": "Authorize urgent finance review request",
                    "affected_obligation_id": ob_fin_approval.id,
                    "consequence_of_decision": "Unblocks proposal pricing schedule",
                }
            ],
            status=DecisionPlanStatus.GENERATED,
        )

        dp_compliance = DecisionPlan(
            id="dp-demo-compliance-03",
            workspace_id=demo_workspace_id,
            target_obligation_id=ob_at_risk.id,
            primary_objective="Mitigate Imminent SOC2 Access Audit Package Deadline",
            overall_urgency="CRITICAL",
            overall_risk=0.92,
            decision_confidence=0.94,
            recommended_actions={
                "strategy_id": "strat-003",
                "strategy_name": "Notify Compliance Board of verified RBAC audit artifacts",
                "target_obligation_id": ob_at_risk.id,
                "target_owner": "Demo Operator",
                "strategy_type": "PRE_AUDIT_VERIFICATION",
                "action_summary": "Transmit David Kim's completed RBAC access audit to compliance portal.",
            },
            key_risks=["Failure to submit within 14 hours breaches annual compliance reporting window"],
            human_decisions_required=[
                {
                    "decision_type": "AUTHORIZE_SUBMISSION",
                    "reason": "Verify RBAC evidence completeness and authorize transmission",
                    "affected_obligation_id": ob_at_risk.id,
                    "consequence_of_decision": "Satisfies annual SOC2 audit mandate",
                }
            ],
            status=DecisionPlanStatus.GENERATED,
        )
        session.add_all([dp_migration, dp_finance, dp_compliance])

        # 10. Mock Semantic LLM Analysis Records (For /intelligence tab)
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
                "action": "Submit final security audit package",
                "owner": demo_email,
                "beneficiary": "Security & Compliance Board",
                "deadline": (now + timedelta(days=1)).isoformat(),
                "confidence": 0.95,
            },
            confidence=0.95,
            validation_status="VALID",
            grounding_status="GROUNDED",
            latency_ms=185.0,
        )
        llm_rec_2 = LLMAnalysisRecord(
            id=f"llm-rec-{uuid.uuid4().hex[:8]}",
            workspace_id=demo_workspace_id,
            source_ref="demo-init-pricing",
            analysis_type="dependency_reasoning",
            prompt_version="dependency_reasoning:v1",
            schema_version="dependency-graph-v1",
            provider="mock",
            model="gemini-1.5-flash",
            input_hash="demo-input-hash-002",
            raw_prompt_redacted="Finance discount approval is blocking pricing finalization which blocks customer proposal.",
            structured_output={
                "chain_length": 3,
                "root_blocker": "ob-demo-fin-approval",
                "critical_path_urgency": "HIGH",
            },
            confidence=0.92,
            validation_status="VALID",
            grounding_status="GROUNDED",
            latency_ms=210.0,
        )
        session.add_all([llm_rec_1, llm_rec_2])

        # 11. Operational Audit Records (Cryptographic SHA-256 Provenance Proofs)
        await OperationalAuditService.log_event(
            session=session,
            workspace_id=demo_workspace_id,
            event_type="WORKSPACE_PROVISIONED",
            action=f"Provisioned demo workspace '{demo_workspace_name}'",
            severity="INFO",
            actor_type="USER",
            actor_id=demo_user_id,
            resource_type="Workspace",
            resource_id=demo_workspace_id,
            result="SUCCESS",
            metadata={"slug": "demo-workspace", "owner_email": demo_email},
        )
        await OperationalAuditService.log_event(
            session=session,
            workspace_id=demo_workspace_id,
            event_type="TEAM_IDENTITIES_INITIALIZED",
            action="Configured cross-functional tenant participants (Engineering, Finance, Sales, Ops, Product, CS)",
            severity="INFO",
            actor_type="SYSTEM",
            actor_id="system-seed",
            resource_type="UserBatch",
            resource_id="team-identities",
            result="SUCCESS",
            metadata={"users_count": len(team_identities)},
        )
        await OperationalAuditService.log_event(
            session=session,
            workspace_id=demo_workspace_id,
            event_type="OBLIGATIONS_INITIALIZED",
            action="Provisioned canonical multi-functional commitments dataset",
            severity="INFO",
            actor_type="SYSTEM",
            actor_id="system-seed",
            resource_type="ObligationBatch",
            resource_id=f"batch-{uuid.uuid4().hex[:6]}",
            result="SUCCESS",
            metadata={"obligations_count": 14, "edges_count": 7},
        )
        await OperationalAuditService.log_event(
            session=session,
            workspace_id=demo_workspace_id,
            event_type="DEPENDENCY_GRAPH_RESOLVED",
            action="Evaluated multi-step dependency cascades and blocked state propagation",
            severity="INFO",
            actor_type="SYSTEM",
            actor_id="engine-graph",
            resource_type="ObligationGraph",
            resource_id=f"graph-{demo_workspace_id}",
            result="SUCCESS",
            metadata={"chains_count": 3, "blocked_nodes": 2},
        )
        await OperationalAuditService.log_event(
            session=session,
            workspace_id=demo_workspace_id,
            event_type="CROSS_PROVIDER_RECONCILIATION_EVALUATED",
            action="Evaluated multi-source evidence contradictions & consistency across Slack, Jira, and Gmail",
            severity="WARNING",
            actor_type="SYSTEM",
            actor_id="engine-reconciliation",
            resource_type="ReconciliationRecord",
            resource_id="rec-demo-proposal-contradiction",
            result="SUCCESS",
            metadata={"workspace_id": demo_workspace_id, "evaluated_records": 3, "contradictions_found": 2},
        )
        await OperationalAuditService.log_event(
            session=session,
            workspace_id=demo_workspace_id,
            event_type="DECISION_STRATEGIES_GENERATED",
            action="Generated 3 human-in-the-loop decision proposals in Decision Center",
            severity="INFO",
            actor_type="SYSTEM",
            actor_id="engine-decision-orchestrator",
            resource_type="DecisionPlanBatch",
            resource_id="dp-batch-01",
            result="SUCCESS",
            metadata={"plans_count": 3, "requires_human_review": True},
        )
        await OperationalAuditService.log_event(
            session=session,
            workspace_id=demo_workspace_id,
            event_type="INTEGRATIONS_CONFIGURED",
            action="Connected Slack and Jira provider adapters for continuous observation",
            severity="INFO",
            actor_type="USER",
            actor_id=demo_user_id,
            resource_type="IntegrationConnection",
            resource_id="conn-slack-jira",
            result="SUCCESS",
            metadata={"providers": ["slack", "jira"]},
        )

        await session.commit()

        logger.info("Demo environment seeded successfully with expanded dataset.")
        return {
            "demo_user_email": demo_email,
            "demo_workspace_name": demo_workspace_name,
            "demo_workspace_id": demo_workspace_id,
            "obligations_count": 14,
            "dependencies_count": 7,
            "evidence_count": 4,
            "ingested_events_count": 6,
            "reconciliation_records_count": 3,
            "decision_plans_count": 3,
            "operational_audit_records_count": 7,
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
    print(f" Entities  : {res['obligations_count']} Obligations, {res['dependencies_count']} Edges, {res['evidence_count']} Evidence Records")
    print(f" Activities: {res['ingested_events_count']} Ingested Events, {res['reconciliation_records_count']} Reconciliation Records")
    print(f" Decisions : {res['decision_plans_count']} Decision Plans, {res['operational_audit_records_count']} Operational Audit Records")
    print("========================================================\n")
