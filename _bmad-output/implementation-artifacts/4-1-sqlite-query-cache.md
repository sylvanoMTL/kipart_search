# Story 4.1: SQLite Query Cache

Status: done

## Story

As a designer,
I want search results and part data cached locally with configurable expiration,
So that repeat searches are instant and I can work offline after initial queries.

## Acceptance Criteria

1. **Given** the application is running, **when** a search query returns results from any source, **then** the results are stored in `~/.kipart-search/cache.db` (separate from the JLCPCB parts database) with the cache key format `{source}:{query_type}:{sha256(normalized_query)}` (ADR-01), **and** each cache entry stores: key, source, query_type, data (JSON string), created_at (Unix timestamp), ttl_seconds.

2. **Given** the same search query is executed again, **when** a valid (non-expired) cache entry exists, **then** cached results are served immediately without a network call (FR31), **and** the log panel shows a cache hit indicator (e.g. "JLCPCB: served from cache").

3. **Given** a cache entry exists but has expired, **when** the query is executed, **then** a fresh API/database query is made and the cache entry is updated.

4. **Given** default TTL values, **when** cache entries are created, **then** pricing/stock data expires after 4 hours, parametric data after 7-30 days, datasheet URLs are cached indefinitely (FR30).

5. **Given** the cache database, **then** it uses WAL journal mode for concurrent read access from GUI and worker threads.

6. **Given** `core/cache.py`, **then** it exposes: `get(key)`, `put(key, data, source, query_type, ttl)`, `invalidate(source=None)`, `is_expired(entry)` — zero GUI dependencies.

## Tasks / Subtasks

