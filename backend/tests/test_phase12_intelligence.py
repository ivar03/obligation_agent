import pytest
import uuid
from datetime import datetime, timezone, timedelta
from httpx import AsyncClient
from sqlalchemy import select

from app.models.obligation import (
    Obligation,
    ObligationEdge,
    Evidence,
    Intervention,
    ReconciliationRecord,
)
from app.models.intelligence import ObligationOutcomeSnapshot, PredictionSnapshot
from app.core.status_machine import (
    ObligationStatus,
    ObligationType,
    EdgeType,
    EventSemanticRole,
    CorrelationStatus,
    ReconciliationStatus,
    ObligationOutcomeType,
    ActionType,
    RiskLevel,
)
from app.services.intelligence.outcome_classifier import OutcomeClassifier
from app.services.intelligence.similarity_engine import SimilarityEngine
from app.services.intelligence.historical_pattern_engine import HistoricalPatternEngine
from app.services.intelligence.predictive_obligation_engine import PredictiveObligationEngine
from app.services.intelligence.prediction_evaluation_service import PredictionEvaluationService
from app.services.intelligence.intelligence_service import IntelligenceService
from app.services.obligation_service import ObligationService
from app.schemas.obligation import ObligationStatusUpdate


# ==============================================================================
# 1. HISTORICAL OUTCOME CLASSIFICATION TESTS
# ==============================================================================

@pytest.mark.asyncio
async def test_on_time_completion_classification(db_session):
    """Test 1: On-time completion is deterministically classified as COMPLETED_ON_TIME."""
    now = datetime.now(timezone.utc)
    ob = Obligation(
        owner="Rahul",
        beneficiary="Ravi",
        action="Submit financial benchmark report",
        deadline=now + timedelta(days=2),
        status=ObligationStatus.COMPLETED,
        obligation_type=ObligationType.OWED_TO_ME,
    )
    db_session.add(ob)
    await db_session.commit()
    await db_session.refresh(ob)

    outcome_type, delay_hours = OutcomeClassifier.classify(ob, completed_at=now)
    assert outcome_type == ObligationOutcomeType.COMPLETED_ON_TIME
    assert delay_hours <= 0.0


@pytest.mark.asyncio
async def test_late_completion_classification(db_session):
    """Test 2: Completion after deadline is classified as COMPLETED_LATE with positive delay hours."""
    now = datetime.now(timezone.utc)
    ob = Obligation(
        owner="Rahul",
        beneficiary="Ravi",
        action="Deliver architecture spec document",
        deadline=now - timedelta(hours=14),
        status=ObligationStatus.COMPLETED,
        obligation_type=ObligationType.OWED_TO_ME,
    )
    db_session.add(ob)
    await db_session.commit()
    await db_session.refresh(ob)

    outcome_type, delay_hours = OutcomeClassifier.classify(ob, completed_at=now)
    assert outcome_type == ObligationOutcomeType.COMPLETED_LATE
    assert delay_hours >= 13.5


@pytest.mark.asyncio
async def test_blocked_outcome_classification(db_session):
    """Test 3: Blocked obligation is classified as BLOCKED."""
    now = datetime.now(timezone.utc)
    ob = Obligation(
        owner="Rahul",
        beneficiary="Ravi",
        action="Deploy API release v2",
        deadline=now + timedelta(days=3),
        status=ObligationStatus.BLOCKED,
        obligation_type=ObligationType.OWED_TO_ME,
    )
    db_session.add(ob)
    await db_session.commit()
    await db_session.refresh(ob)

    outcome_type, delay_hours = OutcomeClassifier.classify(ob)
    assert outcome_type == ObligationOutcomeType.BLOCKED


