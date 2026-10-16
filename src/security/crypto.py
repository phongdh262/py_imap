import base64
import hashlib
import os
from typing import Optional


class SecretManager:
    """
    Handles credential masking and secret encryption:
    - Prevents accidental credential leaks in logs, reports, and UI
    - Provides lightweight obfuscation / encryption for stored tokens
    """

    @staticmethod
    def mask_secret(value: Optional[str], visible_chars: int = 3) -> str:
        """
        Masks a password or secret token (e.g., 'mySecretPassword123' -> 'myS***123').
        Returns '***' for short secrets.
        """
        if not value:
            return ""
        if len(value) <= visible_chars * 2:
            return "***"
        return f"{value[:visible_chars]}***{value[-visible_chars:]}"

    @staticmethod
    def hash_identifier(value: str) -> str:
        """Computes a SHA-256 hash for pseudonymized tracking in audit logs."""
        return hashlib.sha256(value.encode("utf-8")).hexdigest()[:16]

    @staticmethod
    def sanitize_log_dict(data: dict) -> dict:
        """Recursively masks sensitive keys (password, token, secret) in log dictionaries."""
        sensitive_keys = {"password", "source_password", "dest_password", "token", "oauth2_token", "secret", "app_password"}
        sanitized = {}
        for k, v in data.items():
            if isinstance(v, dict):
                sanitized[k] = SecretManager.sanitize_log_dict(v)
            elif any(s in k.lower() for s in sensitive_keys):
                sanitized[k] = SecretManager.mask_secret(str(v)) if v else ""
            else:
                sanitized[k] = v
        return sanitized
