"""
Phase 19 Hardened Webhook Endpoints.

Supports both:
  1. Fast Asynchronous ACK (<20ms): Validates signature/token, durably persists
     into EventInboxRecord (status: QUEUED), returns HTTP 200/202 immediately.
  2. Direct Synchronous Ingestion: Durably persists into EventInboxRecord, runs
     the intelligence pipeline, and returns the full IngestionResultResponse.
"""

import json
from typing import Dict, Any, Optional
from fastapi import APIRouter, status, Request, Response, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import DatabaseSession
from app.core.config import settings
from app.core.logging import get_logger
from app.core.resource_limits import ResourceLimits
from app.core.metrics import metrics
from app.schemas.obligation import IngestionResultResponse
from app.services.event_inbox_service import EventInboxService
from app.services.event_ingestion_service import EventIngestionService

logger = get_logger("obligation_agent.webhooks")

router = APIRouter(prefix="/webhooks", tags=["Webhooks"])


async def _read_and_check_body(request: Request, limit: int = None) -> bytes:
    limit = limit or settings.MAX_WEBHOOK_PAYLOAD_BYTES
    body = await request.body()
    if len(body) > limit:
        ResourceLimits.check_webhook_payload(len(body))
    return body


def _extract_workspace_id(request: Request) -> str:
    return (
        request.headers.get("X-Workspace-Id")
        or request.query_params.get("workspace_id")
        or "ws-default"
    )


def _is_async_requested(request: Request) -> bool:
    param = request.query_params.get("async", "").lower()
    header = request.headers.get("X-Async-Processing", "").lower()
    return param in ("true", "1") or header in ("true", "1") or getattr(settings, "WEBHOOK_ASYNC_MODE", False)


# ---------------------------------------------------------------------------
# POST /webhooks/slack
# ---------------------------------------------------------------------------

@router.post("/slack")
async def handle_slack_webhook(
    request: Request,
    db: AsyncSession = DatabaseSession,
):
    from app.services.providers.slack_provider import SlackProvider

    # 1. Size check
    try:
        raw_body = await _read_and_check_body(request)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="Webhook payload exceeds maximum allowed size.",
        )

    timestamp = request.headers.get("X-Slack-Request-Timestamp")
    signature = request.headers.get("X-Slack-Signature")

    # 2. Signature validation
    if settings.SLACK_SIGNING_SECRET or (timestamp and signature):
        is_valid = SlackProvider.verify_slack_signature(
            request_body=raw_body,
            timestamp=timestamp,
            signature=signature,
            tolerance_seconds=settings.SLACK_SIGNATURE_TOLERANCE_SECONDS,
        )
        if not is_valid:
            logger.warning("Slack webhook: invalid signature or expired timestamp.")
            metrics.increment("ingestion.webhook.rejected", labels={"provider": "slack", "reason": "invalid_signature"})
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Slack request verification failed: invalid signature or timestamp.",
            )

    try:
        payload = json.loads(raw_body.decode("utf-8")) if raw_body else {}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid JSON payload: {str(e)}",
        )

    # 3. URL verification challenge
    if isinstance(payload, dict) and payload.get("type") == "url_verification":
        logger.info("Slack URL verification challenge accepted.")
        return {"challenge": payload.get("challenge", "")}

    workspace_id = _extract_workspace_id(request)
    metrics.increment("events.received_total", labels={"provider": "slack"})

    # 4. Durable Inbox Buffer Persistence
    inbox_rec, is_dup = await EventInboxService.ingest_to_inbox(
        session=db,
        workspace_id=workspace_id,
        provider="slack",
        raw_payload=payload,
        event_type="message",
    )

    # 5. Fast ACK if async requested
    if _is_async_requested(request):
        return {
            "status": "queued",
            "event_id": inbox_rec.id,
            "stream_key": inbox_rec.stream_key,
            "provider": "slack",
            "deduplicated": is_dup,
            "received_at": inbox_rec.received_at.isoformat(),
        }

    # 6. Direct execution
    try:
        result = await EventIngestionService.ingest_from_provider(
            session=db,
            provider_name="slack",
            raw_payload=payload,
            workspace_id=workspace_id,
        )
        return result
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


