"""
Compliance service — Phase 8b.

Provides:
  - Consent record CRUD
  - DNC entry CRUD
  - Calling-hours rule CRUD
  - check_outbound_allowed() — the gate called before every outbound call

⚠ Engineering scaffolding.  This is a starting technical checklist, not
a legal sign-off.  Review with qualified legal counsel before placing
outbound AI calls to real people.
"""
import json
import uuid
from datetime import datetime, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit import AuditLogEntry
from app.models.compliance import CallingHoursRule, ConsentRecord, DncEntry
from app.schemas.compliance import (
    CallingHoursRuleCreate,
    CallingHoursRuleOut,
    ComplianceStatusOut,
    ConsentRecordCreate,
    ConsentRecordOut,
    DncEntryCreate,
    DncEntryOut,
)

# Day-of-week mapping: Python datetime.weekday() → abbreviation
_DOW_MAP = {0: "mon", 1: "tue", 2: "wed", 3: "thu", 4: "fri", 5: "sat", 6: "sun"}


def _now() -> datetime:
    return datetime.now(timezone.utc)


# ---------------------------------------------------------------------------
# check_outbound_allowed — the main gate
# ---------------------------------------------------------------------------

async def check_outbound_allowed(
    workspace_id: uuid.UUID,
    phone_number: str,
    db: AsyncSession,
    agent_id: uuid.UUID | None = None,
    run_id: uuid.UUID | None = None,
    agent_name: str = "voice_agent",
) -> ComplianceStatusOut:
    """
    Run all three compliance checks against a phone number.

    Returns a ComplianceStatusOut.  The caller is responsible for raising
    an HTTP error if can_call=False — this function only returns data so it
    can be used both as a gate and as a read-only UI check.

    Audit log entries are written for DNC blocks.
    """
    status = ComplianceStatusOut(phone_number=phone_number, can_call=True)

    # ── 1. DNC check ─────────────────────────────────────────────────────────
    dnc_result = await db.execute(
        select(DncEntry).where(
            DncEntry.workspace_id == workspace_id,
            DncEntry.phone_number == phone_number,
        )
    )
    if dnc_result.scalar_one_or_none():
        status.dnc_listed = True
        status.can_call = False
        status.reason = "Number is on the workspace do-not-call list."

        # Write to audit log if we have a run context
        if agent_id and run_id:
            db.add(AuditLogEntry(
                workspace_id=workspace_id,
                agent_id=agent_id,
                run_id=run_id,
                agent_name=agent_name,
                tool_name="compliance_dnc_check",
                tool_input_json=json.dumps({"phone_number": phone_number}),
                tool_result_json=json.dumps({"blocked": True, "reason": "dnc_listed"}),
                outcome="error",
            ))

        return status  # fail fast — no need to check further

    # ── 2. Consent check ─────────────────────────────────────────────────────
    consent_result = await db.execute(
        select(ConsentRecord).where(
            ConsentRecord.workspace_id == workspace_id,
            ConsentRecord.phone_number == phone_number,
            ConsentRecord.consent_given.is_(True),
            ConsentRecord.revoked_at.is_(None),
        )
    )
    if consent_result.scalar_one_or_none():
        status.consent_active = True
    else:
        status.consent_active = False
        status.can_call = False
        status.reason = "No active consent record for this number."
        return status  # fail fast

    # ── 3. Calling-hours check ────────────────────────────────────────────────
    hours_ok, hours_reason = await _check_calling_hours(workspace_id, phone_number, db)
    status.within_calling_hours = hours_ok
    if not hours_ok:
        status.can_call = False
        status.reason = hours_reason

    return status


