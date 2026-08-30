"""
================================================================================
Feature Attribution Engine
Obligation Agent — Phase 13: Adaptive Prediction & Intelligence Feedback
================================================================================

Extracts, normalizes, and attributes predictive contributions for all features
used during obligation forecasting. Ensures explanations can be faithfully
reconstructed from persisted feature attributions.
"""

from typing import List, Dict, Any, Optional
from datetime import datetime, timezone

from app.core.status_machine import FeatureDirection
from app.schemas.intelligence import FeatureAttributionItem


class FeatureAttributionEngine:
    """
    Standardizes feature attribution tracking for explainability and weight learning.
    """

    FEATURE_NAMES = [
        "DEADLINE_PRESSURE",
        "HISTORICAL_DELAY_PATTERN",
        "DEPENDENCY_HEALTH",
        "OWNER_LATENCY",
        "SIMILAR_TASK_SUCCESS_RATE",
        "RECONCILIATION_CONTRADICTION",
        "CURRENT_RISK",
        "INTERVENTION_RESPONSE_HISTORY",
    ]

    @classmethod
    def build_attribution(
        cls,
        feature: str,
        raw_value: float,
        normalized_value: float,
        contribution: float,
        explanation: str,
    ) -> FeatureAttributionItem:
        """
        Creates a standardized FeatureAttributionItem.
        """
        if contribution > 0.01:
            direction = FeatureDirection.INCREASES_RISK.value
        elif contribution < -0.01:
            direction = FeatureDirection.DECREASES_RISK.value
        else:
            direction = FeatureDirection.NEUTRAL.value

        return FeatureAttributionItem(
            feature=feature,
            raw_value=round(float(raw_value), 4),
            normalized_value=round(float(normalized_value), 4),
            contribution=round(float(contribution), 4),
            direction=direction,
            explanation=explanation,
        )

    @classmethod
    def extract_attributions(
        cls,
        current_risk_score: float,
        hours_remaining: Optional[float],
        owner_avg_delay: float,
        owner_on_time_rate: float,
        blocker_count: int,
        similar_tasks_count: int,
        similar_on_time_rate: float,
        contradiction_score: float,
        learned_weights: Optional[Dict[str, float]] = None,
    ) -> List[FeatureAttributionItem]:
        """
        Calculates normalized feature signals and weighted contributions.
        """
        weights = learned_weights or {}
        attributions: List[FeatureAttributionItem] = []

        # 1. DEADLINE_PRESSURE
        if hours_remaining is not None:
            if hours_remaining < 0:
                norm_deadline = 1.0
                raw_deadline = hours_remaining
                explanation = f"Obligation is already {abs(round(hours_remaining, 1))}h past deadline."
            elif hours_remaining <= 24:
                norm_deadline = max(0.0, (24.0 - hours_remaining) / 24.0)
                raw_deadline = hours_remaining
                explanation = f"Imminent deadline: {round(hours_remaining, 1)}h remaining."
            elif hours_remaining <= 72:
                norm_deadline = max(0.0, (72.0 - hours_remaining) / 144.0)
                raw_deadline = hours_remaining
                explanation = f"Approaching deadline: {round(hours_remaining, 1)}h remaining."
            else:
                norm_deadline = 0.0
                raw_deadline = hours_remaining
                explanation = f"Comfortable temporal window: {round(hours_remaining, 1)}h remaining."

            w_deadline = weights.get("DEADLINE_PRESSURE", 0.22)
            contrib_deadline = (norm_deadline * 2.0 - 0.5) * w_deadline
            attributions.append(
                cls.build_attribution("DEADLINE_PRESSURE", raw_deadline, norm_deadline, contrib_deadline, explanation)
            )

        # 2. CURRENT_RISK
        norm_risk = max(0.0, min(1.0, current_risk_score))
        w_risk = weights.get("CURRENT_RISK", 0.20)
        contrib_risk = (norm_risk - 0.3) * w_risk
        attributions.append(
            cls.build_attribution(
                "CURRENT_RISK",
                current_risk_score,
                norm_risk,
                contrib_risk,
                f"Current RiskEngine composite score: {round(current_risk_score, 2)}.",
            )
        )

        # 3. OWNER_LATENCY / HISTORICAL_DELAY_PATTERN
        if owner_avg_delay > 0:
            norm_delay = min(1.0, owner_avg_delay / 48.0)
            w_delay = weights.get("HISTORICAL_DELAY_PATTERN", 0.16)
            contrib_delay = norm_delay * w_delay
            explanation = f"Owner historically delivers with latency (average delay: ~{round(owner_avg_delay, 1)}h)."
        elif owner_on_time_rate >= 0.8:
            norm_delay = 0.0
            w_delay = weights.get("HISTORICAL_DELAY_PATTERN", 0.16)
            contrib_delay = -0.12 * w_delay
            explanation = f"Owner maintains strong on-time delivery record ({round(owner_on_time_rate * 100)}% on-time)."
        else:
            norm_delay = 0.2
            contrib_delay = 0.0
            explanation = "Owner historical delivery latency is moderate / neutral."

        attributions.append(
            cls.build_attribution(
                "HISTORICAL_DELAY_PATTERN",
                owner_avg_delay,
                norm_delay,
                contrib_delay,
                explanation,
            )
        )

        # 4. DEPENDENCY_HEALTH
        if blocker_count > 0:
            norm_dep = min(1.0, blocker_count / 3.0)
            w_dep = weights.get("DEPENDENCY_HEALTH", 0.18)
            contrib_dep = norm_dep * w_dep
            explanation = f"Blocked by {blocker_count} active prerequisite dependencies."
        else:
            norm_dep = 0.0
            w_dep = weights.get("DEPENDENCY_HEALTH", 0.18)
            contrib_dep = -0.05 * w_dep
            explanation = "Prerequisite dependency graph is unblocked and clear."

        attributions.append(
            cls.build_attribution("DEPENDENCY_HEALTH", blocker_count, norm_dep, contrib_dep, explanation)
        )

        # 5. SIMILAR_TASK_SUCCESS_RATE
        if similar_tasks_count > 0:
            norm_sim = 1.0 - similar_on_time_rate
            w_sim = weights.get("SIMILAR_TASK_SUCCESS_RATE", 0.14)
            if similar_on_time_rate >= 0.7:
                contrib_sim = -0.10 * w_sim
                explanation = f"Structurally similar tasks historically completed on time ({round(similar_on_time_rate * 100)}% on-time rate)."
            elif similar_on_time_rate <= 0.4:
                contrib_sim = 0.12 * w_sim
                explanation = f"Structurally similar tasks frequently experienced delays ({round((1 - similar_on_time_rate) * 100)}% late/overdue rate)."
            else:
                contrib_sim = 0.0
                explanation = f"Structurally similar tasks have mixed historical completion rates ({round(similar_on_time_rate * 100)}% on-time)."

            attributions.append(
                cls.build_attribution(
                    "SIMILAR_TASK_SUCCESS_RATE",
                    similar_on_time_rate,
                    norm_sim,
                    contrib_sim,
                    explanation,
                )
            )

        # 6. RECONCILIATION_CONTRADICTION
        if contradiction_score > 0.2:
            norm_con = min(1.0, contradiction_score)
            w_con = weights.get("RECONCILIATION_CONTRADICTION", 0.15)
            contrib_con = norm_con * w_con
            explanation = f"Multi-source evidence contradiction detected across communication channels ({round(contradiction_score * 100)}% contradiction score)."
            attributions.append(
                cls.build_attribution(
                    "RECONCILIATION_CONTRADICTION",
                    contradiction_score,
                    norm_con,
                    contrib_con,
                    explanation,
                )
            )

        return attributions
