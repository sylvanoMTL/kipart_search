# Sprint Change Proposal — 2026-03-22

## Section 1: Issue Summary

**Problem:** The board scan reads component data exclusively from the PCB via the KiCad IPC API (`board.get_footprints()`). This has two gaps:

1. **Field desync:** After Story 5.7 pushes MPN assignments to `.kicad_sch` files, a re-scan reads stale PCB data — showing missing/red statuses for fields the user just pushed. The schematic has the correct data, but the PCB won't reflect it until the user runs "Update PCB from Schematic" (F8).

2. **Invisible components:** Components that exist in the schematic but haven't been placed on the PCB yet are completely invisible to the scan. The verification dashboard gives a false sense of completeness — the user doesn't know 30 more components exist in the schematic.

**Discovered:** During implementation of Story 5.7 (file-based write-back). The schematic parser (`core/kicad_sch.py`) from Story 5.6 already has full read access to `.kicad_sch` files — but this capability is only used for writing, never for reading during scan.

**Category:** Gap discovered during implementation — the scan assumes PCB is the source of truth, but the schematic is always more authoritative and more up-to-date.

**Evidence:**
- `kicad_bridge.get_components()` reads only from IPC API (`board.get_footprints()`) — PCB footprints only
- `kicad_sch.read_symbols()` can read all properties from `.kicad_sch` files but is never called during scan
- KiCad 9 IPC API only supports PCB editor — no schematic API until KiCad 10
- After `_on_push_to_kicad()` writes to schematic, the success dialog tells the user to run F8, but a re-scan before F8 shows stale data with no warning
- No comparison or merge logic exists between PCB and schematic data

---

## Section 2: Impact Analysis

### Epic Impact

**Epic 5 (Safe KiCad Write-Back & Assignment):** Currently marked "done" with Stories 5.1–5.7 complete. One new story (5.8) is needed for dual-source scanning. No other epics are affected.

### Story Impact

| Story | Current Status | Change Needed |
|-------|---------------|---------------|
| 5.1 (KiCad Connection and Board Scan) | done | No change — PCB scan path unchanged |
| 5.6 (Schematic File Parser Module) | done | No change — `read_symbols()` already provides full read access |
| 5.7 (File-Based Write-Back) | done | No change — write path unchanged |
| **5.8 (NEW)** | — | Dual-source scan: merge schematic + PCB data, detect desync and unplaced components |

### Artifact Conflicts

| Artifact | Conflict | Resolution |
|----------|----------|------------|
| **Epics (epics.md)** | Epic 5 has no Story 5.8 | Add Story 5.8 definition |
| **sprint-status.yaml** | Epic 5 marked done, no 5.8 entry | Reopen Epic 5 to in-progress, add 5.8 as backlog |
| **PRD** | No conflict — FR11/FR17 don't specify data source | No change needed |
| **Architecture** | Scan workflow is PCB-only | Minor: document dual-source scan flow (can be done in story implementation) |
| **UX spec** | No "Not on PCB" or "PCB out of sync" status states | Minor: new status indicators fit within existing UX-DR15/UX-DR16 patterns |
| **project-context.md** | No conflict — `core/kicad_sch.py` already an allowed read path | No change needed |

### Technical Impact

- New or modified: `core/` merge logic function (e.g., `merge_pcb_sch()`)
- New or extended: `BoardComponent` or new `MergedComponent` dataclass with `source` flag and `sync_mismatches`
- Modified: `ScanWorker` in `gui/main_window.py` to read schematic files alongside PCB scan
- Modified: `gui/verify_panel.py` for new status indicators ("Not on PCB", "PCB out of sync")
- New test: comparison/merge logic tests

---

## Section 3: Recommended Approach

**Selected path: Direct Adjustment (Option 1)**

Add Story 5.8 to Epic 5. No rollback, no MVP scope change.

**Rationale:**
- **Low effort:** `read_symbols()` and `find_schematic_files()` already exist from Story 5.6. The new work is merge logic and UI status indicators.
- **Low risk:** Read-only schematic access. No file writes. Graceful degradation if schematic files aren't found.
- **High value:** Fixes two real gaps — stale PCB data after Push to KiCad, and invisible unplaced components. Prevents user confusion and duplicate work.
- **No dependencies:** Builds entirely on completed Stories 5.1, 5.6, and 5.7.
- **Timeline:** One story, self-contained.

