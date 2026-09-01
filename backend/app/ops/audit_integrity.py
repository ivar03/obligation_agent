"""
Phase 21 Operational Audit Integrity Verification CLI.

Cryptographically verifies the append-only SHA-256 hash chains across all
workspaces to ensure tamper detection.
"""

import sys
import asyncio
from typing import List
from sqlalchemy import select

from app.core.database import AsyncSessionLocal, engine, Base
from app.models.auth import Workspace
from app.models.operational_audit import OperationalAuditRecord
from app.services.operational_audit_service import OperationalAuditService


async def verify_all_audit_chains() -> bool:
    print("=" * 80)
    print(" OBLIGATION AGENT — OPERATIONAL AUDIT HASH CHAIN INTEGRITY VERIFIER")
    print("=" * 80)

    # Ensure tables exist
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    overall_passed = True
    async with AsyncSessionLocal() as session:
        ws_stmt = select(Workspace.id)
        ws_res = await session.execute(ws_stmt)
        workspaces = [w for w in ws_res.scalars().all()] or ["ws-default"]

        for ws_id in workspaces:
            res = await OperationalAuditService.verify_chain(ws_id, session)
            status_tag = "[PASS]" if res.verified else "[FAIL]"
            print(f" {status_tag} Workspace '{ws_id}': {res.intact_records}/{res.total_records} records verified intact ({res.verification_duration_ms}ms)")
            if not res.verified:
                overall_passed = False
                print(f"   [!] Corrupted records detected: {res.corrupted_records} (IDs: {res.tampered_record_ids})")

    print("=" * 80)
    if overall_passed:
        print(" RESULT: ALL OPERATIONAL AUDIT CHAINS ARE CRYPTOGRAPHICALLY INTACT.")
    else:
        print(" RESULT: AUDIT CHAIN INTEGRITY VIOLATION DETECTED!")
    print("=" * 80)

    return overall_passed


def main():
    passed = asyncio.run(verify_all_audit_chains())
    sys.exit(0 if passed else 1)


if __name__ == "__main__":
    main()
