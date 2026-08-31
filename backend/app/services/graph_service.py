from datetime import datetime, timezone
from typing import List, Optional, Set, Dict, Any, Tuple
from sqlalchemy import select, or_, and_
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException, status

from app.core.logging import logger
from app.core.status_machine import (
    ObligationStatus,
    ObligationType,
    EdgeType,
    validate_status_transition,
)
from app.models.obligation import Obligation, ObligationEdge
from app.schemas.obligation import (
    ObligationResponse,
    ObligationEdgeCreate,
    ObligationEdgeResponse,
    ObligationGraphResponse,
    BlockerDetail,
    BlockReason,
)


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def is_overdue_by_date(obligation: Obligation) -> bool:
    if obligation.status in [ObligationStatus.COMPLETED, ObligationStatus.CANCELLED]:
        return False
    if obligation.status == ObligationStatus.OVERDUE:
        return True
    if obligation.deadline:
        now = utc_now()
        deadline_tz = obligation.deadline
        if deadline_tz.tzinfo is None:
            deadline_tz = deadline_tz.replace(tzinfo=timezone.utc)
        return deadline_tz < now
    return False


class DependencyCycleError(Exception):
    """Raised when a proposed DEPENDS_ON edge creates a dependency cycle."""
    pass


class GraphService:
    """
    Dedicated graph service providing edge validation, cycle prevention,
    dependency traversals, and authoritative status propagation across obligations.
    """

    @staticmethod
    async def detect_dependency_cycle(session: AsyncSession, from_id: str, to_id: str) -> bool:
        """
        Determines if adding `from_id` DEPENDS_ON `to_id` would create a cycle.
        A cycle occurs if `from_id` is reachable from `to_id` by following outgoing DEPENDS_ON edges.
        """
        if from_id == to_id:
            return True

        visited: Set[str] = set()
        queue: List[str] = [to_id]

        while queue:
            current = queue.pop(0)
            if current == from_id:
                return True
            if current in visited:
                continue
            visited.add(current)

            # Query all obligations that `current` depends on
            stmt = select(ObligationEdge.to_obligation_id).where(
                and_(
                    ObligationEdge.from_obligation_id == current,
                    ObligationEdge.edge_type == EdgeType.DEPENDS_ON
                )
            )
            result = await session.execute(stmt)
            next_nodes = result.scalars().all()
            for nxt in next_nodes:
                if nxt not in visited:
                    queue.append(nxt)

        return False

    @staticmethod
    async def create_edge(session: AsyncSession, data: ObligationEdgeCreate, workspace_id: str = "ws-default") -> ObligationEdgeResponse:
        from_id = data.from_obligation_id
        to_id = data.to_obligation_id
        edge_type = data.edge_type

        # 1. Self-reference check
        if from_id == to_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Self-referencing relationship not allowed: An obligation cannot depend on or link to itself.",
            )

        # 2. Verify both obligations exist and belong to the same workspace
        from_ob = await session.get(Obligation, from_id)
        to_ob = await session.get(Obligation, to_id)
        if not from_ob or not to_ob:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="One or both obligation records not found.",
            )
        if from_ob.workspace_id != to_ob.workspace_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot link obligations across different workspaces.",
            )

        # 3. Duplicate check
        dup_stmt = select(ObligationEdge).where(
            and_(
                ObligationEdge.from_obligation_id == from_id,
                ObligationEdge.to_obligation_id == to_id,
                ObligationEdge.edge_type == edge_type,
            )
        )
        dup_res = await session.execute(dup_stmt)
        if dup_res.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"This {edge_type.value} relationship edge already exists.",
            )

        # 4. Dependency cycle check for DEPENDS_ON
        if edge_type == EdgeType.DEPENDS_ON:
            has_cycle = await GraphService.detect_dependency_cycle(session, from_id, to_id)
            if has_cycle:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Cannot create dependency: '{from_id}' -> '{to_id}' would create an invalid dependency cycle.",
                )

        # 5. Insert edge
        edge = ObligationEdge(
            workspace_id=from_ob.workspace_id,
            from_obligation_id=from_id,
            to_obligation_id=to_id,
            edge_type=edge_type,
        )
        session.add(edge)
        await session.flush()
        await session.refresh(edge)

        from app.services.audit_service import AuditService
        from app.core.status_machine import AuditAction
        await AuditService.record_mutation(
            session=session,
            workspace_id=from_ob.workspace_id,
            action=AuditAction.EDGE_CREATED,
            actor_user_id=None,
            actor_role=None,
            entity_type="edge",
            entity_id=edge.id,
            after_state={
                "from_obligation_id": from_id,
                "to_obligation_id": to_id,
                "edge_type": edge_type.value,
            },
            reason="Dependency / linked edge created",
        )

        logger.info(f"GraphEdge created in workspace [{from_ob.workspace_id}]: [{from_id}] --{edge_type.value}--> [{to_id}]")

        # 6. If DEPENDS_ON, evaluate blocker state for from_obligation
        if edge_type == EdgeType.DEPENDS_ON:
            await GraphService.evaluate_and_propagate(session, from_id)

        return ObligationEdgeResponse.model_validate(edge)

    @staticmethod
    async def remove_edge(session: AsyncSession, edge_id: str, workspace_id: Optional[str] = None) -> bool:
        edge = await session.get(ObligationEdge, edge_id)
        if not edge:
            return False
        if workspace_id and edge.workspace_id != workspace_id:
            return False

        from_id = edge.from_obligation_id
        edge_type = edge.edge_type
        ws_id = edge.workspace_id

        await session.delete(edge)
        await session.flush()

        from app.services.audit_service import AuditService
        from app.core.status_machine import AuditAction
        await AuditService.record_mutation(
            session=session,
            workspace_id=ws_id,
            action=AuditAction.EDGE_DELETED,
            actor_user_id=None,
            actor_role=None,
            entity_type="edge",
            entity_id=edge_id,
            before_state={
                "from_obligation_id": from_id,
                "edge_type": edge_type.value,
            },
            reason="Graph edge deleted",
        )

        logger.info(f"GraphEdge deleted: {edge_id}")

        # If it was a dependency, re-evaluate dependent
        if edge_type == EdgeType.DEPENDS_ON:
            await GraphService.evaluate_and_propagate(session, from_id)

        return True

    @staticmethod
    async def get_dependencies(session: AsyncSession, obligation_id: str) -> List[Obligation]:
        """Returns all obligations that `obligation_id` depends on (prerequisites)."""
        stmt = (
            select(Obligation)
            .join(ObligationEdge, ObligationEdge.to_obligation_id == Obligation.id)
            .where(
                and_(
                    ObligationEdge.from_obligation_id == obligation_id,
                    ObligationEdge.edge_type == EdgeType.DEPENDS_ON,
                )
            )
        )
        result = await session.execute(stmt)
        return list(result.scalars().all())

    @staticmethod
    async def get_dependents(session: AsyncSession, obligation_id: str) -> List[Obligation]:
        """Returns all obligations that depend on `obligation_id` (dependents)."""
        stmt = (
            select(Obligation)
            .join(ObligationEdge, ObligationEdge.from_obligation_id == Obligation.id)
            .where(
                and_(
                    ObligationEdge.to_obligation_id == obligation_id,
                    ObligationEdge.edge_type == EdgeType.DEPENDS_ON,
                )
            )
        )
        result = await session.execute(stmt)
        return list(result.scalars().all())

    @staticmethod
    async def get_linked_obligations(session: AsyncSession, obligation_id: str) -> List[Obligation]:
        """Returns all obligations linked symmetrically via LINKED edge."""
        stmt = (
            select(Obligation)
            .join(
                ObligationEdge,
                or_(
                    and_(ObligationEdge.to_obligation_id == Obligation.id, ObligationEdge.from_obligation_id == obligation_id),
                    and_(ObligationEdge.from_obligation_id == Obligation.id, ObligationEdge.to_obligation_id == obligation_id),
                ),
            )
            .where(
                and_(
                    ObligationEdge.edge_type == EdgeType.LINKED,
                    Obligation.id != obligation_id,
                )
            )
        )
        result = await session.execute(stmt)
        return list(result.scalars().all())

    @staticmethod
    async def get_blockers(session: AsyncSession, obligation_id: str) -> List[BlockerDetail]:
        """Identifies active blocking dependencies preventing `obligation_id` from proceeding."""
        dependencies = await GraphService.get_dependencies(session, obligation_id)
        blockers: List[BlockerDetail] = []

        for dep in dependencies:
            if dep.status == ObligationStatus.COMPLETED:
                continue

            reason = "Prerequisite obligation is not completed."
            if dep.status == ObligationStatus.OVERDUE or is_overdue_by_date(dep):
                reason = f"Prerequisite obligation by {dep.owner} is overdue."
            elif dep.status == ObligationStatus.BLOCKED:
                reason = f"Prerequisite obligation by {dep.owner} is itself blocked."
            elif dep.status == ObligationStatus.CANCELLED:
                reason = f"Prerequisite obligation by {dep.owner} was cancelled."

            blockers.append(
                BlockerDetail(
                    obligation_id=dep.id,
                    owner=dep.owner,
                    beneficiary=dep.beneficiary,
                    action=dep.action,
                    status=dep.status,
                    reason=reason,
                )
            )

        return blockers

    @staticmethod
    async def evaluate_and_propagate(
        session: AsyncSession, obligation_id: str, visited: Optional[Set[str]] = None
    ) -> None:
        """
        Authoritative domain evaluator for dependency-driven state propagation.
        Evaluates blocker state for `obligation_id` and cascades updates to dependents.
        """
        if visited is None:
            visited = set()

        if obligation_id in visited:
            return
        visited.add(obligation_id)

        target = await session.get(Obligation, obligation_id)
        if not target or target.status in [ObligationStatus.COMPLETED, ObligationStatus.CANCELLED]:
            return

        blockers = await GraphService.get_blockers(session, obligation_id)

        if blockers:
            # Active blockers exist: target should be BLOCKED
            new_block_reason = {
                "blocked": True,
                "blocked_by": [b.model_dump() for b in blockers],
                "updated_at": utc_now().isoformat(),
            }
            target.block_reason = new_block_reason

            if target.status != ObligationStatus.BLOCKED:
                logger.info(
                    f"GraphPropagation: Obligation [{target.id}] ({target.owner}) transitioned "
                    f"from {target.status.value} -> BLOCKED (Blockers: {len(blockers)})"
                )
                target.status = ObligationStatus.BLOCKED

                # Append audit event to evidence
                current_ev = list(target.evidence or [])
                current_ev.append({
                    "type": "graph_transition",
                    "event": "OBLIGATION_BLOCKED",
                    "reason": f"Blocked by {len(blockers)} unresolved prerequisite(s).",
                    "recorded_at": utc_now().isoformat(),
                })
                target.evidence = current_ev

            await session.flush()

            # Cascade: notify obligations that depend on `target`
            dependents = await GraphService.get_dependents(session, obligation_id)
            for dep in dependents:
                await GraphService.evaluate_and_propagate(session, dep.id, visited)

        else:
            # No blockers exist
            if target.status == ObligationStatus.BLOCKED:
                logger.info(
                    f"GraphPropagation: Obligation [{target.id}] ({target.owner}) UNBLOCKED -> CONFIRMED"
                )
                target.status = ObligationStatus.CONFIRMED
                target.block_reason = None

                # Append audit event to evidence
                current_ev = list(target.evidence or [])
                current_ev.append({
                    "type": "graph_transition",
                    "event": "OBLIGATION_UNBLOCKED",
                    "reason": "All prerequisite dependencies have been satisfied.",
                    "recorded_at": utc_now().isoformat(),
                })
                target.evidence = current_ev

                await session.flush()

                # Cascade: re-evaluate dependents
                dependents = await GraphService.get_dependents(session, obligation_id)
                for dep in dependents:
                    await GraphService.evaluate_and_propagate(session, dep.id, visited)

    @staticmethod
    async def get_graph_for_obligation(
        session: AsyncSession, obligation_id: str, workspace_id: Optional[str] = None
    ) -> ObligationGraphResponse:
        """Returns a composite graph DTO for the obligation detail view."""
        from app.services.obligation_service import to_response_dto

        obligation = await session.get(Obligation, obligation_id)
        if not obligation or (workspace_id and obligation.workspace_id != workspace_id):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Obligation with ID '{obligation_id}' not found.",
            )

        dependencies = await GraphService.get_dependencies(session, obligation_id)
        dependents = await GraphService.get_dependents(session, obligation_id)
        linked = await GraphService.get_linked_obligations(session, obligation_id)
        blockers = await GraphService.get_blockers(session, obligation_id)

        # Calculate which dependents would be unblocked if `obligation` completed
        unblocks: List[ObligationResponse] = []
        for dep in dependents:
            dep_blockers = await GraphService.get_blockers(session, dep.id)
            # If `obligation` is the sole blocker for `dep`
            if len(dep_blockers) == 1 and dep_blockers[0].obligation_id == obligation_id:
                unblocks.append(to_response_dto(dep))

        return ObligationGraphResponse(
            obligation=to_response_dto(obligation),
            dependencies=[to_response_dto(d) for d in dependencies],
            dependents=[to_response_dto(d) for d in dependents],
            linked=[to_response_dto(l) for l in linked],
            blockers=blockers,
            is_blocked=obligation.status == ObligationStatus.BLOCKED or len(blockers) > 0,
            unblocks_on_completion=unblocks,
        )

    # ==============================================================================
    # PHASE 14: INTELLIGENCE & ROOT-CAUSE GRAPH TRAVERSALS
    # ==============================================================================

    @staticmethod
    async def get_upstream_chain(
        session: AsyncSession, obligation_id: str, max_depth: int = 20
    ) -> List[Dict[str, Any]]:
        """
        Traverses upstream along DEPENDS_ON edges to find all transitive prerequisites.
        Returns a list of dicts with obligation, hop_distance, and path from source.
        LINKED edges are strictly excluded from blocker/dependency chains.
        """
        results: List[Dict[str, Any]] = []
        visited: Set[str] = {obligation_id}
        queue: List[Tuple[str, int, List[str]]] = [(obligation_id, 0, [obligation_id])]

        while queue:
            curr_id, dist, path = queue.pop(0)
            if dist >= max_depth:
                continue

            # Fetch direct dependencies
            deps = await GraphService.get_dependencies(session, curr_id)
            for dep in deps:
                if dep.id not in visited:
                    visited.add(dep.id)
                    new_dist = dist + 1
                    new_path = path + [dep.id]
                    results.append({
                        "obligation": dep,
                        "hop_distance": new_dist,
                        "path": new_path,
                    })
                    queue.append((dep.id, new_dist, new_path))

        return results

    @staticmethod
    async def get_downstream_impact(
        session: AsyncSession, obligation_id: str, max_depth: int = 20
    ) -> List[Dict[str, Any]]:
        """
        Traverses downstream along inverse DEPENDS_ON edges to identify all obligations
        affected if `obligation_id` is delayed, blocked, or altered.
        """
        results: List[Dict[str, Any]] = []
        visited: Set[str] = {obligation_id}
        queue: List[Tuple[str, int, List[str]]] = [(obligation_id, 0, [obligation_id])]

        while queue:
            curr_id, dist, path = queue.pop(0)
            if dist >= max_depth:
                continue

            dependents = await GraphService.get_dependents(session, curr_id)
            for dep in dependents:
                if dep.id not in visited:
                    visited.add(dep.id)
                    new_dist = dist + 1
                    new_path = path + [dep.id]
                    results.append({
                        "obligation": dep,
                        "hop_distance": new_dist,
                        "path": new_path,
                    })
                    queue.append((dep.id, new_dist, new_path))

        return results

    @staticmethod
    async def get_root_blockers(
        session: AsyncSession, obligation_id: str
    ) -> List[Dict[str, Any]]:
        """
        Recursively identifies the ultimate root-cause blocker obligations.
        A root blocker is an uncompleted upstream prerequisite that either has no blockers
        itself or is the originating failure node (e.g. OVERDUE, cancelled, or lacking evidence).
        """
        upstream = await GraphService.get_upstream_chain(session, obligation_id)
        if not upstream:
            return []

        # Find all uncompleted upstream obligations
        uncompleted = [item for item in upstream if item["obligation"].status != ObligationStatus.COMPLETED]
        if not uncompleted:
            return []

        root_blockers: List[Dict[str, Any]] = []
        for item in uncompleted:
            dep_obj: Obligation = item["obligation"]
            # Check if this node has any uncompleted prerequisites itself
            dep_blockers = await GraphService.get_blockers(session, dep_obj.id)
            if not dep_blockers:
                # Leaf uncompleted prerequisite -> definitely a root blocker
                root_blockers.append(item)
            else:
                # If all its blockers are completed or none exist, it is a root
                unresolved_sub_blockers = [
                    b for b in dep_blockers if b.status != ObligationStatus.COMPLETED
                ]
                if not unresolved_sub_blockers:
                    root_blockers.append(item)

        # If cyclic/complex topology returned empty but uncompleted exist, pick deepest uncompleted
        if not root_blockers and uncompleted:
            max_dist = max(item["hop_distance"] for item in uncompleted)
            root_blockers = [item for item in uncompleted if item["hop_distance"] == max_dist]

        return root_blockers

    @staticmethod
    async def get_dependency_depth(session: AsyncSession, obligation_id: str) -> int:
        """Computes the maximum depth of the upstream dependency tree."""
        upstream = await GraphService.get_upstream_chain(session, obligation_id)
        if not upstream:
            return 0
        return max(item["hop_distance"] for item in upstream)

    @staticmethod
    async def get_impact_summary(
        session: AsyncSession, obligation_id: str
    ) -> Dict[str, Any]:
        """
        Aggregates downstream blast radius metrics for an obligation.
        """
        direct_dependents = await GraphService.get_dependents(session, obligation_id)
        downstream = await GraphService.get_downstream_impact(session, obligation_id)

        all_downstream_objs = [d["obligation"] for d in downstream]
        affected_owners = list({d.owner for d in all_downstream_objs if d.owner})
        affected_deadlines = [d.deadline.isoformat() for d in all_downstream_objs if d.deadline]
        max_depth = max([d["hop_distance"] for d in downstream], default=0)

        high_risk_count = sum(
            1 for d in all_downstream_objs
            if d.status in (ObligationStatus.OVERDUE, ObligationStatus.BLOCKED)
        )

        return {
            "obligation_id": obligation_id,
            "direct_dependents_count": len(direct_dependents),
            "total_downstream_dependents_count": len(downstream),
            "maximum_dependency_depth": max_depth,
            "affected_owners": affected_owners,
            "affected_deadlines": affected_deadlines,
            "affected_high_risk_obligations": high_risk_count,
            "downstream_items": [
                {
                    "obligation_id": d["obligation"].id,
                    "action": d["obligation"].action,
                    "owner": d["obligation"].owner,
                    "status": d["obligation"].status.value if hasattr(d["obligation"].status, "value") else str(d["obligation"].status),
                    "hop_distance": d["hop_distance"],
                }
                for d in downstream
            ],
        }

