"""
Credential scrubber — Phase 10c.

Before any third-party submission enters the review queue, its config_payload
is scanned for patterns that look like credentials or workspace-specific data.

If suspicious patterns are found, the submission is REJECTED with a clear
error before it even reaches an admin reviewer.

⚠ Security note: this is a best-effort heuristic, not a cryptographic guarantee.
A determined bad actor could obfuscate credentials. The review step (human eyes)
is the second line of defence. Do NOT rely solely on this scrubber to prevent
credential leakage — the admin review queue exists precisely because automated
detection is imperfect.

Patterns checked:
  - OAuth / Bearer tokens (ya29., xoxb-, sk-, pk_, etc.)
  - API keys (common prefixes and high-entropy strings)
  - UUIDs that look like workspace/agent/connector IDs (keys named *_id, *Id)
  - JWT-shaped strings (three dot-separated base64 segments)
  - Private key PEM blocks
  - Password / secret / token field names with non-empty values
  - Twilio SID patterns (AC*, SK*, etc.)
  - High-entropy strings > 32 chars (potential raw secrets)
"""
import math
import re
import uuid
from typing import Any


# ---------------------------------------------------------------------------
# Regex patterns
# ---------------------------------------------------------------------------

_OAUTH_TOKEN     = re.compile(r"\bya29\.[0-9A-Za-z_\-]+")
_SLACK_TOKEN     = re.compile(r"\bxox[bpoa]-[0-9A-Za-z\-]+")
_ANTHROPIC_KEY   = re.compile(r"\bsk-ant-[0-9A-Za-z_\-]+")
_OPENAI_KEY      = re.compile(r"\bsk-[0-9A-Za-z]{20,}")
_STRIPE_KEY      = re.compile(r"\b(pk_live|sk_live|rk_live)_[0-9A-Za-z]+")
_TWILIO_SID      = re.compile(r"\b(AC|SK|CA|CR)[0-9a-f]{32}\b")
_JWT             = re.compile(r"\beyJ[A-Za-z0-9_\-]+\.[A-Za-z0-9_\-]+\.[A-Za-z0-9_\-]+")
_PEM_BLOCK       = re.compile(r"-----BEGIN (RSA |EC |OPENSSH )?PRIVATE KEY-----")
_UUID_PATTERN    = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
    re.IGNORECASE,
)

# Field names that should never have non-empty values in a public payload
_SECRET_FIELD_NAMES = {
    "password", "secret", "token", "api_key", "apikey", "auth_token",
    "access_token", "refresh_token", "client_secret", "private_key",
    "encrypted_credentials", "credentials", "key", "bearer",
}

# Keys that indicate workspace/agent/connector identity
_IDENTITY_FIELD_SUFFIXES = ("_id", "Id", "ID")
_IDENTITY_FIELD_NAMES = {
    "workspace_id", "agent_id", "connector_id", "user_id",
    "workspaceId", "agentId", "connectorId", "userId",
}


def _shannon_entropy(s: str) -> float:
    """Approximate Shannon entropy of a string — high values suggest random secrets."""
    if not s:
        return 0.0
    freq = {}
    for c in s:
        freq[c] = freq.get(c, 0) + 1
    n = len(s)
    return -sum((count / n) * math.log2(count / n) for count in freq.values())


def _check_string_value(key: str, value: str) -> list[str]:
    """Return a list of warning messages if value looks like a credential."""
    warnings = []

    # Known token prefixes
    for pattern, name in [
        (_OAUTH_TOKEN,   "Google OAuth token"),
        (_SLACK_TOKEN,   "Slack token"),
        (_ANTHROPIC_KEY, "Anthropic API key"),
        (_OPENAI_KEY,    "OpenAI API key"),
        (_STRIPE_KEY,    "Stripe key"),
        (_TWILIO_SID,    "Twilio SID"),
        (_JWT,           "JWT token"),
        (_PEM_BLOCK,     "PEM private key"),
    ]:
        if pattern.search(value):
            warnings.append(f"Field '{key}' contains a potential {name}.")

    # UUID in identity fields
    key_lower = key.lower()
    if key in _IDENTITY_FIELD_NAMES or any(key_lower.endswith(s.lower()) for s in _IDENTITY_FIELD_SUFFIXES):
        if _UUID_PATTERN.match(value.strip()):
            warnings.append(
                f"Field '{key}' looks like a workspace/agent/connector ID (UUID). "
                "Templates must be workspace-agnostic."
            )

    # Secret field name with non-empty value
    if key_lower in _SECRET_FIELD_NAMES and value.strip():
        warnings.append(
            f"Field '{key}' has a name associated with secrets and contains a non-empty value."
        )

    # High-entropy string (likely a raw secret/key)
    if len(value) > 32 and _shannon_entropy(value) > 4.5:
        warnings.append(
            f"Field '{key}' contains a high-entropy string (possible raw secret, "
            f"length={len(value)})."
        )

    return warnings


def _walk(obj: Any, path: str = "") -> list[str]:
    """Recursively walk a JSON-like object and collect warnings."""
    warnings: list[str] = []

    if isinstance(obj, dict):
        for k, v in obj.items():
            child_path = f"{path}.{k}" if path else k
            if isinstance(v, str):
                warnings.extend(_check_string_value(child_path, v))
            elif isinstance(v, (dict, list)):
                warnings.extend(_walk(v, child_path))

    elif isinstance(obj, list):
        for i, item in enumerate(obj):
            warnings.extend(_walk(item, f"{path}[{i}]"))

    return warnings


def scrub_payload(payload: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    """
    Scan a config_payload for credential-like content.

    Returns:
        (cleaned_payload, warnings)
        cleaned_payload: the payload with no modifications (we don't auto-remove —
                         the submitter must fix their payload)
        warnings: list of human-readable warning messages; empty = clean

    The caller should raise an error if warnings is non-empty.
    """
    warnings = _walk(payload)
    return payload, warnings
