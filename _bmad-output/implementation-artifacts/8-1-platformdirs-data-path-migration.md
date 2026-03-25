# Story 8.1: platformdirs Data Path Migration

Status: done

## Story

As a developer,
I want all user data paths to use `platformdirs` instead of hardcoded `~/.kipart-search/`,
so that data is stored in platform-correct locations and the app follows Windows conventions for installed programs.

## Acceptance Criteria

1. **Given** the application uses `Path.home() / ".kipart-search"` for config, cache, database, backups, and templates, **when** the developer replaces all paths with `platformdirs.user_data_dir("KiPartSearch")`, **then** on Windows data is stored under `%LOCALAPPDATA%\KiPartSearch\` (not roaming — the JLCPCB database is ~500 MB).

2. **Given** the new path module exists, **when** running on Linux, **then** data follows XDG conventions (`~/.local/share/KiPartSearch/`).

3. **Given** the new path module exists, **when** running on macOS, **then** data uses `~/Library/Application Support/KiPartSearch/`.

4. **Given** the old `~/.kipart-search/` directory exists and the new location is empty, **when** the app launches for the first time after the migration, **then** a one-time migration copies files atomically (per file: copy → verify size → delete old).

5. **Given** migration fails mid-way (e.g. disk full, permission error), **when** the error is caught, **then** both copies are preserved, a warning is logged, and the app continues using whichever location has the data.

6. **Given** both old and new locations exist with data, **when** the app resolves paths, **then** the new location takes priority but old is checked as fallback.

7. **Given** the `platformdirs` package, **when** added to dependencies, **then** it is listed in `pyproject.toml` (BSD license — GPL firewall safe).

8. **Given** all existing tests and functionality, **when** run after the migration, **then** they pass with the new paths.

## Tasks / Subtasks

- [x] Task 1: Create `core/paths.py` — centralised path module (AC: #1, #2, #3)
  - [x] 1.1 Add `platformdirs` to `pyproject.toml` dependencies
  - [x] 1.2 Create `core/paths.py` with `data_dir()`, `config_path()`, `cache_path()`, `jlcpcb_dir()`, `backups_dir()`, `templates_dir()` functions
  - [x] 1.3 Use `platformdirs.user_data_dir("KiPartSearch", appauthor=False)` — `appauthor=False` avoids an extra nesting level on Windows
  - [x] 1.4 All functions return `Path` objects and create directories on first call (`mkdir(parents=True, exist_ok=True)`)

- [x] Task 2: Add one-time migration logic (AC: #4, #5, #6)
  - [x] 2.1 Add `migrate_legacy_data()` function in `core/paths.py`
  - [x] 2.2 Detect old dir: `Path.home() / ".kipart-search"`
  - [x] 2.3 If old dir exists AND new dir is empty/missing → copy each file individually: `shutil.copy2()` → verify `os.path.getsize()` match → `os.remove()` old
  - [x] 2.4 If any file copy fails → log warning, preserve both, continue
  - [x] 2.5 After all files migrated successfully, attempt `rmdir` on empty old subdirs (non-recursive, ignore errors)
  - [x] 2.6 If both locations have data (partial migration or manual copy) → new location wins, old is fallback

- [x] Task 3: Replace all hardcoded paths in core modules (AC: #1, #8)
  - [x] 3.1 `core/source_config.py` — replace `_config_dir()` and `_config_path()` to call `paths.data_dir()` / `paths.config_path()`
  - [x] 3.2 `core/cache.py` — replace `Path.home() / ".kipart-search" / "cache.db"` default with `paths.cache_path()`
  - [x] 3.3 `core/sources.py` — replace `JLCPCBSource.default_db_path()` to use `paths.jlcpcb_dir() / "parts-fts5.db"`

- [x] Task 4: Replace hardcoded paths in GUI modules (AC: #1, #8)
  - [x] 4.1 `gui/main_window.py` — replace standalone backup fallback `Path.home() / ".kipart-search" / "backups"` with `paths.backups_dir()`
  - [x] 4.2 `gui/download_dialog.py` — uses `JLCPCBSource.default_db_path()` already (no change needed if Task 3.3 done)
  - [x] 4.3 Verify no other GUI files reference `~/.kipart-search` directly

- [x] Task 5: Call migration at startup (AC: #4)
  - [x] 5.1 In `__main__.py`, call `migrate_legacy_data()` early — AFTER `_check_version_flag()` but BEFORE any data access
  - [x] 5.2 Migration must happen before `QApplication` — no GUI dependencies
  - [x] 5.3 Log migration activity to stderr (logging not yet initialised at this point — use `print()` to stderr or `logging.basicConfig()` minimal)

- [x] Task 6: Update tests (AC: #8)
  - [x] 6.1 Add `tests/core/test_paths.py` — test `data_dir()` returns expected platform path, test `migrate_legacy_data()` copies files, test partial migration preserves both copies, test fallback logic
  - [x] 6.2 Update `tests/core/test_jlcpcb_download.py` if it references `.kipart-search` paths
  - [x] 6.3 Update smoke test descriptions in `tests/smoke_test_build.py` and `tests/smoke_test_writeback.py`
  - [x] 6.4 Run full test suite and verify no regressions

- [x] Task 7: Verify Nuitka compatibility (AC: #8)
  - [x] 7.1 Verify `platformdirs` has no native extensions (it's pure Python — should work with Nuitka without extra flags)
  - [x] 7.2 Check that `build_nuitka.py` `--include-package` flags don't need updating (platformdirs is a simple import, no dynamic backends)
  - [x] 7.3 Run GPL firewall check: `python -c "from build_nuitka import check_licenses; check_licenses()"` — platformdirs is MIT/BSD, should pass

## Dev Notes

### Central Design Decision: Single `core/paths.py` Module

All path resolution MUST go through `core/paths.py`. No module should ever construct a `~/.kipart-search/` path directly. This is the single source of truth for where user data lives.

**Module signature:**

```python
# core/paths.py
from pathlib import Path
import platformdirs

