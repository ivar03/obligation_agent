"""
Historical Owner Analytics Service — Phase 16

Calculates strictly neutral, factual commitment analytics for owners from memory.
Guarantees zero personality judgments or character characterizations.
"""

from typing import List, Dict, Any, Optional
from datetime import datetime, timezone
import statistics
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, desc

from app.models.memory import OrganizationalMemory
from app.core.status_machine import MemoryType
from app.schemas.memory import HistoricalOwnerAnalyticsResponse


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class HistoricalOwnerAnalyticsService:
    """
    Produces factual, observational metrics for commitment owners.
    """

    @classmethod
    async def get_owner_analytics(
        cls,
        session: AsyncSession,
        owner_id: str,
        workspace_id: str = "ws-default",
    ) -> HistoricalOwnerAnalyticsResponse:
        """
        Gathers memory records for an owner and computes neutral observed metrics.
        """
        stmt = select(OrganizationalMemory).where(
            and_(
                OrganizationalMemory.workspace_id == workspace_id,
                OrganizationalMemory.owner_id == owner_id,
                OrganizationalMemory.is_active == True,
            )
        ).order_by(desc(OrganizationalMemory.observed_at))

        res = await session.execute(stmt)
        memories = res.scalars().all()

        outcome_mems = [m for m in memories if m.memory_type == MemoryType.OBLIGATION_OUTCOME]
        iv_mems = [m for m in memories if m.memory_type == MemoryType.INTERVENTION_OUTCOME]
        blocker_mems = [m for m in memories if m.memory_type == MemoryType.BLOCKER_PATTERN]
        ev_mems = [m for m in memories if m.memory_type == MemoryType.EVIDENCE_PATTERN]

        total_obs = len(outcome_mems)
        has_sufficient = total_obs >= 3

        if not has_sufficient:
            return HistoricalOwnerAnalyticsResponse(
                owner_id=owner_id,
                total_commitments_observed=total_obs,
                has_sufficient_history=False,
                completion_rate=1.0 if total_obs > 0 else 0.0,
                on_time_completion_rate=1.0 if total_obs > 0 else 0.0,
                median_delay_hours=0.0,
                late_completion_frequency=0.0,
                evidence_confirmation_rate=1.0,
                intervention_response_rate=1.0 if iv_mems else 0.0,
                recurring_blockers_count=len(blocker_mems),
                neutral_summary=f"Insufficient history ({total_obs} observation(s) observed, minimum 3 required for statistical baseline).",
                evaluated_at=utc_now(),
            )

        completed_count = len([m for m in outcome_mems if "COMPLETED" in str(m.outcome).upper()])
        on_time_count = len([m for m in outcome_mems if m.outcome == "COMPLETED_ON_TIME"])
        late_count = len([m for m in outcome_mems if m.outcome == "COMPLETED_LATE"])

        completion_rate = completed_count / total_obs if total_obs else 0.0
        on_time_rate = on_time_count / total_obs if total_obs else 0.0
        late_freq = late_count / total_obs if total_obs else 0.0

        # Delay hours
        delays = [
            m.metadata_json.get("delay_hours", 0.0)
            for m in outcome_mems
            if m.metadata_json.get("delay_hours", 0.0) > 0
        ]
        median_delay = float(statistics.median(delays)) if delays else 0.0

        # Intervention response rate
        iv_count = len(iv_mems)
        iv_responses = len([
            m for m in iv_mems
            if "PROGRESS" in str(m.outcome).upper() or "COMPLETED" in str(m.outcome).upper() or "ACK" in str(m.outcome).upper()
        ])
        iv_rate = iv_responses / iv_count if iv_count else 1.0

        # Evidence confirmation rate
        ev_count = len(ev_mems)
        ev_confirmed = len([m for m in ev_mems if "CONFIRMED" in str(m.outcome).upper()])
        ev_rate = ev_confirmed / ev_count if ev_count else 1.0

        neutral_summary = (
            f"{total_obs} comparable obligations observed for {owner_id}. "
            f"{on_time_count} completed on schedule, {late_count} completed past deadline "
            f"(median delay {median_delay:.1f} hours). Completion rate: {int(completion_rate * 100)}%."
        )

        return HistoricalOwnerAnalyticsResponse(
            owner_id=owner_id,
            total_commitments_observed=total_obs,
            has_sufficient_history=True,
            completion_rate=round(completion_rate, 2),
            on_time_completion_rate=round(on_time_rate, 2),
            median_delay_hours=round(median_delay, 1),
            late_completion_frequency=round(late_freq, 2),
            evidence_confirmation_rate=round(ev_rate, 2),
            intervention_response_rate=round(iv_rate, 2),
            recurring_blockers_count=len(blocker_mems),
            neutral_summary=neutral_summary,
            evaluated_at=utc_now(),
        )
