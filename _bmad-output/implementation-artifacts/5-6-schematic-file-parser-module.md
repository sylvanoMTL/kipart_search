# Story 5.6: Schematic File Parser Module

Status: done

## Story

As a designer,
I want KiPart Search to read and write fields in my `.kicad_sch` files,
So that MPN assignments persist in my KiCad project files.

## Acceptance Criteria

1. **Given** a `.kicad_sch` file with symbol blocks containing `(property ...)` entries
   **When** `read_symbols(sch_path)` is called
   **Then** it returns a list of symbols with all their properties (Reference, Value, Footprint, MPN, Manufacturer, etc.)
   **And** the parser handles nested S-expressions correctly (depth-counting, not regex)

2. **Given** a symbol identified by reference designator (e.g. "C12")
   **When** `set_field(sch_path, reference, field_name, value)` is called with a field that doesn't exist
   **Then** a new `(property ...)` entry is inserted into the symbol block with the correct format
   **And** the field is hidden by default (`(effects (font (size 1.27 1.27)) hide)`)
   **And** the rest of the file is preserved byte-for-byte (no reformatting)

3. **Given** a symbol with an existing field
   **When** `set_field()` is called with `allow_overwrite=False` (default)
   **Then** the field is NOT modified and the method returns False
   **And** with `allow_overwrite=True`, the field value is updated in-place

4. **Given** a KiCad project directory
   **When** `find_schematic_files(project_dir)` is called
   **Then** it discovers the root `.kicad_sch` and all sub-sheets referenced via `(sheet ...)` blocks
   **And** `find_symbol_sheet(project_dir, reference)` returns the path to the sheet containing the given reference

## Tasks / Subtasks

