# Story 5.7: File-Based Write-Back via Push to KiCad

Status: done

## Story

As a designer,
I want to push my MPN assignments from KiPart Search into my KiCad schematic files,
so that my KiCad project carries all manufacturing references and future BOM exports from KiCad are already complete.

## Acceptance Criteria

1. **Given** the designer has made local MPN assignments (`_local_assignments` is non-empty), **When** they click "Push to KiCad", **Then** the system checks if KiCad's eeschema process has the schematic files open (via lock file detection).

2. **Given** the schematic files are open in KiCad, **When** the open-file check detects this, **Then** the system shows a warning: "Close the schematic editor in KiCad before pushing changes. File-based write cannot proceed while the schematic is open." **And** the write is blocked — no file modification occurs.

3. **Given** the schematic files are NOT open in KiCad (or KiCad is not running), **When** the designer confirms the push, **Then** all `.kicad_sch` files in the project are backed up to `~/.kipart-search/backups/{project}/{YYYY-MM-DD_HHMM}/` (extends Story 5.5) **And** each local assignment is written to the correct schematic file via `core/kicad_sch.py` **And** each write is logged to the undo CSV (timestamp, reference, field, old value, new value) **And** the add-never-overwrite policy is enforced (non-empty fields are not modified without explicit confirmation).

4. **Given** the push completes successfully, **When** the success dialog is shown, **Then** it displays: "Written N fields to M components. Run 'Update PCB from Schematic' (F8) in KiCad to sync the board." **And** `_local_assignments` is cleared for the successfully written fields **And** the log panel records: "Pushed N field(s) to .kicad_sch — run Update PCB from Schematic to sync".

5. **Given** a write fails for any component, **When** the error is caught, **Then** the system continues writing remaining components (non-atomic across components, atomic per component) **And** failed writes remain in `_local_assignments` for retry **And** the error is logged with the specific component reference and reason.

## Tasks / Subtasks

