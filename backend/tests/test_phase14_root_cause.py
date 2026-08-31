import pytest
import pytest_asyncio
from datetime import datetime, timezone, timedelta
from typing import AsyncGenerator
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy import select

from app.main import app
from app.models.obligation import Obligation, ObligationEdge, Evidence, Intervention, Base
from app.models.auth import User, Workspace, WorkspaceMembership
from app.core.database import get_db
from app.core.status_machine import (
    ObligationStatus,
    ObligationType,
    EdgeType,
    CausalFactorType,
    ResolutionStrategyType,
    SimulationActionType,
    ConcentrationType,
    WorkspaceRole,
)
from app.services.graph_service import GraphService
from app.services.intelligence.root_cause_engine import RootCauseAnalysisEngine
from app.services.intelligence.impact_analysis_service import ImpactAnalysisService
from app.services.intelligence.critical_path_engine import CriticalPathEngine
from app.services.intelligence.resolution_planner import ResolutionPlanner
from app.services.intelligence.resolution_simulation_service import ResolutionSimulationService
from app.services.intelligence.risk_concentration_service import RiskConcentrationService
from app.schemas.intelligence import ResolutionSimulationRequest

from app.services.auth_service import AuthService

TEST_DB_URL = "sqlite+aiosqlite:///:memory:"


@pytest_asyncio.fixture(scope="function")
async def test_session() -> AsyncGenerator[AsyncSession, None]:
    engine = create_async_engine(TEST_DB_URL, echo=False)
    async_session = async_sessionmaker(engine, expire_on_commit=False)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with async_session() as session:
        # Create default workspace and user using AuthService
        await AuthService.ensure_default_dev_user(session)
        yield session

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

    await engine.dispose()


