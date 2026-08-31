"""
REST API Routes for Phase 15 Decision Layer.
"""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.auth import User, Workspace
from app.models.obligation import Obligation
from app.models.decision import DecisionPlan
from app.core.auth_deps import get_current_user, get_current_workspace
from app.core.status_machine import DecisionPlanStatus
from app.schemas.decision import (
    DecisionPlanResponse,
    DecisionPlanSummaryResponse,
    DecisionPlanListResponse,
    DecisionPlanApproveRequest,
    DecisionPlanRejectRequest,
    DecisionPlanSimulateRequest,
)
from app.services.intelligence.intelligence_orchestrator import IntelligenceOrchestrator
from app.services.intelligence.resolution_simulation_service import ResolutionSimulationService
from app.schemas.intelligence import ResolutionSimulationRequest, ResolutionSimulationResponse

router = APIRouter(prefix="/intelligence/decision", tags=["Decision Orchestrator"])


def _to_plan_response(plan: DecisionPlan, obligation: Optional[Obligation] = None) -> DecisionPlanResponse:
    target_action = obligation.action if obligation else None
    target_owner = obligation.owner if obligation else None
    target_status = obligation.status.value if obligation and hasattr(obligation.status, "value") else str(obligation.status) if obligation else None

    return DecisionPlanResponse(
        id=plan.id,
        workspace_id=plan.workspace_id,
        target_obligation_id=plan.target_obligation_id,
        target_obligation_action=target_action,
        target_obligation_owner=target_owner,
        target_obligation_status=target_status,
        generated_at=plan.generated_at,
        plan_version=plan.plan_version,
        status=plan.status,
        overall_urgency=plan.overall_urgency,
        overall_risk=plan.overall_risk,
        decision_confidence=plan.decision_confidence,
        primary_objective=plan.primary_objective,
        root_cause_obligation_id=plan.root_cause_obligation_id,
        root_cause_summary=plan.resolution_notes,
        critical_path=plan.critical_path or [],
        impact_summary=plan.impact_summary or {},
        key_risks=plan.key_risks or [],
        supporting_evidence=plan.supporting_evidence or [],
        recommended_actions=plan.recommended_actions or {},
        alternative_actions=plan.alternative_actions or [],
        human_decisions_required=plan.human_decisions_required or [],
        assumptions=plan.assumptions or [],
        uncertainties=plan.uncertainties or [],
        simulation_summary=plan.simulation_summary or {},
        created_from_snapshot_ids=plan.created_from_snapshot_ids or [],
        created_from_event_ids=plan.created_from_event_ids or [],
        explainability_narrative=plan.resolution_notes or "",
        approved_at=plan.approved_at,
        approved_by_user_id=plan.approved_by_user_id,
        rejected_at=plan.rejected_at,
        rejected_by_user_id=plan.rejected_by_user_id,
        superseded_at=plan.superseded_at,
        superseded_by_plan_id=plan.superseded_by_plan_id,
        resolution_notes=plan.resolution_notes,
        is_stale=plan.status == DecisionPlanStatus.SUPERSEDED,
    )


@router.post("/{obligation_id}/generate", response_model=DecisionPlanResponse)
async def generate_decision_plan(
    obligation_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    workspace: Workspace = Depends(get_current_workspace),
):
    """
    Synthesizes multi-source intelligence to generate or return the active DecisionPlan for an obligation.
    Safety Invariant: Generation never mutates operational obligation state.
    """
    try:
        plan = await IntelligenceOrchestrator.generate_decision_plan(
            session=db,
            obligation_id=obligation_id,
            workspace_id=workspace.id,
            force_refresh=False,
        )
        obligation = await db.get(Obligation, obligation_id)
        return _to_plan_response(plan, obligation)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate decision plan: {str(e)}",
        )


@router.get("/queue", response_model=DecisionPlanListResponse)
async def get_decision_queue(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    workspace: Workspace = Depends(get_current_workspace),
):
    """
    Retrieves the decision queue for the current workspace.
    """
    plans = await IntelligenceOrchestrator.get_workspace_decision_queue(
        session=db, workspace_id=workspace.id
    )
    items: List[DecisionPlanSummaryResponse] = []
    for p in plans:
        ob = await db.get(Obligation, p.target_obligation_id)
        rec = p.recommended_actions or {}
        items.append(
            DecisionPlanSummaryResponse(
                id=p.id,
                workspace_id=p.workspace_id,
                target_obligation_id=p.target_obligation_id,
                target_obligation_action=ob.action if ob else "Unknown",
                target_obligation_owner=ob.owner if ob else "Unassigned",
                target_obligation_status=ob.status.value if ob and hasattr(ob.status, "value") else str(ob.status) if ob else "UNKNOWN",
                plan_version=p.plan_version,
                status=p.status,
                overall_urgency=p.overall_urgency,
                overall_risk=p.overall_risk,
                decision_confidence=p.decision_confidence,
                primary_objective=p.primary_objective,
                recommended_strategy_name=rec.get("strategy_name", "Primary Strategy"),
                target_owner=rec.get("target_owner", "Unassigned"),
                human_decisions_count=len(p.human_decisions_required or []),
                is_stale=p.status == DecisionPlanStatus.SUPERSEDED,
                generated_at=p.generated_at,
            )
        )
    return DecisionPlanListResponse(items=items, total=len(items))


