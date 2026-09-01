"""
Phase 21 Operational Observability & Audit REST API.

Provides endpoints for operational audit search, cryptographic chain integrity,
system-wide trace graph exploration, alert management, and SLO metrics.
"""

from typing import Optional, List, Dict, Any
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select, desc, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.core.metrics import metrics
from app.models.operational_audit import OperationalAuditRecord
from app.models.operational_alert import OperationalAlert
from app.models.event_inbox import EventInboxRecord, EventInboxStatus
from app.schemas.observability import (
    OperationalAuditRecordSchema,
    AuditIntegrityResult,
    AuditStatsResponse,
    TraceWorkflowGraph,
    OperationalAlertSchema,
    AlertActionRequest,
    SLIReport,
    ErrorBudgetReport,
    OperationsDashboardMetrics,
)
from app.services.operational_audit_service import OperationalAuditService
from app.services.trace_service import TraceService
from app.services.alert_engine import AlertEngine
from app.services.slo_engine import SLOEngine

router = APIRouter(prefix="/api/ops", tags=["Operational Observability"])


# -----------------------------------------------------------------------------
# 1. Operational Audit Endpoints
# -----------------------------------------------------------------------------

@router.get("/audit", response_model=List[Dict[str, Any]])
async def list_operational_audit_records(
    workspace_id: str = Query("ws-default"),
    event_type: Optional[str] = None,
    severity: Optional[str] = None,
    actor_id: Optional[str] = None,
    trace_id: Optional[str] = None,
    request_id: Optional[str] = None,
    resource_id: Optional[str] = None,
    provider: Optional[str] = None,
    limit: int = Query(50, le=200),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    """Searches workspace-scoped operational audit records with pagination and filters."""
    stmt = (
        select(OperationalAuditRecord)
        .where(OperationalAuditRecord.workspace_id == workspace_id)
    )
    if event_type:
        stmt = stmt.where(OperationalAuditRecord.event_type == event_type)
    if severity:
        stmt = stmt.where(OperationalAuditRecord.severity == severity)
    if actor_id:
        stmt = stmt.where(OperationalAuditRecord.actor_id == actor_id)
    if trace_id:
        stmt = stmt.where(OperationalAuditRecord.trace_id == trace_id)
    if request_id:
        stmt = stmt.where(OperationalAuditRecord.request_id == request_id)
    if resource_id:
        stmt = stmt.where(OperationalAuditRecord.resource_id == resource_id)
    if provider:
        stmt = stmt.where(OperationalAuditRecord.provider == provider)

    stmt = stmt.order_by(desc(OperationalAuditRecord.timestamp)).offset(offset).limit(limit)
    res = await db.execute(stmt)
    records = res.scalars().all()

    return [
        {
            "id": r.id,
            "workspace_id": r.workspace_id,
            "timestamp": r.timestamp.isoformat(),
            "event_type": r.event_type,
            "severity": r.severity,
            "actor_type": r.actor_type,
            "actor_id": r.actor_id,
            "request_id": r.request_id,
            "trace_id": r.trace_id,
            "span_id": r.span_id,
            "resource_type": r.resource_type,
            "resource_id": r.resource_id,
            "provider": r.provider,
            "action": r.action,
            "result": r.result,
            "error_code": r.error_code,
            "metadata": r.metadata_json or {},
            "previous_hash": r.previous_hash,
            "record_hash": r.record_hash,
        }
        for r in records
    ]


@router.get("/audit/stats", response_model=AuditStatsResponse)
async def get_audit_statistics(
    workspace_id: str = Query("ws-default"),
    db: AsyncSession = Depends(get_db),
):
    """Returns distribution of operational events by severity, type, and result."""
    return await OperationalAuditService.get_stats(workspace_id, db)


@router.get("/audit/integrity", response_model=AuditIntegrityResult)
async def verify_audit_integrity(
    workspace_id: str = Query("ws-default"),
    db: AsyncSession = Depends(get_db),
):
    """Cryptographically verifies the append-only SHA-256 hash chain for the workspace."""
    return await OperationalAuditService.verify_chain(workspace_id, db)


@router.get("/audit/{record_id}", response_model=Dict[str, Any])
async def get_operational_audit_record(
    record_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Retrieves single operational audit record details."""
    rec = await db.get(OperationalAuditRecord, record_id)
    if not rec:
        raise HTTPException(status_code=404, detail=f"OperationalAuditRecord '{record_id}' not found.")

    return {
        "id": rec.id,
        "workspace_id": rec.workspace_id,
        "timestamp": rec.timestamp.isoformat(),
        "event_type": rec.event_type,
        "severity": rec.severity,
        "actor_type": rec.actor_type,
        "actor_id": rec.actor_id,
        "request_id": rec.request_id,
        "trace_id": rec.trace_id,
        "span_id": rec.span_id,
        "resource_type": rec.resource_type,
        "resource_id": rec.resource_id,
        "provider": rec.provider,
        "action": rec.action,
        "result": rec.result,
        "error_code": rec.error_code,
        "metadata": rec.metadata_json or {},
        "previous_hash": rec.previous_hash,
        "record_hash": rec.record_hash,
    }


# -----------------------------------------------------------------------------
# 2. System-Wide Trace Graph Explorer
# -----------------------------------------------------------------------------

@router.get("/traces/{trace_id}", response_model=TraceWorkflowGraph)
async def get_system_trace_graph(
    trace_id: str,
    workspace_id: str = Query("ws-default"),
    db: AsyncSession = Depends(get_db),
):
    """Reconstructs the full multi-stage execution DAG for a trace."""
    return await TraceService.reconstruct_trace(trace_id, workspace_id, db)


# -----------------------------------------------------------------------------
# 3. Operational Alerts Endpoints
# -----------------------------------------------------------------------------

@router.get("/alerts", response_model=List[Dict[str, Any]])
async def list_alerts(
    workspace_id: str = Query("ws-default"),
    status: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
):
    """Lists operational alerts for workspace."""
    stmt = select(OperationalAlert).where(OperationalAlert.workspace_id == workspace_id)
    if status:
        stmt = stmt.where(OperationalAlert.status == status.upper())
    stmt = stmt.order_by(desc(OperationalAlert.created_at))

    res = await db.execute(stmt)
    alerts = res.scalars().all()

    return [
        {
            "id": a.id,
            "workspace_id": a.workspace_id,
            "alert_name": a.alert_name,
            "alert_type": a.alert_type,
            "severity": a.severity,
            "status": a.status,
            "summary": a.summary,
            "details": a.details or {},
            "fingerprint": a.fingerprint,
            "trace_id": a.trace_id,
            "acknowledged_by": a.acknowledged_by,
            "acknowledged_at": a.acknowledged_at.isoformat() if a.acknowledged_at else None,
            "resolved_at": a.resolved_at.isoformat() if a.resolved_at else None,
            "created_at": a.created_at.isoformat(),
            "updated_at": a.updated_at.isoformat(),
        }
        for a in alerts
    ]


@router.post("/alerts/evaluate", response_model=List[Dict[str, Any]])
async def evaluate_alert_rules(
    workspace_id: str = Query("ws-default"),
    db: AsyncSession = Depends(get_db),
):
    """Triggers deterministic evaluation of operational alert conditions."""
    alerts = await AlertEngine.evaluate_rules(workspace_id, db)
    return [
        {
            "id": a.id,
            "alert_name": a.alert_name,
            "severity": a.severity,
            "status": a.status,
            "summary": a.summary,
        }
        for a in alerts
    ]


@router.post("/alerts/{alert_id}/action", response_model=Dict[str, Any])
async def perform_alert_action(
    alert_id: str,
    req: AlertActionRequest,
    db: AsyncSession = Depends(get_db),
):
    """Transitions alert lifecycle status (acknowledge, resolve, suppress)."""
    alert = await AlertEngine.transition_status(
        alert_id=alert_id,
        action=req.action,
        actor_id=req.actor_id,
        session=db,
    )
    if not alert:
        raise HTTPException(status_code=404, detail=f"Alert '{alert_id}' not found.")

    return {
        "success": True,
        "alert_id": alert.id,
        "new_status": alert.status,
    }


# -----------------------------------------------------------------------------
# 4. SLO & Operations Dashboard Metrics
# -----------------------------------------------------------------------------

@router.get("/slo", response_model=Dict[str, Any])
async def get_slo_reports(
    workspace_id: str = Query("ws-default"),
    db: AsyncSession = Depends(get_db),
):
    """Returns SLI compliance and error budget consumption reports."""
    slis, budgets = await SLOEngine.evaluate_slos(workspace_id, db)
    return {
        "workspace_id": workspace_id,
        "slis": [s.model_dump() for s in slis],
        "error_budgets": [b.model_dump() for b in budgets],
    }


@router.get("/dashboard", response_model=OperationsDashboardMetrics)
async def get_operations_dashboard_metrics(
    workspace_id: str = Query("ws-default"),
    db: AsyncSession = Depends(get_db),
):
    """Returns complete real-time metrics for the operations control center."""
    now_iso = datetime.now(timezone.utc).isoformat()
    snap = metrics.snapshot()

    # Queue stats
    inbox_stmt = (
        select(
            func.count(EventInboxRecord.id),
            func.count(EventInboxRecord.id).filter(EventInboxRecord.status == EventInboxStatus.DEAD_LETTER),
        )
        .where(EventInboxRecord.workspace_id == workspace_id)
    )
    inbox_res = await db.execute(inbox_stmt)
    total_q, dlq_cnt = inbox_res.one()

    # Open alerts count
    alert_stmt = (
        select(func.count(OperationalAlert.id))
        .where(
            OperationalAlert.workspace_id == workspace_id,
            OperationalAlert.status.in_(["OPEN", "ACKNOWLEDGED"]),
        )
    )
    alert_res = await db.execute(alert_stmt)
    open_alerts = alert_res.scalar() or 0

    # Circuit breakers
    try:
        from app.core.circuit_breaker import circuit_breaker
        open_cbs = len([p for p, cb in circuit_breaker._breakers.items() if cb.is_open()])
        prov_summary = {p: cb.state.value for p, cb in circuit_breaker._breakers.items()}
    except Exception:
        open_cbs = 0
        prov_summary = {"default": "CLOSED"}

    # Latency percentiles
    api_stats = metrics.get_histogram_stats("api.latency_ms")
    llm_stats = metrics.get_histogram_stats("llm.latency_ms")

    lat_pcts = {
        "api": {"p50": api_stats.get("p50"), "p95": api_stats.get("p95"), "p99": api_stats.get("p99")},
        "llm": {"p50": llm_stats.get("p50"), "p95": llm_stats.get("p95"), "p99": llm_stats.get("p99")},
    }

    # Throughput
    throughput = {
        "api_rpm": round(metrics.get_counter("api.requests"), 1),
        "llm_rpm": round(metrics.get_counter("llm.requests_total"), 1),
        "events_total": float(total_q),
    }

    slis, budgets = await SLOEngine.evaluate_slos(workspace_id, db)

    return OperationsDashboardMetrics(
        workspace_id=workspace_id,
        timestamp=now_iso,
        api_health="HEALTHY",
        database_backend="postgresql" if settings.is_postgres() else "sqlite",
        worker_status="RUNNING" if settings.WORKER_ENABLED else "STOPPED",
        total_queued_events=total_q,
        dead_letter_depth=dlq_cnt,
        open_alerts_count=open_alerts,
        active_circuit_breakers_open=open_cbs,
        throughput_rpm=throughput,
        latency_percentiles=lat_pcts,
        error_rates={"api_errors": metrics.get_counter("api.errors")},
        slos=slis,
        error_budgets=budgets,
        provider_health_summary=prov_summary,
    )
