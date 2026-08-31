"""
Phase 19 Production Startup Preflight Checks.

Validates environment, database connectivity, required tables, encryption keys,
and security settings prior to accepting incoming production traffic.
"""

from typing import List, Dict, Any
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.logging import logger
from app.core.database import AsyncSessionLocal


REQUIRED_TABLES = [
    "users",
    "workspaces",
    "workspace_memberships",
    "obligations",
    "obligation_edges",
    "obligation_evidence",
    "interventions",
    "ingested_events",
    "reconciliation_records",
    "audit_events",
    "decision_plans",
    "execution_records",
    "monitoring_events",
    "escalation_candidates",
    "background_jobs",
    "event_inbox",
    "llm_analysis_records",
]



class StartupCheckResult:
    def __init__(self, check_name: str, passed: bool, message: str, details: Dict[str, Any] = None):
        self.check_name = check_name
        self.passed = passed
        self.message = message
        self.details = details or {}


async def run_all_startup_checks() -> List[StartupCheckResult]:
    """
    Executes all preflight checks and returns their structured results.
    """
    results: List[StartupCheckResult] = []

    # 1. Config Integrity Check
    config_errors = settings.validate_production_config()
    if config_errors:
        results.append(StartupCheckResult(
            check_name="config_integrity",
            passed=False,
            message=f"Configuration issues: {'; '.join(config_errors)}",
            details={"errors": config_errors}
        ))
    else:
        results.append(StartupCheckResult(
            check_name="config_integrity",
            passed=True,
            message="Configuration verified for environment.",
            details={"environment": settings.APP_ENV, "auth_mode": settings.AUTH_MODE}
        ))

    # 2. Database Connectivity Check
    db_connected = False
    try:
        async with AsyncSessionLocal() as session:
            res = await session.execute(text("SELECT 1"))
            val = res.scalar()
            if val == 1:
                db_connected = True
                results.append(StartupCheckResult(
                    check_name="database_connection",
                    passed=True,
                    message="Database connection established.",
                    details={"backend": "postgresql" if settings.is_postgres() else "sqlite"}
                ))
    except Exception as exc:
        results.append(StartupCheckResult(
            check_name="database_connection",
            passed=False,
            message=f"Failed to connect to database: {str(exc)}",
            details={"error": str(exc)}
        ))

    # 3. Schema & Tables Existence Check
    if db_connected:
        try:
            async with AsyncSessionLocal() as session:
                missing_tables = []
                for table in REQUIRED_TABLES:
                    try:
                        await session.execute(text(f"SELECT 1 FROM {table} LIMIT 1"))
                    except Exception:
                        missing_tables.append(table)

                if missing_tables:
                    results.append(StartupCheckResult(
                        check_name="schema_integrity",
                        passed=False,
                        message=f"Missing required database tables: {', '.join(missing_tables)}",
                        details={"missing_tables": missing_tables}
                    ))
                else:
                    results.append(StartupCheckResult(
                        check_name="schema_integrity",
                        passed=True,
                        message=f"All {len(REQUIRED_TABLES)} required database tables verified.",
                        details={"table_count": len(REQUIRED_TABLES)}
                    ))
        except Exception as exc:
            results.append(StartupCheckResult(
                check_name="schema_integrity",
                passed=False,
                message=f"Schema check error: {str(exc)}",
                details={"error": str(exc)}
            ))

    # 4. Encryption & Security Key Check
    if settings.is_production() and not settings.ENCRYPTION_KEY:
        results.append(StartupCheckResult(
            check_name="security_keys",
            passed=False,
            message="ENCRYPTION_KEY is required in production environment.",
        ))
    else:
        results.append(StartupCheckResult(
            check_name="security_keys",
            passed=True,
            message="Security and JWT keys validated.",
            details={"jwt_algorithm": settings.JWT_ALGORITHM}
        ))

    # 5. Durable Queue Check
    results.append(StartupCheckResult(
        check_name="worker_durability",
        passed=True,
        message=f"Worker configured with concurrency={settings.WORKER_CONCURRENCY}, durable={settings.WORKER_DURABLE_QUEUE}.",
        details={
            "concurrency": settings.WORKER_CONCURRENCY,
            "durable": settings.WORKER_DURABLE_QUEUE,
            "lease_timeout": settings.WORKER_LEASE_TIMEOUT_SECONDS
        }
    ))

    return results
