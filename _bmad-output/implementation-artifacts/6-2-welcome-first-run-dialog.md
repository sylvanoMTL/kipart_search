# Story 6.2: Welcome / First-Run Dialog

Status: review

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a new user,
I want a guided first-launch experience that helps me set up at least one data source,
so that I can start searching immediately without reading documentation.

## Acceptance Criteria

1. **First-launch detection** (UX Journey 3)
   **Given** the application launches for the first time (no config.json exists OR `welcome_shown` flag is false)
   **When** the main window opens
   **Then** a Welcome Dialog (modal QDialog) appears with a brief tool description and 3 options

2. **JLCPCB download option** (FR7, UX-DR8)
   **Given** the Welcome Dialog is displayed
   **When** the user clicks "Download JLCPCB Database"
   **Then** a progress bar appears showing download progress (~500 MB) with a Cancel button
   **And** on completion the dialog auto-closes, the JLCPCB source is enabled, and the status bar updates to show "JLCPCB" as active
   **And** the app is immediately usable for searching

3. **Configure API source option**
   **Given** the Welcome Dialog is displayed
   **When** the user clicks "Configure API Source"
   **Then** the Source Preferences Dialog from Story 6.1 opens (modal)
   **And** after the user accepts preferences, the Welcome Dialog closes and sources are applied

4. **Skip option**
   **Given** the Welcome Dialog is displayed
   **When** the user clicks "Skip for now"
   **Then** the dialog closes, the app opens normally with status bar showing "No sources configured"
   **And** the Preferences toolbar button receives a subtle visual emphasis (e.g. bold text or highlighted icon) to guide the user back
   **And** the Welcome Dialog is NOT shown again on subsequent launches

5. **Returning user bypass**
   **Given** a user who has previously completed or skipped the Welcome Dialog
   **When** the application launches
   **Then** the Welcome Dialog does not appear — the app opens directly to the main window

6. **Download cancellation**
   **Given** the JLCPCB download is in progress within the Welcome Dialog
   **When** the user clicks Cancel
   **Then** the download stops, the Welcome Dialog returns to its initial state (3 options visible)
   **And** no partial database file is left behind

## Tasks / Subtasks

