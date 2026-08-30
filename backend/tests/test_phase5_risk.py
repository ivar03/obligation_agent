import pytest
from datetime import datetime, timedelta, timezone
from httpx import AsyncClient
from app.core.status_machine import ObligationStatus, EdgeType, RiskLevel, ActionType


@pytest.mark.asyncio
async def test_1_far_future_deadline_low_risk(client: AsyncClient):
    """Test 1: Obligation due far in the future has LOW risk."""
    now = datetime.now(timezone.utc)
    future_dl = (now + timedelta(days=30)).isoformat()

    ob = (await client.post("/api/obligations", json={
        "owner": "Ravi", "beneficiary": "Rahul", "action": "Future Task", "obligation_type": "OWED_BY_ME", "deadline": future_dl
    })).json()

    res = await client.get(f"/api/obligations/{ob['id']}/risk")
    assert res.status_code == 200
    data = res.json()
    assert data["risk_level"] == "LOW"
    assert data["risk_score"] < 0.30


@pytest.mark.asyncio
async def test_2_tomorrow_deadline_no_progress_elevated_risk(client: AsyncClient):
    """Test 2: Obligation due tomorrow with no progress has elevated risk."""
    now = datetime.now(timezone.utc)
    tomorrow_dl = (now + timedelta(hours=20)).isoformat()

    ob = (await client.post("/api/obligations", json={
        "owner": "Ravi", "beneficiary": "Rahul", "action": "Tomorrow Task", "obligation_type": "OWED_BY_ME", "deadline": tomorrow_dl
    })).json()

    res = await client.get(f"/api/obligations/{ob['id']}/risk")
    assert res.status_code == 200
    data = res.json()
    assert data["risk_level"] in ["HIGH", "CRITICAL", "MEDIUM"]
    assert data["breakdown"]["deadline_pressure"] >= 0.20
    assert any("deadline" in r.lower() for r in data["reasons"])


@pytest.mark.asyncio
async def test_3_imminent_deadline_critical_risk(client: AsyncClient):
    """Test 3: Obligation due within a few hours has high/critical risk."""
    now = datetime.now(timezone.utc)
    soon_dl = (now + timedelta(hours=5)).isoformat()

    ob = (await client.post("/api/obligations", json={
        "owner": "Ravi", "beneficiary": "Rahul", "action": "Urgent Deliverable", "obligation_type": "OWED_BY_ME", "deadline": soon_dl
    })).json()

    res = await client.get(f"/api/obligations/{ob['id']}/risk")
    data = res.json()
    assert data["risk_score"] >= 0.40
    assert data["breakdown"]["deadline_pressure"] >= 0.30


@pytest.mark.asyncio
async def test_4_overdue_obligation_status_not_relabeled(client: AsyncClient):
    """Test 4: Overdue obligation preserves OVERDUE status while assessing risk."""
    now = datetime.now(timezone.utc)
    overdue_dl = (now - timedelta(days=2)).isoformat()

    ob = (await client.post("/api/obligations", json={
        "owner": "Rahul", "beneficiary": "Ravi", "action": "Overdue Benchmark", "obligation_type": "OWED_TO_ME", "deadline": overdue_dl, "status": "OVERDUE"
    })).json()

    res = await client.get(f"/api/obligations/{ob['id']}/risk")
    data = res.json()
    assert data["status"] == "OVERDUE"
    assert any(s["signal_type"] == "DEADLINE_PASSED" for s in data["signals"])


