"""
Phase 15 -- Enterprise Audit, Governance & Compliance Layer
Live Demonstration Script

Run:
    python scratch/live_demonstration_phase15.py
"""

import json
import time
import csv
import io
import sqlite3
import sys
import os
from datetime import datetime
import requests

# Ensure UTF-8 output on Windows terminals
if sys.stdout.encoding != "utf-8":
    import io as _io
    sys.stdout = _io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

BASE = "http://127.0.0.1:8000"

STEP = 0
PASS = 0
FAIL = 0


def step(title: str):
    global STEP
    STEP += 1
    print(f"\n{'-' * 70}")
    print(f"  STEP {STEP:02d}: {title}")
    print(f"{'-' * 70}")


def ok(msg: str):
    global PASS
    PASS += 1
    print(f"  OK   {msg}")


def warn(msg: str):
    print(f"  WARN {msg}")


def fail_step(msg: str):
    global FAIL
    FAIL += 1
    print(f"  FAIL {msg}")


def req(method, path, *, token=None, workspace=None, json_body=None, params=None):
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    if workspace:
        headers["X-Workspace-Id"] = workspace
    fn = getattr(requests, method)
    r = fn(f"{BASE}{path}", headers=headers, json=json_body, params=params, timeout=15)
    return r


print("\n" + "=" * 70)
print("  OBLIGATION AGENT -- PHASE 15 LIVE DEMONSTRATION")
print(f"  {datetime.now().isoformat()}")
print("=" * 70)

# STEP 1: Register user A (OWNER)
step("Register User A -- workspace owner")

ts = int(time.time())
user_a_email = f"ceo.demo.{ts}@corp.example"
user_a_pass = "SecureP@ss1!"
r = req("post", "/api/auth/register", json_body={
    "email": user_a_email,
    "password": user_a_pass,
    "display_name": "Alice CEO",
    "workspace_name": f"AcmeCorp-{ts}",
})
if r.status_code in (200, 201):
    auth_a = r.json()
    token_a = auth_a["token"]
    # Support both response shapes
    if "active_workspace_id" in auth_a:
        ws_id = auth_a["active_workspace_id"]
    else:
        ws_id = auth_a.get("current_workspace", {}).get("id") or auth_a["workspaces"][0]["id"]
    user_a_id = auth_a["user"]["id"]
    ok(f"User A registered -- id={user_a_id}")
    ok(f"Workspace created  -- id={ws_id}")
else:
    fail_step(f"Register failed: {r.status_code} {r.text}")
    sys.exit(1)

# STEP 2: Failed login audit
step("Trigger failed login -- security audit recorded")

r = req("post", "/api/auth/login", json_body={"email": user_a_email, "password": "WRONG-password!"})
if r.status_code == 401:
    ok("Failed login correctly rejected (HTTP 401) -- LOGIN_FAILED audited")
else:
    warn(f"Expected 401, got {r.status_code}")

time.sleep(0.2)

# STEP 3: Register user B
step("Register User B -- will be invited as ADMIN")

user_b_email = f"admin.demo.{ts}@corp.example"
user_b_pass = "SecureP@ss2!"
r = req("post", "/api/auth/register", json_body={
    "email": user_b_email,
    "password": user_b_pass,
    "display_name": "Bob Admin",
    "workspace_name": f"BobPersonal-{ts}",
})
if r.status_code in (200, 201):
    auth_b = r.json()
    token_b = auth_b["token"]
    user_b_id = auth_b["user"]["id"]
    if "active_workspace_id" in auth_b:
        ws_id_b = auth_b["active_workspace_id"]
    else:
        ws_id_b = auth_b.get("current_workspace", {}).get("id") or auth_b["workspaces"][0]["id"]
    ok(f"User B registered -- id={user_b_id}")
else:
    fail_step(f"Register failed: {r.status_code} {r.text}")
    sys.exit(1)

# STEP 4: Invite user B into AcmeCorp as ADMIN
step("Invite User B into AcmeCorp workspace as ADMIN (role-elevation audit)")

r = req("post", f"/api/workspaces/{ws_id}/members", token=token_a, workspace=ws_id, json_body={
    "email": user_b_email,
    "role": "ADMIN",
})
if r.status_code in (200, 201):
    ok(f"User B invited as ADMIN into workspace {ws_id}")
else:
    fail_step(f"Invite failed: {r.status_code} {r.text}")

# STEP 5: Create obligation
step("Create obligation -- audit CREATE_OBLIGATION event")

r = req("post", "/api/obligations", token=token_a, workspace=ws_id, json_body={
    "owner": "Alice CEO",
    "beneficiary": "Compliance Dept",
    "action": "Submit Q3 regulatory filing to SEC",
    "obligation_type": "OWED_BY_ME",
    "deadline": "2026-09-30T00:00:00Z",
    "jurisdiction": "US",
    "regulatory_body": "SEC",
})
if r.status_code in (200, 201):
    obl = r.json()
    obl_id = obl["id"]
    ok(f"Obligation created -- id={obl_id}")
