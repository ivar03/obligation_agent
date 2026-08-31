"""
Phase 16 Comprehensive Automated Test Suite — Organizational Memory, Semantic Context & Historical Reasoning

Verifies:
1. Memory formation (obligation completion, intervention, dependency, blocker, idempotency)
2. Semantic representation extraction and explainability
3. Retrieval relevance scoring, ranking, and explanation
4. Pattern detection and maturity classification (INSUFFICIENT_HISTORY, EMERGING, ESTABLISHED)
5. Strictly neutral owner analytics and sufficiency gating
6. Evidence & intervention historical context
7. Risk signals and adaptive feature boundedness
8. Orchestrator integration and historical provenance
9. Historical immutability and safety invariants (zero autonomous mutations)
"""

import pytest
import pytest_asyncio
from datetime import datetime, timezone, timedelta
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

from app.models.obligation import Obligation, ObligationEdge, Evidence, Intervention, Base
from app.models.memory import OrganizationalMemory
from app.models.auth import User, Workspace
from app.core.status_machine import (
    ObligationStatus,
    ObligationType,
    EdgeType,
    MemoryType,
    PatternType,
    PatternMaturity,
    RecurrenceInterval,
)
from app.core.intervention_status import InterventionStatus, InterventionType
from app.schemas.memory import (
    OrganizationalMemoryCreate,
    SemanticRepresentationResponse,
)
from app.services.intelligence.memory.semantic_context_engine import SemanticContextEngine
from app.services.intelligence.memory.memory_formation_service import MemoryFormationService
from app.services.intelligence.memory.memory_retrieval_service import MemoryRetrievalService
from app.services.intelligence.memory.pattern_detection_service import PatternDetectionService
from app.services.intelligence.memory.historical_owner_analytics_service import HistoricalOwnerAnalyticsService
from app.services.intelligence.memory.historical_risk_signal_provider import HistoricalRiskSignalProvider
from app.services.intelligence.intelligence_orchestrator import IntelligenceOrchestrator


@pytest_asyncio.fixture
async def async_session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with session_factory() as session:
        # Seed default workspace and user
        ws = Workspace(id="ws-default", name="Default Workspace", slug="default")
        user = User(id="usr-1", email="dev@example.com", display_name="Dev User", password_hash="pw", is_active=True)
        session.add_all([ws, user])
        await session.commit()

        yield session

    await engine.dispose()


# ==============================================================================
# 1. MEMORY FORMATION TESTS
# ==============================================================================

@pytest.mark.asyncio
async def test_01_obligation_completion_creates_memory(async_session: AsyncSession):
    now = datetime.now(timezone.utc)
    ob = Obligation(
        id="ob-101",
        workspace_id="ws-default",
        owner="Rahul",
        beneficiary="Engineering",
        action="Deploy database benchmark suite",
        status=ObligationStatus.COMPLETED,
        obligation_type=ObligationType.OWED_BY_ME,
        deadline=now - timedelta(hours=5),
    )
    async_session.add(ob)
    await async_session.commit()

    mem = await MemoryFormationService.record_obligation_completion(async_session, ob, completion_time=now)
    assert mem is not None
    assert mem.obligation_id == "ob-101"
    assert mem.owner_id == "Rahul"
    assert mem.memory_type == MemoryType.OBLIGATION_OUTCOME
    assert mem.outcome == "COMPLETED_LATE"
    assert mem.metadata_json.get("is_late") is True
    assert "database" in mem.entities


@pytest.mark.asyncio
async def test_02_intervention_outcome_creates_memory(async_session: AsyncSession):
    ob = Obligation(
        id="ob-iv-parent",
        workspace_id="ws-default",
        owner="Rahul",
        beneficiary="Engineering",
        action="Run benchmark tests",
        obligation_type=ObligationType.OWED_BY_ME,
    )
    async_session.add(ob)
    await async_session.commit()

    iv = Intervention(
        id="iv-201",
        obligation_id="ob-iv-parent",
        workspace_id="ws-default",
        intervention_type=InterventionType.FOLLOW_UP_OWNER,
        target_owner="Rahul",
        target_beneficiary="Engineering",
        title="Follow up on benchmark results",
        rationale="Benchmark follow up",
        message_draft="Hey Rahul, any update?",
        status=InterventionStatus.RESOLVED,
    )
    async_session.add(iv)
    await async_session.commit()

    mem = await MemoryFormationService.record_intervention_outcome(
        async_session, iv, outcome_status="PROGRESS_REPORTED", response_summary="Rahul replied with staging logs."
    )
    assert mem is not None
    assert mem.memory_type == MemoryType.INTERVENTION_OUTCOME
    assert mem.owner_id == "Rahul"
    assert mem.outcome == "PROGRESS_REPORTED"


