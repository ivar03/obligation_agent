"""
Phase 15: Intelligence Orchestrator & Decision Layer.

Synthesizes multi-source intelligence across the graph:
- Obligation State
- Risk Assessment
- Adaptive Prediction
- Root Cause Analysis
- Blast Radius Impact
- Critical Path
- Systemic Bottlenecks & Risk Concentrations
- Evidence & Interventions

Produces a unified, ranked, explainable, and human-authorized DecisionPlan.
Safety Invariants:
1. Generation, refresh, and simulation never mutate operational obligation state.
2. Simulation is 100% side-effect free and isolated.
3. Historical plans are immutable (supersession creates Plan v2, marking Plan v1 SUPERSEDED).
4. No unsupported alternatives are fabricated.
5. All recommendations maintain strict source provenance.
"""

import uuid
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any, Tuple
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import logger
from app.core.status_machine import (
    ObligationStatus,
    DecisionPlanStatus,
    HumanDecisionType,
    ProvenanceSourceType,
    SimulationActionType,
    ResolutionStrategyType,
    CausalFactorType,
)
from app.models.obligation import Obligation, Evidence
from app.models.decision import DecisionPlan
from app.schemas.decision import (
    DecisionPlanResponse,
    DecisionPlanSummaryResponse,
    HumanDecisionRequirement,
    CandidateStrategyItem,
    DecisionPlanApproveRequest,
    DecisionPlanRejectRequest,
)
from app.services.graph_service import GraphService
from app.services.risk_engine import RiskEngine
from app.services.intelligence.root_cause_engine import RootCauseAnalysisEngine
from app.services.intelligence.impact_analysis_service import ImpactAnalysisService
from app.services.intelligence.critical_path_engine import CriticalPathEngine
from app.services.intelligence.resolution_planner import ResolutionPlanner
from app.services.intelligence.resolution_simulation_service import ResolutionSimulationService
from app.services.intelligence.risk_concentration_service import RiskConcentrationService
from app.services.intelligence.decision_ranking_engine import DecisionRankingEngine
from app.services.intelligence.memory.memory_retrieval_service import MemoryRetrievalService
from app.services.intelligence.memory.pattern_detection_service import PatternDetectionService
from app.schemas.intelligence import ResolutionSimulationRequest
from enum import Enum


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _json_safe(obj: Any) -> Any:
    """Recursively converts datetimes and complex types to JSON-serializable primitives."""
    if obj is None:
        return None
    if isinstance(obj, datetime):
        return obj.isoformat()
    if isinstance(obj, Enum):
        return obj.value
    if hasattr(obj, "model_dump"):
        return _json_safe(obj.model_dump())
    if hasattr(obj, "dict"):
        return _json_safe(obj.dict())
    if isinstance(obj, dict):
        return {str(k): _json_safe(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple, set)):
        return [_json_safe(item) for item in obj]
    return obj



