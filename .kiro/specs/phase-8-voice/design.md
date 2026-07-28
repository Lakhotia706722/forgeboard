# Phase 8 — Voice & Telephony Agent Module: Technical Design

## Codebase state as of design date

The scaffolding from Phase 8 planning is already committed and real:
- Vendor-abstraction interfaces, Twilio/Deepgram/ElevenLabs concrete providers, `call_engine.py`, `VoiceAgent`/`CallLog` ORM models, migration `0006`, `voice_service.py`, all REST+WebSocket endpoints, and the frontend `voiceApi.ts`, `CallStatusBadge`, `CallLogDrawer` components are **complete**.
- The voice router is **already registered** in `api/v1/router.py`.
- All Phase 8 Python dependencies (`twilio`, `deepgram-sdk`, `elevenlabs`, `websockets`) are **already in** `requirements.txt`.
- All voice env vars are **already defined** in `config.py` and `.env.example`.

What this document designs is the **remaining gaps** across all five sub-phases.

---

## 8a — Telephony Foundation: Remaining Gaps

### Gap 1 — Inbound call routing by phone number

**Problem:** The `/voice/answer/{call_log_id}` webhook currently returns "not configured" for inbound calls because the `call_log_id` in the URL path is only meaningful for outbound (where we create the `CallLog` before placing the call). For inbound, Twilio hits a static URL per phone number — it has no `call_log_id` yet.

**Design:**

Add a second webhook route that Twilio posts to for inbound calls, keyed by `voice_agent_id` rather than `call_log_id`. The URL you configure in the Twilio console per phone number becomes:

```
POST /api/v1/voice/inbound/{voice_agent_id}
```

This endpoint:
1. Reads `CallSid`, `From`, `To` from the Twilio form POST.
2. Calls the existing `voice_service.handle_inbound_call()` (already implemented) which creates the `AgentRun` + `CallLog` and returns TwiML.
3. Returns the TwiML as `application/xml`.

`handle_inbound_call()` already exists in `voice_service.py` — the only change is wiring a new endpoint that calls it.

**Files changed:**
- `backend/app/api/v1/endpoints/voice.py` — add `POST /inbound/{voice_agent_id}` route.

---

### Gap 2 — `workspace_id` not available in the inbound webhook

