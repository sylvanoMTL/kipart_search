# Story 2.3: Health Summary Bar with Live Updates

Status: review

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a designer,
I want a health summary bar above the verification table that shows BOM readiness at a glance and updates live after each assignment,
So that I can see my progress without re-scanning and know when the BOM is ready for export.

## Acceptance Criteria

1. **Given** a board has been scanned with components in the verification table
   **When** the health summary bar is displayed
   **Then** it shows a QProgressBar color-coded by percentage (red <50%, amber 50-99%, green 100%) (UX-DR10)
   **And** summary text reads: "Components: N total | Valid MPN: X | Needs attention: Y | Missing MPN: Z"

2. **Given** a designer assigns an MPN to a component via the assign dialog
   **When** the assignment is confirmed and fields are written to KiCad
   **Then** the health bar percentage, color, and summary counts update immediately without a full re-scan (UX-DR18)
   **And** the component row color updates from red/amber to green immediately

3. **Given** the health bar shows percentage below 50%
   **When** the bar is displayed
   **Then** the bar chunk color is red (#FFC8C8)

4. **Given** the health bar shows percentage between 50% and 99%
   **When** the bar is displayed
   **Then** the bar chunk color is amber (#FFEBB4)

5. **Given** the health bar shows 100%
   **When** the bar is displayed
   **Then** the bar chunk color is green (#C8FFC8)
   **And** the summary text includes "Ready for export" indication

6. **Given** no scan has been performed
   **When** the verify panel is displayed
   **Then** the health bar is hidden and the summary shows "Scan a project or open a BOM to begin" (UX-DR12)

7. **Given** the Health Summary Bar is a custom composite widget
   **When** it is created
   **Then** it sets `setAccessibleName()` and `setAccessibleDescription()` for screen reader support (UX-DR15)

## Tasks / Subtasks

- [x] Task 1: Add color-coding to the existing health bar in `verify_panel.py` (AC: #1, #3, #4, #5)
  - [x] Create a `_update_health_bar_style(pct: int)` method that applies a stylesheet to the QProgressBar based on percentage thresholds: red <50%, amber 50-99%, green 100%
  - [x] Use QProgressBar stylesheet with `::chunk` pseudo-element to set the bar fill color
  - [x] Call `_update_health_bar_style()` from `set_results()` after computing the percentage
  - [x] When pct == 100, append " — Ready for export" to the summary text

- [x] Task 2: Add accessibility properties to the health bar (AC: #7)
  - [x] Call `self.health_bar.setAccessibleName("BOM health progress")` in `__init__`
  - [x] Call `self.health_bar.setAccessibleDescription("Shows percentage of components with verified MPNs")` in `__init__`
  - [x] Call `self.summary_label.setAccessibleName("BOM health summary")` in `__init__`

- [x] Task 3: Add `update_component_status()` method to `VerifyPanel` (AC: #2)
  - [x] Add method signature: `update_component_status(self, reference: str, new_status: Confidence) -> None`
  - [x] Find the component row by reference (iterate `_components`, match `reference`)
  - [x] Update `_mpn_statuses[reference]` to `new_status`
  - [x] Update the row's background color for all cells to the new status color
  - [x] Update the MPN Status cell text and tooltip
  - [x] Recompute `has_mpn`, `missing_mpn`, `issues` counts from `_mpn_statuses`
  - [x] Update summary label text and health bar value/color via `_update_health_bar_style()`

- [x] Task 4: Wire live updates from assignment flow in `main_window.py` (AC: #2)
  - [x] After successful field write-back in `_on_part_selected()`, call `self.verify_panel.update_component_status(ref, Confidence.GREEN)`
  - [x] Also update the `_assign_target` component's `mpn` field in-memory so `has_mpn` returns True on the component object
  - [x] Log the status update: `self.log_panel.log(f"{ref} status updated to Verified")`

- [x] Task 5: Refresh component data after assignment (AC: #2)
  - [x] After writing fields in `_on_part_selected()`, update the `BoardComponent` in-memory: set `comp.mpn` to the assigned MPN value, update `comp.extra_fields` with written fields (manufacturer, description, etc.)
  - [x] This ensures `comp.has_mpn` returns True and the verify panel reflects the current state

- [x] Task 6: Write tests (AC: #1-#7)
  - [x] Test `_update_health_bar_style` with 0%, 49%, 50%, 99%, 100% values
  - [x] Test `update_component_status` changes row colors and summary counts
  - [x] Test that accessibility names are set on health bar and summary label
  - [x] Test the empty state (no scan) shows guidance text and hidden bar
  - [x] Note: GUI tests require `pytest-qt` — if not available, document manual test steps instead

## Dev Notes

### Architecture Compliance

- **Core/GUI separation**: All changes are in `gui/verify_panel.py` and `gui/main_window.py` — zero changes to `core/`. No new core modules needed.
- **Signal/Slot pattern**: The live update is driven by method call from `main_window.py` to `verify_panel.py` after assignment, not via a new Signal. This is simpler since `main_window` already holds a reference to `verify_panel`.
- **No new dependencies**: Uses only existing PySide6 widgets (QProgressBar stylesheet, QLabel).

### Current State of `verify_panel.py`

The verify panel **already has** a `summary_label` (QLabel) and `health_bar` (QProgressBar) — both created in `__init__`. The `set_results()` method already computes `has_mpn`, `missing_mpn`, `issues` counts and sets the health bar value and format text. What's **missing**:

1. **Color-coding the progress bar** by percentage (currently no color — just default Qt style)
2. **`update_component_status()` method** for live updates after assignment
3. **Accessibility** names on the health bar and summary label

### QProgressBar Color-Coding Implementation

Use stylesheet on the QProgressBar `::chunk` pseudo-element:

```python
def _update_health_bar_style(self, pct: int) -> None:
    if pct >= 100:
        color = "#C8FFC8"  # green
    elif pct >= 50:
        color = "#FFEBB4"  # amber
    else:
        color = "#FFC8C8"  # red
    self.health_bar.setStyleSheet(
        f"QProgressBar::chunk {{ background-color: {color}; }}"
    )
```

These colors match the existing `COLORS` dict values in `verify_panel.py` (GREEN=#C8FFC8, AMBER=#FFEBB4, RED=#FFC8C8).

### Live Update Wiring in `main_window.py`

The assignment flow is in `_on_part_selected()` (line ~573). After fields are written to KiCad:

```python
# After the write-back loop:
if written > 0:
    self.log_panel.log(f"Wrote {written} field(s) to {ref}")
    # Update component in-memory
    comp = self._assign_target
    if comp and "MPN" in fields:
        comp.mpn = fields["MPN"]
    for fname, fval in fields.items():
        comp.extra_fields[fname.lower()] = fval
    # Live update the verify panel
    self.verify_panel.update_component_status(ref, Confidence.GREEN)
```

**Critical**: The `self._assign_target` is set to `None` AFTER this code runs — the current code already does this correctly (line 612).

### `update_component_status()` Implementation Notes

When updating a single component's status:
1. Iterate `self._components` to find the one matching `reference`
2. Update `self._mpn_statuses[reference]`
3. Find the visual row in the table by iterating rows and checking the UserRole data (original index)
4. Update all cell backgrounds in that row
5. Update the MPN Status cell (column 3) text and tooltip
6. Recompute counts by iterating `_mpn_statuses` (not `_components`) — this is O(n) but n is typically <200 components, so negligible
7. Call `_update_health_bar_style(new_pct)` to update the bar color

**Sort-safety**: The table may be sorted — rows may not match `_components` order. Use `_original_index()` / UserRole data to find the correct visual row. Iterate all visual rows and check `item.data(Qt.ItemDataRole.UserRole)` against the component's index in `_components`.

### What This Story Does NOT Include

- **No re-scan after assignment** — live update avoids this entirely (that's the point of UX-DR18)
- **No changes to `core/` modules** — this is purely GUI behavior
- **No new Signals** — method call is sufficient since `main_window` already owns `verify_panel`
- **No BOM export dialog** — Story 2.4
- **No stale data indicators** — Story 3.4
- **No "Ready for export" enabling of the Export BOM button** — Story 2.4 (but the summary text hint is added here)

### Previous Story Intelligence (Story 2.2)

Key learnings from Story 2.2:
- `BoardComponent.extra_fields` is `dict[str, str]` — field name case varies. Use `.get()` with known key names.
- All 133 tests pass as of last commit (`6958c69`). No GUI tests exist yet — test suite is core-only.
- Commit pattern: one implementation commit, one code review fix commit per story.
- Code review fixes for 2.1 included renaming, dead code removal, moving constants to module level — expect similar review feedback.

### Git Intelligence

Recent commits:
```
6958c69 Code review fixes for Story 2.2: add fallback alias tests
2f17fbe Add JLCPCB and Newbury Electronics preset BOM templates (Story 2.2)
bc99fc5 Code review fixes for Story 2.1: naming consistency and dead code removal
ae5ad62 Add BOM export engine with PCBWay template (Story 2.1)
```

Files recently modified:
- `src/kipart_search/core/bom_export.py` (Stories 2.1, 2.2)
- `tests/core/test_bom_export.py` (Stories 2.1, 2.2)

Files to modify in this story:
- `src/kipart_search/gui/verify_panel.py` (health bar color, `update_component_status()`, accessibility)
- `src/kipart_search/gui/main_window.py` (wire live update after assignment)

### Testing Notes

- **GUI tests**: Require `pytest-qt` and `QApplication` — not currently in the test setup. If pytest-qt is available, test `VerifyPanel` methods directly. If not, document manual test steps.
- **Core-only tests**: No core changes in this story, so no new core tests needed.
- **Manual test flow**: Scan project → note health bar color/counts → assign MPN to a red component → verify bar updates immediately without re-scan → verify row turns green.
- **Edge cases to test manually**: Assign to last missing component → bar should hit 100% and turn green. Start with 0 verified components → bar is red. Assign when bar is at 49% → crosses 50% threshold → bar turns amber.

### Anti-Patterns to Avoid

- Do NOT add a new Signal for the live update — a direct method call from `main_window` to `verify_panel` is simpler and sufficient
- Do NOT re-run the full scan/verification after assignment — the whole point is incremental update
- Do NOT modify `core/` modules — this story is GUI-only
- Do NOT change the existing `set_results()` method signature — it still handles the initial scan population
- Do NOT use `QTimer` or deferred updates for the health bar color — update synchronously within `update_component_status()`
- Do NOT hardcode color strings in multiple places — reuse the existing `COLORS` dict values from `verify_panel.py`

### Cross-Story Dependencies

- **Story 2.1** (done): BOM export engine — independent
- **Story 2.2** (done): Preset CM templates — independent
- **Story 2.4** (next): BOM Export Dialog — will use the health bar percentage to show a warning when coverage <100%
- **Story 3.4** (future): Stale Data Indicators — will add amber stale state to the health bar counts

### Project Structure Notes

- Modified: `src/kipart_search/gui/verify_panel.py` (health bar color-coding, `update_component_status()`, accessibility)
- Modified: `src/kipart_search/gui/main_window.py` (wire live update in `_on_part_selected()`)
- No new files created
- Alignment: follows existing QDockWidget panel architecture from Epic 1

### References

- [Source: _bmad-output/planning-artifacts/epics.md — Epic 2, Story 2.3]
- [Source: _bmad-output/planning-artifacts/epics.md — UX-DR10: Health Summary Bar definition]
- [Source: _bmad-output/planning-artifacts/epics.md — UX-DR18: Live dashboard updates after assignment]
- [Source: _bmad-output/planning-artifacts/epics.md — UX-DR15: Accessibility for custom widgets]
- [Source: _bmad-output/planning-artifacts/ux-design-specification.md — Component Strategy: Health Summary Bar]
- [Source: _bmad-output/planning-artifacts/architecture.md — ADR-07: QDockWidget Panel Migration]
- [Source: _bmad-output/planning-artifacts/prd.md — FR18: Health bar showing BOM readiness percentage]
- [Source: _bmad-output/project-context.md — Core/GUI separation, PySide6 rules]
- [Source: src/kipart_search/gui/verify_panel.py — existing health_bar and summary_label widgets]
- [Source: src/kipart_search/gui/main_window.py — _on_part_selected() assignment flow, lines 573-616]
- [Source: _bmad-output/implementation-artifacts/2-2-preset-cm-templates-jlcpcb-newbury-electronics.md — Previous story intelligence]

## Change Log

- 2026-03-18: Implemented health summary bar color-coding, accessibility, live updates, and tests (Story 2.3)

## Dev Agent Record

### Agent Model Used

Claude Opus 4.6 (1M context)

### Debug Log References

- No blocking issues encountered during implementation.

### Completion Notes List

- Task 1: Added `_update_health_bar_style(pct)` method using QProgressBar `::chunk` stylesheet. Added `_COLOR_HEX` dict to avoid hardcoding color strings. Called from `set_results()` after percentage computation. "Ready for export" appended to summary at 100%.
- Task 2: Added `setAccessibleName` and `setAccessibleDescription` to `health_bar` and `summary_label` in `__init__`.
- Task 3: Added `update_component_status(reference, new_status)` method — sort-safe row lookup via UserRole data, updates background colors for all cells, updates MPN Status text/tooltip, recomputes counts, updates health bar value and color.
- Task 4: Wired live update in `main_window._on_part_selected()` — after successful field write-back, calls `verify_panel.update_component_status(ref, Confidence.GREEN)` and logs the status change.
- Task 5: In same code block, updates `BoardComponent` in-memory (`comp.mpn`, `comp.extra_fields`) so `has_mpn` returns True for subsequent operations.
- Task 6: 18 GUI tests in `tests/test_health_bar.py` covering all ACs — color-coding thresholds, accessibility names, update_component_status behavior, empty state. All tests pass using `pytest.importorskip("PySide6")` pattern (no pytest-qt needed).

### File List

- Modified: `src/kipart_search/gui/verify_panel.py`
- Modified: `src/kipart_search/gui/main_window.py`
- Added: `tests/test_health_bar.py`
