"""
Deterministic Decision Ranking Engine for Phase 15.

Evaluates and ranks candidate resolution strategies using bounded, deterministic multi-factor scoring:
- Risk reduction
- Blast radius recovery
- Critical path improvement
- Evidence & prediction confidence
- Penalties for execution complexity and uncertainty

Invariant: Scores are strictly bounded: 0.0 <= decision_score <= 1.0
Terminology: "Recommended strategy based on current available signals" (never "optimal").
"""

from typing import Dict, Any, Tuple


class DecisionRankingEngine:
    """
    Deterministic ranking engine for candidate resolution strategies.
    """

    @classmethod
    def rank_strategy(cls, strategy_data: Dict[str, Any]) -> Tuple[float, Dict[str, float]]:
        """
        Calculates a deterministic, bounded decision score in [0.0, 1.0].
        """
        risk_reduction = float(strategy_data.get("risk_reduction", 0.0))
        # Ensure positive reduction value
        if risk_reduction < 0:
            risk_reduction = abs(risk_reduction)
        risk_reduction = min(1.0, max(0.0, risk_reduction))

        blast_radius_reduction = float(strategy_data.get("blast_radius_reduction", 0.0))
        blast_radius_reduction = min(1.0, max(0.0, blast_radius_reduction))

        critical_path_improvement = float(strategy_data.get("critical_path_improvement", 0.0))
        critical_path_improvement = min(1.0, max(0.0, critical_path_improvement))

        evidence_confidence = float(strategy_data.get("evidence_confidence", 0.8))
        evidence_confidence = min(1.0, max(0.0, evidence_confidence))

        prediction_confidence = float(strategy_data.get("prediction_confidence", 0.8))
        prediction_confidence = min(1.0, max(0.0, prediction_confidence))

        execution_complexity = float(strategy_data.get("execution_complexity", 0.2))
        execution_complexity = min(1.0, max(0.0, execution_complexity))

        uncertainty_penalty = float(strategy_data.get("uncertainty_penalty", 0.0))
        uncertainty_penalty = min(1.0, max(0.0, uncertainty_penalty))

        # Weightings
        w_risk = 0.30 * risk_reduction
        w_blast = 0.25 * blast_radius_reduction
        w_cp = 0.20 * critical_path_improvement
        w_evidence = 0.15 * evidence_confidence
        w_pred = 0.10 * prediction_confidence

        p_complexity = 0.10 * execution_complexity
        p_uncertainty = 0.10 * uncertainty_penalty

        raw_score = (w_risk + w_blast + w_cp + w_evidence + w_pred) - (p_complexity + p_uncertainty)
        bounded_score = round(max(0.05, min(0.99, raw_score)), 3)

        breakdown = {
            "risk_reduction_component": round(w_risk, 3),
            "blast_radius_component": round(w_blast, 3),
            "critical_path_component": round(w_cp, 3),
            "evidence_confidence_component": round(w_evidence, 3),
            "prediction_confidence_component": round(w_pred, 3),
            "complexity_penalty": round(-p_complexity, 3),
            "uncertainty_penalty": round(-p_uncertainty, 3),
            "raw_total": round(raw_score, 3),
            "final_bounded_score": bounded_score,
        }

        return bounded_score, breakdown
