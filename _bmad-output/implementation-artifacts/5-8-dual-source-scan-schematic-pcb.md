# Story 5.8: Dual-Source Scan (Schematic + PCB)

Status: done

## Story

As a designer,
I want the scan to read component data from both my `.kicad_sch` schematic files and the PCB via IPC API,
so that I see all components (including unplaced ones), get the most up-to-date field values, and get warned when the PCB is out of sync with the schematic.

## Acceptance Criteria

1. **Given** the app is connected to KiCad and a board scan is initiated, **When** the scan reads components from the PCB via IPC API, **Then** the system also reads symbol properties from all `.kicad_sch` files in the project directory via `core/kicad_sch.py` **And** for each component, the scan merges data from both sources: schematic fields take priority over PCB fields for MPN, Manufacturer, and other custom properties (schematic is the source of truth).

2. **Given** a component exists in the schematic but has no footprint placed on the PCB, **When** the verification dashboard displays results, **Then** that component appears in the table with a distinct "Not on PCB" status indicator **And** click-to-highlight is unavailable for that component (no footprint to select) **And** the health summary bar counts these components under "Needs attention" **And** the log panel reports: "N component(s) found in schematic but not placed on PCB".

3. **Given** a component's schematic symbol has field values (e.g. MPN) that differ from the PCB footprint fields, **When** the verification dashboard displays results, **Then** that component shows an amber "PCB out of sync" indicator **And** a tooltip or detail text reads: "Schematic has MPN '[value]' but PCB does not — run Update PCB from Schematic (F8) in KiCad".

4. **Given** one or more components are detected as out of sync or not on PCB, **When** the scan completes, **Then** a banner or log message warns: "N component(s) need attention — run Update PCB from Schematic (F8) in KiCad, then re-scan."

5. **Given** all components have matching fields between PCB and schematic and all are placed, **When** the scan completes, **Then** no sync warning is shown — the scan proceeds as normal.

6. **Given** the app cannot locate the `.kicad_sch` project files (e.g. standalone mode, project directory not resolvable), **When** the scan runs, **Then** schematic reading is silently skipped — the scan works exactly as before (PCB-only) **And** no error is shown (graceful degradation).

## Tasks / Subtasks

