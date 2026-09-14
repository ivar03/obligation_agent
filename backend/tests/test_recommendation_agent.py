import pytest

from app.core.status_machine import ObligationType
from app.schemas.llm import AgentRecommendation
from app.schemas.obligation import ObligationCreate
from app.services.obligation_service import ObligationService
from app.services.agents.recommendation_agent import (
    RecommendationAgentService,
    RECOMMENDATION_SYSTEM_PROMPT,
)


class _FakeAgent:
    def __init__(self, response, captured):
        self._response = response
        self._captured = captured

    async def structured_output_async(self, output_model, prompt=None):
        self._captured["output_model"] = output_model
        self._captured["prompt"] = prompt
        return self._response


async def _make_obligation(db_session):
    return await ObligationService.create(
        db_session,
        ObligationCreate(owner="ravi", beneficiary="skj", action="Ship the migration",
                         obligation_type=ObligationType.OWED_BY_ME),
        workspace_id="ws-alpha",
    )


@pytest.mark.asyncio
async def test_recommend_returns_recommendation_bound_to_a_decision_plan(db_session):
    created = await _make_obligation(db_session)
    expected = AgentRecommendation(
        obligation_id=created.id,
        recommended_strategy="Escalate to the root blocker's owner",
        rationale="The upstream account provisioning has been blocked for 6 days.",
        expected_outcome="Root blocker unblocks, downstream deadline is met.",
        confidence=0.7,
        grounded_on=["get_root_cause_summary"],
    )
    captured = {}

    service = RecommendationAgentService(
        agent_factory=lambda system_prompt, tools=None: _FakeAgent(expected, captured)
    )
    result = await service.recommend(db_session, created.id, workspace_id="ws-alpha")

    assert result.recommended_strategy == expected.recommended_strategy
    assert result.requires_human_authorization is True
    assert result.decision_plan_id, "recommendation must cite the DecisionPlan it addresses"
    assert captured["output_model"] is AgentRecommendation
    assert created.id in captured["prompt"]


@pytest.mark.asyncio
async def test_recommend_uses_the_recommendation_prompt_and_full_toolkit(db_session):
    created = await _make_obligation(db_session)
    captured = {}

    def factory(system_prompt, tools=None):
        captured["system_prompt"] = system_prompt
        captured["tool_names"] = [t.tool_name for t in (tools or [])]
        return _FakeAgent(
            AgentRecommendation(
                obligation_id=created.id, recommended_strategy="s", rationale="r",
                expected_outcome="o", confidence=0.5,
            ),
            captured,
        )

    await RecommendationAgentService(agent_factory=factory).recommend(
        db_session, created.id, workspace_id="ws-alpha"
    )

    assert captured["system_prompt"] == RECOMMENDATION_SYSTEM_PROMPT
    assert len(captured["tool_names"]) == 8


@pytest.mark.asyncio
async def test_recommend_never_authorizes_even_if_the_model_says_so(db_session):
    """The model does not get a vote on authorization."""
    created = await _make_obligation(db_session)
    rogue = AgentRecommendation(
        obligation_id=created.id, recommended_strategy="s", rationale="r",
        expected_outcome="o", confidence=0.9, requires_human_authorization=False,
    )

    result = await RecommendationAgentService(
        agent_factory=lambda system_prompt, tools=None: _FakeAgent(rogue, {})
    ).recommend(db_session, created.id, workspace_id="ws-alpha")

    assert result.requires_human_authorization is True


@pytest.mark.asyncio
async def test_recommend_rejects_foreign_workspace(db_session):
    created = await _make_obligation(db_session)
    service = RecommendationAgentService(
        agent_factory=lambda system_prompt, tools=None: _FakeAgent(None, {})
    )
    # LookupError, not ValueError: a foreign-workspace obligation is "not found",
    # which the route maps to 404. Configuration failures stay ValueError -> 500.
    with pytest.raises(LookupError):
        await service.recommend(db_session, created.id, workspace_id="ws-beta")

@pytest.mark.asyncio
async def test_unconfigured_runtime_is_not_reported_as_not_found(db_session, monkeypatch):
    """A missing GEMINI_API_KEY is a server misconfiguration, not a missing
    obligation. Reporting it as 404 sends operators hunting the wrong thing at
    exactly the moment of cutover."""
    from app.services.agents import runtime
    created = await _make_obligation(db_session)

    def unconfigured_factory(system_prompt, tools=None):
        raise ValueError("Strands runtime is not configured: GEMINI_API_KEY is missing.")

    service = RecommendationAgentService(agent_factory=unconfigured_factory)

    with pytest.raises(ValueError, match="not configured"):
        await service.recommend(db_session, created.id, workspace_id="ws-alpha")


@pytest.mark.asyncio
async def test_missing_obligation_raises_lookup_error(db_session):
    service = RecommendationAgentService(
        agent_factory=lambda sp, tools=None: _FakeAgent(None, {})
    )
    with pytest.raises(LookupError):
        await service.recommend(db_session, "no-such-obligation", workspace_id="ws-alpha")
