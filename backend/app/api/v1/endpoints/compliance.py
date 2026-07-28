"""
Compliance endpoints — Phase 8b.

  Consent:
  POST   /compliance/consent              — upsert consent record
  POST   /compliance/consent/revoke       — revoke consent for a number
  GET    /compliance/consent              — list all consent records
  GET    /compliance/consent/{phone}      — get consent record for a number

  DNC:
  POST   /compliance/dnc                  — add number to DNC list
  DELETE /compliance/dnc/{phone}          — remove from DNC list
  GET    /compliance/dnc                  — list DNC entries

  Calling hours:
  POST   /compliance/calling-hours        — create a calling-hours rule
  DELETE /compliance/calling-hours/{id}   — delete a rule
  GET    /compliance/calling-hours        — list rules

  Status check:
  GET    /compliance/check/{phone}        — can this number be called right now?

⚠ Engineering scaffolding — not a legal sign-off.
Review with qualified legal counsel before placing outbound AI calls to real people.
"""
import uuid

from fastapi import APIRouter

from app.api.deps import CurrentWorkspace, DB
from app.schemas.compliance import (
    CallingHoursRuleCreate,
    CallingHoursRuleOut,
    ComplianceStatusOut,
    ConsentRecordCreate,
    ConsentRecordOut,
    DncEntryCreate,
    DncEntryOut,
)
from app.services import compliance_service

router = APIRouter()


# ---------------------------------------------------------------------------
# Consent
# ---------------------------------------------------------------------------

@router.post("/consent", response_model=ConsentRecordOut, status_code=201)
async def upsert_consent(
    body: ConsentRecordCreate, workspace: CurrentWorkspace, db: DB
):
    """
    Record or update consent for a phone number.
    If a record already exists it is updated in-place (idempotent).
    Setting consent_given=false has the same effect as revoke.
    """
    result = await compliance_service.upsert_consent(workspace.id, body, db)
    await db.commit()
    return result


@router.post("/consent/revoke", response_model=ConsentRecordOut)
async def revoke_consent(
    body: dict, workspace: CurrentWorkspace, db: DB
):
    """
    Revoke consent for a phone number. The record is kept for audit purposes
    with revoked_at stamped.  Accepts {"phone_number": "+15551234567"}.
    """
    phone = body.get("phone_number", "")
    if not phone:
        from fastapi import HTTPException
        raise HTTPException(status_code=422, detail="phone_number is required.")
    result = await compliance_service.revoke_consent(workspace.id, phone, db)
    await db.commit()
    return result


@router.get("/consent", response_model=list[ConsentRecordOut])
async def list_consent_records(workspace: CurrentWorkspace, db: DB):
    return await compliance_service.list_consent_records(workspace.id, db)


@router.get("/consent/{phone_number:path}", response_model=ConsentRecordOut)
async def get_consent_record(
    phone_number: str, workspace: CurrentWorkspace, db: DB
):
    """Lookup consent status for a single number. phone_number must be E.164."""
    return await compliance_service.get_consent_record(workspace.id, phone_number, db)


# ---------------------------------------------------------------------------
# DNC
# ---------------------------------------------------------------------------

@router.post("/dnc", response_model=DncEntryOut, status_code=201)
async def add_dnc(body: DncEntryCreate, workspace: CurrentWorkspace, db: DB):
    """Add a number to the workspace DNC list. Idempotent."""
    result = await compliance_service.add_dnc_entry(workspace.id, body, db)
    await db.commit()
    return result


@router.delete("/dnc/{phone_number:path}", status_code=204)
async def remove_dnc(phone_number: str, workspace: CurrentWorkspace, db: DB):
    """Remove a number from the DNC list. phone_number must be E.164."""
    await compliance_service.remove_dnc_entry(workspace.id, phone_number, db)
    await db.commit()


@router.get("/dnc", response_model=list[DncEntryOut])
async def list_dnc(workspace: CurrentWorkspace, db: DB):
    return await compliance_service.list_dnc_entries(workspace.id, db)


# ---------------------------------------------------------------------------
# Calling hours
# ---------------------------------------------------------------------------

@router.post("/calling-hours", response_model=CallingHoursRuleOut, status_code=201)
async def create_calling_hours(
    body: CallingHoursRuleCreate, workspace: CurrentWorkspace, db: DB
):
    result = await compliance_service.create_calling_hours_rule(workspace.id, body, db)
    await db.commit()
    return result


@router.delete("/calling-hours/{rule_id}", status_code=204)
async def delete_calling_hours(
    rule_id: uuid.UUID, workspace: CurrentWorkspace, db: DB
):
    await compliance_service.delete_calling_hours_rule(workspace.id, rule_id, db)
    await db.commit()


@router.get("/calling-hours", response_model=list[CallingHoursRuleOut])
async def list_calling_hours(workspace: CurrentWorkspace, db: DB):
    return await compliance_service.list_calling_hours_rules(workspace.id, db)


# ---------------------------------------------------------------------------
# Status check (read-only — no side effects)
# ---------------------------------------------------------------------------

@router.get("/check/{phone_number:path}", response_model=ComplianceStatusOut)
async def check_compliance(
    phone_number: str, workspace: CurrentWorkspace, db: DB
):
    """
    Non-destructive pre-call compliance check.
    Returns can_call + reason without writing anything to the DB.
    Useful for UI feedback before initiating a call.
    """
    return await compliance_service.check_outbound_allowed(
        workspace_id=workspace.id,
        phone_number=phone_number,
        db=db,
    )
