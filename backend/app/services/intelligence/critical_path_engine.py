from datetime import datetime, timezone
from typing import List, Optional, Dict, Any, Set
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import logger
from app.core.status_machine import ObligationStatus, EdgeType
from app.models.obligation import Obligation, ObligationEdge
from app.schemas.intelligence import CriticalPathResponse, CriticalPathItem
from app.services.graph_service import GraphService
from app.services.risk_engine import RiskEngine


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class CriticalPathEngine:
    """
    Computes the deterministic Critical Path across obligation dependency DAGs.
    Identifies the highest-risk / highest-impact dependency path leading to or from an obligation.
    """

    @classmethod
    async def compute_critical_path(
        cls, session: AsyncSession, obligation_id: str, workspace_id: Optional[str] = None
    ) -> CriticalPathResponse:
        obligation = await session.get(Obligation, obligation_id)
        if not obligation or (workspace_id and obligation.workspace_id != workspace_id):
            raise ValueError(f"Obligation with ID '{obligation_id}' not found.")

        # 1. Find all upstream paths leading to this obligation
        # We perform a recursive path exploration from leaf roots to `obligation_id`
        upstream_items = await GraphService.get_upstream_chain(session, obligation_id)

        if not upstream_items:
            # Single-node path
            risk_ass = await RiskEngine.assess_obligation(session, obligation_id)
            node_risk = risk_ass.risk_score if risk_ass else 0.0
            return CriticalPathResponse(
                obligation_id=obligation.id,
                critical_path=[obligation.id],
                critical_path_length=1,
                critical_path_risk=node_risk,
                root_blocker_id=None,
                root_blocker_owner=None,
                root_blocker_action=None,
                path_details=[
                    CriticalPathItem(
                        obligation_id=obligation.id,
                        owner=obligation.owner or "Unassigned",
                        action=obligation.action,
                        status=obligation.status.value if hasattr(obligation.status, "value") else str(obligation.status),
                        deadline=obligation.deadline.isoformat() if obligation.deadline else None,
                        risk_score=node_risk,
                        is_root_blocker=False,
                        hop_from_root=0,
                    )
                ],
                explanation=f"Obligation '{obligation.action}' has no upstream dependencies; critical path is self-contained.",
                evaluated_at=utc_now(),
            )

        # Build paths from roots to `obligation_id` with bounded depth and path limit
        paths: List[List[str]] = []
        max_paths = 50
        max_depth = 20

        async def find_paths(curr_id: str, current_path: List[str], depth: int = 0):
            if len(paths) >= max_paths or depth >= max_depth:
                full_p = list(reversed(current_path))
                paths.append(full_p)
                return

            deps = await GraphService.get_dependencies(session, curr_id)
            if not deps:
                # Leaf node reached: reverse path so root is at index 0 and target is at end
                full_p = list(reversed(current_path))
                paths.append(full_p)
                return

            for d in deps:
                if d.id not in current_path and len(paths) < max_paths:
                    await find_paths(d.id, current_path + [d.id], depth + 1)

        await find_paths(obligation_id, [obligation_id])

        if not paths:
            paths = [[u["obligation"].id for u in upstream_items] + [obligation_id]]

        # Evaluate each path to find the highest-risk / highest-impact critical path
        best_path: List[str] = paths[0]
        best_score: float = -1.0

        path_details_map: Dict[str, CriticalPathItem] = {}

        for p in paths:
            # Path score considers: path length, count of overdue/blocked nodes, average risk
            node_risks: List[float] = []
            penalty: float = 0.0

            for idx, node_id in enumerate(p):
                if node_id not in path_details_map:
                    node_obj = await session.get(Obligation, node_id)
                    if node_obj:
                        risk_res = await RiskEngine.assess_obligation(session, node_id)
                        r_score = risk_res.risk_score if risk_res else 0.0
                        is_root = (idx == 0 and len(p) > 1 and node_obj.status != ObligationStatus.COMPLETED)
                        path_details_map[node_id] = CriticalPathItem(
                            obligation_id=node_obj.id,
                            owner=node_obj.owner or "Unassigned",
                            action=node_obj.action,
                            status=node_obj.status.value if hasattr(node_obj.status, "value") else str(node_obj.status),
                            deadline=node_obj.deadline.isoformat() if node_obj.deadline else None,
                            risk_score=r_score,
                            is_root_blocker=is_root,
                            hop_from_root=idx,
                        )
                    else:
                        node_risks.append(0.0)

                item = path_details_map.get(node_id)
                if item:
                    node_risks.append(item.risk_score)
                    if item.status == "OVERDUE":
                        penalty += 0.5
                    elif item.status == "BLOCKED":
                        penalty += 0.3

            avg_risk = sum(node_risks) / len(node_risks) if node_risks else 0.0
            path_score = (0.4 * (len(p) / 10.0)) + (0.4 * avg_risk) + (0.2 * min(1.0, penalty))

            if path_score > best_score:
                best_score = path_score
                best_path = p

        # Assemble path details for best path
        chosen_details: List[CriticalPathItem] = []
        root_node_item: Optional[CriticalPathItem] = None

        for idx, nid in enumerate(best_path):
            item = path_details_map.get(nid)
            if item:
                item_copy = item.model_copy()
                item_copy.hop_from_root = idx
                if idx == 0 and len(best_path) > 1 and item.status != "COMPLETED":
                    item_copy.is_root_blocker = True
                    root_node_item = item_copy
                chosen_details.append(item_copy)

        root_id = root_node_item.obligation_id if root_node_item else None
        root_owner = root_node_item.owner if root_node_item else None
        root_action = root_node_item.action if root_node_item else None

        avg_path_risk = sum(d.risk_score for d in chosen_details) / len(chosen_details) if chosen_details else 0.0
        capped_path_risk = max(0.0, min(1.0, round(avg_path_risk, 3)))

        if root_node_item:
            explanation = (
                f"Critical dependency path of length {len(best_path)} identified. "
                f"Root prerequisite is '{root_action}' owned by {root_owner} (status: {root_node_item.status})."
            )
        else:
            explanation = f"Critical dependency path of length {len(best_path)} evaluated with average risk score {capped_path_risk}."

        return CriticalPathResponse(
            obligation_id=obligation.id,
            critical_path=best_path,
            critical_path_length=len(best_path),
            critical_path_risk=capped_path_risk,
            root_blocker_id=root_id,
            root_blocker_owner=root_owner,
            root_blocker_action=root_action,
            path_details=chosen_details,
            explanation=explanation,
            evaluated_at=utc_now(),
        )
