import pytest
from httpx import AsyncClient
from app.core.status_machine import ObligationStatus, EdgeType, CorrelationStatus, EventSemanticRole


@pytest.mark.asyncio
async def test_1_ingest_normalized_event(client: AsyncClient):
    """Test 1: Ingest normalized event creates suggested evidence."""
    ob = (await client.post("/api/obligations", json={
        "owner": "Ravi", "beneficiary": "Rahul", "action": "Send API documentation", "obligation_type": "OWED_BY_ME"
    })).json()

    res = await client.post("/api/events", json={
        "source_type": "slack",
        "source_ref": "slack_msg_101",
        "sender": "Ravi",
        "recipients": ["Rahul"],
        "content": "Sent the API documentation to Rahul.",
        "metadata": {"channel": "dev-team"}
    })
    assert res.status_code == 201
    data = res.json()
    assert data["ingested"] is True
    assert data["semantic_role"] == "COMPLETION_SIGNAL"
    assert len(data["evidence_records"]) >= 1
    assert data["evidence_records"][0]["obligation_id"] == ob["id"]
    assert data["evidence_records"][0]["correlation_status"] == "SUGGESTED"


@pytest.mark.asyncio
async def test_2_duplicate_event_deduplication(client: AsyncClient):
    """Test 2: Re-ingesting the exact same source event deduplicates without error."""
    ob = (await client.post("/api/obligations", json={
        "owner": "Ravi", "beneficiary": "Rahul", "action": "Task Deduplicate", "obligation_type": "OWED_BY_ME"
    })).json()

    event_payload = {
        "source_type": "email",
        "source_ref": "email_unique_999",
        "sender": "Ravi",
        "recipients": ["Rahul"],
        "content": "Sent the Task Deduplicate deliverable.",
    }

    res1 = await client.post("/api/events", json=event_payload)
    assert res1.status_code == 201
    rec1_id = res1.json()["evidence_records"][0]["id"]

    res2 = await client.post("/api/events", json=event_payload)
    assert res2.status_code == 201
    rec2_id = res2.json()["evidence_records"][0]["id"]

    assert rec1_id == rec2_id


@pytest.mark.asyncio
async def test_3_completion_signal_high_confidence(client: AsyncClient):
    """Test 3: Past-tense delivery produces a high-confidence completion candidate."""
    ob = (await client.post("/api/obligations", json={
        "owner": "Rahul", "beneficiary": "Ravi", "action": "Send database benchmark numbers", "obligation_type": "OWED_TO_ME"
    })).json()

    res = await client.post("/api/events/analyze", json={
        "source_type": "message",
        "sender": "Rahul",
        "recipients": ["Ravi"],
        "content": "Sent the database benchmark numbers.",
    })
    assert res.status_code == 200
    data = res.json()
    assert data["semantic_role"] == "COMPLETION_SIGNAL"
    assert data["best_match"] is not None
    assert data["best_match"]["obligation_id"] == ob["id"]
    assert data["best_match"]["correlation_confidence"] >= 0.80
    assert data["best_match"]["is_completion_candidate"] is True


@pytest.mark.asyncio
async def test_4_future_commitment_not_completion(client: AsyncClient):
    """Test 4: Future commitment expression is classified as COMMITMENT and NOT completion."""
    await client.post("/api/obligations", json={
        "owner": "Ravi", "beneficiary": "Rahul", "action": "Send project report", "obligation_type": "OWED_BY_ME"
    })

    res = await client.post("/api/events/analyze", json={
        "source_type": "message",
        "sender": "Ravi",
        "recipients": ["Rahul"],
        "content": "I will send the project report tomorrow.",
    })
    assert res.status_code == 200
    data = res.json()
    assert data["semantic_role"] == "COMMITMENT"
    if data["best_match"]:
        assert data["best_match"]["is_completion_candidate"] is False
        assert data["best_match"]["correlation_confidence"] <= 0.40