The webhook receives no auth token (it's Twilio, not a user). `handle_inbound_call` needs a `workspace_id`. The lookup path: given `voice_agent_id`, the `VoiceAgent` row already has `workspace_id` — so the endpoint loads the voice agent first to get it.

**Files changed:**
- `backend/app/api/v1/endpoints/voice.py` — the new inbound handler queries `VoiceAgent` for `workspace_id` before calling the service.

---

### Gap 3 — Twilio signature validation (security)

Twilio webhook endpoints currently accept any POST. For production, every Twilio webhook must verify the `X-Twilio-Signature` header using the Twilio auth token. This is a FastAPI dependency.

**Design:** A reusable `validate_twilio_signature` dependency function in `app/api/deps.py` that:
1. Reads `settings.TWILIO_AUTH_TOKEN` and reconstructs the expected URL.
2. Uses `twilio.request_validator.RequestValidator` to verify the signature.
3. Raises HTTP 403 if invalid.
4. Is applied to all three Twilio webhook routes (`/inbound/{id}`, `/answer/{id}`, `/status`).

**Files changed:**
- `backend/app/api/deps.py` — add `validate_twilio_signature` dependency.
- `backend/app/api/v1/endpoints/voice.py` — apply to the three webhook routes.

---

## 8b — Compliance Layer

> **⚠ Engineering scaffolding only. This is a starting technical checklist — not a legal sign-off. Real counsel review is mandatory before placing outbound AI calls to real people.**

### Data model additions

Three new tables, one new migration (`0007_compliance.py`):

**`consent_records`**
```
id              UUID PK
workspace_id    UUID FK workspaces
phone_number    VARCHAR(30) NOT NULL  -- E.164, indexed
consent_given   BOOLEAN NOT NULL DEFAULT false
consent_method  VARCHAR(50)           -- "web_form" | "sms_reply" | "manual"
consent_text    TEXT                  -- exact wording shown to callee
consented_at    TIMESTAMPTZ
revoked_at      TIMESTAMPTZ NULL
created_at      TIMESTAMPTZ
```

**`dnc_entries`**
```
id              UUID PK
workspace_id    UUID FK workspaces
phone_number    VARCHAR(30) NOT NULL
source          VARCHAR(50)   -- "manual" | "callee_request" | "national_registry_import"
added_at        TIMESTAMPTZ
notes           TEXT NULL
UNIQUE(workspace_id, phone_number)
```

**`calling_hours_rules`**
```
id              UUID PK
workspace_id    UUID FK workspaces
region_code     VARCHAR(10) NOT NULL  -- "US-CA", "US", "*" (wildcard)
days_of_week    VARCHAR(20)           -- "mon,tue,wed,thu,fri"
start_time_utc  TIME NOT NULL         -- stored as UTC; converted from local at rule creation
end_time_utc    TIME NOT NULL
created_at      TIMESTAMPTZ
```

ORM models go in a new file: `backend/app/models/compliance.py`.

---

### Enforcement in `voice_service.initiate_outbound_call()`

Before placing any outbound call, three sequential checks are inserted immediately after the concurrency cap checks:

**Step 1 — DNC check**
```python
dnc = await db.execute(
    select(DncEntry).where(
        DncEntry.workspace_id == workspace_id,
        DncEntry.phone_number == request.to,
    )
)
if dnc.scalar_one_or_none():
    # Log the blocked attempt to audit log, raise 403
    raise HTTPException(status_code=403, detail="Number is on the DNC list.")
call_log.dnc_checked = True
```

**Step 2 — Consent check**
```python
consent = await db.execute(
    select(ConsentRecord).where(
        ConsentRecord.workspace_id == workspace_id,
        ConsentRecord.phone_number == request.to,
        ConsentRecord.consent_given == True,
        ConsentRecord.revoked_at == None,
    )
)
if not consent.scalar_one_or_none():
    raise HTTPException(status_code=403, detail="No active consent record for this number.")
call_log.consent_verified = True
```

**Step 3 — Calling hours check**
```python
now_utc = datetime.now(timezone.utc)
# Load rules for workspace — try region match, then wildcard
# Compare now_utc.time() against start_time_utc/end_time_utc
# Compare now_utc.weekday() against days_of_week
# If no rules exist, default to allowing the call (open)
```

**Files changed:**
- `backend/app/models/compliance.py` — new file, three ORM models.
- `backend/alembic/versions/0007_compliance.py` — new migration.
- `backend/app/services/voice_service.py` — insert the three checks in `initiate_outbound_call`.
- `backend/app/services/compliance_service.py` — new file, functions for consent CRUD, DNC CRUD, calling hours CRUD, and the `check_outbound_allowed()` helper (extracted so it's testable independently).
- `backend/app/schemas/compliance.py` — new file, Pydantic schemas for all three resources.
- `backend/app/api/v1/endpoints/compliance.py` — new file, REST endpoints for managing consent/DNC/calling hours.
- `backend/app/api/v1/router.py` — register compliance router at `/compliance`.

---

### AI disclosure enforcement

The current call engine sets `call_log.ai_disclosed = True` after the call ends. The opening message already includes "I'm an AI assistant" — but there's no gate preventing someone from removing that line.

**Design:** The opening message construction in `call_engine.run_call_session()` is extracted into a function `_build_opening(agent, voice_agent)` that always prepends the disclosure statement. The disclosure prefix is a platform-level constant that cannot be removed via config — only the appended text can vary.

```python
DISCLOSURE_PREFIX = "Hello, I'm an AI assistant calling on behalf of"
# result: "Hello, I'm an AI assistant calling on behalf of [agent name]. [goal]. How can I help?"
```

`call_log.ai_disclosed = True` is set immediately after the opening TTS is sent, not at call end.

**Files changed:**
- `backend/app/voice/call_engine.py` — extract `_build_opening()`, set `ai_disclosed` early.

---

## 8c — Transcripts, Recording & Archive

### Real-time transcript storage

Already implemented: `call_engine.py` accumulates `list[TranscriptSegment]` and writes to `call_log.transcript_json` on call end. No changes needed for transcript storage itself.

The gap is the **archive UI** — a searchable transcript list page in the frontend.

### Call recording via Twilio

Twilio supports dual-channel recording via the `record` parameter on `calls.create()`. When a recording completes, Twilio POSTs a callback with `RecordingUrl` and `RecordingSid`.

**Design:**

Add `recording_url` and `recording_sid` columns to `CallLog`:
```
recording_sid   VARCHAR(100) NULL
recording_url   TEXT NULL           -- Twilio HTTPS URL to the .mp3/.wav
```

Migration `0008_call_recording.py`.

In `TwilioProvider.place_outbound_call()`, add `record=True` and `recording_status_callback` to the `calls.create()` params.

Add a new Twilio webhook `POST /voice/recording-status` that receives the recording callback and updates `CallLog.recording_url` / `recording_sid`.

**Encryption note:** The `recording_url` is a Twilio-hosted URL (requires Twilio auth to access). Storing it as-is is acceptable for MVP. Full encrypted at-rest storage (download + encrypt + store in S3/GCS) is a post-Phase-8 hardening item — flag this explicitly in the code as a TODO.

**Files changed:**
- `backend/app/models/voice_agent.py` — add `recording_sid`, `recording_url` to `CallLog`.
- `backend/alembic/versions/0008_call_recording.py` — add the two columns.
- `backend/app/voice/providers/twilio_provider.py` — add `record=True` + recording callback param to `place_outbound_call`.
- `backend/app/api/v1/endpoints/voice.py` — add `POST /recording-status` webhook.
- `backend/app/schemas/voice.py` — add `recording_url` / `recording_sid` to `CallLogOut`.

### Redaction

Regex-based redaction runs on the final `transcript_json` before it is committed to the database. Applied in `call_engine.py` just before the `await db.commit()` at call end.

Patterns to redact (replace with `[REDACTED]`):
- Card numbers: `\b(?:\d[ -]?){13,16}\b`
- US SSN: `\b\d{3}-\d{2}-\d{4}\b`
- US SSN no dashes: `\b\d{9}\b` (only in context — applied conservatively)
- CVV: `\b[0-9]{3,4}\b` adjacent to card-related words (conservative — match only when preceded by "cvv", "security code", "cvc" within 50 chars)

Redaction is a pure string pass over each transcript segment's `text` field before JSON serialization. Implementation in a new `backend/app/voice/redaction.py` module.

**Files changed:**
- `backend/app/voice/redaction.py` — new file, `redact_transcript(segments: list[TranscriptSegment]) -> list[TranscriptSegment]`.
- `backend/app/voice/call_engine.py` — call `redact_transcript()` before committing.

### Transcript archive UI

**New frontend page:** `frontend/src/pages/VoicePage.tsx`

This page:
- Lists all call logs for the workspace (paginated, most recent first).
- Has a search bar that filters by `from_number`, `to_number`, and transcript text (client-side filter on loaded data for MVP; backend full-text search is a post-8 item).
- Each row shows: agent name, direction, phone numbers, duration, status badge, compliance flags, and a "View" button that opens the existing `CallLogDrawer`.
- The page is reachable from the `AppShell` nav.

**New frontend component:** `frontend/src/components/voice/TranscriptSearchBar.tsx` — a controlled input that filters the call log list.

**Files changed (frontend):**
- `frontend/src/pages/VoicePage.tsx` — new file.
- `frontend/src/components/voice/TranscriptSearchBar.tsx` — new file.
- `frontend/src/components/layout/AppShell.tsx` — add "Voice" nav link.
- `frontend/src/App.tsx` — add `/voice` route.

---

## 8d — Live Handoff & Escalation

### Warm handoff

`TwilioProvider.transfer_to_human()` already exists. The missing piece is triggering it from the call engine when either:
(a) Claude decides to transfer (tool call), or
(b) Sentiment detection triggers it.

**Design — Claude-triggered transfer:**

Add a synthetic tool to the agent's tool list during voice calls:

```python
TRANSFER_TOOL = {
    "name": "transfer_to_human",
    "description": "Transfer this call to a human agent when you cannot resolve the issue, the caller is distressed, or they request a human.",
    "input_schema": {
        "type": "object",
        "properties": {
            "reason": {"type": "string"},
        },
        "required": ["reason"],
    },
}
```

This tool is injected into `api_kwargs["tools"]` in `call_engine.py` regardless of the agent's configured connectors — it's always available on voice calls.

When Claude uses this tool, `call_engine.py`:
1. Loads the workspace's escalation number from `VoiceAgent.escalation_number` (new field).
2. Calls `get_telephony_provider().transfer_to_human(call_sid, escalation_number, context)` where `context` is a 2-sentence summary of the transcript so far.
3. Sets `call_log.status = CallStatus.TRANSFERRED`.
4. Increments `voice_agent.total_escalations`.
5. Breaks out of the call loop.

**New field on `VoiceAgent`:**
```
escalation_number   VARCHAR(30) NULL   -- E.164, human agent to transfer to
```

Migration `0009_escalation.py`.

### Sentiment / escalation detection

A lightweight inline check runs after each final human transcript segment, before feeding to Claude:

```python
ESCALATION_KEYWORDS = [
    "speak to a human", "real person", "manager", "supervisor",
    "this is unacceptable", "lawsuit", "cancel", "i'm angry", "furious",
]

def _detect_escalation(text: str) -> bool:
    lower = text.lower()
    return any(kw in lower for kw in ESCALATION_KEYWORDS)
```

If triggered:
1. A `TraceEvent(type="escalation_alert")` is appended.
2. `voice_agent.total_escalations` is incremented.
3. The escalation is logged in the audit log.
4. If `voice_agent.escalation_number` is set, the transfer tool is invoked automatically (same path as Claude-triggered transfer).
5. If no `escalation_number` is set, the flag is recorded but the call continues — Claude is notified via a system message injected into `messages`: `"[SYSTEM: Escalation signal detected. Offer to transfer to a human if possible.]"`

**Files changed:**
- `backend/app/models/voice_agent.py` — add `escalation_number` to `VoiceAgent`.
- `backend/alembic/versions/0009_escalation.py` — add the column.
- `backend/app/voice/call_engine.py` — inject `TRANSFER_TOOL`, add `_detect_escalation()`, handle transfer tool call, handle auto-escalation.
- `backend/app/schemas/voice.py` — add `escalation_number` to `VoiceAgentCreate`, `VoiceAgentUpdate`, `VoiceAgentOut`.
- `backend/app/services/voice_service.py` — update CRUD to handle `escalation_number`.

### Handoff context passed to human

When `transfer_to_human()` is called, the `context_twiml` parameter carries a brief read-out:

```python
summary = f"Transferring a call from {call_log.from_number}. " \
          f"The caller said: {transcript[-3:] last human utterance}. " \
          f"Reason: {reason}."
```

Twilio reads this to the receiving human agent before bridging the call, so they have context without the caller repeating themselves. This is handled inside `_execute_transfer()` in `call_engine.py`.

---

## 8e — Board & Concurrency Integration

### VoiceAgentCard frontend component

A new card component `frontend/src/components/voice/VoiceAgentCard.tsx` that renders in the same Kanban lanes as `AgentCard`, but with voice-specific metrics instead of run count / cost.

**Props:**
```typescript
interface VoiceAgentCardProps {
  agent: AgentOut           // base agent from existing agentApi
  voiceAgent: VoiceAgentOut // voice extension from voiceApi
  onOpenDetail: (agent: AgentOut) => void
  isDragging?: boolean
}
```

**Bottom row metrics (replaces run count / cost):**
- Phone icon + phone number (or "No number")
- Call volume: `{voiceAgent.total_calls} calls`
- Avg duration: `{formatDuration(Math.round(voiceAgent.total_call_seconds / Math.max(voiceAgent.total_calls, 1)))}`
- Escalation rate: `{voiceAgent.total_escalations}/{voiceAgent.total_calls}` escalations (shown in amber if > 0)
- `CallStatusBadge` showing current status (idle unless a live call is in progress — derived from a separate live-call query or polling)

The drag handle, name, goal, failure alert, and DnD wiring are identical to `AgentCard`.

### Board integration

**Problem:** `KanbanBoard` currently receives `agents: AgentOut[]` and renders all of them with `AgentCard`. Voice agents need to render as `VoiceAgentCard` instead, but the board doesn't know which agents are voice agents.

**Design:** `KanbanBoard` receives an additional prop `voiceAgentsByAgentId: Record<string, VoiceAgentOut>`. For each agent in a lane, it checks `voiceAgentsByAgentId[agent.id]` — if present, renders `VoiceAgentCard`; otherwise renders `AgentCard`.

The drag-and-drop logic is unchanged — both card types expose the same `useSortable` wiring and the status update API call is the same (`agentApi.updateStatus`).

**BoardPage** (`pages/BoardPage.tsx`) fetches both `agentApi.list()` and `voiceApi.listVoiceAgents()` in parallel, builds the `voiceAgentsByAgentId` map, and passes it down.

**Files changed (frontend):**
- `frontend/src/components/voice/VoiceAgentCard.tsx` — new file.
- `frontend/src/components/board/KanbanBoard.tsx` — add `voiceAgentsByAgentId` prop, conditional render.
- `frontend/src/components/board/KanbanLane.tsx` — pass `voiceAgentsByAgentId` through to cards.
- `frontend/src/pages/BoardPage.tsx` — add parallel voice agents fetch.

### Concurrency caps — already implemented

Per-agent cap (`voice_agent.max_concurrent_calls`) and per-workspace cap (`settings.MAX_CONCURRENT_CALLS_PER_WORKSPACE`) are both enforced in `voice_service.initiate_outbound_call()`. No new backend work needed.

For completeness, the `VoiceAgentUpdate` schema and service already support patching `max_concurrent_calls`. The board detail drawer (8e UI polish) should surface this field — handled in the `VoiceAgentCard` click detail, which opens `AgentDetailDrawer` with an additional "Voice Settings" section.

**No new backend changes needed for 8e concurrency.** It's already there.

---

## File change summary by sub-phase

### 8a
| File | Change |
|------|--------|
| `backend/app/api/v1/endpoints/voice.py` | Add `POST /inbound/{voice_agent_id}` route; add Twilio signature validation dependency to all webhook routes |
| `backend/app/api/deps.py` | Add `validate_twilio_signature` dependency |

### 8b
| File | Change |
|------|--------|
| `backend/app/models/compliance.py` | New — `ConsentRecord`, `DncEntry`, `CallingHoursRule` ORM models |
| `backend/alembic/versions/0007_compliance.py` | New — create 3 compliance tables |
| `backend/app/schemas/compliance.py` | New — Pydantic schemas |
| `backend/app/services/compliance_service.py` | New — CRUD + `check_outbound_allowed()` |
| `backend/app/api/v1/endpoints/compliance.py` | New — REST endpoints |
| `backend/app/api/v1/router.py` | Register compliance router |
| `backend/app/services/voice_service.py` | Insert 3 compliance checks in `initiate_outbound_call` |
| `backend/app/voice/call_engine.py` | Extract `_build_opening()`, enforce disclosure prefix, set `ai_disclosed` early |

### 8c
| File | Change |
|------|--------|
| `backend/app/voice/redaction.py` | New — `redact_transcript()` |
| `backend/app/voice/call_engine.py` | Call redaction before commit |
| `backend/app/models/voice_agent.py` | Add `recording_sid`, `recording_url` to `CallLog` |
| `backend/alembic/versions/0008_call_recording.py` | New — add recording columns |
| `backend/app/voice/providers/twilio_provider.py` | Add recording params to `place_outbound_call` |
| `backend/app/api/v1/endpoints/voice.py` | Add `POST /recording-status` webhook |
| `backend/app/schemas/voice.py` | Add recording fields to `CallLogOut` |
| `frontend/src/pages/VoicePage.tsx` | New — transcript archive page |
| `frontend/src/components/voice/TranscriptSearchBar.tsx` | New — search input |
| `frontend/src/components/layout/AppShell.tsx` | Add Voice nav link |
| `frontend/src/App.tsx` | Add `/voice` route |

### 8d
| File | Change |
|------|--------|
| `backend/app/models/voice_agent.py` | Add `escalation_number` to `VoiceAgent` |
| `backend/alembic/versions/0009_escalation.py` | New — add escalation_number column |
| `backend/app/voice/call_engine.py` | Inject transfer tool, `_detect_escalation()`, transfer handling |
| `backend/app/schemas/voice.py` | Add `escalation_number` to all voice agent schemas |
| `backend/app/services/voice_service.py` | Handle `escalation_number` in CRUD |

### 8e
| File | Change |
|------|--------|
| `frontend/src/components/voice/VoiceAgentCard.tsx` | New — voice-specific Kanban card |
| `frontend/src/components/board/KanbanBoard.tsx` | Add `voiceAgentsByAgentId` prop + conditional render |
| `frontend/src/components/board/KanbanLane.tsx` | Pass voice agents map through |
| `frontend/src/pages/BoardPage.tsx` | Parallel fetch of voice agents, build map |

---

## Locked decisions

1. **Compliance bypass:** `skip_compliance_checks` boolean on `VoiceAgent`. Structurally impossible to be `true` when `agent.status = live` — enforced by a service-layer guard (raises HTTP 422) AND a DB check constraint. Every use written to audit log.

2. **Calling hours:** Store timezone string (e.g. `"America/Los_Angeles"`) + local `start_time` / `end_time` per rule. Convert to callee's local time at enforcement using Python `zoneinfo` (stdlib, no new dependency). Do NOT store UTC-only.

3. **Recording storage:** Store Twilio HTTPS URL pointer only. Twilio storage is already encrypted at rest with signed-URL access. No download/re-encrypt/self-host pipeline in Phase 8.

4. **Escalation alerts (no escalation_number):** Send real-time email to workspace owner via the existing Gmail connector from Phase 2, in addition to the trace log entry. No WebSocket infra.

5. **Live call status on board:** Poll every 5 seconds while a voice agent's base agent status is `live`. No WebSocket push in Phase 8.
