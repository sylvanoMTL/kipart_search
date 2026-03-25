# Sprint Change Proposal — User-Driven Verification Status

**Date:** 2026-03-25
**Triggered by:** New requirement from primary user (Sylvain)
**Change scope:** Minor — additive feature within existing epic structure

---

## Section 1: Issue Summary

### Problem Statement

The verification dashboard currently shows only **auto-check status** (green/amber/red) based on MPN presence and database verification. This reflects what the *tool* found — not what the *engineer* decided.

Real workflow gaps:
- A red component (MPN not in JLCPCB DB) might be a known-good TI part sourced from DigiKey. The engineer has no way to mark it "reviewed — OK."
- A green component might need attention for reasons the tool can't detect (e.g., approaching EOL, preferred alternate exists). No way to flag it.
- The health bar reports *tool confidence*, not *engineering sign-off*. A 100% green health bar means "all MPNs found in DB" — not "I've reviewed every component."

### Evidence

This is a new requirement from the primary user, emerging from real use of the scan → verify → assign workflow. The gap is: auto-check status ≠ engineer's verification decision.

---

## Section 2: Impact Analysis

### Epic Impact

**No existing epic is invalidated.** This is an additive feature that extends Epic 3 (Search & Verification Enhancements), which is already complete. The change adds a new story to a new or existing epic.

**Recommended approach:** Add a new **Epic 9: User Verification & Per-Project State** (or append as story 3.5 to Epic 3 if reopening completed epics is acceptable). Given Epic 3 is done and retrospected, a new epic is cleaner.

### Story Impact

No existing stories are affected. This is a new story that builds on:
- Story 3.3 (Verification Dashboard Enhancements) — the table, status colors, context menu, health bar
- Story 1.5 (Context Menus) — the right-click infrastructure
- Story 8.1 (platformdirs) — the data path convention for per-project state files

### Artifact Conflicts

| Artifact | Impact | Sections Affected |
|----------|--------|-------------------|
| **PRD** | Add FR36-FR39 for user verification status | §Functional Requirements (new subsection) |
| **Architecture** | Add `core/project_state.py` module, update data model | §Project Structure, §Data Flow |
| **UX Design** | Add user status column, context menu items, health bar logic | §Table Interaction Patterns, §Health Summary Bar, §Action Hierarchy |
| **Epics** | Add Epic 9 with one story (9.1) | New section at end |
| **Sprint Status** | Add Epic 9 entries | New block |

### Technical Impact

**Files to create:**
- `src/kipart_search/core/project_state.py` — load/save per-project verification state as JSON

**Files to modify:**
- `src/kipart_search/core/models.py` — add `UserVerificationStatus` enum
- `src/kipart_search/core/paths.py` — add `projects_dir()` helper
- `src/kipart_search/gui/verify_panel.py` — add "Review" column, context menu items, health bar logic update

**Risk:** Low. The user status is orthogonal to auto-check — it's a parallel data track, not a replacement. No existing logic changes, only additive.

---

## Section 3: Recommended Approach

**Selected: Option 1 — Direct Adjustment** (add new epic + story within current plan)

### Rationale

- **Scope is contained:** One new core module (`project_state.py`), one enum addition, one column + context menu extension, one path helper. No changes to existing logic.
- **No rollback needed:** Nothing already built conflicts with this addition.
- **No MVP redefinition:** This extends the verification workflow — it doesn't change what "done" means for existing features.
- **Effort estimate:** Low — ~1 story, moderate complexity
- **Risk level:** Low — additive, orthogonal to auto-check
- **Timeline impact:** None on Epic 8 (installer pipeline). This can be scheduled after Epic 8 or in parallel.

---

## Section 4: Detailed Change Proposals

### 4.1 PRD Changes

**Section:** §Functional Requirements → new subsection "User Verification Status"

**NEW (add after FR35):**

```
### User Verification Status

- **FR36:** Designer can set a manual verification status on any component via right-click context menu: Verified (green), Needs Attention (amber), Rejected (red), or None (clear)
- **FR37:** User verification status is persisted per-project in a local JSON file and survives across sessions
- **FR38:** The health bar reflects user verification decisions — components marked Verified by the user count as healthy regardless of auto-check status; components marked Rejected count as unhealthy regardless of auto-check status
- **FR39:** Both auto-check status and user status are visible in the verification table (auto-check column + user review column)
```

---

### 4.2 Architecture Changes

**Section:** §Project Structure → add new file