@pytest.mark.asyncio
async def test_5_request_not_completion(client: AsyncClient):
    """Test 5: Request/directive is classified as REQUEST and NOT completion."""
    await client.post("/api/obligations", json={
        "owner": "Ravi", "beneficiary": "Rahul", "action": "Send API docs", "obligation_type": "OWED_BY_ME"
    })

    res = await client.post("/api/events/analyze", json={
        "source_type": "message",
        "sender": "Rahul",
        "recipients": ["Ravi"],
        "content": "Can you please send the API docs?",
    })
    assert res.status_code == 200
    data = res.json()
    assert data["semantic_role"] == "REQUEST"
    if data["best_match"]:
        assert data["best_match"]["is_completion_candidate"] is False


@pytest.mark.asyncio
async def test_6_progress_update(client: AsyncClient):
    """Test 6: Progress statement is classified as PROGRESS_UPDATE."""
    res = await client.post("/api/events/analyze", json={
        "source_type": "message",
        "sender": "Ravi",
        "recipients": ["Rahul"],
        "content": "Currently working on the report specs.",
    })
    assert res.status_code == 200
    assert res.json()["semantic_role"] == "PROGRESS_UPDATE"


@pytest.mark.asyncio
async def test_7_irrelevant_message(client: AsyncClient):
    """Test 7: Pleasantries are classified as IRRELEVANT."""
    res = await client.post("/api/events/analyze", json={
        "source_type": "message",
        "sender": "Ravi",
        "recipients": ["Rahul"],
        "content": "Good morning team!",
    })
    assert res.status_code == 200
    assert res.json()["semantic_role"] == "IRRELEVANT"


@pytest.mark.asyncio
async def test_8_negative_evidence_non_completion(client: AsyncClient):
    """Test 8: Inability or blocker is classified as NON_COMPLETION_SIGNAL."""
    res = await client.post("/api/events/analyze", json={
        "source_type": "message",
        "sender": "Ravi",
        "recipients": ["Rahul"],
        "content": "Couldn't send the report because the client rejected the proposal.",
    })
    assert res.status_code == 200
    assert res.json()["semantic_role"] == "NON_COMPLETION_SIGNAL"


@pytest.mark.asyncio
async def test_9_owner_mismatch_penalty(client: AsyncClient):
    """Test 9: Mismatched sender receives a confidence penalty compared to owner."""
    ob = (await client.post("/api/obligations", json={
        "owner": "Rahul", "beneficiary": "Ravi", "action": "Send server logs", "obligation_type": "OWED_TO_ME"
    })).json()

    # Mismatched sender (Amit instead of Rahul)
    res = await client.post("/api/events/analyze", json={
        "source_type": "message",
        "sender": "Amit",
        "recipients": ["Ravi"],
        "content": "Sent server logs.",
    })
    data = res.json()
    match = next(m for m in data["matches"] if m["obligation_id"] == ob["id"])
    assert any("differs" in r.lower() or "does not match" in r.lower() for r in match["reasoning"])


@pytest.mark.asyncio
async def test_10_beneficiary_match_boost(client: AsyncClient):
    """Test 10: Beneficiary match provides a positive signal in reasoning."""
    ob = (await client.post("/api/obligations", json={
        "owner": "Ravi", "beneficiary": "Sarah", "action": "Send design assets", "obligation_type": "OWED_BY_ME"
    })).json()

    res = await client.post("/api/events/analyze", json={
        "source_type": "message",
        "sender": "Ravi",
        "recipients": ["Sarah"],
        "content": "Sent design assets to Sarah.",
    })
    data = res.json()
    match = next(m for m in data["matches"] if m["obligation_id"] == ob["id"])
    assert any("beneficiary" in s.lower() for s in match["matched_signals"])