@pytest.mark.asyncio
async def test_5_recent_progress_reduces_risk(client: AsyncClient):
    """Test 5: Recent progress update evidence decreases risk score."""
    now = datetime.now(timezone.utc)
    dl = (now + timedelta(hours=20)).isoformat()

    # Obligation without progress
    ob1 = (await client.post("/api/obligations", json={
        "owner": "Ravi", "beneficiary": "Rahul", "action": "Prepare Financial Audit", "obligation_type": "OWED_BY_ME", "deadline": dl
    })).json()

    # Obligation with progress
    ob2 = (await client.post("/api/obligations", json={
        "owner": "Ravi", "beneficiary": "Rahul", "action": "Draft Engineering Specs", "obligation_type": "OWED_BY_ME", "deadline": dl
    })).json()
    await client.post("/api/events", json={
        "source_type": "slack", "source_ref": "ev_prog_5", "sender": "Ravi", "recipients": ["Rahul"],
        "content": "Working on Draft Engineering Specs."
    })

    res1 = (await client.get(f"/api/obligations/{ob1['id']}/risk")).json()
    res2 = (await client.get(f"/api/obligations/{ob2['id']}/risk")).json()

    assert res2["risk_score"] < res1["risk_score"]


@pytest.mark.asyncio
async def test_6_negative_evidence_increases_risk(client: AsyncClient):
    """Test 6: Negative evidence statement increases risk score."""
    now = datetime.now(timezone.utc)
    dl = (now + timedelta(days=3)).isoformat()

    ob = (await client.post("/api/obligations", json={
        "owner": "Ravi", "beneficiary": "Rahul", "action": "Task with Blocker Statement", "obligation_type": "OWED_BY_ME", "deadline": dl
    })).json()

    await client.post("/api/events", json={
        "source_type": "slack", "source_ref": "ev_neg_6", "sender": "Ravi",
        "content": "Couldn't send the Task with Blocker Statement because client rejected."
    })

    res = (await client.get(f"/api/obligations/{ob['id']}/risk")).json()
    assert any(s["signal_type"] == "NEGATIVE_EVIDENCE" for s in res["signals"])
    assert res["breakdown"]["evidence_risk"] > 0


@pytest.mark.asyncio
async def test_7_conflicting_evidence_increases_uncertainty(client: AsyncClient):
    """Test 7: Both completion and non-completion evidence generates CONFLICTING_EVIDENCE signal."""
    ob = (await client.post("/api/obligations", json={
        "owner": "Ravi", "beneficiary": "Rahul", "action": "Conflict Obligation", "obligation_type": "OWED_BY_ME"
    })).json()

    await client.post("/api/events", json={
        "source_type": "slack", "source_ref": "ev_conf_1", "sender": "Ravi", "content": "Sent Conflict Obligation deliverable."
    })
    await client.post("/api/events", json={
        "source_type": "slack", "source_ref": "ev_conf_2", "sender": "Ravi", "content": "Couldn't complete Conflict Obligation."
    })

    res = (await client.get(f"/api/obligations/{ob['id']}/risk")).json()
    assert any(s["signal_type"] == "CONFLICTING_EVIDENCE" for s in res["signals"])
    assert res["action_type"] == "REVIEW_EVIDENCE"


@pytest.mark.asyncio
async def test_8_dependency_overdue_elevates_risk(client: AsyncClient):
    """Test 8: Prerequisite B is overdue -> dependent A risk is elevated."""
    ob_b = (await client.post("/api/obligations", json={
        "owner": "Rahul", "beneficiary": "Ravi", "action": "Prereq Numbers", "obligation_type": "OWED_TO_ME", "status": "OVERDUE"
    })).json()
    ob_a = (await client.post("/api/obligations", json={
        "owner": "Ravi", "beneficiary": "Team", "action": "Dependent Report", "obligation_type": "OWED_BY_ME", "status": "CONFIRMED"
    })).json()

    await client.post("/api/obligations/edges", json={
        "from_obligation_id": ob_a["id"], "to_obligation_id": ob_b["id"], "edge_type": "DEPENDS_ON"
    })

    res = (await client.get(f"/api/obligations/{ob_a['id']}/risk")).json()
    assert any(s["signal_type"] == "DEPENDENCY_OVERDUE" for s in res["signals"])
    assert res["breakdown"]["dependency_risk"] >= 0.30