```
OLD:
│       ├── core/
│       │   ├── models.py
│       │   ├── sources.py
│       │   ├── cache.py
│       │   ├── search.py
│       │   ├── units.py
│       │   └── paths.py

NEW:
│       ├── core/
│       │   ├── models.py            # + UserVerificationStatus enum
│       │   ├── sources.py
│       │   ├── cache.py
│       │   ├── search.py
│       │   ├── units.py
│       │   ├── paths.py             # + projects_dir() helper
│       │   └── project_state.py     # [NEW] Per-project verification state (JSON persistence)
```

**Rationale:** `project_state.py` belongs in `core/` (zero GUI deps). It manages loading/saving a JSON dict keyed by component reference, storing user verification status. The file lives at `{data_dir}/projects/{project-hash}/verification-state.json`.

**Section:** §Data Model

**NEW addition to models.py:**

```python
class UserVerificationStatus(Enum):
    """Engineer's manual review decision — independent of auto-check."""
    NONE = "none"           # Not yet reviewed (default)
    VERIFIED = "verified"   # Engineer confirms: correct
    ATTENTION = "attention" # Engineer flags: come back to this
    REJECTED = "rejected"   # Engineer flags: wrong or incomplete
```

**Section:** §Data Flow

Add note: "User verification status flows: GUI context menu → `project_state.save()` → JSON file. On scan, `project_state.load()` restores user status and merges with auto-check results. The two status tracks are independent — neither overrides the other's stored value."

---

### 4.3 UX Design Changes

**Section:** §Table Interaction Patterns

**OLD:**
```
VERIFY_COLUMNS = ["Reference", "Value", "MPN", "MPN Status", "Footprint"]
```

**NEW:**
```
VERIFY_COLUMNS = ["Reference", "Value", "MPN", "MPN Status", "Review", "Footprint"]
```

The "Review" column shows the user's manual status:
- Empty cell (no icon/text) = not yet reviewed
- ✓ green background = "Verified"
- ⚠ amber background = "Needs Attention"
- ✗ red background = "Rejected"

**Section:** §Context Menu (right-click on verification table row)

**OLD:**
```
1. "Search for this component"
2. "Assign MPN"
3. "Manual Assign"
4. "Copy MPN"
```

**NEW:**
```
1. "Search for this component"
2. "Assign MPN"
3. "Manual Assign"
4. "Copy MPN"
   ---  (separator)
5. "Mark as Verified"       → sets Review to ✓ green
6. "Mark as Needs Attention" → sets Review to ⚠ amber
7. "Mark as Rejected"       → sets Review to ✗ red
8. "Clear Review Status"    → removes user status
```

Items 5-8 apply to multi-selection (Ctrl+click, Shift+click) so the engineer can mark multiple components at once.

**Section:** §Health Summary Bar

**OLD logic:**
- Health % = count of GREEN auto-check components / total PCB components

**NEW logic (user status takes precedence when set):**
- A component counts as "healthy" if:
  - User status is VERIFIED (regardless of auto-check), OR
  - User status is NONE and auto-check is GREEN
- A component counts as "unhealthy" if:
  - User status is REJECTED (regardless of auto-check), OR
  - User status is ATTENTION (regardless of auto-check), OR
  - User status is NONE and auto-check is RED/AMBER
- Health % = healthy / total PCB components

This means: user decisions override auto-check for health bar purposes, but the auto-check column still shows the tool's findings independently.

**Section:** §State Patterns

**NEW:**
```
| **Per-project state** | JSON file in data_dir/projects/{hash}/ | User verification decisions, persisted across sessions. Project identified by KiCad project file path hash. |
```

---

### 4.4 Epic Changes

**NEW Epic:**

