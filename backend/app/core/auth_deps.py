from typing import Optional, Callable
from fastapi import Request, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.auth import User, Workspace, WorkspaceMembership
from app.core.status_machine import WorkspaceRole, ROLE_HIERARCHY, has_permission
from app.core.security import decode_session_token
from app.services.auth_service import AuthService


async def get_current_user_optional(
    request: Request,
    session: AsyncSession = Depends(get_db),
) -> Optional[User]:
    """
    Extracts the authenticated user from Bearer token or HTTP-only cookie if present.
    """
    token = None
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        token = auth_header[7:].strip()
    elif "obligation_session" in request.cookies:
        token = request.cookies.get("obligation_session")
    elif "session_token" in request.cookies:
        token = request.cookies.get("session_token")

    if token:
        payload = decode_session_token(token)
        if payload and "sub" in payload:
            user = await session.get(User, payload["sub"])
            if user and user.is_active:
                return user
    return None


async def get_current_user(
    request: Request,
    session: AsyncSession = Depends(get_db),
) -> User:
    """
    FastAPI dependency resolving the current authenticated user.
    In production mode (AUTH_MODE=production or APP_ENV=production), rejects unauthenticated requests with 401.
    In development/testing mode (AUTH_MODE=mock), falls back cleanly to default dev user ('usr-default')
    when no authentication token is provided, preserving regression suites.
    """
    user = await get_current_user_optional(request, session)
    if user:
        return user

    # Check if explicit invalid token was passed
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        token = auth_header[7:].strip()
        if token and token != "dev-token":
            # Token was provided but invalid/expired
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired authentication session.",
                headers={"WWW-Authenticate": "Bearer"},
            )

    # In production mode, reject unauthenticated requests
    from app.core.config import settings
    if settings.is_production_auth():
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required. Please provide a valid Bearer token.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # In dev/test mode without credentials, fall back to default demo user
    dev_user, _, _ = await AuthService.ensure_default_dev_user(session)
    return dev_user


async def get_current_membership(
    request: Request,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> WorkspaceMembership:
    """
    Resolves the active WorkspaceMembership for the current user and requested workspace.
    """
    # Check if a specific workspace is requested via header or cookie
    requested_ws_id = (
        request.headers.get("X-Workspace-Id")
        or request.cookies.get("obligation_workspace")
        or request.query_params.get("workspace_id")
    )

    if requested_ws_id:
        stmt = select(WorkspaceMembership).where(
            WorkspaceMembership.workspace_id == requested_ws_id,
            WorkspaceMembership.user_id == user.id,
        )
        res = await session.execute(stmt)
        mem = res.scalar_one_or_none()
        if not mem:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied: You are not a member of workspace '{requested_ws_id}'.",
            )
        return mem

    # Fallback to user's first workspace membership
    mem_stmt = select(WorkspaceMembership).where(
        WorkspaceMembership.user_id == user.id
    ).order_by(WorkspaceMembership.created_at.asc())
    mem_res = await session.execute(mem_stmt)
    mem = mem_res.scalars().first()

    if not mem:
        # User has no memberships; ensure default dev workspace membership
        _, _, default_mem = await AuthService.ensure_default_dev_user(session)
        # If user is different from dev_user, create membership in default workspace
        if user.id != "usr-default":
            mem = WorkspaceMembership(
                workspace_id="ws-default",
                user_id=user.id,
                role=WorkspaceRole.OWNER,
            )
            session.add(mem)
            await session.commit()
            return mem
        return default_mem

    return mem


async def get_current_workspace(
    membership: WorkspaceMembership = Depends(get_current_membership),
    session: AsyncSession = Depends(get_db),
) -> Workspace:
    """
    FastAPI dependency returning the active Workspace object.
    """
    ws = await session.get(Workspace, membership.workspace_id)
    if not ws:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Workspace not found.",
        )
    return ws


def require_role(min_role: WorkspaceRole) -> Callable:
    """
    Dependency factory enforcing that the user has at least the specified minimum role
    in the active workspace. Records PERMISSION_DENIED audit events on failure.
    """
    async def role_checker(
        request: Request,
        membership: WorkspaceMembership = Depends(get_current_membership),
        session: AsyncSession = Depends(get_db),
    ) -> WorkspaceMembership:
        user_role = membership.role
        if ROLE_HIERARCHY.get(user_role, 0) < ROLE_HIERARCHY.get(min_role, 0):
            # Record security audit event for permission denial
            try:
                from app.services.audit_service import AuditService
                from app.core.status_machine import AuditAction, AuditSeverity, AuditResult
                await AuditService.record_security_event(
                    session=session,
                    workspace_id=membership.workspace_id,
                    action=AuditAction.PERMISSION_DENIED,
                    actor_user_id=membership.user_id,
                    actor_role=user_role.value if hasattr(user_role, "value") else str(user_role),
                    reason=f"Role '{user_role.value}' is below required minimum role '{min_role.value}'",
                    metadata={"required_role": min_role.value, "user_role": user_role.value, "path": str(request.url.path)},
                    severity=AuditSeverity.WARNING,
                    result=AuditResult.DENIED,
                )
                await session.commit()
            except Exception:
                pass  # Never block the auth check on audit failures
            # Security: return 403 (not 404) for role failures since caller knows they're authenticated
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Forbidden: Action requires at least '{min_role.value}' role.",
            )
        return membership

    return role_checker


def require_permission(capability: str) -> Callable:
    """
    Dependency factory enforcing granular capability authorization.
    Records PERMISSION_DENIED audit events on failure.
    """
    async def perm_checker(
        request: Request,
        membership: WorkspaceMembership = Depends(get_current_membership),
        session: AsyncSession = Depends(get_db),
    ) -> WorkspaceMembership:
        user_role = membership.role
        if not has_permission(user_role, capability):
            try:
                from app.services.audit_service import AuditService
                from app.core.status_machine import AuditAction, AuditSeverity, AuditResult
                await AuditService.record_security_event(
                    session=session,
                    workspace_id=membership.workspace_id,
                    action=AuditAction.PERMISSION_DENIED,
                    actor_user_id=membership.user_id,
                    actor_role=user_role.value if hasattr(user_role, "value") else str(user_role),
                    reason=f"Role '{user_role.value}' lacks capability '{capability}'",
                    metadata={"required_capability": capability, "user_role": user_role.value, "path": str(request.url.path)},
                    severity=AuditSeverity.WARNING,
                    result=AuditResult.DENIED,
                )
                await session.commit()
            except Exception:
                pass
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Forbidden: Role '{membership.role.value}' lacks capability '{capability}'.",
            )
        return membership

    return perm_checker
