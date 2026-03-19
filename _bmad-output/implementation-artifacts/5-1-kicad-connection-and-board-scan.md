# Story 5.1: KiCad Connection and Board Scan

Status: done

## Story

As a designer,
I want the application to auto-detect a running KiCad instance and scan all board components into the verification dashboard,
So that I can start the BOM workflow without manual configuration.

## Acceptance Criteria

1. **Given** KiCad 9+ is running with IPC API enabled
   **When** the application launches or the user clicks "Scan Project"
   **Then** the app auto-detects the KiCad IPC API socket (via `KICAD_API_SOCKET` env var or default path) without manual configuration
   **And** all components are read from the active PCB project: reference, value, footprint, and existing field data (MPN, manufacturer, description, supplier P/Ns)
   **And** the verification dashboard populates with all components and their status
   **And** the scan completes in < 10 seconds for a 70-component board
   **And** all IPC API calls are isolated in `gui/kicad_bridge.py` behind a single abstraction layer

2. **Given** KiCad is not running or the IPC API is unavailable
   **When** the application launches
   **Then** the status bar shows "Standalone" (gray pill) and KiCad-specific actions (highlight, Push to KiCad) are grayed out
   **And** all other functionality (search, verify against local data, export) works normally

## Tasks / Subtasks

- [x] Task 1: Audit existing `gui/kicad_bridge.py` against acceptance criteria (AC: #1, #2)
  - [x] 1.1 Verify `KiCadBridge.connect()` auto-detects socket via env var and default path
  - [x] 1.2 Verify `get_components()` reads all required fields: reference, value, footprint, MPN, manufacturer, description, supplier P/Ns
  - [x] 1.3 Identify any missing field extraction (manufacturer, description, supplier P/Ns may not be fully extracted)
  - [x] 1.4 Add extraction for any missing fields from `fp.texts_and_fields`

- [x] Task 2: Audit `ScanWorker` and `_on_scan()` flow in `main_window.py` (AC: #1)
  - [x] 2.1 Verify scan worker reads components and populates verify panel
  - [x] 2.2 Verify MPN verification runs against configured sources
  - [x] 2.3 Verify the scan complete signal chain: `ScanWorker.scan_complete` → `_on_scan_complete` → `verify_panel.set_results`

- [x] Task 3: Verify standalone mode behavior (AC: #2)
  - [x] 3.1 Verify status bar shows "Standalone" gray pill when KiCad is not available
  - [x] 3.2 Verify "Push to KiCad" is grayed out (`_act_push.setEnabled(False)`)
  - [x] 3.3 Verify search, JLCPCB local DB, and export work without KiCad connection
  - [x] 3.4 Verify `_show_connection_error()` provides helpful diagnostics

- [x] Task 4: Write tests for KiCad bridge and scan flow (AC: #1, #2)
  - [x] 4.1 Test `KiCadBridge` with mocked `kipy` — connect success/failure
  - [x] 4.2 Test `get_components()` returns properly-populated `BoardComponent` list
  - [x] 4.3 Test graceful degradation when `kipy` is not installed (`ImportError`)
  - [x] 4.4 Test graceful degradation when KiCad is not running (connection refused)
  - [x] 4.5 Test `ScanWorker` completes and emits correct signals

- [x] Task 5: Fix any gaps found in audit (AC: #1)
  - [x] 5.1 Implement missing field extraction if needed
  - [x] 5.2 Ensure all IPC API calls are in `kicad_bridge.py` (no leakage to other modules)

## Dev Notes

### CRITICAL: Most of this functionality already exists

The KiCad bridge and scan flow are **already implemented**. This story is primarily an **audit, test, and gap-fill** exercise, not a greenfield implementation. Do NOT rewrite existing code.

**Existing implementation:**

| Component | File | Status |
|-----------|------|--------|
| `KiCadBridge` class | `gui/kicad_bridge.py` | Full implementation exists: `connect()`, `get_components()`, `select_component()`, `write_field()`, `get_diagnostics()` |
| `ScanWorker` QThread | `gui/main_window.py:79-133` | Full implementation: reads components, verifies MPNs, emits results |
| `_on_scan()` handler | `gui/main_window.py:577-596` | Connects bridge, launches worker, handles errors |
| `_on_scan_complete()` | `gui/main_window.py:~620` | Populates verify panel, enables export, updates status |
| Status bar mode badge | `gui/main_window.py:457-468` | Green "Connected to KiCad" / gray "Standalone" pill |
| Push to KiCad grayed | `gui/main_window.py:232,507` | `_act_push.setEnabled(self._bridge.is_connected)` |
| Connection error dialog | `gui/main_window.py:674` | `_show_connection_error()` with diagnostics |

### Fields currently extracted by `get_components()`

The existing `get_components()` in `kicad_bridge.py:108-164` reads:
- `reference` — from `fp.reference_field.text.value`
- `value` — from `fp.value_field.text.value`
- `footprint` — from `fp.definition.id`
- `datasheet` — from `fp.datasheet_field.text.value`
- `mpn` — scanned from `fp.texts_and_fields` matching `MPN_FIELD_NAMES`
- `extra_fields` — all custom fields as dict

**Potential gap:** The acceptance criteria explicitly mention "manufacturer, description, supplier P/Ns" — these are captured in `extra_fields` dict but not extracted as named fields on `BoardComponent`. Verify this is sufficient for downstream consumers (verify panel, assign dialog, BOM export).

### MPN_FIELD_NAMES set (models.py)

```python
MPN_FIELD_NAMES = {"mpn", "manf#", "mfr part", "mfr.part", "manufacturer part number",
                   "manufacturer_part_number", "part number", "pn"}
```

The bridge iterates `fp.texts_and_fields` and checks `fname.lower().strip()` against this set. All 8 KiCad MPN field aliases are covered.

### Architecture constraints

- **Core/GUI separation**: `kicad_bridge.py` lives in `gui/` (correct — it depends on optional `kipy`). `BoardComponent` lives in `core/models.py` (correct — zero GUI deps).
- **QThread pattern**: `ScanWorker` follows established pattern: `Signal` for results, error signal for failures, log signal for progress. See `gui/main_window.py:79-133`.
- **Adapter error handling**: Bridge methods return empty results on failure, never crash. `connect()` returns `(bool, str)` tuple.
- **Anti-pattern**: Never modify `.kicad_sch` files directly — use IPC API only via `kicad_bridge.py`.

### kipy (kicad-python) API surface used

```python
from kipy import KiCad

kicad = KiCad()                        # Auto-detects socket
board = kicad.get_board()              # Get board handle
footprints = board.get_footprints()    # List all footprints

# Per footprint:
fp.reference_field.text.value          # "C3"
fp.value_field.text.value              # "100nF"
fp.definition.id                       # footprint library:name
fp.datasheet_field.text.value          # URL string
fp.texts_and_fields                    # iterable of custom fields
  item.name                            # field name string
  item.text.value                      # field value string

# Selection:
board.clear_selection()
board.add_to_selection(fp)             # Highlights in PCB editor

# Write-back:
fp.datasheet_field.text.value = "..."
item.text.value = "..."
board.update_items(fp)                 # Commit changes
```

### Previous story learnings (from Story 4.2)

- `check_same_thread=False` required for SQLite connections used from QThread workers
- Error handling: cache/DB failures never crash the app — return empty/graceful
- Test fixtures: use `tmp_path` for all file operations, never touch real `~/.kipart-search/`
- Mock external dependencies (`httpx.Client`, `kipy.KiCad`) to avoid real network/IPC calls
- Test count baseline: 284 passed, 1 pre-existing failure (`test_central_widget_is_shrinkable_placeholder`)

### Testing approach

Since `kipy` requires a running KiCad instance, all tests must mock the `kipy` module:

```python
# Mock kipy import and KiCad class
mock_kicad = MagicMock()
mock_board = MagicMock()
mock_kicad.get_board.return_value = mock_board

# Create mock footprints with realistic field structure
mock_fp = MagicMock()
mock_fp.reference_field.text.value = "C1"
mock_fp.value_field.text.value = "100nF"
mock_fp.definition.id = "Capacitor_SMD:C_0805_2012Metric"
mock_fp.datasheet_field.text.value = ""
mock_fp.texts_and_fields = []
mock_board.get_footprints.return_value = [mock_fp]
```

Test file location: `tests/gui/test_kicad_bridge.py`

### Project Structure Notes

- All KiCad IPC API calls are correctly isolated in `gui/kicad_bridge.py`
- `BoardComponent` dataclass is in `core/models.py` — correct layer
- `ScanWorker` is in `gui/main_window.py` — acceptable, but could be extracted to a separate file if it grows. For now, leave it.
- No `core/` files import `kipy` — correct boundary enforcement

### References

- [Source: _bmad-output/planning-artifacts/epics.md - Epic 5, Story 5.1]
- [Source: _bmad-output/planning-artifacts/architecture.md - KiCad IPC API Integration, ADR-08, Cross-Cutting Concerns]
- [Source: _bmad-output/planning-artifacts/ux-design-specification.md - Dual-mode architecture, Scan initiation, Status bar]
- [Source: _bmad-output/planning-artifacts/architecture.md - Anti-patterns: direct file manipulation, silent field overwrite]
- [Source: CLAUDE.md - KiCad IPC API integration, kicad_bridge.py responsibilities]

## Dev Agent Record

### Agent Model Used

Claude Opus 4.6 (1M context)

### Debug Log References

- Full audit of `gui/kicad_bridge.py` — all AC fields verified present
- Full audit of `ScanWorker` and `_on_scan()` flow — signal chain verified
- Full audit of standalone mode — gray pill, grayed-out push, independent search/export
- Grep confirmed `kipy` only imported in `gui/kicad_bridge.py`

### Completion Notes List

- **Task 1 (Audit kicad_bridge.py):** All fields extracted correctly. `connect()` auto-detects via `KiCad()` constructor. `get_components()` reads reference, value, footprint, datasheet, MPN (via MPN_FIELD_NAMES), and all custom fields in `extra_fields`. Manufacturer, description, and supplier P/Ns are captured in `extra_fields` — sufficient for all downstream consumers.
- **Task 2 (Audit ScanWorker):** Signal chain `ScanWorker.scan_complete` → `_on_scan_complete` → `verify_panel.set_results` verified correct. MPN verification runs via `orchestrator.verify_mpn()`.
- **Task 3 (Standalone mode):** Status bar shows "Standalone" gray pill. Push to KiCad disabled. Search, JLCPCB DB, and export all work without KiCad. `_show_connection_error()` provides diagnostics.
- **Task 4 (Tests):** Created 37 tests in `tests/gui/test_kicad_bridge.py` covering: connect success/failure (3), get_components field extraction (12), graceful degradation without kipy (5), graceful degradation without KiCad (5), ScanWorker signals (5), select_component (2), write_field safety (5). All 37 pass. Installed `pytest-qt` for ScanWorker QThread tests.
- **Task 5 (Fix gaps):** No gaps found. No code changes needed — existing implementation fully meets all acceptance criteria.

### Change Log

- 2026-03-19: Story 5.1 audit and test implementation. Created `tests/gui/test_kicad_bridge.py` (37 tests). No production code changes required — existing implementation fully meets ACs.
- 2026-03-19: Code review fixes — removed dead `_extract_package_from_footprint` alias and unused `extract_package_from_footprint` import from `kicad_bridge.py`. Relocated `_import_blocker` helper to test helpers section.

### File List

- `tests/gui/__init__.py` (new)
- `tests/gui/test_kicad_bridge.py` (new — 37 tests, helper relocated during review)
- `src/kipart_search/gui/kicad_bridge.py` (review fix — removed dead alias and unused import)
