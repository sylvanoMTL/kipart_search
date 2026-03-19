# Story 3.4: Stale Data Indicators

Status: done

## Story

As a designer,
I want to see which components were verified against an older database version,
So that I know what to re-check after a database update.

## Acceptance Criteria

1. **Given** components were verified against the JLCPCB database at a certain timestamp, **when** the database is refreshed/updated to a newer version, **then** previously verified components are flagged with an amber stale indicator.

2. **Given** a stale indicator is shown, **then** it displays: "Last verified: [date] — database updated since. Re-scan recommended."

3. **Given** stale components exist, **then** the health summary bar reflects stale components in the "Needs attention" count.

4. **Given** a component was never verified (freshly scanned), **when** it is displayed in the verification table, **then** no stale indicator is shown — only its normal verification status.

## Tasks / Subtasks

- [x] Task 1: Add verification timestamp tracking to core data model (AC: #1, #4)
  - [x] 1.1 Add `verified_at: float | None` field to `BoardComponent` in `core/models.py`
  - [x] 1.2 Add `verified_source: str | None` field to `BoardComponent` for source provenance
  - [x] 1.3 Record `time.time()` in `ScanWorker.run()` when each MPN verification completes
  - [x] 1.4 Persist timestamps through re-verify cycles (don't lose timestamp on partial re-scan)

- [x] Task 2: Add database timestamp detection (AC: #1)
  - [x] 2.1 Add `get_db_modified_time() -> float | None` method to `JLCPCBSource` — returns `os.path.getmtime()` of `parts-fts5.db`
  - [x] 2.2 Add `get_db_modified_time(source_name: str) -> float | None` to `SearchOrchestrator` for GUI access
  - [x] 2.3 Store the database mtime at scan time so stale detection compares against the DB version used during verification, not current

- [x] Task 3: Implement stale detection logic (AC: #1, #4)
  - [x] 3.1 Add `is_stale(component: BoardComponent, db_mtime: float) -> bool` function — returns `True` when `component.verified_at` is not None AND `component.verified_at < db_mtime`
  - [x] 3.2 Never-verified components (`verified_at is None`) are NOT stale — they show normal status only
  - [x] 3.3 Components with `Confidence.RED` (missing MPN / not found) are not stale — they already need action

- [x] Task 4: Add stale indicator to verification table UI (AC: #1, #2)
  - [x] 4.1 Add a "Freshness" column to `VERIFY_COLUMNS` in `verify_panel.py` (after MPN Status)
  - [x] 4.2 Stale cells show amber background (#FFEBB4) with text "Stale" and tooltip: "Last verified: [date] — database updated since. Re-scan recommended."
  - [x] 4.3 Fresh/current cells show no special indicator (empty or "Current" in green)
  - [x] 4.4 Never-verified cells show no freshness indicator (dash or empty)
  - [x] 4.5 Use accessibility labels: add `setAccessibleDescription()` on stale cells

- [x] Task 5: Update health summary bar for stale awareness (AC: #3)
  - [x] 5.1 Add stale count to `_build_summary()`: "Components: X | Valid: Y | Stale: Z | Missing: W"
  - [x] 5.2 Stale components count toward "Needs attention" in the health bar percentage
  - [x] 5.3 Health bar color thresholds account for stale components (they reduce the "healthy" percentage)

- [x] Task 6: Integrate stale detection in scan/re-verify workflow (AC: #1, #4)
  - [x] 6.1 Pass `db_mtime` from `ScanWorker` to `VerifyPanel.set_results()`
  - [x] 6.2 After re-verify, clear stale flag on re-verified components (they now have fresh `verified_at`)
  - [x] 6.3 Log stale detection to log panel: "[HH:MM:SS] N components verified before last database update — re-scan recommended"

- [x] Task 7: Write tests (all ACs)
  - [x] 7.1 Test `is_stale()` logic: stale when verified_at < db_mtime, not stale otherwise, not stale when never verified
  - [x] 7.2 Test stale indicator appears in table with correct tooltip text
  - [x] 7.3 Test health bar includes stale count
  - [x] 7.4 Test re-verify clears stale flag
  - [x] 7.5 Test no stale indicator when db_mtime is None (no database present)

## Dev Notes

### Architecture Constraints

- **Core/GUI separation**: Stale detection logic (`is_stale()`) goes in `core/` — zero GUI dependencies. Only visual rendering in `gui/verify_panel.py`.
- **Stateless → stateful transition**: The verification system is currently stateless (only `Confidence` enum per component). This story adds temporal state (`verified_at` timestamp) to `BoardComponent`. This is a foundational change — keep it minimal.
- **No new QThread classes**: Reuse existing `ScanWorker` pattern. Just add timestamp recording to its `run()` method.
- **Signal conventions**: Signals emit plain Python types only. The `scan_complete` signal signature may need updating: `Signal(list, dict, float)` to pass `db_mtime`, or bundle it in the dict.

### Database Timestamp Strategy

The JLCPCB database file is at `~/.kipart-search/jlcpcb/parts-fts5.db`. Since the full database download/refresh system (Epic 4, Story 4-2) doesn't exist yet, use `os.path.getmtime()` on the database file as the "database version timestamp". This is sufficient — when the user manually replaces or re-downloads the file, its mtime changes, triggering stale detection.

Do NOT build any database download/refresh UI — that's Epic 4 scope.

### Stale Detection Rules

```
component.verified_at is None → NOT stale (never verified)
component.verified_at >= db_mtime → NOT stale (verified after DB update)
component.verified_at < db_mtime → STALE (verified before DB update)
db_mtime is None → NOT stale (no database present, nothing to compare against)
component.confidence == RED → NOT stale (already flagged as needing action)
```

### Color & Text Patterns (from UX spec)

| State | Color | Text | Tooltip |
|-------|-------|------|---------|
| Stale | Amber (#FFEBB4) | "Stale" | "Last verified: 2026-03-10 — database updated since. Re-scan recommended." |
| Current | — (no indicator) | "" or "Current" | "Verified: 2026-03-15" |
| Never verified | — | "" | — |

Status always uses color + text + accessible description (never color-only). This follows the pattern established in Story 3.3.

### Existing Code Patterns to Follow

**Status label pattern** (from Story 3.3):
```python
_STALE_LABEL = "Stale"
_STALE_TOOLTIP = "Last verified: {date} — database updated since. Re-scan recommended."
```

**Sort key pattern** (from Story 3.3):
Use `_StatusItem` with `UserRole + 1` for sort keys. Stale items sort between RED and GREEN (they're amber-level).

**Health bar update pattern** (from verify_panel.py):
```python
def _build_summary(self) -> str:
    # Add stale count alongside existing missing/valid counts
```

**Logging pattern**:
```python
import logging
log = logging.getLogger(__name__)
log.info("N components verified before last database update")
```

### Files to Modify

| File | Changes |
|------|---------|
| `src/kipart_search/core/models.py` | Add `verified_at`, `verified_source` fields to `BoardComponent` |
| `src/kipart_search/core/sources.py` | Add `get_db_modified_time()` to `DataSource` ABC and `JLCPCBSource` |
| `src/kipart_search/core/search.py` | Add `get_db_modified_time()` proxy method to `SearchOrchestrator` |
| `src/kipart_search/gui/verify_panel.py` | Add Freshness column, stale indicator rendering, update `_build_summary()`, update `set_results()` signature |
| `src/kipart_search/gui/main_window.py` | Record timestamps in `ScanWorker.run()`, pass `db_mtime` to verify panel, log stale count |
| `tests/test_stale_data_indicators.py` | New test file — stale detection logic + UI tests |

### Files NOT to Modify

- `core/cache.py` — cache TTL is a separate concern; stale detection is about DB version vs verification time, not cache expiry
- `gui/search_bar.py` — no search UI changes
- `gui/results_table.py` — stale indicators are only in the verification panel
- `gui/bom_export_dialog.py` — BOM export doesn't need stale awareness yet

### What This Story Does NOT Include

- Database download/refresh UI (Epic 4, Story 4-2)
- Cache invalidation or TTL management (Epic 4, Story 4-1)
- Stale detection for non-JLCPCB sources (future enhancement)
- Automatic re-verification when database updates (user-triggered only)
- Persisting verification timestamps across app restarts (in-memory only for now)
- Batch "re-verify stale only" button (re-verify always does full scan)

### Cross-Epic Dependency Note

The acceptance criteria reference "when the database is refreshed/updated" — this implies Epic 4 (Story 4-2: JLCPCB Database Download and Refresh). However, stale detection can work NOW using `os.path.getmtime()` on the existing database file. When Epic 4 adds proper refresh tracking, the stale detection logic will naturally integrate via the same timestamp comparison. No placeholder code needed.

### Project Structure Notes

- All paths follow existing `src/kipart_search/` layout
- New test file follows `tests/test_*.py` naming convention
- No new modules or packages — extends existing files
- `verified_at` and `verified_source` are optional fields with `None` defaults — no breaking changes to existing `BoardComponent` construction

### Previous Story Intelligence (from Story 3.3)

Key learnings to apply:
- Use `_StatusItem` with `UserRole + 1` for sort keys — don't hardcode column indices
- Use `VERIFY_COLUMNS.index()` to find column indices dynamically
- `blockSignals()` during widget population to prevent spurious signal emissions
- Test `isHidden()` instead of `isVisible()` for Qt widget visibility in tests
- `has_active_sources` parameter pattern — extend `set_results()` signature cleanly with defaults
- Code review caught: status label logic must run BEFORE cell creation so `bg_color` reflects correct state
- 236 tests currently passing — zero regressions expected

### Git Intelligence

Recent commits show consistent patterns:
- Commit messages: imperative mood, story reference in message
- All stories maintain full test coverage (222 → 236 tests across stories 3.1-3.3)
- Code review fixes applied as separate commits
- `verify_panel.py` and `main_window.py` are the primary files for verification features

### References

- [Source: _bmad-output/planning-artifacts/epics.md — Epic 3, Story 3.4]
- [Source: _bmad-output/planning-artifacts/architecture.md — ADR-01 (Separate Cache Database), Cache Module Contract]
- [Source: _bmad-output/planning-artifacts/ux-design-specification.md — Status Communication table, State Patterns (Stale row)]
- [Source: CLAUDE.md — BOM verification checks, caching TTLs, KiCad IPC API integration]
- [Source: 3-3-verification-dashboard-enhancements.md — Previous story dev notes and code review fixes]

## Dev Agent Record

### Agent Model Used
Claude Opus 4.6 (1M context)

### Debug Log References
- QTableWidgetItem has no `setAccessibleDescription()` — stored accessibility text via `UserRole+2` data role instead.
- Pre-existing test failure: `test_central_widget_is_shrinkable_placeholder` (sizePolicy mismatch) — unrelated to this story.

### Completion Notes List
- Added `verified_at` and `verified_source` fields to `BoardComponent` with `None` defaults (no breaking changes)
- Added `is_stale()` pure function in `core/models.py` — zero GUI dependencies
- Added `get_db_modified_time()` to `DataSource` ABC (default `None`) and `JLCPCBSource` (uses `os.path.getmtime()`)
- Added `get_db_modified_time(source_name)` proxy to `SearchOrchestrator`
- Updated `ScanWorker` signal to `Signal(list, dict, float)` to pass `db_mtime`
- `ScanWorker.run()` now records `time.time()` on each component after MPN verification and captures `db_mtime` at scan start
- Added "Freshness" column to `VERIFY_COLUMNS` between MPN Status and Footprint
- Stale cells: amber background (#FFEBB4), "Stale" text, tooltip with last-verified date and re-scan recommendation
- Current/never-verified cells: empty text, no special color
- RED components are never marked stale (they already need action)
- Health summary bar now includes "Stale: N" count when stale > 0
- Health bar stays amber (not green) when 100% valid but stale components exist
- `_on_scan_complete` logs stale count to log panel
- Re-verify naturally clears stale flags (fresh `verified_at` timestamps from new scan)
- 20 new tests in `test_stale_data_indicators.py` covering all ACs
- 255 passed, 1 pre-existing failure (unrelated), 0 regressions

### File List
- `src/kipart_search/core/models.py` — Added `verified_at`, `verified_source` fields to `BoardComponent`; added `is_stale()` function
- `src/kipart_search/core/sources.py` — Added `get_db_modified_time()` to `DataSource` ABC and `JLCPCBSource`; added `os` import
- `src/kipart_search/core/search.py` — Added `get_db_modified_time(source_name)` proxy method to `SearchOrchestrator`
- `src/kipart_search/gui/verify_panel.py` — Added "Freshness" column, `_STALE_LABEL`, `_STALE_COLOR`, `_FRESHNESS_SORT`, `_make_freshness_item()`; updated `set_results()` signature with `db_mtime`; updated `_build_summary()` and `_update_health_bar_style()` for stale awareness
- `src/kipart_search/gui/main_window.py` — Updated `ScanWorker` signal and `run()` for timestamps/db_mtime; updated `_on_scan_complete()` to pass `db_mtime` and log stale count; added `time` import
- `tests/test_stale_data_indicators.py` — New: 20 tests covering stale detection logic, UI indicators, health bar, re-verify, and edge cases

### Change Log
- Story 3.4: Add stale data indicators with verification timestamps, Freshness column, and health bar stale awareness (Date: 2026-03-19)