@pytest.mark.asyncio
async def test_9_dependency_blocked_elevates_risk(client: AsyncClient):
    """Test 9: Prerequisite B is blocked -> dependent A risk is elevated."""
    ob_b = (await client.post("/api/obligations", json={
        "owner": "Rahul", "beneficiary": "Ravi", "action": "Prereq Blocked Task", "obligation_type": "OWED_TO_ME", "status": "BLOCKED"
    })).json()
    ob_a = (await client.post("/api/obligations", json={
        "owner": "Ravi", "beneficiary": "Team", "action": "Dependent Task 9", "obligation_type": "OWED_BY_ME", "status": "CONFIRMED"
    })).json()

    await client.post("/api/obligations/edges", json={
        "from_obligation_id": ob_a["id"], "to_obligation_id": ob_b["id"], "edge_type": "DEPENDS_ON"
    })

    res = (await client.get(f"/api/obligations/{ob_a['id']}/risk")).json()
    assert any("dependency" in s["signal_type"].lower() for s in res["signals"])


@pytest.mark.asyncio
async def test_10_dependency_completed_removes_risk(client: AsyncClient):
    """Test 10: Prerequisite completed -> dependency risk is zero."""
    ob_b = (await client.post("/api/obligations", json={
        "owner": "Rahul", "beneficiary": "Ravi", "action": "Prereq Completed Task", "obligation_type": "OWED_TO_ME", "status": "COMPLETED"
    })).json()
    ob_a = (await client.post("/api/obligations", json={
        "owner": "Ravi", "beneficiary": "Team", "action": "Dependent Task 10", "obligation_type": "OWED_BY_ME", "status": "CONFIRMED"
    })).json()

    await client.post("/api/obligations/edges", json={
        "from_obligation_id": ob_a["id"], "to_obligation_id": ob_b["id"], "edge_type": "DEPENDS_ON"
    })

    res = (await client.get(f"/api/obligations/{ob_a['id']}/risk")).json()
    assert res["breakdown"]["dependency_risk"] == 0.0


@pytest.mark.asyncio
async def test_11_multihop_dependency_risk(client: AsyncClient):
    """Test 11: Multi-hop chain A -> B -> C; C overdue -> propagates to A."""
    ob_c = (await client.post("/api/obligations", json={
        "owner": "Charlie", "beneficiary": "Bob", "action": "Base C", "obligation_type": "OWED_TO_ME", "status": "OVERDUE"
    })).json()
    ob_b = (await client.post("/api/obligations", json={
        "owner": "Bob", "beneficiary": "Alice", "action": "Middle B", "obligation_type": "OWED_BY_ME", "status": "CONFIRMED"
    })).json()
    ob_a = (await client.post("/api/obligations", json={
        "owner": "Alice", "beneficiary": "Team", "action": "Top A", "obligation_type": "OWED_BY_ME", "status": "CONFIRMED"
    })).json()

    await client.post("/api/obligations/edges", json={"from_obligation_id": ob_b["id"], "to_obligation_id": ob_c["id"], "edge_type": "DEPENDS_ON"})
    await client.post("/api/obligations/edges", json={"from_obligation_id": ob_a["id"], "to_obligation_id": ob_b["id"], "edge_type": "DEPENDS_ON"})

    res_a = (await client.get(f"/api/obligations/{ob_a['id']}/risk")).json()
    assert res_a["breakdown"]["dependency_risk"] > 0


@pytest.mark.asyncio
async def test_12_fan_out_dependency_priority(client: AsyncClient):
    """Test 12: Obligation blocking multiple downstream tasks receives higher priority score."""
    root = (await client.post("/api/obligations", json={
        "owner": "Ravi", "beneficiary": "Team", "action": "Root Core Blocker", "obligation_type": "OWED_BY_ME", "status": "CONFIRMED"
    })).json()
    isolated = (await client.post("/api/obligations", json={
        "owner": "Ravi", "beneficiary": "Team", "action": "Isolated Single Task", "obligation_type": "OWED_BY_ME", "status": "CONFIRMED"
    })).json()

    # Create 3 dependents on root
    for i in range(3):
        dep = (await client.post("/api/obligations", json={
            "owner": f"Worker{i}", "beneficiary": "Team", "action": f"Dep Task {i}", "obligation_type": "OWED_BY_ME"
        })).json()
        await client.post("/api/obligations/edges", json={"from_obligation_id": dep["id"], "to_obligation_id": root["id"], "edge_type": "DEPENDS_ON"})

    res_root = (await client.get(f"/api/obligations/{root['id']}/risk")).json()
    res_iso = (await client.get(f"/api/obligations/{isolated['id']}/risk")).json()

    assert res_root["dependent_count"] == 3
    assert res_root["priority_score"] > res_iso["priority_score"]


