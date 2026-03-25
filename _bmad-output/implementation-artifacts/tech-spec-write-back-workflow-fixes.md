---
title: 'Write-back Workflow Fixes'
slug: 'write-back-workflow-fixes'
created: '2026-03-25'
status: 'implementation-complete'
stepsCompleted: [1, 2, 3, 4]
tech_stack: ['Python 3.10+', 'PySide6']
files_to_modify: ['src/kipart_search/gui/main_window.py', 'src/kipart_search/core/backup.py', 'src/kipart_search/gui/verify_panel.py']
code_patterns: ['QThread scan worker', 'signal/slot for scan results', 'BoardComponent dataclass']
test_patterns: []
---

# Tech-Spec: Write-back Workflow Fixes

**Created:** 2026-03-25

## Overview

### Problem Statement

The write-back → re-verify cycle is broken in three ways:

1. **Verification state lost on re-scan**: After Push to KiCad → re-scan, all verified parts show "Need attention" with 0% verification. Root cause: `ScanWorker` creates fresh `BoardComponent` objects each scan, and the `mpn_statuses` dict is local to each worker run — never persisted on MainWindow.

2. **Folder selection dialog appears unnecessarily**: `_resolve_project_dir()` has a 3-level fallback (KiCad → BOM path → user picker), but in connected mode the picker still appears because `bridge.get_project_dir()` returns None in some cases after push.

3. **Backup location is user-scoped, not project-scoped**: Backups go to `~/.kipart-search/backups/` which is disconnected from the KiCad project. Users expect backups alongside their project files.

### Solution

1. Cache `mpn_statuses` dict on MainWindow; restore on re-scan by matching reference + MPN
2. Fix folder auto-detect to use the board path captured during the last successful scan
3. Move backup directory to `{kicad_project}/.kipart-search/backups/`

### Scope

**In Scope:**
- Persist mpn_statuses across re-scans on MainWindow
- Fix _resolve_project_dir() to use cached project path from last scan
- Relocate backup directory to project-scoped path
- Show confirmation instead of picker when project dir is auto-detected

**Out of Scope:**
- Undo/restore rework
- Schematic parser changes
- Verification logic changes (what constitutes verified vs need attention)

## Context for Development

### Codebase Patterns

- Scan runs in `ScanWorker(QThread)` — emits `scan_complete(components, mpn_statuses, db_mtime)` signal
- `_on_scan_complete()` receives results, passes to verify_panel via `set_results()`
- `_local_assignments` dict persists unsaved field assignments across scans (pattern to follow for mpn_statuses)
- `_resolve_project_dir()` has 3-level fallback: KiCad bridge → BOM path → user picker
- `BackupManager` takes `backup_dir` in constructor, defaults to `~/.kipart-search/backups/`
- After successful push, `_local_assignments` entries are removed for written fields (line 1008-1013)
- `verify_panel.set_results()` takes `(components, mpn_statuses, has_sources, db_mtime=)` and renders the full table
- `VERIFY_COLUMNS` list at line 69 defines table columns: `["Reference", "Value", "MPN", "MPN Status", "Freshness", "Footprint"]`

### Files to Reference

| File | Purpose | Key Lines |
| ---- | ------- | --------- |
| `src/kipart_search/gui/main_window.py` | Scan orchestration, state management, push-to-kicad flow | `ScanWorker.run()` L95-142, `_on_scan_complete()` L795-858, `_on_push_to_kicad()` L867-1072, `_resolve_project_dir()` L1074-1104 |
| `src/kipart_search/core/backup.py` | BackupManager class, backup directory logic | `__init__` L35-36, `ensure_session_backup` L42-71, `backup_schematic_files` L73-121 |
| `src/kipart_search/gui/kicad_bridge.py` | get_project_dir(), get_components() | `get_project_dir()` L117-132, `get_components()` L134-190 |
| `src/kipart_search/gui/verify_panel.py` | set_results(), verification percentage, freshness column | `VERIFY_COLUMNS` L69, `set_results()` L186-337, `_make_freshness_item()` L339-364 |

