import json

import pytest

from app.core.status_machine import EdgeType, ObligationType
from app.schemas.obligation import ObligationCreate, ObligationEdgeCreate
from app.services.graph_service import GraphService
from app.services.obligation_service import ObligationService
from app.services.agents.tools.obligation_tools import build_obligation_tools

TOOL_NAMES = [
    "get_obligation_snapshot",
    "get_dependency_chain",
    "get_root_cause_summary",
    "get_related_evidence",
    "get_risk_assessment",
    "get_downstream_impact",
    "get_related_obligations",
    "get_recent_events",
]


def _ob(action: str) -> ObligationCreate:
    return ObligationCreate(
        owner="ravi", beneficiary="skj", action=action,
        obligation_type=ObligationType.OWED_BY_ME,
    )


def _tool(tools, name):
    return next(t for t in tools if t.tool_name == name)


@pytest.mark.asyncio
async def test_toolkit_exposes_all_eight_tools_in_order(db_session):
    tools = build_obligation_tools(db_session, workspace_id="ws-alpha")
    assert [t.tool_name for t in tools] == TOOL_NAMES


@pytest.mark.asyncio
async def test_get_related_evidence_returns_json_list(db_session):
    created = await ObligationService.create(db_session, _ob("Send doc"), workspace_id="ws-alpha")
    tools = build_obligation_tools(db_session, workspace_id="ws-alpha")

    result = await _tool(tools, "get_related_evidence")(obligation_id=created.id)

    assert result["status"] == "success"
    assert isinstance(json.loads(result["content"][0]["text"]), list)


@pytest.mark.asyncio
async def test_get_risk_assessment_returns_payload(db_session):
    created = await ObligationService.create(db_session, _ob("Send doc"), workspace_id="ws-alpha")
    tools = build_obligation_tools(db_session, workspace_id="ws-alpha")

    result = await _tool(tools, "get_risk_assessment")(obligation_id=created.id)

    assert result["status"] == "success"


@pytest.mark.asyncio
async def test_get_downstream_impact_lists_dependents(db_session):
    blocker = await ObligationService.create(db_session, _ob("Provision account"), workspace_id="ws-alpha")
    blocked = await ObligationService.create(db_session, _ob("Deploy runtime"), workspace_id="ws-alpha")
    await GraphService.create_edge(
        db_session,
        ObligationEdgeCreate(
            from_obligation_id=blocked.id, to_obligation_id=blocker.id,
            edge_type=EdgeType.DEPENDS_ON,
        ),
        workspace_id="ws-alpha",
    )
    tools = build_obligation_tools(db_session, workspace_id="ws-alpha")

    result = await _tool(tools, "get_downstream_impact")(obligation_id=blocker.id)

    assert result["status"] == "success"
    assert blocked.id in result["content"][0]["text"]


@pytest.mark.asyncio
async def test_get_recent_events_returns_json(db_session):
    tools = build_obligation_tools(db_session, workspace_id="ws-alpha")

    result = await _tool(tools, "get_recent_events")(obligation_id="anything")

    assert result["status"] == "success"
    assert isinstance(json.loads(result["content"][0]["text"]), list)


@pytest.mark.asyncio
async def test_every_new_tool_blocks_cross_workspace_access(db_session):
    created = await ObligationService.create(db_session, _ob("Secret"), workspace_id="ws-alpha")
    tools = build_obligation_tools(db_session, workspace_id="ws-beta")

    for name in ("get_related_evidence", "get_risk_assessment",
                 "get_downstream_impact", "get_related_obligations"):
        result = await _tool(tools, name)(obligation_id=created.id)
        assert result["status"] == "error", f"{name} leaked across workspaces"


@pytest.mark.asyncio
async def test_no_tool_declares_a_workspace_parameter(db_session):
    """The model must never be able to name a workspace."""
    tools = build_obligation_tools(db_session, workspace_id="ws-alpha")
    for t in tools:
        props = t.tool_spec["inputSchema"]["json"]["properties"]
        assert "workspace_id" not in props, f"{t.tool_name} exposes workspace_id to the model"


@pytest.mark.asyncio
async def test_budget_is_shared_across_all_tools(db_session):
    created = await ObligationService.create(db_session, _ob("Send doc"), workspace_id="ws-alpha")
    tools = build_obligation_tools(db_session, workspace_id="ws-alpha", max_calls=2)

    first = await _tool(tools, "get_obligation_snapshot")(obligation_id=created.id)
    second = await _tool(tools, "get_related_evidence")(obligation_id=created.id)
    third = await _tool(tools, "get_risk_assessment")(obligation_id=created.id)

    assert first["status"] == "success"
    assert second["status"] == "success"
    assert third["status"] == "error"
    assert "budget" in third["content"][0]["text"]