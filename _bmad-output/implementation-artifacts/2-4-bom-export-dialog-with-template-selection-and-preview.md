# Story 2.4: BOM Export Dialog with Template Selection and Preview

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a designer,
I want an export dialog where I select a CM template, preview the output, configure DNP handling, and export the file,
So that I can verify the BOM looks correct before generating the file.

## Acceptance Criteria

1. **Given** the designer clicks "Export BOM" in the toolbar
   **When** the BOM export dialog opens (non-modal, so the user can go back to fix issues)
   **Then** a template selector shows all preset templates (PCBWay, JLCPCB, Newbury) plus any custom templates (UX-DR6)
   **And** selecting a template shows a live preview table with the actual BOM data in the selected column layout and grouping
   **And** a DNP handling toggle lets the user choose "Include marked" or "Exclude entirely"
   **And** a file format selector offers Excel (.xlsx) or CSV (.csv)

2. **Given** the health bar is below 100%
   **When** the export dialog opens
   **Then** a warning banner appears: "X components still missing MPNs" with an option to proceed anyway or go back (FR28)

3. **Given** the user confirms export
   **When** the file is written
   **Then** a success message shows the file path with an "Open File" button
   **And** export completes in < 5 seconds for a 70-component board (NFR4)

4. **Given** no components have been scanned or loaded
   **When** the designer clicks "Export BOM"
   **Then** the button is disabled or shows an informative tooltip explaining a scan is required first

5. **Given** the designer changes the template selector
   **When** a different template is chosen
   **Then** the preview table updates immediately showing the new column layout, grouping, and sample data

6. **Given** the designer toggles DNP handling
   **When** switching between "Include marked" and "Exclude entirely"
   **Then** the preview table updates to show/hide DNP components accordingly

## Tasks / Subtasks