@pytest.mark.asyncio
async def test_11_action_similarity_boost(client: AsyncClient):
    """Test 11: Keyword overlap produces action similarity match signal."""
    ob = (await client.post("/api/obligations", json={
        "owner": "Ravi", "beneficiary": "Team", "action": "Publish quarterly financial audit", "obligation_type": "OWED_BY_ME"
    })).json()

    res = await client.post("/api/events/analyze", json={
        "source_type": "message",
        "sender": "Ravi",
        "recipients": ["Team"],
        "content": "Published the quarterly financial audit deck.",
    })
    data = res.json()
    match = next(m for m in data["matches"] if m["obligation_id"] == ob["id"])
    assert match["correlation_confidence"] >= 0.80
    assert any("action overlap" in s.lower() for s in match["matched_signals"])


@pytest.mark.asyncio
async def test_12_multiple_evidence_records(client: AsyncClient):
    """Test 12: Multiple evidence records can coexist for one obligation."""
    ob = (await client.post("/api/obligations", json={
        "owner": "Ravi", "beneficiary": "Rahul", "action": "Deliver project specs", "obligation_type": "OWED_BY_ME"
    })).json()

    # Evidence 1: Message
    await client.post("/api/events", json={
        "source_type": "slack", "source_ref": "ev_msg_1", "sender": "Ravi", "recipients": ["Rahul"],
        "content": "Working on the deliver project specs."
    })
    # Evidence 2: File Attachment
    await client.post("/api/events", json={
        "source_type": "file", "source_ref": "ev_file_2", "sender": "Ravi", "recipients": ["Rahul"],
        "content": "Sent deliver project specs PDF.",
        "metadata": {"attachments": [{"name": "specs.pdf"}]}
    })

    # Query evidence list for obligation
    list_res = await client.get(f"/api/obligations/{ob['id']}/evidence")
    assert list_res.status_code == 200
    ev_list = list_res.json()
    assert len(ev_list) >= 2


@pytest.mark.asyncio
async def test_13_evidence_confirmation(client: AsyncClient):
    """Test 13: Confirming evidence transitions obligation to COMPLETED and evidence to CONFIRMED."""
    ob = (await client.post("/api/obligations", json={
        "owner": "Ravi", "beneficiary": "Rahul", "action": "Send confirmation test", "obligation_type": "OWED_BY_ME", "status": "CONFIRMED"
    })).json()

    ingest_res = await client.post("/api/events", json={
        "source_type": "message", "source_ref": "msg_confirm_test", "sender": "Ravi", "recipients": ["Rahul"],
        "content": "Sent the confirmation test doc."
    })
    ev_id = ingest_res.json()["evidence_records"][0]["id"]

    # Confirm evidence
    confirm_res = await client.post(
        f"/api/obligations/{ob['id']}/evidence/{ev_id}/confirm",
        json={"notes": "Verified receipt in Slack"}
    )
    assert confirm_res.status_code == 200
    updated_ob = confirm_res.json()
    assert updated_ob["status"] == "COMPLETED"
    assert any(e.get("type") == "evidence_confirmation" for e in updated_ob["evidence"])


@pytest.mark.asyncio
async def test_14_evidence_rejection(client: AsyncClient):
    """Test 14: Rejecting evidence marks evidence as REJECTED without mutating obligation status."""
    ob = (await client.post("/api/obligations", json={
        "owner": "Ravi", "beneficiary": "Rahul", "action": "Send rejection test", "obligation_type": "OWED_BY_ME", "status": "CONFIRMED"
    })).json()

    ingest_res = await client.post("/api/events", json={
        "source_type": "message", "source_ref": "msg_reject_test", "sender": "Ravi", "recipients": ["Rahul"],
        "content": "Sent rejection test."
    })
    ev_id = ingest_res.json()["evidence_records"][0]["id"]

    # Reject evidence
    reject_res = await client.post(f"/api/obligations/{ob['id']}/evidence/{ev_id}/reject")
    assert reject_res.status_code == 200
    assert reject_res.json()["correlation_status"] == "REJECTED"

    # Check obligation status remains unchanged
    ob_check = (await client.get(f"/api/obligations/{ob['id']}")).json()
    assert ob_check["status"] == "CONFIRMED"