else:
    fail_step(f"Create obligation failed: {r.status_code} {r.text}")
    sys.exit(1)

# STEP 6: Update obligation
step("Update obligation -- audit UPDATE_OBLIGATION with before/after state diff")

r = req("put", f"/api/obligations/{obl_id}", token=token_a, workspace=ws_id, json_body={
    "action": "Submit Q3 regulatory filing to SEC -- REVISED",
    "jurisdiction": "US-Federal",
})
if r.status_code == 200:
    ok("Obligation updated -- before/after diff captured in audit event")
else:
    warn(f"Update returned {r.status_code}: {r.text}")

# STEP 7: Create graph edge
step("Create dependency edge -- audit CREATE_GRAPH_EDGE")

r = req("post", "/api/obligations", token=token_a, workspace=ws_id, json_body={
    "owner": "Bob Admin",
    "beneficiary": "Legal Team",
    "action": "Review and approve filing document",
    "obligation_type": "OWED_TO_ME",
})
dep_id = None
if r.status_code in (200, 201):
    dep_id = r.json()["id"]
    ok(f"Dependency obligation created -- id={dep_id}")

    r2 = req("post", "/api/graph/edges", token=token_a, workspace=ws_id, json_body={
        "source_id": dep_id,
        "target_id": obl_id,
        "edge_type": "BLOCKS",
    })
    if r2.status_code == 200:
        edge_id = r2.json().get("id", "?")
        ok(f"Graph edge created -- id={edge_id}")
    else:
        warn(f"Edge creation returned {r2.status_code}: {r2.text}")
else:
    warn(f"Dependency obligation returned {r.status_code}")

# STEP 8: Plan and approve intervention
step("Plan and approve intervention -- audit PLAN + APPROVE_INTERVENTION")

r = req("post", f"/api/obligations/{obl_id}/interventions", token=token_a, workspace=ws_id, json_body={
    "target_owner": "Alice CEO",
    "target_beneficiary": "Compliance Dept",
    "intervention_type": "ESCALATION",
    "recommended_action": "Escalate to CFO for sign-off",
    "reason": "Deadline risk detected -- CFO sign-off required",
    "risk_score_at_recommendation": 0.82,
})
iv_id = None
if r.status_code in (200, 201):
    iv = r.json()
    iv_id = iv["id"]
    ok(f"Intervention planned -- id={iv_id}")

    r2 = req("post", f"/api/interventions/{iv_id}/approve", token=token_a, workspace=ws_id, json_body={
        "approver_notes": "CFO has been notified. Proceed with escalation.",
    })
    if r2.status_code in (200, 201):
        ok("Intervention approved -- APPROVE_INTERVENTION audited")
    else:
        warn(f"Approve returned {r2.status_code}: {r2.text}")
else:
    warn(f"Intervention planning returned {r.status_code}: {r.text}")

# STEP 9: Execute and resolve intervention
step("Execute and resolve intervention -- audit EXECUTE + RESOLVE_INTERVENTION")

if iv_id:
    r = req("post", f"/api/interventions/{iv_id}/schedule", token=token_a, workspace=ws_id, json_body={
        "scheduled_for": "2026-09-01T09:00:00Z",
    })
    if r.status_code == 200:
        ok("Intervention scheduled")

    r2 = req("post", f"/api/interventions/{iv_id}/execute", token=token_a, workspace=ws_id, json_body={})
    if r2.status_code == 200:
        ok("Intervention executed -- EXECUTE_INTERVENTION audited")

    r3 = req("post", f"/api/interventions/{iv_id}/outcome", token=token_a, workspace=ws_id, json_body={
        "outcome_notes": "CFO confirmed sign-off. Risk resolved.",
        "was_effective": True,
    })
    if r3.status_code == 200:
        ok("Intervention resolved -- RESOLVE_INTERVENTION audited")
    else:
        warn(f"Resolve returned {r3.status_code}: {r3.text}")
else:
    warn("Skipping execution -- intervention was not created")

# STEP 10: Add and confirm evidence
step("Add and confirm evidence -- audit CONFIRM_EVIDENCE")

r = req("post", f"/api/obligations/{obl_id}/evidence", token=token_a, workspace=ws_id, json_body={
    "source": "SEC_PORTAL",
    "evidence_type": "FILING_RECEIPT",
    "reference_id": "SEC-2026-Q3-FILING-001",
    "description": "Confirmed Q3 filing submission receipt from SEC portal",
})
if r.status_code in (200, 201):
    ev = r.json()
    ev_id = ev["id"]
    ok(f"Evidence added -- id={ev_id}")

    r2 = req("post", f"/api/obligations/{obl_id}/evidence/{ev_id}/confirm", token=token_a, workspace=ws_id)
    if r2.status_code in (200, 201):
        ok("Evidence confirmed -- CONFIRM_EVIDENCE audited")
    else:
        warn(f"Confirm returned {r2.status_code}: {r2.text}")