@pytest.mark.asyncio
async def test_13_ambiguous_ownership_risk(client: AsyncClient):
    """Test 13: Group 'We' or unassigned owner generates OWNERSHIP_UNCERTAINTY."""
    ob = (await client.post("/api/obligations", json={
        "owner": "We", "beneficiary": "Client", "action": "Send proposal to client", "obligation_type": "OWED_BY_ME"
    })).json()

    res = (await client.get(f"/api/obligations/{ob['id']}/risk")).json()
    assert any(s["signal_type"] == "OWNERSHIP_UNCERTAINTY" for s in res["signals"])
    assert res["action_type"] == "ASSIGN_OWNER"


@pytest.mark.asyncio
async def test_14_unknown_deadline_no_fabricated_date(client: AsyncClient):
    """Test 14: Obligation without deadline generates DEADLINE_AMBIGUOUS without fabricating dates."""
    ob = (await client.post("/api/obligations", json={
        "owner": "Ravi", "beneficiary": "Rahul", "action": "Task without date", "obligation_type": "OWED_BY_ME"
    })).json()

    res = (await client.get(f"/api/obligations/{ob['id']}/risk")).json()
    assert res["deadline"] is None
    assert any(s["signal_type"] == "DEADLINE_AMBIGUOUS" for s in res["signals"])


@pytest.mark.asyncio
async def test_15_conditional_deadline_waiting_trigger(client: AsyncClient):
    """Test 15: Obligation with conditions generates CONDITIONAL_TRIGGER_WAITING signal."""
    ob = (await client.post("/api/obligations", json={
        "owner": "Ravi", "beneficiary": "Professor", "action": "Review after submission", "obligation_type": "OWED_BY_ME",
        "conditions": "Once student submits draft"
    })).json()

    res = (await client.get(f"/api/obligations/{ob['id']}/risk")).json()
    assert any(s["signal_type"] == "CONDITIONAL_TRIGGER_WAITING" for s in res["signals"])
    assert res["action_type"] == "MONITOR_CONDITION"


@pytest.mark.asyncio
async def test_16_completion_candidate_evidence_reduces_risk(client: AsyncClient):
    """Test 16: Suggested completion evidence decreases risk and recommends review."""
    ob = (await client.post("/api/obligations", json={
        "owner": "Ravi", "beneficiary": "Rahul", "action": "Send API Documentation", "obligation_type": "OWED_BY_ME"
    })).json()

    await client.post("/api/events", json={
        "source_type": "slack", "source_ref": "ev_comp_16", "sender": "Ravi", "recipients": ["Rahul"],
        "content": "Sent the API Documentation to Rahul."
    })

    res = (await client.get(f"/api/obligations/{ob['id']}/risk")).json()
    assert any(s["signal_type"] == "COMPLETION_CANDIDATE_DETECTED" for s in res["signals"])
    assert res["action_type"] == "REVIEW_EVIDENCE"


@pytest.mark.asyncio
async def test_17_confirmed_completion_zero_active_risk(client: AsyncClient):
    """Test 17: COMPLETED obligation has zero risk score and is_at_risk=False."""
    ob = (await client.post("/api/obligations", json={
        "owner": "Ravi", "beneficiary": "Rahul", "action": "Completed Task 17", "obligation_type": "OWED_BY_ME", "status": "COMPLETED"
    })).json()

    res = (await client.get(f"/api/obligations/{ob['id']}/risk")).json()
    assert res["risk_score"] == 0.0
    assert res["is_at_risk"] is False
    assert res["action_type"] == "NO_ACTION"


