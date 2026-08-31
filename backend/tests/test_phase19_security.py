"""
Phase 19 Test Suite: Security Hardening & Secret Sanitization.
Tests credential scrubbing, path traversal rejection, script injection detection, and sensitive key redaction.
"""

import pytest
from app.core.sanitizer import (
    sanitize_for_audit,
    is_sensitive_key,
    check_safe_path,
    check_safe_input,
)


def test_sensitive_key_detection():
    assert is_sensitive_key("password") is True
    assert is_sensitive_key("api_key") is True
    assert is_sensitive_key("user_secret_token") is True
    assert is_sensitive_key("authorization") is True
    assert is_sensitive_key("obligation_name") is False
    assert is_sensitive_key("deadline") is False


def test_sanitize_for_audit_redaction():
    raw_event = {
        "user_id": "usr-123",
        "action": "login",
        "access_token": "secret-jwt-token-12345",
        "nested": {
            "password_hash": "argon2$hashedpass",
            "safe_field": "visible value",
        }
    }
    sanitized = sanitize_for_audit(raw_event)
    assert sanitized["user_id"] == "usr-123"
    assert sanitized["access_token"] == "[REDACTED]"
    assert sanitized["nested"]["password_hash"] == "[REDACTED]"
    assert sanitized["nested"]["safe_field"] == "visible value"


def test_path_traversal_detection():
    assert check_safe_path("normal/path/file.json") is True
    assert check_safe_path("../etc/passwd") is False
    assert check_safe_path("..\\windows\\system32") is False
    assert check_safe_path("%2e%2e%2froot") is False


def test_script_injection_detection():
    assert check_safe_input("Normal commitment text") is True
    assert check_safe_input("<script>alert('xss')</script>") is False
    assert check_safe_input("javascript:evil()") is False
