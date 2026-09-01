"""
Phase 17 Credential Encryption & Secret Storage Utility.

Provides symmetric encryption and decryption for third-party provider tokens
and integration secrets at rest with key-versioning metadata.
Ensures raw credentials are NEVER leaked in plaintext across APIs, logs, or audits.
"""

import base64
import hashlib
from typing import Optional, Tuple
from cryptography.fernet import Fernet, InvalidToken

from app.core.config import settings
from app.core.logging import logger


class CryptoService:
    """
    Symmetric encryption service for secrets at rest.
    Uses AES-128-CBC / HMAC-SHA256 (Fernet) with base64 urlsafe encoding.
    """

    _cipher: Optional[Fernet] = None
    _key_version: str = "v1"

    @classmethod
    def _get_fernet(cls) -> Fernet:
        if cls._cipher is None:
            raw_key = settings.ENCRYPTION_KEY.strip()
            if not raw_key:
                # Derive a deterministic 32-byte urlsafe base64 key from JWT_SECRET_KEY
                derived = hashlib.sha256(settings.JWT_SECRET_KEY.encode("utf-8")).digest()
                raw_key = base64.urlsafe_b64encode(derived).decode("utf-8")
            else:
                # Ensure it is valid base64 32-byte
                try:
                    decoded = base64.urlsafe_b64decode(raw_key.encode("utf-8"))
                    if len(decoded) != 32:
                        derived = hashlib.sha256(raw_key.encode("utf-8")).digest()
                        raw_key = base64.urlsafe_b64encode(derived).decode("utf-8")
                except Exception:
                    derived = hashlib.sha256(raw_key.encode("utf-8")).digest()
                    raw_key = base64.urlsafe_b64encode(derived).decode("utf-8")

            cls._cipher = Fernet(raw_key.encode("utf-8"))
        return cls._cipher

    @classmethod
    def encrypt(cls, plaintext: str) -> str:
        """
        Encrypts a plaintext string and returns a versioned envelope string.
        Envelope format: 'enc:v1:<base64-ciphertext>'
        """
        if not plaintext:
            return ""
        cipher = cls._get_fernet()
        encrypted_bytes = cipher.encrypt(plaintext.encode("utf-8"))
        return f"enc:{cls._key_version}:{encrypted_bytes.decode('utf-8')}"

    @classmethod
    def decrypt(cls, ciphertext_envelope: str) -> str:
        """
        Decrypts a versioned ciphertext envelope.
        If plaintext is already unencrypted (legacy format), returns it safely.
        """
        if not ciphertext_envelope:
            return ""
        if not ciphertext_envelope.startswith("enc:"):
            # Plaintext / legacy fallback
            return ciphertext_envelope

        parts = ciphertext_envelope.split(":", 2)
        if len(parts) != 3:
            return ciphertext_envelope

        version, payload = parts[1], parts[2]
        cipher = cls._get_fernet()
        try:
            decrypted_bytes = cipher.decrypt(payload.encode("utf-8"))
            return decrypted_bytes.decode("utf-8")
        except InvalidToken:
            logger.error("Failed to decrypt secret: invalid token or corrupted key.")
            raise ValueError("Decryption failed: corrupted ciphertext or invalid encryption key.")

    @classmethod
    def mask_secret(cls, secret: str, visible_chars: int = 4) -> str:
        """
        Safely masks a secret string for display in logs or UI (e.g., 'xoxb-****1234').
        """
        if not secret:
            return ""
        if len(secret) <= visible_chars * 2:
            return "********"
        prefix = secret[:visible_chars]
        suffix = secret[-visible_chars:]
        return f"{prefix}****{suffix}"


encrypt_secret = CryptoService.encrypt
decrypt_secret = CryptoService.decrypt
mask_secret = CryptoService.mask_secret