@pytest.mark.asyncio
async def test_intervention_assisted_completion(db_session):
    """Test 4: Obligation completed after human intervention is classified as COMPLETED_AFTER_INTERVENTION."""
    now = datetime.now(timezone.utc)
    ob = Obligation(
        owner="Rahul",
        beneficiary="Ravi",
        action="Provide vendor security assessment",
        deadline=now + timedelta(days=1),
        status=ObligationStatus.COMPLETED,
        obligation_type=ObligationType.OWED_TO_ME,
    )
    db_session.add(ob)
    await db_session.commit()
    await db_session.refresh(ob)

    inv = Intervention(
        obligation_id=ob.id,
        intervention_type="FOLLOW_UP_OWNER",
        status="EXECUTED",
        target_owner="Rahul",
        target_beneficiary="Ravi",
        title="Follow up with Rahul",
        rationale="Follow up on security assessment",
        message_draft="Please share the security assessment.",
        urgency="HIGH",
    )
    db_session.add(inv)
    await db_session.commit()

    outcome_type, _ = OutcomeClassifier.classify(ob, completed_at=now, interventions_list=[inv])
    assert outcome_type == ObligationOutcomeType.COMPLETED_AFTER_INTERVENTION


@pytest.mark.asyncio
async def test_conflicted_completion_classification(db_session):
    """Test 5: Obligation completed with unresolved contradiction history classified as CONFLICTED_COMPLETION."""
    now = datetime.now(timezone.utc)
    ob = Obligation(
        owner="Rahul",
        beneficiary="Ravi",
        action="Submit tax filing annexures",
        deadline=now + timedelta(days=1),
        status=ObligationStatus.COMPLETED,
        obligation_type=ObligationType.OWED_TO_ME,
    )
    db_session.add(ob)
    await db_session.commit()
    await db_session.refresh(ob)

    rec = ReconciliationRecord(
        obligation_id=ob.id,
        status=ReconciliationStatus.RESOLVED_CONFLICTING,
        confidence=0.85,
        consistency_score=0.40,
        contradiction_score=0.80,
    )
    db_session.add(rec)
    await db_session.commit()

    outcome_type, _ = OutcomeClassifier.classify(ob, completed_at=now, reconciliation_records=[rec])
    assert outcome_type == ObligationOutcomeType.CONFLICTED_COMPLETION


# ==============================================================================
# 2. PATTERN ANALYSIS & SIMILARITY ENGINE TESTS
# ==============================================================================

@pytest.mark.asyncio
async def test_owner_historical_completion_statistics(db_session):
    """Test 6: HistoricalPatternEngine computes neutral operational metrics per owner."""
    now = datetime.now(timezone.utc)
    
    # 2 on-time snapshots for Ravi, 2 late snapshots for Alex
    snap1 = ObligationOutcomeSnapshot(
        obligation_id=str(uuid.uuid4()),
        status="COMPLETED",
        outcome_type="COMPLETED_ON_TIME",
        owner="Ravi",
        beneficiary="Team",
        obligation_type="OWED_BY_ME",
        action="Complete sprint tasks",
        delay_hours=0.0,
    )
    snap2 = ObligationOutcomeSnapshot(
        obligation_id=str(uuid.uuid4()),
        status="COMPLETED",
        outcome_type="COMPLETED_ON_TIME",
        owner="Ravi",
        beneficiary="Team",
        obligation_type="OWED_BY_ME",
        action="Prepare product demo",
        delay_hours=0.0,
    )
    snap3 = ObligationOutcomeSnapshot(
        obligation_id=str(uuid.uuid4()),
        status="COMPLETED",
        outcome_type="COMPLETED_LATE",
        owner="Alex",
        beneficiary="Team",
        obligation_type="OWED_TO_ME",
        action="Deliver database migration",
        delay_hours=18.5,
    )
    snap4 = ObligationOutcomeSnapshot(
        obligation_id=str(uuid.uuid4()),
        status="COMPLETED",
        outcome_type="COMPLETED_LATE",
        owner="Alex",
        beneficiary="Team",
        obligation_type="OWED_TO_ME",
        action="Deliver API endpoints",
        delay_hours=24.0,
    )
    db_session.add_all([snap1, snap2, snap3, snap4])
    await db_session.commit()

    metrics = await HistoricalPatternEngine.get_owner_metrics(db_session)
    assert len(metrics) == 2

    ravi_m = next(m for m in metrics if m.owner == "Ravi")
    assert ravi_m.on_time_rate == 1.0
    assert ravi_m.avg_delay_hours == 0.0

    alex_m = next(m for m in metrics if m.owner == "Alex")
    assert alex_m.late_rate == 1.0
    assert alex_m.avg_delay_hours >= 20.0
    assert any("latency is elevated" in ins for ins in alex_m.insights)