- [x] Task 1: Extend BoardComponent with source and sync fields (AC: #1, #3)
  - [x] 1.1: Add `source: str = "pcb_only"` field to `BoardComponent` with values: `"both"`, `"pcb_only"`, `"sch_only"`
  - [x] 1.2: Add `sync_mismatches: list[str] = field(default_factory=list)` to `BoardComponent` — human-readable descriptions of field differences (e.g. `"MPN: schematic='RC0402FR-071KL', PCB=''"`  )

- [x] Task 2: Create merge logic in `core/verify.py` or new `core/merge.py` (AC: #1, #2, #3)
  - [x] 2.1: Implement `merge_pcb_sch(pcb_components: list[BoardComponent], sch_symbols: list[SchSymbol]) -> list[BoardComponent]` — match by reference designator (case-insensitive)
  - [x] 2.2: For components in both sources: copy MPN, Manufacturer, and custom fields from schematic to BoardComponent if schematic value is non-empty (schematic is source of truth). Record mismatches in `sync_mismatches`. Set `source = "both"`.
  - [x] 2.3: For components only in schematic: create new `BoardComponent` from `SchSymbol` data with `source = "sch_only"`. Copy reference, value, footprint, and all fields from the schematic symbol.
  - [x] 2.4: For components only in PCB: leave `source = "pcb_only"` (unchanged from current behavior).
  - [x] 2.5: Use `MPN_FIELD_NAMES` set (from `models.py`) to identify MPN fields across different naming conventions in schematic properties.

- [x] Task 3: Update ScanWorker to read schematic files (AC: #1, #6)
  - [x] 3.1: After `bridge.get_components()`, resolve project directory via `bridge.get_project_dir()`
  - [x] 3.2: If project directory available, call `kicad_sch.find_schematic_files(project_dir)` to discover all `.kicad_sch` files
  - [x] 3.3: Call `kicad_sch.read_symbols(path)` for each schematic file, collect all `SchSymbol` objects
  - [x] 3.4: Call `merge_pcb_sch(pcb_components, sch_symbols)` to produce merged component list
  - [x] 3.5: Log schematic reading progress: "Reading schematic files: N sheets found, M symbols read"
  - [x] 3.6: If project directory not available or schematic files not found, log "Schematic files not found — using PCB data only" and continue with PCB-only components (graceful degradation)
  - [x] 3.7: Wrap schematic reading in try/except — any schematic read failure falls back to PCB-only silently

- [x] Task 4: Update ScanWorker signal to carry sync metadata (AC: #2, #3, #4)
  - [x] 4.1: Extend `scan_complete` signal or add counts to emitted data for sch-only and mismatched components
  - [x] 4.2: In `_on_scan_complete()`, log warnings: "N component(s) found in schematic but not placed on PCB" if any `sch_only` components exist
  - [x] 4.3: In `_on_scan_complete()`, log warnings: "N component(s) need attention — run Update PCB from Schematic (F8) in KiCad, then re-scan." if any sync mismatches or sch-only components exist

- [x] Task 5: Update verify_panel to display new statuses (AC: #2, #3, #5)
  - [x] 5.1: In `set_results()`, detect `source == "sch_only"` components — display "Not on PCB" in the MPN Status column with a distinct color (e.g. light blue or grey background, not RED — this is informational, not an error)
  - [x] 5.2: In `set_results()`, detect components with non-empty `sync_mismatches` — display "PCB out of sync" in amber
  - [x] 5.3: Add tooltip to "PCB out of sync" cells: show the specific mismatches from `sync_mismatches` list
  - [x] 5.4: Update health bar counts: `sch_only` components count as "Needs attention" (subtract from "Ready" percentage)
  - [x] 5.5: For `sch_only` components, disable click-to-highlight (no footprint to select in PCB). In `_on_component_clicked()` check source before calling `bridge.select_component()`.

- [x] Task 6: Handle click-to-highlight for sch-only components (AC: #2)
  - [x] 6.1: In `_on_component_clicked()` in `main_window.py`, check if component has `source == "sch_only"` before attempting PCB highlight
  - [x] 6.2: If sch-only, log "Component {ref} exists only in schematic — cannot highlight in PCB" (no error dialog)
  - [x] 6.3: Guided search (double-click) should still work for sch-only components — use their value/footprint for query

- [x] Task 7: Testing (all ACs)
  - [x] 7.1: Unit test `merge_pcb_sch()` with components in both sources, PCB-only, and sch-only
  - [x] 7.2: Unit test field priority — schematic MPN overwrites empty PCB MPN; PCB value preserved when schematic is empty
  - [x] 7.3: Unit test sync mismatch detection — different MPN values produce correct mismatch description
  - [ ] 7.4: Manual test with real KiCad project: scan with some components not placed on PCB, verify "Not on PCB" appears
  - [ ] 7.5: Manual test: push MPN to schematic (Story 5.7), then re-scan WITHOUT running F8 — verify "PCB out of sync" indicator appears
  - [ ] 7.6: Manual test: standalone mode — verify graceful degradation (PCB-only scan, no error)
  - [ ] 7.7: Manual test: hierarchical project with sub-sheets — verify all sheets are scanned

## Dev Notes

### Architecture & Key Decisions

**This story is read-only** — no `.kicad_sch` file modification occurs. The schematic parser from Story 5.6 is used purely for reading. Lock files do NOT prevent read access.

**Merge logic belongs in `core/`** — zero GUI dependencies. The merge function takes typed inputs (`list[BoardComponent]`, `list[SchSymbol]`) and returns `list[BoardComponent]` (extended with source/sync fields). This keeps the verify panel and main window free of merge logic.

**Extend `BoardComponent` rather than creating `MergedComponent`** — the epics suggest either approach. Extending `BoardComponent` is simpler: add two fields (`source`, `sync_mismatches`) with sensible defaults so existing code (BOM export, assign dialog, detail panel) continues to work unchanged. A new `MergedComponent` class would require updating every consumer.

**Schematic is source of truth for custom fields** — when both sources have data, schematic values win for MPN, Manufacturer, Description, and supplier P/Ns. PCB wins for footprint (it represents the actual board placement). Reference and Value should always agree — if they don't, flag as mismatch but don't override.

### Existing Code to Reuse — DO NOT Reinvent

| What | Where | How to use |
|------|-------|------------|
| Schematic reading | `core/kicad_sch.py` | `read_symbols(path) -> list[SchSymbol]` — returns symbols with all fields |
| Sheet discovery | `core/kicad_sch.py` | `find_schematic_files(project_dir) -> list[Path]` — BFS through hierarchy |
| Project directory | `gui/kicad_bridge.py:get_project_dir()` | Returns `Path` to KiCad project directory (board file parent) |
| MPN field aliases | `core/models.py` | `MPN_FIELD_NAMES` set — use to identify MPN across naming conventions |
| Component model | `core/models.py:BoardComponent` | Extend with `source` and `sync_mismatches` fields |
| Scan worker | `gui/main_window.py:ScanWorker` | Modify `run()` to add schematic reading after PCB scan |
| Verify panel | `gui/verify_panel.py:set_results()` | Modify to display new status indicators |
| Health bar | `gui/verify_panel.py` | Update count logic for sch-only components |

### Critical Integration Points

1. **`ScanWorker.run()` (main_window.py, ~line 83)** — After `self.bridge.get_components()` returns PCB components, add schematic reading and merge. The merged list replaces the PCB-only list for all downstream processing (MPN verification, signal emission).

2. **`verify_panel.set_results()` (verify_panel.py, ~line 171)** — Currently iterates `components` and sets cell colors based on MPN presence and verification status. Add checks for `comp.source == "sch_only"` and `len(comp.sync_mismatches) > 0` to set appropriate status text and color.

3. **`_on_scan_complete()` (main_window.py, ~line 707)** — Currently re-applies `_local_assignments` and calls `verify_panel.set_results()`. Add warning log messages about sch-only and desync components.

4. **`_on_component_clicked()` (main_window.py, ~line 1029)** — Currently calls `bridge.select_component(reference)`. Guard with source check — sch-only components have no footprint to highlight.

5. **MPN verification for sch-only components** — `ScanWorker` already verifies MPNs for any component with `has_mpn == True`. After merge, sch-only components that have MPN values from the schematic will be verified automatically — no special handling needed.

### Data Flow After This Story

```
User clicks "Scan Project"
    ↓
ScanWorker.run() [background thread]
    ├─ bridge.get_components()  →  list[BoardComponent] from PCB
    ├─ bridge.get_project_dir()  →  Path | None
    ├─ kicad_sch.find_schematic_files(project_dir)  →  list[Path]
    ├─ kicad_sch.read_symbols(path) for each sheet  →  list[SchSymbol]
    ├─ merge_pcb_sch(pcb_components, sch_symbols)  →  list[BoardComponent] (merged)
    │   ├─ Match by reference (case-insensitive)
    │   ├─ Copy schematic fields to BoardComponent (schematic wins)
    │   ├─ Flag sync mismatches
    │   └─ Create BoardComponent entries for sch-only symbols
    └─ For each component with MPN: verify_mpn() [unchanged]
    ↓
scan_complete.emit(merged_components, mpn_statuses, db_mtime)
    ↓
_on_scan_complete()
    ├─ Re-apply _local_assignments [unchanged]
    ├─ Log sch-only / desync warnings
    └─ verify_panel.set_results(merged_components, ...) [with new status handling]
```

### Reference Matching: SchSymbol ↔ BoardComponent

Match by reference designator. `SchSymbol.reference` is extracted from `(property "Reference" "C3" ...)`. `BoardComponent.reference` is from `fp.reference_field.text.value`. Both are strings like "C3", "R1", "U5".

**Case sensitivity:** KiCad references are case-sensitive ("C3" ≠ "c3"). Use exact match — KiCad itself enforces consistent casing.

**Multi-unit symbols:** KiCad uses suffixes like "U1A", "U1B" for multi-unit parts. Each unit is a separate symbol in the schematic but maps to a single footprint "U1" on the PCB. Handle by matching on the base reference (strip trailing letter for multi-unit parts) OR document this as a known limitation for v1.

### Schematic Field Discovery

`SchSymbol.fields` is a `dict[str, str]` containing ALL properties. The keys are the property names exactly as written in the `.kicad_sch` file — e.g. `"MPN"`, `"mpn"`, `"Manf#"`, `"Manufacturer"`, etc.

To find the MPN value from a SchSymbol:
```python
mpn = ""
for field_name, field_value in symbol.fields.items():
    if field_name.lower().strip() in MPN_FIELD_NAMES:
        mpn = field_value
        break
```

Similarly for Manufacturer — use a similar alias set or check for common names.

### GUI Status Display Approach

| Component state | MPN Status text | Background color | Notes |
|----------------|-----------------|------------------|-------|
| In both, synced, MPN verified | "Verified" | GREEN (#C8FFC8) | Existing behavior |
| In both, synced, no MPN | "Missing MPN" | RED (#FFC8C8) | Existing behavior |
| In both, fields differ | "PCB out of sync" | AMBER (#FFEBB4) | New — tooltip shows mismatches |
| Sch only, has MPN | "Not on PCB" | Light blue (#C8E0FF) | New — informational |
| Sch only, no MPN | "Not on PCB" | Light blue (#C8E0FF) | New — still needs MPN |
| PCB only | Normal behavior | Per existing logic | source="pcb_only" is the default |

**Tooltip for "PCB out of sync":** Join `sync_mismatches` list with newlines. E.g.: "Schematic has MPN 'RC0402FR-071KL' but PCB has ''\nRun Update PCB from Schematic (F8) in KiCad"

### Error Handling

- **Schematic files not found:** Log once, continue PCB-only (graceful degradation)
- **Single sheet read fails:** Log error for that sheet, continue with other sheets
- **Merge produces unexpected state:** Never crash — worst case is PCB-only behavior
- **SchSymbol with no Reference:** Skip — can't match to PCB component
- **Power symbols in schematic:** These are `(symbol (lib_id "power:GND") ...)` etc. They have references like "#PWR01" which start with "#". Filter these out — they have no PCB footprint and are not real components.

### Filtering Schematic Symbols

Not all SchSymbol entries are real components:
- **Power symbols:** Reference starts with `"#"` (e.g. `#PWR01`, `#FLG01`). Skip these.
- **Power flags:** lib_id starts with `"power:"`. Skip these.
- **Graphic symbols:** Some symbols have no footprint property or empty footprint. May or may not be relevant — include if they have a meaningful reference, exclude if reference starts with `"#"`.

### Previous Story Intelligence (from Stories 5.6 and 5.7)

**From Story 5.6 (Schematic Parser):**
- `_find_block()` handles escaped quotes in property values (fixed in code review)
- `_find_insertion_point()` was hardened for compact/single-line symbol blocks
- Property ID auto-detection works — not relevant for read-only use here
- `SchSymbol.fields` dict contains ALL properties including Reference, Value, Footprint
- Parser correctly skips `(lib_symbols ...)` section — only placed symbols returned
- 26 automated tests validate parser correctness

**From Story 5.7 (Push to KiCad):**
- `get_project_dir()` already exists in `kicad_bridge.py` — returns board file parent directory
- `_resolve_project_dir()` handles 3 modes: connected → board path parent, standalone with BOM → BOM file parent, fallback → folder picker
- `find_schematic_files()` and `read_symbols()` are already used in the push flow — proven to work with real projects
- The push flow reads old values before writing — same pattern used here for merge comparison
- Lock files do NOT block reading (only writing). The story 5.7 push checks locks, but scan reads are always safe.

### Git Intelligence

Recent commits show:
- `f3eda46`: Story 5.7 implemented full push-to-kicad orchestration
- `cf59efc`: Code review #2 added value escaping to kicad_sch writer
- `7b9b0e3`: Code review fixed escaped-quote handling in parser
- `9e486af`: Story 5.6 created the S-expression parser
- `4677e57`: IPC write-back disabled — board.update_items() destroys custom fields

All recent work is in the schematic parser / write-back pipeline. This story completes the cycle by using the parser for reading during scan.

### Project Structure Notes

- Merge logic: `core/verify.py` (if small) or new `core/merge.py` — both are valid. Prefer adding to `core/verify.py` since it already handles component verification logic, or consider `core/models.py` if the function is purely about data transformation.
- No new GUI modules needed — changes are to existing `verify_panel.py` and `main_window.py`
- Test file: `tests/core/test_merge.py` (or extend `tests/core/test_verify.py`)
- No new dependencies — all required modules (`kicad_sch`, `models`, `kicad_bridge`) already exist

### References

- [Source: _bmad-output/planning-artifacts/epics.md — Epic 5, Story 5.8]
- [Source: _bmad-output/planning-artifacts/architecture.md — ADR-08: Write-Back Strategy (dual-path)]
- [Source: _bmad-output/planning-artifacts/sprint-change-proposal-2026-03-22.md — Full proposal for Story 5.8]
- [Source: _bmad-output/project-context.md — Critical rules for core/GUI separation, kicad_sch.py usage]
- [Source: src/kipart_search/core/kicad_sch.py — read_symbols(), find_schematic_files(), SchSymbol]
- [Source: src/kipart_search/core/models.py — BoardComponent, MPN_FIELD_NAMES, Confidence]
- [Source: src/kipart_search/gui/main_window.py — ScanWorker, _on_scan_complete(), _on_component_clicked()]
- [Source: src/kipart_search/gui/verify_panel.py — set_results(), health bar logic]
- [Source: src/kipart_search/gui/kicad_bridge.py — get_project_dir(), get_components(), select_component()]
- [Source: _bmad-output/implementation-artifacts/5-7-file-based-write-back-push-to-kicad.md — Previous story learnings]
- [Source: _bmad-output/implementation-artifacts/5-6-schematic-file-parser-module.md — Parser implementation details]

## Dev Agent Record

### Agent Model Used

Claude Opus 4.6 (1M context)

### Debug Log References

### Completion Notes List

- Created `core/merge.py` with `merge_pcb_sch()` — merges PCB and schematic data by reference match, schematic fields take priority, filters power symbols and empty references
- Extended `BoardComponent` with `source` ("pcb_only"/"both"/"sch_only") and `sync_mismatches` (list of human-readable field diff strings)
- Added `_merge_schematic_data()` helper to `ScanWorker` — reads all schematic sheets via `kicad_sch.find_schematic_files()` + `read_symbols()`, graceful degradation on any failure
- `_on_scan_complete()` now logs sync warnings: "N component(s) found in schematic but not placed on PCB" and "N component(s) need attention" messages
- `verify_panel.set_results()` displays "Not on PCB" (light blue #C8E0FF) for sch-only and "PCB out of sync" (amber) with tooltip for desynced components
- Health bar and summary updated: sch-only and desynced components count as "Needs attention", "Ready for export" requires zero sch-only
- `_on_component_clicked()` guards sch-only components — logs info message instead of trying PCB highlight
- Detail panel shows source info and mismatch list for desynced components
- 19 unit tests covering: both-source merge, sch-only creation, pcb-only preservation, power symbol filtering, MPN alias matching, manufacturer/datasheet merge with mismatch detection, mixed scenarios
- 0 regressions in full test suite (181 core tests pass, 13 pre-existing GUI test failures unchanged)

### Change Log

- 2026-03-22: Story 5.8 implementation complete — dual-source scan with schematic+PCB merge
- 2026-03-22: Code review — fixed 2 MEDIUM issues: (1) desynced components now sort as AMBER instead of retaining GREEN sort order, (2) update_component_status() recount now accounts for sch-only and desynced components
- 2026-03-23: Code review #2 — fixed 3 issues: (1) HIGH: get_health_percentage() now excludes desynced and sch-only components from healthy count, (2) MEDIUM: Datasheet field lookup is now case-insensitive matching MPN/Manufacturer approach, (3) LOW: sch-only components no longer duplicate MPN/Datasheet in extra_fields

### File List

- `src/kipart_search/core/models.py` — Added `source` and `sync_mismatches` fields to BoardComponent
- `src/kipart_search/core/merge.py` — NEW: merge_pcb_sch() function and supporting helpers
- `src/kipart_search/gui/main_window.py` — ScanWorker._merge_schematic_data(), _on_scan_complete() sync warnings, _on_component_clicked() sch-only guard
- `src/kipart_search/gui/verify_panel.py` — "Not on PCB" and "PCB out of sync" status display, health bar updates, detail panel sync info
- `tests/core/test_merge.py` — NEW: 19 unit tests for merge logic
