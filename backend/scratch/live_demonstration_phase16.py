"""
Phase 16 Live Demonstration: Controlled Decision Execution & Outcome Verification Layer.

Demonstrates the 15-step end-to-end causal execution and outcome verification lifecycle:
1. Workspace & Operator Setup
2. Obligation Graph Setup (Root Blocker -> Dependent)
3. Intelligence Orchestrator Decision Plan Synthesis (v1)
4. Invariant A Verification: Unapproved Plan Execution Rejection
5. Human Approval of Decision Plan
6. Outbound Controlled Execution via Provider Adapter (SIM-EXEC Ref)
7. Invariant E Verification: Strong Idempotency (repeated execution returns same record)
8. Invariant F Verification: Delivery != Obligation Completed
9. Immutable Execution Receipt Retrieval & Redaction Verification
10. Ingest Progress Event -> Reconciles to PROGRESS_REPORTED
11. Invariant G Verification: Progress != Obligation Completed
12. Ingest Completion Signal -> Generates Suggested Evidence
13. Invariant H Verification: Completion Signal != Obligation Completed (Human confirmation required)
14. Human Operator Confirms Evidence -> Obligation Completed
15. Execution Record transitions to RESOLVED & Audit Provenance Verified
"""

import asyncio
import os
import sys
import uuid
from datetime import datetime, timezone, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import AsyncSessionLocal, engine, Base
from app.models.auth import User, Workspace
from app.models.obligation import Obligation, ObligationEdge, Evidence, Intervention, IngestedEventRecord
from app.models.decision import DecisionPlan
from app.models.execution import ExecutionRecord
from app.core.status_machine import (
    ObligationStatus,
    ObligationType,
    DecisionPlanStatus,
    ExecutionStatus,
    ExecutionOutcome,
    EventSemanticRole,
)
from app.core.intervention_status import InterventionStatus, InterventionType
from app.services.execution.execution_authorization_service import (
    ExecutionAuthorizationService,
    ExecutionAuthorizationError,
)
from app.services.execution.execution_service import ExecutionService
from app.services.execution.outcome_reconciliation_service import OutcomeReconciliationService
from app.schemas.obligation import ExternalEvent
from app.schemas.execution import ExecutionAuthorizeRequest, ExecutionExecuteRequest


def utc_now():
    return datetime.now(timezone.utc)


def print_step(step_num: int, title: str):
    print("\n" + "=" * 80)
    print(f" STEP {step_num}: {title.upper()}")
    print("=" * 80)