@pytest.mark.asyncio
async def test_deadline_delay_distribution_patterns(db_session):
    """Test 7: HistoricalPatternEngine computes delay bucket distribution."""
    now = datetime.now(timezone.utc)
    snap_ontime = ObligationOutcomeSnapshot(
        obligation_id=str(uuid.uuid4()),
        status="COMPLETED",
        outcome_type="COMPLETED_ON_TIME",
        owner="Ravi",
        beneficiary="Team",
        obligation_type="OWED_BY_ME",
        action="Task 1",
        delay_hours=0.0,
    )
    snap_under12 = ObligationOutcomeSnapshot(
        obligation_id=str(uuid.uuid4()),
        status="COMPLETED",
        outcome_type="COMPLETED_LATE",
        owner="Rahul",
        beneficiary="Team",
        obligation_type="OWED_TO_ME",
        action="Task 2",
        delay_hours=6.0,
    )
    snap_over48 = ObligationOutcomeSnapshot(
        obligation_id=str(uuid.uuid4()),
        status="OVERDUE",
        outcome_type="OVERDUE",
        owner="Rahul",
        beneficiary="Team",
        obligation_type="OWED_TO_ME",
        action="Task 3",
        delay_hours=52.0,
    )
    db_session.add_all([snap_ontime, snap_under12, snap_over48])
    await db_session.commit()

    patterns = await HistoricalPatternEngine.get_historical_patterns(db_session)
    assert patterns.total_historical_snapshots == 3
    assert patterns.delay_distribution["ON_TIME"] == 1
    assert patterns.delay_distribution["UNDER_12_HOURS"] == 1
    assert patterns.delay_distribution["OVER_48_HOURS"] == 1


@pytest.mark.asyncio
async def test_similar_obligation_retrieval(db_session):
    """Test 8: SimilarityEngine retrieves structurally similar past obligations."""
    now = datetime.now(timezone.utc)
    target = Obligation(
        owner="Rahul",
        beneficiary="Ravi",
        action="Submit quarterly financial audit report",
        deadline=now + timedelta(days=2),
        status=ObligationStatus.CONFIRMED,
        obligation_type=ObligationType.OWED_TO_ME,
    )
    db_session.add(target)
    await db_session.commit()
    await db_session.refresh(target)

    # Similar snapshot (shares keywords 'quarterly', 'financial', 'audit', 'report', and owner Rahul)
    snap_similar = ObligationOutcomeSnapshot(
        obligation_id=str(uuid.uuid4()),
        status="COMPLETED",
        outcome_type="COMPLETED_ON_TIME",
        owner="Rahul",
        beneficiary="Ravi",
        obligation_type="OWED_TO_ME",
        action="Quarterly financial audit analysis report",
        delay_hours=0.0,
    )
    # Unrelated snapshot
    snap_unrelated = ObligationOutcomeSnapshot(
        obligation_id=str(uuid.uuid4()),
        status="COMPLETED",
        outcome_type="COMPLETED_ON_TIME",
        owner="Sara",
        beneficiary="Design",
        obligation_type="OWED_BY_ME",
        action="Design mobile app UI wireframes",
        delay_hours=0.0,
    )
    db_session.add_all([snap_similar, snap_unrelated])
    await db_session.commit()

    res = await SimilarityEngine.find_similar_obligations(db_session, target.id, limit=5)
    assert res.total_similar_count >= 1
    top = res.items[0]
    assert top.obligation_id == snap_similar.obligation_id
    assert top.similarity_score >= 0.50
    assert any("Matching keywords" in feat for feat in top.shared_features)


# ==============================================================================
# 3. PREDICTIVE ENGINE & EXPLANATION TESTS
# ==============================================================================

@pytest.mark.asyncio
async def test_high_deadline_pressure_increases_predicted_failure(db_session):
    """Test 9: Imminent deadline pressure elevates predicted failure probability with explainable reason."""
    now = datetime.now(timezone.utc)
    ob = Obligation(
        owner="Rahul",
        beneficiary="Ravi",
        action="Deliver project budget spreadsheet",
        deadline=now + timedelta(hours=6),  # 6 hours left
        status=ObligationStatus.CONFIRMED,
        obligation_type=ObligationType.OWED_TO_ME,
    )
    db_session.add(ob)
    await db_session.commit()
    await db_session.refresh(ob)

    pred = await PredictiveObligationEngine.predict_obligation(db_session, ob.id)
    assert pred.failure_probability >= 0.35
    assert any(r.signal == "DEADLINE_PRESSURE" for r in pred.reasons)
    assert pred.expected_delay_hours > 0


