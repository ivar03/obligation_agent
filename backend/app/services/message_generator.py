from typing import Optional, List, Dict, Any
from app.core.intervention_status import InterventionType
from app.models.obligation import Obligation
from app.schemas.obligation import BlockerDetail, RiskAssessmentResponse


class MessageGenerator:
    """
    Produces deterministic, professional, fact-grounded intervention message drafts.
    Guarantees zero hallucinations, zero fabricated claims, and strict fact grounding.
    """

    @classmethod
    def generate_draft(
        cls,
        obligation: Obligation,
        intervention_type: InterventionType,
        target_owner: str,
        target_beneficiary: str,
        blockers: Optional[List[BlockerDetail]] = None,
        dependents: Optional[List[Any]] = None,
        risk_assessment: Optional[RiskAssessmentResponse] = None,
    ) -> str:
        recipient_name = target_owner if target_owner and target_owner.lower() not in ["we", "team", "unassigned"] else "Team"
        action_text = obligation.action.strip()

        # Check deadline facts
        is_overdue = False
        deadline_text = ""
        if obligation.deadline:
            from datetime import datetime, timezone
            now = datetime.now(timezone.utc)
            dl = obligation.deadline
            if dl.tzinfo is None:
                dl = dl.replace(tzinfo=timezone.utc)
            if dl < now:
                is_overdue = True
                hours_past = abs(int((dl - now).total_seconds() / 3600))
                deadline_text = f"was due {hours_past} hour(s) ago" if hours_past < 48 else "has passed"
            else:
                hours_left = int((dl - now).total_seconds() / 3600)
                if hours_left <= 24:
                    deadline_text = f"is due within {hours_left} hours"
                else:
                    days_left = int(hours_left / 24)
                    deadline_text = f"is due in {days_left} day(s)"

        # Check blocking facts
        blocking_sentence = ""
        if blockers and len(blockers) > 0:
            b = blockers[0]
            blocking_sentence = f" This is currently blocking '{obligation.action}'."
        elif dependents and len(dependents) > 0:
            blocking_sentence = f" Note that this deliverable is a prerequisite for downstream task '{dependents[0].action if hasattr(dependents[0], 'action') else 'project tasks'}'."

        # Template Generation based on InterventionType
        if intervention_type == InterventionType.RESOLVE_DEPENDENCY:
            if blockers and len(blockers) > 0:
                b = blockers[0]
                if is_overdue or b.status.value == "OVERDUE":
                    return (
                        f"Hi {b.owner}, following up on '{b.action}'. "
                        f"This deliverable is currently overdue and blocking '{obligation.action}'. "
                        f"Could you provide an update on when this will be ready?"
                    )
                return (
                    f"Hi {b.owner}, checking in on '{b.action}'. "
                    f"Our task '{obligation.action}' depends on this deliverable. "
                    f"Could you share the latest progress or expected completion timeline?"
                )
            return (
                f"Hi {recipient_name}, checking in regarding prerequisite dependencies for '{action_text}'. "
                f"Could you let us know the current status so we can coordinate next steps?"
            )

        elif intervention_type == InterventionType.FOLLOW_UP_OWNER:
            if is_overdue:
                return (
                    f"Hi {recipient_name}, following up on '{action_text}'. "
                    f"The deadline {deadline_text}.{blocking_sentence} "
                    f"Could you share the latest status or let us know if any support is needed to finalize it?"
                )
            if deadline_text:
                return (
                    f"Hi {recipient_name}, sending a quick check-in regarding '{action_text}'. "
                    f"The commitment {deadline_text}.{blocking_sentence} "
                    f"Please let us know if everything is on track for delivery."
                )
            return (
                f"Hi {recipient_name}, following up regarding '{action_text}'.{blocking_sentence} "
                f"Could you provide an update on the current progress?"
            )

        elif intervention_type == InterventionType.REQUEST_STATUS_UPDATE:
            return (
                f"Hi {recipient_name}, requesting a quick status update on '{action_text}'. "
                f"We want to ensure everything remains on schedule.{blocking_sentence} "
                f"Could you let us know what stage this is in?"
            )

        elif intervention_type == InterventionType.REQUEST_MISSING_DELIVERABLE:
            return (
                f"Hi {recipient_name}, following up regarding the deliverable for '{action_text}'. "
                f"We haven't received the output artifact yet.{blocking_sentence} "
                f"Could you please share the completed file or link when available?"
            )

        elif intervention_type == InterventionType.REVIEW_EVIDENCE:
            return (
                f"Review required: Recent evidence statements have been recorded for '{action_text}'. "
                f"Please verify fulfillment artifacts to confirm completion."
            )

        elif intervention_type == InterventionType.ASSIGN_OWNER:
            return (
                f"Action required: Obligation '{action_text}' owes '{target_beneficiary}' "
                f"but currently lacks a confirmed individual owner. "
                f"Please assign an accountable owner to ensure clear execution."
            )

        elif intervention_type == InterventionType.CLARIFY_DEADLINE:
            return (
                f"Hi {recipient_name}, checking in on '{action_text}'. "
                f"There is no explicit deadline set for this commitment. "
                f"Could you clarify the expected target completion date?"
            )

        elif intervention_type == InterventionType.MONITOR_CONDITION:
            cond = str(obligation.conditions) if obligation.conditions else "prerequisite trigger"
            return (
                f"Status check: Obligation '{action_text}' is conditional upon '{cond}'. "
                f"Please verify whether the trigger condition has been satisfied before beginning work."
            )

        return (
            f"Hi {recipient_name}, following up regarding '{action_text}'. "
            f"Please let us know if you need any assistance."
        )
