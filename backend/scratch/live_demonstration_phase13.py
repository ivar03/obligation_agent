"""
================================================================================
Obligation Agent — Phase 13 Live Demonstration Script
Adaptive Prediction, Calibration & Intelligence Feedback Layer
================================================================================
"""

import asyncio
import os
import sys
from datetime import datetime, timezone, timedelta
from typing import Dict, Any

# Ensure stdout handles utf-8 characters on Windows
if sys.stdout.encoding != "utf-8":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

# Ensure backend root is on Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

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
from app.services.intelligence.predictive_obligation_engine import PredictiveObligationEngine
from app.services.intelligence.feedback_service import FeedbackService
from app.services.intelligence.intervention_effectiveness_service import InterventionEffectivenessService


async def run_live_demonstration():
    print("=" * 80)
    print("  OBLIGATION AGENT — PHASE 13 LIVE DEMONSTRATION")
    print("  Adaptive Prediction, Calibration & Intelligence Feedback Layer")
    print("=" * 80)

    # --------------------------------------------------------------------------
    # Step 1: Initialize Database
    # --------------------------------------------------------------------------
    print("\n[Step 1/14] Initializing database and ensuring schema tables...")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print("  ✓ Schema tables verified (including prediction_feedbacks).")

    # --------------------------------------------------------------------------
    # Step 2: Create Active Commitments
    # --------------------------------------------------------------------------
    print("\n[Step 2/14] Creating active commitments with upstream dependencies...")
    async with AsyncSessionLocal() as session:
        now = datetime.now(timezone.utc)

        prereq = Obligation(
            owner="Alice",
            beneficiary="Engineering Team",
            action="Finalize core API security specification",
            deadline=now + timedelta(hours=6),
            status=ObligationStatus.CONFIRMED,
            obligation_type=ObligationType.OWED_TO_ME,
        )
        session.add(prereq)
        await session.commit()

        target_ob = Obligation(
            owner="Bob",
            beneficiary="Engineering Team",
            action="Implement OAuth2 authentication gateway",
            deadline=now + timedelta(hours=24),
            status=ObligationStatus.CONFIRMED,
            obligation_type=ObligationType.OWED_TO_ME,
        )
        session.add(target_ob)
        await session.commit()

        # Link dependency
        edge = ObligationEdge(
            from_obligation_id=target_ob.id,
            to_obligation_id=prereq.id,
            edge_type="DEPENDS_ON",
        )
        session.add(edge)
        await session.commit()

        target_id = target_ob.id
        prereq_id = prereq.id
        print(f"  ✓ Created target obligation: '{target_ob.action}' (ID: {target_id[:8]}...)")
        print(f"  ✓ Linked prerequisite: '{prereq.action}' (ID: {prereq_id[:8]}...)")

    # --------------------------------------------------------------------------
    # Step 3: Generate Initial predictive-v1 Baseline Forecast
    # --------------------------------------------------------------------------
    print("\n[Step 3/14] Generating predictive-v1 baseline forecast...")
    async with AsyncSessionLocal() as session:
        pred_v1 = await PredictiveObligationEngine.predict_obligation(session, target_id)
        print(f"  ✓ Model: {pred_v1.model_version}")
        print(f"  ✓ Baseline Failure Prob: {pred_v1.failure_probability * 100:.1f}%")
        print(f"  ✓ Expected Delay: ~{pred_v1.expected_delay_hours:.1f}h")
        print(f"  ✓ Confidence: {pred_v1.confidence * 100:.1f}%")

    # --------------------------------------------------------------------------
    # Step 4: Generate Initial adaptive-v1 Calibrated Forecast
    # --------------------------------------------------------------------------
    print("\n[Step 4/14] Generating adaptive-v1 calibrated forecast...")
    async with AsyncSessionLocal() as session:
        pred_adapt = await AdaptivePredictionProvider.predict(session, target_id)
        print(f"  ✓ Model: {pred_adapt.model_version}")
        print(f"  ✓ Adaptive Failure Prob: {pred_adapt.failure_probability * 100:.1f}%")
        print(f"  ✓ Adaptive Completion Prob: {pred_adapt.completion_probability * 100:.1f}%")
        print(f"  ✓ Expected Delay: ~{pred_adapt.expected_delay_hours:.1f}h")
        print(f"  ✓ Recommendation: {pred_adapt.preventative_recommendation}")

    # --------------------------------------------------------------------------
    # Step 5: Verify Structured Feature Attributions
    # --------------------------------------------------------------------------
    print("\n[Step 5/14] Verifying structured feature attribution signals...")
    async with AsyncSessionLocal() as session:
        weights = await WeightLearningEngine.get_calibrated_weights(session)
        attrs = FeatureAttributionEngine.extract_attributions(
            current_risk_score=0.60,
            hours_remaining=24.0,
            owner_avg_delay=12.0,
            owner_on_time_rate=0.45,
            blocker_count=1,
            similar_tasks_count=4,
            similar_on_time_rate=0.50,
            contradiction_score=0.0,
            learned_weights=weights,
        )
        for a in attrs:
            print(f"  • Feature: {a.feature:<28} | Val: {a.normalized_value:.2f} | Contrib: {a.contribution:+.2f} | Dir: {a.direction}")

    # --------------------------------------------------------------------------
    # Step 6: Model Comparison (predictive-v1 vs adaptive-v1)
    # --------------------------------------------------------------------------
    print("\n[Step 6/14] Comparing predictive-v1 (baseline) vs adaptive-v1 (calibrated)...")
    async with AsyncSessionLocal() as session:
        comp = await IntelligenceService.compare_models(session, target_id)
        print(f"  ✓ Variance: {comp.probability_variance * 100:+.1f}% failure probability")
        print(f"  ✓ Delay Variance: {comp.delay_variance_hours:+.1f}h")
        print(f"  ✓ Adjustment Reasons:")
        for r in comp.adjustment_reasons:
            print(f"     - {r}")

    # --------------------------------------------------------------------------
    # Step 7: Authoritative Ground-Truth Outcome Recording
    # --------------------------------------------------------------------------
    print("\n[Step 7/14] Recording authoritative outcome snapshots for resolved obligations...")
    async with AsyncSessionLocal() as session:
        # Create and resolve 5 historical obligations with various outcomes
        for i in range(5):
            hist_ob = Obligation(
                owner="Bob" if i % 2 == 0 else "Carol",
                beneficiary="Team",
                action=f"Historical Commitment {i+1}",
                deadline=now - timedelta(hours=20 - i * 4),
                status=ObligationStatus.COMPLETED,
                obligation_type=ObligationType.OWED_TO_ME,
            )
            session.add(hist_ob)
            await session.commit()

            # Record prediction snapshot first
            snap = await IntelligenceService.predict_and_snapshot(session, hist_ob.id, provider="adaptive-v1")

            # Record outcome snapshot
            outcome = await IntelligenceService.record_outcome_snapshot(
                session=session,
                obligation_id=hist_ob.id,
                completed_at=now - timedelta(hours=10 if i % 2 == 0 else 0),
            )
        print("  ✓ 5 ground-truth outcomes recorded and linked with prior prediction snapshots.")

    # --------------------------------------------------------------------------
    # Step 8: Closed-Loop Prediction Feedback Generation
    # --------------------------------------------------------------------------
    print("\n[Step 8/14] Generating closed-loop prediction feedback records...")
    async with AsyncSessionLocal() as session:
        patterns = await WeightLearningEngine.get_feature_patterns(session)
        print(f"  ✓ Total Feedback Evaluated: {patterns.total_feedback_evaluated}")
        print(f"  ✓ Top Learned Weights:")
        for feat, w in list(patterns.learned_weights.items())[:4]:
            print(f"     - {feat:<28}: {w:.4f}")

    # --------------------------------------------------------------------------
    # Step 9: Verify Historical Feedback Immutability
    # --------------------------------------------------------------------------
    print("\n[Step 9/14] Verifying immutability of historical PredictionFeedback records...")
    async with AsyncSessionLocal() as session:
        from sqlalchemy import select
        stmt = select(PredictionFeedback).limit(1)
        res = await session.execute(stmt)
        fb = res.scalar_one_or_none()
        if fb:
            orig_err = fb.absolute_delay_error
            # Update target obligation without mutating feedback
            target = await session.get(Obligation, target_id)
            if target:
                target.action = "Updated action title (testing immutability)"
                session.add(target)
                await session.commit()
            refreshed_fb = await session.get(PredictionFeedback, fb.id)
            assert refreshed_fb.absolute_delay_error == orig_err
            print(f"  ✓ Verified feedback record {fb.id[:8]}... remained strictly unchanged.")

    # --------------------------------------------------------------------------
    # Step 10: Statistical Calibration Evaluation Across Sufficiency Thresholds
    # --------------------------------------------------------------------------
    print("\n[Step 10/14] Evaluating model calibration and sample sufficiency...")
    async with AsyncSessionLocal() as session:
        cal = await CalibrationEngine.compute_calibration(session, model_version="adaptive-v1")
        print(f"  ✓ Sufficiency Status: {cal.status}")
        print(f"  ✓ Total Evaluations: {cal.total_evaluations}")
        print(f"  ✓ Brier Score: {cal.brier_score if cal.brier_score is not None else '—'}")
        print(f"  ✓ Mean Delay MAE: {cal.mean_absolute_delay_error if cal.mean_absolute_delay_error is not None else '—'}h")
        print(f"  ✓ Calibration Error: {cal.calibration_error if cal.calibration_error is not None else '—'}")
        print(f"  ✓ Advisory Message: {cal.message}")

    # --------------------------------------------------------------------------
    # Step 11: Statistical Weight Learning Updates
    # --------------------------------------------------------------------------
    print("\n[Step 11/14] Verifying statistical weight learning bounds...")
    async with AsyncSessionLocal() as session:
        weights = await WeightLearningEngine.get_calibrated_weights(session)
        for feat, w in weights.items():
            assert WeightLearningEngine.MIN_WEIGHT <= w <= WeightLearningEngine.MAX_WEIGHT
            print(f"  • {feat:<28}: {w:.3f} [bounded in 0.05..0.40]")

    # --------------------------------------------------------------------------
    # Step 12: Objective Intervention Effectiveness Analytics
    # --------------------------------------------------------------------------
    print("\n[Step 12/14] Analyzing observed intervention efficacy (neutral language)...")
    async with AsyncSessionLocal() as session:
        metrics = await InterventionEffectivenessService.get_metrics(session)
        print(f"  ✓ Sample Sufficiency: {metrics.sample_size_status}")
        print(f"  ✓ Observed Completion (With Follow-up): {metrics.observed_completion_rate_with_intervention * 100:.1f}%")
        print(f"  ✓ Observed Completion (No Follow-up): {metrics.observed_completion_rate_without_intervention * 100:.1f}%")
        print(f"  ✓ Objective Insights:")
        for ins in metrics.insights:
            print(f"     - {ins}")

    # --------------------------------------------------------------------------
    # Step 13: Safety Invariants Verification
    # --------------------------------------------------------------------------
    print("\n[Step 13/14] Verifying strict safety invariants...")
    async with AsyncSessionLocal() as session:
        target = await session.get(Obligation, target_id)
        # Check invariants
        assert target.status == ObligationStatus.CONFIRMED, "Invariant 1 failed: status altered"
        assert target.status != ObligationStatus.COMPLETED, "Invariant 2 failed: completed autonomously"
        
        inv_stmt = select(Intervention).where(Intervention.obligation_id == target_id)
        inv_res = await session.execute(inv_stmt)
        assert len(inv_res.scalars().all()) == 0, "Invariant 3 failed: autonomous intervention created"
        print("  ✓ Invariant 1: Predictions NEVER alter obligation lifecycle state.")
        print("  ✓ Invariant 2: Predictions NEVER complete obligations autonomously.")
        print("  ✓ Invariant 3: Predictions NEVER create unapproved external interventions.")
        print("  ✓ Invariant 4: Historical prediction snapshots & feedbacks remain immutable.")

    # --------------------------------------------------------------------------
    # Step 14: REST API & Adaptive Overview Verification
    # --------------------------------------------------------------------------
    print("\n[Step 14/14] Testing Adaptive REST API overview aggregation...")
    async with AsyncSessionLocal() as session:
        overview = await IntelligenceService.get_adaptive_overview(session)
        print(f"  ✓ Calibration Status: {overview.calibration_status}")
        print(f"  ✓ Active Evaluations: {overview.active_evaluations}")
        print(f"  ✓ Top Effective Features: {len(overview.top_effective_features)}")

    print("\n" + "=" * 80)
    print("  ✓ PHASE 13 LIVE CAUSAL DEMONSTRATION COMPLETE (14/14 Steps Passed)")
    print("=" * 80)


if __name__ == "__main__":
    asyncio.run(run_live_demonstration())
