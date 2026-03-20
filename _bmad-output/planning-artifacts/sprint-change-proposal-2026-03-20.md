# Sprint Change Proposal — 2026-03-20

## Section 1: Issue Summary

**Problem:** Assigning MPN to KiCad components fails with "write refused by bridge" when the component doesn't have a pre-existing MPN or Manufacturer custom field.

**Discovered:** GitHub Issue #1 — user (author) attempted to assign a 1µF 0402 capacitor MPN to C1 after scanning 47 components. Search worked (200 results), but write-back failed for both MPN and Manufacturer fields.

**Root Cause (initial):** `kicad_bridge.py:write_field()` could only modify existing fields. When a field didn't exist on the footprint, the method returned `False` instead of creating the field.

**Root Cause (deeper):** Custom fields like MPN and Manufacturer are properties of **schematic symbols**, not PCB footprints. The KiCad 9 IPC API only exposes the PCB editor — there is no schematic API to create new symbol fields. The `kicad-python` (kipy) library confirms: no `SchematicEditor` class exists, only `Board`. KiCad 10 is expected to add schematic editor IPC API support.

**Evidence:**
- Error log: "Failed to write 2 field(s) to C1: MPN: write refused by bridge, Manufacturer: write refused by bridge"
- Result: "No fields written to C1 — skipping in-memory update"
- Attempted fix via `fp.definition.add_item()` + `board.update_items()` — KiCad silently ignores new sub-items on footprints

## Section 2: Impact Analysis

**Epic Impact:** Epic 5 (Safe KiCad Write-Back & Assignment) — the write-back to KiCad is deferred to KiCad 10. Assignment works via local state for BOM export.

**Story Impact:**
- Story 5.3 (MPN Assignment): Works — assigns locally, table goes green, BOM export includes the data
- Story 5.4 (Write-Back Safety Guards): Unchanged — guards still apply for fields that already exist
- No new stories needed — ADR-08 already planned for this fallback

**Artifact Conflicts:**
- **ADR-08** predicted this outcome: "If not: defer write-back to Phase 2 (wait for API expansion), and Phase 1 assigns to local state only (BOM export still works)."
- No PRD, Architecture, or UX spec changes needed — the scope clarification was already documented

**Technical Impact:** Changes to 2 files, no API contract changes.

## Section 3: Recommended Approach

**Selected: Direct Adjustment with Scope Clarification (per ADR-08)**

The write-back to KiCad symbol fields is deferred until KiCad 10 adds schematic IPC API support. The assign workflow works end-to-end via local state: scan → search → assign (local) → export BOM.

**Rationale:**
- KiCad 9 IPC API limitation is confirmed — cannot create symbol fields from the PCB editor
- ADR-08 explicitly planned for this fallback scenario
- The core deliverable (BOM export) works without KiCad write-back
- No workarounds (direct .kicad_sch file editing) — project rules forbid it, and it would be fragile

**Effort:** Low (changes already applied and tested)
**Risk:** Low (well-understood limitation, documented fallback)
**Timeline Impact:** None — BOM export workflow is unaffected

## Section 4: Detailed Change Proposals

### Change 1: `kicad_bridge.py:write_field()` — Informative log for missing fields

**File:** `src/kipart_search/gui/kicad_bridge.py`

When a field doesn't exist on the footprint, log the KiCad 9 API limitation clearly and return `False` so the caller falls back to local-state assignment.

```python
# Field doesn't exist on footprint — KiCad stores custom fields
# on schematic symbols, not PCB footprints.  The IPC API (KiCad 9)
# only exposes the PCB editor, so we cannot create new symbol fields.
# Return False so the caller can fall back to local-state assignment.
log.info(
    "Field '%s' not found on %s — schematic field creation "
    "not supported by KiCad 9 IPC API", field_name, reference,
)
return False
```

### Change 2: `main_window.py` — Local-state fallback for assign

When the bridge can't write fields (because they don't exist in KiCad), the assign handler now:
- Tracks refused writes as `local_only` (not `failed`)
- Updates in-memory component state so the table goes green
- Logs: "Assigned N field(s) to REF locally — KiCad 9 IPC API cannot create new symbol fields. BOM export will include them."
- Stores local assignments in `_local_assignments` dict for persistence across re-verify

### Change 3: `main_window.py` — Preserve local assignments across re-verify

After a re-scan reads fresh data from KiCad (which doesn't have the locally-assigned fields), local assignments are merged back into the component data. Log: "Restored N local MPN assignment(s) — not yet in KiCad".

### Change 4: `main_window.py` — Health % in log

Log message after assignment now includes BOM health percentage: "C6 status updated to Verified — BOM health: 2%"

### Change 5: `main_window.py` — Push to KiCad tooltip

Button remains disabled with updated tooltip: "KiCad 9 IPC API does not support creating symbol fields. Expected in KiCad 10."

## Section 5: Implementation Handoff

**Change Scope:** Minor — all changes applied and tested.

**Status:** Complete. Remaining:
1. Commit changes
2. Close GitHub Issue #1 with explanation of KiCad 9 limitation and local-state workaround

**Success Criteria (all verified):**
- Assigning MPN to a component without pre-existing field → table goes green, health updates
- Re-verify preserves local assignments → "Restored 1 local MPN assignment(s)"
- BOM export includes locally-assigned MPNs
- Push to KiCad button disabled with informative tooltip
- Log shows health percentage after each assignment
