# Story 1.3: Detail Panel for Part Inspection

Status: review

## Story

As a designer,
I want a detail panel that shows full specs, pricing, datasheet link, and an assign button for the selected search result,
So that I can inspect a part thoroughly before deciding to assign it.

## Acceptance Criteria

1. **Given** the dockable panel architecture from Story 1.1
   **When** a search result is selected (single-click) in the results table
   **Then** a Detail Panel (QDockWidget, right dock) displays: part MPN, manufacturer, description, package, stock, price breaks, and a clickable datasheet URL

2. **Given** the detail panel is showing a part
   **When** a verify-panel component is also selected (via `_assign_target`)
   **Then** the detail panel includes an "Assign to [reference]" button that triggers assignment

3. **Given** no search result is selected
   **When** the detail panel is visible
   **Then** it shows centered guidance text: "Select a search result to view details" (UX-DR12)

## Tasks / Subtasks

- [x]Task 1: Create `gui/detail_panel.py` with `DetailPanel` widget (AC: #1, #3)
  - [x]Create new file `src/kipart_search/gui/detail_panel.py`
  - [x]`DetailPanel(QWidget)` with a `QVBoxLayout` containing a `QTextBrowser` (read-only, `setOpenExternalLinks(True)`) and an "Assign" `QPushButton` at the bottom
  - [x]Add `set_part(part: PartResult | None)` method: when `part` is not None, render HTML detail (reuse `_render_detail` logic from `results_table.py`); when None, show guidance text
  - [x]Add `set_assign_target(reference: str | None)` method: when reference is set, show "Assign to {reference}" button enabled; when None, hide or disable the button
  - [x]Define signal `assign_requested = Signal()` emitted when the Assign button is clicked
  - [x]Empty-state: centered guidance text "Select a search result to view details" rendered as HTML `<p style="text-align:center; color:#888; margin-top:40%;">Select a search result to view details</p>`
  - [x]Imports: `from __future__ import annotations`, `from kipart_search.core.models import PartResult`

- [x]Task 2: Extract `_render_detail` from `results_table.py` into shared utility (AC: #1)
  - [x]Move the `_render_detail(part: PartResult) -> str` static method out of `ResultsTable` into `detail_panel.py` as a module-level function `render_part_html(part: PartResult) -> str`
  - [x]Update `ResultsTable._on_click` to call the new function: `from kipart_search.gui.detail_panel import render_part_html`
  - [x]Alternatively: keep `_render_detail` in `results_table.py` and have `detail_panel.py` import it — choose whichever avoids circular imports (detail_panel imports from models only, so moving the function into detail_panel.py is cleanest)

- [x]Task 3: Add `dock_detail` to `main_window.py` (AC: #1, #2, #3)
  - [x]Import `DetailPanel` from `kipart_search.gui.detail_panel`
  - [x]Create `self.detail_panel = DetailPanel()`
  - [x]Create `self.dock_detail = self._create_dock("Detail", self.detail_panel, Qt.DockWidgetArea.RightDockWidgetArea)` — after dock_search, before dock_log
  - [x]objectName will be `dock_detail` (via existing `_create_dock` helper)

- [x]Task 4: Wire single-click signal from results table to detail panel (AC: #1)
  - [x]Add a new signal to `ResultsTable`: `part_clicked = Signal(int)` (single-click, distinct from `part_selected` which is double-click for assignment)
  - [x]In `ResultsTable._on_click`, emit `self.part_clicked.emit(row)` in addition to updating the inline detail browser
  - [x]In `MainWindow.__init__`, connect: `self.results_table.part_clicked.connect(self._on_part_clicked)`
  - [x]Add `_on_part_clicked(self, row: int)` method: get `PartResult` via `self.results_table.get_result(row)`, call `self.detail_panel.set_part(part)`

- [x]Task 5: Wire assign button in detail panel (AC: #2)
  - [x]Connect `self.detail_panel.assign_requested.connect(self._on_detail_assign)`
  - [x]Add `_on_detail_assign(self)` method: call `self._on_part_selected(row)` or directly invoke the assign dialog with the currently displayed part and `_assign_target`
  - [x]When `_assign_target` changes (in `_on_component_clicked` and `_on_guided_search`), call `self.detail_panel.set_assign_target(comp.reference)`
  - [x]When `_assign_target` is cleared (after assignment or target change), call `self.detail_panel.set_assign_target(None)`

- [x]Task 6: Update View menu and Reset Layout for 4th dock (AC: #1)
  - [x]In `_build_menus()`, add `view_menu.addAction(self.dock_detail.toggleViewAction())` after dock_search toggle
  - [x]In `_reset_layout()`, add `(self.dock_detail, Qt.DockWidgetArea.RightDockWidgetArea)` to the reset list

- [x]Task 7: Clear detail panel on new search (AC: #3)
  - [x]In `_on_search()` or `_on_results()`, call `self.detail_panel.set_part(None)` to reset to empty state when new search results arrive

- [x]Task 8: Add tests for DetailPanel and dock integration (AC: #1-#3)
  - [x]Add `tests/test_detail_panel.py` with unit tests for `DetailPanel`:
    - `test_empty_state_shows_guidance` — default state has guidance text
    - `test_set_part_shows_detail` — calling `set_part(part)` renders HTML with MPN
    - `test_set_part_none_shows_guidance` — calling `set_part(None)` reverts to guidance
    - `test_assign_button_hidden_no_target` — assign button disabled/hidden when no target
    - `test_assign_button_shows_reference` — `set_assign_target("R14")` shows "Assign to R14"
    - `test_assign_signal_emitted` — clicking assign button emits `assign_requested`
  - [x]Update `tests/test_main_window_docks.py`:
    - Add `test_dock_detail_exists` and `test_dock_detail_object_name` to `TestDockWidgetStructure`
    - Update `test_unique_object_names` to expect 4 names
    - Add `test_detail_docked_right` to `TestDefaultDockPositions`
    - Update `test_view_menu_has_toggles_and_reset` to expect 5 actions (4 toggles + Reset Layout)
    - Add `test_reset_layout_restores_detail` to `TestResetLayout`
  - [x]Use `pytest.importorskip("PySide6")` guard in new test file

- [x]Task 9: Smoke test (AC: #1-#3)
  - [x]Launch app — verify 4 docks visible: Verify, Search, Detail, Log
  - [x]Detail panel shows guidance text initially
  - [x]Search for something, single-click a result — detail panel populates
  - [x]View menu shows 4 panel toggles + Reset Layout
  - [x]Run all tests — no regressions

## Dev Notes

### Architecture Compliance

- **Core/GUI separation**: `detail_panel.py` lives in `gui/`, imports only `core.models.PartResult`. No core changes needed.
- **ADR-07**: Adds 4th QDockWidget (`dock_detail`) to the right area. Default layout becomes: Verify (left) | Search (center/right) | Detail (right) | Log (bottom).
- **UX-DR5**: Detail Panel shows selected part specs, pricing, datasheet link, and assign button.
- **UX-DR12**: Empty state with centered guidance text.
- **FR4**: Designer can view detailed part information for any search result.

### Critical: Existing Detail Browser in `results_table.py`

**The inline detail browser (`QTextBrowser`) inside `ResultsTable` already renders part details on single-click** (lines 86-96 of `results_table.py`). It uses `_render_detail()` to produce HTML.

**Decision needed:** Keep the inline detail browser as-is (it's useful as a compact preview within the search panel) OR remove it and rely solely on the dock panel. The story AC says "Detail Panel (QDockWidget, right dock)" — so the dock widget is required. The inline detail browser can coexist as a compact preview, or be removed to avoid duplication. **Recommended: keep both** — the inline browser serves as a quick preview, the dock panel shows the full detail with assign button. Extract the render function to `detail_panel.py` so both can use it.

### Current Code State (main_window.py, ~551 lines)

From Story 1.2 completion:
- 3 dock widgets: `dock_verify` (left), `dock_search` (right), `dock_log` (bottom)
- QToolBar with 4 actions
- 3-zone QStatusBar
- View menu with 3 toggle actions + Reset Layout
- `_reset_layout()` handles 3 docks
- `_assign_target` tracks the selected verify component
- `_on_part_selected(row)` handles double-click assignment via `AssignDialog`

### What Changes

**New files:**
- `src/kipart_search/gui/detail_panel.py` — `DetailPanel` widget + `render_part_html()` function
- `tests/test_detail_panel.py` — Unit tests for DetailPanel

**Modified:**
- `src/kipart_search/gui/main_window.py` — add `dock_detail`, wire signals, update View menu and `_reset_layout()`
- `src/kipart_search/gui/results_table.py` — add `part_clicked` signal, optionally refactor `_render_detail` to use shared function
- `tests/test_main_window_docks.py` — update dock count assertions, add dock_detail tests

### PartResult Fields Available for Display

From `core/models.py`, `PartResult` has:
- `mpn: str`, `manufacturer: str`, `description: str`, `package: str`
- `category: str`, `datasheet_url: str`, `lifecycle: str`
- `source: str`, `source_part_id: str`, `source_url: str`
- `specs: list[ParametricValue]` — parametric specs table
- `price_breaks: list[PriceBreak]` — quantity pricing (qty, unit_price, currency)
- `stock: int | None`
- `confidence: Confidence`

### Signal Architecture

```
ResultsTable.part_clicked(row)  →  MainWindow._on_part_clicked(row)  →  DetailPanel.set_part(part)
ResultsTable.part_selected(row) →  MainWindow._on_part_selected(row) →  AssignDialog (existing)
DetailPanel.assign_requested()  →  MainWindow._on_detail_assign()    →  AssignDialog
VerifyPanel.component_clicked   →  MainWindow._on_component_clicked  →  DetailPanel.set_assign_target(ref)
```

### Anti-Patterns to Avoid

- Do NOT import PySide6 in any `core/` module
- Do NOT create a circular import between `detail_panel.py` and `results_table.py` — put the shared render function in `detail_panel.py` (it imports from `core.models` only)
- Do NOT remove the inline `QTextBrowser` from `results_table.py` unless explicitly asked — it serves as a compact preview
- Do NOT change the `part_selected` signal semantics — it's already used for double-click assignment
- Do NOT make the detail panel a separate window — it must be a QDockWidget
- Do NOT add features beyond the story scope (no datasheet download, no comparison view)

### Cross-Story Dependencies

- **Story 1.1** (done): Provides QDockWidget architecture, `_create_dock()` helper, objectName pattern.
- **Story 1.2** (done): Provides View menu with toggles, `_reset_layout()` — both need updating for 4th dock.
- **Story 1.4** (next): Will add QSettings save/restore for all 4 dock positions.
- **Story 1.5**: Context menus — "Assign to [reference]" in results table context menu already partially exists.

### Previous Story Intelligence (Story 1.2)

Key learnings:
- `_create_dock()` helper generates objectNames from title: `f"dock_{title.lower().replace(' ', '_')}"` → `dock_detail`
- Hidden central widget pattern (`placeholder.setMaximumSize(0, 0)`) works — don't change it
- View menu toggle actions work via `dock.toggleViewAction()` — just add the new dock's toggle
- `_reset_layout()` uses `removeDockWidget` → `addDockWidget` → `setFloating(False)` → `show()` — add dock_detail to this list
- Tests use `pytest.importorskip("PySide6")` guard — follow same pattern in new test file
- All 48 existing tests pass — run them after changes

### Git Intelligence

Recent commits:
```
f09b1eb Code review fixes for Story 1.2: use pathlib.stat() instead of os.path, mark story done
66a8dd5 Add toolbar, 3-zone status bar, and View menu Reset Layout (Story 1.2)
9f65498 Code review fixes for Story 1.1: document log_panel.py change, add PySide6 skip guard
5019538 Migrate MainWindow from QSplitter to QDockWidget panel architecture
```

Pattern: one source file + one test file per story, test class naming by feature area.

### Project Structure Notes

New file location: `src/kipart_search/gui/detail_panel.py` — consistent with existing panel modules (`verify_panel.py`, `log_panel.py`, `search_bar.py`, `results_table.py`).

New test file: `tests/test_detail_panel.py` — follows `tests/test_main_window_docks.py` pattern.

### Testing Notes

- Use `pytest-qt` `qtbot` fixture if available, but simple `QApplication` instance works (existing pattern)
- Create a minimal `PartResult` fixture for detail panel tests
- Test HTML content with `assertIn` on the text browser's HTML
- Run `tests/test_main_window_docks.py` after changes to verify no regressions

### References

- [Source: _bmad-output/planning-artifacts/epics.md — Epic 1, Story 1.3]
- [Source: _bmad-output/planning-artifacts/architecture.md — ADR-07: QDockWidget Panel Migration]
- [Source: _bmad-output/planning-artifacts/ux-design-specification.md — UX-DR5: Detail Panel, UX-DR12: Empty States]
- [Source: _bmad-output/planning-artifacts/prd.md — FR4: View detailed part information]
- [Source: _bmad-output/project-context.md — PySide6 patterns, naming conventions]
- [Source: src/kipart_search/gui/results_table.py — existing _render_detail() and inline QTextBrowser]
- [Source: src/kipart_search/core/models.py — PartResult dataclass fields]
- [Source: _bmad-output/implementation-artifacts/1-2-toolbar-status-bar-and-view-menu.md — Previous story learnings]

## Dev Agent Record

### Agent Model Used

Claude Opus 4.6 (1M context)

### Debug Log References

- Initial test run: 1 failure (`isVisible` on unshown widget) + 1 error (`qtbot` fixture missing). Fixed by using `isVisibleTo(panel)` and signal-slot manual wiring instead of pytest-qt.
- Final test run: 69/69 passed, 0 failures, 0 errors.

### Completion Notes List

- Created `DetailPanel` widget with `QTextBrowser` + `QPushButton` in `detail_panel.py`
- Extracted `render_part_html()` as shared module-level function; `ResultsTable` now imports it (removed duplicated `_render_detail` static method)
- Added `part_clicked` signal to `ResultsTable` (single-click, distinct from `part_selected` double-click)
- Added 4th dock widget `dock_detail` (right area) to `MainWindow`
- Wired `part_clicked` → `_on_part_clicked` → `DetailPanel.set_part()`
- Wired `assign_requested` → `_on_detail_assign` → reuses existing `_on_part_selected` flow
- Updated `_on_component_clicked` and `_on_guided_search` to set assign target on detail panel
- Detail panel cleared on new search results
- View menu updated: 4 toggles + Reset Layout
- `_reset_layout()` updated for 4 docks
- 17 new tests in `test_detail_panel.py`, 5 updated tests in `test_main_window_docks.py`
- All 69 tests pass with no regressions

### Change Log

- 2026-03-18: Implemented Story 1.3 — Detail Panel for Part Inspection. Created DetailPanel widget, extracted shared render function, added dock_detail, wired signals, updated View menu and Reset Layout, added 17 new tests.

### File List

- src/kipart_search/gui/detail_panel.py (new)
- src/kipart_search/gui/results_table.py (modified — added `part_clicked` signal, removed `_render_detail`, imports `render_part_html`)
- src/kipart_search/gui/main_window.py (modified — added `dock_detail`, `DetailPanel` import, `_on_part_clicked`, `_on_detail_assign`, updated View menu and `_reset_layout`)
- tests/test_detail_panel.py (new)
- tests/test_main_window_docks.py (modified — added dock_detail tests, updated assertions for 4 docks)
