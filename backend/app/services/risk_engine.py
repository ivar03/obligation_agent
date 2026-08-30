from datetime import datetime, timedelta, timezone
from typing import List, Optional, Dict, Any, Tuple
from sqlalchemy import select, and_, or_, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import logger
from app.core.status_machine import (
    ObligationStatus,
    ObligationType,
    RiskLevel,
    ActionType,
    EventSemanticRole,
    CorrelationStatus,
    ReconciliationStatus,
)
from app.models.obligation import Obligation, Evidence, Intervention, ReconciliationRecord
from app.core.intervention_status import InterventionStatus, InterventionOutcome
from app.schemas.obligation import (
    RiskSignal,
    RiskBreakdown,
    RiskAssessmentResponse,
    BlockerDetail,
)
from app.services.recommendation_engine import RecommendationEngine


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class RiskEngine:
    """
    Centralized, deterministic multi-signal risk calculation engine for obligations.
    Evaluates deadline pressure, dependency health, evidence recency/strength,
    ownership uncertainty, and graph fan-out impact.
    """

    # Centralized Risk Thresholds
    THRESHOLD_CRITICAL = 0.80
    THRESHOLD_HIGH = 0.60
    THRESHOLD_MEDIUM = 0.30

    @classmethod
    def classify_risk_level(cls, score: float) -> RiskLevel:
        if score >= cls.THRESHOLD_CRITICAL:
            return RiskLevel.CRITICAL
        if score >= cls.THRESHOLD_HIGH:
            return RiskLevel.HIGH
        if score >= cls.THRESHOLD_MEDIUM:
            return RiskLevel.MEDIUM
        return RiskLevel.LOW

    @classmethod
    async def assess_obligation(
        cls, session: AsyncSession, obligation_id: str, workspace_id: Optional[str] = None
    ) -> Optional[RiskAssessmentResponse]:
        from app.services.graph_service import GraphService

        obligation = await session.get(Obligation, obligation_id)
        if not obligation:
            return None
        if workspace_id and obligation.workspace_id != workspace_id:
            return None

        # Fetch blockers and dependents from GraphService
        blockers = await GraphService.get_blockers(session, obligation_id)
        dependents = await GraphService.get_dependents(session, obligation_id)

        # Fetch evidence records
        ev_stmt = (
            select(Evidence)
            .where(Evidence.obligation_id == obligation_id)
            .order_by(desc(Evidence.observed_at))
        )
        ev_result = await session.execute(ev_stmt)
        evidence_records = list(ev_result.scalars().all())

        # Fetch interventions
        inv_stmt = (
            select(Intervention)
            .where(Intervention.obligation_id == obligation_id)
            .order_by(desc(Intervention.created_at))
        )
        inv_result = await session.execute(inv_stmt)
        interventions = list(inv_result.scalars().all())

        # Phase 11: Fetch reconciliation record
        rec_stmt = (
            select(ReconciliationRecord)
            .where(ReconciliationRecord.obligation_id == obligation_id)
            .order_by(desc(ReconciliationRecord.updated_at))
        )
        rec_result = await session.execute(rec_stmt)
        reconciliation = rec_result.scalars().first()

        return cls.calculate_assessment(
            obligation=obligation,
            blockers=blockers,
            dependents=dependents,
            evidence_records=evidence_records,
            interventions=interventions,
            reconciliation=reconciliation,
        )

    @classmethod
    def calculate_assessment(
        cls,
        obligation: Obligation,
        blockers: List[BlockerDetail],
        dependents: List[Any],
        evidence_records: List[Evidence],
        interventions: Optional[List[Intervention]] = None,
        reconciliation: Optional[ReconciliationRecord] = None,
    ) -> RiskAssessmentResponse:
        now = utc_now()
        signals: List[RiskSignal] = []
        reasons: List[str] = []

        # 0. Resolved Obligations have zero risk
        if obligation.status in [ObligationStatus.COMPLETED, ObligationStatus.CANCELLED]:
            return RiskAssessmentResponse(
                obligation_id=obligation.id,
                owner=obligation.owner,
                beneficiary=obligation.beneficiary,
                action=obligation.action,
                status=obligation.status,
                obligation_type=obligation.obligation_type,
                deadline=obligation.deadline,
                risk_score=0.0,
                risk_level=RiskLevel.LOW,
                is_at_risk=False,
                priority_score=0.0,
                dependent_count=len(dependents),
                reasons=["Obligation is resolved; no active risk."],
                signals=[],
                breakdown=RiskBreakdown(),
                recommended_action="No action required.",
                action_type=ActionType.NO_ACTION,
                assessed_at=now,
            )

        deadline_pressure_pts = 0.0
        dependency_risk_pts = 0.0
        progress_risk_pts = 0.0
        ownership_risk_pts = 0.0
        evidence_risk_pts = 0.0

        # ==========================================
        # SIGNAL 1: DEADLINE PRESSURE (0.0 to 0.35)
        # ==========================================
        if obligation.deadline:
            dl = obligation.deadline
            if dl.tzinfo is None:
                dl = dl.replace(tzinfo=timezone.utc)

            time_diff = dl - now
            hours_left = time_diff.total_seconds() / 3600.0

            if hours_left < 0:
                # Deadline passed (Overdue lifecycle state)
                deadline_pressure_pts = 0.35
                hours_past = abs(int(hours_left))
                signals.append(
                    RiskSignal(
                        signal_type="DEADLINE_PASSED",
                        severity="CRITICAL",
                        contribution=0.35,
                        explanation=f"Deadline passed {hours_past} hour(s) ago.",
                    )
                )
                reasons.append(f"Deadline has passed ({hours_past}h overdue).")
            elif hours_left <= 12:
                deadline_pressure_pts = 0.32
                signals.append(
                    RiskSignal(
                        signal_type="DEADLINE_PROXIMITY",
                        severity="CRITICAL",
                        contribution=0.32,
                        explanation=f"Deadline is imminent ({int(hours_left)} hours remaining).",
                    )
                )
                reasons.append(f"Deadline is imminent ({int(hours_left)} hours remaining).")
            elif hours_left <= 24:
                deadline_pressure_pts = 0.28
                signals.append(
                    RiskSignal(
                        signal_type="DEADLINE_PROXIMITY",
                        severity="HIGH",
                        contribution=0.28,
                        explanation=f"Deadline is tomorrow ({int(hours_left)} hours remaining).",
                    )
                )
                reasons.append(f"Deadline is tomorrow ({int(hours_left)} hours remaining).")
            elif hours_left <= 48:
                deadline_pressure_pts = 0.20
                signals.append(
                    RiskSignal(
                        signal_type="DEADLINE_PROXIMITY",
                        severity="MEDIUM",
                        contribution=0.20,
                        explanation=f"Deadline approaching within 48 hours ({int(hours_left)} hours left).",
                    )
                )
                reasons.append(f"Deadline is approaching in {int(hours_left)} hours.")
            elif hours_left <= 168:  # 7 days
                deadline_pressure_pts = 0.08
                signals.append(
                    RiskSignal(
                        signal_type="DEADLINE_PROXIMITY",
                        severity="LOW",
                        contribution=0.08,
                        explanation=f"Due in {int(hours_left / 24)} days.",
                    )
                )
            else:
                deadline_pressure_pts = 0.02
        else:
            # No explicit calendar deadline
            if obligation.conditions:
                deadline_pressure_pts = 0.05
                signals.append(
                    RiskSignal(
                        signal_type="CONDITIONAL_TRIGGER_WAITING",
                        severity="LOW",
                        contribution=0.05,
                        explanation=f"Waiting on condition trigger: '{obligation.conditions}'.",
                    )
                )
                reasons.append(f"Waiting on conditional trigger: {obligation.conditions}")
            else:
                deadline_pressure_pts = 0.08
                signals.append(
                    RiskSignal(
                        signal_type="DEADLINE_AMBIGUOUS",
                        severity="LOW",
                        contribution=0.08,
                        explanation="No deadline specified; timeline is ambiguous.",
                    )
                )

        # ==========================================
        # SIGNAL 2: DEPENDENCY HEALTH & BLOCKERS (0.0 to 0.35)
        # ==========================================
        if blockers:
            overdue_blockers = [b for b in blockers if b.status == ObligationStatus.OVERDUE]
            blocked_blockers = [b for b in blockers if b.status == ObligationStatus.BLOCKED]

            if overdue_blockers:
                dependency_risk_pts = 0.35
                b = overdue_blockers[0]
                signals.append(
                    RiskSignal(
                        signal_type="DEPENDENCY_OVERDUE",
                        severity="CRITICAL",
                        contribution=0.35,
                        explanation=f"Blocked by {b.owner}'s overdue deliverable: '{b.action}'.",
                    )
                )
                reasons.append(f"Blocked by {b.owner}'s overdue obligation: {b.action}")
            elif blocked_blockers:
                dependency_risk_pts = 0.28
                b = blocked_blockers[0]
                signals.append(
                    RiskSignal(
                        signal_type="DEPENDENCY_BLOCKED",
                        severity="HIGH",
                        contribution=0.28,
                        explanation=f"Blocked by {b.owner}'s task '{b.action}', which is also blocked.",
                    )
                )
                reasons.append(f"Blocked by cascading dependency: {b.owner}'s {b.action}")
            else:
                dependency_risk_pts = 0.20
                b = blockers[0]
                signals.append(
                    RiskSignal(
                        signal_type="DEPENDENCY_UNRESOLVED",
                        severity="MEDIUM",
                        contribution=0.20,
                        explanation=f"Prerequisite deliverable by {b.owner} is unresolved.",
                    )
                )
                reasons.append(f"Waiting on prerequisite by {b.owner}: {b.action}")
        elif obligation.status == ObligationStatus.BLOCKED:
            dependency_risk_pts = 0.25
            signals.append(
                RiskSignal(
                    signal_type="OBLIGATION_BLOCKED",
                    severity="HIGH",
                    contribution=0.25,
                    explanation="Obligation state is marked BLOCKED.",
                )
            )
            reasons.append("Obligation is marked as BLOCKED.")

        # ==========================================
        # SIGNAL 3: PROGRESS & EVIDENCE QUALITY (-0.25 to +0.20)
        # ==========================================
        has_completion_candidate = any(
            e.semantic_role == EventSemanticRole.COMPLETION_SIGNAL and e.correlation_status == CorrelationStatus.SUGGESTED
            for e in evidence_records
        )
        has_negative_evidence = any(
            e.semantic_role == EventSemanticRole.NON_COMPLETION_SIGNAL for e in evidence_records
        )
        has_progress_update = any(
            e.semantic_role == EventSemanticRole.PROGRESS_UPDATE for e in evidence_records
        )

        # Check conflicting evidence
        has_completion_signal = any(
            e.semantic_role == EventSemanticRole.COMPLETION_SIGNAL for e in evidence_records
        )
        if has_completion_signal and has_negative_evidence:
            evidence_risk_pts += 0.15
            signals.append(
                RiskSignal(
                    signal_type="CONFLICTING_EVIDENCE",
                    severity="HIGH",
                    contribution=0.15,
                    explanation="Conflicting evidence observed (both completion and delay signals present).",
                )
            )
            reasons.append("Conflicting evidence statements detected requiring human review.")
        elif has_negative_evidence:
            evidence_risk_pts += 0.18
            signals.append(
                RiskSignal(
                    signal_type="NEGATIVE_EVIDENCE",
                    severity="HIGH",
                    contribution=0.18,
                    explanation="Recent negative/blocker statement detected in evidence feed.",
                )
            )
            reasons.append("Negative progress signal/blocker recorded in evidence.")

        if has_completion_candidate:
            progress_risk_pts -= 0.25
            signals.append(
                RiskSignal(
                    signal_type="COMPLETION_CANDIDATE_DETECTED",
                    severity="LOW",
                    contribution=-0.25,
                    explanation="Detected candidate completion evidence pending review.",
                )
            )
            reasons.append("Possible completion evidence detected awaiting confirmation.")
        elif has_progress_update:
            progress_risk_pts -= 0.15
            signals.append(
                RiskSignal(
                    signal_type="PROGRESS_DETECTED",
                    severity="LOW",
                    contribution=-0.15,
                    explanation="Active progress updates detected.",
                )
            )
        elif not evidence_records and obligation.deadline:
            dl = obligation.deadline
            if dl.tzinfo is None:
                dl = dl.replace(tzinfo=timezone.utc)
            if (dl - now).total_seconds() <= 48 * 3600:
                progress_risk_pts += 0.15
                signals.append(
                    RiskSignal(
                        signal_type="NO_PROGRESS",
                        severity="MEDIUM",
                        contribution=0.15,
                        explanation="Approaching deadline with no recorded progress evidence.",
                    )
                )
                reasons.append("No progress or evidence recorded despite approaching deadline.")

        # ==========================================
        # SIGNAL 4: POST-INTERVENTION OUTCOME / FEEDBACK (-0.15 to +0.15)
        # ==========================================
        if interventions and len(interventions) > 0:
            latest_inv = interventions[0]
            if latest_inv.status in [InterventionStatus.EXECUTED, InterventionStatus.ACKNOWLEDGED] or latest_inv.executed_at is not None:
                if latest_inv.outcome in [InterventionOutcome.ACKNOWLEDGED, InterventionOutcome.PROGRESS_REPORTED]:
                    progress_risk_pts -= 0.15
                    signals.append(
                        RiskSignal(
                            signal_type="ACKNOWLEDGED_INTERVENTION",
                            severity="LOW",
                            contribution=-0.15,
                            explanation=f"Follow-up intervention was acknowledged by owner ({latest_inv.outcome.value}).",
                        )
                    )
                    reasons.append("Follow-up intervention acknowledged by owner.")
                elif latest_inv.outcome == InterventionOutcome.NO_RESPONSE:
                    if not any(s.signal_type == "NO_PROGRESS" for s in signals):
                        progress_risk_pts += 0.15
                    signals.append(
                        RiskSignal(
                            signal_type="NO_RESPONSE_AFTER_INTERVENTION",
                            severity="HIGH",
                            contribution=0.15,
                            explanation="No response received following executed intervention.",
                        )
                    )
                    reasons.append("No response received following executed follow-up.")
                elif latest_inv.outcome == InterventionOutcome.NEGATIVE_RESPONSE:
                    if not any(s.signal_type == "NEGATIVE_EVIDENCE" for s in signals):
                        evidence_risk_pts += 0.15
                    signals.append(
                        RiskSignal(
                            signal_type="NEGATIVE_INTERVENTION_RESPONSE",
                            severity="HIGH",
                            contribution=0.15,
                            explanation="Negative response received after follow-up intervention.",
                        )
                    )
                    reasons.append("Owner reported blockers during follow-up intervention.")

        # ==========================================
        # SIGNAL 5: OWNERSHIP UNCERTAINTY (0.0 to 0.10)
        # ==========================================
        norm_owner = (obligation.owner or "").strip().lower()
        if norm_owner in ["we", "team", "unassigned", "anyone", "someone", "unknown"] or (
            isinstance(obligation.confidence, dict) and obligation.confidence.get("owner", 1.0) < 0.70
        ):
            ownership_risk_pts = 0.10
            signals.append(
                RiskSignal(
                    signal_type="OWNERSHIP_UNCERTAINTY",
                    severity="MEDIUM",
                    contribution=0.10,
                    explanation=f"Owner '{obligation.owner}' is ambiguous or unassigned.",
                )
            )
            reasons.append("No single accountable owner has been confirmed.")

        # ==========================================
        # SIGNAL 6: TEMPORAL & CALENDAR SIGNALS (0.0 to +0.20)
        # ==========================================
        temporal_risk_pts = 0.0
        cal_evs = [
            e for e in evidence_records
            if e.source_type == "google_calendar"
            or (isinstance(e.extra_metadata, dict) and e.extra_metadata.get("source_provider") == "google_calendar")
        ]

        for cev in cal_evs:
            cmeta = cev.extra_metadata if isinstance(cev.extra_metadata, dict) else {}
            m_status = cmeta.get("meeting_status", "")
            summary = cmeta.get("summary") or "Project Review"
            start_raw = cmeta.get("start_time")
            end_raw = cmeta.get("end_time")

            # 1. Check meeting completed without evidence
            if m_status == "MEETING_COMPLETED" or cmeta.get("completed"):
                if not has_completion_candidate and obligation.status in [ObligationStatus.CONFIRMED, ObligationStatus.IN_PROGRESS]:
                    temporal_risk_pts += 0.15
                    signals.append(
                        RiskSignal(
                            signal_type="RELATED_MEETING_COMPLETED_WITHOUT_COMPLETION",
                            severity="HIGH",
                            contribution=0.15,
                            explanation=f"Associated meeting '{summary}' has concluded without confirmed deliverable evidence.",
                        )
                    )
                    reasons.append(f"Associated meeting '{summary}' completed without fulfillment proof.")
            # 2. Check upcoming meeting proximity
            elif start_raw and (m_status == "MEETING_SCHEDULED" or not m_status):
                try:
                    sdt = datetime.fromisoformat(str(start_raw).replace("Z", "+00:00"))
                    if sdt.tzinfo is None:
                        sdt = sdt.replace(tzinfo=timezone.utc)
                    if now < sdt <= now + timedelta(hours=36):
                        if not any(s.signal_type == "UPCOMING_RELATED_MEETING" for s in signals):
                            temporal_risk_pts += 0.10
                            signals.append(
                                RiskSignal(
                                    signal_type="UPCOMING_RELATED_MEETING",
                                    severity="MEDIUM",
                                    contribution=0.10,
                                    explanation=f"Related meeting '{summary}' is scheduled within 36h ({sdt.strftime('%b %d, %H:%M')}).",
                                )
                            )
                            reasons.append(f"Upcoming meeting '{summary}' approaching soon.")
                except Exception:
                    pass
            # 3. Check rescheduled meeting
            elif m_status == "MEETING_RESCHEDULED" or cmeta.get("rescheduled"):
                if not any(s.signal_type == "RELATED_MEETING_RESCHEDULED" for s in signals):
                    signals.append(
                        RiskSignal(
                            signal_type="RELATED_MEETING_RESCHEDULED",
                            severity="MEDIUM",
                            contribution=0.05,
                            explanation=f"Related meeting '{summary}' was rescheduled.",
                        )
                    )
                    reasons.append(f"Related meeting '{summary}' was rescheduled.")
            # 4. Check cancelled meeting
            elif m_status == "MEETING_CANCELLED" or cmeta.get("cancelled"):
                if not any(s.signal_type == "RELATED_MEETING_CANCELLED" for s in signals):
                    signals.append(
                        RiskSignal(
                            signal_type="RELATED_MEETING_CANCELLED",
                            severity="MEDIUM",
                            contribution=0.05,
                            explanation=f"Associated meeting '{summary}' was cancelled.",
                        )
                    )
                    reasons.append(f"Associated meeting '{summary}' was cancelled.")

        # ==========================================
        # SIGNAL 7: CROSS-PROVIDER RECONCILIATION SIGNALS (-0.15 to +0.20)
        # ==========================================
        reconciliation_risk_pts = 0.0
        if reconciliation:
            if reconciliation.status == ReconciliationStatus.CONFLICTING:
                reconciliation_risk_pts += 0.20
                signals.append(
                    RiskSignal(
                        signal_type="CONFLICTING_EVIDENCE",
                        severity="HIGH",
                        contribution=0.20,
                        explanation="Contradiction detected across independent providers (e.g. reported completion vs. negative blocker or ongoing progress).",
                    )
                )
                reasons.append("Cross-provider contradiction detected requiring human review.")
            elif reconciliation.status == ReconciliationStatus.CONSISTENT and reconciliation.consistency_score >= 0.85:
                # Strong consistent evidence reduces risk
                reconciliation_risk_pts -= 0.15
                signals.append(
                    RiskSignal(
                        signal_type="STRONG_SUPPORTING_EVIDENCE",
                        severity="LOW",
                        contribution=-0.15,
                        explanation=f"Multiple consistent observations support completion (consistency: {reconciliation.consistency_score*100:.0f}%).",
                    )
                )
            elif reconciliation.status == ReconciliationStatus.AMBIGUOUS:
                reconciliation_risk_pts += 0.10
                signals.append(
                    RiskSignal(
                        signal_type="AMBIGUOUS_RECONCILIATION",
                        severity="MEDIUM",
                        contribution=0.10,
                        explanation="Evidence signals across providers are ambiguous or contain conditional conflicts.",
                    )
                )
                reasons.append("Ambiguous evidence state across providers.")

        # ==========================================
        # AGGREGATE TOTAL SCORE & BOUNDING
        # ==========================================
        raw_score = (
            deadline_pressure_pts
            + dependency_risk_pts
            + progress_risk_pts
            + ownership_risk_pts
            + evidence_risk_pts
            + temporal_risk_pts
            + reconciliation_risk_pts
        )
        final_score = max(0.05, min(0.98, raw_score))
        risk_level = cls.classify_risk_level(final_score)

        # Graph fan-out impact calculation
        dependent_count = len(dependents)
        fan_out_bonus = min(0.25, dependent_count * 0.08)
        priority_score = min(1.0, round(final_score * 0.75 + fan_out_bonus, 2))

        if dependent_count > 0 and risk_level in [RiskLevel.HIGH, RiskLevel.CRITICAL]:
            reasons.append(f"High graph impact: blocks {dependent_count} downstream obligation(s).")

        # Determine is_at_risk
        is_at_risk = (
            risk_level in [RiskLevel.HIGH, RiskLevel.CRITICAL]
            or obligation.status in [ObligationStatus.OVERDUE, ObligationStatus.BLOCKED]
            or final_score >= cls.THRESHOLD_MEDIUM
        )

        # Generate recommendation
        action_type, rec_text = RecommendationEngine.generate_recommendation(
            obligation=obligation,
            risk_level=risk_level,
            signals=signals,
            blockers=blockers,
        )

        return RiskAssessmentResponse(
            obligation_id=obligation.id,
            owner=obligation.owner,
            beneficiary=obligation.beneficiary,
            action=obligation.action,
            status=obligation.status,
            obligation_type=obligation.obligation_type,
            deadline=obligation.deadline,
            risk_score=round(final_score, 2),
            risk_level=risk_level,
            is_at_risk=is_at_risk,
            priority_score=priority_score,
            dependent_count=dependent_count,
            reasons=reasons or ["Commitment timeline is normal and healthy."],
            signals=signals,
            breakdown=RiskBreakdown(
                deadline_pressure=round(deadline_pressure_pts, 2),
                dependency_risk=round(dependency_risk_pts, 2),
                progress_risk=round(progress_risk_pts, 2),
                ownership_risk=round(ownership_risk_pts, 2),
                evidence_risk=round(evidence_risk_pts, 2),
            ),
            recommended_action=rec_text,
            action_type=action_type,
            assessed_at=now,
        )