@pytest.mark.asyncio
async def test_active_blockers_increase_failure_and_blockage_likelihood(db_session):
    """Test 10: Unresolved prerequisite blockers elevate failure prob and blockage likelihood."""
    now = datetime.now(timezone.utc)
    ob_a = Obligation(
        owner="Rahul",
        beneficiary="Ravi",
        action="Database schema migration",
        deadline=now + timedelta(days=2),
        status=ObligationStatus.CONFIRMED,
        obligation_type=ObligationType.OWED_TO_ME,
    )
    ob_b = Obligation(
        owner="Ravi",
        beneficiary="Client",
        action="Frontend integration with new schema",
        deadline=now + timedelta(days=4),
        status=ObligationStatus.CONFIRMED,
        obligation_type=ObligationType.OWED_BY_ME,
    )
    db_session.add_all([ob_a, ob_b])
    await db_session.commit()
    await db_session.refresh(ob_a)
    await db_session.refresh(ob_b)

    # Edge: B depends on A
    edge = ObligationEdge(
        from_obligation_id=ob_b.id,
        to_obligation_id=ob_a.id,
        edge_type=EdgeType.DEPENDS_ON,
    )
    db_session.add(edge)
    await db_session.commit()

    pred_b = await PredictiveObligationEngine.predict_obligation(db_session, ob_b.id)
    assert pred_b.blockage_likelihood >= 0.20
    assert pred_b.failure_probability >= 0.20


@pytest.mark.asyncio
async def test_reconciliation_contradiction_elevates_failure_probability(db_session):
    """Test 11: Cross-provider contradiction elevates failure probability with RECONCILIATION_CONTRADICTION reason."""
    now = datetime.now(timezone.utc)
    ob = Obligation(
        owner="Rahul",
        beneficiary="Ravi",
        action="Submit compliance audit checklist",
        deadline=now + timedelta(days=2),
        status=ObligationStatus.CONFIRMED,
        obligation_type=ObligationType.OWED_TO_ME,
    )
    db_session.add(ob)
    await db_session.commit()
    await db_session.refresh(ob)

    rec = ReconciliationRecord(
        obligation_id=ob.id,
        status=ReconciliationStatus.CONFLICTING,
        confidence=0.90,
        consistency_score=0.20,
        contradiction_score=0.85,
    )
    db_session.add(rec)
    await db_session.commit()

    pred = await PredictiveObligationEngine.predict_obligation(db_session, ob.id)
    assert any(r.signal == "RECONCILIATION_CONTRADICTION" for r in pred.reasons)
    assert pred.failure_probability >= 0.30
    assert pred.recommended_action_type == ActionType.REVIEW_CONFLICTING_EVIDENCE


@pytest.mark.asyncio
async def test_predictions_remain_strictly_bounded(db_session):
    """Test 12: Probability values remain strictly bounded between 0.05 and 0.95."""
    now = datetime.now(timezone.utc)
    ob = Obligation(
        owner="SuperOverdueUser",
        beneficiary="Ravi",
        action="Impossible task long overdue",
        deadline=now - timedelta(days=30),  # Long past deadline
        status=ObligationStatus.OVERDUE,
        obligation_type=ObligationType.OWED_TO_ME,
    )
    db_session.add(ob)
    await db_session.commit()
    await db_session.refresh(ob)

    pred = await PredictiveObligationEngine.predict_obligation(db_session, ob.id)
    assert 0.05 <= pred.failure_probability <= 0.95
    assert 0.05 <= pred.completion_probability <= 0.95
    assert 0.20 <= pred.confidence <= 0.95
    assert pred.model_version == "predictive-v1"


# ==============================================================================
# 4. SAFETY INVARIANTS TESTS
# ==============================================================================

