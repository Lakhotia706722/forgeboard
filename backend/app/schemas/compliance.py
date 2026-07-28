"""
Pydantic schemas for the Phase 8b compliance endpoints.

⚠ Engineering scaffolding — not legal sign-off.
"""
import uuid
from datetime import datetime, time

from pydantic import BaseModel, Field, field_validator


# ---------------------------------------------------------------------------
# Consent records
# ---------------------------------------------------------------------------

class ConsentRecordCreate(BaseModel):
    phone_number: str = Field(description="E.164 format, e.g. +15551234567")
    consent_given: bool
    consent_method: str = Field(
        default="manual",
        description="How consent was captured: web_form | sms_reply | ivr | manual",
    )
    consent_text: str | None = Field(
        default=None,
        description="Verbatim wording shown/read to the callee at consent capture time.",
    )


class ConsentRecordRevoke(BaseModel):
    """Payload to revoke an existing consent record."""
    phone_number: str


class ConsentRecordOut(BaseModel):
    id: uuid.UUID
    workspace_id: uuid.UUID
    phone_number: str
    consent_given: bool
    consent_method: str
    consent_text: str | None
    consented_at: datetime | None
    revoked_at: datetime | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# DNC entries
# ---------------------------------------------------------------------------

class DncEntryCreate(BaseModel):
    phone_number: str = Field(description="E.164 format")
    source: str = Field(
        default="manual",
        description="manual | callee_request | national_registry_import",
    )
    notes: str | None = None


class DncEntryOut(BaseModel):
    id: uuid.UUID
    workspace_id: uuid.UUID
    phone_number: str
    source: str
    notes: str | None
    added_at: datetime

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Calling-hours rules
# ---------------------------------------------------------------------------

class CallingHoursRuleCreate(BaseModel):
    region_code: str = Field(
        default="*",
        description="Region code: '*' (wildcard), 'US', 'US-CA', 'GB', etc.",
    )
    days_of_week: str = Field(
        default="mon,tue,wed,thu,fri",
        description="Comma-separated lowercase day abbreviations: mon,tue,wed,thu,fri,sat,sun",
    )
    start_time: time = Field(description="Local start time, e.g. 09:00:00")
    end_time: time = Field(description="Local end time, e.g. 20:00:00")
    timezone: str = Field(
        default="America/New_York",
        description="IANA timezone string, e.g. America/Los_Angeles, Europe/London",
    )

    @field_validator("timezone")
    @classmethod
    def validate_timezone(cls, v: str) -> str:
        try:
            from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
            ZoneInfo(v)
        except Exception:
            raise ValueError(f"Unknown IANA timezone: {v!r}")
        return v

    @field_validator("days_of_week")
    @classmethod
    def validate_days(cls, v: str) -> str:
        valid = {"mon", "tue", "wed", "thu", "fri", "sat", "sun"}
        days = [d.strip().lower() for d in v.split(",") if d.strip()]
        bad = [d for d in days if d not in valid]
        if bad:
            raise ValueError(f"Invalid day abbreviations: {bad}")
        return ",".join(days)


class CallingHoursRuleOut(BaseModel):
    id: uuid.UUID
    workspace_id: uuid.UUID
    region_code: str
    days_of_week: str
    start_time: time
    end_time: time
    timezone: str
    created_at: datetime

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Compliance status check (read-only response)
# ---------------------------------------------------------------------------

class ComplianceStatusOut(BaseModel):
    """
    Result of checking whether a phone number can be called right now.
    Used by the UI before placing a call for user-facing feedback.
    """
    phone_number: str
    can_call: bool
    reason: str | None = None          # why it's blocked, if can_call=False
    dnc_listed: bool = False
    consent_active: bool = False
    within_calling_hours: bool = True  # True if no rules exist (open by default)
