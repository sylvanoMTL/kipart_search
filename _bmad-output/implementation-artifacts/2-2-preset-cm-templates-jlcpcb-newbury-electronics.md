# Story 2.2: Preset CM Templates (JLCPCB, Newbury Electronics)

Status: review

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a designer,
I want preset BOM templates for JLCPCB and Newbury Electronics in addition to PCBWay,
So that I can export in the right format for whichever CM I'm using without building templates manually.

## Acceptance Criteria

1. **Given** the BOM export engine from Story 2.1
   **When** the JLCPCB SMT template is selected
   **Then** the export produces a file with columns: Comment, Designator, Footprint, JLCPCB Part # — matching the `ExistingWorksOn/Sample-BOM_JLCSMT.xlsx` reference file

2. **Given** a component that was assigned from the JLCPCB search results
   **When** the JLCPCB template is used for export
   **Then** the "JLCPCB Part #" column is populated from `extra_fields.get("LCSC Part", "")` or `extra_fields.get("lcsc", "")`

3. **Given** the Newbury Electronics template is selected
   **When** the export runs
   **Then** it produces columns: Item#, Description, Quantity, Manufacturer Name, Manufacturer Part Number, Supplier Name, Supplier Part Number, Designator, Notes — matching `ExistingWorksOn/pcb-bom-sample-file-newbury-electronics.xlsx`

4. **Given** the three preset templates exist
   **When** imported from `core/bom_export.py`
   **Then** `PCBWAY_TEMPLATE`, `JLCPCB_TEMPLATE`, and `NEWBURY_TEMPLATE` are all available as module-level constants
   **And** a `PRESET_TEMPLATES` list contains all three in order

5. **Given** any preset template
   **When** exported as CSV (by overriding `file_format="csv"`)
   **Then** the CSV output has the same columns and data as the xlsx output

6. **Given** the JLCPCB template groups components
   **When** multiple components share the same MPN
   **Then** they are grouped into one row with combined designators and correct quantity (reusing the existing `_group_components` logic)

7. **Given** new field mappings needed for JLCPCB and Newbury templates
   **When** `_group_components` builds row dicts
   **Then** it includes `lcsc_part` (from `extra_fields`) and `supplier_name` / `supplier_pn` (from `extra_fields`) alongside existing fields

8. **Given** the `core/bom_export.py` module
   **When** inspected
   **Then** it has zero GUI dependencies (no PySide6 imports, no imports from `gui/`)

## Tasks / Subtasks