- [x] Task 1: Upgrade existing `core/cache.py` to match ADR-01 contract (AC: #1, #5, #6)
  - [x] 1.1 Add WAL journal mode: `conn.execute("PRAGMA journal_mode=WAL")` in `_get_conn()`
  - [x] 1.2 Add `invalidate(source: str | None = None)` method — deletes all entries for a source, or all entries if source is None
  - [x] 1.3 Add `is_expired(key: str) -> bool` convenience method
  - [x] 1.4 Add `stats() -> dict` method returning entry count, total size, oldest entry (for debugging/logging)
  - [x] 1.5 Ensure `_get_conn()` uses `check_same_thread=False` for QThread compatibility (matches JLCPCBSource pattern)

- [x] Task 2: Integrate cache into `SearchOrchestrator` (AC: #1, #2, #3)
  - [x] 2.1 Add `cache: QueryCache | None` parameter to `SearchOrchestrator.__init__()`
  - [x] 2.2 In `_search_sources()`, check cache before calling `source.search()` for each source+variant
  - [x] 2.3 After successful `source.search()`, store results in cache via `cache.put()`
  - [x] 2.4 Serialize `PartResult` to/from JSON using `dataclasses.asdict()` and a reconstruction helper
  - [x] 2.5 In `verify_mpn()`, check cache before calling `source.get_part()`

- [x] Task 3: Add PartResult serialization helpers (AC: #1)
  - [x] 3.1 Add `to_dict() -> dict` method or standalone `part_result_to_dict(part: PartResult) -> dict` in `core/models.py`
  - [x] 3.2 Add `part_result_from_dict(d: dict) -> PartResult` reconstruction function in `core/models.py`
  - [x] 3.3 Handle nested dataclasses (`PriceBreak`, `ParametricValue`) in serialization
  - [x] 3.4 Ensure round-trip fidelity: `from_dict(to_dict(part)) == part` for all fields

- [x] Task 4: Wire cache into GUI layer (AC: #2)
  - [x] 4.1 Instantiate `QueryCache` in `main_window.py` at app startup
  - [x] 4.2 Pass cache instance to `SearchOrchestrator` constructor
  - [x] 4.3 Log cache hits to the log panel: "[HH:MM:SS] {source}: served from cache"
  - [x] 4.4 Log cache misses (fresh queries) normally: "[HH:MM:SS] {source}: N results"

- [x] Task 5: Add TTL assignment logic (AC: #4)
  - [x] 5.1 Each DataSource query type gets appropriate TTL — `search` queries use `TTL_PARAMETRIC` (7 days), `get_part` for MPN verification uses `TTL_PARAMETRIC`
  - [x] 5.2 Future API sources (DigiKey, Mouser) will use `TTL_PRICING` for pricing/stock data — document this in code comments
  - [x] 5.3 JLCPCB local database queries: cache with `TTL_PARAMETRIC` (avoids re-running FTS5 for identical queries within session)

- [x] Task 6: Add cache management (AC: #6)
  - [x] 6.1 Add `cache.close()` call in `MainWindow.closeEvent()` for clean shutdown
  - [x] 6.2 Handle `sqlite3.OperationalError` gracefully — if cache DB is corrupt or locked, log warning and continue without cache (never crash)

- [x] Task 7: Write tests (all ACs)
  - [x] 7.1 Test cache `put()` and `get()` round-trip with PartResult data
  - [x] 7.2 Test TTL expiry — expired entries return None
  - [x] 7.3 Test indefinite TTL (ttl=0) entries never expire
  - [x] 7.4 Test `invalidate(source)` clears only that source's entries
  - [x] 7.5 Test `invalidate(None)` clears all entries
  - [x] 7.6 Test WAL mode is active after connection
  - [x] 7.7 Test cache key normalization — same query with different case produces same key
  - [x] 7.8 Test SearchOrchestrator cache integration — second identical search returns cached results
  - [x] 7.9 Test PartResult round-trip serialization (`to_dict` → `from_dict`)
  - [x] 7.10 Test graceful degradation when cache is None (SearchOrchestrator works without cache)

## Dev Notes

### CRITICAL: Existing cache.py Already Exists

`core/cache.py` (86 lines) is **already implemented** but **completely unused** — zero imports anywhere in the codebase. The existing implementation covers:
- SHA256 key generation: `_make_key(source, query_type, query)`
- `get(source, query_type, query)` with TTL checking
- `put(source, query_type, query, value, ttl)` with JSON serialization
- `close()` for clean shutdown
- TTL constants: `TTL_PRICING=4h`, `TTL_PARAMETRIC=7d`, `TTL_DATASHEET=indefinite`
- Schema: `cache(key, value, source, query_type, created_at, ttl)`

**What needs to change:**
1. Add WAL journal mode (missing)
2. Add `check_same_thread=False` (missing — needed for QThread workers)
3. Add `invalidate()` method (missing from ADR-01 contract)
4. Add `is_expired()` method (missing from ADR-01 contract)
5. Wire it into `SearchOrchestrator` and `main_window.py`
6. Add PartResult serialization (currently stores raw dicts, needs PartResult↔dict conversion)

**Do NOT rewrite cache.py from scratch** — extend the existing implementation.

### Architecture Constraints

- **Core/GUI separation**: `core/cache.py` has ZERO GUI imports. Cache instantiation happens in `gui/main_window.py`, passed to `SearchOrchestrator` via constructor injection.
- **Error handling**: Cache failures never crash the app. If `cache.db` is corrupt or locked, log a warning and proceed without caching. The search workflow must work identically with or without cache.
- **Thread safety**: Use `check_same_thread=False` + WAL mode. One connection per `QueryCache` instance. The SQLite WAL mode allows concurrent readers (search workers) with a single writer.
- **No new QThread classes**: Cache reads/writes happen inside existing search worker threads. No dedicated cache worker needed.
- **JSON serialization only**: Store `PartResult` as JSON strings via `json.dumps(dataclasses.asdict(part))`. Never use pickle (per architecture anti-patterns).

### SearchOrchestrator Integration Pattern

The cache sits between the orchestrator and sources — a cache-aside pattern:

```python
def _search_sources(self, sources, query, filters, limit):
    variants = generate_query_variants(query)
    seen = set()
    results = []

    for variant in variants:
        for source in sources:
            # Check cache first
            if self._cache:
                cached = self._cache.get(source.name, "search", variant)
                if cached is not None:
                    # Deserialize cached PartResults
                    for d in cached:
                        part = part_result_from_dict(d)
                        key = (part.mpn, part.source)
                        if key not in seen:
                            seen.add(key)
                            results.append(part)
                    continue  # Skip API call

            # Cache miss — query source
            parts = source.search(variant, filters, limit)

            # Store in cache
            if self._cache and parts:
                self._cache.put(
                    source.name, "search", variant,
                    [part_result_to_dict(p) for p in parts],
                    TTL_PARAMETRIC,
                )

            for part in parts:
                key = (part.mpn, part.source)
                if key not in seen:
                    seen.add(key)
                    results.append(part)

    return results
```

### PartResult Serialization

`PartResult` contains nested dataclasses (`price_breaks: list[PriceBreak]`, `parametrics: list[ParametricValue]`). Use `dataclasses.asdict()` for serialization and explicit reconstruction for deserialization:

```python
def part_result_to_dict(part: PartResult) -> dict:
    return dataclasses.asdict(part)

def part_result_from_dict(d: dict) -> PartResult:
    d["price_breaks"] = [PriceBreak(**pb) for pb in d.get("price_breaks", [])]
    d["parametrics"] = [ParametricValue(**pv) for pv in d.get("parametrics", [])]
    d["confidence"] = Confidence(d["confidence"]) if d.get("confidence") else None
    return PartResult(**d)
```

### Cache Key Strategy

The existing `_make_key()` already implements ADR-01's key format:
- `{source}:{query_type}:{sha256(normalized_query)}`
- Normalization: lowercase the entire key string before hashing
- `query_type` values: `"search"` (parametric search), `"get_part"` (MPN lookup), `"datasheet"` (URL verification — future)

**Important**: Filters are NOT included in the cache key currently. For Phase 1 (JLCPCB-only), this is fine because JLCPCB local search applies filters post-query. When API sources with server-side filtering are added (Phase 2), the cache key must incorporate filter parameters. Add a TODO comment for this.

### Logging Pattern

Cache hit/miss logging should go through the existing log infrastructure:

```python
import logging
log = logging.getLogger(__name__)

# In SearchOrchestrator:
log.info("%s: served from cache", source.name)   # cache hit
log.info("%s: %d results", source.name, len(parts))  # cache miss
```

The `main_window.py` `LogHandler` already captures `logging` output and displays it in the log panel with timestamps.

### Files to Modify

| File | Changes |
|------|---------|
| `src/kipart_search/core/cache.py` | Add WAL mode, `check_same_thread=False`, `invalidate()`, `is_expired()`, `stats()` |
| `src/kipart_search/core/models.py` | Add `part_result_to_dict()` and `part_result_from_dict()` serialization helpers |
| `src/kipart_search/core/search.py` | Add `cache` parameter to `__init__`, integrate cache-aside in `_search_sources()` and `verify_mpn()` |
| `src/kipart_search/gui/main_window.py` | Instantiate `QueryCache`, pass to `SearchOrchestrator`, close on exit |
| `tests/test_sqlite_query_cache.py` | New: cache unit tests, round-trip tests, orchestrator integration tests |

### Files NOT to Modify

- `core/sources.py` — sources are unaware of the cache; caching is the orchestrator's responsibility
- `gui/search_bar.py` — no UI changes needed; cache is transparent to search UI
- `gui/verify_panel.py` — verification uses `verify_mpn()` which benefits from cache transparently
- `gui/results_table.py` — results model doesn't change; cached results look identical
- `core/units.py` — query variant generation is cache-key-agnostic

### What This Story Does NOT Include

- Cache statistics UI (no settings dialog for cache size/clear — Epic 6 scope)
- Per-source cache configuration (all sources use the same TTL constants — sufficient for Phase 1)
- Filter-aware cache keys (JLCPCB applies filters post-query; API sources with server-side filtering are Phase 2)
- Database download/refresh (Story 4-2)
- Offline mode detection or status bar updates (Story 4-3)
- Cache warming or preloading
- Cache size limits or eviction policies (SQLite DB grows unbounded for now — acceptable for a desktop app with ~1000s of queries)

### Existing Code Patterns to Follow

**Connection pattern** (from JLCPCBSource):
```python
def _get_conn(self) -> sqlite3.Connection:
    if self._conn is None:
        self._conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
        self._conn.execute("PRAGMA journal_mode=WAL")
    return self._conn
```

**Error handling pattern** (from architecture):
```python
try:
    cached = self._cache.get(source.name, "search", variant)
except sqlite3.OperationalError:
    log.warning("Cache read failed, querying source directly")
    cached = None
```

**Logging pattern**:
```python
import logging
log = logging.getLogger(__name__)
```

**Import convention**: `from kipart_search.core.cache import QueryCache, TTL_PARAMETRIC`

### Project Structure Notes

- All paths follow existing `src/kipart_search/` layout
- New test file: `tests/test_sqlite_query_cache.py`
- No new modules or packages — extends existing `cache.py` and wires into existing modules
- `QueryCache` constructor takes optional `db_path` — tests pass a temp file, production uses default `~/.kipart-search/cache.db`

### Previous Story Intelligence (from Story 3.4)

Key learnings to apply:
- `check_same_thread=False` is required for SQLite connections used from QThread workers
- `ScanWorker` and search workers run in QThread — any cache calls from workers need thread-safe connections
- Signal conventions: signals emit plain Python types — cache integration happens before signal emission (inside the worker's `run()` method)
- Test count before this story: 255 passed, 1 pre-existing failure (unrelated)
- `verify_panel.py` calls `orchestrator.verify_mpn()` during scan — this will automatically benefit from cache once wired

### Git Intelligence

Recent commit patterns:
- Imperative mood commit messages with story reference
- Code review fixes as separate commits
- All stories maintain full test coverage
- `main_window.py` is the primary integration point for new infrastructure
- `search.py` (SearchOrchestrator) is small (92 lines) — cache integration is the biggest change it will see

### References

- [Source: _bmad-output/planning-artifacts/architecture.md — ADR-01 (Separate Cache Database)]
- [Source: _bmad-output/planning-artifacts/architecture.md — Cache Module Contract, Database & Cache Patterns]
- [Source: _bmad-output/planning-artifacts/epics.md — Epic 4, Story 4.1]
- [Source: _bmad-output/planning-artifacts/prd.md — FR30 (Cache with TTL), FR31 (Serve cached offline)]
- [Source: CLAUDE.md — Caching section, coding style preferences]
- [Source: _bmad-output/project-context.md — SQLite3 usage, JSON serialization patterns]
- [Source: 3-4-stale-data-indicators.md — Previous story dev notes, test patterns, QThread patterns]

## Dev Agent Record

### Agent Model Used

Claude Opus 4.6 (1M context)

### Debug Log References

- Fixed Confidence enum JSON serialization: `dataclasses.asdict()` preserves Enum objects which aren't JSON-serializable. Added explicit `.value` conversion in `part_result_to_dict()`.

### Completion Notes List

- Upgraded `core/cache.py` with WAL journal mode, `check_same_thread=False`, `invalidate()`, `is_expired()`, and `stats()` methods — extending existing implementation as instructed.
- Added `part_result_to_dict()` and `part_result_from_dict()` serialization helpers in `core/models.py` with proper handling of nested dataclasses and Confidence enum.
- Integrated cache-aside pattern into `SearchOrchestrator` — both `_search_sources()` and `verify_mpn()` check cache before querying sources. Graceful error handling via `_cache_get()` / `_cache_put()` helpers that catch `sqlite3.OperationalError`.
- Wired cache into `MainWindow`: instantiation at startup (with graceful fallback if init fails), passed to orchestrator via constructor injection, closed on app exit.
- All search and MPN verification queries use `TTL_PARAMETRIC` (7 days). TODO comment added for filter-aware cache keys in Phase 2.
- Cache hit/miss logging goes through `logging.getLogger(__name__)` which the existing `LogHandler` captures for the log panel.
- 19 new tests covering all ACs. Full suite: 274 passed, 1 pre-existing failure (unrelated).

### Change Log

- 2026-03-19: Implemented SQLite query cache (Story 4.1) — cache-aside pattern in SearchOrchestrator, PartResult serialization, 19 new tests

### File List

- `src/kipart_search/core/cache.py` — Added WAL mode, check_same_thread=False, invalidate(), is_expired(), stats(), logging
- `src/kipart_search/core/models.py` — Added dataclasses import, part_result_to_dict(), part_result_from_dict()
- `src/kipart_search/core/search.py` — Added cache parameter, cache-aside in _search_sources() and verify_mpn(), _cache_get/_cache_put helpers
- `src/kipart_search/gui/main_window.py` — Added QueryCache import, _init_cache(), cache instantiation, cache.close() in closeEvent, cache passed to orchestrator
- `tests/core/test_sqlite_query_cache.py` — New: 19 tests for cache, serialization, orchestrator integration, graceful degradation
