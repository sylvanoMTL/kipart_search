# Story 4.2: JLCPCB Database Download and Refresh

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a designer,
I want to download the JLCPCB parts database on first run with progress indication and refresh it when needed,
So that I have offline search capabilities without manual file management.

## Acceptance Criteria

1. **Given** the application launches and no JLCPCB database exists locally, **when** the user is prompted to download, **then** a progress dialog shows download progress (chunked download from GitHub Pages hosting, ~500 MB) (FR7), **and** the download can be cancelled without corrupting local state, **and** on completion the database is stored at `~/.kipart-search/jlcpcb/parts-fts5.db` and the JLCPCB source becomes available.

2. **Given** the JLCPCB database already exists locally, **when** the user clicks a "Refresh Database" action, **then** the database is re-downloaded with progress indication (FR8), **and** the old database is replaced only after the new download completes successfully, **and** the cache database (`cache.db`) and configuration are not affected by the refresh (NFR12).

3. **Given** the local database file is corrupted or unreadable, **when** the application detects the corruption (e.g. SQLite open fails), **then** the user is prompted to re-download with a clear message: "Database corrupted — download a fresh copy?" (NFR12), **and** configuration, cache, and API keys are preserved.

## Tasks / Subtasks

- [x] Task 1: Add first-run detection and auto-prompt (AC: #1)
  - [x] 1.1 In `_init_jlcpcb_source()`, after detecting no database exists, show a `QMessageBox` asking whether to download now
  - [x] 1.2 If user accepts, open `DownloadDialog` automatically
  - [x] 1.3 If user declines, app continues in no-source mode (graceful degradation already works)

- [x] Task 2: Add corruption detection and recovery prompt (AC: #3)
  - [x] 2.1 Add `JLCPCBSource.check_database_integrity(db_path) -> tuple[bool, str]` static method — runs `PRAGMA integrity_check` or at minimum attempts `SELECT count(*) FROM parts LIMIT 1`
  - [x] 2.2 Call integrity check in `_init_jlcpcb_source()` when database file exists — if check fails, show `QMessageBox` with "Database corrupted — download a fresh copy?"
  - [x] 2.3 If user accepts, delete the corrupt file and open `DownloadDialog`
  - [x] 2.4 If user declines, continue without JLCPCB source (log warning)
  - [x] 2.5 Ensure cache.db, config.json, and keyring credentials are not touched during recovery

- [x] Task 3: Add download cancellation safety (AC: #1)
  - [x] 3.1 Add cancellation flag to `DownloadWorker` — `self._cancelled = False` with a `cancel()` method
  - [x] 3.2 Check `_cancelled` between each chunk download — if cancelled, clean up partial chunks and zip fragments
  - [x] 3.3 Wire cancel button in `DownloadDialog` to call `_worker.cancel()` before `reject()`
  - [x] 3.4 On cancellation, existing database (if any) must remain untouched

- [x] Task 4: Implement atomic database replacement for refresh (AC: #2)
  - [x] 4.1 Modify `download_database()` to download to a temporary directory (e.g. `~/.kipart-search/jlcpcb/.download-tmp/`)
  - [x] 4.2 Only after extraction succeeds, close existing connection, rename old DB to `.bak`, move new DB into place
  - [x] 4.3 Delete `.bak` and temp directory on success; restore `.bak` on failure
  - [x] 4.4 In `_on_db_downloaded()`, close existing `JLCPCBSource` connection before replacement (already done)

- [x] Task 5: Add "Refresh Database" toolbar/menu action (AC: #2)
  - [x] 5.1 The "Download Database" menu item already exists — rename to "Download / Refresh Database" or keep as-is (the `DownloadDialog` already handles both cases via `check_for_update()`)
  - [x] 5.2 Verify that when DB exists, dialog shows "Update available" with correct info vs "Up to date"

- [x] Task 6: Write tests (all ACs)
  - [x] 6.1 Test `check_database_integrity()` with valid fixture DB returns `(True, ...)`
  - [x] 6.2 Test `check_database_integrity()` with corrupted/empty file returns `(False, ...)`
  - [x] 6.3 Test `check_database_integrity()` with non-existent file returns `(False, ...)`
  - [x] 6.4 Test download cancellation cleans up partial files
  - [x] 6.5 Test atomic replacement — on success, new DB is in place and old is gone
  - [x] 6.6 Test atomic replacement — on failure, old DB is restored from `.bak`
  - [x] 6.7 Test that cache.db is not affected by download/refresh operations

## Dev Notes

### CRITICAL: Extensive Existing Code — Extend, Don't Rewrite

Most of the download infrastructure already exists and works. This story fills three specific gaps:

1. **First-run auto-prompt** — currently no automatic prompt on startup when DB missing
2. **Corruption detection** — currently no integrity check; corrupt DB causes `sqlite3.OperationalError` during search
3. **Download cancellation & atomic replacement** — currently download writes directly to final location; cancellation or failure mid-download leaves corrupt state

### Existing Code Map

| File | What exists | What to add |
|------|-------------|-------------|
| `core/sources.py` → `JLCPCBSource` | `download_database()`, `check_for_update()`, `db_needs_download()`, `_save_db_metadata()`, `default_db_path()` | `check_database_integrity()`, temp-dir download for atomic replacement, cancellation support via callback |
| `gui/download_dialog.py` → `DownloadDialog` | Full dialog: update check, progress bar, browse, download, cancel button, retry on error | Cancel → cleanup (wire cancel to worker), atomic replacement flow |
| `gui/download_dialog.py` → `DownloadWorker` | `progress`, `finished`, `error` signals; calls `JLCPCBSource.download_database()` | `cancel()` method, cancelled flag checked between chunks |
| `gui/main_window.py` → `MainWindow` | `_init_jlcpcb_source()`, `_on_download_db()`, `_on_db_downloaded()` | First-run prompt in `_init_jlcpcb_source()`, corruption detection + recovery prompt |

### Architecture Constraints

- **Core/GUI separation**: `check_database_integrity()` goes in `core/sources.py` (zero GUI). The prompt dialogs (`QMessageBox`) go in `gui/main_window.py`.
- **Atomic replacement**: Download to temp dir, then swap. This logic belongs in `core/sources.py` `download_database()` since it's file I/O with no GUI dependencies.
- **Thread safety**: `JLCPCBSource.close()` must be called before replacing the database file (already done in `_on_db_downloaded()`). After replacement, a new `JLCPCBSource` is created with the new path.
- **Cache isolation (NFR12)**: `cache.db` is at `~/.kipart-search/cache.db`. JLCPCB DB is at `~/.kipart-search/jlcpcb/parts-fts5.db`. They are separate directories. Download/refresh only touches `~/.kipart-search/jlcpcb/`. Never delete the parent `~/.kipart-search/` directory.

### Cancellation Design

The `download_database()` static method currently downloads all chunks sequentially. To support cancellation:

```python
# In download_database(), add a cancel_check parameter:
@staticmethod
def download_database(
    target_dir: Path | None = None,
    progress_callback: Callable[[int, int, str], None] | None = None,
    cancel_check: Callable[[], bool] | None = None,
) -> Path:
    ...
    for i in range(1, total_chunks + 1):
        if cancel_check and cancel_check():
            # Clean up partial downloads
            for f in tmp_dir.glob("*"):
                f.unlink()
            tmp_dir.rmdir()
            raise RuntimeError("Download cancelled")
        ...
```

```python
# In DownloadWorker:
class DownloadWorker(QThread):
    def __init__(self, target_dir: Path):
        super().__init__()
        self.target_dir = target_dir
        self._cancelled = False

    def cancel(self):
        self._cancelled = True

    def run(self):
        try:
            db_path = JLCPCBSource.download_database(
                target_dir=self.target_dir,
                progress_callback=lambda cur, total, msg: self.progress.emit(cur, total, msg),
                cancel_check=lambda: self._cancelled,
            )
            if not self._cancelled:
                self.finished.emit(str(db_path))
        except RuntimeError as e:
            if self._cancelled:
                self.error.emit("Download cancelled")
            else:
                self.error.emit(str(e))
        except Exception as e:
            self.error.emit(str(e))
```

### Atomic Replacement Design

```python
# In download_database():
tmp_dir = target_dir / ".download-tmp"
tmp_dir.mkdir(parents=True, exist_ok=True)

# Download chunks to tmp_dir...
# Extract to tmp_dir...
# Then:
tmp_db = tmp_dir / "parts-fts5.db"
final_db = target_dir / "parts-fts5.db"
backup_db = target_dir / "parts-fts5.db.bak"

# Atomic swap
if final_db.exists():
    final_db.rename(backup_db)
try:
    tmp_db.rename(final_db)
    if backup_db.exists():
        backup_db.unlink()
except Exception:
    # Restore backup
    if backup_db.exists():
        backup_db.rename(final_db)
    raise
finally:
    # Clean up tmp_dir
    import shutil
    if tmp_dir.exists():
        shutil.rmtree(tmp_dir, ignore_errors=True)
```

### Corruption Detection Design

```python
@staticmethod
def check_database_integrity(db_path: Path | None = None) -> tuple[bool, str]:
    """Check if the JLCPCB database is readable and has the expected structure."""
    path = db_path or JLCPCBSource.default_db_path()
    if not path.exists():
        return False, "Database file not found"
    try:
        conn = sqlite3.connect(str(path))
        # Check that the parts table exists and is queryable
        row = conn.execute("SELECT count(*) FROM parts LIMIT 1").fetchone()
        conn.close()
        return True, f"Database OK ({row[0]} parts)"
    except sqlite3.DatabaseError as e:
        return False, f"Database corrupted: {e}"
```

### First-Run Prompt in MainWindow

```python
def _init_jlcpcb_source(self):
    """Initialize JLCPCB source if database exists."""
    db_path = JLCPCBSource.default_db_path()
    self._jlcpcb_source = JLCPCBSource(db_path)

    if not db_path.exists():
        # First-run: prompt to download
        reply = QMessageBox.question(
            self,
            "JLCPCB Database",
            "No JLCPCB parts database found.\n\n"
            "Download now? (~500 MB, provides offline search for 1M+ parts)\n\n"
            "You can also download later from File > Download Database.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            self._on_download_db()
        return

    # Database exists — check integrity
    ok, msg = JLCPCBSource.check_database_integrity(db_path)
    if not ok:
        log.warning("JLCPCB database integrity check failed: %s", msg)
        reply = QMessageBox.warning(
            self,
            "Database Corrupted",
            f"The JLCPCB database appears corrupted:\n{msg}\n\n"
            "Download a fresh copy?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            db_path.unlink(missing_ok=True)
            self._on_download_db()
        return

    # Database is valid — add to orchestrator
    if self._jlcpcb_source.is_configured():
        self._orchestrator.add_source(self._jlcpcb_source)
```

### DownloadDialog Cancel Wiring

```python
# In DownloadDialog._start_download():
self.close_btn.clicked.disconnect()  # Remove old connection
self.close_btn.clicked.connect(self._on_cancel)

def _on_cancel(self):
    if self._worker and self._worker.isRunning():
        self._worker.cancel()
        self.status_label.setText("Cancelling...")
        self.close_btn.setEnabled(False)
    else:
        self.reject()
```

### Files to Modify

| File | Changes |
|------|---------|
| `src/kipart_search/core/sources.py` | Add `check_database_integrity()`, add `cancel_check` param to `download_database()`, implement temp-dir atomic replacement |
| `src/kipart_search/gui/download_dialog.py` | Add `cancel()` to `DownloadWorker`, wire cancel button to worker, handle cancelled state |
| `src/kipart_search/gui/main_window.py` | Add first-run prompt and corruption detection in `_init_jlcpcb_source()` |
| `tests/core/test_jlcpcb_download.py` | New: integrity check tests, cancellation tests, atomic replacement tests |

### Files NOT to Modify

- `core/cache.py` — cache is completely separate; no changes needed
- `core/search.py` — orchestrator is unaware of download; already handles missing sources
- `core/models.py` — no model changes
- `gui/results_table.py` — unaffected
- `gui/verify_panel.py` — unaffected
- `gui/search_bar.py` — unaffected

### What This Story Does NOT Include

- Automatic background update checking on app launch (not in ACs — would be Epic 6 scope)
- Database size display in status bar (Story 4-3 / Epic 6 scope)
- Offline mode detection or "Local DB" status bar badge (Story 4-3)
- Settings dialog for database path configuration (Epic 6 scope)
- Welcome / first-run wizard (Epic 6, Story 6-2)
- Download resume after interruption (nice-to-have, not in ACs)

### Previous Story Intelligence (from Story 4.1)

Key learnings to apply:
- `check_same_thread=False` is required for SQLite connections used from QThread workers — integrity check should use a fresh connection, not the source's shared connection
- Error handling: cache/DB failures never crash the app — same principle applies to integrity check and download
- Graceful degradation: app must work fully without JLCPCB source; the prompt is informational, never blocking
- Test count before this story: 274 passed, 1 pre-existing failure (unrelated)
- `_on_db_downloaded()` already closes existing source and recreates orchestrator — this pattern is correct for atomic replacement

### Git Intelligence

Recent commit patterns:
- `1c72d27` Add SQLite query cache with code review fixes (Story 4.1)
- Imperative mood commit messages with story reference
- Code review fixes as separate commits
- `main_window.py` is the primary integration point — changes there should be minimal and focused

### Testing Notes

- Use `tmp_path` fixture for all file operations — never touch real `~/.kipart-search/`
- Create a minimal valid SQLite FTS5 fixture database for integrity tests (a few rows, same schema as JLCPCB)
- For download tests, mock `httpx.Client` to avoid network calls
- For cancellation tests, mock `download_database` to check that cancel_check is respected
- Test atomic replacement with real file operations on `tmp_path`

### Project Structure Notes

- All paths follow existing `src/kipart_search/` layout
- New test file: `tests/core/test_jlcpcb_download.py`
- No new modules or packages — extends existing `sources.py` and `download_dialog.py`
- JLCPCB database path: `~/.kipart-search/jlcpcb/parts-fts5.db` (not `~/.kipart-search/parts-fts5.db` — note the `jlcpcb/` subdirectory, matching `default_db_path()`)

### References

- [Source: _bmad-output/planning-artifacts/epics.md — Epic 4, Story 4.2]
- [Source: _bmad-output/planning-artifacts/architecture.md — ADR-01 (Separate Cache Database), User Data Files section]
- [Source: _bmad-output/planning-artifacts/prd.md — FR7 (Download database), FR8 (Refresh database), NFR12 (Corruption recovery)]
- [Source: _bmad-output/planning-artifacts/ux-design-specification.md — First-run experience, download progress, source configuration]
- [Source: CLAUDE.md — JLCPCB/LCSC offline database section, kicad-jlcpcb-tools reference]
- [Source: _bmad-output/project-context.md — SQLite3 usage, download dialog chunked zip, graceful degradation]
- [Source: 4-1-sqlite-query-cache.md — Previous story dev notes, error handling patterns, test patterns]

## Dev Agent Record

### Agent Model Used

Claude Opus 4.6 (1M context)

### Debug Log References

None — clean implementation with no debugging required.

### Completion Notes List

- ✅ Added `check_database_integrity()` static method to `JLCPCBSource` — uses fresh SQLite connection to verify `parts` table is queryable
- ✅ Updated `_init_jlcpcb_source()` in `MainWindow` with first-run auto-prompt (QMessageBox.question) and corruption detection (QMessageBox.warning)
- ✅ Added `cancel_check` callback parameter to `download_database()` — checked between each chunk download, cleans up temp dir on cancellation
- ✅ Added `cancel()` method to `DownloadWorker` with `_cancelled` flag
- ✅ Wired cancel button in `DownloadDialog` to call `_worker.cancel()` during download, with proper button state management
- ✅ Implemented atomic database replacement: downloads to `.download-tmp/` dir, backs up old DB to `.bak`, swaps atomically, restores backup on failure
- ✅ Renamed menu item from "Download Database" to "Download / Refresh Database"
- ✅ Updated existing test for menu item rename
- ✅ 10 new tests: 5 integrity check, 2 cancellation, 3 atomic replacement — all passing
- ✅ Full regression suite: 284 passed, 1 pre-existing failure (unrelated `test_central_widget_is_shrinkable_placeholder`)

### Change Log

- 2026-03-19: Implemented Story 4.2 — JLCPCB database download and refresh (first-run prompt, corruption detection, cancellation safety, atomic replacement, 10 new tests)
- 2026-03-19: Code review fixes — connection leak in check_database_integrity(), deduplicated _on_error() in DownloadDialog, rewrote atomic replacement tests to exercise actual download_database() code path

### File List

- `src/kipart_search/core/sources.py` — added `check_database_integrity()`, `cancel_check` param + atomic replacement in `download_database()`
- `src/kipart_search/gui/download_dialog.py` — added `cancel()` to `DownloadWorker`, cancel button wiring, button state restoration
- `src/kipart_search/gui/main_window.py` — first-run prompt, corruption detection in `_init_jlcpcb_source()`, menu item rename
- `tests/core/test_jlcpcb_download.py` — new: 10 tests for integrity, cancellation, atomic replacement
- `tests/test_main_window_docks.py` — updated menu item test for new label
