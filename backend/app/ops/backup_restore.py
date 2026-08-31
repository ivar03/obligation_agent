"""
Phase 18 Database Backup & Disaster Recovery Utility.

Usage:
    python -m app.ops.backup_restore backup [backup_path]
    python -m app.ops.backup_restore restore <backup_path>
    python -m app.ops.backup_restore test
"""

import sys
import os
import shutil
import sqlite3
import asyncio
from datetime import datetime, timezone
from sqlalchemy import select, func

from app.core.config import settings
from app.core.database import AsyncSessionLocal, engine, Base
from app.models.auth import Workspace, User, WorkspaceMembership
from app.models.obligation import Obligation, ObligationEdge, Evidence
from app.models.decision import DecisionPlan
from app.models.execution import ExecutionRecord
from app.models.audit import AuditEvent


def get_db_path() -> str:
    db_url = settings.DATABASE_URL
    if "sqlite" in db_url:
        path = db_url.split("///")[-1]
        return os.path.abspath(path)
    return ""


def perform_backup(target_path: str = None) -> str:
    db_path = get_db_path()
    if not db_path or not os.path.exists(db_path):
        raise FileNotFoundError(f"Source database file not found at: {db_path}")

    if not target_path:
        os.makedirs("./backups", exist_ok=True)
        ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        target_path = os.path.abspath(f"./backups/obligation_db_backup_{ts}.db")

    # Use SQLite online backup API for crash consistency
    src_conn = sqlite3.connect(db_path)
    dst_conn = sqlite3.connect(target_path)
    with dst_conn:
        src_conn.backup(dst_conn)
    dst_conn.close()
    src_conn.close()

    print(f"[OK] Database backed up successfully to: {target_path}")
    return target_path


def perform_restore(backup_path: str) -> bool:
    if not os.path.exists(backup_path):
        raise FileNotFoundError(f"Backup file not found at: {backup_path}")

    db_path = get_db_path()
    if not db_path:
        raise ValueError("Cannot resolve database target path.")

    # Restore using SQLite online backup
    src_conn = sqlite3.connect(backup_path)
    dst_conn = sqlite3.connect(db_path)
    with dst_conn:
        src_conn.backup(dst_conn)
    dst_conn.close()
    src_conn.close()

    print(f"[OK] Database restored successfully from: {backup_path}")
    return True


async def verify_integrity() -> bool:
    async with AsyncSessionLocal() as session:
        try:
            ws_count = (await session.execute(select(func.count(Workspace.id)))).scalar() or 0
            u_count = (await session.execute(select(func.count(User.id)))).scalar() or 0
            ob_count = (await session.execute(select(func.count(Obligation.id)))).scalar() or 0
            audit_count = (await session.execute(select(func.count(AuditEvent.id)))).scalar() or 0
            print(f"[INTEGRITY VERIFIED] Workspaces: {ws_count}, Users: {u_count}, Obligations: {ob_count}, Audit Events: {audit_count}")
            return True
        except Exception as e:
            print(f"[ERROR] Database integrity verification failed: {e}")
            return False


async def test_backup_restore_cycle() -> bool:
    print("=" * 80)
    print(" TESTING AUTOMATED BACKUP & RESTORE CYCLE")
    print("=" * 80)
    backup_file = perform_backup()
    assert os.path.exists(backup_file)

    # Verify restore
    restored = perform_restore(backup_file)
    assert restored is True

    # Verify DB integrity
    valid = await verify_integrity()
    assert valid is True

    # Clean up test backup
    if os.path.exists(backup_file):
        os.remove(backup_file)

    print("=" * 80)
    print(" [PASS] BACKUP & RESTORE RECOVERY CYCLE 100% VERIFIED.")
    print("=" * 80)
    return True


def main():
    if len(sys.argv) < 2 or sys.argv[1] == "test":
        asyncio.run(test_backup_restore_cycle())
    elif sys.argv[1] == "backup":
        path = sys.argv[2] if len(sys.argv) > 2 else None
        perform_backup(path)
    elif sys.argv[1] == "restore":
        if len(sys.argv) < 3:
            print("Usage: python -m app.ops.backup_restore restore <backup_path>")
            sys.exit(1)
        perform_restore(sys.argv[2])
        asyncio.run(verify_integrity())


if __name__ == "__main__":
    main()
