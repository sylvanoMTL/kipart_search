# Story 6.1: Source Preferences Dialog

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a designer,
I want a preferences dialog where I can enable/disable data sources, enter API keys, and test connections,
so that I control which distributors the tool queries and can validate my credentials before searching.

## Acceptance Criteria

1. **Dialog Access** (UX-DR7)
   **Given** the designer clicks the "Preferences" toolbar button or "Preferences..." in the Tools menu
   **When** the Source Preferences Dialog opens
   **Then** it is a modal QDialog listing all available sources: JLCPCB (offline DB), DigiKey, Mouser, Octopart
   **And** each source row has: an enable/disable toggle, a status indicator (green = configured, amber = key missing, red = key invalid after test), and source-specific configuration

2. **API Key Management** (FR32, NFR6)
   **Given** a source requires an API key (DigiKey, Mouser, Octopart)
   **When** the source is enabled
   **Then** an API key input field appears with a "Test Connection" button
   **And** clicking "Test" validates the credentials against the API and shows green checkmark (valid) or red X with error message (invalid)
   **And** valid API keys are stored via `keyring` (OS-native secret storage), never in plaintext config files
   **And** environment variable overrides are supported: `KIPART_DIGIKEY_CLIENT_ID`, `KIPART_MOUSER_API_KEY`, etc.

3. **JLCPCB Source Configuration**
   **Given** the JLCPCB source row is displayed
   **When** the designer views its configuration
   **Then** it shows database status (downloaded / not downloaded / stale), database path, file size, and a "Download" or "Refresh" button

4. **Default Source Selection**
   **Given** multiple sources are enabled
   **When** the designer sets a default source
   **Then** that source is pre-selected in the search bar's source selector dropdown

5. **No Telemetry** (NFR7)
   **Given** any source configuration is saved
   **When** the dialog closes
   **Then** no data is sent to external servers — only explicit user-initiated API calls (Test Connection, Search) contact distributor APIs

6. **Preferences Persistence**
   **Given** the designer saves preferences and restarts the app
   **When** the app relaunches
   **Then** enabled/disabled states, default source, and credential status are preserved
   **And** the search bar source selector reflects the saved configuration

## Tasks / Subtasks

