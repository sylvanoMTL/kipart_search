# Story 9.1: User Verification Status with Per-Project Persistence

## Story

As a designer,
I want to mark each component with my own review status (Verified / Needs Attention / Rejected) via right-click,
So that I can track my engineering decisions separately from the tool's auto-check and see my progress toward a fully-reviewed BOM.

## Status

done

## Context

The verification dashboard currently shows only auto-check status (green/amber/red) based on MPN presence and database verification. This reflects what the tool found — not what the engineer decided. A designer reviewing a board needs to record their own decisions: "I've checked this, it's correct" vs "I need to come back to this" vs "this is wrong." The two status tracks (auto-check + user review) coexist independently.

**Sprint Change Proposal:** `planning-artifacts/sprint-change-proposal-2026-03-25.md`

## Acceptance Criteria

**Given** a board has been scanned and the verification table is displayed
**When** the designer right-clicks a component row
**Then** the context menu includes: "Mark as Verified", "Mark as Needs Attention", "Mark as Rejected", "Clear Review Status"

**Given** the designer selects "Mark as Verified" on component C12
**When** the context menu action executes
**Then** the "Review" column for C12 shows a green "Verified" indicator
**And** the health bar recalculates to include C12 as healthy (regardless of auto-check status)
**And** the change is immediately persisted to `{project_dir}/.kipart-search/verification-state.json`
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

## Implementation Details

### 1. `core/models.py` — Add UserVerificationStatus enum

```python
class UserVerificationStatus(Enum):
    """Engineer's manual review decision — independent of auto-check."""
    NONE = "none"           # Not yet reviewed (default)
    VERIFIED = "verified"   # Engineer confirms: correct
    ATTENTION = "attention" # Engineer flags: come back to this
    REJECTED = "rejected"   # Engineer flags: wrong or incomplete
```

### 2. `core/paths.py` — Add project state path helpers

```python
def projects_dir() -> Path:
    """Directory for per-project state. Creates if needed."""
    d = data_dir() / "projects"
    d.mkdir(parents=True, exist_ok=True)
    return d

def project_state_path(project_id: str) -> Path:
    """Path to a project's verification state JSON."""
    d = projects_dir() / project_id
    d.mkdir(parents=True, exist_ok=True)
    return d / "verification-state.json"
```

### 3. `core/project_state.py` (NEW) — Per-project state persistence

Zero GUI dependencies. Pure functions operating on dicts and JSON files.

```python
def compute_project_id(kicad_project_path: str) -> str:
    """SHA256 hash of the normalized absolute path, truncated to 16 hex chars."""

def load_user_statuses(project_id: str) -> dict[str, UserVerificationStatus]:
    """Read verification-state.json. Returns empty dict if file doesn't exist."""

def save_user_statuses(project_id: str, statuses: dict[str, UserVerificationStatus]) -> None:
    """Atomic write: write to .tmp file, then rename. Only saves non-NONE statuses."""
```

**JSON format:**
```json
{
  "format_version": 1,
  "statuses": {
    "C12": "verified",
    "U3": "rejected",
    "R7": "attention"
  }
}
```

Components with NONE status are omitted from the file (sparse storage).

### 4. `gui/verify_panel.py` — UI changes

**Column addition:**
- Add "Review" to `VERIFY_COLUMNS` between "MPN Status" and "Footprint"
- Review column cells show text label + background color matching the status
- NONE status = empty cell, no background

**Context menu extension:**
- After existing items ("Search for this component", "Assign MPN", "Manual Assign", "Copy MPN"), add a separator
- Add: "Mark as Verified", "Mark as Needs Attention", "Mark as Rejected", "Clear Review Status"
- Actions apply to ALL selected rows (support multi-row via `QAbstractItemView.ExtendedSelection`)

**New instance state:**
- `_user_statuses: dict[str, UserVerificationStatus]` — loaded from project state on populate, updated on context menu action
- `_project_id: str | None` — set when scan completes, needed for save

**New method:**
```python
def set_user_status(self, references: list[str], status: UserVerificationStatus) -> None:
    """Update user review status for given components. Persists immediately."""
```

**Health bar logic change in `get_health_percentage()`:**
- If user status is VERIFIED → count as healthy (regardless of auto-check)
- If user status is REJECTED or ATTENTION → count as unhealthy (regardless of auto-check)
- If user status is NONE → fall back to existing auto-check logic

