# Sprint Change Proposal — 2026-03-21

## Section 1: Issue Summary

**Problem:** MPN assignments made in KiPart Search do not persist back to the KiCad project files. All write-back via the IPC API was disabled (sprint change proposal 2026-03-20) because `board.update_items()` destroys custom fields in KiCad 9. Assignments exist only in local memory — they are lost when the application closes and must be re-done next session.

**Discovered:** Investigation into alternative write paths (documented in `ExistingWorksOn/kicad_api_symbol_fields.md`) revealed that KiCad `.kicad_sch` schematic files are plain-text S-expressions that can be directly parsed and modified by an external tool. This is a viable write-back path that bypasses the broken IPC API entirely.

**Category:** Failed approach (IPC API) requiring a different solution (direct file modification).

**Evidence:**
- `.kicad_sch` file format is stable, well-documented S-expressions with `(property ...)` entries per symbol
- The investigation document provides a working parser sketch and references `kicad-skip`, a third-party library that proves the approach
- The current local-only workflow has a real gap: assignments don't persist across sessions, meaning the KiCad project never carries the enriched data
- FR13 ("write back MPN, manufacturer, description fields to a KiCad component") is listed as delivered but is not actually functional
- The backup system (Story 5.5) and undo log are already built — they just need a working write path behind them

---

## Section 2: Impact Analysis

### Epic Impact

**Epic 5 (Safe KiCad Write-Back & Assignment):** Currently marked "done" with write-back disabled. Two new stories are needed to deliver file-based write-back. No other epics are affected.

### Story Impact

| Story | Current Status | Change Needed |
|-------|---------------|---------------|
| 5.4 (Write-Back Safety Guards) | done (disabled) | No change — guards are preserved and will protect the new write path |
| 5.5 (Backup System & Undo Log) | done | Minor extension — include `.kicad_sch` files in pre-write backups |
| **5.6 (NEW)** | — | Schematic file parser module (`core/kicad_sch.py`) |
| **5.7 (NEW)** | — | File-based write-back via "Push to KiCad" button |

### Artifact Conflicts

| Artifact | Conflict | Resolution |
|----------|----------|------------|
| **project-context.md** critical rule | "NEVER directly modify .kicad_sch or .kicad_pcb files" | Revise: allow `.kicad_sch` modification via `core/kicad_sch.py` only; `.kicad_pcb` rule unchanged |
| **ADR-08** (Write-Back Strategy) | "Defer write-back to Phase 2 (wait for KiCad 10)" | Revise: file-based `.kicad_sch` write-back in Phase 1; IPC-based write-back deferred to KiCad 10 |
| **PRD FR13** | Listed as delivered but not functional | No text change needed — implementation will deliver it for real |
| **UX spec** | "Push to KiCad" button described but currently info-only | No text change needed — implementation matches existing spec |

### Technical Impact

- New module: `src/kipart_search/core/kicad_sch.py` (~200-300 lines)
- Modified: `gui/kicad_bridge.py` (add file-based write path as fallback)
- Modified: `gui/main_window.py` ("Push to KiCad" button wired to real functionality)
- Modified: `core/backup.py` (include `.kicad_sch` files in backup scope)
- New test: `tests/manual_tests/test_sch_write.py`
- No new dependencies — bespoke S-expression parser, no `kicad-skip`

---

## Section 3: Recommended Approach

**Selected: Direct Adjustment — add file-based `.kicad_sch` write-back to Phase 1**

### Rationale

1. **The workflow gap is real.** Without persisting assignments to `.kicad_sch`, every session starts from scratch. The tool enriches component data but it evaporates when you close the app. The KiCad project remains the incomplete source of truth.

2. **The safety infrastructure is already built.** Story 5.5 (backup system + undo log) was designed specifically for write-back protection. It just needs a working write path behind it.

3. **The file format is stable and simple.** `.kicad_sch` is a text S-expression format that hasn't changed significantly between KiCad 7-9. This is documented plaintext, not fragile reverse-engineering.

