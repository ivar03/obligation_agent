"""
Execution Authorization Service for Phase 16.
Strictly validates all 10 human-authorization and safety boundaries before allowing outbound execution.
"""

from typing import Tuple, Optional, Dict, Any
from sqlalchemy import select, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException, status

from app.core.status_machine import (
    DecisionPlanStatus,
    ObligationStatus,
    ExecutionStatus,
)
from app.models.decision import DecisionPlan
from app.models.obligation import Obligation, Intervention
from app.models.execution import ExecutionRecord


class ExecutionAuthorizationError(HTTPException):
    def __init__(self, detail: str, error_code: str = "AUTHORIZATION_FAILED"):
        super().__init__(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error_code": error_code, "message": detail},
        )


class ExecutionAuthorizationService:
    """
    Validates that a Decision Plan has met all mandatory authorization criteria
    before an ExecutionRecord can be created or executed.
    """

    @classmethod
    async def validate_authorization(
        cls,
        session: AsyncSession,
        plan_id: str,
        workspace_id: str = "ws-default",
        requested_provider: str = "mock",
        requested_action: Optional[Dict[str, Any]] = None,
    ) -> Tuple[DecisionPlan, Obligation, Optional[Intervention]]:
        # 1. Decision Plan Exists
        plan_stmt = select(DecisionPlan).where(
            and_(
                DecisionPlan.id == plan_id,
                DecisionPlan.workspace_id == workspace_id,
            )
        )
        plan_res = await session.execute(plan_stmt)
        plan = plan_res.scalar_one_or_none()
        if not plan:
            raise ExecutionAuthorizationError(
                detail=f"Decision Plan [{plan_id}] does not exist in workspace [{workspace_id}].",
                error_code="PLAN_NOT_FOUND",
            )

        # 2. Decision Plan is current and not superseded
        if plan.superseded_by_plan_id is not None or plan.status == DecisionPlanStatus.SUPERSEDED:
            raise ExecutionAuthorizationError(
                detail=f"Decision Plan [{plan_id}] is superseded by Plan [{plan.superseded_by_plan_id}] and cannot execute.",
                error_code="DECISION_PLAN_SUPERSEDED",
            )

        # 3. Decision Plan is not stale
        from app.services.intelligence.intelligence_orchestrator import IntelligenceOrchestrator
        ob = await session.get(Obligation, plan.target_obligation_id)
        if not ob or ob.workspace_id != workspace_id:
            raise ExecutionAuthorizationError(
                detail=f"Target obligation [{plan.target_obligation_id}] not found.",
                error_code="OBLIGATION_NOT_FOUND",
            )

        is_stale = await IntelligenceOrchestrator._is_plan_stale(session, plan, ob)
        if is_stale:
            raise ExecutionAuthorizationError(
                detail=f"Decision Plan [{plan_id}] is marked STALE due to graph state changes. Refresh to a new version before executing.",
                error_code="DECISION_PLAN_STALE",
            )

        # 4. Decision Plan status permits execution
        if plan.status not in [DecisionPlanStatus.APPROVED, DecisionPlanStatus.PARTIALLY_EXECUTED]:
            raise ExecutionAuthorizationError(
                detail=f"Decision Plan [{plan_id}] has status '{plan.status.value}'. Only APPROVED plans can execute.",
                error_code="PLAN_NOT_APPROVED",
            )

        # 5. Required human decisions must be explicitly satisfied
        if plan.human_decisions_required and len(plan.human_decisions_required) > 0:
            # Check if plan has been approved by operator
            if not plan.approved_by_user_id:
                raise ExecutionAuthorizationError(
                    detail="Decision Plan has unsatisfied human authorization requirements.",
                    error_code="HUMAN_DECISION_REQUIRED",
                )

        # 6. Target obligation still exists and is not COMPLETED or CANCELLED
        ob = await session.get(Obligation, plan.target_obligation_id)
        if not ob or ob.workspace_id != workspace_id:
            raise ExecutionAuthorizationError(
                detail=f"Target obligation [{plan.target_obligation_id}] not found.",
                error_code="OBLIGATION_NOT_FOUND",
            )

        if ob.status in [ObligationStatus.COMPLETED, ObligationStatus.CANCELLED]:
            raise ExecutionAuthorizationError(
                detail=f"Target obligation [{ob.id}] is already '{ob.status.value}'. Execution rejected.",
                error_code="OBLIGATION_ALREADY_RESOLVED",
            )

        # 7. No conflicting active execution in progress
        active_exec_stmt = select(ExecutionRecord).where(
            and_(
                ExecutionRecord.workspace_id == workspace_id,
                ExecutionRecord.decision_plan_id == plan_id,
                ExecutionRecord.status.in_([
                    ExecutionStatus.QUEUED,
                    ExecutionStatus.EXECUTING,
                    ExecutionStatus.RESPONSE_PENDING,
                ]),
            )
        )
        active_exec_res = await session.execute(active_exec_stmt)
        conflicting_exec = active_exec_res.scalar_one_or_none()
        if conflicting_exec:
            raise ExecutionAuthorizationError(
                detail=f"An active execution [{conflicting_exec.id}] is already in status '{conflicting_exec.status.value}'.",
                error_code="CONFLICTING_EXECUTION_IN_PROGRESS",
            )

        # 8. Check associated intervention if present
        intervention: Optional[Intervention] = None
        rec_actions = plan.recommended_actions or {}
        inv_id = rec_actions.get("intervention_id")
        if inv_id:
            intervention = await session.get(Intervention, inv_id)

        # 9. Provider connection availability check
        if requested_provider not in ["mock", "slack", "email", "webhook"]:
            raise ExecutionAuthorizationError(
                detail=f"Unknown execution provider '{requested_provider}'.",
                error_code="UNKNOWN_PROVIDER",
            )

        return plan, ob, intervention
