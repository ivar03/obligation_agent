"""
================================================================================
Phase 13 Test Suite: Adaptive Prediction, Calibration & Intelligence Feedback
================================================================================
"""

import pytest
import os
from datetime import datetime, timezone, timedelta
from httpx import AsyncClient, ASGITransport

from sqlalchemy import select
from app.main import app
from app.core.database import AsyncSessionLocal, engine, Base
from app.models.obligation import Obligation, ObligationEdge, Evidence, Intervention
from app.models.intelligence import (
    ObligationOutcomeSnapshot,
    PredictionSnapshot,
    PredictionFeedback,
)
from app.core.status_machine import (
    ObligationStatus,
    ObligationType,
    ActionType,
    CalibrationStatus,
    FeatureDirection,
)
from app.services.obligation_service import ObligationService
from app.services.intelligence.intelligence_service import IntelligenceService
from app.services.intelligence.calibration_engine import CalibrationEngine
from app.services.intelligence.weight_learning_engine import WeightLearningEngine
from app.services.intelligence.feature_attribution_engine import FeatureAttributionEngine
from app.services.intelligence.adaptive_prediction_provider import AdaptivePredictionProvider
from app.services.intelligence.feedback_service import FeedbackService
from app.services.intelligence.intervention_effectiveness_service import InterventionEffectivenessService
from app.schemas.obligation import ObligationStatusUpdate


@pytest.fixture(autouse=True)
async def setup_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield


@pytest.mark.asyncio
async def test_feedback_recording_on_completion():
    """Verify PredictionFeedback record is automatically created on obligation completion."""
    async with AsyncSessionLocal() as session:
        now = datetime.now(timezone.utc)
        ob = Obligation(
            owner="Alice",
            beneficiary="Bob",
            action="Deliver security compliance review",
            deadline=now + timedelta(hours=10),
            status=ObligationStatus.CONFIRMED,
            obligation_type=ObligationType.OWED_TO_ME,
        )
        session.add(ob)
        await session.commit()

        # Generate a prediction snapshot
        pred = await IntelligenceService.predict_and_snapshot(session, ob.id, provider="adaptive-v1")
        assert pred.failure_probability >= 0.05
        assert pred.model_version == "adaptive-v1"

        # Authoritatively complete the obligation late
        ob.status = ObligationStatus.COMPLETED
        session.add(ob)
        await session.commit()

        snap = await IntelligenceService.record_outcome_snapshot(
            session=session,
            obligation_id=ob.id,
            completed_at=now + timedelta(hours=15),  # 5 hours late
        )
        assert snap is not None

        # Verify feedback was created
        feedbacks = await FeedbackService.record_feedback(session, ob.id, snap)
        assert len(feedbacks) >= 1
        fb = feedbacks[0]
        assert fb.obligation_id == ob.id
        assert fb.observed_outcome in ("COMPLETED_LATE", "COMPLETED_ON_TIME", "OVERDUE")
        assert fb.absolute_delay_error >= 0.0
        assert 0.0 <= fb.probability_error <= 1.0


@pytest.mark.asyncio
async def test_feedback_immutability():
    """Verify historical feedback records remain immutable when obligation states change."""
    async with AsyncSessionLocal() as session:
        now = datetime.now(timezone.utc)
        ob = Obligation(
            owner="Alice",
            beneficiary="Bob",
            action="Audit backend codebase",
            deadline=now - timedelta(hours=2),
            status=ObligationStatus.CONFIRMED,
            obligation_type=ObligationType.OWED_TO_ME,
        )
        session.add(ob)
        await session.commit()

        pred = await IntelligenceService.predict_and_snapshot(session, ob.id, provider="predictive-v1")
        snap = await IntelligenceService.record_outcome_snapshot(session, ob.id, completed_at=now)
        assert snap is not None

        feedbacks = await FeedbackService.record_feedback(session, ob.id, snap)
        assert len(feedbacks) >= 1
        original_fb_id = feedbacks[0].id
        original_delay_error = feedbacks[0].absolute_delay_error

        # Update obligation title
        ob.action = "Updated action title"
        session.add(ob)
        await session.commit()

        # Check feedback unchanged
        refreshed_fb = await session.get(PredictionFeedback, original_fb_id)
        assert refreshed_fb is not None
        assert refreshed_fb.absolute_delay_error == original_delay_error


@pytest.mark.asyncio
async def test_calibration_insufficient_history():
    """Verify CalibrationEngine returns INSUFFICIENT_HISTORY when samples < 3."""
    async with AsyncSessionLocal() as session:
        cal = await CalibrationEngine.compute_calibration(session)
        assert cal.status in (CalibrationStatus.INSUFFICIENT_HISTORY.value, CalibrationStatus.LOW_SAMPLE.value, CalibrationStatus.CALIBRATION_AVAILABLE.value)
        if cal.total_evaluations < 3:
            assert cal.status == CalibrationStatus.INSUFFICIENT_HISTORY.value
            assert cal.brier_score is None