@pytest.mark.asyncio
async def test_safety_prediction_cannot_complete_obligation(db_session):
    """Test 13: Generating a prediction NEVER completes an obligation."""
    now = datetime.now(timezone.utc)
    ob = Obligation(
        owner="Rahul",
        beneficiary="Ravi",
        action="Complete architectural review",
        deadline=now + timedelta(days=2),
        status=ObligationStatus.CONFIRMED,
        obligation_type=ObligationType.OWED_TO_ME,
    )
    db_session.add(ob)
    await db_session.commit()
    await db_session.refresh(ob)

    pred = await IntelligenceService.predict_and_snapshot(db_session, ob.id)
    assert pred is not None

    await db_session.refresh(ob)
    assert ob.status == ObligationStatus.CONFIRMED
    assert ob.status != ObligationStatus.COMPLETED


@pytest.mark.asyncio
async def test_safety_prediction_cannot_alter_obligation_status(db_session):
    """Test 14: Generating a prediction NEVER alters obligation status."""
    now = datetime.now(timezone.utc)
    ob = Obligation(
        owner="Rahul",
        beneficiary="Ravi",
        action="Draft API contracts",
        deadline=now + timedelta(days=1),
        status=ObligationStatus.IN_PROGRESS,
        obligation_type=ObligationType.OWED_TO_ME,
    )
    db_session.add(ob)
    await db_session.commit()
    await db_session.refresh(ob)

    await IntelligenceService.predict_and_snapshot(db_session, ob.id)

    await db_session.refresh(ob)
    assert ob.status == ObligationStatus.IN_PROGRESS


@pytest.mark.asyncio
async def test_safety_recommendation_is_advisory_only(db_session):
    """Test 15: Preventative recommendation does NOT automatically create or execute an intervention."""
    now = datetime.now(timezone.utc)
    ob = Obligation(
        owner="Rahul",
        beneficiary="Ravi",
        action="High risk deliverable requiring review",
        deadline=now + timedelta(hours=4),
        status=ObligationStatus.CONFIRMED,
        obligation_type=ObligationType.OWED_TO_ME,
    )
    db_session.add(ob)
    await db_session.commit()
    await db_session.refresh(ob)

    pred = await IntelligenceService.predict_and_snapshot(db_session, ob.id)
    assert pred.preventative_recommendation is not None

    # Verify no interventions were autonomously created or executed
    inv_stmt = select(Intervention).where(Intervention.obligation_id == ob.id)
    inv_res = await db_session.execute(inv_stmt)
    invs = inv_res.scalars().all()
    assert len(invs) == 0


# ==============================================================================
# 5. PREDICTION EVALUATION & CALIBRATION TESTS
# ==============================================================================

@pytest.mark.asyncio
async def test_prediction_evaluation_insufficient_history(db_session):
    """Test 16: Fewer than 3 evaluated snapshots returns INSUFFICIENT_HISTORY status."""
    eval_res = await PredictionEvaluationService.evaluate_predictions(db_session)
    assert eval_res.status == "INSUFFICIENT_HISTORY"
    assert eval_res.total_predictions_evaluated == 0


@pytest.mark.asyncio
async def test_prediction_evaluation_metrics_calculation(db_session):
    """Test 17: PredictionEvaluationService computes MAE, Brier score, and accuracy once >= 3 outcomes exist."""
    now = datetime.now(timezone.utc)

    # Create 3 obligations with prediction snapshots and corresponding outcome snapshots
    for i in range(3):
        ob = Obligation(
            owner=f"User{i}",
            beneficiary="Team",
            action=f"Deliverable {i}",
            deadline=now - timedelta(hours=i * 5),
            status=ObligationStatus.COMPLETED,
            obligation_type=ObligationType.OWED_BY_ME,
        )
        db_session.add(ob)
        await db_session.commit()
        await db_session.refresh(ob)

        pred_snap = PredictionSnapshot(
            obligation_id=ob.id,
            model_version="predictive-v1",
            failure_probability=0.20 if i == 0 else 0.70,
            completion_probability=0.80 if i == 0 else 0.30,
            expected_delay_hours=0.0 if i == 0 else 10.0,
            confidence=0.85,
        )
        db_session.add(pred_snap)

        outcome_snap = ObligationOutcomeSnapshot(
            obligation_id=ob.id,
            status="COMPLETED",
            outcome_type="COMPLETED_ON_TIME" if i == 0 else "COMPLETED_LATE",
            owner=ob.owner,
            beneficiary=ob.beneficiary,
            obligation_type="OWED_BY_ME",
            action=ob.action,
            delay_hours=0.0 if i == 0 else 8.0,
        )
        db_session.add(outcome_snap)
        await db_session.commit()

    eval_res = await PredictionEvaluationService.evaluate_predictions(db_session)
    assert eval_res.status == "EVALUATED"
    assert eval_res.total_predictions_evaluated == 3
    assert eval_res.brier_score is not None
    assert eval_res.mean_absolute_error_hours is not None
    assert eval_res.accuracy is not None