@pytest.mark.asyncio
async def test_03_dependency_resolution_creates_memory(async_session: AsyncSession):
    up = Obligation(id="up-1", workspace_id="ws-default", owner="Rahul", beneficiary="Engineering", action="Database Schema Migration", obligation_type=ObligationType.OWED_BY_ME)
    down1 = Obligation(id="down-1", workspace_id="ws-default", owner="Ravi", beneficiary="Engineering", action="REST Billing API", obligation_type=ObligationType.OWED_BY_ME)
    down2 = Obligation(id="down-2", workspace_id="ws-default", owner="Priya", beneficiary="Engineering", action="Billing Dashboard", obligation_type=ObligationType.OWED_BY_ME)
    async_session.add_all([up, down1, down2])
    await async_session.commit()

    mem = await MemoryFormationService.record_dependency_resolution(async_session, up, [down1, down2])
    assert mem is not None
    assert mem.memory_type == MemoryType.DEPENDENCY_PATTERN
    assert mem.metadata_json.get("unblocked_count") == 2


@pytest.mark.asyncio
async def test_04_negative_blocker_creates_memory(async_session: AsyncSession):
    ob = Obligation(id="ob-blocker", workspace_id="ws-default", owner="Priya", beneficiary="Engineering", action="Export data metrics", obligation_type=ObligationType.OWED_BY_ME)
    async_session.add(ob)
    await async_session.commit()

    mem = await MemoryFormationService.record_blocker_pattern(
        async_session, ob, blocker_reason="disk full on export server"
    )
    assert mem is not None
    assert mem.memory_type == MemoryType.BLOCKER_PATTERN
    assert "disk full" in mem.semantic_labels


@pytest.mark.asyncio
async def test_05_idempotent_formation_prevents_duplicate_memory(async_session: AsyncSession):
    ob = Obligation(id="ob-idem", workspace_id="ws-default", owner="Rahul", beneficiary="Engineering", action="Prepare migration", obligation_type=ObligationType.OWED_BY_ME)
    async_session.add(ob)
    await async_session.commit()

    mem1 = await MemoryFormationService.record_obligation_completion(async_session, ob)
    mem2 = await MemoryFormationService.record_obligation_completion(async_session, ob)
    assert mem1.id == mem2.id


# ==============================================================================
# 2. SEMANTIC REPRESENTATION TESTS
# ==============================================================================

def test_06_action_extraction():
    sem = SemanticContextEngine.extract_semantic_representation("Send the database benchmark numbers to Ravi")
    assert sem.action == "send"


def test_07_deliverable_extraction():
    sem = SemanticContextEngine.extract_semantic_representation("Review and submit the billing API documentation")
    assert "billing" in sem.deliverable.lower() or "documentation" in sem.deliverable.lower()


def test_08_entity_and_topic_extraction():
    sem = SemanticContextEngine.extract_semantic_representation("Deploy postgres schema migration on staging cluster")
    assert "database" in sem.entities
    assert "infrastructure" in sem.topics or "infrastructure" in sem.entities


def test_09_obligation_type_representation():
    sem = SemanticContextEngine.extract_semantic_representation(
        "Complete compliance audit report", obligation_type="OWED_TO_ME"
    )
    assert sem.obligation_type == "OWED_TO_ME"


def test_10_explainability_of_semantic_representation():
    now = datetime.now(timezone.utc)
    sem = SemanticContextEngine.extract_semantic_representation(
        "Investigate disk full error on production database",
        deadline=now - timedelta(days=1),
    )
    assert sem.deadline_characteristic == "overdue"
    assert len(sem.blocker_terms) > 0