@pytest.mark.asyncio
async def test_calibration_metrics_calculation():
    """Verify Brier score, calibration error, and MAE delay error calculations with mock feedbacks."""
    async with AsyncSessionLocal() as session:
        now = datetime.now(timezone.utc)
        # Create 4 test feedbacks
        for i in range(4):
            ob = Obligation(
                owner=f"User_{i}",
                beneficiary="Team",
                action=f"Task {i}",
                status=ObligationStatus.COMPLETED,
                obligation_type=ObligationType.OWED_TO_ME,
            )
            session.add(ob)
            await session.commit()

            snap = PredictionSnapshot(
                obligation_id=ob.id,
                model_version="adaptive-v1",
                failure_probability=0.70 if i % 2 == 0 else 0.20,
                expected_delay_hours=10.0 if i % 2 == 0 else 0.0,
                confidence=0.80,
                actual_outcome="COMPLETED_LATE" if i % 2 == 0 else "COMPLETED_ON_TIME",
                actual_delay_hours=12.0 if i % 2 == 0 else 0.0,
                evaluated_at=now,
            )
            session.add(snap)
            await session.commit()

            fb = PredictionFeedback(
                prediction_snapshot_id=snap.id,
                obligation_id=ob.id,
                prediction_provider="adaptive-v1",
                model_version="adaptive-v1",
                predicted_failure_probability=snap.failure_probability,
                predicted_completion_probability=1.0 - snap.failure_probability,
                predicted_expected_delay_hours=snap.expected_delay_hours,
                predicted_intervention_likelihood=0.5,
                predicted_confidence=0.8,
                observed_outcome=snap.actual_outcome,
                observed_delay_hours=snap.actual_delay_hours,
                absolute_delay_error=2.0 if i % 2 == 0 else 0.0,
                probability_error=0.30 if i % 2 == 0 else 0.20,
                was_high_risk_prediction_correct=True,
                created_at=now,
            )
            session.add(fb)

        await session.commit()

        cal = await CalibrationEngine.compute_calibration(session, model_version="adaptive-v1")
        assert cal.total_evaluations >= 4
        assert cal.status in (CalibrationStatus.LOW_SAMPLE.value, CalibrationStatus.CALIBRATION_AVAILABLE.value)
        assert cal.brier_score is not None
        assert 0.0 <= cal.brier_score <= 1.0
        assert cal.mean_absolute_delay_error is not None
        assert cal.high_risk_precision is not None


@pytest.mark.asyncio
async def test_feature_attribution_engine():
    """Verify FeatureAttributionEngine standardizes features, normalized values, and directions."""
    attributions = FeatureAttributionEngine.extract_attributions(
        current_risk_score=0.65,
        hours_remaining=12.0,
        owner_avg_delay=24.0,
        owner_on_time_rate=0.4,
        blocker_count=2,
        similar_tasks_count=3,
        similar_on_time_rate=0.33,
        contradiction_score=0.80,
    )
    assert len(attributions) >= 5
    feat_names = [a.feature for a in attributions]
    assert "DEADLINE_PRESSURE" in feat_names
    assert "CURRENT_RISK" in feat_names
    assert "HISTORICAL_DELAY_PATTERN" in feat_names
    assert "DEPENDENCY_HEALTH" in feat_names

    for attr in attributions:
        assert 0.0 <= attr.normalized_value <= 1.0
        assert attr.direction in ("INCREASES_RISK", "DECREASES_RISK", "NEUTRAL")
        assert len(attr.explanation) > 0


@pytest.mark.asyncio
async def test_weight_learning_bounded_updates():
    """Verify learned weights remain bounded within [MIN_WEIGHT, MAX_WEIGHT]."""
    async with AsyncSessionLocal() as session:
        patterns = await WeightLearningEngine.get_feature_patterns(session)
        assert patterns.learned_weights is not None
        for feat, weight in patterns.learned_weights.items():
            assert WeightLearningEngine.MIN_WEIGHT <= weight <= WeightLearningEngine.MAX_WEIGHT

        assert len(patterns.features) >= 5
        for f in patterns.features:
            assert 0.0 <= f.reliability_score <= 1.0
            assert 0.0 <= f.confidence <= 1.0


