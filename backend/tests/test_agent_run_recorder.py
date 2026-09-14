import pytest
from sqlalchemy import select

from app.core.status_machine import AuditAction, ObligationType
from app.models.audit import AuditEvent
from app.services.agents.agent_run_recorder import record_agent_run
from app.services.agents.tools.obligation_tools import build_obligation_tools
from app.schemas.obligation import ObligationCreate
from app.services.obligation_service import ObligationService


@pytest.mark.asyncio
async def test_successful_run_writes_an_audit_event(db_session):
    counter = {}
    async with record_agent_run(
        db_session, workspace_id="ws-alpha", agent_name="investigation",
        obligation_id="obl-1", counter=counter,
    ) as run:
        counter["calls"] = 3
        assert run["agent_run_id"]

    rows = (await db_session.execute(select(AuditEvent))).scalars().all()
    agent_rows = [r for r in rows if r.action == AuditAction.AGENT_RUN_COMPLETED.value]
    assert len(agent_rows) == 1
    meta = agent_rows[0].audit_metadata
    assert meta["agent_name"] == "investigation"
    assert meta["tool_calls"] == 3
    assert meta["obligation_id"] == "obl-1"
    assert isinstance(meta["latency_ms"], (int, float))


@pytest.mark.asyncio
async def test_failed_run_records_failure_and_reraises(db_session):
    with pytest.raises(RuntimeError, match="boom"):
        async with record_agent_run(
            db_session, workspace_id="ws-alpha", agent_name="investigation",
            obligation_id="obl-1",
        ):
            raise RuntimeError("boom")

    rows = (await db_session.execute(select(AuditEvent))).scalars().all()
    failed = [r for r in rows if r.action == AuditAction.AGENT_RUN_FAILED.value]
    assert len(failed) == 1


@pytest.mark.asyncio
async def test_tool_factory_reports_calls_used(db_session):
    created = await ObligationService.create(
        db_session,
        ObligationCreate(owner="r", beneficiary="s", action="a",
                         obligation_type=ObligationType.OWED_BY_ME),
        workspace_id="ws-alpha",
    )
    counter = {}
    tools = build_obligation_tools(db_session, "ws-alpha", max_calls=5, counter=counter)

    await tools[0](obligation_id=created.id)
    await tools[0](obligation_id=created.id)

    assert counter["calls"] == 2


@pytest.mark.asyncio
async def test_run_record_carries_trace_correlation(db_session):
    async with record_agent_run(
        db_session, workspace_id="ws-alpha", agent_name="investigation",
        obligation_id="obl-1",
    ):
        pass

    rows = (await db_session.execute(select(AuditEvent))).scalars().all()
    meta = rows[0].audit_metadata
    assert meta["trace_id"]
    assert meta["agent_run_id"]