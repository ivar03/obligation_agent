import base64
import json
import re
import uuid
import time
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone

from app.core.config import settings
from app.core.logging import logger
from app.schemas.obligation import ExternalEvent
from app.services.providers.base_provider import BaseProvider


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def parse_email_identity(raw_identity: Optional[str]) -> str:
    """
    Normalizes an email identity string into a human-readable display name or clean email.
    e.g., 'Rahul Sharma <rahul@acme.com>' -> 'Rahul Sharma'
          '<rahul@acme.com>' -> 'rahul@acme.com'
          'Rahul' -> 'Rahul'
    """
    if not raw_identity:
        return "Unknown"
    
    raw = str(raw_identity).strip()
    match = re.match(r'^"?([^"<]+)"?\s*<([^>]+)>$', raw)
    if match:
        name = match.group(1).strip()
        email = match.group(2).strip()
        return name if name else email
    
    # Check if only angle brackets e.g. <user@domain.com>
    angle_match = re.match(r'^<([^>]+)>$', raw)
    if angle_match:
        return angle_match.group(1).strip()

    return raw


class GmailProvider(BaseProvider):
    """
    Real Provider Adapter for Google Workspace / Gmail.
    Normalizes email messages, threads, attachments, and Google Cloud Pub/Sub push
    notifications into provider-agnostic ExternalEvent instances.
    Contains ZERO obligation-specific intelligence.
    """

    SCENARIO_PROGRESS = "GMAIL_SCENARIO_A_PROGRESS"
    SCENARIO_COMPLETION = "GMAIL_SCENARIO_B_COMPLETION"
    SCENARIO_BLOCKER = "GMAIL_SCENARIO_C_BLOCKER"
    SCENARIO_REQUEST = "GMAIL_SCENARIO_D_REQUEST"
    SCENARIO_CHATTER = "GMAIL_SCENARIO_E_CHATTER"
    SCENARIO_THREAD_REPLY = "GMAIL_SCENARIO_F_THREAD_REPLY"

    @property
    def provider_name(self) -> str:
        return "gmail"

    @property
    def provider_version(self) -> str:
        return "1.0.0"

    @property
    def capabilities(self) -> List[str]:
        return [
            "events",
            "messages",
            "threads",
            "attachments",
            "oauth",
            "email_ingestion",
        ]

    def validate_connection(self) -> bool:
        """
        Validates Gmail connection configuration.
        Returns True if Gmail is enabled with configured client credentials or in dev mode.
        """
        if settings.GMAIL_ENABLED and (settings.GMAIL_CLIENT_ID or settings.GMAIL_PUBSUB_TOPIC):
            return True
        return False

    def validate_payload(self, raw_payload: Dict[str, Any]) -> bool:
        """
        Validates that the raw payload contains required structure for an email or Gmail event.
        """
        if not isinstance(raw_payload, dict) or not raw_payload:
            return False

        # Support canonical scenarios
        if "scenario" in raw_payload:
            return True

        # Support Google Cloud Pub/Sub push format
        if "message" in raw_payload and isinstance(raw_payload["message"], dict):
            return True

        # Support standard email dictionaries
        email_keys = ["from", "sender", "to", "recipients", "subject", "body", "snippet", "text", "content", "payload"]
        if any(k in raw_payload for k in email_keys):
            return True

        return False

    def normalize_event(self, raw_payload: Dict[str, Any]) -> ExternalEvent:
        """
        Transforms Gmail payloads (direct email, Pub/Sub, Gmail API message, canonical scenario)
        into a normalized ExternalEvent.
        """
        if not self.validate_payload(raw_payload):
            raise ValueError("Malformed Gmail payload: invalid structure or empty dictionary.")

        # 1. Handle Canonical Scenarios for testing and development
        scenario = raw_payload.get("scenario")
        if scenario:
            return self.generate_canonical_event(
                scenario=scenario,
                custom_sender=raw_payload.get("sender") or raw_payload.get("from"),
                custom_recipients=raw_payload.get("recipients") or raw_payload.get("to"),
                custom_content=raw_payload.get("content") or raw_payload.get("body"),
                custom_subject=raw_payload.get("subject"),
                custom_metadata=raw_payload.get("metadata"),
                source_ref=raw_payload.get("source_ref") or raw_payload.get("message_id"),
            )

        # 2. Handle Google Cloud Pub/Sub push notification wrappers
        working_payload = raw_payload
        if "message" in raw_payload and isinstance(raw_payload["message"], dict):
            pubsub_msg = raw_payload["message"]
            pubsub_data = pubsub_msg.get("data")
            if pubsub_data:
                try:
                    decoded = base64.b64decode(pubsub_data).decode("utf-8")
                    parsed_json = json.loads(decoded)
                    if isinstance(parsed_json, dict):
                        working_payload = parsed_json
                        working_payload["pubsub_message_id"] = pubsub_msg.get("messageId")
                except Exception as e:
                    logger.debug(f"Pub/Sub data decode fallback: {e}")

        # 3. Extract sender and recipients
        raw_sender = (
            working_payload.get("from")
            or working_payload.get("sender")
            or working_payload.get("author")
            or "Unknown"
        )
        sender = parse_email_identity(raw_sender)

        raw_recipients = (
            working_payload.get("to")
            or working_payload.get("recipients")
            or working_payload.get("recipient")
            or []
        )
        if isinstance(raw_recipients, str):
            raw_recipients = [r.strip() for r in raw_recipients.split(",") if r.strip()]
        elif not isinstance(raw_recipients, list):
            raw_recipients = [str(raw_recipients)]

        recipients = [parse_email_identity(r) for r in raw_recipients if r]

        # 4. Extract subject and body content
        subject = working_payload.get("subject") or ""
        body_text = (
            working_payload.get("body")
            or working_payload.get("text")
            or working_payload.get("snippet")
            or working_payload.get("content")
            or ""
        )

        # Format unified content string while preserving subject context
        if subject and body_text and subject.lower() not in body_text.lower():
            content = f"Subject: {subject}\n\n{body_text}".strip()
        else:
            content = body_text or subject or "Empty Email Message"

        # 5. Extract Gmail Thread, Message, and MIME Metadata
        message_id = (
            working_payload.get("message_id")
            or working_payload.get("id")
            or working_payload.get("messageId")
            or working_payload.get("pubsub_message_id")
        )
        thread_id = working_payload.get("thread_id") or working_payload.get("threadId")
        in_reply_to = working_payload.get("in_reply_to") or working_payload.get("inReplyTo")
        references = working_payload.get("references")
        labels = working_payload.get("labels") or working_payload.get("labelIds") or []

        # 6. Resolve Deterministic Source Reference for Idempotency
        if working_payload.get("source_ref"):
            source_ref = str(working_payload.get("source_ref"))
        elif message_id:
            # Strip enclosing angle brackets if present in standard RFC message IDs
            clean_msg_id = str(message_id).strip("<> ")
            source_ref = f"gmail_{clean_msg_id}"
        elif thread_id:
            source_ref = f"gmail_thread_{thread_id}_{int(time.time() * 1000)}"
        else:
            source_ref = f"gmail_{uuid.uuid4().hex[:16]}"

        # 7. Normalize Attachments Metadata (Safely, without arbitrary file downloading)
        attachments_input = (
            working_payload.get("attachments")
            or working_payload.get("files")
            or []
        )
        normalized_attachments = []
        if isinstance(attachments_input, list):
            for att in attachments_input:
                if isinstance(att, dict):
                    att_name = att.get("name") or att.get("filename") or att.get("title") or "attachment"
                    att_filetype = att.get("filetype") or att.get("file_type") or att_name.split(".")[-1] if "." in att_name else "unknown"
                    normalized_attachments.append({
                        "name": att_name,
                        "filetype": att_filetype,
                        "mimetype": att.get("mimetype") or att.get("mime_type") or "application/octet-stream",
                        "size": att.get("size") or 0,
                        "attachment_id": att.get("attachment_id") or att.get("id"),
                    })

        # 8. Extract Timestamp
        raw_ts = working_payload.get("timestamp") or working_payload.get("date") or working_payload.get("internalDate")
        if isinstance(raw_ts, (int, float)):
            try:
                # Handle millisecond epoch from Gmail internalDate
                epoch = raw_ts / 1000.0 if raw_ts > 1e11 else raw_ts
                event_ts = datetime.fromtimestamp(epoch, tz=timezone.utc)
            except Exception:
                event_ts = utc_now()
        elif isinstance(raw_ts, str):
            try:
                event_ts = datetime.fromisoformat(raw_ts.replace("Z", "+00:00"))
            except ValueError:
                event_ts = utc_now()
        elif isinstance(raw_ts, datetime):
            event_ts = raw_ts
        else:
            event_ts = utc_now()

        # 9. Build Safe Metadata Dictionary (zero secret exposure)
        metadata: Dict[str, Any] = {
            "source_provider": "gmail",
            "subject": subject,
            "raw_sender": raw_sender,
            "recipients_raw": raw_recipients,
        }
        if message_id:
            metadata["message_id"] = str(message_id)
        if thread_id:
            metadata["thread_id"] = str(thread_id)
        if in_reply_to:
            metadata["in_reply_to"] = str(in_reply_to)
        if references:
            metadata["references"] = references
        if labels:
            metadata["labels"] = labels
        if normalized_attachments:
            metadata["attachments"] = normalized_attachments

        # Merge custom metadata safely
        custom_meta = working_payload.get("metadata")
        if isinstance(custom_meta, dict):
            for k, v in custom_meta.items():
                if k not in ["token", "secret", "access_token", "refresh_token", "client_secret", "authorization"]:
                    metadata[k] = v

        return ExternalEvent(
            source_type="gmail",
            source_ref=source_ref,
            sender=sender,
            recipients=recipients,
            timestamp=event_ts,
            content=content,
            metadata=metadata,
        )

    def generate_canonical_event(
        self,
        scenario: str,
        custom_sender: Optional[str] = None,
        custom_recipients: Optional[List[str]] = None,
        custom_content: Optional[str] = None,
        custom_subject: Optional[str] = None,
        custom_metadata: Optional[Dict[str, Any]] = None,
        source_ref: Optional[str] = None,
    ) -> ExternalEvent:
        """
        Generates deterministic test scenarios for Gmail provider verification.
        """
        sender = custom_sender or "Rahul <rahul@acme.com>"
        recipients = custom_recipients or ["Ravi <ravi@acme.com>"]
        ts = utc_now()
        meta = custom_metadata.copy() if custom_metadata else {}
        scenario_key = scenario.upper()

        if scenario_key in ["GMAIL_SCENARIO_A_PROGRESS", "GMAIL_SCENARIO_A", "PROGRESS"]:
            subject = custom_subject or "Re: Database benchmark numbers"
            content = custom_content or "Working on the database benchmark numbers. I'll send them shortly."
            meta.update({
                "subject": subject,
                "thread_id": "thread_gmail_benchmarks_101",
                "message_id": "<msg_progress_101@acme.com>",
            })
            ref = source_ref or "gmail_msg_progress_101"
            return self.normalize_event({
                "sender": sender,
                "recipients": recipients,
                "subject": subject,
                "body": content,
                "source_ref": ref,
                "metadata": meta,
                "timestamp": ts,
            })

        elif scenario_key in ["GMAIL_SCENARIO_B_COMPLETION", "GMAIL_SCENARIO_B", "COMPLETION"]:
            subject = custom_subject or "Database benchmark results"
            content = custom_content or "Sent the database benchmark numbers."
            meta.update({
                "subject": subject,
                "thread_id": "thread_gmail_benchmarks_101",
                "message_id": "<msg_completion_102@acme.com>",
                "attachments": [{"name": "benchmark_results.csv", "size": 16384, "filetype": "csv", "mimetype": "text/csv"}],
            })
            ref = source_ref or "gmail_msg_completion_102"
            return self.normalize_event({
                "sender": sender,
                "recipients": recipients,
                "subject": subject,
                "body": content,
                "source_ref": ref,
                "attachments": meta["attachments"],
                "metadata": meta,
                "timestamp": ts,
            })

        elif scenario_key in ["GMAIL_SCENARIO_C_BLOCKER", "GMAIL_SCENARIO_C", "BLOCKER"]:
            subject = custom_subject or "Blocked: Database benchmark export"
            content = custom_content or "Couldn't send the database benchmark numbers because the production database is unavailable."
            meta.update({
                "subject": subject,
                "thread_id": "thread_gmail_benchmarks_101",
                "message_id": "<msg_blocker_103@acme.com>",
            })
            ref = source_ref or "gmail_msg_blocker_103"
            return self.normalize_event({
                "sender": sender,
                "recipients": recipients,
                "subject": subject,
                "body": content,
                "source_ref": ref,
                "metadata": meta,
                "timestamp": ts,
            })

        elif scenario_key in ["GMAIL_SCENARIO_D_REQUEST", "GMAIL_SCENARIO_D", "REQUEST"]:
            req_sender = custom_sender or "Ravi <ravi@acme.com>"
            req_recipients = custom_recipients or ["Rahul <rahul@acme.com>"]
            subject = custom_subject or "Status Request: Database benchmark numbers"
            content = custom_content or "Rahul, could you send the updated benchmark numbers?"
            meta.update({
                "subject": subject,
                "thread_id": "thread_gmail_benchmarks_101",
                "message_id": "<msg_request_104@acme.com>",
            })
            ref = source_ref or "gmail_msg_request_104"
            return self.normalize_event({
                "sender": req_sender,
                "recipients": req_recipients,
                "subject": subject,
                "body": content,
                "source_ref": ref,
                "metadata": meta,
                "timestamp": ts,
            })

        elif scenario_key in ["GMAIL_SCENARIO_E_CHATTER", "GMAIL_SCENARIO_E", "CHATTER", "IRRELEVANT"]:
            subject = custom_subject or "Team Morning Greeting"
            content = custom_content or "Good morning everyone! Hope you all have a productive week."
            meta.update({
                "subject": subject,
                "thread_id": "thread_gmail_chatter_999",
                "message_id": "<msg_chatter_999@acme.com>",
            })
            ref = source_ref or "gmail_msg_chatter_999"
            return self.normalize_event({
                "sender": custom_sender or "Ravi <ravi@acme.com>",
                "recipients": custom_recipients or ["Team <team@acme.com>"],
                "subject": subject,
                "body": content,
                "source_ref": ref,
                "metadata": meta,
                "timestamp": ts,
            })

        elif scenario_key in ["GMAIL_SCENARIO_F_THREAD_REPLY", "GMAIL_SCENARIO_F", "THREAD_REPLY"]:
            subject = custom_subject or "Re: Database benchmark numbers [Thread Step 2]"
            content = custom_content or "Here is the follow up on the benchmarks as requested."
            meta.update({
                "subject": subject,
                "thread_id": "thread_gmail_benchmarks_101",
                "in_reply_to": "<msg_request_104@acme.com>",
                "references": ["<msg_request_104@acme.com>"],
                "message_id": "<msg_thread_reply_105@acme.com>",
            })
            ref = source_ref or "gmail_msg_thread_reply_105"
            return self.normalize_event({
                "sender": sender,
                "recipients": recipients,
                "subject": subject,
                "body": content,
                "source_ref": ref,
                "metadata": meta,
                "timestamp": ts,
            })

        # Fallback generic event
        return self.normalize_event({
            "sender": sender,
            "recipients": recipients,
            "subject": custom_subject or f"Gmail Event: {scenario}",
            "body": custom_content or f"Canonical Gmail payload for {scenario}",
            "source_ref": source_ref or f"gmail_{scenario.lower()}_{uuid.uuid4().hex[:8]}",
            "metadata": meta,
            "timestamp": ts,
        })
