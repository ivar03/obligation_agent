import pytest
from datetime import datetime, timezone
from httpx import AsyncClient
from app.schemas.obligation import DeadlineType, MessageContext


@pytest.mark.asyncio
async def test_case_1_explicit_first_person(client: AsyncClient):
    """Case 1: Explicit first person ('I will send the report tomorrow.')"""
    payload = {
        "text": "I will send the report tomorrow.",
        "context": {
            "sender": "Ravi",
            "recipients": ["Rahul"],
            "current_user": "Ravi"
        },
        "reference_datetime": "2026-08-30T12:00:00Z"
    }
    response = await client.post("/api/obligations/extract", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["detected"] is True
    ob = data["obligation"]
    assert ob["owner"] == "Ravi"
    assert ob["obligation_type"] == "OWED_BY_ME"
    assert ob["confidence"]["owner"] >= 0.80
    assert ob["deadline_type"] == DeadlineType.RELATIVE
    assert ob["deadline"] is not None
    assert ob["resolution"]["ownership"]["ambiguous"] is False


@pytest.mark.asyncio
async def test_case_2_explicit_second_person(client: AsyncClient):
    """Case 2: Explicit second person ('Rahul, please send the report tomorrow.')"""
    payload = {
        "text": "Rahul, please send the report tomorrow.",
        "reference_datetime": "2026-08-30T12:00:00Z"
    }
    response = await client.post("/api/obligations/extract", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["detected"] is True
    ob = data["obligation"]
    assert ob["owner"] == "Rahul"
    assert ob["obligation_type"] == "OWED_TO_ME"
    assert ob["confidence"]["owner"] >= 0.80
    assert ob["resolution"]["ownership"]["ambiguous"] is False


@pytest.mark.asyncio
async def test_case_3_explicit_third_person(client: AsyncClient):
    """Case 3: Explicit third person ('Rahul will send the report tomorrow.')"""
    payload = {
        "text": "Rahul will send the report tomorrow.",
        "reference_datetime": "2026-08-30T12:00:00Z"
    }
    response = await client.post("/api/obligations/extract", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["detected"] is True
    ob = data["obligation"]
    assert ob["owner"] == "Rahul"
    assert ob["obligation_type"] == "OWED_TO_ME"
    assert ob["confidence"]["owner"] >= 0.80


@pytest.mark.asyncio
async def test_case_4_reciprocal_obligation(client: AsyncClient):
    """Case 4: Reciprocal obligation ('Rahul owes Ravi the database numbers.')"""
    payload = {
        "text": "Rahul owes Ravi: Send the database numbers.",
        "context": {"current_user": "Ravi"}
    }
    response = await client.post("/api/obligations/extract", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["detected"] is True
    ob = data["obligation"]
    assert ob["owner"] == "Rahul"
    assert ob["beneficiary"] == "Ravi"
    assert ob["obligation_type"] == "OWED_TO_ME"
    assert ob["confidence"]["owner"] >= 0.80


@pytest.mark.asyncio
async def test_case_5_ambiguous_group_ownership(client: AsyncClient):
    """Case 5: Ambiguous group phrasing ('We should probably send this to the client tomorrow.')"""
    payload = {
        "text": "We should probably send this to the client tomorrow.",
        "reference_datetime": "2026-08-30T12:00:00Z"
    }
    response = await client.post("/api/obligations/extract", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["detected"] is True
    ob = data["obligation"]
    assert "Ambiguous" in ob["owner"] or "Unassigned" in ob["owner"]
    assert ob["confidence"]["owner"] < 0.60
    assert ob["resolution"]["review_required"] is True
    assert any(amb["field"] == "owner" for amb in ob["resolution"]["ambiguities"])


@pytest.mark.asyncio
async def test_case_6_relative_deadline_resolution(client: AsyncClient):
    """Case 6: Relative deadline resolved against reference timestamp ('Send the report tomorrow.')"""
    ref_time = "2026-08-30T10:00:00Z"
    payload = {
        "text": "Send the report tomorrow.",
        "reference_datetime": ref_time
    }
    response = await client.post("/api/obligations/extract", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["detected"] is True
    ob = data["obligation"]
    assert ob["deadline_type"] == DeadlineType.RELATIVE
    assert ob["deadline"] is not None
    # 2026-08-30 + 1 day = 2026-08-31
    assert "2026-08-31" in ob["deadline"]
    assert ob["confidence"]["deadline"] >= 0.80


@pytest.mark.asyncio
async def test_case_7_explicit_deadline(client: AsyncClient):
    """Case 7: Explicit deadline ('Send the report by 5 PM Friday.')"""
    # 2026-08-30 is a Sunday. Next Friday is 2026-09-04.
    payload = {
        "text": "Send the report by 5 PM Friday.",
        "reference_datetime": "2026-08-30T12:00:00Z"
    }
    response = await client.post("/api/obligations/extract", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["detected"] is True
    ob = data["obligation"]
    assert ob["deadline_type"] == DeadlineType.EXPLICIT
    assert ob["deadline"] is not None
    assert "2026-09-04" in ob["deadline"]
    assert ob["confidence"]["deadline"] >= 0.80


@pytest.mark.asyncio
async def test_case_8_conditional_deadline(client: AsyncClient):
    """Case 8: Conditional deadline ('Send the report once Rahul sends the numbers.')"""
    payload = {
        "text": "Send the report once Rahul sends the numbers."
    }
    response = await client.post("/api/obligations/extract", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["detected"] is True
    ob = data["obligation"]
    assert ob["deadline_type"] == DeadlineType.CONDITIONAL
    assert ob["deadline"] is None  # Must NOT force fake date
    assert ob["conditions"] is not None
    assert "Rahul sends the numbers" in ob["conditions"]
    assert ob["resolution"]["deadline"]["ambiguous"] is False


@pytest.mark.asyncio
async def test_case_9_ambiguous_deadline(client: AsyncClient):
    """Case 9: Ambiguous deadline ('Send it sometime soon.')"""
    payload = {
        "text": "Send the report sometime soon."
    }
    response = await client.post("/api/obligations/extract", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["detected"] is True
    ob = data["obligation"]
    assert ob["deadline_type"] == DeadlineType.UNKNOWN
    assert ob["deadline"] is None
    assert ob["confidence"]["deadline"] < 0.60
    assert ob["resolution"]["review_required"] is True
    assert any(amb["field"] == "deadline" for amb in ob["resolution"]["ambiguities"])


@pytest.mark.asyncio
async def test_case_10_no_obligation(client: AsyncClient):
    """Case 10: Non-obligation conversational message ('Good morning everyone.')"""
    payload = {
        "text": "Good morning everyone, hope you have a great week!"
    }
    response = await client.post("/api/obligations/extract", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["detected"] is False
    assert data["obligation"] is None
    assert data["reason"] is not None
