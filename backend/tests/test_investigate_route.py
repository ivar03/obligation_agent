import pytest

import app.api.routes.llm_intelligence as llm_intelligence_routes
from app.schemas.llm import AgentInvestigationSummary


class _FakeInvestigationAgentService:
    async def investigate(self, session, obligation_id, workspace_id):
        _FakeInvestigationAgentService.last_workspace_id = workspace_id
        return AgentInvestigationSummary(
            obligation_id=obligation_id,
            narrative="Test narrative.",
            root_cause_type="DIRECT_CAUSE",
            confidence=0.5,
            grounded_on=["get_obligation_snapshot"],
        )


@pytest.mark.asyncio
async def test_investigate_endpoint_returns_summary(client, monkeypatch):
    monkeypatch.setattr(
        llm_intelligence_routes, "InvestigationAgentService", _FakeInvestigationAgentService
    )

    resp = await client.post(
        "/api/intelligence/llm/investigate",
        json={"obligation_id": "obl-123", "workspace_id": "ws-alpha"},
    )

    assert resp.status_code == 200
    body = resp.json()
    assert body["obligation_id"] == "obl-123"
    assert body["narrative"] == "Test narrative."
    assert body["grounded_on"] == ["get_obligation_snapshot"]
    assert _FakeInvestigationAgentService.last_workspace_id == "ws-alpha"


@pytest.mark.asyncio
async def test_investigate_endpoint_defaults_workspace(client, monkeypatch):
    monkeypatch.setattr(
        llm_intelligence_routes, "InvestigationAgentService", _FakeInvestigationAgentService
    )

    resp = await client.post(
        "/api/intelligence/llm/investigate", json={"obligation_id": "obl-123"}
    )

    assert resp.status_code == 200
    assert _FakeInvestigationAgentService.last_workspace_id == "ws-default"


@pytest.mark.asyncio
async def test_investigate_endpoint_requires_obligation_id(client):
    resp = await client.post("/api/intelligence/llm/investigate", json={})

    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_investigate_endpoint_reports_agent_failure(client, monkeypatch):
    class _ExplodingService:
        async def investigate(self, session, obligation_id, workspace_id):
            raise RuntimeError("gemini unreachable")

    monkeypatch.setattr(
        llm_intelligence_routes, "InvestigationAgentService", _ExplodingService
    )

    resp = await client.post(
        "/api/intelligence/llm/investigate", json={"obligation_id": "obl-123"}
    )

    assert resp.status_code == 500
