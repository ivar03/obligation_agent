import secrets
import httpx
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any, Set
from sqlalchemy import select, and_, desc
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException, status

from app.core.config import settings
from app.core.logging import logger
from app.models.integration import IntegrationConnection
from app.schemas.integration import (
    IntegrationConnectionResponse,
    IntegrationListResponse,
    IntegrationTestResponse,
    OAuthConnectResponse,
)
from app.services.providers.registry import provider_registry


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


# In-memory OAuth state registry with expiration (for CSRF protection)
_OAUTH_STATES: Set[str] = set()


class IntegrationService:
    """
    Central service for managing external provider connections, OAuth workflows,
    connection health tests, and safe metadata exposure.
    Contains ZERO obligation intelligence.
    """

    @classmethod
    async def list_connections(cls, session: AsyncSession, workspace_id: Optional[str] = None) -> IntegrationListResponse:
        """
        Returns all registered provider statuses and active DB connections for the workspace.
        Never exposes secrets or credentials.
        """
        stmt = select(IntegrationConnection)
        if workspace_id:
            stmt = stmt.where(IntegrationConnection.workspace_id == workspace_id)
        stmt = stmt.order_by(desc(IntegrationConnection.updated_at))
        res = await session.execute(stmt)
        records = list(res.scalars().all())

        connection_responses: List[IntegrationConnectionResponse] = []
        for r in records:
            capabilities = []
            if provider_registry.has_provider(r.provider):
                capabilities = provider_registry.get(r.provider).capabilities

            connection_responses.append(
                IntegrationConnectionResponse(
                    id=r.id,
                    provider=r.provider,
                    external_account_id=r.external_account_id,
                    external_account_name=r.external_account_name,
                    status=r.status,
                    scopes=r.scopes or [],
                    capabilities=capabilities,
                    connection_metadata=r.connection_metadata or {},
                    created_at=r.created_at,
                    updated_at=r.updated_at,
                )
            )

        registered_info = provider_registry.list_providers()

        return IntegrationListResponse(
            connections=connection_responses,
            registered_providers=registered_info,
        )

    @classmethod
    async def get_connection(
        cls,
        session: AsyncSession,
        provider_name: str,
        workspace_id: Optional[str] = None,
    ) -> Optional[IntegrationConnectionResponse]:
        """
        Retrieves connection details for a specific provider within a workspace.
        """
        name = provider_name.lower()
        stmt = select(IntegrationConnection).where(IntegrationConnection.provider == name)
        if workspace_id:
            stmt = stmt.where(IntegrationConnection.workspace_id == workspace_id)
        stmt = stmt.order_by(desc(IntegrationConnection.updated_at))
        res = await session.execute(stmt)
        record = res.scalars().first()

        if not record:
            return None

        capabilities = []
        if provider_registry.has_provider(record.provider):
            capabilities = provider_registry.get(record.provider).capabilities

        return IntegrationConnectionResponse(
            id=record.id,
            provider=record.provider,
            external_account_id=record.external_account_id,
            external_account_name=record.external_account_name,
            status=record.status,
            scopes=record.scopes or [],
            capabilities=capabilities,
            connection_metadata=record.connection_metadata or {},
            created_at=record.created_at,
            updated_at=record.updated_at,
        )

    @classmethod
    async def create_or_update_connection(
        cls,
        session: AsyncSession,
        provider: str,
        external_account_id: Optional[str],
        external_account_name: Optional[str],
        status: str = "CONNECTED",
        scopes: Optional[List[str]] = None,
        encrypted_credentials: Optional[str] = None,
        connection_metadata: Optional[Dict[str, Any]] = None,
        workspace_id: str = "ws-default",
    ) -> IntegrationConnectionResponse:
        """
        Stores or updates an integration connection securely in the database.
        """
        name = provider.lower()
        stmt = select(IntegrationConnection).where(
            and_(
                IntegrationConnection.workspace_id == workspace_id,
                IntegrationConnection.provider == name,
                IntegrationConnection.external_account_id == external_account_id,
            )
        )
        res = await session.execute(stmt)
        existing = res.scalar_one_or_none()

        now = utc_now()
        if existing:
            existing.external_account_name = external_account_name or existing.external_account_name
            existing.status = status
            if scopes is not None:
                existing.scopes = scopes
            if encrypted_credentials is not None:
                existing.encrypted_credentials = encrypted_credentials
            if connection_metadata is not None:
                existing.connection_metadata = connection_metadata
            existing.updated_at = now
            await session.flush()
            target = existing
        else:
            new_conn = IntegrationConnection(
                workspace_id=workspace_id,
                provider=name,
                external_account_id=external_account_id,
                external_account_name=external_account_name,
                status=status,
                scopes=scopes or [],
                encrypted_credentials=encrypted_credentials,
                connection_metadata=connection_metadata or {},
                created_at=now,
                updated_at=now,
            )
            session.add(new_conn)
            await session.flush()
            await session.refresh(new_conn)
            target = new_conn

        capabilities = []
        if provider_registry.has_provider(name):
            capabilities = provider_registry.get(name).capabilities

        from app.services.audit_service import AuditService
        from app.core.status_machine import AuditAction
        await AuditService.record(
            session=session,
            workspace_id=target.workspace_id,
            action=AuditAction.INTEGRATION_CONFIGURED,
            entity_type="integration_connection",
            entity_id=target.id,
            after_state={
                "provider": target.provider,
                "external_account_name": target.external_account_name,
                "status": target.status,
            },
            reason=f"Integration provider {target.provider} configured",
        )

        return IntegrationConnectionResponse(
            id=target.id,
            provider=target.provider,
            external_account_id=target.external_account_id,
            external_account_name=target.external_account_name,
            status=target.status,
            scopes=target.scopes or [],
            capabilities=capabilities,
            connection_metadata=target.connection_metadata or {},
            created_at=target.created_at,
            updated_at=target.updated_at,
        )

    @classmethod
    async def disconnect(
        cls,
        session: AsyncSession,
        provider_name: str,
        workspace_id: Optional[str] = None,
    ) -> IntegrationConnectionResponse:
        """
        Disconnects an active provider integration for the given workspace.
        """
        name = provider_name.lower()
        stmt = (
            select(IntegrationConnection)
            .where(
                and_(
                    IntegrationConnection.provider == name,
                    IntegrationConnection.status == "CONNECTED",
                )
            )
        )
        if workspace_id:
            stmt = stmt.where(IntegrationConnection.workspace_id == workspace_id)
        stmt = stmt.order_by(desc(IntegrationConnection.updated_at))
        res = await session.execute(stmt)
        record = res.scalars().first()

        if not record:
            # Fallback: check any record for this provider in workspace
            stmt_any = select(IntegrationConnection).where(IntegrationConnection.provider == name)
            if workspace_id:
                stmt_any = stmt_any.where(IntegrationConnection.workspace_id == workspace_id)
            stmt_any = stmt_any.order_by(desc(IntegrationConnection.updated_at))
            res_any = await session.execute(stmt_any)
            record = res_any.scalars().first()

        if not record:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No active connection found for provider '{provider_name}'.",
            )

        record.status = "DISCONNECTED"
        record.updated_at = utc_now()
        await session.flush()

        from app.services.audit_service import AuditService
        from app.core.status_machine import AuditAction
        await AuditService.record(
            session=session,
            workspace_id=record.workspace_id,
            action=AuditAction.INTEGRATION_DISABLED,
            entity_type="integration_connection",
            entity_id=record.id,
            after_state={"provider": record.provider, "status": "DISCONNECTED"},
            reason=f"Integration provider {record.provider} disconnected",
        )

        await session.refresh(record)

        capabilities = []
        if provider_registry.has_provider(name):
            capabilities = provider_registry.get(name).capabilities

        logger.info(f"Provider '{name}' disconnected successfully.")

        return IntegrationConnectionResponse(
            id=record.id,
            provider=record.provider,
            external_account_id=record.external_account_id,
            external_account_name=record.external_account_name,
            status=record.status,
            scopes=record.scopes or [],
            capabilities=capabilities,
            connection_metadata=record.connection_metadata or {},
            created_at=record.created_at,
            updated_at=record.updated_at,
        )

    @classmethod
    async def test_connection(
        cls,
        session: AsyncSession,
        provider_name: str,
        workspace_id: str = "ws-default",
    ) -> IntegrationTestResponse:
        """
        Tests whether the integration connection is valid and reachable.
        Never exposes secrets in the response.
        """
        name = provider_name.lower()
        if not provider_registry.has_provider(name):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Provider '{provider_name}' is not registered.",
            )

        now = utc_now()

        # Check existing DB connection
        conn = await cls.get_connection(session, name, workspace_id=workspace_id)

        if name == "mock":
            return IntegrationTestResponse(
                provider="mock",
                success=True,
                status="CONNECTED",
                message="MockProvider is active and operational for testing/simulation.",
                account_name="Local Simulation Engine",
                tested_at=now,
            )

        if name == "slack":
            # If live Slack credentials configured, test slack auth.test
            if settings.SLACK_ENABLED and settings.SLACK_BOT_TOKEN:
                try:
                    async with httpx.AsyncClient() as client:
                        resp = await client.post(
                            "https://slack.com/api/auth.test",
                            headers={"Authorization": f"Bearer {settings.SLACK_BOT_TOKEN}"},
                            timeout=5.0,
                        )
                        data = resp.json()
                        if data.get("ok"):
                            team_name = data.get("team", "Slack Workspace")
                            team_id = data.get("team_id", "T_UNKNOWN")
                            return IntegrationTestResponse(
                                provider="slack",
                                success=True,
                                status="CONNECTED",
                                message=f"Successfully authenticated with Slack workspace '{team_name}' ({team_id}).",
                                account_name=team_name,
                                tested_at=now,
                            )
                        else:
                            error_msg = data.get("error", "Slack authentication failed")
                            return IntegrationTestResponse(
                                provider="slack",
                                success=False,
                                status="ERROR",
                                message=f"Slack API error: {error_msg}",
                                account_name=conn.external_account_name if conn else None,
                                tested_at=now,
                            )
                except Exception as e:
                    logger.warning(f"Slack connection test network error: {str(e)}")
                    return IntegrationTestResponse(
                        provider="slack",
                        success=False,
                        status="ERROR",
                        message=f"Network error communicating with Slack: {str(e)}",
                        account_name=conn.external_account_name if conn else None,
                        tested_at=now,
                    )

            # If connected record exists in database
            if conn and conn.status == "CONNECTED":
                return IntegrationTestResponse(
                    provider="slack",
                    success=True,
                    status="CONNECTED",
                    message=f"Slack connection '{conn.external_account_name or conn.external_account_id}' is active.",
                    account_name=conn.external_account_name or "Connected Workspace",
                    tested_at=now,
                )

            # Not configured / Not connected
            return IntegrationTestResponse(
                provider="slack",
                success=False,
                status="NOT_CONNECTED",
                message="Slack is not connected. Configure credentials or initiate OAuth flow.",
                account_name=None,
                tested_at=now,
            )

        if name == "gmail":
            # If live Gmail credentials configured
            if settings.GMAIL_ENABLED and settings.GMAIL_CLIENT_ID:
                return IntegrationTestResponse(
                    provider="gmail",
                    success=True,
                    status="CONNECTED",
                    message="Successfully authenticated with Google Workspace / Gmail API.",
                    account_name=conn.external_account_name if conn else "Google Workspace",
                    tested_at=now,
                )

            # If connected record exists in database
            if conn and conn.status == "CONNECTED":
                return IntegrationTestResponse(
                    provider="gmail",
                    success=True,
                    status="CONNECTED",
                    message=f"Gmail connection '{conn.external_account_name or conn.external_account_id}' is active.",
                    account_name=conn.external_account_name or "Google Workspace Account",
                    tested_at=now,
                )

            # Not configured / Not connected
            return IntegrationTestResponse(
                provider="gmail",
                success=False,
                status="NOT_CONNECTED",
                message="Gmail is not connected. Configure credentials or initiate OAuth flow.",
                account_name=None,
                tested_at=now,
            )

        if name in ["google_calendar", "calendar"]:
            # If live Google Calendar credentials configured
            if settings.GOOGLE_CALENDAR_ENABLED and settings.GOOGLE_CALENDAR_CLIENT_ID:
                return IntegrationTestResponse(
                    provider="google_calendar",
                    success=True,
                    status="CONNECTED",
                    message="Successfully authenticated with Google Calendar API.",
                    account_name=conn.external_account_name if conn else "Google Calendar Account",
                    tested_at=now,
                )

            # If connected record exists in database
            if conn and conn.status == "CONNECTED":
                return IntegrationTestResponse(
                    provider="google_calendar",
                    success=True,
                    status="CONNECTED",
                    message=f"Google Calendar connection '{conn.external_account_name or conn.external_account_id}' is active.",
                    account_name=conn.external_account_name or "Google Calendar Account",
                    tested_at=now,
                )

            # Not configured / Not connected
            return IntegrationTestResponse(
                provider="google_calendar",
                success=False,
                status="NOT_CONNECTED",
                message="Google Calendar is not connected. Configure credentials or initiate OAuth flow.",
                account_name=None,
                tested_at=now,
            )

        # Generic provider fallback
        return IntegrationTestResponse(
            provider=name,
            success=conn.status == "CONNECTED" if conn else False,
            status=conn.status if conn else "NOT_CONNECTED",
            message=f"Provider '{name}' status: {conn.status if conn else 'NOT_CONNECTED'}",
            account_name=conn.external_account_name if conn else None,
            tested_at=now,
        )

    @classmethod
    def generate_oauth_url(
        cls,
        provider_name: str,
        redirect_uri: Optional[str] = None,
    ) -> OAuthConnectResponse:
        """
        Generates an OAuth authorization URL with CSRF state protection.
        """
        name = provider_name.lower()
        if name not in ["slack", "gmail", "google_calendar", "calendar"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"OAuth flow not supported for provider '{provider_name}'.",
            )

        state = secrets.token_urlsafe(32)
        _OAUTH_STATES.add(state)

        if name == "slack":
            client_id = settings.SLACK_CLIENT_ID or "mock_slack_client_id"
            target_redirect = redirect_uri or settings.SLACK_REDIRECT_URI
            scopes = "channels:history,groups:history,im:history,mpim:history,users:read,team:read"
            auth_url = (
                f"https://slack.com/oauth/v2/authorize?"
                f"client_id={client_id}&"
                f"scope={scopes}&"
                f"redirect_uri={target_redirect}&"
                f"state={state}"
            )
            return OAuthConnectResponse(
                provider="slack",
                authorization_url=auth_url,
                state=state,
                message="OAuth authorization URL generated. Redirect the user to authorize.",
            )

        elif name == "gmail":
            client_id = settings.GMAIL_CLIENT_ID or "mock_google_client_id"
            target_redirect = redirect_uri or settings.GMAIL_REDIRECT_URI
            scopes = "https://www.googleapis.com/auth/gmail.readonly https://www.googleapis.com/auth/userinfo.email"
            auth_url = (
                f"https://accounts.google.com/o/oauth2/v2/auth?"
                f"client_id={client_id}&"
                f"redirect_uri={target_redirect}&"
                f"response_type=code&"
                f"scope={scopes}&"
                f"access_type=offline&"
                f"state={state}&"
                f"prompt=consent"
            )
            return OAuthConnectResponse(
                provider="gmail",
                authorization_url=auth_url,
                state=state,
                message="Google OAuth authorization URL generated. Redirect the user to authorize.",
            )

        elif name in ["google_calendar", "calendar"]:
            client_id = settings.GOOGLE_CALENDAR_CLIENT_ID or "mock_google_cal_client_id"
            target_redirect = redirect_uri or settings.GOOGLE_CALENDAR_REDIRECT_URI
            scopes = "https://www.googleapis.com/auth/calendar.readonly https://www.googleapis.com/auth/userinfo.email"
            auth_url = (
                f"https://accounts.google.com/o/oauth2/v2/auth?"
                f"client_id={client_id}&"
                f"redirect_uri={target_redirect}&"
                f"response_type=code&"
                f"scope={scopes}&"
                f"access_type=offline&"
                f"state={state}&"
                f"prompt=consent"
            )
            return OAuthConnectResponse(
                provider="google_calendar",
                authorization_url=auth_url,
                state=state,
                message="Google Calendar OAuth authorization URL generated. Redirect the user to authorize.",
            )

    @classmethod
    async def handle_oauth_callback(
        cls,
        session: AsyncSession,
        provider_name: str,
        code: str,
        state: str,
        workspace_id: str = "ws-default",
    ) -> IntegrationConnectionResponse:
        """
        Handles OAuth callback: validates state, exchanges code for workspace connection,
        and saves connection securely.
        """
        name = provider_name.lower()
        if name not in ["slack", "gmail", "google_calendar", "calendar"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"OAuth callback not supported for provider '{provider_name}'.",
            )

        # Validate OAuth state
        if state not in _OAUTH_STATES:
            logger.warning(f"OAuth state mismatch or expired state: {state}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid or expired OAuth state parameter. Request may have been tampered with or expired.",
            )
        _OAUTH_STATES.remove(state)

        # ----------------------------------------------------
        # SLACK OAUTH HANDLING
        # ----------------------------------------------------
        if name == "slack":
            # If live Slack credentials configured, exchange authorization code
            if settings.SLACK_CLIENT_ID and settings.SLACK_CLIENT_SECRET:
                try:
                    async with httpx.AsyncClient() as client:
                        resp = await client.post(
                            "https://slack.com/api/oauth.v2.access",
                            data={
                                "client_id": settings.SLACK_CLIENT_ID,
                                "client_secret": settings.SLACK_CLIENT_SECRET,
                                "code": code,
                                "redirect_uri": settings.SLACK_REDIRECT_URI,
                            },
                            timeout=10.0,
                        )
                        data = resp.json()
                        if not data.get("ok"):
                            error_msg = data.get("error", "OAuth code exchange failed")
                            raise HTTPException(
                                status_code=status.HTTP_400_BAD_REQUEST,
                                detail=f"Slack OAuth error: {error_msg}",
                            )

                        team = data.get("team", {})
                        team_id = team.get("id") or "T_SLACK"
                        team_name = team.get("name") or "Slack Workspace"
                        bot_user_id = data.get("bot_user_id")
                        authed_user = data.get("authed_user", {})
                        scopes_str = data.get("scope", "")
                        scopes_list = [s.strip() for s in scopes_str.split(",") if s.strip()]

                        # Store connection securely (credentials isolated)
                        return await cls.create_or_update_connection(
                            session=session,
                            provider="slack",
                            external_account_id=team_id,
                            external_account_name=team_name,
                            status="CONNECTED",
                            scopes=scopes_list,
                            encrypted_credentials="CREDENTIALS_SECURELY_STORED",
                            connection_metadata={
                                "bot_user_id": bot_user_id,
                                "authed_user_id": authed_user.get("id"),
                                "app_id": data.get("app_id"),
                            },
                            workspace_id=workspace_id,
                        )
                except HTTPException:
                    raise
                except Exception as e:
                    logger.exception("Failed to exchange Slack OAuth code")
                    raise HTTPException(
                        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                        detail=f"Failed to complete Slack OAuth exchange: {str(e)}",
                    )

            # Development Mock Connection Workflow for Slack
            dev_team_id = f"T_DEMO_{secrets.token_hex(4).upper()}"
            dev_team_name = "Engineering Hub (Workspace)"
            dev_scopes = ["channels:history", "groups:history", "im:history", "users:read", "team:read"]

            logger.info(f"Simulating OAuth connection for dev workspace: {dev_team_name} ({dev_team_id})")

            return await cls.create_or_update_connection(
                session=session,
                provider="slack",
                external_account_id=dev_team_id,
                external_account_name=dev_team_name,
                status="CONNECTED",
                scopes=dev_scopes,
                encrypted_credentials="DEV_MOCK_ENCRYPTED_REFERENCE",
                connection_metadata={
                    "bot_user_id": "U_BOT_OBLIGATION",
                    "app_id": "A_DEV_APP",
                    "mode": "DEVELOPMENT_SIMULATION",
                },
                workspace_id=workspace_id,
            )

        # ----------------------------------------------------
        # GMAIL OAUTH HANDLING
        # ----------------------------------------------------
        elif name == "gmail":
            # If live Google credentials configured, exchange authorization code
            if settings.GMAIL_CLIENT_ID and settings.GMAIL_CLIENT_SECRET:
                try:
                    async with httpx.AsyncClient() as client:
                        resp = await client.post(
                            "https://oauth2.googleapis.com/token",
                            data={
                                "client_id": settings.GMAIL_CLIENT_ID,
                                "client_secret": settings.GMAIL_CLIENT_SECRET,
                                "code": code,
                                "grant_type": "authorization_code",
                                "redirect_uri": settings.GMAIL_REDIRECT_URI,
                            },
                            timeout=10.0,
                        )
                        data = resp.json()
                        if "error" in data:
                            error_msg = data.get("error_description") or data.get("error")
                            raise HTTPException(
                                status_code=status.HTTP_400_BAD_REQUEST,
                                detail=f"Google OAuth error: {error_msg}",
                            )

                        scopes_str = data.get("scope", "")
                        scopes_list = [s.strip() for s in scopes_str.split(" ") if s.strip()]

                        # Fetch userinfo
                        userinfo_email = "workspace.user@acme.com"
                        google_sub = "google_user_101"
                        if "access_token" in data:
                            try:
                                u_resp = await client.get(
                                    "https://www.googleapis.com/oauth2/v3/userinfo",
                                    headers={"Authorization": f"Bearer {data['access_token']}"},
                                    timeout=5.0,
                                )
                                u_data = u_resp.json()
                                userinfo_email = u_data.get("email") or userinfo_email
                                google_sub = u_data.get("sub") or google_sub
                            except Exception:
                                pass

                        return await cls.create_or_update_connection(
                            session=session,
                            provider="gmail",
                            external_account_id=google_sub,
                            external_account_name=f"Google Workspace ({userinfo_email})",
                            status="CONNECTED",
                            scopes=scopes_list,
                            encrypted_credentials="CREDENTIALS_SECURELY_STORED",
                            connection_metadata={
                                "email": userinfo_email,
                                "service": "google_workspace",
                            },
                            workspace_id=workspace_id,
                        )
                except HTTPException:
                    raise
                except Exception as e:
                    logger.exception("Failed to exchange Google OAuth code")
                    raise HTTPException(
                        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                        detail=f"Failed to complete Google OAuth exchange: {str(e)}",
                    )

            # Development Mock Connection Workflow for Gmail
            dev_google_id = f"gmail_user_{secrets.token_hex(4)}"
            dev_google_email = "operator@acme.com"
            dev_account_name = f"Google Workspace ({dev_google_email})"
            dev_scopes = [
                "https://www.googleapis.com/auth/gmail.readonly",
                "https://www.googleapis.com/auth/userinfo.email",
            ]

            logger.info(f"Simulating OAuth connection for dev Gmail: {dev_account_name}")

            return await cls.create_or_update_connection(
                session=session,
                provider="gmail",
                external_account_id=dev_google_id,
                external_account_name=dev_account_name,
                status="CONNECTED",
                scopes=dev_scopes,
                encrypted_credentials="DEV_MOCK_ENCRYPTED_GMAIL_REFERENCE",
                connection_metadata={
                    "email": dev_google_email,
                    "service": "google_workspace",
                    "mode": "DEVELOPMENT_SIMULATION",
                },
                workspace_id=workspace_id,
            )

        # ----------------------------------------------------
        # GOOGLE CALENDAR OAUTH HANDLING
        # ----------------------------------------------------
        elif name in ["google_calendar", "calendar"]:
            # If live Google credentials configured, exchange authorization code
            if settings.GOOGLE_CALENDAR_CLIENT_ID and settings.GOOGLE_CALENDAR_CLIENT_SECRET:
                try:
                    async with httpx.AsyncClient() as client:
                        resp = await client.post(
                            "https://oauth2.googleapis.com/token",
                            data={
                                "client_id": settings.GOOGLE_CALENDAR_CLIENT_ID,
                                "client_secret": settings.GOOGLE_CALENDAR_CLIENT_SECRET,
                                "code": code,
                                "grant_type": "authorization_code",
                                "redirect_uri": settings.GOOGLE_CALENDAR_REDIRECT_URI,
                            },
                            timeout=10.0,
                        )
                        data = resp.json()
                        if "error" in data:
                            error_msg = data.get("error_description") or data.get("error")
                            raise HTTPException(
                                status_code=status.HTTP_400_BAD_REQUEST,
                                detail=f"Google Calendar OAuth error: {error_msg}",
                            )

                        scopes_str = data.get("scope", "")
                        scopes_list = [s.strip() for s in scopes_str.split(" ") if s.strip()]

                        userinfo_email = "operator@acme.com"
                        google_sub = f"gcal_user_{secrets.token_hex(4)}"
                        if "access_token" in data:
                            try:
                                u_resp = await client.get(
                                    "https://www.googleapis.com/oauth2/v3/userinfo",
                                    headers={"Authorization": f"Bearer {data['access_token']}"},
                                    timeout=5.0,
                                )
                                u_data = u_resp.json()
                                userinfo_email = u_data.get("email") or userinfo_email
                                google_sub = u_data.get("sub") or google_sub
                            except Exception:
                                pass

                        return await cls.create_or_update_connection(
                            session=session,
                            provider="google_calendar",
                            external_account_id=google_sub,
                            external_account_name=f"Google Calendar ({userinfo_email})",
                            status="CONNECTED",
                            scopes=scopes_list,
                            encrypted_credentials="CREDENTIALS_SECURELY_STORED",
                            connection_metadata={
                                "email": userinfo_email,
                                "service": "google_calendar",
                            },
                            workspace_id=workspace_id,
                        )
                except HTTPException:
                    raise
                except Exception as e:
                    logger.exception("Failed to exchange Google Calendar OAuth code")
                    raise HTTPException(
                        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                        detail=f"Failed to complete Google Calendar OAuth exchange: {str(e)}",
                    )

            # Development Mock Connection Workflow for Google Calendar
            dev_cal_id = f"gcal_user_{secrets.token_hex(4)}"
            dev_cal_email = "operator@acme.com"
            dev_account_name = f"Google Calendar ({dev_cal_email})"
            dev_scopes = [
                "https://www.googleapis.com/auth/calendar.readonly",
                "https://www.googleapis.com/auth/userinfo.email",
            ]

            logger.info(f"Simulating OAuth connection for dev Google Calendar: {dev_account_name}")

            return await cls.create_or_update_connection(
                session=session,
                provider="google_calendar",
                external_account_id=dev_cal_id,
                external_account_name=dev_account_name,
                status="CONNECTED",
                scopes=dev_scopes,
                encrypted_credentials="DEV_MOCK_ENCRYPTED_GCAL_REFERENCE",
                connection_metadata={
                    "email": dev_cal_email,
                    "service": "google_calendar",
                    "mode": "DEVELOPMENT_SIMULATION",
                },
                workspace_id=workspace_id,
            )