4. **It makes "Push to KiCad" real.** The button, dialog, backup system, and undo log all exist. Only the actual write is missing.

5. **Bespoke parser over external dependency.** The scope of what KiPart Search needs is narrow: read fields by reference, write/add fields by reference, discover sub-sheets. A focused ~200-line module is sufficient. `kicad-skip` adds an external dependency with uncertain maintenance for minimal gain.

### Effort & Risk

| Factor | Assessment |
|--------|-----------|
| Effort | **Medium** — 2 new stories, ~1 week implementation |
| Risk | **Medium** — writing to user design files requires careful safety engineering |
| Timeline impact | Extends Phase 1 by ~1 week |
| Mitigation | Backup system already built; add-never-overwrite policy; KiCad-open detection |

### Alternatives Considered

| Option | Verdict | Reason |
|--------|---------|--------|
| Defer to KiCad 10 (status quo) | Rejected | Leaves a real workflow gap; KiCad 10 timeline uncertain |
| Use `kicad-skip` library | Rejected | External dependency; narrow use case doesn't justify it |
| Regex-based parser | Rejected | Fragile for nested S-expressions; proper depth-counting parser is safer |

---

## Section 4: Detailed Change Proposals

### New Story 5.6: Schematic File Parser Module

**File:** `src/kipart_search/core/kicad_sch.py` (new)

As a designer,
I want KiPart Search to read and write fields in my `.kicad_sch` files,
So that MPN assignments persist in my KiCad project files.

**Acceptance Criteria:**

**Given** a `.kicad_sch` file with symbol blocks containing `(property ...)` entries
**When** `read_symbols(sch_path)` is called
**Then** it returns a list of symbols with all their properties (Reference, Value, Footprint, MPN, Manufacturer, etc.)
**And** the parser handles nested S-expressions correctly (depth-counting, not regex)

**Given** a symbol identified by reference designator (e.g. "C12")
**When** `set_field(sch_path, reference, field_name, value)` is called with a field that doesn't exist
**Then** a new `(property ...)` entry is inserted into the symbol block with the correct format
**And** the field is hidden by default (`(effects (font (size 1.27 1.27)) hide)`)
**And** the rest of the file is preserved byte-for-byte (no reformatting)

**Given** a symbol with an existing field
**When** `set_field()` is called with `allow_overwrite=False` (default)
**Then** the field is NOT modified and the method returns False
**And** with `allow_overwrite=True`, the field value is updated in-place

**Given** a KiCad project directory
**When** `find_schematic_files(project_dir)` is called
**Then** it discovers the root `.kicad_sch` and all sub-sheets referenced via `(sheet ...)` blocks
**And** `find_symbol_sheet(project_dir, reference)` returns the path to the sheet containing the given reference

**Technical constraints:**
- Zero GUI dependencies — lives in `core/`
- Proper S-expression depth-counting parser (not regex for block extraction)
- Preserves file formatting, comments, and whitespace outside modified blocks
- UTF-8 encoding throughout
- Uses `pathlib.Path` for all file operations

---

### New Story 5.7: File-Based Write-Back via Push to KiCad

**File:** `gui/kicad_bridge.py`, `gui/main_window.py` (modified)

As a designer,
I want to push my MPN assignments from KiPart Search into my KiCad schematic files,
So that my KiCad project carries all manufacturing references and future BOM exports from KiCad are already complete.

**Acceptance Criteria:**

**Given** the designer has made local MPN assignments (`_local_assignments` is non-empty)
**When** they click "Push to KiCad"
**Then** the system checks if KiCad's eeschema process has the schematic files open

**Given** the schematic files are open in KiCad
**When** the open-file check detects this
**Then** the system shows a warning: "Close the schematic editor in KiCad before pushing changes. File-based write cannot proceed while the schematic is open."
**And** the write is blocked — no file modification occurs

