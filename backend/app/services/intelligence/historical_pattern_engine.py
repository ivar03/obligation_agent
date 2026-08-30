import statistics
from typing import List, Dict, Any, Optional
from collections import defaultdict
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.intelligence import ObligationOutcomeSnapshot
from app.schemas.intelligence import (
    OwnerPatternMetric,
    HistoricalPatternsResponse,
)


class HistoricalPatternEngine:
    """
    Historical pattern learning service that analyzes outcome snapshots to identify
    delay patterns, owner latencies, dependency bottlenecks, and intervention efficacies.
    """

    @classmethod
    async def get_owner_metrics(cls, session: AsyncSession) -> List[OwnerPatternMetric]:
        """
        Calculates neutral, objective operational analytics per obligation owner.
        """
        stmt = select(ObligationOutcomeSnapshot).order_by(ObligationOutcomeSnapshot.created_at.desc())
        res = await session.execute(stmt)
        snapshots = res.scalars().all()

        owner_groups: Dict[str, List[ObligationOutcomeSnapshot]] = defaultdict(list)
        for snap in snapshots:
            owner_groups[snap.owner].append(snap)

        metrics: List[OwnerPatternMetric] = []
        for owner, snaps in owner_groups.items():
            total = len(snaps)
            completed = sum(1 for s in snaps if s.status == "COMPLETED")
            on_time = sum(1 for s in snaps if s.outcome_type in [
                "COMPLETED_ON_TIME", "COMPLETED_AFTER_INTERVENTION", "COMPLETED_AFTER_DEPENDENCY_RESOLUTION"
            ])
            late = sum(1 for s in snaps if s.outcome_type == "COMPLETED_LATE")
            overdue = sum(1 for s in snaps if s.outcome_type == "OVERDUE")
            blocked = sum(1 for s in snaps if s.outcome_type == "BLOCKED" or s.blocker_count > 0)

            delays = [s.delay_hours for s in snaps if s.delay_hours > 0]
            avg_delay = float(sum(delays) / len(delays)) if delays else 0.0
            med_delay = float(statistics.median(delays)) if delays else 0.0

            inv_req = sum(1 for s in snaps if s.intervention_required or s.intervention_count > 0)
            inv_succ = sum(1 for s in snaps if s.intervention_successful)
            inv_rate = (inv_succ / inv_req) if inv_req > 0 else 1.0

            on_time_rate = (on_time / completed) if completed > 0 else (0.0 if total > 0 else 1.0)
            late_rate = (late / completed) if completed > 0 else 0.0
            blocker_freq = blocked / total if total > 0 else 0.0

            insights: List[str] = []
            if total >= 2:
                if on_time_rate >= 0.85:
                    insights.append(f"High on-time completion consistency ({on_time_rate * 100:.0f}%).")
                elif late_rate >= 0.40 or avg_delay >= 12.0:
                    insights.append(f"Historical completion latency is elevated (avg delay: ~{avg_delay:.1f}h).")

                if blocker_freq >= 0.35:
                    insights.append(f"Frequently constrained by upstream dependency blockers ({blocker_freq * 100:.0f}%).")

                if inv_req > 0 and inv_rate >= 0.75:
                    insights.append("Responsive to follow-up interventions and status inquiries.")

            if not insights:
                insights.append("Baseline operational delivery pattern observed.")

            metrics.append(
                OwnerPatternMetric(
                    owner=owner,
                    total_obligations=total,
                    completed_count=completed,
                    on_time_count=on_time,
                    late_count=late,
                    overdue_count=overdue,
                    blocked_count=blocked,
                    on_time_rate=round(on_time_rate, 2),
                    late_rate=round(late_rate, 2),
                    avg_delay_hours=round(avg_delay, 1),
                    median_delay_hours=round(med_delay, 1),
                    intervention_response_rate=round(inv_rate, 2),
                    blocker_frequency=round(blocker_freq, 2),
                    insights=insights,
                )
            )

        metrics.sort(key=lambda m: m.total_obligations, reverse=True)
        return metrics

    @classmethod
    async def get_historical_patterns(cls, session: AsyncSession) -> HistoricalPatternsResponse:
        """
        Aggregates global historical outcome patterns across all obligations.
        """
        stmt = select(ObligationOutcomeSnapshot).order_by(ObligationOutcomeSnapshot.created_at.desc())
        res = await session.execute(stmt)
        snapshots = res.scalars().all()

        total = len(snapshots)
        if total == 0:
            return HistoricalPatternsResponse(
                total_historical_snapshots=0,
                completion_rate=1.0,
                on_time_completion_rate=1.0,
                avg_delay_hours=0.0,
                median_delay_hours=0.0,
                dependency_bottleneck_rate=0.0,
                intervention_success_rate=1.0,
                frequent_blockers=[],
                delay_distribution={"ON_TIME": 0, "UNDER_12_HOURS": 0, "12_TO_48_HOURS": 0, "OVER_48_HOURS": 0},
                owner_metrics=[],
            )

        completed = sum(1 for s in snapshots if s.status == "COMPLETED")
        on_time = sum(1 for s in snapshots if s.outcome_type in [
            "COMPLETED_ON_TIME", "COMPLETED_AFTER_INTERVENTION", "COMPLETED_AFTER_DEPENDENCY_RESOLUTION"
        ])
        delays = [s.delay_hours for s in snapshots if s.delay_hours > 0]
        avg_delay = float(sum(delays) / len(delays)) if delays else 0.0
        med_delay = float(statistics.median(delays)) if delays else 0.0

        blocked_count = sum(1 for s in snapshots if s.blocker_count > 0 or s.outcome_type == "BLOCKED")
        bottleneck_rate = blocked_count / total if total > 0 else 0.0

        inv_req = sum(1 for s in snapshots if s.intervention_required or s.intervention_count > 0)
        inv_succ = sum(1 for s in snapshots if s.intervention_successful)
        inv_rate = (inv_succ / inv_req) if inv_req > 0 else 1.0

        # Delay distribution
        delay_dist = {
            "ON_TIME": sum(1 for s in snapshots if s.delay_hours <= 0),
            "UNDER_12_HOURS": sum(1 for s in snapshots if 0 < s.delay_hours <= 12),
            "12_TO_48_HOURS": sum(1 for s in snapshots if 12 < s.delay_hours <= 48),
            "OVER_48_HOURS": sum(1 for s in snapshots if s.delay_hours > 48),
        }

        owner_metrics = await cls.get_owner_metrics(session)

        return HistoricalPatternsResponse(
            total_historical_snapshots=total,
            completion_rate=round(completed / total, 2) if total > 0 else 1.0,
            on_time_completion_rate=round(on_time / completed, 2) if completed > 0 else 1.0,
            avg_delay_hours=round(avg_delay, 1),
            median_delay_hours=round(med_delay, 1),
            dependency_bottleneck_rate=round(bottleneck_rate, 2),
            intervention_success_rate=round(inv_rate, 2),
            frequent_blockers=[],
            delay_distribution=delay_dist,
            owner_metrics=owner_metrics,
        )
