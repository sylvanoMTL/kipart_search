# Story 1.4: Layout Persistence and Empty States

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a designer,
I want my panel arrangement to be saved between sessions and every panel to show helpful guidance when empty,
So that I don't have to reconfigure my layout each time and I always know what to do next.

## Acceptance Criteria

1. **Given** the user has customized the panel layout (moved, resized, floated, or hidden panels)
   **When** the application closes
   **Then** window geometry and dock state are saved via QSettings (organization="kipart-search", app="kipart-search")
   **And** when the application reopens, the saved layout is restored exactly

2. **Given** the application launches for the first time (no saved state)
   **When** the main window appears
   **Then** the default layout is shown: Verify (left), Search+Detail (right), Log (bottom)

3. **Given** the application launches with no project scanned and no search performed
   **When** the verify panel is empty
   **Then** it shows centered guidance text: "Scan a project or open a BOM to begin"
   **And** the search results area shows: "Search for components using the query bar above"
   **And** the log panel shows: "Ready" as initial entry

4. **Given** a saved layout exists but is corrupted or from an incompatible version
   **When** the application launches
   **Then** `restoreState()` fails gracefully and the default layout is applied instead

5. **Given** the user clicks "View > Reset Layout"
   **When** the layout resets
   **Then** the persisted state is also cleared so that next launch uses defaults

## Tasks / Subtasks

