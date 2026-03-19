# Story 3.2: Two-Mode Search Architecture (Specific vs Unified)

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a designer,
I want to choose between searching a single source or all enabled sources at once,
So that I get fast results when I know which source to use, and comprehensive results when I'm discovering parts.

## Acceptance Criteria

1. **Given** the search panel with a source selector dropdown
   **When** a specific source is selected (e.g. "JLCPCB")
   **Then** the search query is sent only to that source (Specific mode) (UX-DR11)
   **And** the results table does not show a "Source" column
   **And** filters apply locally to the returned results

2. **Given** "All Sources" is selected in the source selector
   **When** a search is executed
   **Then** the query is sent to all enabled sources in parallel (Unified mode) (UX-DR11)
   **And** a "Source" column appears in the results table showing which source each result came from
   **And** results from multiple sources are displayed as they arrive (incremental, no blocking)

3. **Given** only one source is configured (e.g. JLCPCB only)
   **When** the source selector is displayed
   **Then** it shows "JLCPCB" and "All Sources" (which behaves identically to JLCPCB-only in this case)

4. **Given** the user switches source selection
   **When** a query is already in the search box
   **Then** the query persists (not cleared) — switching sources re-runs the same query if the user clicks Search (UX spec: "Query persists until cleared — switching sources re-runs the same query")

5. **Given** the user is in Specific mode (single source)
   **When** results are displayed and filtered
   **Then** filters apply locally (same behavior as Story 3.1) — no API re-query

6. **Given** the user is in Unified mode (All Sources)
   **When** results are displayed and filtered
   **Then** filters apply locally to the merged result set (cascade back to APIs is deferred — see Scope section)

## Tasks / Subtasks

