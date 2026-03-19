# Story 5.4: Write-Back Safety Guards

Status: review

## Story

As a designer,
I want the tool to prevent accidental overwrites and warn about mismatches,
so that my existing correct data is never silently destroyed and I catch assignment errors early.

## Acceptance Criteria

1. **Overwrite Confirmation for Non-Empty Fields** (FR14)
   **Given** a target component already has a non-empty MPN field
   **When** the designer attempts to assign a different MPN
   **Then** the assign dialog shows an explicit warning: "MPN field already contains [existing value]. Overwrite?"
   **And** separate Overwrite / Cancel buttons are provided (default is Cancel, not Overwrite)

2. **Mismatch Acknowledgment Gate** (FR15)
   **Given** the assigned part has a different package or type than the target component
   **When** the assign dialog opens
   **Then** a mismatch warning is displayed: "Warning: Part package [QFN-24] does not match footprint [SOIC-8]"
   **And** the designer must explicitly acknowledge the mismatch before the Assign button becomes enabled

3. **Atomic Write-Back with Error Isolation** (NFR11, NFR13)
   **Given** a write-back to KiCad fails for one field (e.g. IPC API error)
   **When** the error occurs
   **Then** the failure is logged and the user is notified
   **And** other fields still attempt to write (per-field isolation, not all-or-nothing)
   **And** the failed field remains in its previous state (not partially written)
   **And** no crash or data loss occurs

## Tasks / Subtasks

