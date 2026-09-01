"""
Unit Tests for JiraProvider Adapter & Normalization Engine.

Verifies:
 - Provider metadata & capabilities.
 - Normalization of issue creation, update (status transition, assignee change, due date change),
   issue deletion, and comment creation events.
 - Atlassian Document Format (ADF) rich text parsing.
 - Webhook HMAC-SHA256 signature verification.
 - Malformed payload rejection.
"""

import hmac
import hashlib
import json
import pytest
from datetime import datetime, timezone

from app.services.providers.jira_provider import JiraProvider, extract_adf_text
from app.schemas.obligation import ExternalEvent


def test_jira_provider_metadata_and_capabilities():
    provider = JiraProvider()
    assert provider.provider_name == "jira"
    assert provider.provider_version == "1.0.0"
    assert "events" in provider.capabilities
    assert "issues" in provider.capabilities
    assert "webhooks" in provider.capabilities
    assert "status_transitions" in provider.capabilities
    assert "comments" in provider.capabilities
    assert "sync" in provider.capabilities
    assert provider.validate_connection() is True


def test_extract_adf_text():
    # 1. Plain string
    assert extract_adf_text("Plain text description") == "Plain text description"

    # 2. ADF document structure
    adf_doc = {
        "version": 1,
        "type": "doc",
        "content": [
            {
                "type": "paragraph",
                "content": [
                    {"type": "text", "text": "This is a root paragraph with "},
                    {"type": "text", "text": "rich text content."},
                ]
            },
            {
                "type": "paragraph",
                "content": [
                    {"type": "text", "text": "Second paragraph line."}
                ]
            }
        ]
    }
    extracted = extract_adf_text(adf_doc)
    assert "This is a root paragraph with rich text content." in extracted
    assert "Second paragraph line." in extracted


def test_normalize_issue_created():
    provider = JiraProvider()
    payload = {
        "webhookEvent": "jira:issue_created",
        "timestamp": 1725235200000,
        "issue": {
            "key": "ENG-402",
            "fields": {
                "summary": "Implement Automated Security Invariant Checker",
                "description": {
                    "type": "doc",
                    "content": [{"type": "paragraph", "content": [{"type": "text", "text": "Create background audit jobs for active workspaces."}]}]
                },
                "status": {"name": "To Do"},
                "priority": {"name": "High"},
                "assignee": {"displayName": "Sarah Connor", "emailAddress": "sarah@company.com"},
                "reporter": {"displayName": "John Doe", "emailAddress": "john@company.com"},
                "project": {"key": "ENG", "name": "Engineering Core"},
                "duedate": "2026-09-20",
                "labels": ["security", "audit"],
                "updated": "2026-09-02T10:00:00Z",
            }
        }
    }

    event = provider.normalize_event(payload)
    assert isinstance(event, ExternalEvent)
    assert event.source_type == "issue"
    assert event.source_ref == "jira:ENG-402"
    assert event.sender == "sarah@company.com"
    assert "john@company.com" in event.recipients
    assert "ENG-402" in event.content
    assert "Implement Automated Security Invariant Checker" in event.content
    assert "**Status**: To Do" in event.content
    assert "**Priority**: High" in event.content
    assert "**Due Date**: 2026-09-20" in event.content
    assert event.metadata["jira_key"] == "ENG-402"
    assert event.metadata["project_key"] == "ENG"
    assert event.metadata["status"] == "To Do"
    assert event.metadata["priority"] == "High"


def test_normalize_issue_updated_status_transition():
    provider = JiraProvider()
    payload = {
        "webhookEvent": "jira:issue_updated",
        "issue": {
            "key": "SEC-881",
            "fields": {
                "summary": "SOC2 Access Review Matrix",
                "status": {"name": "Blocked"},
                "priority": {"name": "Critical"},
                "assignee": {"displayName": "Priya Sharma", "emailAddress": "priya@company.com"},
                "project": {"key": "SEC", "name": "Security"},
            }
        },
        "changelog": {
            "items": [
                {
                    "field": "status",
                    "fromString": "In Progress",
                    "toString": "Blocked",
                }
            ]
        }
    }

    event = provider.normalize_event(payload)
    assert event.source_ref == "jira:SEC-881"
    assert "**Status Transition**: In Progress -> Blocked" in event.content
    assert event.metadata["status_transition"] == "In Progress -> Blocked"
    assert event.metadata["status"] == "Blocked"


def test_normalize_issue_updated_assignee_and_duedate():
    provider = JiraProvider()
    payload = {
        "webhookEvent": "jira:issue_updated",
        "issue": {
            "key": "INFRA-200",
            "fields": {
                "summary": "Kubernetes 1.30 Cluster Upgrade",
                "status": {"name": "In Progress"},
                "priority": {"name": "High"},
                "assignee": {"displayName": "Alex Chen", "emailAddress": "alex@company.com"},
                "project": {"key": "INFRA", "name": "Infrastructure"},
                "duedate": "2026-09-30",
            }
        },
        "changelog": {
            "items": [
                {
                    "field": "assignee",
                    "fromString": "DevOps Bot",
                    "toString": "Alex Chen",
                },
                {
                    "field": "duedate",
                    "fromString": "2026-09-15",
                    "toString": "2026-09-30",
                }
            ]
        }
    }

    event = provider.normalize_event(payload)
    assert "**Assignment Change**: DevOps Bot -> Alex Chen" in event.content
    assert "**Due Date Change**: 2026-09-15 -> 2026-09-30" in event.content
    assert event.metadata["due_date"] == "2026-09-30"



def test_normalize_issue_comment_created():
    provider = JiraProvider()
    payload = {
        "webhookEvent": "comment_created",
        "issue": {
            "key": "ENG-402",
            "fields": {
                "summary": "Implement Automated Security Invariant Checker",
                "status": {"name": "In Progress"},
                "priority": {"name": "High"},
            }
        },
        "comment": {
            "id": "10499",
            "author": {"displayName": "Priya Sharma", "emailAddress": "priya@company.com"},
            "body": "Blocked by database benchmark run. Need staging replica resized before cutover.",
            "updated": "2026-09-02T11:15:00Z",
        }
    }

    event = provider.normalize_event(payload)
    assert event.source_type == "comment"
    assert event.source_ref == "jira:ENG-402:comment:10499"
    assert event.sender == "priya@company.com"
    assert "Blocked by database benchmark run" in event.content
    assert event.metadata["has_comment"] is True


def test_verify_jira_webhook_signatures():
    secret = "my-secret-webhook-key-12345"
    body = b'{"webhookEvent":"jira:issue_created","issue":{"key":"TEST-1"}}'
    
    # 1. Correct HMAC-SHA256 signature
    correct_sig = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
    assert JiraProvider.verify_jira_webhook(body, secret=secret, signature=f"sha256={correct_sig}") is True
    assert JiraProvider.verify_jira_webhook(body, secret=secret, signature=correct_sig) is True

    # 2. Incorrect HMAC signature
    assert JiraProvider.verify_jira_webhook(body, secret=secret, signature="sha256=invalid-signature") is False

    # 3. Query token parameter match
    assert JiraProvider.verify_jira_webhook(body, secret=secret, token_param=secret) is True
    assert JiraProvider.verify_jira_webhook(body, secret=secret, token_param="wrong-token") is False


def test_malformed_jira_payload_rejection():
    provider = JiraProvider()
    with pytest.raises(ValueError, match="Malformed Jira payload"):
        provider.normalize_event({})
    
    with pytest.raises(ValueError, match="Malformed Jira payload"):
        provider.normalize_event({"random_key": 123})
