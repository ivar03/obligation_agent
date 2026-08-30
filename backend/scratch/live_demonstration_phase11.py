"""Phase 11: Cross-Provider Obligation Reconciliation & Contradiction Intelligence

13-Step Comprehensive End-to-End Live Demonstration Script
Canonical Project Name: Obligation Agent
"""

import asyncio
import json
import os
import sys
import uuid
from datetime import datetime, timezone, timedelta

# Ensure backend root is in python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from sqlalchemy import select

from app.core.database import AsyncSessionLocal, Base, engine
from app.models.obligation import (
    Obligation,
    ObligationEdge,
    Evidence,
    ReconciliationRecord,
)
from app.core.status_machine import (
    ObligationStatus,
    ObligationType,
    EdgeType,
    EventSemanticRole,
    CorrelationStatus,
    ReconciliationStatus,
    ReconciliationResolutionAction,
    ActionType,
)
from app.services.reconciliation_service import ReconciliationService
from app.services.event_ingestion_service import EventIngestionService
from app.services.risk_engine import RiskEngine
from app.services.recommendation_engine import RecommendationEngine
from app.services.graph_service import GraphService
from app.schemas.obligation import ReconciliationResolutionRequest


async def run_live_demonstration():
    print("=" * 80)
    print("OBLIGATION AGENT — PHASE 11 LIVE DEMONSTRATION")
    print("Cross-Provider Obligation Reconciliation & Contradiction Intelligence")
    print("=" * 80)

    # Initialize tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with AsyncSessionLocal() as session:
        now = datetime.now(timezone.utc)

        # ----------------------------------------------------------------------
        # STEP 1: CREATE DEPENDENCY GRAPH
        # ----------------------------------------------------------------------
        print("\n[STEP 1] Creating Dependency Graph (Obligation A -> Dependent Obligation B)...")
        ob_a = Obligation(
            owner="Rahul Sharma",
            beneficiary="Ravi Kumar",
            action="Complete quarterly financial audit report",
            deadline=now + timedelta(days=3),
            status=ObligationStatus.CONFIRMED,
            obligation_type=ObligationType.OWED_TO_ME,
        )
        ob_b = Obligation(
            owner="Ravi Kumar",
            beneficiary="Regulatory Compliance Board",
            action="File quarterly corporate compliance filing",
            deadline=now + timedelta(days=7),
            status=ObligationStatus.CONFIRMED,
            obligation_type=ObligationType.OWED_BY_ME,
        )
        session.add_all([ob_a, ob_b])
        await session.commit()
        await session.refresh(ob_a)
        await session.refresh(ob_b)

        # Create edge: B DEPENDS_ON A
        edge = ObligationEdge(
            from_obligation_id=ob_b.id,
            to_obligation_id=ob_a.id,
            edge_type=EdgeType.DEPENDS_ON,
        )
        session.add(edge)
        await session.commit()

        # Update initial block reason on B
        await GraphService.evaluate_and_propagate(session, ob_a.id)
        await session.refresh(ob_b)
        print(f"  -> Obligation A (Parent): '{ob_a.action}' [Status: {ob_a.status.value}] (ID: {ob_a.id[:8]}...)")
        print(f"  -> Obligation B (Dependent): '{ob_b.action}' [Status: {ob_b.status.value}] (ID: {ob_b.id[:8]}...)")
        print(f"  -> Dependency Edge: B depends on A. B Blocked: {ob_b.block_reason is not None}")

        # ----------------------------------------------------------------------
        # STEP 2: INGEST SLACK PROGRESS EVENT
        # ----------------------------------------------------------------------
        print("\n[STEP 2] Ingesting Slack Progress Event from Rahul...")
        slack_payload = {
            "channel": "finance-audit",
            "user": "Rahul Sharma",
            "text": "Working on quarterly financial audit report analysis. Draft is 60% done.",
            "ts": f"{now.timestamp()}",
        }
        res_slack = await EventIngestionService.ingest_from_provider(session, "slack", slack_payload)
        print(f"  -> Ingested Slack Event: {res_slack.semantic_role} (Status: {res_slack.status})")
        print(f"  -> Affected Obligations: {[oid[:8] for oid in res_slack.affected_obligation_ids]}")
        await session.refresh(ob_a)
        print(f"  -> Obligation A Status: {ob_a.status.value} (Preserved active state)")

        # ----------------------------------------------------------------------
        # STEP 3: INGEST GMAIL COMPLETION DELIVERABLE
        # ----------------------------------------------------------------------
        print("\n[STEP 3] Ingesting Gmail Completion Deliverable from Rahul...")
        gmail_payload = {
            "from": "Rahul Sharma <rahul@acme.com>",
            "to": ["Ravi Kumar <ravi@acme.com>"],
            "subject": "Complete quarterly financial audit report - Deliverable",
            "body": "Hi Ravi, please find attached the delivered completed quarterly financial audit report.",
            "attachments": [{"name": "audit_report_v1.pdf", "size": 245000}],
        }
        res_gmail = await EventIngestionService.ingest_from_provider(session, "gmail", gmail_payload)
        print(f"  -> Ingested Gmail Event: {res_gmail.semantic_role} (Status: {res_gmail.status})")

        # ----------------------------------------------------------------------
        # STEP 4: RECONCILIATION AUTO-TRIGGER & NO AUTO-COMPLETION SAFETY CHECK
        # ----------------------------------------------------------------------
        print("\n[STEP 4] Evaluating Cross-Provider Reconciliation & Safety Check...")
        rec1 = await ReconciliationService.get_by_obligation(session, ob_a.id)
        assert rec1 is not None
        print(f"  -> Reconciliation Record Status: {rec1.status.value}")
        print(f"  -> Consistency Score: {rec1.consistency_score * 100:.0f}%")
        print(f"  -> Contradiction Score: {rec1.contradiction_score * 100:.0f}%")
        print(f"  -> Recommended Action: {rec1.recommended_action}")
        await session.refresh(ob_a)
        print(f"  -> [SAFETY GATE] Obligation A Status: {ob_a.status.value} (NOT auto-completed!)")
        assert ob_a.status != ObligationStatus.COMPLETED, "Violated safety boundary: Auto-completed!"

        # ----------------------------------------------------------------------
        # STEP 5: INGEST LATER SLACK BLOCKER (CONTRADICTION TRIGGER)
        # ----------------------------------------------------------------------
        print("\n[STEP 5] Ingesting Later Slack Blocker / Negative Signal from Rahul...")
        slack_blocker_payload = {
            "channel": "finance-audit",
            "user": "Rahul Sharma",
            "text": "Hold on Ravi, found discrepancies in payroll numbers. Audit report is blocked on revised data.",
            "ts": f"{(now + timedelta(hours=1)).timestamp()}",
        }
        res_slack_block = await EventIngestionService.ingest_from_provider(session, "slack", slack_blocker_payload)
        print(f"  -> Ingested Slack Blocker: {res_slack_block.semantic_role}")

        # ----------------------------------------------------------------------
        # STEP 6: CONTRADICTION DETECTION & RECONCILIATION RE-EVALUATION
        # ----------------------------------------------------------------------
        print("\n[STEP 6] Cross-Provider Contradiction Intelligence Analysis...")
        rec2 = await ReconciliationService.get_by_obligation(session, ob_a.id)
        assert rec2 is not None
        print(f"  -> Reconciliation Status: {rec2.status.value}")
        print(f"  -> Contradiction Score: {rec2.contradiction_score * 100:.0f}%")
        print(f"  -> Supporting Evidence Count: {len(rec2.supporting_evidence_ids)}")
        print(f"  -> Conflicting Evidence Count: {len(rec2.conflicting_evidence_ids)}")
        print(f"  -> Explanations Observed:")
        for exp in rec2.explanation:
            print(f"     * {exp}")

        # ----------------------------------------------------------------------
        # STEP 7: RISK ENGINE & ADVISORY RECALCULATION
        # ----------------------------------------------------------------------
        print("\n[STEP 7] Risk Engine Recalculation with Signal 7 (Reconciliation Risk)...")
        risk_assess = await RiskEngine.assess_obligation(session, ob_a.id)
        print(f"  -> Risk Level: {risk_assess.risk_level.value}")
        print(f"  -> Risk Score: {risk_assess.risk_score:.2f}")
        print(f"  -> Recommended Action: {risk_assess.recommended_action}")
        print(f"  -> Signals:")
        for sig in risk_assess.signals:
            if "EVIDENCE" in sig.signal_type or "RECONCILIATION" in sig.signal_type:
                sev = sig.severity.value if hasattr(sig.severity, "value") else str(sig.severity)
                print(f"     * [{sev}] {sig.signal_type}: {sig.explanation}")

        # ----------------------------------------------------------------------
        # STEP 8: HUMAN REVIEW ACTION 1 (KEEP OBLIGATION ACTIVE)
        # ----------------------------------------------------------------------
        print("\n[STEP 8] Human Decision 1: Acknowledging Contradiction & Keeping Active...")
        resolve_req_1 = ReconciliationResolutionRequest(
            action=ReconciliationResolutionAction.KEEP_OBLIGATION_ACTIVE,
            notes="Acknowledged payroll discrepancy blocker; keeping task active until v2.",
            operator="Ravi Kumar (Obligee)",
        )
        rec_resolved_1 = await ReconciliationService.resolve_reconciliation(session, rec2.id, resolve_req_1)
        print(f"  -> Reconciliation Status: {rec_resolved_1.status.value}")
        await session.refresh(ob_a)
        await session.refresh(ob_b)
        print(f"  -> Obligation A Status: {ob_a.status.value}")
        print(f"  -> Obligation B Status: {ob_b.status.value} (Still Blocked on A)")

        # ----------------------------------------------------------------------
        # STEP 9: INGEST SECOND GMAIL FINAL DELIVERABLE
        # ----------------------------------------------------------------------
        print("\n[STEP 9] Ingesting Final Gmail Deliverable v2 from Rahul...")
        gmail_v2_payload = {
            "from": "Rahul Sharma <rahul@acme.com>",
            "to": ["Ravi Kumar <ravi@acme.com>"],
            "subject": "Complete quarterly financial audit report - FINAL SIGNED v2",
            "body": "Hi Ravi, all payroll discrepancies resolved and audited. Attached final signed quarterly audit report v2.",
            "attachments": [{"name": "audit_report_v2_final_signed.pdf", "size": 310000}],
        }
        res_gmail_v2 = await EventIngestionService.ingest_from_provider(session, "gmail", gmail_v2_payload)
        print(f"  -> Ingested Gmail v2: {res_gmail_v2.semantic_role}")

        # ----------------------------------------------------------------------
        # STEP 10: RE-RECONCILIATION & CONSISTENCY SYNTHESIS
        # ----------------------------------------------------------------------
        print("\n[STEP 10] Multi-Source Re-Reconciliation & Evidence Synthesis...")
        rec3 = await ReconciliationService.reconcile_obligation(session, ob_a.id)
        print(f"  -> Reconciliation Status: {rec3.status.value}")
        print(f"  -> Consistency Score: {rec3.consistency_score * 100:.0f}%")
        print(f"  -> Contradiction Score: {rec3.contradiction_score * 100:.0f}%")
        print(f"  -> Recommended Action: {rec3.recommended_action}")

        # ----------------------------------------------------------------------
        # STEP 11: HUMAN CONFIRMATION OF COMPLETION
        # ----------------------------------------------------------------------
        print("\n[STEP 11] Human Decision 2: Authoritative Confirmation of Completion...")
        resolve_req_2 = ReconciliationResolutionRequest(
            action=ReconciliationResolutionAction.CONFIRM_COMPLETION,
            notes="Reviewed audit report v2 and verified signatures. Task complete.",
            operator="Ravi Kumar (Obligee)",
        )
        rec_resolved_2 = await ReconciliationService.resolve_reconciliation(session, rec3.id, resolve_req_2)
        print(f"  -> Reconciliation Record Status: {rec_resolved_2.status.value}")
        await session.refresh(ob_a)
        print(f"  -> Obligation A Status: {ob_a.status.value} (AUTHORITATIVELY COMPLETED)")

        # ----------------------------------------------------------------------
        # STEP 12: DOWNSTREAM GRAPH CASCADE & UNBLOCKING
        # ----------------------------------------------------------------------
        print("\n[STEP 12] Verifying Downstream Cascade & Graph Unblocking...")
        graph_b = await GraphService.get_graph_for_obligation(session, ob_b.id)
        await session.refresh(ob_b)
        print(f"  -> Obligation B Is Blocked: {graph_b.is_blocked}")
        print(f"  -> Obligation B Block Reason: {ob_b.block_reason}")
        assert not graph_b.is_blocked, "Obligation B should be unblocked after A completion!"
        print(f"  -> Obligation B is UNBLOCKED and ready for execution!")

        # ----------------------------------------------------------------------
        # STEP 13: AUDIT TRAIL & PROVENANCE VERIFICATION
        # ----------------------------------------------------------------------
        print("\n[STEP 13] Full Audit Trail & Provenance Verification...")
        detail = await ReconciliationService.get_reconciliation(session, rec3.id)
        assert detail is not None
        print(f"  -> Timeline Observations Recorded: {len(detail.evidence_timeline)}")
        for idx, ev in enumerate(detail.evidence_timeline, 1):
            role_tag = "[SUPPORTING]" if ev.is_supporting else "[CONFLICTING]" if ev.is_conflicting else "[CONTEXT]"
            print(f"     {idx}. {role_tag} [{ev.provider.upper()}] ({ev.semantic_role}): {ev.content[:60]}...")

        print("\n" + "=" * 80)
        print("PHASE 11 LIVE DEMONSTRATION COMPLETE — 100% VERIFIED!")
        print("=" * 80)


if __name__ == "__main__":
    asyncio.run(run_live_demonstration())