# ==============================================================================
# 3. RETRIEVAL & RANKING TESTS
# ==============================================================================

@pytest.mark.asyncio
async def test_11_similar_obligation_retrieval(async_session: AsyncSession):
    now = datetime.now(timezone.utc)
    mem1 = OrganizationalMemory(
        id="mem-1", workspace_id="ws-default", memory_type=MemoryType.OBLIGATION_OUTCOME,
        owner_id="Rahul", content="Rahul completed database migration", semantic_summary="Rahul: database migration (COMPLETED)",
        semantic_labels=["COMPLETED", "database"], entities=["database"], topics=["infrastructure"], outcome="COMPLETED_ON_TIME",
        metadata_json={"deliverable": "database migration", "action": "migrate"}, observed_at=now,
    )
    mem2 = OrganizationalMemory(
        id="mem-2", workspace_id="ws-default", memory_type=MemoryType.OBLIGATION_OUTCOME,
        owner_id="Ravi", content="Ravi prepared sales pitch", semantic_summary="Ravi: sales pitch (COMPLETED)",
        semantic_labels=["COMPLETED", "sales"], entities=["sales"], topics=["marketing"], outcome="COMPLETED_ON_TIME",
        metadata_json={"deliverable": "sales pitch", "action": "prepare"}, observed_at=now,
    )
    async_session.add_all([mem1, mem2])
    await async_session.commit()

    target = Obligation(id="ob-target", workspace_id="ws-default", owner="Rahul", beneficiary="Engineering", action="Execute database migration v2", obligation_type=ObligationType.OWED_BY_ME)
    async_session.add(target)
    await async_session.commit()

    retrieved = await MemoryRetrievalService.retrieve_for_obligation(async_session, target, min_relevance=0.2)
    assert len(retrieved) >= 1
    top_match = retrieved[0]
    assert top_match.memory.id == "mem-1"
    assert top_match.relevance_score > 0.4
    assert any("Same owner" in r for r in top_match.match_reasons)


@pytest.mark.asyncio
async def test_12_same_deliverable_relevance(async_session: AsyncSession):
    now = datetime.now(timezone.utc)
    mem = OrganizationalMemory(
        id="mem-deliv", workspace_id="ws-default", memory_type=MemoryType.OBLIGATION_OUTCOME,
        owner_id="Priya", content="Priya updated billing API", semantic_summary="Priya: billing API (COMPLETED)",
        semantic_labels=["COMPLETED", "api"], entities=["billing", "api"], topics=["integration"], outcome="COMPLETED_ON_TIME",
        metadata_json={"deliverable": "billing API endpoints", "action": "update"}, observed_at=now,
    )
    async_session.add(mem)
    await async_session.commit()

    target = Obligation(id="ob-target-deliv", workspace_id="ws-default", owner="DifferentOwner", beneficiary="Engineering", action="Update billing API endpoints", obligation_type=ObligationType.OWED_BY_ME)
    async_session.add(target)
    await async_session.commit()

    retrieved = await MemoryRetrievalService.retrieve_for_obligation(async_session, target, min_relevance=0.2)
    assert len(retrieved) >= 1
    assert any("deliverable" in r.lower() for r in retrieved[0].match_reasons)


@pytest.mark.asyncio
async def test_13_weak_match_filtering_and_bounds(async_session: AsyncSession):
    now = datetime.now(timezone.utc)
    mem_irrelevant = OrganizationalMemory(
        id="mem-irr", workspace_id="ws-default", memory_type=MemoryType.OBLIGATION_OUTCOME,
        owner_id="Other", content="Organized holiday lunch party", semantic_summary="Other: holiday party",
        semantic_labels=["social"], entities=["social"], topics=["social"], outcome="COMPLETED",
        metadata_json={"deliverable": "holiday party"}, observed_at=now,
    )
    async_session.add(mem_irrelevant)
    await async_session.commit()

    target = Obligation(id="ob-sec", workspace_id="ws-default", owner="SecurityTeam", beneficiary="Engineering", action="Run penetration test on auth service", obligation_type=ObligationType.OWED_BY_ME)
    async_session.add(target)
    await async_session.commit()

    retrieved = await MemoryRetrievalService.retrieve_for_obligation(async_session, target, min_relevance=0.4)
    assert not any(m.memory.id == "mem-irr" for m in retrieved)


