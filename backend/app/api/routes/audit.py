"""
REST API Routes — Enterprise Audit, Governance & Compliance.

Provides workspace-scoped audit trail querying, hash-chain verification,
governance summary dashboards, and export endpoints.

RBAC:
  - ADMIN/OWNER: Full access to all endpoints.
  - MEMBER/VIEWER: Only entity-level history (/api/audit/entity/...).
"""

from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Depends, Query, HTTPException, status
from fastapi.responses import Response, StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.auth_deps import get_current_user, get_current_membership
from app.core.status_machine import WorkspaceRole, ROLE_HIERARCHY
from app.models.auth import User, WorkspaceMembership
from app.services.audit_service import AuditService
from app.schemas.audit import (
    AuditEventResponse,
    AuditListResponse,
    AuditVerificationResponse,
    GovernanceSummaryResponse,
)

router = APIRouter(prefix="/api/audit", tags=["Audit & Governance"])

ADMIN_ROLES = {WorkspaceRole.ADMIN, WorkspaceRole.OWNER}


def _require_admin(membership: WorkspaceMembership) -> None:
    """Raises 403 if membership is below ADMIN level."""
    if membership.role not in ADMIN_ROLES:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: Governance center requires ADMIN or OWNER role.",
        )


@router.get("", response_model=AuditListResponse, summary="List workspace audit events")
async def list_audit_events(
    action: Optional[str] = Query(None, description="Filter by action code"),
    actor_user_id: Optional[str] = Query(None),
    entity_type: Optional[str] = Query(None),
    entity_id: Optional[str] = Query(None),
    severity: Optional[str] = Query(None),
    result: Optional[str] = Query(None),
    request_id: Optional[str] = Query(None),
    date_from: Optional[datetime] = Query(None),
    date_to: Optional[datetime] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    session: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
    membership: WorkspaceMembership = Depends(get_current_membership),
) -> AuditListResponse:
    """Returns paginated, filterable workspace audit event log. Requires ADMIN/OWNER."""
    _require_admin(membership)
    items, total = await AuditService.get_workspace_events(
        session=session,
        workspace_id=membership.workspace_id,
        action=action,
        actor_user_id=actor_user_id,
        entity_type=entity_type,
        entity_id=entity_id,
        severity=severity,
        result=result,
        request_id=request_id,
        date_from=date_from,
        date_to=date_to,
        limit=limit,
        offset=offset,
    )
    return AuditListResponse(items=items, total=total, limit=limit, offset=offset)


@router.get("/summary", response_model=GovernanceSummaryResponse, summary="Governance summary dashboard")
async def get_governance_summary(
    session: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
    membership: WorkspaceMembership = Depends(get_current_membership),
) -> GovernanceSummaryResponse:
    """Returns aggregated operational governance metrics for the workspace. Requires ADMIN/OWNER."""
    _require_admin(membership)
    return await AuditService.get_governance_summary(session=session, workspace_id=membership.workspace_id)


@router.get("/verify", response_model=AuditVerificationResponse, summary="Verify audit hash chain")
async def verify_audit_chain(
    session: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
    membership: WorkspaceMembership = Depends(get_current_membership),
) -> AuditVerificationResponse:
    """Verifies the cryptographic SHA-256 hash chain integrity of the workspace audit log. Requires ADMIN/OWNER."""
    _require_admin(membership)
    return await AuditService.verify_chain(session=session, workspace_id=membership.workspace_id)


@router.get("/security", response_model=AuditListResponse, summary="Security events feed")
async def list_security_events(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    session: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
    membership: WorkspaceMembership = Depends(get_current_membership),
) -> AuditListResponse:
    """Returns only security-class audit events (PERMISSION_DENIED, SECURITY_VIOLATION, AUTH_LOGIN_FAILED).
    Requires ADMIN/OWNER."""
    _require_admin(membership)
    from app.core.status_machine import AuditAction
    security_actions = [
        AuditAction.PERMISSION_DENIED.value,
        AuditAction.SECURITY_VIOLATION.value,
        AuditAction.AUTH_LOGIN_FAILED.value,
    ]
    all_items = []
    for sa in security_actions:
        items, _ = await AuditService.get_workspace_events(
            session=session,
            workspace_id=membership.workspace_id,
            action=sa,
            limit=200,
            offset=0,
        )
        all_items.extend(items)
    # Sort by timestamp desc
    all_items.sort(key=lambda e: e.timestamp, reverse=True)
    total = len(all_items)
    paginated = all_items[offset: offset + limit]
    return AuditListResponse(items=paginated, total=total, limit=limit, offset=offset)


