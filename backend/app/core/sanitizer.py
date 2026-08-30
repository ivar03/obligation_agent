"""
Secret Sanitization Engine for Audit and Governance Logging.
Ensures no sensitive credentials, secrets, tokens, passwords, cookies,
or authorization headers are ever persisted into immutable audit logs.
"""

from typing import Any, Dict, List, Set, Union
from datetime import datetime, date


SENSITIVE_KEY_SUBSTRINGS: Set[str] = {
    "password",
    "passwd",
    "secret",
    "token",
    "cookie",
    "authorization",
    "auth_header",
    "api_key",
    "apikey",
    "private_key",
    "credentials",
    "bearer",
    "access_token",
    "refresh_token",
    "client_secret",
    "signing_secret",
    "password_hash",
    "hash_password",
    "session_token",
    "salt",
}


def is_sensitive_key(key: str) -> bool:
    """
    Checks if a key name suggests sensitive data.
    """
    key_lower = str(key).lower().replace("-", "_")
    return any(substr in key_lower for substr in SENSITIVE_KEY_SUBSTRINGS)


def sanitize_for_audit(data: Any, max_depth: int = 6) -> Any:
    """
    Recursively scrubs sensitive keys from dictionaries, lists, and objects.
    Converts datetimes and non-serializable objects to safe primitives.
    """
    if max_depth <= 0:
        return "[TRUNCATED_DEPTH]"

    if data is None:
        return None

    if isinstance(data, (int, float, bool)):
        return data

    if isinstance(data, (datetime, date)):
        return data.isoformat()

    if isinstance(data, str):
        # Prevent huge string dumps
        if len(data) > 10000:
            return data[:10000] + "... [TRUNCATED]"
        return data

    if isinstance(data, dict):
        sanitized: Dict[str, Any] = {}
        for k, v in data.items():
            str_key = str(k)
            if is_sensitive_key(str_key):
                sanitized[str_key] = "[REDACTED]"
            else:
                sanitized[str_key] = sanitize_for_audit(v, max_depth - 1)
        return sanitized

    if isinstance(data, (list, tuple, set)):
        return [sanitize_for_audit(item, max_depth - 1) for item in data]

    # If it's a Pydantic model or SQLAlchemy model or dataclass with __dict__
    if hasattr(data, "model_dump"):
        return sanitize_for_audit(data.model_dump(), max_depth - 1)
    elif hasattr(data, "dict"):
        return sanitize_for_audit(data.dict(), max_depth - 1)
    elif hasattr(data, "__dict__"):
        safe_dict = {
            k: v for k, v in data.__dict__.items()
            if not k.startswith("_") and not callable(v)
        }
        return sanitize_for_audit(safe_dict, max_depth - 1)

    return str(data)
