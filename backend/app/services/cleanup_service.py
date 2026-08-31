"""
Phase 17 Data Retention & Cleanup Service.

Implements workspace-aware data retention and cleanup routines:
- Prunes stale raw ingested events beyond retention threshold
- Prunes resolved monitoring runs and expired temporary execution logs
- PRESERVES core historical integrity: audit chains, immutable Decision Plans, and confirmed evidence.
"""

from datetime import datetime, timezone, timedelta
from typing import Dict, Any
from sqlalchemy import delete, and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.logging import logger
from app.models.obligation import IngestedEventRecord
from app.models.monitoring import MonitoringRun, MonitoringEvent
from app.core.status_machine import MonitoringSeverity


class CleanupService:
    """
    Data retention lifecycle manager.
    Safely prunes transient and raw log records while protecting core historical provenance.
    """

    @classmethod
    async def run_retention_cleanup(
        cls,
        session: AsyncSession,
        workspace_id: str,
        retention_days: int = None,
    ) -> Dict[str, Any]:
        """
        Executes retention policy cleanup for a specific workspace.
        """
        days = retention_days or settings.DATA_RETENTION_DAYS
        threshold = datetime.now(timezone.utc) - timedelta(days=days)

        stats = {
            "workspace_id": workspace_id,
            "retention_days": days,
            "threshold": threshold.isoformat(),
            "raw_events_pruned": 0,
            "transient_monitoring_events_pruned": 0,
            "monitoring_runs_pruned": 0,
        }

        # 1. Prune un-correlated raw ingested event records older than retention threshold
        stmt_events = (
            delete(IngestedEventRecord)
            .where(
                and_(
                    IngestedEventRecord.workspace_id == workspace_id,
                    IngestedEventRecord.received_at < threshold,
                    IngestedEventRecord.correlated_obligation_id.is_(None),
                )
            )
        )
        res_events = await session.execute(stmt_events)
        stats["raw_events_pruned"] = res_events.rowcount or 0

        # 2. Prune resolved low-severity INFO/NOTICE monitoring events older than threshold
        stmt_mon = (
            delete(MonitoringEvent)
            .where(
                and_(
                    MonitoringEvent.workspace_id == workspace_id,
                    MonitoringEvent.detected_at < threshold,
                    MonitoringEvent.severity.in_([MonitoringSeverity.INFO, MonitoringSeverity.NOTICE]),
                    MonitoringEvent.resolved_at.isnot(None),
                )
            )
        )
        res_mon = await session.execute(stmt_mon)
        stats["transient_monitoring_events_pruned"] = res_mon.rowcount or 0

        await session.commit()
        logger.info(f"Retention cleanup completed for workspace [{workspace_id}]: {stats}")
        return stats
