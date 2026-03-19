# Story 5.3: MPN Assignment with Preview Dialog

Status: review

## Story

As a designer,
I want to assign an MPN from search results or manually enter one, with a clear preview of all field changes before confirming,
so that I know exactly what will be written and can catch mistakes before they happen.

## Acceptance Criteria

1. **Assign from Search Result** (FR21, FR23)
   **Given** a search result is selected AND a target component is selected in the verification table
   **When** the designer clicks "Assign" (from detail panel, context menu, or double-click on search result)
   **Then** an assign dialog opens showing plain-language confirmation: "Add MPN: [value] to [reference]?"
   **And** the dialog previews ALL field changes: MPN, Manufacturer, Description, and any supplier P/Ns
   **And** the designer can confirm or cancel

2. **Manual Entry for Missing Part** (FR22)
   **Given** the designer needs to assign a part not found in any database
   **When** they choose "Manual Entry" in the assign dialog
   **Then** editable fields appear for MPN, Manufacturer, and Description
   **And** the preview updates to show the manually-entered values before confirmation

3. **Write-Back in Connected Mode** (FR13)
   **Given** the designer confirms the assignment in connected mode
   **When** the write-back executes
   **Then** fields are written to the KiCad component via IPC API
   **And** the verification table row updates immediately (green status)

4. **Write-Back in Standalone Mode**
   **Given** the designer confirms assignment in standalone mode (no KiCad connection)
   **When** the write-back executes
   **Then** fields are stored in the in-memory `BoardComponent` for BOM export
   **And** the verification table row updates immediately (green status)

## Tasks / Subtasks