@router.get("/export", summary="Export audit log as CSV or JSON")
async def export_audit_log(
    format: str = Query("json", pattern="^(json|csv)$", description="Export format: json or csv"),
    action: Optional[str] = Query(None),
    entity_type: Optional[str] = Query(None),
    severity: Optional[str] = Query(None),
    date_from: Optional[datetime] = Query(None),
    date_to: Optional[datetime] = Query(None),
    session: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
    membership: WorkspaceMembership = Depends(get_current_membership),
) -> Response:
    """Exports workspace audit records as CSV or JSON. Requires ADMIN/OWNER."""
    _require_admin(membership)
    content, mime_type = await AuditService.export_audit_log(
        session=session,
        workspace_id=membership.workspace_id,
        export_format=format,
        action=action,
        entity_type=entity_type,
        severity=severity,
        date_from=date_from,
        date_to=date_to,
    )
    suffix = "csv" if format.lower() == "csv" else "json"
    filename = f"audit_export_{membership.workspace_id}.{suffix}"
    return Response(
        content=content,
        media_type=mime_type,
        headers={
            "Content-Disposition": f"attachment; filename={filename}",
            "X-Total-Records": str(content.count("\n")),
        },
    )


@router.get("/entity/{entity_type}/{entity_id}", response_model=list, summary="Audit history for a specific entity")
async def get_entity_audit_history(
    entity_type: str,
    entity_id: str,
    session: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
    membership: WorkspaceMembership = Depends(get_current_membership),
) -> list:
    """Returns the full chronological audit history for a specific domain entity.
    Available to all workspace members (MEMBER, VIEWER, ADMIN, OWNER)."""
    # Entity-level history is accessible to all roles, not just ADMIN
    return await AuditService.get_entity_history(
        session=session,
        workspace_id=membership.workspace_id,
        entity_type=entity_type,
        entity_id=entity_id,
    )


@router.get("/{audit_id}", response_model=AuditEventResponse, summary="Get single audit event")
async def get_audit_event(
    audit_id: str,
    session: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
    membership: WorkspaceMembership = Depends(get_current_membership),
) -> AuditEventResponse:
    """Returns a single audit event by ID. Requires ADMIN/OWNER."""
    _require_admin(membership)
    items, total = await AuditService.get_workspace_events(
        session=session,
        workspace_id=membership.workspace_id,
        entity_id=audit_id,
        limit=1,
        offset=0,
    )
    # Try direct lookup by audit_id (entity_id match won't work directly, query by ID field)
    from sqlalchemy import select
    from app.models.audit import AuditEvent
    stmt = select(AuditEvent).where(
        AuditEvent.id == audit_id,
        AuditEvent.workspace_id == membership.workspace_id,
    )
    res = await session.execute(stmt)
    event = res.scalar_one_or_none()
    if not event:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Audit event not found.")
    actor_name = event.actor.display_name if event.actor else None
    actor_email = event.actor.email if event.actor else None
    return AuditEventResponse(
        id=event.id,
        workspace_id=event.workspace_id,
        actor_user_id=event.actor_user_id,
        actor_name=actor_name,
        actor_email=actor_email,
        actor_role=event.actor_role,
        action=event.action,
        entity_type=event.entity_type,
        entity_id=event.entity_id,
        timestamp=event.timestamp,
        request_id=event.request_id,
        source=event.source,
        ip_address=event.ip_address,
        user_agent=event.user_agent,
        before_state=event.before_state,
        after_state=event.after_state,
        audit_metadata=event.audit_metadata,
        reason=event.reason,
        severity=event.severity,
        result=event.result,
        previous_event_hash=event.previous_event_hash,
        event_hash=event.event_hash,
    )
