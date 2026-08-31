from datetime import datetime, timezone
from typing import List, Optional, Dict, Any, Set
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import logger
from app.core.status_machine import (
    ObligationStatus,
    SimulationActionType,
    RiskLevel,
)
from app.models.obligation import Obligation
from app.schemas.intelligence import (
    ResolutionSimulationRequest,
    ResolutionSimulationResponse,
)
from app.services.graph_service import GraphService
from app.services.risk_engine import RiskEngine


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class ResolutionSimulationService:
    """
    100% Side-Effect Free Resolution Simulation Engine.
    Simulates "what happens if?" scenarios entirely in-memory:
    - Simulates completing an obligation / resolving a blocker / assigning owner / confirming evidence.
    - Projects cascading unblocks and risk reductions across the entire downstream graph.
    - NEVER touches or mutates the database.
    - NEVER creates interventions, messages, evidence, or records.
    """

    @classmethod
    async def simulate(
        cls,
        session: AsyncSession,
        request: ResolutionSimulationRequest,
        workspace_id: Optional[str] = None,
    ) -> ResolutionSimulationResponse:
        target_id = request.target_obligation_id
        action = request.action
        params = request.parameters or {}

        target = await session.get(Obligation, target_id)
        if not target or (workspace_id and target.workspace_id != workspace_id):
            raise ValueError(f"Target obligation with ID '{target_id}' not found.")

        # 1. Capture current baseline state
        current_risk_res = await RiskEngine.assess_obligation(session, target_id)
        current_risk_score = current_risk_res.risk_score if current_risk_res else 0.5
        current_blockers = await GraphService.get_blockers(session, target_id)
        downstream_impact = await GraphService.get_downstream_impact(session, target_id)

        current_state = {
            "obligation_id": target.id,
            "action": target.action,
            "owner": target.owner,
            "status": target.status.value if hasattr(target.status, "value") else str(target.status),
            "risk_score": current_risk_score,
            "blockers_count": len(current_blockers),
            "downstream_count": len(downstream_impact),
        }

        # 2. In-memory Counterfactual Graph Simulation
        projected_target_status: str = current_state["status"]
        projected_target_risk: float = current_risk_score
        unblocked_obligations: List[Dict[str, Any]] = []
        affected_obligations: List[Dict[str, Any]] = []
        explanation: str = ""

        # Virtual simulated completion set (IDs of obligations simulated as COMPLETED)
        simulated_completed_ids: Set[str] = set()

        if action == SimulationActionType.COMPLETE_OBLIGATION:
            simulated_completed_ids.add(target.id)
            projected_target_status = ObligationStatus.COMPLETED.value
            projected_target_risk = 0.0

            # Evaluate cascading unblocking along downstream dependents
            # For each downstream node, check if all its blockers are in simulated_completed_ids or already COMPLETED
            for d in downstream_impact:
                dep_obj: Obligation = d["obligation"]
                dep_blockers = await GraphService.get_blockers(session, dep_obj.id)
                # Filter unresolved blockers that are NOT in simulated_completed_ids
                remaining_blockers = [
                    b for b in dep_blockers
                    if b.obligation_id not in simulated_completed_ids and b.status != ObligationStatus.COMPLETED
                ]

                if not remaining_blockers and dep_obj.status == ObligationStatus.BLOCKED:
                    # This downstream node becomes unblocked in simulation!
                    simulated_completed_ids.add(dep_obj.id)
                    unblocked_obligations.append({
                        "obligation_id": dep_obj.id,
                        "action": dep_obj.action,
                        "owner": dep_obj.owner,
                        "previous_status": dep_obj.status.value if hasattr(dep_obj.status, "value") else str(dep_obj.status),
                        "projected_status": ObligationStatus.CONFIRMED.value,
                        "hop_distance": d["hop_distance"],
                    })

                # Calculate projected risk reduction for this dependent
                dep_risk_res = await RiskEngine.assess_obligation(session, dep_obj.id)
                dep_current_risk = dep_risk_res.risk_score if dep_risk_res else 0.5
                dep_projected_risk = max(0.10, dep_current_risk - 0.40) if not remaining_blockers else dep_current_risk

                affected_obligations.append({
                    "obligation_id": dep_obj.id,
                    "action": dep_obj.action,
                    "owner": dep_obj.owner,
                    "current_risk": dep_current_risk,
                    "projected_risk": dep_projected_risk,
                    "risk_reduced": round(dep_current_risk - dep_projected_risk, 3),
                    "hop_distance": d["hop_distance"],
                })

            explanation = (
                f"Simulated completion of '{target.action}'. "
                f"Projected to immediately unblock {len(unblocked_obligations)} downstream obligation(s) "
                f"and reduce risk across {len(affected_obligations)} connected commitment(s)."
            )

        elif action == SimulationActionType.RESOLVE_BLOCKER:
            simulated_completed_ids.add(target.id)
            projected_target_status = ObligationStatus.CONFIRMED.value if target.status == ObligationStatus.BLOCKED else current_state["status"]
            projected_target_risk = max(0.15, current_risk_score - 0.50)

            # Check direct dependents
            direct_deps = await GraphService.get_dependents(session, target.id)
            for dep in direct_deps:
                dep_blockers = await GraphService.get_blockers(session, dep.id)
                remaining = [b for b in dep_blockers if b.obligation_id != target.id and b.status != ObligationStatus.COMPLETED]
                if not remaining and dep.status == ObligationStatus.BLOCKED:
                    unblocked_obligations.append({
                        "obligation_id": dep.id,
                        "action": dep.action,
                        "owner": dep.owner,
                        "previous_status": dep.status.value if hasattr(dep.status, "value") else str(dep.status),
                        "projected_status": ObligationStatus.CONFIRMED.value,
                        "hop_distance": 1,
                    })

            explanation = f"Simulated resolving blocker '{target.action}', unblocking {len(unblocked_obligations)} dependent obligation(s)."

        elif action == SimulationActionType.ASSIGN_OWNER:
            new_owner = params.get("new_owner", "Assigned Lead")
            projected_target_status = ObligationStatus.CONFIRMED.value if target.status == ObligationStatus.DETECTED else current_state["status"]
            projected_target_risk = max(0.10, current_risk_score - 0.25)
            explanation = f"Simulated assigning owner '{new_owner}' to '{target.action}'. Reduces ambiguity risk by ~25%."

        elif action == SimulationActionType.CONFIRM_EVIDENCE:
            projected_target_status = ObligationStatus.COMPLETED.value
            projected_target_risk = 0.0
            explanation = f"Simulated confirming completion evidence for '{target.action}'. Transitions obligation to COMPLETED and clears prerequisite blocks."

        elif action == SimulationActionType.REMOVE_DEPENDENCY:
            projected_target_status = ObligationStatus.CONFIRMED.value if target.status == ObligationStatus.BLOCKED else current_state["status"]
            projected_target_risk = max(0.15, current_risk_score - 0.40)
            explanation = f"Simulated decoupling dependency link on '{target.action}'. Frees obligation from prerequisite blockage."

        # Compute overall risk delta
        risk_delta = round(projected_target_risk - current_risk_score, 3)

        projected_state = {
            "obligation_id": target.id,
            "action": target.action,
            "owner": target.owner,
            "status": projected_target_status,
            "risk_score": projected_target_risk,
            "unblocked_count": len(unblocked_obligations),
        }

        return ResolutionSimulationResponse(
            simulated_action=action,
            target_obligation_id=target.id,
            current_state=current_state,
            projected_state=projected_state,
            affected_obligations=affected_obligations,
            risk_delta=risk_delta,
            unblocked_obligations=unblocked_obligations,
            newly_at_risk_obligations=[],
            explanation=explanation,
            is_simulation_marker=True,
            simulated_at=utc_now(),
        )