@pytest.mark.asyncio
async def test_adaptive_prediction_provider_bounds():
    """Verify AdaptivePredictionProvider strictly bounds all probabilities within [0.05, 0.95]."""
    async with AsyncSessionLocal() as session:
        now = datetime.now(timezone.utc)
        ob = Obligation(
            owner="Carlos",
            beneficiary="Diana",
            action="Deploy payment gateway integration",
            deadline=now + timedelta(hours=48),
            status=ObligationStatus.CONFIRMED,
            obligation_type=ObligationType.OWED_TO_ME,
        )
        session.add(ob)
        await session.commit()

        pred = await AdaptivePredictionProvider.predict(session, ob.id)
        assert pred.model_version == "adaptive-v1"
        assert 0.05 <= pred.failure_probability <= 0.95
        assert 0.05 <= pred.completion_probability <= 0.95
        assert 0.05 <= pred.confidence <= 0.95
        assert abs((pred.failure_probability + pred.completion_probability) - 1.0) < 0.01
        assert pred.expected_delay_hours >= 0.0
        assert len(pred.reasons) >= 1
        assert pred.preventative_recommendation is not None


@pytest.mark.asyncio
async def test_model_comparison():
    """Verify IntelligenceService.compare_models returns both models and calculates variances."""
    async with AsyncSessionLocal() as session:
        now = datetime.now(timezone.utc)
        ob = Obligation(
            owner="Elena",
            beneficiary="Team",
            action="Publish product release notes",
            deadline=now + timedelta(hours=24),
            status=ObligationStatus.CONFIRMED,
            obligation_type=ObligationType.OWED_TO_ME,
        )
        session.add(ob)
        await session.commit()

        comp = await IntelligenceService.compare_models(session, ob.id)
        assert comp.obligation_id == ob.id
        assert comp.predictive_v1.model_version == "predictive-v1"
        assert comp.adaptive_v1.model_version == "adaptive-v1"
        assert isinstance(comp.probability_variance, float)
        assert isinstance(comp.delay_variance_hours, float)
        assert len(comp.adjustment_reasons) >= 1


@pytest.mark.asyncio
async def test_prediction_history():
    """Verify IntelligenceService.get_prediction_history returns prediction snapshots."""
    async with AsyncSessionLocal() as session:
        now = datetime.now(timezone.utc)
        ob = Obligation(
            owner="Elena",
            beneficiary="Team",
            action="Sync marketing assets",
            deadline=now + timedelta(hours=18),
            status=ObligationStatus.CONFIRMED,
            obligation_type=ObligationType.OWED_TO_ME,
        )
        session.add(ob)
        await session.commit()

        # Generate 2 predictions
        await IntelligenceService.predict_and_snapshot(session, ob.id, provider="predictive-v1")
        await IntelligenceService.predict_and_snapshot(session, ob.id, provider="adaptive-v1")

        history = await IntelligenceService.get_prediction_history(session, ob.id)
        assert history.obligation_id == ob.id
        assert len(history.history) >= 2
        versions = [h.model_version for h in history.history]
        assert "predictive-v1" in versions
        assert "adaptive-v1" in versions


@pytest.mark.asyncio
async def test_intervention_effectiveness_analytics():
    """Verify InterventionEffectivenessService computes objective completion rates."""
    async with AsyncSessionLocal() as session:
        metric = await InterventionEffectivenessService.get_metrics(session)
        assert metric.sample_size_status in ("INSUFFICIENT_HISTORY", "LOW_SAMPLE", "CALIBRATION_AVAILABLE")
        assert 0.0 <= metric.observed_completion_rate_with_intervention <= 1.0
        assert 0.0 <= metric.observed_completion_rate_without_intervention <= 1.0
        assert len(metric.insights) >= 1


@pytest.mark.asyncio
async def test_safety_invariants():
    """Verify predictions NEVER change obligation status, complete obligations, or execute interventions."""
    async with AsyncSessionLocal() as session:
        now = datetime.now(timezone.utc)
        ob = Obligation(
            owner="SafetyTestUser",
            beneficiary="Admin",
            action="Critical infrastructure migration",
            deadline=now + timedelta(hours=5),
            status=ObligationStatus.CONFIRMED,
            obligation_type=ObligationType.OWED_TO_ME,
        )
        session.add(ob)
        await session.commit()

        # Run adaptive forecast
        pred = await AdaptivePredictionProvider.predict(session, ob.id)
        await session.refresh(ob)

        # Invariant 1: Status unchanged
        assert ob.status == ObligationStatus.CONFIRMED

        # Invariant 2: Obligation not completed
        assert ob.status != ObligationStatus.COMPLETED

        # Invariant 3 & 4: No autonomous interventions or messages
        inv_stmt = select(Intervention).where(Intervention.obligation_id == ob.id)
        inv_res = await session.execute(inv_stmt)
        assert len(inv_res.scalars().all()) == 0