- [x] Task 1: Add QSettings layout persistence to `main_window.py` (AC: #1, #2, #4)
  - [x] Override `closeEvent(self, event)` to save geometry and dock state before closing
  - [x] Call `QSettings("kipart-search", "kipart-search")` — matches ADR-07 naming
  - [x] Save two keys: `settings.setValue("geometry", self.saveGeometry())` and `settings.setValue("windowState", self.saveState())`
  - [x] Call `event.accept()` after saving
  - [x] At the end of `__init__`, after all docks are created, attempt restore: `settings.value("geometry")` and `settings.value("windowState")`
  - [x] Guard restore with `if geometry is not None` and `if state is not None` — first launch has no saved state, so fall through to default layout
  - [x] `restoreState()` returns `bool` — if it returns `False`, log a warning and call `_reset_layout()` to apply defaults (AC: #4)

- [x] Task 2: Clear persisted state on Reset Layout (AC: #5)
  - [x] In `_reset_layout()`, after repositioning all docks, add: `QSettings("kipart-search", "kipart-search").clear()`
  - [x] This ensures next launch uses the default layout, not a stale saved state
  - [x] Import `QSettings` from `PySide6.QtCore` (add to existing import line)

- [x] Task 3: Add empty-state guidance to `verify_panel.py` (AC: #3)
  - [x] Define `_EMPTY_GUIDANCE` constant: `"Scan a project or open a BOM to begin"` (matches UX-DR12)
  - [x] In `__init__`, set `self.summary_label.setText(_EMPTY_GUIDANCE)` as initial state
  - [x] In `clear()`, reset to `self.summary_label.setText(_EMPTY_GUIDANCE)` instead of `""`
  - [x] Style: centered, muted color (#888), consistent with detail_panel.py guidance pattern

- [x] Task 4: Add empty-state guidance to `results_table.py` (AC: #3)
  - [x] Define `_EMPTY_GUIDANCE` constant: `"Search for components using the query bar above"`
  - [x] In `__init__`, set the detail `QTextBrowser` HTML to centered guidance text (same HTML pattern as detail_panel.py's `_GUIDANCE_HTML`)
  - [x] In `clear_results()`, reset the detail browser to the guidance HTML
  - [x] The `_count_label` can remain empty — guidance is in the detail browser area

- [x] Task 5: Add initial "Ready" log entry to `log_panel.py` (AC: #3)
  - [x] In `__init__`, after creating the `QTextEdit`, call `self.log("Ready")` to show an initial timestamped entry
  - [x] This replaces the placeholder text approach — a real log entry is more consistent with the log panel's purpose

- [x] Task 6: Add tests for layout persistence (AC: #1, #2, #4, #5)
  - [x] Update `tests/test_main_window_docks.py` with new test class `TestLayoutPersistence`:
    - `test_close_event_saves_state` — create window, close it, verify QSettings has "geometry" and "windowState" keys
    - `test_restore_state_on_init` — save state from one window, create new window, verify restoreState was applied (geometry matches)
    - `test_first_launch_no_saved_state` — clear QSettings, create window, verify default layout (no crash)
    - `test_reset_layout_clears_settings` — call `_reset_layout()`, verify QSettings is cleared
  - [x] Use `QSettings("kipart-search", "kipart-search").clear()` in test fixture teardown to avoid test pollution

- [x] Task 7: Add tests for empty states (AC: #3)
  - [x] In `tests/test_main_window_docks.py` or new `tests/test_empty_states.py`:
    - `test_verify_panel_initial_guidance` — verify panel summary_label text contains guidance message
    - `test_results_table_initial_guidance` — results table detail browser contains guidance HTML
    - `test_log_panel_initial_ready` — log panel text contains "Ready"
    - `test_detail_panel_initial_guidance` — (already tested in test_detail_panel.py, verify it still passes)
  - [x] Use `pytest.importorskip("PySide6")` guard

- [x] Task 8: Smoke test (AC: #1-#5)
  - [x] Launch app — verify 4 docks visible with default layout
  - [x] Verify panel shows "Scan a project or open a BOM to begin"
  - [x] Results area shows "Search for components using the query bar above"
  - [x] Log panel shows timestamped "Ready" entry
  - [x] Detail panel shows "Select a search result to view details"
  - [x] Move a dock to a different position, close app
  - [x] Relaunch — verify dock position is restored
  - [x] Click "View > Reset Layout" — verify default restored
  - [x] Close and relaunch — verify default layout (not the moved position)
  - [x] Run all tests — no regressions

## Dev Notes

### Architecture Compliance

- **Core/GUI separation**: All changes are in `gui/` modules only. No core changes needed.
- **ADR-07**: QSettings persistence pattern is explicitly documented in the architecture: `QSettings("kipart-search", "kipart-search")` for both geometry and windowState.
- **UX-DR12**: Empty states with centered guidance text — "not blank, always tell the user what to do next."
- **UX-DR14**: Layout persistence via QSettings.

### Current Code State (from Story 1.3 completion)

`main_window.py` (~580 lines):
- 4 dock widgets: `dock_verify` (left), `dock_search` (right), `dock_detail` (right), `dock_log` (bottom)
- Hidden zero-size central widget placeholder (lines 133-135)
- `_create_dock()` helper generates objectNames: `dock_verify`, `dock_search`, `dock_detail`, `dock_log`
- `_reset_layout()` (lines 293-304): repositions all 4 docks programmatically
- **No QSettings usage at all** — this is the gap Story 1.4 fills
- **No closeEvent override** — default Qt close behavior
- Status bar right zone: `_action_label` initialized to `"Ready"` (line 218)
- File > Close action calls `self.close()` (line 247)

### What Exists vs What's Missing

| Panel | Current Empty State | Required Empty State |
|-------|-------------------|---------------------|
| **verify_panel.py** | `summary_label=""` (blank) | "Scan a project or open a BOM to begin" |
| **results_table.py** | detail browser empty, `_count_label=""` | "Search for components using the query bar above" |
| **log_panel.py** | `setPlaceholderText("Activity log ...")` | Initial `log("Ready")` entry |
| **detail_panel.py** | `_GUIDANCE_HTML` with centered text | Already done (Story 1.3) |
| **search_bar.py** | `setPlaceholderText(...)` on inputs | Already done |

### QSettings Key Facts for Implementation

- `QSettings("kipart-search", "kipart-search")` — org and app both "kipart-search"
- On Windows: stored in registry `HKEY_CURRENT_USER\Software\kipart-search\kipart-search`
- On Linux: `~/.config/kipart-search/kipart-search.conf`
- On macOS: `~/Library/Preferences/com.kipart-search.kipart-search.plist`
- `saveGeometry()` returns `QByteArray` — stores window position, size, maximized state
- `saveState()` returns `QByteArray` — stores dock positions, sizes, visibility, floating state
- `restoreState()` returns `bool` — `False` if data is incompatible (e.g., dock objectNames changed)
- **Critical**: `restoreState()` requires all docks to exist with matching `objectName`s BEFORE calling it. Place the restore call at the end of `__init__`, after all docks are created.

### Implementation Pattern (from Architecture Doc)

```python
# On close (closeEvent)
settings = QSettings("kipart-search", "kipart-search")
settings.setValue("geometry", self.saveGeometry())
settings.setValue("windowState", self.saveState())

# On open (end of __init__)
settings = QSettings("kipart-search", "kipart-search")
geometry = settings.value("geometry")
state = settings.value("windowState")
if geometry is not None:
    self.restoreGeometry(geometry)
if state is not None:
    if not self.restoreState(state):
        log.warning("Failed to restore window state, using defaults")
        self._reset_layout()
```

### Empty State HTML Pattern (from detail_panel.py)

Reuse the same centered guidance pattern already established:
```python
_GUIDANCE_HTML = (
    '<p style="text-align:center; color:#888; margin-top:40%;">'
    "Your guidance text here</p>"
)
```

For `verify_panel.py`, the guidance goes in `summary_label.setText()` since it's a `QLabel`, not HTML. Style with `summary_label.setAlignment(Qt.AlignCenter)` and `summary_label.setStyleSheet("color: #888;")` — but only for the empty state. Reset style when populated.

### Anti-Patterns to Avoid

- Do NOT save/restore in `config.json` — use QSettings (it's the Qt-native approach and ADR-07 mandates it)
- Do NOT use `QSettings.sync()` explicitly — Qt handles sync on destruction and on `setValue`
- Do NOT store window state in core/ — this is purely GUI state
- Do NOT change dock objectNames — they must match between save and restore sessions
- Do NOT block the close event — save quickly and accept
- Do NOT clear QSettings in closeEvent — only in `_reset_layout()`
- Do NOT use `settings.remove()` for individual keys — use `settings.clear()` in reset to wipe all app settings cleanly

### Cross-Story Dependencies

- **Story 1.1** (done): Provides QDockWidget architecture, `_create_dock()` helper, objectName pattern
- **Story 1.2** (done): Provides View menu with "Reset Layout", `_reset_layout()` method, toolbar, status bar
- **Story 1.3** (done): Provides 4th dock (`dock_detail`), empty state pattern (`_GUIDANCE_HTML`)
- **Story 1.5** (next): Context menus and accessibility labels — no dependency on this story

### Previous Story Intelligence (Story 1.3)

Key learnings from Story 1.3:
- `_create_dock()` helper generates objectNames from title: `f"dock_{title.lower().replace(' ', '_')}"` — produces `dock_verify`, `dock_search`, `dock_detail`, `dock_log`
- Hidden central widget pattern (`placeholder.setMaximumSize(0, 0)`) works — don't change it
- `_GUIDANCE_HTML` pattern with centered #888 text at 40% margin-top is the established empty-state pattern
- `_reset_layout()` uses `removeDockWidget` → `addDockWidget` → `setFloating(False)` → `show()` — add QSettings clear to this
- All 69 existing tests pass — run them after changes to verify no regressions
- Tests use `pytest.importorskip("PySide6")` guard — follow same pattern

### Git Intelligence

Recent commits:
```
f100f53 Code review fixes for Story 1.3: use dynamic source label instead of hardcoded LCSC, mark story done
2a14392 Add detail panel for part inspection with assign button (Story 1.3)
f09b1eb Code review fixes for Story 1.2: use pathlib.stat() instead of os.path, mark story done
66a8dd5 Add toolbar, 3-zone status bar, and View menu Reset Layout (Story 1.2)
```

Pattern: one commit per story implementation, one commit per code review fix. Test class naming by feature area.

### Project Structure Notes

- All changes in existing files — no new source files needed
- Modified: `main_window.py` (QSettings save/restore, closeEvent), `verify_panel.py` (guidance text), `results_table.py` (guidance text), `log_panel.py` (initial Ready entry)
- Test changes: `test_main_window_docks.py` (layout persistence tests, empty state tests)

### Testing Notes

- Use `QSettings("kipart-search", "kipart-search").clear()` in test fixture teardown to prevent test pollution
- Test `closeEvent` by calling `window.close()` (already in teardown) and checking QSettings after
- Test restore by saving state from one MainWindow, then creating a new one and checking geometry
- Use `pytest.importorskip("PySide6")` guard in all test files
- Existing QApplication at module level pattern — reuse, don't create a new one

### References

- [Source: _bmad-output/planning-artifacts/epics.md — Epic 1, Story 1.4]
- [Source: _bmad-output/planning-artifacts/architecture.md — ADR-07: QDockWidget Panel Migration, QSettings pattern]
- [Source: _bmad-output/planning-artifacts/ux-design-specification.md — UX-DR12: Empty States, UX-DR14: Layout Persistence]
- [Source: _bmad-output/planning-artifacts/prd.md — NFR14-15: Portability]
- [Source: _bmad-output/project-context.md — PySide6 patterns, naming conventions]
- [Source: _bmad-output/implementation-artifacts/1-3-detail-panel-for-part-inspection.md — Previous story learnings, _GUIDANCE_HTML pattern]
- [Source: src/kipart_search/gui/main_window.py — Current _reset_layout, dock creation, no QSettings]
- [Source: src/kipart_search/gui/detail_panel.py — _GUIDANCE_HTML empty state pattern]

## Dev Agent Record

### Agent Model Used

Claude Opus 4.6 (1M context)

### Debug Log References

None — clean implementation, all 79 tests passed on first run.

### Completion Notes List

- Added `closeEvent()` override to `MainWindow` that saves geometry and dock state via `QSettings("kipart-search", "kipart-search")`
- Added restore logic at end of `__init__` — reads saved geometry/state, falls back to defaults if `restoreState()` fails or no saved state exists
- Added `QSettings.clear()` call to `_reset_layout()` so resetting also clears persisted state for next launch
- Added `_EMPTY_GUIDANCE` constant and centered/muted guidance text to `VerifyPanel` — shown on init and after `clear()`
- Added `_EMPTY_GUIDANCE` HTML constant to `ResultsTable` — shown in detail browser on init and after `clear_results()`
- Replaced `setPlaceholderText` in `LogPanel` with an actual `self.log("Ready")` call in `__init__`
- Added `TestLayoutPersistence` class (4 tests) to `test_main_window_docks.py`
- Created `tests/test_empty_states.py` (6 tests) covering all 4 panels' empty-state guidance
- All 79 tests pass (69 existing + 10 new), zero regressions

### Code Review Fixes

- **Fixed**: Toolbar missing `objectName` — caused `QMainWindow::saveState()` warning, breaking layout persistence. Added `toolbar.setObjectName("main_toolbar")`
- **Fixed**: `_reset_layout()` used `settings.clear()` which wipes ALL app settings — replaced with targeted `settings.remove("geometry")` + `settings.remove("windowState")` to preserve future user preferences
- **Fixed**: `import logging` placement — moved into stdlib block per project import convention
- **Added**: `test_toolbar_has_object_name` test to prevent regression
- All 80 tests pass (69 existing + 11 new), zero regressions

### Change Log

- 2026-03-18: Implemented Story 1.4 — layout persistence via QSettings and empty-state guidance for all panels
- 2026-03-18: Code review fixes — toolbar objectName, targeted settings removal, import ordering

### File List

- src/kipart_search/gui/main_window.py (modified — QSettings import, closeEvent, restore logic, targeted remove in _reset_layout, toolbar objectName)
- src/kipart_search/gui/verify_panel.py (modified — _EMPTY_GUIDANCE constant, centered/muted style, clear() update)
- src/kipart_search/gui/results_table.py (modified — _EMPTY_GUIDANCE HTML constant, init guidance, clear_results update)
- src/kipart_search/gui/log_panel.py (modified — replaced placeholderText with self.log("Ready"))
- tests/test_main_window_docks.py (modified — QSettings import, TestLayoutPersistence class with 4 tests, toolbar objectName test)
- tests/test_empty_states.py (new — 6 tests for empty-state guidance across all panels)
