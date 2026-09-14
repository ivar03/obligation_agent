"""
Telemetry and audit for one agentic run.

Every Strands agent run is bounded and accounted for: it gets an agent_run_id,
is capped by a wall-clock timeout, emits latency/outcome metrics, and lands an
immutable entry in the existing hash-chained audit log. This rides the
project's existing AuditService and metrics registry rather than standing up a
parallel observability stack for one subsystem.
"""
import time
import uuid
from contextlib import asynccontextmanager
from typing import Any, Dict, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import logger
from app.core.metrics import metrics
from app.core.request_context import get_current_request_id, get_current_trace_id
from app.core.status_machine import AuditAction, AuditResult, AuditSeverity, AuditSource
from app.services.audit_service import AuditService


@asynccontextmanager
async def record_agent_run(
    session: AsyncSession,
    workspace_id: str,
    agent_name: str,
    obligation_id: Optional[str] = None,
    counter: Optional[Dict[str, int]] = None,
):
    """
    Wraps one agent run: assigns an id, times it, and records the outcome to
    metrics and the audit chain. Re-raises whatever the body raised, after
    recording the failure.
    """
    agent_run_id = str(uuid.uuid4())
    started = time.perf_counter()
    run: Dict[str, Any] = {"agent_run_id": agent_run_id}

    metrics.increment("agent.runs_total", labels={"agent": agent_name})

    try:
        yield run
    except Exception as e:
        latency_ms = (time.perf_counter() - started) * 1000
        metrics.increment("agent.failure_total", labels={"agent": agent_name})
        logger.error(f"Agent run {agent_run_id} ({agent_name}) failed: {e}")
        await _record(
            session, workspace_id, agent_name, agent_run_id, obligation_id,
            counter, latency_ms, AuditAction.AGENT_RUN_FAILED,
            AuditSeverity.ERROR, AuditResult.FAILED, error=str(e),
        )
        raise

    latency_ms = (time.perf_counter() - started) * 1000
    metrics.increment("agent.success_total", labels={"agent": agent_name})
    metrics.record_duration("agent.latency_ms", latency_ms, labels={"agent": agent_name})
    await _record(
        session, workspace_id, agent_name, agent_run_id, obligation_id,
        counter, latency_ms, AuditAction.AGENT_RUN_COMPLETED,
        AuditSeverity.INFO, AuditResult.SUCCESS,
    )


async def _record(
    session, workspace_id, agent_name, agent_run_id, obligation_id,
    counter, latency_ms, action, severity, result, error=None,
):
    # ponytail: failure records ride the request session, so a 500 that triggers
    # get_db's rollback discards them; success records commit normally. Move the
    # failure path onto its own short-lived session if failed-run auditing becomes
    # a compliance requirement.
    tool_calls = (counter or {}).get("calls", 0)
    metrics.record_duration("agent.tool_calls", tool_calls, labels={"agent": agent_name})
    payload = {
        "agent_run_id": agent_run_id,
        "agent_name": agent_name,
        "obligation_id": obligation_id,
        "trace_id": get_current_trace_id(),
        "request_id": get_current_request_id(),
        "tool_calls": tool_calls,
        "latency_ms": round(latency_ms, 2),
    }
    if error is not None:
        payload["error"] = error
    try:
        await AuditService.record(
            session,
            workspace_id=workspace_id,
            action=action,
            entity_type="agent_run",
            entity_id=agent_run_id,
            source=AuditSource.SYSTEM_WORKER,
            metadata=payload,
            severity=severity,
            result=result,
        )
    except Exception as e:  # audit must never take the request down with it
        logger.error(f"Failed to record agent run {agent_run_id} to audit log: {e}")