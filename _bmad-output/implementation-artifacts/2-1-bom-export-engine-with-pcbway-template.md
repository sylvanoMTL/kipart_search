# Story 2.1: BOM Export Engine with PCBWay Template

Status: ready-for-dev

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a designer,
I want a core BOM export engine that transforms my verified component data into a PCBWay-format Excel file,
So that I can generate a production BOM my CM accepts without manual spreadsheet work.

## Acceptance Criteria

1. **Given** a list of ComponentData objects with MPN, manufacturer, description, footprint, and designator fields
   **When** the export engine is invoked with the PCBWay template
   **Then** it produces an Excel file (.xlsx via openpyxl) with columns: Item #, Designator, Qty, Manufacturer, Mfg Part #, Description/Value, Package, Type (FR24, FR29)
   **And** CSV export is also supported as an alternative file format

2. **Given** multiple components share the same MPN and manufacturer
   **When** the export runs
   **Then** they are grouped into a single row with combined designators (e.g. "R14,R18") and correct quantity (e.g. 2) (FR25)

3. **Given** a component has a KiCad footprint name like `C_0805_2012Metric`
   **When** the export engine processes it
   **Then** the Package column contains the standard package name "0805" (FR26)

4. **Given** a component footprint
   **When** the export engine processes it
   **Then** the Type column shows "SMD" or "THT" based on footprint analysis (FR27)

5. **Given** the export engine is in `core/bom_export.py`
   **When** it is imported
   **Then** it has zero GUI dependencies (no PySide6 imports)

6. **Given** the project dependencies
   **When** `openpyxl` is needed for Excel export
   **Then** it is listed in `pyproject.toml` under `[project] dependencies`

7. **Given** the BOMTemplate and BOMColumn dataclasses
   **When** defined in `core/bom_export.py`
   **Then** they follow ADR-02: declarative dict-based mappings with `name`, `columns`, `group_by`, `dnp_handling`, `file_format` fields

## Tasks / Subtasks