### Technical Decisions

- **State persistence approach**: Simple dict on MainWindow (`self._cached_mpn_statuses`) keyed by `(reference, mpn)` tuple — no database, no file. Cleared on app close. This is sufficient because re-scan re-verifies MPNs anyway; we just need to avoid losing status when the same MPN is still present after push.
- **Project dir caching**: Store `self._project_dir` on MainWindow after first successful resolution. Reuse on subsequent push operations without re-prompting. Reset when KiCad connection changes.
- **Backup location**: `{project_dir}/.kipart-search/backups/{timestamp}/` — created on first push. Falls back to `~/.kipart-search/backups/` when project_dir is None (standalone mode). The `.kipart-search` folder follows the convention of tool-specific hidden directories in project roots.
- **Freshness column removal**: Remove from `VERIFY_COLUMNS`, delete `_make_freshness_item()`, remove all `freshness_col` references and stale-related display logic. Keep `is_stale()` in models.py (it's not GUI code).

## Implementation Plan

### Tasks

- [x] Task 1: Cache mpn_statuses on MainWindow across re-scans
  - File: `src/kipart_search/gui/main_window.py`
  - Action: Add `self._cached_mpn_statuses: dict[str, Confidence] = {}` in `__init__`. In `_on_scan_complete()`, after the local-assignments restore block (line 817), add a second restore block: for each component where `mpn_statuses[ref]` is RED but `self._cached_mpn_statuses.get(ref)` is GREEN and the component's MPN matches the cached MPN, upgrade `mpn_statuses[ref]` to the cached value. After all restores, update the cache: `self._cached_mpn_statuses = dict(mpn_statuses)`.
  - Notes: Need to also cache the MPN value alongside the status to avoid restoring stale status when MPN changes. Use a secondary dict `self._cached_mpn_values: dict[str, str] = {}` that maps ref → mpn at scan time. Only restore if `comp.mpn == self._cached_mpn_values.get(ref)`.

- [x] Task 2: Cache project directory after first resolution
  - File: `src/kipart_search/gui/main_window.py`
  - Action: Add `self._project_dir: Path | None = None` in `__init__`. In `_resolve_project_dir()`, check `self._project_dir` first (before bridge). When any resolution succeeds, store to `self._project_dir`. Log the source (cached/KiCad/BOM/user). Remove the direct QFileDialog fallback — instead, if auto-detect fails, show a `QMessageBox.question` confirming the auto-detected path or allowing the user to browse.
  - Notes: Also cache project_dir from scan — after `_on_scan_complete`, if bridge is connected, store `self._project_dir = self._bridge.get_project_dir()`. This way even if bridge disconnects between scan and push, the cached dir is available.

- [x] Task 3: Update `_resolve_project_dir()` fallback to show confirmation instead of raw picker
  - File: `src/kipart_search/gui/main_window.py`
  - Action: Replace the `QFileDialog.getExistingDirectory()` fallback (lines 1097-1102) with a two-step flow: (a) if `self._project_dir` is set, show `QMessageBox.question("Use project directory: {path}?", Yes/Browse)` — Yes reuses cached, Browse opens picker; (b) if no cached dir, then show the picker as last resort.
  - Notes: This eliminates the "folder picker appears out of nowhere" UX issue.

- [x] Task 4: Move backup directory to project-scoped path
  - File: `src/kipart_search/core/backup.py`
  - Action: Change `BackupManager.__init__` default from `Path.home() / ".kipart-search" / "backups"` to accept an explicit `backup_dir` parameter with no default. Callers must provide it.
  - File: `src/kipart_search/gui/main_window.py`
  - Action: In `_ensure_backup_manager()` (or wherever BackupManager is created), compute backup_dir as `project_dir / ".kipart-search" / "backups"` when project_dir is available, or fall back to `Path.home() / ".kipart-search" / "backups"` when not. Pass to `BackupManager(backup_dir=...)`.
  - Notes: The `.kipart-search/` directory in the project root should be added to a suggested `.gitignore` entry in the push confirmation dialog message, or at minimum logged.

- [x] Task 5: Remove Freshness column from verify_panel
  - File: `src/kipart_search/gui/verify_panel.py`
  - Action: Remove `"Freshness"` from `VERIFY_COLUMNS` list (line 69). Delete `_make_freshness_item()` method (lines 339-364). Remove `freshness_col` variable and `self.table.setItem(row, freshness_col, freshness_item)` call. Remove `stale_count` tracking, `_STALE_LABEL`, `_FRESHNESS_SORT` constants, and stale-related display in `_build_summary()` and `_update_health_bar_style()`. Remove `is_stale` import if no longer used in this file.
  - Notes: Keep `is_stale()` in `core/models.py` and `verified_at`/`verified_source` fields on `BoardComponent` — they may be useful for future features. Only remove the GUI column and its rendering logic.

- [x] Task 6: Remove stale logging from main_window scan complete
  - File: `src/kipart_search/gui/main_window.py`
  - Action: Remove the stale detection log block (lines 848-858) that logs `"{stale_count} component(s) verified before last database update"`. Remove the `is_stale` import at line 797 if no longer used.
  - Notes: The `db_mtime` parameter can remain in the signal and `set_results()` signature for now — removing it would be a larger refactor for minimal gain.

### Acceptance Criteria

- [ ] AC 1: Given a board with 10 components that have been scanned and show 8 GREEN MPNs, when the user pushes assignments to KiCad and then re-scans, then the 8 previously GREEN components still show GREEN (not RED/0%).

- [ ] AC 2: Given a re-scan where a component's MPN has changed (e.g. user edited it in KiCad between scans), when the cached MPN doesn't match the new MPN, then the cached status is NOT restored — the component gets a fresh verification.

- [ ] AC 3: Given a connected KiCad session where a scan has been performed, when the user clicks "Push to KiCad", then no folder picker dialog appears — the project directory is resolved automatically from the board path.

- [ ] AC 4: Given a standalone session (no KiCad connection), when the user triggers push and no BOM path is available, then a folder picker appears as the last resort.

- [ ] AC 5: Given a successful push with a connected KiCad project at `/home/user/my-board/`, when backups are created, then backup files are stored in `/home/user/my-board/.kipart-search/backups/{timestamp}/` (not `~/.kipart-search/backups/`).

- [ ] AC 6: Given a standalone session with no project directory resolved, when backups are created, then backup files fall back to `~/.kipart-search/backups/` as before.

- [ ] AC 7: Given the verify_panel table after a scan, when the user views the columns, then there is no "Freshness" column — only Reference, Value, MPN, MPN Status, Footprint.

- [ ] AC 8: Given a scan with stale components, when the scan completes, then no stale-related log messages appear in the log panel.

## Additional Context

### Dependencies

None — all changes are internal to existing modules. No new libraries required.

### Testing Strategy

**Manual smoke test (primary):**
1. Connect to KiCad → Scan → verify GREEN statuses appear
2. Assign MPNs to 2-3 components → Push to KiCad
3. Re-scan → verify GREEN statuses are preserved (AC 1)
4. In KiCad, change one component's MPN → re-scan → verify that component gets fresh status (AC 2)
5. Push again → verify no folder picker appears (AC 3)
6. Check backup location is inside the KiCad project directory (AC 5)
7. Verify Freshness column is gone (AC 7)

**Edge cases to test manually:**
- Close and reopen KiPart Search → cached statuses should be gone (fresh start)
- Standalone mode (no KiCad) → folder picker should appear on push
- Push when project dir has spaces or Unicode in the path

### Notes

- Issue #1 is the highest priority — it's the core value proposition regression.
- The backup relocation (#3) should be communicated to users: old backups in `~/.kipart-search/backups/` are not migrated. New backups go to the project directory.
- Task 5 (remove Freshness) is technically part of Spec B (UI polish) but included here because it's a simple deletion and the column is currently unpopulated/unused. If you prefer it in Spec B, it can be moved.