- [x] Task 1: Allow overwrite of non-empty fields with confirmation (AC: #1)
  - [x] 1.1 In `AssignDialog._populate_part_table()`: change non-empty fields from hard "Skip (not empty)" to "Overwrite?" with an opt-in checkbox or button
  - [x] 1.2 In `AssignDialog._populate_manual_table()`: re-enable QLineEdit for non-empty fields, pre-fill with current value, add overwrite toggle per field
  - [x] 1.3 Non-empty field rows show amber background with "Current: [value]" — unchecked by default (opt-in overwrite)
  - [x] 1.4 When the user checks the overwrite checkbox for a non-empty field, include it in `_write_fields`
  - [x] 1.5 Update `_update_assign_button()`: Assign button enabled when at least one field has a new value (empty or overwrite-checked)
  - [x] 1.6 In `KiCadBridge.write_field()`: add an `allow_overwrite: bool = False` parameter. When True, skip the non-empty check and write anyway. When False, keep current behavior (refuse non-empty).

- [x] Task 2: Mismatch acknowledgment gate (AC: #2)
  - [x] 2.1 When `_check_mismatches()` returns warnings, disable the Assign button initially
  - [x] 2.2 Add a checkbox: "I acknowledge the mismatch warnings above" below the warning banner
  - [x] 2.3 Assign button becomes enabled only when the acknowledgment checkbox is checked AND there are fields to write
  - [x] 2.4 In manual mode (no PartResult), skip mismatch checks entirely (no category/package data available)

- [x] Task 3: Improve write-back error handling (AC: #3)
  - [x] 3.1 In `_apply_assignment()`: wrap each `bridge.write_field()` call in try/except, log per-field success/failure
  - [x] 3.2 After the write loop, if any fields failed: show a `QMessageBox.warning()` listing which fields failed and why
  - [x] 3.3 Only mark the component GREEN if at least MPN was written successfully; otherwise keep amber/red
  - [x] 3.4 On total failure (no fields written), show error and do NOT update in-memory component state

- [x] Task 4: Write tests (AC: #1–#3)
  - [x] 4.1 Test AssignDialog with non-empty MPN: overwrite checkbox unchecked by default, field NOT in `fields_to_write`
  - [x] 4.2 Test AssignDialog with non-empty MPN: check overwrite checkbox, field IS in `fields_to_write`
  - [x] 4.3 Test AssignDialog manual mode with non-empty fields: QLineEdit enabled with overwrite toggle
  - [x] 4.4 Test mismatch warnings: Assign button disabled until acknowledgment checkbox checked
  - [x] 4.5 Test mismatch warnings: no warnings → no acknowledgment checkbox, button enabled normally
  - [x] 4.6 Test `write_field(allow_overwrite=True)` writes to non-empty field
  - [x] 4.7 Test `write_field(allow_overwrite=False)` refuses non-empty field (existing behavior)
  - [x] 4.8 Test `_apply_assignment` with partial failure: some fields written, some failed, correct log + dialog
  - [x] 4.9 Test `_apply_assignment` with total failure: no in-memory update, no GREEN status

## Dev Notes

### What Already Exists — Extend, Don't Reinvent

The assign dialog, mismatch checking, and write-back flow are **already implemented**. This story adds three safety layers on top:

1. **Overwrite opt-in** — currently non-empty fields are hard-skipped with "Skip (not empty)". Change this to an opt-in overwrite with per-field checkbox. The UI already shows current vs new values — just make non-empty rows actionable.

2. **Mismatch gate** — `_check_mismatches()` already detects type and package mismatches and displays warnings. Currently the user can click Assign anyway with no gate. Add a checkbox acknowledgment that must be checked before Assign is enabled.

3. **Error resilience** — `_apply_assignment()` already loops per field. Add try/except per field and a summary dialog on failure.

### Key Files to Modify

| File | Change |
|------|--------|
| `src/kipart_search/gui/assign_dialog.py` | Overwrite checkboxes for non-empty fields, mismatch acknowledgment gate, re-enable QLineEdit for non-empty fields in manual mode |
| `src/kipart_search/gui/main_window.py` | Error handling in `_apply_assignment()`: per-field try/except, failure summary dialog, conditional GREEN status |
| `src/kipart_search/gui/kicad_bridge.py` | Add `allow_overwrite` parameter to `write_field()` |
| `tests/gui/test_assign_dialog.py` | Extend with overwrite and mismatch gate tests |

### Existing Code Patterns to Follow

**AssignDialog** (`gui/assign_dialog.py`):
- `ASSIGNABLE_FIELDS`: list of `(display_name, part_attr, kicad_field)` tuples — 4 fields: MPN, Manufacturer, Datasheet, Description
- `_write_fields: dict[str, str]` — the output contract consumed by `_apply_assignment()`
- `_populate_part_table()`: builds read-only preview rows. Currently skips non-empty fields with "Skip (not empty)" amber row
- `_populate_manual_table()`: builds QLineEdit rows. Currently disables QLineEdit for non-empty fields (`edit.setEnabled(False)`)
- `_check_mismatches()`: module-level function returning `list[str]` warnings. Checks: (1) type mismatch via `_REF_CATEGORY_HINTS`, (2) cross-type match, (3) package/footprint mismatch
- Warning label: HTML with `⚠` prefix, yellow/orange styling, displayed above the table

**Main Window** (`gui/main_window.py:780-818`):
```
_apply_assignment(fields):
  → Connected: loop bridge.write_field(ref, field, value) per field
  → In-memory: update comp.mpn, comp.extra_fields
  → verify_panel.update_component_status(ref, GREEN)
  → clear assign target
```

**KiCadBridge.write_field** (`gui/kicad_bridge.py:183-223`):
- Checks predefined fields (datasheet) and custom fields by name
- Currently refuses non-empty fields (returns False with log warning)
- Returns `bool` for success/failure per field

### Architecture Constraints

1. **No direct file manipulation** — never modify `.kicad_sch` or `.kicad_pcb` files. Use `KiCadBridge.write_field()` for connected mode only.

2. **Default is safe** — overwrite checkboxes are UNCHECKED by default. The user must explicitly opt in to each field overwrite. Default button remains Cancel on any overwrite confirmation.

3. **`fields_to_write` remains the contract** — the dict output must carry enough info for `_apply_assignment()` to know which fields need `allow_overwrite=True`. Consider either: (a) a parallel `_overwrite_fields: set[str]` tracking which fields are overwrites, or (b) the dialog passes `(fields_to_write, overwrite_fields)` tuple. Option (a) with a new property `overwrite_fields` is cleaner.

4. **Mismatch gate is UI-only** — `_check_mismatches()` stays as-is (core-compatible function). The acknowledgment gate is purely in the AssignDialog UI layer.

### Design Details

**Overwrite UI for `_populate_part_table()` (search-result mode):**
- Non-empty field row: amber background, Action column shows QCheckBox "Overwrite"
- When checkbox is checked: row goes green, field added to `_write_fields`, field also added to `_overwrite_fields` set
- When unchecked (default): row stays amber, field excluded from `_write_fields`

**Overwrite UI for `_populate_manual_table()` (manual mode):**
- Non-empty field row: QLineEdit pre-filled with current value, QCheckBox "Overwrite" in action column
- QLineEdit disabled until checkbox is checked
- When checkbox checked: QLineEdit enabled, text goes into `_write_fields` on change, field in `_overwrite_fields`
- When unchecked: QLineEdit disabled, field excluded

**Mismatch acknowledgment:**
- `QCheckBox("I understand and want to proceed")` inserted below the warning label
- Connected to `_update_assign_button()` — if mismatches exist and checkbox unchecked, Assign stays disabled
- Store the checkbox as `self._mismatch_ack_checkbox` for test access
- If no mismatches, no checkbox needed (current behavior)

**`_apply_assignment()` error handling:**
- Change: `bridge.write_field(ref, field, value)` → `bridge.write_field(ref, field, value, allow_overwrite=(field in overwrite_fields))`
- Wrap in try/except per field. Collect `failed_fields: list[tuple[str, str]]` (field_name, error_msg)
- After loop: if failed_fields, show `QMessageBox.warning()` with plain-language list
- Only set GREEN status if MPN was successfully written (or was already present). If MPN write failed, keep current status.

### Previous Story Intelligence (5.3)

- `part` parameter is now optional (`part: PartResult | None = None`)
- `_manual_mode` flag controls which table population method runs
- `_manual_edits: dict[str, QLineEdit]` tracks the QLineEdit widgets by kicad field name
- `_toggle_manual_mode()` switches between modes when both are available
- `_apply_assignment()` was extracted as a shared method for both `_on_part_selected` and `_on_manual_assign`
- `manual_assign_requested` signal on VerifyPanel triggers `_on_manual_assign` in MainWindow
- 28 tests in `tests/gui/test_assign_dialog.py` — extend this file, don't create a new one

### Git Intelligence

Recent commits show the pattern:
- Story 5.3 (4f5aec1): Added manual entry mode, standalone assignment, dual-mode constructor
- Story 5.2 (c000615): Click-to-highlight cross-probe
- Story 5.1 (4ba1f37): KiCad bridge tests and code review fixes
- Testing pattern: pytest with `MagicMock` for kipy, `pytest-qt` for signals
- All tests run via: `.env/Scripts/python.exe -m pytest tests/`

### What This Story Does NOT Include

- **Silent backup before first write** → Story 5.5
- **Undo log (CSV)** → Story 5.5
- **Backup browser / restore** → Story 5.5
- **Batch assignment** (assign to multiple components at once) → not in scope
- **Cancel mid-session / partial write rollback** → Story 5.5 (undo log enables this)

### Project Structure Notes

- All code follows existing patterns: `from __future__ import annotations` in every file
- No new files except test extensions in existing `tests/gui/test_assign_dialog.py`
- `BoardComponent` in `core/models.py` — no changes needed
- `ASSIGNABLE_FIELDS` in assign_dialog.py defines the 4-field mapping — unchanged

### References

- [Source: _bmad-output/planning-artifacts/epics.md#Story 5.4] — acceptance criteria and BDD scenarios
- [Source: _bmad-output/planning-artifacts/prd.md#FR14] — prevent overwriting non-empty fields without explicit confirmation
- [Source: _bmad-output/planning-artifacts/prd.md#FR15] — type/package mismatch warning
- [Source: _bmad-output/planning-artifacts/architecture.md#ADR-08] — write-back strategy, IPC API preferred
- [Source: _bmad-output/planning-artifacts/ux-design-specification.md#Safety & Reversibility] — "add never overwrite" without explicit per-field confirmation, plain-language dialogs
- [Source: src/kipart_search/gui/assign_dialog.py] — existing AssignDialog (395 lines, dual-mode)
- [Source: src/kipart_search/gui/main_window.py#_apply_assignment] — existing write-back flow (lines 780-818)
- [Source: src/kipart_search/gui/kicad_bridge.py#write_field] — existing write-back with non-empty guard (lines 183-223)
- [Source: tests/gui/test_assign_dialog.py] — existing 28 tests to extend

## Dev Agent Record

### Agent Model Used

Claude Opus 4.6 (1M context)

### Debug Log References

No issues encountered during implementation.

### Completion Notes List

- **Task 1 — Overwrite confirmation**: Replaced "Skip (not empty)" with per-field QCheckBox "Overwrite" in both search-result and manual modes. Non-empty fields show amber background. In manual mode, QLineEdit is pre-filled with current value and disabled until overwrite is checked. Added `_overwrite_fields: set[str]` and `overwrite_fields` property for contract between dialog and `_apply_assignment()`. Added `allow_overwrite` parameter to `KiCadBridge.write_field()`.
- **Task 2 — Mismatch gate**: Added `_mismatch_ack_checkbox` ("I understand and want to proceed") below mismatch warning banner. Assign button stays disabled until checkbox is checked. No checkbox when no mismatches. Manual mode (no PartResult) skips mismatch checks entirely.
- **Task 3 — Error handling**: Wrapped each `bridge.write_field()` in try/except with per-field failure tracking. On partial failure, shows `QMessageBox.warning()` listing failed fields. On total failure, skips in-memory update entirely. GREEN status only set when MPN was successfully written.
- **Task 4 — Tests**: Added 19 new tests (47 total, up from 28) covering: overwrite checkbox in both modes (4.1-4.3), mismatch gate (4.4-4.5), `write_field` `allow_overwrite` parameter (4.6-4.7), partial/total failure handling (4.8-4.9). All 395 project tests pass.

### Change Log

- 2026-03-19: Implemented write-back safety guards — overwrite confirmation, mismatch acknowledgment gate, per-field error isolation (Story 5.4)

### File List

- `src/kipart_search/gui/assign_dialog.py` — Modified: added QCheckBox import, `_overwrite_fields` set, `_overwrite_checkboxes` dict, `_mismatch_ack_checkbox`, overwrite toggles in both populate methods, `_on_overwrite_toggled()`, `_on_manual_overwrite_toggled()`, mismatch gate in `_update_assign_button()`, `overwrite_fields` property
- `src/kipart_search/gui/kicad_bridge.py` — Modified: added `allow_overwrite: bool = False` parameter to `write_field()`, conditional non-empty check
- `src/kipart_search/gui/main_window.py` — Modified: `_apply_assignment()` now accepts `overwrite_fields` parameter, per-field try/except, failure tracking, `QMessageBox.warning()` on failure, conditional GREEN status based on MPN write success, total failure guard
- `tests/gui/test_assign_dialog.py` — Modified: 19 new tests added (47 total), updated 3 existing tests for new signatures
