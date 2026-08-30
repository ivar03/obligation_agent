import hmac
import hashlib
import time
import re
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone

from app.core.config import settings
from app.core.logging import logger
from app.schemas.obligation import ExternalEvent
from app.services.providers.base_provider import BaseProvider


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class SlackProvider(BaseProvider):
    """
    Real Provider Adapter for Slack Workspaces & Events API.
    Normalizes Slack event payloads into provider-agnostic ExternalEvent objects.
    Contains ZERO obligation-specific intelligence.
    """

    @property
    def provider_name(self) -> str:
        return "slack"

    @property
    def provider_version(self) -> str:
        return "1.0.0"

    @property
    def capabilities(self) -> List[str]:
        return ["events", "messages", "webhook", "channel_messages", "attachments"]

    def validate_connection(self) -> bool:
        """
        Validates Slack connection configuration.
        Returns True if Slack is enabled and credentials are configured,
        or in development mode when simulated connections exist.
        """
        if settings.SLACK_ENABLED and (settings.SLACK_BOT_TOKEN or settings.SLACK_SIGNING_SECRET):
            return True
        return False

    def validate_payload(self, raw_payload: Dict[str, Any]) -> bool:
        """
        Validates that the raw payload has a valid Slack structure.
        """
        if not isinstance(raw_payload, dict) or not raw_payload:
            return False
        # Valid if it's an event_callback, url_verification, or direct message structure
        if raw_payload.get("type") in ["event_callback", "url_verification", "app_mention"]:
            return True
        if "event" in raw_payload or "text" in raw_payload or "message" in raw_payload:
            return True
        return False

    def normalize_event(self, raw_payload: Dict[str, Any]) -> ExternalEvent:
        """
        Transforms Slack webhook / Events API payloads into a standardized ExternalEvent.
        Handles message events, threaded replies, bot messages, edits, and file attachments.
        """
        if not self.validate_payload(raw_payload):
            raise ValueError("Malformed Slack payload: invalid structure or empty dictionary.")

        # 1. Extract event data from Slack Events API wrapper if present
        payload_type = raw_payload.get("type", "")
        team_id = raw_payload.get("team_id") or raw_payload.get("team") or "T_UNKNOWN"
        api_app_id = raw_payload.get("api_app_id")
        event_id = raw_payload.get("event_id")
        event_time = raw_payload.get("event_time")

        if payload_type == "event_callback" and "event" in raw_payload:
            event_data = raw_payload.get("event", {})
        else:
            event_data = raw_payload

        # 2. Extract message content, handling message_changed subtype
        subtype = event_data.get("subtype", "")
        if subtype == "message_changed" and "message" in event_data:
            inner_msg = event_data.get("message", {})
            content = inner_msg.get("text", "")
            slack_user_id = inner_msg.get("user") or event_data.get("user")
            ts_str = inner_msg.get("ts") or event_data.get("ts")
            files = inner_msg.get("files") or event_data.get("files") or []
        else:
            content = event_data.get("text") or event_data.get("content") or ""
            slack_user_id = event_data.get("user") or event_data.get("sender_id") or event_data.get("user_id")
            ts_str = event_data.get("ts") or event_data.get("timestamp")
            files = event_data.get("files") or event_data.get("attachments") or []

        # Ignore subtype if it represents clearly non-content noise (e.g. channel_join, message_deleted)
        if subtype in ["channel_join", "channel_leave", "message_deleted"]:
            logger.debug(f"Slack non-content event subtype ignored: {subtype}")

        # 3. Resolve Channel and Thread Context
        channel_id = event_data.get("channel") or raw_payload.get("channel_id") or "C_GENERAL"
        channel_name = event_data.get("channel_name") or raw_payload.get("channel_name")
        thread_ts = event_data.get("thread_ts")

        # 4. Deterministic source_ref calculation for idempotency
        if event_id:
            source_ref = f"slack_{team_id}_{event_id}"
        elif ts_str:
            source_ref = f"slack_{team_id}_{channel_id}_{ts_str}"
        elif raw_payload.get("source_ref"):
            source_ref = str(raw_payload.get("source_ref"))
        else:
            source_ref = f"slack_{team_id}_{channel_id}_{int(time.time() * 1000)}"

        # 5. User / Sender identity mapping
        sender = (
            raw_payload.get("sender")
            or event_data.get("user_name")
            or event_data.get("username")
            or raw_payload.get("user_name")
            or (event_data.get("user_profile", {}).get("real_name") if isinstance(event_data.get("user_profile"), dict) else None)
            or (event_data.get("user_profile", {}).get("display_name") if isinstance(event_data.get("user_profile"), dict) else None)
            or slack_user_id
            or "Unknown"
        )

        # 6. Extract Recipient Mentions from Content (<@U12345>) or explicit payload
        recipients = raw_payload.get("recipients") or []
        if isinstance(recipients, str):
            recipients = [recipients]
        else:
            recipients = list(recipients)

        if content:
            # Look for Slack user mentions like <@U01234567> or <@W1234567|alice>
            mentions = re.findall(r"<@([A-Z0-9]+)(?:\|([^>]+))?>", content)
            for uid, name in mentions:
                recipient_val = name if name else uid
                if recipient_val not in recipients:
                    recipients.append(recipient_val)

        # 7. Normalize Attachments / Files metadata
        normalized_attachments = []
        if isinstance(files, list):
            for f in files:
                if isinstance(f, dict):
                    normalized_attachments.append({
                        "name": f.get("name") or f.get("title") or f.get("filename") or "attachment",
                        "filetype": f.get("filetype") or f.get("file_type") or "unknown",
                        "mimetype": f.get("mimetype") or f.get("mime_type") or "application/octet-stream",
                        "size": f.get("size") or 0,
                        "url": f.get("url_private") or f.get("permalink") or f.get("url"),
                        "timestamp": f.get("timestamp") or ts_str,
                    })

        # 8. Construct Safe Metadata (strictly no tokens or secrets)
        metadata: Dict[str, Any] = {
            "team_id": team_id,
            "channel_id": channel_id,
            "slack_user_id": slack_user_id,
            "event_type": event_data.get("type", "message"),
            "subtype": subtype if subtype else None,
            "ts": ts_str,
        }
        if channel_name:
            metadata["channel_name"] = channel_name
        if thread_ts:
            metadata["thread_ts"] = thread_ts
        if api_app_id:
            metadata["api_app_id"] = api_app_id
        if normalized_attachments:
            metadata["attachments"] = normalized_attachments

        # Merge additional custom metadata if present (safely avoiding secrets)
        custom_meta = raw_payload.get("metadata")
        if isinstance(custom_meta, dict):
            for k, v in custom_meta.items():
                if k not in ["token", "secret", "bot_token", "signing_secret", "authorization"]:
                    metadata[k] = v

        # 9. Parse Event Timestamp
        ts_datetime = utc_now()
        if ts_str:
            try:
                # Slack ts is usually Unix timestamp string e.g. "1609459200.000200"
                epoch_sec = float(ts_str.split(".")[0])
                ts_datetime = datetime.fromtimestamp(epoch_sec, tz=timezone.utc)
            except (ValueError, TypeError):
                ts_datetime = utc_now()
        elif event_time:
            try:
                ts_datetime = datetime.fromtimestamp(float(event_time), tz=timezone.utc)
            except (ValueError, TypeError):
                ts_datetime = utc_now()

        return ExternalEvent(
            source_type="slack",
            source_ref=source_ref,
            sender=sender,
            recipients=recipients,
            timestamp=ts_datetime,
            content=content,
            metadata=metadata,
        )

    @staticmethod
    def verify_slack_signature(
        request_body: bytes,
        timestamp: Optional[str],
        signature: Optional[str],
        signing_secret: Optional[str] = None,
        tolerance_seconds: int = 300,
    ) -> bool:
        """
        Verifies Slack request authenticity using HMAC-SHA256 signature and timestamp tolerance.
        Protects against request tampering and replay attacks.
        Uses constant-time comparison (hmac.compare_digest).
        """
        secret = signing_secret or settings.SLACK_SIGNING_SECRET
        if not secret:
            logger.warning("Slack signing secret not configured; signature verification skipped in dev mode.")
            return True

        if not timestamp or not signature:
            logger.warning("Missing Slack timestamp or signature header.")
            return False

        # Verify timestamp to protect against replay attacks
        try:
            req_time = float(timestamp)
            current_time = time.time()
            if abs(current_time - req_time) > tolerance_seconds:
                logger.warning(
                    f"Slack request timestamp expired or out of tolerance: drift={abs(current_time - req_time)}s > {tolerance_seconds}s"
                )
                return False
        except (ValueError, TypeError):
            logger.warning("Invalid Slack timestamp header format.")
            return False

        # Compute signature: v0=HMAC_SHA256("v0:{timestamp}:{body}", secret)
        sig_basestring = f"v0:{timestamp}:".encode("utf-8") + request_body
        computed_hash = hmac.new(
            secret.encode("utf-8"),
            sig_basestring,
            hashlib.sha256,
        ).hexdigest()
        expected_signature = f"v0={computed_hash}"

        # Constant-time comparison
        is_valid = hmac.compare_digest(expected_signature, signature)
        if not is_valid:
            logger.warning("Slack request signature mismatch.")
        return is_valid
