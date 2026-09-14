"""
Read-only Strands tools over existing obligation domain services.

`build_obligation_tools(session, workspace_id)` returns tools closed over a
trusted session and workspace_id taken from the caller's already-authenticated
request context. Tool functions never accept workspace_id as a parameter, so
the agent can never select a workspace other than the one it was invoked for.

An optional `max_calls` caps how many of these tools the agent may invoke in
total during one investigation, guarding against runaway tool-calling loops.
"""
import json
from typing import Any, Callable, Dict, List, Optional

from sqlalchemy.ext.asyncio import AsyncSession
from strands import tool

from app.services.obligation_service import ObligationService
from app.services.graph_service import GraphService
from app.services.intelligence.root_cause_engine import RootCauseAnalysisEngine
from app.services.event_ingestion_service import EventIngestionService

_BUDGET_EXHAUSTED = {
    "status": "error",
    "content": [{"text": "Tool-call budget exhausted for this investigation."}],
}


def build_obligation_tools(
    session: AsyncSession,
    workspace_id: str,
    max_calls: Optional[int] = None,
    counter: Optional[Dict[str, int]] = None,
) -> List[Callable]:
    """Returns Strands tools scoped to one session + workspace.

    `counter`, when given, is populated with {"calls": N} as tools run, so the
    caller can record how much tool work an agent actually did.
    """
    budget = {"remaining": max_calls, "used": 0}
    if counter is not None:
        counter["calls"] = 0

    def _spend_call() -> bool:
        """Consumes one unit of the call budget. Returns True if it was already spent."""
        if budget["remaining"] is not None:
            if budget["remaining"] <= 0:
                return True
            budget["remaining"] -= 1
        budget["used"] += 1
        if counter is not None:
            counter["calls"] = budget["used"]
        return False

    def _not_found(obligation_id: str) -> Dict[str, Any]:
        return {
            "status": "error",
            "content": [{"text": f"Obligation '{obligation_id}' not found in this workspace."}],
        }

    @tool
    async def get_obligation_snapshot(obligation_id: str) -> Dict[str, Any]:
        """
        Fetch the current state of one obligation: owner, beneficiary,
        action, deadline, status, and risk.

        Args:
            obligation_id: The obligation's ID.
        """
        if _spend_call():
            return _BUDGET_EXHAUSTED
        obligation = await ObligationService.get_by_id(
            session, obligation_id, workspace_id=workspace_id
        )
        if obligation is None:
            return _not_found(obligation_id)
        return {"status": "success", "content": [{"text": obligation.model_dump_json()}]}

    @tool
    async def get_dependency_chain(obligation_id: str) -> Dict[str, Any]:
        """
        Fetch the upstream prerequisites and root blockers for one obligation.

        Args:
            obligation_id: The obligation's ID.
        """
        if _spend_call():
            return _BUDGET_EXHAUSTED
        obligation = await ObligationService.get_by_id(
            session, obligation_id, workspace_id=workspace_id
        )
        if obligation is None:
            return _not_found(obligation_id)
        upstream = await GraphService.get_upstream_chain(session, obligation_id)
        root_blockers = await GraphService.get_root_blockers(session, obligation_id)
        payload = {
            "upstream_chain": [item["obligation"].id for item in upstream],
            "root_blockers": [item["obligation"].id for item in root_blockers],
        }
        return {"status": "success", "content": [{"text": json.dumps(payload)}]}

    @tool
    async def get_root_cause_summary(obligation_id: str) -> Dict[str, Any]:
        """
        Run the deterministic root-cause analysis engine for one obligation and
        return its structured findings: direct causes, upstream causes,
        contributing factors, and the evidence they rest on.

        Args:
            obligation_id: The obligation's ID.
        """
        if _spend_call():
            return _BUDGET_EXHAUSTED
        try:
            result = await RootCauseAnalysisEngine.analyze(
                session, obligation_id, workspace_id=workspace_id
            )
        except ValueError as e:
            return {"status": "error", "content": [{"text": str(e)}]}
        return {"status": "success", "content": [{"text": result.model_dump_json()}]}

    @tool
    async def get_related_evidence(obligation_id: str) -> Dict[str, Any]:
        """
        Fetch the evidence records attached to one obligation: what was
        observed, from which provider, and whether a human confirmed it.

        Args:
            obligation_id: The obligation's ID.
        """
        if _spend_call():
            return _BUDGET_EXHAUSTED
        obligation = await ObligationService.get_by_id(
            session, obligation_id, workspace_id=workspace_id
        )
        if obligation is None:
            return _not_found(obligation_id)
        evidence = await ObligationService.get_evidence(
            session, obligation_id, workspace_id=workspace_id
        )
        payload = [e.model_dump(mode="json") for e in evidence]
        return {"status": "success", "content": [{"text": json.dumps(payload)}]}

    @tool
    async def get_risk_assessment(obligation_id: str) -> Dict[str, Any]:
        """
        Fetch the deterministic risk assessment for one obligation: its risk
        score, level, and the reasons the risk engine gave.

        Args:
            obligation_id: The obligation's ID.
        """
        if _spend_call():
            return _BUDGET_EXHAUSTED
        obligation = await ObligationService.get_by_id(
            session, obligation_id, workspace_id=workspace_id
        )
        if obligation is None:
            return _not_found(obligation_id)
        assessment = await ObligationService.get_risk_assessment(
            session, obligation_id, workspace_id=workspace_id
        )
        if assessment is None:
            return {"status": "success", "content": [{"text": json.dumps({})}]}
        return {"status": "success", "content": [{"text": assessment.model_dump_json()}]}

    @tool
    async def get_downstream_impact(obligation_id: str) -> Dict[str, Any]:
        """
        Fetch the obligations that would be affected if this one slips: every
        downstream dependent, with how many hops away it sits.

        Args:
            obligation_id: The obligation's ID.
        """
        if _spend_call():
            return _BUDGET_EXHAUSTED
        obligation = await ObligationService.get_by_id(
            session, obligation_id, workspace_id=workspace_id
        )
        if obligation is None:
            return _not_found(obligation_id)
        downstream = await GraphService.get_downstream_impact(session, obligation_id)
        payload = [
            {"obligation_id": item["obligation"].id,
             "action": item["obligation"].action,
             "hop_distance": item.get("hop_distance")}
            for item in downstream
        ]
        return {"status": "success", "content": [{"text": json.dumps(payload)}]}

    @tool
    async def get_related_obligations(obligation_id: str) -> Dict[str, Any]:
        """
        Fetch obligations linked to this one for context (LINKED edges), which
        are related work but not prerequisites.

        Args:
            obligation_id: The obligation's ID.
        """
        if _spend_call():
            return _BUDGET_EXHAUSTED
        obligation = await ObligationService.get_by_id(
            session, obligation_id, workspace_id=workspace_id
        )
        if obligation is None:
            return _not_found(obligation_id)
        linked = await GraphService.get_linked_obligations(session, obligation_id)
        payload = [{"obligation_id": o.id, "action": o.action} for o in linked]
        return {"status": "success", "content": [{"text": json.dumps(payload)}]}

    @tool
    async def get_recent_events(obligation_id: str) -> Dict[str, Any]:
        """
        Fetch recent external signals ingested into this workspace from Slack,
        Gmail, Calendar or Jira, newest first.

        Args:
            obligation_id: The obligation being investigated, for context.
        """
        if _spend_call():
            return _BUDGET_EXHAUSTED
        events = await EventIngestionService.list_events(
            session, limit=20, workspace_id=workspace_id
        )
        payload = [
            {"event_id": e.id, "provider": e.provider,
             "semantic_role": getattr(e.semantic_role, "value", e.semantic_role),
             "source_ref": e.source_ref, "sender": e.sender,
             "content": (e.content or "")[:500]}
            for e in events.items
        ]
        return {"status": "success", "content": [{"text": json.dumps(payload)}]}

    return [
        get_obligation_snapshot,
        get_dependency_chain,
        get_root_cause_summary,
        get_related_evidence,
        get_risk_assessment,
        get_downstream_impact,
        get_related_obligations,
        get_recent_events,
    ]
