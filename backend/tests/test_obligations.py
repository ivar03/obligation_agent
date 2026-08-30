import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_create_and_get_obligation(client: AsyncClient):
    payload = {
        "owner": "Ravi",
        "beneficiary": "Rahul",
        "action": "Send the API documentation",
        "deadline": "2026-09-05T17:00:00Z",
        "conditions": "Once auth endpoints ready",
        "status": "CONFIRMED",
        "next_action": "Write OpenAPI spec",
        "source_ref": "Slack #engineering",
        "obligation_type": "OWED_BY_ME",
        "confidence": {"overall": 0.95}
    }
    create_res = await client.post("/api/obligations", json=payload)
    assert create_res.status_code == 201
    created_data = create_res.json()
    assert created_data["id"] is not None
    assert created_data["owner"] == "Ravi"
    assert created_data["beneficiary"] == "Rahul"
    assert created_data["status"] == "CONFIRMED"

    ob_id = created_data["id"]
    get_res = await client.get(f"/api/obligations/{ob_id}")
    assert get_res.status_code == 200
    assert get_res.json()["id"] == ob_id


@pytest.mark.asyncio
async def test_controlled_status_transitions(client: AsyncClient):
    # 1. Create CONFIRMED obligation
    payload = {
        "owner": "Ravi",
        "beneficiary": "Rahul",
        "action": "Complete database migration",
        "obligation_type": "OWED_BY_ME",
        "status": "CONFIRMED",
    }
    create_res = await client.post("/api/obligations", json=payload)
    ob_id = create_res.json()["id"]

    # 2. Valid transition: CONFIRMED -> IN_PROGRESS
    res_in_prog = await client.patch(
        f"/api/obligations/{ob_id}/status",
        json={"status": "IN_PROGRESS"}
    )
    assert res_in_prog.status_code == 200
    assert res_in_prog.json()["status"] == "IN_PROGRESS"

    # 3. Valid transition: IN_PROGRESS -> COMPLETED with evidence
    res_comp = await client.patch(
        f"/api/obligations/{ob_id}/status",
        json={
            "status": "COMPLETED",
            "evidence": {"type": "commit", "url": "https://github.com/repo/commit/123"}
        }
    )
    assert res_comp.status_code == 200
    assert res_comp.json()["status"] == "COMPLETED"
    assert len(res_comp.json()["evidence"]) > 0

    # 4. Invalid transition: COMPLETED -> BLOCKED (should return 422)
    res_invalid = await client.patch(
        f"/api/obligations/{ob_id}/status",
        json={"status": "BLOCKED"}
    )
    assert res_invalid.status_code == 422


@pytest.mark.asyncio
async def test_obligation_filtering_and_deletion(client: AsyncClient):
    # Create 2 obligations: one owed by me, one owed to me
    await client.post("/api/obligations", json={
        "owner": "Ravi",
        "beneficiary": "Alex",
        "action": "Send wireframes",
        "obligation_type": "OWED_BY_ME",
    })
    ob2_res = await client.post("/api/obligations", json={
        "owner": "Alex",
        "beneficiary": "Ravi",
        "action": "Review pull request",
        "obligation_type": "OWED_TO_ME",
    })
    ob2_id = ob2_res.json()["id"]

    # Filter by OWED_BY_ME
    list_me = await client.get("/api/obligations?obligation_type=OWED_BY_ME")
    assert list_me.status_code == 200
    assert all(item["obligation_type"] == "OWED_BY_ME" for item in list_me.json()["items"])

    # Filter by OWED_TO_ME
    list_to_me = await client.get("/api/obligations?obligation_type=OWED_TO_ME")
    assert list_to_me.status_code == 200
    assert any(item["id"] == ob2_id for item in list_to_me.json()["items"])

    # Search keyword
    search_res = await client.get("/api/obligations?search=wireframes")
    assert search_res.status_code == 200
    assert len(search_res.json()["items"]) == 1

    # Delete
    del_res = await client.delete(f"/api/obligations/{ob2_id}")
    assert del_res.status_code == 204

    # Verify 404 on deleted
    get_del = await client.get(f"/api/obligations/{ob2_id}")
    assert get_del.status_code == 404
