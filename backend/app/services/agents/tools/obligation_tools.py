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

_BUDGET_EXHAUSTED = {
    "status": "error",
    "content": [{"text": "Tool-call budget exhausted for this investigation."}],
}


def build_obligation_tools(
    session: AsyncSession, workspace_id: str, max_calls: Optional[int] = None
) -> List[Callable]:
    """Returns Strands tools scoped to one session + workspace."""
    budget = {"remaining": max_calls}

    def _spend_call() -> bool:
        """Consumes one unit of the call budget. Returns True if it was already spent."""
        if budget["remaining"] is None:
            return False
        if budget["remaining"] <= 0:
            return True
        budget["remaining"] -= 1
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

    return [get_obligation_snapshot, get_dependency_chain, get_root_cause_summary]
