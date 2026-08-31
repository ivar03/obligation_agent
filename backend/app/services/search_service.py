"""
Phase 18 Workspace-Scoped Global Search Service.

Searches across obligations, people, events, decision plans, interventions,
executions, and evidence with multi-tenant workspace isolation.
"""

from typing import List, Dict, Any, Optional
from sqlalchemy import select, or_, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.obligation import Obligation, Intervention, Evidence, IngestedEventRecord
from app.models.decision import DecisionPlan
from app.models.execution import ExecutionRecord
from app.models.auth import User, WorkspaceMembership


class SearchService:
    """
    Unified multi-entity workspace search engine.
    """

    @classmethod
    async def global_search(
        cls,
        session: AsyncSession,
        workspace_id: str,
        query: str,
        entity_types: Optional[List[str]] = None,
        status_filter: Optional[str] = None,
        owner_filter: Optional[str] = None,
        limit: int = 30,
    ) -> Dict[str, Any]:
        term = f"%{query.strip().lower()}%" if query else "%"
        active_types = set(entity_types) if entity_types else {
            "obligations", "people", "events", "decisions", "executions", "evidence"
        }

        results: Dict[str, List[Dict[str, Any]]] = {
            "obligations": [],
            "people": [],
            "events": [],
            "decisions": [],
            "executions": [],
            "evidence": [],
        }

        # 1. Obligations
        if "obligations" in active_types:
            stmt_ob = select(Obligation).where(
                and_(
                    Obligation.workspace_id == workspace_id,
                    or_(
                        Obligation.action.ilike(term),
                        Obligation.owner.ilike(term),
                        Obligation.beneficiary.ilike(term),
                    )
                )
            )
            if status_filter:
                stmt_ob = stmt_ob.where(Obligation.status == status_filter)
            if owner_filter:
                stmt_ob = stmt_ob.where(Obligation.owner.ilike(f"%{owner_filter}%"))
            obs = (await session.execute(stmt_ob.limit(limit))).scalars().all()
            results["obligations"] = [
                {
                    "id": o.id,
                    "action": o.action,
                    "owner": o.owner,
                    "status": o.status.value,
                    "priority": getattr(o, "priority", "MEDIUM"),
                    "deadline": o.deadline.isoformat() if o.deadline else None,
                    "url": f"/obligations/{o.id}",
                }
                for o in obs
            ]

        # 2. People (Workspace Members)
        if "people" in active_types:
            stmt_mem = (
                select(User, WorkspaceMembership.role)
                .join(WorkspaceMembership, User.id == WorkspaceMembership.user_id)
                .where(
                    and_(
                        WorkspaceMembership.workspace_id == workspace_id,
                        or_(
                            User.display_name.ilike(term),
                            User.email.ilike(term),
                        )
                    )
                )
            )
            people = (await session.execute(stmt_mem.limit(limit))).all()
            results["people"] = [
                {
                    "id": u.id,
                    "display_name": u.display_name,
                    "email": u.email,
                    "role": r.value if hasattr(r, "value") else str(r),
                }
                for u, r in people
            ]

        # 3. Events
        if "events" in active_types:
            stmt_ev = select(IngestedEventRecord).where(
                and_(
                    IngestedEventRecord.workspace_id == workspace_id,
                    or_(
                        IngestedEventRecord.content.ilike(term),
                        IngestedEventRecord.sender.ilike(term),
                        IngestedEventRecord.source_ref.ilike(term),
                    )
                )
            )
            evs = (await session.execute(stmt_ev.limit(limit))).scalars().all()
            results["events"] = [
                {
                    "id": e.id,
                    "provider": e.provider,
                    "sender": e.sender,
                    "content_snippet": (e.content or "")[:120],
                    "received_at": e.received_at.isoformat(),
                    "correlated_obligation_id": e.correlated_obligation_id,
                    "url": f"/events/{e.id}",
                }
                for e in evs
            ]

        # 4. Decision Plans
        if "decisions" in active_types:
            stmt_dp = select(DecisionPlan).where(
                and_(
                    DecisionPlan.workspace_id == workspace_id,
                    or_(
                        DecisionPlan.primary_objective.ilike(term),
                        DecisionPlan.target_obligation_id.ilike(term),
                    )
                )
            )
            dps = (await session.execute(stmt_dp.limit(limit))).scalars().all()
            results["decisions"] = [
                {
                    "id": d.id,
                    "target_obligation_id": d.target_obligation_id,
                    "status": d.status.value,
                    "primary_objective": d.primary_objective,
                    "overall_risk": d.overall_risk,
                    "urgency": d.overall_urgency,
                    "url": f"/intelligence/decisions/{d.id}",
                }
                for d in dps
            ]

        # 5. Executions
        if "executions" in active_types:
            stmt_ex = select(ExecutionRecord).where(
                and_(
                    ExecutionRecord.workspace_id == workspace_id,
                    or_(
                        ExecutionRecord.provider_execution_ref.ilike(term),
                        ExecutionRecord.idempotency_key.ilike(term),
                    )
                )
            )
            exs = (await session.execute(stmt_ex.limit(limit))).scalars().all()
            results["executions"] = [
                {
                    "id": ex.id,
                    "decision_plan_id": ex.decision_plan_id,
                    "provider": ex.provider,
                    "status": ex.status.value,
                    "provider_ref": ex.provider_execution_ref,
                    "url": f"/intelligence/execution/{ex.id}",
                }
                for ex in exs
            ]

        # 6. Evidence
        if "evidence" in active_types:
            stmt_evi = select(Evidence).where(
                and_(
                    Evidence.workspace_id == workspace_id,
                    or_(
                        Evidence.content.ilike(term),
                        Evidence.actor.ilike(term),
                        Evidence.source_ref.ilike(term),
                    )
                )
            )
            evis = (await session.execute(stmt_evi.limit(limit))).scalars().all()
            results["evidence"] = [
                {
                    "id": ev.id,
                    "obligation_id": ev.obligation_id,
                    "content_snippet": (ev.content or "")[:120],
                    "status": ev.correlation_status.value,
                    "actor": ev.actor,
                    "url": f"/obligations/{ev.obligation_id}",
                }
                for ev in evis
            ]

        total = sum(len(items) for items in results.values())
        return {
            "query": query,
            "workspace_id": workspace_id,
            "total_matches": total,
            "results": results,
        }
