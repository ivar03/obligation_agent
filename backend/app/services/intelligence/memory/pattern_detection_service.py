"""
Pattern Detection Service — Phase 16

Detects recurring patterns across organizational memories with explicit
sufficiency thresholds (INSUFFICIENT_HISTORY < 3, EMERGING_PATTERN 3-9, ESTABLISHED_PATTERN 10+).
"""

from typing import List, Dict, Any, Optional
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, desc

from app.models.obligation import Obligation
from app.models.memory import OrganizationalMemory
from app.core.status_machine import (
    MemoryType,
    PatternType,
    PatternMaturity,
    RecurrenceInterval,
)
from app.schemas.memory import (
    HistoricalPatternItem,
    RecurringObligationItem,
    MemoryRetrievalItem,
)


def _classify_maturity(count: int) -> PatternMaturity:
    if count < 3:
        return PatternMaturity.INSUFFICIENT_HISTORY
    elif count < 10:
        return PatternMaturity.EMERGING_PATTERN
    else:
        return PatternMaturity.ESTABLISHED_PATTERN


class PatternDetectionService:
    """
    Identifies recurring organizational patterns and recurrence cadences from memory.
    """

    @classmethod
    async def detect_patterns_for_obligation(
        cls,
        session: AsyncSession,
        obligation: Obligation,
        relevant_memories: List[MemoryRetrievalItem],
    ) -> List[HistoricalPatternItem]:
        """
        Detects patterns specifically relevant to the target obligation.
        """
        patterns: List[HistoricalPatternItem] = []

        if not relevant_memories:
            return patterns

        # 1. Check for Recurring Delay Pattern
        delay_memories = [
            m.memory for m in relevant_memories
            if m.memory.memory_type == MemoryType.OBLIGATION_OUTCOME and m.memory.outcome == "COMPLETED_LATE"
        ]
        if delay_memories:
            count = len(delay_memories)
            maturity = _classify_maturity(count)
            delays = [m.metadata_json.get("delay_hours", 0.0) for m in delay_memories]
            avg_delay = sum(delays) / count if count else 0.0

            desc = f"{count} comparable commitment(s) completed past deadline (avg {avg_delay:.1f}h delay)."
            confidence = min(0.95, 0.4 + (count * 0.08))

            patterns.append(
                HistoricalPatternItem(
                    pattern_type=PatternType.RECURRING_DELAY_PATTERN,
                    maturity=maturity,
                    observation_count=count,
                    confidence=round(confidence, 2),
                    supporting_memory_ids=[m.id for m in delay_memories],
                    first_observed_at=min([m.observed_at for m in delay_memories]) if delay_memories else None,
                    last_observed_at=max([m.observed_at for m in delay_memories]) if delay_memories else None,
                    description=desc,
                    neutral_metrics={
                        "late_count": count,
                        "average_delay_hours": round(avg_delay, 1),
                    },
                )
            )

        # 2. Check for Recurring Blocker Pattern
        blocker_memories = [
            m.memory for m in relevant_memories
            if m.memory.memory_type == MemoryType.BLOCKER_PATTERN
        ]
        if blocker_memories:
            count = len(blocker_memories)
            maturity = _classify_maturity(count)
            reasons = [m.metadata_json.get("blocker_reason", m.semantic_summary) for m in blocker_memories]
            desc = f"{count} comparable blocker instance(s) observed: {', '.join(reasons[:2])}."
            confidence = min(0.95, 0.5 + (count * 0.08))

            patterns.append(
                HistoricalPatternItem(
                    pattern_type=PatternType.RECURRING_BLOCKER_PATTERN,
                    maturity=maturity,
                    observation_count=count,
                    confidence=round(confidence, 2),
                    supporting_memory_ids=[m.id for m in blocker_memories],
                    first_observed_at=min([m.observed_at for m in blocker_memories]) if blocker_memories else None,
                    last_observed_at=max([m.observed_at for m in blocker_memories]) if blocker_memories else None,
                    description=desc,
                    neutral_metrics={"blocker_occurrences": count},
                )
            )

        # 3. Check for Recurring Dependency Cascade Pattern
        dep_memories = [
            m.memory for m in relevant_memories
            if m.memory.memory_type == MemoryType.DEPENDENCY_PATTERN
        ]
        if dep_memories:
            count = len(dep_memories)
            maturity = _classify_maturity(count)
            desc = f"{count} historical dependency cascade resolution(s) observed for similar prerequisites."
            confidence = min(0.95, 0.5 + (count * 0.07))

            patterns.append(
                HistoricalPatternItem(
                    pattern_type=PatternType.RECURRING_DEPENDENCY_PATTERN,
                    maturity=maturity,
                    observation_count=count,
                    confidence=round(confidence, 2),
                    supporting_memory_ids=[m.id for m in dep_memories],
                    first_observed_at=min([m.observed_at for m in dep_memories]) if dep_memories else None,
                    last_observed_at=max([m.observed_at for m in dep_memories]) if dep_memories else None,
                    description=desc,
                    neutral_metrics={"cascade_count": count},
                )
            )

        # 4. Check for Intervention Response Pattern
        iv_memories = [
            m.memory for m in relevant_memories
            if m.memory.memory_type == MemoryType.INTERVENTION_OUTCOME
        ]
        if iv_memories:
            count = len(iv_memories)
            maturity = _classify_maturity(count)
            progress_responses = len([m for m in iv_memories if "PROGRESS" in str(m.outcome).upper() or "COMPLETED" in str(m.outcome).upper()])
            rate = progress_responses / count if count else 0.0
            desc = f"{progress_responses} of {count} comparable intervention(s) received a progress or completion response ({int(rate*100)}%)."
            confidence = min(0.95, 0.5 + (count * 0.08))

            patterns.append(
                HistoricalPatternItem(
                    pattern_type=PatternType.RECURRING_INTERVENTION_RESPONSE,
                    maturity=maturity,
                    observation_count=count,
                    confidence=round(confidence, 2),
                    supporting_memory_ids=[m.id for m in iv_memories],
                    first_observed_at=min([m.observed_at for m in iv_memories]) if iv_memories else None,
                    last_observed_at=max([m.observed_at for m in iv_memories]) if iv_memories else None,
                    description=desc,
                    neutral_metrics={
                        "interventions_count": count,
                        "positive_response_rate": round(rate, 2),
                    },
                )
            )

        return patterns

    @classmethod
    async def detect_recurring_commitment(
        cls,
        session: AsyncSession,
        obligation: Obligation,
        relevant_memories: List[MemoryRetrievalItem],
    ) -> Optional[RecurringObligationItem]:
        """
        Detects if an obligation is part of a recurring cadence (e.g. weekly reports, daily checkins).
        """
        outcome_memories = [
            m.memory for m in relevant_memories
            if m.memory.memory_type == MemoryType.OBLIGATION_OUTCOME and m.relevance_score >= 0.5
        ]

        if len(outcome_memories) < 2:
            return None

        # Sort chronologically
        sorted_mems = sorted(outcome_memories, key=lambda x: x.observed_at)
        timestamps = [m.observed_at for m in sorted_mems]

        intervals_days = []
        for i in range(1, len(timestamps)):
            diff = (timestamps[i] - timestamps[i - 1]).total_seconds() / 86400.0
            if diff > 0.1:
                intervals_days.append(diff)

        if not intervals_days:
            return None

        avg_interval = sum(intervals_days) / len(intervals_days)
        count = len(sorted_mems)

        rec_type = RecurrenceInterval.AD_HOC
        if 0.8 <= avg_interval <= 1.5:
            rec_type = RecurrenceInterval.DAILY
        elif 6.0 <= avg_interval <= 8.5:
            rec_type = RecurrenceInterval.WEEKLY
        elif 12.0 <= avg_interval <= 16.0:
            rec_type = RecurrenceInterval.BIWEEKLY
        elif 25.0 <= avg_interval <= 35.0:
            rec_type = RecurrenceInterval.MONTHLY
        elif 80.0 <= avg_interval <= 100.0:
            rec_type = RecurrenceInterval.QUARTERLY

        confidence = min(0.95, 0.4 + (count * 0.1))
        last_occ = timestamps[-1]

        desc = f"Comparable commitment observed {count} times with an estimated {rec_type.value.lower()} cadence (~{avg_interval:.1f} days)."

        return RecurringObligationItem(
            recurrence_type=rec_type,
            estimated_interval_days=round(avg_interval, 1),
            observation_count=count,
            confidence=round(confidence, 2),
            last_occurrence=last_occ,
            next_expected_window=f"Within ~{int(avg_interval)} days of last occurrence",
            description=desc,
        )