**Given** the schematic files are NOT open in KiCad (or KiCad is not running)
**When** the designer confirms the push
**Then** all `.kicad_sch` files in the project are backed up to `~/.kipart-search/backups/{project}/{YYYY-MM-DD_HHMM}/` (extends Story 5.5)
**And** each local assignment is written to the correct schematic file via `core/kicad_sch.py`
**And** each write is logged to the undo CSV (timestamp, reference, field, old value, new value)
**And** the add-never-overwrite policy is enforced (non-empty fields are not modified without explicit confirmation)

**Given** the push completes successfully
**When** the success dialog is shown
**Then** it displays: "Written N fields to M components in [project]. Run 'Update PCB from Schematic' (F8) in KiCad to sync the board."
**And** `_local_assignments` is cleared for the successfully written fields
**And** the log panel records: "Pushed N field(s) to .kicad_sch — run Update PCB from Schematic to sync"

**Given** a write fails for any component
**When** the error is caught
**Then** the system continues writing remaining components (non-atomic across components, atomic per component)
**And** failed writes remain in `_local_assignments` for retry
**And** the error is logged with the specific component reference and reason

**Safety constraints:**
- KiCad-open detection is mandatory — refuse to write if schematic is open
- Backup is mandatory — no writes without a successful backup first
- Add-never-overwrite is the default — matches existing UX-DR17 spec
- Undo log records every change for auditability

---

### ADR-08 Update

**File:** `_bmad-output/planning-artifacts/architecture.md`

```
OLD:
ADR-08: Write-Back Strategy — Investigate existing kicad_bridge.py capabilities first.
If field write-back works in kicad-python v0.6.0, use it.
If not, defer to Phase 2.

NEW:
ADR-08: Write-Back Strategy — Dual-path approach.
- Path A (KiCad 9): File-based write-back via direct .kicad_sch modification.
  Schematic files are plain-text S-expressions; a bespoke parser in core/kicad_sch.py
  reads/writes symbol properties. Requires schematic to be closed in KiCad.
  Backup mandatory before every write session.
- Path B (KiCad 10+): IPC-based write-back via schematic editor API (when available).
  Original write logic preserved in kicad_bridge.py comments for re-enablement.
- Safety: add-never-overwrite, backup before write, undo log, KiCad-open detection.
```

### project-context.md Update

```
OLD:
- **NEVER** directly modify .kicad_sch or .kicad_pcb files — always use IPC API via kicad_bridge.py

NEW:
- **NEVER** directly modify .kicad_pcb files — always use IPC API via kicad_bridge.py
- Only modify .kicad_sch files via the `core/kicad_sch.py` module — never raw string
  manipulation elsewhere. File-based writes require: schematic closed in KiCad,
  backup completed, add-never-overwrite policy enforced.
```

---

## Section 5: Implementation Handoff

### Change Scope: Minor-to-Moderate

- **2 new stories** added to Epic 5
- **2 artifact updates** (ADR-08, project-context.md)
- No PRD changes needed (FR13 already specified)
- No UX spec changes needed ("Push to KiCad" and backup system already designed)

### Implementation Order

1. **Story 5.6** first — the core parser module with no GUI dependencies. Can be tested independently.
2. **Story 5.7** second — wires the parser into the GUI workflow. Depends on 5.6.

### Handoff

- **Route to:** Development team (solo developer) for direct implementation
- **Deliverables:** Two story files in `implementation-artifacts/`, updated architecture and project-context
- **Success criteria:**
  - MPN assignments persist in `.kicad_sch` files after "Push to KiCad"
  - KiCad "Update PCB from Schematic" picks up the new fields
  - Backup created before every write session
  - No writes when schematic is open in KiCad
  - Undo log records all changes

---

## Approval

**Status:** Awaiting user approval

**Date:** 2026-03-21
**Author:** Claude (Scrum Master agent)
**Triggered by:** Investigation of `.kicad_sch` direct write path as alternative to disabled IPC write-back
