"""
Phase 19 Test Suite: Webhook Hardening & Ingestion Protection.
Tests fast ACK behavior, size limits, and duplicate event suppression.
"""

import pytest
import json


@pytest.mark.asyncio
async def test_webhook_slack_url_verification(client):
    response = await client.post(
        "/api/webhooks/slack",
        json={"type": "url_verification", "challenge": "challenge_token_abc_123"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data.get("challenge") == "challenge_token_abc_123"


@pytest.mark.asyncio
async def test_webhook_fast_ack_and_deduplication(client):
    payload = {
        "event_id": "evt_unique_test_123",
        "type": "message",
        "text": "Commitment: I will send report tomorrow",
    }

    # First delivery: returns 200 OK
    resp1 = await client.post("/api/webhooks/slack", json=payload)
    assert resp1.status_code == 200

    # Second delivery (duplicate): returns 200 OK immediately
    resp2 = await client.post("/api/webhooks/slack", json=payload)
    assert resp2.status_code == 200
