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
    JiraConnectTokenRequest,
    JiraSelectProjectsRequest,
    JiraSyncRequest,
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
    return IntegrationService.generate_oauth_url(provider, redirect_uri, workspace_id=workspace.id)


@router.get("/{provider}/callback")
async def handle_oauth_callback(
    provider: str,
    code: str = Query(..., description="Authorization code from provider"),
    state: str = Query(..., description="OAuth CSRF state token"),
    db: AsyncSession = DatabaseSession,
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


# =============================================================================
# JIRA CLOUD SPECIFIC INTEGRATION ENDPOINTS
# =============================================================================

@router.post("/jira/connect-token")
async def connect_jira_with_token(
    payload: JiraConnectTokenRequest,
    db: AsyncSession = DatabaseSession,
    workspace: Workspace = Depends(get_current_workspace),
    membership: WorkspaceMembership = Depends(require_role(WorkspaceRole.ADMIN)),
    user: User = Depends(get_current_user),
):
    """
    Connects Jira Cloud using API token authentication. Requires workspace ADMIN.
    """
    from app.services.jira_service import JiraService
    return await JiraService.connect_jira(
        session=db,
        workspace_id=workspace.id,
        site_url=payload.site_url,
        email=payload.email,
        api_token=payload.api_token,
    )


@router.get("/jira/projects")
async def list_jira_projects(
    db: AsyncSession = DatabaseSession,
    workspace: Workspace = Depends(get_current_workspace),
    user: User = Depends(get_current_user),
):
    """
    Discovers accessible Jira projects for the active workspace.
    """
    from app.services.jira_service import JiraService
    return await JiraService.list_projects(session=db, workspace_id=workspace.id)


@router.post("/jira/projects")
async def select_jira_projects(
    payload: JiraSelectProjectsRequest,
    db: AsyncSession = DatabaseSession,
    workspace: Workspace = Depends(get_current_workspace),
    membership: WorkspaceMembership = Depends(require_role(WorkspaceRole.ADMIN)),
    user: User = Depends(get_current_user),
):
    """
    Updates the list of Jira projects to synchronize for the active workspace. Requires ADMIN.
    """
    from app.services.jira_service import JiraService
    return await JiraService.select_projects(
        session=db,
        workspace_id=workspace.id,
        project_keys=payload.project_keys,
    )


@router.post("/jira/sync")
async def trigger_jira_sync(
    payload: Optional[JiraSyncRequest] = None,
    db: AsyncSession = DatabaseSession,
    workspace: Workspace = Depends(get_current_workspace),
    membership: WorkspaceMembership = Depends(require_role(WorkspaceRole.ADMIN)),
    user: User = Depends(get_current_user),
):
    """
    Triggers an on-demand synchronization of Jira issues into the event pipeline. Requires ADMIN.
    """
    from app.services.jira_service import JiraService
    project_keys = payload.project_keys if payload else None
    return await JiraService.sync_issues(
        session=db,
        workspace_id=workspace.id,
        project_keys=project_keys,
    )


@router.post("/gmail/watch")
async def start_gmail_watch(
    db: AsyncSession = DatabaseSession,
    workspace: Workspace = Depends(get_current_workspace),
    membership: WorkspaceMembership = Depends(require_role(WorkspaceRole.ADMIN)),
    user: User = Depends(get_current_user),
):
    """Registers or renews the Gmail mailbox watch for the connected account."""
    from app.services.google_workspace_service import GoogleWorkspaceService
    return await GoogleWorkspaceService.start_gmail_watch(db, workspace.id)


@router.post("/gmail/sync")
async def sync_gmail(
    db: AsyncSession = DatabaseSession,
    workspace: Workspace = Depends(get_current_workspace),
    membership: WorkspaceMembership = Depends(require_role(WorkspaceRole.ADMIN)),
    user: User = Depends(get_current_user),
):
    """Pulls recent Gmail messages; useful before a public webhook is available."""
    from app.services.google_workspace_service import GoogleWorkspaceService
    return await GoogleWorkspaceService.sync_gmail(db, workspace.id)


@router.post("/google_calendar/sync")
@router.post("/google-calendar/sync")
async def sync_google_calendar(
    db: AsyncSession = DatabaseSession,
    workspace: Workspace = Depends(get_current_workspace),
    membership: WorkspaceMembership = Depends(require_role(WorkspaceRole.ADMIN)),
    user: User = Depends(get_current_user),
):
    """Pulls upcoming Calendar events; useful before a public webhook is available."""
    from app.services.google_workspace_service import GoogleWorkspaceService
    return await GoogleWorkspaceService.sync_calendar(db, workspace.id)


@router.get("/jira/sync/status")
async def get_jira_sync_status(
    db: AsyncSession = DatabaseSession,
    workspace: Workspace = Depends(get_current_workspace),
    user: User = Depends(get_current_user),
):
    """
    Returns current sync status, selected projects, and last synced timestamp.
    """
    from app.services.jira_service import JiraService
    return await JiraService.get_sync_status(session=db, workspace_id=workspace.id)

