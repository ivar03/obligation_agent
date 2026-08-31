"""
Phase 15: Intelligence Orchestrator & Decision Layer Automated Test Suite.

Comprehensive tests for:
- Decision Plan Domain Model & Lifecycle
- Deterministic Decision Ranking Engine
- Upstream-First Strategy & Legitimate Alternatives
- Counterfactual Simulation Isolation & Zero Mutation Invariant
- Human Decision Boundary & Explainability
- Provenance & Historical Immutability
- Plan Staleness & Supersession
- REST APIs (/api/intelligence/decision/)
"""

import pytest
import pytest_asyncio
from datetime import datetime, timezone, timedelta
from typing import AsyncGenerator
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy import select

from app.main import app
from app.models.obligation import Obligation, ObligationEdge, Evidence, Intervention, Base
from app.models.decision import DecisionPlan
from app.models.auth import User, Workspace, WorkspaceMembership
from app.core.database import get_db
from app.core.status_machine import (
    ObligationStatus,
    ObligationType,
    EdgeType,
    DecisionPlanStatus,
    HumanDecisionType,
    SimulationActionType,
    ResolutionStrategyType,
)
from app.services.auth_service import AuthService
from app.services.intelligence.intelligence_orchestrator import IntelligenceOrchestrator
from app.services.intelligence.decision_ranking_engine import DecisionRankingEngine
from app.schemas.decision import (
    DecisionPlanApproveRequest,
    DecisionPlanRejectRequest,
    DecisionPlanSimulateRequest,
)

TEST_DB_URL = "sqlite+aiosqlite:///:memory:"


@pytest_asyncio.fixture(scope="function")
async def test_session() -> AsyncGenerator[AsyncSession, None]:
    engine = create_async_engine(TEST_DB_URL, echo=False)
    async_session = async_sessionmaker(engine, expire_on_commit=False)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with async_session() as session:
        await AuthService.ensure_default_dev_user(session)
        yield session

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

    await engine.dispose()