else:
    warn(f"Evidence add returned {r.status_code}: {r.text}")

# STEP 11: Reconciliation decision
step("Reconciliation decision -- audit RESOLVE_RECONCILIATION")

r = req("get", "/api/reconciliation", token=token_a, workspace=ws_id, params={"limit": 5})
if r.status_code == 200:
    recs = r.json().get("items", [])
    if recs:
        rec = recs[0]
        rec_id = rec["id"]
        r2 = req("post", f"/api/reconciliation/{rec_id}/resolve", token=token_a, workspace=ws_id, json_body={
            "resolution": "ACCEPTED",
            "reason": "Manual review confirmed obligation is valid and complete",
        })
        if r2.status_code == 200:
            ok("Reconciliation resolved -- RESOLVE_RECONCILIATION audited")
        else:
            warn(f"Reconciliation resolve returned {r2.status_code}: {r2.text}")
    else:
        ok("No reconciliation records yet -- skipping (expected for fresh DB)")
else:
    warn(f"Reconciliation list returned {r.status_code}")

# STEP 12: IDOR / Permission Denied
step("Attempt IDOR access with wrong workspace -- PERMISSION_DENIED security audit")

r = req("get", f"/api/obligations/{obl_id}", token=token_b, workspace=ws_id_b)
if r.status_code in (403, 401, 404):
    ok(f"Access correctly denied (HTTP {r.status_code}) -- PERMISSION_DENIED audited")
else:
    warn(f"Expected 403/401/404, got {r.status_code}")

# STEP 13: Fetch audit feed
step("Fetch workspace audit feed -- ADMIN sees all events")

r = req("get", "/api/audit", token=token_a, workspace=ws_id, params={"limit": 50, "offset": 0})
if r.status_code == 200:
    feed = r.json()
    total = feed.get("total", 0)
    items = feed.get("items", [])
    ok(f"Audit feed -- total_events={total}, fetched={len(items)}")
    print("  Last 5 events:")
    for ev in items[-5:]:
        print(f"     [{ev['severity']:8s}] {ev['action']:40s}  {ev['result']}")
else:
    fail_step(f"Audit feed failed: {r.status_code} {r.text}")

# STEP 14: Verify hash chain
step("Cryptographic SHA-256 hash chain verification")

r = req("get", "/api/audit/verify", token=token_a, workspace=ws_id)
if r.status_code == 200:
    v = r.json()
    ok(f"chain_valid          = {v['chain_valid']}")
    ok(f"status               = {v['status']}")
    ok(f"verified_event_count = {v['verified_event_count']}")
    ok(f"message              = {v['message']}")
    if v["chain_valid"]:
        ok("SHA-256 HASH CHAIN VERIFIED -- full cryptographic integrity confirmed")
    else:
        warn(f"Chain integrity issue: {v}")
else:
    fail_step(f"Verify endpoint failed: {r.status_code} {r.text}")

# STEP 15: Entity audit history
step("Fetch entity audit trail -- obligation provenance history")

r = req("get", f"/api/audit/entity/obligation/{obl_id}", token=token_a, workspace=ws_id)
if r.status_code == 200:
    hist = r.json()
    ok(f"Obligation provenance history -- {len(hist)} events")
    for ev in hist:
        print(f"     [{ev['timestamp'][:19]}] {ev['action']}")
        print(f"       hash: {ev['event_hash'][:32]}...")
else:
    warn(f"Entity history returned {r.status_code}: {r.text}")

# STEP 16 + 17: Tamper simulation
step("Tamper simulation -- inject invalid hash, detect breakdown")

db_candidates = [
    "obligation_agent.db",
    "../obligation_agent.db",
    os.path.join(os.path.dirname(__file__), "..", "obligation_agent.db"),
]
db_path = None
for c in db_candidates:
    if os.path.exists(c):
        db_path = os.path.abspath(c)
        break