- [ ] Task 1: Move `BoardComponent` dataclass from `gui/kicad_bridge.py` to `core/models.py` (AC: #5)
  - [ ] Cut the `BoardComponent` dataclass (and its properties: `has_mpn`, `footprint_short`, `build_search_query()`) from `gui/kicad_bridge.py`
  - [ ] Paste it into `core/models.py` alongside `PartResult` — it's a data model, not GUI code
  - [ ] In `gui/kicad_bridge.py`, replace with `from kipart_search.core.models import BoardComponent` — all existing code continues to work
  - [ ] Update any other files that import `BoardComponent` from `kicad_bridge` (check `verify_panel.py`, `main_window.py`, `assign_dialog.py`)
  - [ ] Run all 92 existing tests — zero regressions expected since the class interface is unchanged

- [ ] Task 2: Add `openpyxl` to pyproject.toml (AC: #6)
  - [ ] Add `openpyxl` to `[project] dependencies` list
  - [ ] Run `pip install -e .` to verify installation

- [ ] Task 3: Move `_extract_package_from_footprint()` to core/ (AC: #3)
  - [ ] Create a public `extract_package_from_footprint(footprint: str) -> str` in `core/models.py`
  - [ ] Move the logic from `gui/kicad_bridge.py` lines 76-99 to the new location
  - [ ] In `gui/kicad_bridge.py`, import and delegate to the core function (backward-compatible)
  - [ ] Add SMD/THT detection: `detect_mount_type(footprint: str) -> str` returning `"SMD"` or `"THT"`
    - SMD: footprints containing `_SMD`, `Capacitor_SMD`, `Resistor_SMD`, `Inductor_SMD`, `Package_SO`, `Package_QFP`, `Package_DFN_QFN`, `Package_BGA`, `Package_CSP`, `LED_SMD`, `Package_TO_SOT_SMD`, or passive sizes (0201-2512)
    - THT: footprints containing `_THT`, `Package_DIP`, `Package_TO_SOT_THT`, `Connector_PinHeader`, `Connector_PinSocket`, or `Package_TO_*THT*`
    - Default: `"SMD"` (conservative — most modern designs are SMD-dominant)

- [ ] Task 4: Create `core/bom_export.py` with BOMTemplate/BOMColumn dataclasses (AC: #5, #7)
  - [ ] Add `from __future__ import annotations` header
  - [ ] Define `BOMColumn` dataclass: `header: str`, `field: str`, `transform: str | None = None`
  - [ ] Define `BOMTemplate` dataclass: `name: str`, `columns: list[BOMColumn]`, `group_by: str = "mpn"`, `dnp_handling: str = "include_marked"`, `file_format: str = "xlsx"`
  - [ ] Define `PCBWAY_TEMPLATE` constant with 9 columns matching the PCBWay format (see Dev Notes for exact columns)

- [ ] Task 5: Implement the export engine function (AC: #1, #2, #3, #4)
  - [ ] Define input type: accept `list[BoardComponent]` (from `core/models.py` after Task 1 move) — the export engine reads `.mpn`, `.manufacturer` (from extra_fields or a new field), `.value`, `.footprint`, `.reference`
  - [ ] Implement `export_bom(components: list[BoardComponent], template: BOMTemplate, output_path: Path) -> Path`:
    1. Group components by `(mpn.upper(), manufacturer.upper())` — skip components with empty MPN (or group them as "UNASSIGNED" rows)
    2. For each group: combine designators sorted naturally (R1,R2,R14 not R1,R14,R2), count quantity
    3. Apply column transforms: `"package_extract"` calls `extract_package_from_footprint()`, `"smd_tht_detect"` calls `detect_mount_type()`
    4. Write to Excel via openpyxl: header row with `header` values from template, data rows with mapped fields
    5. Item # column: sequential 1, 2, 3...
    6. Return the output path
  - [ ] Implement natural sort for designators: R1, R2, R10 (not R1, R10, R2)
  - [ ] Handle edge cases: empty component list (write header-only file), components with no MPN (include with empty MPN cell or separate section)

- [ ] Task 6: Add CSV export support (AC: #1)
  - [ ] Implement `_write_csv(rows: list[dict], template: BOMTemplate, output_path: Path) -> Path`
  - [ ] `export_bom()` checks `template.file_format` and dispatches to xlsx or csv writer
  - [ ] CSV uses stdlib `csv.writer` — no extra dependency

- [ ] Task 7: Write tests in `tests/core/test_bom_export.py` (AC: #1-#7)
  - [ ] `test_pcbway_template_columns` — verify PCBWAY_TEMPLATE has 9 columns with correct headers
  - [ ] `test_grouping_by_mpn` — 3 components (R1, R2 same MPN; C1 different) → 2 rows, R1+R2 qty=2
  - [ ] `test_designator_natural_sort` — R1,R10,R2 → "R1,R2,R10"
  - [ ] `test_package_extraction` — C_0805_2012Metric → "0805", R_0402_1005Metric → "0402"
  - [ ] `test_smd_tht_detection` — Resistor_SMD → "SMD", Package_DIP → "THT"
  - [ ] `test_excel_output` — export to temp file, open with openpyxl, verify header and data rows
  - [ ] `test_csv_output` — export to temp CSV, read back, verify content
  - [ ] `test_empty_component_list` — export with no components → file with header only
  - [ ] `test_no_gui_imports` — `import core.bom_export; assert 'PySide6' not in sys.modules`

- [ ] Task 8: Integration smoke test
  - [ ] Launch app, scan a project (or mock), verify Export BOM button is still disabled (GUI wiring is Story 2.4)
  - [ ] Run `python -c "from kipart_search.core.bom_export import export_bom, PCBWAY_TEMPLATE"` — imports cleanly
  - [ ] Run all tests — no regressions

## Dev Notes

### Architecture Compliance

- **Core/GUI separation**: `core/bom_export.py` has ZERO PySide6 imports. It depends on `core/models.py` (or wherever package extraction lands), `openpyxl`, and stdlib `csv`.
- **ADR-02**: BOMTemplate is a declarative dataclass, NOT a Jinja2 template. Preset templates are module-level constants. Custom templates will be JSON (Story 2.2+).
- **ADR-02 verbatim**: "Each CM template is a Python dataclass defining column names, column order, field mappings, grouping rules, and DNP handling. No Jinja2 or string-template dependency."

### PCBWay Template Columns (from Sample_BOM_PCBWay.xlsx)

The PCBWay Excel file has headers at row 6, data starting at row 7. Required fields marked with `*`:

| # | Header | Field Source | Transform | Required |
|---|--------|-------------|-----------|----------|
| A | Item # | auto-increment | none | no |
| B | *Designator | reference (grouped) | none | yes |
| C | *Qty | count of grouped refs | none | yes |
| D | Manufacturer | extra_fields["manufacturer"] or "" | none | no |
| E | *Mfg Part # | mpn | none | yes |
| F | Description / Value | value or description | none | no |
| G | *Package/Footprint | footprint | package_extract | yes |
| H | Type | footprint | smd_tht_detect | no |
| I | Your Instructions / Notes | "" | none | no |

### BOMColumn field mapping

The `field` attribute on `BOMColumn` maps to `BoardComponent` attributes:
- `"item_number"` → auto-increment (special case)
- `"designator"` → grouped references string
- `"quantity"` → count of grouped refs
- `"manufacturer"` → `comp.extra_fields.get("manufacturer", "")`
- `"mpn"` → `comp.mpn`
- `"value"` → `comp.value`
- `"package"` → `extract_package_from_footprint(comp.footprint)`
- `"mount_type"` → `detect_mount_type(comp.footprint)`
- `"notes"` → `""` (empty by default)

### Manufacturer field on BoardComponent

`BoardComponent.extra_fields` stores arbitrary KiCad fields. The manufacturer name may be under various aliases: "manufacturer", "mfr", "Manufacturer", etc. The kicad_bridge already normalizes field names into `extra_fields`. For the export engine, use `comp.extra_fields.get("manufacturer", "")` — the bridge handles alias resolution.

### Package Extraction — Already Implemented

`_extract_package_from_footprint()` in `gui/kicad_bridge.py` (lines 76-99) already handles:
- Passive sizes: strips library prefix, matches 4-digit imperial codes (0402, 0805, 1206, etc.)
- IC packages: regex for SOT-*, SOIC-*, QFN-*, BGA-*, TSSOP-*, LQFP-*, etc.
- Connectors: extracts pin count

Move this to `core/` so `bom_export.py` can import it. Keep the function signature identical. In `kicad_bridge.py`, replace the function body with `from kipart_search.core.models import extract_package_from_footprint` (or wherever it lands) and call through.

### SMD/THT Detection — New Logic

KiCad footprint library names indicate mount type:
- `Capacitor_SMD:*` → SMD
- `Resistor_THT:*` → THT
- `Package_DIP:*` → THT
- `Package_SO:*` → SMD
- `Package_QFP:*` → SMD
- `Package_TO_SOT_SMD:*` → SMD
- `Package_TO_SOT_THT:*` → THT

Strategy: check the library prefix (part before `:`) for `_SMD` or `_THT` suffixes. For ambiguous footprints, check specific library names. Default to "SMD".

### Grouping Algorithm

```
Input: [BoardComponent(ref="R1", mpn="RC0805FR-0710KL", mfr="Yageo", ...),
        BoardComponent(ref="R2", mpn="RC0805FR-0710KL", mfr="Yageo", ...),
        BoardComponent(ref="C1", mpn="GRM21BR71C104KA01L", mfr="Murata", ...)]

Group key: (mpn.upper(), manufacturer.upper())

Output rows:
  Row 1: Item=1, Designator="R1,R2", Qty=2, Mfr="Yageo", MPN="RC0805FR-0710KL", ...
  Row 2: Item=2, Designator="C1", Qty=1, Mfr="Murata", MPN="GRM21BR71C104KA01L", ...
```

Components with empty MPN: group by `("", "")` → single row with all unassigned designators. Or list each separately. PCBWay requires MPN, so warn but include.

### Natural Sort for Designators

Designators must be sorted naturally: R1, R2, R10 (not R1, R10, R2). Use a key function that splits on letter/digit boundary: `("R", 1)`, `("R", 2)`, `("R", 10)`.

```python
import re
def _natural_sort_key(ref: str) -> tuple:
    parts = re.split(r'(\d+)', ref)
    return tuple(int(p) if p.isdigit() else p for p in parts)
```

### openpyxl Usage Pattern

```python
from openpyxl import Workbook

wb = Workbook()
ws = wb.active
ws.title = "BOM"

# Header row
headers = [col.header for col in template.columns]
ws.append(headers)

# Data rows
for row_data in rows:
    ws.append([row_data.get(col.field, "") for col in template.columns])

wb.save(output_path)
```

Keep it minimal — no cell formatting, no merged cells, no styles. Plain data. CMs import data, not formatting.

### What This Story Does NOT Include

- **No GUI dialog** — the export dialog is Story 2.4
- **No toolbar button wiring** — the button stays disabled; Story 2.4 wires it
- **No JLCPCB or Newbury templates** — those are Story 2.2
- **No health summary bar** — that is Story 2.3
- **No coverage validation / warning** — FR28 is handled in Story 2.4 (dialog shows warning)
- **No custom template JSON loading** — future story
- **No DNP filtering** — the BOMTemplate has `dnp_handling` field, but logic deferred to Story 2.4

### Project Structure Notes

- New file: `src/kipart_search/core/bom_export.py`
- New file: `tests/core/test_bom_export.py`
- Modified: `pyproject.toml` (add openpyxl dependency)
- Modified: `src/kipart_search/core/models.py` (add `BoardComponent` from kicad_bridge, add `extract_package_from_footprint`, `detect_mount_type`)
- Modified: `src/kipart_search/gui/kicad_bridge.py` (import BoardComponent from core/models, delegate package extraction to core function)
- Modified: any files importing `BoardComponent` from `kicad_bridge` (verify_panel.py, main_window.py, assign_dialog.py, etc.)
- Alignment: follows `src/kipart_search/` layout from architecture spec

### Previous Story Intelligence (Story 1.5)

Key learnings from Epic 1:
- All 92 tests pass after Story 1.5 (80 from stories 1.1-1.4 + 12 from 1.5)
- Test pattern: `pytest.importorskip("PySide6")` guard for GUI tests — NOT needed for `test_bom_export.py` since it tests core/ code with no GUI deps
- Commit pattern: one commit per story implementation, one per code review fix
- `_build_context_menu()` refactor was needed because `QMenu.exec` can't be patched — similarly, keep export engine testable by having pure functions that return data, not side effects
- QAction does not support `setAccessibleDescription()` — this kind of Qt API limitation is common; check API docs before assuming methods exist

### Git Intelligence

Recent commits show pattern: one story per commit, descriptive message referencing the story. Code review fixes in a separate commit. Tests always included in the story commit.

```
f565611 Code review fixes for Story 1.5
9d1a79b Add context menus, descriptive status labels, and accessibility properties (Story 1.5)
e157709 Code review fixes for Story 1.4
01fc29d Add layout persistence via QSettings and empty-state guidance for all panels (Story 1.4)
```

### Testing Notes

- `tests/core/test_bom_export.py` — NO PySide6 dependency, NO `pytest.importorskip` guard needed
- Use `tmp_path` fixture for output files (pytest built-in)
- For Excel verification: `from openpyxl import load_workbook` to read back and assert
- For CSV: use `csv.reader` to read back
- Create `BoardComponent` test fixtures directly: `from kipart_search.core.models import BoardComponent` (available after Task 1 move — no PySide6 dependency)

### Anti-Patterns to Avoid

- Do NOT import PySide6 in `core/bom_export.py` — this is the #1 architectural constraint
- Do NOT import anything from `gui/` in `core/` modules — `BoardComponent` is in `core/models.py` after Task 1
- Do NOT add cell formatting/styling to the Excel output — plain data, CMs import data not formatting
- Do NOT implement the export dialog or wire the toolbar button — that's Story 2.4
- Do NOT implement JLCPCB or Newbury templates — that's Story 2.2
- Do NOT use Jinja2 or string templates — ADR-02 mandates declarative dataclass mappings
- Do NOT block the GUI thread — even though Story 2.1 is core-only, design the export function to be callable from a QThread worker later
- Do NOT use `pickle` for any serialization — JSON only (project rule)
- Do NOT hardcode file paths — use `pathlib.Path` everywhere

### Cross-Story Dependencies

- **Story 1.1-1.5** (done): QDockWidget architecture, toolbar with disabled "Export BOM" button
- **Story 2.2** (next): Adds JLCPCB and Newbury templates as additional constants in `core/bom_export.py`
- **Story 2.3** (future): Health Summary Bar — uses component status data but NOT the export engine
- **Story 2.4** (future): Export Dialog — the GUI that calls `export_bom()`, wires the toolbar button, handles coverage warnings and DNP filtering

### References

- [Source: _bmad-output/planning-artifacts/epics.md — Epic 2, Story 2.1]
- [Source: _bmad-output/planning-artifacts/architecture.md — ADR-02: BOM Export Template Engine]
- [Source: _bmad-output/planning-artifacts/architecture.md — BOM Export Patterns, BOMTemplate/BOMColumn code]
- [Source: _bmad-output/planning-artifacts/ux-design-specification.md — BOM Export Window, Template Selection]
- [Source: _bmad-output/planning-artifacts/prd.md — FR24-FR29: BOM Export requirements]
- [Source: _bmad-output/project-context.md — Core/GUI separation, naming conventions, dataclass rules]
- [Source: ExistingWorksOn/Sample_BOM_PCBWay.xlsx — PCBWay column format reference]
- [Source: src/kipart_search/gui/kicad_bridge.py — _extract_package_from_footprint(), BoardComponent]
- [Source: src/kipart_search/core/models.py — PartResult, Confidence, existing dataclasses]

## Dev Agent Record

### Agent Model Used

{{agent_model_name_version}}

### Debug Log References

### Completion Notes List

### File List