# ---------------------------------------------------------------------------
# POST /webhooks/gmail
# ---------------------------------------------------------------------------

@router.post("/gmail")
async def handle_gmail_webhook(
    request: Request,
    db: AsyncSession = DatabaseSession,
):
    try:
        raw_body = await _read_and_check_body(request)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="Webhook payload exceeds maximum allowed size.",
        )

    token_param = request.query_params.get("token")
    token_header = request.headers.get("X-Goog-PubSub-Token")
    if settings.GMAIL_PUBSUB_VERIFICATION_TOKEN:
        received_token = token_param or token_header
        if received_token != settings.GMAIL_PUBSUB_VERIFICATION_TOKEN:
            logger.warning("Gmail webhook: invalid verification token.")
            metrics.increment("ingestion.webhook.rejected", labels={"provider": "gmail", "reason": "invalid_token"})
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Gmail webhook verification failed: invalid token.",
            )

    try:
        payload = json.loads(raw_body.decode("utf-8")) if raw_body else {}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid JSON payload: {str(e)}",
        )

    workspace_id = _extract_workspace_id(request)
    metrics.increment("events.received_total", labels={"provider": "gmail"})

    # Durable Inbox Buffer Persistence
    inbox_rec, is_dup = await EventInboxService.ingest_to_inbox(
        session=db,
        workspace_id=workspace_id,
        provider="gmail",
        raw_payload=payload,
        event_type="email",
    )

    if _is_async_requested(request):
        return {
            "status": "queued",
            "event_id": inbox_rec.id,
            "stream_key": inbox_rec.stream_key,
            "provider": "gmail",
            "deduplicated": is_dup,
            "received_at": inbox_rec.received_at.isoformat(),
        }

    try:
        result = await EventIngestionService.ingest_from_provider(
            session=db,
            provider_name="gmail",
            raw_payload=payload,
            workspace_id=workspace_id,
        )
        return result
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


# ---------------------------------------------------------------------------
# POST /webhooks/google-calendar & /google_calendar
# ---------------------------------------------------------------------------

@router.post("/google-calendar")
@router.post("/google_calendar")
async def handle_google_calendar_webhook(
    request: Request,
    db: AsyncSession = DatabaseSession,
):
    try:
        raw_body = await _read_and_check_body(request)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="Webhook payload exceeds maximum allowed size.",
        )

    token_param = request.query_params.get("token")
    token_header = request.headers.get("X-Goog-Channel-Token") or request.headers.get("X-Goog-PubSub-Token")
    if settings.GOOGLE_CALENDAR_WEBHOOK_SECRET:
        received_token = token_param or token_header
        if received_token != settings.GOOGLE_CALENDAR_WEBHOOK_SECRET:
            logger.warning("Google Calendar webhook: invalid token.")
            metrics.increment("ingestion.webhook.rejected", labels={"provider": "google_calendar", "reason": "invalid_token"})
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Google Calendar webhook verification failed: invalid token.",
            )

    try:
        payload = json.loads(raw_body.decode("utf-8")) if raw_body else {}
    except Exception as e:
        if request.headers.get("X-Goog-Channel-ID"):
            payload = {
                "channelId": request.headers.get("X-Goog-Channel-ID"),
                "resourceId": request.headers.get("X-Goog-Resource-ID"),
                "resourceState": request.headers.get("X-Goog-Resource-State", "exists"),
                "resourceUri": request.headers.get("X-Goog-Resource-URI", ""),
            }
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid JSON payload: {str(e)}",
            )

    if isinstance(payload, dict):
        if "channelId" not in payload and request.headers.get("X-Goog-Channel-ID"):
            payload["channelId"] = request.headers.get("X-Goog-Channel-ID")
            payload["resourceId"] = request.headers.get("X-Goog-Resource-ID")
            payload["resourceState"] = request.headers.get("X-Goog-Resource-State")

    workspace_id = _extract_workspace_id(request)
    metrics.increment("events.received_total", labels={"provider": "google_calendar"})

    inbox_rec, is_dup = await EventInboxService.ingest_to_inbox(
        session=db,
        workspace_id=workspace_id,
        provider="google_calendar",
        raw_payload=payload,
        event_type="calendar_event",
    )

    if _is_async_requested(request):
        return {
            "status": "queued",
            "event_id": inbox_rec.id,
            "stream_key": inbox_rec.stream_key,
            "provider": "google_calendar",
            "deduplicated": is_dup,
            "received_at": inbox_rec.received_at.isoformat(),
        }

    try:
        result = await EventIngestionService.ingest_from_provider(
            session=db,
            provider_name="google_calendar",
            raw_payload=payload,
            workspace_id=workspace_id,
        )
        return result
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


