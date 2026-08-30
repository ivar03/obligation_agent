import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_extract_valid_obligation(client: AsyncClient):
    response = await client.post(
        "/api/obligations/extract",
        json={"text": "Ravi owes Rahul: Send the API documentation by Friday."}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["detected"] is True
    assert data["obligation"] is not None
    assert data["obligation"]["owner"] == "You"
    assert data["obligation"]["beneficiary"] == "Rahul"
    assert "API documentation" in data["obligation"]["action"]
    assert data["obligation"]["obligation_type"] == "OWED_BY_ME"
    assert data["obligation"]["confidence"]["overall"] >= 0.8


@pytest.mark.asyncio
async def test_extract_no_obligation(client: AsyncClient):
    response = await client.post(
        "/api/obligations/extract",
        json={"text": "Hello, good morning! Hope you have a wonderful day."}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["detected"] is False
    assert data["obligation"] is None
    assert data["reason"] is not None


@pytest.mark.asyncio
async def test_extract_ambiguous_ownership(client: AsyncClient):
    response = await client.post(
        "/api/obligations/extract",
        json={"text": "We should probably send this to the client tomorrow."}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["detected"] is True
    assert data["obligation"] is not None
    # Ambiguous ownership flagged with low confidence
    assert data["obligation"]["confidence"]["owner"] < 0.6
    assert "Ambiguous" in data["obligation"]["owner"]


@pytest.mark.asyncio
async def test_extract_conditional_obligation(client: AsyncClient):
    response = await client.post(
        "/api/obligations/extract",
        json={"text": "Professor owes Ravi: Review the project report after Ravi submits it."}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["detected"] is True
    assert data["obligation"]["owner"] == "Professor"
    assert data["obligation"]["beneficiary"] == "You"
    assert data["obligation"]["obligation_type"] == "OWED_TO_ME"
    assert data["obligation"]["conditions"] is not None
