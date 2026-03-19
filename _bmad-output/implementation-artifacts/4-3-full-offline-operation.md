# Story 4.3: Full Offline Operation

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a designer,
I want the application to work fully offline after the initial database download,
so that I can search, verify, and export BOMs without an internet connection.

## Acceptance Criteria

1. **Given** the JLCPCB database has been downloaded and cached results exist, **when** the application launches with no internet connection, **then** the application starts normally and all local functionality works: FTS5 search, board scan, verification, MPN assignment, BOM export (FR33), **and** the status bar shows the data mode clearly (FR35), **and** API-based sources (DigiKey, Mouser) show as unavailable without errors or crashes (NFR9), **and** previously cached API results are still served from `cache.db`.

2. **Given** the application is offline and a search returns no results from the local database, **when** the user sees 0 results, **then** the log panel notes that online sources are unavailable: e.g. "DigiKey: offline — cached results only", **and** the manual MPN entry workflow remains fully functional.

3. **Given** the application has a network connection, **when** API sources are configured and reachable, **then** the status bar shows the number of active sources (e.g. "JLCPCB (500 MB, 2026-03-15) + DigiKey + Mouser") with online indication.

4. **Given** the application starts, **when** network connectivity changes or sources become unavailable during a session, **then** the source status updates gracefully without crashing or blocking the UI.

## Tasks / Subtasks

