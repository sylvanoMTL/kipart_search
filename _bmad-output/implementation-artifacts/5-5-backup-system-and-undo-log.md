# Story 5.5: Backup System and Undo Log

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a designer,
I want automatic backups before any write session and a persistent undo log,
so that I can always recover if something goes wrong, even beyond KiCad's undo stack.

## Acceptance Criteria

1. **Silent Pre-Session Backup** (UX-DR17)
   **Given** the designer is about to confirm the first write-back of a session (connected mode)
   **When** the write-back is initiated
   **Then** a silent timestamped backup is created at `~/.kipart-search/backups/{project}/{YYYY-MM-DD_HHMM}/` before any fields are written
   **And** subsequent writes in the same session do not create additional backups (one backup per session)
   **And** no user action is required — backups are automatic and silent

2. **Persistent Undo Log** (UX-DR17)
   **Given** any write-back is performed (connected or standalone)
   **When** the field change is committed
   **Then** an entry is appended to an undo log CSV file: timestamp, reference, field name, old value, new value
   **And** the undo log persists across application sessions

3. **Backup Browser and Restore**
   **Given** the designer wants to view or restore from a backup
   **When** they access the backup browser (via menu)
   **Then** a list of available backups is shown with project name and timestamp
   **And** the designer can restore any previous backup

## Tasks / Subtasks

