import httpx
import json
import time

BASE_URL = "http://127.0.0.1:8000"

def log_step(step: str, detail: str = ""):
    print(f"\n========================================\n[STEP] {step}")
    if detail:
        print(detail)
    print("========================================")

def main():
    print("=== STARTING PHASE 7 LIVE CAUSAL E2E DEMONSTRATION ===")
    with httpx.Client(base_url=BASE_URL, timeout=30.0) as client:
        # 1. Health & Providers
        log_step("1. Checking Server Health and Provider Registry")
        h_res = client.get("/api/health")
        print(f"Health: {h_res.status_code} -> {h_res.json()}")
        assert h_res.status_code == 200

        prov_res = client.get("/api/events/providers")
        print(f"Providers ({len(prov_res.json())}): {prov_res.json()}")
        assert prov_res.status_code == 200
        assert any(p["name"] == "mock" for p in prov_res.json())

        # 2. Create Prerequisite & Dependent Obligations
        log_step("2. Creating Prerequisite & Dependent Obligations for Graph Ingestion Flow")
        prereq_res = client.post("/api/obligations", json={
            "owner": "Rahul",
            "beneficiary": "Ravi",
            "action": "Deliver database performance telemetry",
            "obligation_type": "OWED_TO_ME",
            "status": "CONFIRMED",
        })
        prereq = prereq_res.json()
        print(f"Prereq Created: ID={prereq['id']} Action='{prereq['action']}' Status={prereq['status']}")

        dep_res = client.post("/api/obligations", json={
            "owner": "Ravi",
            "beneficiary": "Executive Team",
            "action": "Publish executive performance briefing",
            "obligation_type": "OWED_BY_ME",
            "status": "CONFIRMED",
        })
        dep = dep_res.json()
        print(f"Dependent Created: ID={dep['id']} Action='{dep['action']}' Status={dep['status']}")

        # Add Edge
        edge_res = client.post("/api/obligations/edges", json={
            "from_obligation_id": dep["id"],
            "to_obligation_id": prereq["id"],
            "edge_type": "DEPENDS_ON",
        })
        print(f"Edge Created: {edge_res.json()['edge_type']}")

        # Dependent should now be BLOCKED
        dep_check = client.get(f"/api/obligations/{dep['id']}").json()
        print(f"Dependent Status After Edge: {dep_check['status']} (Expected: BLOCKED)")
        assert dep_check["status"] == "BLOCKED"

        # 3. Plan & Execute Intervention
        log_step("3. Planning & Executing Intervention on Prerequisite Obligation")
        inv_plan_res = client.post("/api/interventions/plan", json={
            "obligation_id": prereq["id"],
            "force": True,
        })
        inv = inv_plan_res.json()
        print(f"Intervention Planned: ID={inv['id']} Urgency={inv['urgency']} Status={inv['status']}")

        # Approve & Execute
        client.post(f"/api/interventions/{inv['id']}/approve", json={"approved_by": "Ravi"})
        exec_res = client.post(f"/api/interventions/{inv['id']}/execute")
        executed_inv = exec_res.json()
        print(f"Intervention Executed: Status={executed_inv['status']} Ref={executed_inv['execution_reference']}")
        assert executed_inv["status"] == "EXECUTED"

        # Generate dynamic timestamped refs for this run
        run_id = int(time.time())
        prog_ref = f"msg_prog_live_{run_id}"
        comp_ref = f"msg_comp_live_{run_id}"

        # 4. Ingest Progress Event
        log_step("4. Ingesting Progress Event from Mock Provider")
        prog_res = client.post("/api/events/ingest", json={
            "provider": "mock",
            "payload": {
                "content": "Working on the database performance telemetry now. Analyzing clusters.",
                "sender": "Rahul",
                "recipients": ["Ravi"],
                "source_ref": prog_ref,
            }
        })
        prog_data = prog_res.json()
        print(f"Progress Ingestion Result: Status={prog_data['status']} Role={prog_data['semantic_role']}")
        print(f"Updated Interventions: {prog_data['updated_intervention_ids']}")
        assert prog_data["status"] == "PROCESSED"
        assert prog_data["semantic_role"] == "PROGRESS_UPDATE"
        assert inv["id"] in prog_data["updated_intervention_ids"]

        # Verify Intervention State Changed to ACKNOWLEDGED
        inv_check = client.get(f"/api/interventions/{inv['id']}").json()
        print(f"Intervention Status After Progress: Status={inv_check['status']} Outcome={inv_check['outcome']}")
        assert inv_check["status"] == "ACKNOWLEDGED"
        assert inv_check["outcome"] == "PROGRESS_REPORTED"

        # 5. Test Deduplication
        log_step("5. Ingesting Duplicate Event with Same Provider + source_ref")
        dup_res = client.post("/api/events/ingest", json={
            "provider": "mock",
            "payload": {
                "content": "Working on the database performance telemetry now. Analyzing clusters.",
                "sender": "Rahul",
                "recipients": ["Ravi"],
                "source_ref": prog_ref,
            }
        })
        dup_data = dup_res.json()
        print(f"Duplicate Result: Status={dup_data['status']} Message='{dup_data['message']}'")
        assert dup_data["status"] == "DUPLICATE"

        # 6. Ingest Completion Signal Event
        log_step("6. Ingesting Completion Signal Event from Mock Provider")
        comp_res = client.post("/api/events/ingest", json={
            "provider": "mock",
            "payload": {
                "content": "Delivered database performance telemetry in the shared storage bucket.",
                "sender": "Rahul",
                "recipients": ["Ravi"],
                "source_ref": comp_ref,
            }
        })
        comp_data = comp_res.json()
        print(f"Completion Ingestion Result: Status={comp_data['status']} Role={comp_data['semantic_role']}")
        print(f"Evidence Generated Count: {len(comp_data['evidence_records'])}")
        assert comp_data["status"] == "PROCESSED"
        assert comp_data["semantic_role"] == "COMPLETION_SIGNAL"
        assert len(comp_data["evidence_records"]) >= 1
        evidence_rec = next(e for e in comp_data["evidence_records"] if e["obligation_id"] == prereq["id"])
        evidence_id = evidence_rec["id"]
        print(f"Evidence ID: {evidence_id} Status: {evidence_rec['correlation_status']}")
        assert evidence_rec["correlation_status"] == "SUGGESTED"

        # Obligation must NOT be completed automatically
        prereq_mid = client.get(f"/api/obligations/{prereq['id']}").json()
        print(f"Prereq Status Before Human Confirmation: {prereq_mid['status']} (Expected: NOT completed)")
        assert prereq_mid["status"] != "COMPLETED"

        # 7. Human Confirms Evidence & Unblocks Graph
        log_step("7. Human Confirms Evidence -> Completes Obligation & Unblocks Dependent")
        confirm_res = client.post(f"/api/obligations/{prereq['id']}/evidence/{evidence_id}/confirm", json={
            "notes": "Verified telemetry files in storage bucket."
        })
        print(f"Confirmation Response: {confirm_res.status_code}")
        assert confirm_res.status_code == 200

        prereq_final = client.get(f"/api/obligations/{prereq['id']}").json()
        dep_final = client.get(f"/api/obligations/{dep['id']}").json()
        print(f"Prerequisite Final Status: {prereq_final['status']} (Expected: COMPLETED)")
        print(f"Dependent Final Status: {dep_final['status']} (Expected: CONFIRMED / UNBLOCKED)")
        assert prereq_final["status"] == "COMPLETED"
        assert dep_final["status"] == "CONFIRMED"

        # 8. Query Ingested Event Audit Feed & Details
        log_step("8. Querying Event Activity Feed and Inspecting Audit Details")
        list_res = client.get("/api/events?provider=mock&limit=10")
        list_data = list_res.json()
        print(f"Total Audit Events Logged: {list_data['total']}")
        assert list_data["total"] >= 2

        first_event_id = comp_data["event_id"]
        detail_res = client.get(f"/api/events/{first_event_id}")
        detail_data = detail_res.json()
        print(f"Event Audit Detail for ID={first_event_id}:")
        print(f"  - Provider: {detail_data['provider']}")
        print(f"  - Semantic Role: {detail_data['semantic_role']}")
        print(f"  - Action Taken: {detail_data['action_taken']}")
        print(f"  - Correlated Obligation: {detail_data['correlated_obligation_id']}")
        print(f"  - Evidence Record: {detail_data['evidence_id']}")
        assert detail_data["id"] == first_event_id
        assert detail_data["semantic_role"] == "COMPLETION_SIGNAL"

        print("\n=== PHASE 7 LIVE CAUSAL E2E DEMONSTRATION SUCCEEDED 100%! ===")

if __name__ == "__main__":
    main()
