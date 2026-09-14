import pytest

from app.core.status_machine import ObligationType
from app.schemas.llm import AgentInvestigationSummary
from app.schemas.obligation import ObligationCreate
from app.services.obligation_service import ObligationService
from app.services.agents.investigation_agent import (
    InvestigationAgentService,
    INVESTIGATION_SYSTEM_PROMPT,
)


class _FakeAgent:
    def __init__(self, response, captured):
        self._response = response
        self._captured = captured

    async def structured_output_async(self, output_model, prompt=None):
        self._captured["output_model"] = output_model
        self._captured["prompt"] = prompt
        return self._response


@pytest.mark.asyncio
async def test_investigate_wires_tools_and_returns_summary(db_session):
    created = await ObligationService.create(
        db_session,
        ObligationCreate(
            owner="ravi",
            beneficiary="skj",
            action="Ship Strands migration",
            obligation_type=ObligationType.OWED_BY_ME,
        ),
        workspace_id="ws-alpha",
    )

    expected = AgentInvestigationSummary(
        obligation_id=created.id,
        narrative="Blocked on AWS builder account provisioning.",
        root_cause_type="UPSTREAM_CAUSE",
        confidence=0.8,
        grounded_on=["get_obligation_snapshot", "get_root_cause_summary"],
    )
    captured = {}

    def fake_factory(system_prompt, tools=None):
        captured["system_prompt"] = system_prompt
        captured["tool_names"] = [t.tool_name for t in (tools or [])]
        return _FakeAgent(expected, captured)

    service = InvestigationAgentService(agent_factory=fake_factory)

    result = await service.investigate(db_session, created.id, workspace_id="ws-alpha")

    assert result == expected
    assert captured["system_prompt"] == INVESTIGATION_SYSTEM_PROMPT
    assert captured["tool_names"] == [
        "get_obligation_snapshot",
        "get_dependency_chain",
        "get_root_cause_summary",
        "get_related_evidence",
        "get_risk_assessment",
        "get_downstream_impact",
        "get_related_obligations",
        "get_recent_events",
    ]
    assert captured["output_model"] is AgentInvestigationSummary
    assert created.id in captured["prompt"]


@pytest.mark.asyncio
async def test_investigate_passes_the_configured_tool_budget(db_session, monkeypatch):
    from app.core.config import settings
    from app.services.agents import investigation_agent

    monkeypatch.setattr(settings, "STRANDS_MAX_TOOL_CALLS", 2)

    created = await ObligationService.create(
        db_session,
        ObligationCreate(
            owner="ravi",
            beneficiary="skj",
            action="Ship Strands migration",
            obligation_type=ObligationType.OWED_BY_ME,
        ),
        workspace_id="ws-alpha",
    )
    captured = {}

    def spy_build_tools(session, workspace_id, max_calls=None):
        captured["workspace_id"] = workspace_id
        captured["max_calls"] = max_calls
        return []

    monkeypatch.setattr(investigation_agent, "build_obligation_tools", spy_build_tools)

    expected = AgentInvestigationSummary(
        obligation_id=created.id,
        narrative="n",
        root_cause_type="UNCERTAINTY",
        confidence=0.1,
    )
    service = InvestigationAgentService(
        agent_factory=lambda system_prompt, tools=None: _FakeAgent(expected, {})
    )

    await service.investigate(db_session, created.id, workspace_id="ws-alpha")

    assert captured["max_calls"] == 2
    assert captured["workspace_id"] == "ws-alpha"