@pytest.mark.asyncio
async def test_18_recommendation_for_blocked_obligation(client: AsyncClient):
    """Test 18: Blocked obligation recommends RESOLVE_DEPENDENCY."""
    ob_b = (await client.post("/api/obligations", json={
        "owner": "Rahul", "beneficiary": "Ravi", "action": "Benchmark Numbers", "obligation_type": "OWED_TO_ME", "status": "OVERDUE"
    })).json()
    ob_a = (await client.post("/api/obligations", json={
        "owner": "Ravi", "beneficiary": "Team", "action": "Blocked Report", "obligation_type": "OWED_BY_ME", "status": "BLOCKED"
    })).json()
    await client.post("/api/obligations/edges", json={"from_obligation_id": ob_a["id"], "to_obligation_id": ob_b["id"], "edge_type": "DEPENDS_ON"})

    res = (await client.get(f"/api/obligations/{ob_a['id']}/risk")).json()
    assert res["action_type"] == "RESOLVE_DEPENDENCY"
    assert "Rahul" in res["recommended_action"]


@pytest.mark.asyncio
async def test_19_recommendation_for_approaching_deadline(client: AsyncClient):
    """Test 19: Approaching deadline for OWED_BY_ME recommends START_WORK."""
    now = datetime.now(timezone.utc)
    dl = (now + timedelta(hours=10)).isoformat()

    ob = (await client.post("/api/obligations", json={
        "owner": "Ravi", "beneficiary": "Rahul", "action": "Imminent Work", "obligation_type": "OWED_BY_ME", "deadline": dl
    })).json()

    res = (await client.get(f"/api/obligations/{ob['id']}/risk")).json()
    assert res["action_type"] == "START_WORK"


@pytest.mark.asyncio
async def test_20_recommendation_for_conflicting_evidence(client: AsyncClient):
    """Test 20: Conflicting evidence recommends REVIEW_EVIDENCE."""
    ob = (await client.post("/api/obligations", json={
        "owner": "Ravi", "beneficiary": "Rahul", "action": "Conflict Work", "obligation_type": "OWED_BY_ME"
    })).json()
    await client.post("/api/events", json={"source_type": "m", "source_ref": "c1", "sender": "Ravi", "content": "Sent Conflict Work."})
    await client.post("/api/events", json={"source_type": "m", "source_ref": "c2", "sender": "Ravi", "content": "Couldn't send Conflict Work."})

    res = (await client.get(f"/api/obligations/{ob['id']}/risk")).json()
    assert res["action_type"] == "REVIEW_EVIDENCE"


@pytest.mark.asyncio
async def test_21_risk_threshold_boundaries(client: AsyncClient):
    """Test 21: Threshold boundaries categorize correctly."""
    from app.services.risk_engine import RiskEngine
    assert RiskEngine.classify_risk_level(0.85) == RiskLevel.CRITICAL
    assert RiskEngine.classify_risk_level(0.70) == RiskLevel.HIGH
    assert RiskEngine.classify_risk_level(0.45) == RiskLevel.MEDIUM
    assert RiskEngine.classify_risk_level(0.15) == RiskLevel.LOW


@pytest.mark.asyncio
async def test_22_risk_explanation_readability(client: AsyncClient):
    """Test 22: Every risk assessment provides clear, readable reasons."""
    now = datetime.now(timezone.utc)
    dl = (now + timedelta(hours=15)).isoformat()

    ob = (await client.post("/api/obligations", json={
        "owner": "Ravi", "beneficiary": "Rahul", "action": "Readable Task", "obligation_type": "OWED_BY_ME", "deadline": dl
    })).json()

    res = (await client.get(f"/api/obligations/{ob['id']}/risk")).json()
    assert len(res["reasons"]) >= 1
    assert all(isinstance(r, str) and len(r) > 5 for r in res["reasons"])


