"""
Phase 19 Structured Logging.

Provides a JSON-formatted logger for production and a human-readable format
for development. All log records are automatically enriched with the active
request_id (correlation ID) and scrubbed for credentials.

Usage:
    from app.core.logging import setup_logging, logger, get_logger
    logger.info("event", extra={"operation": "plan.approve", "workspace_id": ws_id})
"""

import re
import sys
import json
import logging
import time
from typing import Any

from app.core.config import settings

# ---------------------------------------------------------------------------
# Credential scrubbing — never log tokens, secrets, keys, or passwords.
# ---------------------------------------------------------------------------
_CREDENTIAL_PATTERNS = [
    re.compile(r'(?i)(token|secret|key|password|passwd|authorization|api[_-]?key|bearer|credential)["\s:=]+[^\s,"}{]+'),
    re.compile(r'(?i)(xoxb|xoxp|xoxa)-[a-zA-Z0-9\-]+'),   # Slack tokens
    re.compile(r'(?i)eyJ[a-zA-Z0-9_\-]+\.[a-zA-Z0-9_\-]+\.[a-zA-Z0-9_\-]+'),  # JWTs
    re.compile(r'(?i)ghp_[a-zA-Z0-9]{36}'),  # GitHub tokens
    re.compile(r'(?i)sk-[a-zA-Z0-9]{32,}'),  # OpenAI keys
]


def _scrub_credentials(value: str) -> str:
    """Replace credential-looking content with redaction markers."""
    for pattern in _CREDENTIAL_PATTERNS:
        value = pattern.sub("[REDACTED]", value)
    return value


def _scrub_dict(d: dict) -> dict:
    """Recursively scrub a dict's string values."""
    result = {}
    for k, v in d.items():
        if isinstance(v, dict):
            result[k] = _scrub_dict(v)
        elif isinstance(v, str):
            result[k] = _scrub_credentials(v)
        else:
            result[k] = v
    return result


# ---------------------------------------------------------------------------
# JSON Formatter
# ---------------------------------------------------------------------------

class JSONFormatter(logging.Formatter):
    """
    Formats log records as single-line JSON objects suitable for log aggregators
    (Datadog, CloudWatch, GCP Logging, Loki, etc.).

    Standard fields always present:
        timestamp, level, logger, message

    Optional enrichment fields (set via extra= kwargs):
        request_id, workspace_id, actor_id, operation, route,
        duration_ms, status, error_code, provider, event_id,
        execution_id, decision_plan_id
    """

    STANDARD_FIELDS = {
        "name", "msg", "args", "levelname", "levelno", "pathname",
        "filename", "module", "exc_info", "exc_text", "stack_info",
        "lineno", "funcName", "created", "msecs", "relativeCreated",
        "thread", "threadName", "processName", "process", "taskName",
        "message",
    }

    def format(self, record: logging.LogRecord) -> str:
        # Resolve the message
        message = record.getMessage()
        message = _scrub_credentials(message)

        record_dict: dict[str, Any] = {
            "timestamp": self.formatTime(record, "%Y-%m-%dT%H:%M:%S.") + f"{int(record.msecs):03d}Z",
            "level": record.levelname,
            "logger": record.name,
            "message": message,
        }

        # Inject correlation ID from context var if available
        try:
            from app.core.request_context import request_id_ctx
            req_id = request_id_ctx.get()
            if req_id:
                record_dict["request_id"] = req_id
        except Exception:
            pass

        # Include any extra structured fields, excluding standard logging internals
        for key, val in record.__dict__.items():
            if key not in self.STANDARD_FIELDS and not key.startswith("_"):
                if isinstance(val, str):
                    val = _scrub_credentials(val)
                record_dict[key] = val

        # Attach exception info if present
        if record.exc_info:
            exc_type, exc_val, _ = record.exc_info
            # Never include full tracebacks in production; include type + safe message
            record_dict["error_type"] = exc_type.__name__ if exc_type else "UnknownError"
            record_dict["error_message"] = _scrub_credentials(str(exc_val)) if exc_val else ""

        return json.dumps(record_dict, default=str, ensure_ascii=False)


# ---------------------------------------------------------------------------
# Text Formatter (development)
# ---------------------------------------------------------------------------

class ContextTextFormatter(logging.Formatter):
    """Human-readable formatter that injects request_id when available."""

    def format(self, record: logging.LogRecord) -> str:
        try:
            from app.core.request_context import request_id_ctx
            req_id = request_id_ctx.get()
            prefix = f"[{req_id[:8]}]" if req_id else ""
        except Exception:
            prefix = ""
        base = super().format(record)
        return f"{prefix} {base}" if prefix else base


# ---------------------------------------------------------------------------
# Setup
# ---------------------------------------------------------------------------

def setup_logging() -> None:
    """
    Configure root logging handler appropriate for the current environment.
    JSON in production/staging; readable text in development.
    """
    log_level = getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO)

    use_json = (
        settings.LOG_FORMAT.lower() == "json"
        or settings.is_production()
        or settings.is_staging()
    )

    handler = logging.StreamHandler(sys.stdout)

    if use_json:
        handler.setFormatter(JSONFormatter())
    else:
        handler.setFormatter(
            ContextTextFormatter(
                fmt="[%(asctime)s] [%(levelname)s] [%(name)s]: %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S",
            )
        )

    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(log_level)

    # Quieten noisy third-party loggers
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    """Return a named logger inheriting the configured handler."""
    return logging.getLogger(name)


# Default application logger
logger = get_logger("obligation_agent")