- [x] Task 1: Add source selector QComboBox to SearchBar (AC: #1, #3)
  - [x]Add a QComboBox `_source_selector` in SearchBar row 1, before the search input
  - [x]Populate with "All Sources" + names of configured sources from SearchOrchestrator
  - [x]Add `source_changed = Signal(str)` — emits the selected source name (or "All Sources")
  - [x]Add `set_sources(sources: list[str])` method to update the dropdown when sources change
  - [x]Add `selected_source` property returning current selection
  - [x]Default selection: "All Sources" (UX spec: "'All Sources' is the default for discovery")

- [x] Task 2: Modify SearchBar to emit source with search (AC: #1, #2, #4)
  - [x]Change `search_requested` signal from `Signal(str)` to `Signal(str, str)` — `(query, source_name)`
  - [x]`_on_search()` emits `(query, self.selected_source)`
  - [x]Source selector does NOT auto-trigger search on change — user must click Search (avoids accidental slow unified search)

- [x] Task 3: Make Source column dynamic in ResultsTable (AC: #1, #2)
  - [x]Add `set_source_column_visible(visible: bool)` method to ResultsTable
  - [x]When Specific mode: hide the "Source" column via `self.table.setColumnHidden(source_col_index, True)`
  - [x]When Unified mode: show the "Source" column
  - [x]Add "Source" to FILTERABLE_FIELDS so it appears as a filter dropdown in Unified mode
  - [x]Keep "Source" in COLUMNS list always (data still stored) — just visually hidden in Specific mode

- [x] Task 4: Update SearchOrchestrator for single-source search (AC: #1, #2)
  - [x]Add `search_source(query, source_name, filters, limit)` method — searches a single named source
  - [x]Add `get_source_names() -> list[str]` method — returns names of configured sources
  - [x]Existing `search()` method becomes the "All Sources" path (unchanged logic)

- [x] Task 5: Update MainWindow search flow (AC: #1, #2, #3)
  - [x]Update `_on_search(query, source)` to accept source parameter
  - [x]If source is a specific source name: call `orchestrator.search_source(query, source_name)`
  - [x]If source is "All Sources": call existing `orchestrator.search(query)` (unchanged)
  - [x]Call `results_table.set_source_column_visible(source != "All Sources")` — wait, inverted: hide Source column in Specific mode
  - [x]On startup: call `search_bar.set_sources(orchestrator.get_source_names())` after source init
  - [x]After database download: refresh search bar source list
  - [x]Update `SearchWorker` to accept optional source_name parameter

- [x] Task 6: Update SearchWorker for source-aware search (AC: #1, #2)
  - [x]Add `source_name: str | None` parameter to SearchWorker.__init__
  - [x]In `run()`: if source_name is set and not "All Sources", use `orchestrator.search_source()`
  - [x]If source_name is "All Sources" or None, use existing `orchestrator.search()` path
  - [x]Log messages reflect which source(s) are being queried

- [x] Task 7: Write tests (AC: #1-#6)
  - [x]Test SearchBar source selector: populated with source names + "All Sources"
  - [x]Test SearchBar emits (query, source) on search
  - [x]Test SearchBar.selected_source returns correct value
  - [x]Test SearchBar.set_sources updates the dropdown
  - [x]Test ResultsTable.set_source_column_visible hides/shows Source column
  - [x]Test Source appears in FILTERABLE_FIELDS when visible
  - [x]Test SearchOrchestrator.search_source queries only the named source
  - [x]Test SearchOrchestrator.get_source_names returns configured source names
  - [x]Follow `pytest.importorskip("PySide6")` pattern from `tests/test_filter_row.py`

## Dev Notes

### Architecture Compliance

- **Core/GUI separation**: SearchOrchestrator changes (`search_source`, `get_source_names`) are in `core/search.py` — zero GUI deps. Source selector is a GUI widget in `search_bar.py`.
- **ADR-05 (Multi-Source Deduplication)**: Not needed yet — only JLCPCB exists as a source. When future sources are added (DigiKey, Mouser), the deduplication logic in `search()` will handle merging by MPN+manufacturer. This story does NOT implement deduplication — it creates the framework for multi-source routing.
- **ADR-07 (QDockWidget)**: Source selector lives inside the Search dock's SearchBar widget. No new docks.
- **UX-DR11**: Two-mode search architecture — this is the exact spec being implemented.

### Existing Code to Reuse — DO NOT REINVENT

- **`gui/search_bar.py`** (88 lines): Add source selector QComboBox to row 1 (before query input). The existing `search_requested = Signal(str)` changes to `Signal(str, str)`. All other SearchBar logic (transform preview, symbol buttons) is unchanged.
- **`gui/results_table.py`** (322 lines): `COLUMNS` already includes "Source" at index 5. The `set_results()` method already populates Source column data. Only need `set_source_column_visible()` to hide/show it. FilterRow already works dynamically — adding "Source" to `FILTERABLE_FIELDS` conditionally is the only filter change.
- **`core/search.py`** (67 lines): `SearchOrchestrator` already has `active_sources` property and `search()` method. Add `search_source()` as a thin wrapper that filters to one source. Add `get_source_names()` to expose source names.
- **`core/sources.py`**: `DataSource.name` attribute already exists on each source (e.g. `JLCPCBSource.name = "JLCPCB"`). No changes needed.
- **`gui/main_window.py`** (692 lines): `_on_search(query)` signature changes to `_on_search(query, source)`. `SearchWorker` gains an optional `source_name` parameter. Source list initialization happens in `_init_jlcpcb_source()` and `_on_db_downloaded()`.

### Source Column Visibility Strategy

The `COLUMNS` list in `results_table.py` always includes "Source" at index 5. Data is always stored. The column is hidden/shown via `QTableWidget.setColumnHidden()`:

```python
def set_source_column_visible(self, visible: bool) -> None:
    """Show or hide the Source column based on search mode."""
    source_col = COLUMNS.index("Source")
    self.table.setColumnHidden(source_col, not visible)
```

This avoids rebuilding the table or changing column indices. `get_result()` and `_original_index()` are unaffected because they use `UserRole` data, not column positions.

### FILTERABLE_FIELDS: Conditional Source Filter

In Unified mode, "Source" should appear as a filter dropdown. In Specific mode, it shouldn't (only one source — useless filter). Two approaches:

**Recommended approach**: Make `FILTERABLE_FIELDS` a module-level constant that always includes Source:

```python
FILTERABLE_FIELDS: list[tuple[str, str]] = [
    ("Manufacturer", "manufacturer"),
    ("Package", "package"),
    ("Category", "category"),
    ("Source", "source"),
]
```

The existing FilterRow logic in `update_filters()` already skips fields with < 2 unique values. In Specific mode, all results have the same source → < 2 unique values → Source dropdown is automatically excluded. No special-casing needed.

### Signal Signature Change

`SearchBar.search_requested` changes from `Signal(str)` to `Signal(str, str)`. This is a breaking change for all signal connections:

- `gui/main_window.py` line 150: `self.search_bar.search_requested.connect(self._on_search)` — update `_on_search` signature
- No other modules connect to this signal.

### SearchWorker Source-Aware Flow

```python
class SearchWorker(QThread):
    def __init__(self, orchestrator, query, source_name=None):
        ...
        self.source_name = source_name

    def run(self):
        if self.source_name and self.source_name != "All Sources":
            results = self.orchestrator.search_source(self.query, self.source_name)
        else:
            results = self.orchestrator.search(self.query, limit=200)
```

### Source Selector Placement

The source selector goes in row 1 of SearchBar, before the search input:

```
[Source: JLCPCB ▼] [Search box: "100nF 0805"] [Ω] [±] [µ] [Search]
```

Use a QComboBox with `SizeAdjustPolicy.AdjustToContents`. Label is not needed — the dropdown self-describes ("JLCPCB" or "All Sources").

### Current State: Only JLCPCB Exists

Currently the only configured source is JLCPCB. The source selector will show:
- "All Sources"
- "JLCPCB"

Both behave identically (single source). But the plumbing is in place for when DigiKey/Mouser adapters are added in Epic 4+. The source selector auto-updates when new sources are registered.

### What This Story Does NOT Include

- **No filter cascade back to APIs** — UX spec mentions this for Unified mode, but it requires API-specific parametric filter support (DigiKey's `ParametricFilters`, etc.). Deferred to when those adapters exist. For now, all filtering is local.
- **No multi-source deduplication** — ADR-05 defines merge by MPN+manufacturer, but with only JLCPCB there's nothing to merge. The existing `seen_mpns` set in `SearchOrchestrator.search()` handles basic dedup.
- **No incremental result display** — AC #2 mentions "results displayed as they arrive." Currently SearchWorker collects all results then emits once. True incremental display (per-source signals) is deferred to when multiple slow API sources exist. With only JLCPCB (local DB, < 2s), there's nothing to stream incrementally.
- **No source enable/disable UI** — That's Story 6.1 (Source Preferences Dialog).
- **No API key management** — Story 6.1.
- **No new DataSource adapters** — DigiKey/Mouser adapters are Epic 4+.

### Edge Cases

- **No sources configured** (DB not downloaded): Source selector shows only "All Sources" with no specific sources. Search shows "No Data Source" message (existing behavior in `_on_search`).
- **Source added after startup** (DB downloaded during session): `_on_db_downloaded()` must call `search_bar.set_sources()` to refresh the dropdown.
- **Source selector with 1 source**: Shows "All Sources" and "JLCPCB". Both work identically. This is expected — the selector establishes the pattern for when more sources are added.

### Project Structure Notes

- **Modified**: `src/kipart_search/gui/search_bar.py` — add source selector QComboBox, change signal signature
- **Modified**: `src/kipart_search/gui/results_table.py` — add `set_source_column_visible()`, add "Source" to FILTERABLE_FIELDS
- **Modified**: `src/kipart_search/core/search.py` — add `search_source()`, `get_source_names()`
- **Modified**: `src/kipart_search/gui/main_window.py` — update `_on_search` signature, wire source selector, update SearchWorker
- **New**: `tests/test_two_mode_search.py` — tests for source selector, source-column visibility, orchestrator source routing
- No core/models.py changes needed — PartResult.source already exists

### Previous Story Intelligence (Story 3.1)

Key learnings from Story 3.1 (Dynamic Filter Row):
- FilterRow in `results_table.py` uses `FILTERABLE_FIELDS` list of tuples — adding `("Source", "source")` follows the same pattern
- `blockSignals(True/False)` pattern during combo population — use this when populating the source selector
- `update_filters()` already skips fields with < 2 unique values — Source filter auto-hides in Specific mode
- `pytest.importorskip("PySide6")` pattern works for GUI tests without `pytest-qt`
- 201 tests currently pass — run full suite after implementation to verify zero regressions
- Story 3.1 code review had 0 HIGH/MEDIUM issues — aim for clean initial implementation

### Git Intelligence

Recent commits:
```
cb34742 Add dynamic filter row replacing hardcoded manufacturer/package filters (Story 3.1)
35bf071 Update sprint status: epic-2 done, create story 3-1 dynamic filter row
24f7f3f Code review fixes for Story 2.4: prevent double preview rebuild and remove redundant fields
1cbb122 Code review fixes for Story 2.4: sync menu state, format combo, and move DNP to core
0172edc Add BOM export dialog with template selection and preview (Story 2.4)
```

Files to modify:
- MODIFY: `src/kipart_search/gui/search_bar.py` (add source selector, change signal)
- MODIFY: `src/kipart_search/gui/results_table.py` (source column visibility, FILTERABLE_FIELDS)
- MODIFY: `src/kipart_search/core/search.py` (search_source, get_source_names)
- MODIFY: `src/kipart_search/gui/main_window.py` (search flow, source wiring)
- NEW: `tests/test_two_mode_search.py`

### Anti-Patterns to Avoid

- Do NOT create a separate SearchMode enum or mode-tracking state — the source selector value IS the mode. "All Sources" = Unified. Anything else = Specific.
- Do NOT modify `core/models.py` — PartResult already has `source` field
- Do NOT add incremental per-source result signals yet — with only JLCPCB, it adds complexity for no benefit
- Do NOT implement filter cascade to APIs — no API adapters exist yet to cascade to
- Do NOT auto-trigger search on source selector change — user must click Search to avoid surprise slow queries
- Do NOT remove the Source column from COLUMNS — always store data, just hide the column visually
- Do NOT use `QButtonGroup` or radio buttons for source selector — QComboBox is compact and scales to many sources
- Do NOT hardcode "JLCPCB" anywhere in the mode logic — use `DataSource.name` dynamically

### Cross-Story Dependencies

- **Story 3.1** (done): Dynamic FilterRow — Source will auto-appear as filter in Unified mode via FILTERABLE_FIELDS
- **Story 3.3** (future): Verification Dashboard Enhancements — guided search uses SearchBar's `search_requested` signal (signature change affects it)
- **Story 6.1** (future): Source Preferences Dialog — will call `search_bar.set_sources()` when sources are enabled/disabled
- **Epic 4** (future): When DigiKey/Mouser adapters are added, they register with SearchOrchestrator and auto-appear in source selector

### References

- [Source: _bmad-output/planning-artifacts/epics.md — Epic 3, Story 3.2]
- [Source: _bmad-output/planning-artifacts/ux-design-specification.md — "Search Architecture — Two Modes" (lines 210-248)]
- [Source: _bmad-output/planning-artifacts/ux-design-specification.md — "Two-mode search (consistent UI, different backend)" table (lines 904-913)]
- [Source: _bmad-output/planning-artifacts/ux-design-specification.md — "Filter behavior rules" (lines 915-920)]
- [Source: _bmad-output/planning-artifacts/ux-design-specification.md — UX-DR11]
- [Source: _bmad-output/planning-artifacts/architecture.md — ADR-05: Multi-Source Deduplication]
- [Source: _bmad-output/planning-artifacts/architecture.md — ADR-07: QDockWidget Panel Migration]
- [Source: src/kipart_search/gui/search_bar.py — current SearchBar (88 lines)]
- [Source: src/kipart_search/gui/results_table.py — COLUMNS, FILTERABLE_FIELDS, FilterRow]
- [Source: src/kipart_search/core/search.py — SearchOrchestrator]
- [Source: src/kipart_search/gui/main_window.py — _on_search, SearchWorker]
- [Source: _bmad-output/implementation-artifacts/3-1-dynamic-filter-row.md — Previous story intelligence]

## Dev Agent Record

### Agent Model Used

Claude Opus 4.6 (1M context)

### Debug Log References

None — clean implementation, no debug issues encountered.

### Completion Notes List

- Added QComboBox source selector to SearchBar row 1, before the query input. Default: "All Sources". Populated dynamically via `set_sources()`.
- Changed `search_requested` signal from `Signal(str)` to `Signal(str, str)` — emits `(query, source_name)`.
- Added `selected_source` property, `set_sources()` method, and `source_changed` signal to SearchBar.
- Added `set_source_column_visible()` to ResultsTable — hides/shows the Source column via `setColumnHidden()` without rebuilding the table.
- Added `("Source", "source")` to `FILTERABLE_FIELDS` — auto-excluded by FilterRow when < 2 unique values (Specific mode), auto-shown in Unified mode.
- Added `search_source()` and `get_source_names()` to SearchOrchestrator in `core/search.py` (zero GUI deps).
- Updated `SearchWorker` to accept optional `source_name` parameter, routing to `search_source()` or `search()` accordingly.
- Updated `MainWindow._on_search()` to accept `(query, source)` parameters, control Source column visibility, and pass source to worker.
- `_init_jlcpcb_source()` and `_on_db_downloaded()` now call `search_bar.set_sources()` to refresh the dropdown.
- 21 new tests in `tests/test_two_mode_search.py` covering: source selector population/persistence, signal emission, source column visibility, filter auto-hide, orchestrator source routing.
- All 222 tests pass (201 existing + 21 new), zero regressions.

### Change Log

- 2026-03-19: Implemented two-mode search architecture (Story 3.2) — source selector, source-aware search routing, dynamic Source column visibility, 21 tests.
- 2026-03-19: Code review fixes — extracted `_search_sources()` helper to eliminate duplication between `search_source()` and `search()`, fixed `set[str]` → `set[tuple[str, str]]` type annotation.

### File List

- MODIFIED: `src/kipart_search/gui/search_bar.py` — added source selector QComboBox, changed signal signature, added set_sources/selected_source
- MODIFIED: `src/kipart_search/gui/results_table.py` — added set_source_column_visible(), added Source to FILTERABLE_FIELDS
- MODIFIED: `src/kipart_search/core/search.py` — added search_source(), get_source_names()
- MODIFIED: `src/kipart_search/gui/main_window.py` — updated _on_search signature, SearchWorker source_name param, source list refresh
- NEW: `tests/test_two_mode_search.py` — 21 tests for two-mode search architecture
