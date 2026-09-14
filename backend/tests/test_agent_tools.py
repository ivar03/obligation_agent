import pytest

from app.core.status_machine import EdgeType, ObligationType
from app.schemas.obligation import ObligationCreate, ObligationEdgeCreate
from app.services.graph_service import GraphService
from app.services.obligation_service import ObligationService
from app.services.agents.tools.obligation_tools import build_obligation_tools


def _new_obligation(action: str) -> ObligationCreate:
    return ObligationCreate(
        owner="ravi",
        beneficiary="skj",
        action=action,
        obligation_type=ObligationType.OWED_BY_ME,
    )


@pytest.mark.asyncio
async def test_get_obligation_snapshot_returns_data_for_own_workspace(db_session):
    created = await ObligationService.create(
        db_session, _new_obligation("Send migration doc"), workspace_id="ws-alpha"
    )

    get_obligation_snapshot = build_obligation_tools(db_session, workspace_id="ws-alpha")[0]

    result = await get_obligation_snapshot(obligation_id=created.id)

    assert result["status"] == "success"
    assert created.id in result["content"][0]["text"]


@pytest.mark.asyncio
async def test_get_obligation_snapshot_blocks_cross_workspace_access(db_session):
    created = await ObligationService.create(
        db_session, _new_obligation("Send migration doc"), workspace_id="ws-alpha"
    )

    # Tools built for a DIFFERENT workspace must not see it.
    get_obligation_snapshot = build_obligation_tools(db_session, workspace_id="ws-beta")[0]

    result = await get_obligation_snapshot(obligation_id=created.id)

    assert result["status"] == "error"
    assert "not found" in result["content"][0]["text"]


@pytest.mark.asyncio
async def test_get_dependency_chain_reports_root_blocker(db_session):
    blocker = await ObligationService.create(
        db_session, _new_obligation("Provision AWS builder account"), workspace_id="ws-alpha"
    )
    blocked = await ObligationService.create(
        db_session, _new_obligation("Deploy Strands runtime"), workspace_id="ws-alpha"
    )
    await GraphService.create_edge(
        db_session,
        ObligationEdgeCreate(
            from_obligation_id=blocked.id,
            to_obligation_id=blocker.id,
            edge_type=EdgeType.DEPENDS_ON,
        ),
        workspace_id="ws-alpha",
    )

    get_dependency_chain = build_obligation_tools(db_session, workspace_id="ws-alpha")[1]

    result = await get_dependency_chain(obligation_id=blocked.id)

    assert result["status"] == "success"
    assert blocker.id in result["content"][0]["text"]


@pytest.mark.asyncio
async def test_get_dependency_chain_blocks_cross_workspace_access(db_session):
    created = await ObligationService.create(
        db_session, _new_obligation("Deploy Strands runtime"), workspace_id="ws-alpha"
    )

    get_dependency_chain = build_obligation_tools(db_session, workspace_id="ws-beta")[1]

    result = await get_dependency_chain(obligation_id=created.id)

    assert result["status"] == "error"


@pytest.mark.asyncio
async def test_tool_call_budget_is_enforced(db_session):
    created = await ObligationService.create(
        db_session, _new_obligation("Send migration doc"), workspace_id="ws-alpha"
    )

    tools = build_obligation_tools(db_session, workspace_id="ws-alpha", max_calls=1)
    get_obligation_snapshot, get_dependency_chain, _ = tools

    first = await get_obligation_snapshot(obligation_id=created.id)
    second = await get_dependency_chain(obligation_id=created.id)

    assert first["status"] == "success"
    assert second["status"] == "error"
    assert "budget" in second["content"][0]["text"]


@pytest.mark.asyncio
async def test_tools_expose_expected_names(db_session):
    tools = build_obligation_tools(db_session, workspace_id="ws-alpha")

    assert [t.tool_name for t in tools] == [
        "get_obligation_snapshot",
        "get_dependency_chain",
        "get_root_cause_summary",
    ]