def data_dir() -> Path:
    """Base data directory. Creates if needed."""
    d = Path(platformdirs.user_data_dir("KiPartSearch", appauthor=False))
    d.mkdir(parents=True, exist_ok=True)
    return d

def config_path() -> Path:
    return data_dir() / "config.json"

def cache_path() -> Path:
    return data_dir() / "cache.db"

def jlcpcb_dir() -> Path:
    d = data_dir() / "jlcpcb"
    d.mkdir(parents=True, exist_ok=True)
    return d

def backups_dir() -> Path:
    d = data_dir() / "backups"
    d.mkdir(parents=True, exist_ok=True)
    return d

def templates_dir() -> Path:
    d = data_dir() / "templates"
    d.mkdir(parents=True, exist_ok=True)
    return d

_LEGACY_DIR = Path.home() / ".kipart-search"

def migrate_legacy_data() -> None:
    """One-time migration from ~/.kipart-search/ to platformdirs location."""
    ...
```

### Platform Path Results

| Platform | `platformdirs.user_data_dir("KiPartSearch", appauthor=False)` |
|----------|---------------------------------------------------------------|
| Windows  | `C:\Users\{user}\AppData\Local\KiPartSearch`                 |
| Linux    | `~/.local/share/KiPartSearch`                                |
| macOS    | `~/Library/Application Support/KiPartSearch`                 |

**Why `appauthor=False`:** By default, platformdirs adds an `{appauthor}/{appname}` structure on Windows. Setting `appauthor=False` gives a flat `%LOCALAPPDATA%\KiPartSearch\` instead of `%LOCALAPPDATA%\MecaFrog\KiPartSearch\`.

**Why `user_data_dir` not `user_config_dir`:** On Linux, `user_config_dir` maps to `~/.config/KiPartSearch`. Since we store large binary data (500 MB JLCPCB database, SQLite cache), `user_data_dir` (`~/.local/share/`) is more appropriate. Config, cache, and data all live together for simplicity — matching the current `~/.kipart-search/` flat structure.

### Exact Files to Modify

| File | Current Path Code | Replace With |
|------|-------------------|--------------|
| `core/source_config.py:76-84` | `_config_dir()` → `Path.home() / ".kipart-search"` | Import and call `paths.data_dir()` |
| `core/source_config.py:83-84` | `_config_path()` → `_config_dir() / "config.json"` | Import and call `paths.config_path()` |
| `core/cache.py:28` | `Path.home() / ".kipart-search" / "cache.db"` | `paths.cache_path()` |
| `core/sources.py:263-265` | `JLCPCBSource.default_db_path()` → `Path.home() / ".kipart-search" / "jlcpcb" / "parts-fts5.db"` | `paths.jlcpcb_dir() / "parts-fts5.db"` |
| `gui/main_window.py:1408` | `Path.home() / ".kipart-search" / "backups"` (standalone fallback) | `paths.backups_dir()` |

**Project-scoped backups (`{project_dir}/.kipart-search/backups/`) are NOT affected** — they live alongside the KiCad project, not in the user data directory.

### Migration Logic Details

```
Migration triggers when:
  - old ~/.kipart-search/ exists
  - AND new platformdirs location is empty or doesn't exist

