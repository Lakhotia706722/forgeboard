"""
Symmetric encryption for connector credentials at rest.

Uses Fernet (AES-128-CBC + HMAC-SHA256) from the `cryptography` package.

⚠ MVP shortcut: the key lives in the FERNET_KEY env var.
Before production: migrate to HashiCorp Vault, AWS Secrets Manager, or GCP Secret Manager.
Key rotation is not implemented here — add envelope encryption if you need it.
"""
import json
from functools import lru_cache

from cryptography.fernet import Fernet, InvalidToken

from app.core.config import settings


@lru_cache(maxsize=1)
def _fernet() -> Fernet:
    key = settings.FERNET_KEY
    if not key:
        # Dev convenience: auto-generate a key and warn loudly.
        # This means credentials won't survive restarts — fine for dev, not for prod.
        import warnings
        generated = Fernet.generate_key().decode()
        warnings.warn(
            f"FERNET_KEY not set — generated ephemeral key: {generated}\n"
            "Set FERNET_KEY in your .env to persist credentials across restarts.",
            RuntimeWarning,
            stacklevel=2,
        )
        return Fernet(generated.encode())
    return Fernet(key.encode() if isinstance(key, str) else key)


def encrypt_json(data: dict) -> str:
    """Serialize dict to JSON then encrypt to a URL-safe base64 string."""
    plaintext = json.dumps(data).encode()
    return _fernet().encrypt(plaintext).decode()


def decrypt_json(token: str) -> dict:
    """Decrypt and deserialize back to dict. Raises InvalidToken if tampered."""
    try:
        plaintext = _fernet().decrypt(token.encode())
        return json.loads(plaintext)
    except (InvalidToken, json.JSONDecodeError) as exc:
        raise ValueError("Failed to decrypt credentials — token invalid or key mismatch.") from exc
