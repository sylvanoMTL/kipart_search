# Sprint Change Proposal — 2026-03-20

## Section 1: Issue Summary

**Problem:** Assigning MPN to KiCad components fails with "write refused by bridge" when the component doesn't have a pre-existing MPN or Manufacturer custom field.

**Discovered:** GitHub Issue #1 — user (author) attempted to assign a 1µF 0402 capacitor MPN to C1 after scanning 47 components. Search worked (200 results), but write-back failed for both MPN and Manufacturer fields.

**Root Cause (initial):** `kicad_bridge.py:write_field()` could only modify existing fields. When a field didn't exist on the footprint, the method returned `False` instead of creating the field.

**Root Cause (deeper — field creation attempt):** Custom fields like MPN and Manufacturer are properties of **schematic symbols**, not PCB footprints. The KiCad 9 IPC API only exposes the PCB editor — there is no schematic API to create new symbol fields. Attempted to create fields via `fp.definition.add_item()` + `board.update_items()` but KiCad silently ignores new sub-items on footprints.

**Root Cause (final — update_items destructive):** Even for **pre-existing** custom fields (manually added to schematic symbols and synced via "Update PCB from Schematic"), calling `board.update_items(fp)` **strips ALL custom fields** from the footprint definition. This is destructive:
- Writing to the MPN field via `update_items()` returns `True` and updates the local Python object
- But KiCad drops the custom fields on the round-trip — re-reading the footprint shows they're gone
- Even writing to a built-in field (like Datasheet) via `update_items()` destroys any custom fields that were synced from the schematic
- The workaround of pre-creating fields in the schematic does NOT work because `update_items()` destroys them

**Evidence:**
- Error log: "Failed to write 2 field(s) to C1: MPN: write refused by bridge, Manufacturer: write refused by bridge"
- Manual test (`tests/manual_tests/test_write_field.py`): confirmed `update_items()` strips custom fields
- KiCad developer documentation confirms: "In KiCad 9.0, the IPC API and the new IPC plugin system are only implemented in the PCB editor, due to development time constraints. In the future, the IPC API will be expanded to support the schematic editor, library editors, and other parts of KiCad."
- Source: https://dev-docs.kicad.org/en/apis-and-binding/ipc-api/for-addon-developers/

## Section 2: Impact Analysis

**Epic Impact:** Epic 5 (Safe KiCad Write-Back & Assignment) — ALL write-back to KiCad is disabled in KiCad 9 to prevent destructive field stripping. Assignment works via local state for BOM export.

**Story Impact:**
- Story 5.3 (MPN Assignment): Works — assigns locally, table goes green, BOM export includes the data
- Story 5.4 (Write-Back Safety Guards): write_field() disabled entirely to prevent data destruction; guards preserved in commented code for KiCad 10
- No new stories needed — ADR-08 already planned for this fallback

**Artifact Conflicts:**
- **ADR-08** predicted this outcome: "If not: defer write-back to Phase 2 (wait for API expansion), and Phase 1 assigns to local state only (BOM export still works)."
- No PRD, Architecture, or UX spec changes needed — the scope clarification was already documented

**Technical Impact:** Changes to 2 source files, 1 test file added. No API contract changes.

## Section 3: Recommended Approach

**Selected: Direct Adjustment with Scope Clarification (per ADR-08)**

ALL write-back via IPC API is disabled in KiCad 9 — not just field creation, but also field updates, because `update_items()` destroys custom fields. The assign workflow works end-to-end via local state: scan → search → assign (local) → export BOM.

**Rationale:**
- KiCad 9 IPC API limitation is confirmed and documented
- `update_items()` is destructive for custom fields — calling it risks destroying user data
- ADR-08 explicitly planned for this fallback scenario
- The core deliverable (BOM export) works without KiCad write-back
- Original write logic preserved as commented code for re-enabling in KiCad 10

**Effort:** Low (changes already applied and tested)
**Risk:** Low (well-understood limitation, documented fallback)
**Timeline Impact:** None — BOM export workflow is unaffected

## Section 4: Detailed Change Proposals

### Change 1: `kicad_bridge.py:write_field()` — Disabled with documentation

**File:** `src/kipart_search/gui/kicad_bridge.py`

`write_field()` now returns `False` immediately with an informative log message. The original write logic is preserved as commented code with detailed documentation explaining:
- Why it's disabled (update_items strips custom fields)
- When to re-enable (KiCad 10 schematic API)
- Link to official KiCad documentation
- Reference to the manual test script

### Change 2: `main_window.py` — Local-state fallback for assign

When the bridge can't write fields, the assign handler now:
- Tracks refused writes as `local_only` (not `failed`)
- Updates in-memory component state so the table goes green
- Logs: "Assigned N field(s) to REF locally — KiCad 9 IPC API cannot create new symbol fields. BOM export will include them."
- Stores local assignments in `_local_assignments` dict for persistence across re-verify

### Change 3: `main_window.py` — Preserve local assignments across re-verify

After a re-scan reads fresh data from KiCad (which doesn't have the locally-assigned fields), local assignments are merged back into the component data. Log: "Restored N local MPN assignment(s) — not yet in KiCad".

### Change 4: `main_window.py` — Health % in log

Log message after assignment now includes BOM health percentage: "C6 status updated to Verified — BOM health: 2%"

### Change 5: `main_window.py` — Push to KiCad info dialog

Button is always enabled but shows an informational dialog explaining the KiCad 9 limitation. Tooltip: "KiCad 9 IPC API does not support creating symbol fields. Expected in KiCad 10."

### Change 6: `tests/manual_tests/test_write_field.py` — Regression test

Manual test script that:
- Connects to KiCad, reads C6 fields
- Attempts to write MPN/Manufacturer via `update_items()`
- Verifies that custom fields are destroyed on the round-trip
- Documents the exact behavior for future KiCad versions
- When KiCad 10 is released, re-run this test — if fields survive, re-enable `write_field()`

## Section 5: Implementation Handoff

**Change Scope:** Minor — all changes applied and tested.

**Status:** Complete. Remaining:
1. Commit changes
2. Close GitHub Issue #1 with explanation of KiCad 9 limitation

**KiCad 10 Re-enablement Checklist:**
When KiCad 10 is available with schematic editor IPC API:
1. Run `tests/manual_tests/test_write_field.py` — check if custom fields survive `update_items()`
2. If PASS: uncomment the write logic in `kicad_bridge.py:write_field()`
3. Update `_on_push_to_kicad()` in `main_window.py` to implement actual push functionality
4. Remove `_local_assignments` fallback (or keep as standalone-mode path)
5. Update the Push to KiCad tooltip

**Success Criteria (all verified):**
- Assigning MPN to a component → table goes green, health updates with %
- Re-verify preserves local assignments → "Restored 1 local MPN assignment(s)"
- BOM export includes locally-assigned MPNs
- Push to KiCad button shows info dialog explaining limitation
- `update_items()` is never called, preventing custom field destruction
- Original write logic preserved for KiCad 10 re-enablement
