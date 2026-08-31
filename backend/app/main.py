"""
Phase 19 FastAPI Application Entry Point.

Phase 19 additions:
  - Unified structured error handlers (no stack traces, no DB internals)
  - Startup: durable queue crash recovery + schema compatibility check
  - Shutdown: graceful drain of in-flight worker jobs
  - Metrics middleware integration
  - Request body size enforcement
"""
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import ValidationError as PydanticValidationError

from app.core.config import settings
from app.core.logging import setup_logging, logger
from app.core.database import engine, Base
from app.core.errors import (
    ObligationAgentError,
    make_error_response,
    ErrorCode,
)
from app.core.status_machine import InvalidStatusTransitionError
from app.core.intervention_status import InvalidInterventionStatusTransitionError
from app.core.request_context import get_current_request_id, RequestContextMiddleware

# Route imports
from app.api.routes import (
    health, auth, workspaces, obligations, dashboard, events,
    risk, interventions, webhooks, integrations, reconciliation, intelligence,
)
from app.api.routes import audit as audit_router
from app.api.routes import decision as decision_router
from app.api.routes import memory as memory_router
from app.api.routes import execution as execution_router
from app.api.routes import monitoring as monitoring_router
from app.api.routes import search as search_router
from app.api.routes import queues as queues_router
from app.api.routes import events_queue as events_queue_router
from app.api.routes import notifications as notifications_router
from app.api.routes import import_export as import_export_router
from app.api.routes import llm_intelligence as llm_intelligence_router

from app.core.worker import worker_queue




# ---------------------------------------------------------------------------
# Lifespan: startup → shutdown
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging()
    logger.info(
        f"Starting {settings.PROJECT_NAME} v{settings.VERSION}",
        extra={"environment": settings.APP_ENV, "auth_mode": settings.AUTH_MODE},
    )

    # Validate production configuration eagerly — exit if invalid
    config_errors = settings.validate_production_config()
    if config_errors:
        for err in config_errors:
            logger.error(f"Production config error: {err}")
        if settings.is_production():
            raise RuntimeError(
                f"Production configuration invalid: {'; '.join(config_errors)}"
            )

    # Auto-create tables (dev/test). Production uses Alembic migrations.
    if settings.is_development():
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info("Database tables verified (development mode).")

    # Start background worker
    if settings.WORKER_ENABLED:
        worker_queue.start()
        logger.info("Background worker started.")

        # Phase 19: recover stale jobs from previous crash
        if settings.WORKER_DURABLE_QUEUE:
            try:
                recovered = await worker_queue.recover_stale_jobs()
                if recovered:
                    logger.info(f"Startup: recovered {recovered} stale jobs from previous crash.")
            except Exception as exc:
                logger.warning(f"Stale job recovery error (non-fatal): {exc}")

    yield

    # Graceful shutdown
    logger.info("Shutting down application...")
    if settings.WORKER_ENABLED:
        await worker_queue.stop()
    await engine.dispose()
    logger.info("Shutdown complete.")


# ---------------------------------------------------------------------------
# Application
# ---------------------------------------------------------------------------

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    lifespan=lifespan,
    docs_url="/docs" if not settings.is_production() else None,
    redoc_url="/redoc" if not settings.is_production() else None,
)


# ---------------------------------------------------------------------------
# Middleware (order matters — outermost is registered last)
# ---------------------------------------------------------------------------

# 1. Request correlation / access logging / metrics
app.add_middleware(RequestContextMiddleware)

# 2. CORS
origins = settings.cors_origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins if origins else ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Phase 19: Unified Exception Handlers
# All errors return structured JSON with stable error codes.
# No stack traces, database internals, or credential leakage.
# ---------------------------------------------------------------------------

@app.exception_handler(ObligationAgentError)
async def obligation_agent_error_handler(request: Request, exc: ObligationAgentError):
    return exc.to_response()


@app.exception_handler(InvalidStatusTransitionError)
async def invalid_status_handler(request: Request, exc: InvalidStatusTransitionError):
    return make_error_response(
        code=ErrorCode.OBLIGATION_INVALID_TRANSITION,
        message=str(exc),
        http_status=status.HTTP_422_UNPROCESSABLE_ENTITY,
    )


@app.exception_handler(InvalidInterventionStatusTransitionError)
async def invalid_intervention_status_handler(request: Request, exc: InvalidInterventionStatusTransitionError):
    return make_error_response(
        code=ErrorCode.OBLIGATION_INVALID_TRANSITION,
        message=str(exc),
        http_status=status.HTTP_422_UNPROCESSABLE_ENTITY,
    )


@app.exception_handler(RequestValidationError)
async def validation_error_handler(request: Request, exc: RequestValidationError):
    # Provide structured validation errors without internal details
    details = []
    for err in exc.errors():
        field_loc = " → ".join(str(l) for l in err.get("loc", []))
        details.append(f"{field_loc}: {err.get('msg', 'Invalid value')}")
    return make_error_response(
        code=ErrorCode.VALIDATION_ERROR,
        message="; ".join(details) or "Request validation failed.",
        http_status=status.HTTP_422_UNPROCESSABLE_ENTITY,
    )


@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception):
    # Log the full exception internally; return a safe generic message
    logger.exception(
        f"Unhandled error on {request.method} {request.url.path}",
        extra={"request_id": get_current_request_id()},
    )
    return make_error_response(
        code=ErrorCode.INTERNAL_ERROR,
        message="An internal server error occurred.",
        http_status=status.HTTP_500_INTERNAL_SERVER_ERROR,
    )


# ---------------------------------------------------------------------------
# Routers
# ---------------------------------------------------------------------------

app.include_router(health.router, prefix="/api")
app.include_router(auth.router, prefix="/api")
app.include_router(workspaces.router, prefix="/api")
app.include_router(obligations.router, prefix="/api")
app.include_router(dashboard.router, prefix="/api")
app.include_router(events_queue_router.router, prefix="/api")
app.include_router(events.router, prefix="/api")
app.include_router(webhooks.router, prefix="/api")
app.include_router(risk.router, prefix="/api")
app.include_router(interventions.router, prefix="/api")
app.include_router(integrations.router, prefix="/api")
app.include_router(reconciliation.router, prefix="/api")
app.include_router(intelligence.router, prefix="/api")
app.include_router(decision_router.router, prefix="/api")
app.include_router(memory_router.router, prefix="/api")
app.include_router(execution_router.router, prefix="/api")
app.include_router(monitoring_router.router, prefix="/api")
app.include_router(search_router.router, prefix="/api")
app.include_router(queues_router.router, prefix="/api")
app.include_router(notifications_router.router, prefix="/api")
app.include_router(import_export_router.router, prefix="/api")
app.include_router(llm_intelligence_router.router)
app.include_router(audit_router.router)



@app.get("/")
async def root():
    return {
        "message": "Obligation Agent API is operational.",
        "version": settings.VERSION,
        "health": "/api/health",
        "ready": "/api/ready",
        "metrics": "/api/metrics",
    }