async def _check_calling_hours(
    workspace_id: uuid.UUID,
    phone_number: str,
    db: AsyncSession,
) -> tuple[bool, str | None]:
    """
    Check whether the current time falls within any applicable calling-hours rule
    for this workspace.

    Matching priority: most-specific region code wins.
    - No rules exist → allowed (open by default)
    - Rule exists but current time is outside window → blocked
    """
    rules_result = await db.execute(
        select(CallingHoursRule).where(
            CallingHoursRule.workspace_id == workspace_id,
        )
    )
    rules: list[CallingHoursRule] = list(rules_result.scalars().all())

    if not rules:
        # No rules configured — allow by default
        return True, None

    # Sort by specificity: "US-CA" (len 5) > "US" (len 2) > "*" (len 1)
    rules_sorted = sorted(rules, key=lambda r: len(r.region_code), reverse=True)

    # For MVP we don't infer the callee's region from the phone number —
    # that requires a number-lookup API (e.g. Twilio Lookup).  Instead we
    # evaluate the most-specific rule that matches "*" or any explicitly
    # configured region.  The workspace owner is responsible for setting up
    # region-specific rules if needed.
    #
    # Future: add Twilio Lookup to resolve callee country/state and use that
    # for region matching.
    applicable = rules_sorted[0]  # most-specific first, wildcard catches all

    try:
        tz = ZoneInfo(applicable.timezone)
    except ZoneInfoNotFoundError:
        # Misconfigured timezone — block and surface the error
        return False, f"Calling-hours rule has invalid timezone: {applicable.timezone!r}"

    local_now = datetime.now(tz)
    current_time = local_now.time()
    current_dow = _DOW_MAP[local_now.weekday()]

    allowed_days = [d.strip() for d in applicable.days_of_week.split(",")]
    if current_dow not in allowed_days:
        return (
            False,
            f"Outbound calls are not allowed on {current_dow} "
            f"per rule for region '{applicable.region_code}' "
            f"(allowed days: {applicable.days_of_week}).",
        )

    if not (applicable.start_time <= current_time <= applicable.end_time):
        return (
            False,
            f"Current local time {current_time.strftime('%H:%M')} "
            f"({applicable.timezone}) is outside the allowed calling window "
            f"{applicable.start_time.strftime('%H:%M')}–"
            f"{applicable.end_time.strftime('%H:%M')}.",
        )

    return True, None


# ---------------------------------------------------------------------------
# Consent CRUD
# ---------------------------------------------------------------------------

async def upsert_consent(
    workspace_id: uuid.UUID,
    data: ConsentRecordCreate,
    db: AsyncSession,
) -> ConsentRecordOut:
    """
    Create or update a consent record for a phone number.
    If consent_given=True, stamps consented_at and clears revoked_at.
    """
    result = await db.execute(
        select(ConsentRecord).where(
            ConsentRecord.workspace_id == workspace_id,
            ConsentRecord.phone_number == data.phone_number,
        )
    )
    record = result.scalar_one_or_none()

    now = _now()
    if record:
        record.consent_given = data.consent_given
        record.consent_method = data.consent_method
        if data.consent_text is not None:
            record.consent_text = data.consent_text
        if data.consent_given:
            record.consented_at = now
            record.revoked_at = None
        record.updated_at = now
    else:
        record = ConsentRecord(
            workspace_id=workspace_id,
            phone_number=data.phone_number,
            consent_given=data.consent_given,
            consent_method=data.consent_method,
            consent_text=data.consent_text,
            consented_at=now if data.consent_given else None,
        )
        db.add(record)

    await db.flush()
    return ConsentRecordOut.model_validate(record)


async def revoke_consent(
    workspace_id: uuid.UUID,
    phone_number: str,
    db: AsyncSession,
) -> ConsentRecordOut:
    """Mark an existing consent record as revoked."""
    result = await db.execute(
        select(ConsentRecord).where(
            ConsentRecord.workspace_id == workspace_id,
            ConsentRecord.phone_number == phone_number,
        )
    )
    record = result.scalar_one_or_none()
    if not record:
        raise HTTPException(status_code=404, detail="Consent record not found.")

    record.revoked_at = _now()
    record.consent_given = False
    record.updated_at = _now()
    await db.flush()
    return ConsentRecordOut.model_validate(record)


async def list_consent_records(
    workspace_id: uuid.UUID,
    db: AsyncSession,
) -> list[ConsentRecordOut]:
    result = await db.execute(
        select(ConsentRecord)
        .where(ConsentRecord.workspace_id == workspace_id)
        .order_by(ConsentRecord.created_at.desc())
    )
    return [ConsentRecordOut.model_validate(r) for r in result.scalars().all()]


