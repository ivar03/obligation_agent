"""
Phase 18 Bulk CSV Ingestion & Validation Service.

Provides robust CSV stream parsing, row validation, duplicate detection,
dependency relationship resolution, and atomic batch commitment.
"""

import csv
import io
import uuid
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional, Tuple
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.status_machine import (
    ObligationStatus,
    ObligationType,
    EdgeType,
    AuditAction,
)
from app.models.obligation import Obligation, ObligationEdge
from app.schemas.import_export import (
    CsvRowValidation,
    CsvImportPreviewResponse,
    CsvImportCommitResponse,
)
from app.services.audit_service import AuditService
from app.services.graph_service import GraphService


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def parse_flexible_date(date_str: str) -> Optional[datetime]:
    if not date_str or not date_str.strip():
        return None
    cleaned = date_str.strip()
    # Try multiple standard formats
    formats = [
        "%Y-%m-%dT%H:%M:%S%z",
        "%Y-%m-%dT%H:%M:%SZ",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d",
        "%d/%m/%Y",
        "%m/%d/%Y",
    ]
    for fmt in formats:
        try:
            dt = datetime.strptime(cleaned, fmt)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt
        except ValueError:
            continue
    return None


class CsvImportService:
    """
    Handles CSV parsing, row-level validation, duplicate checking, and atomic ingestion.
    """

    @classmethod
    async def preview_csv(
        cls,
        session: AsyncSession,
        workspace_id: str,
        csv_text: str,
    ) -> CsvImportPreviewResponse:
        # Load existing actions in this workspace for duplicate detection
        stmt = select(Obligation.action).where(Obligation.workspace_id == workspace_id)
        existing_actions = set((await session.execute(stmt)).scalars().all())

        reader = csv.DictReader(io.StringIO(csv_text.strip()))
        if not reader.fieldnames:
            return CsvImportPreviewResponse(
                total_rows=0,
                valid_rows_count=0,
                invalid_rows_count=0,
                validation_results=[],
                detected_duplicates=[],
                can_commit=False,
            )

        # Normalize header keys to lowercase
        results: List[CsvRowValidation] = []
        seen_in_batch = set()
        duplicates = []

        for idx, raw_row in enumerate(reader, start=1):
            row = {k.strip().lower(): (v.strip() if v else "") for k, v in raw_row.items() if k}
            errors = []

            # 1. Action requirement
            action = row.get("action") or row.get("title") or row.get("commitment")
            if not action:
                errors.append("Missing required field 'action'.")

            # 2. Owner requirement
            owner = row.get("owner") or row.get("assignee") or row.get("person")
            if not owner:
                errors.append("Missing required field 'owner'.")

            # 3. Beneficiary (optional, defaults to Company)
            beneficiary = row.get("beneficiary") or row.get("recipient") or "Company"

            # 4. Deadline parsing
            raw_deadline = row.get("deadline") or row.get("due_date") or row.get("due")
            deadline_dt = None
            if raw_deadline:
                deadline_dt = parse_flexible_date(raw_deadline)
                if not deadline_dt:
                    errors.append(f"Invalid deadline date format '{raw_deadline}'. Expected YYYY-MM-DD.")

            # 5. Priority parsing
            raw_priority = (row.get("priority") or "MEDIUM").upper()
            priority = raw_priority if raw_priority in ("LOW", "MEDIUM", "HIGH", "CRITICAL") else "MEDIUM"

            # 6. Type parsing
            raw_type = (row.get("type") or row.get("obligation_type") or "OWED_BY_ME").upper()
            try:
                ob_type = ObligationType(raw_type)
            except ValueError:
                ob_type = ObligationType.OWED_BY_ME

            # 7. Duplicate checking
            if action:
                action_norm = action.strip().lower()
                if action_norm in existing_actions or action_norm in seen_in_batch:
                    duplicates.append(action)
                seen_in_batch.add(action_norm)

            parsed = None
            is_valid = len(errors) == 0
            if is_valid:
                parsed = {
                    "row_index": idx,
                    "action": action,
                    "owner": owner,
                    "beneficiary": beneficiary,
                    "description": row.get("description", ""),
                    "deadline": deadline_dt.isoformat() if deadline_dt else None,
                    "priority": priority,
                    "obligation_type": ob_type.value,
                    "source": row.get("source", "csv_import"),
                    "dependencies": [d.strip() for d in (row.get("dependencies") or "").split(",") if d.strip()],
                }

            results.append(CsvRowValidation(
                row_index=idx,
                is_valid=is_valid,
                errors=errors,
                parsed_data=parsed,
            ))

        valid_count = sum(1 for r in results if r.is_valid)
        invalid_count = len(results) - valid_count

        return CsvImportPreviewResponse(
            total_rows=len(results),
            valid_rows_count=valid_count,
            invalid_rows_count=invalid_count,
            validation_results=results,
            detected_duplicates=duplicates,
            can_commit=valid_count > 0,
        )

    @classmethod
    async def commit_import(
        cls,
        session: AsyncSession,
        workspace_id: str,
        user_id: str,
        rows: List[Dict[str, Any]],
        skip_duplicates: bool = True,
    ) -> CsvImportCommitResponse:
        stmt = select(Obligation.action).where(Obligation.workspace_id == workspace_id)
        existing_actions = set((await session.execute(stmt)).scalars().all())

        created_obs: List[Obligation] = []
        action_to_ob: Dict[str, Obligation] = {}
        errors = []

        for r in rows:
            action = r.get("action")
            if not action:
                continue

            if skip_duplicates and action.strip().lower() in existing_actions:
                continue

            deadline_dt = parse_flexible_date(r.get("deadline")) if r.get("deadline") else None
            ob_type = ObligationType(r.get("obligation_type", ObligationType.OWED_BY_ME.value))

            ob = Obligation(
                id=f"ob-{uuid.uuid4().hex[:8]}",
                workspace_id=workspace_id,
                owner=r.get("owner", "Unassigned"),
                beneficiary=r.get("beneficiary", "Company"),
                action=action,
                status=ObligationStatus.CONFIRMED,
                obligation_type=ob_type,
                deadline=deadline_dt,
                source_ref=r.get("source", "csv_import"),
            )
            session.add(ob)
            created_obs.append(ob)
            action_to_ob[action.strip().lower()] = ob
            existing_actions.add(action.strip().lower())

        await session.flush()

        # Connect dependencies
        created_edge_count = 0
        for r in rows:
            dep_names = r.get("dependencies", [])
            from_ob = action_to_ob.get(r.get("action", "").strip().lower())
            if not from_ob or not dep_names:
                continue

            for dep_name in dep_names:
                to_ob = action_to_ob.get(dep_name.strip().lower())
                if to_ob and to_ob.id != from_ob.id:
                    edge = ObligationEdge(
                        id=f"edge-{uuid.uuid4().hex[:8]}",
                        workspace_id=workspace_id,
                        from_obligation_id=from_ob.id,
                        to_obligation_id=to_ob.id,
                        edge_type=EdgeType.DEPENDS_ON,
                    )
                    session.add(edge)
                    created_edge_count += 1

        # Audit
        await AuditService.record(
            session=session,
            workspace_id=workspace_id,
            action=AuditAction.OBLIGATION_CREATED,
            actor_user_id=user_id,
            entity_type="bulk_import",
            reason=f"Bulk imported {len(created_obs)} obligations via CSV with {created_edge_count} dependency edges.",
        )

        await session.commit()

        return CsvImportCommitResponse(
            imported_count=len(created_obs),
            created_obligation_ids=[o.id for o in created_obs],
            created_edge_count=created_edge_count,
            errors=errors,
        )