# ==============================================================================
# 6. REST API ENDPOINTS TESTS
# ==============================================================================

@pytest.mark.asyncio
async def test_intelligence_rest_api_endpoints(client: AsyncClient, db_session):
    """Test 18: REST API endpoints for overview, dossier, prediction, patterns, and evaluation."""
    now = datetime.now(timezone.utc)
    ob = Obligation(
        owner="Rahul",
        beneficiary="Ravi",
        action="Quarterly financial compliance review",
        deadline=now + timedelta(days=2),
        status=ObligationStatus.CONFIRMED,
        obligation_type=ObligationType.OWED_TO_ME,
    )
    db_session.add(ob)
    await db_session.commit()
    await db_session.refresh(ob)

    # 1. GET /api/intelligence/overview
    res_ov = await client.get("/api/intelligence/overview")
    assert res_ov.status_code == 200
    ov_data = res_ov.json()
    assert "active_obligations_evaluated" in ov_data
    assert "predictions" in ov_data

    # 2. GET /api/intelligence/obligations/{id}/prediction
    res_pred = await client.get(f"/api/intelligence/obligations/{ob.id}/prediction")
    assert res_pred.status_code == 200
    pred_data = res_pred.json()
    assert pred_data["obligation_id"] == ob.id
    assert 0.05 <= pred_data["failure_probability"] <= 0.95
    assert len(pred_data["reasons"]) >= 1

    # 3. GET /api/intelligence/obligations/{id}
    res_dos = await client.get(f"/api/intelligence/obligations/{ob.id}")
    assert res_dos.status_code == 200
    dos_data = res_dos.json()
    assert "prediction" in dos_data
    assert "similar_obligations" in dos_data

    # 4. GET /api/intelligence/patterns
    res_pat = await client.get("/api/intelligence/patterns")
    assert res_pat.status_code == 200
    assert "delay_distribution" in res_pat.json()

    # 5. GET /api/intelligence/owners
    res_own = await client.get("/api/intelligence/owners")
    assert res_own.status_code == 200
    assert isinstance(res_own.json(), list)

    # 6. GET /api/intelligence/evaluation
    res_eval = await client.get("/api/intelligence/evaluation")
    assert res_eval.status_code == 200
    assert "status" in res_eval.json()

    # 7. GET /api/intelligence/history/{id}
    res_hist = await client.get(f"/api/intelligence/history/{ob.id}")
    assert res_hist.status_code == 200
    assert isinstance(res_hist.json(), list)


@pytest.mark.asyncio
async def test_lifecycle_snapshot_recorded_on_obligation_completed(db_session):
    """Test 19: ObligationService.update_status to COMPLETED triggers outcome snapshot recording."""
    now = datetime.now(timezone.utc)
    ob = Obligation(
        owner="Rahul",
        beneficiary="Ravi",
        action="Complete API integration",
        deadline=now + timedelta(days=1),
        status=ObligationStatus.CONFIRMED,
        obligation_type=ObligationType.OWED_TO_ME,
    )
    db_session.add(ob)
    await db_session.commit()
    await db_session.refresh(ob)

    # Complete via ObligationService
    await ObligationService.update_status(
        session=db_session,
        obligation_id=ob.id,
        status_data=ObligationStatusUpdate(status=ObligationStatus.COMPLETED),
    )

    # Verify outcome snapshot was persisted
    stmt = select(ObligationOutcomeSnapshot).where(ObligationOutcomeSnapshot.obligation_id == ob.id)
    res = await db_session.execute(stmt)
    snapshot = res.scalars().first()
    assert snapshot is not None
    assert snapshot.status == "COMPLETED"
    assert snapshot.outcome_type in ["COMPLETED_ON_TIME", "COMPLETED_LATE"]