```markdown
## Epic 9: User Verification & Per-Project State

Engineers can record their manual review decisions (Verified / Needs Attention / Rejected) on each component, independent of the tool's auto-check. These decisions persist across sessions in per-project state files and influence the health bar. This separates "what the tool found" from "what the engineer decided."

**FRs covered:** FR36, FR37, FR38, FR39
**NFRs addressed:** NFR11 (no data loss), NFR15 (platform-agnostic paths)

### Story 9.1: User Verification Status with Per-Project Persistence

As a designer,
I want to mark each component with my own review status (Verified / Needs Attention / Rejected) via right-click,
So that I can track my engineering decisions separately from the tool's auto-check and see my progress toward a fully-reviewed BOM.

**Acceptance Criteria:**

**Given** a board has been scanned and the verification table is displayed
**When** the designer right-clicks a component row
**Then** the context menu includes: "Mark as Verified", "Mark as Needs Attention", "Mark as Rejected", "Clear Review Status"

**Given** the designer selects "Mark as Verified" on component C12
**When** the context menu action executes
**Then** the "Review" column for C12 shows a green "Verified" indicator
**And** the health bar recalculates to include C12 as healthy (regardless of auto-check status)
**And** the change is immediately persisted to `{data_dir}/projects/{project-hash}/verification-state.json`
**And** the log panel shows: "[HH:MM:SS] Marked C12 as Verified"

**Given** the designer selects multiple components (Ctrl+click or Shift+click)
**When** they right-click and choose a review status
**Then** all selected components receive the chosen status
**And** the log shows one entry per component

**Given** the designer closes and reopens the app
**When** they scan the same KiCad project
**Then** previously saved user verification statuses are restored from the project state file
**And** the Review column and health bar reflect the restored statuses

**Given** a component's auto-check status is RED (MPN not found)
**When** the designer marks it as "Verified" (because they know the MPN is correct, just not in the local DB)
**Then** the auto-check column still shows RED/Not Found
**But** the Review column shows green/Verified
**And** the health bar counts this component as healthy

**Given** a component's auto-check status is GREEN
**When** the designer marks it as "Rejected" (e.g., wants to change to a different part)
**Then** the auto-check column still shows GREEN/Verified
**But** the Review column shows red/Rejected
**And** the health bar counts this component as unhealthy

**Given** the project state file does not exist (first scan of a new project)
**When** the verification table loads
**Then** all components have empty Review status (NONE)
**And** the health bar uses auto-check status only (existing behavior)

**Implementation Details:**

1. **`core/models.py`** — Add `UserVerificationStatus` enum (NONE, VERIFIED, ATTENTION, REJECTED)

2. **`core/paths.py`** — Add `projects_dir()` returning `{data_dir}/projects/`. Add `project_state_path(project_id: str)` returning `{projects_dir}/{project_id}/verification-state.json`.

3. **`core/project_state.py`** (NEW) — Functions:
   - `compute_project_id(kicad_project_path: str) -> str` — SHA256 hash of the normalized absolute path, truncated to 16 hex chars
   - `load_user_statuses(project_id: str) -> dict[str, UserVerificationStatus]` — reads JSON, returns {reference: status}. Returns empty dict if file doesn't exist.
   - `save_user_statuses(project_id: str, statuses: dict[str, UserVerificationStatus]) -> None` — atomic write (write to .tmp, rename)
   - Zero GUI dependencies. Pure dict-in, dict-out.

4. **`gui/verify_panel.py`** — Changes:
   - Add "Review" to `VERIFY_COLUMNS` (between "MPN Status" and "Footprint")
   - Store `_user_statuses: dict[str, UserVerificationStatus]` alongside `_mpn_statuses`
   - In `_build_context_menu()`: add separator + 4 review status actions after existing items
   - Support multi-row selection: actions apply to all selected rows
   - New method `set_user_status(references: list[str], status: UserVerificationStatus)` — updates table cells, recalculates health bar, calls `project_state.save_user_statuses()`
   - `get_health_percentage()` updated: user VERIFIED overrides auto-check for healthy count; user REJECTED/ATTENTION overrides for unhealthy count
   - `populate()` accepts optional `user_statuses` parameter to restore persisted state

5. **Project ID computation:** The KiCad project path is available from `kicad_bridge.py` (connected mode) or from the opened BOM file path (standalone mode). The hash ensures unique state per project without exposing file paths in the state directory name.

**Definition of Done:**
- Right-click context menu shows review status options
- Multi-select works for batch marking
- Review column displays correctly with color coding
- Health bar reflects user decisions
- State persists across app restarts for the same project
- Auto-check column is unchanged — both statuses coexist
- Tests: mark components, close/reopen, verify persistence; test health bar with mixed auto/user statuses
```

---

## Section 5: Implementation Handoff

### Change Scope: Minor

This is a self-contained additive feature. No existing code is modified in a breaking way. The dev team (solo developer) can implement it directly.

### Handoff

| Recipient | Responsibility |
|-----------|---------------|
| **Dev (Sylvain)** | Implement Story 9.1 |
| **SM** | Create story file, update sprint status after completion |

### Artifact Update Checklist

After approval, the following artifacts need updating:

- [ ] **PRD** — Add FR36-FR39 (User Verification Status subsection)
- [ ] **Architecture** — Add `project_state.py` to structure, `UserVerificationStatus` to data model, data flow note
- [ ] **UX Design** — Add Review column spec, context menu items, health bar logic
- [ ] **Epics** — Add Epic 9 with Story 9.1
- [ ] **Sprint Status** — Add `epic-9` and `9-1-user-verification-status` entries
- [ ] **Story file** — Create `9-1-user-verification-status.md` implementation artifact

### Success Criteria

- Engineer can mark and unmark components with review status via right-click
- Status persists across sessions for the same project
- Health bar reflects user decisions (user status takes precedence over auto-check when set)
- Both auto-check and user status are visible simultaneously
- No regression in existing verification, search, or assignment workflows