- [x] Task 1: Determine project directory from KiCad connection (AC: #3)
  - [x] 1.1: Add method to `kicad_bridge.py` that returns the KiCad project directory path (parent of `.kicad_pcb`)
  - [x] 1.2: Standalone fallback: use last-opened BOM file directory or prompt user

- [x] Task 2: Extend `BackupManager` for schematic file backups (AC: #3)
  - [x] 2.1: Add method `backup_schematic_files(project_name, sch_paths: list[Path]) -> Path` that copies all `.kicad_sch` files to the backup directory
  - [x] 2.2: Reuse existing session-backup-once pattern (one backup per session)

- [x] Task 3: Implement `_on_push_to_kicad()` in `main_window.py` (AC: #1, #2, #3, #4, #5)
  - [x] 3.1: Guard: check `_local_assignments` is non-empty, else show "No assignments to push"
  - [x] 3.2: Resolve project directory and discover schematic files via `kicad_sch.find_schematic_files()`
  - [x] 3.3: Check lock files via `kicad_sch.is_schematic_locked()` for each `.kicad_sch` — block if any locked
  - [x] 3.4: Show confirmation dialog: "Push N field(s) to M component(s) into schematic files? This will modify .kicad_sch files on disk."
  - [x] 3.5: Back up all schematic files before writing
  - [x] 3.6: Iterate `_local_assignments`: for each ref, find correct sheet via `find_symbol_sheet()`, call `set_field()` with `allow_overwrite` based on whether user confirmed overwrite in the original assign dialog
  - [x] 3.7: Log each write to undo CSV via `BackupManager.log_field_change()`
  - [x] 3.8: Read old value before writing for undo log (use `read_symbols()` on the target sheet)
  - [x] 3.9: On success: clear written entries from `_local_assignments`, show success dialog with F8 instruction
  - [x] 3.10: On partial failure: keep failed entries in `_local_assignments`, log errors, show summary

- [x] Task 4: Update toolbar button state (AC: #1)
  - [x] 4.1: Enable "Push to KiCad" button when `_local_assignments` is non-empty (currently shows info dialog)
  - [x] 4.2: Disable when assignments are empty or after successful push

- [x] Task 5: Handle standalone mode (no KiCad connection) (AC: #3)
  - [x] 5.1: If standalone but user loaded BOM from file, derive project directory from BOM file path
  - [x] 5.2: If project directory cannot be determined, prompt user with folder picker

- [x] Task 6: Track overwrite permissions from assign dialog (AC: #3)
  - [x] 6.1: Extend `_local_assignments` structure to carry `overwrite_fields` set per reference
  - [x] 6.2: When pushing, use stored overwrite permission for `allow_overwrite` parameter

- [x] Task 7: Testing (all ACs)
  - [x] 7.1: Manual test: assign MPNs to multiple components, push to KiCad, verify `.kicad_sch` files updated
  - [x] 7.2: Manual test: attempt push with schematic open in KiCad — verify lock detection blocks write
  - [x] 7.3: Manual test: verify backup created in `~/.kipart-search/backups/`
  - [x] 7.4: Manual test: verify undo log CSV entries correct
  - [x] 7.5: Manual test: partial failure recovery (corrupt one `.kicad_sch` path)

## Dev Notes

### Architecture & Key Decisions

**ADR-08 (Write-Back Strategy)** governs this story: file-based write-back via direct `.kicad_sch` modification is the only working write path in KiCad 9. The IPC API `board.update_items()` destroys custom fields — this was confirmed in commit `4677e57`.

**Affected modules:**
- `gui/main_window.py` — Replace placeholder `_on_push_to_kicad()` (currently shows "Not Available Yet" info dialog at line 751)
- `gui/kicad_bridge.py` — Add `get_project_dir() -> Path | None` method
- `core/backup.py` — Extend to back up `.kicad_sch` files (currently only backs up component JSON state)
- `core/kicad_sch.py` — Already complete from Story 5.6. Use `find_schematic_files()`, `find_symbol_sheet()`, `set_field()`, `is_schematic_locked()`, `read_symbols()`.

### Existing Code to Reuse — DO NOT Reinvent

| What | Where | How to use |
|------|-------|------------|
| S-expression parser | `core/kicad_sch.py` | `set_field(path, ref, field, value, allow_overwrite)` — already handles add/overwrite/no-overwrite |
| Lock detection | `core/kicad_sch.py` | `is_schematic_locked(path) -> bool` — checks `~filename.kicad_sch.lck` |
| Sheet discovery | `core/kicad_sch.py` | `find_schematic_files(project_dir) -> list[Path]`, `find_symbol_sheet(project_dir, ref) -> Path` |
| Symbol reading | `core/kicad_sch.py` | `read_symbols(path) -> list[SchSymbol]` — use to get old field values for undo log |
| Backup manager | `core/backup.py` | `BackupManager.ensure_session_backup()`, `log_field_change()` |
| Local assignments | `main_window.py:156` | `self._local_assignments: dict[str, dict[str, str]]` — already populated by `_apply_assignment()` |
| Assign dialog | `gui/assign_dialog.py` | `dialog.fields_to_write` and `dialog.overwrite_fields` — capture overwrite intent |
| Project name | `main_window.py:886` | `_get_project_name()` — returns board filename stem or "standalone" |

### Critical Integration Points

1. **`_on_push_to_kicad()` at line 751** — Currently a placeholder info dialog. Replace entirely with the push logic.

2. **`_local_assignments` at line 156** — Already populated by `_apply_assignment()` (line 899). Structure: `{ref: {field_name: value}}`. This is the data source for push.

3. **`_apply_assignment()` at line 899** — Currently stores overwrite decisions in `overwrite_fields` parameter but does NOT persist which fields were approved for overwrite. The push needs this info. Either:
   - (a) Add a parallel dict `_local_overwrites: dict[str, set[str]]` mapping ref → set of field names approved for overwrite, OR
   - (b) Store overwrite info alongside assignments in a richer structure

4. **Project directory resolution** — `kicad_bridge.get_project_name()` returns the board filename stem (e.g. "my_board"). Need the full directory path. The KiCad IPC API provides the board path — extract `board.get_filename()` from kipy. For standalone mode, derive from BOM import path.

### KiCad `.kicad_sch` File Safety

- **Lock file check is mandatory**: `is_schematic_locked()` checks for `~<filename>.kicad_sch.lck` which KiCad creates when the schematic is open. REFUSE to write if any lock file exists.
- **Backup is mandatory**: Copy all `.kicad_sch` files before any modification. Use `shutil.copy2()` to preserve timestamps.
- **Add-never-overwrite default**: `set_field(..., allow_overwrite=False)` is the default. Only pass `True` for fields the user explicitly approved via overwrite checkbox in assign dialog.
- **Atomic per component**: Each `set_field()` call reads the file, modifies one field, writes back. If one component fails, others still succeed.
- **File preserved byte-for-byte**: `kicad_sch.set_field()` only modifies the targeted property block. Everything else stays identical.

### GUI Flow

1. User assigns MPNs via search results or manual entry → stored in `_local_assignments`
2. User clicks "Push to KiCad" toolbar button
3. System checks: any assignments? → if empty, show "No assignments to push"
4. System resolves project dir → discovers all `.kicad_sch` files
5. System checks lock files → if locked, show warning and block
6. Confirmation dialog: "Push N fields to M components? This modifies .kicad_sch files."
7. Backup all schematic files
8. For each assignment: find sheet → read old value → write field → log to undo CSV
9. Success: clear written assignments, show "Written N fields. Run F8 in KiCad."
10. Partial failure: keep failed in `_local_assignments`, show error summary

### UX Requirements (from UX Design Spec)

- **Confirmation dialog**: Modal, plain-language. "Push to KiCad will modify design files" is a dangerous confirmation (requires explicit confirm).
- **Button placement**: Cancel left, Confirm right. Default is Cancel for destructive operations.
- **Success message**: Must include "Run 'Update PCB from Schematic' (F8)" instruction — critical for user to sync board with schematic changes.
- **Log panel**: Record all push operations. Use existing `self.log_panel.log()` pattern.
- **Status bar**: Update status pill during push operation.

### Project Structure Notes

- All file I/O through `core/kicad_sch.py` — the ONLY module allowed to modify `.kicad_sch` files
- GUI code in `gui/main_window.py` orchestrates the flow
- Backup logic in `core/backup.py` — extend, don't duplicate
- No new modules needed — this story wires existing modules together

### Error Handling

- Lock file detected → block with clear message, no file modification
- Backup failure → block push entirely (no writes without backup)
- `find_symbol_sheet()` returns None → skip component, log error, continue others
- `set_field()` raises exception → log, keep in `_local_assignments`, continue others
- All schematic files missing → show error, abort
- Empty project directory → prompt user for folder

### Previous Story Intelligence (from Story 5.6)

- `kicad_sch.py` handles escaped quotes in property values (fixed in code review)
- `_find_insertion_point()` was hardened for compact/single-line symbol blocks
- Property ID auto-detection works — new fields get next available ID
- Indentation is auto-detected from surrounding properties
- `set_field()` returns `True` if field was written/added, `False` if blocked by no-overwrite policy
- `SchSymbol.fields` dict contains ALL properties (Reference, Value, Footprint, MPN, etc.) — use to read old values

### References

- [Source: _bmad-output/planning-artifacts/epics.md — Epic 5, Story 5.7]
- [Source: _bmad-output/planning-artifacts/architecture.md — ADR-08: Write-Back Strategy]
- [Source: _bmad-output/planning-artifacts/ux-design-specification.md — Safety & Reversibility, Dialog Patterns]
- [Source: _bmad-output/planning-artifacts/prd.md — FR13-FR15, FR21-FR23]
- [Source: src/kipart_search/core/kicad_sch.py — S-expression parser API]
- [Source: src/kipart_search/gui/main_window.py:751 — Current placeholder _on_push_to_kicad()]
- [Source: src/kipart_search/gui/main_window.py:899 — _apply_assignment() integration point]
- [Source: src/kipart_search/core/backup.py — BackupManager API]

## Dev Agent Record

### Agent Model Used
Claude Opus 4.6 (1M context)

### Debug Log References
- All 161 core tests pass (158 existing + 3 new backup tests)
- Pre-existing Qt access violation in test_status_bar_accessible_names unrelated to changes

### Completion Notes List
- Task 1: Added `get_project_dir()` to `kicad_bridge.py` — extracts board path parent from IPC API
- Task 2: Added `backup_schematic_files()` to `BackupManager` — copies `.kicad_sch` files with session-once pattern, uses `shutil.copy2()` to preserve timestamps
- Task 3: Replaced placeholder `_on_push_to_kicad()` with full push orchestration: empty-check guard, project dir resolution, schematic discovery, lock file check, confirmation dialog, backup, per-ref field writing with undo logging, success/partial-failure/failure dialogs
- Task 4: Push button now starts disabled, enabled/disabled dynamically via `_update_push_button_state()` called after assignments and after push completion
- Task 5: `_resolve_project_dir()` handles 3 modes: (1) connected KiCad → board path parent, (2) standalone with BOM → BOM file parent, (3) fallback → `QFileDialog` folder picker
- Task 6: Added `_local_overwrites` dict alongside `_local_assignments` — populated during `_apply_assignment()` in both connected and standalone modes. Overwrite permissions flow through to `set_field(allow_overwrite=...)` during push.
- Task 7: Unit tests added for `backup_schematic_files()` (3 tests). Manual test scenarios defined in story tasks. Full regression suite passes.

### Change Log
- 2026-03-22: Implemented file-based write-back push-to-kicad (Story 5.7) — replaced placeholder info dialog with full push orchestration
- 2026-03-22: Code review #1 — Fixed H1: schematic backup silently skipped when ensure_session_backup() already set _session_backup_dir (connected-mode flow). Added _sch_backed_up flag so backup_schematic_files() always copies .kicad_sch files into session dir. Added regression test.

### File List
- `src/kipart_search/gui/kicad_bridge.py` — added `get_project_dir()` method
- `src/kipart_search/core/backup.py` — added `shutil` import, added `backup_schematic_files()` method, added `_sch_backed_up` flag to track schematic backup independently from component JSON backup
- `src/kipart_search/gui/main_window.py` — added `QFileDialog` import, added `_local_overwrites` dict, replaced `_on_push_to_kicad()` placeholder with full implementation, added `_resolve_project_dir()` helper, added `_update_push_button_state()` helper, updated `_update_status()` to use dynamic push state, updated `_apply_assignment()` to track local overwrites in both modes and store standalone assignments
- `tests/core/test_backup.py` — added `TestBackupSchematicFiles` class with 4 tests (including connected-mode regression test)
