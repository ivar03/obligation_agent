from datetime import datetime, timezone
from typing import Tuple, List, Optional, Any, Dict

from app.core.status_machine import ObligationStatus, ObligationOutcomeType
from app.models.obligation import Obligation, Evidence, Intervention, ReconciliationRecord


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class OutcomeClassifier:
    """
    Deterministic classifier that derives concrete historical lifecycle outcomes
    from persisted database state, timestamps, evidence, interventions, and reconciliations.
    """

    @classmethod
    def classify(
        cls,
        obligation: Obligation,
        completed_at: Optional[datetime] = None,
        evidence_list: Optional[List[Evidence]] = None,
        interventions_list: Optional[List[Intervention]] = None,
        reconciliation_records: Optional[List[ReconciliationRecord]] = None,
    ) -> Tuple[ObligationOutcomeType, float]:
        """
        Classifies the final or current outcome of an obligation.
        Returns (ObligationOutcomeType, delay_hours).
        Positive delay_hours indicates late completion or overdue duration.
        """
        now = utc_now()
        delay_hours = 0.0

        # Calculate deadline delay
        if obligation.deadline:
            deadline_tz = obligation.deadline
            if deadline_tz.tzinfo is None:
                deadline_tz = deadline_tz.replace(tzinfo=timezone.utc)

            comp_time = completed_at or now
            if comp_time.tzinfo is None:
                comp_time = comp_time.replace(tzinfo=timezone.utc)

            delta = (comp_time - deadline_tz).total_seconds() / 3600.0
            delay_hours = max(0.0, delta) if (comp_time > deadline_tz) else delta

        # 1. Evaluate COMPLETED Status
        if obligation.status == ObligationStatus.COMPLETED:
            # Check reconciliation conflict history
            if reconciliation_records:
                for rec in reconciliation_records:
                    if rec.contradiction_score >= 0.50 or rec.status == "RESOLVED_CONFLICTING":
                        return ObligationOutcomeType.CONFLICTED_COMPLETION, max(0.0, delay_hours)

            # Check if completed after human intervention
            if interventions_list:
                for inv in interventions_list:
                    if inv.status in ["EXECUTED", "RESOLVED"]:
                        return ObligationOutcomeType.COMPLETED_AFTER_INTERVENTION, max(0.0, delay_hours)

            # Check if delay occurred
            if obligation.deadline and delay_hours > 0.5:
                return ObligationOutcomeType.COMPLETED_LATE, delay_hours
            else:
                return ObligationOutcomeType.COMPLETED_ON_TIME, max(0.0, delay_hours)

        # 2. Evaluate OVERDUE Status
        if obligation.status == ObligationStatus.OVERDUE:
            if obligation.deadline:
                deadline_tz = obligation.deadline
                if deadline_tz.tzinfo is None:
                    deadline_tz = deadline_tz.replace(tzinfo=timezone.utc)
                delay_hours = max(0.0, (now - deadline_tz).total_seconds() / 3600.0)
            return ObligationOutcomeType.OVERDUE, delay_hours

        # 3. Evaluate BLOCKED Status
        if obligation.status == ObligationStatus.BLOCKED:
            return ObligationOutcomeType.BLOCKED, max(0.0, delay_hours)

        # 4. Evaluate CANCELLED Status
        if obligation.status == ObligationStatus.CANCELLED:
            return ObligationOutcomeType.CANCELLED, max(0.0, delay_hours)

        # 5. Check if active obligation has exceeded deadline significantly
        if obligation.deadline:
            deadline_tz = obligation.deadline
            if deadline_tz.tzinfo is None:
                deadline_tz = deadline_tz.replace(tzinfo=timezone.utc)
            if now > deadline_tz + (now - now):  # Past deadline
                delay = (now - deadline_tz).total_seconds() / 3600.0
                if delay > 0:
                    return ObligationOutcomeType.OVERDUE, delay

        return ObligationOutcomeType.UNKNOWN, 0.0
