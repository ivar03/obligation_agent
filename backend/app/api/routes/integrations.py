from typing import Optional
from fastapi import APIRouter, status, HTTPException, Query, Request, Response, Depends
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import DatabaseSession
from app.core.config import settings
from app.core.status_machine import WorkspaceRole
from app.models.auth import User, Workspace, WorkspaceMembership
from app.core.auth_deps import (
    get_current_user,
    get_current_membership,
    get_current_workspace,
    require_role,
)
from app.schemas.integration import (
    IntegrationConnectionResponse,
    IntegrationListResponse,
    IntegrationTestResponse,
    OAuthConnectResponse,
)
from app.services.integration_service import IntegrationService

router = APIRouter(prefix="/integrations", tags=["Integrations & Connections"])


@router.get("", response_model=IntegrationListResponse)
async def list_integrations(
    db: AsyncSession = DatabaseSession,
    workspace: Workspace = Depends(get_current_workspace),
    user: User = Depends(get_current_user),
):
    """
    Lists all connected external providers and registered adapter capabilities for active workspace.
    Never exposes secrets or credentials.
    """
    return await IntegrationService.list_connections(db, workspace_id=workspace.id)


@router.get("/{provider}", response_model=IntegrationConnectionResponse)
async def get_integration(
    provider: str,
    db: AsyncSession = DatabaseSession,
    workspace: Workspace = Depends(get_current_workspace),
    user: User = Depends(get_current_user),
):
    """
    Retrieves safe connection status for a specific provider in the active workspace.
    """
    conn = await IntegrationService.get_connection(db, provider, workspace_id=workspace.id)
    if not conn:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No connection found for provider '{provider}'.",
        )
    return conn


@router.get("/{provider}/connect", response_model=OAuthConnectResponse)
async def initiate_oauth_connect(
    provider: str,
    redirect_uri: Optional[str] = Query(None),
    workspace: Workspace = Depends(get_current_workspace),
    membership: WorkspaceMembership = Depends(require_role(WorkspaceRole.ADMIN)),
    user: User = Depends(get_current_user),
):
    """
    Generates an OAuth authorization URL with CSRF protection state. Requires ADMIN or higher.
    """
    return IntegrationService.generate_oauth_url(provider, redirect_uri)


@router.get("/{provider}/callback")
async def handle_oauth_callback(
    provider: str,
    code: str = Query(..., description="Authorization code from provider"),
    state: str = Query(..., description="OAuth CSRF state token"),
    db: AsyncSession = DatabaseSession,
    workspace: Workspace = Depends(get_current_workspace),
):
    """
    OAuth redirect callback endpoint.
    Exchanges code, verifies state, stores connection, and redirects back to frontend integrations page.
    """
    conn = await IntegrationService.handle_oauth_callback(
        session=db,
        provider_name=provider,
        code=code,
        state=state,
        workspace_id=workspace.id,
    )
    # Redirect to frontend integrations page with success parameter
    frontend_redirect = f"{settings.FRONTEND_URL}/integrations?connected={provider}&status=success"
    return RedirectResponse(url=frontend_redirect, status_code=status.HTTP_302_FOUND)


@router.post("/{provider}/callback", response_model=IntegrationConnectionResponse)
async def handle_oauth_callback_direct(
    provider: str,
    code: str = Query(..., description="Authorization code from provider"),
    state: str = Query(..., description="OAuth CSRF state token"),
    db: AsyncSession = DatabaseSession,
    workspace: Workspace = Depends(get_current_workspace),
    membership: WorkspaceMembership = Depends(require_role(WorkspaceRole.ADMIN)),
    user: User = Depends(get_current_user),
):
    """
    Direct API OAuth exchange endpoint for headless / programmatic clients and automated testing.
    """
    return await IntegrationService.handle_oauth_callback(
        session=db,
        provider_name=provider,
        code=code,
        state=state,
        workspace_id=workspace.id,
    )


@router.post("/{provider}/test", response_model=IntegrationTestResponse)
async def test_integration_connection(
    provider: str,
    db: AsyncSession = DatabaseSession,
    workspace: Workspace = Depends(get_current_workspace),
    membership: WorkspaceMembership = Depends(require_role(WorkspaceRole.ADMIN)),
    user: User = Depends(get_current_user),
):
    """
    Tests whether the external provider connection is valid and reachable. Requires ADMIN or higher.
    """
    return await IntegrationService.test_connection(db, provider, workspace_id=workspace.id)


@router.post("/{provider}/disconnect", response_model=IntegrationConnectionResponse)
@router.delete("/{provider}", response_model=IntegrationConnectionResponse)
async def disconnect_integration(
    provider: str,
    db: AsyncSession = DatabaseSession,
    workspace: Workspace = Depends(get_current_workspace),
    membership: WorkspaceMembership = Depends(require_role(WorkspaceRole.ADMIN)),
    user: User = Depends(get_current_user),
):
    """
    Disconnects an active external provider. Requires ADMIN or higher.
    """
    return await IntegrationService.disconnect(db, provider, workspace_id=workspace.id)