- [x] Task 1: Extend `_group_components` to populate additional row fields (AC: #7)
  - [x] Add `"lcsc_part"` to row dict: `first.extra_fields.get("LCSC Part", "") or first.extra_fields.get("lcsc", "")`
  - [x] Add `"description"` to row dict: `first.extra_fields.get("description", "") or first.value`
  - [x] Add `"supplier_name"` to row dict: `first.extra_fields.get("supplier_name", "") or first.extra_fields.get("Supplier", "")`
  - [x] Add `"supplier_pn"` to row dict: `first.extra_fields.get("supplier_pn", "") or first.extra_fields.get("Supplier Part", "")`
  - [x] Existing fields (`item_number`, `designator`, `quantity`, `manufacturer`, `mpn`, `value`, `package`, `mount_type`, `notes`) remain unchanged — zero regression risk

- [x] Task 2: Define `JLCPCB_TEMPLATE` constant (AC: #1, #2)
  - [x] Add `JLCPCB_TEMPLATE = BOMTemplate(...)` after `PCBWAY_TEMPLATE`
  - [x] 4 columns matching the reference file exactly:
    - `BOMColumn(header="Comment", field="value")` — component value/description
    - `BOMColumn(header="Designator", field="designator")` — grouped refs
    - `BOMColumn(header="Footprint", field="package", transform="package_extract")` — standard package name
    - `BOMColumn(header="JLCPCB Part #", field="lcsc_part")` — LCSC number from extra_fields
  - [x] Set `file_format="csv"` (JLCPCB accepts CSV uploads)
  - [x] Keep `group_by="mpn"` and `dnp_handling="include_marked"` (same as PCBWay)

- [x] Task 3: Define `NEWBURY_TEMPLATE` constant (AC: #3)
  - [x] Add `NEWBURY_TEMPLATE = BOMTemplate(...)` after `JLCPCB_TEMPLATE`
  - [x] 9 columns matching the reference file:
    - `BOMColumn(header="Item#", field="item_number")`
    - `BOMColumn(header="Description", field="description")` — full description preferred over bare value
    - `BOMColumn(header="Quantity", field="quantity")`
    - `BOMColumn(header="Manufacturer Name", field="manufacturer")`
    - `BOMColumn(header="Manufacturer Part Number", field="mpn")`
    - `BOMColumn(header="Supplier Name", field="supplier_name")`
    - `BOMColumn(header="Supplier Part Number", field="supplier_pn")`
    - `BOMColumn(header="Designator", field="designator")`
    - `BOMColumn(header="Notes", field="notes")`
  - [x] Set `file_format="xlsx"` (Newbury expects Excel)

- [x] Task 4: Create `PRESET_TEMPLATES` list (AC: #4)
  - [x] Add `PRESET_TEMPLATES: list[BOMTemplate] = [PCBWAY_TEMPLATE, JLCPCB_TEMPLATE, NEWBURY_TEMPLATE]` after all template constants
  - [x] This list will be used by the export dialog (Story 2.4) for the template selector dropdown

- [x] Task 5: Write tests in `tests/core/test_bom_export.py` (AC: #1-#8)
  - [x] `TestJLCPCBTemplate.test_has_4_columns` — verify column count
  - [x] `TestJLCPCBTemplate.test_column_headers` — verify exact headers: Comment, Designator, Footprint, JLCPCB Part #
  - [x] `TestJLCPCBTemplate.test_file_format_csv` — default format is CSV
  - [x] `TestJLCPCBTemplate.test_export_with_lcsc_part` — component with `extra_fields={"LCSC Part": "C12345"}` produces correct JLCPCB Part # column
  - [x] `TestJLCPCBTemplate.test_export_without_lcsc_part` — component without LCSC field produces empty string in that column
  - [x] `TestNewburyTemplate.test_has_9_columns` — verify column count
  - [x] `TestNewburyTemplate.test_column_headers` — verify exact headers match reference
  - [x] `TestNewburyTemplate.test_file_format_xlsx` — default format is Excel
  - [x] `TestNewburyTemplate.test_export_with_supplier_fields` — component with supplier name/pn in extra_fields populates correctly
  - [x] `TestNewburyTemplate.test_description_field` — verify description populated from extra_fields or value fallback
  - [x] `TestPresetTemplates.test_preset_list_contains_all` — `PRESET_TEMPLATES` has 3 entries: PCBWay, JLCPCB, Newbury
  - [x] `TestPresetTemplates.test_preset_names` — names are "PCBWay", "JLCPCB", "Newbury Electronics"
  - [x] `TestCSVExportAllTemplates.test_jlcpcb_csv_output` — export JLCPCB template to CSV, verify headers and data
  - [x] `TestCSVExportAllTemplates.test_newbury_csv_output` — export Newbury template with `file_format="csv"` override, verify output
  - [x] Ensure existing 27 PCBWay tests still pass — zero regressions

- [x] Task 6: Run all tests and verify (AC: #8)
  - [x] Run full test suite: `python -m pytest tests/ -v`
  - [x] Verify zero regressions on existing 119 tests
  - [x] Verify all new tests pass
  - [x] Run import check: `python -c "from kipart_search.core.bom_export import JLCPCB_TEMPLATE, NEWBURY_TEMPLATE, PRESET_TEMPLATES"`

## Dev Notes

### Architecture Compliance

- **Core/GUI separation**: All changes are in `core/bom_export.py` — zero PySide6 imports. No imports from `gui/`.
- **ADR-02**: Templates are declarative dataclass constants. No Jinja2. No string templates.
- **Existing engine reuse**: The `export_bom()` function, `_group_components()`, `_write_xlsx()`, and `_write_csv()` from Story 2.1 are reused as-is. New templates just define different column layouts that read from the same row dict.

### JLCPCB Template Column Details (from Sample-BOM_JLCSMT.xlsx)

The JLCPCB reference file has 4 columns, header at row 1, data at row 2+:

| Col | Header | Maps to | Notes |
|-----|--------|---------|-------|
| A | Comment | `value` | Component value/description (100nF, 10K, etc.) |
| B | Designator | `designator` | Comma-separated grouped refs |
| C | Footprint | `package` (with `package_extract` transform) | Package name, not full KiCad footprint |
| D | JLCPCB Part # | `lcsc_part` | LCSC number (C12345), optional but usually filled |

**Note on the header**: The reference file has Unicode fullwidth parentheses in "JLCPCB Part #（optional）" — use the clean ASCII version "JLCPCB Part #" in the template header. JLCPCB's import system matches on column position, not exact header text.

**LCSC Part Number sourcing**: When a part is assigned from JLCPCB search results, the `PartResult.source_part_id` contains the LCSC number (e.g., "C12345"). The assign dialog writes this to KiCad's "LCSC Part" field via `extra_fields`. For the export, read from `extra_fields.get("LCSC Part", "")`. Also check `extra_fields.get("lcsc", "")` as a fallback alias.

### Newbury Electronics Template Column Details (from pcb-bom-sample-file-newbury-electronics.xlsx)

The Newbury reference file has 9 columns, header at row 1, data at row 2+:

| Col | Header | Maps to | Required per Newbury |
|-----|--------|---------|---------------------|
| A | Item# | `item_number` | Yes |
| B | Description | `description` | Compulsory |
| C | Quantity | `quantity` | Compulsory |
| D | Manufacturer Name | `manufacturer` | Compulsory |
| E | Manufacturer Part Number | `mpn` | Compulsory |
| F | Supplier Name | `supplier_name` | Optional (for costing) |
| G | Supplier Part Number | `supplier_pn` | Optional (for costing) |
| H | Designator | `designator` | Compulsory |
| I | Notes | `notes` | Optional |

**Description vs Value**: Newbury expects a full description (e.g., "CAP 1nF 16V 5% 0201 MLCC"). Use `extra_fields.get("description", "")` first; fall back to `comp.value` if description is empty. The `PartResult.description` field from JLCPCB search results is typically a full description string.

**Supplier fields**: Currently, the assign dialog writes MPN, Manufacturer, Datasheet, Description to KiCad fields (see `ASSIGNABLE_FIELDS` in `assign_dialog.py`). Supplier name and part number may be empty for most components today. The columns should still be present in the template — they'll be populated when Phase 2 adds DigiKey/Mouser adapters, or when users manually enter supplier info in KiCad fields.

### How `_group_components` Changes

The current `_group_components()` builds a row dict with these keys: `item_number`, `designator`, `quantity`, `manufacturer`, `mpn`, `value`, `package`, `mount_type`, `notes`.

Add these new keys to the same dict:
```python
"lcsc_part": first.extra_fields.get("LCSC Part", "") or first.extra_fields.get("lcsc", ""),
"description": first.extra_fields.get("description", "") or first.value,
"supplier_name": first.extra_fields.get("supplier_name", "") or first.extra_fields.get("Supplier", ""),
"supplier_pn": first.extra_fields.get("supplier_pn", "") or first.extra_fields.get("Supplier Part", ""),
```

This is additive — existing templates ignore keys they don't reference. The `_write_xlsx` and `_write_csv` functions already use `row_data.get(col.field, "")` which returns empty string for missing keys, so the PCBWay template continues to work identically.

### What This Story Does NOT Include

- **No GUI changes** — no export dialog, no toolbar wiring (Story 2.4)
- **No custom template JSON loading** — future story
- **No DNP filtering logic** — deferred to Story 2.4
- **No coverage validation / warning** — Story 2.4
- **No health summary bar** — Story 2.3
- **No changes to `assign_dialog.py`** — supplier fields will populate from future adapter work
- **No new dependencies** — uses existing `openpyxl` and stdlib `csv`

### Project Structure Notes

- Modified: `src/kipart_search/core/bom_export.py` (add JLCPCB_TEMPLATE, NEWBURY_TEMPLATE, PRESET_TEMPLATES; extend _group_components)
- Modified: `tests/core/test_bom_export.py` (add ~14 new tests)
- No new files created
- Alignment: follows existing pattern established by PCBWAY_TEMPLATE in Story 2.1

### Previous Story Intelligence (Story 2.1)

Key learnings:
- `BoardComponent.extra_fields` is a `dict[str, str]` populated by `kicad_bridge.py` from all KiCad component fields. Field name case varies — use `.get()` with known key names.
- The `_group_components` function uses `first = group[0]` to get representative data for grouped rows. This means all components in a group inherit the first component's extra_fields — acceptable since grouped components share the same MPN and should have the same metadata.
- `_write_xlsx` and `_write_csv` both use `row_data.get(col.field, "")` — templates with new field names work without changing the writer functions.
- The `transform` field on `BOMColumn` is currently unused by the writer code — transforms are pre-applied during `_group_components` (package and mount_type are computed there, not in the writer). The JLCPCB template's `package_extract` transform on Footprint column works the same way — `_group_components` already populates the `"package"` key with the extracted value.
- Story 2.1 added 27 tests, bringing total to 119. All passing as of last commit (`bc99fc5`).
- Commit pattern: one implementation commit, one code review fix commit per story.

### Git Intelligence

Recent commits:
```
bc99fc5 Code review fixes for Story 2.1: naming consistency and dead code removal
ae5ad62 Add BOM export engine with PCBWay template (Story 2.1)
```

Code review fixes for 2.1 included: renaming `_extract_ref_prefix` to `extract_ref_prefix` (public API), removing dead `_apply_transforms()` method, moving `_THT_LIBS`/`_SMD_LIBS` to module level.

### Testing Notes

- Add new test classes to existing `tests/core/test_bom_export.py` — don't create a new file
- Reuse the `_make_comp` helper and `three_components` fixture from Story 2.1
- For LCSC part testing, create components with `extra_fields={"LCSC Part": "C12345"}`
- For supplier testing, create components with `extra_fields={"supplier_name": "Farnell", "supplier_pn": "123-456"}`
- Use `tmp_path` fixture for all file outputs
- For CSV output verification: `csv.reader` to read back
- For Excel output verification: `openpyxl.load_workbook` to read back

### Anti-Patterns to Avoid

- Do NOT import PySide6 in `core/bom_export.py`
- Do NOT modify `_write_xlsx` or `_write_csv` — they already handle arbitrary column layouts via `row_data.get(col.field, "")`
- Do NOT change the PCBWAY_TEMPLATE — it's already working and tested
- Do NOT add cell formatting/styling to Excel output — plain data only
- Do NOT hardcode LCSC part number key as only "LCSC Part" — check fallback aliases
- Do NOT use the `transform` field to apply runtime transforms in the writer — transforms are pre-applied during grouping (the `"package"` row key already holds the extracted value)

### Cross-Story Dependencies

- **Story 2.1** (done): BOM export engine, BOMColumn/BOMTemplate dataclasses, PCBWAY_TEMPLATE, export_bom(), _group_components()
- **Story 2.3** (next): Health Summary Bar — independent of templates
- **Story 2.4** (future): Export Dialog — will use `PRESET_TEMPLATES` list for the template selector dropdown

### References

- [Source: _bmad-output/planning-artifacts/epics.md — Epic 2, Story 2.2]
- [Source: _bmad-output/planning-artifacts/architecture.md — ADR-02: BOM Export Template Engine]
- [Source: _bmad-output/planning-artifacts/ux-design-specification.md — BOM Export Window, Template Selection, UX-DR6]
- [Source: _bmad-output/planning-artifacts/prd.md — FR24-FR29: BOM Export requirements]
- [Source: _bmad-output/project-context.md — Core/GUI separation, naming conventions]
- [Source: ExistingWorksOn/Sample-BOM_JLCSMT.xlsx — JLCPCB column format reference]
- [Source: ExistingWorksOn/pcb-bom-sample-file-newbury-electronics.xlsx — Newbury column format reference]
- [Source: src/kipart_search/core/bom_export.py — existing PCBWAY_TEMPLATE, _group_components, export_bom]
- [Source: src/kipart_search/core/models.py — BoardComponent.extra_fields, PartResult.source_part_id]
- [Source: src/kipart_search/gui/assign_dialog.py — ASSIGNABLE_FIELDS, field write-back flow]
- [Source: _bmad-output/implementation-artifacts/2-1-bom-export-engine-with-pcbway-template.md — Previous story intelligence]

## Dev Agent Record

### Agent Model Used

Claude Opus 4.6 (1M context)

### Debug Log References

No issues encountered — clean implementation.

### Completion Notes List

- Extended `_group_components` with 4 new row fields: `lcsc_part`, `description`, `supplier_name`, `supplier_pn` — all additive, zero regression risk
- Defined `JLCPCB_TEMPLATE` with 4 columns (Comment, Designator, Footprint, JLCPCB Part #), CSV format
- Defined `NEWBURY_TEMPLATE` with 9 columns matching reference file, XLSX format
- Created `PRESET_TEMPLATES` list with all 3 templates in order
- Added 14 new tests across 4 test classes: TestJLCPCBTemplate (5), TestNewburyTemplate (5), TestPresetTemplates (2), TestCSVExportAllTemplates (2)
- All 133 tests pass (119 existing + 14 new), zero regressions
- Import check verified: `JLCPCB_TEMPLATE`, `NEWBURY_TEMPLATE`, `PRESET_TEMPLATES` all importable
- Zero GUI dependencies confirmed — no PySide6 imports in `core/bom_export.py`

### Change Log

- 2026-03-18: Story 2.2 implementation — added JLCPCB and Newbury Electronics preset templates, extended _group_components with extra_fields support, added 14 tests

### File List

- Modified: `src/kipart_search/core/bom_export.py`
- Modified: `tests/core/test_bom_export.py`
- Modified: `_bmad-output/implementation-artifacts/sprint-status.yaml`