- [x] Task 1: Add `welcome_shown` flag to SourceConfigManager (AC: #1, #5)
  - [x] 1.1 Add `welcome_shown: bool` field to config.json schema in `SourceConfigManager`
  - [x] 1.2 Implement `get_welcome_shown() -> bool` — returns False if config.json doesn't exist or flag is missing
  - [x] 1.3 Implement `set_welcome_shown(value: bool)` — persists to config.json without overwriting other settings
  - [x] 1.4 Add tests for welcome_shown get/set/default in `tests/core/test_source_config.py`

- [x] Task 2: Create `gui/welcome_dialog.py` — Welcome Dialog UI (AC: #1, #2, #3, #4, #6)
  - [x] 2.1 Create `WelcomeDialog(QDialog)` — modal, fixed size, non-resizable
  - [x] 2.2 Layout: app name + brief description label at top, then 3 option buttons stacked vertically (or as cards)
  - [x] 2.3 Option 1 button: "Download JLCPCB Database" with subtitle "No API key needed — ~500 MB offline database"
  - [x] 2.4 Option 2 button: "Configure API Source" with subtitle "Set up DigiKey, Mouser, or Octopart"
  - [x] 2.5 Option 3 button: "Skip for now" with subtitle "Configure sources later in Preferences"
  - [x] 2.6 Download state: when Option 1 clicked, replace the 3 buttons with a progress bar + cancel button (reuse `DownloadWorker` from `download_dialog.py`)
  - [x] 2.7 On download complete: emit `source_configured` signal, auto-close dialog
  - [x] 2.8 On download cancel: return to initial 3-button state, clean up partial files
  - [x] 2.9 On Option 2 clicked: open `SourcePreferencesDialog` as nested modal. If accepted, emit `source_configured` signal with the configs, close Welcome Dialog. If cancelled, return to Welcome Dialog.
  - [x] 2.10 On Option 3 (Skip): close dialog with `QDialog.Rejected` result
  - [x] 2.11 Define signal: `source_configured = Signal()` — emitted when any source becomes configured

- [x] Task 3: Wire Welcome Dialog into MainWindow startup (AC: #1, #4, #5)
  - [x] 3.1 In `MainWindow.__init__()`, after `_init_sources_from_config()` and `_update_status()`, check `SourceConfigManager().get_welcome_shown()`
  - [x] 3.2 If False: show `WelcomeDialog` modal. Connect `source_configured` signal to rebuild sources and update status.
  - [x] 3.3 After dialog closes (accepted or rejected), call `SourceConfigManager().set_welcome_shown(True)`
  - [x] 3.4 Remove the existing ad-hoc QMessageBox first-run database prompt from `_init_jlcpcb_source()` (lines ~456-469) — the Welcome Dialog replaces this flow
  - [x] 3.5 If Skip chosen: apply subtle emphasis to `_act_prefs` toolbar button (e.g. bold font or highlighted icon)
  - [x] 3.6 Ensure `_update_status()` and search bar reflect new source state after dialog

- [x] Task 4: Tests (AC: all)
  - [x] 4.1 `tests/gui/test_welcome_dialog.py` — test dialog construction, button visibility, option 3 (skip) closes dialog
  - [x] 4.2 Test download state transition: clicking Option 1 shows progress bar, hides buttons
  - [x] 4.3 Test Option 2 opens SourcePreferencesDialog (mock or verify dialog creation)
  - [x] 4.4 Test `source_configured` signal emission on download complete
  - [x] 4.5 Test first-run detection: no config.json → welcome shown; config exists with `welcome_shown: true` → welcome not shown
  - [x] 4.6 Extend `tests/core/test_source_config.py` with welcome_shown flag tests
  - [x] 4.7 Update `tests/test_main_window_docks.py` if startup flow changes affect existing tests

## Dev Notes

### Architecture Compliance

- **core/GUI separation is paramount**: The `welcome_shown` flag goes in `core/source_config.py` (persistence) while the dialog UI goes in `gui/welcome_dialog.py`. Zero PySide6 imports in core.
- **Anti-pattern**: Do NOT create a separate config file for the welcome flag. It belongs in the existing `~/.kipart-search/config.json` alongside source configs.
- **Anti-pattern**: Do NOT use QSettings for the welcome flag. All app config uses config.json for consistency.

### Existing Code to Reuse — Do NOT Reinvent

- **`DownloadWorker` from `gui/download_dialog.py`**: Reuse this QThread worker for the JLCPCB download within the Welcome Dialog. It handles chunked zip download with progress callbacks. Do NOT implement download logic again.
- **`JLCPCBSource.download_database()`**: Static method in `core/sources.py` (line ~357). Takes `target_dir`, `progress_callback(int, int, str)`, and `cancel_check() -> bool`. Returns `Path` to DB file. Raises `RuntimeError` on failure.
- **`SourcePreferencesDialog`** from `gui/source_preferences_dialog.py`: Open it as a nested modal from Option 2. Use the same pattern as `MainWindow._on_preferences()` — construct with `SourceConfigManager`, call `.exec()`, get configs from `.get_saved_configs()`.
- **`SourceConfigManager`**: Already handles config.json read/write. Add `welcome_shown` as a top-level key alongside the existing `sources` key.
- **`MainWindow._apply_source_configs(configs)`**: Call this after the Welcome Dialog closes with configured sources to rebuild the SearchOrchestrator.
- **`MainWindow._on_db_downloaded(db_path)`**: Existing handler for JLCPCB download completion. Reuse the same post-download logic (create JLCPCBSource, add to orchestrator, update status).
- **Colour constants**: GREEN=#C8FFC8, AMBER=#FFEBB4, RED=#FFC8C8 (from verify_panel.py). Use if needed for status indicators.

### Replacing Existing First-Run Detection

The current `_init_jlcpcb_source()` in `main_window.py` (around lines 456-469) has ad-hoc first-run detection using `QMessageBox.question()` when the database is missing. **This must be removed** and replaced by the Welcome Dialog flow. After this story:
- If `welcome_shown` is False → Welcome Dialog handles database download
- If `welcome_shown` is True and JLCPCB enabled but DB missing → existing `DownloadDialog` handles it (the full download dialog, not the welcome one)

### Config.json Schema After This Story

```json
{
  "welcome_shown": true,
  "sources": {
    "JLCPCB": {"enabled": true, "is_default": true},
    "DigiKey": {"enabled": false, "is_default": false},
    "Mouser": {"enabled": false, "is_default": false},
    "Octopart": {"enabled": false, "is_default": false}
  }
}
```

### Signal Flow

```
MainWindow.__init__()
  → _init_sources_from_config()      # load existing configs (may find none)
  → _update_status()                  # shows "No sources configured" initially
  → check welcome_shown flag
  → WelcomeDialog.exec()              # modal, blocks
      ├─ Option 1 (Download JLCPCB)
      │   → DownloadWorker.run()      # background thread
      │   → download_complete          # signal to dialog
      │   → source_configured.emit()   # signal to main window
      │   → dialog auto-closes
      ├─ Option 2 (Configure API)
      │   → SourcePreferencesDialog.exec()  # nested modal
      │   → if accepted: source_configured.emit()
      │   → dialog closes
      └─ Option 3 (Skip)
          → dialog closes (Rejected)
  → set_welcome_shown(True)
  → _apply_source_configs() or _on_db_downloaded()  # rebuild sources
  → _update_status()                  # now shows active sources
```

### Visual Design Notes

- Title: "Welcome to KiPart Search" (or just app name)
- Brief description: 1-2 sentences about what the tool does
- 3 option buttons should be visually distinct — QPushButtons with descriptive text, not just single words
- Consider using slightly larger buttons or card-like styling for the 3 options
- Progress bar during download: standard QProgressBar with percentage label
- Dialog should NOT be resizable — fixed, compact size
- Follow the modal dialog pattern from UX spec: OK/Cancel not needed — the 3 options ARE the choices

### Preferences Button Emphasis After Skip

When the user clicks "Skip for now", the `_act_prefs` toolbar action should be visually emphasized. Options:
- Set the button font to bold: `widget.setStyleSheet("font-weight: bold;")`
- Add a tooltip: "Configure data sources to start searching"
- The emphasis should persist until the user opens Preferences at least once (could track via another flag, or simply remove emphasis when `_on_preferences()` is called)

### Project Structure Notes

- `gui/welcome_dialog.py` follows the flat `gui/*.py` structure — no subdirectories
- Config file at `~/.kipart-search/config.json` — same path used by `SourceConfigManager`
- No new core modules needed — only extending `SourceConfigManager`

### Previous Story Intelligence (Story 6.1)

- **SourceConfigManager pattern**: Story 6.1 established config.json schema with `sources` key. Welcome flag adds a sibling key at the same level — do NOT nest it under sources.
- **Dialog pattern**: `SourcePreferencesDialog` is modal, uses `QDialogButtonBox`, saves on accept. Welcome Dialog is simpler — no button box, just 3 option buttons.
- **Test pattern**: Story 6.1 added 26 core + 27 GUI tests. Follow same pytest style with `qtbot` for GUI tests.
- **Code review fixes from 6.1**: Renamed `TestConnectionWorker` to `ConnectionTestWorker` to avoid pytest collection warning. Name the download worker carefully to avoid similar issues (e.g. `WelcomeDownloadWorker`).
- **All 470 tests were passing after Story 6.1** — maintain this baseline.
- **Public API pattern**: Story 6.1 renamed `_compute_status` to `compute_status` (public). Follow this convention — methods called from outside the class should not have underscore prefix.

### Git Intelligence

Recent commits follow pattern: "Add {feature} (Story X.Y)". Last commit: `343d5f0 Add source preferences dialog with code review fixes (Story 6.1)`. Files created/modified per story: new modules in core/ and gui/, main_window.py modifications, dedicated test files.

### References

- [Source: _bmad-output/planning-artifacts/epics.md#Epic 6, Story 6.2]
- [Source: _bmad-output/planning-artifacts/ux-design-specification.md#Welcome / First-Run Dialog]
- [Source: _bmad-output/planning-artifacts/ux-design-specification.md#Journey 3: First-Run Experience]
- [Source: _bmad-output/planning-artifacts/architecture.md#ADR-03 Credential Storage]
- [Source: _bmad-output/planning-artifacts/prd.md#FR7, FR32, NFR7]
- [Source: _bmad-output/project-context.md#Critical Don't-Miss Rules]

## Dev Agent Record

### Agent Model Used

Claude Opus 4.6 (1M context)

### Debug Log References

- Pre-existing PySide6 segfault in `test_main_window_docks.py` and `test_context_menus.py::test_status_bar_accessible_names` — Qt access violation when creating multiple MainWindow instances in a single test process on Windows. Unrelated to Story 6.2 changes. Added `tests/conftest.py` with autouse fixture to patch `_check_welcome` to prevent modal dialog blocking during tests.

### Completion Notes List

- Task 1: Added `get_welcome_shown()` and `set_welcome_shown()` to `SourceConfigManager`. Both methods preserve existing config.json keys. Updated `save_configs()` to preserve non-source keys (e.g. `welcome_shown`). 7 tests added.
- Task 2: Created `WelcomeDialog(QDialog)` in `gui/welcome_dialog.py`. Modal, fixed-size, 3 option buttons. Option 1 reuses `DownloadWorker` for JLCPCB download with progress bar. Option 2 opens `SourcePreferencesDialog` as nested modal. Option 3 (Skip) rejects dialog. Cancel during download returns to initial 3-button state. Emits `source_configured` signal on successful setup.
- Task 3: Added `_check_welcome()` to `MainWindow.__init__()` after source init. Removed ad-hoc `QMessageBox.question` first-run prompt from `_init_jlcpcb_source()`. Connected `source_configured` signal to `_on_db_downloaded` or `_apply_source_configs` depending on path taken. Added Preferences button emphasis (bold font) when user skips, removed on first Preferences open.
- Task 4: 18 GUI tests in `tests/gui/test_welcome_dialog.py` covering dialog construction, skip behavior, download state transitions, configure option, signal emission, first-run detection, download cancellation, and progress updates. 7 core tests in `tests/core/test_source_config.py::TestWelcomeShown`. Added `tests/conftest.py` with autouse fixture to prevent welcome dialog blocking during MainWindow tests.

### Change Log

- 2026-03-20: Implemented Story 6.2 — Welcome / First-Run Dialog with all 4 tasks complete

### File List

- src/kipart_search/core/source_config.py (modified — added welcome_shown flag methods, updated save_configs to preserve non-source keys)
- src/kipart_search/gui/welcome_dialog.py (new — WelcomeDialog with 3 options, download progress, signal emission)
- src/kipart_search/gui/main_window.py (modified — added _check_welcome(), removed QMessageBox first-run prompt, added QDialog import, prefs emphasis on skip)
- tests/conftest.py (new — autouse fixture to patch _check_welcome for all tests)
- tests/core/test_source_config.py (modified — added TestWelcomeShown class with 7 tests)
- tests/gui/test_welcome_dialog.py (new — 18 tests covering all acceptance criteria)