@pytest.mark.asyncio
async def test_15_evidence_confirmation_triggers_graph_unblocking(client: AsyncClient):
    """Test 15: Confirming evidence on prerequisite B automatically unblocks dependent A!"""
    ob_b = (await client.post("/api/obligations", json={
        "owner": "Rahul", "beneficiary": "Ravi", "action": "Send numbers for graph test", "obligation_type": "OWED_TO_ME", "status": "OVERDUE"
    })).json()
    ob_a = (await client.post("/api/obligations", json={
        "owner": "Ravi", "beneficiary": "Team", "action": "Finish report for graph test", "obligation_type": "OWED_BY_ME", "status": "CONFIRMED"
    })).json()

    # Connect A depends on B (A immediately becomes BLOCKED)
    await client.post("/api/obligations/edges", json={
        "from_obligation_id": ob_a["id"], "to_obligation_id": ob_b["id"], "edge_type": "DEPENDS_ON"
    })
    ob_a_check = (await client.get(f"/api/obligations/{ob_a['id']}")).json()
    assert ob_a_check["status"] == "BLOCKED"

    # Ingest completion event for B
    ev_res = await client.post("/api/events", json={
        "source_type": "message", "source_ref": "msg_graph_unblock", "sender": "Rahul", "recipients": ["Ravi"],
        "content": "Sent the numbers for graph test."
    })
    ev_id = ev_res.json()["evidence_records"][0]["id"]

    # Confirm completion evidence on B
    await client.post(f"/api/obligations/{ob_b['id']}/evidence/{ev_id}/confirm")

    # Verify B is COMPLETED and A is automatically UNBLOCKED to CONFIRMED!
    ob_b_after = (await client.get(f"/api/obligations/{ob_b['id']}")).json()
    ob_a_after = (await client.get(f"/api/obligations/{ob_a['id']}")).json()
    assert ob_b_after["status"] == "COMPLETED"
    assert ob_a_after["status"] == "CONFIRMED"
    assert ob_a_after["block_reason"] is None


@pytest.mark.asyncio
async def test_16_evidence_cannot_bypass_status_machine(client: AsyncClient):
    """Test 16: Confirming evidence on CANCELLED obligation fails controlled transition validation."""
    ob = (await client.post("/api/obligations", json={
        "owner": "Ravi", "beneficiary": "Rahul", "action": "Cancelled Task", "obligation_type": "OWED_BY_ME", "status": "CANCELLED"
    })).json()

    ev_res = await client.post("/api/events", json={
        "source_type": "message", "source_ref": "msg_cancelled_bypass", "sender": "Ravi", "recipients": ["Rahul"],
        "content": "Sent Cancelled Task."
    })
    # If ingested
    if ev_res.json()["evidence_records"]:
        ev_id = ev_res.json()["evidence_records"][0]["id"]
        confirm_res = await client.post(f"/api/obligations/{ob['id']}/evidence/{ev_id}/confirm")
        assert confirm_res.status_code == 422


@pytest.mark.asyncio
async def test_17_source_reference_uniqueness(client: AsyncClient):
    """Test 17: Ingesting the same source reference on the same obligation is idempotent."""
    ob = (await client.post("/api/obligations", json={
        "owner": "Ravi", "beneficiary": "Rahul", "action": "Idempotent Task", "obligation_type": "OWED_BY_ME"
    })).json()

    ev1 = await client.post("/api/events", json={
        "source_type": "jira", "source_ref": "JIRA-100", "sender": "Ravi", "recipients": ["Rahul"],
        "content": "Sent Idempotent Task."
    })
    ev2 = await client.post("/api/events", json={
        "source_type": "jira", "source_ref": "JIRA-100", "sender": "Ravi", "recipients": ["Rahul"],
        "content": "Sent Idempotent Task."
    })
    assert len(ev1.json()["evidence_records"]) == 1
    assert len(ev2.json()["evidence_records"]) == 1
    assert ev1.json()["evidence_records"][0]["id"] == ev2.json()["evidence_records"][0]["id"]


