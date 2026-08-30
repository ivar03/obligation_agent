import pytest
from datetime import datetime, timedelta, timezone
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_dashboard_summary(client: AsyncClient):
    now = datetime.now(timezone.utc)

    # 1. You Owe obligation (Active)
    await client.post("/api/obligations", json={
        "owner": "Ravi",
        "beneficiary": "Rahul",
        "action": "Send API docs",
        "obligation_type": "OWED_BY_ME",
        "status": "CONFIRMED",
        "deadline": (now + timedelta(days=5)).isoformat(),
    })

    # 2. Others Owe You (Active)
    await client.post("/api/obligations", json={
        "owner": "Rahul",
        "beneficiary": "Ravi",
        "action": "Send benchmark results",
        "obligation_type": "OWED_TO_ME",
        "status": "CONFIRMED",
        "deadline": (now + timedelta(days=5)).isoformat(),
    })

    # 3. At Risk (Overdue)
    await client.post("/api/obligations", json={
        "owner": "Vendor",
        "beneficiary": "Ravi",
        "action": "Deliver server parts",
        "obligation_type": "OWED_TO_ME",
        "status": "OVERDUE",
        "deadline": (now - timedelta(days=1)).isoformat(),
    })

    # 4. Completed obligation
    await client.post("/api/obligations", json={
        "owner": "Ravi",
        "beneficiary": "Security",
        "action": "Rotate keys",
        "obligation_type": "OWED_BY_ME",
        "status": "COMPLETED",
    })

    res = await client.get("/api/dashboard/summary")
    assert res.status_code == 200
    data = res.json()
    assert data["you_owe_count"] >= 1
    assert data["others_owe_count"] >= 2  # Including the overdue one owed to me
    assert data["at_risk_count"] >= 1
    assert data["completed_count"] >= 1