Files to migrate (if present):
  - config.json
  - cache.db
  - jlcpcb/parts-fts5.db
  - jlcpcb/db_meta.json
  - backups/**  (entire tree)
  - templates/**  (entire tree)

Per-file strategy:
  1. shutil.copy2(old, new)  — preserves timestamps
  2. Verify: new.stat().st_size == old.stat().st_size
  3. old.unlink()
  4. If step 1 or 2 fails: log warning, keep both, continue next file

After all files:
  - Walk old dir bottom-up, rmdir empty dirs (ignore errors)
  - If old dir still has files: leave it, log "partial migration"
```

### What NOT to Do

- Do NOT split config vs data into separate directories (e.g. `user_config_dir` + `user_data_dir`) — keep the current flat structure under one root
- Do NOT use `user_cache_dir` for the cache.db — it should survive OS cache cleanup
- Do NOT move project-scoped backups (`{project}/.kipart-search/backups/`) — those stay with the KiCad project
- Do NOT change the keyring service name (`"kipart-search"`) — credentials are in OS keyring, not filesystem
- Do NOT change QSettings organization/application name (`"kipart-search"`) — window state is in the registry, not filesystem
- Do NOT add `platformdirs` to the `[project.optional-dependencies]` — it's a core dependency, not optional
- Do NOT use `roaming=True` on Windows — the JLCPCB database is ~500 MB, unsuitable for roaming profiles
- Do NOT delete old directory if any files remain after migration attempt

### Nuitka Compatibility

`platformdirs` is pure Python with no native extensions and no dynamic imports. It should work with Nuitka `--include-package=kipart_search` without any additional flags. The `--include-package=platformdirs` is not needed because it's a simple top-level import that Nuitka's dependency scanner will find automatically.

### Project Structure Notes

**New files:**
- `src/kipart_search/core/paths.py` — centralised path resolution + legacy migration
- `tests/core/test_paths.py` — unit tests for path resolution and migration

**Modified files:**
- `pyproject.toml` — add `platformdirs` dependency
- `src/kipart_search/__main__.py` — call `migrate_legacy_data()` at startup
- `src/kipart_search/core/source_config.py` — replace `_config_dir()` / `_config_path()` with `paths` imports
- `src/kipart_search/core/cache.py` — replace default path with `paths.cache_path()`
- `src/kipart_search/core/sources.py` — replace `default_db_path()` with `paths.jlcpcb_dir()`
- `src/kipart_search/gui/main_window.py` — replace standalone backup fallback with `paths.backups_dir()`

**No changes to:**
- `core/backup.py` — receives `backup_dir` as a parameter (already abstracted)
- `core/license.py` — uses OS keyring, no filesystem paths
- `gui/download_dialog.py` — delegates to `JLCPCBSource.default_db_path()` (fixed transitively)
- `build_nuitka.py` — no path changes needed
- `.github/workflows/build-windows.yml` — no path changes needed

### Previous Story Intelligence

**From Story 7.5 (CI Build Pipeline):**
- `__main__.py` has `_check_version_flag()` that runs before QApplication — migration call goes right after this
- Build script `build_nuitka.py` has `check_licenses()` — verify platformdirs passes GPL check
- 49 tests in `test_build_nuitka.py` — should not be affected

**From Epic 7 general learnings:**
- Pure Python deps work fine with Nuitka (no `--include-package` needed for simple imports)
- The `_init_keyring_compiled()` call in `__main__.py` must stay after `_check_version_flag()` — migration should go between version check and keyring init
- Smoke test (`kipart-search.exe --version`) exits before migration — good, no side effects in CI

### Git Intelligence

Recent commits show active work on write-back workflow (backup paths, project dir detection) and UI polish. The backup path logic in `main_window.py:1398-1410` was recently touched in commit `2c4fb13`. Be careful not to break the dual-mode backup (project vs standalone) when replacing the standalone fallback path.

### References

- [Source: _bmad-output/planning-artifacts/epics.md — Epic 8, Story 8.1]
- [Source: _bmad-output/planning-artifacts/architecture.md — ADR-01 Cache DB, User Data Files section]
- [Source: src/kipart_search/core/source_config.py:76-84 — current _config_dir/_config_path]
- [Source: src/kipart_search/core/cache.py:28 — current cache path default]
- [Source: src/kipart_search/core/sources.py:262-265 — current JLCPCB default_db_path]
- [Source: src/kipart_search/gui/main_window.py:1398-1410 — backup manager dual-mode paths]
- [Source: platformdirs PyPI — BSD license, pure Python, v4.3.x latest]

## Dev Agent Record

### Agent Model Used

Claude Opus 4.6 (1M context)

### Debug Log References

None — clean implementation with no debug issues.

### Completion Notes List

- Created `core/paths.py` centralised path module with `data_dir()`, `config_path()`, `cache_path()`, `jlcpcb_dir()`, `backups_dir()`, `templates_dir()` — all using `platformdirs.user_data_dir("KiPartSearch", appauthor=False)`
- Implemented `migrate_legacy_data()` with per-file atomic copy (copy2 → verify size → unlink), partial failure preservation, and bottom-up empty dir cleanup
- Replaced all 4 hardcoded `~/.kipart-search/` paths in core modules (source_config, cache, sources) and 1 in GUI (main_window standalone backup fallback)
- Migration called at startup in `__main__.py` after `_check_version_flag()` but before `_init_keyring_compiled()` and `QApplication`
- 15 new tests in `test_paths.py` covering path resolution (8 tests) and migration logic (7 tests including partial failure)
- Updated `test_jlcpcb_download.py` and smoke test descriptions to remove `~/.kipart-search` references
- Verified: platformdirs is pure Python (no native extensions), GPL firewall passes (43 packages clean), no Nuitka build flag changes needed
- 301 tests pass, 1 skipped. Pre-existing Qt access violation in `test_context_menus.py::test_status_bar_accessible_names` (MainWindow init crash) — unrelated to this story.

### Implementation Plan

Followed story tasks sequentially: create paths module → add migration → replace core paths → replace GUI paths → wire startup → update tests → verify Nuitka. Used lazy imports in modified modules to avoid circular imports.

### Change Log

- 2026-03-25: Story 8.1 implemented — all user data paths migrated from `~/.kipart-search/` to platformdirs locations

### File List

**New files:**
- `src/kipart_search/core/paths.py`
- `tests/core/test_paths.py`

**Modified files:**
- `pyproject.toml`
- `src/kipart_search/__main__.py`
- `src/kipart_search/core/source_config.py`
- `src/kipart_search/core/cache.py`
- `src/kipart_search/core/sources.py`
- `src/kipart_search/gui/main_window.py`
- `tests/core/test_jlcpcb_download.py`
- `tests/smoke_test_build.py`
- `tests/smoke_test_writeback.py`
