import hmac
import hashlib
import base64
import json
import secrets
import time
from typing import Optional, Dict, Any

from app.core.config import settings

# Default secret for local dev if not explicitly configured in environment
AUTH_SECRET_KEY = getattr(settings, "AUTH_SECRET", "obligation_agent_secret_signing_key_2026_dev_mode_change_in_prod")


def hash_password(password: str) -> str:
    """
    Hashes a password using PBKDF2-HMAC-SHA256 with 100,000 iterations and a 16-byte random salt.
    Format: pbkdf2_sha256$<iterations>$<salt_hex>$<hash_hex>
    """
    salt = secrets.token_bytes(16)
    iterations = 100_000
    derived = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
    return f"pbkdf2_sha256${iterations}${salt.hex()}${derived.hex()}"


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verifies a plaintext password against a stored PBKDF2 hash using constant-time comparison.
    """
    try:
        parts = hashed_password.split("$")
        if len(parts) != 4 or parts[0] != "pbkdf2_sha256":
            return False
        iterations = int(parts[1])
        salt = bytes.fromhex(parts[2])
        expected_hash = bytes.fromhex(parts[3])
        derived = hashlib.pbkdf2_hmac("sha256", plain_password.encode("utf-8"), salt, iterations)
        return secrets.compare_digest(derived, expected_hash)
    except Exception:
        return False


def create_session_token(
    user_id: str,
    workspace_id: Optional[str] = None,
    expires_in_seconds: int = 86400 * 7,  # 7 days
) -> str:
    """
    Generates a cryptographically signed tamper-proof session token.
    Token format: base64url(payload).base64url(hmac_signature)
    """
    now = int(time.time())
    payload = {
        "sub": user_id,
        "ws": workspace_id,
        "iat": now,
        "exp": now + expires_in_seconds,
    }
    payload_json = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    payload_b64 = base64.urlsafe_b64encode(payload_json).decode("utf-8").rstrip("=")

    signature = hmac.new(
        AUTH_SECRET_KEY.encode("utf-8"),
        payload_b64.encode("utf-8"),
        hashlib.sha256,
    ).digest()
    sig_b64 = base64.urlsafe_b64encode(signature).decode("utf-8").rstrip("=")

    return f"{payload_b64}.{sig_b64}"


def decode_session_token(token: str) -> Optional[Dict[str, Any]]:
    """
    Verifies the HMAC-SHA256 signature and expiration of a session token,
    returning the decoded payload dictionary or None if invalid/expired.
    """
    if not token or "." not in token:
        return None

    try:
        payload_b64, sig_b64 = token.split(".", 1)

        # Verify signature
        expected_sig = hmac.new(
            AUTH_SECRET_KEY.encode("utf-8"),
            payload_b64.encode("utf-8"),
            hashlib.sha256,
        ).digest()
        expected_sig_b64 = base64.urlsafe_b64encode(expected_sig).decode("utf-8").rstrip("=")

        if not secrets.compare_digest(sig_b64, expected_sig_b64):
            return None

        # Decode payload
        padding = 4 - (len(payload_b64) % 4)
        if padding != 4:
            payload_b64 += "=" * padding
        payload_json = base64.urlsafe_b64decode(payload_b64).decode("utf-8")
        payload = json.loads(payload_json)

        # Check expiration
        now = int(time.time())
        if "exp" in payload and payload["exp"] < now:
            return None

        return payload
    except Exception:
        return None
