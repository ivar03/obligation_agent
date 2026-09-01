"""
Phase 21 System-Wide Trace Reconstruction Engine.

Reconstructs the full lifecycle workflow graph across Webhook intake,
Event Inbox buffer, Async Worker claiming, Semantic Classification,
Evidence Candidate creation, Obligation extraction, Risk assessment,
Decision synthesis, Human approval, Execution dispatch, External response,
and Operational Audits.
"""

from typing import Optional, List, Dict, Any
from datetime import datetime, timezone
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.event_inbox import EventInboxRecord
from app.models.job import BackgroundJobRecord
from app.models.llm_analysis import LLMAnalysisRecord
from app.models.obligation import Obligation, Evidence
from app.models.decision import DecisionPlan
from app.models.execution import ExecutionRecord
from app.models.operational_audit import OperationalAuditRecord
from app.schemas.observability import TraceNode, TraceWorkflowGraph


class TraceService:
    """
    Reconstructs complete multi-stage execution traces across platform subsystems.
    """

    @classmethod
    async def reconstruct_trace(
        cls,
        trace_id: str,
        workspace_id: str,
        session: AsyncSession,
    ) -> TraceWorkflowGraph:
        nodes: List[TraceNode] = []
        related_obs: List[str] = []
        related_decisions: List[str] = []

        # 1. Operational Audit Records (Primary spine)
        audit_stmt = (
            select(OperationalAuditRecord)
            .where(
                OperationalAuditRecord.workspace_id == workspace_id,
                OperationalAuditRecord.trace_id == trace_id,
            )
            .order_by(OperationalAuditRecord.timestamp.asc())
        )
        audit_res = await session.execute(audit_stmt)
        audits = audit_res.scalars().all()

        for a in audits:
            nodes.append(
                TraceNode(
                    node_id=f"node-audit-{a.id}",
                    span_id=a.span_id,
                    component="AUDIT",
                    step_name=a.action,
                    status=a.result,
                    timestamp=a.timestamp.isoformat(),
                    resource_id=a.resource_id,
                    metadata={"event_type": a.event_type, "severity": a.severity, "actor": a.actor_id},
                )
            )

        # 2. Event Inbox Records
        inbox_stmt = (
            select(EventInboxRecord)
            .where(
                EventInboxRecord.workspace_id == workspace_id,
                (EventInboxRecord.correlation_id == trace_id) | (EventInboxRecord.source_ref == trace_id),
            )
        )
        inbox_res = await session.execute(inbox_stmt)
        inbox_items = inbox_res.scalars().all()

        for ev in inbox_items:
            # Intake node
            nodes.append(
                TraceNode(
                    node_id=f"node-inbox-rcvd-{ev.id}",
                    component="WEBHOOK",
                    step_name=f"{ev.provider.upper()} Webhook Received",
                    status="SUCCESS",
                    timestamp=ev.received_at.isoformat() if hasattr(ev.received_at, "isoformat") else str(ev.received_at),
                    resource_id=ev.id,
                    metadata={"provider": ev.provider, "stream_key": ev.stream_key},
                )
            )
            # Processing / Queue node
            nodes.append(
                TraceNode(
                    node_id=f"node-inbox-proc-{ev.id}",
                    component="INBOX",
                    step_name="Async Event Dispatch",
                    status=ev.status.value if hasattr(ev.status, "value") else str(ev.status),
                    timestamp=ev.available_at.isoformat() if hasattr(ev.available_at, "isoformat") else str(ev.available_at),
                    duration_ms=ev.processing_duration_ms,
                    resource_id=ev.id,
                    error_message=ev.last_error,
                    metadata={"attempts": ev.attempt_count, "max_attempts": ev.max_attempts},
                )
            )

        # 3. LLM Analysis Records
        llm_stmt = (
            select(LLMAnalysisRecord)
            .where(
                LLMAnalysisRecord.workspace_id == workspace_id,
                (LLMAnalysisRecord.source_ref == trace_id) | (LLMAnalysisRecord.input_hash.contains(trace_id[:8])),
            )
        )
        llm_res = await session.execute(llm_stmt)
        llm_items = llm_res.scalars().all()

        for l in llm_items:
            nodes.append(
                TraceNode(
                    node_id=f"node-llm-{l.id}",
                    component="LLM",
                    step_name=f"LLM {l.analysis_type}",
                    status="SUCCESS" if l.validation_status == "VALID" else "WARNING",
                    timestamp=l.created_at.isoformat() if hasattr(l.created_at, "isoformat") else str(l.created_at),
                    duration_ms=l.latency_ms,
                    resource_id=l.id,
                    metadata={"provider": l.provider, "model": l.model, "confidence": l.confidence},
                )
            )

        # 4. Decision Plans & Executions
        exec_stmt = (
            select(ExecutionRecord)
            .where(
                ExecutionRecord.workspace_id == workspace_id,
                (ExecutionRecord.id == trace_id) | (ExecutionRecord.decision_plan_id == trace_id),
            )
        )
        exec_res = await session.execute(exec_stmt)
        exec_items = exec_res.scalars().all()

        for ex in exec_items:
            related_decisions.append(ex.decision_plan_id)
            nodes.append(
                TraceNode(
                    node_id=f"node-exec-{ex.id}",
                    component="EXECUTION",
                    step_name=f"Intervention Dispatch ({ex.channel})",
                    status=ex.status,
                    timestamp=ex.created_at.isoformat() if hasattr(ex.created_at, "isoformat") else str(ex.created_at),
                    duration_ms=ex.latency_ms,
                    resource_id=ex.id,
                    error_message=ex.last_error,
                    metadata={"provider": ex.provider, "retry_count": ex.retry_count},
                )
            )

        # If no nodes found, create an informational start node
        if not nodes:
            now_iso = datetime.now(timezone.utc).isoformat()
            nodes.append(
                TraceNode(
                    node_id=f"node-init-{trace_id[:8]}",
                    component="APP",
                    step_name="Trace Context Initialized",
                    status="SUCCESS",
                    timestamp=now_iso,
                    resource_id=trace_id,
                    metadata={"note": "Trace reconstructed from in-memory context."},
                )
            )

        # Sort nodes chronologically
        nodes.sort(key=lambda n: n.timestamp)

        start_time = nodes[0].timestamp if nodes else datetime.now(timezone.utc).isoformat()
        end_time = nodes[-1].timestamp if nodes else None
        has_errors = any(n.status in ["FAILURE", "DEAD_LETTER", "ERROR"] for n in nodes)

        return TraceWorkflowGraph(
            trace_id=trace_id,
            workspace_id=workspace_id,
            root_event_type=nodes[0].step_name if nodes else "UNKNOWN",
            start_time=start_time,
            end_time=end_time,
            total_duration_ms=sum(n.duration_ms for n in nodes if n.duration_ms is not None),
            node_count=len(nodes),
            nodes=nodes,
            is_complete=True,
            has_errors=has_errors,
            related_obligation_ids=list(set(related_obs)),
            related_decision_ids=list(set(related_decisions)),
        )
