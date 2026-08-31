import uuid
import traceback
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any, List, Tuple
from sqlalchemy import select, and_, or_, func, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import logger
from app.models.auth import User
from app.models.monitoring import (
    MonitoringWatch,
    MonitoringEvent,
    EscalationCandidate,
    MonitoringRun,
)
from app.core.status_machine import (
    WatchType,
    WatchStatus,
    MonitoringEventType,
    MonitoringSeverity,
    EscalationStatus,
    MonitoringRunStatus,
    TargetType,
)
from app.schemas.monitoring import (
    MonitoringWatchCreate,
    MonitoringWatchUpdate,
    MonitoringSummaryResponse,
    MonitoringEventResponse,
    EscalationCandidateResponse,
)
from app.services.monitoring.monitoring_engine import MonitoringEngine
from app.services.monitoring.escalation_policy_engine import EscalationPolicyEngine


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class MonitoringService:
    """
    High-level service managing Continuous Monitoring Watches, Evaluation Cycles,
    Escalation Lifecycles, and Health Summary Metrics.
    """

    # =========================================================================
    # 1. Watch Management (CRUD)
    # =========================================================================

    @classmethod
    async def create_watch(
        cls,
        session: AsyncSession,
        workspace_id: str,
        data: MonitoringWatchCreate,
        user: Optional[User] = None,
    ) -> MonitoringWatch:
        now = utc_now()
        watch = MonitoringWatch(
            id=str(uuid.uuid4()),
            workspace_id=workspace_id,
            watch_type=data.watch_type,
            target_type=data.target_type,
            target_id=data.target_id,
            status=WatchStatus.ACTIVE,
            configuration=data.configuration or {},
            next_evaluation_at=data.next_evaluation_at or now,
            last_observed_state={},
            trigger_count=0,
            created_by=user.display_name if user else "System",
            created_at=now,
            updated_at=now,
        )
        session.add(watch)
        await session.flush()
        return watch

    @classmethod
    async def get_watch(
        cls,
        session: AsyncSession,
        watch_id: str,
        workspace_id: str,
    ) -> Optional[MonitoringWatch]:
        stmt = select(MonitoringWatch).where(
            and_(
                MonitoringWatch.id == watch_id,
                MonitoringWatch.workspace_id == workspace_id,
            )
        )
        return (await session.execute(stmt)).scalars().first()

    @classmethod
    async def list_watches(
        cls,
        session: AsyncSession,
        workspace_id: str,
        status: Optional[WatchStatus] = None,
        watch_type: Optional[WatchType] = None,
        target_id: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> Tuple[List[MonitoringWatch], int]:
        filters = [MonitoringWatch.workspace_id == workspace_id]
        if status:
            filters.append(MonitoringWatch.status == status)
        if watch_type:
            filters.append(MonitoringWatch.watch_type == watch_type)
        if target_id:
            filters.append(MonitoringWatch.target_id == target_id)

        count_stmt = select(func.count(MonitoringWatch.id)).where(and_(*filters))
        total = (await session.execute(count_stmt)).scalar() or 0

        query_stmt = (
            select(MonitoringWatch)
            .where(and_(*filters))
            .order_by(desc(MonitoringWatch.created_at))
            .limit(limit)
            .offset(offset)
        )
        items = (await session.execute(query_stmt)).scalars().all()
        return list(items), total

    @classmethod
    async def pause_watch(
        cls,
        session: AsyncSession,
        watch_id: str,
        workspace_id: str,
    ) -> MonitoringWatch:
        watch = await cls.get_watch(session, watch_id, workspace_id)
        if not watch:
            raise ValueError(f"Watch {watch_id} not found.")
        watch.status = WatchStatus.PAUSED
        watch.updated_at = utc_now()
        await session.flush()
        return watch

    @classmethod
    async def resume_watch(
        cls,
        session: AsyncSession,
        watch_id: str,
        workspace_id: str,
    ) -> MonitoringWatch:
        watch = await cls.get_watch(session, watch_id, workspace_id)
        if not watch:
            raise ValueError(f"Watch {watch_id} not found.")
        watch.status = WatchStatus.ACTIVE
        watch.updated_at = utc_now()
        await session.flush()
        return watch

    @classmethod
    async def delete_watch(
        cls,
        session: AsyncSession,
        watch_id: str,
        workspace_id: str,
    ) -> bool:
        watch = await cls.get_watch(session, watch_id, workspace_id)
        if not watch:
            return False
        await session.delete(watch)
        await session.flush()
        return True

    # =========================================================================
    # 2. Monitoring Cycle Execution
    # =========================================================================

    @classmethod
    async def run_monitoring_cycle(
        cls,
        session: AsyncSession,
        workspace_id: str,
        watch_ids: Optional[List[str]] = None,
        force_all: bool = False,
    ) -> MonitoringRun:
        """
        Executes a controlled, non-autonomous monitoring evaluation cycle across due watches.
        Catches and isolates individual watch failures.
        """
        now = utc_now()

        run = MonitoringRun(
            id=str(uuid.uuid4()),
            workspace_id=workspace_id,
            started_at=now,
            watches_evaluated=0,
            events_created=0,
            escalations_created=0,
            errors=[],
            status=MonitoringRunStatus.RUNNING,
        )
        session.add(run)
        await session.flush()

        # Query due watches
        query_filters = [
            MonitoringWatch.workspace_id == workspace_id,
            MonitoringWatch.status == WatchStatus.ACTIVE,
        ]

        if watch_ids:
            query_filters.append(MonitoringWatch.id.in_(watch_ids))
        elif not force_all:
            # Only evaluate watches that are due
            query_filters.append(
                or_(
                    MonitoringWatch.next_evaluation_at.is_(None),
                    MonitoringWatch.next_evaluation_at <= now,
                )
            )

        watches_stmt = select(MonitoringWatch).where(and_(*query_filters))
        watches = (await session.execute(watches_stmt)).scalars().all()

        evaluated_count = 0
        events_count = 0
        escalations_count = 0
        errors: List[Dict[str, Any]] = []

        for watch in watches:
            try:
                # Evaluate watch inside isolated block
                async with session.begin_nested():
                    new_events = await MonitoringEngine.evaluate_watch(session, watch)
                    for ev in new_events:
                        session.add(ev)
                        await session.flush()
                        events_count += 1

                        # Evaluate escalation candidate
                        escalation = await EscalationPolicyEngine.evaluate_event(
                            session=session,
                            event=ev,
                            workspace_id=workspace_id,
                        )
                        if escalation:
                            escalations_count += 1

                    # Update watch evaluation timestamps
                    watch.last_evaluated_at = now
                    watch.next_evaluation_at = now + timedelta(minutes=15)
                    watch.updated_at = now

                evaluated_count += 1

            except Exception as ex:
                logger.error(f"Error evaluating watch {watch.id}: {ex}\n{traceback.format_exc()}")
                errors.append({
                    "watch_id": watch.id,
                    "watch_type": watch.watch_type.value,
                    "target_id": watch.target_id,
                    "error": str(ex),
                })

        # Finalize run
        run.completed_at = utc_now()
        run.watches_evaluated = evaluated_count
        run.events_created = events_count
        run.escalations_created = escalations_count
        run.errors = errors
        run.status = (
            MonitoringRunStatus.COMPLETED
            if not errors
            else MonitoringRunStatus.PARTIAL
            if evaluated_count > 0
            else MonitoringRunStatus.FAILED
        )

        await session.flush()
        return run

    # =========================================================================
    # 3. Events & Escalations Query & Lifecycle
    # =========================================================================

    @classmethod
    async def list_events(
        cls,
        session: AsyncSession,
        workspace_id: str,
        severity: Optional[MonitoringSeverity] = None,
        target_id: Optional[str] = None,
        event_type: Optional[MonitoringEventType] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> Tuple[List[MonitoringEvent], int]:
        filters = [MonitoringEvent.workspace_id == workspace_id]
        if severity:
            filters.append(MonitoringEvent.severity == severity)
        if target_id:
            filters.append(MonitoringEvent.target_id == target_id)
        if event_type:
            filters.append(MonitoringEvent.event_type == event_type)

        count_stmt = select(func.count(MonitoringEvent.id)).where(and_(*filters))
        total = (await session.execute(count_stmt)).scalar() or 0

        query_stmt = (
            select(MonitoringEvent)
            .where(and_(*filters))
            .order_by(desc(MonitoringEvent.detected_at))
            .limit(limit)
            .offset(offset)
        )
        items = (await session.execute(query_stmt)).scalars().all()
        return list(items), total

    @classmethod
    async def get_event(
        cls,
        session: AsyncSession,
        event_id: str,
        workspace_id: str,
    ) -> Optional[MonitoringEvent]:
        stmt = select(MonitoringEvent).where(
            and_(
                MonitoringEvent.id == event_id,
                MonitoringEvent.workspace_id == workspace_id,
            )
        )
        return (await session.execute(stmt)).scalars().first()

    @classmethod
    async def list_escalations(
        cls,
        session: AsyncSession,
        workspace_id: str,
        status: Optional[EscalationStatus] = None,
        severity: Optional[MonitoringSeverity] = None,
        target_id: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> Tuple[List[EscalationCandidate], int]:
        filters = [EscalationCandidate.workspace_id == workspace_id]
        if status:
            filters.append(EscalationCandidate.status == status)
        if severity:
            filters.append(EscalationCandidate.severity == severity)
        if target_id:
            filters.append(EscalationCandidate.target_id == target_id)

        count_stmt = select(func.count(EscalationCandidate.id)).where(and_(*filters))
        total = (await session.execute(count_stmt)).scalar() or 0

        query_stmt = (
            select(EscalationCandidate)
            .where(and_(*filters))
            .order_by(desc(EscalationCandidate.created_at))
            .limit(limit)
            .offset(offset)
        )
        items = (await session.execute(query_stmt)).scalars().all()
        return list(items), total

    @classmethod
    async def get_escalation(
        cls,
        session: AsyncSession,
        escalation_id: str,
        workspace_id: str,
    ) -> Optional[EscalationCandidate]:
        stmt = select(EscalationCandidate).where(
            and_(
                EscalationCandidate.id == escalation_id,
                EscalationCandidate.workspace_id == workspace_id,
            )
        )
        return (await session.execute(stmt)).scalars().first()

    @classmethod
    async def acknowledge_escalation(
        cls,
        session: AsyncSession,
        escalation_id: str,
        workspace_id: str,
        user: Optional[User] = None,
        notes: Optional[str] = None,
    ) -> EscalationCandidate:
        esc = await cls.get_escalation(session, escalation_id, workspace_id)
        if not esc:
            raise ValueError(f"Escalation {escalation_id} not found.")
        esc.status = EscalationStatus.ACKNOWLEDGED
        esc.acknowledged_at = utc_now()
        esc.acknowledged_by = user.display_name if user else "Operator"
        await session.flush()
        return esc

    @classmethod
    async def resolve_escalation(
        cls,
        session: AsyncSession,
        escalation_id: str,
        workspace_id: str,
        user: Optional[User] = None,
        resolution_reason: Optional[str] = None,
    ) -> EscalationCandidate:
        esc = await cls.get_escalation(session, escalation_id, workspace_id)
        if not esc:
            raise ValueError(f"Escalation {escalation_id} not found.")
        esc.status = EscalationStatus.RESOLVED
        esc.resolved_at = utc_now()
        await session.flush()
        return esc

    @classmethod
    async def dismiss_escalation(
        cls,
        session: AsyncSession,
        escalation_id: str,
        workspace_id: str,
        user: Optional[User] = None,
        reason: Optional[str] = None,
    ) -> EscalationCandidate:
        esc = await cls.get_escalation(session, escalation_id, workspace_id)
        if not esc:
            raise ValueError(f"Escalation {escalation_id} not found.")
        esc.status = EscalationStatus.DISMISSED
        esc.resolved_at = utc_now()
        await session.flush()
        return esc

    # =========================================================================
    # 4. Monitoring Summary & Health Aggregator
    # =========================================================================

    @classmethod
    async def get_monitoring_summary(
        cls,
        session: AsyncSession,
        workspace_id: str,
    ) -> MonitoringSummaryResponse:
        # Active watches count
        watches_count = (
            await session.execute(
                select(func.count(MonitoringWatch.id)).where(
                    and_(
                        MonitoringWatch.workspace_id == workspace_id,
                        MonitoringWatch.status == WatchStatus.ACTIVE,
                    )
                )
            )
        ).scalar() or 0

        # Critical / High events count (last 24h)
        since_24h = utc_now() - timedelta(hours=24)

        crit_count = (
            await session.execute(
                select(func.count(MonitoringEvent.id)).where(
                    and_(
                        MonitoringEvent.workspace_id == workspace_id,
                        MonitoringEvent.severity == MonitoringSeverity.CRITICAL,
                        MonitoringEvent.detected_at >= since_24h,
                    )
                )
            )
        ).scalar() or 0

        high_count = (
            await session.execute(
                select(func.count(MonitoringEvent.id)).where(
                    and_(
                        MonitoringEvent.workspace_id == workspace_id,
                        MonitoringEvent.severity == MonitoringSeverity.HIGH,
                        MonitoringEvent.detected_at >= since_24h,
                    )
                )
            )
        ).scalar() or 0

        open_esc_count = (
            await session.execute(
                select(func.count(EscalationCandidate.id)).where(
                    and_(
                        EscalationCandidate.workspace_id == workspace_id,
                        EscalationCandidate.status == EscalationStatus.OPEN,
                    )
                )
            )
        ).scalar() or 0

        deadline_breaches = (
            await session.execute(
                select(func.count(MonitoringEvent.id)).where(
                    and_(
                        MonitoringEvent.workspace_id == workspace_id,
                        MonitoringEvent.event_type == MonitoringEventType.DEADLINE_BREACHED,
                        MonitoringEvent.detected_at >= since_24h,
                    )
                )
            )
        ).scalar() or 0

        risk_escalations = (
            await session.execute(
                select(func.count(MonitoringEvent.id)).where(
                    and_(
                        MonitoringEvent.workspace_id == workspace_id,
                        MonitoringEvent.event_type == MonitoringEventType.RISK_ESCALATED,
                        MonitoringEvent.detected_at >= since_24h,
                    )
                )
            )
        ).scalar() or 0

        exec_failures = (
            await session.execute(
                select(func.count(MonitoringEvent.id)).where(
                    and_(
                        MonitoringEvent.workspace_id == workspace_id,
                        MonitoringEvent.event_type == MonitoringEventType.EXECUTION_FAILED,
                        MonitoringEvent.detected_at >= since_24h,
                    )
                )
            )
        ).scalar() or 0

        resp_timeouts = (
            await session.execute(
                select(func.count(MonitoringEvent.id)).where(
                    and_(
                        MonitoringEvent.workspace_id == workspace_id,
                        MonitoringEvent.event_type == MonitoringEventType.EXECUTION_RESPONSE_TIMEOUT,
                        MonitoringEvent.detected_at >= since_24h,
                    )
                )
            )
        ).scalar() or 0

        dep_blocks = (
            await session.execute(
                select(func.count(MonitoringEvent.id)).where(
                    and_(
                        MonitoringEvent.workspace_id == workspace_id,
                        MonitoringEvent.event_type == MonitoringEventType.DEPENDENCY_BLOCKED,
                        MonitoringEvent.detected_at >= since_24h,
                    )
                )
            )
        ).scalar() or 0

        stale_plans = (
            await session.execute(
                select(func.count(MonitoringEvent.id)).where(
                    and_(
                        MonitoringEvent.workspace_id == workspace_id,
                        MonitoringEvent.event_type == MonitoringEventType.DECISION_PLAN_STALE,
                        MonitoringEvent.detected_at >= since_24h,
                    )
                )
            )
        ).scalar() or 0

        # Recent events (last 10)
        recent_events_stmt = (
            select(MonitoringEvent)
            .where(MonitoringEvent.workspace_id == workspace_id)
            .order_by(desc(MonitoringEvent.detected_at))
            .limit(10)
        )
        recent_events = (await session.execute(recent_events_stmt)).scalars().all()

        # Open escalations (last 10)
        open_esc_stmt = (
            select(EscalationCandidate)
            .where(
                and_(
                    EscalationCandidate.workspace_id == workspace_id,
                    EscalationCandidate.status == EscalationStatus.OPEN,
                )
            )
            .order_by(desc(EscalationCandidate.created_at))
            .limit(10)
        )
        open_escalations = (await session.execute(open_esc_stmt)).scalars().all()

        return MonitoringSummaryResponse(
            active_watches_count=watches_count,
            critical_events_count=crit_count,
            high_events_count=high_count,
            open_escalations_count=open_esc_count,
            deadline_breaches_count=deadline_breaches,
            risk_escalations_count=risk_escalations,
            execution_failures_count=exec_failures,
            response_timeouts_count=resp_timeouts,
            dependency_blocks_count=dep_blocks,
            stale_decision_plans_count=stale_plans,
            recent_events=[MonitoringEventResponse.model_validate(e) for e in recent_events],
            open_escalations=[EscalationCandidateResponse.model_validate(e) for e in open_escalations],
        )

    @classmethod
    async def list_runs(
        cls,
        session: AsyncSession,
        workspace_id: str,
        limit: int = 20,
        offset: int = 0,
    ) -> Tuple[List[MonitoringRun], int]:
        filters = [MonitoringRun.workspace_id == workspace_id]
        count_stmt = select(func.count(MonitoringRun.id)).where(and_(*filters))
        total = (await session.execute(count_stmt)).scalar() or 0

        query_stmt = (
            select(MonitoringRun)
            .where(and_(*filters))
            .order_by(desc(MonitoringRun.started_at))
            .limit(limit)
            .offset(offset)
        )
        items = (await session.execute(query_stmt)).scalars().all()
        return list(items), total

    @classmethod
    async def get_run(
        cls,
        session: AsyncSession,
        run_id: str,
        workspace_id: str,
    ) -> Optional[MonitoringRun]:
        stmt = select(MonitoringRun).where(
            and_(
                MonitoringRun.id == run_id,
                MonitoringRun.workspace_id == workspace_id,
            )
        )
        return (await session.execute(stmt)).scalars().first()