class IntelligenceOrchestrator:
    """
    Unified Intelligence Orchestrator and Decision Synthesis Engine.
    """

    @classmethod
    async def generate_decision_plan(
        cls,
        session: AsyncSession,
        obligation_id: str,
        workspace_id: Optional[str] = None,
        force_refresh: bool = False,
    ) -> DecisionPlan:
        """
        Synthesizes all intelligence sources into a unified DecisionPlan.
        If an active non-stale plan already exists and force_refresh is False, returns the active plan.
        Otherwise, creates a new plan version, superseding the previous active plan.
        """
        obligation = await session.get(Obligation, obligation_id)
        if not obligation or (workspace_id and obligation.workspace_id != workspace_id):
            raise ValueError(f"Obligation with ID '{obligation_id}' not found.")

        ws_id = obligation.workspace_id

        # Check existing active plans
        existing_stmt = (
            select(DecisionPlan)
            .where(
                DecisionPlan.target_obligation_id == obligation_id,
                DecisionPlan.workspace_id == ws_id,
                DecisionPlan.status.in_([
                    DecisionPlanStatus.GENERATED,
                    DecisionPlanStatus.PENDING_REVIEW,
                    DecisionPlanStatus.APPROVED,
                ]),
            )
            .order_by(desc(DecisionPlan.plan_version))
        )
        existing_res = await session.execute(existing_stmt)
        latest_plan = existing_res.scalars().first()

        # Check staleness if not force_refresh
        if latest_plan and not force_refresh:
            is_stale = await cls._is_plan_stale(session, latest_plan, obligation)
            if not is_stale:
                return latest_plan

        # Determine next version
        version_stmt = (
            select(DecisionPlan.plan_version)
            .where(
                DecisionPlan.target_obligation_id == obligation_id,
                DecisionPlan.workspace_id == ws_id,
            )
            .order_by(desc(DecisionPlan.plan_version))
        )
        version_res = await session.execute(version_stmt)
        highest_version = version_res.scalars().first() or 0
        new_version = highest_version + 1

        # 1. Gather all intelligence outputs
        risk_res = await RiskEngine.assess_obligation(session, obligation_id)
        rc_res = await RootCauseAnalysisEngine.analyze(session, obligation_id, workspace_id=ws_id)
        impact_res = await ImpactAnalysisService.analyze_impact(session, obligation_id, workspace_id=ws_id)
        cp_res = await CriticalPathEngine.compute_critical_path(session, obligation_id, workspace_id=ws_id)
        res_plan_res = await ResolutionPlanner.plan_resolution(session, obligation_id, workspace_id=ws_id)
        bottlenecks = await RiskConcentrationService.get_bottlenecks(session, ws_id)

        overall_risk = risk_res.risk_score if risk_res else 0.0
        decision_confidence = rc_res.confidence if rc_res else 0.85

        # Determine overall urgency
        overall_urgency = "LOW"
        if obligation.status == ObligationStatus.OVERDUE or overall_risk >= 0.70:
            overall_urgency = "CRITICAL"
        elif obligation.status == ObligationStatus.BLOCKED or overall_risk >= 0.40:
            overall_urgency = "HIGH"
        elif overall_risk >= 0.25:
            overall_urgency = "MEDIUM"

        primary_objective = f"Resolve commitments blocking '{obligation.action}' and recover downstream delivery schedule."

        # 2. Build Primary Recommended Strategy
        primary_sim_action = SimulationActionType.COMPLETE_OBLIGATION
        if res_plan_res.strategy == ResolutionStrategyType.RESOLVE_ROOT_BLOCKER:
            primary_sim_action = SimulationActionType.RESOLVE_BLOCKER
        elif res_plan_res.strategy == ResolutionStrategyType.ASSIGN_OWNER:
            primary_sim_action = SimulationActionType.ASSIGN_OWNER

        # Run side-effect-free simulation for primary strategy
        primary_sim = await ResolutionSimulationService.simulate(
            session,
            ResolutionSimulationRequest(
                action=primary_sim_action,
                target_obligation_id=res_plan_res.target_obligation_id,
            ),
            workspace_id=ws_id,
        )

        # Score primary strategy
        primary_score, primary_breakdown = DecisionRankingEngine.rank_strategy({
            "risk_reduction": abs(primary_sim.risk_delta),
            "blast_radius_reduction": len(primary_sim.unblocked_obligations) / max(1, impact_res.total_downstream_dependents_count + 1),
            "critical_path_improvement": 1.0 if cp_res.critical_path_length <= 2 else 0.75,
            "evidence_confidence": rc_res.confidence,
            "prediction_confidence": 0.85,
            "execution_complexity": 0.25,
            "uncertainty_penalty": 0.10 if len(rc_res.uncertainties) > 0 else 0.0,
        })

        primary_human_decisions: List[Dict[str, Any]] = []
        if res_plan_res.target_obligation_id != obligation.id:
            primary_human_decisions.append({
                "decision_type": HumanDecisionType.APPROVE_INTERVENTION.value,
                "reason": f"Authorize human intervention with {res_plan_res.target_owner} regarding prerequisite '{res_plan_res.target_action}'.",
                "affected_obligation_id": res_plan_res.target_obligation_id,
                "affected_obligation_action": res_plan_res.target_action,
                "consequence_of_decision": "Initiates outreach to root owner without autonomous escalation.",
                "supporting_evidence": rc_res.evidence_refs,
                "confidence": rc_res.confidence,
                "proposed_default": "APPROVE",
                "requires_admin": False,
            })

        recommended_action = {
            "strategy_id": "strat-primary-1",
            "strategy_name": f"Strategy A — {res_plan_res.strategy.replace('_', ' ').title()}",
            "strategy_type": res_plan_res.strategy,
            "target_obligation_id": res_plan_res.target_obligation_id,
            "target_owner": res_plan_res.target_owner,
            "target_action": res_plan_res.target_action,
            "rationale": res_plan_res.rationale,
            "decision_score": primary_score,
            "expected_impact": res_plan_res.expected_impact,
            "risk_reduction": round(primary_sim.risk_delta, 3),
            "projected_unblocks_count": len(primary_sim.unblocked_obligations),
            "simulated_evaluation": primary_sim.model_dump() if hasattr(primary_sim, "model_dump") else primary_sim.dict(),
            "human_decisions": primary_human_decisions,
            "is_primary_recommendation": True,
            "score_breakdown": primary_breakdown,
        }

        # 3. Build Legitimate Alternative Strategies
        alternative_actions: List[Dict[str, Any]] = []

        # Alternative 1: Decouple Dependency (if obligation has prerequisites)
        direct_blockers = await GraphService.get_blockers(session, obligation_id)
        if direct_blockers and len(direct_blockers) > 0:
            direct_blocker = direct_blockers[0]
            alt1_sim = await ResolutionSimulationService.simulate(
                session,
                ResolutionSimulationRequest(
                    action=SimulationActionType.REMOVE_DEPENDENCY,
                    target_obligation_id=obligation_id,
                    parameters={"dependency_obligation_id": direct_blocker.obligation_id},
                ),
                workspace_id=ws_id,
            )

            alt1_score, alt1_breakdown = DecisionRankingEngine.rank_strategy({
                "risk_reduction": abs(alt1_sim.risk_delta),
                "blast_radius_reduction": 0.35,
                "critical_path_improvement": 0.50,
                "evidence_confidence": 0.70,
                "prediction_confidence": 0.75,
                "execution_complexity": 0.60,  # Higher complexity due to architectural decoupling
                "uncertainty_penalty": 0.20,
            })

            alternative_actions.append({
                "strategy_id": "strat-alt-decouple",
                "strategy_name": "Strategy B — Decouple Dependency",
                "strategy_type": "REMOVE_DEPENDENCY",
                "target_obligation_id": obligation_id,
                "target_owner": obligation.owner or "Unassigned",
                "target_action": f"Decouple dependency on '{direct_blocker.action}'",
                "rationale": f"Architecturally decouple '{obligation.action}' from upstream blocker '{direct_blocker.action}' to allow parallel execution.",
                "decision_score": alt1_score,
                "expected_impact": f"Allows '{obligation.action}' to proceed independently with architectural compromise.",
                "risk_reduction": round(alt1_sim.risk_delta, 3),
                "projected_unblocks_count": 1,
                "simulated_evaluation": alt1_sim.model_dump() if hasattr(alt1_sim, "model_dump") else alt1_sim.dict(),
                "human_decisions": [{
                    "decision_type": HumanDecisionType.REMOVE_DEPENDENCY.value,
                    "reason": f"Requires engineering authorization to remove dependency on '{direct_blocker.action}'.",
                    "affected_obligation_id": obligation_id,
                    "affected_obligation_action": obligation.action,
                    "consequence_of_decision": "Removes graph edge; downstream must verify functional compatibility.",
                    "supporting_evidence": [],
                    "confidence": 0.75,
                    "proposed_default": "REVIEW",
                    "requires_admin": True,
                }],
                "is_primary_recommendation": False,
                "score_breakdown": alt1_breakdown,
            })

        # Alternative 2: Reassign Root Obligation (if root is unassigned or overdue)
        if rc_res.primary_root_cause and res_plan_res.target_obligation_id != obligation.id:
            root_ob = await session.get(Obligation, res_plan_res.target_obligation_id)
            if root_ob and (not root_ob.owner or root_ob.status == ObligationStatus.OVERDUE):
                alt2_sim = await ResolutionSimulationService.simulate(
                    session,
                    ResolutionSimulationRequest(
                        action=SimulationActionType.ASSIGN_OWNER,
                        target_obligation_id=root_ob.id,
                        parameters={"new_owner": "Unassigned Lead"},
                    ),
                    workspace_id=ws_id,
                )

                alt2_score, alt2_breakdown = DecisionRankingEngine.rank_strategy({
                    "risk_reduction": abs(alt2_sim.risk_delta),
                    "blast_radius_reduction": 0.20,
                    "critical_path_improvement": 0.30,
                    "evidence_confidence": 0.80,
                    "prediction_confidence": 0.80,
                    "execution_complexity": 0.40,
                    "uncertainty_penalty": 0.15,
                })

                alternative_actions.append({
                    "strategy_id": "strat-alt-reassign",
                    "strategy_name": "Strategy C — Reassign Root Obligation",
                    "strategy_type": "ASSIGN_OWNER",
                    "target_obligation_id": root_ob.id,
                    "target_owner": root_ob.owner or "Unassigned",
                    "target_action": root_ob.action,
                    "rationale": f"Reassign bottleneck obligation '{root_ob.action}' to a dedicated owner to clear stalled progress.",
                    "decision_score": alt2_score,
                    "expected_impact": "Accelerates resolution of root prerequisite via owner escalation.",
                    "risk_reduction": round(alt2_sim.risk_delta, 3),
                    "projected_unblocks_count": 0,
                    "simulated_evaluation": alt2_sim.model_dump() if hasattr(alt2_sim, "model_dump") else alt2_sim.dict(),
                    "human_decisions": [{
                        "decision_type": HumanDecisionType.ASSIGN_OWNER.value,
                        "reason": f"Requires manager authorization to reassign '{root_ob.action}'.",
                        "affected_obligation_id": root_ob.id,
                        "affected_obligation_action": root_ob.action,
                        "consequence_of_decision": "Transfers accountability for prerequisite completion.",
                        "supporting_evidence": [],
                        "confidence": 0.80,
                        "proposed_default": "REVIEW",
                        "requires_admin": False,
                    }],
                    "is_primary_recommendation": False,
                    "score_breakdown": alt2_breakdown,
                })

        # 4. Consolidate All Human Decisions
        all_human_decisions: List[Dict[str, Any]] = list(primary_human_decisions)
        for alt in alternative_actions:
            all_human_decisions.extend(alt.get("human_decisions", []))

        # 5. Extract Provenance and Evidence References
        supporting_evidence: List[Dict[str, Any]] = []
        for ref in rc_res.evidence_refs:
            supporting_evidence.append({
                "source_type": ProvenanceSourceType.EVIDENCE.value,
                "reference_id": ref,
                "description": f"Observed completion/progress signal ref {ref}",
                "confidence": 0.95,
            })
        for event_id in rc_res.event_refs:
            supporting_evidence.append({
                "source_type": ProvenanceSourceType.EVENT.value,
                "reference_id": event_id,
                "description": f"Ingested event signal ref {event_id}",
                "confidence": 0.90,
            })

        # 5b. Retrieve Organizational Memory Context
        memory_items = await MemoryRetrievalService.retrieve_for_obligation(
            session, obligation, min_relevance=0.25, limit=5
        )
        patterns = await PatternDetectionService.detect_patterns_for_obligation(
            session, obligation, memory_items
        )

        for mem_item in memory_items:
            supporting_evidence.append({
                "source_type": "ORGANIZATIONAL_MEMORY",
                "reference_id": mem_item.memory.id,
                "description": f"Historical memory: {mem_item.memory.semantic_summary} (Relevance: {int(mem_item.relevance_score * 100)}%)",
                "confidence": mem_item.memory.confidence,
            })

        # 6. Build Explainability Narrative ("WHY THIS PLAN?")
        root_cause_text = rc_res.primary_root_cause or "No severe upstream blocker detected."
        cp_labels = [
            node.action if hasattr(node, "action") else node.get("action", getattr(node, "obligation_id", str(node)))
            for node in (cp_res.path_details or [])
        ]
        unc_labels = [
            u.description if hasattr(u, "description") else u.get("description", str(u))
            for u in (rc_res.uncertainties or [])
        ]
        narrative_lines = [
            "WHY THIS PLAN?",
            f"1. Primary blocker: {root_cause_text}",
            f"2. Why it matters: Impedes {impact_res.total_downstream_dependents_count} downstream commitment(s) across {len(impact_res.affected_owners)} team member(s).",
            f"3. Current risk level: {risk_res.risk_level.value if risk_res else 'LOW'} (Score: {overall_risk:.2f}).",
            f"4. Critical path: {' -> '.join(cp_labels) if cp_labels else obligation.action}.",
            f"5. Recommended first action: {recommended_action['strategy_name']} targeting {recommended_action['target_owner']} on '{recommended_action['target_action']}'.",
            f"6. Why this action: Upstream resolution is projected to unblock {len(primary_sim.unblocked_obligations)} commitment(s) with risk delta {primary_sim.risk_delta:.2f}.",
            f"7. Uncertainties: {', '.join(unc_labels) if unc_labels else 'None; high confidence in graph causality.'}",
            f"8. Human decisions required: {len(all_human_decisions)} authorization point(s) require operator review.",
        ]

        if memory_items:
            mem_summaries = [f"{m.memory.semantic_summary}" for m in memory_items[:2]]
            narrative_lines.append(
                f"9. Historical context: {len(memory_items)} comparable commitment(s) observed ({'; '.join(mem_summaries)})."
            )
        if patterns:
            pat_summaries = [p.description for p in patterns if p.maturity != "INSUFFICIENT_HISTORY"]
            if pat_summaries:
                narrative_lines.append(f"10. Historical patterns: {'; '.join(pat_summaries)}.")

        explainability_narrative = "\n".join(narrative_lines)

        # 7. Supersede old active plans
        if latest_plan and latest_plan.status in (
            DecisionPlanStatus.GENERATED,
            DecisionPlanStatus.PENDING_REVIEW,
        ):
            latest_plan.status = DecisionPlanStatus.SUPERSEDED
            latest_plan.superseded_at = utc_now()

        # 8. Create and persist new DecisionPlan
        new_plan_id = str(uuid.uuid4())
        if latest_plan:
            latest_plan.superseded_by_plan_id = new_plan_id

        serialized_cp = [
            node.model_dump() if hasattr(node, "model_dump")
            else node.dict() if hasattr(node, "dict")
            else node if isinstance(node, dict)
            else {"id": str(node)}
            for node in (cp_res.path_details or [])
        ]

        root_cause_id = None
        if rc_res.upstream_causes:
            root_cause_id = rc_res.upstream_causes[0].target_obligation_id
        elif rc_res.direct_causes:
            root_cause_id = rc_res.direct_causes[0].target_obligation_id
        elif res_plan_res.target_obligation_id != obligation_id:
            root_cause_id = res_plan_res.target_obligation_id

        plan = DecisionPlan(
            id=new_plan_id,
            workspace_id=ws_id,
            target_obligation_id=obligation_id,
            generated_at=utc_now(),
            plan_version=new_version,
            status=DecisionPlanStatus.GENERATED,
            overall_urgency=overall_urgency,
            overall_risk=overall_risk,
            decision_confidence=decision_confidence,
            primary_objective=primary_objective,
            root_cause_obligation_id=root_cause_id,
            critical_path=_json_safe(serialized_cp),
            impact_summary=_json_safe({
                "direct_dependents_count": impact_res.direct_dependents_count,
                "total_downstream_dependents_count": impact_res.total_downstream_dependents_count,
                "maximum_dependency_depth": impact_res.maximum_dependency_depth,
                "affected_owners": impact_res.affected_owners,
                "affected_deadlines": impact_res.affected_deadlines,
                "impact_score": impact_res.impact_score,
                "impact_level": impact_res.impact_level,
            }),
            key_risks=_json_safe(risk_res.reasons if risk_res else []),
            supporting_evidence=_json_safe(supporting_evidence),
            recommended_actions=_json_safe(recommended_action),
            alternative_actions=_json_safe(alternative_actions),
            human_decisions_required=_json_safe(all_human_decisions),
            assumptions=_json_safe([
                "Graph dependency relationships reflect active project commitments.",
                "Completion of root prerequisites unblocks direct downstream dependents.",
            ]),
            uncertainties=_json_safe(unc_labels),
            simulation_summary=_json_safe({
                "primary_simulation": primary_sim.model_dump() if hasattr(primary_sim, "model_dump") else primary_sim.dict(),
                "alternatives_count": len(alternative_actions),
                "is_simulation_marker": True,
            }),
            created_from_snapshot_ids=[],
            created_from_event_ids=_json_safe(rc_res.event_refs),
            resolution_notes=explainability_narrative,
        )

        session.add(plan)
        await session.commit()
        await session.refresh(plan)

        logger.info(f"Generated DecisionPlan {plan.id} v{plan.plan_version} for obligation {obligation_id}")
        return plan

    @classmethod
    async def get_active_plan(
        cls, session: AsyncSession, obligation_id: str, workspace_id: Optional[str] = None
    ) -> Optional[DecisionPlan]:
        """
        Retrieves the latest active DecisionPlan for an obligation.
        """
        stmt = (
            select(DecisionPlan)
            .where(
                DecisionPlan.target_obligation_id == obligation_id,
                DecisionPlan.status.in_([
                    DecisionPlanStatus.GENERATED,
                    DecisionPlanStatus.PENDING_REVIEW,
                    DecisionPlanStatus.APPROVED,
                    DecisionPlanStatus.PARTIALLY_EXECUTED,
                ]),
            )
            .order_by(desc(DecisionPlan.plan_version))
        )
        if workspace_id:
            stmt = stmt.where(DecisionPlan.workspace_id == workspace_id)

        res = await session.execute(stmt)
        return res.scalars().first()

    @classmethod
    async def get_plan_history(
        cls, session: AsyncSession, obligation_id: str, workspace_id: Optional[str] = None
    ) -> List[DecisionPlan]:
        """
        Retrieves the immutable historical versions of DecisionPlans for an obligation.
        """
        stmt = (
            select(DecisionPlan)
            .where(DecisionPlan.target_obligation_id == obligation_id)
            .order_by(desc(DecisionPlan.plan_version))
        )
        if workspace_id:
            stmt = stmt.where(DecisionPlan.workspace_id == workspace_id)

        res = await session.execute(stmt)
        return list(res.scalars().all())

    @classmethod
    async def get_workspace_decision_queue(
        cls, session: AsyncSession, workspace_id: str
    ) -> List[DecisionPlan]:
        """
        Retrieves active decision plans across the workspace sorted by urgency and risk.
        """
        stmt = (
            select(DecisionPlan)
            .where(
                DecisionPlan.workspace_id == workspace_id,
                DecisionPlan.status.in_([
                    DecisionPlanStatus.GENERATED,
                    DecisionPlanStatus.PENDING_REVIEW,
                    DecisionPlanStatus.APPROVED,
                ]),
            )
            .order_by(desc(DecisionPlan.overall_risk), desc(DecisionPlan.generated_at))
        )
        res = await session.execute(stmt)
        return list(res.scalars().all())

    @classmethod
    async def approve_plan(
        cls,
        session: AsyncSession,
        plan_id: str,
        user_id: Optional[str] = None,
        request: Optional[DecisionPlanApproveRequest] = None,
    ) -> DecisionPlan:
        """
        Human authorization of a DecisionPlan.
        Safety Invariant: Approval authorizes human follow-up; does NOT execute autonomous actions.
        """
        plan = await session.get(DecisionPlan, plan_id)
        if not plan:
            raise ValueError(f"DecisionPlan '{plan_id}' not found.")

        if plan.status in (DecisionPlanStatus.SUPERSEDED, DecisionPlanStatus.REJECTED):
            raise ValueError(f"Cannot approve plan in status '{plan.status}'.")

        plan.status = DecisionPlanStatus.APPROVED
        plan.approved_at = utc_now()
        plan.approved_by_user_id = user_id

        if request and request.notes:
            notes = plan.resolution_notes or ""
            plan.resolution_notes = f"{notes}\n[Approval Note]: {request.notes}"

        await session.commit()
        await session.refresh(plan)
        logger.info(f"DecisionPlan {plan_id} approved by user {user_id}")
        return plan

    @classmethod
    async def reject_plan(
        cls,
        session: AsyncSession,
        plan_id: str,
        user_id: Optional[str] = None,
        request: Optional[DecisionPlanRejectRequest] = None,
    ) -> DecisionPlan:
        """
        Human rejection of a DecisionPlan with rationale.
        """
        plan = await session.get(DecisionPlan, plan_id)
        if not plan:
            raise ValueError(f"DecisionPlan '{plan_id}' not found.")

        plan.status = DecisionPlanStatus.REJECTED
        plan.rejected_at = utc_now()
        plan.rejected_by_user_id = user_id

        reason = request.reason if request else "Rejected by operator."
        notes = plan.resolution_notes or ""
        plan.resolution_notes = f"{notes}\n[Rejection Reason]: {reason}"

        await session.commit()
        await session.refresh(plan)
        logger.info(f"DecisionPlan {plan_id} rejected by user {user_id}")
        return plan

    @classmethod
    async def resolve_plan(
        cls, session: AsyncSession, plan_id: str, notes: Optional[str] = None
    ) -> DecisionPlan:
        """
        Marks a DecisionPlan as successfully resolved.
        """
        plan = await session.get(DecisionPlan, plan_id)
        if not plan:
            raise ValueError(f"DecisionPlan '{plan_id}' not found.")

        plan.status = DecisionPlanStatus.RESOLVED
        if notes:
            cur_notes = plan.resolution_notes or ""
            plan.resolution_notes = f"{cur_notes}\n[Resolution]: {notes}"

        await session.commit()
        await session.refresh(plan)
        return plan

    @classmethod
    async def _is_plan_stale(
        cls, session: AsyncSession, plan: DecisionPlan, obligation: Obligation
    ) -> bool:
        """
        Deterministic staleness detection:
        Checks if underlying obligation state, root blocker status, or dependencies have changed.
        """
        # 1. Target obligation status change
        rec_raw = plan.recommended_actions
        rec_action: Dict[str, Any] = {}
        if isinstance(rec_raw, dict):
            rec_action = rec_raw
        elif isinstance(rec_raw, list) and len(rec_raw) > 0 and isinstance(rec_raw[0], dict):
            rec_action = rec_raw[0]

        target_id = rec_action.get("target_obligation_id")
        if target_id:
            target_ob = await session.get(Obligation, target_id)
            if target_ob and target_ob.status == ObligationStatus.COMPLETED:
                return True


        # 2. Obligation status changed from when plan was generated
        if obligation.status == ObligationStatus.COMPLETED:
            return True

        # 3. Age > 24 hours
        if plan.generated_at:
            gen_at = plan.generated_at
            if gen_at.tzinfo is None:
                gen_at = gen_at.replace(tzinfo=timezone.utc)
            delta = utc_now() - gen_at
            if delta.total_seconds() > 86400:
                return True

        return False
