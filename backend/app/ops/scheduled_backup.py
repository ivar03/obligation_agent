"""
Phase 19 Scheduled Backup Runner.

Entry point for cron jobs, container schedulers (e.g., Kubernetes CronJob,
AWS ECS scheduled tasks), or systemd timers to execute scheduled backups.
"""

import sys
import logging
from app.core.config import settings
from app.ops.backup_restore import perform_backup, prune_old_backups

logging.basicConfig(level=logging.INFO, format="[%(asctime)s] [%(levelname)s]: %(message)s")
logger = logging.getLogger("scheduled_backup")


def run_scheduled_backup():
    logger.info("Initiating scheduled database backup...")
    try:
        manifest = perform_backup()
        logger.info(f"Backup succeeded: {manifest['backup_file']} ({manifest['size_bytes']} bytes, SHA256: {manifest['sha256'][:12]}...)")
        pruned = prune_old_backups(keep_count=settings.BACKUP_RETENTION_COUNT)
        logger.info(f"Scheduled backup complete. Pruned {pruned} old backup(s).")
        sys.exit(0)
    except Exception as exc:
        logger.error(f"Scheduled backup failed: {exc}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    run_scheduled_backup()
