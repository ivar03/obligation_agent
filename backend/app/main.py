from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.core.config import settings
from app.core.logging import setup_logging, logger
from app.core.database import engine, Base
from app.core.status_machine import InvalidStatusTransitionError
from app.core.intervention_status import InvalidInterventionStatusTransitionError
from app.api.routes import health, auth, workspaces, obligations, dashboard, events, risk, interventions, webhooks, integrations, reconciliation, intelligence
from app.api.routes import audit as audit_router
from app.api.routes import decision as decision_router
from app.api.routes import memory as memory_router
from app.api.routes import execution as execution_router
from app.api.routes import monitoring as monitoring_router
from app.api.routes import search as search_router
from app.api.routes import queues as queues_router
from app.api.routes import notifications as notifications_router
from app.api.routes import import_export as import_export_router
from app.core.request_context import RequestContextMiddleware


from app.core.worker import worker_queue


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging()
    logger.info(f"Starting {settings.PROJECT_NAME} v{settings.VERSION}")
    # Auto-create tables for local fast development (in production Alembic is used)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Database tables verified.")
    
    # Start background worker queue
    if settings.WORKER_ENABLED:
        worker_queue.start()
        
    yield
    
    logger.info("Shutting down application...")
    if settings.WORKER_ENABLED:
        await worker_queue.stop()
    await engine.dispose()


app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# Request Correlation Context Middleware (Phase 15)
app.add_middleware(RequestContextMiddleware)

# CORS Configuration
origins = settings.cors_origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins if origins else ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Exception Handlers
@app.exception_handler(InvalidStatusTransitionError)
async def invalid_status_handler(request: Request, exc: InvalidStatusTransitionError):
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={"detail": str(exc), "error_type": "InvalidStatusTransition"},
    )


@app.exception_handler(InvalidInterventionStatusTransitionError)
async def invalid_intervention_status_handler(request: Request, exc: InvalidInterventionStatusTransitionError):
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={"detail": str(exc), "error_type": "InvalidInterventionStatusTransition"},
    )


@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception):
    logger.exception(f"Unhandled error processing request: {request.url.path}")
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "An internal server error occurred.", "error_type": "InternalServerError"},
    )


# Mount Routers under /api
app.include_router(health.router, prefix="/api")
app.include_router(auth.router, prefix="/api")
app.include_router(workspaces.router, prefix="/api")
app.include_router(obligations.router, prefix="/api")
app.include_router(dashboard.router, prefix="/api")
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
app.include_router(audit_router.router)


@app.get("/")
async def root():
    return {
        "message": "Obligation Agent API is operational.",
        "docs": "/docs",
        "health": "/api/health",
    }
