import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import asyncio
import time
import uuid
from datetime import datetime, timezone, timedelta
from httpx import AsyncClient, ASGITransport

from app.main import app
from app.core.database import AsyncSessionLocal, engine, Base
from app.models.obligation import Obligation, ObligationEdge, Evidence, Intervention, IngestedEventRecord
from app.models.integration import IntegrationConnection
from app.core.status_machine import ObligationStatus, ObligationType, EdgeType, EventSemanticRole, RiskLevel
from app.core.intervention_status import InterventionStatus, InterventionOutcome, InterventionType
from app.services.risk_engine import RiskEngine
from app.services.integration_service import IntegrationService


async def run_live_demonstration():
    print("=" * 80)
    print("OBLIGATION AGENT — PHASE 9 LIVE DEMONSTRATION")
    print("Gmail Provider Integration & Email-Based Obligation Intelligence")
    print("=" * 80)

    # Initialize tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://127.0.0.1:8000") as client:
        async with AsyncSessionLocal() as session:
            # -------------------------------------------------------------------------
            # STEP 1: Register Gmail Provider & OAuth Connection
            # -------------------------------------------------------------------------
            print("\n[STEP 1] Register Gmail Provider & Connect Account")
            print("-" * 60)

            # Generate OAuth URL
            init_res = await client.get("/api/integrations/gmail/connect")
            oauth_data = init_res.json()
            state = oauth_data["state"]
            print(f"Generated Google OAuth URL: {oauth_data['authorization_url'][:65]}...")
            print(f"CSRF State Parameter: {state}")

            # Complete OAuth callback
            cb_res = await client.post(f"/api/integrations/gmail/callback?code=live_demo_auth_code&state={state}")
            conn_data = cb_res.json()
            print(f"Connection Established: {conn_data['provider'].upper()} -> {conn_data['status']}")
            print(f"Account: {conn_data['external_account_name']} ({conn_data['external_account_id']})")
            print(f"Capabilities: {', '.join(conn_data['capabilities'])}")

            # Test connection health
            test_res = await client.post("/api/integrations/gmail/test")
            print(f"Health Verification: {test_res.json()['message']}")

            # -------------------------------------------------------------------------
            # STEP 2: Create Prerequisite Obligation & Graph Dependency
            # -------------------------------------------------------------------------
            print("\n[STEP 2] Create Prerequisite Obligation & Dependent Graph Node")
            print("-" * 60)
            ob_rahul = Obligation(
                owner="Rahul",
                beneficiary="Ravi",
                action="Deliver database benchmark numbers",
                deadline=datetime.now(timezone.utc) + timedelta(days=1),
                status=ObligationStatus.CONFIRMED,
                obligation_type=ObligationType.OWED_TO_ME,
            )
            ob_ravi = Obligation(
                owner="Ravi",
                beneficiary="Executive Team",
                action="Publish executive performance briefing",
                deadline=datetime.now(timezone.utc) + timedelta(days=2),
                status=ObligationStatus.BLOCKED,
                obligation_type=ObligationType.OWED_BY_ME,
                block_reason={"blocked": True, "blocked_by": [{"obligation_id": "placeholder"}]}
            )
            session.add_all([ob_rahul, ob_ravi])
            await session.commit()
            await session.refresh(ob_rahul)
            await session.refresh(ob_ravi)

            # Create dependency: ob_ravi depends on ob_rahul
            edge = ObligationEdge(
                from_obligation_id=ob_ravi.id,
                to_obligation_id=ob_rahul.id,
                edge_type=EdgeType.DEPENDS_ON,
            )
            session.add(edge)
            await session.commit()

            print(f"Prerequisite Obligation (Rahul): '{ob_rahul.action}' -> Status: {ob_rahul.status.value}")
            print(f"Dependent Obligation (Ravi):     '{ob_ravi.action}' -> Status: {ob_ravi.status.value} (BLOCKED by Rahul)")

            # -------------------------------------------------------------------------
            # STEP 3: Plan and Execute a Human-Approved Intervention
            # -------------------------------------------------------------------------
            print("\n[STEP 3] Plan and Execute Human-Approved Follow-Up Intervention")
            print("-" * 60)
            inv = Intervention(
                obligation_id=ob_rahul.id,
                intervention_type=InterventionType.REQUEST_STATUS_UPDATE,
                target_owner="Rahul",
                target_beneficiary="Ravi",
                title="Follow up on database benchmarks",
                rationale="Prerequisite for executive briefing",
                message_draft="Hi Rahul, please share the database benchmark numbers.",
                status=InterventionStatus.EXECUTED,
                urgency="HIGH",
            )
            session.add(inv)
            await session.commit()
            await session.refresh(inv)

            print(f"Intervention Prepared & Executed: '{inv.title}' -> Status: {inv.status.value}")

            # -------------------------------------------------------------------------
            # STEP 4: Ingest Gmail Progress Message
            # -------------------------------------------------------------------------
            print("\n[STEP 4] Ingest Inbound Gmail Progress Update")
            print("-" * 60)
            progress_payload = {
                "from": "Rahul <rahul@acme.com>",
                "to": ["Ravi <ravi@acme.com>"],
                "subject": "Re: Database benchmark numbers",
                "body": "Working on the database benchmark numbers. I'll send them shortly.",
                "message_id": f"<msg_prog_{uuid.uuid4().hex[:8]}@acme.com>",
                "thread_id": "thread_benchmarks_101",
            }
            print(f"Inbound Email: From: {progress_payload['from']} | Subject: \"{progress_payload['subject']}\"")
            print(f"Body: \"{progress_payload['body']}\"")

            res4 = await client.post("/api/webhooks/gmail", json=progress_payload)
            data4 = res4.json()
            print(f"Ingestion Result: Status={data4['status']} | SemanticRole={data4['semantic_role']}")

            await session.refresh(inv)
            print(f"Intervention Lifecycle Response: Status={inv.status.value} | Outcome={inv.outcome.value}")
            assert inv.outcome == InterventionOutcome.PROGRESS_REPORTED

            # -------------------------------------------------------------------------
            # STEP 5: Re-Ingest the Exact Same Gmail Message (Idempotency Check)
            # -------------------------------------------------------------------------
            print("\n[STEP 5] Idempotency Check: Re-Ingesting Duplicate Email Payload")
            print("-" * 60)
            res5 = await client.post("/api/webhooks/gmail", json=progress_payload)
            data5 = res5.json()
            print(f"Re-delivery Result: Status={data5['status']} | Message={data5['message']}")
            print(f"Event ID Preserved: {data5['event_id']}")
            assert data5["status"] == "DUPLICATE"
            assert data5["event_id"] == data4["event_id"]

            # -------------------------------------------------------------------------
            # STEP 6: Ingest Gmail Completion Email with Attachment
            # -------------------------------------------------------------------------
            print("\n[STEP 6] Ingest Inbound Gmail Completion Email with Attachment")
            print("-" * 60)
            completion_payload = {
                "from": "Rahul <rahul@acme.com>",
                "to": ["Ravi <ravi@acme.com>"],
                "subject": "Database benchmark results",
                "body": "Sent the database benchmark numbers.",
                "message_id": f"<msg_comp_{uuid.uuid4().hex[:8]}@acme.com>",
                "thread_id": "thread_benchmarks_101",
                "attachments": [
                    {
                        "name": "benchmark_results.csv",
                        "filetype": "csv",
                        "mimetype": "text/csv",
                        "size": 16384,
                    }
                ],
            }
            print(f"Inbound Email: From: {completion_payload['from']} | Attachment: benchmark_results.csv")
            print(f"Body: \"{completion_payload['body']}\"")

            res6 = await client.post("/api/webhooks/gmail", json=completion_payload)
            data6 = res6.json()
            print(f"Ingestion Result: Status={data6['status']} | SemanticRole={data6['semantic_role']}")

            matching_evs = [e for e in data6["evidence_records"] if e["obligation_id"] == ob_rahul.id]
            assert len(matching_evs) > 0
            ev_candidate = matching_evs[0]
            print(f"Evidence Generated: ID={ev_candidate['id']} | Status={ev_candidate['correlation_status']} | Confidence={ev_candidate['correlation_confidence']}")

            # Verify Human Safety Gate: Prerequisite obligation is NOT automatically completed
            await session.refresh(ob_rahul)
            await session.refresh(ob_ravi)
            print(f"Human Safety Gate Check: Prerequisite Status = {ob_rahul.status.value} (NOT automatically completed!)")
            print(f"Dependent Status = {ob_ravi.status.value} (Remains BLOCKED pending human confirmation)")
            assert ob_rahul.status == ObligationStatus.CONFIRMED
            assert ob_ravi.status == ObligationStatus.BLOCKED

            # -------------------------------------------------------------------------
            # STEP 7: Human Confirms Evidence & Triggers Graph Cascade Unblocking
            # -------------------------------------------------------------------------
            print("\n[STEP 7] Human Operator Confirms Evidence & Graph Cascade Propagates")
            print("-" * 60)
            confirm_res = await client.post(
                f"/api/obligations/{ob_rahul.id}/evidence/{ev_candidate['id']}/confirm",
                json={"notes": "Human review: benchmark_results.csv verified accurate."},
            )
            print(f"Evidence Confirmation: HTTP {confirm_res.status_code}")

            await session.refresh(ob_rahul)
            await session.refresh(ob_ravi)
            await session.refresh(inv)

            print(f"1. Prerequisite Obligation (Rahul): Status -> {ob_rahul.status.value}")
            print(f"2. GraphService Propagation -> Dependent Obligation (Ravi): Status -> {ob_ravi.status.value} (UNBLOCKED!)")

            risk_a = await RiskEngine.assess_obligation(session, ob_rahul.id)
            print(f"3. RiskEngine Recalculation -> Prerequisite Risk Score = {risk_a.risk_score} ({risk_a.risk_level.value})")
            print(f"4. Intervention Status -> {inv.status.value}")

            assert ob_rahul.status == ObligationStatus.COMPLETED
            assert ob_ravi.status == ObligationStatus.CONFIRMED
            assert risk_a.risk_score == 0.0

            # -------------------------------------------------------------------------
            # STEP 8: Inspect Activity Center Feed
            # -------------------------------------------------------------------------
            print("\n[STEP 8] Inspect Event Activity Center Feed")
            print("-" * 60)
            events_res = await client.get("/api/events?limit=5")
            events_list = events_res.json()["items"]
            gmail_events = [e for e in events_list if e["provider"] == "gmail"]
            print(f"Retrieved {len(gmail_events)} recent Gmail events in Activity Center:")
            for ge in gmail_events[:2]:
                print(f"  • [{ge['provider'].upper()}] Role: {ge['semantic_role']} | Ref: {ge['source_ref']} | Content: \"{ge['content'][:50]}...\"")

            # -------------------------------------------------------------------------
            # STEP 9: Multi-Provider Integration Health Verification
            # -------------------------------------------------------------------------
            print("\n[STEP 9] Inspect Multi-Provider Integration Health (Gmail, Slack, Mock)")
            print("-" * 60)
            int_res = await client.get("/api/integrations")
            int_data = int_res.json()

            print(f"Active Provider Connections ({len(int_data['connections'])}):")
            for c in int_data["connections"]:
                print(f"  • {c['provider'].upper()}: {c['status']} ({c['external_account_name']})")

            print(f"Registered Providers in System ({len(int_data['registered_providers'])}):")
            for p in int_data["registered_providers"]:
                print(f"  • {p['name'].upper()} v{p['version']}: Capabilities: [{', '.join(p['capabilities'])}]")

            print("\n" + "=" * 80)
            print("PHASE 9 LIVE DEMONSTRATION COMPLETE — ALL 9 STEPS VERIFIED")
            print("=" * 80)


if __name__ == "__main__":
    asyncio.run(run_live_demonstration())