# ---------------------------------------------------------------------------
# POST /webhooks/jira — Dedicated Jira Cloud Webhook Endpoint
# ---------------------------------------------------------------------------

@router.post("/jira")
async def handle_jira_webhook(
    request: Request,
    db: AsyncSession = DatabaseSession,
):
    from app.services.providers.jira_provider import JiraProvider

    # 1. Payload size check
    try:
        raw_body = await _read_and_check_body(request)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="Jira webhook payload exceeds maximum allowed size.",
        )

    # 2. Signature / secret token validation
    secret = settings.JIRA_WEBHOOK_SECRET
    sig_header = (
        request.headers.get("X-Hub-Signature")
        or request.headers.get("X-Atlassian-Webhook-Signature")
        or request.headers.get("X-Signature")
    )
    token_param = request.query_params.get("secret") or request.query_params.get("token")

    if secret:
        is_valid = JiraProvider.verify_jira_webhook(
            request_body=raw_body,
            secret=secret,
            signature=sig_header,
            token_param=token_param,
        )
        if not is_valid:
            logger.warning("Jira webhook: unauthorized signature or secret token mismatch.")
            metrics.increment("ingestion.webhook.rejected", labels={"provider": "jira", "reason": "invalid_signature"})
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Jira webhook verification failed: invalid signature or token.",
            )

    try:
        payload = json.loads(raw_body.decode("utf-8")) if raw_body else {}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid JSON payload: {str(e)}",
        )

    workspace_id = _extract_workspace_id(request)
    webhook_event = payload.get("webhookEvent") or "jira:issue_updated"
    metrics.increment("events.received_total", labels={"provider": "jira", "event": webhook_event})

    # 3. Durable intake into EventInboxRecord
    inbox_rec, is_dup = await EventInboxService.ingest_to_inbox(
        session=db,
        workspace_id=workspace_id,
        provider="jira",
        raw_payload=payload,
        event_type=webhook_event,
    )

    # 4. Async ACK vs synchronous pipeline
    if _is_async_requested(request):
        return {
            "status": "queued",
            "event_id": inbox_rec.id,
            "stream_key": inbox_rec.stream_key,
            "provider": "jira",
            "deduplicated": is_dup,
            "received_at": inbox_rec.received_at.isoformat(),
        }

    try:
        result = await EventIngestionService.ingest_from_provider(
            session=db,
            provider_name="jira",
            raw_payload=payload,
            workspace_id=workspace_id,
        )
        return result
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


# ---------------------------------------------------------------------------
# POST /webhooks/{provider} — generic webhook endpoint
# ---------------------------------------------------------------------------

@router.post("/{provider}", status_code=status.HTTP_201_CREATED)

async def handle_provider_webhook(
    provider: str,
    payload: Dict[str, Any],
    request: Request,
    db: AsyncSession = DatabaseSession,
):
    workspace_id = _extract_workspace_id(request)
    metrics.increment("events.received_total", labels={"provider": provider})

    inbox_rec, is_dup = await EventInboxService.ingest_to_inbox(
        session=db,
        workspace_id=workspace_id,
        provider=provider,
        raw_payload=payload,
        event_type="generic_event",
    )

    if _is_async_requested(request):
        return {
            "status": "queued",
            "event_id": inbox_rec.id,
            "stream_key": inbox_rec.stream_key,
            "provider": provider,
            "deduplicated": is_dup,
            "received_at": inbox_rec.received_at.isoformat(),
        }

    try:
        return await EventIngestionService.ingest_from_provider(
            session=db,
            provider_name=provider,
            raw_payload=payload,
            workspace_id=workspace_id,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