- [x] Task 1: Create `core/backup.py` — backup and undo log engine (AC: #1, #2)
  - [x] 1.1 Create `BackupManager` class with `backup_dir: Path` (defaults to `~/.kipart-search/backups/`)
  - [x] 1.2 Implement `ensure_session_backup(project_name: str, components: list[BoardComponent]) -> Path` — creates timestamped snapshot on first call per session, returns backup dir. Second call returns same dir without re-creating.
  - [x] 1.3 Snapshot format: JSON file `components.json` containing `[{reference, mpn, datasheet, extra_fields}]` for all components. Use `dataclasses.asdict()` + `json.dumps()`.
  - [x] 1.4 Implement `log_field_change(project_name: str, reference: str, field_name: str, old_value: str, new_value: str)` — appends one row to `undo_log.csv` inside the session backup dir.
  - [x] 1.5 CSV columns: `timestamp, reference, field, old_value, new_value` (header row written on file creation)
  - [x] 1.6 Implement `list_backups(project_name: str) -> list[BackupEntry]` — returns available backups sorted newest-first. `BackupEntry` is a dataclass: `path, project, timestamp, component_count, change_count`.
  - [x] 1.7 Implement `load_backup(backup_path: Path) -> list[dict]` — reads `components.json` from a backup dir.
  - [x] 1.8 Implement `reset_session()` — clears the session state so next write triggers a new backup.

- [x] Task 2: Integrate backup into `_apply_assignment()` in `main_window.py` (AC: #1, #2)
  - [x] 2.1 Add `self._backup_manager: BackupManager | None` initialized in `__init__` (lazy, created on first connected write)
  - [x] 2.2 Before the write loop in `_apply_assignment()` (connected mode only): call `self._backup_manager.ensure_session_backup(project_name, components)` where `project_name` comes from KiCad board filename or "standalone" fallback
  - [x] 2.3 After each successful `bridge.write_field()`: call `self._backup_manager.log_field_change(project_name, ref, field_name, old_value, new_value)` — old_value comes from the component's current state before write
  - [x] 2.4 In standalone mode: still log field changes (undo log), but skip the component snapshot (no KiCad files to back up)
  - [x] 2.5 Call `self._backup_manager.reset_session()` on new KiCad connection (re-scan) so a fresh backup is created for the new session

- [x] Task 3: Build backup browser dialog `gui/backup_dialog.py` (AC: #3)
  - [x] 3.1 Create `BackupBrowserDialog(QDialog)` with a `QTableWidget` listing backups: Project, Timestamp, Components, Changes
  - [x] 3.2 "View Details" button: opens the undo log CSV for the selected backup (read-only `QTextEdit` or table)
  - [x] 3.3 "Restore" button: loads `components.json` and writes all fields back to KiCad via `bridge.write_field()` with `allow_overwrite=True`. Show confirmation dialog first: "Restore {N} components to state from {timestamp}?"
  - [x] 3.4 Restore creates a NEW backup before overwriting (safety net: backup before restore)
  - [x] 3.5 Add "Backups..." menu item under a "Tools" menu in main_window.py

- [x] Task 4: Write tests (AC: #1, #2, #3)
  - [x] 4.1 Test `BackupManager.ensure_session_backup()`: first call creates dir + components.json, second call returns same path
  - [x] 4.2 Test `BackupManager.log_field_change()`: appends row to CSV with correct columns
  - [x] 4.3 Test `BackupManager.list_backups()`: returns sorted list, newest first
  - [x] 4.4 Test `BackupManager.load_backup()`: reads components.json correctly
  - [x] 4.5 Test `BackupManager.reset_session()`: next ensure_session_backup creates a new dir
  - [x] 4.6 Test integration: `_apply_assignment()` calls backup before write and logs after
  - [x] 4.7 Test standalone mode: undo log written but no component snapshot
  - [x] 4.8 Test `BackupBrowserDialog`: lists backups, restore triggers write-back with `allow_overwrite=True`
  - [x] 4.9 Test edge cases: empty backup dir, corrupted components.json, missing CSV

## Dev Notes

### What Already Exists — Extend, Don't Reinvent

The write-back flow is **fully implemented** in Stories 5.1–5.4. This story adds a non-intrusive backup/logging layer around the existing write path. The key integration point is `MainWindow._apply_assignment()` at [main_window.py:780-869](src/kipart_search/gui/main_window.py#L780-L869).

**Existing code you MUST reuse:**
- `KiCadBridge.get_components()` — reads all current component state (use for snapshot)
- `KiCadBridge.write_field(ref, field, value, allow_overwrite=True)` — used for restore
- `_apply_assignment()` — the ONLY place where writes happen; insert backup hooks here
- `BoardComponent` dataclass in `core/models.py` — the data model for component state
- `self._bridge.is_connected` — gate backup creation (only in connected mode)

**Existing pattern for atomic file operations** (in `core/sources.py` JLCPCB download):
```python
# Atomic swap pattern — backup old, move new, clean up
backup_db = target_dir / "parts-fts5.db.bak"
db_file.rename(backup_db)
# ... on failure: backup_db.rename(db_file)
```

### Key Files to Modify

| File | Change |
|------|--------|
| `src/kipart_search/core/backup.py` | **NEW** — `BackupManager` class, `BackupEntry` dataclass |
| `src/kipart_search/gui/main_window.py` | Hook backup into `_apply_assignment()`, add menu item, `_backup_manager` attribute |
| `src/kipart_search/gui/backup_dialog.py` | **NEW** — `BackupBrowserDialog` with table, view, restore |
| `tests/core/test_backup.py` | **NEW** — BackupManager unit tests |
| `tests/gui/test_backup_dialog.py` | **NEW** — BackupBrowserDialog tests |

### Architecture Constraints

1. **`core/backup.py` has ZERO GUI imports** — it's a core module. Uses only `pathlib`, `json`, `csv`, `time`, `dataclasses` from stdlib. No PySide6.

2. **`gui/backup_dialog.py` handles all Qt code** — the dialog, table widget, restore confirmation. It calls `BackupManager` methods from core.

3. **Never modify `.kicad_sch` or `.kicad_pcb` files directly** — restore uses `KiCadBridge.write_field()` via IPC API, same as normal assignment.

4. **Backup is silent** — no dialogs, no user prompts during backup creation. The UX spec says: "Safety is silent until needed". Log to log_panel only.

5. **One backup per session** — a "session" starts on first write after app launch or after `reset_session()` (which should be called on re-scan). Use a `_session_backup_dir: Path | None` flag.

6. **Undo log in both modes** — standalone mode logs field changes too (useful for audit), but skips the component snapshot (no KiCad project to restore to).

### Design Details

**Backup directory structure:**
```
~/.kipart-search/backups/
└── {project_name}/
    └── 2026-03-19_1430/
        ├── components.json    # Full component state snapshot
        └── undo_log.csv       # Per-field change log
```

**`components.json` format** (JSON array of objects):
```json
[
  {
    "reference": "C12",
    "value": "100nF",
    "footprint": "C_0805_2012Metric",
    "mpn": "GRM21BR71C104KA01L",
    "datasheet": "https://...",
    "extra_fields": {"manufacturer": "Murata", "lcsc": "C12345"}
  }
]
```

**`undo_log.csv` format:**
```csv
timestamp,reference,field,old_value,new_value
2026-03-19T14:30:15,C12,MPN,,GRM21BR71C104KA01L
2026-03-19T14:30:15,C12,Manufacturer,,Murata
2026-03-19T14:31:02,R7,MPN,RC0805FR-0710KL,ERJ-6ENF1002V
```

**Integration into `_apply_assignment()`** — insert BEFORE the write loop:
```python
# Before writes — ensure session backup exists (connected mode)
if self._bridge.is_connected:
    project = self._get_project_name()  # from board filename
    components = self.verify_panel.get_components()
    self._backup_manager.ensure_session_backup(project, components)
```

**Insert AFTER each successful write:**
```python
if ok:
    written += 1
    # Log the change to undo CSV
    old = comp.extra_fields.get(field_name.lower(), "") if field_name != "MPN" else comp.mpn
    self._backup_manager.log_field_change(project, ref, field_name, old, value)
```

**Getting old_value** — must read BEFORE writing:
- For MPN: `comp.mpn` (from the in-memory `BoardComponent`)
- For datasheet: `comp.datasheet`
- For other fields: `comp.extra_fields.get(field_name.lower(), "")`

This is safe because `_apply_assignment()` updates in-memory state AFTER the write loop, not during it. So `comp.mpn` still holds the old value during the loop.

**Getting project name:**
```python
def _get_project_name(self) -> str:
    """Extract project name from KiCad board or fallback."""
    if self._bridge.is_connected and self._bridge._board:
        try:
            # kicad-python board may expose filename
            return Path(str(self._bridge._board)).stem
        except Exception:
            pass
    return "standalone"
```
If board filename isn't accessible via kipy API, fall back to "unknown-project". Investigate `self._bridge._board` attributes at implementation time.

**Restore flow:**
1. User opens Tools → Backups...
2. `BackupBrowserDialog` lists available backups via `BackupManager.list_backups()`
3. User selects a backup and clicks "Restore"
4. Confirmation dialog: "This will overwrite current component fields with values from {timestamp}. A new backup will be created first. Continue?"
5. On confirm: `ensure_session_backup()` first (safety net), then loop `load_backup()` results and call `bridge.write_field(ref, field, value, allow_overwrite=True)` for each field
6. Log all restore actions to log_panel

**`reset_session()` call points:**
- After `_on_scan_complete()` in main_window.py (when KiCad board is re-scanned)
- The idea: each scan starts a new "session", so the next write creates a fresh backup

### Existing Code Patterns to Follow

**File paths** — use `pathlib.Path` everywhere, never string concatenation:
```python
from pathlib import Path
backup_dir = Path.home() / ".kipart-search" / "backups" / project / timestamp
backup_dir.mkdir(parents=True, exist_ok=True)
```

**JSON serialization** — use `json.dumps()`/`json.loads()`, not pickle:
```python
import json
from dataclasses import asdict
data = [asdict(comp) for comp in components]
(backup_dir / "components.json").write_text(json.dumps(data, indent=2))
```

**CSV writing** — use stdlib `csv` module:
```python
import csv
with open(csv_path, "a", newline="") as f:
    writer = csv.writer(f)
    if csv_path.stat().st_size == 0:
        writer.writerow(["timestamp", "reference", "field", "old_value", "new_value"])
    writer.writerow([timestamp, reference, field, old_value, new_value])
```

**Logging** — `logging.getLogger(__name__)` at module level, never `print()`.

**Imports** — every file starts with `from __future__ import annotations`.

**Testing** — pytest with `tmp_path` fixture for file operations, `MagicMock` for kipy. Run via `.env/Scripts/python.exe -m pytest tests/`.

### Previous Story Intelligence (5.4)

Story 5.4 established these patterns that 5.5 must follow:
- `_apply_assignment()` accepts `fields: dict[str, str]` and `overwrite_fields: set[str]`
- Per-field try/except with `failed: list[tuple[str, str]]` for error collection
- `written` counter tracks successful writes; `mpn_written` flag gates GREEN status
- In-memory `comp` update happens AFTER the write loop (so old values are available during writes)
- `allow_overwrite=True` on `write_field()` is needed for restore operations
- 47 tests in `tests/gui/test_assign_dialog.py` — do NOT break these
- Total project test count: 395

### What This Story Does NOT Include

- **Automatic backup pruning/cleanup** — old backups accumulate. Manual deletion for now.
- **Selective per-field undo** — the undo log is for audit/manual recovery. No "undo last write" button.
- **Batch restore** — restore replaces ALL fields from the snapshot. No selective component restore.
- **Backup compression** — JSON files are small enough for typical boards (~70 components).
- **Standalone mode backup** — no component snapshot in standalone (no KiCad project to restore to), only undo log.

### Project Structure Notes

- `core/backup.py` is a NEW file in the core package — zero GUI imports, importable by CLI/tests
- `gui/backup_dialog.py` is a NEW file in the gui package — PySide6 dialog
- Both follow existing naming conventions: `snake_case` files, `PascalCase` classes
- `BackupEntry` dataclass goes in `core/backup.py` (not `core/models.py`) to keep it co-located with the manager
- `tests/core/test_backup.py` and `tests/gui/test_backup_dialog.py` are NEW test files

### References

- [Source: _bmad-output/planning-artifacts/epics.md#Story 5.5] — acceptance criteria, BDD scenarios
- [Source: _bmad-output/planning-artifacts/ux-design-specification.md#Safety & Reversibility] — silent timestamped backups, undo log as CSV, backup browser, cancel/revert
- [Source: _bmad-output/planning-artifacts/architecture.md#User Data Files] — `~/.kipart-search/backups/` directory structure
- [Source: _bmad-output/planning-artifacts/architecture.md#Anti-Patterns] — use `pathlib.Path`, `json.dumps()` not pickle, never modify .kicad_sch directly
- [Source: _bmad-output/planning-artifacts/architecture.md#Architectural Boundaries] — core/ has zero GUI deps, gui/ depends on core/
- [Source: src/kipart_search/gui/main_window.py#L780-L869] — `_apply_assignment()` integration point
- [Source: src/kipart_search/gui/kicad_bridge.py#L183-L226] — `write_field()` with `allow_overwrite` parameter
- [Source: src/kipart_search/gui/kicad_bridge.py#L104-L160] — `get_components()` for snapshot data
- [Source: src/kipart_search/core/models.py] — `BoardComponent` dataclass
- [Source: _bmad-output/implementation-artifacts/5-4-write-back-safety-guards.md] — previous story patterns, file list, test approach

## Dev Agent Record

### Agent Model Used

Claude Opus 4.6 (1M context)

### Debug Log References

- Existing tests using `MainWindow.__new__()` skip `__init__`, causing `_backup_manager` AttributeError → fixed with `getattr()` fallback in `_ensure_backup_manager()`
- `MagicMock(spec=KiCadBridge)` blocks access to private `_board` attr → fixed `_get_project_name()` to use `getattr()` instead of direct attribute access
- Menu order test expected `["File", "View", "Help"]` → updated to include new "Tools" menu

### Completion Notes List

- Created `BackupManager` class in `core/backup.py` with zero GUI dependencies (stdlib only: json, csv, pathlib, dataclasses)
- Implemented one-backup-per-session semantics via `_session_backup_dir` flag, cleared by `reset_session()`
- Standalone mode writes undo log to `{backup_dir}/{project}/standalone/` (no component snapshot)
- Connected mode creates timestamped snapshot at `~/.kipart-search/backups/{project}/{YYYY-MM-DD_HHMM}/components.json`
- Integrated backup hooks into `_apply_assignment()`: pre-write backup (connected), per-field undo logging (both modes)
- Old values captured from in-memory `BoardComponent` before write loop (safe because in-memory update happens after writes)
- Added `reset_session()` call in `_on_scan_complete()` so each scan starts a fresh session
- Built `BackupBrowserDialog` with table listing, undo log viewer, and restore with confirmation + safety-net backup
- Restore uses `bridge.write_field(allow_overwrite=True)` via IPC API (never modifies KiCad files directly)
- Added "Tools" menu with "Backups..." item
- 22 new tests (14 core + 8 GUI/integration), all passing. Full suite: 417 tests, 0 regressions.

### Change Log

- 2026-03-19: Implemented Story 5.5 — backup system and undo log (all 4 tasks, 22 new tests)
- 2026-03-20: Code review — 2 fixes applied: extracted `get_project_name()` public method on KiCadBridge (was accessing private `_board`), strengthened `test_reset_creates_new_backup` assertions

### File List

**New files:**
- src/kipart_search/core/backup.py
- src/kipart_search/gui/backup_dialog.py
- tests/core/test_backup.py
- tests/gui/test_backup_dialog.py

**Modified files:**
- src/kipart_search/gui/main_window.py (backup integration, Tools menu, _get_project_name, _ensure_backup_manager, _on_restore_backup)
- src/kipart_search/gui/kicad_bridge.py (added `get_project_name()` public method)
- tests/test_main_window_docks.py (updated menu order test to include "Tools")
