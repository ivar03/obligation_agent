import json
from typing import Dict, Any, Union
from fastapi import APIRouter, status, HTTPException, Request, Response
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import DatabaseSession
from app.core.config import settings
from app.core.logging import logger
from app.schemas.obligation import IngestionResultResponse
from app.services.event_ingestion_service import EventIngestionService
from app.services.providers.slack_provider import SlackProvider

router = APIRouter(prefix="/webhooks", tags=["Webhooks"])


@router.post("/slack")
async def handle_slack_webhook(
    request: Request,
    db: AsyncSession = DatabaseSession,
):
    """
    Dedicated Slack Webhook & Events API endpoint.
    1. Validates Slack request signature & timestamp against replay attacks.
    2. Handles Slack URL verification challenge.
    3. Normalizes payload and ingests event into the intelligence pipeline.
    """
    raw_body = await request.body()
    timestamp = request.headers.get("X-Slack-Request-Timestamp")
    signature = request.headers.get("X-Slack-Signature")

    # 1. Validate Slack Request Signature (if signing secret configured or signature headers present)
    if settings.SLACK_SIGNING_SECRET or (timestamp and signature):
        is_valid = SlackProvider.verify_slack_signature(
            request_body=raw_body,
            timestamp=timestamp,
            signature=signature,
            tolerance_seconds=settings.SLACK_SIGNATURE_TOLERANCE_SECONDS,
        )
        if not is_valid:
            logger.warning("Rejected unauthorized Slack webhook request: invalid signature or expired timestamp.")
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

    # 2. Handle Slack URL Verification Challenge
    if isinstance(payload, dict) and payload.get("type") == "url_verification":
        challenge = payload.get("challenge", "")
        logger.info("Slack URL verification challenge accepted.")
        return {"challenge": challenge}

    # 3. Normalize & Ingest via EventIngestionService
    workspace_id = request.headers.get("X-Workspace-Id") or request.query_params.get("workspace_id") or "ws-default"
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


@router.post("/gmail")
async def handle_gmail_webhook(
    request: Request,
    db: AsyncSession = DatabaseSession,
):
    """
    Dedicated Gmail Webhook & Google Cloud Pub/Sub push endpoint.
    1. Validates Pub/Sub verification token if configured.
    2. Normalizes email/PubSub payload and ingests event into the intelligence pipeline.
    """
    raw_body = await request.body()
    token_param = request.query_params.get("token")
    token_header = request.headers.get("X-Goog-PubSub-Token")

    # Validate Pub/Sub token if configured
    if settings.GMAIL_PUBSUB_VERIFICATION_TOKEN:
        received_token = token_param or token_header
        if received_token != settings.GMAIL_PUBSUB_VERIFICATION_TOKEN:
            logger.warning("Rejected unauthorized Gmail Pub/Sub webhook: invalid verification token.")
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

    workspace_id = request.headers.get("X-Workspace-Id") or request.query_params.get("workspace_id") or "ws-default"
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


@router.post("/google-calendar")
@router.post("/google_calendar")
async def handle_google_calendar_webhook(
    request: Request,
    db: AsyncSession = DatabaseSession,
):
    """
    Dedicated Google Calendar Webhook & Push Notification endpoint.
    1. Validates Google Calendar webhook secret token if configured.
    2. Handles channel sync headers (X-Goog-Resource-State, X-Goog-Channel-ID).
    3. Normalizes calendar event payload and ingests into intelligence pipeline.
    """
    raw_body = await request.body()
    token_param = request.query_params.get("token")
    token_header = request.headers.get("X-Goog-Channel-Token") or request.headers.get("X-Goog-PubSub-Token")

    # Validate secret token if configured
    if settings.GOOGLE_CALENDAR_WEBHOOK_SECRET:
        received_token = token_param or token_header
        if received_token != settings.GOOGLE_CALENDAR_WEBHOOK_SECRET:
            logger.warning("Rejected unauthorized Google Calendar webhook: invalid verification token.")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Google Calendar webhook verification failed: invalid token.",
            )

    try:
        payload = json.loads(raw_body.decode("utf-8")) if raw_body else {}
    except Exception as e:
        # If payload is empty but Google headers are present, construct sync payload
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

    # Attach Google sync headers to payload if not already present
    if isinstance(payload, dict):
        if "channelId" not in payload and request.headers.get("X-Goog-Channel-ID"):
            payload["channelId"] = request.headers.get("X-Goog-Channel-ID")
            payload["resourceId"] = request.headers.get("X-Goog-Resource-ID")
            payload["resourceState"] = request.headers.get("X-Goog-Resource-State")

    workspace_id = request.headers.get("X-Workspace-Id") or request.query_params.get("workspace_id") or "ws-default"
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


@router.post("/{provider}", response_model=IngestionResultResponse, status_code=status.HTTP_201_CREATED)
async def handle_provider_webhook(
    provider: str,
    payload: Dict[str, Any],
    request: Request,
    db: AsyncSession = DatabaseSession,
):
    """
    Generic webhook receiver endpoint.
    Routes provider webhooks to the corresponding adapter for normalization and ingestion.
    """
    workspace_id = request.headers.get("X-Workspace-Id") or request.query_params.get("workspace_id") or "ws-default"
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