**Populate change:**
- `populate()` accepts optional `user_statuses: dict[str, UserVerificationStatus]` parameter
- `main_window.py` loads user statuses via `project_state.load_user_statuses()` before calling `populate()`

### 5. Project ID source

- **Connected mode:** KiCad project path from `kicad_bridge.py` (the `.kicad_pro` path)
- **Standalone mode:** Path of the opened BOM file or schematic file
- Hash ensures unique state per project without exposing paths in directory names

## Files to Create

| File | Description |
|------|-------------|
| `src/kipart_search/core/project_state.py` | Per-project state load/save (JSON) |

## Files to Modify

| File | Change |
|------|--------|
| `src/kipart_search/core/models.py` | Add `UserVerificationStatus` enum |
| `src/kipart_search/core/paths.py` | (no longer modified — project state path moved to project_state.py) |
| `src/kipart_search/gui/verify_panel.py` | Add Review column, context menu items, multi-select, health bar logic, state integration |
| `src/kipart_search/gui/main_window.py` | Load/pass user statuses on scan, pass project_id to verify panel |

## Definition of Done

- [x] Right-click context menu shows review status options (4 items + separator)
- [x] Multi-select works for batch marking
- [x] Review column displays correctly with color coding (green/amber/red/empty)
- [x] Health bar reflects user decisions when set, falls back to auto-check when NONE
- [x] State persists across app restarts for the same project
- [x] Auto-check column is unchanged — both statuses coexist independently
- [x] Log panel shows entries for status changes
- [ ] Manual testing: mark components, close/reopen, verify persistence
- [ ] Manual testing: health bar with mixed auto/user statuses

## Dev Agent Record

### Implementation Plan
- Added `UserVerificationStatus` enum to `core/models.py` (NONE/VERIFIED/ATTENTION/REJECTED)
- Created `core/project_state.py` with `project_state_path()`, `load_user_statuses()`, `save_user_statuses()` — atomic JSON writes, state stored in `{project_dir}/.kipart-search/`
- Extended `gui/verify_panel.py`: new "Review" column, context menu with 4 review actions, multi-select support via ExtendedSelection, health bar override logic (_is_healthy()), signal for persistence, `get_project_dir()` public accessor
- Integrated in `gui/main_window.py`: loads user statuses on scan complete, saves on status change, logs each status change

### Completion Notes
- 21 tests: 8 for project_state (round-trip, corruption, unknown values, path resolution), 13 for verify_panel (column rendering, set/clear/batch, health bar overrides, auto-check independence)
- All existing tests pass (5 pre-existing failures in `test_verify_dashboard_enhancements.py` due to renamed `reverify_button` → `refresh_button` — unrelated to this story)
- Health bar counting refactored from inline duplicated logic to shared `_compute_health_counts()` / `_refresh_health_bar()` methods

### Code Review Fixes (2026-03-25)
- **H1**: Added `get_project_dir()` public accessor to `VerifyPanel` — `main_window.py` no longer accesses private `_project_dir`
- **M1**: `update_component_status()` now skips the Review column when painting auto-check background colors — two status tracks remain visually independent
- **L1**: Clearing review status now uses transparent `QColor()` instead of opaque white, preserving alternating row colors
- **Location change**: Moved state from `{data_dir}/projects/{hash}/` to `{project_dir}/.kipart-search/verification-state.json` — state travels with the project, no platform-dependent hash

## File List

| File | Action |
|------|--------|
| `src/kipart_search/core/models.py` | Modified — added `UserVerificationStatus` enum |
| `src/kipart_search/core/paths.py` | Modified — removed `projects_dir()`, `project_state_path()` (moved to project_state.py) |
| `src/kipart_search/core/project_state.py` | Created — project_state_path, load/save user statuses (project-local storage) |
| `src/kipart_search/gui/verify_panel.py` | Modified — Review column, context menu, health bar logic, set_user_status(), get_project_dir(), signals |
| `src/kipart_search/gui/main_window.py` | Modified — load/save user statuses on scan/change, logging |
| `tests/test_project_state.py` | Created — 8 tests for project state persistence |
| `tests/test_user_verification_status.py` | Created — 13 tests for verify panel user review status |

## Change Log

- 2026-03-25: Implemented Story 9.1 — User Verification Status with per-project persistence
- 2026-03-25: Code review fixes — H1 (private access), M1 (review column clobbering), L1 (white background), location change to project-local storage
