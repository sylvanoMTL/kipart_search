# Story 3.1: Dynamic Filter Row

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a designer,
I want search result filters that automatically adapt to the data returned by each search,
So that I can narrow results by manufacturer, package, category, or other fields without guessing what's available.

## Acceptance Criteria

1. **Given** a search has returned results in the results table
   **When** the results are displayed
   **Then** a horizontal row of QComboBox dropdowns appears above the results table, with one dropdown per filterable field found in the data (e.g. Manufacturer, Package, Category) (UX-DR9)
   **And** each dropdown is populated with unique values from the returned results for that field, plus an "All" default option
   **And** a result count label shows "X of Y results" reflecting current filter state
   **And** selecting a filter value narrows the displayed results immediately (local filtering)
   **And** clearing a filter (selecting "All") restores results without re-searching
   **And** filters are additive — applying Package: 0805 AND Manufacturer: Murata shows only matching rows (FR3)

2. **Given** no search has been performed yet
   **When** the search panel is displayed
   **Then** the filter row is hidden (no empty dropdowns shown)

3. **Given** a new search is executed
   **When** different results come back with different filterable fields
   **Then** the filter dropdowns are rebuilt to match the new result set (old filters cleared)

4. **Given** results with varying field completeness (e.g. some parts have Category, some don't)
   **When** filters are built
   **Then** only fields with at least 2 unique non-empty values get a dropdown (no point filtering on a single value or all-empty field)

5. **Given** the results table is sorted by clicking a column header
   **When** filters are active
   **Then** sorting and filtering work together correctly — hidden rows stay hidden, visible rows are sorted

6. **Given** the user clears all results or starts a new search
   **When** the filter row is rebuilt
   **Then** previously selected filter values do not carry over — all dropdowns reset to "All"

## Tasks / Subtasks

- [x] Task 1: Replace hardcoded filter row with dynamic `FilterRow` widget (AC: #1, #2, #3, #4)
  - [x] Create a `FilterRow` class (QWidget) that dynamically creates/destroys QComboBox dropdowns
  - [x] Define `FILTERABLE_FIELDS` mapping: field display name → PartResult attribute name (e.g. `{"Manufacturer": "manufacturer", "Package": "package", "Category": "category"}`)
  - [x] Implement `update_filters(results: list[PartResult])` — scans results, creates a dropdown for each field that has ≥2 unique non-empty values
  - [x] Each dropdown: label + QComboBox with "All" default + sorted unique values
  - [x] Add result count label at the right end: "X of Y results"
  - [x] Hide the entire filter row when no results exist (AC #2)
  - [x] Emit a signal (e.g. `filters_changed`) when any dropdown selection changes

- [x] Task 2: Integrate FilterRow into ResultsTable (AC: #1, #5, #6)
  - [x] Remove the existing hardcoded `_filter_mfr` and `_filter_pkg` QComboBox code from `ResultsTable.__init__`
  - [x] Replace with `self._filter_row = FilterRow()` inserted at the same layout position
  - [x] Connect `FilterRow.filters_changed` → `ResultsTable._apply_filters`
  - [x] Update `set_results()` to call `self._filter_row.update_filters(results)` instead of manually populating combos
  - [x] Update `_apply_filters()` to read active filters from `FilterRow.get_active_filters() -> dict[str, str]` and apply all of them
  - [x] Update `clear_results()` to call `self._filter_row.clear()`

- [x] Task 3: Update `_apply_filters` for dynamic multi-field filtering (AC: #1, #5)
  - [x] Replace the hardcoded mfr/pkg filter checks with a loop over `get_active_filters()` dict
  - [x] For each active filter `{attr_name: value}`, check `getattr(part, attr_name) == value`
  - [x] Maintain the result count label update: "X of Y results" (move count label ownership to FilterRow or keep in ResultsTable — either works, but keep a single source of truth)

- [x] Task 4: Write tests (AC: #1-#6)
  - [x] Test FilterRow creates correct dropdowns from varied PartResult data
  - [x] Test FilterRow hides when no results / shows when results arrive
  - [x] Test fields with <2 unique values are excluded
  - [x] Test empty-string values are excluded from dropdown options
  - [x] Test filters_changed signal emits when dropdown selection changes
  - [x] Test get_active_filters returns correct dict
  - [x] Test _apply_filters hides/shows correct rows with multi-field filtering
  - [x] Test filter row resets on new set_results call
  - [x] Follow `pytest.importorskip("PySide6")` pattern from `tests/test_export_dialog.py`

## Dev Notes

### Architecture Compliance

- **Core/GUI separation**: FilterRow is purely a GUI widget (`gui/results_table.py`). No core/ changes needed. PartResult fields are read via `getattr()` — no model changes required.
- **ADR-07**: FilterRow lives inside the Search Panel's QDockWidget, within ResultsTable. Not a separate dock panel.
- **UX-DR9**: Dynamic filter row — dropdowns created/removed based on search results. This is the exact spec.

### Existing Code to Reuse — DO NOT REINVENT

- **`gui/results_table.py`** (259 lines): Contains the current hardcoded filter row at lines 49-70. The `_apply_filters()` method at lines 174-199 already implements the show/hide pattern via `setRowHidden()`. The `set_results()` method at lines 109-149 already populates combos — this logic moves into FilterRow.
- **`core/models.py` `PartResult`**: Fields to filter on already exist: `manufacturer`, `package`, `category`, `source`, `lifecycle`. No model changes needed.
- **`_count_label`**: Already exists at line 67. Keep the same "X of Y results" format.
- **`get_result(row)`**: Already safely maps visual rows to PartResult via UserRole. Reuse as-is.

### Current Filter Row Code to Replace

The following block in `ResultsTable.__init__` (lines 49-70) is the **entire scope of replacement**:

```python
# ── Filter row ──
filter_row = QHBoxLayout()

filter_row.addWidget(QLabel("Manufacturer:"))
self._filter_mfr = QComboBox()
self._filter_mfr.addItem("All")
self._filter_mfr.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToContents)
self._filter_mfr.currentIndexChanged.connect(self._apply_filters)
filter_row.addWidget(self._filter_mfr)

filter_row.addWidget(QLabel("Package:"))
self._filter_pkg = QComboBox()
self._filter_pkg.addItem("All")
self._filter_pkg.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToContents)
self._filter_pkg.currentIndexChanged.connect(self._apply_filters)
filter_row.addWidget(self._filter_pkg)

filter_row.addStretch()
self._count_label = QLabel("")
filter_row.addWidget(self._count_label)

layout.addLayout(filter_row)
```

Replace with:
```python
self._filter_row = FilterRow()
self._filter_row.filters_changed.connect(self._apply_filters)
self._filter_row.setVisible(False)  # hidden until results arrive
layout.addWidget(self._filter_row)
```

### FilterRow Design

```python
# Suggested field ordering — most useful filters first
FILTERABLE_FIELDS: list[tuple[str, str]] = [
    ("Manufacturer", "manufacturer"),
    ("Package", "package"),
    ("Category", "category"),
]
```

Use a `list[tuple]` (not dict) to preserve display order. The list can be extended later (e.g. add `("Lifecycle", "lifecycle")`, `("Source", "source")`) without changing any logic.

**Dynamic creation approach**: In `update_filters()`, clear existing combo widgets, iterate `FILTERABLE_FIELDS`, extract unique non-empty values from results for each field, and only create a QComboBox if ≥2 unique values exist.

**Widget lifecycle**: Store combos in `self._combos: dict[str, QComboBox]` keyed by attr name. On `update_filters()`, remove old combos from layout, create new ones. Use `blockSignals(True)` during population to avoid spurious `filters_changed` emissions.

### _apply_filters Replacement

Current (hardcoded):
```python
mfr_filter = self._filter_mfr.currentText()
pkg_filter = self._filter_pkg.currentText()
# ... check part.manufacturer, part.package
```

New (dynamic):
```python
active = self._filter_row.get_active_filters()  # {"manufacturer": "Murata", "package": "0805"}
for row in range(self.table.rowCount()):
    part = self.get_result(row)
    if part is None:
        continue
    hide = any(
        getattr(part, attr, "") != value
        for attr, value in active.items()
    )
    self.table.setRowHidden(row, hide)
    if not hide:
        visible += 1
```

### FilterRow vs Separate File

Keep FilterRow **in `results_table.py`** — it's tightly coupled to the results table (same module, same lifecycle). No need for a separate file. This follows the existing pattern where widgets that are only used by one parent live in the parent's module.

### Sorting Compatibility

The current `setRowHidden()` approach works correctly with `QTableWidget.setSortingEnabled(True)`. When the user sorts, Qt rearranges visible rows; hidden rows stay hidden. The `_original_index()` / `UserRole` pattern ensures `get_result(row)` maps correctly after sorting. No changes needed for sorting compatibility.

### Edge Cases

- **All results have the same manufacturer**: No Manufacturer dropdown appears (< 2 unique values). This is intentional — a filter with only one option is useless.
- **Empty string values**: Exclude `""` from dropdown options. A part with `package=""` should not create an "(empty)" option — it just doesn't match any package filter.
- **Result count with 0 visible**: Show "0 of Y results" — this tells the user their filters are too restrictive.
- **Very long dropdown values**: `QComboBox.SizeAdjustPolicy.AdjustToContents` handles this (already used in current code). If values are very long, Qt truncates with ellipsis.

### What This Story Does NOT Include

- **No Unified mode cascade filtering** (sending filters back to APIs) — that's Story 3.2
- **No parametric spec filters** (voltage, capacitance ranges) — future scope, requires structured ParametricValue data in results
- **No text search / free-text filter** on columns — not in the acceptance criteria
- **No multi-select** within a single dropdown — each filter is single-value
- **No filter persistence** across searches — filters reset on each new search (AC #6)
- **No "Source" filter** in this story — Source column filtering comes with Story 3.2 (Two-Mode Search)
- **No changes to core/ modules** — this is a purely GUI story

### Project Structure Notes

- **Modified**: `src/kipart_search/gui/results_table.py` — replace hardcoded filter row with dynamic FilterRow class
- **New file**: `tests/test_filter_row.py` — tests for FilterRow and dynamic filtering
- Alignment: follows QComboBox + QHBoxLayout pattern from current results_table.py

### Previous Story Intelligence (Story 2.4)

Key learnings from the most recent story:
- GUI tests work without `pytest-qt` using `pytest.importorskip("PySide6")` pattern — follow this for filter row tests
- All 181 tests pass as of last commit (`1cbb122`). Test suite covers core + GUI tests.
- `blockSignals(True/False)` pattern used in `set_results()` to prevent spurious signal emissions during bulk updates — use the same pattern in FilterRow.update_filters()
- Code review fixes typically involve: extracting helpers, renaming for consistency, removing dead code — keep the initial implementation clean
- `_COLOR_HEX` dict pattern in verify_panel.py — define constants, don't hardcode

### Git Intelligence

Recent commits:
```
1cbb122 Code review fixes for Story 2.4: sync menu state, format combo, and move DNP to core
0172edc Add BOM export dialog with template selection and preview (Story 2.4)
d787582 Add Copy Log button and File menu to log panel
c163974 Code review fixes for Story 1.6: extract _build_context_menu for testability
e3bbffb Add persistent session log with section separators and auto-scroll (Story 1.6)
```

Files to modify:
- MODIFY: `src/kipart_search/gui/results_table.py` (replace lines 49-70, update _apply_filters, update set_results)
- NEW: `tests/test_filter_row.py`

### Anti-Patterns to Avoid

- Do NOT create FilterRow in a separate file — it belongs in results_table.py (single consumer)
- Do NOT use QSortFilterProxyModel — the current QTableWidget + setRowHidden approach works and is simpler. Switching to a model/view architecture is a separate refactor if ever needed.
- Do NOT modify core/models.py — PartResult already has all needed fields
- Do NOT add parametric spec filters (voltage, capacitance) — out of scope
- Do NOT persist filter selections across searches — AC #6 requires reset
- Do NOT hardcode field names in _apply_filters — use getattr() loop for extensibility
- Do NOT emit filters_changed during update_filters() — block signals during population
- Do NOT create dropdowns for fields with <2 unique values — wastes space and confuses users
- Do NOT include empty-string values in dropdown options

### Cross-Story Dependencies

- **Story 1.1** (done): QDockWidget migration — search panel is a dock, FilterRow lives inside it
- **Story 1.3** (done): Detail panel — shares splitter space with results table, not affected by filter row changes
- **Story 1.5** (done): Context menus — `_build_context_menu()` unaffected by filter changes
- **Story 3.2** (future): Two-Mode Search — will add "Source" to FILTERABLE_FIELDS and may add cascade filtering to APIs
- **Story 3.3** (future): Verification Dashboard Enhancements — separate panel, not affected

### References

- [Source: _bmad-output/planning-artifacts/epics.md — Epic 3, Story 3.1]
- [Source: _bmad-output/planning-artifacts/epics.md — FR3: Filter search results by manufacturer and package type]
- [Source: _bmad-output/planning-artifacts/ux-design-specification.md — UX-DR9: Dynamic Filter Row]
- [Source: _bmad-output/planning-artifacts/ux-design-specification.md — Filter Behavior Rules]
- [Source: _bmad-output/planning-artifacts/architecture.md — ADR-07: QDockWidget Panel Migration]
- [Source: _bmad-output/planning-artifacts/architecture.md — Anti-Patterns table]
- [Source: src/kipart_search/gui/results_table.py — current filter row (lines 49-70), _apply_filters (lines 174-199)]
- [Source: src/kipart_search/core/models.py — PartResult dataclass with filterable fields]
- [Source: _bmad-output/implementation-artifacts/2-4-bom-export-dialog-with-template-selection-and-preview.md — Previous story intelligence]

## Dev Agent Record

### Agent Model Used

Claude Opus 4.6 (1M context)

### Debug Log References

- One test initially failed due to `isVisible()` returning False when parent widget isn't shown — fixed by using `isHidden()` instead

### Completion Notes List

- Created `FilterRow` class (QWidget) in `results_table.py` with dynamic QComboBox creation/destruction based on search results
- Defined `FILTERABLE_FIELDS` as ordered list of tuples: Manufacturer, Package, Category
- `update_filters()` scans results, creates dropdowns only for fields with ≥2 unique non-empty values
- Each dropdown has "All" default + sorted unique values, with `blockSignals()` during population
- `get_active_filters()` returns `dict[str, str]` for non-"All" selections
- `update_count()` maintains "X of Y results" label (count label owned by FilterRow)
- Replaced hardcoded `_filter_mfr`/`_filter_pkg` in `ResultsTable.__init__` with single `FilterRow` instance
- Updated `set_results()`, `_apply_filters()`, and `clear_results()` to use FilterRow API
- `_apply_filters()` now uses `getattr()` loop over active filters — extensible without code changes
- 19 new tests covering all ACs: dropdown creation, visibility, empty-string exclusion, signal emission, active filters, multi-field filtering, reset on new results, clear behaviour
- All 201 tests pass (181 existing + 20 new), zero regressions

### File List

- MODIFIED: `src/kipart_search/gui/results_table.py` — replaced hardcoded filter row with dynamic FilterRow class
- NEW: `tests/test_filter_row.py` — 19 tests for FilterRow and ResultsTable dynamic filtering

## Change Log

- 2026-03-19: Story 3.1 implemented — dynamic FilterRow replaces hardcoded manufacturer/package filters with extensible multi-field filtering. 19 tests added, 200 total pass.
- 2026-03-19: Code review passed — 0 HIGH/MEDIUM issues. Added 1 test (zero-visible-results count label). 201 total pass.