- [x] Task 1: Add Manual Entry mode to AssignDialog (AC: #2)
  - [x] 1.1 Add a "Manual Entry" button/toggle to AssignDialog that switches to editable mode
  - [x] 1.2 In manual mode, replace the read-only New Value column with QLineEdit fields for MPN, Manufacturer, Description
  - [x] 1.3 Preview table updates live as user types in manual entry fields
  - [x] 1.4 Assign button only enabled when MPN field is non-empty (MPN is the minimum required field)
  - [x] 1.5 Support opening AssignDialog in manual-entry mode directly (no PartResult required)

- [x] Task 2: Add standalone AssignDialog entry point (AC: #2)
  - [x] 2.1 Add a "Manual Assign" action to the verification panel context menu and/or toolbar
  - [x] 2.2 This action opens AssignDialog in manual-entry mode for the selected component
  - [x] 2.3 No search result required — designer enters MPN/Manufacturer/Description directly

- [x] Task 3: Enable assignment in standalone mode (AC: #4)
  - [x] 3.1 Remove the "Not Connected" guard in `_on_part_selected` that blocks assignment when disconnected
  - [x] 3.2 When not connected, write fields to `BoardComponent` in-memory only (update `comp.mpn`, `comp.extra_fields`)
  - [x] 3.3 When connected, use existing `KiCadBridge.write_field()` as current code does
  - [x] 3.4 Update verify panel status to GREEN in both modes after successful assignment

- [x] Task 4: Refactor AssignDialog constructor for dual mode (AC: #1, #2)
  - [x] 4.1 Make `part` parameter optional: `AssignDialog(component, part=None, parent=None)`
  - [x] 4.2 If `part` is provided: current behavior (read-only preview from PartResult)
  - [x] 4.3 If `part` is None: start in manual entry mode with empty editable fields
  - [x] 4.4 Add toggle to switch between search-result mode and manual-entry mode when both are available

- [x] Task 5: Write tests (AC: #1–#4)
  - [x] 5.1 Test AssignDialog with PartResult — fields_to_write populated correctly (existing behavior)
  - [x] 5.2 Test AssignDialog in manual mode — editable fields, fields_to_write from user input
  - [x] 5.3 Test AssignDialog manual mode with empty MPN — Assign button disabled
  - [x] 5.4 Test standalone assignment — BoardComponent updated in-memory, verify panel goes GREEN
  - [x] 5.5 Test connected assignment — write_field called, verify panel goes GREEN
  - [x] 5.6 Test mismatch warnings still display in both modes

## Dev Notes

### What Already Exists — Extend, Don't Reinvent

The assign dialog and write-back flow are **already implemented and working**. This story extends them with two new capabilities:

1. **Manual entry mode** — the AssignDialog currently requires a `PartResult`. Add support for a `part=None` path where the user types MPN/Manufacturer/Description directly.

2. **Standalone mode assignment** — the current `_on_part_selected` in `main_window.py:743` blocks with a "Not Connected" dialog when KiCad is not running. Remove this gate. In standalone mode, write to `BoardComponent` in-memory only (no bridge calls). The BOM export engine already reads from `BoardComponent` objects, so this works end-to-end.

### Key Files to Modify

| File | Change |
|------|--------|
| `src/kipart_search/gui/assign_dialog.py` | Add manual entry mode: optional `part` param, editable QLineEdit fields, toggle button |
| `src/kipart_search/gui/main_window.py` | Remove "Not Connected" guard in `_on_part_selected` (~line 743). Add standalone write path. Add "Manual Assign" action. |
| `src/kipart_search/gui/verify_panel.py` | Add "Manual Assign" context menu item (optional — if not already present) |
| `tests/gui/test_assign_dialog.py` | New test file for AssignDialog unit tests |
| `tests/gui/test_kicad_bridge.py` | Add tests for standalone assignment path |

### Existing Code Patterns to Follow

**AssignDialog** (`gui/assign_dialog.py`):
- Constructor: `__init__(self, component: BoardComponent, part: PartResult, parent=None)`
- `ASSIGNABLE_FIELDS` list defines the 4 fields: MPN, Manufacturer, Datasheet, Description
- `_check_mismatches()` generates warnings for type/package mismatch — must work in manual mode too (skip if no category/package data)
- `fields_to_write` property returns `dict[str, str]` — this is the contract consumed by `main_window.py`
- Preview table: 4 columns (Field, Current Value, New Value, Action) with color-coded rows

**Main Window assignment flow** (`gui/main_window.py:737-789`):
```
_on_part_selected(row) or _on_detail_assign()
  → AssignDialog(component, part)
  → dialog.exec() → if accepted:
      → dialog.fields_to_write → {field: value}
      → bridge.write_field(ref, field, value) per field
      → update comp.mpn, comp.extra_fields in-memory
      → verify_panel.update_component_status(ref, GREEN)
      → clear assign target
```

**Signal chain for context menu** (`results_table.py`):
- Right-click context menu already has "Assign to [reference]" action → emits `part_selected(row)`

**KiCadBridge.write_field** (`gui/kicad_bridge.py:183`):
- Safety: refuses to overwrite non-empty fields (returns False)
- Searches predefined fields (datasheet) and custom fields by name
- Returns `bool` for success/failure per field

### Architecture Constraints

1. **No direct file manipulation** — never modify `.kicad_sch` or `.kicad_pcb` files. Use `KiCadBridge.write_field()` for connected mode, in-memory `BoardComponent` for standalone.

2. **Add-never-overwrite** — the existing `write_field` already enforces this. The AssignDialog already shows "Skip (not empty)" for non-empty fields. Story 5.4 will add explicit overwrite confirmation — do NOT implement overwrite in this story.

3. **Atomic per-component** — each assignment is one component at a time. If a field write fails, other fields should still be written. The existing loop in `_on_part_selected` already handles this.

4. **`fields_to_write` is the contract** — both manual and search-result modes must produce the same `dict[str, str]` output. The main window code should not care which mode produced the fields.

### Manual Entry Mode Design

The manual entry mode should be **lightweight**:
- Add a "Manual Entry" toggle/button that replaces the read-only "New Value" column with QLineEdit widgets
- MPN is the minimum required field — Assign button disabled until MPN is non-empty
- When `part=None`, start directly in manual mode
- When `part` is provided, show the search-result preview with an option to switch to manual entry (for corrections)
- `_check_mismatches()` should gracefully handle no PartResult (skip category check, keep package check if user enters package info)

### Standalone Mode Design

Currently in `main_window.py:743-748`:
```python
if not self._bridge.is_connected:
    QMessageBox.information(self, "Not Connected", "Connect to KiCad first...")
    return
```

Replace with:
```python
# Connected mode: write via bridge
# Standalone mode: write to in-memory BoardComponent only
```

The in-memory write path already exists after the bridge write loop (lines 773-779):
```python
comp = self._assign_target
if comp and "MPN" in fields:
    comp.mpn = fields["MPN"]
if comp:
    for fname, fval in fields.items():
        comp.extra_fields[fname.lower()] = fval
```

This code runs in both modes. The only change is removing the connection gate and conditionally skipping the `bridge.write_field` calls.

### Testing Approach

Follow the pattern from `tests/gui/test_kicad_bridge.py`:
- Mock `kipy` module entirely with `MagicMock`
- Use `pytest-qt` for signal testing
- Test AssignDialog in isolation (construct with `BoardComponent` + `PartResult` or `None`)
- Test `fields_to_write` output for both modes
- Test the standalone assignment path in MainWindow (mock verify_panel, check comp.mpn updated)

### What This Story Does NOT Include

- **Overwrite confirmation** for non-empty fields → Story 5.4
- **Package/type mismatch acknowledgment gate** (proceed-anyway button) → Story 5.4
- **Silent backup before first write** → Story 5.5
- **Undo log** → Story 5.5
- **Batch assignment** (assign to multiple components at once) → not in scope

### Project Structure Notes

- All new code follows existing patterns: `from __future__ import annotations` in every file
- AssignDialog stays in `gui/assign_dialog.py` — no new files except tests
- `BoardComponent` in `core/models.py` is the shared data model — no changes needed
- `ASSIGNABLE_FIELDS` in assign_dialog.py defines the field mapping — extend if adding supplier P/N fields

### References

- [Source: _bmad-output/planning-artifacts/epics.md#Story 5.3] — acceptance criteria and BDD scenarios
- [Source: _bmad-output/planning-artifacts/architecture.md#ADR-08] — write-back strategy (investigate first, IPC API preferred)
- [Source: _bmad-output/planning-artifacts/ux-design-specification.md#Safety & Reversibility] — "add never overwrite", plain-language confirmation
- [Source: _bmad-output/planning-artifacts/ux-design-specification.md#Effortless Interactions] — "Red → assigned in 3 clicks"
- [Source: src/kipart_search/gui/assign_dialog.py] — existing AssignDialog implementation (260 lines)
- [Source: src/kipart_search/gui/main_window.py#_on_part_selected] — existing assignment flow (lines 737-789)
- [Source: src/kipart_search/gui/kicad_bridge.py#write_field] — existing write-back (lines 183-223)

## Change Log

- 2026-03-19: Implemented manual entry mode, standalone assignment, and dual-mode constructor for AssignDialog. Added 28 tests. Refactored main_window assignment flow into `_apply_assignment()`.

## Dev Agent Record

### Agent Model Used

Claude Opus 4.6 (1M context)

### Debug Log References

- Full test suite: 375 passed, 1 pre-existing failure (unrelated size policy test)
- New tests: 28/28 passed in 0.62s

### Completion Notes List

- **Task 4 (Constructor refactor):** Made `part` parameter optional (`part: PartResult | None = None`). When `part=None`, dialog starts in manual entry mode. Added `_manual_mode` flag and `_manual_edits` dict to track QLineEdit widgets.
- **Task 1 (Manual Entry mode):** Added `_populate_manual_table()` with QLineEdit widgets for all 4 ASSIGNABLE_FIELDS. Live preview via `_on_manual_field_changed()` connected to `textChanged` signals. Assign button gated on non-empty MPN. Toggle button switches between modes when PartResult is available.
- **Task 2 (Standalone entry point):** Added `manual_assign_requested` signal to VerifyPanel. Added "Manual Assign" context menu item. Connected signal to new `_on_manual_assign()` method in MainWindow that opens AssignDialog with `part=None`.
- **Task 3 (Standalone mode):** Removed "Not Connected" guard from `_on_part_selected`. Extracted `_apply_assignment()` method that handles both connected (bridge.write_field) and standalone (in-memory only) modes. Both modes update verify panel to GREEN.
- **Task 5 (Tests):** 28 tests across 8 test classes covering: search-result mode, manual mode, validation, standalone assignment, connected assignment, mismatch warnings, mode toggle, and verify panel signal/context menu.

### File List

- `src/kipart_search/gui/assign_dialog.py` — Modified: dual-mode constructor, manual entry table, toggle, validation
- `src/kipart_search/gui/main_window.py` — Modified: removed Not Connected guard, added `_on_manual_assign()`, extracted `_apply_assignment()`, connected manual_assign_requested signal
- `src/kipart_search/gui/verify_panel.py` — Modified: added `manual_assign_requested` signal, added "Manual Assign" context menu item
- `tests/gui/test_assign_dialog.py` — New: 28 tests for AssignDialog and assignment flow