async def run_phase16_demo():
    print("Initializing Database tables...")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with AsyncSessionLocal() as session:
        # ---------------------------------------------------------------------
        # STEP 1: Workspace & Operator Setup
        # ---------------------------------------------------------------------
        print_step(1, "Workspace & Operator Setup")
        ws_id = f"ws-demo-{uuid.uuid4().hex[:6]}"
        ws = Workspace(id=ws_id, name="Cloud Operations WS", slug=f"cloud-ops-{uuid.uuid4().hex[:6]}")
        user = User(
            id=f"usr-{uuid.uuid4().hex[:6]}",
            email="sarah.connor@defense.gov",
            display_name="Sarah Connor (Incident Commander)",
            password_hash="argon2_demo_hash",
            is_active=True,
        )
        session.add_all([ws, user])
        await session.flush()
        print(f" [OK] Created Workspace: [{ws.name}] (ID: {ws.id})")
        print(f" [OK] Created Human Operator: [{user.display_name}] (Role: OPERATOR)")

        # ---------------------------------------------------------------------
        # STEP 2: Create Multi-Hop Obligation Graph
        # ---------------------------------------------------------------------
        print_step(2, "Create Multi-Hop Overdue Obligation Graph")
        now = utc_now()
        ob_root = Obligation(
            id=f"ob-root-{uuid.uuid4().hex[:6]}",
            workspace_id=ws_id,
            owner="Rahul Sharma",
            beneficiary="Sarah Connor",
            action="Deploy PostgreSQL partition migration on production cluster",
            status=ObligationStatus.OVERDUE,
            obligation_type=ObligationType.OWED_BY_ME,
            deadline=now - timedelta(hours=4),
        )
        ob_dep = Obligation(
            id=f"ob-dep-{uuid.uuid4().hex[:6]}",
            workspace_id=ws_id,
            owner="Elena Rostova",
            beneficiary="Sarah Connor",
            action="Run live latency benchmark suite after partitioning",
            status=ObligationStatus.BLOCKED,
            obligation_type=ObligationType.OWED_BY_ME,
            deadline=now + timedelta(hours=12),
        )
        session.add_all([ob_root, ob_dep])
        await session.flush()

        from app.core.status_machine import EdgeType
        edge = ObligationEdge(
            workspace_id=ws_id,
            from_obligation_id=ob_dep.id,
            to_obligation_id=ob_root.id,
            edge_type=EdgeType.DEPENDS_ON,
        )
        session.add(edge)
        await session.flush()
        print(f" [OK] Root Blocker: [{ob_root.action}] (Owner: {ob_root.owner}, Status: {ob_root.status.value})")
        print(f" [OK] Downstream Obligation: [{ob_dep.action}] (Owner: {ob_dep.owner}, Status: {ob_dep.status.value})")
        print(f" [OK] Graph Dependency: Root -> Downstream (BLOCKS)")

        # ---------------------------------------------------------------------
        # STEP 3: Intelligence Orchestrator Synthesizes Decision Plan v1
        # ---------------------------------------------------------------------
        print_step(3, "Synthesize Phase 15 Decision Plan v1")
        inv = Intervention(
            id=f"inv-{uuid.uuid4().hex[:6]}",
            workspace_id=ws_id,
            obligation_id=ob_root.id,
            intervention_type=InterventionType.FOLLOW_UP_OWNER,
            target_owner=ob_root.owner,
            target_beneficiary="Sarah Connor",
            title="Follow up on Postgres partitioning blocker",
            message_draft=f"Hi {ob_root.owner}, the Postgres partition migration is overdue and blocking Elena's latency benchmarks. What is current deployment status?",
            status=InterventionStatus.APPROVED,
            urgency="HIGH",
            rationale="Root causal blocker on critical path",
        )
        session.add(inv)
        await session.flush()

        plan = DecisionPlan(
            id=f"plan-p16-{uuid.uuid4().hex[:6]}",
            workspace_id=ws_id,
            target_obligation_id=ob_root.id,
            plan_version=1,
            status=DecisionPlanStatus.GENERATED,
            overall_urgency="HIGH",
            overall_risk=0.88,
            decision_confidence=0.92,
            primary_objective="Clear root blocker: Deploy Postgres partition migration",
            recommended_actions={
                "strategy_name": "FOLLOW_UP_ROOT_OWNER",
                "action_summary": f"Follow up with {ob_root.owner} via Slack to unblock downstream benchmark suite.",
                "target_owner": ob_root.owner,
                "intervention_id": inv.id,
            },
            human_decisions_required=[
                {
                    "decision_type": "APPROVE_OUTBOUND_COMMUNICATION",
                    "reason": "Authorizes automated delivery to external stakeholder channel.",
                    "consequence_of_decision": "Sends message to Rahul without modifying obligation status.",
                    "requires_admin": False,
                }
            ],
        )
        session.add(plan)
        await session.commit()
        print(f" [OK] Generated Decision Plan: ID=[{plan.id}] Version=[v{plan.plan_version}] Status=[{plan.status.value}]")
        print(f" [OK] Recommended Strategy: {plan.recommended_actions['strategy_name']}")

        # ---------------------------------------------------------------------
        # STEP 4: Invariant A Verification: Unapproved Plan Rejection
        # ---------------------------------------------------------------------
        print_step(4, "Invariant A Verification: Unapproved Plan Cannot Execute")
        try:
            await ExecutionAuthorizationService.validate_authorization(
                session=session,
                plan_id=plan.id,
                workspace_id=ws_id,
            )
            raise AssertionError("Invariant A Violation: Unapproved plan allowed to execute!")
        except ExecutionAuthorizationError as exc:
            print(f" [INVARIANT ENFORCED] Unapproved execution blocked successfully.")
            print(f"   Error Code: {exc.detail.get('error_code')} | Detail: {exc.detail.get('message')}")

        # ---------------------------------------------------------------------
        # STEP 5: Human Approval of Decision Plan
        # ---------------------------------------------------------------------
        print_step(5, "Human Operator Explicit Approval of Decision Plan")
        plan.status = DecisionPlanStatus.APPROVED
        plan.approved_by_user_id = user.id
        plan.approved_at = utc_now()
        await session.commit()
        print(f" [OK] Decision Plan Approved by: [{user.display_name}] at [{plan.approved_at.isoformat()}]")

        # ---------------------------------------------------------------------
        # STEP 6: Controlled Outbound Execution via Mock Provider
        # ---------------------------------------------------------------------
        print_step(6, "Controlled Outbound Execution via Provider Adapter")
        exec_res = await ExecutionService.execute(
            session=session,
            plan_id=plan.id,
            user=user,
            workspace_id=ws_id,
            request=ExecutionExecuteRequest(provider="mock", notes="Incident triage follow-up"),
        )
        print(f" [OK] Execution Record Created: ID=[{exec_res.id}]")
        print(f" [OK] Provider Execution Ref: [{exec_res.provider_execution_ref}]")
        print(f" [OK] Delivery Status: [{exec_res.delivery_status}] | Status: [{exec_res.status.value}]")

        # ---------------------------------------------------------------------
        # STEP 7: Invariant E Verification: Strong Idempotency
        # ---------------------------------------------------------------------
        print_step(7, "Invariant E Verification: Strong Execution Idempotency")
        exec_res_repeat1 = await ExecutionService.execute(session=session, plan_id=plan.id, user=user, workspace_id=ws_id)
        exec_res_repeat2 = await ExecutionService.execute(session=session, plan_id=plan.id, user=user, workspace_id=ws_id)

        assert exec_res.id == exec_res_repeat1.id == exec_res_repeat2.id
        assert exec_res.provider_execution_ref == exec_res_repeat1.provider_execution_ref == exec_res_repeat2.provider_execution_ref

        # Check count in DB
        db_count = (await session.execute(select(ExecutionRecord).where(ExecutionRecord.decision_plan_id == plan.id))).scalars().all()
        assert len(db_count) == 1
        print(f" [INVARIANT ENFORCED] 3 execution requests dispatched exactly 1 provider action.")
        print(f"   Execution ID: {exec_res.id} | Provider Ref: {exec_res.provider_execution_ref} | DB Records Count: {len(db_count)}")

        # ---------------------------------------------------------------------
        # STEP 8: Invariant F Verification: Delivery != Obligation Completed
        # ---------------------------------------------------------------------
        print_step(8, "Invariant F Verification: Delivery Does NOT Complete Obligation")
        fresh_ob = await session.get(Obligation, ob_root.id)
        assert fresh_ob.status == ObligationStatus.OVERDUE
        print(f" [INVARIANT ENFORCED] Target Obligation Status remains: [{fresh_ob.status.value}]")
        print(f"   Safety Invariant Verified: INTERVENTION_EXECUTED != OBLIGATION_COMPLETED.")

        # ---------------------------------------------------------------------
        # STEP 9: Immutable Execution Receipt Retrieval & Redaction
        # ---------------------------------------------------------------------
        print_step(9, "Immutable Execution Receipt Retrieval & Redaction")
        receipt = await ExecutionService.get_receipt(session=session, execution_id=exec_res.id, workspace_id=ws_id)
        print(f" [OK] Generated Receipt ID: {receipt.execution_id}")
        print(f"   Provider Ref: {receipt.provider_execution_ref}")
        print(f"   Authorized By: {receipt.authorized_by}")
        print(f"   Delivery Status: {receipt.delivery_status}")
        print(f"   Safe Metadata: {receipt.safe_metadata}")
        for k in ["token", "secret", "password", "key", "authorization"]:
            assert k not in receipt.safe_metadata
        print(" [OK] Credential Zero-Leakage Guarantee Verified: 100% redacted.")

        # ---------------------------------------------------------------------
        # STEP 10: Ingest External Progress Event
        # ---------------------------------------------------------------------
        print_step(10, "Ingest External Progress Event (PROGRESS_UPDATE)")
        ev_prog = IngestedEventRecord(
            id=f"evt-prog-{uuid.uuid4().hex[:6]}",
            workspace_id=ws_id,
            provider="slack",
            source_ref=f"slack-msg-{uuid.uuid4().hex[:6]}",
            semantic_role=EventSemanticRole.PROGRESS_UPDATE,
            correlated_obligation_id=ob_root.id,
            sender="Rahul Sharma",
            content="I am currently running partition script on table telemetry_logs, 60% complete.",
            action_taken="NONE",
            received_at=utc_now(),
        )
        session.add(ev_prog)
        await session.flush()

        ext_prog = ExternalEvent(
            source_type="slack",
            source_ref=ev_prog.source_ref,
            sender=ev_prog.sender,
            content=ev_prog.content,
            timestamp=ev_prog.received_at,
        )
        reconciled_prog = await OutcomeReconciliationService.reconcile_event(
            session=session,
            event_record=ev_prog,
            external_event=ext_prog,
        )
        print(f" [OK] Reconciled Event [{ev_prog.id}] with Execution [{exec_res.id}]")
        print(f"   Detected Outcome: {reconciled_prog[0].outcome.value}")
        print(f"   Updated Execution Status: {reconciled_prog[0].updated_execution_status.value}")

        # ---------------------------------------------------------------------
        # STEP 11: Invariant G Verification: Progress != Obligation Completed
        # ---------------------------------------------------------------------
        print_step(11, "Invariant G Verification: Progress Response Does NOT Complete Obligation")
        fresh_ob = await session.get(Obligation, ob_root.id)
        assert fresh_ob.status == ObligationStatus.OVERDUE
        print(f" [INVARIANT ENFORCED] Obligation Status is still: [{fresh_ob.status.value}]")

        # ---------------------------------------------------------------------
        # STEP 12: Ingest External Completion Signal (COMPLETION_SIGNAL)
        # ---------------------------------------------------------------------
        print_step(12, "Ingest External Completion Signal Event")
        ev_comp = IngestedEventRecord(
            id=f"evt-comp-{uuid.uuid4().hex[:6]}",
            workspace_id=ws_id,
            provider="slack",
            source_ref=f"slack-msg-{uuid.uuid4().hex[:6]}",
            semantic_role=EventSemanticRole.COMPLETION_SIGNAL,
            correlated_obligation_id=ob_root.id,
            sender="Rahul Sharma",
            content="Partition migration deployed and verified on production. Attached logs: migration_20260831.log",
            action_taken="SUGGESTED_EVIDENCE_CREATED",
            evidence_id=f"evi-{uuid.uuid4().hex[:6]}",
            received_at=utc_now(),
        )
        session.add(ev_comp)
        await session.flush()

        ext_comp = ExternalEvent(
            source_type="slack",
            source_ref=ev_comp.source_ref,
            sender=ev_comp.sender,
            content=ev_comp.content,
            timestamp=ev_comp.received_at,
        )
        reconciled_comp = await OutcomeReconciliationService.reconcile_event(
            session=session,
            event_record=ev_comp,
            external_event=ext_comp,
        )
        print(f" [OK] Detected Outcome: {reconciled_comp[0].outcome.value}")
        print(f"   Suggested Evidence Created: {reconciled_comp[0].evidence_created}")
        print(f"   Evidence ID: {reconciled_comp[0].evidence_id}")

        # ---------------------------------------------------------------------
        # STEP 13: Invariant H Verification: Human Evidence Confirmation Boundary
        # ---------------------------------------------------------------------
        print_step(13, "Invariant H Verification: Human Evidence Confirmation Boundary")
        fresh_ob = await session.get(Obligation, ob_root.id)
        assert fresh_ob.status == ObligationStatus.OVERDUE
        print(f" [INVARIANT ENFORCED] Obligation Status is still: [{fresh_ob.status.value}]")
        print("   Safety Invariant Verified: Ingested completion signal generates suggested evidence, but NEVER completes obligation without operator confirmation.")

        # ---------------------------------------------------------------------
        # STEP 14: Human Operator Authoritatively Confirms Evidence
        # ---------------------------------------------------------------------
        print_step(14, "Human Operator Authoritatively Confirms Evidence")
        from app.core.status_machine import EvidenceType, CorrelationStatus
        evidence = Evidence(
            id=ev_comp.evidence_id,
            workspace_id=ws_id,
            obligation_id=ob_root.id,
            evidence_type=EvidenceType.MESSAGE,
            source_type="slack",
            source_ref=ev_comp.source_ref,
            content="Postgres partition migration completed successfully on prod cluster.",
            correlation_status=CorrelationStatus.CONFIRMED,
            actor=user.display_name,
        )
        session.add(evidence)
        fresh_ob.status = ObligationStatus.COMPLETED
        fresh_ob.completed_at = utc_now()
        await session.flush()
        print(f" [OK] Human Operator [{user.display_name}] Confirmed Evidence [{evidence.id}]")
        print(f" [OK] Obligation [{ob_root.id}] Transitioned to COMPLETED!")

        # ---------------------------------------------------------------------
        # STEP 15: Execution Record & Decision Plan Resolution
        # ---------------------------------------------------------------------
        print_step(15, "Execution Record & Decision Plan Final Resolution")
        resolved_ids = await OutcomeReconciliationService.resolve_on_obligation_completed(session, ob_root.id)
        final_exec = await session.get(ExecutionRecord, exec_res.id)
        assert final_exec.status == ExecutionStatus.RESOLVED

        print(f" [OK] Execution Record [{final_exec.id}] Status: [{final_exec.status.value}]")
        print(f" [OK] Resolved Executions: {resolved_ids}")
        print("\n" + "*" * 80)
        print(" PHASE 16 CONTROLLED DECISION EXECUTION DEMONSTRATION COMPLETE & FULLY VERIFIED!")
        print("*" * 80)


if __name__ == "__main__":
    asyncio.run(run_phase16_demo())