- [x] Task 1: Create `core/source_config.py` — source configuration model and persistence (AC: #2, #5, #6)
  - [x] 1.1 Create `SourceConfig` dataclass: `source_name: str`, `enabled: bool`, `status: str` (configured/key_missing/key_invalid/not_downloaded), `is_default: bool`
  - [x] 1.2 Create `SourceConfigManager` class that reads/writes `~/.kipart-search/config.json` for non-secret settings (enabled state, default source)
  - [x] 1.3 Implement `get_credential(source_name: str, field_name: str) -> str | None` — checks env var first (`KIPART_{SOURCE}_{FIELD}`), then `keyring.get_password("kipart-search", key)`
  - [x] 1.4 Implement `set_credential(source_name: str, field_name: str, value: str)` — stores via `keyring.set_password("kipart-search", key, value)`
  - [x] 1.5 Implement `delete_credential(source_name: str, field_name: str)` — removes from keyring
  - [x] 1.6 Implement `get_all_configs() -> list[SourceConfig]` — returns config for every known source
  - [x] 1.7 Implement `save_configs(configs: list[SourceConfig])` — persists enabled/default state to config.json
  - [x] 1.8 Define `SOURCE_REGISTRY: list[dict]` — static list of all known sources with `name`, `needs_key`, `key_fields`, `env_var_names`, `is_local`

- [x] Task 2: Create `gui/source_preferences_dialog.py` — the dialog UI (AC: #1, #2, #3, #4)
  - [x] 2.1 Create `SourcePreferencesDialog(QDialog)` with vertical layout of source rows
  - [x] 2.2 Each source row: QCheckBox (enable/disable), source name label, status indicator (colored circle or icon), configuration area
  - [x] 2.3 For API-key sources: QLineEdit (masked input, echoMode=Password), "Test" QPushButton, status label (result of test)
  - [x] 2.4 For JLCPCB: database status label (downloaded/not downloaded/stale + file size + date), "Download" / "Refresh" button (reuse existing download logic from JLCPCBSource)
  - [x] 2.5 Default source: QComboBox at bottom populated with enabled source names, plus "None" option
  - [x] 2.6 Dialog buttons: OK / Cancel (QDialogButtonBox). OK saves all changes; Cancel discards
  - [x] 2.7 Status indicators: green (#C8FFC8) = configured, amber (#FFEBB4) = key missing, red (#FFC8C8) = key invalid. Same colour constants as verify_panel.py
  - [x] 2.8 "Test Connection" runs in background (QThread) to avoid blocking dialog. Shows spinner or "Testing..." while running

- [x] Task 3: Wire dialog into main_window.py (AC: #1, #6)
  - [x] 3.1 Enable the existing `_act_prefs` toolbar action (currently disabled with "not yet implemented" tooltip)
  - [x] 3.2 Connect `_act_prefs.triggered` to `_on_preferences()` method
  - [x] 3.3 Add "Preferences..." action to Tools menu (alongside existing "Backups...")
  - [x] 3.4 In `_on_preferences()`: open modal dialog, on accept: update SearchOrchestrator sources, update status bar sources label, update search bar source selector
  - [x] 3.5 On app startup: load saved source configs and register enabled sources with SearchOrchestrator (currently main_window hardcodes JLCPCBSource — replace with config-driven registration)

- [x] Task 4: Tests (AC: all)
  - [x] 4.1 `tests/core/test_source_config.py` — test SourceConfigManager: save/load configs, credential get/set with env var priority, config.json round-trip
  - [x] 4.2 `tests/gui/test_source_preferences_dialog.py` — test dialog construction, enable/disable toggle updates status, default source combo population
  - [x] 4.3 Update `tests/test_main_window_docks.py` if menu order changes (add Preferences to Tools menu)

## Dev Notes

### Architecture Compliance

- **core/GUI separation is paramount**: `core/source_config.py` has ZERO GUI imports. It handles config persistence and keyring. The dialog in `gui/` imports from `core/source_config.py` only.
- **Anti-pattern**: Never store API keys in `config.json` — use `keyring` with env var fallback (ADR-03). `config.json` stores only: `{sources: [{name, enabled, is_default}]}`.
- **`keyring` is already a declared dependency** (pyproject.toml) but not yet used in the codebase. This is its first use.

### Existing Code to Reuse — Do NOT Reinvent

- **`JLCPCBSource` database management**: `check_database_integrity()`, `check_for_update()`, `download_database()` in `core/sources.py` already handle download/refresh. The dialog should call these methods, not reimplement download logic.
- **`DataSource.name`, `.needs_key`, `.key_fields`, `.is_configured()`**: The ABC already defines these. The config manager should read these from the source classes.
- **`SearchOrchestrator.add_source()`**: Use this to register enabled sources. Currently main_window creates `JLCPCBSource()` directly and calls `add_source()` — replace with config-driven loop.
- **Status bar `_sources_label`**: Already exists in main_window and displays active sources. Update it after preferences change.
- **Colour constants**: GREEN=#C8FFC8, AMBER=#FFEBB4, RED=#FFC8C8 — currently in `verify_panel.py`. Consider extracting to a shared `gui/colours.py` or importing from verify_panel. Avoid duplicating.
- **BackupBrowserDialog** (from Story 5.5): Use as a reference for dialog pattern — modal QDialog, launched from Tools menu, with QThread worker for background operations.

### API Source Stubs

DigiKey, Mouser, and Octopart `DataSource` subclasses do **not exist yet**. For this story, the dialog should:
- List them as available sources in the registry (name, needs_key=True, key_fields)
- Allow enabling/disabling and API key entry
- "Test Connection" for these sources should show a placeholder message: "Source adapter not yet implemented — credentials saved for future use"
- Do NOT implement the actual search/get_part methods for these sources in this story

Source registry data:

| Source | needs_key | key_fields | env_vars |
|--------|-----------|------------|----------|
| JLCPCB | No | [] | — |
| DigiKey | Yes | ["client_id", "client_secret"] | KIPART_DIGIKEY_CLIENT_ID, KIPART_DIGIKEY_CLIENT_SECRET |
| Mouser | Yes | ["api_key"] | KIPART_MOUSER_API_KEY |
| Octopart | Yes | ["client_id", "client_secret"] | KIPART_NEXAR_CLIENT_ID, KIPART_NEXAR_CLIENT_SECRET |

### File Locations

| File | Action |
|------|--------|
| `src/kipart_search/core/source_config.py` | NEW — config model + keyring integration |
| `src/kipart_search/gui/source_preferences_dialog.py` | NEW — preferences dialog |
| `src/kipart_search/gui/main_window.py` | MODIFY — wire up Preferences action, config-driven source registration |
| `tests/core/test_source_config.py` | NEW — config manager tests |
| `tests/gui/test_source_preferences_dialog.py` | NEW — dialog tests |
| `tests/test_main_window_docks.py` | MODIFY — update menu order test if needed |

### Testing Standards

- pytest, no unittest classes
- Mock `keyring` calls in tests (do not touch real OS credential store)
- Mock API calls for "Test Connection" — return success/failure without network
- Use `tmp_path` fixture for config.json file I/O tests
- Use `qtbot` (pytest-qt) for dialog interaction tests
- Follow pattern from Story 5.5: 15-25 new tests expected

### QDialog Pattern (from UX spec)

- Modal dialog — blocks main window while open
- No nested dialogs — API key fields show inline, not in sub-dialogs
- Title: "Source Preferences"
- OK/Cancel buttons: right-aligned, primary button on right
- Changes only applied on OK — Cancel discards all edits
- No telemetry: dialog never contacts external servers on its own. Only "Test Connection" button sends a request, and only to the specific source being tested.

### Project Structure Notes

- Alignment with unified project structure: `core/source_config.py` follows the same `core/` pattern as `backup.py`, `cache.py`, `search.py`
- Config file at `~/.kipart-search/config.json` matches architecture spec (user data files section)
- Dialog follows `gui/*.py` flat structure — no subdirectories

### Previous Story Intelligence (Story 5.5)

- Dialog integration pattern: `BackupBrowserDialog` in `gui/backup_dialog.py` is a good reference for modal QDialog + QThread worker + menu integration
- Menu integration: Story 5.5 added "Backups..." to Tools menu. This story adds "Preferences..." to same menu.
- All 417 tests were passing after 5.5 — maintain this baseline
- Worker pattern: QThread subclass with Signals for async operations (used for Test Connection)

### Git Intelligence

Recent commits follow the pattern: "Add {feature} (Story X.Y)". Each story creates new modules in core/ and gui/, modifies main_window.py for integration, and adds dedicated test files.

### References

- [Source: _bmad-output/planning-artifacts/epics.md#Epic 6, Story 6.1]
- [Source: _bmad-output/planning-artifacts/architecture.md#ADR-03 Credential Storage]
- [Source: _bmad-output/planning-artifacts/ux-design-specification.md#Source Preferences Dialog]
- [Source: _bmad-output/planning-artifacts/ux-design-specification.md#Experience Mechanics, Section 0]
- [Source: _bmad-output/planning-artifacts/prd.md#FR32, NFR6, NFR7]
- [Source: _bmad-output/project-context.md#Critical Don't-Miss Rules]

## Dev Agent Record

### Agent Model Used

Claude Opus 4.6 (1M context)

### Debug Log References

- Fixed 2 GUI test failures: `isVisible()` returns False when dialog not shown; switched to `isHidden()` checks
- Renamed test class to avoid pytest collection warning from `TestConnectionWorker` in source

### Completion Notes List

- **Task 1**: Created `core/source_config.py` with `SourceConfig` dataclass, `SourceConfigManager` (config.json + keyring + env var), and `SOURCE_REGISTRY` for all 4 sources. Zero GUI imports — strict core/GUI separation maintained.
- **Task 2**: Created `gui/source_preferences_dialog.py` with modal `SourcePreferencesDialog`, per-source `_SourceRow` widgets (checkbox, status indicator, key inputs), `ConnectionTestWorker` QThread for background connection testing, default source QComboBox, and OK/Cancel button box.
- **Task 3**: Enabled `_act_prefs` toolbar action, connected to `_on_preferences()`, added "Preferences..." to Tools menu, created `_apply_source_configs()` for post-dialog source registration, and `_init_sources_from_config()` for config-driven startup replacing hardcoded JLCPCB init.
- **Task 4**: 26 core tests (config persistence, credential management, status computation, registry lookup) + 27 GUI tests (dialog construction, toggle, key inputs, status indicators, default combo, save flow, connection worker) + 1 existing test updated (`test_preferences_enabled`). All 470 tests pass.

### Change Log

- Story 6.1 implementation complete (Date: 2026-03-20)
- Code review fixes applied (Date: 2026-03-20): Fixed JLCPCB source not initialised when re-enabled via preferences after being disabled at startup; extracted `set_default_source()` public method on SearchBar to eliminate private attribute access; renamed `_compute_status` to `compute_status` (public API); renamed `TestConnectionWorker` to `ConnectionTestWorker` to eliminate pytest collection warning.

### File List

- `src/kipart_search/core/source_config.py` — NEW
- `src/kipart_search/gui/source_preferences_dialog.py` — NEW
- `src/kipart_search/gui/main_window.py` — MODIFIED
- `src/kipart_search/gui/search_bar.py` — MODIFIED (added `set_default_source()` public method)
- `tests/core/test_source_config.py` — NEW
- `tests/gui/test_source_preferences_dialog.py` — NEW
- `tests/test_main_window_docks.py` — MODIFIED