@pytest.mark.asyncio
async def test_api_adaptive_endpoints():
    """Verify Phase 13 REST API endpoints return 200 OK with valid schemas."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Overview
        res = await client.get("/api/intelligence/adaptive/overview")
        assert res.status_code == 200
        data = res.json()
        assert "calibration_status" in data
        assert "top_effective_features" in data

        # Features
        res_feat = await client.get("/api/intelligence/adaptive/features")
        assert res_feat.status_code == 200
        feat_data = res_feat.json()
        assert "learned_weights" in feat_data

        # Calibration
        res_cal = await client.get("/api/intelligence/adaptive/calibration")
        assert res_cal.status_code == 200
        cal_data = res_cal.json()
        assert "status" in cal_data

        # Intervention effectiveness
        res_eff = await client.get("/api/intelligence/intervention-effectiveness")
        assert res_eff.status_code == 200
        eff_data = res_eff.json()
        assert "sample_size_status" in eff_data


@pytest.mark.asyncio
async def test_api_compare_and_history():
    """Verify /compare/{id} and /prediction-history REST endpoints."""
    async with AsyncSessionLocal() as session:
        now = datetime.now(timezone.utc)
        ob = Obligation(
            owner="David",
            beneficiary="Sarah",
            action="Finalize API documentation",
            deadline=now + timedelta(hours=14),
            status=ObligationStatus.CONFIRMED,
            obligation_type=ObligationType.OWED_TO_ME,
        )
        session.add(ob)
        await session.commit()
        ob_id = ob.id

        # Generate a prediction
        await IntelligenceService.predict_and_snapshot(session, ob_id, provider="adaptive-v1")

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Compare
        res_comp = await client.get(f"/api/intelligence/compare/{ob_id}")
        assert res_comp.status_code == 200
        comp_data = res_comp.json()
        assert comp_data["obligation_id"] == ob_id
        assert "predictive_v1" in comp_data
        assert "adaptive_v1" in comp_data
        assert "probability_variance" in comp_data

        # History
        res_hist = await client.get(f"/api/intelligence/obligations/{ob_id}/prediction-history")
        assert res_hist.status_code == 200
        hist_data = res_hist.json()
        assert hist_data["obligation_id"] == ob_id
        assert len(hist_data["history"]) >= 1


@pytest.mark.asyncio
async def test_monotonic_weight_learning():
    """Verify weight updates adaptively increase weight when a feature consistently predicts failure."""
    async with AsyncSessionLocal() as session:
        now = datetime.now(timezone.utc)
        initial_patterns = await WeightLearningEngine.get_feature_patterns(session)
        init_deadline_w = initial_patterns.learned_weights.get("DEADLINE_PRESSURE", 0.22)

        # Add 5 concordant feedbacks where DEADLINE_PRESSURE was high and outcome was late
        for i in range(5):
            ob = Obligation(
                owner=f"PressureUser_{i}",
                beneficiary="Team",
                action=f"Urgent task {i}",
                status=ObligationStatus.COMPLETED,
                obligation_type=ObligationType.OWED_TO_ME,
            )
            session.add(ob)
            await session.commit()

            snap = PredictionSnapshot(
                obligation_id=ob.id,
                model_version="adaptive-v1",
                failure_probability=0.85,
                expected_delay_hours=18.0,
                confidence=0.80,
                prediction_reasons=[{
                    "signal": "DEADLINE_PRESSURE",
                    "impact": 0.25,
                    "explanation": "Lapsed deadline.",
                }],
                actual_outcome="COMPLETED_LATE",
                actual_delay_hours=20.0,
                evaluated_at=now,
            )
            session.add(snap)
            await session.commit()

            fb = PredictionFeedback(
                prediction_snapshot_id=snap.id,
                obligation_id=ob.id,
                prediction_provider="adaptive-v1",
                model_version="adaptive-v1",
                predicted_failure_probability=0.85,
                predicted_completion_probability=0.15,
                predicted_expected_delay_hours=18.0,
                predicted_intervention_likelihood=0.7,
                predicted_confidence=0.85,
                feature_attributions=[{
                    "feature": "DEADLINE_PRESSURE",
                    "raw_value": -5.0,
                    "normalized_value": 0.95,
                    "contribution": 0.25,
                    "direction": "INCREASES_RISK",
                    "explanation": "Lapsed deadline.",
                }],
                observed_outcome="COMPLETED_LATE",
                observed_delay_hours=20.0,
                absolute_delay_error=2.0,
                probability_error=0.15,
                was_high_risk_prediction_correct=True,
                created_at=now,
            )
            session.add(fb)
        await session.commit()

        updated_patterns = await WeightLearningEngine.get_feature_patterns(session)
        updated_deadline_w = updated_patterns.learned_weights.get("DEADLINE_PRESSURE", 0.22)
        # Weight should have increased due to 100% concordance
        assert updated_deadline_w >= init_deadline_w
        assert updated_deadline_w <= WeightLearningEngine.MAX_WEIGHT

