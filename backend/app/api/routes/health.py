"""
Phase 17 Health, Readiness & Production Metrics API Endpoints.
"""

import time
import psutil
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, status, HTTPException
from fastapi.responses import JSONResponse
from sqlalchemy import text, select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.core.worker import worker_queue
from app.models.obligation import Obligation
from app.models.decision import DecisionPlan
from app.models.execution import ExecutionRecord
from app.models.monitoring import MonitoringEvent, EscalationCandidate

router = APIRouter(tags=["Health & Diagnostics"])

START_TIME = time.time()


@router.get("/health")
async def liveness_check():
    """
    Process Liveness Endpoint: Verifies the application process is running and healthy.
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
        "memory_usage_mb": round(memory_info.rss / (1024 * 1024), 2),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@router.get("/ready")
async def readiness_check(session: AsyncSession = Depends(get_db)):
    """
    Dependency Readiness Endpoint: Verifies database connectivity, configuration integrity,
    and background worker subsystems before accepting production traffic.
    """
    readiness = {
        "status": "ready",
        "database": "unknown",
        "worker_queue": "unknown",
        "configuration": "unknown",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    is_ready = True
    errors = []

    # 1. Database Check
    try:
        await session.execute(text("SELECT 1"))
        readiness["database"] = "connected"
    except Exception as exc:
        is_ready = False
        readiness["database"] = f"error: {str(exc)}"
        errors.append(f"Database error: {str(exc)}")

    # 2. Worker Queue Check
    if worker_queue._running:
        readiness["worker_queue"] = "operational"
    else:
        readiness["worker_queue"] = "stopped"

    # 3. Configuration Check
    config_errors = settings.validate_production_config()
    if config_errors:
        is_ready = False
        readiness["configuration"] = f"invalid: {', '.join(config_errors)}"
        errors.extend(config_errors)
    else:
        readiness["configuration"] = "valid"

    if not is_ready:
        readiness["status"] = "unready"
        readiness["errors"] = errors
        return JSONResponse(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, content=readiness)

    return readiness


@router.get("/metrics")
async def production_metrics(session: AsyncSession = Depends(get_db)):
    """
    Structured System, Intelligence, Decision, and Execution Metrics.
    Sanitized and free of credentials or sensitive personal message content.
    """
    # Obligations
    total_ob = (await session.execute(select(func.count(Obligation.id)))).scalar() or 0
    active_ob = (await session.execute(select(func.count(Obligation.id)).where(Obligation.status.in_(["CONFIRMED", "ACTIVE", "IN_PROGRESS"])))).scalar() or 0
    overdue_ob = (await session.execute(select(func.count(Obligation.id)).where(Obligation.status == "OVERDUE"))).scalar() or 0
    blocked_ob = (await session.execute(select(func.count(Obligation.id)).where(Obligation.status == "BLOCKED"))).scalar() or 0

    # Decision Plans
    total_plans = (await session.execute(select(func.count(DecisionPlan.id)))).scalar() or 0
    approved_plans = (await session.execute(select(func.count(DecisionPlan.id)).where(DecisionPlan.status == "APPROVED"))).scalar() or 0
    resolved_plans = (await session.execute(select(func.count(DecisionPlan.id)).where(DecisionPlan.status == "RESOLVED"))).scalar() or 0

    # Executions
    total_exec = (await session.execute(select(func.count(ExecutionRecord.id)))).scalar() or 0
    delivered_exec = (await session.execute(select(func.count(ExecutionRecord.id)).where(ExecutionRecord.status == "DELIVERED"))).scalar() or 0
    failed_exec = (await session.execute(select(func.count(ExecutionRecord.id)).where(ExecutionRecord.status == "FAILED"))).scalar() or 0

    # Monitoring Events & Escalations
    total_mon_events = (await session.execute(select(func.count(MonitoringEvent.id)))).scalar() or 0
    open_escalations = (await session.execute(select(func.count(EscalationCandidate.id)).where(EscalationCandidate.status == "OPEN"))).scalar() or 0

    return {
        "system": {
            "service": settings.PROJECT_NAME,
            "version": settings.VERSION,
            "environment": settings.APP_ENV,
            "uptime_seconds": round(time.time() - START_TIME, 2),
            "worker_concurrency": settings.WORKER_CONCURRENCY,
        },
        "obligations": {
            "total": total_ob,
            "active": active_ob,
            "overdue": overdue_ob,
            "blocked": blocked_ob,
        },
        "decisions": {
            "plans_generated": total_plans,
            "plans_approved": approved_plans,
            "plans_resolved": resolved_plans,
        },
        "executions": {
            "total_dispatched": total_exec,
            "delivered": delivered_exec,
            "failed": failed_exec,
        },
        "monitoring": {
            "events_detected": total_mon_events,
            "open_escalations": open_escalations,
        },
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
