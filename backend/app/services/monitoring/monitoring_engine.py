import hashlib
import json
import uuid
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any, List, Tuple
from sqlalchemy import select, and_, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import logger
from app.models.obligation import Obligation, ObligationEdge, Evidence
from app.models.execution import ExecutionRecord
from app.models.decision import DecisionPlan
from app.models.monitoring import MonitoringWatch, MonitoringEvent
from app.core.status_machine import (
    ObligationStatus,
    WatchType,
    WatchStatus,
    MonitoringEventType,
    MonitoringSeverity,
    TargetType,
    ExecutionStatus,
    DecisionPlanStatus,
    RiskLevel,
)
from app.services.risk_engine import RiskEngine
from app.services.graph_service import GraphService


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def compute_event_dedup_key(
    workspace_id: str,
    target_type: str,
    target_id: str,
    event_type: str,
    signature: str,
) -> str:
    raw = f"{workspace_id}:{target_type}:{target_id}:{event_type}:{signature}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:32]


class MonitoringEngine:
    """
    Continuous state-diff and monitoring evaluation engine.
    Periodically evaluates target obligations, executions, dependencies, deadlines, and decision plans.
    Strictly observational: NEVER triggers autonomous actions.
    """

    # Deadline thresholds
    DEADLINE_BREACHED = "BREACHED"
    DEADLINE_CRITICAL = "CRITICAL_12H"
    DEADLINE_URGENT = "URGENT_24H"
    DEADLINE_APPROACHING = "APPROACHING_48H"
    DEADLINE_NORMAL = "NORMAL"

    @classmethod
    async def evaluate_watch(
        cls,
        session: AsyncSession,
        watch: MonitoringWatch,
        ignore_cooldown: bool = False,
    ) -> List[MonitoringEvent]:
        """
        Evaluates a specific MonitoringWatch and returns any newly detected MonitoringEvents.
        """
        if watch.status != WatchStatus.ACTIVE:
            return []

        # Check cooldown if set
        now = utc_now()
        if not ignore_cooldown and watch.cooldown_until and now < watch.cooldown_until:
            return []

        events: List[MonitoringEvent] = []

        if watch.watch_type == WatchType.DEADLINE:
            events.extend(await cls._evaluate_deadline(session, watch))
        elif watch.watch_type == WatchType.RISK:
            events.extend(await cls._evaluate_risk(session, watch))
        elif watch.watch_type == WatchType.DEPENDENCY:
            events.extend(await cls._evaluate_dependency(session, watch))
        elif watch.watch_type == WatchType.EXECUTION:
            events.extend(await cls._evaluate_execution(session, watch))
        elif watch.watch_type == WatchType.RESPONSE:
            events.extend(await cls._evaluate_response(session, watch))
        elif watch.watch_type == WatchType.EVIDENCE:
            events.extend(await cls._evaluate_evidence(session, watch))
        elif watch.watch_type == WatchType.DECISION_PLAN:
            events.extend(await cls._evaluate_decision_plan(session, watch))
        elif watch.watch_type == WatchType.CRITICAL_PATH:
            events.extend(await cls._evaluate_critical_path(session, watch))
        elif watch.watch_type == WatchType.BOTTLENECK:
            events.extend(await cls._evaluate_bottlenecks(session, watch))
        else:
            # Fallback evaluation
            events.extend(await cls._evaluate_generic(session, watch))

        # Update watch metrics if events generated
        if events:
            watch.last_triggered_at = now
            watch.trigger_count = (watch.trigger_count or 0) + len(events)
            # Set default 1-hour watch cooldown to prevent thrashing
            watch.cooldown_until = now + timedelta(hours=1)

        return events

    # =========================================================================
    # 1. Deadline Monitoring
    # =========================================================================
    @classmethod
    async def _evaluate_deadline(
        cls,
        session: AsyncSession,
        watch: MonitoringWatch,
    ) -> List[MonitoringEvent]:
        events: List[MonitoringEvent] = []
        now = utc_now()

        ob = await session.get(Obligation, watch.target_id)
        if not ob:
            return events

        # Invariant: Completed or dismissed obligations don't trigger deadline alarms
        if ob.status in (ObligationStatus.COMPLETED, ObligationStatus.CANCELLED):
            return events

        # Invariant I & J: Unknown or conditional deadlines without fixed timestamp never fabricate deadline alarms
        if not ob.deadline:
            # Check if watch recorded an unknown state previously
            prev_category = watch.last_observed_state.get("deadline_category", "NONE")
            watch.last_observed_state = {
                "deadline_category": "NONE",
                "deadline": None,
                "evaluated_at": now.isoformat(),
            }
            return events

        time_left = ob.deadline - now
        hours_left = time_left.total_seconds() / 3600.0

        if hours_left < 0:
            current_category = cls.DEADLINE_BREACHED
        elif hours_left < 12:
            current_category = cls.DEADLINE_CRITICAL
        elif hours_left < 24:
            current_category = cls.DEADLINE_URGENT
        elif hours_left < 48:
            current_category = cls.DEADLINE_APPROACHING
        else:
            current_category = cls.DEADLINE_NORMAL

        prev_category = watch.last_observed_state.get("deadline_category", cls.DEADLINE_NORMAL)

        # State-diff check: Trigger only on state change or breach
        if current_category != prev_category and current_category != cls.DEADLINE_NORMAL:
            event_type = (
                MonitoringEventType.DEADLINE_BREACHED
                if current_category == cls.DEADLINE_BREACHED
                else MonitoringEventType.DEADLINE_APPROACHING
            )

            severity = (
                MonitoringSeverity.CRITICAL
                if current_category in (cls.DEADLINE_BREACHED, cls.DEADLINE_CRITICAL)
                else MonitoringSeverity.HIGH
                if current_category == cls.DEADLINE_URGENT
                else MonitoringSeverity.WARNING
            )

            explanation = (
                f"Obligation deadline breached by {abs(hours_left):.1f} hours (Target was {ob.deadline.isoformat()})."
                if current_category == cls.DEADLINE_BREACHED
                else f"Obligation deadline is approaching in {hours_left:.1f} hours ({current_category})."
            )

            dedup_key = compute_event_dedup_key(
                watch.workspace_id,
                TargetType.OBLIGATION.value,
                ob.id,
                event_type.value,
                f"{current_category}:{ob.deadline.isoformat()}",
            )

            event = MonitoringEvent(
                id=str(uuid.uuid4()),
                workspace_id=watch.workspace_id,
                watch_id=watch.id,
                event_type=event_type,
                severity=severity,
                target_type=TargetType.OBLIGATION,
                target_id=ob.id,
                previous_state={"deadline_category": prev_category, "hours_left": watch.last_observed_state.get("hours_left")},
                current_state={"deadline_category": current_category, "hours_left": hours_left, "deadline": ob.deadline.isoformat()},
                detected_at=now,
                explanation=explanation,
                signals={"hours_left": hours_left, "deadline": ob.deadline.isoformat(), "owner": ob.owner},
                provenance={"source_service": "MonitoringEngine._evaluate_deadline", "authoritative_model": "Obligation.deadline"},
                deduplication_key=dedup_key,
            )
            events.append(event)

        # Update last observed state
        watch.last_observed_state = {
            "deadline_category": current_category,
            "hours_left": hours_left,
            "deadline": ob.deadline.isoformat(),
            "evaluated_at": now.isoformat(),
        }
        return events

    # =========================================================================
    # 2. Risk Monitoring
    # =========================================================================
    @classmethod
    async def _evaluate_risk(
        cls,
        session: AsyncSession,
        watch: MonitoringWatch,
    ) -> List[MonitoringEvent]:
        events: List[MonitoringEvent] = []
        now = utc_now()

        ob = await session.get(Obligation, watch.target_id)
        if not ob or ob.status in (ObligationStatus.COMPLETED, ObligationStatus.CANCELLED):
            return events

        # Invoke authoritative RiskEngine
        risk_assessment = await RiskEngine.assess_obligation(session, ob.id, watch.workspace_id)
        if not risk_assessment:
            return events

        current_score = risk_assessment.risk_score
        current_level = risk_assessment.risk_level.value

        prev_score = watch.last_observed_state.get("risk_score", 0.0)
        prev_level = watch.last_observed_state.get("risk_level", RiskLevel.LOW.value)

        delta = current_score - prev_score
        level_changed = current_level != prev_level
        material_shift = abs(delta) >= 0.15

        if level_changed or material_shift:
            if delta > 0 or (level_changed and current_score > prev_score):
                event_type = MonitoringEventType.RISK_ESCALATED
                severity = (
                    MonitoringSeverity.CRITICAL
                    if current_level == RiskLevel.CRITICAL.value
                    else MonitoringSeverity.HIGH
                    if current_level == RiskLevel.HIGH.value
                    else MonitoringSeverity.WARNING
                )
                explanation = f"Obligation risk escalated from {prev_level} ({prev_score:.2f}) to {current_level} ({current_score:.2f}). Δ={delta:+.2f}."
            else:
                event_type = MonitoringEventType.RISK_DEESCALATED
                severity = MonitoringSeverity.INFO
                explanation = f"Obligation risk de-escalated from {prev_level} ({prev_score:.2f}) to {current_level} ({current_score:.2f}). Δ={delta:+.2f}."

            dedup_key = compute_event_dedup_key(
                watch.workspace_id,
                TargetType.OBLIGATION.value,
                ob.id,
                event_type.value,
                f"{current_level}:{round(current_score, 1)}",
            )

            event = MonitoringEvent(
                id=str(uuid.uuid4()),
                workspace_id=watch.workspace_id,
                watch_id=watch.id,
                event_type=event_type,
                severity=severity,
                target_type=TargetType.OBLIGATION,
                target_id=ob.id,
                previous_state={"risk_score": prev_score, "risk_level": prev_level},
                current_state={"risk_score": current_score, "risk_level": current_level},
                detected_at=now,
                explanation=explanation,
                signals={"risk_score": current_score, "delta": delta, "breakdown": risk_assessment.breakdown.model_dump() if risk_assessment.breakdown else {}},
                provenance={"source_service": "RiskEngine.assess_obligation", "authoritative_model": "RiskAssessmentResponse"},
                deduplication_key=dedup_key,
            )
            events.append(event)

        watch.last_observed_state = {
            "risk_score": current_score,
            "risk_level": current_level,
            "evaluated_at": now.isoformat(),
        }
        return events

    # =========================================================================
    # 3. Dependency & Critical Path Monitoring
    # =========================================================================
    @classmethod
    async def _evaluate_dependency(
        cls,
        session: AsyncSession,
        watch: MonitoringWatch,
    ) -> List[MonitoringEvent]:
        events: List[MonitoringEvent] = []
        now = utc_now()

        ob = await session.get(Obligation, watch.target_id)
        if not ob:
            return events

        # Query incoming blockers via GraphService
        active_blockers = await GraphService.get_blockers(session, ob.id)

        current_blocked_count = len(active_blockers)
        prev_blocked_count = watch.last_observed_state.get("blocked_count", 0)
        current_status = ob.status.value
        prev_status = watch.last_observed_state.get("status", current_status)

        if current_blocked_count > 0 and (prev_blocked_count == 0 or current_status == ObligationStatus.BLOCKED.value and prev_status != ObligationStatus.BLOCKED.value):
            event_type = MonitoringEventType.DEPENDENCY_BLOCKED
            severity = MonitoringSeverity.HIGH
            explanation = f"Obligation has {current_blocked_count} active blocker dependencies unresolved."

            dedup_key = compute_event_dedup_key(
                watch.workspace_id,
                TargetType.OBLIGATION.value,
                ob.id,
                event_type.value,
                f"blockers:{current_blocked_count}",
            )

            event = MonitoringEvent(
                id=str(uuid.uuid4()),
                workspace_id=watch.workspace_id,
                watch_id=watch.id,
                event_type=event_type,
                severity=severity,
                target_type=TargetType.OBLIGATION,
                target_id=ob.id,
                previous_state={"blocked_count": prev_blocked_count, "status": prev_status},
                current_state={"blocked_count": current_blocked_count, "status": current_status},
                detected_at=now,
                explanation=explanation,
                signals={"blocker_ids": [b.obligation_id for b in active_blockers]},
                provenance={"source_service": "GraphService.get_obligation_graph", "authoritative_model": "ObligationEdge"},
                deduplication_key=dedup_key,
            )
            events.append(event)
        elif current_blocked_count == 0 and prev_blocked_count > 0:
            event_type = MonitoringEventType.DEPENDENCY_RESOLVED
            severity = MonitoringSeverity.INFO
            explanation = f"All upstream dependencies resolved for obligation."

            dedup_key = compute_event_dedup_key(
                watch.workspace_id,
                TargetType.OBLIGATION.value,
                ob.id,
                event_type.value,
                "all_resolved",
            )

            event = MonitoringEvent(
                id=str(uuid.uuid4()),
                workspace_id=watch.workspace_id,
                watch_id=watch.id,
                event_type=event_type,
                severity=severity,
                target_type=TargetType.OBLIGATION,
                target_id=ob.id,
                previous_state={"blocked_count": prev_blocked_count, "status": prev_status},
                current_state={"blocked_count": current_blocked_count, "status": current_status},
                detected_at=now,
                explanation=explanation,
                signals={"cleared": True},
                provenance={"source_service": "GraphService.get_obligation_graph", "authoritative_model": "ObligationEdge"},
                deduplication_key=dedup_key,
            )
            events.append(event)

        watch.last_observed_state = {
            "blocked_count": current_blocked_count,
            "status": current_status,
            "evaluated_at": now.isoformat(),
        }
        return events

    # =========================================================================
    # 4. Execution Monitoring
    # =========================================================================
    @classmethod
    async def _evaluate_execution(
        cls,
        session: AsyncSession,
        watch: MonitoringWatch,
    ) -> List[MonitoringEvent]:
        events: List[MonitoringEvent] = []
        now = utc_now()

        # Query executions for target (either target_id is execution_id or obligation_id)
        if watch.target_type == TargetType.EXECUTION:
            exec_stmt = select(ExecutionRecord).where(ExecutionRecord.id == watch.target_id)
        else:
            exec_stmt = (
                select(ExecutionRecord)
                .where(ExecutionRecord.obligation_id == watch.target_id)
                .order_by(desc(ExecutionRecord.created_at))
                .limit(1)
            )

        exec_res = (await session.execute(exec_stmt)).scalars().first()
        if not exec_res:
            return events

        current_status = exec_res.status.value
        prev_status = watch.last_observed_state.get("status", current_status)

        # Check execution failure
        if exec_res.status == ExecutionStatus.FAILED and prev_status != ExecutionStatus.FAILED.value:
            event_type = MonitoringEventType.EXECUTION_FAILED
            severity = (
                MonitoringSeverity.CRITICAL
                if exec_res.retry_count >= exec_res.max_retries
                else MonitoringSeverity.HIGH
            )
            explanation = f"Execution {exec_res.id} failed ({exec_res.failure_code}): {exec_res.failure_reason}"

            dedup_key = compute_event_dedup_key(
                watch.workspace_id,
                TargetType.EXECUTION.value,
                exec_res.id,
                event_type.value,
                f"failed:{exec_res.failure_code}:{exec_res.retry_count}",
            )

            event = MonitoringEvent(
                id=str(uuid.uuid4()),
                workspace_id=watch.workspace_id,
                watch_id=watch.id,
                event_type=event_type,
                severity=severity,
                target_type=TargetType.EXECUTION,
                target_id=exec_res.id,
                previous_state={"status": prev_status},
                current_state={"status": current_status, "retry_count": exec_res.retry_count, "failure_code": exec_res.failure_code},
                detected_at=now,
                explanation=explanation,
                signals={"provider": exec_res.provider, "retry_count": exec_res.retry_count, "max_retries": exec_res.max_retries},
                provenance={"source_service": "ExecutionService", "authoritative_model": "ExecutionRecord"},
                deduplication_key=dedup_key,
            )
            events.append(event)

        # Check response timeout (> 24 hours in RESPONSE_PENDING)
        timeout_hours = watch.configuration.get("response_timeout_hours", 24)
        if exec_res.status == ExecutionStatus.RESPONSE_PENDING and exec_res.executed_at:
            elapsed_hours = (now - exec_res.executed_at).total_seconds() / 3600.0
            prev_timed_out = watch.last_observed_state.get("timed_out", False)

            if elapsed_hours >= timeout_hours and not prev_timed_out:
                event_type = MonitoringEventType.EXECUTION_RESPONSE_TIMEOUT
                severity = MonitoringSeverity.HIGH
                explanation = f"Execution {exec_res.id} reached response timeout ({elapsed_hours:.1f}h elapsed >= {timeout_hours}h limit)."

                dedup_key = compute_event_dedup_key(
                    watch.workspace_id,
                    TargetType.EXECUTION.value,
                    exec_res.id,
                    event_type.value,
                    f"timeout:{timeout_hours}h",
                )

                event = MonitoringEvent(
                    id=str(uuid.uuid4()),
                    workspace_id=watch.workspace_id,
                    watch_id=watch.id,
                    event_type=event_type,
                    severity=severity,
                    target_type=TargetType.EXECUTION,
                    target_id=exec_res.id,
                    previous_state={"status": prev_status, "timed_out": False},
                    current_state={"status": current_status, "timed_out": True, "elapsed_hours": elapsed_hours},
                    detected_at=now,
                    explanation=explanation,
                    signals={"elapsed_hours": elapsed_hours, "recipient": exec_res.safe_request_metadata.get("recipient")},
                    provenance={"source_service": "ExecutionService", "authoritative_model": "ExecutionRecord"},
                    deduplication_key=dedup_key,
                )
                events.append(event)

        watch.last_observed_state = {
            "status": current_status,
            "retry_count": exec_res.retry_count,
            "timed_out": (now - exec_res.executed_at).total_seconds() / 3600.0 >= timeout_hours if (exec_res.status == ExecutionStatus.RESPONSE_PENDING and exec_res.executed_at) else False,
            "evaluated_at": now.isoformat(),
        }
        return events

    # =========================================================================
    # 5. Owner Responsiveness Monitoring
    # =========================================================================
    @classmethod
    async def _evaluate_response(
        cls,
        session: AsyncSession,
        watch: MonitoringWatch,
    ) -> List[MonitoringEvent]:
        events: List[MonitoringEvent] = []
        now = utc_now()

        ob = await session.get(Obligation, watch.target_id)
        if not ob or ob.status in (ObligationStatus.COMPLETED, ObligationStatus.CANCELLED):
            return events

        # Query recent executions
        exec_stmt = (
            select(ExecutionRecord)
            .where(ExecutionRecord.obligation_id == ob.id)
            .order_by(desc(ExecutionRecord.created_at))
            .limit(1)
        )
        exec_rec = (await session.execute(exec_stmt)).scalars().first()

        if exec_rec and exec_rec.status == ExecutionStatus.RESPONSE_PENDING and exec_rec.executed_at:
            elapsed_hours = (now - exec_rec.executed_at).total_seconds() / 3600.0
            if elapsed_hours >= 24.0:
                prev_unresponsive = watch.last_observed_state.get("unresponsive", False)
                if not prev_unresponsive:
                    event_type = MonitoringEventType.OWNER_UNRESPONSIVE
                    severity = MonitoringSeverity.WARNING
                    explanation = f"Structural signal: NO_RESPONSE_OBSERVED for {ob.owner} after {elapsed_hours:.1f} hours."

                    dedup_key = compute_event_dedup_key(
                        watch.workspace_id,
                        TargetType.OBLIGATION.value,
                        ob.id,
                        event_type.value,
                        f"unresponsive:{int(elapsed_hours // 24)}d",
                    )

                    event = MonitoringEvent(
                        id=str(uuid.uuid4()),
                        workspace_id=watch.workspace_id,
                        watch_id=watch.id,
                        event_type=event_type,
                        severity=severity,
                        target_type=TargetType.OBLIGATION,
                        target_id=ob.id,
                        previous_state={"unresponsive": False},
                        current_state={"unresponsive": True, "elapsed_hours": elapsed_hours},
                        detected_at=now,
                        explanation=explanation,
                        signals={"owner": ob.owner, "signal_type": "NO_RESPONSE_OBSERVED", "elapsed_hours": elapsed_hours},
                        provenance={"source_service": "MonitoringEngine._evaluate_response", "authoritative_model": "ExecutionRecord"},
                        deduplication_key=dedup_key,
                    )
                    events.append(event)

        watch.last_observed_state = {
            "unresponsive": (now - exec_rec.executed_at).total_seconds() / 3600.0 >= 24.0 if (exec_rec and exec_rec.status == ExecutionStatus.RESPONSE_PENDING and exec_rec.executed_at) else False,
            "evaluated_at": now.isoformat(),
        }
        return events

    # =========================================================================
    # 6. Evidence Monitoring
    # =========================================================================
    @classmethod
    async def _evaluate_evidence(
        cls,
        session: AsyncSession,
        watch: MonitoringWatch,
    ) -> List[MonitoringEvent]:
        events: List[MonitoringEvent] = []
        now = utc_now()

        ob = await session.get(Obligation, watch.target_id)
        if not ob:
            return events

        # Query latest evidence
        ev_stmt = (
            select(Evidence)
            .where(Evidence.obligation_id == ob.id)
            .order_by(desc(Evidence.created_at))
            .limit(1)
        )
        latest_ev = (await session.execute(ev_stmt)).scalars().first()
        if not latest_ev:
            return events

        prev_ev_id = watch.last_observed_state.get("latest_evidence_id")
        if latest_ev.id != prev_ev_id:
            event_type = MonitoringEventType.NEW_COMPLETION_EVIDENCE
            severity = MonitoringSeverity.NOTICE
            explanation = f"New evidence submitted for {ob.action} (Type: {latest_ev.evidence_type.value}). Requires human confirmation."

            dedup_key = compute_event_dedup_key(
                watch.workspace_id,
                TargetType.OBLIGATION.value,
                ob.id,
                event_type.value,
                latest_ev.id,
            )

            event = MonitoringEvent(
                id=str(uuid.uuid4()),
                workspace_id=watch.workspace_id,
                watch_id=watch.id,
                event_type=event_type,
                severity=severity,
                target_type=TargetType.OBLIGATION,
                target_id=ob.id,
                previous_state={"latest_evidence_id": prev_ev_id},
                current_state={"latest_evidence_id": latest_ev.id, "evidence_type": latest_ev.evidence_type.value},
                detected_at=now,
                explanation=explanation,
                signals={"evidence_id": latest_ev.id, "source_type": latest_ev.source_type},
                provenance={"source_service": "EvidenceService", "authoritative_model": "Evidence"},
                deduplication_key=dedup_key,
            )
            events.append(event)

        watch.last_observed_state = {
            "latest_evidence_id": latest_ev.id,
            "evaluated_at": now.isoformat(),
        }
        return events

    # =========================================================================
    # 7. Decision Plan Monitoring
    # =========================================================================
    @classmethod
    async def _evaluate_decision_plan(
        cls,
        session: AsyncSession,
        watch: MonitoringWatch,
    ) -> List[MonitoringEvent]:
        events: List[MonitoringEvent] = []
        now = utc_now()

        from app.services.intelligence.orchestrator import IntelligenceOrchestrator

        plan = await session.get(DecisionPlan, watch.target_id)
        if not plan:
            # If target_id is an obligation, find its active plan
            plan_stmt = (
                select(DecisionPlan)
                .where(DecisionPlan.target_obligation_id == watch.target_id)
                .order_by(desc(DecisionPlan.plan_version))
                .limit(1)
            )
            plan = (await session.execute(plan_stmt)).scalars().first()

        if not plan:
            return events

        ob = await session.get(Obligation, plan.target_obligation_id)
        if not ob:
            return events

        # Check if plan became stale dynamically
        is_stale = await IntelligenceOrchestrator._is_plan_stale(session, plan, ob)
        prev_is_stale = watch.last_observed_state.get("is_stale", False)

        if is_stale and not prev_is_stale and plan.status not in (DecisionPlanStatus.SUPERSEDED, DecisionPlanStatus.RESOLVED):
            event_type = MonitoringEventType.DECISION_PLAN_STALE
            severity = MonitoringSeverity.WARNING
            explanation = f"Decision Plan v{plan.plan_version} (ID: {plan.id}) is STALE due to graph or status changes."

            dedup_key = compute_event_dedup_key(
                watch.workspace_id,
                TargetType.DECISION_PLAN.value,
                plan.id,
                event_type.value,
                f"stale:v{plan.plan_version}",
            )

            event = MonitoringEvent(
                id=str(uuid.uuid4()),
                workspace_id=watch.workspace_id,
                watch_id=watch.id,
                event_type=event_type,
                severity=severity,
                target_type=TargetType.DECISION_PLAN,
                target_id=plan.id,
                previous_state={"is_stale": False, "status": plan.status.value},
                current_state={"is_stale": True, "status": plan.status.value},
                detected_at=now,
                explanation=explanation,
                signals={"target_obligation_id": ob.id, "plan_version": plan.plan_version},
                provenance={"source_service": "IntelligenceOrchestrator", "authoritative_model": "DecisionPlan"},
                deduplication_key=dedup_key,
            )
            events.append(event)

        # Check if obligation resolved
        if ob.status == ObligationStatus.COMPLETED and plan.status != DecisionPlanStatus.RESOLVED:
            event_type = MonitoringEventType.DECISION_PLAN_RESOLVED
            severity = MonitoringSeverity.INFO
            explanation = f"Decision Plan v{plan.plan_version} target obligation resolved."

            dedup_key = compute_event_dedup_key(
                watch.workspace_id,
                TargetType.DECISION_PLAN.value,
                plan.id,
                event_type.value,
                f"resolved:v{plan.plan_version}",
            )

            event = MonitoringEvent(
                id=str(uuid.uuid4()),
                workspace_id=watch.workspace_id,
                watch_id=watch.id,
                event_type=event_type,
                severity=severity,
                target_type=TargetType.DECISION_PLAN,
                target_id=plan.id,
                previous_state={"status": plan.status.value},
                current_state={"status": DecisionPlanStatus.RESOLVED.value},
                detected_at=now,
                explanation=explanation,
                signals={"target_obligation_id": ob.id},
                provenance={"source_service": "MonitoringEngine", "authoritative_model": "DecisionPlan"},
                deduplication_key=dedup_key,
            )
            events.append(event)

        watch.last_observed_state = {
            "is_stale": is_stale,
            "status": plan.status.value,
            "evaluated_at": now.isoformat(),
        }
        return events

    # =========================================================================
    # 8. Critical Path & Systemic Bottlenecks Monitoring
    # =========================================================================
    @classmethod
    async def _evaluate_critical_path(
        cls,
        session: AsyncSession,
        watch: MonitoringWatch,
    ) -> List[MonitoringEvent]:
        events: List[MonitoringEvent] = []
        now = utc_now()

        ob = await session.get(Obligation, watch.target_id)
        if not ob:
            return events

        # Query downstream dependents
        downstream_stmt = (
            select(ObligationEdge)
            .where(
                and_(
                    ObligationEdge.to_obligation_id == ob.id,
                    ObligationEdge.workspace_id == watch.workspace_id,
                )
            )
        )
        downstream_edges = (await session.execute(downstream_stmt)).scalars().all()
        current_dep_count = len(downstream_edges)
        prev_dep_count = watch.last_observed_state.get("downstream_count", 0)

        if current_dep_count != prev_dep_count:
            event_type = MonitoringEventType.CRITICAL_PATH_CHANGED
            severity = MonitoringSeverity.NOTICE
            explanation = f"Critical dependency path changed: {current_dep_count} downstream commitments affected (was {prev_dep_count})."

            dedup_key = compute_event_dedup_key(
                watch.workspace_id,
                TargetType.OBLIGATION.value,
                ob.id,
                event_type.value,
                f"deps:{current_dep_count}",
            )

            event = MonitoringEvent(
                id=str(uuid.uuid4()),
                workspace_id=watch.workspace_id,
                watch_id=watch.id,
                event_type=event_type,
                severity=severity,
                target_type=TargetType.OBLIGATION,
                target_id=ob.id,
                previous_state={"downstream_count": prev_dep_count},
                current_state={"downstream_count": current_dep_count},
                detected_at=now,
                explanation=explanation,
                signals={"downstream_count": current_dep_count},
                provenance={"source_service": "GraphService", "authoritative_model": "ObligationEdge"},
                deduplication_key=dedup_key,
            )
            events.append(event)

        watch.last_observed_state = {
            "downstream_count": current_dep_count,
            "evaluated_at": now.isoformat(),
        }
        return events

    @classmethod
    async def _evaluate_bottlenecks(
        cls,
        session: AsyncSession,
        watch: MonitoringWatch,
    ) -> List[MonitoringEvent]:
        events: List[MonitoringEvent] = []
        now = utc_now()

        ob = await session.get(Obligation, watch.target_id)
        if not ob or ob.status in (ObligationStatus.COMPLETED, ObligationStatus.CANCELLED):
            return events

        # Count active downstream blocked obligations
        downstream_stmt = (
            select(ObligationEdge)
            .where(
                and_(
                    ObligationEdge.to_obligation_id == ob.id,
                    ObligationEdge.workspace_id == watch.workspace_id,
                )
            )
        )
        edges = (await session.execute(downstream_stmt)).scalars().all()
        downstream_count = len(edges)

        prev_bottleneck = watch.last_observed_state.get("is_bottleneck", False)
        is_bottleneck = downstream_count >= 2 and ob.status == ObligationStatus.OVERDUE

        if is_bottleneck and not prev_bottleneck:
            event_type = MonitoringEventType.SYSTEMIC_BOTTLENECK_DETECTED
            severity = MonitoringSeverity.CRITICAL if downstream_count >= 3 else MonitoringSeverity.HIGH
            explanation = f"Systemic bottleneck detected: Overdue obligation blocks {downstream_count} downstream commitments."

            dedup_key = compute_event_dedup_key(
                watch.workspace_id,
                TargetType.OBLIGATION.value,
                ob.id,
                event_type.value,
                f"bottleneck:{downstream_count}",
            )

            event = MonitoringEvent(
                id=str(uuid.uuid4()),
                workspace_id=watch.workspace_id,
                watch_id=watch.id,
                event_type=event_type,
                severity=severity,
                target_type=TargetType.OBLIGATION,
                target_id=ob.id,
                previous_state={"is_bottleneck": False},
                current_state={"is_bottleneck": True, "downstream_blocked": downstream_count},
                detected_at=now,
                explanation=explanation,
                signals={"downstream_blocked": downstream_count, "owner": ob.owner},
                provenance={"source_service": "MonitoringEngine._evaluate_bottlenecks", "authoritative_model": "ObligationEdge"},
                deduplication_key=dedup_key,
            )
            events.append(event)

        watch.last_observed_state = {
            "is_bottleneck": is_bottleneck,
            "downstream_count": downstream_count,
            "evaluated_at": now.isoformat(),
        }
        return events

    @classmethod
    async def _evaluate_generic(
        cls,
        session: AsyncSession,
        watch: MonitoringWatch,
    ) -> List[MonitoringEvent]:
        # Fallback for generic/custom watches
        watch.last_observed_state = {"evaluated_at": utc_now().isoformat()}
        return []