async def get_consent_record(
    workspace_id: uuid.UUID,
    phone_number: str,
    db: AsyncSession,
) -> ConsentRecordOut:
    result = await db.execute(
        select(ConsentRecord).where(
            ConsentRecord.workspace_id == workspace_id,
            ConsentRecord.phone_number == phone_number,
        )
    )
    record = result.scalar_one_or_none()
    if not record:
        raise HTTPException(status_code=404, detail="Consent record not found.")
    return ConsentRecordOut.model_validate(record)


# ---------------------------------------------------------------------------
# DNC CRUD
# ---------------------------------------------------------------------------

async def add_dnc_entry(
    workspace_id: uuid.UUID,
    data: DncEntryCreate,
    db: AsyncSession,
) -> DncEntryOut:
    """Add a number to the DNC list. Idempotent — updates source/notes if already listed."""
    result = await db.execute(
        select(DncEntry).where(
            DncEntry.workspace_id == workspace_id,
            DncEntry.phone_number == data.phone_number,
        )
    )
    existing = result.scalar_one_or_none()
    if existing:
        # Update source and notes on re-add
        existing.source = data.source
        if data.notes is not None:
            existing.notes = data.notes
        await db.flush()
        return DncEntryOut.model_validate(existing)

    entry = DncEntry(
        workspace_id=workspace_id,
        phone_number=data.phone_number,
        source=data.source,
        notes=data.notes,
    )
    db.add(entry)
    await db.flush()
    return DncEntryOut.model_validate(entry)


async def remove_dnc_entry(
    workspace_id: uuid.UUID,
    phone_number: str,
    db: AsyncSession,
) -> None:
    result = await db.execute(
        select(DncEntry).where(
            DncEntry.workspace_id == workspace_id,
            DncEntry.phone_number == phone_number,
        )
    )
    entry = result.scalar_one_or_none()
    if not entry:
        raise HTTPException(status_code=404, detail="DNC entry not found.")
    await db.delete(entry)


async def list_dnc_entries(
    workspace_id: uuid.UUID,
    db: AsyncSession,
) -> list[DncEntryOut]:
    result = await db.execute(
        select(DncEntry)
        .where(DncEntry.workspace_id == workspace_id)
        .order_by(DncEntry.added_at.desc())
    )
    return [DncEntryOut.model_validate(e) for e in result.scalars().all()]


# ---------------------------------------------------------------------------
# Calling-hours CRUD
# ---------------------------------------------------------------------------

async def create_calling_hours_rule(
    workspace_id: uuid.UUID,
    data: CallingHoursRuleCreate,
    db: AsyncSession,
) -> CallingHoursRuleOut:
    rule = CallingHoursRule(
        workspace_id=workspace_id,
        region_code=data.region_code,
        days_of_week=data.days_of_week,
        start_time=data.start_time,
        end_time=data.end_time,
        timezone=data.timezone,
    )
    db.add(rule)
    await db.flush()
    return CallingHoursRuleOut.model_validate(rule)


async def delete_calling_hours_rule(
    workspace_id: uuid.UUID,
    rule_id: uuid.UUID,
    db: AsyncSession,
) -> None:
    result = await db.execute(
        select(CallingHoursRule).where(
            CallingHoursRule.id == rule_id,
            CallingHoursRule.workspace_id == workspace_id,
        )
    )
    rule = result.scalar_one_or_none()
    if not rule:
        raise HTTPException(status_code=404, detail="Calling-hours rule not found.")
    await db.delete(rule)


async def list_calling_hours_rules(
    workspace_id: uuid.UUID,
    db: AsyncSession,
) -> list[CallingHoursRuleOut]:
    result = await db.execute(
        select(CallingHoursRule)
        .where(CallingHoursRule.workspace_id == workspace_id)
        .order_by(CallingHoursRule.region_code)
    )
    return [CallingHoursRuleOut.model_validate(r) for r in result.scalars().all()]