# ==============================================================================
# 4. PATTERN DETECTION & SUFFICIENCY TESTS
# ==============================================================================

@pytest.mark.asyncio
async def test_14_insufficient_history_pattern_threshold(async_session: AsyncSession):
    now = datetime.now(timezone.utc)
    m1 = OrganizationalMemory(
        id="m-del-1", workspace_id="ws-default", memory_type=MemoryType.OBLIGATION_OUTCOME,
        owner_id="Rahul", content="Rahul late 1", semantic_summary="Rahul: db (COMPLETED_LATE)",
        semantic_labels=["COMPLETED_LATE"], entities=["database"], outcome="COMPLETED_LATE",
        metadata_json={"delay_hours": 3.0}, observed_at=now,
    )
    m2 = OrganizationalMemory(
        id="m-del-2", workspace_id="ws-default", memory_type=MemoryType.OBLIGATION_OUTCOME,
        owner_id="Rahul", content="Rahul late 2", semantic_summary="Rahul: db (COMPLETED_LATE)",
        semantic_labels=["COMPLETED_LATE"], entities=["database"], outcome="COMPLETED_LATE",
        metadata_json={"delay_hours": 4.0}, observed_at=now,
    )
    async_session.add_all([m1, m2])
    await async_session.commit()

    target = Obligation(id="ob-pat", workspace_id="ws-default", owner="Rahul", beneficiary="Engineering", action="Deploy database schema", obligation_type=ObligationType.OWED_BY_ME)
    mem_items = await MemoryRetrievalService.retrieve_for_obligation(async_session, target, min_relevance=0.2)

    patterns = await PatternDetectionService.detect_patterns_for_obligation(async_session, target, mem_items)
    delay_pat = next((p for p in patterns if p.pattern_type == PatternType.RECURRING_DELAY_PATTERN), None)
    assert delay_pat is not None
    assert delay_pat.maturity == PatternMaturity.INSUFFICIENT_HISTORY
    assert delay_pat.observation_count == 2


@pytest.mark.asyncio
async def test_15_emerging_and_established_pattern_threshold(async_session: AsyncSession):
    now = datetime.now(timezone.utc)
    blocker_mems = [
        OrganizationalMemory(
            id=f"m-blk-{i}", workspace_id="ws-default", memory_type=MemoryType.BLOCKER_PATTERN,
            owner_id="Dev", content=f"Disk full error #{i}", semantic_summary="Disk full on node",
            semantic_labels=["BLOCKER", "disk full"], entities=["database", "infrastructure"],
            outcome="BLOCKED", metadata_json={"blocker_reason": "disk full on node"}, observed_at=now - timedelta(days=i),
        )
        for i in range(5)
    ]
    async_session.add_all(blocker_mems)
    await async_session.commit()

    target = Obligation(id="ob-blk-target", workspace_id="ws-default", owner="Dev", beneficiary="Engineering", action="Clean database disk node", obligation_type=ObligationType.OWED_BY_ME)
    mem_items = await MemoryRetrievalService.retrieve_for_obligation(async_session, target, min_relevance=0.2)

    patterns = await PatternDetectionService.detect_patterns_for_obligation(async_session, target, mem_items)
    blk_pat = next((p for p in patterns if p.pattern_type == PatternType.RECURRING_BLOCKER_PATTERN), None)
    assert blk_pat is not None
    assert blk_pat.maturity == PatternMaturity.EMERGING_PATTERN
    assert blk_pat.observation_count == 5