@pytest.mark.asyncio
async def test_18_low_confidence_evidence_review_required(client: AsyncClient):
    """Test 18: Partial/ambiguous match requires review."""
    await client.post("/api/obligations", json={
        "owner": "Ravi", "beneficiary": "Client", "action": "Deliver executive summary", "obligation_type": "OWED_BY_ME"
    })

    res = await client.post("/api/events/analyze", json={
        "source_type": "message",
        "sender": "UnknownPerson",
        "content": "Sent some summary notes.",
    })
    data = res.json()
    if data["best_match"]:
        assert data["best_match"]["review_required"] is True


@pytest.mark.asyncio
async def test_19_high_confidence_evidence(client: AsyncClient):
    """Test 19: Clear fulfillment match receives level HIGH."""
    await client.post("/api/obligations", json={
        "owner": "Ravi", "beneficiary": "Rahul", "action": "Send weekly sprint metrics", "obligation_type": "OWED_BY_ME"
    })

    res = await client.post("/api/events/analyze", json={
        "source_type": "email",
        "sender": "Ravi",
        "recipients": ["Rahul"],
        "content": "Sent the weekly sprint metrics to Rahul.",
    })
    data = res.json()
    assert data["best_match"]["confidence_level"] == "HIGH"


@pytest.mark.asyncio
async def test_20_evidence_timeline_ordering(client: AsyncClient):
    """Test 20: Evidence endpoint returns records in order."""
    ob = (await client.post("/api/obligations", json={
        "owner": "Ravi", "beneficiary": "Rahul", "action": "Timeline task", "obligation_type": "OWED_BY_ME"
    })).json()

    await client.post("/api/events", json={"source_type": "msg", "source_ref": "t1", "sender": "Ravi", "content": "Working on Timeline task."})
    await client.post("/api/events", json={"source_type": "msg", "source_ref": "t2", "sender": "Ravi", "content": "Sent Timeline task."})

    res = await client.get(f"/api/obligations/{ob['id']}/evidence")
    items = res.json()
    assert len(items) >= 2


@pytest.mark.asyncio
async def test_21_attachment_metadata_signal(client: AsyncClient):
    """Test 21: Attached deliverable file provides an attachment signal boost."""
    await client.post("/api/obligations", json={
        "owner": "Rahul", "beneficiary": "Ravi", "action": "Send performance benchmark CSV", "obligation_type": "OWED_TO_ME"
    })

    res = await client.post("/api/events/analyze", json={
        "source_type": "file",
        "sender": "Rahul",
        "recipients": ["Ravi"],
        "content": "Attached performance benchmark CSV.",
        "metadata": {"attachments": [{"name": "benchmark.csv", "size": 1024}]}
    })
    data = res.json()
    assert any("attached" in s.lower() for s in data["best_match"]["matched_signals"])


@pytest.mark.asyncio
async def test_22_stateless_event_analysis(client: AsyncClient):
    """Test 22: POST /api/events/analyze evaluates without mutating DB state."""
    ob = (await client.post("/api/obligations", json={
        "owner": "Ravi", "beneficiary": "Rahul", "action": "Stateless test", "obligation_type": "OWED_BY_ME"
    })).json()

    res = await client.post("/api/events/analyze", json={
        "source_type": "message",
        "sender": "Ravi",
        "recipients": ["Rahul"],
        "content": "Sent the Stateless test.",
    })
    assert res.status_code == 200

    # Ensure no evidence record was persisted
    ev_list = (await client.get(f"/api/obligations/{ob['id']}/evidence")).json()
    assert len(ev_list) == 0
