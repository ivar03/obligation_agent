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


def hash_invitation_token(raw_token: str) -> str:
    """Computes SHA-256 hash of an invitation token for database storage."""
    return hashlib.sha256(raw_token.strip().encode("utf-8")).hexdigest()


def verify_invitation_token(raw_token: str, stored_hash: str) -> bool:
    """Verifies a raw invitation token against its stored SHA-256 hash."""
    computed_hash = hash_invitation_token(raw_token)
    return secrets.compare_digest(computed_hash, stored_hash)


def generate_secure_invitation_token() -> tuple[str, str]:
    """
    Generates a high-entropy URL-safe invitation token and its persistent SHA-256 hash.
    Returns: (raw_token_for_email_link, hashed_token_for_db)
    """
    raw_token = secrets.token_urlsafe(32)
    hashed_token = hash_invitation_token(raw_token)
    return raw_token, hashed_token


def generate_oauth_state(workspace_id: str, provider: str = "slack") -> str:
    """Generates an HMAC-signed CSRF state parameter for OAuth handshakes."""
    now = int(time.time())
    nonce = secrets.token_hex(16)
    payload = f"{workspace_id}:{provider}:{now}:{nonce}"
    sig = hmac.new(AUTH_SECRET_KEY.encode("utf-8"), payload.encode("utf-8"), hashlib.sha256).hexdigest()[:32]
    return f"{payload}:{sig}"


def validate_oauth_state(state: str, max_age_seconds: int = 600) -> Optional[Dict[str, str]]:
    """
    Validates an OAuth state string for signature validity and expiration (10 min).
    Returns dict with workspace_id and provider if valid, None otherwise.
    """
    if not state or state.count(":") != 4:
        return None
    try:
        ws_id, provider, ts_str, nonce, sig = state.split(":")
        payload = f"{ws_id}:{provider}:{ts_str}:{nonce}"
        expected_sig = hmac.new(AUTH_SECRET_KEY.encode("utf-8"), payload.encode("utf-8"), hashlib.sha256).hexdigest()[:32]
        if not secrets.compare_digest(sig, expected_sig):
            return None
        ts = int(ts_str)
        if time.time() - ts > max_age_seconds:
            return None
        return {"workspace_id": ws_id, "provider": provider}
    except Exception:
        return None

