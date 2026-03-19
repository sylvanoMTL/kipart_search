# Story 5.2: Click-to-Highlight Cross-Probe

Status: done

## Story

As a designer,
I want to click a component in the app and have it highlighted in KiCad's PCB editor,
so that I can visually locate components on the board while working through verification.

## Acceptance Criteria

1. **Given** the app is connected to KiCad and the verification table shows scanned components
   **When** the designer single-clicks a component row in the verification table
   **Then** the corresponding footprint is selected/highlighted in KiCad's PCB editor (FR12)
   **And** KiCad's internal cross-probe automatically highlights the component in the schematic editor

2. **Given** the app is in standalone mode (no KiCad connection)
   **When** the designer clicks a component row
   **Then** the detail panel updates normally but no KiCad highlight occurs
   **And** no error is shown — the feature is silently unavailable

## Tasks / Subtasks

- [x] Task 1: Audit existing click-to-highlight signal chain (AC: #1)
  - [x] 1.1 Verify `VerifyPanel.component_clicked` signal emits the correct reference on single-click
  - [x] 1.2 Verify signal connection: `verify_panel.component_clicked` → `MainWindow._on_component_clicked`
  - [x] 1.3 Verify `_on_component_clicked` calls `self._bridge.select_component(reference)`
  - [x] 1.4 Verify `select_component()` calls `_board.clear_selection()` then `_board.add_to_selection(fp)`
  - [x] 1.5 Verify `_footprint_cache` is populated by prior `get_components()` call during scan
  - [x] 1.6 Test the full chain end-to-end with a mocked kipy board (clear_selection + add_to_selection called)

- [x] Task 2: Audit standalone mode behavior (AC: #2)
  - [x] 2.1 Verify `select_component()` returns `False` silently when `is_connected` is `False`
  - [x] 2.2 Verify `_on_component_clicked` does NOT show error dialogs when `select_component` returns `False`
  - [x] 2.3 Verify the detail panel still updates on click regardless of connection state
  - [x] 2.4 Verify no error toast, no log panel error entry, no exception on standalone click

- [x] Task 3: Edge case audit (AC: #1, #2)
  - [x] 3.1 Verify behavior when component reference is not in `_footprint_cache` (deleted from board after scan)
  - [x] 3.2 Verify behavior when KiCad connection drops mid-session (was connected, now disconnected)
  - [x] 3.3 Verify behavior when user clicks rapidly between rows (no race condition in clear/add selection)
  - [x] 3.4 Verify `_footprint_cache` is cleared and re-populated on re-scan

- [x] Task 4: Write tests for click-to-highlight flow (AC: #1, #2)
  - [x] 4.1 Test `select_component()` with mocked board — verify `clear_selection` + `add_to_selection` called
  - [x] 4.2 Test `select_component()` with unknown reference — returns `False`, no exception
  - [x] 4.3 Test `select_component()` when not connected — returns `False` immediately
  - [x] 4.4 Test `select_component()` when `add_to_selection` raises — returns `False`, logs warning
  - [x] 4.5 Test `_on_component_clicked` calls `select_component` with correct reference
  - [x] 4.6 Test detail panel updates on click regardless of bridge connection state

- [x] Task 5: Fix any gaps found in audit (AC: #1, #2)
  - [x] 5.1 Implement fixes for any issues discovered in Tasks 1-3
  - [x] 5.2 Ensure no error UI is shown to user when highlight silently fails

## Dev Notes

### CRITICAL: This functionality already exists — this is an audit story

The click-to-highlight cross-probe chain is **already fully implemented**. Like Story 5.1, this story is primarily an **audit, test, and gap-fill** exercise. Do NOT rewrite existing code.

**Existing implementation:**

| Component | File | Location | Status |
|-----------|------|----------|--------|
| `component_clicked` signal | `gui/verify_panel.py:87` | Signal definition | Exists: `component_clicked = Signal(str)` |
| Cell click handler | `gui/verify_panel.py:437` | `_on_cell_clicked(row, col)` | Exists: emits `component_clicked` with reference |
| Signal connection | `gui/main_window.py:163` | In constructor | Exists: `verify_panel.component_clicked.connect(self._on_component_clicked)` |
| Click handler | `gui/main_window.py:696-710` | `_on_component_clicked(reference)` | Exists: calls `_bridge.select_component(reference)` + updates assign target |
| `select_component()` | `gui/kicad_bridge.py:166-185` | KiCadBridge method | Exists: clears selection, adds footprint, returns bool |
| `_footprint_cache` | `gui/kicad_bridge.py:149` | Populated in `get_components()` | Exists: dict keyed by reference |

### Cross-probe chain (how it works)

```
User clicks row in VerifyPanel
  → VerifyPanel._on_cell_clicked(row, col)
    → VerifyPanel.component_clicked.emit(reference)  [Signal]
      → MainWindow._on_component_clicked(reference)  [Slot]
        → KiCadBridge.select_component(reference)
          → _board.clear_selection()
          → _board.add_to_selection(fp)     # fp from _footprint_cache[reference]
            → KiCad PCB editor highlights footprint
              → KiCad internal cross-probe highlights in schematic
```

No explicit schematic API call is needed. KiCad handles PCB → schematic cross-probe internally.

### `select_component()` implementation detail

```python
def select_component(self, reference: str) -> bool:
    if not self.is_connected:
        return False
    fp = self._footprint_cache.get(reference)
    if fp is None:
        log.warning("Component %s not found in cache", reference)
        return False
    try:
        self._board.clear_selection()
        self._board.add_to_selection(fp)
        return True
    except Exception as e:
        log.warning("Failed to select %s: %s", reference, e)
        return False
```

Key: Returns `False` silently on any failure. No exceptions escape. Caller (`_on_component_clicked`) does NOT check the return value for error display — this is correct behavior for AC #2.

### Standalone mode behavior

When not connected (`is_connected == False`):
- `select_component()` returns `False` immediately (line 168)
- `_on_component_clicked` calls it but does not check the return value for error display
- The method continues to update assign target UI state regardless
- No error dialog, no log error, no user-visible indication — the highlight simply doesn't happen

### Footprint cache lifecycle

1. **Populated**: During `get_components()` (called by `ScanWorker`)
2. **Cleared**: At start of each `get_components()` call
3. **Used by**: `select_component()` for footprint lookup by reference
4. **Implication**: `get_components()` must be called before any `select_component()` call — this happens automatically during board scan

### Results table does NOT trigger KiCad highlight

The results table (search results) has separate signals:
- `part_clicked` (single click) → updates detail panel only
- `part_selected` (double click) → triggers assignment workflow

Neither calls `select_component()`. KiCad highlight is only triggered from the verification panel. This is correct behavior — search results are not board components.

### Architecture constraints

- **Core/GUI separation**: `kicad_bridge.py` is in `gui/` (correct — depends on optional `kipy`). `BoardComponent` is in `core/models.py` (zero GUI deps).
- **Error handling pattern**: Bridge methods return empty/False on failure, never crash the app.
- **Anti-pattern**: Never modify `.kicad_sch` or `.kicad_pcb` files directly — IPC API only.
- **Thread safety**: `select_component()` is called from the GUI thread (signal/slot connection). The footprint cache is populated from a QThread worker (`ScanWorker`), but the cache is only read after the worker completes and emits `scan_complete`. No concurrent access concern.

### kipy API calls used for selection

```python
self._board.clear_selection()           # Clear any existing PCB selection
self._board.add_to_selection(fp)        # Select the target footprint
```

These are the only two kipy calls needed. The cross-probe from PCB → schematic is handled entirely by KiCad internally.

### Previous story intelligence (Story 5.1)

From Story 5.1 completion notes:
- All KiCad bridge methods audited and verified working
- 37 tests created in `tests/gui/test_kicad_bridge.py`
- `select_component` tests already exist in Story 5.1 test suite (2 tests covering basic selection)
- Story 5.2 should ADD edge case tests, not duplicate existing ones
- Test approach: mock `kipy` module entirely, create mock footprints with realistic field structure
- `pytest-qt` is installed and used for QThread/signal testing
- Test baseline: 284+ tests passing

**Important**: Check `tests/gui/test_kicad_bridge.py` before writing tests — some `select_component` tests may already exist from Story 5.1. Extend coverage, don't duplicate.

### Testing approach

Mock the kipy module as established in Story 5.1:

```python
mock_board = MagicMock()
bridge = KiCadBridge()
bridge._board = mock_board
bridge._footprint_cache = {"C1": mock_fp, "R1": mock_fp2}

# Test selection
result = bridge.select_component("C1")
assert result is True
mock_board.clear_selection.assert_called_once()
mock_board.add_to_selection.assert_called_once_with(mock_fp)
```

Test file: extend `tests/gui/test_kicad_bridge.py` (do NOT create a separate file)

For testing the signal chain (`_on_component_clicked`), use `pytest-qt` with `qtbot`:

```python
# Test that clicking a verify panel row triggers select_component
with patch.object(window._bridge, 'select_component') as mock_select:
    window._on_component_clicked("C1")
    mock_select.assert_called_once_with("C1")
```

### Project Structure Notes

- No new files expected — this is an audit + test extension story
- Tests extend existing `tests/gui/test_kicad_bridge.py`
- If MainWindow signal chain tests are needed, they may go in `tests/gui/test_main_window.py` (check if exists)
- All code stays in existing files — no new modules needed

### References

- [Source: _bmad-output/planning-artifacts/epics.md - Epic 5, Story 5.2]
- [Source: _bmad-output/planning-artifacts/architecture.md - ADR-08, KiCad Integration, Cross-Cutting Concerns]
- [Source: _bmad-output/planning-artifacts/ux-design-specification.md - Table Interaction Patterns, Connected vs Standalone Mode]
- [Source: CLAUDE.md - KiCad IPC API integration, cross-probe chain]
- [Source: _bmad-output/implementation-artifacts/5-1-kicad-connection-and-board-scan.md - Previous story learnings, test approach]

## Dev Agent Record

### Agent Model Used

Claude Opus 4.6 (1M context)

### Debug Log References

None — no bugs or issues encountered during audit.

### Completion Notes List

- **Audit complete**: Full click-to-highlight signal chain audited across 3 files (verify_panel.py, main_window.py, kicad_bridge.py). All links verified correct.
- **No gaps found**: The existing implementation fully satisfies both ACs. No code changes needed.
- **Standalone mode verified**: `select_component()` returns `False` silently when disconnected; `_on_component_clicked` does not check return value for error display — correct behavior per AC #2.
- **Edge cases verified**: Reference not in cache (returns False + warning log), IPC errors caught by try/except, no race condition (same-thread signal/slot), cache cleared on re-scan.
- **13 new tests added** to `tests/gui/test_kicad_bridge.py`:
  - `TestSelectComponentEdgeCases` (8 tests): call order verification, clear_selection/add_to_selection exception handling, not-connected path, unknown reference, sequential selection, cache re-population on rescan, rescan cache correctness
  - `TestOnComponentClickedSignalChain` (5 tests): MainWindow._on_component_clicked calls bridge, silent failure, assign target update, VerifyPanel signal emission, detail panel update on click
- **Test suite**: 347 passed, 1 pre-existing failure (unrelated `test_central_widget_is_shrinkable_placeholder`)
- **Task 5 (gaps)**: No gaps found in Tasks 1-3. No code fixes needed. 5.1 marked as "no issues discovered". 5.2 confirmed: no error UI shown to user on highlight failure.

### Change Log

- 2026-03-19: Audited click-to-highlight cross-probe chain, added 13 edge case and signal chain tests

### File List

- `tests/gui/test_kicad_bridge.py` (modified) — added TestSelectComponentEdgeCases and TestOnComponentClickedSignalChain test classes
- `_bmad-output/implementation-artifacts/5-1-kicad-connection-and-board-scan.md` (modified) — updated status after 5.2 review
- `_bmad-output/implementation-artifacts/sprint-status.yaml` (modified) — synced story 5.2 status