@pytest_asyncio.fixture(scope="function")
async def client(test_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    async def override_get_db():
        try:
            yield test_session
            await test_session.commit()
        except Exception:
            await test_session.rollback()
            raise

    app.dependency_overrides[get_db] = override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()


# ==============================================================================
# 1. ROOT-CAUSE ANALYSIS TESTS
# ==============================================================================

@pytest.mark.asyncio
async def test_01_single_direct_blocker(test_session: AsyncSession):
    # A (overdue) -> B (blocked)
    ob_a = Obligation(
        id="ob-a", workspace_id="ws-default", owner="Rahul", beneficiary="Team", action="Deliver benchmark",
        status=ObligationStatus.OVERDUE, obligation_type=ObligationType.OWED_BY_ME
    )
    ob_b = Obligation(
        id="ob-b", workspace_id="ws-default", owner="Ravi", beneficiary="Team", action="Benchmark analysis",
        status=ObligationStatus.BLOCKED, obligation_type=ObligationType.OWED_BY_ME
    )
    edge = ObligationEdge(
        id="edge-1", workspace_id="ws-default", from_obligation_id="ob-b", to_obligation_id="ob-a", edge_type=EdgeType.DEPENDS_ON
    )
    test_session.add_all([ob_a, ob_b, edge])
    await test_session.commit()

    res = await RootCauseAnalysisEngine.analyze(test_session, "ob-b")
    assert res.obligation_id == "ob-b"
    assert res.primary_root_cause != ""
    assert res.root_cause_type in (CausalFactorType.DIRECT_CAUSE, CausalFactorType.UPSTREAM_CAUSE)
    assert len(res.direct_causes) >= 1
    assert "Rahul" in res.direct_causes[0].target_owner
    assert res.confidence >= 0.80


@pytest.mark.asyncio
async def test_02_multi_hop_root_blocker(test_session: AsyncSession):
    # A (Rahul, overdue) -> B (Ravi, blocked) -> C (Priya, blocked) -> D (Manager, blocked)
    ob_a = Obligation(id="ob-a", workspace_id="ws-default", owner="Rahul", beneficiary="Team", action="Raw Data", status=ObligationStatus.OVERDUE, obligation_type=ObligationType.OWED_BY_ME)
    ob_b = Obligation(id="ob-b", workspace_id="ws-default", owner="Ravi", beneficiary="Team", action="Analysis", status=ObligationStatus.BLOCKED, obligation_type=ObligationType.OWED_BY_ME)
    ob_c = Obligation(id="ob-c", workspace_id="ws-default", owner="Priya", beneficiary="Team", action="Briefing", status=ObligationStatus.BLOCKED, obligation_type=ObligationType.OWED_BY_ME)
    ob_d = Obligation(id="ob-d", workspace_id="ws-default", owner="Manager", beneficiary="Exec", action="Executive Review", status=ObligationStatus.BLOCKED, obligation_type=ObligationType.OWED_BY_ME)

    e1 = ObligationEdge(id="e1", workspace_id="ws-default", from_obligation_id="ob-b", to_obligation_id="ob-a", edge_type=EdgeType.DEPENDS_ON)
    e2 = ObligationEdge(id="e2", workspace_id="ws-default", from_obligation_id="ob-c", to_obligation_id="ob-b", edge_type=EdgeType.DEPENDS_ON)
    e3 = ObligationEdge(id="e3", workspace_id="ws-default", from_obligation_id="ob-d", to_obligation_id="ob-c", edge_type=EdgeType.DEPENDS_ON)

    test_session.add_all([ob_a, ob_b, ob_c, ob_d, e1, e2, e3])
    await test_session.commit()

    # Analyze D: root cause must be Rahul's A
    res = await RootCauseAnalysisEngine.analyze(test_session, "ob-d")
    assert res.obligation_id == "ob-d"
    assert res.root_cause_type == CausalFactorType.UPSTREAM_CAUSE
    assert "Rahul" in res.primary_root_cause or "Raw Data" in res.primary_root_cause
    assert len(res.upstream_causes) >= 1
    assert res.upstream_causes[0].target_obligation_id == "ob-a"
    assert len(res.dependency_path) >= 3


@pytest.mark.asyncio
async def test_03_multiple_prerequisites_branching(test_session: AsyncSession):
    # A (overdue) -> B (blocked), C (completed) -> D (blocked on B and C)
    ob_a = Obligation(id="ob-a", workspace_id="ws-default", owner="Alice", beneficiary="Team", action="Architecture Doc", status=ObligationStatus.OVERDUE, obligation_type=ObligationType.OWED_BY_ME)
    ob_b = Obligation(id="ob-b", workspace_id="ws-default", owner="Bob", beneficiary="Team", action="Backend Module", status=ObligationStatus.BLOCKED, obligation_type=ObligationType.OWED_BY_ME)
    ob_c = Obligation(id="ob-c", workspace_id="ws-default", owner="Charlie", beneficiary="Team", action="Frontend Module", status=ObligationStatus.COMPLETED, obligation_type=ObligationType.OWED_BY_ME)
    ob_d = Obligation(id="ob-d", workspace_id="ws-default", owner="Lead", beneficiary="Team", action="Integration Release", status=ObligationStatus.BLOCKED, obligation_type=ObligationType.OWED_BY_ME)

    e1 = ObligationEdge(id="e1", workspace_id="ws-default", from_obligation_id="ob-b", to_obligation_id="ob-a", edge_type=EdgeType.DEPENDS_ON)
    e2 = ObligationEdge(id="e2", workspace_id="ws-default", from_obligation_id="ob-d", to_obligation_id="ob-b", edge_type=EdgeType.DEPENDS_ON)
    e3 = ObligationEdge(id="e3", workspace_id="ws-default", from_obligation_id="ob-d", to_obligation_id="ob-c", edge_type=EdgeType.DEPENDS_ON)

    test_session.add_all([ob_a, ob_b, ob_c, ob_d, e1, e2, e3])
    await test_session.commit()

    res = await RootCauseAnalysisEngine.analyze(test_session, "ob-d")
    # Only branch A -> B is causing blockage, C is completed
    assert "Alice" in res.overall_explanation or "Architecture Doc" in res.overall_explanation


@pytest.mark.asyncio
async def test_04_linked_relationship_ignored_as_blocker(test_session: AsyncSession):
    # A is LINKED to B; B is OVERDUE, but B does not block A
    ob_a = Obligation(id="ob-a", workspace_id="ws-default", owner="Alice", beneficiary="Team", action="Marketing blog", status=ObligationStatus.IN_PROGRESS, obligation_type=ObligationType.OWED_BY_ME)
    ob_b = Obligation(id="ob-b", workspace_id="ws-default", owner="Bob", beneficiary="Team", action="Sales deck", status=ObligationStatus.OVERDUE, obligation_type=ObligationType.OWED_BY_ME)
    edge = ObligationEdge(id="edge-link", workspace_id="ws-default", from_obligation_id="ob-a", to_obligation_id="ob-b", edge_type=EdgeType.LINKED)

    test_session.add_all([ob_a, ob_b, edge])
    await test_session.commit()

    res = await RootCauseAnalysisEngine.analyze(test_session, "ob-a")
    # A should NOT be marked as blocked by B
    assert res.root_cause_type != CausalFactorType.UPSTREAM_CAUSE
    assert not any(dc.target_obligation_id == "ob-b" for dc in res.direct_causes)


@pytest.mark.asyncio
async def test_05_independent_risk_distinguished_from_dependency_risk(test_session: AsyncSession):
    # A is OVERDUE on its own (past deadline) with no upstream dependencies
    now = datetime.now(timezone.utc)
    ob_a = Obligation(
        id="ob-ind", workspace_id="ws-default", owner="Alice", beneficiary="Gov", action="Tax filing",
        status=ObligationStatus.OVERDUE, deadline=now - timedelta(days=2), obligation_type=ObligationType.OWED_BY_ME
    )
    test_session.add(ob_a)
    await test_session.commit()

    res = await RootCauseAnalysisEngine.analyze(test_session, "ob-ind")
    assert res.root_cause_type == CausalFactorType.DIRECT_CAUSE
    assert "deadline" in res.primary_root_cause.lower()
    assert len(res.upstream_causes) == 0


@pytest.mark.asyncio
async def test_06_ambiguous_causal_situation(test_session: AsyncSession):
    # Obligation with no owner, no deadline, DETECTED
    ob = Obligation(id="ob-unassigned", workspace_id="ws-default", owner="Unassigned", beneficiary="Team", action="TBD research", status=ObligationStatus.DETECTED, obligation_type=ObligationType.OWED_BY_ME)
    test_session.add(ob)
    await test_session.commit()

    res = await RootCauseAnalysisEngine.analyze(test_session, "ob-unassigned")
    assert any("owner" in dc.description.lower() for dc in res.direct_causes)


@pytest.mark.asyncio
async def test_07_root_cause_confidence_levels(test_session: AsyncSession):
    ob = Obligation(id="ob-conf", workspace_id="ws-default", owner="Alice", beneficiary="Team", action="Deploy prod", status=ObligationStatus.IN_PROGRESS, obligation_type=ObligationType.OWED_BY_ME)
    test_session.add(ob)
    await test_session.commit()

    res = await RootCauseAnalysisEngine.analyze(test_session, "ob-conf")
    assert 0.0 <= res.confidence <= 1.0
    assert res.confidence_level in ("HIGH", "MEDIUM", "LOW")


@pytest.mark.asyncio
async def test_08_evidence_provenance_tracking(test_session: AsyncSession):
    ob = Obligation(id="ob-ev", workspace_id="ws-default", owner="Alice", beneficiary="Team", action="Deploy prod", status=ObligationStatus.IN_PROGRESS, obligation_type=ObligationType.OWED_BY_ME)
    ev = Evidence(id="ev-1", obligation_id="ob-ev", workspace_id="ws-default", source_type="message", source_ref="ref-1", content="PR merged", observed_at=datetime.now(timezone.utc))
    test_session.add_all([ob, ev])
    await test_session.commit()

    res = await RootCauseAnalysisEngine.analyze(test_session, "ob-ev")
    assert "ev-1" in res.evidence_refs


# ==============================================================================
# 2. IMPACT ANALYSIS TESTS
# ==============================================================================

@pytest.mark.asyncio
async def test_09_direct_dependent_count(test_session: AsyncSession):
    # Root A -> B, Root A -> C
    ob_a = Obligation(id="ob-root", workspace_id="ws-default", owner="Root", beneficiary="Team", action="DB Migration", status=ObligationStatus.IN_PROGRESS, obligation_type=ObligationType.OWED_BY_ME)
    ob_b = Obligation(id="ob-d1", workspace_id="ws-default", owner="Dev1", beneficiary="Team", action="API update", status=ObligationStatus.BLOCKED, obligation_type=ObligationType.OWED_BY_ME)
    ob_c = Obligation(id="ob-d2", workspace_id="ws-default", owner="Dev2", beneficiary="Team", action="Web update", status=ObligationStatus.BLOCKED, obligation_type=ObligationType.OWED_BY_ME)

    e1 = ObligationEdge(id="e1", workspace_id="ws-default", from_obligation_id="ob-d1", to_obligation_id="ob-root", edge_type=EdgeType.DEPENDS_ON)
    e2 = ObligationEdge(id="e2", workspace_id="ws-default", from_obligation_id="ob-d2", to_obligation_id="ob-root", edge_type=EdgeType.DEPENDS_ON)

    test_session.add_all([ob_a, ob_b, ob_c, e1, e2])
    await test_session.commit()

    impact = await ImpactAnalysisService.analyze_impact(test_session, "ob-root")
    assert impact.direct_dependents_count == 2
    assert impact.total_downstream_dependents_count == 2


@pytest.mark.asyncio
async def test_10_multi_hop_downstream_count(test_session: AsyncSession):
    # A -> B -> C -> D
    ob_a = Obligation(id="ob-1", workspace_id="ws-default", owner="A", beneficiary="Team", action="A", status=ObligationStatus.IN_PROGRESS, obligation_type=ObligationType.OWED_BY_ME)
    ob_b = Obligation(id="ob-2", workspace_id="ws-default", owner="B", beneficiary="Team", action="B", status=ObligationStatus.BLOCKED, obligation_type=ObligationType.OWED_BY_ME)
    ob_c = Obligation(id="ob-3", workspace_id="ws-default", owner="C", beneficiary="Team", action="C", status=ObligationStatus.BLOCKED, obligation_type=ObligationType.OWED_BY_ME)
    ob_d = Obligation(id="ob-4", workspace_id="ws-default", owner="D", beneficiary="Team", action="D", status=ObligationStatus.BLOCKED, obligation_type=ObligationType.OWED_BY_ME)

    e1 = ObligationEdge(id="e1", workspace_id="ws-default", from_obligation_id="ob-2", to_obligation_id="ob-1", edge_type=EdgeType.DEPENDS_ON)
    e2 = ObligationEdge(id="e2", workspace_id="ws-default", from_obligation_id="ob-3", to_obligation_id="ob-2", edge_type=EdgeType.DEPENDS_ON)
    e3 = ObligationEdge(id="e3", workspace_id="ws-default", from_obligation_id="ob-4", to_obligation_id="ob-3", edge_type=EdgeType.DEPENDS_ON)

    test_session.add_all([ob_a, ob_b, ob_c, ob_d, e1, e2, e3])
    await test_session.commit()

    impact = await ImpactAnalysisService.analyze_impact(test_session, "ob-1")
    assert impact.direct_dependents_count == 1
    assert impact.total_downstream_dependents_count == 3
    assert impact.maximum_dependency_depth == 3


@pytest.mark.asyncio
async def test_11_affected_owners_deduplication(test_session: AsyncSession):
    ob_a = Obligation(id="ob-a", workspace_id="ws-default", owner="Alice", beneficiary="Team", action="Core Lib", status=ObligationStatus.IN_PROGRESS, obligation_type=ObligationType.OWED_BY_ME)
    ob_b1 = Obligation(id="ob-b1", workspace_id="ws-default", owner="Bob", beneficiary="Team", action="Module 1", status=ObligationStatus.BLOCKED, obligation_type=ObligationType.OWED_BY_ME)
    ob_b2 = Obligation(id="ob-b2", workspace_id="ws-default", owner="Bob", beneficiary="Team", action="Module 2", status=ObligationStatus.BLOCKED, obligation_type=ObligationType.OWED_BY_ME)

    e1 = ObligationEdge(id="e1", workspace_id="ws-default", from_obligation_id="ob-b1", to_obligation_id="ob-a", edge_type=EdgeType.DEPENDS_ON)
    e2 = ObligationEdge(id="e2", workspace_id="ws-default", from_obligation_id="ob-b2", to_obligation_id="ob-a", edge_type=EdgeType.DEPENDS_ON)

    test_session.add_all([ob_a, ob_b1, ob_b2, e1, e2])
    await test_session.commit()

    impact = await ImpactAnalysisService.analyze_impact(test_session, "ob-a")
    assert impact.affected_owners == ["Bob"]


@pytest.mark.asyncio
async def test_12_affected_deadlines_capture(test_session: AsyncSession):
    now = datetime.now(timezone.utc)
    ob_a = Obligation(id="ob-a", workspace_id="ws-default", owner="Alice", beneficiary="Team", action="Step 1", status=ObligationStatus.IN_PROGRESS, obligation_type=ObligationType.OWED_BY_ME)
    ob_b = Obligation(id="ob-b", workspace_id="ws-default", owner="Bob", beneficiary="Team", action="Step 2", status=ObligationStatus.BLOCKED, deadline=now + timedelta(days=1), obligation_type=ObligationType.OWED_BY_ME)
    e1 = ObligationEdge(id="e1", workspace_id="ws-default", from_obligation_id="ob-b", to_obligation_id="ob-a", edge_type=EdgeType.DEPENDS_ON)

    test_session.add_all([ob_a, ob_b, e1])
    await test_session.commit()

    impact = await ImpactAnalysisService.analyze_impact(test_session, "ob-a")
    assert len(impact.affected_deadlines) == 1


@pytest.mark.asyncio
async def test_13_impact_score_bounded_guarantee(test_session: AsyncSession):
    ob_a = Obligation(id="ob-iso", workspace_id="ws-default", owner="Solo", beneficiary="Team", action="Isolated task", status=ObligationStatus.IN_PROGRESS, obligation_type=ObligationType.OWED_BY_ME)
    test_session.add(ob_a)
    await test_session.commit()

    impact = await ImpactAnalysisService.analyze_impact(test_session, "ob-iso")
    assert 0.0 <= impact.impact_score <= 1.0
    assert impact.impact_level == "LOW"
    assert "raw_total" in impact.score_breakdown


# ==============================================================================
# 3. CRITICAL PATH TESTS
# ==============================================================================

@pytest.mark.asyncio
async def test_14_linear_critical_path(test_session: AsyncSession):
    # A -> B -> C
    ob_a = Obligation(id="ob-a", workspace_id="ws-default", owner="Rahul", beneficiary="Team", action="Raw Data", status=ObligationStatus.OVERDUE, obligation_type=ObligationType.OWED_BY_ME)
    ob_b = Obligation(id="ob-b", workspace_id="ws-default", owner="Ravi", beneficiary="Team", action="Analysis", status=ObligationStatus.BLOCKED, obligation_type=ObligationType.OWED_BY_ME)
    ob_c = Obligation(id="ob-c", workspace_id="ws-default", owner="Priya", beneficiary="Team", action="Briefing", status=ObligationStatus.BLOCKED, obligation_type=ObligationType.OWED_BY_ME)

    e1 = ObligationEdge(id="e1", workspace_id="ws-default", from_obligation_id="ob-b", to_obligation_id="ob-a", edge_type=EdgeType.DEPENDS_ON)
    e2 = ObligationEdge(id="e2", workspace_id="ws-default", from_obligation_id="ob-c", to_obligation_id="ob-b", edge_type=EdgeType.DEPENDS_ON)

    test_session.add_all([ob_a, ob_b, ob_c, e1, e2])
    await test_session.commit()

    cp = await CriticalPathEngine.compute_critical_path(test_session, "ob-c")
    assert cp.critical_path == ["ob-a", "ob-b", "ob-c"]
    assert cp.critical_path_length == 3
    assert cp.root_blocker_id == "ob-a"
    assert cp.root_blocker_owner == "Rahul"


@pytest.mark.asyncio
async def test_15_branching_dag_highest_risk_path_selection(test_session: AsyncSession):
    # Path 1: A (Rahul, overdue) -> C (Target)
    # Path 2: B (Bob, completed) -> C (Target)
    ob_a = Obligation(id="ob-a", workspace_id="ws-default", owner="Rahul", beneficiary="Team", action="Critical DB", status=ObligationStatus.OVERDUE, obligation_type=ObligationType.OWED_BY_ME)
    ob_b = Obligation(id="ob-b", workspace_id="ws-default", owner="Bob", beneficiary="Team", action="Minor CSS", status=ObligationStatus.COMPLETED, obligation_type=ObligationType.OWED_BY_ME)
    ob_c = Obligation(id="ob-c", workspace_id="ws-default", owner="Lead", beneficiary="Team", action="Release", status=ObligationStatus.BLOCKED, obligation_type=ObligationType.OWED_BY_ME)

    e1 = ObligationEdge(id="e1", workspace_id="ws-default", from_obligation_id="ob-c", to_obligation_id="ob-a", edge_type=EdgeType.DEPENDS_ON)
    e2 = ObligationEdge(id="e2", workspace_id="ws-default", from_obligation_id="ob-c", to_obligation_id="ob-b", edge_type=EdgeType.DEPENDS_ON)

    test_session.add_all([ob_a, ob_b, ob_c, e1, e2])
    await test_session.commit()

    cp = await CriticalPathEngine.compute_critical_path(test_session, "ob-c")
    assert cp.root_blocker_id == "ob-a"
    assert cp.critical_path == ["ob-a", "ob-c"]


@pytest.mark.asyncio
async def test_16_completed_root_recalculation(test_session: AsyncSession):
    # A (completed) -> B (in progress) -> C (blocked on B)
    ob_a = Obligation(id="ob-a", workspace_id="ws-default", owner="Rahul", beneficiary="Team", action="Step 1", status=ObligationStatus.COMPLETED, obligation_type=ObligationType.OWED_BY_ME)
    ob_b = Obligation(id="ob-b", workspace_id="ws-default", owner="Ravi", beneficiary="Team", action="Step 2", status=ObligationStatus.IN_PROGRESS, obligation_type=ObligationType.OWED_BY_ME)
    ob_c = Obligation(id="ob-c", workspace_id="ws-default", owner="Priya", beneficiary="Team", action="Step 3", status=ObligationStatus.BLOCKED, obligation_type=ObligationType.OWED_BY_ME)

    e1 = ObligationEdge(id="e1", workspace_id="ws-default", from_obligation_id="ob-b", to_obligation_id="ob-a", edge_type=EdgeType.DEPENDS_ON)
    e2 = ObligationEdge(id="e2", workspace_id="ws-default", from_obligation_id="ob-c", to_obligation_id="ob-b", edge_type=EdgeType.DEPENDS_ON)

    test_session.add_all([ob_a, ob_b, ob_c, e1, e2])
    await test_session.commit()

    cp = await CriticalPathEngine.compute_critical_path(test_session, "ob-c")
    # A is completed, so B is the active root blocker for C
    assert cp.critical_path_length >= 2


# ==============================================================================
# 4. RESOLUTION PLANNING TESTS
# ==============================================================================

@pytest.mark.asyncio
async def test_17_upstream_first_resolution_plan(test_session: AsyncSession):
    # A (Rahul, overdue) -> B (Ravi, blocked) -> C (Priya, blocked)
    ob_a = Obligation(id="ob-a", workspace_id="ws-default", owner="Rahul", beneficiary="Team", action="Benchmark numbers", status=ObligationStatus.OVERDUE, obligation_type=ObligationType.OWED_BY_ME)
    ob_b = Obligation(id="ob-b", workspace_id="ws-default", owner="Ravi", beneficiary="Team", action="Analysis", status=ObligationStatus.BLOCKED, obligation_type=ObligationType.OWED_BY_ME)
    ob_c = Obligation(id="ob-c", workspace_id="ws-default", owner="Priya", beneficiary="Exec", action="Executive briefing", status=ObligationStatus.BLOCKED, obligation_type=ObligationType.OWED_BY_ME)

    e1 = ObligationEdge(id="e1", workspace_id="ws-default", from_obligation_id="ob-b", to_obligation_id="ob-a", edge_type=EdgeType.DEPENDS_ON)
    e2 = ObligationEdge(id="e2", workspace_id="ws-default", from_obligation_id="ob-c", to_obligation_id="ob-b", edge_type=EdgeType.DEPENDS_ON)

    test_session.add_all([ob_a, ob_b, ob_c, e1, e2])
    await test_session.commit()

    # When planning resolution for C (Priya's obligation), target must be Rahul (upstream root)
    plan = await ResolutionPlanner.plan_resolution(test_session, "ob-c")
    assert plan.target_obligation_id == "ob-a"
    assert plan.target_owner == "Rahul"
    assert plan.strategy == ResolutionStrategyType.FOLLOW_UP_ROOT_OWNER
    assert "Rahul" in plan.rationale


@pytest.mark.asyncio
async def test_18_assign_owner_recommendation(test_session: AsyncSession):
    ob = Obligation(id="ob-no-owner", workspace_id="ws-default", owner="Unassigned", beneficiary="Team", action="Draft contract", status=ObligationStatus.DETECTED, obligation_type=ObligationType.OWED_BY_ME)
    test_session.add(ob)
    await test_session.commit()

    plan = await ResolutionPlanner.plan_resolution(test_session, "ob-no-owner")
    assert plan.strategy == ResolutionStrategyType.ASSIGN_OWNER


@pytest.mark.asyncio
async def test_19_missing_evidence_recommendation(test_session: AsyncSession):
    ob = Obligation(id="ob-no-ev", workspace_id="ws-default", owner="Alice", beneficiary="Team", action="Deploy code", status=ObligationStatus.IN_PROGRESS, obligation_type=ObligationType.OWED_BY_ME)
    test_session.add(ob)
    await test_session.commit()

    plan = await ResolutionPlanner.plan_resolution(test_session, "ob-no-ev")
    assert plan.strategy in (ResolutionStrategyType.REQUEST_MISSING_EVIDENCE, ResolutionStrategyType.NO_ACTION)


@pytest.mark.asyncio
async def test_20_terminal_state_no_action_plan(test_session: AsyncSession):
    ob = Obligation(id="ob-done", workspace_id="ws-default", owner="Alice", beneficiary="Gov", action="Tax filing", status=ObligationStatus.COMPLETED, obligation_type=ObligationType.OWED_BY_ME)
    test_session.add(ob)
    await test_session.commit()

    plan = await ResolutionPlanner.plan_resolution(test_session, "ob-done")
    assert plan.strategy == ResolutionStrategyType.NO_ACTION


# ==============================================================================
# 5. RESOLUTION SIMULATION TESTS (ZERO SIDE EFFECTS)
# ==============================================================================

@pytest.mark.asyncio
async def test_21_complete_root_simulation_cascading_unblocks(test_session: AsyncSession):
    # A (Rahul, overdue) -> B (Ravi, blocked) -> C (Priya, blocked)
    ob_a = Obligation(id="ob-a", workspace_id="ws-default", owner="Rahul", beneficiary="Team", action="Benchmark", status=ObligationStatus.OVERDUE, obligation_type=ObligationType.OWED_BY_ME)
    ob_b = Obligation(id="ob-b", workspace_id="ws-default", owner="Ravi", beneficiary="Team", action="Report", status=ObligationStatus.BLOCKED, obligation_type=ObligationType.OWED_BY_ME)
    ob_c = Obligation(id="ob-c", workspace_id="ws-default", owner="Priya", beneficiary="Team", action="Briefing", status=ObligationStatus.BLOCKED, obligation_type=ObligationType.OWED_BY_ME)

    e1 = ObligationEdge(id="e1", workspace_id="ws-default", from_obligation_id="ob-b", to_obligation_id="ob-a", edge_type=EdgeType.DEPENDS_ON)
    e2 = ObligationEdge(id="e2", workspace_id="ws-default", from_obligation_id="ob-c", to_obligation_id="ob-b", edge_type=EdgeType.DEPENDS_ON)

    test_session.add_all([ob_a, ob_b, ob_c, e1, e2])
    await test_session.commit()

    sim_req = ResolutionSimulationRequest(action=SimulationActionType.COMPLETE_OBLIGATION, target_obligation_id="ob-a")
    sim_res = await ResolutionSimulationService.simulate(test_session, sim_req)

    assert sim_res.is_simulation_marker is True
    assert sim_res.target_obligation_id == "ob-a"
    assert sim_res.projected_state["status"] == "COMPLETED"
    assert len(sim_res.unblocked_obligations) >= 1
    assert any(u["obligation_id"] == "ob-b" for u in sim_res.unblocked_obligations)


@pytest.mark.asyncio
async def test_22_simulation_does_not_mutate_database(test_session: AsyncSession):
    ob_a = Obligation(id="ob-a", workspace_id="ws-default", owner="Rahul", beneficiary="Team", action="Benchmark", status=ObligationStatus.OVERDUE, obligation_type=ObligationType.OWED_BY_ME)
    ob_b = Obligation(id="ob-b", workspace_id="ws-default", owner="Ravi", beneficiary="Team", action="Report", status=ObligationStatus.BLOCKED, obligation_type=ObligationType.OWED_BY_ME)
    edge = ObligationEdge(id="e1", workspace_id="ws-default", from_obligation_id="ob-b", to_obligation_id="ob-a", edge_type=EdgeType.DEPENDS_ON)

    test_session.add_all([ob_a, ob_b, edge])
    await test_session.commit()

    sim_req = ResolutionSimulationRequest(action=SimulationActionType.COMPLETE_OBLIGATION, target_obligation_id="ob-a")
    await ResolutionSimulationService.simulate(test_session, sim_req)

    # Re-fetch from database: must be completely unmutated!
    fresh_a = await test_session.get(Obligation, "ob-a")
    fresh_b = await test_session.get(Obligation, "ob-b")

    assert fresh_a.status == ObligationStatus.OVERDUE
    assert fresh_b.status == ObligationStatus.BLOCKED


@pytest.mark.asyncio
async def test_23_simulation_does_not_create_interventions_or_evidence(test_session: AsyncSession):
    ob_a = Obligation(id="ob-a", workspace_id="ws-default", owner="Rahul", beneficiary="Team", action="Benchmark", status=ObligationStatus.OVERDUE, obligation_type=ObligationType.OWED_BY_ME)
    test_session.add(ob_a)
    await test_session.commit()

    sim_req = ResolutionSimulationRequest(action=SimulationActionType.COMPLETE_OBLIGATION, target_obligation_id="ob-a")
    await ResolutionSimulationService.simulate(test_session, sim_req)

    # Verify zero interventions and zero evidence records created
    inv_res = await test_session.execute(select(Intervention).where(Intervention.obligation_id == "ob-a"))
    ev_res = await test_session.execute(select(Evidence).where(Evidence.obligation_id == "ob-a"))

    assert len(list(inv_res.scalars().all())) == 0
    assert len(list(ev_res.scalars().all())) == 0


@pytest.mark.asyncio
async def test_24_resolve_blocker_simulation(test_session: AsyncSession):
    ob_a = Obligation(id="ob-a", workspace_id="ws-default", owner="Rahul", beneficiary="Team", action="Benchmark", status=ObligationStatus.OVERDUE, obligation_type=ObligationType.OWED_BY_ME)
    ob_b = Obligation(id="ob-b", workspace_id="ws-default", owner="Ravi", beneficiary="Team", action="Report", status=ObligationStatus.BLOCKED, obligation_type=ObligationType.OWED_BY_ME)
    edge = ObligationEdge(id="e1", workspace_id="ws-default", from_obligation_id="ob-b", to_obligation_id="ob-a", edge_type=EdgeType.DEPENDS_ON)
    test_session.add_all([ob_a, ob_b, edge])
    await test_session.commit()

    sim_req = ResolutionSimulationRequest(action=SimulationActionType.RESOLVE_BLOCKER, target_obligation_id="ob-a")
    sim_res = await ResolutionSimulationService.simulate(test_session, sim_req)

    assert sim_res.simulated_action == SimulationActionType.RESOLVE_BLOCKER
    assert len(sim_res.unblocked_obligations) == 1


# ==============================================================================
# 6. RISK CONCENTRATION & BOTTLENECKS TESTS
# ==============================================================================

@pytest.mark.asyncio
async def test_25_systemic_bottleneck_detection(test_session: AsyncSession):
    # Rahul's single obligation blocks 3 different obligations
    ob_hub = Obligation(id="ob-hub", workspace_id="ws-default", owner="Rahul", beneficiary="Team", action="Database Core", status=ObligationStatus.IN_PROGRESS, obligation_type=ObligationType.OWED_BY_ME)
    ob_1 = Obligation(id="ob-1", workspace_id="ws-default", owner="Alice", beneficiary="Team", action="Service A", status=ObligationStatus.BLOCKED, obligation_type=ObligationType.OWED_BY_ME)
    ob_2 = Obligation(id="ob-2", workspace_id="ws-default", owner="Bob", beneficiary="Team", action="Service B", status=ObligationStatus.BLOCKED, obligation_type=ObligationType.OWED_BY_ME)
    ob_3 = Obligation(id="ob-3", workspace_id="ws-default", owner="Charlie", beneficiary="Team", action="Service C", status=ObligationStatus.BLOCKED, obligation_type=ObligationType.OWED_BY_ME)

    e1 = ObligationEdge(id="e1", workspace_id="ws-default", from_obligation_id="ob-1", to_obligation_id="ob-hub", edge_type=EdgeType.DEPENDS_ON)
    e2 = ObligationEdge(id="e2", workspace_id="ws-default", from_obligation_id="ob-2", to_obligation_id="ob-hub", edge_type=EdgeType.DEPENDS_ON)
    e3 = ObligationEdge(id="e3", workspace_id="ws-default", from_obligation_id="ob-3", to_obligation_id="ob-hub", edge_type=EdgeType.DEPENDS_ON)

    test_session.add_all([ob_hub, ob_1, ob_2, ob_3, e1, e2, e3])
    await test_session.commit()

    bottlenecks = await RiskConcentrationService.get_bottlenecks(test_session, "ws-default")
    assert bottlenecks.total_bottlenecks >= 1
    top_b = bottlenecks.bottlenecks[0]
    assert top_b.obligation_id == "ob-hub"
    assert top_b.downstream_dependents_count == 3
    assert top_b.affected_owners_count == 3
    assert top_b.bottleneck_score > 0.40


@pytest.mark.asyncio
async def test_26_risk_concentration_multi_owner_choke_point(test_session: AsyncSession):
    # Rahul has obligations blocking Alice and Bob
    ob_hub = Obligation(id="ob-hub", workspace_id="ws-default", owner="Rahul", beneficiary="Team", action="DB Migration", status=ObligationStatus.IN_PROGRESS, obligation_type=ObligationType.OWED_BY_ME)
    ob_1 = Obligation(id="ob-1", workspace_id="ws-default", owner="Alice", beneficiary="Team", action="API", status=ObligationStatus.BLOCKED, obligation_type=ObligationType.OWED_BY_ME)
    ob_2 = Obligation(id="ob-2", workspace_id="ws-default", owner="Bob", beneficiary="Team", action="Web", status=ObligationStatus.BLOCKED, obligation_type=ObligationType.OWED_BY_ME)

    e1 = ObligationEdge(id="e1", workspace_id="ws-default", from_obligation_id="ob-1", to_obligation_id="ob-hub", edge_type=EdgeType.DEPENDS_ON)
    e2 = ObligationEdge(id="e2", workspace_id="ws-default", from_obligation_id="ob-2", to_obligation_id="ob-hub", edge_type=EdgeType.DEPENDS_ON)

    test_session.add_all([ob_hub, ob_1, ob_2, e1, e2])
    await test_session.commit()

    concentrations = await RiskConcentrationService.get_risk_concentrations(test_session, "ws-default")
    assert concentrations.total_concentrations >= 1
    assert any(c.concentration_type == ConcentrationType.HIGH_IMPACT_OWNER and "Rahul" in c.target_name for c in concentrations.items)


# ==============================================================================
# 7. REST API INTEGRATION TESTS
# ==============================================================================

@pytest.mark.asyncio
async def test_27_api_root_cause(client: AsyncClient, test_session: AsyncSession):
    ob = Obligation(id="api-ob-1", workspace_id="ws-default", owner="Alice", beneficiary="Team", action="Deploy API", status=ObligationStatus.IN_PROGRESS, obligation_type=ObligationType.OWED_BY_ME)
    test_session.add(ob)
    await test_session.commit()

    res = await client.get("/api/intelligence/obligations/api-ob-1/root-cause")
    assert res.status_code == 200
    data = res.json()
    assert data["obligation_id"] == "api-ob-1"
    assert "confidence" in data
    assert "overall_explanation" in data


@pytest.mark.asyncio
async def test_28_api_impact(client: AsyncClient, test_session: AsyncSession):
    ob = Obligation(id="api-ob-2", workspace_id="ws-default", owner="Alice", beneficiary="Team", action="Database init", status=ObligationStatus.IN_PROGRESS, obligation_type=ObligationType.OWED_BY_ME)
    test_session.add(ob)
    await test_session.commit()

    res = await client.get("/api/intelligence/obligations/api-ob-2/impact")
    assert res.status_code == 200
    data = res.json()
    assert data["obligation_id"] == "api-ob-2"
    assert 0.0 <= data["impact_score"] <= 1.0


@pytest.mark.asyncio
async def test_29_api_critical_path(client: AsyncClient, test_session: AsyncSession):
    ob = Obligation(id="api-ob-3", workspace_id="ws-default", owner="Alice", beneficiary="Team", action="Auth module", status=ObligationStatus.IN_PROGRESS, obligation_type=ObligationType.OWED_BY_ME)
    test_session.add(ob)
    await test_session.commit()

    res = await client.get("/api/intelligence/obligations/api-ob-3/critical-path")
    assert res.status_code == 200
    data = res.json()
    assert data["obligation_id"] == "api-ob-3"
    assert data["critical_path_length"] >= 1


@pytest.mark.asyncio
async def test_30_api_resolution_plan(client: AsyncClient, test_session: AsyncSession):
    ob = Obligation(id="api-ob-4", workspace_id="ws-default", owner="Alice", beneficiary="Team", action="Payment gateway", status=ObligationStatus.IN_PROGRESS, obligation_type=ObligationType.OWED_BY_ME)
    test_session.add(ob)
    await test_session.commit()

    res = await client.get("/api/intelligence/obligations/api-ob-4/resolution-plan")
    assert res.status_code == 200
    data = res.json()
    assert data["obligation_id"] == "api-ob-4"
    assert "strategy" in data


@pytest.mark.asyncio
async def test_31_api_simulate_resolution(client: AsyncClient, test_session: AsyncSession):
    ob = Obligation(id="api-ob-5", workspace_id="ws-default", owner="Alice", beneficiary="Team", action="Core setup", status=ObligationStatus.IN_PROGRESS, obligation_type=ObligationType.OWED_BY_ME)
    test_session.add(ob)
    await test_session.commit()

    payload = {
        "action": "COMPLETE_OBLIGATION",
        "target_obligation_id": "api-ob-5"
    }
    res = await client.post("/api/intelligence/obligations/api-ob-5/simulate-resolution", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["is_simulation_marker"] is True
    assert data["projected_state"]["status"] == "COMPLETED"


@pytest.mark.asyncio
async def test_32_api_bottlenecks(client: AsyncClient, test_session: AsyncSession):
    res = await client.get("/api/intelligence/bottlenecks")
    assert res.status_code == 200
    data = res.json()
    assert "bottlenecks" in data
    assert "total_bottlenecks" in data


@pytest.mark.asyncio
async def test_33_api_risk_concentration(client: AsyncClient, test_session: AsyncSession):
    res = await client.get("/api/intelligence/risk-concentration")
    assert res.status_code == 200
    data = res.json()
    assert "items" in data
    assert "total_concentrations" in data


@pytest.mark.asyncio
async def test_34_api_404_handling(client: AsyncClient):
    res = await client.get("/api/intelligence/obligations/non-existent-id/root-cause")
    assert res.status_code == 404


@pytest.mark.asyncio
async def test_35_assign_owner_simulation(test_session: AsyncSession):
    ob = Obligation(id="ob-unassigned-sim", workspace_id="ws-default", owner="Unassigned", beneficiary="Team", action="Draft terms", status=ObligationStatus.DETECTED, obligation_type=ObligationType.OWED_BY_ME)
    test_session.add(ob)
    await test_session.commit()

    sim_req = ResolutionSimulationRequest(
        action=SimulationActionType.ASSIGN_OWNER, target_obligation_id="ob-unassigned-sim", parameters={"new_owner": "Alice"}
    )
    sim_res = await ResolutionSimulationService.simulate(test_session, sim_req)
    assert sim_res.simulated_action == SimulationActionType.ASSIGN_OWNER
    assert sim_res.risk_delta < 0


@pytest.mark.asyncio
async def test_36_confirm_evidence_simulation(test_session: AsyncSession):
    ob = Obligation(id="ob-ev-sim", workspace_id="ws-default", owner="Alice", beneficiary="Team", action="Deploy microservice", status=ObligationStatus.IN_PROGRESS, obligation_type=ObligationType.OWED_BY_ME)
    test_session.add(ob)
    await test_session.commit()

    sim_req = ResolutionSimulationRequest(action=SimulationActionType.CONFIRM_EVIDENCE, target_obligation_id="ob-ev-sim")
    sim_res = await ResolutionSimulationService.simulate(test_session, sim_req)
    assert sim_res.simulated_action == SimulationActionType.CONFIRM_EVIDENCE
    assert sim_res.projected_state["status"] == "COMPLETED"


@pytest.mark.asyncio
async def test_37_remove_dependency_simulation(test_session: AsyncSession):
    ob_a = Obligation(id="ob-a-sim", workspace_id="ws-default", owner="Rahul", beneficiary="Team", action="Benchmark", status=ObligationStatus.OVERDUE, obligation_type=ObligationType.OWED_BY_ME)
    ob_b = Obligation(id="ob-b-sim", workspace_id="ws-default", owner="Ravi", beneficiary="Team", action="Analysis", status=ObligationStatus.BLOCKED, obligation_type=ObligationType.OWED_BY_ME)
    edge = ObligationEdge(id="e-sim", workspace_id="ws-default", from_obligation_id="ob-b-sim", to_obligation_id="ob-a-sim", edge_type=EdgeType.DEPENDS_ON)
    test_session.add_all([ob_a, ob_b, edge])
    await test_session.commit()

    sim_req = ResolutionSimulationRequest(action=SimulationActionType.REMOVE_DEPENDENCY, target_obligation_id="ob-b-sim")
    sim_res = await ResolutionSimulationService.simulate(test_session, sim_req)
    assert sim_res.simulated_action == SimulationActionType.REMOVE_DEPENDENCY
    assert sim_res.projected_state["status"] == "CONFIRMED"