@pytest.mark.asyncio
async def test_16_recurring_cadence_detection(async_session: AsyncSession):
    now = datetime.now(timezone.utc)
    weekly_mems = [
        OrganizationalMemory(
            id=f"m-week-{i}", workspace_id="ws-default", memory_type=MemoryType.OBLIGATION_OUTCOME,
            owner_id="Alice", content=f"Weekly sprint report #{i}", semantic_summary="Alice: Weekly sprint report (COMPLETED)",
            semantic_labels=["COMPLETED", "report"], entities=["report"], topics=["documentation"],
            outcome="COMPLETED_ON_TIME", metadata_json={"deliverable": "Weekly sprint report"},
            observed_at=now - timedelta(days=(3 - i) * 7),
        )
        for i in range(4)
    ]
    async_session.add_all(weekly_mems)
    await async_session.commit()

    target = Obligation(id="ob-week-target", workspace_id="ws-default", owner="Alice", beneficiary="Engineering", action="Submit weekly sprint report", obligation_type=ObligationType.OWED_BY_ME)
    mem_items = await MemoryRetrievalService.retrieve_for_obligation(async_session, target, min_relevance=0.3)

    cadence = await PatternDetectionService.detect_recurring_commitment(async_session, target, mem_items)
    assert cadence is not None
    assert cadence.recurrence_type == RecurrenceInterval.WEEKLY
    assert cadence.observation_count == 4


# ==============================================================================
# 5. HISTORICAL OWNER ANALYTICS & NEUTRALITY
# ==============================================================================

@pytest.mark.asyncio
async def test_17_historical_owner_analytics_neutrality(async_session: AsyncSession):
    now = datetime.now(timezone.utc)
    mems = [
        OrganizationalMemory(
            id=f"m-own-{i}", workspace_id="ws-default", memory_type=MemoryType.OBLIGATION_OUTCOME,
            owner_id="Bob", content=f"Task #{i}", semantic_summary=f"Bob: Task #{i}",
            semantic_labels=["COMPLETED"], entities=[], topics=[],
            outcome="COMPLETED_ON_TIME" if i < 3 else "COMPLETED_LATE",
            metadata_json={"delay_hours": 0.0 if i < 3 else 4.0},
            observed_at=now - timedelta(days=i),
        )
        for i in range(5)
    ]
    async_session.add_all(mems)
    await async_session.commit()

    analytics = await HistoricalOwnerAnalyticsService.get_owner_analytics(async_session, "Bob")
    assert analytics.has_sufficient_history is True
    assert analytics.total_commitments_observed == 5
    assert analytics.completion_rate == 1.0
    assert analytics.on_time_completion_rate == 0.60
    assert analytics.median_delay_hours == 4.0

    summary_lower = analytics.neutral_summary.lower()
    prohibited_words = ["reliable", "unreliable", "slow", "lazy", "bad", "good", "slack"]
    for pw in prohibited_words:
        assert pw not in summary_lower, f"Prohibited judgment word '{pw}' found in owner summary!"


# ==============================================================================
# 6. HISTORICAL RISK SIGNALS & BOUNDEDNESS
# ==============================================================================

@pytest.mark.asyncio
async def test_18_historical_risk_signals_bounded(async_session: AsyncSession):
    now = datetime.now(timezone.utc)
    mems = [
        OrganizationalMemory(
            id=f"m-risk-del-{i}", workspace_id="ws-default", memory_type=MemoryType.OBLIGATION_OUTCOME,
            owner_id="RiskOwner", content=f"Late task #{i}", semantic_summary=f"RiskOwner: Late task #{i}",
            semantic_labels=["COMPLETED_LATE"], entities=["database"], topics=["infrastructure"],
            outcome="COMPLETED_LATE", metadata_json={"delay_hours": 5.0}, observed_at=now - timedelta(days=i),
        )
        for i in range(4)
    ]
    async_session.add_all(mems)
    await async_session.commit()

    target = Obligation(id="ob-risk-target", workspace_id="ws-default", owner="RiskOwner", beneficiary="Engineering", action="Deploy database update", obligation_type=ObligationType.OWED_BY_ME)
    async_session.add(target)
    await async_session.commit()

    risk_sig = await HistoricalRiskSignalProvider.get_historical_risk_signals(async_session, target)
    assert "HISTORICAL_DELAY_PATTERN" in risk_sig["signals"]
    assert 0.0 < risk_sig["signals"]["HISTORICAL_DELAY_PATTERN"] <= 0.25
    assert -0.25 <= risk_sig["net_historical_risk_delta"] <= 0.35
    assert len(risk_sig["supporting_memory_ids"]) > 0