- [x] Task 1: S-expression depth-counting parser (AC: #1)
  - [x] 1.1 Implement `_find_block(text, start_pos)` — from an opening `(` at `start_pos`, find the matching `)` using depth counting. Returns `(start, end)` slice. This is the core primitive used by all other functions.
  - [x] 1.2 Implement `read_symbols(sch_path)` — scan file for `(symbol (lib_id ...))` blocks (skip the `(lib_symbols ...)` section), extract all `(property "Name" "Value" ...)` pairs per symbol. Return list of dicts or dataclass with `lib_id`, `reference`, `value`, `footprint`, `fields` (dict of all properties).
  - [x] 1.3 Handle edge cases: symbols with no custom fields, symbols with `(property "ki_keywords" ...)` metadata entries, nested `(symbol ...)` inside `(lib_symbols ...)` that must be skipped.

- [x] Task 2: Field write — add and update (AC: #2, #3)
  - [x] 2.1 Implement `set_field(sch_path, reference, field_name, value, allow_overwrite=False)` — locate symbol by Reference property, then:
    - If field exists and `allow_overwrite=False`: return `False`, no modification
    - If field exists and `allow_overwrite=True`: replace the value string in-place (preserve all other attributes like `id`, `at`, `effects`)
    - If field does not exist: insert a new `(property ...)` line before the first `(pin ...)` or closing `)` of the symbol block
  - [x] 2.2 New property format: `(property "{field_name}" "{value}" (at {x} {y} 0) (effects (font (size 1.27 1.27)) hide))` — copy `(at ...)` coordinates from the symbol's own `(at ...)` for positioning. Use next available `(id N)` or omit if KiCad file version >= 20231120 (KiCad 8+ dropped mandatory IDs on properties).
  - [x] 2.3 Byte-for-byte preservation: file content outside the modified symbol block must not change. No trailing newline additions, no whitespace normalization, no re-indentation.

- [x] Task 3: Sub-sheet discovery (AC: #4)
  - [x] 3.1 Implement `find_schematic_files(project_dir)` — find the root `.kicad_sch` (same name as `.kicad_pro`), then recursively scan for `(sheet ... (property "Sheetfile" "subsheet.kicad_sch") ...)` blocks to discover all sub-sheets.
  - [x] 3.2 Implement `find_symbol_sheet(project_dir, reference)` — iterate over all discovered sheets, call `read_symbols()` on each, return the path of the sheet containing the symbol with the given reference.

- [x] Task 4: Manual testing
  - [x] 4.1 Test with a real `.kicad_sch` file: read symbols, add a new MPN field, verify the file opens correctly in KiCad after modification.
  - [x] 4.2 Test with a hierarchical project (root + sub-sheets): verify `find_schematic_files()` discovers all sheets and `find_symbol_sheet()` resolves references correctly.

## Dev Notes

### Architecture & Location

- **New file:** `src/kipart_search/core/kicad_sch.py`
- **Zero GUI dependencies** — this is a `core/` module. No PySide6, no Qt imports. Stdlib only (`pathlib`, `re`, `logging`, `dataclasses`).
- This module is the ONLY place `.kicad_sch` file modification is allowed. See project-context.md critical rule: "Only modify `.kicad_sch` files via the `core/kicad_sch.py` module."
- Story 5.7 will wire this module into `gui/kicad_bridge.py` and `gui/main_window.py`. This story is purely the core parser — no GUI integration.

### KiCad `.kicad_sch` File Format Reference

The file is a plain-text S-expression. Key structure:

```
(kicad_sch (version YYYYMMDD) (generator "eeschema") ...
  (lib_symbols
    (symbol "Device:R" ...)    <-- LIBRARY definitions, SKIP these
    ...
  )
  (symbol (lib_id "Device:R") (at 123.19 57.15 0)
    (uuid ...)
    (property "Reference" "R1" (id 0) (at 125.73 55.88 0)
      (effects (font (size 1.27 1.27)) (justify left)))
    (property "Value" "1K" (id 1) ...)
    (property "Footprint" "Resistor_SMD:R_0402" (id 2) ...)
    (property "Datasheet" "~" (id 3) ...)
    (property "MPN" "RC0402FR-071KL" (id 4) ...)   <-- custom field
    (pin "1" (uuid ...))
    (pin "2" (uuid ...))
  )
  (sheet (at ...) (size ...)
    (property "Sheetname" "Power" ...)
    (property "Sheetfile" "power.kicad_sch" ...)
    ...
  )
)
```

**Critical parsing rules:**
- `(symbol ...)` blocks at root level = placed component instances. These have `(lib_id ...)`.
- `(symbol ...)` blocks inside `(lib_symbols ...)` = library definitions. **MUST SKIP** these.
- The `(lib_symbols ...)` block is a single top-level entry. Use depth-counting to find its end and exclude it from symbol scanning.
- Reference designator is in `(property "Reference" "C12" ...)`.
- Sub-sheets are `(sheet ...)` blocks with `(property "Sheetfile" "name.kicad_sch" ...)`.
- Property IDs (`(id N)`) are optional in KiCad 8+. Do not assume they exist. When adding a new property, include `(id N)` only if the file's other properties use them.

### Parser Strategy — Depth-Counting, Not Regex

The sprint change proposal and architecture ADR-08 both mandate a **depth-counting parser**, not regex for block extraction. The reason: S-expressions can nest arbitrarily deep. Regex fails on edge cases like string values containing parentheses.

**Core algorithm for `_find_block()`:**
1. Start at an opening `(`
2. Increment depth on `(`, decrement on `)`
3. Skip characters inside quoted strings (`"..."`) — parentheses inside strings don't count
4. When depth returns to 0, you've found the matching `)`
5. Return the slice indices

**Use regex only for**: extracting property name/value pairs from within an already-isolated block (where the structure is flat and predictable).

### Field Insertion Format

When inserting a new property, use this template:
```
    (property "{name}" "{value}" (at {x} {y} 0)
      (effects (font (size 1.27 1.27)) hide))
```

- Copy the `(at x y angle)` from the parent symbol's `(at ...)` for default positioning
- `hide` makes the field invisible on the schematic (standard for MPN, Manufacturer, etc.)
- Insert before the first `(pin ...)` line or before the symbol's closing `)`, whichever comes first
- Match the indentation of surrounding property lines (typically 4 spaces)

### Existing Code Patterns to Follow

- **`from __future__ import annotations`** at top of file
- **`logging.getLogger(__name__)`** at module level
- **`pathlib.Path`** for all file operations
- **`@dataclass`** for return types (e.g., a `SchSymbol` dataclass)
- **Type hints** with `X | Y` union syntax
- **Function signatures** should accept `Path | str` for file paths and convert internally

### What NOT to Do

- Do NOT import PySide6 or any GUI library
- Do NOT use `kicad-skip` or any external S-expression library — bespoke parser only (~200-300 lines)
- Do NOT use regex to find matching parentheses — use depth-counting with string-quoting awareness
- Do NOT modify `.kicad_pcb` files — this module is `.kicad_sch` only
- Do NOT add write-back GUI integration — that's Story 5.7
- Do NOT normalize or reformat file whitespace — preserve original formatting exactly

### Previous Story Intelligence (Story 5.5)

**Relevant learnings from Story 5.5 (Backup System & Undo Log):**
- `BackupManager` in `core/backup.py` stores backups at `~/.kipart-search/backups/{project}/{YYYY-MM-DD_HHMM}/`
- Undo log is a CSV with columns: timestamp, reference, field, old_value, new_value
- Zero GUI dependencies in core module — same pattern applies here
- `core/backup.py` currently backs up `components.json` (in-memory state). Story 5.7 will extend it to back up `.kicad_sch` files before modification.
- The `BackupManager.reset_session()` pattern is called from `_on_scan_complete()` — session lifecycle is GUI-managed.

**Files created in Story 5.5:** `core/backup.py`, `gui/backup_dialog.py`, `tests/core/test_backup.py`, `tests/gui/test_backup_dialog.py`

### Git Intelligence

Recent commits show the IPC write-back was disabled (commit 4677e57) because `board.update_items()` destroys custom fields in KiCad 9. This is the direct motivation for this story — file-based `.kicad_sch` modification is the only viable write path.

The codebase currently has 417 tests. New tests for this module should follow the existing pattern in `tests/core/`.

### Project Structure Notes

- New file goes at: `src/kipart_search/core/kicad_sch.py`
- Test file goes at: `tests/core/test_kicad_sch.py` (if automated tests are added)
- Manual test artifacts (sample `.kicad_sch` files) can go in `tests/manual_tests/`
- No conflicts with existing structure. No existing `kicad_sch.py` file.

### References

- [Source: _bmad-output/planning-artifacts/architecture.md — ADR-08: Write-Back Strategy]
- [Source: _bmad-output/planning-artifacts/epics.md — Epic 5, Story 5.6]
- [Source: _bmad-output/planning-artifacts/sprint-change-proposal-2026-03-21.md — Section 4]
- [Source: ExistingWorksOn/kicad_api_symbol_fields.md — Workaround 1, parser sketch]
- [Source: _bmad-output/project-context.md — Critical rules for .kicad_sch modification]
- [Source: src/kipart_search/core/backup.py — BackupManager patterns]
- [Source: src/kipart_search/core/models.py — MPN_FIELD_NAMES, BoardComponent]

## Dev Agent Record

### Agent Model Used
Claude Opus 4.6 (1M context)

### Debug Log References
- None — clean implementation, no debug issues.

### Completion Notes List
- Implemented `_find_block()` depth-counting S-expression parser with string-quoting awareness (handles escaped quotes, parens inside strings)
- Implemented `read_symbols()` that correctly skips `(lib_symbols ...)` section and extracts all placed symbol instances with their properties, UUIDs, and positions
- Implemented `set_field()` with add-new / overwrite / no-overwrite-by-default modes; preserves file content outside modified symbol block; auto-detects property ID usage and indentation
- Implemented `find_schematic_files()` with BFS sub-sheet discovery via `(sheet ...)` blocks
- Implemented `find_symbol_sheet()` to locate which sheet contains a given reference designator
- Created `SchSymbol` dataclass for return type (lib_id, reference, value, footprint, fields dict, uuid, position)
- 22 automated tests: 4 for `_find_block`, 5 for `read_symbols`, 6 for `set_field`, 3 for `find_schematic_files`, 3 for `find_symbol_sheet`, 2 for `is_schematic_locked` — all pass
- Manual integration test with realistic KiCad 9 sample files (root + sub-sheet hierarchy) — all operations verified
- Manual test on real KiCad 9 project (81 symbols): read, add MPN, overwrite, no-overwrite, lock detection — all verified by user
- Added `is_schematic_locked()` to detect KiCad lock files (`~filename.kicad_sch.lck`) and prevent writes while schematic is open
- Core tests: 154 passed, 0 failed (no regressions). Pre-existing GUI test failures (8) from disabled IPC write-back (commit 4677e57) are unrelated.

### Change Log
- 2026-03-21: Implemented Story 5.6 — `core/kicad_sch.py` S-expression parser with depth-counting, field read/write, sub-sheet discovery, lock detection. 22 new tests added. Manual validation on real KiCad 9 project (81 symbols) passed.
- 2026-03-22: Code review fixes — Fixed regex patterns (`_PROPERTY_RE`, `set_field` field_pattern, `_find_symbol_block` ref_pattern) to handle escaped quotes in property values. Hardened `_find_insertion_point()` for compact/single-line symbol blocks. 2 new edge-case tests added (24 total).
- 2026-03-22: Code review #2 — Added `_escape_sexpr_string()` to escape `"` and `\` in values written by `set_field()` (both insert and overwrite paths). Manual test tool now uses `is_schematic_locked()` instead of duplicating logic. Fixed `NameError` on `lock_file` reference left behind by the refactor. Removed unused `_escape_sexpr_string` import from tests. 2 new tests added (26 total).
- 2026-03-22: Code review #3 — Fixed `_SHEETFILE_RE` to handle escaped quotes in sheet filenames (was using `[^"]+`, now matches `_PROPERTY_RE` pattern). Escaped `field_name` in `set_field()` insert path. Replaced `list.pop(0)` with `deque.popleft()` in BFS. Added clarifying comment for `_AT_RE` position assumption.

### File List
- `src/kipart_search/core/kicad_sch.py` — NEW: KiCad schematic file parser and field writer
- `tests/core/test_kicad_sch.py` — NEW: 26 automated tests for kicad_sch module
- `tests/manual_tests/sample_project/sample.kicad_pro` — NEW: sample KiCad project file for manual testing
- `tests/manual_tests/sample_project/sample.kicad_sch` — NEW: sample root schematic with R1, R2, C1 + sub-sheet reference
- `tests/manual_tests/sample_project/power.kicad_sch` — NEW: sample sub-sheet with C10, C11
- `tests/manual_tests/test_parser_manual.py` — NEW: GUI manual test tool with folder picker, symbol table, MPN editing, lock detection