@pytest.mark.asyncio
async def test_23_risk_score_bounded(client: AsyncClient):
    """Test 23: Risk score is strictly bounded between 0.0 and 1.0."""
    now = datetime.now(timezone.utc)
    dl = (now - timedelta(days=10)).isoformat()

    ob = (await client.post("/api/obligations", json={
        "owner": "We", "beneficiary": "Client", "action": "Extreme Bad Task", "obligation_type": "OWED_BY_ME", "deadline": dl, "status": "OVERDUE"
    })).json()

    res = (await client.get(f"/api/obligations/{ob['id']}/risk")).json()
    assert 0.0 <= res["risk_score"] <= 1.0


@pytest.mark.asyncio
async def test_24_no_duplicate_signals(client: AsyncClient):
    """Test 24: No duplicate signal types are appended for the same underlying factor."""
    now = datetime.now(timezone.utc)
    dl = (now + timedelta(hours=8)).isoformat()

    ob = (await client.post("/api/obligations", json={
        "owner": "Ravi", "beneficiary": "Rahul", "action": "Unique Signal Task", "obligation_type": "OWED_BY_ME", "deadline": dl
    })).json()

    res = (await client.get(f"/api/obligations/{ob['id']}/risk")).json()
    signal_types = [s["signal_type"] for s in res["signals"]]
    assert len(signal_types) == len(set(signal_types))


@pytest.mark.asyncio
async def test_25_risk_recalculation_after_dependency_completion(client: AsyncClient):
    """Test 25: Unblocking prerequisite dynamically eliminates dependency risk upon re-evaluation."""
    ob_b = (await client.post("/api/obligations", json={
        "owner": "Rahul", "beneficiary": "Ravi", "action": "Prereq 25", "obligation_type": "OWED_TO_ME", "status": "OVERDUE"
    })).json()
    ob_a = (await client.post("/api/obligations", json={
        "owner": "Ravi", "beneficiary": "Team", "action": "Dependent 25", "obligation_type": "OWED_BY_ME", "status": "BLOCKED"
    })).json()
    await client.post("/api/obligations/edges", json={"from_obligation_id": ob_a["id"], "to_obligation_id": ob_b["id"], "edge_type": "DEPENDS_ON"})

    # Check initial blocked risk
    res1 = (await client.get(f"/api/obligations/{ob_a['id']}/risk")).json()
    assert res1["breakdown"]["dependency_risk"] > 0

    # Complete B
    await client.post("/api/obligations/status", json={"status": "COMPLETED"}) # update B status
    await client.patch(f"/api/obligations/{ob_b['id']}/status", json={"status": "COMPLETED"})

    # Check recalculated risk on A
    res2 = (await client.get(f"/api/obligations/{ob_a['id']}/risk")).json()
    assert res2["breakdown"]["dependency_risk"] == 0.0


@pytest.mark.asyncio
async def test_26_bulk_risk_endpoint_sorting_and_filtering(client: AsyncClient):
    """Test 26: GET /api/risk returns prioritized items and respects filters."""
    now = datetime.now(timezone.utc)
    await client.post("/api/obligations", json={
        "owner": "Ravi", "beneficiary": "Rahul", "action": "Bulk Task 1", "obligation_type": "OWED_BY_ME", "deadline": (now + timedelta(hours=10)).isoformat()
    })
    await client.post("/api/obligations", json={
        "owner": "Rahul", "beneficiary": "Ravi", "action": "Bulk Task 2", "obligation_type": "OWED_TO_ME", "deadline": (now + timedelta(days=20)).isoformat()
    })

    res = await client.get("/api/risk")
    assert res.status_code == 200
    data = res.json()
    assert "total_at_risk" in data
    assert "items" in data
    assert len(data["items"]) >= 2

    # Verify priority sorting (highest priority first)
    priorities = [item["priority_score"] for item in data["items"]]
    assert priorities == sorted(priorities, reverse=True)