**Trade-offs considered:**
- Could wait for KiCad 10's schematic IPC API — but that's 12+ months away and the file parser already works.
- Could make this a separate epic — but it fits naturally within Epic 5 ("Safe KiCad Write-Back & Assignment") since it completes the scan/write cycle.

---

## Section 4: Detailed Change Proposals

### 4.1 — New Story in epics.md

**Location:** After Story 5.7, before Epic 6

```markdown
### Story 5.8: Dual-Source Scan (Schematic + PCB)

As a designer,
I want the scan to read component data from both my `.kicad_sch` schematic files and the PCB via IPC API,
So that I see all components (including unplaced ones), get the most up-to-date field values, and get warned when the PCB is out of sync with the schematic.

**Acceptance Criteria:**

**Given** the app is connected to KiCad and a board scan is initiated
**When** the scan reads components from the PCB via IPC API
**Then** the system also reads symbol properties from all `.kicad_sch` files in the project directory via `core/kicad_sch.py`
**And** for each component, the scan merges data from both sources: schematic fields take priority over PCB fields for MPN, Manufacturer, and other custom properties (schematic is the source of truth)

**Given** a component exists in the schematic but has no footprint placed on the PCB
**When** the verification dashboard displays results
**Then** that component appears in the table with a distinct "Not on PCB" status indicator
**And** click-to-highlight is unavailable for that component (no footprint to select)
**And** the health summary bar counts these components under "Needs attention"
**And** the log panel reports: "N component(s) found in schematic but not placed on PCB"

**Given** a component's schematic symbol has field values (e.g. MPN) that differ from the PCB footprint fields
**When** the verification dashboard displays results
**Then** that component shows an amber "PCB out of sync" indicator
**And** a tooltip or detail text reads: "Schematic has MPN '[value]' but PCB does not — run Update PCB from Schematic (F8) in KiCad"

**Given** one or more components are detected as out of sync or not on PCB
**When** the scan completes
**Then** a banner or log message warns: "N component(s) need attention — run Update PCB from Schematic (F8) in KiCad, then re-scan."

**Given** all components have matching fields between PCB and schematic and all are placed
**When** the scan completes
**Then** no sync warning is shown — the scan proceeds as normal

**Given** the app cannot locate the `.kicad_sch` project files (e.g. standalone mode, project directory not resolvable)
**When** the scan runs
**Then** schematic reading is silently skipped — the scan works exactly as before (PCB-only)
**And** no error is shown (graceful degradation)

**Technical constraints:**
- Merge logic lives in `core/` (zero GUI dependencies) — e.g. `merge_pcb_sch(pcb_components: list[BoardComponent], sch_symbols: list[SchSymbol]) -> list[MergedComponent]`
- A new `MergedComponent` dataclass or extended `BoardComponent` carries a `source` flag indicating: `both`, `pcb_only`, `sch_only`, and a `sync_mismatches: list[str]` for differing fields
- Schematic file discovery reuses `kicad_sch.find_schematic_files()` and `read_symbols()`
- The scan worker thread handles schematic reads in background (no GUI blocking)
- Schematic lock files do NOT prevent read access — only writes are blocked by locks
- This is read-only — no `.kicad_sch` file modification occurs
```

### 4.2 — sprint-status.yaml update

```
OLD:
  epic-5: in-progress  # reopened: stories 5.6, 5.7 added for file-based .kicad_sch write-back
  ...
  5-7-file-based-write-back-push-to-kicad: done

NEW:
  epic-5: in-progress  # reopened: stories 5.6, 5.7, 5.8 added
  ...
  5-7-file-based-write-back-push-to-kicad: done
  5-8-dual-source-scan-schematic-pcb: backlog  # Merge schematic + PCB data during scan
```

---

## Section 5: Implementation Handoff

**Change scope: Minor** — Direct implementation by development team.

**Handoff:**
- **Dev agent:** Implement Story 5.8 (merge logic in `core/`, scan worker changes in `gui/`, verify panel status indicators)
- **No backlog reorganization needed** — single story addition to existing epic
- **No architectural review needed** — uses existing patterns and modules

**Success criteria:**
- Scan with KiCad connected shows components from both schematic and PCB
- Schematic-only components visible with "Not on PCB" status
- Field mismatches flagged with "PCB out of sync" indicator
- Graceful degradation when schematic files unavailable
- No regression in existing scan/verify/assign/push workflow
