# Story 3.3: Verification Dashboard Enhancements

Status: ready-for-dev

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a designer,
I want the verification dashboard to show clear per-component status with text labels, support re-verification, and provide guided search from context,
So that I can quickly triage all components and fix issues efficiently.

## Acceptance Criteria

1. **Given** a board has been scanned
   **When** the verification table is displayed
   **Then** each component row is color-coded by status (green/amber/red) with a text label: "Verified", "Missing MPN", "Not Found", "Needs attention", "Unverified" (FR16, FR17)
   **And** per-component status shows: MPN present, MPN verified in database, footprint match (FR17)
   **And** components are sorted by status (red first, then amber, then green) by default

2. **Given** a component has a missing or unverified MPN (red/amber status)
   **When** the designer double-clicks that component row
   **Then** the search panel opens with a pre-filled query using the component's value and package (e.g. "100nF 0805 capacitor") (FR19)
   **And** the query is transformed using the existing query transform pipeline (FR5)
   **And** the designer can edit the transformed query before executing (FR6)

3. **Given** the designer has made changes (assigned MPNs, edited fields)
   **When** they click a "Re-verify" button in the verify panel
   **Then** verification re-runs against the current component state and the dashboard updates (FR20)

## Tasks / Subtasks

- [ ] Task 1: Add "Unverified" status label for components with MPN but no verification result yet (AC: #1)
  - [ ] Add `"Unverified"` text to `_STATUS_LABELS` mapping — this is for when a component has an MPN but hasn't been checked against any source yet (currently shows "Needs attention" for all AMBER, but AMBER covers both "found on 1 source" and "has MPN, unverified")
  - [ ] Track distinction: AMBER with verified partial result vs AMBER with no verification attempted. Consider a `_NO_RESULT_LABELS` mapping or an additional field on the status model

- [ ] Task 2: Add default sort by status (red first, then amber, then green) (AC: #1)
  - [ ] After `set_results()` populates the table and re-enables sorting, call `self.table.sortByColumn()` on the MPN Status column (col 3) in ascending order so that "Missing MPN" and "Not found" (red) sort before "Needs attention" (amber) before "Verified" (green)
  - [ ] `QTableWidgetItem` sort is lexicographic by default — status labels must sort correctly alphabetically OR set a `UserRole+1` sort key on status items (e.g. RED=0, AMBER=1, GREEN=2) so that red sorts first regardless of label text
  - [ ] Verify that the `UserRole` data (original component index) is preserved and not confused with the sort key — use `Qt.ItemDataRole.UserRole + 1` for sort order

- [ ] Task 3: Add "Re-verify" button to the verify panel (AC: #3)
  - [ ] Add a QPushButton "Re-verify" next to/below the health bar in the summary area
  - [ ] The button should only be visible/enabled after a scan has been performed (`self._components` is non-empty)
  - [ ] Add a `reverify_requested = Signal()` signal to VerifyPanel
  - [ ] Wire the button click to emit `reverify_requested`
  - [ ] In `main_window.py`, connect `verify_panel.reverify_requested` to a handler that:
    - Reads updated component data from the bridge (re-reads fields from KiCad in case fields were edited outside the app)
    - Re-runs `orchestrator.verify_mpn()` for each component
    - Calls `verify_panel.set_results()` with the updated data
  - [ ] Re-verification should run in a background thread (reuse `ScanWorker`) to avoid blocking the GUI
  - [ ] Disable the Re-verify button while re-verification is running, re-enable on completion
  - [ ] Log the re-verification activity: "Re-verifying X components..."

- [ ] Task 4: Ensure guided search works correctly with updated signal signature (AC: #2)
  - [ ] Verify `_on_guided_search` in main_window.py still works correctly after Story 3.2's `search_requested` signal change from `Signal(str)` to `Signal(str, str)` — the guided search calls `search_bar.search_button.click()` which triggers the signal with `(query, source)`
  - [ ] The current guided search flow already works (Story 3.2 preserved it), but confirm that the source selector respects the user's current selection when doing guided search (UX spec: "Source selector respects user's enabled sources and default")
  - [ ] No code changes expected — this is a verification/test task

- [ ] Task 5: Write tests (AC: #1-#3)
  - [ ] Test default sort order: after `set_results()`, verify red-status rows appear before amber before green
  - [ ] Test sort key data: verify `UserRole + 1` sort keys are set correctly (0=RED, 1=AMBER, 2=GREEN)
  - [ ] Test "Re-verify" button: visible after scan, hidden/disabled before scan
  - [ ] Test `reverify_requested` signal emission on button click
  - [ ] Test status labels: "Missing MPN" for red+no-MPN, "Not found" for red+has-MPN, "Needs attention" for amber, "Verified" for green
  - [ ] Follow `pytest.importorskip("PySide6")` pattern from `tests/test_filter_row.py`

## Dev Notes

### Architecture Compliance

- **Core/GUI separation**: All changes are in `gui/verify_panel.py` and `gui/main_window.py` — zero core/ changes. The `Confidence` enum and `BoardComponent` dataclass in `core/models.py` are unchanged.
- **ADR-07 (QDockWidget)**: Re-verify button lives inside the Verify dock panel. No new docks created.
- **Signal/Worker pattern**: Re-verification reuses the existing `ScanWorker` QThread pattern — background thread with `scan_complete`/`error` signals.
- **Error handling**: Re-verification errors (KiCad disconnected, etc.) follow existing pattern — `QMessageBox.warning()` + log panel entry.

### Existing Code to Reuse — DO NOT REINVENT

- **`gui/verify_panel.py`** (432 lines): Already has `_STATUS_LABELS`, `_STATUS_TOOLTIPS`, color coding, health bar, summary builder, context menu, guided search signal. Modify in place — do NOT create a new panel.
- **`gui/main_window.py`** (704 lines): Already has `ScanWorker`, `_on_scan()`, `_on_scan_complete()`, `_on_guided_search()`. The Re-verify button handler should reuse the same scan flow. Can directly call `_on_scan()` if the bridge is already connected, or create a lighter `_on_reverify()` that skips the connection check since scan already connected.
- **`_on_cell_double_clicked`** (line 331): Already emits `search_for_component` for ALL rows — guided search already works for any component (not just red/amber). This is correct behavior per the UX spec ("Double-click a component" opens guided search).
- **`ScanWorker`** (lines 78-126): Reuse directly for re-verification. It reads components from the bridge and runs `verify_mpn()` for each. Re-verification is functionally identical to an initial scan.

### Default Sort Implementation

The key challenge is sorting by status (red first). `QTableWidget` sorts lexicographically by item text, but our status labels don't sort in the desired order alphabetically ("Missing MPN" < "Needs attention" < "Not found" < "Verified" — wrong order).

**Solution**: Set a numeric sort key in `UserRole + 1` on the MPN Status column items:

```python
# In set_results(), when creating the status_item:
sort_order = {Confidence.RED: 0, Confidence.AMBER: 1, Confidence.GREEN: 2}
status_item.setData(Qt.ItemDataRole.UserRole + 1, sort_order[status])
```

Then override sort behavior with a custom sort key. However, `QTableWidget.sortByColumn()` uses `QTableWidgetItem.__lt__()` which compares `text()` by default. Two options:

**Option A (Recommended)**: Subclass `QTableWidgetItem` for the status column to override `__lt__()`:

```python
class _StatusItem(QTableWidgetItem):
    def __lt__(self, other):
        my_order = self.data(Qt.ItemDataRole.UserRole + 1)
        other_order = other.data(Qt.ItemDataRole.UserRole + 1)
        if my_order is not None and other_order is not None:
            return my_order < other_order
        return super().__lt__(other)
```

**Option B**: Prefix status text with invisible sort characters (fragile, not recommended).

Use Option A. Create `_StatusItem` as a private class in `verify_panel.py` and use it for column 3 items.

After setting results, trigger default sort:
```python
self.table.sortByColumn(3, Qt.SortOrder.AscendingOrder)  # MPN Status, red first
```

### Re-verify Button Placement

Add the button to the summary area, in a horizontal layout with the summary label:

```
[Components: 68 total | Valid MPN: 45 | ...]  [Re-verify]
[████████████████████████░░░░░░░░░░] Ready: 66%
```

Use a `QHBoxLayout` for the summary row: summary_label (stretch=1) + reverify button (fixed width). The button gets `setVisible(False)` initially, shown when `set_results()` is called with non-empty components.

### Status Label Refinement

Current `_STATUS_LABELS`:
```python
_STATUS_LABELS = {
    Confidence.GREEN: "Verified",
    Confidence.AMBER: "Needs attention",
    Confidence.RED: "Not found",
}
```

The AC requires these labels: "Verified", "Missing MPN", "Not Found", "Needs attention", "Unverified". The current code already handles "Missing MPN" as a special case in `set_results()` (line 187-189) — when `status == RED and not comp.has_mpn`, it shows "Missing MPN". This is correct.

The new label "Unverified" applies to components that have an MPN but were never checked against any source. Currently these get `Confidence.AMBER` with "Needs attention". The distinction is:
- **"Needs attention"** (AMBER): MPN exists, was checked, found on 1 source but not fully verified
- **"Unverified"** (AMBER or new state): MPN exists but was never checked (e.g., no sources configured, or source was offline)

**Simplest approach**: In `ScanWorker.run()`, when `verify_mpn()` returns `None` and the component has an MPN, we currently set `Confidence.RED`. We should instead set `Confidence.AMBER` for "has MPN but not found" (it's not the same severity as "no MPN at all"). Then in `verify_panel.set_results()`, distinguish the label:

- RED + no MPN → "Missing MPN"
- RED + has MPN → "Not found" (searched all sources, MPN not recognized)
- AMBER → "Needs attention" (found on 1 source, partially verified)
- GREEN → "Verified" (fully verified)

For "Unverified" — this would apply when no sources are configured. The current behavior when no sources exist is that `verify_mpn()` returns None for all MPNs (no sources to search). Consider adding this label as a tooltip or secondary text when the issue is "no sources available" rather than "MPN not found in sources".

**Recommended minimal change**: Keep the current status model as-is. The _STATUS_LABELS dict already covers the primary cases. Add "Unverified" as a special case in `set_results()` when a component has MPN but no sources are active (i.e., `orchestrator.active_sources` is empty). This is an edge case — most users will have JLCPCB configured.

### What This Story Does NOT Include

- **No datasheet URL verification** (HTTP HEAD check) — that's `core/verify.py` work, deferred
- **No symbol verification** (library reference validation) — deferred
- **No footprint-vs-package cross-check** (MPN says QFN-24, footprint is QFN-24) — deferred
- **No duplicate MPN detection** — deferred
- **No stale data indicators** — that's Story 3.4
- **No filter/sort persistence** across sessions — use Qt's built-in column sort state
- **No batch re-verify** (verify only selected components) — re-verify always does full re-scan

### Edge Cases

- **No sources configured**: Re-verify still reads components from KiCad (gets updated field values) but `verify_mpn()` returns None for all. Status shows "Not found" / "Missing MPN" as appropriate.
- **KiCad disconnected during re-verify**: `ScanWorker` catches the error and emits on the `error` signal. `_on_scan_error()` shows a `QMessageBox.warning()` and re-enables the Re-verify button.
- **Re-verify while previous scan is running**: Disable the Re-verify button (and Scan button) while `ScanWorker` is active. Both share the same `_scan_worker` state.
- **Table already sorted by user (clicked column header)**: After re-verify, `set_results()` resets the table and applies default sort (red first). User's custom sort is lost. This is expected — the data changed.
- **Zero components**: Re-verify button stays hidden. Health bar stays hidden. Summary shows "No components found".

### Project Structure Notes

- **Modified**: `src/kipart_search/gui/verify_panel.py` — add `_StatusItem`, default sort, Re-verify button + signal
- **Modified**: `src/kipart_search/gui/main_window.py` — connect `reverify_requested` signal, handler reuses `_on_scan`
- **New**: Tests in `tests/test_verify_dashboard_enhancements.py`
- No core/ changes — all models and enums are unchanged

### Previous Story Intelligence (Story 3.2)

Key learnings from Story 3.2:
- Signal signature change: `search_requested` is now `Signal(str, str)` — `(query, source_name)`. Guided search calls `search_bar.search_button.click()` which goes through this path correctly.
- `blockSignals(True/False)` pattern during widget population — use when populating combo boxes or updating table items programmatically
- 222 tests currently pass — run full suite after implementation to verify zero regressions
- Code review extracted `_search_sources()` helper in `search.py` — good pattern for eliminating duplication
- `pytest.importorskip("PySide6")` pattern works for GUI tests
- `UserRole` is used for original row index in both verify_panel.py and results_table.py — use `UserRole + 1` for sort keys to avoid collision

### Git Intelligence

Recent commits:
```
96f4980 Add two-mode search architecture with source selector (Story 3.2)
cb34742 Add dynamic filter row replacing hardcoded manufacturer/package filters (Story 3.1)
35bf071 Update sprint status: epic-2 done, create story 3-1 dynamic filter row
24f7f3f Code review fixes for Story 2.4: prevent double preview rebuild and remove redundant fields
1cbb122 Code review fixes for Story 2.4: sync menu state, format combo, and move DNP to core
```

Patterns observed:
- Commit messages follow: "Add [feature description] (Story X.Y)" format
- Code review fixes are separate commits
- Tests are in the same commit as the feature
- Each story modifies 3-5 files typically

### Anti-Patterns to Avoid

- Do NOT modify `core/models.py` — the `Confidence` enum is sufficient as-is, no new enum values needed
- Do NOT create a new QThread subclass for re-verification — reuse `ScanWorker`
- Do NOT replace the QTableWidget with QTableView/model — the current approach works and is simpler
- Do NOT add filter/sort persistence — let Qt handle column sort state within the session
- Do NOT implement batch operations (multi-select, batch verify) — single-row selection per UX spec
- Do NOT hardcode sort column index — use `VERIFY_COLUMNS.index("MPN Status")` to find column 3
- Do NOT clear the detail browser on re-verify unless the selected component's data changed

### Cross-Story Dependencies

- **Story 3.2** (done): Changed `search_requested` signal signature — guided search still works via `search_button.click()`
- **Story 3.1** (done): Dynamic FilterRow — not affected by verify panel changes
- **Story 3.4** (next): Stale Data Indicators — will add timestamp tracking to verification results, building on the re-verify infrastructure created here
- **Story 2.3** (done): Health Summary Bar — already implemented, this story enhances it with Re-verify button placement

### References

- [Source: _bmad-output/planning-artifacts/epics.md — Epic 3, Story 3.3 (lines 408-431)]
- [Source: _bmad-output/planning-artifacts/prd.md — FR16-FR20 (Verification Dashboard)]
- [Source: _bmad-output/planning-artifacts/ux-design-specification.md — "Triage & Fix" table (lines 396-406)]
- [Source: _bmad-output/planning-artifacts/ux-design-specification.md — "Health Summary Bar" widget spec (lines 777-788)]
- [Source: _bmad-output/planning-artifacts/ux-design-specification.md — "Table Interaction Patterns" (lines 928-940)]
- [Source: _bmad-output/planning-artifacts/ux-design-specification.md — "Color is never the only indicator" accessibility (line 965)]
- [Source: _bmad-output/planning-artifacts/architecture.md — ADR-07: QDockWidget Panel Migration]
- [Source: _bmad-output/planning-artifacts/architecture.md — Signal & Worker Patterns (lines 333-347)]
- [Source: src/kipart_search/gui/verify_panel.py — current VerifyPanel (432 lines)]
- [Source: src/kipart_search/gui/main_window.py — ScanWorker, _on_scan, _on_guided_search]
- [Source: _bmad-output/implementation-artifacts/3-2-two-mode-search-architecture-specific-vs-unified.md — Previous story intelligence]

## Dev Agent Record

### Agent Model Used

{{agent_model_name_version}}

### Debug Log References

### Completion Notes List

### File List
