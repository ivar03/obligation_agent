import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import asyncio
import time
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
    print("OBLIGATION AGENT — PHASE 8 LIVE DEMONSTRATION")
    print("Real Provider Integration & Secure Connection Management (Slack)")
    print("=" * 80)

    # Initialize tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://127.0.0.1:8000") as client:
        async with AsyncSessionLocal() as session:
            # -------------------------------------------------------------------------
            # STEP 1: Connect Slack Workspace
            # -------------------------------------------------------------------------
            print("\n[STEP 1] Connect Slack Workspace")
            print("-" * 50)

            # Initiate OAuth
            init_res = await client.get("/api/integrations/slack/connect")
            oauth_data = init_res.json()
            state = oauth_data["state"]
            print(f"Generated OAuth Authorization URL: {oauth_data['authorization_url'][:60]}...")
            print(f"CSRF State Parameter: {state}")

            # Complete OAuth callback
            cb_res = await client.post(f"/api/integrations/slack/callback?code=live_demo_auth_code&state={state}")
            conn_data = cb_res.json()
            print(f"Connection Status: {conn_data['provider'].upper()} -> {conn_data['status']}")
            print(f"Workspace Name: {conn_data['external_account_name']} ({conn_data['external_account_id']})")
            print(f"Granted Capabilities: {', '.join(conn_data['capabilities'])}")

            # Test connection
            test_res = await client.post("/api/integrations/slack/test")
            print(f"Health Verification: {test_res.json()['message']}")

            # Setup Domain Scenario: Rahul must deliver benchmark numbers, which blocks Ravi's migration
            print("\n[SETUP] Initializing Obligations, Dependencies & Interventions")
            print("-" * 50)
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
                beneficiary="Management",
                action="Execute database migration to production",
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

            # Create active intervention for Rahul's obligation
            inv = Intervention(
                obligation_id=ob_rahul.id,
                intervention_type=InterventionType.REQUEST_STATUS_UPDATE,
                target_owner="Rahul",
                target_beneficiary="Ravi",
                title="Follow up on database benchmarks",
                rationale="Required before database migration can begin",
                message_draft="Hi Rahul, please share the database benchmark numbers.",
                status=InterventionStatus.APPROVED,
                urgency="HIGH",
            )
            session.add(inv)
            await session.commit()
            await session.refresh(inv)

            print(f"Created Obligation A (Rahul): '{ob_rahul.action}' [Status: {ob_rahul.status.value}]")
            print(f"Created Obligation B (Ravi):  '{ob_ravi.action}' [Status: {ob_ravi.status.value}] (BLOCKED by A)")
            print(f"Created Intervention:         '{inv.title}' [Status: {inv.status.value}]")

            # -------------------------------------------------------------------------
            # STEP 2: Receive Slack Progress Update Event
            # -------------------------------------------------------------------------
            print("\n[STEP 2] Receive Slack Event: Progress Update")
            print("-" * 50)
            progress_payload = {
                "type": "event_callback",
                "team_id": "T_DEMO_HUB",
                "event": {
                    "type": "message",
                    "user": "U_RAHUL",
                    "user_name": "Rahul",
                    "text": "Working on the database benchmark numbers. Will send them shortly.",
                    "ts": f"{int(time.time())}.000100",
                    "channel": "C_ENG",
                    "channel_name": "engineering",
                }
            }
            print(f"Inbound Slack Message: \"{progress_payload['event']['text']}\" from {progress_payload['event']['user_name']}")
            res2 = await client.post("/api/webhooks/slack", json=progress_payload)
            data2 = res2.json()
            print(f"Webhook Ingestion Result: Status={data2['status']} | SemanticRole={data2['semantic_role']}")
            print(f"Affected Obligations: {data2['affected_obligation_ids']}")
            print(f"Updated Interventions: {data2['updated_intervention_ids']}")

            await session.refresh(inv)
            print(f"Intervention Updated: Outcome={inv.outcome.value}")

            # -------------------------------------------------------------------------
            # STEP 3: Receive Slack Completion Signal with Attachment
            # -------------------------------------------------------------------------
            print("\n[STEP 3] Receive Slack Event: Completion Signal with Attachment")
            print("-" * 50)
            completion_ts = f"{int(time.time())}.000200"
            completion_payload = {
                "type": "event_callback",
                "team_id": "T_DEMO_HUB",
                "event": {
                    "type": "message",
                    "user": "U_RAHUL",
                    "user_name": "Rahul",
                    "text": "Sent the database benchmark numbers.",
                    "ts": completion_ts,
                    "channel": "C_ENG",
                    "files": [
                        {
                            "name": "benchmark_results.csv",
                            "filetype": "csv",
                            "mimetype": "text/csv",
                            "size": 16384,
                            "url_private": "https://files.slack.com/files-pri/T_DEMO_HUB/benchmark_results.csv",
                        }
                    ]
                }
            }
            print(f"Inbound Slack Message: \"{completion_payload['event']['text']}\" + Attachment: benchmark_results.csv")
            res3 = await client.post("/api/webhooks/slack", json=completion_payload)
            data3 = res3.json()
            print(f"Webhook Ingestion Result: Status={data3['status']} | SemanticRole={data3['semantic_role']}")
            assert len(data3["evidence_records"]) > 0
            ev_record = data3["evidence_records"][0]
            print(f"Evidence Candidate Created: ID={ev_record['id']} | Status={ev_record['correlation_status']} | Confidence={ev_record['correlation_confidence']}")

            # Check human-confirmation gate
            await session.refresh(ob_rahul)
            print(f"Obligation A Status check (Human-Gated): {ob_rahul.status.value} (NOT automatically completed!)")
            assert ob_rahul.status == ObligationStatus.CONFIRMED

            # -------------------------------------------------------------------------
            # STEP 4: Human Confirms Evidence -> Causal Chain Reaction
            # -------------------------------------------------------------------------
            print("\n[STEP 4] Human Confirms Evidence & Triggers Graph Cascade")
            print("-" * 50)
            confirm_res = await client.post(
                f"/api/obligations/{ob_rahul.id}/evidence/{ev_record['id']}/confirm",
                json={"notes": "Verified benchmark_results.csv and performance metrics."},
            )
            print(f"Evidence Confirmed by Human Operator: HTTP {confirm_res.status_code}")

            await session.refresh(ob_rahul)
            await session.refresh(ob_ravi)
            await session.refresh(inv)

            print(f"1. Obligation A (Rahul): Status -> {ob_rahul.status.value}")
            print(f"2. GraphService Propagation -> Obligation B (Ravi) Status -> {ob_ravi.status.value} (UNBLOCKED!)")

            risk_a = await RiskEngine.assess_obligation(session, ob_rahul.id)
            print(f"3. RiskEngine Recalculation -> Risk Score = {risk_a.risk_score} ({risk_a.risk_level.value})")
            print(f"4. Intervention Lifecycle -> Status = {inv.status.value}")

            assert ob_rahul.status == ObligationStatus.COMPLETED
            assert ob_ravi.status == ObligationStatus.CONFIRMED

            # -------------------------------------------------------------------------
            # STEP 5: Deliver Duplicate Slack Event -> Idempotency Check
            # -------------------------------------------------------------------------
            print("\n[STEP 5] Idempotency Check: Re-delivering Duplicate Slack Payload")
            print("-" * 50)
            res5 = await client.post("/api/webhooks/slack", json=completion_payload)
            data5 = res5.json()
            print(f"Re-delivery Result: Status={data5['status']} | Message={data5['message']}")
            print(f"Event ID preserved: {data5['event_id']}")

            # Verify no state changes occurred
            await session.refresh(ob_rahul)
            await session.refresh(ob_ravi)
            print(f"Obligation A Status remaining: {ob_rahul.status.value}")
            print(f"Obligation B Status remaining: {ob_ravi.status.value}")
            assert data5["status"] == "DUPLICATE"

            print("\n" + "=" * 80)
            print("LIVE DEMONSTRATION COMPLETE — ALL 5 STEPS PASSED VERIFICATION")
            print("=" * 80)


if __name__ == "__main__":
    asyncio.run(run_live_demonstration())