- [x] Task 1: Create `gui/export_dialog.py` with `ExportDialog(QDialog)` (AC: #1, #5, #6)
  - [x] Create non-modal QDialog with title "Export BOM"
  - [x] Add template selector (QComboBox) populated from `PRESET_TEMPLATES` list
  - [x] Add DNP handling toggle (QComboBox: "Include marked" / "Exclude entirely")
  - [x] Add file format selector (QComboBox: "Excel (.xlsx)" / "CSV (.csv)")
  - [x] Add preview table (QTableWidget, read-only) showing live BOM preview
  - [x] Implement `_refresh_preview()` called when template, DNP, or format changes
  - [x] Preview uses `group_components()` from `core/bom_export.py` to show real grouped data

- [x] Task 2: Add health warning banner (AC: #2)
  - [x] Add a QLabel banner at the top of the dialog, styled with amber background
  - [x] Show "X components still missing MPNs — export anyway?" when health < 100%
  - [x] Hide the banner when health is 100%
  - [x] Pass health percentage and missing count to dialog constructor

- [x] Task 3: Implement export action with file path selection (AC: #3)
  - [x] Add "Export" button that opens QFileDialog.getSaveFileName() with appropriate filter
  - [x] Default filename: `BOM.{ext}` based on selected format
  - [x] Call `export_bom(components, template, output_path)` from `core/bom_export.py`
  - [x] On success: show inline success message with file path and "Open File" button
  - [x] On error: show QMessageBox.warning() with error details
  - [x] "Open File" uses `QDesktopServices.openUrl(QUrl.fromLocalFile(path))`

- [x] Task 4: Wire Export BOM toolbar action in `main_window.py` (AC: #1, #4)
  - [x] Connect `_act_export.triggered` to a new `_on_export_bom()` method
  - [x] Enable `_act_export` after a successful scan (in `_on_scan_complete()`)
  - [x] Disable `_act_export` when no components are loaded
  - [x] In `_on_export_bom()`: read components via `verify_panel.get_components()`, compute health %, instantiate and show `ExportDialog`
  - [x] Add "Export BOM..." to the File menu (after Scan Project)

- [x] Task 5: Add public accessor for components on VerifyPanel (AC: #4)
  - [x] Add `get_components() -> list[BoardComponent]` method to `VerifyPanel`
  - [x] Add `get_health_percentage() -> int` method to `VerifyPanel`
  - [x] Add `get_missing_mpn_count() -> int` method to `VerifyPanel`
  - [x] These avoid reaching into private `_components` / `_mpn_statuses` from main_window

- [x] Task 6: Write tests (AC: #1-#6)
  - [x] Test ExportDialog instantiation with mock components and templates
  - [x] Test preview table updates when template selection changes
  - [x] Test warning banner visibility based on health percentage
  - [x] Test export button triggers file dialog (mock QFileDialog)
  - [x] Test that Export BOM action is disabled before scan and enabled after
  - [x] Follow the `pytest.importorskip("PySide6")` pattern from `tests/test_health_bar.py`

## Dev Notes

### Architecture Compliance

- **Core/GUI separation**: The export dialog (`gui/export_dialog.py`) imports from `core/bom_export.py` but adds zero logic to core. The export engine already exists and is fully tested.
- **ADR-02**: BOM templates are declarative dataclasses — the dialog reads them, never modifies them.
- **ADR-07**: The dialog is a standalone QDialog (non-modal), NOT a QDockWidget panel. It opens from the toolbar and can coexist with the main window.
- **No nested dialogs**: Per UX spec, if sub-configuration is needed it goes inline in the dialog, not in a nested dialog.

### Existing Code to Reuse — DO NOT REINVENT

- **`core/bom_export.py`**: `export_bom()`, `_group_components()`, `_write_xlsx()`, `_write_csv()`, `PRESET_TEMPLATES`, `BOMTemplate`, `BOMColumn` — all exist and are tested with 133+ test cases. Do NOT duplicate grouping logic or template definitions.
- **`gui/assign_dialog.py`**: Reference for QDialog patterns in this project — constructor takes data objects, uses QVBoxLayout, QTableWidget for preview, QPushButton for actions. Follow the same style.
- **`gui/download_dialog.py`**: Reference for non-blocking dialog patterns.
- **`gui/verify_panel.py`**: `_components`, `_mpn_statuses`, health bar — source of component data for export. Add public getters, don't access privates from main_window.

### ExportDialog Constructor Signature

```python
class ExportDialog(QDialog):
    def __init__(
        self,
        components: list[BoardComponent],
        health_pct: int,
        missing_count: int,
        parent: QWidget | None = None,
    ) -> None:
```

The dialog receives components and health data — it does NOT reach back into verify_panel.

### Preview Table Implementation

The preview should call `_group_components()` from `core/bom_export.py` to get the grouped rows, then display them using the selected template's column definitions. This ensures the preview matches exactly what the export will produce.

**Important**: `_group_components()` is currently private (underscore prefix). Either:
1. Make it public by removing the underscore (preferred — it's useful outside the module)
2. Or duplicate the grouping in the dialog (NOT preferred — violates DRY)

Recommend option 1: rename `_group_components` to `group_components` in `core/bom_export.py` and update the one internal call site.

### DNP Handling

The `BOMTemplate.dnp_handling` field exists but is not currently used by `export_bom()` — DNP filtering is not yet implemented in the engine. For this story:
- The dialog shows the DNP toggle per the UX spec
- Pass the selected DNP value when calling `export_bom()`
- If the engine doesn't filter yet, add minimal DNP filtering in `_group_components()`: check `BoardComponent` for a DNP marker field and exclude if `dnp_handling == "exclude"`
- Check how DNP is represented in `BoardComponent` — likely `extra_fields.get("dnp")` or a dedicated attribute

### File Format Handling

The template has a default `file_format` but the user can override it in the dialog. When calling `export_bom()`, create a copy of the template with the user's chosen format:

```python
from dataclasses import replace
export_template = replace(selected_template, file_format=chosen_format, dnp_handling=chosen_dnp)
```

### Wiring in main_window.py

Current state (lines 207-210):
```python
self._act_export = QAction("Export BOM", self)
self._act_export.setEnabled(False)
self._act_export.setToolTip("Export BOM (not yet implemented)")
self.toolbar.addAction(self._act_export)
```

Change to:
1. Connect: `self._act_export.triggered.connect(self._on_export_bom)`
2. Update tooltip: `"Export BOM to Excel or CSV"`
3. Enable in `_on_scan_complete()`: `self._act_export.setEnabled(True)`
4. Add File menu item after the Scan Project action

### Non-Modal Dialog Pattern

Per UX-DR6, the export dialog is **non-modal** so the user can go back to the dashboard to fix issues without closing:

```python
dialog = ExportDialog(components, health_pct, missing_count, parent=self)
dialog.show()  # NOT dialog.exec() — non-modal
```

Store a reference to prevent garbage collection: `self._export_dialog = dialog`

### Warning Banner Styling

Use a QLabel with amber background matching the project's color scheme:
```python
self._warning_banner = QLabel()
self._warning_banner.setStyleSheet(
    "background-color: #FFEBB4; padding: 8px; border-radius: 4px;"
)
```

Use `#FFEBB4` (amber) from the existing `COLORS` dict in verify_panel.py — same palette.

### Success Message with "Open File"

After successful export, replace the export button area with:
- Success text: "Exported to: /path/to/file.xlsx"
- "Open File" button using `QDesktopServices.openUrl()`
- "Close" button

### What This Story Does NOT Include

- **No custom template editor** — custom templates are a future story. Only preset templates are shown.
- **No "New Template" button** — future scope.
- **No batch export** (multiple templates at once) — export one template at a time.
- **No auto-save** path memory — user picks path each time (QFileDialog remembers last dir natively).
- **No changes to `core/bom_export.py` logic** beyond making `_group_components` public and minimal DNP filtering.
- **No Push to KiCad** integration — that's Epic 5.

### Project Structure Notes

- **New file**: `src/kipart_search/gui/export_dialog.py` — the export dialog widget
- **Modified**: `src/kipart_search/gui/main_window.py` — wire Export BOM action, enable/disable
- **Modified**: `src/kipart_search/gui/verify_panel.py` — add public getters for components/health
- **Modified**: `src/kipart_search/core/bom_export.py` — make `_group_components` public (rename only)
- **New file**: `tests/test_export_dialog.py` — GUI tests following test_health_bar.py pattern
- Alignment: follows QDialog pattern from `assign_dialog.py`, uses existing `core/bom_export.py` engine

### Previous Story Intelligence (Story 2.3)

Key learnings:
- GUI tests work without `pytest-qt` using `pytest.importorskip("PySide6")` pattern — follow this for export dialog tests
- All 151 tests pass as of last commit (`cf1e81a`). Test suite covers core + health bar GUI tests.
- `BoardComponent.extra_fields` is `dict[str, str]` with variable-case keys — use `.get()` with known names.
- Commit pattern: one implementation commit, one code review fix commit per story.
- Code review fixes typically involve: extracting helpers, renaming for consistency, removing dead code — keep the initial implementation clean to minimize review churn.
- `_COLOR_HEX` dict was added to verify_panel.py to avoid hardcoding color strings — reuse in export_dialog if needed.
- The `update_component_status()` method was carefully made sort-safe using UserRole data — same care needed if the preview table needs sorting.

### Git Intelligence

Recent commits:
```
cf1e81a Code review fixes for Story 2.3: fix stale MPN cell text and extract helpers
8c4615c Add health summary bar color-coding and live updates (Story 2.3)
6958c69 Code review fixes for Story 2.2: add fallback alias tests
2f17fbe Add JLCPCB and Newbury Electronics preset BOM templates (Story 2.2)
```

Files to create/modify:
- NEW: `src/kipart_search/gui/export_dialog.py`
- MODIFY: `src/kipart_search/gui/main_window.py` (lines 207-210, `_on_scan_complete`, File menu)
- MODIFY: `src/kipart_search/gui/verify_panel.py` (add public getters)
- MODIFY: `src/kipart_search/core/bom_export.py` (rename `_group_components` → `group_components`)
- NEW: `tests/test_export_dialog.py`

### Anti-Patterns to Avoid

- Do NOT create a QDockWidget for the export dialog — it's a QDialog per UX-DR6
- Do NOT use `dialog.exec()` — the dialog must be non-modal (`.show()`)
- Do NOT duplicate grouping logic from `core/bom_export.py` — import and reuse
- Do NOT access `verify_panel._components` directly from main_window — add public getters
- Do NOT import PySide6 in `core/bom_export.py` — boundary enforcement
- Do NOT add custom template editing — out of scope for this story
- Do NOT block the GUI thread during export — for small BOMs (<200 components) synchronous is fine per NFR4 (<5s), but if export is slow, use QThread
- Do NOT hardcode color values — reuse from existing palette constants
- Do NOT use nested dialogs for any sub-configuration

### Cross-Story Dependencies

- **Story 2.1** (done): BOM export engine with PCBWay template — provides `export_bom()`, `BOMTemplate`, `BOMColumn`
- **Story 2.2** (done): Preset CM templates — provides `JLCPCB_TEMPLATE`, `NEWBURY_TEMPLATE`, CSV export
- **Story 2.3** (done): Health summary bar — provides health percentage data, color palette
- **Story 3.4** (future): Stale data indicators — may add amber stale state to health calculations

### References

- [Source: _bmad-output/planning-artifacts/epics.md — Epic 2, Story 2.4]
- [Source: _bmad-output/planning-artifacts/epics.md — UX-DR6: BOM Export Window definition]
- [Source: _bmad-output/planning-artifacts/epics.md — FR28: Warn when MPN coverage below 100%]
- [Source: _bmad-output/planning-artifacts/epics.md — NFR4: Export < 5 seconds for 70-component board]
- [Source: _bmad-output/planning-artifacts/architecture.md — ADR-02: BOM Export Template Engine]
- [Source: _bmad-output/planning-artifacts/architecture.md — gui/export_dialog.py in file structure]
- [Source: _bmad-output/planning-artifacts/ux-design-specification.md — Journey 5: BOM Export with Template Selection]
- [Source: _bmad-output/planning-artifacts/ux-design-specification.md — Component Strategy: BOM Export Window]
- [Source: _bmad-output/planning-artifacts/ux-design-specification.md — Non-modal windows rule]
- [Source: src/kipart_search/core/bom_export.py — export_bom(), PRESET_TEMPLATES, _group_components()]
- [Source: src/kipart_search/gui/main_window.py — _act_export action (lines 207-210)]
- [Source: src/kipart_search/gui/verify_panel.py — _components, health_bar, get_component()]
- [Source: src/kipart_search/gui/assign_dialog.py — QDialog pattern reference]
- [Source: _bmad-output/implementation-artifacts/2-3-health-summary-bar-with-live-updates.md — Previous story intelligence]

## Dev Agent Record

### Agent Model Used

Claude Opus 4.6 (1M context)

### Debug Log References

- Fixed test visibility assertions: `isVisible()` returns False for child widgets when parent dialog is not shown; switched to `isHidden()` checks.

### Completion Notes List

- Created `ExportDialog` as non-modal QDialog with template selector (QComboBox populated from PRESET_TEMPLATES), DNP handling toggle, file format selector, and live preview table using `group_components()`.
- Health warning banner with amber (#FFEBB4) background shows missing MPN count when health < 100%, hidden at 100%.
- Export action opens QFileDialog, calls `export_bom()` with user-chosen format/DNP overrides via `dataclasses.replace()`, shows success message with "Open File" button using QDesktopServices.
- Wired `_act_export.triggered` → `_on_export_bom()` in main_window.py; enabled after scan in `_on_scan_complete()`; added "Export BOM..." to File menu.
- Added 3 public getters to VerifyPanel: `get_components()`, `get_health_percentage()`, `get_missing_mpn_count()` — avoids private access from main_window.
- Renamed `_group_components` → `group_components` in `core/bom_export.py` (public API for preview).
- DNP filtering via `_is_dnp()` helper checking `extra_fields` for dnp/do_not_populate/dnf variants.
- 22 new tests in `test_export_dialog.py` covering instantiation, preview updates, DNP filtering, warning banner, export action, and VerifyPanel getters.
- All 181 tests pass (159 existing + 22 new), zero regressions.

### File List

- NEW: `src/kipart_search/gui/export_dialog.py`
- MODIFIED: `src/kipart_search/gui/main_window.py`
- MODIFIED: `src/kipart_search/gui/verify_panel.py`
- MODIFIED: `src/kipart_search/core/bom_export.py`
- MODIFIED: `src/kipart_search/core/models.py`
- NEW: `tests/test_export_dialog.py`

### Change Log

- 2026-03-18: Story 2.4 implementation — BOM export dialog with template selection, preview table, DNP filtering, health warning banner, and 22 tests
- 2026-03-19: Code review fixes — removed dead code block, synced File menu Export BOM enabled state, auto-sync format combo on template change, moved DNP detection to core/models.py as BoardComponent.is_dnp property
