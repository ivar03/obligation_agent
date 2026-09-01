"""
Phase 23 Jira Provider Adapter.

Normalizes Jira Cloud webhooks, REST API sync payloads, issue lifecycle events,
status transitions, and comments into standardized, provider-agnostic ExternalEvent objects.
Contains ZERO obligation-specific intelligence.
"""

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


def extract_adf_text(content_node: Any) -> str:
    """
    Recursively extracts plain text from Atlassian Document Format (ADF) JSON structure,
    or returns plain string if already formatted.
    """
    if isinstance(content_node, str):
        return content_node.strip()
    if not isinstance(content_node, dict):
        return ""
    
    text_parts: List[str] = []
    
    if content_node.get("type") == "text" and "text" in content_node:
        text_parts.append(content_node["text"])
    
    if "content" in content_node and isinstance(content_node["content"], list):
        for child in content_node["content"]:
            child_text = extract_adf_text(child)
            if child_text:
                text_parts.append(child_text)
                
    return " ".join(text_parts).strip()


class JiraProvider(BaseProvider):
    """
    Real Provider Adapter for Jira Cloud (REST API & Webhooks).
    Normalizes issue creation, updates, transitions, comments, and project synchronization
    into provider-agnostic ExternalEvent instances.
    """

    @property
    def provider_name(self) -> str:
        return "jira"

    @property
    def provider_version(self) -> str:
        return "1.0.0"

    @property
    def capabilities(self) -> List[str]:
        return [
            "events",
            "issues",
            "webhooks",
            "status_transitions",
            "comments",
            "sync",
            "projects",
        ]

    def validate_connection(self) -> bool:
        """
        Validates Jira connection configuration.
        Returns True if Jira is enabled with configured API token, site URL, or in dev mode.
        """
        if settings.JIRA_ENABLED and (settings.JIRA_SITE_URL or settings.JIRA_API_TOKEN or settings.is_development()):
            return True
        return False

    def validate_payload(self, raw_payload: Dict[str, Any]) -> bool:
        """
        Validates that the raw payload contains a recognized Jira webhook or sync structure.
        """
        if not isinstance(raw_payload, dict) or not raw_payload:
            return False
        
        # Webhook formats
        if "webhookEvent" in raw_payload or "issue_event_type_name" in raw_payload:
            return True
        
        # Direct issue format (from REST API search / sync)
        if "key" in raw_payload and ("fields" in raw_payload or "summary" in raw_payload):
            return True
        
        if "issue" in raw_payload and isinstance(raw_payload["issue"], dict):
            return True
            
        return False

    @staticmethod
    def verify_jira_webhook(
        request_body: bytes,
        secret: str,
        signature: Optional[str] = None,
        token_param: Optional[str] = None,
    ) -> bool:
        """
        Verifies the authenticity of an incoming Jira webhook.
        Supports both HMAC-SHA256 signature verification and shared secret verification.
        """
        if not secret:
            return True  # If no secret configured in dev mode

        # 1. Query token verification
        if token_param and hmac.compare_digest(token_param, secret):
            return True

        # 2. HMAC-SHA256 header verification
        if signature:
            # Strip sha256= prefix if present
            clean_sig = signature.replace("sha256=", "").strip()
            computed_hmac = hmac.new(secret.encode("utf-8"), request_body, hashlib.sha256).hexdigest()
            if hmac.compare_digest(clean_sig, computed_hmac):
                return True

        return False

    def normalize_event(self, raw_payload: Dict[str, Any]) -> ExternalEvent:
        """
        Transforms Jira webhook payloads and REST API issue sync items into standardized ExternalEvent.
        Handles issue_created, issue_updated (status changes, assignee changes, due date changes),
        issue_deleted, and comment_created/updated events.
        """
        if not self.validate_payload(raw_payload):
            raise ValueError("Malformed Jira payload: missing required issue or webhook structure.")

        webhook_event = raw_payload.get("webhookEvent") or raw_payload.get("event") or "jira:issue_updated"
        
        # Extract issue dictionary
        if "issue" in raw_payload and isinstance(raw_payload["issue"], dict):
            issue = raw_payload["issue"]
        else:
            issue = raw_payload

        key = issue.get("key") or raw_payload.get("key") or "JIRA-UNKNOWN"
        fields = issue.get("fields", {}) if isinstance(issue.get("fields"), dict) else {}

        # Extract Core Issue Fields
        summary = fields.get("summary") or issue.get("summary") or "Untitled Jira Issue"
        raw_desc = fields.get("description") or issue.get("description") or ""
        description = extract_adf_text(raw_desc) if isinstance(raw_desc, dict) else str(raw_desc or "")
        
        # Status
        status_obj = fields.get("status", {}) if isinstance(fields.get("status"), dict) else {}
        status_name = status_obj.get("name") or issue.get("status") or "To Do"
        
        # Priority
        priority_obj = fields.get("priority", {}) if isinstance(fields.get("priority"), dict) else {}
        priority_name = priority_obj.get("name") or issue.get("priority") or "Medium"
        
        # Assignee & Reporter
        assignee_obj = fields.get("assignee") if isinstance(fields.get("assignee"), dict) else None
        assignee_name = (assignee_obj.get("displayName") or assignee_obj.get("emailAddress")) if assignee_obj else None
        assignee_email = assignee_obj.get("emailAddress") if assignee_obj else None
        
        reporter_obj = fields.get("reporter") if isinstance(fields.get("reporter"), dict) else None
        reporter_name = (reporter_obj.get("displayName") or reporter_obj.get("emailAddress")) if reporter_obj else None
        reporter_email = reporter_obj.get("emailAddress") if reporter_obj else None

        # Project
        project_obj = fields.get("project", {}) if isinstance(fields.get("project"), dict) else {}
        project_key = project_obj.get("key") or issue.get("project") or (key.split("-")[0] if "-" in key else "PROJ")
        project_name = project_obj.get("name") or project_key

        # Due Date
        due_date_str = fields.get("duedate") or issue.get("duedate") or issue.get("due_date")

        # Labels & Components
        labels = fields.get("labels", []) if isinstance(fields.get("labels"), list) else []
        
        # Changelog / Field Transitions
        changelog_items: List[Dict[str, Any]] = []
        changelog_obj = raw_payload.get("changelog", {})
        if isinstance(changelog_obj, dict) and "items" in changelog_obj:
            changelog_items = changelog_obj.get("items", [])

        status_transition: Optional[str] = None
        assignee_transition: Optional[str] = None
        duedate_transition: Optional[str] = None

        for chg in changelog_items:
            field_name = str(chg.get("field", "")).lower()
            from_str = chg.get("fromString") or "None"
            to_str = chg.get("toString") or "None"
            if field_name == "status":
                status_transition = f"{from_str} -> {to_str}"
                status_name = to_str
            elif field_name == "assignee":
                assignee_transition = f"{from_str} -> {to_str}"
                assignee_name = to_str
            elif field_name in ("duedate", "due date"):
                duedate_transition = f"{from_str} -> {to_str}"
                due_date_str = to_str

        # Comments
        comment_body: Optional[str] = None
        comment_author_email: Optional[str] = None
        comment_author_name: Optional[str] = None
        comment_id: Optional[str] = None
        if "comment" in raw_payload and isinstance(raw_payload["comment"], dict):
            c_obj = raw_payload["comment"]
            comment_id = c_obj.get("id")
            raw_c_body = c_obj.get("body")
            comment_body = extract_adf_text(raw_c_body) if isinstance(raw_c_body, dict) else str(raw_c_body or "")
            c_author_obj = c_obj.get("author", {}) if isinstance(c_obj.get("author"), dict) else {}
            comment_author_email = c_author_obj.get("emailAddress")
            comment_author_name = c_author_obj.get("displayName") or comment_author_email or "Jira User"

        # Construct Readable Markdown Observation Content
        content_lines: List[str] = []
        
        if comment_body:
            content_lines.append(f"**Jira Comment on {key}** by {comment_author_name or 'User'}:")
            content_lines.append(f"> \"{comment_body}\"")
            content_lines.append(f"Issue Summary: {summary} | Status: {status_name} | Priority: {priority_name}")
        else:
            content_lines.append(f"**Jira Issue [{key}]**: {summary}")
            if status_transition:
                content_lines.append(f"**Status Transition**: {status_transition}")
            else:
                content_lines.append(f"**Status**: {status_name}")

            if assignee_transition:
                content_lines.append(f"**Assignment Change**: {assignee_transition}")
            elif assignee_name:
                content_lines.append(f"**Assignee**: {assignee_name}")

            if duedate_transition:
                content_lines.append(f"**Due Date Change**: {duedate_transition}")
            elif due_date_str:
                content_lines.append(f"**Due Date**: {due_date_str}")

            content_lines.append(f"**Priority**: {priority_name} | **Project**: {project_name} ({project_key})")
            
            if description:
                desc_snippet = description[:300] + ("..." if len(description) > 300 else "")
                content_lines.append(f"**Description**: {desc_snippet}")

            if labels:
                content_lines.append(f"**Labels**: {', '.join(labels)}")

        content_text = "\n".join(content_lines)

        # Timestamp
        timestamp_raw = (
            fields.get("updated")
            or issue.get("updated")
            or raw_payload.get("timestamp")
            or (raw_payload.get("comment", {}).get("updated") if isinstance(raw_payload.get("comment"), dict) else None)
        )
        observed_time: Optional[datetime] = None
        if timestamp_raw:
            try:
                if isinstance(timestamp_raw, (int, float)):
                    observed_time = datetime.fromtimestamp(timestamp_raw / 1000.0 if timestamp_raw > 1e11 else timestamp_raw, tz=timezone.utc)
                elif isinstance(timestamp_raw, str):
                    observed_time = datetime.fromisoformat(timestamp_raw.replace("Z", "+00:00"))
            except Exception:
                observed_time = utc_now()
        else:
            observed_time = utc_now()

        # Sender & Recipients
        sender = comment_author_email or comment_author_name or assignee_email or assignee_name or reporter_email or reporter_name or "jira-bot"
        recipients: List[str] = []
        if reporter_email or reporter_name:
            recipients.append(reporter_email or reporter_name)
        if assignee_email and assignee_email != sender:
            recipients.append(assignee_email)


        # Source reference
        if comment_id:
            source_ref = f"jira:{key}:comment:{comment_id}"
            source_type = "comment"
        else:
            source_ref = f"jira:{key}"
            source_type = "issue"

        # Metadata
        event_metadata: Dict[str, Any] = {
            "provider": "jira",
            "webhook_event": webhook_event,
            "jira_key": key,
            "project_key": project_key,
            "project_name": project_name,
            "status": status_name,
            "priority": priority_name,
            "due_date": due_date_str,
            "assignee": assignee_name,
            "reporter": reporter_name,
            "labels": labels,
            "has_comment": bool(comment_body),
            "status_transition": status_transition,
            "changelog": changelog_items,
            "url": f"{settings.JIRA_SITE_URL.rstrip('/')}/browse/{key}" if settings.JIRA_SITE_URL else None,
        }

        return ExternalEvent(
            source_type=source_type,
            source_ref=source_ref,
            sender=sender,
            recipients=recipients,
            timestamp=observed_time,
            content=content_text,
            metadata=event_metadata,
        )
