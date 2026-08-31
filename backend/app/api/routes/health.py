"""
Phase 19 Health, Readiness & Production Metrics API.

Endpoints:
  GET /api/health  — process liveness (no DB required)
  GET /api/ready   — dependency readiness (DB, worker, config)
  GET /api/metrics — full structured production metrics
"""

import time
import psutil
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, status
from fastapi.responses import JSONResponse
from sqlalchemy import text, select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.core.worker import worker_queue
from app.core.metrics import metrics as app_metrics
from app.core.circuit_breaker import get_all_circuit_statuses
from app.models.obligation import Obligation, Evidence
from app.models.decision import DecisionPlan
from app.models.execution import ExecutionRecord
from app.models.monitoring import MonitoringEvent, EscalationCandidate
from app.models.job import BackgroundJobRecord, JobStatus

router = APIRouter(tags=["Health & Diagnostics"])

START_TIME = time.time()


# ---------------------------------------------------------------------------
# GET /health — liveness (never touches DB; crash/restart detector)
# ---------------------------------------------------------------------------

@router.get("/health")
async def liveness_check():
    """
    Process liveness probe. Used by container orchestrators (K8s, ECS, Fly.io)
    to determine if the process should be restarted.
    Never touches the database — should always return 200 if the process is alive.
    """
    uptime_seconds = time.time() - START_TIME
    process = psutil.Process()
    memory_info = process.memory_info()

    return {
        "status": "healthy",
        "service": settings.PROJECT_NAME,
        "version": settings.VERSION,
        "environment": settings.APP_ENV,
        "auth_mode": settings.AUTH_MODE,
        "uptime_seconds": round(uptime_seconds, 2),
        "memory_rss_mb": round(memory_info.rss / (1024 * 1024), 2),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


# ---------------------------------------------------------------------------
# GET /ready — readiness (DB + worker + config)
# ---------------------------------------------------------------------------

@router.get("/ready")
async def readiness_check(session: AsyncSession = Depends(get_db)):
    """
    Dependency readiness probe. Used by load balancers / k8s to determine
    if the instance should receive traffic. Fails if DB is unreachable or
    production config is invalid.
    """
    readiness: dict = {
        "status": "ready",
        "database": "unknown",
        "worker_queue": "unknown",
        "configuration": "unknown",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    is_ready = True
    errors = []

    # 1. Database connectivity
    try:
        await session.execute(text("SELECT 1"))
        readiness["database"] = "connected"
    except Exception as exc:
        is_ready = False
        readiness["database"] = "error"
        errors.append("Database unreachable.")

    # 2. Worker queue
    readiness["worker_queue"] = "operational" if worker_queue._running else "stopped"

    # 3. Configuration
    config_errors = settings.validate_production_config()
    if config_errors:
        if settings.is_production():
            is_ready = False
        readiness["configuration"] = "invalid"
        errors.extend(config_errors)
    else:
        readiness["configuration"] = "valid"

    if not is_ready:
        readiness["status"] = "unready"
        readiness["errors"] = errors
        return JSONResponse(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, content=readiness)

    return readiness


# ---------------------------------------------------------------------------
# GET /metrics — full production metrics
# ---------------------------------------------------------------------------

@router.get("/metrics")
async def production_metrics(session: AsyncSession = Depends(get_db)):
    """
    Comprehensive structured production metrics.
    Covers: API latency, obligation lifecycle, decision plans, executions,
    evidence, monitoring, worker queue, circuit breakers, and system resources.
    All values are credential-free and safe to expose to internal dashboards.
    """
    uptime = round(time.time() - START_TIME, 2)
    process = psutil.Process()
    memory_info = process.memory_info()

    # ---- Obligations -------------------------------------------------------
    def _count(q): return session.execute(select(func.count()).select_from(q.subquery()))

    total_ob = (await session.execute(select(func.count(Obligation.id)))).scalar() or 0
    active_ob = (await session.execute(
        select(func.count(Obligation.id)).where(Obligation.status.in_(["CONFIRMED", "ACTIVE", "IN_PROGRESS"]))
    )).scalar() or 0
    overdue_ob = (await session.execute(
        select(func.count(Obligation.id)).where(Obligation.status == "OVERDUE")
    )).scalar() or 0
    blocked_ob = (await session.execute(
        select(func.count(Obligation.id)).where(Obligation.status == "BLOCKED")
    )).scalar() or 0
    complete_ob = (await session.execute(
        select(func.count(Obligation.id)).where(Obligation.status == "COMPLETE")
    )).scalar() or 0

    # ---- Evidence ----------------------------------------------------------
    total_evidence = (await session.execute(select(func.count(Evidence.id)))).scalar() or 0
    confirmed_evidence = (await session.execute(
        select(func.count(Evidence.id)).where(Evidence.confirmed == True)
    )).scalar() or 0

    # ---- Decision Plans ----------------------------------------------------
    total_plans = (await session.execute(select(func.count(DecisionPlan.id)))).scalar() or 0
    pending_plans = (await session.execute(
        select(func.count(DecisionPlan.id)).where(DecisionPlan.status == "PENDING")
    )).scalar() or 0
    approved_plans = (await session.execute(
        select(func.count(DecisionPlan.id)).where(DecisionPlan.status == "APPROVED")
    )).scalar() or 0
    resolved_plans = (await session.execute(
        select(func.count(DecisionPlan.id)).where(DecisionPlan.status == "RESOLVED")
    )).scalar() or 0
    rejected_plans = (await session.execute(
        select(func.count(DecisionPlan.id)).where(DecisionPlan.status == "REJECTED")
    )).scalar() or 0

    # ---- Executions --------------------------------------------------------
    total_exec = (await session.execute(select(func.count(ExecutionRecord.id)))).scalar() or 0
    delivered_exec = (await session.execute(
        select(func.count(ExecutionRecord.id)).where(ExecutionRecord.status == "DELIVERED")
    )).scalar() or 0
    failed_exec = (await session.execute(
        select(func.count(ExecutionRecord.id)).where(ExecutionRecord.status == "FAILED")
    )).scalar() or 0
    pending_exec = (await session.execute(
        select(func.count(ExecutionRecord.id)).where(ExecutionRecord.status.in_(["PENDING", "AUTHORIZED"]))
    )).scalar() or 0

    # ---- Monitoring --------------------------------------------------------
    total_mon_events = (await session.execute(select(func.count(MonitoringEvent.id)))).scalar() or 0
    open_escalations = (await session.execute(
        select(func.count(EscalationCandidate.id)).where(EscalationCandidate.status == "OPEN")
    )).scalar() or 0

    # ---- Worker Queue (durable) --------------------------------------------
    worker_stats = {}
    if settings.WORKER_DURABLE_QUEUE:
        try:
            worker_stats = await worker_queue.get_queue_stats()
        except Exception:
            pass
    else:
        # Legacy in-memory queue
        jobs = getattr(worker_queue, '_jobs', {})
        worker_stats = {
            "queued": sum(1 for j in jobs.values() if getattr(j, 'status', None) and j.status.value == "QUEUED"),
            "processing": sum(1 for j in jobs.values() if getattr(j, 'status', None) and j.status.value == "PROCESSING"),
            "completed": sum(1 for j in jobs.values() if getattr(j, 'status', None) and j.status.value == "COMPLETED"),
            "failed": sum(1 for j in jobs.values() if getattr(j, 'status', None) and j.status.value in ("FAILED", "DEAD_LETTER")),
        }

    # ---- Circuit Breakers --------------------------------------------------
    circuit_statuses = get_all_circuit_statuses()

    # ---- In-Process API Metrics (rolling window) ---------------------------
    api_latency = app_metrics.get_histogram_stats("api.latency_ms")
    api_requests = app_metrics.get_counter("api.requests")
    api_errors = app_metrics.get_counter("api.errors")

    # ---- Event Inbox Queue -------------------------------------------------
    from app.services.async_event_dispatcher import event_dispatcher
    inbox_stats = await event_dispatcher.get_inbox_queue_stats(session=session)

    return {
        "system": {
            "service": settings.PROJECT_NAME,
            "version": settings.VERSION,
            "environment": settings.APP_ENV,
            "database_backend": "postgresql" if settings.is_postgres() else "sqlite",
            "uptime_seconds": uptime,
            "worker_concurrency": settings.WORKER_CONCURRENCY,
            "worker_durable": settings.WORKER_DURABLE_QUEUE,
            "memory_rss_mb": round(memory_info.rss / (1024 * 1024), 2),
            "cpu_percent": cpu_percent,
            **({"disk_used_pct": round(disk.percent, 1)} if disk else {}),
        },
        "api": {
            "total_requests": api_requests,
            "total_errors": api_errors,
            "error_rate_pct": round((api_errors / api_requests * 100) if api_requests else 0, 2),
            "latency_ms": api_latency,
        },
        "obligations": {
            "total": total_ob,
            "active": active_ob,
            "overdue": overdue_ob,
            "blocked": blocked_ob,
            "complete": complete_ob,
        },
        "evidence": {
            "total": total_evidence,
            "confirmed": confirmed_evidence,
            "pending": total_evidence - confirmed_evidence,
        },
        "decisions": {
            "plans_generated": total_plans,
            "plans_pending": pending_plans,
            "plans_approved": approved_plans,
            "plans_resolved": resolved_plans,
            "plans_rejected": rejected_plans,
        },
        "executions": {
            "total_dispatched": total_exec,
            "delivered": delivered_exec,
            "failed": failed_exec,
            "pending_authorization": pending_exec,
        },
        "monitoring": {
            "events_detected": total_mon_events,
            "open_escalations": open_escalations,
        },
        "worker_queue": worker_stats,
        "event_inbox": inbox_stats,
        "circuit_breakers": circuit_statuses,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

