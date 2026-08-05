"""
Transcript redaction — Phase 8c.

Runs regex patterns over transcript segment text to replace obvious
sensitive data with [REDACTED] before storing to the database.

Patterns covered:
  - Payment card numbers (13–19 digits, optionally space/dash separated)
  - US Social Security Numbers (NNN-NN-NNNN and 9 consecutive digits when
    preceded by a disclosure phrase)
  - CVV/CVC codes (3–4 digits when immediately preceded by a trigger phrase)

Design notes:
  - Conservative by default: we only redact when context makes it clear
    the digits are sensitive.  False negatives (missed PII) are preferable
    to false positives (redacting phone/zip/year values).
  - Patterns are applied per-segment, not across segment boundaries.
  - This is a best-effort heuristic.  It does not replace a purpose-built
    PII-detection service (e.g. AWS Comprehend, Google DLP) for high-risk
    deployments.
"""
import re

from app.voice.interfaces import TranscriptSegment


# ---------------------------------------------------------------------------
# Compiled patterns
# ---------------------------------------------------------------------------

# Payment card: 13–19 digits with optional single-char separators (space or dash)
# Covers Visa (16), Mastercard (16), Amex (15), Discover (16), Diners (14), etc.
_CARD_NUMBER = re.compile(
    r"\b(?:\d[ -]?){13,18}\d\b"
)

# US SSN — dashed form: NNN-NN-NNNN
_SSN_DASHED = re.compile(
    r"\b\d{3}-\d{2}-\d{4}\b"
)

# US SSN — 9 consecutive digits, but only when preceded (within 60 chars) by
# a disclosure phrase.  Lookahead not used because Python re doesn't support
# variable-length lookbehind; we match phrase + digits together and keep phrase.
_SSN_TRIGGER = re.compile(
    r"(social\s+security(?:\s+number)?|ssn|social\s+security\s+#|tax\s+id)"
    r"[\s:,\-–—]*(\d{9})",
    re.IGNORECASE,
)

# CVV / CVC — 3 or 4 digits immediately following a trigger word
_CVV_TRIGGER = re.compile(
    r"(cvv|cvc|cvv2|cvc2|security\s+code|card\s+security\s+(?:number|code))"
    r"[\s:,\-–—]*(\d{3,4})\b",
    re.IGNORECASE,
)

# Credit-card expiry in context — MM/YY or MM/YYYY after "expiry"/"expiration"
_EXPIRY_TRIGGER = re.compile(
    r"(expir(?:y|ation|es?)\s*(?:date)?)"
    r"[\s:,\-–—]*(\d{1,2}/\d{2,4})\b",
    re.IGNORECASE,
)

_REDACTED = "[REDACTED]"


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def redact_text(text: str) -> str:
    """
    Apply all redaction patterns to a single string.
    Returns the string with sensitive values replaced by [REDACTED].
    """
    # Order matters: apply card number first (broadest pattern) then specifics
    text = _CARD_NUMBER.sub(_REDACTED, text)
    text = _SSN_DASHED.sub(_REDACTED, text)
    # For SSN trigger: keep the trigger phrase, replace only the digit group
    text = _SSN_TRIGGER.sub(lambda m: m.group(1) + " " + _REDACTED, text)
    # For CVV trigger: keep trigger phrase, replace digits
    text = _CVV_TRIGGER.sub(lambda m: m.group(1) + " " + _REDACTED, text)
    # For expiry trigger: keep trigger phrase, replace date
    text = _EXPIRY_TRIGGER.sub(lambda m: m.group(1) + " " + _REDACTED, text)
    return text


def redact_transcript(
    segments: list[TranscriptSegment],
) -> list[TranscriptSegment]:
    """
    Return a new list of TranscriptSegments with sensitive data redacted.
    The original list is not mutated.
    """
    redacted = []
    for seg in segments:
        cleaned = redact_text(seg.text)
        if cleaned != seg.text:
            # Rebuild dataclass with redacted text, preserve all other fields
            redacted.append(TranscriptSegment(
                speaker=seg.speaker,
                text=cleaned,
                is_final=seg.is_final,
                confidence=seg.confidence,
                timestamp_ms=seg.timestamp_ms,
            ))
        else:
            redacted.append(seg)
    return redacted