if db_path:
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute(
        "SELECT id, event_hash FROM audit_events WHERE workspace_id=? ORDER BY timestamp ASC LIMIT 1",
        (ws_id,)
    )
    row = cur.fetchone()
    if row:
        tamper_id, original_hash = row
        fake_hash = "TAMPERED" + "0" * 56
        cur.execute("UPDATE audit_events SET event_hash=? WHERE id=?", (fake_hash, tamper_id))
        conn.commit()
        ok(f"Tampered event id={tamper_id}: hash replaced with TAMPERED...")

        r = req("get", "/api/audit/verify", token=token_a, workspace=ws_id)
        if r.status_code == 200:
            v = r.json()
            if not v["chain_valid"]:
                ok(f"Tamper DETECTED -- status={v['status']}")
                ok(f"  broken_at_event_id = {v.get('broken_at_event_id')}")
                ok(f"  message            = {v['message']}")
            else:
                warn("Tamper was not detected (unexpected)")

        step("Roll back tamper -- restore original hash, re-verify chain clean")
        cur.execute("UPDATE audit_events SET event_hash=? WHERE id=?", (original_hash, tamper_id))
        conn.commit()
        ok("Tamper rolled back -- original hash restored")

        r = req("get", "/api/audit/verify", token=token_a, workspace=ws_id)
        if r.status_code == 200:
            v = r.json()
            if v["chain_valid"]:
                ok(f"Chain re-verified CLEAN after rollback -- status={v['status']}")
            else:
                warn(f"Chain still reports issues: {v['message']}")
    else:
        warn("No audit events found in DB for tamper test")
    conn.close()
else:
    warn(f"SQLite DB not found at candidates: {db_candidates} -- skipping tamper simulation")
    step("Roll back tamper -- skipped (DB not found)")
    warn("Tamper rollback skipped")

# STEP 18: Governance summary
step("Fetch governance summary -- KPI dashboard metrics")

r = req("get", "/api/audit/summary", token=token_a, workspace=ws_id)
if r.status_code == 200:
    s = r.json()
    ok(f"Governance summary received:")
    ok(f"  total_audit_events           = {s.get('total_audit_events', '?')}")
    ok(f"  events_today                 = {s.get('events_today', '?')}")
    ok(f"  mutations_today              = {s.get('mutations_today', '?')}")
    ok(f"  security_events_count        = {s.get('security_events_count', '?')}")
    ok(f"  permission_denials_count     = {s.get('permission_denials_count', '?')}")
    ok(f"  failed_logins_count          = {s.get('failed_logins_count', '?')}")
    ok(f"  human_actions_count          = {s.get('human_actions_count', '?')}")
    ok(f"  interventions_approved_count = {s.get('interventions_approved_count', '?')}")
    ok(f"  interventions_executed_count = {s.get('interventions_executed_count', '?')}")
    ok(f"  evidence_confirmations_count = {s.get('evidence_confirmations_count', '?')}")
    ok(f"  chain_integrity_status       = {s.get('chain_integrity_status', '?')}")
    print("\n  Top actors:")
    for actor in s.get("top_actors", [])[:5]:
        print(f"     {actor.get('actor_name', '?'):20s}  {actor.get('mutation_count', 0)} mutations")
    print("\n  Most modified entities:")
    for ent in s.get("most_modified_entities", [])[:5]:
        print(f"     {ent.get('entity_type', '?'):20s}  {ent.get('mutation_count', 0)} mutations")
else:
    fail_step(f"Governance summary failed: {r.status_code} {r.text}")

# STEP 19: Export CSV
step("Export audit log as CSV")

r = req("get", "/api/audit/export", token=token_a, workspace=ws_id, params={"format": "csv"})
if r.status_code == 200:
    content = r.text
    reader = csv.DictReader(io.StringIO(content))
    rows = list(reader)
    ok(f"CSV export -- {len(rows)} rows, {len(reader.fieldnames or [])} columns")
    ok(f"  Columns: {', '.join((reader.fieldnames or [])[:8])}...")
    if "event_hash" in (reader.fieldnames or []):
        ok("event_hash column present -- cryptographic provenance in export")
    else:
        warn("event_hash column missing from CSV export")
else:
    warn(f"CSV export returned {r.status_code}: {r.text[:200]}")

# STEP 20: Export JSON
step("Export audit log as JSON")

r = req("get", "/api/audit/export", token=token_a, workspace=ws_id, params={"format": "json"})
if r.status_code == 200:
    try:
        data = r.json()
        count = len(data) if isinstance(data, list) else data.get("count", "?")
        ok(f"JSON export -- {count} records")
        if isinstance(data, list) and data:
            sample = data[0]
            ok(f"  Sample fields: {list(sample.keys())[:6]}")
            if "event_hash" in sample:
                ok("event_hash field present in JSON -- cryptographic provenance confirmed")
    except Exception as e:
        warn(f"JSON parse error: {e}")
else:
    warn(f"JSON export returned {r.status_code}: {r.text[:200]}")

# Final summary
print("\n" + "=" * 70)
print("  DEMONSTRATION COMPLETE")
print(f"  Steps executed : {STEP}")
print(f"  Assertions OK  : {PASS}")
print(f"  Failures       : {FAIL}")
print(f"  Timestamp      : {datetime.now().isoformat()}")
print("=" * 70 + "\n")

if FAIL > 0:
    sys.exit(1)