@pytest.mark.asyncio
async def test_lifecycle_snapshot_recorded_on_obligation_cancelled(db_session):
    """Test 20: ObligationService.update_status to CANCELLED triggers outcome snapshot recording."""
    now = datetime.now(timezone.utc)
    ob = Obligation(
        owner="Rahul",
        beneficiary="Ravi",
        action="Obsolete task to be cancelled",
        deadline=now + timedelta(days=1),
        status=ObligationStatus.CONFIRMED,
        obligation_type=ObligationType.OWED_TO_ME,
    )
    db_session.add(ob)
    await db_session.commit()
    await db_session.refresh(ob)

    await ObligationService.update_status(
        session=db_session,
        obligation_id=ob.id,
        status_data=ObligationStatusUpdate(status=ObligationStatus.CANCELLED),
    )

    stmt = select(ObligationOutcomeSnapshot).where(ObligationOutcomeSnapshot.obligation_id == ob.id)
    res = await db_session.execute(stmt)
    snapshot = res.scalars().first()
    assert snapshot is not None
    assert snapshot.outcome_type == "CANCELLED"


@pytest.mark.asyncio
async def test_empty_historical_database_handled_gracefully(db_session):
    """Test 21: HistoricalPatternEngine handles empty database gracefully without errors."""
    patterns = await HistoricalPatternEngine.get_historical_patterns(db_session)
    assert patterns.total_historical_snapshots == 0
    assert patterns.completion_rate == 1.0
    assert patterns.avg_delay_hours == 0.0

    metrics = await HistoricalPatternEngine.get_owner_metrics(db_session)
    assert isinstance(metrics, list)


@pytest.mark.asyncio
async def test_prediction_provenance_information_populated(db_session):
    """Test 22: Predictions populate complete derived provenance information."""
    now = datetime.now(timezone.utc)
    ob = Obligation(
        owner="Ravi",
        beneficiary="Team",
        action="Write comprehensive project test suite",
        deadline=now + timedelta(days=3),
        status=ObligationStatus.CONFIRMED,
        obligation_type=ObligationType.OWED_BY_ME,
    )
    db_session.add(ob)
    await db_session.commit()
    await db_session.refresh(ob)

    pred = await PredictiveObligationEngine.predict_obligation(db_session, ob.id)
    assert pred.derived_from.current_risk_evaluated is True
    assert isinstance(pred.derived_from.similar_obligations_count, int)
    assert isinstance(pred.derived_from.dependency_history_count, int)


@pytest.mark.asyncio
async def test_custom_prediction_provider_interface(db_session):
    """Test 23: PredictiveObligationEngine supports pluggable PredictionProvider implementations."""
    now = datetime.now(timezone.utc)
    ob = Obligation(
        owner="TestUser",
        beneficiary="TestBeneficiary",
        action="Pluggable provider test task",
        deadline=now + timedelta(days=1),
        status=ObligationStatus.CONFIRMED,
        obligation_type=ObligationType.OWED_BY_ME,
    )
    db_session.add(ob)
    await db_session.commit()
    await db_session.refresh(ob)

    from app.services.intelligence.predictive_obligation_engine import (
        PredictionProvider,
        DeterministicPredictionProvider,
        ObligationPredictionResponse,
    )

    class CustomMockProvider:
        async def predict(self, session, obligation, context=None):
            return ObligationPredictionResponse(
                obligation_id=obligation.id,
                model_version="custom-mock-v1",
                failure_probability=0.42,
                completion_probability=0.58,
                expected_delay_hours=4.2,
                intervention_likelihood=0.10,
                blockage_likelihood=0.0,
                confidence=0.99,
                reasons=[],
                preventative_recommendation="Custom mock advice.",
                recommended_action_type=ActionType.NO_ACTION,
            )

    # Swap to custom provider
    original_provider = PredictiveObligationEngine._provider
    try:
        PredictiveObligationEngine.set_provider(CustomMockProvider())
        custom_pred = await PredictiveObligationEngine.predict_obligation(db_session, ob.id)
        assert custom_pred.model_version == "custom-mock-v1"
        assert custom_pred.failure_probability == 0.42
    finally:
        # Restore standard deterministic provider
        PredictiveObligationEngine.set_provider(original_provider)

    # Verify standard provider is restored
    std_pred = await PredictiveObligationEngine.predict_obligation(db_session, ob.id)
    assert std_pred.model_version == "predictive-v1"

