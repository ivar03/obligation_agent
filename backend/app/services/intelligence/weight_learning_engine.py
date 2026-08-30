"""
================================================================================
Weight Learning Engine
Obligation Agent — Phase 13: Adaptive Prediction & Intelligence Feedback
================================================================================

Learns bounded statistical feature weights from historical PredictionFeedback
records without opaque ML dependencies or uncontrolled weight updates.
"""

from typing import Dict, List, Any, Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.intelligence import PredictionFeedback
from app.schemas.intelligence import (
    FeatureEffectivenessItem,
    AdaptiveFeaturePatternsResponse,
)


class WeightLearningEngine:
    """
    Computes statistical feature effectiveness and bounded calibrated weights.
    """

    BASE_WEIGHTS: Dict[str, float] = {
        "DEADLINE_PRESSURE": 0.22,
        "CURRENT_RISK": 0.20,
        "DEPENDENCY_HEALTH": 0.18,
        "HISTORICAL_DELAY_PATTERN": 0.16,
        "RECONCILIATION_CONTRADICTION": 0.15,
        "SIMILAR_TASK_SUCCESS_RATE": 0.14,
        "OWNERSHIP_UNCERTAINTY": 0.10,
        "INTERVENTION_RESPONSE_HISTORY": 0.10,
    }

    LEARNING_RATE: float = 0.15
    MIN_WEIGHT: float = 0.05
    MAX_WEIGHT: float = 0.40

    @classmethod
    async def get_calibrated_weights(
        cls,
        session: AsyncSession,
    ) -> Dict[str, float]:
        """
        Computes learned weights based on historical feedback records.
        If insufficient feedback exists, returns BASE_WEIGHTS.
        """
        patterns = await cls.get_feature_patterns(session)
        return patterns.learned_weights

    @classmethod
    async def get_feature_patterns(
        cls,
        session: AsyncSession,
    ) -> AdaptiveFeaturePatternsResponse:
        """
        Evaluates observation counts, predictive direction, and empirical
        reliability for every feature across all historical feedback records.
        """
        query = select(PredictionFeedback).order_by(PredictionFeedback.created_at.desc())
        result = await session.execute(query)
        feedbacks = result.scalars().all()

        total_feedbacks = len(feedbacks)
        if total_feedbacks == 0:
            default_items = [
                FeatureEffectivenessItem(
                    feature=name,
                    observation_count=0,
                    average_contribution=0.0,
                    predictive_direction="NEUTRAL",
                    outcome_association=0.5,
                    reliability_score=0.5,
                    historical_usefulness="INITIAL_BASELINE",
                    confidence=0.5,
                )
                for name in cls.BASE_WEIGHTS.keys()
            ]
            return AdaptiveFeaturePatternsResponse(
                total_feedback_evaluated=0,
                learned_weights=dict(cls.BASE_WEIGHTS),
                features=default_items,
            )

        # Aggregate feature attribution data across feedbacks
        feature_stats: Dict[str, List[Dict[str, Any]]] = {k: [] for k in cls.BASE_WEIGHTS.keys()}

        for fb in feedbacks:
            attrs = fb.feature_attributions or []
            # Ground truth: was this a failure / delay?
            is_failure = 1.0 if fb.observed_outcome in ("COMPLETED_LATE", "OVERDUE", "BLOCKED") or fb.observed_delay_hours > 0.5 else 0.0

            for attr in attrs:
                feat = attr.get("feature")
                if feat in feature_stats:
                    feature_stats[feat].append({
                        "raw_value": float(attr.get("raw_value", 0.0)),
                        "normalized_value": float(attr.get("normalized_value", 0.0)),
                        "contribution": float(attr.get("contribution", 0.0)),
                        "direction": attr.get("direction", "NEUTRAL"),
                        "is_failure": is_failure,
                        "delay_hours": fb.observed_delay_hours,
                    })

        learned_weights: Dict[str, float] = {}
        effectiveness_items: List[FeatureEffectivenessItem] = []

        for feat_name, base_w in cls.BASE_WEIGHTS.items():
            obs = feature_stats[feat_name]
            obs_count = len(obs)

            if obs_count == 0:
                learned_weights[feat_name] = base_w
                effectiveness_items.append(
                    FeatureEffectivenessItem(
                        feature=feat_name,
                        observation_count=0,
                        average_contribution=0.0,
                        predictive_direction="NEUTRAL",
                        outcome_association=0.5,
                        reliability_score=0.5,
                        historical_usefulness="NO_OBSERVATIONS",
                        confidence=0.5,
                    )
                )
                continue

            avg_contrib = sum(o["contribution"] for o in obs) / obs_count
            
            # Correlation / association between normalized feature signal and failure
            # If high signal (> 0.5) occurred when failed -> +1, if high signal when succeeded -> -1
            concordance_sum = 0.0
            for o in obs:
                norm_val = o["normalized_value"]
                is_fail = o["is_failure"]
                # If feature is high (>=0.5) and failed -> concordant (1.0)
                # If feature is low (<0.5) and succeeded -> concordant (1.0)
                if (norm_val >= 0.5 and is_fail == 1.0) or (norm_val < 0.5 and is_fail == 0.0):
                    concordance_sum += 1.0
                else:
                    concordance_sum += 0.0

            outcome_assoc = concordance_sum / obs_count
            reliability = round(min(1.0, max(0.2, outcome_assoc * 0.9 + 0.1)), 3)

            # Bounded weight learning update:
            # new_w = clamp(base_w * (1 - lr) + (base_w * outcome_assoc * 1.5) * lr, MIN_WEIGHT, MAX_WEIGHT)
            lr = cls.LEARNING_RATE
            target_w = base_w * (0.6 + outcome_assoc * 0.8)
            updated_w = round(
                min(cls.MAX_WEIGHT, max(cls.MIN_WEIGHT, base_w * (1.0 - lr) + target_w * lr)),
                3
            )
            learned_weights[feat_name] = updated_w

            if avg_contrib > 0.01:
                direction = "INCREASES_FAILURE_RISK"
            elif avg_contrib < -0.01:
                direction = "DECREASES_FAILURE_RISK"
            else:
                direction = "NEUTRAL"

            if outcome_assoc >= 0.75:
                usefulness = "HIGHLY_PREDICTIVE"
            elif outcome_assoc >= 0.55:
                usefulness = "MODERATELY_PREDICTIVE"
            else:
                usefulness = "LOW_PREDICTIVE_SIGNAL"

            confidence = round(min(0.95, max(0.50, 0.50 + obs_count * 0.05)), 2)

            effectiveness_items.append(
                FeatureEffectivenessItem(
                    feature=feat_name,
                    observation_count=obs_count,
                    average_contribution=round(avg_contrib, 3),
                    predictive_direction=direction,
                    outcome_association=round(outcome_assoc, 3),
                    reliability_score=reliability,
                    historical_usefulness=usefulness,
                    confidence=confidence,
                )
            )

        # Sort effectiveness by reliability descending
        effectiveness_items.sort(key=lambda x: x.reliability_score, reverse=True)

        return AdaptiveFeaturePatternsResponse(
            total_feedback_evaluated=total_feedbacks,
            learned_weights=learned_weights,
            features=effectiveness_items,
        )