- [x] Task 1: Add network/source availability detection to SearchOrchestrator (AC: #1, #2, #4)
  - [x] 1.1 Add `is_online(source: DataSource) -> bool` method or equivalent — for local sources (JLCPCB), always returns True if DB exists; for future API sources, returns True if last query succeeded or connectivity check passes
  - [x] 1.2 Distinguish local sources (offline-capable) from API sources (network-dependent) in `DataSource` ABC — add `is_local: bool` property (default `False`), override to `True` in `JLCPCBSource`
  - [x] 1.3 When a source query raises a connection error (httpx.ConnectError, httpx.TimeoutException), catch it gracefully, log "SourceName: offline — cached results only", and fall back to cache

- [x] Task 2: Update status bar to show data mode (AC: #1, #3)
  - [x] 2.1 In `_update_status()`, build source status text that distinguishes local vs online sources — e.g. "JLCPCB (500 MB, 2026-03-15)" for local, "DigiKey" / "DigiKey (offline)" for API sources
  - [x] 2.2 When only local sources are available (no API sources configured or all API sources offline), show "Local DB" badge or indication in the sources label area
  - [x] 2.3 When API sources are active, show source count: e.g. "JLCPCB + 2 online sources"

- [x] Task 3: Add offline fallback in search and verification workers (AC: #1, #2)
  - [x] 3.1 In `SearchWorker.run()`, handle connection errors from API sources gracefully — emit log message "SourceName: offline — cached results only" and continue with local/cached results
  - [x] 3.2 In `ScanWorker.run()`, handle connection errors during MPN verification — fall back to cache for MPN lookups, log which sources were unavailable
  - [x] 3.3 Ensure 0-result searches when offline show an informative message in the log panel rather than a confusing error

- [x] Task 4: Ensure all local workflows function offline (AC: #1)
  - [x] 4.1 Verify FTS5 search against JLCPCB database works with no network — this should already work (JLCPCB is local SQLite), confirm with a test
  - [x] 4.2 Verify board scan + verification works offline — MPN verification against local DB should work; API-based verification should gracefully skip unavailable sources
  - [x] 4.3 Verify BOM export works offline — export uses only local data, no network calls
  - [x] 4.4 Verify cached API results from `cache.db` are served when the originating source is offline

- [x] Task 5: Write tests (all ACs)
  - [x] 5.1 Test that JLCPCBSource search works with no network (it's local — should always work)
  - [x] 5.2 Test that SearchOrchestrator gracefully handles a source that raises connection errors — returns results from other sources + cache
  - [x] 5.3 Test that `is_local` property returns True for JLCPCBSource, False for DataSource base
  - [x] 5.4 Test that cached results are served when source is offline (cache hit path)
  - [x] 5.5 Test that verify_mpn falls back to cache when source raises connection error

## Dev Notes

### CRITICAL: This is Mostly a Robustness Story — Minimal New Code

The application already works offline for JLCPCB searches since it uses a local SQLite database. The cache layer (Story 4.1) already serves cached results. This story is primarily about:

1. **Making offline operation explicit** — status bar shows data mode, log messages explain what's unavailable
2. **Graceful error handling** — connection errors from future API sources don't crash the app
3. **User awareness** — clear feedback about what works offline vs what requires network

There are currently **no API sources implemented** (DigiKey, Mouser are planned for Phase 2). So the "offline" scenario today means: JLCPCB local DB works, cache serves previous results, no API sources exist yet. The code written here must handle the future case where API sources exist but are unreachable.

### Existing Code That Already Works Offline

| Feature | Why it works offline | Notes |
|---------|---------------------|-------|
| FTS5 search | `JLCPCBSource` queries local SQLite DB | No network calls |
| Board scan | `ScanWorker` reads KiCad via IPC API (local socket) | No network calls |
| MPN verification | `verify_mpn()` checks local DB + cache | Cache serves previous API results |
| BOM export | `BomExportEngine` uses local data model | No network calls |
| Query transformation | `units.py` is pure computation | No network calls |
| Detail panel | Displays cached `PartResult` data | No network calls |

### Architecture Constraints

- **Core/GUI separation**: `is_local` property goes on `DataSource` ABC in `core/sources.py`. Status bar updates go in `gui/main_window.py`. Connection error handling goes in `core/search.py` (orchestrator) and `gui/main_window.py` (workers).
- **No new QThread classes**: Connection error handling happens inside existing `SearchWorker.run()` and `ScanWorker.run()` — no dedicated connectivity checker thread needed.
- **No active polling**: Do NOT add a background thread that periodically checks network connectivity. Instead, detect offline state reactively when a source query fails. This is simpler and avoids unnecessary network traffic.
- **Error types to catch**: `httpx.ConnectError`, `httpx.TimeoutException`, `httpx.NetworkError` — these indicate the source is unreachable. Do NOT catch `httpx.HTTPStatusError` (4xx/5xx) as "offline" — those mean the server responded but the request failed.

### DataSource `is_local` Property

Add a read-only property to the `DataSource` ABC:

```python
# In core/sources.py DataSource ABC:
@property
def is_local(self) -> bool:
    """Whether this source works without network access."""
    return False

# In JLCPCBSource:
@property
def is_local(self) -> bool:
    return True
```

This is the simplest way to distinguish local vs API sources. Future API adapters (DigiKey, Mouser) inherit the default `False`.

### SearchOrchestrator Connection Error Handling

In `_search_sources()`, wrap the `source.search()` call:

```python
try:
    parts = source.search(variant, filters, limit)
except Exception as e:
    # Connection error — source is offline
    log.warning("%s: offline — %s", source.name, e)
    # Try cache as fallback
    cached = self._cache_get(source.name, "search", variant)
    if cached is not None:
        parts = [part_result_from_dict(d) for d in cached]
        log.info("%s: served from cache (offline fallback)", source.name)
    else:
        parts = []
    # Don't re-raise — continue with other sources
```

Same pattern in `verify_mpn()` — catch connection errors, fall back to cache.

**Important**: Currently `JLCPCBSource.search()` can raise `sqlite3.OperationalError` if the DB is corrupt. This is already handled by the caller. The new error handling is specifically for future API sources that raise `httpx` exceptions. Use a broad `Exception` catch for now since we don't have httpx in the import path of `search.py`, but add a comment explaining the expected exception types.

### Status Bar Data Mode Display

Update `_update_status()` in `main_window.py`:

```python
def _update_status(self):
    # ... mode badge (KiCad connection) unchanged ...

    # Center zone: source availability
    source_parts: list[str] = []
    if self._jlcpcb_source and self._jlcpcb_source.is_configured():
        # Local source — always available
        db_path = self._jlcpcb_source.db_path
        try:
            stat = db_path.stat()
            dt = datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d")
            size_mb = stat.st_size / (1024 * 1024)
            source_parts.append(f"JLCPCB ({size_mb:.0f} MB, {dt})")
        except OSError:
            source_parts.append("JLCPCB")

    # Future: add online source status here when API adapters are implemented
    # For now, the only source is JLCPCB (local).

    if source_parts:
        self._sources_label.setText(" + ".join(source_parts))
    else:
        self._sources_label.setText("No sources configured")
```

The current implementation already does this correctly. The key addition is ensuring that when API sources exist in the future, their online/offline state is reflected. For now, add a comment placeholder and the `is_local` infrastructure.

### Log Panel Messages for Offline Sources

When a search finds no results and some sources were offline, the log should explain:

```
[14:32:15] Searching all sources for '100nF 0805' ...
[14:32:15] JLCPCB: 47 results
[14:32:16] DigiKey: offline — cached results only
[14:32:16] Mouser: offline — cached results only
```

This happens naturally through the `log.warning()` calls in the orchestrator — the existing `LogHandler` in `main_window.py` captures all `logging` output and displays it in the log panel.

### Files to Modify

| File | Changes |
|------|---------|
| `src/kipart_search/core/sources.py` | Add `is_local` property to `DataSource` ABC (return False) and `JLCPCBSource` (return True) |
| `src/kipart_search/core/search.py` | Add connection error handling in `_search_sources()` and `verify_mpn()` with cache fallback |
| `src/kipart_search/gui/main_window.py` | Update `_update_status()` to show data mode; update `SearchWorker` and `ScanWorker` to handle connection errors gracefully |
| `tests/core/test_offline_operation.py` | New: tests for is_local property, offline fallback, cache serving when source fails |

### Files NOT to Modify

- `core/cache.py` — cache is already offline-capable; no changes needed
- `core/models.py` — no model changes
- `core/units.py` — query transformation is offline by design
- `gui/download_dialog.py` — download is an online operation, unrelated
- `gui/results_table.py` — results display is source-agnostic
- `gui/verify_panel.py` — verification panel displays whatever the scan worker provides
- `gui/search_bar.py` — search bar is UI-only
- `gui/kicad_bridge.py` — KiCad connection is local (IPC socket), not network

### What This Story Does NOT Include

- Active network connectivity monitoring/polling (reactive detection only)
- "Go online" / "Go offline" toggle in the UI
- Automatic retry when network comes back (user re-runs search manually)
- DigiKey/Mouser API adapter implementation (Phase 2, Epic scope TBD)
- Cache warming or pre-fetching for offline use
- Offline indicator icon/badge in the toolbar (status bar text is sufficient)
- Settings dialog for offline mode preferences (Epic 6 scope)

### Previous Story Intelligence (from Story 4.1 and 4.2)

Key learnings to apply:
- `sqlite3.OperationalError` is already caught gracefully in cache helpers (`_cache_get`, `_cache_put`) — same pattern for source errors
- Error handling pattern: catch, log warning, continue without crashing — never let a source failure block the app
- `SearchOrchestrator` already has `_cache_get()` / `_cache_put()` helpers with graceful error handling — extend this pattern for source connection errors
- `ScanWorker` emits `error` signal on unhandled exceptions — ensure connection errors are caught BEFORE they propagate to the error signal
- Test count before this story: 284 passed, 1 pre-existing failure (unrelated `test_central_widget_is_shrinkable_placeholder`)
- `_update_status()` already builds source text dynamically — extend it, don't rewrite
- `LogHandler` captures all `logging` output — no special log panel integration needed

### Git Intelligence

Recent commit patterns:
- `1c72d27` Add SQLite query cache with code review fixes (Story 4.1)
- Imperative mood commit messages with story reference
- Code review fixes as separate commits
- Stories 4.1-4.2 established the cache and download infrastructure this story builds on
- `search.py` is small (170 lines) — connection error handling is the main addition
- `main_window.py` changes should be minimal — only `_update_status()` and worker error handling

### Testing Notes

- Use `tmp_path` fixture for any file operations
- Create a mock `DataSource` subclass that raises connection errors to test offline fallback
- Test that `SearchOrchestrator` returns local results when an API source fails
- Test that cache serves results when source raises an exception
- No network calls in tests — mock all external sources
- Existing tests must continue passing (284 tests)

### Scope Calibration

This is a **small story** — primarily adding:
1. One property (`is_local`) on the DataSource ABC + override in JLCPCBSource (~4 lines)
2. Try/except wrapping in `_search_sources()` and `verify_mpn()` (~20 lines)
3. Minor `_update_status()` enhancement for future source status (~10 lines)
4. Worker error handling improvements (~10 lines)
5. Tests (~50-80 lines)

Total new code: ~100-120 lines. Do NOT over-engineer this.

### Project Structure Notes

- All paths follow existing `src/kipart_search/` layout
- New test file: `tests/core/test_offline_operation.py`
- No new modules or packages — extends existing `sources.py`, `search.py`, `main_window.py`

### References

- [Source: _bmad-output/planning-artifacts/epics.md — Epic 4, Story 4.3]
- [Source: _bmad-output/planning-artifacts/prd.md — FR31 (Cached results offline), FR33 (Full offline use), FR35 (Data mode indicator), NFR9 (Graceful degradation)]
- [Source: _bmad-output/planning-artifacts/architecture.md — ADR-01 (Cache DB), Thread Safety, Cross-Component Dependencies]
- [Source: _bmad-output/planning-artifacts/prd.md — Offline Capabilities section]
- [Source: _bmad-output/project-context.md — Graceful degradation rules, error handling patterns]
- [Source: CLAUDE.md — DataSource ABC pattern, coding style]
- [Source: 4-1-sqlite-query-cache.md — Cache-aside pattern, error handling, test patterns]
- [Source: 4-2-jlcpcb-database-download-and-refresh.md — Atomic replacement, integrity checks, graceful degradation]

## Dev Agent Record

### Agent Model Used

Claude Opus 4.6 (1M context)

### Debug Log References

None — clean implementation, no debug issues encountered.

### Completion Notes List

- Added `is_local` property to `DataSource` ABC (returns `False`) and overridden to `True` in `JLCPCBSource` — future API sources inherit the default `False`
- Added try/except connection error handling in `SearchOrchestrator._search_sources()` and `verify_mpn()` — catches any exception from source queries, logs warning, continues with other sources
- Updated `_update_status()` in `main_window.py` to iterate active sources via orchestrator, distinguishing local vs online sources with `[Local DB]` badge when no API sources are active
- Task 3 (worker offline fallback) required no additional code — connection errors are handled at the orchestrator level (core layer), workers delegate to orchestrator and already handle top-level exceptions
- Task 4 (local workflow verification) confirmed by code review — FTS5 search, board scan, BOM export, and cache serving all use local data paths with no network calls
- Fixed pre-existing test `test_sources_label_no_db` that broke because it only nulled `_jlcpcb_source` without clearing orchestrator sources — now also resets orchestrator
- 13 new tests, all passing. Full suite: 297 passed, 1 pre-existing failure (unrelated `test_central_widget_is_shrinkable_placeholder`)

### Change Log

- 2026-03-19: Story 4.3 implementation complete — is_local property, offline error handling, status bar data mode, 13 tests
- 2026-03-19: Code review fixes — narrowed `except Exception` to `except (OSError, ConnectionError)` in search.py; corrected File List to exclude changes already committed in Story 4.2

### File List

- `src/kipart_search/core/search.py` — Added connection error handling in `_search_sources()` and `verify_mpn()` with `(OSError, ConnectionError)` catch
- `tests/core/test_offline_operation.py` — New: 13 tests for is_local, offline fallback, cache serving, JLCPCB offline
- `tests/test_main_window_docks.py` — Fixed `test_sources_label_no_db` to also reset orchestrator; added SearchOrchestrator import

_Note: `is_local` property (sources.py) and `_update_status()` rewrite (main_window.py) were committed in Story 4.2 (ed28e0c)._