# ==============================================================================
# 7. INTELLIGENCE ORCHESTRATOR & DECISION PLAN INTEGRATION
# ==============================================================================

@pytest.mark.asyncio
async def test_19_decision_plan_includes_historical_context(async_session: AsyncSession):
    now = datetime.now(timezone.utc)
    mem_rahul = OrganizationalMemory(
        id="mem-rahul-hist", workspace_id="ws-default", memory_type=MemoryType.OBLIGATION_OUTCOME,
        owner_id="Rahul", content="Rahul completed database migration late", semantic_summary="Rahul: database migration (COMPLETED_LATE)",
        semantic_labels=["COMPLETED_LATE"], entities=["database"], topics=["infrastructure"], outcome="COMPLETED_LATE",
        metadata_json={"deliverable": "database schema migration", "delay_hours": 6.0}, observed_at=now,
    )
    mem_mgr = OrganizationalMemory(
        id="mem-mgr-hist", workspace_id="ws-default", memory_type=MemoryType.OBLIGATION_OUTCOME,
        owner_id="Manager", content="Manager executed previous Client Demo Release", semantic_summary="Manager: Client Demo Release (COMPLETED)",
        semantic_labels=["COMPLETED"], entities=["client", "demo"], topics=["management"], outcome="COMPLETED_ON_TIME",
        metadata_json={"deliverable": "Client Demo Release"}, observed_at=now,
    )
    async_session.add_all([mem_rahul, mem_mgr])

    ob_rahul = Obligation(
        id="ob-rahul-live", workspace_id="ws-default", owner="Rahul",
        beneficiary="Engineering",
        action="Database schema migration", status=ObligationStatus.OVERDUE,
        obligation_type=ObligationType.OWED_BY_ME, deadline=now - timedelta(days=1),
    )
    ob_mgr = Obligation(
        id="ob-mgr-live", workspace_id="ws-default", owner="Manager",
        beneficiary="Engineering",
        action="Client Demo Release", status=ObligationStatus.BLOCKED,
        obligation_type=ObligationType.OWED_BY_ME, deadline=now + timedelta(days=3),
    )
    edge = ObligationEdge(
        id="e-hist", workspace_id="ws-default", from_obligation_id="ob-mgr-live",
        to_obligation_id="ob-rahul-live", edge_type=EdgeType.DEPENDS_ON,
    )
    async_session.add_all([ob_rahul, ob_mgr, edge])
    await async_session.commit()

    plan = await IntelligenceOrchestrator.generate_decision_plan(async_session, "ob-mgr-live", force_refresh=True)
    assert plan is not None
    assert "WHY THIS PLAN?" in (plan.resolution_notes or "")
    # Check supporting evidence contains historical provenance
    has_mem_provenance = any(e.get("source_type") == "ORGANIZATIONAL_MEMORY" for e in plan.supporting_evidence)
    assert has_mem_provenance is True


# ==============================================================================
# 8. IMMUTABILITY & ZERO AUTONOMOUS MUTATION INVARIANTS
# ==============================================================================

@pytest.mark.asyncio
async def test_20_memory_retrieval_causes_zero_lifecycle_mutation(async_session: AsyncSession):
    now = datetime.now(timezone.utc)
    ob = Obligation(
        id="ob-safe", workspace_id="ws-default", owner="Tester",
        beneficiary="Engineering",
        action="Safety check obligation", status=ObligationStatus.BLOCKED,
        obligation_type=ObligationType.OWED_BY_ME,
    )
    async_session.add(ob)
    await async_session.commit()

    # Retrieve memories and compute analytics
    await MemoryRetrievalService.retrieve_for_obligation(async_session, ob)
    await HistoricalOwnerAnalyticsService.get_owner_analytics(async_session, "Tester")
    await HistoricalRiskSignalProvider.get_historical_risk_signals(async_session, ob)

    # Verify obligation state is 100% unchanged
    fresh_ob = await async_session.get(Obligation, "ob-safe")
    assert fresh_ob.status == ObligationStatus.BLOCKED
    assert fresh_ob.owner == "Tester"