@router.get("/{obligation_id}", response_model=DecisionPlanResponse)
async def get_decision_plan(
    obligation_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    workspace: Workspace = Depends(get_current_workspace),
):
    """
    Retrieves the active DecisionPlan for an obligation.
    If none exists yet, automatically generates one.
    """
    plan = await IntelligenceOrchestrator.get_active_plan(
        session=db, obligation_id=obligation_id, workspace_id=workspace.id
    )
    if not plan:
        try:
            plan = await IntelligenceOrchestrator.generate_decision_plan(
                session=db, obligation_id=obligation_id, workspace_id=workspace.id
            )
        except ValueError as e:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))

    obligation = await db.get(Obligation, obligation_id)
    return _to_plan_response(plan, obligation)


@router.get("/{obligation_id}/history", response_model=List[DecisionPlanResponse])
async def get_decision_plan_history(
    obligation_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    workspace: Workspace = Depends(get_current_workspace),
):
    """
    Retrieves the immutable historical decision plan versions for an obligation.
    """
    plans = await IntelligenceOrchestrator.get_plan_history(
        session=db, obligation_id=obligation_id, workspace_id=workspace.id
    )
    obligation = await db.get(Obligation, obligation_id)
    return [_to_plan_response(p, obligation) for p in plans]


@router.post("/{plan_id}/approve", response_model=DecisionPlanResponse)
async def approve_decision_plan(
    plan_id: str,
    payload: Optional[DecisionPlanApproveRequest] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    workspace: Workspace = Depends(get_current_workspace),
):
    """
    Human authorization of a DecisionPlan.
    Safety Invariant: Authorizes plan without autonomous operational execution.
    """
    try:
        plan = await IntelligenceOrchestrator.approve_plan(
            session=db,
            plan_id=plan_id,
            user_id=current_user.id,
            request=payload,
        )
        obligation = await db.get(Obligation, plan.target_obligation_id)
        return _to_plan_response(plan, obligation)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to approve plan: {str(e)}",
        )


@router.post("/{plan_id}/reject", response_model=DecisionPlanResponse)
async def reject_decision_plan(
    plan_id: str,
    payload: DecisionPlanRejectRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    workspace: Workspace = Depends(get_current_workspace),
):
    """
    Human rejection of a DecisionPlan with operator reason.
    """
    try:
        plan = await IntelligenceOrchestrator.reject_plan(
            session=db,
            plan_id=plan_id,
            user_id=current_user.id,
            request=payload,
        )
        obligation = await db.get(Obligation, plan.target_obligation_id)
        return _to_plan_response(plan, obligation)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to reject plan: {str(e)}",
        )


@router.post("/{plan_id}/refresh", response_model=DecisionPlanResponse)
async def refresh_decision_plan(
    plan_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    workspace: Workspace = Depends(get_current_workspace),
):
    """
    Forces recalculation of the decision plan, creating Plan v(N+1) and superseding the previous plan.
    """
    plan = await db.get(DecisionPlan, plan_id)
    if not plan or plan.workspace_id != workspace.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"DecisionPlan '{plan_id}' not found.",
        )

    try:
        new_plan = await IntelligenceOrchestrator.generate_decision_plan(
            session=db,
            obligation_id=plan.target_obligation_id,
            workspace_id=workspace.id,
            force_refresh=True,
        )
        obligation = await db.get(Obligation, plan.target_obligation_id)
        return _to_plan_response(new_plan, obligation)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to refresh plan: {str(e)}",
        )


@router.post("/{plan_id}/simulate", response_model=ResolutionSimulationResponse)
async def simulate_plan_strategy(
    plan_id: str,
    payload: DecisionPlanSimulateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    workspace: Workspace = Depends(get_current_workspace),
):
    """
    100% side-effect-free in-memory simulation of a strategy from the DecisionPlan.
    """
    plan = await db.get(DecisionPlan, plan_id)
    if not plan or plan.workspace_id != workspace.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"DecisionPlan '{plan_id}' not found.",
        )

    target_id = plan.target_obligation_id
    action = payload.custom_action or "COMPLETE_OBLIGATION"
    params = payload.custom_parameters or {}

    rec = plan.recommended_actions or {}
    if payload.strategy_id and payload.strategy_id == rec.get("strategy_id"):
        target_id = rec.get("target_obligation_id", target_id)
        action = rec.get("strategy_type", action)

    for alt in plan.alternative_actions or []:
        if payload.strategy_id and payload.strategy_id == alt.get("strategy_id"):
            target_id = alt.get("target_obligation_id", target_id)
            action = alt.get("strategy_type", action)

    sim_res = await ResolutionSimulationService.simulate(
        session=db,
        request=ResolutionSimulationRequest(
            action=action,
            target_obligation_id=target_id,
            parameters=params,
        ),
        workspace_id=workspace.id,
    )
    return sim_res