@pytest_asyncio.fixture(scope="function")
async def client(test_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    async def override_get_db():
        yield test_session

    app.dependency_overrides[get_db] = override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()


# ==============================================================================
# 1. DECISION PLAN GENERATION TESTS
# ==============================================================================

@pytest.mark.asyncio
async def test_01_generate_plan_for_healthy_obligation(test_session: AsyncSession):
    ob = Obligation(
        id="ob-healthy",
        workspace_id="ws-default",
        owner="Alice",
        beneficiary="Team",
        action="Write documentation",
        status=ObligationStatus.IN_PROGRESS,
        obligation_type=ObligationType.OWED_BY_ME,
    )
    test_session.add(ob)
    await test_session.commit()

    plan = await IntelligenceOrchestrator.generate_decision_plan(test_session, "ob-healthy")
    assert plan.target_obligation_id == "ob-healthy"
    assert plan.status == DecisionPlanStatus.GENERATED
    assert plan.plan_version == 1
    assert plan.overall_urgency in ("LOW", "MEDIUM")
    assert plan.recommended_actions is not None
    assert "strategy_name" in plan.recommended_actions


@pytest.mark.asyncio
async def test_02_generate_plan_for_blocked_obligation(test_session: AsyncSession):
    ob_root = Obligation(
        id="ob-root",
        workspace_id="ws-default",
        owner="Rahul",
        beneficiary="Team",
        action="Database Migration",
        status=ObligationStatus.IN_PROGRESS,
        obligation_type=ObligationType.OWED_BY_ME,
        deadline=datetime.now(timezone.utc) - timedelta(days=1),
    )
    ob_leaf = Obligation(
        id="ob-leaf",
        workspace_id="ws-default",
        owner="Ravi",
        beneficiary="Team",
        action="API Deployment",
        status=ObligationStatus.BLOCKED,
        obligation_type=ObligationType.OWED_BY_ME,
    )
    edge = ObligationEdge(
        id="e1",
        workspace_id="ws-default",
        from_obligation_id="ob-leaf",
        to_obligation_id="ob-root",
        edge_type=EdgeType.DEPENDS_ON,
    )
    test_session.add_all([ob_root, ob_leaf, edge])
    await test_session.commit()

    plan = await IntelligenceOrchestrator.generate_decision_plan(test_session, "ob-leaf")
    assert plan.target_obligation_id == "ob-leaf"
    assert plan.overall_urgency in ("HIGH", "CRITICAL")
    assert plan.root_cause_obligation_id == "ob-root"
    assert plan.recommended_actions["target_obligation_id"] == "ob-root"


@pytest.mark.asyncio
async def test_03_root_cause_correctly_propagated(test_session: AsyncSession):
    ob_a = Obligation(id="ob-a", workspace_id="ws-default", owner="A", beneficiary="Team", action="Root A", status=ObligationStatus.IN_PROGRESS, obligation_type=ObligationType.OWED_BY_ME)
    ob_b = Obligation(id="ob-b", workspace_id="ws-default", owner="B", beneficiary="Team", action="Middle B", status=ObligationStatus.BLOCKED, obligation_type=ObligationType.OWED_BY_ME)
    ob_c = Obligation(id="ob-c", workspace_id="ws-default", owner="C", beneficiary="Team", action="Target C", status=ObligationStatus.BLOCKED, obligation_type=ObligationType.OWED_BY_ME)

    e1 = ObligationEdge(id="e1", workspace_id="ws-default", from_obligation_id="ob-b", to_obligation_id="ob-a", edge_type=EdgeType.DEPENDS_ON)
    e2 = ObligationEdge(id="e2", workspace_id="ws-default", from_obligation_id="ob-c", to_obligation_id="ob-b", edge_type=EdgeType.DEPENDS_ON)
    test_session.add_all([ob_a, ob_b, ob_c, e1, e2])
    await test_session.commit()

    plan = await IntelligenceOrchestrator.generate_decision_plan(test_session, "ob-c")
    assert plan.root_cause_obligation_id == "ob-a"
    assert "Root A" in plan.resolution_notes or "Root A" in plan.primary_objective or "ob-a" in str(plan.recommended_actions)


@pytest.mark.asyncio
async def test_04_blast_radius_correctly_incorporated(test_session: AsyncSession):
    ob_hub = Obligation(id="ob-hub", workspace_id="ws-default", owner="Hub", beneficiary="Team", action="Hub Service", status=ObligationStatus.IN_PROGRESS, obligation_type=ObligationType.OWED_BY_ME)
    ob_d1 = Obligation(id="ob-d1", workspace_id="ws-default", owner="Dev1", beneficiary="Team", action="Dep 1", status=ObligationStatus.BLOCKED, obligation_type=ObligationType.OWED_BY_ME)
    ob_d2 = Obligation(id="ob-d2", workspace_id="ws-default", owner="Dev2", beneficiary="Team", action="Dep 2", status=ObligationStatus.BLOCKED, obligation_type=ObligationType.OWED_BY_ME)

    e1 = ObligationEdge(id="e1", workspace_id="ws-default", from_obligation_id="ob-d1", to_obligation_id="ob-hub", edge_type=EdgeType.DEPENDS_ON)
    e2 = ObligationEdge(id="e2", workspace_id="ws-default", from_obligation_id="ob-d2", to_obligation_id="ob-hub", edge_type=EdgeType.DEPENDS_ON)
    test_session.add_all([ob_hub, ob_d1, ob_d2, e1, e2])
    await test_session.commit()

    plan = await IntelligenceOrchestrator.generate_decision_plan(test_session, "ob-hub")
    assert plan.impact_summary["total_downstream_dependents_count"] == 2
    assert set(plan.impact_summary["affected_owners"]) == {"Dev1", "Dev2"}
    assert 0.0 <= plan.impact_summary["impact_score"] <= 1.0


@pytest.mark.asyncio
async def test_05_critical_path_correctly_incorporated(test_session: AsyncSession):
    ob_1 = Obligation(id="ob-1", workspace_id="ws-default", owner="Alice", beneficiary="Team", action="Task 1", status=ObligationStatus.IN_PROGRESS, obligation_type=ObligationType.OWED_BY_ME)
    ob_2 = Obligation(id="ob-2", workspace_id="ws-default", owner="Bob", beneficiary="Team", action="Task 2", status=ObligationStatus.BLOCKED, obligation_type=ObligationType.OWED_BY_ME)

    e1 = ObligationEdge(id="e1", workspace_id="ws-default", from_obligation_id="ob-2", to_obligation_id="ob-1", edge_type=EdgeType.DEPENDS_ON)
    test_session.add_all([ob_1, ob_2, e1])
    await test_session.commit()

    plan = await IntelligenceOrchestrator.generate_decision_plan(test_session, "ob-2")
    assert len(plan.critical_path) >= 2


@pytest.mark.asyncio
async def test_06_upstream_first_strategy_selected(test_session: AsyncSession):
    # Root A -> B -> Target C
    ob_a = Obligation(id="ob-a", workspace_id="ws-default", owner="Rahul", beneficiary="Team", action="Root DB", status=ObligationStatus.IN_PROGRESS, obligation_type=ObligationType.OWED_BY_ME)
    ob_b = Obligation(id="ob-b", workspace_id="ws-default", owner="Ravi", beneficiary="Team", action="Mid API", status=ObligationStatus.BLOCKED, obligation_type=ObligationType.OWED_BY_ME)
    ob_c = Obligation(id="ob-c", workspace_id="ws-default", owner="Priya", beneficiary="Team", action="End UI", status=ObligationStatus.BLOCKED, obligation_type=ObligationType.OWED_BY_ME)

    e1 = ObligationEdge(id="e1", workspace_id="ws-default", from_obligation_id="ob-b", to_obligation_id="ob-a", edge_type=EdgeType.DEPENDS_ON)
    e2 = ObligationEdge(id="e2", workspace_id="ws-default", from_obligation_id="ob-c", to_obligation_id="ob-b", edge_type=EdgeType.DEPENDS_ON)
    test_session.add_all([ob_a, ob_b, ob_c, e1, e2])
    await test_session.commit()

    plan = await IntelligenceOrchestrator.generate_decision_plan(test_session, "ob-c")
    rec = plan.recommended_actions
    assert rec["target_obligation_id"] == "ob-a"
    assert rec["target_owner"] == "Rahul"
    assert rec["is_primary_recommendation"] is True


@pytest.mark.asyncio
async def test_07_valid_alternative_strategies_generated(test_session: AsyncSession):
    ob_a = Obligation(id="ob-a", workspace_id="ws-default", owner="Rahul", beneficiary="Team", action="Root DB", status=ObligationStatus.OVERDUE, obligation_type=ObligationType.OWED_BY_ME)
    ob_b = Obligation(id="ob-b", workspace_id="ws-default", owner="Ravi", beneficiary="Team", action="API", status=ObligationStatus.BLOCKED, obligation_type=ObligationType.OWED_BY_ME)
    e1 = ObligationEdge(id="e1", workspace_id="ws-default", from_obligation_id="ob-b", to_obligation_id="ob-a", edge_type=EdgeType.DEPENDS_ON)
    test_session.add_all([ob_a, ob_b, e1])
    await test_session.commit()

    plan = await IntelligenceOrchestrator.generate_decision_plan(test_session, "ob-b")
    assert len(plan.alternative_actions) >= 1
    alt_types = [alt["strategy_type"] for alt in plan.alternative_actions]
    assert "REMOVE_DEPENDENCY" in alt_types or "ASSIGN_OWNER" in alt_types


@pytest.mark.asyncio
async def test_08_unsupported_alternatives_not_fabricated(test_session: AsyncSession):
    # Standalone obligation without dependencies
    ob = Obligation(id="ob-solo", workspace_id="ws-default", owner="Alice", beneficiary="Team", action="Solo task", status=ObligationStatus.IN_PROGRESS, obligation_type=ObligationType.OWED_BY_ME)
    test_session.add(ob)
    await test_session.commit()

    plan = await IntelligenceOrchestrator.generate_decision_plan(test_session, "ob-solo")
    # Should not fabricate remove dependency if no blockers exist
    assert len(plan.alternative_actions) == 0


# ==============================================================================
# 2. SIMULATION & RANKING ENGINE TESTS
# ==============================================================================

@pytest.mark.asyncio
async def test_09_counterfactual_simulation_produces_expected_result(test_session: AsyncSession):
    ob_a = Obligation(id="ob-a", workspace_id="ws-default", owner="Rahul", beneficiary="Team", action="Root", status=ObligationStatus.IN_PROGRESS, obligation_type=ObligationType.OWED_BY_ME)
    ob_b = Obligation(id="ob-b", workspace_id="ws-default", owner="Ravi", beneficiary="Team", action="Leaf", status=ObligationStatus.BLOCKED, obligation_type=ObligationType.OWED_BY_ME)
    e1 = ObligationEdge(id="e1", workspace_id="ws-default", from_obligation_id="ob-b", to_obligation_id="ob-a", edge_type=EdgeType.DEPENDS_ON)
    test_session.add_all([ob_a, ob_b, e1])
    await test_session.commit()

    plan = await IntelligenceOrchestrator.generate_decision_plan(test_session, "ob-b")
    sim = plan.simulation_summary.get("primary_simulation", {})
    assert "unblocked_obligations" in sim
    assert len(sim["unblocked_obligations"]) == 1


@pytest.mark.asyncio
async def test_10_simulation_causes_zero_db_mutation(test_session: AsyncSession):
    ob_a = Obligation(id="ob-a", workspace_id="ws-default", owner="Rahul", beneficiary="Team", action="Root", status=ObligationStatus.IN_PROGRESS, obligation_type=ObligationType.OWED_BY_ME)
    ob_b = Obligation(id="ob-b", workspace_id="ws-default", owner="Ravi", beneficiary="Team", action="Leaf", status=ObligationStatus.BLOCKED, obligation_type=ObligationType.OWED_BY_ME)
    e1 = ObligationEdge(id="e1", workspace_id="ws-default", from_obligation_id="ob-b", to_obligation_id="ob-a", edge_type=EdgeType.DEPENDS_ON)
    test_session.add_all([ob_a, ob_b, e1])
    await test_session.commit()

    plan = await IntelligenceOrchestrator.generate_decision_plan(test_session, "ob-b")

    # Verify live DB status
    fresh_a = await test_session.get(Obligation, "ob-a")
    fresh_b = await test_session.get(Obligation, "ob-b")
    assert fresh_a.status == ObligationStatus.IN_PROGRESS
    assert fresh_b.status == ObligationStatus.BLOCKED


@pytest.mark.asyncio
async def test_11_decision_score_remains_bounded():
    # Test boundary conditions
    score_high, breakdown_high = DecisionRankingEngine.rank_strategy({
        "risk_reduction": 1.0,
        "blast_radius_reduction": 1.0,
        "critical_path_improvement": 1.0,
        "evidence_confidence": 1.0,
        "prediction_confidence": 1.0,
        "execution_complexity": 0.0,
        "uncertainty_penalty": 0.0,
    })
    assert 0.0 <= score_high <= 1.0

    score_low, breakdown_low = DecisionRankingEngine.rank_strategy({
        "risk_reduction": 0.0,
        "blast_radius_reduction": 0.0,
        "critical_path_improvement": 0.0,
        "evidence_confidence": 0.0,
        "prediction_confidence": 0.0,
        "execution_complexity": 1.0,
        "uncertainty_penalty": 1.0,
    })
    assert 0.0 <= score_low <= 1.0
    assert score_high > score_low


@pytest.mark.asyncio
async def test_12_human_decision_requirements_generated_correctly(test_session: AsyncSession):
    ob_a = Obligation(id="ob-a", workspace_id="ws-default", owner="Rahul", beneficiary="Team", action="Root", status=ObligationStatus.IN_PROGRESS, obligation_type=ObligationType.OWED_BY_ME)
    ob_b = Obligation(id="ob-b", workspace_id="ws-default", owner="Ravi", beneficiary="Team", action="Leaf", status=ObligationStatus.BLOCKED, obligation_type=ObligationType.OWED_BY_ME)
    e1 = ObligationEdge(id="e1", workspace_id="ws-default", from_obligation_id="ob-b", to_obligation_id="ob-a", edge_type=EdgeType.DEPENDS_ON)
    test_session.add_all([ob_a, ob_b, e1])
    await test_session.commit()

    plan = await IntelligenceOrchestrator.generate_decision_plan(test_session, "ob-b")
    assert len(plan.human_decisions_required) >= 1
    req = plan.human_decisions_required[0]
    assert req["decision_type"] == HumanDecisionType.APPROVE_INTERVENTION.value
    assert "Rahul" in req["reason"] or "ob-a" in req["affected_obligation_id"]


@pytest.mark.asyncio
async def test_13_provenance_references_preserved(test_session: AsyncSession):
    ob = Obligation(id="ob-ev", workspace_id="ws-default", owner="Alice", beneficiary="Team", action="Deploy", status=ObligationStatus.IN_PROGRESS, obligation_type=ObligationType.OWED_BY_ME)
    ev = Evidence(id="ev-1", obligation_id="ob-ev", workspace_id="ws-default", source_type="message", source_ref="ref-1", content="Deployed to staging", observed_at=datetime.now(timezone.utc))
    test_session.add_all([ob, ev])
    await test_session.commit()

    plan = await IntelligenceOrchestrator.generate_decision_plan(test_session, "ob-ev")
    assert isinstance(plan.supporting_evidence, list)


# ==============================================================================
# 3. PLAN LIFECYCLE, IMMUTABILITY & SUPERSESSION
# ==============================================================================

@pytest.mark.asyncio
async def test_14_historical_plan_immutability(test_session: AsyncSession):
    ob = Obligation(id="ob-hist", workspace_id="ws-default", owner="Alice", beneficiary="Team", action="Task", status=ObligationStatus.IN_PROGRESS, obligation_type=ObligationType.OWED_BY_ME)
    test_session.add(ob)
    await test_session.commit()

    plan_v1 = await IntelligenceOrchestrator.generate_decision_plan(test_session, "ob-hist")
    v1_id = plan_v1.id
    assert plan_v1.plan_version == 1

    # Force refresh generates Plan v2 and supersedes Plan v1
    plan_v2 = await IntelligenceOrchestrator.generate_decision_plan(test_session, "ob-hist", force_refresh=True)
    assert plan_v2.plan_version == 2
    assert plan_v2.id != v1_id

    # Verify Plan v1 remains persisted and marked SUPERSEDED
    old_plan = await test_session.get(DecisionPlan, v1_id)
    assert old_plan.status == DecisionPlanStatus.SUPERSEDED
    assert old_plan.superseded_by_plan_id == plan_v2.id


@pytest.mark.asyncio
async def test_15_plan_supersession_after_state_change(test_session: AsyncSession):
    ob_a = Obligation(id="ob-a", workspace_id="ws-default", owner="Rahul", beneficiary="Team", action="Root", status=ObligationStatus.IN_PROGRESS, obligation_type=ObligationType.OWED_BY_ME)
    ob_b = Obligation(id="ob-b", workspace_id="ws-default", owner="Ravi", beneficiary="Team", action="Leaf", status=ObligationStatus.BLOCKED, obligation_type=ObligationType.OWED_BY_ME)
    e1 = ObligationEdge(id="e1", workspace_id="ws-default", from_obligation_id="ob-b", to_obligation_id="ob-a", edge_type=EdgeType.DEPENDS_ON)
    test_session.add_all([ob_a, ob_b, e1])
    await test_session.commit()

    plan_v1 = await IntelligenceOrchestrator.generate_decision_plan(test_session, "ob-b")
    assert plan_v1.plan_version == 1

    # State change: complete Root A
    ob_a.status = ObligationStatus.COMPLETED
    await test_session.commit()

    # Next generation detects staleness and creates Plan v2
    plan_v2 = await IntelligenceOrchestrator.generate_decision_plan(test_session, "ob-b")
    assert plan_v2.plan_version == 2
    assert plan_v2.status == DecisionPlanStatus.GENERATED


@pytest.mark.asyncio
async def test_16_approval_lifecycle(test_session: AsyncSession):
    ob = Obligation(id="ob-appr", workspace_id="ws-default", owner="Alice", beneficiary="Team", action="Task", status=ObligationStatus.IN_PROGRESS, obligation_type=ObligationType.OWED_BY_ME)
    test_session.add(ob)
    await test_session.commit()

    plan = await IntelligenceOrchestrator.generate_decision_plan(test_session, "ob-appr")
    assert plan.status == DecisionPlanStatus.GENERATED

    approved = await IntelligenceOrchestrator.approve_plan(
        test_session, plan.id, user_id="usr-default", request=DecisionPlanApproveRequest(notes="Approved for sprint")
    )
    assert approved.status == DecisionPlanStatus.APPROVED
    assert approved.approved_by_user_id == "usr-default"
    assert approved.approved_at is not None


@pytest.mark.asyncio
async def test_17_rejection_lifecycle(test_session: AsyncSession):
    ob = Obligation(id="ob-rej", workspace_id="ws-default", owner="Alice", beneficiary="Team", action="Task", status=ObligationStatus.IN_PROGRESS, obligation_type=ObligationType.OWED_BY_ME)
    test_session.add(ob)
    await test_session.commit()

    plan = await IntelligenceOrchestrator.generate_decision_plan(test_session, "ob-rej")
    rejected = await IntelligenceOrchestrator.reject_plan(
        test_session, plan.id, user_id="usr-default", request=DecisionPlanRejectRequest(reason="Postponed by customer")
    )
    assert rejected.status == DecisionPlanStatus.REJECTED
    assert rejected.rejected_by_user_id == "usr-default"
    assert "Postponed by customer" in (rejected.resolution_notes or "")


@pytest.mark.asyncio
async def test_18_resolution_lifecycle(test_session: AsyncSession):
    ob = Obligation(id="ob-res", workspace_id="ws-default", owner="Alice", beneficiary="Team", action="Task", status=ObligationStatus.IN_PROGRESS, obligation_type=ObligationType.OWED_BY_ME)
    test_session.add(ob)
    await test_session.commit()

    plan = await IntelligenceOrchestrator.generate_decision_plan(test_session, "ob-res")
    resolved = await IntelligenceOrchestrator.resolve_plan(test_session, plan.id, notes="Work completed successfully")
    assert resolved.status == DecisionPlanStatus.RESOLVED


# ==============================================================================
# 4. REST API ENDPOINT TESTS
# ==============================================================================

@pytest.mark.asyncio
async def test_19_api_generate_decision_plan(client: AsyncClient, test_session: AsyncSession):
    ob = Obligation(id="api-ob-1", workspace_id="ws-default", owner="Alice", beneficiary="Team", action="Build API", status=ObligationStatus.IN_PROGRESS, obligation_type=ObligationType.OWED_BY_ME)
    test_session.add(ob)
    await test_session.commit()

    response = await client.post("/api/intelligence/decision/api-ob-1/generate")
    assert response.status_code == 200
    data = response.json()
    assert data["target_obligation_id"] == "api-ob-1"
    assert data["status"] == "GENERATED"
    assert "recommended_actions" in data


@pytest.mark.asyncio
async def test_20_api_get_decision_plan(client: AsyncClient, test_session: AsyncSession):
    ob = Obligation(id="api-ob-2", workspace_id="ws-default", owner="Bob", beneficiary="Team", action="Design UI", status=ObligationStatus.IN_PROGRESS, obligation_type=ObligationType.OWED_BY_ME)
    test_session.add(ob)
    await test_session.commit()

    response = await client.get("/api/intelligence/decision/api-ob-2")
    assert response.status_code == 200
    data = response.json()
    assert data["target_obligation_id"] == "api-ob-2"


@pytest.mark.asyncio
async def test_21_api_get_decision_history(client: AsyncClient, test_session: AsyncSession):
    ob = Obligation(id="api-ob-3", workspace_id="ws-default", owner="Charlie", beneficiary="Team", action="QA Testing", status=ObligationStatus.IN_PROGRESS, obligation_type=ObligationType.OWED_BY_ME)
    test_session.add(ob)
    await test_session.commit()

    # Generate v1
    await client.post("/api/intelligence/decision/api-ob-3/generate")
    # Refresh to v2
    get_res = await client.get("/api/intelligence/decision/api-ob-3")
    plan_id = get_res.json()["id"]
    await client.post(f"/api/intelligence/decision/{plan_id}/refresh")

    history_res = await client.get("/api/intelligence/decision/api-ob-3/history")
    assert history_res.status_code == 200
    history = history_res.json()
    assert len(history) == 2
    assert history[0]["plan_version"] == 2
    assert history[1]["plan_version"] == 1


@pytest.mark.asyncio
async def test_22_api_approve_decision_plan(client: AsyncClient, test_session: AsyncSession):
    ob = Obligation(id="api-ob-4", workspace_id="ws-default", owner="Dana", beneficiary="Team", action="Release", status=ObligationStatus.IN_PROGRESS, obligation_type=ObligationType.OWED_BY_ME)
    test_session.add(ob)
    await test_session.commit()

    gen_res = await client.post("/api/intelligence/decision/api-ob-4/generate")
    plan_id = gen_res.json()["id"]

    approve_res = await client.post(f"/api/intelligence/decision/{plan_id}/approve", json={"notes": "Approved by lead"})
    assert approve_res.status_code == 200
    assert approve_res.json()["status"] == "APPROVED"


@pytest.mark.asyncio
async def test_23_api_reject_decision_plan(client: AsyncClient, test_session: AsyncSession):
    ob = Obligation(id="api-ob-5", workspace_id="ws-default", owner="Evan", beneficiary="Team", action="Audit", status=ObligationStatus.IN_PROGRESS, obligation_type=ObligationType.OWED_BY_ME)
    test_session.add(ob)
    await test_session.commit()

    gen_res = await client.post("/api/intelligence/decision/api-ob-5/generate")
    plan_id = gen_res.json()["id"]

    reject_res = await client.post(f"/api/intelligence/decision/{plan_id}/reject", json={"reason": "Not feasible this quarter"})
    assert reject_res.status_code == 200
    assert reject_res.json()["status"] == "REJECTED"


@pytest.mark.asyncio
async def test_24_api_simulate_decision_plan_strategy(client: AsyncClient, test_session: AsyncSession):
    ob = Obligation(id="api-ob-6", workspace_id="ws-default", owner="Frank", beneficiary="Team", action="Deploy", status=ObligationStatus.IN_PROGRESS, obligation_type=ObligationType.OWED_BY_ME)
    test_session.add(ob)
    await test_session.commit()

    gen_res = await client.post("/api/intelligence/decision/api-ob-6/generate")
    plan_id = gen_res.json()["id"]

    sim_res = await client.post(f"/api/intelligence/decision/{plan_id}/simulate", json={"custom_action": "COMPLETE_OBLIGATION"})
    assert sim_res.status_code == 200
    assert sim_res.json()["is_simulation_marker"] is True


@pytest.mark.asyncio
async def test_25_api_decision_queue(client: AsyncClient, test_session: AsyncSession):
    ob = Obligation(id="api-ob-7", workspace_id="ws-default", owner="Grace", beneficiary="Team", action="Security review", status=ObligationStatus.IN_PROGRESS, obligation_type=ObligationType.OWED_BY_ME)
    test_session.add(ob)
    await test_session.commit()

    await client.post("/api/intelligence/decision/api-ob-7/generate")

    queue_res = await client.get("/api/intelligence/decision/queue")
    assert queue_res.status_code == 200
    data = queue_res.json()
    assert data["total"] >= 1
    assert any(item["target_obligation_id"] == "api-ob-7" for item in data["items"])


@pytest.mark.asyncio
async def test_26_api_404_not_found(client: AsyncClient):
    res = await client.get("/api/intelligence/decision/non-existent-ob")
    assert res.status_code == 404


# ==============================================================================
# 5. SAFETY INVARIANTS & INTEGRATION FLOW TESTS
# ==============================================================================

@pytest.mark.asyncio
async def test_27_no_autonomous_intervention_execution(test_session: AsyncSession):
    ob = Obligation(id="ob-no-auto-iv", workspace_id="ws-default", owner="Alice", beneficiary="Team", action="Task", status=ObligationStatus.BLOCKED, obligation_type=ObligationType.OWED_BY_ME)
    test_session.add(ob)
    await test_session.commit()

    plan = await IntelligenceOrchestrator.generate_decision_plan(test_session, "ob-no-auto-iv")
    # Verify no interventions were created in the database
    stmt = select(Intervention).where(Intervention.obligation_id == "ob-no-auto-iv")
    res = await test_session.execute(stmt)
    assert len(res.scalars().all()) == 0


@pytest.mark.asyncio
async def test_28_no_autonomous_evidence_confirmation(test_session: AsyncSession):
    from app.core.status_machine import CorrelationStatus
    ob = Obligation(id="ob-no-auto-ev", workspace_id="ws-default", owner="Alice", beneficiary="Team", action="Task", status=ObligationStatus.IN_PROGRESS, obligation_type=ObligationType.OWED_BY_ME)
    ev = Evidence(id="ev-unconf", obligation_id="ob-no-auto-ev", workspace_id="ws-default", source_type="message", source_ref="ref-1", content="Work update", correlation_status=CorrelationStatus.SUGGESTED)
    test_session.add_all([ob, ev])
    await test_session.commit()

    plan = await IntelligenceOrchestrator.generate_decision_plan(test_session, "ob-no-auto-ev")
    fresh_ev = await test_session.get(Evidence, "ev-unconf")
    assert fresh_ev.correlation_status == CorrelationStatus.SUGGESTED


@pytest.mark.asyncio
async def test_29_no_autonomous_obligation_completion(test_session: AsyncSession):
    ob = Obligation(id="ob-no-auto-comp", workspace_id="ws-default", owner="Alice", beneficiary="Team", action="Task", status=ObligationStatus.IN_PROGRESS, obligation_type=ObligationType.OWED_BY_ME)
    test_session.add(ob)
    await test_session.commit()

    plan = await IntelligenceOrchestrator.generate_decision_plan(test_session, "ob-no-auto-comp")
    fresh_ob = await test_session.get(Obligation, "ob-no-auto-comp")
    assert fresh_ob.status == ObligationStatus.IN_PROGRESS


@pytest.mark.asyncio
async def test_30_decision_plan_remains_deterministic(test_session: AsyncSession):
    ob = Obligation(id="ob-det", workspace_id="ws-default", owner="Alice", beneficiary="Team", action="Task", status=ObligationStatus.IN_PROGRESS, obligation_type=ObligationType.OWED_BY_ME)
    test_session.add(ob)
    await test_session.commit()

    plan1 = await IntelligenceOrchestrator.generate_decision_plan(test_session, "ob-det", force_refresh=True)
    plan2 = await IntelligenceOrchestrator.generate_decision_plan(test_session, "ob-det", force_refresh=True)

    assert plan1.primary_objective == plan2.primary_objective
    assert plan1.overall_urgency == plan2.overall_urgency
    assert plan1.overall_risk == plan2.overall_risk
    assert plan1.recommended_actions["strategy_name"] == plan2.recommended_actions["strategy_name"]
    assert plan1.recommended_actions["decision_score"] == plan2.recommended_actions["decision_score"]


@pytest.mark.asyncio
async def test_31_duplicate_generation_returns_active_plan(test_session: AsyncSession):
    ob = Obligation(id="ob-dup", workspace_id="ws-default", owner="Alice", beneficiary="Team", action="Task", status=ObligationStatus.IN_PROGRESS, obligation_type=ObligationType.OWED_BY_ME)
    test_session.add(ob)
    await test_session.commit()

    plan1 = await IntelligenceOrchestrator.generate_decision_plan(test_session, "ob-dup", force_refresh=False)
    plan2 = await IntelligenceOrchestrator.generate_decision_plan(test_session, "ob-dup", force_refresh=False)

    assert plan1.id == plan2.id
    assert plan1.plan_version == plan2.plan_version


@pytest.mark.asyncio
async def test_32_critical_path_changes_after_upstream_completion(test_session: AsyncSession):
    ob_a = Obligation(id="ob-a", workspace_id="ws-default", owner="Rahul", beneficiary="Team", action="Root DB", status=ObligationStatus.IN_PROGRESS, obligation_type=ObligationType.OWED_BY_ME)
    ob_b = Obligation(id="ob-b", workspace_id="ws-default", owner="Ravi", beneficiary="Team", action="Mid API", status=ObligationStatus.BLOCKED, obligation_type=ObligationType.OWED_BY_ME)
    ob_c = Obligation(id="ob-c", workspace_id="ws-default", owner="Priya", beneficiary="Team", action="End UI", status=ObligationStatus.BLOCKED, obligation_type=ObligationType.OWED_BY_ME)

    e1 = ObligationEdge(id="e1", workspace_id="ws-default", from_obligation_id="ob-b", to_obligation_id="ob-a", edge_type=EdgeType.DEPENDS_ON)
    e2 = ObligationEdge(id="e2", workspace_id="ws-default", from_obligation_id="ob-c", to_obligation_id="ob-b", edge_type=EdgeType.DEPENDS_ON)
    test_session.add_all([ob_a, ob_b, ob_c, e1, e2])
    await test_session.commit()

    plan_v1 = await IntelligenceOrchestrator.generate_decision_plan(test_session, "ob-c")
    assert plan_v1.recommended_actions["target_obligation_id"] == "ob-a"

    # Upstream completed
    ob_a.status = ObligationStatus.COMPLETED
    await test_session.commit()

    plan_v2 = await IntelligenceOrchestrator.generate_decision_plan(test_session, "ob-c", force_refresh=True)
    assert plan_v2.critical_path[0]["status"] == ObligationStatus.COMPLETED.value
    assert plan_v2.recommended_actions["target_obligation_id"] in ("ob-b", "ob-c")


@pytest.mark.asyncio
async def test_33_full_end_to_end_causal_decision_flow(test_session: AsyncSession):
    # Setup full 4-node chain: Rahul -> Ravi -> Priya -> Manager
    ob_rahul = Obligation(id="e2e-rahul", workspace_id="ws-default", owner="Rahul", beneficiary="Team", action="Database Schema", status=ObligationStatus.OVERDUE, obligation_type=ObligationType.OWED_BY_ME)
    ob_ravi = Obligation(id="e2e-ravi", workspace_id="ws-default", owner="Ravi", beneficiary="Team", action="API Endpoints", status=ObligationStatus.BLOCKED, obligation_type=ObligationType.OWED_BY_ME)
    ob_priya = Obligation(id="e2e-priya", workspace_id="ws-default", owner="Priya", beneficiary="Team", action="UI Views", status=ObligationStatus.BLOCKED, obligation_type=ObligationType.OWED_BY_ME)
    ob_manager = Obligation(id="e2e-manager", workspace_id="ws-default", owner="Manager", beneficiary="Client", action="Demo Release", status=ObligationStatus.BLOCKED, obligation_type=ObligationType.OWED_BY_ME)

    e1 = ObligationEdge(id="e2e-e1", workspace_id="ws-default", from_obligation_id="e2e-ravi", to_obligation_id="e2e-rahul", edge_type=EdgeType.DEPENDS_ON)
    e2 = ObligationEdge(id="e2e-e2", workspace_id="ws-default", from_obligation_id="e2e-priya", to_obligation_id="e2e-ravi", edge_type=EdgeType.DEPENDS_ON)
    e3 = ObligationEdge(id="e2e-e3", workspace_id="ws-default", from_obligation_id="e2e-manager", to_obligation_id="e2e-priya", edge_type=EdgeType.DEPENDS_ON)

    test_session.add_all([ob_rahul, ob_ravi, ob_priya, ob_manager, e1, e2, e3])
    await test_session.commit()

    # 1. Generate plan for Manager's Demo Release
    plan = await IntelligenceOrchestrator.generate_decision_plan(test_session, "e2e-manager")
    assert plan.root_cause_obligation_id == "e2e-rahul"
    assert plan.recommended_actions["target_owner"] == "Rahul"

    # 2. Human reviews and approves
    approved_plan = await IntelligenceOrchestrator.approve_plan(
        test_session, plan.id, user_id="usr-default", request=DecisionPlanApproveRequest(notes="Authorized sprint lead follow-up")
    )
    assert approved_plan.status == DecisionPlanStatus.APPROVED

    # 3. Simulate completion (zero side effects)
    sim = plan.simulation_summary["primary_simulation"]
    assert len(sim["unblocked_obligations"]) == 3

    # 4. Resolve plan when work completes
    resolved = await IntelligenceOrchestrator.resolve_plan(test_session, plan.id, notes="Demo delivered")
    assert resolved.status == DecisionPlanStatus.RESOLVED

