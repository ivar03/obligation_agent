"""
Historical Risk Signal Provider — Phase 16

Supplies bounded, explainable historical memory signals to the Risk Engine
and Adaptive Intelligence system without dominating authoritative current factual signals.
"""

from typing import Dict, Any, List, Optional
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.obligation import Obligation
from app.schemas.memory import MemoryRetrievalItem
from app.services.intelligence.memory.memory_retrieval_service import MemoryRetrievalService
from app.services.intelligence.memory.pattern_detection_service import PatternDetectionService
from app.core.status_machine import PatternType, PatternMaturity


class HistoricalRiskSignalProvider:
    """
    Computes bounded historical risk adjustments with strict provenance.
    """

    @classmethod
    async def get_historical_risk_signals(
        cls,
        session: AsyncSession,
        obligation: Obligation,
        relevant_memories: Optional[List[MemoryRetrievalItem]] = None,
    ) -> Dict[str, Any]:
        """
        Computes bounded risk signals from historical organizational memory.
        Returns:
            {
                "signals": {
                    "HISTORICAL_DELAY_PATTERN": float,
                    "SIMILAR_TASK_SUCCESS_RATE": float,
                    "RECURRING_BLOCKER_PATTERN": float,
                    "INTERVENTION_RESPONSE_HISTORY": float,
                },
                "net_historical_risk_delta": float,
                "supporting_memory_ids": List[str],
                "explanation": str,
            }
        """
        if relevant_memories is None:
            relevant_memories = await MemoryRetrievalService.retrieve_for_obligation(
                session, obligation, min_relevance=0.3, limit=10
            )

        patterns = await PatternDetectionService.detect_patterns_for_obligation(
            session, obligation, relevant_memories
        )

        signals: Dict[str, float] = {
            "HISTORICAL_DELAY_PATTERN": 0.0,
            "SIMILAR_TASK_SUCCESS_RATE": 0.0,
            "RECURRING_BLOCKER_PATTERN": 0.0,
            "INTERVENTION_RESPONSE_HISTORY": 0.0,
        }

        supporting_ids: List[str] = []
        notes: List[str] = []

        for p in patterns:
            # Only count patterns with at least EMERGING maturity
            if p.maturity == PatternMaturity.INSUFFICIENT_HISTORY:
                continue

            if p.pattern_type == PatternType.RECURRING_DELAY_PATTERN:
                # Bounded penalty: up to +0.25
                weight = 0.15 if p.maturity == PatternMaturity.EMERGING_PATTERN else 0.25
                signals["HISTORICAL_DELAY_PATTERN"] = round(min(0.25, weight * p.confidence), 3)
                supporting_ids.extend(p.supporting_memory_ids)
                notes.append(f"Historical delay pattern (+{signals['HISTORICAL_DELAY_PATTERN']:.2f})")

            elif p.pattern_type == PatternType.RECURRING_BLOCKER_PATTERN:
                # Bounded penalty: up to +0.20
                weight = 0.12 if p.maturity == PatternMaturity.EMERGING_PATTERN else 0.20
                signals["RECURRING_BLOCKER_PATTERN"] = round(min(0.20, weight * p.confidence), 3)
                supporting_ids.extend(p.supporting_memory_ids)
                notes.append(f"Recurring blocker pattern (+{signals['RECURRING_BLOCKER_PATTERN']:.2f})")

            elif p.pattern_type == PatternType.RECURRING_INTERVENTION_RESPONSE:
                # Bounded risk reduction (responsive owner): up to -0.15
                rate = p.neutral_metrics.get("positive_response_rate", 0.0)
                if rate >= 0.7:
                    reduction = -0.10 if p.maturity == PatternMaturity.EMERGING_PATTERN else -0.15
                    signals["INTERVENTION_RESPONSE_HISTORY"] = round(reduction * p.confidence, 3)
                    supporting_ids.extend(p.supporting_memory_ids)
                    notes.append(f"Responsive historical intervention rate ({signals['INTERVENTION_RESPONSE_HISTORY']:.2f})")

        # Check for similar task success rate
        outcome_mems = [m for m in relevant_memories if m.memory.memory_type == "OBLIGATION_OUTCOME"]
        if len(outcome_mems) >= 3:
            completed_on_time = len([m for m in outcome_mems if m.memory.outcome == "COMPLETED_ON_TIME"])
            ratio = completed_on_time / len(outcome_mems)
            if ratio >= 0.8:
                signals["SIMILAR_TASK_SUCCESS_RATE"] = -0.10
                notes.append("High historical comparable on-time rate (-0.10)")

        # Net adjustment bounded between -0.25 and +0.35
        net_delta = sum(signals.values())
        bounded_net_delta = max(-0.25, min(0.35, net_delta))

        explanation = "; ".join(notes) if notes else "No significant historical pattern risk signals detected."

        return {
            "signals": signals,
            "net_historical_risk_delta": round(bounded_net_delta, 3),
            "supporting_memory_ids": list(set(supporting_ids)),
            "explanation": explanation,
        }
