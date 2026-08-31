"""
Phase 19 Production Readiness Diagnostic CLI.

Usage:
    python -m app.ops.production_readiness

Runs a comprehensive suite of production verification checks including:
  - Startup preflight checks (database, schema, configuration, encryption)
  - Durable worker & queue status
  - Integrity checker invariant audit
  - Circuit breaker health status
  - Metrics collector subsystem
  - Backup & disaster recovery status

Returns exit code 0 on pass, 1 on fail.
"""

import sys
import asyncio
from typing import List, Tuple
from sqlalchemy import text, select, func

from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.core.crypto import CryptoService
from app.core.circuit_breaker import get_all_circuit_statuses
from app.core.metrics import metrics
from app.ops.startup_checks import run_all_startup_checks
from app.ops.integrity_checker import IntegrityChecker
from app.ops.backup_restore import list_backups
from app.models.job import BackgroundJobRecord


class DiagnosticRunner:
    def __init__(self):
        self.results: List[Tuple[str, bool, str]] = []

    def record(self, check_name: str, passed: bool, message: str = ""):
        self.results.append((check_name, passed, message))
        status_label = "[PASS]" if passed else "[FAIL]"
        print(f" {status_label} {check_name}: {message}")

    async def run_all(self) -> bool:
        print("=" * 80)
        print(f" OBLIGATION AGENT — PHASE 19 PRODUCTION READINESS DIAGNOSTICS")
        print(f" Environment: {settings.APP_ENV} | Auth Mode: {settings.AUTH_MODE} | Version: {settings.VERSION}")
        print("=" * 80)

        # 1. Startup Preflight Checks
        preflight_results = await run_all_startup_checks()
        for res in preflight_results:
            self.record(f"Preflight: {res.check_name}", res.passed, res.message)

        # 2. Database Session & Model Verification
        async with AsyncSessionLocal() as session:
            try:
                job_count = (await session.execute(select(func.count(BackgroundJobRecord.id)))).scalar() or 0
                self.record("Durable Worker Datastore", True, f"background_jobs table operational ({job_count} jobs tracked).")
            except Exception as exc:
                self.record("Durable Worker Datastore", False, f"Failed to access background_jobs: {exc}")

            # 3. System Invariant Integrity Scan
            try:
                integrity_result = await IntegrityChecker.verify_all(session=session)
                crit_count = integrity_result["critical_violations"]
                if crit_count == 0:
                    self.record("Safety Invariants Audit", True, f"0 critical invariant violations across scanned entities.")
                else:
                    self.record("Safety Invariants Audit", False, f"{crit_count} critical violations detected in data layer.")
            except Exception as exc:
                self.record("Safety Invariants Audit", False, f"Integrity scan error: {exc}")

        # 4. Credential Encryption at Rest
        try:
            test_secret = "test-token-secret-12345"
            enc = CryptoService.encrypt(test_secret)
            dec = CryptoService.decrypt(enc)
            if dec == test_secret:
                self.record("Credential Encryption at Rest", True, "AES/Fernet symmetric encryption operational.")
            else:
                self.record("Credential Encryption at Rest", False, "Decrypted text mismatch.")
        except Exception as e:
            self.record("Credential Encryption at Rest", False, f"Crypto error: {e}")

        # 5. Circuit Breaker & Provider Isolation
        try:
            cb_statuses = get_all_circuit_statuses()
            self.record("Circuit Breaker System", True, f"Registered providers: {list(cb_statuses.keys()) or ['default']}")
        except Exception as exc:
            self.record("Circuit Breaker System", False, f"Circuit breaker error: {exc}")

        # 6. Real-time In-Process Metrics Engine
        try:
            snapshot = metrics.snapshot()
            uptime = snapshot.get("uptime_seconds", 0)
            self.record("Metrics Engine", True, f"Rolling metrics collector operational (Uptime: {uptime}s).")
        except Exception as exc:
            self.record("Metrics Engine", False, f"Metrics error: {exc}")

        # 7. Backup & DR Subsystem
        try:
            backups = list_backups()
            self.record("Disaster Recovery & Backups", True, f"{len(backups)} backups available in manifest repository.")
        except Exception as exc:
            self.record("Disaster Recovery & Backups", False, f"Backup error: {exc}")

        print("=" * 80)
        total = len(self.results)
        passed = sum(1 for _, p, _ in self.results if p)
        failed = total - passed

        if failed == 0:
            print(f" RESULT: ALL {total} CHECKS PASSED. SYSTEM IS FULLY PRODUCTION READY.")
            print("=" * 80)
            return True
        else:
            print(f" RESULT: {failed} OF {total} CHECKS FAILED. RESOLVE BEFORE DEPLOYMENT.")
            print("=" * 80)
            return False


async def main_async():
    runner = DiagnosticRunner()
    success = await runner.run_all()
    sys.exit(0 if success else 1)


def main():
    asyncio.run(main_async())


if __name__ == "__main__":
    main()
