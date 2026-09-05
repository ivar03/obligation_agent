"""Google Workspace synchronization helpers for Gmail and Calendar.

OAuth connections are stored encrypted in IntegrationConnection. This service
uses those credentials to refresh access and pull provider records into the
existing provider-agnostic event ingestion pipeline.
"""

import base64
import json
import time
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Any, Dict, List, Optional

import httpx
from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.crypto import CryptoService
from app.models.integration import IntegrationConnection
from app.services.event_ingestion_service import EventIngestionService


GMAIL_SCOPE = "https://www.googleapis.com/auth/gmail.readonly"
CALENDAR_SCOPE = "https://www.googleapis.com/auth/calendar.readonly"


class GoogleWorkspaceService:
    """Pulls Gmail messages and Calendar events for a workspace connection."""

    @staticmethod
    async def _connection(session: AsyncSession, provider: str, workspace_id: str) -> IntegrationConnection:
        result = await session.execute(
            select(IntegrationConnection)
            .where(
                IntegrationConnection.workspace_id == workspace_id,
                IntegrationConnection.provider == provider,
                IntegrationConnection.status == "CONNECTED",
            )
            .order_by(IntegrationConnection.updated_at.desc())
        )
        connection = result.scalars().first()
        if not connection or not connection.encrypted_credentials:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"{provider} is not connected with usable credentials.",
            )
        return connection

    @staticmethod
    def _credentials(connection: IntegrationConnection) -> Dict[str, Any]:
        try:
            credentials = json.loads(CryptoService.decrypt(connection.encrypted_credentials or ""))
        except (TypeError, ValueError, json.JSONDecodeError) as exc:
            raise HTTPException(status_code=500, detail="Stored Google credentials could not be read.") from exc
        if not credentials.get("access_token") and not credentials.get("refresh_token"):
            raise HTTPException(status_code=500, detail="Stored Google credentials contain no usable token.")
        return credentials

    @classmethod
    async def _save_credentials(cls, session: AsyncSession, connection: IntegrationConnection, credentials: Dict[str, Any]) -> None:
        connection.encrypted_credentials = CryptoService.encrypt(json.dumps(credentials))
        connection.updated_at = datetime.now(timezone.utc)
        await session.flush()

    @classmethod
    async def _access_token(
        cls, session: AsyncSession, connection: IntegrationConnection, credentials: Dict[str, Any]
    ) -> str:
        expires_at = float(credentials.get("expires_at") or 0)
        if credentials.get("access_token") and expires_at > time.time() + 60:
            return str(credentials["access_token"])

        refresh_token = credentials.get("refresh_token")
        if not refresh_token:
            if credentials.get("access_token"):
                return str(credentials["access_token"])
            raise HTTPException(status_code=401, detail="Google access token expired and no refresh token is available.")

        client_id = settings.GMAIL_CLIENT_ID or settings.GOOGLE_CALENDAR_CLIENT_ID
        client_secret = settings.GMAIL_CLIENT_SECRET or settings.GOOGLE_CALENDAR_CLIENT_SECRET
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(
                "https://oauth2.googleapis.com/token",
                data={
                    "client_id": client_id,
                    "client_secret": client_secret,
                    "refresh_token": refresh_token,
                    "grant_type": "refresh_token",
                },
            )
        if response.status_code >= 400:
            raise HTTPException(status_code=401, detail="Google token refresh failed.")
        refreshed = response.json()
        credentials.update(refreshed)
        credentials["refresh_token"] = refreshed.get("refresh_token") or refresh_token
        credentials["expires_at"] = time.time() + int(refreshed.get("expires_in", 3600))
        await cls._save_credentials(session, connection, credentials)
        return str(credentials["access_token"])

    @classmethod
    async def _google_request(
        cls,
        session: AsyncSession,
        connection: IntegrationConnection,
        credentials: Dict[str, Any],
        method: str,
        url: str,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        token = await cls._access_token(session, connection, credentials)
        headers = dict(kwargs.pop("headers", {}) or {})
        headers["Authorization"] = f"Bearer {token}"
        async with httpx.AsyncClient(timeout=20.0) as client:
            response = await client.request(method, url, headers=headers, **kwargs)
        if response.status_code >= 400:
            detail = response.text[:500]
            raise HTTPException(status_code=502, detail=f"Google API request failed: {detail}")
        return response.json() if response.content else {}

    @staticmethod
    def _decode_body(payload: Dict[str, Any]) -> str:
        data = payload.get("body", {}).get("data") if isinstance(payload.get("body"), dict) else None
        if data:
            return base64.urlsafe_b64decode(data + "=" * (-len(data) % 4)).decode("utf-8", errors="replace")
        for part in payload.get("parts", []) or []:
            if isinstance(part, dict):
                text = GoogleWorkspaceService._decode_body(part)
                if text:
                    return text
        return ""

    @classmethod
    async def start_gmail_watch(cls, session: AsyncSession, workspace_id: str) -> Dict[str, Any]:
        connection = await cls._connection(session, "gmail", workspace_id)
        credentials = cls._credentials(connection)
        if not settings.GMAIL_PUBSUB_TOPIC:
            raise HTTPException(status_code=400, detail="GMAIL_PUBSUB_TOPIC is not configured.")
        result = await cls._google_request(
            session,
            connection,
            credentials,
            "POST",
            "https://gmail.googleapis.com/gmail/v1/users/me/watch",
            json={"topicName": settings.GMAIL_PUBSUB_TOPIC, "labelIds": ["INBOX"], "labelFilterBehavior": "INCLUDE"},
        )
        metadata = dict(connection.connection_metadata or {})
        metadata["gmail_watch_history_id"] = result.get("historyId")
        metadata["gmail_watch_expiration"] = result.get("expiration")
        connection.connection_metadata = metadata
        await session.commit()
        return {"provider": "gmail", "status": "WATCHING", **result}

    @classmethod
    async def sync_gmail(cls, session: AsyncSession, workspace_id: str, limit: int = 20) -> Dict[str, Any]:
        connection = await cls._connection(session, "gmail", workspace_id)
        credentials = cls._credentials(connection)
        listing = await cls._google_request(
            session,
            connection,
            credentials,
            "GET",
            "https://gmail.googleapis.com/gmail/v1/users/me/messages",
            params={"labelIds": "INBOX", "maxResults": min(limit, 100)},
        )
        from app.services.providers.registry import provider_registry

        provider = provider_registry.get("gmail")
        processed = 0
        duplicates = 0
        for item in listing.get("messages", [])[:limit]:
            message_id = item.get("id")
            if not message_id:
                continue
            message = await cls._google_request(
                session,
                connection,
                credentials,
                "GET",
                f"https://gmail.googleapis.com/gmail/v1/users/me/messages/{message_id}",
                params={"format": "full"},
            )
            headers = {
                h.get("name", "").lower(): h.get("value", "")
                for h in message.get("payload", {}).get("headers", [])
                if isinstance(h, dict)
            }
            body = cls._decode_body(message.get("payload", {})) or message.get("snippet", "")
            event = provider.normalize_event(
                {
                    "from": headers.get("from", "Unknown"),
                    "to": headers.get("to", ""),
                    "subject": headers.get("subject", ""),
                    "body": body,
                    "message_id": message_id,
                    "thread_id": message.get("threadId"),
                    "source_ref": f"gmail_{message_id}",
                    "timestamp": headers.get("date"),
                    "metadata": {"label_ids": message.get("labelIds", []), "history_id": message.get("historyId")},
                }
            )
            result = await EventIngestionService.ingest_normalized_event(
                session=session, event=event, provider_name="gmail", raw_payload=message, workspace_id=workspace_id
            )
            if result.status == "DUPLICATE":
                duplicates += 1
            else:
                processed += 1
        await session.commit()
        return {"provider": "gmail", "status": "SYNCED", "processed": processed, "duplicates": duplicates}

    @classmethod
    async def sync_calendar(cls, session: AsyncSession, workspace_id: str, limit: int = 50) -> Dict[str, Any]:
        connection = await cls._connection(session, "google_calendar", workspace_id)
        credentials = cls._credentials(connection)
        calendar = await cls._google_request(
            session,
            connection,
            credentials,
            "GET",
            "https://www.googleapis.com/calendar/v3/calendars/primary/events",
            params={"singleEvents": "true", "orderBy": "startTime", "maxResults": min(limit, 250)},
        )
        from app.services.providers.registry import provider_registry

        provider = provider_registry.get("google_calendar")
        processed = 0
        duplicates = 0
        for item in calendar.get("items", [])[:limit]:
            event = provider.normalize_event(item)
            result = await EventIngestionService.ingest_normalized_event(
                session=session, event=event, provider_name="google_calendar", raw_payload=item, workspace_id=workspace_id
            )
            if result.status == "DUPLICATE":
                duplicates += 1
            else:
                processed += 1
        await session.commit()
        return {"provider": "google_calendar", "status": "SYNCED", "processed": processed, "duplicates": duplicates}
